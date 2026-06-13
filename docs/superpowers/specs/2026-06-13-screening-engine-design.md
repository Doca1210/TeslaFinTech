# Screening Engine — Design Spec

**Date:** 2026-06-13
**Project:** Garaža FinTech AI Hackathon — Sokin sanctions screening
**Status:** Approved

---

## Overview

A new `ScreeningEngine` built from scratch that handles both individual persons and legal entities. Uses a two-stage cascade: fast deterministic search first, vector semantic search as fallback when confidence is low. Returns rich evidence for every decision.

---

## Architecture

```
ScreeningEngine
│
├── normalize(name, entity_type)      # type-aware normalization
├── normal_search(normalized)         # fast, deterministic
├── advanced_search(normalized)       # vector, only if confidence < 0.85
├── compose_result(candidates)        # pick verdict, build evidence
└── ScreeningResult                   # rich output
```

Single engine instance created at FastAPI startup (lifespan). FAISS index built at init time (~5s).

---

## File Structure

```
screening/
├── engine.py          # ScreeningEngine — orchestration only
├── normalizer.py      # Normalizer (individual + entity branches)
├── normal_search.py   # NormalSearcher (blocking + alias + scoring)
├── vector_search.py   # VectorSearcher (FAISS + sentence-transformers)
├── models.py          # ScreeningResult, MatchCandidate, EntityProfile, ScoreBreakdown
└── composer.py        # verdict composition across originator + beneficiary
```

---

## Section 1: Type Detection

If caller passes `entity_type="auto"` (default), the normalizer detects type via heuristic:

- Input contains legal suffixes (LLC, Ltd, GmbH, d.o.o., JSC, OJSC, PJSC, Corp, Inc, S.A., B.V., Holdings, Group, Trading, Company, International, Enterprises, Services) → `entity`
- Otherwise → `individual`

Caller can always override with explicit `entity_type="individual"` or `entity_type="entity"`.

---

## Section 2: Normalization

Both branches return a `NormalizedInput` object with fields: `raw`, `cleaned`, `phonetic`, `type`.

### Individual branch

```
"Sergei Kuzhugetovich SHOIGU"
  → lowercase + strip punctuation
  → patronym removal (tokens >10 chars ending in -ovich/-evna/-ievich/-ovna)
  → unidecode (Cyrillic/Arabic → Latin, only if non-ASCII detected)
  → NYSIIS phonetic code

NormalizedInput(
  raw="Sergei Kuzhugetovich SHOIGU",
  cleaned="sergei shoigu",
  phonetic="SARJ SAG",
  type="individual"
)
```

### Entity branch

```
"Rosneft Oil Company LLC"
  → lowercase + strip punctuation
  → legal suffix stripping
  → unidecode
  → abbreviation expansion (config-driven map, e.g. "vtb" → "vneshtorgbank")

NormalizedInput(
  raw="Rosneft Oil Company LLC",
  cleaned="rosneft",
  phonetic=None,
  type="entity"
)
```

Legal suffixes stripped: `llc, ltd, gmbh, d.o.o., inc, corp, s.a., b.v., jsc, ojsc, pjsc, holdings, group, trading, company, international, enterprises, services`

---

## Section 3: Normal Search

**Input:** `NormalizedInput`
**Output:** list of `MatchCandidate` ranked by score

### Step 1 — Blocking pass

```sql
SELECT entity_id, normalized_name
FROM entity_names
WHERE token_set_ratio(normalized_name, input.cleaned) > 55
```

`entity_names` rows are pre-normalized at index build time using the same pipeline as queries (patronyms stripped, suffixes stripped). This fixes the blocking-pass bug in the old engine that caused 50% recall.

### Step 2 — Alias expansion

For each `entity_id` in the candidate pool, fetch ALL names from `entity_names`. Score each alias. Keep the highest-scoring alias per entity.

### Step 3 — Scoring pass

```
score = token_set_ratio(input.cleaned, candidate.name)  × 0.40
      + jaro_winkler(input.cleaned, candidate.name)      × 0.35
      + phonetic_match(input.phonetic, candidate.phonetic) × 0.25
```

When `phonetic=None` (entity type), the phonetic term is dropped and weights are renormalized: `token_set_ratio × 0.53 + jaro_winkler × 0.47`.

### Step 4 — Confidence gate

- `score >= 0.85` → return immediately, skip advanced search
- `0.60 <= score < 0.85` → pass to advanced search to confirm or deny
- `score < 0.60` (or no candidates) → pass to advanced search

Return top-5 candidates sorted by score.

---

## Section 4: Advanced Search (Vector)

Only runs when normal search top score is below 0.85.

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers)
- 384-dimensional embeddings
- Multilingual — handles Cyrillic/Arabic implicitly
- ~117MB, runs locally, no API cost

**Index:** FAISS `IndexFlatIP` (inner product on L2-normalized vectors = cosine similarity)
- Built at engine startup from all rows in `entity_names` (~60k names, ~5s build time, ~90MB RAM)
- Rebuilt automatically after each OFAC ingest
- In-memory only, no persistence

### Query flow

```python
query_vector = model.encode([input.cleaned], normalize_embeddings=True)
scores, indices = faiss_index.search(query_vector, k=10)
# scores = cosine similarities, indices = positions in names array
```

### Re-scoring

For each vector candidate, run the same Jaro-Winkler + token_set scoring:

```
combined_score = 0.6 × fuzzy_score + 0.4 × cosine_similarity
```

