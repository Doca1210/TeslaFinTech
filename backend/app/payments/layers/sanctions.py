"""Layer A — sanctions name screening.

Wraps the existing `screening.engine.ScreeningEngine` (frozen — do not tune
matcher/thresholds here, see docs/design/priority_backlog.md T-004).

TODO (T-004): screen originator and beneficiary independently and return the
highest-confidence hit as this layer's LayerResult, including matched entity
profiles (name, aliases, programs, DOB, nationalities) for explainability.
"""

from __future__ import annotations

from app.payments.layers.base import LayerContext, ScreeningLayer
from app.payments.layers.registry import registry
from app.payments.schemas import LayerResult, PaymentInstruction


class SanctionsLayer(ScreeningLayer):
    name = "sanctions"

    def run(self, payment: PaymentInstruction, context: LayerContext) -> LayerResult:
        raise NotImplementedError


registry.register(SanctionsLayer())
