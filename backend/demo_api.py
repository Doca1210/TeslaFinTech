#!/usr/bin/env python3
"""Minimal demo API for the React UI.

Wraps the same pipeline as demo.py (Layer A sanctions screening via
screening_v2 + Layer B behavioral AML via app.aml_detect + VerdictComposer)
and exposes it as JSON over HTTP for a local frontend.

Usage (from backend/):
    python -m uvicorn demo_api:app --reload --port 8000
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

# Allow imports from backend/ regardless of where the script is invoked
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.aml_detect import Context, evaluate, _outcome
from screening_v2.engine import ScreeningEngine
from screening_v2.composer import VerdictComposer


@dataclass
class Tx:
    entity_id: int
    amount: float
    currency: str = "USD"
    direction: str = "out"
    counterparty_country: str = "US"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


NOW = datetime.now(timezone.utc)

SCENARIOS = [
    {
        "id": 1,
        "label": "Clean domestic wire",
        "originator": "Alice Johnson",
        "beneficiary": "Global Trade LLC",
        "tx": Tx(entity_id=1, amount=2_500.00, counterparty_country="US"),
        "history": [],
    },
    {
        "id": 2,
        "label": "Originator name matches OFAC SDN",
        "originator": "Saddam Hussein",
        "beneficiary": "Legitimate Corp",
        "tx": Tx(entity_id=2, amount=50_000.00, counterparty_country="DE"),
        "history": [],
    },
    {
        "id": 3,
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
        "id": 4,
        "label": "Large transfer to sanctioned jurisdiction (Iran)",
        "originator": "Omar Al-Rashid",
        "beneficiary": "Tehran Imports Co",
        "tx": Tx(entity_id=4, amount=15_000.00, counterparty_country="IR"),
        "history": [],
    },
    {
        "id": 5,
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
    for s in SCENARIOS:
        tx = s["tx"]
        history_by_entity = {tx.entity_id: s["history"] + [tx]}
        ctx = Context(history=history_by_entity)

        orig = engine.screen(s["originator"])
        bene = engine.screen(s["beneficiary"])

        beh_score, beh_hits = evaluate(tx, ctx)
        beh_outcome = _outcome(beh_score)

        decision = composer.compose_payment(
            originator=orig,
            beneficiary=bene,
            behavioral_score=beh_score,
            behavioral_outcome=beh_outcome,
            behavioral_hits=beh_hits,
        )

        results.append({
            "id": s["id"],
            "label": s["label"],
            "originator": s["originator"],
            "beneficiary": s["beneficiary"],
            "amount": tx.amount,
            "currency": tx.currency,
            "counterparty_country": tx.counterparty_country,
            "layer_a": {
                "originator": _party_payload(orig),
                "beneficiary": _party_payload(bene),
            },
            "layer_b": {
                "score": beh_score,
                "outcome": beh_outcome,
                "rules_fired": [
                    {
                        "rule_id": h.rule_id,
                        "severity": h.severity,
                        "score": h.score,
                        "reason": h.reason,
                        "explanation": h.explanation,
                    }
                    for h in beh_hits
                ],
            },
            "verdict": decision["verdict"],
            "confidence": decision["confidence"],
            "recommended_action": decision["recommended_action"],
            "triggered_layers": decision["triggered_layers"],
            "explanation": decision["explanation"],
        })

    _results_cache = results
    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the vector model and pre-compute scenario results so the
    # first /transactions request doesn't pay the model-load cost.
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
