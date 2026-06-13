"""Base class for pluggable screening layers (Layer A/B/C/... in section 2.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.payments.schemas import LayerResult, PaymentInstruction


@dataclass
class LayerContext:
    """Shared resources made available to every layer for a single /screen call.

    Extend this as layers need more shared state (e.g. risk config for Layer C,
    transaction history repo for Layer B). Keep it read-only / side-effect free —
    layers report results to the composer, they do not write to outputs directly.
    """

    db: Session
    extra: dict[str, Any] | None = None


class ScreeningLayer(ABC):
    """A single, independently pluggable risk assessment for a payment.

    Implementations must be safe to run concurrently with other layers and must
    not depend on the outcome of any other layer — the composer is the only stage
    that sees results across layers.
    """

    #: Unique, stable identifier used in `ScreeningDecision.layers_executed`.
    name: str

    @abstractmethod
    def run(self, payment: PaymentInstruction, context: LayerContext) -> LayerResult:
        """Assess `payment` and return this layer's verdict/score/signals."""
        raise NotImplementedError
