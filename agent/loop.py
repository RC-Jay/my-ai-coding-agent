import time
from pathlib import Path

from google import genai
from google.genai import errors, types

from .prompts import system_prompt
from .tools import TOOL_MAP, TOOLS


def generate_with_retry(
    client: genai.Client,
    contents: list,
    config: types.GenerateContentConfig,
    retries: int = 3,
):
    """Call generate_content with exponential backoff on rate limit errors."""
    for attempt in range(retries):
        try:
            return client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config,
            )
        except errors.ClientError as e:
            if e.code == 429:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s
                print(f"\n[Rate limited] Retrying in {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Exceeded maximum retries due to rate limiting.")


def run_agent(
    client: genai.Client,
    contents: list,
    project_dir: Path,
    verbose: bool = False,
) -> None:
    """Run one turn of the agent, modifying contents in place to preserve history."""
    config = types.GenerateContentConfig(
        tools=TOOLS,
        system_instruction=system_prompt(project_dir),
    )

    while True:
        response = generate_with_retry(client, contents, config)
        contents.append(response.candidates[0].content)

        function_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if part.function_call
        ]

        if not function_calls:
            print(f"\nAgent: {response.text}")
            break

        tool_parts = []
        for fc in function_calls:
            fn = TOOL_MAP.get(fc.name)
            result = fn(**dict(fc.args)) if fn else f"Unknown tool: {fc.name}"

            if verbose:
                print(f"\n[Tool] {fc.name}({dict(fc.args)})")
                print(f"[Result] {str(result)[:300]}{'...' if len(str(result)) > 300 else ''}")

            tool_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"output": result},
                    )
                )
            )

        contents.append(types.Content(role="user", parts=tool_parts))

    if verbose:
        usage = response.usage_metadata
        print(f"\nPrompt tokens:   {usage.prompt_token_count}")
        print(f"Thinking tokens: {usage.thoughts_token_count}")
        print(f"Response tokens: {usage.candidates_token_count}")
        print(f"Total tokens:    {usage.total_token_count}")
