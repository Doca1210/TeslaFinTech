# screening_v2 Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Achieve sub-1s screening latency by replacing the O(N) linear scan with an inverted token index, eliminating all DB hits during search via an in-memory profile cache, and optimizing vector search with an LRU embedding cache and FAISS IVF index.

**Architecture:** NormalSearcher builds four structures at startup (IndexEntry list, token inverted index, phonetic inverted index, profile cache). Blocking reduces the comparison pool from ~80k to ~200–2000 entries. VectorSearcher is opt-in via `use_vector=True`, uses a module-level LRU dict for query embeddings, and switches to IndexIVFFlat for approximate ANN. Profile cache is shared across both searchers — single source of truth, zero DB hits at query time.

**Tech Stack:** Python 3.11, rapidfuzz, jellyfish, faiss-cpu, sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2), pytest, SQLAlchemy (SessionLocal from app.database)

---

## File Map

| File | Action | What changes |
|---|---|---|
| `backend/screening_v2/models.py` | Modify | Add `IndexEntry` dataclass |
| `backend/screening_v2/db_helpers.py` | Modify | Add `load_all_profiles()` bulk loader |
| `backend/screening_v2/normal_search.py` | Modify | New index structures, `_build_structures()`, union blocking, profile cache property |
| `backend/screening_v2/vector_search.py` | Modify | Accept `profile_cache`, LRU encode cache, IVF FAISS index, remove own DB fetch |
| `backend/screening_v2/engine.py` | Modify | Add `use_vector` param, wire shared profile cache, update `rebuild_indexes()` |
| `backend/tests/screening_v2/test_engine.py` | Modify | Fix `test_vector_used_when_normal_below_threshold` to pass `use_vector=True` |
| `backend/tests/screening_v2/test_vector_search.py` | Modify | Update fixture to pass `profile_cache` |
| `backend/tests/screening_v2/test_index_structures.py` | Create | Token index, phonetic index, profile cache, latency, concurrency tests |

---

## Task 1: Add IndexEntry to models.py

**Files:**
- Modify: `backend/screening_v2/models.py`
- Test: `backend/tests/screening_v2/test_index_structures.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/screening_v2/test_index_structures.py`:

```python
from screening_v2.models import IndexEntry


def test_index_entry_fields():
    entry = IndexEntry(
        norm_name="vladimir putin",
        phonetic="FLTMRPTN",
        entity_pk=42,
        list_code="OFAC_SDN",
        source_uid="SDN-12345",
        raw_name="PUTIN, Vladimir",
        entity_type="individual",
    )
    assert entry.norm_name == "vladimir putin"
    assert entry.phonetic == "FLTMRPTN"
    assert entry.entity_pk == 42
    assert entry.list_code == "OFAC_SDN"
    assert entry.source_uid == "SDN-12345"
    assert entry.raw_name == "PUTIN, Vladimir"
    assert entry.entity_type == "individual"


def test_index_entry_phonetic_none_for_entity():
    entry = IndexEntry(
        norm_name="rosneft",
        phonetic=None,
        entity_pk=7,
        list_code="OFAC_SDN",
        source_uid="SDN-99",
        raw_name="Rosneft Oil Company",
        entity_type="entity",
    )
    assert entry.phonetic is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py::test_index_entry_fields -v
```

Expected: `ImportError` — `IndexEntry` not defined yet.

- [ ] **Step 3: Add IndexEntry to models.py**

Open `backend/screening_v2/models.py` and add after the existing imports, before `NormalizedInput`:

```python
@dataclass(slots=True)
class IndexEntry:
    norm_name: str
    phonetic: str | None
    entity_pk: int
    list_code: str
    source_uid: str
    raw_name: str
    entity_type: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -v
```

Expected: 2 passed.

---

## Task 2: Add load_all_profiles() to db_helpers.py

**Files:**
- Modify: `backend/screening_v2/db_helpers.py`
- Test: `backend/tests/screening_v2/test_index_structures.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/screening_v2/test_index_structures.py`:

