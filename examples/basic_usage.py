"""Run after `ollama pull gemma:2b` (or any local model) to see the breaker
work with zero paid API keys. Swap in anthropic_tier/openai_tier/etc. above
the ollama_tier to see it fall through from paid to local once the budget
in this example is spent.
"""
from llm_circuit_breaker import LLMCircuitBreaker, ollama_tier

breaker = LLMCircuitBreaker(
    tiers=[ollama_tier(model="gemma:2b")],
    daily_limit_usd=1.0,
    ledger_path="example_spend.jsonl",
)

result = breaker.complete(system="Answer in one short sentence.", user="What is 2+2?")
print(f"[{result.tier_used}] {result.text}  (cost: ${result.cost_usd})")
print("status:", breaker.status())
