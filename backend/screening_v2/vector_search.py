from __future__ import annotations
import logging
import numpy as np
from rapidfuzz.fuzz import token_set_ratio
import jellyfish
from .models import NormalizedInput, MatchCandidate, ScoreBreakdown
from .normalizer import Normalizer
from .db_helpers import fetch_entity_profiles_by_pks
from .scoring import (
    VECTOR_MIN_FUZZY,
    all_significant_tokens_match,
    apply_entity_coverage_penalty,
    reorder_resistant_similarity,
)

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 50
TOP_N = 5


class VectorSearcher:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._normalizer = Normalizer()
        self._model = None
        self._index = None
        # Each entry: (full_name, entity_pk, list_code, source_uid, entity_type)
        self._index_map: list[tuple[str, int, str, str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        import faiss
        from sentence_transformers import SentenceTransformer
        from app.models import EntityName, Entity, SourceList

        self._model = SentenceTransformer(MODEL_NAME)

        session = self._session_factory()
        try:
            rows = (
                session.query(
                    EntityName.full_name,
                    Entity.id,
                    Entity.source_uid,
                    SourceList.code,
                    Entity.entity_type,
                )
                .join(Entity, EntityName.entity_id == Entity.id)
                .join(SourceList, Entity.source_list_id == SourceList.id)
                .filter(Entity.is_active == True)
                .filter(EntityName.full_name.isnot(None))
                .all()
            )
        finally:
            session.close()

        if not rows:
            logger.warning("VectorSearcher: no entity names found, index is empty")
            return

        self._index_map = [
            (r[0], r[1], r[3], r[2], r[4] or "individual") for r in rows
        ]
        names = [r[0] for r in rows]

        logger.info("VectorSearcher: encoding %d names...", len(names))
        vectors = self._model.encode(
            names, normalize_embeddings=True, show_progress_bar=False, batch_size=256
        )
        self._index = faiss.IndexFlatIP(vectors.shape[1])
        self._index.add(vectors.astype(np.float32))
        logger.info("VectorSearcher: FAISS index built (%d vectors)", self._index.ntotal)

    def search(self, normalized: NormalizedInput, normal_candidates: list[MatchCandidate]) -> list[MatchCandidate]:
        if self._index is None or self._model is None:
            return []

        already_found = {c.entity_id for c in normal_candidates}

        query_vector = self._model.encode(
            [normalized.cleaned], normalize_embeddings=True, show_progress_bar=False
        )
        cosine_scores, indices = self._index.search(query_vector.astype(np.float32), TOP_K)

        seen_entity_pks: set[int] = set()
        candidates_data = []

        for cosine_score, idx in zip(cosine_scores[0], indices[0]):
            if idx < 0:
                continue
            full_name, entity_pk, list_code, source_uid, entity_type = self._index_map[idx]
            entity_id = f"{list_code}:{source_uid}"
            if entity_id in already_found or entity_pk in seen_entity_pks:
                continue
            seen_entity_pks.add(entity_pk)

            norm_candidate = self._normalizer.normalize(full_name, entity_type).cleaned
            tsr = token_set_ratio(normalized.cleaned, norm_candidate) / 100.0
            jw = reorder_resistant_similarity(normalized.cleaned, norm_candidate)
            fuzzy_score = tsr * 0.53 + jw * 0.47

            if fuzzy_score < VECTOR_MIN_FUZZY:
                continue
            if normalized.entity_type == "individual" and not all_significant_tokens_match(
                normalized.cleaned, norm_candidate
            ):
                continue
            if normalized.entity_type == "entity":
                fuzzy_score = apply_entity_coverage_penalty(
                    fuzzy_score, normalized.cleaned, norm_candidate
                )
                if fuzzy_score < VECTOR_MIN_FUZZY:
                    continue

            combined = 0.6 * fuzzy_score + 0.4 * float(cosine_score)
            candidates_data.append((combined, entity_pk, entity_id, full_name, tsr, jw, float(cosine_score)))

        if not candidates_data:
            return []

        candidates_data.sort(key=lambda x: x[0], reverse=True)
        candidates_data = candidates_data[:TOP_N]
        top_pks = [x[1] for x in candidates_data]
        profiles = fetch_entity_profiles_by_pks(self._session_factory, top_pks)

        results: list[MatchCandidate] = []
        for combined, entity_pk, entity_id, full_name, tsr, jw, cosine in candidates_data:
            profile = profiles.get(entity_pk)
            if profile is None:
                continue
            is_primary = full_name == profile.primary_name
            results.append(MatchCandidate(
                entity_id=entity_id,
                match_score=combined,
                match_method="vector",
                matched_name=full_name,
                matched_via_alias=not is_primary,
                alias_hit=full_name if not is_primary else None,
                entity_profile=profile,
                score_breakdown=ScoreBreakdown(
                    token_set_ratio=tsr,
                    jaro_winkler=jw,
                    phonetic_match=None,
                    cosine_similarity=cosine,
                    weights_used=[0.6, 0.4],
                ),
            ))

        return results

    def rebuild(self) -> None:
        """Call after list ingestion to rebuild the FAISS index."""
        self._index = None
        self._index_map.clear()
        self._build_index()
