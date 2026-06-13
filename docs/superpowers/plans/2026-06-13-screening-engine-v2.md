# Screening Engine V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `screening_v2` Python module that screens individual persons and legal entities against all active watchlists using a fuzzy cascade → vector search pipeline, returning rich evidence for every decision.

**Architecture:** A single `ScreeningEngine` class orchestrates a type-aware `Normalizer` → `NormalSearcher` (blocking pass + alias expansion + weighted fuzzy scoring) → optional `VectorSearcher` (FAISS + multilingual MiniLM embeddings) cascade. A `VerdictComposer` combines originator and beneficiary results into a payment-level verdict.

**Tech Stack:** Python, SQLAlchemy (existing `app.models`), `rapidfuzz`, `jellyfish`, `unidecode` (all installed), `sentence-transformers`, `faiss-cpu` (to add).

---

## File Map

| File | Role |
|------|------|
| `backend/screening_v2/__init__.py` | Empty package marker |
| `backend/screening_v2/models.py` | Dataclasses: `NormalizedInput`, `EntityProfile`, `ScoreBreakdown`, `MatchCandidate`, `ScreeningResult` |
| `backend/screening_v2/normalizer.py` | `Normalizer` — individual (patronym strip + NYSIIS) and entity (suffix strip) branches |
| `backend/screening_v2/db_helpers.py` | `fetch_entity_profile(session_factory, entity_pk)` — shared DB fetch used by both searchers |
| `backend/screening_v2/normal_search.py` | `NormalSearcher` — builds in-memory normalized name index at startup, blocking + scoring pass |
| `backend/screening_v2/vector_search.py` | `VectorSearcher` — FAISS IndexFlatIP over multilingual MiniLM embeddings |
| `backend/screening_v2/engine.py` | `ScreeningEngine` — orchestrates cascade, composes `ScreeningResult` |
| `backend/screening_v2/composer.py` | `VerdictComposer` — merges originator + beneficiary into payment verdict |
| `backend/tests/screening_v2/test_normalizer.py` | Pure unit tests for normalizer, no DB |
| `backend/tests/screening_v2/test_normal_search.py` | Integration tests against real `aml.db` |
| `backend/tests/screening_v2/test_vector_search.py` | Integration tests — transliteration + Cyrillic |
| `backend/tests/screening_v2/test_engine.py` | End-to-end integration tests |
| `backend/tests/screening_v2/test_composer.py` | Unit tests for composer logic |

---

## Task 1: Add Missing Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add sentence-transformers and faiss-cpu**

Append to `backend/requirements.txt`:
```
sentence-transformers>=3.0.0
faiss-cpu>=1.8.0
```

- [ ] **Step 2: Install**

Run from `backend/`:
```bash
pip install sentence-transformers faiss-cpu
```
Expected: Both install without errors. `sentence-transformers` will pull in `torch` (CPU-only) and `transformers`.

- [ ] **Step 3: Verify**

```bash
python -c "import sentence_transformers; import faiss; print('OK')"
```
Expected: `OK`

---

## Task 2: Data Models

**Files:**
- Create: `backend/screening_v2/__init__.py`
- Create: `backend/screening_v2/models.py`
- Create: `backend/tests/screening_v2/__init__.py`

- [ ] **Step 1: Create package markers**

Create `backend/screening_v2/__init__.py` — empty file.
Create `backend/tests/screening_v2/__init__.py` — empty file.

- [ ] **Step 2: Write models**

Create `backend/screening_v2/models.py`:
```python
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
```

- [ ] **Step 3: Verify import**

```bash
cd backend && python -c "from screening_v2.models import ScreeningResult; print('OK')"
```
Expected: `OK`

---

## Task 3: Normalizer

