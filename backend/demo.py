#!/usr/bin/env python3
"""
Full AML pipeline demo — Layers A + B → VerdictComposer

Usage (run from backend/):
    python demo.py
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

# Allow imports from backend/ regardless of where the script is invoked
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Point the DB at the real watchlist data
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal                          # noqa: E402
from app.aml_detect import Context, evaluate, _outcome        # noqa: E402
from screening_v2.engine import ScreeningEngine               # noqa: E402
from screening_v2.composer import VerdictComposer             # noqa: E402


# ---------------------------------------------------------------------------
# Minimal transaction stand-in (duck-types EntityTransaction for aml_detect)
# ---------------------------------------------------------------------------
@dataclass
class Tx:
    entity_id: int
    amount: float
    currency: str = "USD"
    direction: str = "out"
    counterparty_country: str = "US"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Sample scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    {
        "label": "Clean domestic wire",
        "originator": "Alice Johnson",
        "beneficiary": "Global Trade LLC",
        "tx": Tx(entity_id=1, amount=2_500.00, counterparty_country="US"),
        "history": [],
    },
    {
        "label": "Originator name matches OFAC SDN",
        "originator": "Saddam Hussein",
        "beneficiary": "Legitimate Corp",
        "tx": Tx(entity_id=2, amount=50_000.00, counterparty_country="DE"),
        "history": [],
    },
    {
        "label": "Structuring (smurfing) — three sub-threshold transfers",
        "originator": "Carlos Mendez",
        "beneficiary": "FastCash Ltd",
        "tx": Tx(entity_id=3, amount=9_500.00, counterparty_country="US", occurred_at=NOW),
        "history": [
            Tx(entity_id=3, amount=9_500.00, counterparty_country="US",
               occurred_at=NOW - timedelta(days=2)),
            Tx(entity_id=3, amount=9_500.00, counterparty_country="US",
               occurred_at=NOW - timedelta(days=5)),
        ],
    },
    {
        "label": "Large transfer to sanctioned jurisdiction (Iran)",
        "originator": "Omar Al-Rashid",
        "beneficiary": "Tehran Imports Co",
        "tx": Tx(entity_id=4, amount=15_000.00, counterparty_country="IR"),
        "history": [],
    },
    {
        "label": "Velocity burst — 6 rapid transfers in 24 h",
        "originator": "Li Wei",
        "beneficiary": "Apex Brokers",
        "tx": Tx(entity_id=5, amount=800.00, counterparty_country="SG", occurred_at=NOW),
        "history": [
            Tx(entity_id=5, amount=800.00, counterparty_country="SG",
               occurred_at=NOW - timedelta(hours=i))
            for i in range(1, 6)
        ],
    },
]

# ---------------------------------------------------------------------------
# Terminal formatting
# ---------------------------------------------------------------------------
BOLD  = "\033[1m"
RESET = "\033[0m"
RED   = "\033[91m"
YEL   = "\033[93m"
GRN   = "\033[92m"
DIM   = "\033[2m"

ACTION_STYLE = {"BLOCK": RED, "MANUAL_REVIEW": YEL, "PASS": GRN}


def _badge(action: str) -> str:
    c = ACTION_STYLE.get(action, "")
    return f"{c}{BOLD}[{action}]{RESET}"


def _verdict_color(v: str) -> str:
    c = {"MATCH": RED, "REVIEW": YEL, "NO_MATCH": GRN}.get(v, "")
    return f"{c}{v}{RESET}"


def _row(label: str, value: str) -> None:
    print(f"  {label:<30} {value}")


def _section(title: str) -> None:
    print(f"\n  {DIM}{'·' * 60}{RESET}")
    print(f"  {BOLD}{title}{RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"\n{BOLD}{'═' * 68}{RESET}")
    print(f"{BOLD}  TeslaFinTech — AML Pipeline Demo{RESET}")
    print(f"  Layer A: sanctions screening (screening_v2)")
    print(f"  Layer B: behavioral AML (aml_detect)")
    print(f"  Verdict: VerdictComposer")
    print(f"{BOLD}{'═' * 68}{RESET}\n")

    print("  Loading screening engine …", end="", flush=True)
    engine = ScreeningEngine(SessionLocal)
    composer = VerdictComposer()
    print(" ready.\n")

    for idx, s in enumerate(SCENARIOS, 1):
        tx = s["tx"]
        history_by_entity = {tx.entity_id: s["history"] + [tx]}
        ctx = Context(history=history_by_entity)

        # Layer A — sanctions name matching
        orig = engine.screen(s["originator"])
        bene = engine.screen(s["beneficiary"])

        # Layer B — behavioral analysis
        beh_score, beh_hits = evaluate(tx, ctx)
        beh_outcome = _outcome(beh_score)

        # Compose
        result = composer.compose_payment(
            originator=orig,
            beneficiary=bene,
            behavioral_score=beh_score,
            behavioral_outcome=beh_outcome,
            behavioral_hits=beh_hits,
        )

        print(f"{BOLD}  Scenario {idx}: {s['label']}{RESET}")
        _row("Originator:", s["originator"])
        _row("Beneficiary:", s["beneficiary"])
        _row("Amount:", f"{tx.amount:>10,.2f} {tx.currency}")
        _row("Counterparty country:", tx.counterparty_country)

        _section("Layer A — sanctions screening")
        _row("Originator verdict:", _verdict_color(orig.verdict) + f"  ({orig.confidence:.0%})")
        _row("Beneficiary verdict:", _verdict_color(bene.verdict) + f"  ({bene.confidence:.0%})")
        if orig.candidates:
            top = orig.candidates[0]
            _row("  → matched:", f"{top.matched_name}  [{top.entity_id}]")
        if bene.candidates:
            top = bene.candidates[0]
            _row("  → matched:", f"{top.matched_name}  [{top.entity_id}]")

        _section("Layer B — behavioral AML")
        _row("Score / outcome:", f"{beh_score:.0f}  →  {beh_outcome}")
        if beh_hits:
            for h in beh_hits:
                _row(f"  rule {h.rule_id}:", f"[{h.severity}] +{h.score:.0f}  {h.reason}")
        else:
            _row("Rules fired:", "none")

        _section("Verdict Composer")
        layers = ", ".join(result["triggered_layers"]) or "none"
        _row("Triggered layers:", layers)
        _row("Confidence:", f"{result['confidence']:.0%}")
        _row("Verdict:", _verdict_color(result["verdict"]))
        print(f"\n  {'Recommended action':<30} {_badge(result['recommended_action'])}")

        print(f"\n{BOLD}{'─' * 68}{RESET}\n")


if __name__ == "__main__":
    main()
