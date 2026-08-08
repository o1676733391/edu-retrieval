import os
from typing import Optional, Tuple, Dict, Any
from src import config
from src.llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API Provider."""

    def __init__(self):
        super().__init__("openai")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        model_name: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> Tuple[str, int, int, int]:
        import openai

        api_key = config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured in the environment.")

        client = openai.OpenAI(api_key=api_key)
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        response = client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""

        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

        return text, input_tokens, output_tokens, total_tokens
