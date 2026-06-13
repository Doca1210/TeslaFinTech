"""Audit store — persists `payments` + `screening_results` (section 4.1, 4.2).

Append-only: `screening_results` rows are never updated after insert.

TODO (T-003): add SQLAlchemy models for `payments` and `screening_results` to
app/models.py, then persist both rows here within a single transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.payments.schemas import PaymentInstruction, ScreeningDecision


class AuditStore:
    """Writes the immutable audit trail for every /screen call."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def persist(self, payment: PaymentInstruction, decision: ScreeningDecision) -> None:
        raise NotImplementedError
