"""Layer B — behavioral anomaly detection.

Uses `entity_transaction_history` (T-011) for the originator/beneficiary account.

TODO (T-006): implement the three signals from the design doc:
    - amount anomaly (z-score vs 90-day rolling avg/stddev, z > 3 -> REVIEW)
    - pass-through (inbound ~ outbound within 24h, ratio > 0.85 -> REVIEW)
    - new counterparty (first payment to this beneficiary -> minor REVIEW signal)

An account with no history must return NO_MATCH (no penalty for unknown accounts).
"""

from __future__ import annotations

from app.payments.layers.base import LayerContext, ScreeningLayer
from app.payments.layers.registry import registry
from app.payments.schemas import LayerResult, PaymentInstruction


class BehavioralLayer(ScreeningLayer):
    name = "behavioral"

    def run(self, payment: PaymentInstruction, context: LayerContext) -> LayerResult:
        raise NotImplementedError


registry.register(BehavioralLayer())
