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
        self.openai_tools = [function_to_openai_schema(fn) for fn in tools]
        self.history: list[dict] = []

        if system_instruction:
            self.history.append({"role": "system", "content": system_instruction})

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
