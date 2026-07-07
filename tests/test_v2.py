import asyncio
import json
import tempfile
import time
from pathlib import Path

from llm_circuit_breaker import LLMCircuitBreaker, Tier, cost_report


def _ledger():
    return str(Path(tempfile.mkdtemp()) / "spend.jsonl")


def stream_tier(name, chunks, cost=0.01, is_local=False, fail=False):
    def _stream(system, user, mt):
        if fail:
            raise RuntimeError("down")
        for c in chunks:
            yield c

    def _call(system, user, mt):
        if fail:
            raise RuntimeError("down")
        return "".join(chunks), cost

    return Tier(name=name, call=_call, is_local=is_local,
                stream_call=_stream, estimate=lambda p, o: cost)


def plain_tier(name, text="whole", cost=0.02, is_local=False):
    return Tier(name=name, call=lambda s, u, mt: (text, cost), is_local=is_local)


# ── streaming ──────────────────────────────────────────────
def test_stream_yields_chunks():
    b = LLMCircuitBreaker([stream_tier("a", ["He", "llo"])], ledger_path=_ledger())
    assert list(b.complete_stream("s", "u")) == ["He", "llo"]
    assert b.status()["total_spent_usd"] == 0.01  # cost recorded once, after stream


def test_stream_falls_back_for_nonstreaming_tier():
    b = LLMCircuitBreaker([plain_tier("p", "full-answer", 0.02)], ledger_path=_ledger())
    assert list(b.complete_stream("s", "u")) == ["full-answer"]


def test_stream_connect_failure_falls_back():
    b = LLMCircuitBreaker(
        [stream_tier("bad", ["x"], fail=True), stream_tier("good", ["ok"])], ledger_path=_ledger())
    assert list(b.complete_stream("s", "u")) == ["ok"]


def test_stream_over_budget_routes_to_local():
    b = LLMCircuitBreaker(
        [stream_tier("paid", ["p"], cost=1.0), stream_tier("local", ["L"], cost=0.0, is_local=True)],
        daily_limit_usd=0.5, ledger_path=_ledger())
    list(b.complete_stream("s", "u"))          # spends $1 -> over the $0.5 cap
    assert list(b.complete_stream("s", "u")) == ["L"]  # now only local


# ── async ──────────────────────────────────────────────────
def test_acomplete():
    b = LLMCircuitBreaker([plain_tier("a", "async-ok", 0.03)], ledger_path=_ledger())
    r = asyncio.run(b.acomplete("s", "u"))
    assert r.text == "async-ok" and r.tier_used == "a"


def test_acomplete_runs_concurrently():
    b = LLMCircuitBreaker([plain_tier("a", "x", 0.01)], ledger_path=_ledger())

    async def go():
        return await asyncio.gather(*[b.acomplete("s", "u") for _ in range(5)])

    res = asyncio.run(go())
    assert len(res) == 5 and all(r.text == "x" for r in res)


# ── cost CLI ───────────────────────────────────────────────
def test_cost_report():
    p = _ledger()
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "tier": "anthropic", "cost_usd": 0.10}) + "\n")
        f.write(json.dumps({"ts": time.time(), "tier": "ollama", "cost_usd": 0.0}) + "\n")
        f.write(json.dumps({"ts": time.time() - 999999, "tier": "anthropic", "cost_usd": 0.05}) + "\n")
    rep = cost_report(p)
    assert rep["calls"] == 3
    assert abs(rep["total_usd"] - 0.15) < 1e-9
    assert abs(rep["today_usd"] - 0.10) < 1e-9          # the old entry is excluded from "today"
    assert rep["by_tier"]["anthropic"]["calls"] == 2
