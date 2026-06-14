#!/usr/bin/env python3
"""
Full AML pipeline demo - Layers A + B -> VerdictComposer

Usage (run from backend/):
    python demo.py
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.aml_detect import Context, _outcome, evaluate  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from screening_v2.composer import VerdictComposer  # noqa: E402
from screening_v2.engine import ScreeningEngine  # noqa: E402


@dataclass
class Tx:
    entity_id: int
    amount: float
    currency: str = "USD"
    direction: str = "out"
    channel: str = "wire"
    counterparty_name: str | None = None
    counterparty_account_name: str | None = None
    counterparty_country: str = "US"
    initiated_from_country: str | None = None
    entity_registered_country: str | None = None
    usual_operating_countries: list[str] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


NOW = datetime.now(timezone.utc)

SCENARIOS = [
    {
        "label": "Clean domestic wire",
        "originator": "Alice Johnson",
        "beneficiary": "Milan Textile GmbH",
        "tx": Tx(
            entity_id=1,
            amount=2_500.00,
            counterparty_name="Milan Textile GmbH",
            counterparty_account_name="Milan Textile GmbH",
            counterparty_country="DE",
            initiated_from_country="RS",
            entity_registered_country="RS",
            usual_operating_countries=["RS", "DE"],
        ),
        "history": [],
    },
    {
        "label": "Originator name matches OFAC SDN",
        "originator": "Saddam Hussein",
        "beneficiary": "Legitimate Corp",
        "tx": Tx(
            entity_id=2,
            amount=50_000.00,
            counterparty_name="Legitimate Corp",
            counterparty_account_name="Legitimate Corp",
            counterparty_country="DE",
        ),
        "history": [],
    },
    {
        "label": "Large payment relative to baseline",
        "originator": "Carlos Mendez",
        "beneficiary": "Nordic Equipment AB",
        "tx": Tx(
            entity_id=3,
            amount=140_000.00,
            counterparty_name="Nordic Equipment AB",
            counterparty_account_name="Nordic Equipment AB",
            counterparty_country="SE",
            occurred_at=NOW,
        ),
        "history": [
            Tx(
                entity_id=3,
                amount=18_000.00,
                counterparty_country="SE",
                occurred_at=NOW - timedelta(days=12),
            ),
            Tx(
                entity_id=3,
                amount=22_000.00,
                counterparty_country="SE",
                occurred_at=NOW - timedelta(days=35),
            ),
            Tx(
                entity_id=3,
                amount=20_000.00,
                counterparty_country="SE",
                occurred_at=NOW - timedelta(days=62),
            ),
        ],
    },
    {
        "label": "Money-in / money-out pass-through",
        "originator": "Omar Al-Rashid",
        "beneficiary": "Atlas Brokerage Ltd",
        "tx": Tx(
            entity_id=4,
            amount=498_700.00,
            counterparty_name="Atlas Brokerage Ltd",
            counterparty_account_name="Atlas Brokerage Ltd",
            counterparty_country="AE",
            occurred_at=NOW,
        ),
        "history": [
            Tx(
                entity_id=4,
                amount=500_000.00,
                direction="in",
                counterparty_country="GB",
                occurred_at=NOW - timedelta(minutes=42),
            ),
        ],
    },
    {
        "label": "High-risk initiation country mismatch",
        "originator": "Li Wei",
        "beneficiary": "Apex Brokers",
        "tx": Tx(
            entity_id=5,
            amount=250_000.00,
            counterparty_name="Apex Brokers",
            counterparty_account_name="Apex Brokers",
            counterparty_country="SG",
            initiated_from_country="RU",
            entity_registered_country="US",
            usual_operating_countries=["US", "SG"],
            occurred_at=NOW,
        ),
        "history": [],
    },
    {
        "label": "Beneficiary account-name mismatch",
        "originator": "Nora Novak",
        "beneficiary": "Blue Harbor Logistics",
        "tx": Tx(
            entity_id=6,
            amount=12_000.00,
            counterparty_name="Blue Harbor Logistics",
            counterparty_account_name="B H Consulting Services",
            counterparty_country="NL",
            occurred_at=NOW,
        ),
        "history": [],
    },
]

BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"
YEL = "\033[93m"
GRN = "\033[92m"
DIM = "\033[2m"

ACTION_STYLE = {"BLOCK": RED, "MANUAL_REVIEW": YEL, "PASS": GRN}


def _badge(action: str) -> str:
    color = ACTION_STYLE.get(action, "")
    return f"{color}{BOLD}[{action}]{RESET}"


def _verdict_color(verdict: str) -> str:
    color = {"MATCH": RED, "REVIEW": YEL, "NO_MATCH": GRN}.get(verdict, "")
    return f"{color}{verdict}{RESET}"


def _row(label: str, value: str) -> None:
    print(f"  {label:<30} {value}")


def _section(title: str) -> None:
    print(f"\n  {DIM}{'.' * 60}{RESET}")
    print(f"  {BOLD}{title}{RESET}")


def main() -> None:
    print(f"\n{BOLD}{'=' * 68}{RESET}")
    print(f"{BOLD}  TeslaFinTech - AML Pipeline Demo{RESET}")
    print("  Layer A: sanctions screening (screening_v2)")
    print("  Layer B: behavioral AML (aml_detect)")
    print("  Verdict: VerdictComposer")
    print(f"{BOLD}{'=' * 68}{RESET}\n")

    print("  Loading screening engine ...", end="", flush=True)
    engine = ScreeningEngine(SessionLocal)
    composer = VerdictComposer()
    print(" ready.\n")

    for idx, scenario in enumerate(SCENARIOS, 1):
        tx = scenario["tx"]
        history_by_entity = {tx.entity_id: scenario["history"] + [tx]}
        ctx = Context(history=history_by_entity)

        originator = engine.screen(scenario["originator"])
        beneficiary = engine.screen(scenario["beneficiary"])

        behavioral_score, behavioral_hits = evaluate(tx, ctx)
        behavioral_outcome = _outcome(behavioral_score)

        result = composer.compose_payment(
            originator=originator,
            beneficiary=beneficiary,
            behavioral_score=behavioral_score,
            behavioral_outcome=behavioral_outcome,
            behavioral_hits=behavioral_hits,
        )

        print(f"{BOLD}  Scenario {idx}: {scenario['label']}{RESET}")
        _row("Originator:", scenario["originator"])
        _row("Beneficiary:", scenario["beneficiary"])
        _row("Amount:", f"{tx.amount:>10,.2f} {tx.currency}")
        _row("Counterparty country:", tx.counterparty_country)

        _section("Layer A - sanctions screening")
        _row("Originator verdict:", _verdict_color(originator.verdict) + f"  ({originator.confidence:.0%})")
        _row("Beneficiary verdict:", _verdict_color(beneficiary.verdict) + f"  ({beneficiary.confidence:.0%})")
        if originator.candidates:
            top = originator.candidates[0]
            _row("  -> matched:", f"{top.matched_name}  [{top.entity_id}]")
        if beneficiary.candidates:
            top = beneficiary.candidates[0]
            _row("  -> matched:", f"{top.matched_name}  [{top.entity_id}]")

        _section("Layer B - behavioral AML")
        _row("Score / outcome:", f"{behavioral_score:.0f}  ->  {behavioral_outcome}")
        if behavioral_hits:
            for hit in behavioral_hits:
                _row(f"  rule {hit.rule_id}:", f"[{hit.severity}] +{hit.score:.0f}  {hit.reason}")
        else:
            _row("Rules fired:", "none")

        _section("Verdict Composer")
        layers = ", ".join(result["triggered_layers"]) or "none"
        _row("Triggered layers:", layers)
        _row("Confidence:", f"{result['confidence']:.0%}")
        _row("Verdict:", _verdict_color(result["verdict"]))
        print(f"\n  {'Recommended action':<30} {_badge(result['recommended_action'])}")

        print(f"\n{BOLD}{'-' * 68}{RESET}\n")


if __name__ == "__main__":
    main()
