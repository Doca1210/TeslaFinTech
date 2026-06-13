"""Adapter that wraps screening_v2.ScreeningEngine to satisfy the pipeline interface.

The ABTestPipeline reads three things from any engine's result:
  result.verdict          → ScreeningVerdict enum
  result.confidence       → float
  result.matched_entities → list where [0].entity.id is the entity_id string

This module converts screening_v2.ScreeningResult into that shape without
touching the existing evaluation infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass
from screening.models import ScreeningVerdict, Transaction, WatchlistEntity


@dataclass
class _FakeEntity:
    id: str


@dataclass
class _FakeMatchedEntity:
    entity: _FakeEntity
    confidence: float


@dataclass
class _AdaptedResult:
    verdict: ScreeningVerdict
    confidence: float
    matched_entities: list[_FakeMatchedEntity]
    explanation: str


class V2EngineAdapter:
    """Wraps screening_v2.ScreeningEngine for use inside ABTestPipeline."""

    def __init__(self, session_factory):
        from screening_v2.engine import ScreeningEngine
        self._engine = ScreeningEngine(session_factory)

    def screen(self, transaction: Transaction) -> _AdaptedResult:
        v2 = self._engine.screen(transaction.counterparty_name)

        verdict = ScreeningVerdict(v2.verdict)

        matched_entities = [
            _FakeMatchedEntity(
                entity=_FakeEntity(id=c.entity_id),
                confidence=c.match_score,
            )
            for c in v2.candidates
        ]

        return _AdaptedResult(
            verdict=verdict,
            confidence=v2.confidence,
            matched_entities=matched_entities,
            explanation=v2.explanation,
        )