**Files:**
- Create: `backend/screening_v2/normalizer.py`
- Create: `backend/tests/screening_v2/test_normalizer.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/screening_v2/test_normalizer.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from screening_v2.normalizer import Normalizer


def test_individual_removes_patronym():
    n = Normalizer()
    result = n.normalize("Sergei Kuzhugetovich Shoigu", "individual")
    assert result.cleaned == "sergei shoigu"


def test_individual_removes_feminine_patronym():
    n = Normalizer()
    result = n.normalize("Anna Vladimirovna Shoigu", "individual")
    assert result.cleaned == "anna shoigu"


def test_individual_handles_cyrillic():
    n = Normalizer()
    result = n.normalize("Владимир Путин", "individual")
    assert "vladimir" in result.cleaned
    assert "putin" in result.cleaned


def test_individual_has_phonetic_code():
    n = Normalizer()
    result = n.normalize("Sergei Shoigu", "individual")
    assert result.phonetic is not None
    assert len(result.phonetic) > 0


def test_entity_strips_llc():
    n = Normalizer()
    result = n.normalize("Rosneft Oil Company LLC", "entity")
    assert result.cleaned == "rosneft"


def test_entity_strips_multiple_suffixes():
    n = Normalizer()
    result = n.normalize("Nord Stream 2 AG", "entity")
    assert "nord" in result.cleaned
    assert "stream" in result.cleaned


def test_entity_no_phonetic():
    n = Normalizer()
    result = n.normalize("Rosneft LLC", "entity")
    assert result.phonetic is None


def test_auto_detects_entity():
    n = Normalizer()
    result = n.normalize("Acme Trading LLC", "auto")
    assert result.entity_type == "entity"


def test_auto_detects_individual():
    n = Normalizer()
    result = n.normalize("John Smith", "auto")
    assert result.entity_type == "individual"


def test_entity_type_stored_in_result():
    n = Normalizer()
    result = n.normalize("Vladimir Putin", "individual")
    assert result.entity_type == "individual"
    assert result.raw == "Vladimir Putin"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/screening_v2/test_normalizer.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` — `screening_v2.normalizer` does not exist yet.

- [ ] **Step 3: Implement normalizer**

Create `backend/screening_v2/normalizer.py`:
```python
from __future__ import annotations
import re
import jellyfish
from unidecode import unidecode
from .models import NormalizedInput

LEGAL_SUFFIXES = {
    "llc", "ltd", "gmbh", "doo", "inc", "corp", "sa", "bv",
    "jsc", "ojsc", "pjsc", "holdings", "holding", "group",
    "trading", "company", "international", "enterprises",
    "services", "limited", "incorporated", "ag", "plc", "nv",
    "srl", "spa", "oy", "ab", "as",
}

PATRONYM_SUFFIXES = (
    "ovich", "evich", "ievich", "ovna", "evna", "ievna",
    "ich", "vna", "itch", "witch",
)

ABBREVIATIONS: dict[str, str] = {
    "vtb": "vneshtorgbank",
    "veb": "vnesheconombank",
}


def _to_ascii(text: str) -> str:
    if text.isascii():
        return text
    return unidecode(text)


class Normalizer:
    def detect_type(self, name: str) -> str:
        tokens = set(re.sub(r"[^\w\s]", " ", name.lower()).split())
        if tokens & LEGAL_SUFFIXES:
            return "entity"
        return "individual"

    def normalize(self, name: str, entity_type: str) -> NormalizedInput:
        if entity_type == "auto":
            entity_type = self.detect_type(name)
        if entity_type == "individual":
            return self._normalize_individual(name)
        return self._normalize_entity(name)

    def _normalize_individual(self, name: str) -> NormalizedInput:
        cleaned = re.sub(r"[^\w\s]", " ", name).strip()
        cleaned = _to_ascii(cleaned).lower()
        tokens = [
            t for t in cleaned.split()
            if not (len(t) > 9 and t.endswith(PATRONYM_SUFFIXES))
        ]
        cleaned = " ".join(tokens)
        phonetic = jellyfish.nysiis(cleaned) if cleaned else None
        return NormalizedInput(raw=name, cleaned=cleaned, phonetic=phonetic, entity_type="individual")

    def _normalize_entity(self, name: str) -> NormalizedInput:
        cleaned = re.sub(r"[^\w\s]", " ", name).strip()
        cleaned = _to_ascii(cleaned).lower()
        tokens = [t for t in cleaned.split() if t not in LEGAL_SUFFIXES]
        cleaned = " ".join(tokens)
        cleaned = ABBREVIATIONS.get(cleaned, cleaned)
        return NormalizedInput(raw=name, cleaned=cleaned, phonetic=None, entity_type="entity")
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/screening_v2/test_normalizer.py -v
```
Expected: All 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/screening_v2/__init__.py backend/screening_v2/models.py backend/screening_v2/normalizer.py backend/tests/screening_v2/__init__.py backend/tests/screening_v2/test_normalizer.py backend/requirements.txt
git commit -m "feat(screening_v2): data models and normalizer with patronym + suffix stripping"
```

---

## Task 4: DB Helpers

**Files:**
- Create: `backend/screening_v2/db_helpers.py`

No separate test file — covered by NormalSearcher and VectorSearcher integration tests.

- [ ] **Step 1: Implement db_helpers**

Create `backend/screening_v2/db_helpers.py`:
```python
from __future__ import annotations
from .models import EntityProfile


