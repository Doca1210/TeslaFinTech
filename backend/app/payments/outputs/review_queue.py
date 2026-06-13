"""Review queue — creates `review_cases` for REVIEW verdicts (section 4.4).

TODO (T-007): add the `review_cases` / `analyst_decisions` SQLAlchemy models,
derive `priority` from confidence + amount, and create a row here when the
composer returns REVIEW. MATCH verdicts must NOT create review cases — those go
to the post-match workflow instead.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.payments.schemas import PaymentInstruction, ScreeningDecision


class ReviewQueue:
    """Enqueues REVIEW-verdict payments for analyst triage."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(self, payment: PaymentInstruction, decision: ScreeningDecision) -> None:
        raise NotImplementedError
