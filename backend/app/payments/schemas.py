"""Pydantic schemas shared across the payment screening pipeline.

These define the contracts between pipeline stages (intake -> layers -> composer ->
outputs). Field sets follow docs/design/priority_backlog.md section 4 (data model);
fill in/extend as T-001 and T-003 land.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from screening.models import MatchSignal, MatchedEntity, ScreeningVerdict


class PaymentInstruction(BaseModel):
    """Normalized payment instruction produced by PaymentIntake (section 4.1)."""

    transaction_id: str

    amount: float
    currency: str

    originator_name: str
    originator_country: str | None = None
    originator_account: str | None = None
    originator_bank_country: str | None = None

    beneficiary_name: str
    beneficiary_country: str | None = None
    beneficiary_account: str | None = None
    beneficiary_bank_country: str | None = None

    countries_in_scope: list[str] = Field(default_factory=list)
    purpose: str | None = None

    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class LayerResult(BaseModel):
    """Output of a single ScreeningLayer (section 4.2 `layers_executed` entry)."""

    layer: str
    verdict: ScreeningVerdict
    score: float
    signals: list[MatchSignal] = Field(default_factory=list)
    matched_entities: list[MatchedEntity] = Field(default_factory=list)
    reason: str
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ScreeningDecision(BaseModel):
    """Composer output: the persisted/returned result of a /screen call (section 4.2)."""

    transaction_id: str
    verdict: ScreeningVerdict
    confidence: float
    layers_executed: list[LayerResult] = Field(default_factory=list)
    explanation: str
    list_versions: dict[str, str | None] = Field(default_factory=dict)
    engine_version: str | None = None
    screened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float | None = None
