"""Approximate per-1M-token USD pricing, used only to estimate spend for the
budget check. Prices change often and vary by region/tier — this is a rough
estimate for budget alerts, not a billing-accurate source. Override
PRICING[model] or pass your own cost from a custom tier if you need accuracy.
"""

PRICING = {
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-opus-4-5": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.0},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "anthropic/claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Frontier open-weight model, served via OpenRouter — cheap enough to carry
    # the heavy agent work while paid frontier tiers stay as a last resort.
    # Standard list price (not the launch promo) so the budget check fails safe.
    # Confirm the exact slug on openrouter.ai/models before use.
    "meituan/longcat-2.0": {"input": 0.75, "output": 2.95},
    "longcat-2.0": {"input": 0.75, "output": 2.95},
    # More cheap frontier open-weight models on OpenRouter. Slugs vary by
    # provider — confirm on openrouter.ai/models; prices are rough and
    # rounded up so the budget check errs toward over-estimating.
    "z-ai/glm-5": {"input": 0.60, "output": 1.92},
    "deepseek/deepseek-v4": {"input": 0.44, "output": 0.88},
    "qwen/qwen3.6": {"input": 0.50, "output": 1.95},
}

# Conservative guess applied to any model not listed above, so unknown
# models fail safe (over-estimate) rather than silently costing $0.
DEFAULT_PRICING = {"input": 5.0, "output": 15.0}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
