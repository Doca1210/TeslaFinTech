from __future__ import annotations
import logging
from rapidfuzz.fuzz import token_set_ratio
import jellyfish
from .models import NormalizedInput, MatchCandidate, ScoreBreakdown
from .normalizer import Normalizer
from .db_helpers import fetch_entity_profiles_by_pks

logger = logging.getLogger(__name__)

BLOCK_THRESHOLD = 55       # token_set_ratio (0–100 scale) to enter candidate pool
HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.60
TOP_N = 5


class NormalSearcher:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._normalizer = Normalizer()
        # Each entry: (normalized_name, entity_pk, list_code, source_uid, raw_name, entity_type)
        self._index: list[tuple[str, int, str, str, str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        from app.models import EntityName, Entity, SourceList
        session = self._session_factory()
        try:
            rows = (
                session.query(
                    EntityName.full_name,
                    Entity.id,
                    Entity.source_uid,
                    Entity.entity_type,
                    SourceList.code,
                )
                .join(Entity, EntityName.entity_id == Entity.id)
                .join(SourceList, Entity.source_list_id == SourceList.id)
                .filter(Entity.is_active == True)
                .filter(EntityName.full_name.isnot(None))
                .all()
            )
        finally:
            session.close()

        for full_name, entity_pk, source_uid, entity_type, list_code in rows:
            etype = entity_type or "individual"
            normalized = self._normalizer.normalize(full_name, etype)
            self._index.append((normalized.cleaned, entity_pk, list_code, source_uid, full_name, etype))

        logger.info("NormalSearcher: built index with %d name entries", len(self._index))

    def search(self, normalized: NormalizedInput) -> list[MatchCandidate]:
        # 1. Blocking pass — find entities whose normalized names score above threshold
        best_per_entity: dict[int, tuple[float, str, str, str, str]] = {}
        # value: (tsr_score, list_code, source_uid, raw_name, entity_type)

        for norm_name, entity_pk, list_code, source_uid, raw_name, entity_type in self._index:
            if not norm_name:
                continue
            tsr = token_set_ratio(normalized.cleaned, norm_name)
            if tsr <= BLOCK_THRESHOLD:
                continue
            score = tsr / 100.0
            if entity_pk not in best_per_entity or score > best_per_entity[entity_pk][0]:
                best_per_entity[entity_pk] = (score, list_code, source_uid, raw_name, entity_type)

        if not best_per_entity:
            return []

        # 2. Detailed scoring on candidates that passed blocking
        scored: list[tuple] = []
        for entity_pk, (_, list_code, source_uid, raw_name, entity_type) in best_per_entity.items():
            norm_name_clean = self._normalizer.normalize(raw_name, entity_type).cleaned
            tsr = token_set_ratio(normalized.cleaned, norm_name_clean) / 100.0
            jw = jellyfish.jaro_winkler_similarity(normalized.cleaned, norm_name_clean)

            if normalized.phonetic and normalized.entity_type == "individual":
                candidate_phonetic = jellyfish.nysiis(norm_name_clean) if norm_name_clean else ""
                phonetic_score: float | None = 1.0 if normalized.phonetic == candidate_phonetic else 0.0
                final = tsr * 0.40 + jw * 0.35 + phonetic_score * 0.25
                weights = [0.40, 0.35, 0.25]
            else:
                phonetic_score = None
                final = tsr * 0.53 + jw * 0.47
                weights = [0.53, 0.47]

            scored.append((final, entity_pk, list_code, source_uid, raw_name, tsr, jw, phonetic_score, weights))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:TOP_N]

        # 3. Batch fetch profiles for top candidates
        top_pks = [x[1] for x in top]
        profiles = fetch_entity_profiles_by_pks(self._session_factory, top_pks)

        # 4. Build MatchCandidate list
        results: list[MatchCandidate] = []
        for final, entity_pk, list_code, source_uid, raw_name, tsr, jw, ph, weights in top:
            profile = profiles.get(entity_pk)
            if profile is None:
                continue
            is_primary = raw_name == profile.primary_name
            results.append(MatchCandidate(
                entity_id=f"{list_code}:{source_uid}",
                match_score=final,
                match_method="normal",
                matched_name=raw_name,
                matched_via_alias=not is_primary,
                alias_hit=raw_name if not is_primary else None,
                entity_profile=profile,
                score_breakdown=ScoreBreakdown(
                    token_set_ratio=tsr,
                    jaro_winkler=jw,
                    phonetic_match=ph,
                    cosine_similarity=None,
                    weights_used=weights,
                ),
            ))

        return results

    def rebuild(self) -> None:
        """Call after list ingestion to refresh the in-memory index."""
        self._index.clear()
        self._build_index()