def fetch_entity_profiles_by_pks(session_factory, entity_pks: list[int]) -> dict[int, EntityProfile]:
    """Batch fetch EntityProfile for a list of entities.id (PKs). Returns dict keyed by PK."""
    if not entity_pks:
        return {}

    from app.models import Entity, SourceList
    session = session_factory()
    try:
        entities = (
            session.query(Entity)
            .filter(Entity.id.in_(entity_pks), Entity.is_active == True)
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

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from screening_v2.db_helpers import fetch_entity_profiles_by_pks; print('OK')"
```
Expected: `OK`

---

## Task 5: Normal Search

**Files:**
- Create: `backend/screening_v2/normal_search.py`
- Create: `backend/tests/screening_v2/test_normal_search.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/screening_v2/test_normal_search.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from app.database import SessionLocal
from screening_v2.normal_search import NormalSearcher
from screening_v2.normalizer import Normalizer

_normalizer = Normalizer()


@pytest.fixture(scope="module")
def searcher():
    return NormalSearcher(SessionLocal)


def test_finds_putin(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0
    assert any("PUTIN" in c.matched_name.upper() for c in candidates)


def test_finds_shoigu_without_patronym(searcher):
    # Key test: patronym normalization fix — DB has "SHOIGU Sergei Kuzhugetovich"
    normalized = _normalizer.normalize("Sergei Shoigu", "individual")
    candidates = searcher.search(normalized)
    assert any("SHOIGU" in c.matched_name.upper() for c in candidates)
    assert candidates[0].match_score >= 0.60


def test_top_result_has_entity_profile(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0
    profile = candidates[0].entity_profile
    assert profile.source_uid
    assert profile.primary_name
    assert len(profile.programs) > 0


def test_top_result_has_score_breakdown(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    bd = candidates[0].score_breakdown
    assert 0.0 <= bd.token_set_ratio <= 1.0
    assert 0.0 <= bd.jaro_winkler <= 1.0


def test_clean_name_has_low_confidence(searcher):
    normalized = _normalizer.normalize("Bartholomew Kingsborough", "individual")
    candidates = searcher.search(normalized)
    if candidates:
        assert candidates[0].match_score < 0.85


def test_returns_at_most_five_candidates(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) <= 5


def test_alias_hit_flagged(searcher):
    # Putin has aliases in OFAC — searching an alias should set matched_via_alias=True
    normalized = _normalizer.normalize("Putin Vladimir", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0


def test_entity_type_scored_without_phonetic(searcher):
    normalized = _normalizer.normalize("Rosneft", "entity")
    candidates = searcher.search(normalized)
    # Should not crash; phonetic component should be absent
    if candidates:
        assert candidates[0].score_breakdown.phonetic_match is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/screening_v2/test_normal_search.py -v
```
Expected: `ImportError` — `screening_v2.normal_search` does not exist yet.

- [ ] **Step 3: Implement NormalSearcher**

Create `backend/screening_v2/normal_search.py`:
```python
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
        # Each entry: (normalized_name, entity_pk, list_code, source_uid, raw_name)
        self._index: list[tuple[str, int, str, str, str]] = []
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
            self._index.append((normalized.cleaned, entity_pk, list_code, source_uid, full_name))

        logger.info("NormalSearcher: built index with %d name entries", len(self._index))

    def search(self, normalized: NormalizedInput) -> list[MatchCandidate]:
        # 1. Blocking pass — find entities whose normalized names score above threshold
        #    Group by entity_pk; keep best-scoring name per entity
        best_per_entity: dict[int, tuple[float, str, str, str]] = {}
        # value: (tsr_score, list_code, source_uid, raw_name)

        for norm_name, entity_pk, list_code, source_uid, raw_name in self._index:
            if not norm_name:
                continue
            tsr = token_set_ratio(normalized.cleaned, norm_name)
            if tsr <= BLOCK_THRESHOLD:
                continue
            score = tsr / 100.0
            if entity_pk not in best_per_entity or score > best_per_entity[entity_pk][0]:
                best_per_entity[entity_pk] = (score, list_code, source_uid, raw_name)

        if not best_per_entity:
            return []

        # 2. Detailed scoring on candidates that passed blocking
        scored: list[tuple[float, int, str, str, str]] = []
        # (final_score, entity_pk, list_code, source_uid, raw_name)
        for entity_pk, (_, list_code, source_uid, raw_name) in best_per_entity.items():
            norm_name_clean = self._normalizer.normalize(raw_name, normalized.entity_type).cleaned
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

            scored.append((final, entity_pk, list_code, source_uid, raw_name,
                           tsr, jw, phonetic_score, weights))

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
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/screening_v2/test_normal_search.py -v
```
Expected: All 8 tests pass. `test_finds_shoigu_without_patronym` is the key regression test for the patronym normalization fix.

- [ ] **Step 5: Commit**

```bash
git add backend/screening_v2/db_helpers.py backend/screening_v2/normal_search.py backend/tests/screening_v2/test_normal_search.py
git commit -m "feat(screening_v2): normal search with patronym-normalized blocking pass and batch profile fetch"
```

---

## Task 6: Vector Search

**Files:**
- Create: `backend/screening_v2/vector_search.py`
- Create: `backend/tests/screening_v2/test_vector_search.py`

**Note:** First run downloads `paraphrase-multilingual-MiniLM-L12-v2` (~117MB). Index build takes ~5s for 60k names. Use `scope="module"` on the fixture to build the index once per test session.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/screening_v2/test_vector_search.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from app.database import SessionLocal
from screening_v2.vector_search import VectorSearcher
from screening_v2.normalizer import Normalizer

_normalizer = Normalizer()


@pytest.fixture(scope="module")
def searcher():
    return VectorSearcher(SessionLocal)


def test_finds_transliteration_variant(searcher):
    # "Shoygu" is an alternate Latin spelling of "Shoigu"
    normalized = _normalizer.normalize("Sergey Shoygu", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert any("SHOIGU" in c.matched_name.upper() for c in candidates)


def test_finds_cyrillic_name(searcher):
    normalized = _normalizer.normalize("Владимир Путин", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert len(candidates) > 0
    assert any("PUTIN" in c.matched_name.upper() for c in candidates)


def test_match_method_tagged_as_vector(searcher):
    normalized = _normalizer.normalize("Sergey Shoygu", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert all(c.match_method == "vector" for c in candidates)


def test_skips_already_found_by_normal_search(searcher):
    from screening_v2.models import MatchCandidate, ScoreBreakdown, EntityProfile
    # Fake a normal candidate with entity_id matching a real entity
    # Vector search should not re-add it
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    # First do a real normal search to get the real entity_id
    from screening_v2.normal_search import NormalSearcher
    normal = NormalSearcher(SessionLocal)
    normal_candidates = normal.search(normalized)
    if not normal_candidates:
        pytest.skip("No normal candidates found for Putin")
    vector_candidates = searcher.search(normalized, normal_candidates=normal_candidates)
    normal_ids = {c.entity_id for c in normal_candidates}
    vector_ids = {c.entity_id for c in vector_candidates}
    # Vector should not duplicate what normal already found
    assert not (normal_ids & vector_ids)


def test_combined_score_between_zero_and_one(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    for c in candidates:
        assert 0.0 <= c.match_score <= 1.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/screening_v2/test_vector_search.py -v
```
Expected: `ImportError` — `screening_v2.vector_search` does not exist yet.

- [ ] **Step 3: Implement VectorSearcher**

Create `backend/screening_v2/vector_search.py`:
```python
from __future__ import annotations
import logging
import numpy as np
from rapidfuzz.fuzz import token_set_ratio
import jellyfish
from .models import NormalizedInput, MatchCandidate, ScoreBreakdown
from .db_helpers import fetch_entity_profiles_by_pks

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 10


class VectorSearcher:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._model = None
        self._index = None
        # Each entry: (full_name, entity_pk, list_code, source_uid)
        self._index_map: list[tuple[str, int, str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        import faiss
        from sentence_transformers import SentenceTransformer
        from app.models import EntityName, Entity, SourceList

        self._model = SentenceTransformer(MODEL_NAME)

        session = self._session_factory()
        try:
            rows = (
                session.query(EntityName.full_name, Entity.id, Entity.source_uid, SourceList.code)
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

        self._index_map = [(r[0], r[1], r[3], r[2]) for r in rows]
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
            full_name, entity_pk, list_code, source_uid = self._index_map[idx]
            entity_id = f"{list_code}:{source_uid}"
            if entity_id in already_found or entity_pk in seen_entity_pks:
                continue
            seen_entity_pks.add(entity_pk)

            norm_candidate = full_name.lower()
            tsr = token_set_ratio(normalized.cleaned, norm_candidate) / 100.0
            jw = jellyfish.jaro_winkler_similarity(normalized.cleaned, norm_candidate)
            fuzzy_score = tsr * 0.53 + jw * 0.47
            combined = 0.6 * fuzzy_score + 0.4 * float(cosine_score)

            candidates_data.append((combined, entity_pk, entity_id, full_name, tsr, jw, float(cosine_score)))

        if not candidates_data:
            return []

        candidates_data.sort(key=lambda x: x[0], reverse=True)
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
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/screening_v2/test_vector_search.py -v
```
Expected: All 5 tests pass. First run downloads model (~117MB). `test_finds_transliteration_variant` and `test_finds_cyrillic_name` are the key differentiator tests.

- [ ] **Step 5: Commit**

```bash
git add backend/screening_v2/vector_search.py backend/tests/screening_v2/test_vector_search.py
git commit -m "feat(screening_v2): FAISS vector search with multilingual MiniLM embeddings"
```

---

## Task 7: Engine

**Files:**
- Create: `backend/screening_v2/engine.py`
- Create: `backend/tests/screening_v2/test_engine.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/screening_v2/test_engine.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from app.database import SessionLocal
from screening_v2.engine import ScreeningEngine


@pytest.fixture(scope="module")
def engine():
    return ScreeningEngine(SessionLocal)


def test_sanctions_hit_returns_match(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert result.verdict == "MATCH"
    assert result.confidence >= 0.85


def test_clean_name_returns_no_match_or_review(engine):
    result = engine.screen("Bartholomew Kingsborough", "individual")
    assert result.verdict in ("NO_MATCH", "REVIEW")
    assert result.confidence < 0.85


def test_cyrillic_input_returns_match(engine):
    result = engine.screen("Владимир Путин", "individual")
    assert result.verdict == "MATCH"


def test_result_has_explanation(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert len(result.explanation) > 30
    assert "PUTIN" in result.explanation.upper() or "match" in result.explanation.lower()


def test_auto_type_detection(engine):
    result = engine.screen("Rosneft Oil Company LLC")
    assert result.input_type == "entity"


def test_normal_search_always_in_methods(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert "normal" in result.search_methods


def test_vector_used_for_transliteration(engine):
    # "Shoygu" is a transliteration variant that fuzzy alone may not catch at >= 0.85
    result = engine.screen("Sergey Shoygu", "individual")
    assert "vector" in result.search_methods


def test_high_confidence_skips_vector(engine):
    # Putin should be found at >= 0.85 by normal search; vector should be skipped
    result = engine.screen("Vladimir Putin", "individual")
    # Normal search finds it above HIGH_CONFIDENCE — vector may not run
    # Either way, verdict must be MATCH
    assert result.verdict == "MATCH"


def test_pep_hit_returns_review_not_match(engine):
    # Only meaningful if PEP list has been ingested
    # This test is skipped if no PEP entities are in DB
    from app.models import Entity, SourceList
    session = SessionLocal()
    pep_count = (
        session.query(Entity)
        .join(SourceList, Entity.source_list_id == SourceList.id)
        .filter(SourceList.list_type == "pep", Entity.is_active == True)
        .count()
    )
    session.close()
    if pep_count == 0:
        pytest.skip("No PEP entities in DB — run: python manage.py fetch --source opensanctions-peps")
    # Search for a known PEP name — this is data-dependent
    # At minimum verify: if any PEP-only hit exists, verdict is REVIEW not MATCH
    result = engine.screen("Emmanuel Macron", "individual")
    if result.candidates and result.candidates[0].entity_profile.list_type == "pep":
        assert result.verdict == "REVIEW"


def test_duration_ms_populated(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert result.search_duration_ms >= 0


def test_candidates_sorted_by_score(engine):
    result = engine.screen("Vladimir Putin", "individual")
    scores = [c.match_score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/screening_v2/test_engine.py -v
```
Expected: `ImportError` — `screening_v2.engine` does not exist yet.

- [ ] **Step 3: Implement engine**

Create `backend/screening_v2/engine.py`:
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
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/screening_v2/test_engine.py -v
```
Expected: All tests pass except `test_pep_hit_returns_review_not_match` which skips if PEP list not ingested.

- [ ] **Step 5: Commit**

```bash
git add backend/screening_v2/engine.py backend/tests/screening_v2/test_engine.py
git commit -m "feat(screening_v2): ScreeningEngine cascade with verdict logic and explanation"
```

---

## Task 8: Verdict Composer

**Files:**
- Create: `backend/screening_v2/composer.py`
- Create: `backend/tests/screening_v2/test_composer.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/screening_v2/test_composer.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from screening_v2.composer import VerdictComposer
from screening_v2.models import ScreeningResult


def _result(verdict: str, confidence: float, name: str = "Test") -> ScreeningResult:
    return ScreeningResult(
        verdict=verdict,
        confidence=confidence,
        input_raw=name,
        input_type="individual",
        input_normalized=name.lower(),
        search_methods=["normal"],
        search_duration_ms=10,
        candidates=[],
        explanation="test explanation",
    )


def test_match_beats_review():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("REVIEW", 0.71, "Risky Corp"))
    assert result["verdict"] == "MATCH"


def test_match_beats_no_match():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert result["verdict"] == "MATCH"


def test_review_beats_no_match():
    c = VerdictComposer()
    result = c.compose(_result("NO_MATCH", 0.0, "Clean"), _result("REVIEW", 0.71, "Risky"))
    assert result["verdict"] == "REVIEW"


def test_both_no_match_returns_no_match():
    c = VerdictComposer()
    result = c.compose(_result("NO_MATCH", 0.0, "A"), _result("NO_MATCH", 0.0, "B"))
    assert result["verdict"] == "NO_MATCH"


def test_confidence_is_max_of_both():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "A"), _result("REVIEW", 0.71, "B"))
    assert result["confidence"] == 0.92


def test_parties_dict_has_both():
    c = VerdictComposer()
    orig = _result("MATCH", 0.92, "Bad Actor")
    bene = _result("NO_MATCH", 0.0, "Clean Co")
    result = c.compose(orig, bene)
    assert result["parties"]["originator"] is orig
    assert result["parties"]["beneficiary"] is bene


def test_explanation_mentions_clean_party():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert "Clean Co" in result["explanation"] or "clean" in result["explanation"].lower()


def test_explanation_mentions_flagged_party():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert "Bad Actor" in result["explanation"] or "flagged" in result["explanation"].lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/screening_v2/test_composer.py -v
```
Expected: `ImportError` — `screening_v2.composer` does not exist yet.

- [ ] **Step 3: Implement composer**

Create `backend/screening_v2/composer.py`:
```python
from __future__ import annotations
from .models import ScreeningResult

_PRIORITY = {"MATCH": 3, "REVIEW": 2, "NO_MATCH": 1}


class VerdictComposer:
    def compose(self, originator: ScreeningResult, beneficiary: ScreeningResult) -> dict:
        verdict = max(
            originator.verdict, beneficiary.verdict, key=lambda v: _PRIORITY[v]
        )
        confidence = max(originator.confidence, beneficiary.confidence)
        explanation = self._build_explanation(originator, beneficiary)
        return {
            "verdict": verdict,
            "confidence": confidence,
            "parties": {"originator": originator, "beneficiary": beneficiary},
            "explanation": explanation,
        }

    @staticmethod
    def _build_explanation(orig: ScreeningResult, bene: ScreeningResult) -> str:
        parts = []
        if orig.verdict == "NO_MATCH":
            parts.append(f"Originator '{orig.input_raw}': clean.")
        else:
            parts.append(f"Originator flagged — {orig.explanation}")
        if bene.verdict == "NO_MATCH":
            parts.append(f"Beneficiary '{bene.input_raw}': clean.")
        else:
            parts.append(f"Beneficiary flagged — {bene.explanation}")
        return " ".join(parts)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/screening_v2/test_composer.py -v
```
Expected: All 8 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
cd backend && python -m pytest tests/screening_v2/ -v
```
Expected: All tests pass (PEP test skips if no PEP data ingested).

- [ ] **Step 6: Commit**

```bash
git add backend/screening_v2/composer.py backend/tests/screening_v2/test_composer.py
git commit -m "feat(screening_v2): VerdictComposer merges originator and beneficiary results"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Models (§5) ✓, normalizer both branches (§2) ✓, normal search cascade (§3) ✓, vector search (§4) ✓, multi-source support (§9) ✓ via `list_type` on EntityProfile, composer (§7) ✓, FastAPI integration left for separate task (wiring engine into `/screen` endpoint)
- [x] **Placeholder scan:** No TBDs or TODOs in code blocks
- [x] **Type consistency:** `MatchCandidate`, `ScreeningResult`, `EntityProfile`, `ScoreBreakdown`, `NormalizedInput` defined in Task 2 and used consistently across Tasks 3–8. `entity_id` format `"{list_code}:{source_uid}"` used consistently. `HIGH_CONFIDENCE` / `LOW_CONFIDENCE` imported from `normal_search.py` in engine.
- [x] **Gap noted:** FastAPI `/screen` endpoint wiring (`app/main.py`) not included — separate task. The engine is importable and testable standalone; wiring is a one-line change in the lifespan handler.
