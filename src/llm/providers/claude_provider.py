import os
import requests
from typing import Optional, Tuple, Dict, Any
from src import config
from src.llm.base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API Provider with official SDK and direct REST fallback."""

    def __init__(self):
        super().__init__("claude")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str],
        model_name: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> Tuple[str, int, int, int]:
        api_key = config.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("CLAUDE_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY (or CLAUDE_API_KEY) is not configured in the environment.")

        max_tok = max_tokens or 4096

        # Try official anthropic SDK first if installed
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "max_tokens": max_tok,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            if system_instruction:
                kwargs["system"] = system_instruction

            response = client.messages.create(**kwargs)
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            text = "".join(text_parts)
            input_tokens = response.usage.input_tokens if hasattr(response, "usage") else len(prompt) // 4
            output_tokens = response.usage.output_tokens if hasattr(response, "usage") else len(text) // 4
            total_tokens = input_tokens + output_tokens
            return text, input_tokens, output_tokens, total_tokens
        except ImportError:
            # Fallback to direct HTTP request with requests
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            body: Dict[str, Any] = {
                "model": model_name,
                "max_tokens": max_tok,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            if system_instruction:
                body["system"] = system_instruction

            res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=60)
            if res.status_code != 200:
                raise RuntimeError(f"Claude API Error ({res.status_code}): {res.text}")
            data = res.json()
            content = data.get("content", [])
            text = "".join([c.get("text", "") for c in content if isinstance(c, dict)])
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", len(prompt) // 4)
            output_tokens = usage.get("output_tokens", len(text) // 4)
            total_tokens = input_tokens + output_tokens
            return text, input_tokens, output_tokens, total_tokens
