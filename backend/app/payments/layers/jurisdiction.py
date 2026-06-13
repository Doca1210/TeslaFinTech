"""Layer C — jurisdiction / location risk.

TODO (T-012): load a static risk tier map (HIGH/MEDIUM/LOW per country) from config
and apply the rules from the design doc:
    - beneficiary country HIGH -> REVIEW
    - originator_bank_country mismatch with originator_country -> REVIEW
    - any HIGH country in countries_in_scope -> REVIEW

Must never override a sanctions MATCH (the composer handles precedence; this layer
only reports its own verdict).
"""

from __future__ import annotations

from app.payments.layers.base import LayerContext, ScreeningLayer
from app.payments.layers.registry import registry
from app.payments.schemas import LayerResult, PaymentInstruction


class JurisdictionLayer(ScreeningLayer):
    name = "jurisdiction"

    def run(self, payment: PaymentInstruction, context: LayerContext) -> LayerResult:
        raise NotImplementedError


registry.register(JurisdictionLayer())
