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
