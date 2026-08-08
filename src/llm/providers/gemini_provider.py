from typing import Optional, Tuple, Dict, Any
from src import config
from src.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider supporting Google AI Studio and Vertex AI."""

    def __init__(self):
        super().__init__("gemini")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        model_name: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> Tuple[str, int, int, int]:
        from google import genai
        from google.genai import types

        if config.USE_VERTEXAI:
            ai_client = genai.Client(
                vertexai=True,
                project=config.GOOGLE_CLOUD_PROJECT,
                location=config.GOOGLE_CLOUD_LOCATION
            )
        else:
            if not config.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not configured in the environment.")
            ai_client = genai.Client(api_key=config.GEMINI_API_KEY)

        config_params: Dict[str, Any] = {}
        if system_instruction:
            config_params["system_instruction"] = system_instruction
        if temperature is not None:
            config_params["temperature"] = temperature
        if max_tokens is not None:
            config_params["max_output_tokens"] = max_tokens

        response = ai_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_params) if config_params else None
        )

        text = response.text or ""
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or (input_tokens + output_tokens)
        else:
            input_tokens = max(1, len((system_instruction or "") + prompt) // 4)
            output_tokens = max(1, len(text) // 4)
            total_tokens = input_tokens + output_tokens

        return text, input_tokens, output_tokens, total_tokens
