from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.aml_detect import Context, _outcome, evaluate


@dataclass
class Tx:
    entity_id: int = 1
    amount: float = 1_000.0
    currency: str = "USD"
    direction: str = "out"
    counterparty_country: str | None = "US"
    counterparty_name: str | None = None
    counterparty_account_name: str | None = None
    initiated_from_country: str | None = None
    entity_registered_country: str | None = None
    usual_operating_countries: list[str] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: int | None = None


NOW = datetime(2026, 6, 14, tzinfo=timezone.utc)


def _rule_ids(tx: Tx, history: list[Tx]) -> set[str]:
    _, hits = evaluate(tx, Context(history={tx.entity_id: history + [tx]}))
    return {hit.rule_id for hit in hits}


def test_clean_normal_transaction_stays_approve():
    tx = Tx(
        amount=2_500,
        counterparty_name="Milan Textile GmbH",
        counterparty_account_name="Milan Textile GmbH",
        initiated_from_country="RS",
        entity_registered_country="RS",
        usual_operating_countries=["RS", "DE"],
        occurred_at=NOW,
    )

    score, hits = evaluate(tx, Context(history={tx.entity_id: [tx]}))

    assert score == 0
    assert hits == []
    assert _outcome(score) == "approve"


def test_amount_vs_baseline_uses_prior_90_days():
    tx = Tx(amount=140_000, occurred_at=NOW)
    history = [
        Tx(amount=18_000, occurred_at=NOW - timedelta(days=12)),
        Tx(amount=22_000, occurred_at=NOW - timedelta(days=35)),
        Tx(amount=20_000, occurred_at=NOW - timedelta(days=62)),
        Tx(amount=1_000_000, occurred_at=NOW - timedelta(days=120)),
    ]

    score, hits = evaluate(tx, Context(history={tx.entity_id: history + [tx]}))
    amount_hit = next(hit for hit in hits if hit.rule_id == "amount_vs_baseline")

    assert amount_hit.severity == "high"
    assert amount_hit.evidence["history_count"] == 3
    assert amount_hit.evidence["avg_amount"] == 20_000
    assert amount_hit.evidence["multiple_of_average"] == 7
    assert score >= 35


def test_pass_through_money_in_out_detects_near_equal_recent_inflow():
    incoming = Tx(id=101, amount=500_000, direction="in", occurred_at=NOW - timedelta(minutes=42))
    tx = Tx(amount=498_700, direction="out", occurred_at=NOW)

    score, hits = evaluate(tx, Context(history={tx.entity_id: [incoming, tx]}))
    hit = next(hit for hit in hits if hit.rule_id == "pass_through_money_in_out")

    assert hit.score == 40
    assert hit.evidence["incoming_transaction_id"] == 101
    assert hit.evidence["time_delta_minutes"] == 42
    assert hit.evidence["amount_delta_pct"] <= 3
    assert _outcome(score) in {"review", "decline", "block_and_review"}


def test_geo_initiation_mismatch_high_risk_country():
    tx = Tx(
        amount=5_000,
        initiated_from_country="RU",
        entity_registered_country="US",
        usual_operating_countries=["US", "SG"],
        occurred_at=NOW,
    )

    score, hits = evaluate(tx, Context(history={tx.entity_id: [tx]}))
    hit = next(hit for hit in hits if hit.rule_id == "geo_initiation_mismatch")

    assert hit.severity == "high"
    assert hit.score == 35
    assert hit.evidence["high_risk_country"] is True
    assert _outcome(score) == "review"


def test_beneficiary_account_name_mismatch_uses_fuzzy_similarity():
    tx = Tx(
        amount=12_000,
        counterparty_name="Blue Harbor Logistics",
        counterparty_account_name="B H Consulting Services",
        occurred_at=NOW,
    )

    _, hits = evaluate(tx, Context(history={tx.entity_id: [tx]}))
    hit = next(hit for hit in hits if hit.rule_id == "beneficiary_account_name_mismatch")

    assert hit.score == 25
    assert hit.evidence["similarity"] < 75


def test_baseline_anomaly_escalates_to_review():
    tx = Tx(amount=140_000, occurred_at=NOW)
    history = [
        Tx(amount=18_000, occurred_at=NOW - timedelta(days=12)),
        Tx(amount=22_000, occurred_at=NOW - timedelta(days=35)),
        Tx(amount=20_000, occurred_at=NOW - timedelta(days=62)),
    ]

    score, hits = evaluate(tx, Context(history={tx.entity_id: history + [tx]}))

    assert "amount_vs_baseline" in {hit.rule_id for hit in hits}
    assert _outcome(score) in {"review", "decline", "block_and_review"}


def test_high_risk_initiation_plus_large_amount_declines_or_blocks():
    tx = Tx(
        amount=250_000,
        initiated_from_country="RU",
        entity_registered_country="US",
        usual_operating_countries=["US", "SG"],
        occurred_at=NOW,
    )

    score, hits = evaluate(tx, Context(history={tx.entity_id: [tx]}))

    assert {"geo_initiation_mismatch", "amt_large"} <= {hit.rule_id for hit in hits}
    assert _outcome(score) in {"decline", "block_and_review"}
