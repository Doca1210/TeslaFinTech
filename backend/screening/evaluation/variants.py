from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from screening.engine import ScreeningEngine
from screening.matcher import NameMatcher, TokenSetMatcher
from screening.models import WatchlistEntity


@dataclass(frozen=True)
class AlgorithmVariant:
    name: str
    description: str
    config: dict[str, Any]
    factory: Callable[[list[WatchlistEntity]], Any]


def default_variants() -> list[AlgorithmVariant]:
    return [
        AlgorithmVariant(
            name="hybrid_default",
            description="Hybrid fuzzy + phonetic matcher with default thresholds.",
            config={
                "matcher": "NameMatcher",
                "match_threshold": 92.0,
                "review_threshold": 78.0,
            },
            factory=_build_hybrid_default,
        ),
        AlgorithmVariant(
            name="hybrid_strict",
            description="Hybrid matcher with higher thresholds (fewer flags).",
            config={
                "matcher": "NameMatcher",
                "match_threshold": 95.0,
                "review_threshold": 85.0,
            },
            factory=_build_hybrid_strict,
        ),
        AlgorithmVariant(
            name="hybrid_sensitive",
            description="Hybrid matcher with lower thresholds (more flags).",
            config={
                "matcher": "NameMatcher",
                "match_threshold": 88.0,
                "review_threshold": 72.0,
            },
            factory=_build_hybrid_sensitive,
        ),
        AlgorithmVariant(
            name="token_set_baseline",
            description="Baseline A/B arm: token-set fuzzy ratio only.",
            config={
                "matcher": "TokenSetMatcher",
                "match_threshold": 92.0,
                "review_threshold": 78.0,
            },
            factory=_build_token_set_baseline,
        ),
        AlgorithmVariant(
            name="v2_cascade",
            description="New engine: type-aware normalisation + patronym strip + FAISS vector fallback.",
            config={
                "normal_block_threshold": 55,
                "high_confidence": 0.85,
                "low_confidence": 0.60,
                "vector_model": "paraphrase-multilingual-MiniLM-L12-v2",
                "top_k_vector": 50,
            },
            factory=_build_v2_cascade,
        ),
    ]


def get_variant(name: str) -> AlgorithmVariant:
    variants = {variant.name: variant for variant in default_variants()}
    if name not in variants:
        known = ", ".join(sorted(variants))
        raise KeyError(f"Unknown variant '{name}'. Available: {known}")
    return variants[name]


def _build_hybrid_default(watchlist: list[WatchlistEntity]) -> ScreeningEngine:
    return ScreeningEngine(
        watchlist,
        matcher=NameMatcher(match_threshold=92.0, review_threshold=78.0),
        match_threshold=92.0,
        review_threshold=78.0,
    )


def _build_hybrid_strict(watchlist: list[WatchlistEntity]) -> ScreeningEngine:
    return ScreeningEngine(
        watchlist,
        matcher=NameMatcher(match_threshold=95.0, review_threshold=85.0),
        match_threshold=95.0,
        review_threshold=85.0,
    )


def _build_hybrid_sensitive(watchlist: list[WatchlistEntity]) -> ScreeningEngine:
    return ScreeningEngine(
        watchlist,
        matcher=NameMatcher(match_threshold=88.0, review_threshold=72.0),
        match_threshold=88.0,
        review_threshold=72.0,
    )


def _build_token_set_baseline(watchlist: list[WatchlistEntity]) -> ScreeningEngine:
    return ScreeningEngine(
        watchlist,
        matcher=TokenSetMatcher(match_threshold=92.0, review_threshold=78.0),
        match_threshold=92.0,
        review_threshold=78.0,
    )


def _build_v2_cascade(watchlist: list[WatchlistEntity]):
    from app.database import SessionLocal
    from screening.evaluation.v2_adapter import V2EngineAdapter
    return V2EngineAdapter(SessionLocal)
