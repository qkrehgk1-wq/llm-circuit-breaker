"""Command line: `llm-cb cost` — read the spend ledger and show it at a glance.

A budget circuit breaker that you can't easily inspect is half a tool, so v0.2
ships a one-command view of where the money went.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path


def _load(ledger: Path) -> list:
    rows = []
    if not ledger.exists():
        return rows
    for line in ledger.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def cost_report(ledger_path: str = "llm_spend.jsonl") -> dict:
    """Aggregate the JSONL spend ledger into today / total / per-tier numbers."""
    ledger = Path(ledger_path)
    rows = _load(ledger)
    day_ago = time.time() - 86400
    total = sum(r.get("cost_usd", 0.0) for r in rows)
    today = sum(r.get("cost_usd", 0.0) for r in rows if r.get("ts", 0) >= day_ago)
    by_tier: dict = defaultdict(lambda: [0, 0.0])  # tier -> [calls, cost]
    for r in rows:
        slot = by_tier[r.get("tier", "?")]
        slot[0] += 1
        slot[1] += r.get("cost_usd", 0.0)
    return {
        "ledger": str(ledger),
        "calls": len(rows),
        "today_usd": round(today, 6),
        "total_usd": round(total, 6),
        "by_tier": {k: {"calls": v[0], "usd": round(v[1], 6)} for k, v in by_tier.items()},
    }


def _print(rep: dict) -> None:
    # ASCII only — CLI output must not crash on non-UTF8 consoles (e.g. Windows cp949).
    print(f"LLM spend  ({rep['ledger']})")
    print(f"   today : ${rep['today_usd']:.4f}")
    print(f"   total : ${rep['total_usd']:.4f}   ({rep['calls']} calls)")
    if rep["by_tier"]:
        print("   by tier:")
        for name, v in sorted(rep["by_tier"].items(), key=lambda x: -x[1]["usd"]):
            print(f"     {name:30} {v['calls']:>4} calls   ${v['usd']:.4f}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="llm-cb", description="llm-circuit-breaker CLI")
    sub = parser.add_subparsers(dest="cmd")
    c = sub.add_parser("cost", help="show LLM spend from the ledger")
    c.add_argument("--ledger", default="llm_spend.jsonl",
                   help="ledger path (default: llm_spend.jsonl)")
    c.add_argument("--json", action="store_true", help="print raw JSON instead of a table")
    args = parser.parse_args(argv)

    if args.cmd == "cost":
        rep = cost_report(args.ledger)
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            _print(rep)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