```python
import pytest
from app.database import SessionLocal
from screening_v2.db_helpers import load_all_profiles
from screening_v2.models import EntityProfile


@pytest.fixture(scope="module")
def all_profiles():
    return load_all_profiles(SessionLocal)


def test_load_all_profiles_returns_dict(all_profiles):
    assert isinstance(all_profiles, dict)
    assert len(all_profiles) > 0


def test_load_all_profiles_keyed_by_int(all_profiles):
    for pk in all_profiles:
        assert isinstance(pk, int)


def test_load_all_profiles_values_are_entity_profiles(all_profiles):
    for profile in all_profiles.values():
        assert isinstance(profile, EntityProfile)
        assert profile.source_uid
        assert profile.primary_name is not None


def test_load_all_profiles_includes_known_entity(all_profiles):
    # At least one profile should reference OFAC_SDN
    list_codes = {p.source_list_code for p in all_profiles.values()}
    assert "OFAC_SDN" in list_codes
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -k "profiles" -v
```

Expected: `ImportError` — `load_all_profiles` not defined.

- [ ] **Step 3: Add load_all_profiles to db_helpers.py**

Open `backend/screening_v2/db_helpers.py`. Add after the existing `fetch_entity_profiles_by_pks` function:

```python
def load_all_profiles(session_factory) -> dict[int, "EntityProfile"]:
    """Bulk-load all active entity profiles into memory. Call once at startup."""
    if not entity_pks:  # guard not needed — load all
        pass
    from app.models import Entity, SourceList
    session = session_factory()
    try:
        entities = (
            session.query(Entity)
            .filter(Entity.is_active == True)
            .all()
        )
        result = {}
        for entity in entities:
            sl = entity.source_list
            result[entity.id] = EntityProfile(
                source_uid=entity.source_uid,
                source_list_code=sl.code if sl else "",
                list_type=sl.list_type if sl else "sanctions",
                primary_name=entity.primary_name or "",
                entity_type=entity.entity_type or "individual",
                aliases=[n.full_name for n in entity.names if n.full_name],
                programs=[p.program_code for p in entity.programs],
                nationalities=[n.country for n in entity.nationalities],
                dob=[d.date_of_birth for d in entity.dates_of_birth],
                addresses=[a.address_line for a in entity.addresses if a.address_line],
                ids=[
                    {"type": i.id_type, "number": i.id_number, "country": i.id_country}
                    for i in entity.identifications
                ],
                remarks=entity.remarks,
                list_version=sl.last_published_at if sl else None,
            )
        return result
    finally:
        session.close()
```

**Important:** Remove the dead `if not entity_pks:` guard — that was copied incorrectly. The function body should start directly with `from app.models import Entity, SourceList`. Final correct version:

```python
def load_all_profiles(session_factory) -> dict[int, "EntityProfile"]:
    """Bulk-load all active entity profiles into memory. Call once at startup."""
    from app.models import Entity, SourceList
    session = session_factory()
    try:
        entities = (
            session.query(Entity)
            .filter(Entity.is_active == True)
            .all()
        )
        result = {}
        for entity in entities:
            sl = entity.source_list
            result[entity.id] = EntityProfile(
                source_uid=entity.source_uid,
                source_list_code=sl.code if sl else "",
                list_type=sl.list_type if sl else "sanctions",
                primary_name=entity.primary_name or "",
                entity_type=entity.entity_type or "individual",
                aliases=[n.full_name for n in entity.names if n.full_name],
                programs=[p.program_code for p in entity.programs],
                nationalities=[n.country for n in entity.nationalities],
                dob=[d.date_of_birth for d in entity.dates_of_birth],
                addresses=[a.address_line for a in entity.addresses if a.address_line],
                ids=[
                    {"type": i.id_type, "number": i.id_number, "country": i.id_country}
                    for i in entity.identifications
                ],
                remarks=entity.remarks,
                list_version=sl.last_published_at if sl else None,
            )
        return result
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -k "profiles" -v
```

