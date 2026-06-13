from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class NormalizedInput:
    raw: str
    cleaned: str
    phonetic: str | None
    entity_type: Literal["individual", "entity"]


@dataclass
class ScoreBreakdown:
    token_set_ratio: float
    jaro_winkler: float
    phonetic_match: float | None
    cosine_similarity: float | None
    weights_used: list[float]


@dataclass
class EntityProfile:
    source_uid: str
    source_list_code: str
    list_type: str                    # "sanctions" | "pep"
    primary_name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)
    nationalities: list[str] = field(default_factory=list)
    dob: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    ids: list[dict] = field(default_factory=list)
    remarks: str | None = None
    list_version: str | None = None


@dataclass
class MatchCandidate:
    entity_id: str                    # "{LIST_CODE}:{source_uid}"
    match_score: float
    match_method: Literal["normal", "vector"]
    matched_name: str
    matched_via_alias: bool
    alias_hit: str | None
    entity_profile: EntityProfile
    score_breakdown: ScoreBreakdown


@dataclass
class ScreeningResult:
    verdict: Literal["MATCH", "REVIEW", "NO_MATCH"]
    confidence: float
    input_raw: str
    input_type: Literal["individual", "entity"]
    input_normalized: str
    search_methods: list[str]
    search_duration_ms: int
    candidates: list[MatchCandidate]
    explanation: str
