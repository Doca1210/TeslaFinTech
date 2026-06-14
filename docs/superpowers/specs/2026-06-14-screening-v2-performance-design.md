# screening_v2 Performance Optimization — Design Spec
**Date:** 2026-06-14  
**Target:** Sub-1s latency on the hot path; vector search opt-in and optimized when used  
**Scope:** `backend/screening_v2/` — no changes to public API surface or caller contracts

---

## 1. Problem Statement

The current `screening_v2` module has five concrete bottlenecks that prevent reliable sub-1s performance:

| # | Bottleneck | Location | Estimated Cost |
|---|---|---|---|
| 1 | Linear O(N) scan — `token_set_ratio` against all 60–100k index entries | `normal_search.py:59` | 50–100ms |
| 2 | Re-normalization in detail phase — `normalize(raw_name)` per candidate | `normal_search.py:75` | 5–15ms |
| 3 | Per-call NYSIIS computation — `jellyfish.nysiis()` per candidate | `normal_search.py:80` | 2–5ms |
| 4 | DB round-trip per request — `fetch_entity_profiles_by_pks` called up to twice | `normal_search.py:99`, `vector_search.py:126` | 15–40ms |
| 5 | Transformer encode per vector call — `model.encode()` on every fallback | `vector_search.py:82` | 50–200ms |

**Total worst-case today:** ~120–360ms on the hot path, with no caching.

**Target after optimization:** Normal path ~5–20ms. Vector path ~50–200ms (encode) + <5ms (everything else).

---

## 2. Approach: In-Memory Optimization + Inverted Token Index

### 2.1 Index Entry Schema

Replace the current 6-field tuple with a typed dataclass:

```python
@dataclass(slots=True)
class IndexEntry:
    norm_name: str        # pre-normalized cleaned name (was recomputed at detail phase)
    phonetic: str | None  # pre-computed NYSIIS (individuals only, None for entities)
    entity_pk: int
    list_code: str
    source_uid: str
    raw_name: str
    entity_type: str
```

All fields are computed once at `_build_index()` time and never recomputed during search.

### 2.2 In-Memory Structures (NormalSearcher)

Four structures replace the current single `_index` list:

| Attribute | Type | Purpose |
|---|---|---|
| `_entries` | `list[IndexEntry]` | ordered list of all index entries |
| `_token_index` | `dict[str, list[int]]` | token → list of positions in `_entries` |
| `_phonetic_index` | `dict[str, list[int]]` | NYSIIS code → list of positions in `_entries` |
| `_profile_cache` | `dict[int, EntityProfile]` | entity_pk → full profile (loaded at startup) |

The profile cache eliminates all DB hits during screening. Profiles change only on list ingestion, so the cache is valid until `rebuild()` is called.

`_profile_cache` is exposed as a property so `VectorSearcher` shares the same instance — no duplicate DB fetch.

---

## 3. NormalSearcher: New Search Algorithm

### 3.1 Blocking Pass (replaces full linear scan)

```
query_tokens = tokenize(query.cleaned)
candidate_positions = union(
    _token_index.get(t, []) for t in query_tokens
) | set(_phonetic_index.get(query.phonetic, []))
```

Typical reduction: 60–100k entries → 200–2,000 candidates.

Edge case: token not in index (rare transliteration, unusual name) → union is small or empty → vector search handles these when `use_vector=True`.

### 3.2 Fuzzy Scoring (unchanged logic, smaller scope)

Run `token_set_ratio` + `BLOCK_THRESHOLD` filter only on `candidate_positions`.  
Dedup to best score per `entity_pk` (same as current).

### 3.3 Detail Scoring (no recomputation)

- `norm_name` → read from `entry.norm_name` (no `normalize()` call)
- `phonetic` → read from `entry.phonetic` (no `jellyfish.nysiis()` call)
- Profile → `self._profile_cache[entity_pk]` (no DB call)

Scoring formula (tsr, jaro_winkler, phonetic weights) is unchanged.

---

## 4. VectorSearcher: Optimizations

### 4.1 Opt-in Flag

`ScreeningEngine.screen()` gains a `use_vector: bool = False` parameter. Vector path executes only when `use_vector=True` AND `top_score < HIGH_CONFIDENCE`. Default is `False` — the hot path never pays the encoding cost.

### 4.2 LRU Query Embedding Cache

