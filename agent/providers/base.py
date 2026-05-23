from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = ""  # used by OpenAI for tool_call_id


@dataclass
class ProviderResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """Common interface for all LLM providers. Each provider manages its own conversation history."""

    @abstractmethod
    def send_message(self, user_message: str) -> ProviderResponse:
        """Add a user message to history and return the model's response."""
        ...

    @abstractmethod
    def send_tool_results(self, results: list[tuple[ToolCall, str]]) -> ProviderResponse:
        """Add tool results to history and return the model's next response."""
        ...

    @abstractmethod
    def export_history(self) -> list[dict]:
        """
        Export conversation history in neutral parts-based JSON format.
        Injected context (summary injection, system messages) is excluded —
        only real conversation turns are returned.
        """
        ...

    @abstractmethod
    def load_context(self, summary: str | None, turns: list[dict]) -> None:
        """
        Pre-populate conversation history from persisted context.

        summary — LLM-generated summary of older turns; injected as an opening
                  user/model exchange so the model has historical context.
        turns   — Recent turns in neutral format to restore verbatim.
        """
        ...

    @abstractmethod
    def one_shot(self, prompt: str) -> str:
        """
        Send a single prompt without affecting the main conversation history.
        Used for tasks like generating a rolling session summary.
        """
        ...
