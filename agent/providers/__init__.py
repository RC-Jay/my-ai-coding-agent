from .azure_openai import AzureOpenAIProvider
from .base import BaseProvider, ProviderResponse, ToolCall
from .gemini import GeminiProvider

__all__ = ["BaseProvider", "ProviderResponse", "ToolCall", "GeminiProvider", "AzureOpenAIProvider", "create_provider"]


def create_provider(config: dict, tools: list, system_instruction: str = "") -> BaseProvider:
    """Factory function — returns the correct provider based on config."""
    provider_id = config["provider"]

    if provider_id == "gemini":
        return GeminiProvider(
            api_key=config["api_key"],
            model=config["model"],
            tools=tools,
            system_instruction=system_instruction,
        )

    if provider_id == "azure_openai":
        return AzureOpenAIProvider(
            api_key=config["api_key"],
            endpoint=config["endpoint"],
            deployment=config["deployment"],
            tools=tools,
            system_instruction=system_instruction,
        )

    raise ValueError(f"Unknown provider: {provider_id!r}")
