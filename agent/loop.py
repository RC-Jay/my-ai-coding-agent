from .providers.base import BaseProvider, ToolCall
from .tools import TOOL_MAP

MAX_ITERATIONS = 20


def run_agent(provider: BaseProvider, user_message: str, verbose: bool = False) -> None:
    """
    Run one turn of the agent.
    Sends user_message to the provider, executes any tool calls, and loops
    until the model returns a plain text response or MAX_ITERATIONS is reached.
    """
    response = provider.send_message(user_message)

    iterations = 0
    while response.tool_calls:
        if iterations >= MAX_ITERATIONS:
            print(f"\n[Agent] Reached maximum tool call iterations ({MAX_ITERATIONS}). Stopping.")
            break

        results: list[tuple[ToolCall, str]] = []

        for tc in response.tool_calls:
            fn = TOOL_MAP.get(tc.name)
            result = fn(**tc.args) if fn else f"Unknown tool: {tc.name}"

            # Always show which tool is being called so the user knows it's active
            print(f"\n  → {tc.name}({', '.join(f'{k}={repr(v)[:50]}' for k, v in tc.args.items())})")
            if verbose:
                print(f"    {str(result)[:300]}{'...' if len(str(result)) > 300 else ''}")

            results.append((tc, str(result)))

        iterations += 1
        response = provider.send_tool_results(results)

    if response.text:
        print(f"\nAgent: {response.text}")

    if verbose and response.usage:
        print()
        for label, value in response.usage.items():
            print(f"{label}: {value}")
