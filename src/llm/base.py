from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers (Gemini, OpenAI, Claude, etc.)."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        model_name: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> Tuple[str, int, int, int]:
        """
        Generate text completion.
        
        Returns:
            Tuple of (text_output, input_tokens, output_tokens, total_tokens)
        """
        pass