Expected: 4 passed.

---

## Task 3: Refactor NormalSearcher — build structures

**Files:**
- Modify: `backend/screening_v2/normal_search.py`
- Test: `backend/tests/screening_v2/test_index_structures.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/screening_v2/test_index_structures.py`:

```python
from app.database import SessionLocal
from screening_v2.normal_search import NormalSearcher
from screening_v2.models import IndexEntry


@pytest.fixture(scope="module")
def normal_searcher():
    return NormalSearcher(SessionLocal)


def test_token_index_covers_all_entries(normal_searcher):
    # Every entry must be reachable via at least one token
    reachable = set()
    for positions in normal_searcher._token_index.values():
        reachable.update(positions)
    all_positions = set(range(len(normal_searcher._entries)))
    unreachable = all_positions - reachable
    # Allow entries with empty norm_name to be unreachable
    actually_unreachable = [
        i for i in unreachable if normal_searcher._entries[i].norm_name
    ]
    assert len(actually_unreachable) == 0, (
        f"{len(actually_unreachable)} entries with non-empty norm_name not in token index"
    )


def test_phonetic_index_covers_individual_entries(normal_searcher):
    reachable_via_phonetic = set()
    for positions in normal_searcher._phonetic_index.values():
        reachable_via_phonetic.update(positions)
    individual_with_phonetic = [
        i for i, e in enumerate(normal_searcher._entries)
        if e.entity_type == "individual" and e.phonetic is not None
    ]
    missing = [i for i in individual_with_phonetic if i not in reachable_via_phonetic]
    assert len(missing) == 0, f"{len(missing)} individual entries missing from phonetic index"


def test_profile_cache_covers_all_entity_pks(normal_searcher):
    all_pks = {e.entity_pk for e in normal_searcher._entries}
    cached_pks = set(normal_searcher.profile_cache.keys())
    missing = all_pks - cached_pks
    assert len(missing) == 0, f"{len(missing)} entity_pks missing from profile cache"


def test_entries_are_index_entry_instances(normal_searcher):
    assert len(normal_searcher._entries) > 0
    for entry in normal_searcher._entries[:10]:
        assert isinstance(entry, IndexEntry)
        assert isinstance(entry.entity_pk, int)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -k "token_index or phonetic_index or profile_cache or entries_are" -v
```

Expected: `AttributeError` — `_token_index`, `_phonetic_index`, `profile_cache` don't exist yet.

- [ ] **Step 3: Replace NormalSearcher.__init__ and _build_index**

Open `backend/screening_v2/normal_search.py`. Replace the entire file content with:

```python
from __future__ import annotations
import logging
from rapidfuzz.fuzz import token_set_ratio
import jellyfish
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

            if normalized.phonetic and normalized.entity_type == "individual":
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
```

- [ ] **Step 4: Run the structural tests**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -v
```

Expected: all tests pass (some may be slow on first run due to index build).

- [ ] **Step 5: Run the existing NormalSearcher tests to confirm no regressions**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_normal_search.py -v
```

Expected: 8 passed.

---

## Task 4: Refactor VectorSearcher

**Files:**
- Modify: `backend/screening_v2/vector_search.py`
- Modify: `backend/tests/screening_v2/test_vector_search.py`

- [ ] **Step 1: Update the VectorSearcher test fixture**

Open `backend/tests/screening_v2/test_vector_search.py`. Replace the fixture:

```python
import pytest
from app.database import SessionLocal
from screening_v2.vector_search import VectorSearcher
from screening_v2.normalizer import Normalizer
from screening_v2.db_helpers import load_all_profiles

_normalizer = Normalizer()


@pytest.fixture(scope="module")
def searcher():
    profile_cache = load_all_profiles(SessionLocal)
    return VectorSearcher(SessionLocal, profile_cache=profile_cache)
```

Leave all five test functions unchanged beneath the fixture.

