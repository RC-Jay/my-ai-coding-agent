from .display import AgentDisplay, console
from .providers.base import BaseProvider, ToolCall
from .tools import TOOL_MAP

MAX_ITERATIONS = 20


def run_agent(provider: BaseProvider, user_message: str, verbose: bool = False) -> None:
    """
    Run one turn of the agent with a live status display.
    Sends user_message to the provider, executes any tool calls, and loops
    until the model returns a plain text response or MAX_ITERATIONS is reached.
    """
    display = AgentDisplay()

    with display:
        response = provider.send_message(user_message)

        iterations = 0
        while response.tool_calls:
            if iterations >= MAX_ITERATIONS:
                display.log(f"[yellow]⚠ Reached maximum tool call iterations ({MAX_ITERATIONS}). Stopping.[/yellow]")
                break

            results: list[tuple[ToolCall, str]] = []

            for tc in response.tool_calls:
                fn = TOOL_MAP.get(tc.name)

                # Show the active tool call in the status line
                args_preview = ", ".join(f"{k}={repr(v)[:40]}" for k, v in tc.args.items())
                display.update(f"{tc.name}({args_preview})")

                result = fn(**tc.args) if fn else f"Unknown tool: {tc.name}"

                if verbose:
                    display.log(f"  [dim cyan]→ {tc.name}({args_preview})[/dim cyan]")
                    display.log(f"  [dim]{str(result)[:300]}{'...' if len(str(result)) > 300 else ''}[/dim]")

                results.append((tc, str(result)))

            iterations += 1
            display.update("Thinking")
            response = provider.send_tool_results(results)

    # Live display has exited — safe to print the final response
    if response.text:
        display.show_response(response.text, response.usage, verbose)
