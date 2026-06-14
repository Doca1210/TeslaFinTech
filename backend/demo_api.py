#!/usr/bin/env python3
"""Minimal demo API for the React UI."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.aml_detect import Context, _outcome, evaluate  # noqa: E402
from app.database import SessionLocal, engine as db_engine  # noqa: E402
from app.schema_upgrade import ensure_sqlite_schema  # noqa: E402
from screening_v2.composer import VerdictComposer  # noqa: E402
from screening_v2.engine import ScreeningEngine  # noqa: E402

ensure_sqlite_schema(db_engine)


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
        "id": 1,
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
        "id": 2,
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
        "id": 3,
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
        "id": 4,
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
        "id": 5,
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
        "id": 6,
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


def _party_payload(result) -> dict:
    top = result.candidates[0] if result.candidates else None
    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "matched_name": top.matched_name if top else None,
        "matched_entity_id": top.entity_id if top else None,
        "match_score": top.match_score if top else None,
    }


_engine: ScreeningEngine | None = None
_composer: VerdictComposer | None = None
_results_cache: list[dict] | None = None


def run_scenarios() -> list[dict]:
    global _engine, _composer, _results_cache

    if _results_cache is not None:
        return _results_cache

    if _engine is None:
        _engine = ScreeningEngine(SessionLocal)
        _composer = VerdictComposer()

    engine = _engine
    composer = _composer

    results = []
    for scenario in SCENARIOS:
        tx = scenario["tx"]
        history_by_entity = {tx.entity_id: scenario["history"] + [tx]}
        ctx = Context(history=history_by_entity)

        originator = engine.screen(scenario["originator"])
        beneficiary = engine.screen(scenario["beneficiary"])

        behavioral_score, behavioral_hits = evaluate(tx, ctx)
        behavioral_outcome = _outcome(behavioral_score)

        decision = composer.compose_payment(
            originator=originator,
            beneficiary=beneficiary,
            behavioral_score=behavioral_score,
            behavioral_outcome=behavioral_outcome,
            behavioral_hits=behavioral_hits,
        )

        results.append(
            {
                "id": scenario["id"],
                "label": scenario["label"],
                "originator": scenario["originator"],
                "beneficiary": scenario["beneficiary"],
                "amount": tx.amount,
                "currency": tx.currency,
                "counterparty_country": tx.counterparty_country,
                "layer_a": {
                    "originator": _party_payload(originator),
                    "beneficiary": _party_payload(beneficiary),
                },
                "layer_b": {
                    "score": behavioral_score,
                    "outcome": behavioral_outcome,
                    "rules_fired": [
                        {
                            "rule_id": hit.rule_id,
                            "severity": hit.severity,
                            "score": hit.score,
                            "reason": hit.reason,
                            "explanation": hit.explanation,
                            "evidence": hit.evidence,
                        }
                        for hit in behavioral_hits
                    ],
                },
                "verdict": decision["verdict"],
                "confidence": decision["confidence"],
                "recommended_action": decision["recommended_action"],
                "triggered_layers": decision["triggered_layers"],
                "explanation": decision["explanation"],
            }
        )

    _results_cache = results
    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_scenarios()
    yield


app = FastAPI(title="AML Demo API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/transactions")
def transactions() -> list[dict]:
    return run_scenarios()
