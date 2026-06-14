"""Behavioral AML anomaly detection over ``EntityTransaction`` history.

Marble-inspired (https://github.com/checkmarble/marble) rule engine.
Each rule is a pure predicate that inspects one transaction plus the
entity's recent history and returns a :class:`RuleHit` when it fires.
Scores are summed into a :class:`TransactionDecision` whose ``outcome``
is derived from configurable thresholds.

No name / sanctions matching here — this script only looks at the
behavior of transactions tied to an ``Entity``. Cross-referencing with
the sanctions schema (``Entity``, ``EntityName``, ...) is handled by a
separate pipeline.

Run standalone (in-memory SQLite demo)::

    python -m app.aml_detect
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
import sys
from typing import Iterable

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app import models as tm


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
HIGH_RISK_COUNTRIES = {"IR", "KP", "SY", "CU", "RU", "BY", "MM", "VE"}

LARGE_AMOUNT_USD = 10_000.0
VELOCITY_WINDOW_H = 24
VELOCITY_MAX = 5
STRUCT_WINDOW_D = 7
STRUCT_MIN, STRUCT_MAX = 9_000.0, 9_999.0
STRUCT_MIN_COUNT = 3
DORMANT_DAYS = 90
DORMANT_REAWAKE_AMOUNT = 5_000.0
BASELINE_LOOKBACK_DAYS = 90
BASELINE_MIN_HISTORY = 3
BASELINE_REVIEW_MULTIPLE = 5
BASELINE_DECLINE_MULTIPLE = 10
PASS_THROUGH_WINDOW_H = 48
PASS_THROUGH_MAX_DELTA_PCT = 3.0
ACCOUNT_NAME_SIMILARITY_THRESHOLD = 75.0

THRESHOLDS = {"review": 30, "decline": 60, "block_and_review": 90}


# --------------------------------------------------------------------------- #
# Rule result
# --------------------------------------------------------------------------- #
@dataclass
class RuleHit:
    rule_id: str
    severity: str
    score: float
    reason: str        # short, machine-style summary
    explanation: str   # plain-English narrative for an analyst
    evidence: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Context: entity history indexed for fast lookback
# --------------------------------------------------------------------------- #
@dataclass
class Context:
    history: dict[int, list]  # entity_id -> [EntityTransaction] sorted by occurred_at


def load_context(session: Session) -> Context:
    rows = session.scalars(
        select(tm.EntityTransaction).order_by(tm.EntityTransaction.occurred_at)
    ).all()
    hist: dict[int, list] = defaultdict(list)
    for r in rows:
        hist[r.entity_id].append(r)
    return Context(history=hist)


def _window(history: list, end: datetime, delta: timedelta) -> list:
    start = end - delta
    return [t for t in history if start <= t.occurred_at <= end]


def _prior_window(history: list, end: datetime, delta: timedelta) -> list:
    start = end - delta
    return [t for t in history if start <= t.occurred_at < end]


def _country(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


def _country_set(values) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    return {cc for cc in (_country(v) for v in values) if cc}


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #
def _r_amount(tx) -> RuleHit | None:
    if tx.amount >= LARGE_AMOUNT_USD:
        return RuleHit(
            "amt_large", "high", 35,
            f"Amount {tx.amount:.2f} {tx.currency} ≥ {LARGE_AMOUNT_USD:.0f}",
            (
                f"This transaction of {tx.amount:,.2f} {tx.currency} is at or above the "
                f"large-transaction reporting threshold of {LARGE_AMOUNT_USD:,.0f}. "
                "Large single movements warrant additional scrutiny because they are a "
                "common vector for layering and integration of illicit funds."
            ),
            {"amount": tx.amount, "threshold": LARGE_AMOUNT_USD},
        )
    return None


def _r_velocity(tx, hist: list) -> RuleHit | None:
    window = _window(hist, tx.occurred_at, timedelta(hours=VELOCITY_WINDOW_H))
    if len(window) > VELOCITY_MAX:
        return RuleHit(
            "velocity_24h", "medium", 25,
            f"{len(window)} txns in {VELOCITY_WINDOW_H}h (limit {VELOCITY_MAX})",
            (
                f"The entity executed {len(window)} transactions in the last "
                f"{VELOCITY_WINDOW_H} hours, exceeding the expected limit of "
                f"{VELOCITY_MAX}. Bursts of activity in a short window can indicate "
                "automated movements, rapid layering, or account takeover."
            ),
            {"count": len(window), "window_h": VELOCITY_WINDOW_H},
        )
    return None


def _r_structuring(tx, hist: list) -> RuleHit | None:
    if not (STRUCT_MIN <= tx.amount <= STRUCT_MAX):
        return None
    window = _window(hist, tx.occurred_at, timedelta(days=STRUCT_WINDOW_D))
    matches = [t for t in window if STRUCT_MIN <= t.amount <= STRUCT_MAX]
    if len(matches) >= STRUCT_MIN_COUNT:
        return RuleHit(
            "structuring_7d", "high", 40,
            f"{len(matches)} sub-threshold txns in {STRUCT_WINDOW_D}d (smurfing)",
            (
                f"Over the last {STRUCT_WINDOW_D} days the entity made {len(matches)} "
                f"transactions sized between {STRUCT_MIN:,.0f} and {STRUCT_MAX:,.0f}, "
                f"each just under the {LARGE_AMOUNT_USD:,.0f} reporting threshold. "
                "This pattern is classic 'smurfing' / structuring intended to evade "
                "currency-transaction reporting requirements."
            ),
            {"count": len(matches), "window_d": STRUCT_WINDOW_D,
             "band": [STRUCT_MIN, STRUCT_MAX]},
        )
    return None


def _r_geo(tx) -> RuleHit | None:
    cc = (tx.counterparty_country or "").upper()
    if cc in HIGH_RISK_COUNTRIES:
        return RuleHit(
            "geo_high_risk", "high", 30,
            f"Counterparty in high-risk jurisdiction {cc}",
            (
                f"The counterparty is located in {cc}, a jurisdiction flagged as "
                "high-risk due to sanctions, FATF grey/black-listing, or weak AML "
                "controls. Exposure here materially raises sanctions-evasion and "
                "terror-finance risk."
            ),
            {"country": cc},
        )
    return None


def _r_dormant(tx, hist: list) -> RuleHit | None:
    prior = [t for t in hist if t.occurred_at < tx.occurred_at]
    if not prior:
        return None
    gap = tx.occurred_at - prior[-1].occurred_at
    if gap >= timedelta(days=DORMANT_DAYS) and tx.amount >= DORMANT_REAWAKE_AMOUNT:
        return RuleHit(
            "dormant_reawake", "medium", 20,
            f"Reactivation after {gap.days}d dormancy with {tx.amount:.2f}",
            (
                f"The account was dormant for {gap.days} days and has just moved "
                f"{tx.amount:,.2f} {tx.currency}. Sudden reactivation of a long-idle "
                "account with a sizeable transaction is a known mule / sleeper-account "
                "indicator and should be reviewed."
            ),
            {"dormant_days": gap.days, "amount": tx.amount},
        )
    return None


def _r_amount_vs_baseline(tx, hist: list) -> RuleHit | None:
    prior = _prior_window(hist, tx.occurred_at, timedelta(days=BASELINE_LOOKBACK_DAYS))
    amounts = [float(t.amount) for t in prior if getattr(t, "amount", 0) is not None]
    if len(amounts) < BASELINE_MIN_HISTORY:
        return None

    avg_amount = mean(amounts)
    if avg_amount <= 0:
        return None

    review_threshold = max(LARGE_AMOUNT_USD, avg_amount * BASELINE_REVIEW_MULTIPLE)
    decline_threshold = max(25_000.0, avg_amount * BASELINE_DECLINE_MULTIPLE)
    current_amount = float(tx.amount)
    multiple = current_amount / avg_amount

    if current_amount > decline_threshold:
        severity = "critical"
        score = 50
        threshold = decline_threshold
    elif current_amount > review_threshold:
        severity = "high"
        score = 35
        threshold = review_threshold
    else:
        return None

    return RuleHit(
        "amount_vs_baseline", severity, score,
        f"Amount is {multiple:.1f}x the 90-day average",
        (
            f"This payment of {current_amount:,.2f} {tx.currency} is materially above "
            f"the entity's recent baseline average of {avg_amount:,.2f}. Large moves "
            "relative to normal account behavior are more suspicious than large moves "
            "in isolation and should be checked against the stated business purpose."
        ),
        {
            "lookback_days": BASELINE_LOOKBACK_DAYS,
            "history_count": len(amounts),
            "avg_amount": round(avg_amount, 2),
            "median_amount": round(median(amounts), 2),
            "current_amount": current_amount,
            "multiple_of_average": round(multiple, 2),
            "threshold": round(threshold, 2),
        },
    )


def _r_pass_through_money_in_out(tx, hist: list) -> RuleHit | None:
    if (tx.direction or "").lower() != "out" or not tx.amount:
        return None

    prior = _prior_window(hist, tx.occurred_at, timedelta(hours=PASS_THROUGH_WINDOW_H))
    incoming = [t for t in prior if (getattr(t, "direction", "") or "").lower() == "in"]
    if not incoming:
        return None

    outgoing_amount = float(tx.amount)
    matches = []
    for candidate in incoming:
        incoming_amount = float(candidate.amount)
        delta_pct = abs(outgoing_amount - incoming_amount) / outgoing_amount * 100
        if delta_pct <= PASS_THROUGH_MAX_DELTA_PCT:
            time_delta = tx.occurred_at - candidate.occurred_at
            matches.append((delta_pct, time_delta, candidate))

    if not matches:
        return None

    delta_pct, time_delta, incoming_tx = sorted(matches, key=lambda item: (item[0], item[1]))[0]
    minutes = int(time_delta.total_seconds() // 60)
    incoming_amount = float(incoming_tx.amount)

    return RuleHit(
        "pass_through_money_in_out", "high", 40,
        f"Outgoing transfer mirrors incoming funds from {minutes} minutes earlier",
        (
            f"The account received {incoming_amount:,.2f} {tx.currency} and sent "
            f"{outgoing_amount:,.2f} {tx.currency} out {minutes} minutes later. "
            "Rapid in-and-out movement with near-equal amounts is a classic layering "
            "signal because the account may be acting as a temporary pass-through."
        ),
        {
            "incoming_amount": incoming_amount,
            "outgoing_amount": outgoing_amount,
            "amount_delta_pct": round(delta_pct, 2),
            "time_delta_minutes": minutes,
            "incoming_transaction_id": getattr(incoming_tx, "id", None),
        },
    )


def _r_geo_initiation_mismatch(tx) -> RuleHit | None:
    initiated = _country(getattr(tx, "initiated_from_country", None))
    if not initiated:
        return None

    registered = _country(getattr(tx, "entity_registered_country", None))
    usual = _country_set(getattr(tx, "usual_operating_countries", None))
    expected = set(usual)
    if registered:
        expected.add(registered)

    if initiated in expected:
        return None

    high_risk = initiated in HIGH_RISK_COUNTRIES
    severity = "high" if high_risk else "medium"
    score = 35 if high_risk else 25

    return RuleHit(
        "geo_initiation_mismatch", severity, score,
        f"Payment initiated from unexpected country {initiated}",
        (
            f"The payment order was initiated from {initiated}, which is outside the "
            "entity's registered or usual operating countries. Location anomalies can "
            "indicate account takeover, proxy operation, or activity that needs manual "
            "KYB and ownership review."
        ),
        {
            "initiated_from_country": initiated,
            "entity_registered_country": registered,
            "usual_operating_countries": sorted(usual),
            "expected_countries": sorted(expected),
            "high_risk_country": high_risk,
        },
    )


def _r_beneficiary_account_name_mismatch(tx) -> RuleHit | None:
    counterparty_name = getattr(tx, "counterparty_name", None)
    account_name = getattr(tx, "counterparty_account_name", None)
    if _is_blank(counterparty_name) or _is_blank(account_name):
        return None

    similarity = float(fuzz.token_set_ratio(counterparty_name, account_name))
    if similarity >= ACCOUNT_NAME_SIMILARITY_THRESHOLD:
        return None

    return RuleHit(
        "beneficiary_account_name_mismatch", "medium", 25,
        f"Beneficiary name/account-name similarity is {similarity:.0f}",
        (
            f"The payment beneficiary name '{counterparty_name}' does not closely "
            f"match the account name '{account_name}'. Verification-of-payee style "
            "mismatches can indicate misdirection, mule accounts, or weak payment "
            "instructions."
        ),
        {
            "counterparty_name": counterparty_name,
            "counterparty_account_name": account_name,
            "similarity": round(similarity, 2),
            "threshold": ACCOUNT_NAME_SIMILARITY_THRESHOLD,
        },
    )


def evaluate(tx, ctx: Context) -> tuple[float, list[RuleHit]]:
    hist = ctx.history.get(tx.entity_id, [])
    hits = [
        h for h in (
            _r_amount(tx),
            _r_velocity(tx, hist),
            _r_structuring(tx, hist),
            _r_geo(tx),
            _r_dormant(tx, hist),
            _r_amount_vs_baseline(tx, hist),
            _r_pass_through_money_in_out(tx, hist),
            _r_geo_initiation_mismatch(tx),
            _r_beneficiary_account_name_mismatch(tx),
        ) if h is not None
    ]
    return sum(h.score for h in hits), hits


def _outcome(score: float) -> str:
    if score >= THRESHOLDS["block_and_review"]:
        return "block_and_review"
    if score >= THRESHOLDS["decline"]:
        return "decline"
    if score >= THRESHOLDS["review"]:
        return "review"
    return "approve"


# --------------------------------------------------------------------------- #
# Scan
# --------------------------------------------------------------------------- #
def scan(session: Session, transactions: Iterable | None = None) -> list:
    ctx = load_context(session)
    pending = transactions if transactions is not None else session.scalars(
        select(tm.EntityTransaction).where(tm.EntityTransaction.status == "pending")
    ).all()

    decisions = []
    for tx in pending:
        score, hits = evaluate(tx, ctx)
        outcome = _outcome(score)
        decision = tm.TransactionDecision(
            transaction_id=tx.id,
            entity_id=tx.entity_id,
            score=score,
            outcome=outcome,
            hits=[
                tm.TransactionRuleHit(
                    rule_id=h.rule_id,
                    severity=h.severity,
                    score=h.score,
                    reason=h.reason,
                    explanation=h.explanation,
                    evidence=h.evidence,
                )
                for h in hits
            ],
        )
        if outcome != "approve":
            tx.status = "flagged"
        session.add(decision)
        decisions.append(decision)
    session.commit()
    return decisions


# --------------------------------------------------------------------------- #
# Standalone demo
# --------------------------------------------------------------------------- #
def _demo() -> None:
    """Run the engine against an in-memory SQLite using the real ``Base``.

    Because ``backend.app.models`` is imported at module top, all tables
    (entities, entity_transactions, transaction_decisions, ...) are already
    registered on ``Base.metadata`` and will be created here.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)

    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        # Minimal source list + entities to satisfy FKs.
        sl = tm.SourceList(code="DEMO", name="Demo", list_type="sanctions")
        s.add(sl); s.flush()
        acme = tm.Entity(source_list_id=sl.id, source_uid="acme", entity_type="entity",
                         primary_name="Acme Corp", raw={})
        bob = tm.Entity(source_list_id=sl.id, source_uid="bob", entity_type="individual",
                        primary_name="Bob Smith", raw={})
        s.add_all([acme, bob]); s.flush()

        txs = [
            # amt_large
            tm.EntityTransaction(entity_id=acme.id, occurred_at=now, amount=25_000,
                                 direction="out", counterparty_country="US"),
            # velocity_24h: 6 small txns within 24h
            *[
                tm.EntityTransaction(entity_id=bob.id, occurred_at=now - timedelta(hours=i),
                                     amount=200, direction="out", counterparty_country="US")
                for i in range(6)
            ],
            # structuring_7d
            *[
                tm.EntityTransaction(entity_id=acme.id, occurred_at=now - timedelta(days=i),
                                     amount=9_500, direction="out", counterparty_country="US")
                for i in range(3)
            ],
            # dormant + geo_high_risk
            tm.EntityTransaction(entity_id=acme.id, occurred_at=now - timedelta(days=200),
                                 amount=100, direction="out", counterparty_country="US"),
            tm.EntityTransaction(entity_id=acme.id, occurred_at=now + timedelta(seconds=1),
                                 amount=7_500, direction="out", counterparty_country="IR"),
        ]
        s.add_all(txs); s.commit()

        for d in scan(s):
            print(f"tx={d.transaction_id} score={d.score:>5.0f} {d.outcome:<18} "
                  f"hits={[h.rule_id for h in d.hits]} "
                  f"explanations={[h.explanation for h in d.hits]}")


if __name__ == "__main__":
    _demo()
