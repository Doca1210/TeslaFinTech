from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScreeningVerdict(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


class EntityType(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class WatchlistEntity(BaseModel):
    id: str
    full_name: str
    entity_type: EntityType = EntityType.INDIVIDUAL
    country: str | None = None
    aliases: list[str] = Field(default_factory=list)
    list_source: str = "PEP"
    risk_category: str = "PEP"
    notes: str | None = None


class Transaction(BaseModel):
    transaction_id: str
    counterparty_name: str
    counterparty_country: str | None = None
    amount: float | None = None
    currency: str | None = None
    direction: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MatchSignal(BaseModel):
    name: str
    score: float
    method: str
    detail: str


class MatchedEntity(BaseModel):
    entity: WatchlistEntity
    confidence: float
    signals: list[MatchSignal]


class ScreeningResult(BaseModel):
    transaction_id: str
    verdict: ScreeningVerdict
    confidence: float
    counterparty_name: str
    counterparty_country: str | None = None
    matched_entities: list[MatchedEntity] = Field(default_factory=list)
    explanation: str
    screened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    audit: dict[str, Any] = Field(default_factory=dict)