### Merge

Deduplicate by `entity_id`. Keep highest score per entity. Tag `match_method="vector"` if found by vector search, `"normal"` if found earlier.

**Latency:** ~30ms model inference + <1ms FAISS search = ~35ms total.

---

## Section 5: Output Schema

```python
ScreeningResult(
  # Verdict
  verdict             = "MATCH" | "REVIEW" | "NO_MATCH",
  confidence          = float,           # highest candidate score

  # Input echo
  input_raw           = str,
  input_type          = "individual" | "entity",
  input_normalized    = str,

  # Provenance
  search_methods      = list[str],       # e.g. ["normal", "vector"]
  search_duration_ms  = int,

  # Candidates (ranked)
  candidates = [
    MatchCandidate(
      entity_id          = str,          # e.g. "OFAC_SDN:35173"
      match_score        = float,
      match_method       = "normal" | "vector",
      matched_name       = str,
      matched_via_alias  = bool,
      alias_hit          = str | None,

      entity_profile = EntityProfile(
        primary_name        = str,
        entity_type         = "individual" | "entity",
        aliases             = list[str],
        programs            = list[str],  # e.g. ["UKRAINE-EO13661"]
        nationalities       = list[str],
        dob                 = str | None,
        pob                 = str | None,
        addresses           = list[str],
        ids                 = list[dict],
        remarks             = str | None,
        registration_country = str | None,  # entity only
        list_version        = str,
        source_uid          = str,
      ),

      score_breakdown = ScoreBreakdown(
        token_set_ratio     = float,
        jaro_winkler        = float,
        phonetic_match      = float | None,
        cosine_similarity   = float | None,
        weights_used        = list[float],
      )
    )
  ],

  # Human-readable (fed into T-015 Haiku summary)
  explanation = str,
)
```

### Verdict thresholds

| Score | Verdict |
|-------|---------|
| >= 0.85 | MATCH |
| 0.60 – 0.84 | REVIEW |
| < 0.60 | NO_MATCH |

---

## Section 6: FastAPI Integration

```python
# app/main.py

engine: ScreeningEngine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    engine = ScreeningEngine(db_path="aml.db")  # builds FAISS index here
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/screen")
async def screen_payment(payment: PaymentInstruction) -> ScreeningResult:
    originator = engine.screen(payment.originator_name)
    beneficiary = engine.screen(payment.beneficiary_name)
    return verdict_composer.compose(originator, beneficiary, payment)
```

One engine instance, shared across all requests. Thread-safe (FAISS read operations are safe concurrent).

---

## Section 7: Verdict Composer (composer.py)

The composer sits above the engine. It takes two `ScreeningResult` objects (originator + beneficiary) and a `PaymentInstruction`, and produces a single payment-level verdict.

**Rules:**
- If either party is `MATCH` → payment verdict is `MATCH`
- If either party is `REVIEW` (and no `MATCH`) → payment verdict is `REVIEW`
- If both are `NO_MATCH` → payment verdict is `NO_MATCH`

**Output:** a combined result that includes both party results under `parties.originator` and `parties.beneficiary`, a top-level `verdict`, and a merged `explanation` string covering both parties. This is what `/screen` returns to the caller and what gets persisted to `screening_results`.

---

## Section 8: Dependencies

```
sentence-transformers   # embedding model
faiss-cpu               # vector index
jellyfish               # Jaro-Winkler, NYSIIS
rapidfuzz               # token_set_ratio (faster than fuzzywuzzy)
unidecode               # Cyrillic/Arabic → Latin
```

---

## Section 9: Multi-Source Support

The DB already has a unified ingestion interface (`app/ingestion/common.py`). Every source adapter (OFAC SDN, OpenSanctions PEPs, EU FSF) normalizes into the same `Entity`/`EntityName`/... tables. The screening engine queries across all active source lists automatically.

### Active source lists (currently)

| Code | Name | Type | Entities |
|------|------|------|----------|
| `OFAC_SDN` | OFAC Specially Designated Nationals | sanctions | ~19k |
| `EU_FSF` | EU Financial Sanctions Files | sanctions | ~2.5k |
| `OPENSANCTIONS_PEPS` | OpenSanctions PEPs Collection | pep | up to 1M (capped) |

### Verdict per list type

| List type | Hit verdict | Reason |
|-----------|-------------|--------|
| `sanctions` | MATCH | Legally prohibited — payment must be blocked |
| `pep` | REVIEW | High-risk, requires Enhanced Due Diligence — not illegal |

If a single payment hits both a sanctions list and a PEP list, the composer takes the strictest verdict (MATCH wins over REVIEW).

### Changes to EntityProfile

Add `source_list_code` and `list_type` fields so the output always tells you which list fired:

```python
entity_profile = EntityProfile(
  ...
  source_list_code = "OFAC_SDN" | "EU_FSF" | "OPENSANCTIONS_PEPS" | ...,
  list_type        = "sanctions" | "pep",
  ...
)
```

### FAISS index

Built from `entity_names` across ALL active source lists. No per-source filtering — the engine screens everything in one pass. The `list_type` on the matched entity determines the verdict, not which index was queried.

---

## Out of Scope

- KYB / beneficial ownership chain (no corporate registry data)
- Shell company heuristics
- EU / UN / OFSI list ingestion
- PEP as separate list
- Persistent FAISS index (rebuild at startup is sufficient)
- Approximate FAISS index (60k vectors doesn't need it)
