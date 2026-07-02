from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional


class BudgetExceeded(Exception):
    """Raised only when the budget is blown and no local tier is configured to catch it."""


class AllTiersFailed(Exception):
    """Raised when every attempted tier raised an exception."""


@dataclass
class Tier:
    name: str
    call: Callable[[str, str, int], "tuple[str, float]"]  # (system, user, max_tokens) -> (text, cost_usd)
    is_local: bool = False


@dataclass
class CompletionResult:
    text: str
    tier_used: str
    cost_usd: float
    attempts: List[str] = field(default_factory=list)


class LLMCircuitBreaker:
    """Try LLM tiers in order. If the budget is spent, skip every paid tier
    and go straight to the local (free) tier instead of raising or overspending.
    """

    def __init__(
        self,
        tiers: List[Tier],
        daily_limit_usd: Optional[float] = None,
        total_limit_usd: Optional[float] = None,
        ledger_path: str = "llm_spend.jsonl",
    ):
        if not tiers:
            raise ValueError("At least one tier is required")
        self.tiers = tiers
        self.daily_limit_usd = daily_limit_usd
        self.total_limit_usd = total_limit_usd
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def _spend(self, since_seconds: Optional[float] = None) -> float:
        if not self.ledger_path.exists():
            return 0.0
        cutoff = time.time() - since_seconds if since_seconds else None
        total = 0.0
        with self.ledger_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cutoff is None or entry.get("ts", 0) >= cutoff:
                    total += entry.get("cost_usd", 0.0)
        return total

    def status(self) -> dict:
        daily = self._spend(since_seconds=86400)
        total = self._spend()
        return {
            "daily_spent_usd": round(daily, 6),
            "daily_limit_usd": self.daily_limit_usd,
            "daily_remaining_usd": (round(self.daily_limit_usd - daily, 6)
                                     if self.daily_limit_usd is not None else None),
            "total_spent_usd": round(total, 6),
            "total_limit_usd": self.total_limit_usd,
        }

    def _budget_exhausted(self) -> bool:
        st = self.status()
        if st["daily_limit_usd"] is not None and st["daily_spent_usd"] >= st["daily_limit_usd"]:
            return True
        if st["total_limit_usd"] is not None and st["total_spent_usd"] >= st["total_limit_usd"]:
            return True
        return False

    def _record(self, tier_name: str, cost_usd: float) -> None:
        entry = {"ts": time.time(), "tier": tier_name, "cost_usd": cost_usd}
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def complete(self, system: str, user: str, max_tokens: int = 1000) -> CompletionResult:
        order = self.tiers
        if self._budget_exhausted():
            local_tiers = [t for t in self.tiers if t.is_local]
            if not local_tiers:
                raise BudgetExceeded(
                    "Budget exhausted and no local tier (is_local=True) configured as a fallback."
                )
            order = local_tiers

        attempts = []
        last_err = None
        for tier in order:
            try:
                text, cost = tier.call(system, user, max_tokens)
                self._record(tier.name, cost)
                attempts.append(tier.name)
                return CompletionResult(text=text, tier_used=tier.name, cost_usd=cost, attempts=attempts)
            except Exception as e:  # noqa: BLE001 - a failed tier should never crash the caller
                attempts.append(f"{tier.name} (failed: {e})")
                last_err = e
                continue

        raise AllTiersFailed(f"All tiers failed. Last error: {last_err}")
