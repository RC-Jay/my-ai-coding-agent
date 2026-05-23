import time

from google import genai
from google.genai import errors, types

from .base import BaseProvider, ProviderResponse, ToolCall

_MAX_RETRIES = 3


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str, tools: list, system_instruction: str = ""):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.tools = tools
        self.system_instruction = system_instruction
        self.history: list[types.Content] = []
        # Number of entries at the start of history that are injected context
        # (not real conversation turns).  export_history() skips these.
        self._context_offset: int = 0

    def send_message(self, user_message: str) -> ProviderResponse:
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )
        return self._generate()

    def send_tool_results(self, results: list[tuple[ToolCall, str]]) -> ProviderResponse:
        tool_parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    name=tc.name,
                    response={"output": result},
                )
            )
            for tc, result in results
        ]
        self.history.append(types.Content(role="user", parts=tool_parts))
        return self._generate()

    # ── Memory interface ──────────────────────────────────────────────────────

    def export_history(self) -> list[dict]:
        """Convert self.history (Gemini types) to neutral JSON format."""
        neutral: list[dict] = []
        for content in self.history[self._context_offset:]:
            role = "user" if content.role == "user" else "model"
            parts: list[dict] = []
            for part in content.parts:
                if part.text:
                    parts.append({"type": "text", "text": part.text})
                elif part.function_call:
                    parts.append({
                        "type": "tool_call",
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args),
                        "id": "",
                    })
                elif part.function_response:
                    resp = part.function_response.response
                    result = (
                        resp.get("output", str(resp))
                        if isinstance(resp, dict)
                        else str(resp)
                    )
                    parts.append({
                        "type": "tool_result",
                        "name": part.function_response.name,
                        "result": result,
                        "id": "",
                    })
            if parts:
                neutral.append({"role": role, "parts": parts})
        return neutral

    def load_context(self, summary: str | None, turns: list[dict]) -> None:
        """Restore conversation from neutral format, optionally injecting a summary."""
        history: list[types.Content] = []

        if summary:
            history.append(types.Content(
                role="user",
                parts=[types.Part(text=f"[Context from previous session]\n{summary}")],
            ))
            history.append(types.Content(
                role="model",
                parts=[types.Part(text=(
                    "Understood. I have context from our previous session "
                    "and will continue accordingly."
                ))],
            ))

        self._context_offset = len(history)  # everything before this is injected

        for entry in turns:
            role = entry.get("role", "user")
            parts: list[types.Part] = []
            for p in entry.get("parts", []):
                ptype = p.get("type")
                if ptype == "text":
                    parts.append(types.Part(text=p["text"]))
                elif ptype == "tool_call":
                    parts.append(types.Part(
                        function_call=types.FunctionCall(
                            name=p["name"],
                            args=p.get("args", {}),
                        )
                    ))
                elif ptype == "tool_result":
                    parts.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=p["name"],
                            response={"output": p.get("result", "")},
                        )
                    ))
            if parts:
                history.append(types.Content(role=role, parts=parts))

        self.history = history

    def one_shot(self, prompt: str) -> str:
        """Send a single prompt without touching conversation history."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                ),
            )
            return response.text or ""
        except Exception as e:
            return f"[Summary generation failed: {e}]"

    # ── Core generation ───────────────────────────────────────────────────────

    def _generate(self) -> ProviderResponse:
        config = types.GenerateContentConfig(
            tools=self.tools,
            system_instruction=self.system_instruction,
        )

        for attempt in range(_MAX_RETRIES):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.history,
                    config=config,
                )
                break
            except errors.ClientError as e:
                if e.code == 429 and attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt * 10  # 10s, 20s, 40s
                    print(f"\n[Rate limited] Retrying in {wait}s... (attempt {attempt + 1}/{_MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError("Exceeded maximum retries due to rate limiting.")

        self.history.append(response.candidates[0].content)

        tool_calls = [
            ToolCall(name=part.function_call.name, args=dict(part.function_call.args))
            for part in response.candidates[0].content.parts
            if part.function_call
        ]

        usage = {}
        if response.usage_metadata:
            usage = {
                "Prompt tokens":   response.usage_metadata.prompt_token_count,
                "Thinking tokens": response.usage_metadata.thoughts_token_count,
                "Response tokens": response.usage_metadata.candidates_token_count,
                "Total tokens":    response.usage_metadata.total_token_count,
            }

        return ProviderResponse(
            text=response.text if not tool_calls else None,
            tool_calls=tool_calls,
            usage=usage,
        )