- [ ] **Step 2: Run vector tests to confirm they currently fail with the new signature**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_vector_search.py -v
```

Expected: `TypeError` — `VectorSearcher.__init__` doesn't accept `profile_cache` yet.

- [ ] **Step 3: Replace vector_search.py**

Replace the full content of `backend/screening_v2/vector_search.py` with:

```python
from __future__ import annotations
import logging
import numpy as np
from rapidfuzz.fuzz import token_set_ratio
import jellyfish
from .models import NormalizedInput, MatchCandidate, ScoreBreakdown, EntityProfile
from .normalizer import Normalizer
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
_EMBED_CACHE_MAX = 1024

# Module-level LRU dict — GIL-protected, safe for concurrent reads/writes
_embed_cache: dict[str, np.ndarray] = {}


def _encode_query(model, text: str) -> np.ndarray:
    """Encode text with a simple module-level LRU dict. Thread-safe under GIL."""
    cached = _embed_cache.get(text)
    if cached is not None:
        return cached
    vec = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0].astype(np.float32)
    if len(_embed_cache) >= _EMBED_CACHE_MAX:
        _embed_cache.pop(next(iter(_embed_cache)))
    _embed_cache[text] = vec
    return vec


class VectorSearcher:
    def __init__(self, session_factory, profile_cache: dict[int, EntityProfile] | None = None):
        self._session_factory = session_factory
        self._normalizer = Normalizer()
        self._model = None
        self._index = None
        self._index_map: list[tuple[str, int, str, str, str]] = []
        self._profile_cache: dict[int, EntityProfile] = profile_cache if profile_cache is not None else {}
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
        ).astype(np.float32)

        dim = vectors.shape[1]
        nlist = min(100, max(1, len(names) // 10))
        quantizer = faiss.IndexFlatIP(dim)
        self._index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        self._index.train(vectors)
        self._index.add(vectors)
        self._index.nprobe = min(10, nlist)
        logger.info("VectorSearcher: IVF index built (%d vectors, nlist=%d)", self._index.ntotal, nlist)

    def search(self, normalized: NormalizedInput, normal_candidates: list[MatchCandidate]) -> list[MatchCandidate]:
        if self._index is None or self._model is None:
            return []

        already_found = {c.entity_id for c in normal_candidates}

        query_vector = _encode_query(self._model, normalized.cleaned)
        cosine_scores, indices = self._index.search(query_vector.reshape(1, -1), TOP_K)

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

        results: list[MatchCandidate] = []
        for combined, entity_pk, entity_id, full_name, tsr, jw, cosine in candidates_data:
            profile = self._profile_cache.get(entity_pk)
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

    def rebuild(self, profile_cache: dict[int, EntityProfile] | None = None) -> None:
        if profile_cache is not None:
            self._profile_cache = profile_cache
        self._index = None
        self._index_map.clear()
        self._build_index()
```

- [ ] **Step 4: Run vector tests**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_vector_search.py -v
```

Expected: 5 passed.

---

## Task 5: Update ScreeningEngine

**Files:**
- Modify: `backend/screening_v2/engine.py`

- [ ] **Step 1: Replace engine.py**

Replace the full content of `backend/screening_v2/engine.py` with:

```python
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
        self._vector = VectorSearcher(session_factory, profile_cache=self._normal.profile_cache)
        self._session_factory = session_factory

    def screen(self, name: str, entity_type: str = "auto", use_vector: bool = False) -> ScreeningResult:
        start = time.perf_counter()

        if entity_type == "auto":
            entity_type = self._normalizer.detect_type(name)

        normalized = self._normalizer.normalize(name, entity_type)
        search_methods: list[str] = []

        candidates = self._normal.search(normalized)
        search_methods.append("normal")

        top_score = candidates[0].match_score if candidates else 0.0
        if use_vector and top_score < HIGH_CONFIDENCE:
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
        self._normal.rebuild()
        self._vector.rebuild(profile_cache=self._normal.profile_cache)
```

- [ ] **Step 2: Run the full screening_v2 test suite**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/ -v --ignore=backend/tests/screening_v2/test_engine.py
```

Expected: all pass except engine tests (not yet fixed).

---

## Task 6: Fix existing engine tests

**Files:**
- Modify: `backend/tests/screening_v2/test_engine.py`

- [ ] **Step 1: Fix the broken test**

Open `backend/tests/screening_v2/test_engine.py`. The test at line 44 asserts vector is in methods unconditionally. Update it to opt in to vector:

Replace:
```python
def test_vector_used_when_normal_below_threshold(engine):
    # A name with no obvious watchlist entry should trigger vector search
    result = engine.screen("Bartholomew Kingsborough", "individual")
    assert "vector" in result.search_methods
```

With:
```python
def test_vector_used_when_normal_below_threshold(engine):
    # Pass use_vector=True — vector only runs when explicitly opted in
    result = engine.screen("Bartholomew Kingsborough", "individual", use_vector=True)
    assert "vector" in result.search_methods
```

- [ ] **Step 2: Run the full engine test suite**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_engine.py -v
```

Expected: 13 passed.

- [ ] **Step 3: Run the complete existing test suite**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/ -v
```

Expected: all 42 original tests pass.

---

## Task 7: Add performance and concurrency tests

**Files:**
- Modify: `backend/tests/screening_v2/test_index_structures.py`

- [ ] **Step 1: Add latency benchmark test**

Append to `backend/tests/screening_v2/test_index_structures.py`:

```python
import time
import threading
from screening_v2.engine import ScreeningEngine


@pytest.fixture(scope="module")
def engine():
    return ScreeningEngine(SessionLocal)


def test_normal_path_latency_10_calls_under_500ms(engine):
    names = [
        "Vladimir Putin", "Sergei Shoigu", "John Smith",
        "Ahmed Al Rashidi", "Maria Garcia", "Wang Wei",
        "Ivan Petrov", "Nadia Hassan", "Carlos Lopez", "Anna Muller",
    ]
    start = time.perf_counter()
    for name in names:
        engine.screen(name, "individual")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 500, f"10 normal-path screenings took {elapsed_ms:.0f}ms, expected <500ms"


def test_vector_opt_in_does_not_encode_on_default(engine):
    """Default use_vector=False must never call model.encode — verified via search_methods."""
    result = engine.screen("Bartholomew Kingsborough", "individual")
    assert "vector" not in result.search_methods


def test_vector_opt_in_runs_when_requested(engine):
    result = engine.screen("Bartholomew Kingsborough", "individual", use_vector=True)
    assert "vector" in result.search_methods


def test_lru_cache_hit_same_result(engine):
    """Two calls with identical name must return identical normalized input and match score."""
    r1 = engine.screen("Vladimir Putin", "individual", use_vector=True)
    r2 = engine.screen("Vladimir Putin", "individual", use_vector=True)
    assert r1.verdict == r2.verdict
    assert r1.confidence == r2.confidence


def test_concurrent_screen_and_rebuild(engine):
    errors: list[Exception] = []
    results: list = []

    def screen_loop():
        for _ in range(5):
            try:
                r = engine.screen("Vladimir Putin", "individual")
                results.append(r)
            except Exception as exc:
                errors.append(exc)

    def rebuild_once():
        try:
            engine.rebuild_indexes()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=screen_loop) for _ in range(5)]
    threads.append(threading.Thread(target=rebuild_once))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errors during concurrent access: {errors}"
    for r in results:
        assert r.verdict in ("MATCH", "REVIEW", "NO_MATCH")
        assert isinstance(r.input_normalized, str)
```

- [ ] **Step 2: Run all new tests**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/test_index_structures.py -v
```

Expected: all pass. The latency test may take a few seconds on first run due to index build — that's expected (one-time startup cost, not per-request).

- [ ] **Step 3: Run the complete test suite one final time**

```bash
cd /Users/user/Desktop/Fintech/TeslaFinTech && \
  python -m pytest backend/tests/screening_v2/ -v
```

Expected: all tests pass (42 original + new index/performance tests).
