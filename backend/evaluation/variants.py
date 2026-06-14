from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AlgorithmVariant:
    name: str
    description: str
    config: dict[str, Any]
    factory: Callable[..., Any]


def default_variants() -> list[AlgorithmVariant]:
    return [
        AlgorithmVariant(
            name="v2_cascade",
            description="Type-aware normalisation + patronym strip + FAISS vector fallback.",
            config={
                "normal_block_threshold": 55,
                "high_confidence": 0.85,
                "low_confidence": 0.72,
                "vector_min_fuzzy": 0.62,
                "vector_token_match_threshold": 0.82,
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


def _build_v2_cascade(_watchlist: Any) -> Any:
    from app.database import SessionLocal
    from evaluation.v2_adapter import V2EngineAdapter
    return V2EngineAdapter(SessionLocal)
