# llm-circuit-breaker

A tiny, readable circuit breaker for LLM calls. When your budget runs out,
it doesn't raise an exception or let the bill run — it falls through to a
free local model so your agent keeps working.

## Why

Agent API costs are unpredictable: most runs cost a few cents, but a stuck
loop or an unbounded retry can burn tens of dollars in minutes. Most LLM
gateways solve *observability* (dashboards, logs) or *routing* (pick the
cheapest/best model) — but none of the popular ones hard-stop into free
local compute the moment you're about to overspend.

This library does one thing: **try providers in order, and once you've hit
your budget, skip straight to a local model instead of failing or
overspending.** No hosted proxy, no dashboard, no vendor lock-in — about
150 lines you can read in five minutes and vendor straight into your own
project.

## Install

```bash
pip install llm-circuit-breaker
# or, with Anthropic support:
pip install "llm-circuit-breaker[anthropic]"
```

## Quickstart

```python
from llm_circuit_breaker import LLMCircuitBreaker, anthropic_tier, ollama_tier

breaker = LLMCircuitBreaker(
    tiers=[
        anthropic_tier(api_key="sk-ant-...", model="claude-sonnet-4-5"),
        ollama_tier(model="gemma:2b"),  # local, free, always-on fallback
    ],
    daily_limit_usd=5.0,
    ledger_path="llm_spend.jsonl",
)

result = breaker.complete(system="You are terse.", user="2+2?")
print(result.text, result.tier_used, result.cost_usd)
```

Once `llm_spend.jsonl` shows $5 spent today, every subsequent call for the
rest of the day skips Anthropic entirely and goes straight to your local
Ollama model — automatically, no code change, no surprise bill.

## v0.2 — streaming, async, and a `cost` CLI

**Stream tokens as they arrive** (`complete_stream`) — same tiers, same budget
fallback, just yielded piece by piece. Built-in Anthropic / OpenAI / Ollama
tiers stream natively; any tier without streaming yields its whole result once.

```python
for chunk in breaker.complete_stream(system="You are terse.", user="Explain RAG in 2 lines"):
    print(chunk, end="", flush=True)
```

**Async** (`acomplete`) — keep many calls in flight at once:

```python
import asyncio
results = asyncio.run(asyncio.gather(*[
    breaker.acomplete(system="s", user=q) for q in questions
]))
```

**See where the money went** — a budget breaker you can actually inspect:

```bash
llm-cb cost                 # today / total / per-tier, straight from the ledger
llm-cb cost --ledger path   # point at a different ledger, or --json for raw
```

```text
LLM spend  (llm_spend.jsonl)
   today : $2.3100
   total : $45.8700   (1240 calls)
   by tier:
     anthropic:claude-sonnet-4-5      980 calls   $44.2000
     ollama:gemma:2b                  260 calls   $0.0000
```

## How it decides

1. Check today's + all-time spend against your limits (a plain JSONL
   ledger file — human-readable, no database).
2. **Under budget:** try each tier in order, return the first success.
3. **Over budget:** skip every paid tier and try only the tiers marked
   `is_local=True`.
4. If every attempted tier fails (or the budget is blown with no local
   tier configured), raise a clear exception instead of failing silently.

## Built-in tiers

`anthropic_tier`, `openai_tier`, `gemini_tier`, `openrouter_tier`, and
`ollama_tier` (local, via [Ollama](https://ollama.com)) — or write your
own in about 5 lines; a `Tier` is just a name and a
`(system, user, max_tokens) -> (text, cost_usd)` function:

```python
from llm_circuit_breaker import Tier

def _call(system, user, max_tokens):
    text = my_provider_sdk.chat(system, user, max_tokens)
    return text, my_own_cost_estimate

my_tier = Tier(name="my-provider", call=_call, is_local=False)
```

## What this is not

Not a hosted gateway, not a dashboard, not a replacement for
[LiteLLM](https://github.com/BerriAI/litellm) or
[Portkey](https://github.com/Portkey-AI/gateway) if you need enterprise
routing, guardrails, or a proxy server in front of a team's traffic. This
is the opposite trade-off: minimal, in-process, one job — for solo
builders and small agent projects who want a hard stop before overspend
without standing up another service.

## Pricing table

`pricing.py` ships an approximate per-model $/1M-token table used only to
estimate spend for the budget check. Prices change and vary by
region/tier; override `PRICING["your-model"] = {"input": ..., "output": ...}`
for accuracy, or return your own cost from a custom tier.

## Development

```bash
pip install -e ".[dev,anthropic]"
pytest
```

## License

MIT
