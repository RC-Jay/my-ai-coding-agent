"""
Session-level token budget tracker.
Accumulates usage across all run_agent() calls and warns/stops when limits are hit.
"""

from .display import console

_WARN_THRESHOLD = 0.75
_MAX_TURNS = 50


class Budget:
    """Tracks cumulative token usage and turn count across a session."""

    def __init__(self, max_tokens: int = 100_000, max_turns: int = _MAX_TURNS):
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        self.total_tokens = 0
        self.turns = 0

    def record_turn(self, usage: dict) -> None:
        """Call after each agent turn with the provider's usage dict."""
        self.total_tokens += usage.get("Total tokens", 0)
        self.turns += 1

    @property
    def tokens_exceeded(self) -> bool:
        return self.total_tokens >= self.max_tokens

    @property
    def turns_exceeded(self) -> bool:
        return self.turns >= self.max_turns

    def warn_if_needed(self) -> None:
        """Print a warning if token usage is approaching the limit."""
        if not self.max_tokens:
            return
        ratio = self.total_tokens / self.max_tokens
        if ratio >= 1.0:
            console.print(
                f"\n[bold red]✗ Token budget exhausted "
                f"({self.total_tokens:,} / {self.max_tokens:,} tokens).[/bold red]"
            )
        elif ratio >= _WARN_THRESHOLD:
            console.print(
                f"\n[yellow]⚠ Token budget {ratio * 100:.0f}% used "
                f"({self.total_tokens:,} / {self.max_tokens:,}).[/yellow]"
            )

    def summary(self) -> str:
        return (
            f"Session: {self.turns} turn(s)  •  "
            f"{self.total_tokens:,} tokens used"
        )
