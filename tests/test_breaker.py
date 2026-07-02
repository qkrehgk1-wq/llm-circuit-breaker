import tempfile
from pathlib import Path

import pytest

from llm_circuit_breaker import LLMCircuitBreaker, Tier, BudgetExceeded, AllTiersFailed


def make_tier(name, cost=0.01, fail=False, is_local=False):
    def _call(system, user, max_tokens):
        if fail:
            raise RuntimeError(f"{name} is down")
        return f"response from {name}", cost
    return Tier(name=name, call=_call, is_local=is_local)


def _breaker(tiers, **kw):
    ledger = Path(tempfile.mkdtemp()) / "spend.jsonl"
    return LLMCircuitBreaker(tiers=tiers, ledger_path=str(ledger), **kw)


def test_first_tier_success():
    b = _breaker([make_tier("a"), make_tier("b")])
    r = b.complete("sys", "hi")
    assert r.tier_used == "a"
    assert r.cost_usd == 0.01


def test_falls_back_on_failure():
    b = _breaker([make_tier("a", fail=True), make_tier("b")])
    r = b.complete("sys", "hi")
    assert r.tier_used == "b"


def test_all_fail_raises():
    b = _breaker([make_tier("a", fail=True), make_tier("b", fail=True)])
    with pytest.raises(AllTiersFailed):
        b.complete("sys", "hi")


def test_budget_exhausted_routes_to_local():
    b = _breaker(
        [make_tier("paid", cost=1.0), make_tier("local", cost=0.0, is_local=True)],
        daily_limit_usd=0.5,
    )
    r1 = b.complete("sys", "hi")  # under budget -> paid tier, spends $1 (now over the $0.5 cap)
    assert r1.tier_used == "paid"
    r2 = b.complete("sys", "hi")  # over budget -> must skip "paid" and go straight to "local"
    assert r2.tier_used == "local"
    assert r2.cost_usd == 0.0


def test_budget_exhausted_no_local_raises():
    b = _breaker([make_tier("paid", cost=1.0)], daily_limit_usd=0.5)
    b.complete("sys", "hi")
    with pytest.raises(BudgetExceeded):
        b.complete("sys", "hi")


def test_status_reports_spend():
    b = _breaker([make_tier("a", cost=0.25)], daily_limit_usd=1.0, total_limit_usd=10.0)
    b.complete("sys", "hi")
    st = b.status()
    assert st["daily_spent_usd"] == 0.25
    assert st["daily_remaining_usd"] == 0.75
