import time
from typing import Optional, Dict, Any, Tuple
from src import config
from src.llm.factory import get_provider_instance

# Runtime active configuration state (can be changed dynamically via API or Streamlit)
_RUNTIME_LLM_CONFIG = {
    "provider": config.DEFAULT_LLM_PROVIDER,
    "model_tier": config.DEFAULT_LLM_MODEL_TIER
}


def get_active_llm_config() -> Dict[str, str]:
    """Get the current global LLM configuration (provider and model tier)."""
    p = config.resolve_provider(_RUNTIME_LLM_CONFIG.get("provider"))
    t = config.TIER_ALIASES.get(_RUNTIME_LLM_CONFIG.get("model_tier", "med"), "med")
    resolved_model = config.resolve_model(p, t)
    return {
        "provider": p,
        "model_tier": t,
        "model_name": resolved_model,
        "display_name": config.LLM_PROVIDER_MODELS.get(p, {}).get("display_name", p)
    }


def set_active_llm_config(provider: Optional[str] = None, model_tier: Optional[str] = None) -> Dict[str, str]:
    """Set the global LLM configuration (provider and model tier)."""
    if provider:
        _RUNTIME_LLM_CONFIG["provider"] = config.resolve_provider(provider)
    if model_tier:
        _RUNTIME_LLM_CONFIG["model_tier"] = config.TIER_ALIASES.get(model_tier.lower(), "med")
    return get_active_llm_config()


def get_all_providers_info() -> Dict[str, Any]:
    """Return all available providers and their 3 model tiers (high, med, low)."""
    active = get_active_llm_config()
    res = {}
    for prov_key, prov_data in config.LLM_PROVIDER_MODELS.items():
        is_configured = False
        if prov_key == "gemini":
            is_configured = bool(config.USE_VERTEXAI or config.GEMINI_API_KEY)
        elif prov_key == "openai":
            is_configured = bool(config.OPENAI_API_KEY)
        elif prov_key == "claude":
            is_configured = bool(config.ANTHROPIC_API_KEY)

        res[prov_key] = {
            "display_name": prov_data.get("display_name", prov_key),
            "is_configured": is_configured,
            "is_active": (prov_key == active["provider"]),
            "tiers": {
                "high": prov_data["high"],
                "med": prov_data["med"],
                "low": prov_data["low"]
            },
            "pricing": prov_data.get("pricing", {})
        }
    return {
        "active": active,
        "providers": res
    }


def compute_cost(provider: str, model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Compute approximate USD cost based on token counts and model pricing."""
    prov_data = config.LLM_PROVIDER_MODELS.get(provider, {})
    pricing_map = prov_data.get("pricing", {})
    
    # Default rates if model not found in table
    in_rate, out_rate = pricing_map.get(model_name, (0.10, 0.40))
    cost = (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate
    return round(cost, 8)


def generate_text(
    prompt: str,
    system_instruction: Optional[str] = None,
    provider: Optional[str] = None,
    model_tier: Optional[str] = None,
    model: Optional[str] = None,
    user_id: Optional[str] = "system",
    conversation_id: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Universal LLM Dispatcher routing requests across modular Provider instances
    (Gemini, OpenAI, Claude) with 3 model tiers (High, Med, Low).
    
    If provider or model_tier is omitted/null (such as in standard n8n workflow calls),
    it automatically falls back to the system's global runtime configuration.
    """
    # 1. Resolve Provider (falls back to runtime active provider)
    target_provider = config.resolve_provider(provider or _RUNTIME_LLM_CONFIG.get("provider"))

    # 2. Resolve Model Name (falls back to runtime active model tier)
    target_tier = config.TIER_ALIASES.get((model_tier or _RUNTIME_LLM_CONFIG.get("model_tier", "med")).lower(), "med")
    resolved_model = config.resolve_model(target_provider, model or target_tier)

    t0 = time.time()

    # 3. Retrieve modular provider instance and generate
    provider_instance = get_provider_instance(target_provider)
    text, in_tok, out_tok, tot_tok = provider_instance.generate(
        prompt=prompt,
        system_instruction=system_instruction,
        model_name=resolved_model,
        temperature=temperature,
        max_tokens=max_tokens
    )

    duration_ms = int((time.time() - t0) * 1000)
    cost = compute_cost(target_provider, resolved_model, in_tok, out_tok)

    usage_payload = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "provider": target_provider,
        "model_tier": target_tier,
        "model_name": resolved_model,
        "model_api_type": target_provider,
        "total_tokens": tot_tok,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost": cost,
        "duration_ms": duration_ms
    }

    return {
        "status": "success",
        "text": text,
        "provider": target_provider,
        "model_tier": target_tier,
        "model_name": resolved_model,
        "usage": usage_payload
    }
