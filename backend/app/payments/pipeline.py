"""Screening pipeline — wires intake, layers, composer, and outputs together.

This is the runtime implementation of the section 2.3 diagram:

    PaymentIntake -> [ScreeningLayer, ...] -> VerdictComposer -> outputs

Layers are pulled from `app.payments.layers.registry` so adding/removing a layer
(Layer D, etc.) requires no change to this file.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.payments.composer import VerdictComposer
from app.payments.intake import PaymentIntake
from app.payments.layers.base import LayerContext, ScreeningLayer
from app.payments.layers.registry import registry
from app.payments.outputs.audit_store import AuditStore
from app.payments.outputs.post_match import PostMatchWorkflow
from app.payments.outputs.review_queue import ReviewQueue
from app.payments.schemas import ScreeningDecision
from screening.models import ScreeningVerdict


class ScreeningPipeline:
    def __init__(
        self,
        db: Session,
        *,
        intake: PaymentIntake | None = None,
        layers: list[ScreeningLayer] | None = None,
        composer: VerdictComposer | None = None,
        audit_store: AuditStore | None = None,
        review_queue: ReviewQueue | None = None,
        post_match_workflow: PostMatchWorkflow | None = None,
    ) -> None:
        self.db = db
        self.intake = intake or PaymentIntake()
        self.layers = layers if layers is not None else registry.all()
        self.composer = composer or VerdictComposer()
        self.audit_store = audit_store or AuditStore(db)
        self.review_queue = review_queue or ReviewQueue(db)
        self.post_match_workflow = post_match_workflow or PostMatchWorkflow(db)

    def screen(self, raw_payload: dict[str, Any]) -> ScreeningDecision:
        """Run one payment instruction through the full pipeline.

        TODO: run `self.layers` concurrently (e.g. asyncio.gather / thread pool)
        once layers are implemented — they are required to be independent.
        """
        payment = self.intake.normalize(raw_payload)
        context = LayerContext(db=self.db)

        layer_results = [layer.run(payment, context) for layer in self.layers]

        decision = self.composer.compose(payment, layer_results)

        self.audit_store.persist(payment, decision)

        if decision.verdict == ScreeningVerdict.REVIEW:
            self.review_queue.enqueue(payment, decision)
        elif decision.verdict == ScreeningVerdict.MATCH:
            self.post_match_workflow.handle(payment, decision)

        return decision
