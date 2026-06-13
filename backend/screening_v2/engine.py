from __future__ import annotations
import time
import logging
from .models import NormalizedInput, ScreeningResult, MatchCandidate
from .normalizer import Normalizer
from .normal_search import NormalSearcher, HIGH_CONFIDENCE, LOW_CONFIDENCE
from .vector_search import VectorSearcher

logger = logging.getLogger(__name__)


class ScreeningEngine:
    def __init__(self, session_factory):
        self._normalizer = Normalizer()
        self._normal = NormalSearcher(session_factory)
        self._vector = VectorSearcher(session_factory)
        self._session_factory = session_factory

    def screen(self, name: str, entity_type: str = "auto") -> ScreeningResult:
        start = time.perf_counter()

        if entity_type == "auto":
            entity_type = self._normalizer.detect_type(name)

        normalized = self._normalizer.normalize(name, entity_type)
        search_methods: list[str] = []

        candidates = self._normal.search(normalized)
        search_methods.append("normal")

        top_score = candidates[0].match_score if candidates else 0.0
        if top_score < HIGH_CONFIDENCE:
            vector_candidates = self._vector.search(normalized, candidates)
            search_methods.append("vector")
            candidates = self._merge(candidates, vector_candidates)

        duration_ms = int((time.perf_counter() - start) * 1000)
        return self._build_result(normalized, candidates, search_methods, duration_ms)

    def _merge(self, normal: list[MatchCandidate], vector: list[MatchCandidate]) -> list[MatchCandidate]:
        by_id: dict[str, MatchCandidate] = {c.entity_id: c for c in normal}
        for vc in vector:
            if vc.entity_id not in by_id or vc.match_score > by_id[vc.entity_id].match_score:
                by_id[vc.entity_id] = vc
        return sorted(by_id.values(), key=lambda c: c.match_score, reverse=True)[:5]

    def _build_result(
        self,
        normalized: NormalizedInput,
        candidates: list[MatchCandidate],
        search_methods: list[str],
        duration_ms: int,
    ) -> ScreeningResult:
        if not candidates:
            return ScreeningResult(
                verdict="NO_MATCH",
                confidence=0.0,
                input_raw=normalized.raw,
                input_type=normalized.entity_type,
                input_normalized=normalized.cleaned,
                search_methods=search_methods,
                search_duration_ms=duration_ms,
                candidates=[],
                explanation=(
                    f"Input '{normalized.raw}' returned no candidates across all active source lists."
                ),
            )

        top = candidates[0]
        score = top.match_score
        list_type = top.entity_profile.list_type

        if score >= HIGH_CONFIDENCE:
            verdict = "MATCH" if list_type == "sanctions" else "REVIEW"
        elif score >= LOW_CONFIDENCE:
            verdict = "REVIEW"
        else:
            verdict = "NO_MATCH"

        explanation = self._build_explanation(normalized, candidates, verdict)

        return ScreeningResult(
            verdict=verdict,
            confidence=score,
            input_raw=normalized.raw,
            input_type=normalized.entity_type,
            input_normalized=normalized.cleaned,
            search_methods=search_methods,
            search_duration_ms=duration_ms,
            candidates=candidates,
            explanation=explanation,
        )

    @staticmethod
    def _build_explanation(
        normalized: NormalizedInput,
        candidates: list[MatchCandidate],
        verdict: str,
    ) -> str:
        top = candidates[0]
        p = top.entity_profile
        via = f" via alias '{top.alias_hit}'" if top.matched_via_alias else ""
        programs = ", ".join(p.programs) if p.programs else "unknown program"
        method = top.match_method

        if verdict == "NO_MATCH":
            return (
                f"Input '{normalized.raw}' did not match any watchlist entity "
                f"(highest score: {top.match_score:.0%} on '{top.matched_name}', below threshold)."
            )
        return (
            f"Input '{normalized.raw}' matched '{top.matched_name}'{via} "
            f"({top.entity_id}) with {top.match_score:.0%} confidence "
            f"using {method} search. "
            f"Subject to: {programs}. "
            f"List: {p.source_list_code} ({p.list_type}). "
            f"Verdict: {verdict}."
        )

    def rebuild_indexes(self) -> None:
        """Rebuild both in-memory indexes after a list ingest."""
        self._normal.rebuild()
        self._vector.rebuild()