"""Post-MATCH workflow — compliance notification for MATCH verdicts.

TODO (T-013): create a compliance event record (or field on `screening_results`),
log "payment blocked", and mock-notify the compliance team (console log or
webhook stub). Surface the action taken via GET /screen/{id}.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.payments.schemas import PaymentInstruction, ScreeningDecision


class PostMatchWorkflow:
    """Handles downstream actions for MATCH-verdict payments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def handle(self, payment: PaymentInstruction, decision: ScreeningDecision) -> None:
        raise NotImplementedError