```python
from functools import lru_cache

@lru_cache(maxsize=1024)
def _encode_cached(model_ref, text: str) -> tuple[float, ...]:
    arr = model_ref.encode([text], normalize_embeddings=True)[0]
    return tuple(arr.tolist())
```

Cache key: normalized query string. Cache hit: zero transformer inference. Effective for payment systems where the same counterparty name recurs across transactions.

`lru_cache` is GIL-protected — thread-safe without additional locking.

### 4.3 FAISS IVF Index

Replace `IndexFlatIP` with `IndexIVFFlat`:

```python
nlist = 100  # Voronoi cells
quantizer = faiss.IndexFlatIP(dim)
index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
index.train(vectors)
index.add(vectors)
index.nprobe = 10  # search 10 cells (~10x speedup vs flat, >99% recall at 19k vectors)
```

At 19k vectors this saves ~5–10ms per vector search. Scales cleanly as UN/EU lists are added.

### 4.4 Shared Profile Cache

`VectorSearcher.__init__` accepts `profile_cache: dict[int, EntityProfile]` from the engine instead of fetching profiles via DB. The engine passes `self._normal.profile_cache` at construction.

---

## 5. Engine Wiring

```python
class ScreeningEngine:
    def __init__(self, session_factory):
        self._normalizer = Normalizer()
        self._normal = NormalSearcher(session_factory)
        self._vector = VectorSearcher(session_factory, profile_cache=self._normal.profile_cache)
        self._session_factory = session_factory

    def screen(self, name: str, entity_type: str = "auto", use_vector: bool = False) -> ScreeningResult:
        ...
        if use_vector and top_score < HIGH_CONFIDENCE:
            vector_candidates = self._vector.search(normalized, candidates)
            ...

    def rebuild_indexes(self) -> None:
        self._normal.rebuild()
        self._vector.rebuild(profile_cache=self._normal.profile_cache)
```

---

## 6. Thread Safety

All four in-memory structures (`_entries`, `_token_index`, `_phonetic_index`, `_profile_cache`) are **write-once at build time, read-only during search**. Python `dict` and `list` reads are GIL-safe without explicit locking.

**Atomic rebuild pattern:**

```python
def rebuild(self) -> None:
    # Build all structures before any swap
    new_entries, new_token_idx, new_phonetic_idx, new_cache = self._build_structures()
    # Attribute assignment is atomic under GIL
    self._entries = new_entries
    self._token_index = new_token_idx
    self._phonetic_index = new_phonetic_idx
    self._profile_cache = new_cache
```

Concurrent readers see either the old or new index — no partial state. No `threading.Lock` needed.

---

## 7. Files Changed

| File | Change |
|---|---|
| `screening_v2/models.py` | Add `IndexEntry` dataclass |
| `screening_v2/normal_search.py` | New index structures, inverted token/phonetic index, profile cache, new blocking algorithm |
| `screening_v2/vector_search.py` | LRU embedding cache, IVF index, accept shared `profile_cache`, remove own DB fetch |
| `screening_v2/engine.py` | Wire shared profile cache, add `use_vector` param, pass cache on rebuild |
| `screening_v2/db_helpers.py` | Expose `load_all_profiles(session_factory) -> dict[int, EntityProfile]` for startup load |

No changes to `composer.py`, `scoring.py`, `normalizer.py`, or any test files (API surface unchanged).

---

## 8. Testing Plan

| Test | Assertion |
|---|---|
| Token index construction | Every entry position is reachable via at least one token in `_token_index` |
| Phonetic index construction | All individual entries have their NYSIIS code in `_phonetic_index` |
| Profile cache completeness | All entity_pks in `_entries` have a corresponding cache entry |
| Latency benchmark | 10 sequential `screen()` calls complete in < 500ms total (normal path) |
| Regression | Existing 42-test suite passes without modification |
| Concurrency | 10 threads calling `screen()` while `rebuild()` runs — no exceptions, all results valid `ScreeningResult` instances |
| Vector opt-in | `use_vector=False` (default) never calls `model.encode()`; `use_vector=True` does |
| LRU cache hit | Second call with same name returns identical embedding, `model.encode` called only once |

---

## 9. Out of Scope

- Async/batched encoding (Approach C) — can be layered on top later
- Disk-persisted FAISS index — useful for faster restarts, not required for sub-1s
- Additional matching signals (DOB, document ID cross-reference)
- Changes to `VerdictComposer` or Layer B behavioral scoring
