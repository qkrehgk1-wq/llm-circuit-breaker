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
}

# Conservative guess applied to any model not listed above, so unknown
# models fail safe (over-estimate) rather than silently costing $0.
DEFAULT_PRICING = {"input": 5.0, "output": 15.0}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
