from typing import Dict
from src.llm.base import BaseLLMProvider
from src.llm.providers.gemini_provider import GeminiProvider
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.claude_provider import ClaudeProvider

# Registered providers registry
_PROVIDER_REGISTRY: Dict[str, BaseLLMProvider] = {
    "gemini": GeminiProvider(),
    "openai": OpenAIProvider(),
    "claude": ClaudeProvider()
}


def get_provider_instance(provider_name: str) -> BaseLLMProvider:
    """Retrieve the singleton instance for a given LLM provider."""
    normalized = provider_name.lower().strip()
    if normalized in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[normalized]
    raise ValueError(
        f"Unsupported LLM provider '{provider_name}'. "
        f"Available providers: {list(_PROVIDER_REGISTRY.keys())}"
    )


def register_provider(provider_name: str, instance: BaseLLMProvider):
    """Register a new LLM provider instance dynamically."""
    _PROVIDER_REGISTRY[provider_name.lower().strip()] = instance
