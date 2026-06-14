"""Demo payment scenarios for the Payments dashboard (the `/transactions` feed).

Runs each scenario through the full pipeline — Layer A (sanctions, screening_v2),
Layer B (behavioral, aml_detect), Layer C (ownership) → VerdictComposer — and
maps the result into the shape the frontend ``TransactionCard`` expects.

Building this requires the screening engine (heavy), so the endpoint serves a
precomputed cache; regenerate it with ``python manage.py generate-transactions``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.aml_detect import Context, _outcome, evaluate
from screening_v2.composer import VerdictComposer

NOW = datetime.now(timezone.utc)


@dataclass
class _Tx:
    """Duck-types EntityTransaction for aml_detect."""

    entity_id: int
    amount: float
    currency: str = "USD"
    direction: str = "out"
    counterparty_country: str = "US"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


SCENARIOS: list[dict] = [
    {
        "label": "Clean domestic wire",
        "originator": "Alice Johnson",
        "beneficiary": "Global Trade LLC",
        "tx": _Tx(entity_id=1, amount=2_500.00, currency="USD", counterparty_country="US"),
        "history": [],
    },
    {
        # Exact OFAC SDN name -> high-confidence Layer A MATCH -> BLOCK.
        "label": "Sanctioned originator (OFAC SDN)",
        "originator": "Sergey Valeryevich AKSYONOV",
        "beneficiary": "Continental Supplies Inc",
        "tx": _Tx(entity_id=2, amount=250_000.00, currency="EUR", counterparty_country="DE"),
        "history": [],
    },
    {
        # Transliterated near-match -> REVIEW (PEP-aware: fuzzy ≠ hard block).
        "label": "Possible OFAC alias match",
        "originator": "Saddam Hussein",
        "beneficiary": "Crescent Holdings",
        "tx": _Tx(entity_id=3, amount=50_000.00, currency="EUR", counterparty_country="JO"),
        "history": [],
    },
    {
        "label": "Structuring — three sub-threshold transfers",
        "originator": "Carlos Mendez",
        "beneficiary": "FastCash Ltd",
        "tx": _Tx(entity_id=4, amount=9_500.00, currency="USD", counterparty_country="US", occurred_at=NOW),
        "history": [
            _Tx(entity_id=4, amount=9_500.00, counterparty_country="US", occurred_at=NOW - timedelta(days=2)),
            _Tx(entity_id=4, amount=9_500.00, counterparty_country="US", occurred_at=NOW - timedelta(days=5)),
        ],
    },
    {
        "label": "Large transfer to sanctioned jurisdiction (Iran)",
        "originator": "Jonathan Pierce",
        "beneficiary": "Tehran Imports Co",
        "tx": _Tx(entity_id=5, amount=15_000.00, currency="USD", counterparty_country="IR"),
        "history": [],
    },
    {
        # Clean by name + behaviour, but the beneficiary is owned by a sanctioned
        # party — only Layer C (ownership) catches it.
        "label": "Clean beneficiary, sanctioned owner (KYB)",
        "originator": "Meridian Exports Ltd",
        "beneficiary": "Northwind Commodities DMCC",
        "tx": _Tx(entity_id=6, amount=20_000_000.00, currency="EUR", counterparty_country="AE"),
        "history": [],
    },
]


def _party(sr) -> dict:
    top = sr.candidates[0] if sr.candidates else None
    return {
        "verdict": sr.verdict,
        "confidence": sr.confidence,
        "matched_name": top.matched_name if top else None,
        "matched_entity_id": top.entity_id if top else None,
    }


def _to_frontend(idx, s, tx, orig, bene, beh_score, beh_outcome, beh_hits, result) -> dict:
    return {
        "id": idx,
        "label": s["label"],
        "originator": s["originator"],
        "beneficiary": s["beneficiary"],
        "amount": tx.amount,
        "currency": tx.currency,
        "counterparty_country": tx.counterparty_country,
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "recommended_action": result["recommended_action"],
        "triggered_layers": result["triggered_layers"],
        "explanation": result["explanation"],
        "layer_a": {"originator": _party(orig), "beneficiary": _party(bene)},
        "layer_b": {
            "score": beh_score,
            "outcome": beh_outcome,
            "rules_fired": [
                {"rule_id": h.rule_id, "severity": h.severity, "score": h.score, "reason": h.reason}
                for h in beh_hits
            ],
        },
        "ownership_risk": result.get("ownership_risk"),
    }


def build_transactions(screening_engine, ownership_engine=None) -> list[dict]:
    """Screen every demo scenario through Layers A+B+C and return frontend rows."""
    composer = VerdictComposer()
    rows: list[dict] = []
    for idx, s in enumerate(SCENARIOS, 1):
        tx = s["tx"]
        ctx = Context(history={tx.entity_id: s["history"] + [tx]})

        orig = screening_engine.screen(s["originator"])
        bene = screening_engine.screen(s["beneficiary"])

        beh_score, beh_hits = evaluate(tx, ctx)
        beh_outcome = _outcome(beh_score)

        ownership = ownership_engine.assess(s["beneficiary"]) if ownership_engine else None
        if ownership and ownership["verdict"] == "NO_MATCH":
            ownership = None  # keep payload clean when ownership adds nothing

        result = composer.compose_payment(
            orig, bene, beh_score, beh_outcome, beh_hits, ownership=ownership
        )
        rows.append(_to_frontend(idx, s, tx, orig, bene, beh_score, beh_outcome, beh_hits, result))
    return rows
