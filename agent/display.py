import time

from rich.console import Console, ConsoleOptions, RenderResult
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

console = Console()


class _StatusLine:
    """
    Custom rich renderable that displays a spinner, current status, and elapsed time.
    rich.Live calls __rich_console__ on every refresh tick, so elapsed time updates live.
    """

    def __init__(self) -> None:
        self._start = time.time()
        self._spinner = Spinner("dots", style="bold cyan")
        self.status = "Thinking"

    def elapsed(self) -> float:
        return time.time() - self._start

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        grid = Table.grid(padding=(0, 1))
        grid.add_row(
            self._spinner,
            Text(self.status, style="bold white"),
            Text(f"{self.elapsed():.1f}s", style="dim"),
        )
        yield grid


class AgentDisplay:
    """
    Live terminal display for the agent loop.

    Shows a spinner with the current status and elapsed time while the agent
    is working. Prints tool calls above the spinner in verbose mode.
    After the loop ends, prints the final response and usage stats.
    """

    def __init__(self) -> None:
        self._status_line = _StatusLine()
        self._live = Live(self._status_line, refresh_per_second=10, console=console)

    def __enter__(self) -> "AgentDisplay":
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        self._live.__exit__(*args)

    def update(self, status: str) -> None:
        """Update the status message shown next to the spinner."""
        self._status_line.status = status

    def log(self, message: str) -> None:
        """Print a line above the live display (safe to call inside the Live context)."""
        self._live.console.print(message)

    def elapsed(self) -> float:
        return self._status_line.elapsed()

    def show_response(self, text: str, usage: dict, verbose: bool = False) -> None:
        """Print the agent's final response and optionally the token usage."""
        console.print(f"\n[bold green]Agent:[/bold green] {text}")

        if verbose and usage:
            usage_str = "  •  ".join(f"{k}: {v:,}" for k, v in usage.items())
            console.print(f"\n[dim]{usage_str}  •  {self.elapsed():.1f}s[/dim]")
        else:
            console.print(f"[dim]{self.elapsed():.1f}s[/dim]")
