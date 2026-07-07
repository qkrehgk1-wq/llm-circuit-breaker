"""Try it yourself — NO API keys needed. Uses your local Ollama (gemma:2b).

    python examples/try_it_local.py

Shows three things:
  1) a normal call,
  2) streaming (tokens print live),
  3) where to see your spend.
"""
import sys

from llm_circuit_breaker import LLMCircuitBreaker, ollama_tier

# Windows(cp949) 콘솔에서도 한글이 안 깨지게 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Only a local tier here → free, offline, no keys. Add paid tiers above it
# (anthropic_tier / openai_tier) and set daily_limit_usd to see the fallback.
breaker = LLMCircuitBreaker(
    tiers=[ollama_tier(model="gemma:2b")],
    daily_limit_usd=1.0,
    ledger_path="my_spend.jsonl",
)

print("1) 일반 호출 (complete)")
r = breaker.complete(system="You are terse.", user="What is 2 + 2?")
print(f"   → {r.text.strip()}   [tier: {r.tier_used}, cost: ${r.cost_usd}]\n")

print("2) 스트리밍 (complete_stream) - 글자가 실시간으로:")
print("   → ", end="")
for chunk in breaker.complete_stream(system="You are terse.", user="Say hello in five words."):
    sys.stdout.write(chunk)
    sys.stdout.flush()
print("\n")

print("3) 비용 보기 — 터미널에서:")
print("   llm-cb cost --ledger my_spend.jsonl")
