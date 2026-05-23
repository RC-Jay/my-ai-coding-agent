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
