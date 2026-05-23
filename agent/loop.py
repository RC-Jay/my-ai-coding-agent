from .providers.base import BaseProvider, ToolCall
from .tools import TOOL_MAP


def run_agent(provider: BaseProvider, user_message: str, verbose: bool = False) -> None:
    """
    Run one turn of the agent.
    Sends user_message to the provider, executes any tool calls, and loops
    until the model returns a plain text response.
    """
    response = provider.send_message(user_message)

    while response.tool_calls:
        results: list[tuple[ToolCall, str]] = []

        for tc in response.tool_calls:
            fn = TOOL_MAP.get(tc.name)
            result = fn(**tc.args) if fn else f"Unknown tool: {tc.name}"

            if verbose:
                print(f"\n[Tool] {tc.name}({tc.args})")
                print(f"[Result] {str(result)[:300]}{'...' if len(str(result)) > 300 else ''}")

            results.append((tc, str(result)))

        response = provider.send_tool_results(results)

    if response.text:
        print(f"\nAgent: {response.text}")

    if verbose and response.usage:
        print()
        for label, value in response.usage.items():
            print(f"{label}: {value}")
