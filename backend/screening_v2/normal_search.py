from __future__ import annotations
import logging
from rapidfuzz.fuzz import token_set_ratio
from .models import NormalizedInput, MatchCandidate, ScoreBreakdown, IndexEntry, EntityProfile
from .normalizer import Normalizer
from .db_helpers import load_all_profiles
from .scoring import apply_entity_coverage_penalty, reorder_resistant_similarity

logger = logging.getLogger(__name__)

BLOCK_THRESHOLD = 55
HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.72
TOP_N = 5


class NormalSearcher:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._normalizer = Normalizer()
        self._entries: list[IndexEntry] = []
        self._token_index: dict[str, list[int]] = {}
        self._phonetic_index: dict[str, list[int]] = {}
        self._profile_cache: dict[int, EntityProfile] = {}
        self._build_index()

    def _build_structures(self) -> tuple[
        list[IndexEntry],
        dict[str, list[int]],
        dict[str, list[int]],
        dict[int, EntityProfile],
    ]:
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

        profile_cache = load_all_profiles(self._session_factory)
        entries: list[IndexEntry] = []
        token_index: dict[str, list[int]] = {}
        phonetic_index: dict[str, list[int]] = {}

        for full_name, entity_pk, source_uid, entity_type, list_code in rows:
            etype = entity_type or "individual"
            normalized = self._normalizer.normalize(full_name, etype)

            entry = IndexEntry(
                norm_name=normalized.cleaned,
                phonetic=normalized.phonetic,
                entity_pk=entity_pk,
                list_code=list_code,
                source_uid=source_uid,
                raw_name=full_name,
                entity_type=etype,
            )
            pos = len(entries)
            entries.append(entry)

            for token in normalized.cleaned.split():
                if token:
                    token_index.setdefault(token, []).append(pos)

            if normalized.phonetic:
                phonetic_index.setdefault(normalized.phonetic, []).append(pos)

        return entries, token_index, phonetic_index, profile_cache

    def _build_index(self) -> None:
        entries, token_index, phonetic_index, profile_cache = self._build_structures()
        self._entries = entries
        self._token_index = token_index
        self._phonetic_index = phonetic_index
        self._profile_cache = profile_cache
        logger.info("NormalSearcher: built index with %d name entries", len(self._entries))

    @property
    def profile_cache(self) -> dict[int, EntityProfile]:
        return self._profile_cache

    def search(self, normalized: NormalizedInput) -> list[MatchCandidate]:
        # 1. Blocking — union of token and phonetic posting lists
        query_tokens = [t for t in normalized.cleaned.split() if t]
        candidate_positions: set[int] = set()
        for token in query_tokens:
            candidate_positions.update(self._token_index.get(token, []))
        if normalized.phonetic:
            candidate_positions.update(self._phonetic_index.get(normalized.phonetic, []))

        if not candidate_positions:
            return []

        # 2. Fuzzy filter — best score per entity_pk
        best_per_entity: dict[int, tuple[float, int]] = {}
        for pos in candidate_positions:
            entry = self._entries[pos]
            if not entry.norm_name:
                continue
            tsr = token_set_ratio(normalized.cleaned, entry.norm_name)
            if tsr <= BLOCK_THRESHOLD:
                continue
            score = tsr / 100.0
            if entry.entity_pk not in best_per_entity or score > best_per_entity[entry.entity_pk][0]:
                best_per_entity[entry.entity_pk] = (score, pos)

        if not best_per_entity:
            return []

        # 3. Detail scoring — no re-normalization, no DB hit
        scored: list[tuple] = []
        for entity_pk, (_, pos) in best_per_entity.items():
            entry = self._entries[pos]
            tsr = token_set_ratio(normalized.cleaned, entry.norm_name) / 100.0
            jw = reorder_resistant_similarity(normalized.cleaned, entry.norm_name)

            if normalized.phonetic and normalized.entity_type == "individual" and entry.entity_type == "individual":
                candidate_phonetic = entry.phonetic or ""
                phonetic_score: float | None = 1.0 if normalized.phonetic == candidate_phonetic else 0.0
                final = tsr * 0.40 + jw * 0.35 + phonetic_score * 0.25
                weights = [0.40, 0.35, 0.25]
            else:
                phonetic_score = None
                final = tsr * 0.53 + jw * 0.47
                weights = [0.53, 0.47]
                final = apply_entity_coverage_penalty(final, normalized.cleaned, entry.norm_name)

            scored.append((final, entity_pk, entry, tsr, jw, phonetic_score, weights))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:TOP_N]

        # 4. Build MatchCandidate — profile from cache, no DB
        results: list[MatchCandidate] = []
        for final, entity_pk, entry, tsr, jw, ph, weights in top:
            profile = self._profile_cache.get(entity_pk)
            if profile is None:
                continue
            is_primary = entry.raw_name == profile.primary_name
            results.append(MatchCandidate(
                entity_id=f"{entry.list_code}:{entry.source_uid}",
                match_score=final,
                match_method="normal",
                matched_name=entry.raw_name,
                matched_via_alias=not is_primary,
                alias_hit=entry.raw_name if not is_primary else None,
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
        self._build_index()
