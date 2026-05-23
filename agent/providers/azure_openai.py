import json
import time

from openai import AzureOpenAI, RateLimitError

from .base import BaseProvider, ProviderResponse, ToolCall
from .utils import function_to_openai_schema

_MAX_RETRIES = 3
_API_VERSION = "2024-10-21"


class AzureOpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, endpoint: str, deployment: str, tools: list, system_instruction: str = ""):
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=_API_VERSION,
        )
        self.deployment = deployment
        self.system_instruction = system_instruction
        self.openai_tools = [function_to_openai_schema(fn) for fn in tools]
        self.history: list[dict] = []

        if system_instruction:
            self.history.append({"role": "system", "content": system_instruction})

        # Number of entries at the start of history that are injected context
        # (system message + any summary injection).  export_history() skips these.
        self._context_offset: int = len(self.history)

    def send_message(self, user_message: str) -> ProviderResponse:
        self.history.append({"role": "user", "content": user_message})
        return self._generate()

    def send_tool_results(self, results: list[tuple[ToolCall, str]]) -> ProviderResponse:
        for tc, result in results:
            self.history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        return self._generate()

    # ── Memory interface ──────────────────────────────────────────────────────

    def export_history(self) -> list[dict]:
        """Convert self.history (OpenAI format) to neutral JSON format."""
        # Build tool_call_id → name map so role="tool" entries can record the name
        id_to_name: dict[str, str] = {}
        for entry in self.history[self._context_offset:]:
            if entry.get("role") == "assistant" and entry.get("tool_calls"):
                for tc in entry["tool_calls"]:
                    id_to_name[tc["id"]] = tc["function"]["name"]

        neutral: list[dict] = []
        for entry in self.history[self._context_offset:]:
            role = entry.get("role")

            if role == "user":
                neutral.append({
                    "role": "user",
                    "parts": [{"type": "text", "text": entry.get("content", "")}],
                })

            elif role == "assistant":
                parts: list[dict] = []
                if entry.get("content"):
                    parts.append({"type": "text", "text": entry["content"]})
                for tc in entry.get("tool_calls", []):
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        args = {}
                    parts.append({
                        "type": "tool_call",
                        "name": tc["function"]["name"],
                        "args": args,
                        "id": tc["id"],
                    })
                if parts:
                    neutral.append({"role": "model", "parts": parts})

            elif role == "tool":
                tool_id = entry.get("tool_call_id", "")
                neutral.append({
                    "role": "user",
                    "parts": [{
                        "type": "tool_result",
                        "name": id_to_name.get(tool_id, ""),
                        "result": entry.get("content", ""),
                        "id": tool_id,
                    }],
                })

        return neutral

    def load_context(self, summary: str | None, turns: list[dict]) -> None:
        """Restore conversation from neutral format, optionally injecting a summary."""
        history: list[dict] = []

        if self.system_instruction:
            history.append({"role": "system", "content": self.system_instruction})

        if summary:
            history.append({
                "role": "user",
                "content": f"[Context from previous session]\n{summary}",
            })
            history.append({
                "role": "assistant",
                "content": (
                    "Understood. I have context from our previous session "
                    "and will continue accordingly."
                ),
            })

        self._context_offset = len(history)  # everything before this is injected

        for entry in turns:
            role = entry.get("role")
            parts = entry.get("parts", [])

            if role == "user":
                text_parts = [p for p in parts if p.get("type") == "text"]
                tool_result_parts = [p for p in parts if p.get("type") == "tool_result"]

                if text_parts:
                    history.append({"role": "user", "content": text_parts[0]["text"]})

                for p in tool_result_parts:
                    history.append({
                        "role": "tool",
                        "tool_call_id": p.get("id", ""),
                        "content": p.get("result", ""),
                    })

            elif role == "model":
                text_parts = [p for p in parts if p.get("type") == "text"]
                call_parts = [p for p in parts if p.get("type") == "tool_call"]

                entry_dict: dict = {
                    "role": "assistant",
                    "content": text_parts[0]["text"] if text_parts else None,
                }
                if call_parts:
                    entry_dict["tool_calls"] = [
                        {
                            "id": p.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": p["name"],
                                "arguments": json.dumps(p.get("args", {})),
                            },
                        }
                        for p in call_parts
                    ]
                history.append(entry_dict)

        self.history = history

    def one_shot(self, prompt: str) -> str:
        """Send a single prompt without touching conversation history."""
        messages: list[dict] = []
        if self.system_instruction:
            messages.append({"role": "system", "content": self.system_instruction})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[Summary generation failed: {e}]"

    # ── Core generation ───────────────────────────────────────────────────────

    def _generate(self) -> ProviderResponse:
        for attempt in range(_MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=self.history,
                    tools=self.openai_tools or None,
                )
                break
            except RateLimitError:
                if attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt * 10
                    print(f"\n[Rate limited] Retrying in {wait}s... (attempt {attempt + 1}/{_MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError("Exceeded maximum retries due to rate limiting.")

        message = response.choices[0].message

        # Store assistant message in history (serialize tool_calls if present)
        assistant_entry: dict = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
        self.history.append(assistant_entry)

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCall(
                    name=tc.function.name,
                    args=json.loads(tc.function.arguments),
                    id=tc.id,
                ))

        usage = {}
        if response.usage:
            usage = {
                "Prompt tokens":   response.usage.prompt_tokens,
                "Response tokens": response.usage.completion_tokens,
                "Total tokens":    response.usage.total_tokens,
            }

        return ProviderResponse(
            text=message.content,
            tool_calls=tool_calls,
            usage=usage,
        )
