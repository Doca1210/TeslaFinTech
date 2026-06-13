# Backend Documentation

AML (Anti-Money Laundering) and sanctions screening backend for TeslaFinTech. Built with FastAPI, SQLAlchemy, and a hybrid fuzzy+vector matching engine.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Data Model](#data-model)
4. [Ingestion Pipeline](#ingestion-pipeline)
5. [Sanctions Screening — v1 (`screening/`)](#sanctions-screening--v1-screening)
6. [Sanctions Screening — v2 (`screening_v2/`)](#sanctions-screening--v2-screening_v2)
7. [AML Behavioral Detection (`app/aml_detect.py`)](#aml-behavioral-detection-appaml_detectpy)
8. [FastAPI HTTP Layer (`app/main.py`)](#fastapi-http-layer-appmaInpy)
9. [Vectorization Export](#vectorization-export)
10. [Evaluation Framework](#evaluation-framework)
11. [CLI (`manage.py`)](#cli-managepy)
12. [Configuration & Environment](#configuration--environment)
13. [Dependencies](#dependencies)
14. [Running the System](#running-the-system)

---

## Architecture Overview

The backend is organized into three independent layers that work together for full payment compliance:

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI HTTP Layer                    │
│              /ingest/*, /entities/search, /export       │
└───────────────────────┬─────────────────────────────────┘
                        │
            ┌───────────▼───────────┐
            │   SQLite / aml.db     │  ← canonical store
            │  (via SQLAlchemy ORM) │
            └─────┬─────────┬───────┘
                  │         │
     ┌────────────▼──┐  ┌───▼────────────────┐
     │  Ingestion    │  │  Screening Engines  │
     │  OFAC SDN     │  │  v1 (fuzzy+phonetic)│
     │  OpenSanctions│  │  v2 (+ FAISS vector)│
     │  EU FSF       │  └───────────┬─────────┘
     └───────────────┘              │
                        ┌───────────▼──────────┐
                        │  VerdictComposer      │
                        │  Layer A (sanctions)  │
                        │  Layer B (behavioral) │
                        └──────────────────────┘
```

**Two screening engines coexist:**
- **v1** (`screening/`) — production-ready fuzzy+phonetic engine, used by the CLI's `screen` command and the A/B evaluation framework
- **v2** (`screening_v2/`) — enhanced engine with type-aware normalization and FAISS semantic vector fallback; accessed via the `v2_cascade` evaluation variant and directly by application code

---

## Directory Structure

```
backend/
├── app/                          # FastAPI core
│   ├── main.py                   # HTTP endpoints
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── schemas.py                # Pydantic API schemas
│   ├── database.py               # DB engine + session factory
│   ├── aml_detect.py             # Behavioral rule engine
│   ├── logging_config.py         # Structured logging setup
│   ├── ingestion/
│   │   ├── common.py             # Shared upsert / soft-delete logic
│   │   ├── ofac_sdn.py           # OFAC SDN XML ingestion
│   │   └── opensanctions.py      # OpenSanctions CSV ingestion (PEPs, EU FSF)
│   └── export/
│       └── vectorize_export.py   # JSONL export for vector pipelines
│
├── screening/                    # Screening engine v1
│   ├── models.py                 # WatchlistEntity, Transaction, ScreeningResult
│   ├── normalizer.py             # Unicode → ASCII, stop tokens, common name detection
│   ├── matcher.py                # NameMatcher (hybrid), TokenSetMatcher (baseline)
│   ├── engine.py                 # ScreeningEngine orchestration
│   ├── watchlist_repo.py         # SQLite watchlist loader
│   └── evaluation/
│       ├── models.py             # BenchmarkCase, VariantEvaluation, metrics models
│       ├── pipeline.py           # ABTestPipeline
│       ├── variants.py           # Algorithm variant definitions
│       ├── benchmark_loader.py   # Benchmark JSON loader
│       ├── metrics.py            # Classification metrics (F1, F2, MCC, etc.)
│       └── v2_adapter.py         # Wraps v2 engine for A/B testing
│
├── screening_v2/                 # Screening engine v2
│   ├── models.py                 # NormalizedInput, MatchCandidate, ScreeningResult
│   ├── normalizer.py             # Type-aware normalizer (individual vs. entity)
│   ├── normal_search.py          # Fuzzy search with in-memory blocking index
│   ├── vector_search.py          # FAISS + sentence-transformers semantic search
│   ├── scoring.py                # Coverage penalty, token matching, JW similarity
│   ├── composer.py               # VerdictComposer (multi-party + behavioral merge)
│   ├── db_helpers.py             # Batch entity profile fetcher
│   └── engine.py                 # ScreeningEngine v2 (cascade orchestration)
│
├── data/
│   ├── aml.db                    # SQLite database (production data)
│   ├── benchmark.json            # Labeled test cases for evaluation
│   └── vectorize_export.jsonl    # Entity text snapshots for embedding pipelines
│
├── tests/
│   ├── test_screening.py
│   ├── test_evaluation.py
│   └── screening_v2/             # Unit tests for v2 engine
│
├── manage.py                     # Unified CLI
├── requirements.txt
├── conftest.py
└── report.py / demo.py           # Dev/demo utilities
```

---

## Data Model

All data lives in a single SQLite database (`data/aml.db`) managed by SQLAlchemy with the models defined in [app/models.py](app/models.py).

### Core Tables

#### `source_lists`
Registry of watchlists that have been ingested.

| Column | Type | Description |
|---|---|---|
| `code` | `str` | Unique identifier — e.g. `OFAC_SDN`, `OPENSANCTIONS_PEPS`, `EU_FSF` |
| `name` | `str` | Human-readable name |
| `list_type` | `str` | `"sanctions"` \| `"pep"` \| `"adverse_media"` |
| `url` | `str?` | Source URL |
| `last_fetched_at` | `datetime?` | When we last pulled from the source |
| `last_published_at` | `str?` | Publish date reported by the source |

#### `entities`
One row per unique entity (person, organization, vessel, aircraft) from any source list.

| Column | Type | Description |
|---|---|---|
| `source_list_id` | FK | Parent source list |
| `source_uid` | `str` | Source-native ID (unique within the source list) |
| `entity_type` | `str` | `"individual"` \| `"entity"` \| `"vessel"` \| `"aircraft"` |
| `primary_name` | `str` | Canonical name |
| `is_active` | `bool` | Soft-delete flag — `False` when removed from the source list |
| `raw` | `JSON` | Original parsed record for auditing |
| `first_seen_at` / `last_seen_at` | `datetime` | Lifecycle timestamps |

The combination `(source_list_id, source_uid)` is unique.

#### Child tables (all FK to `entities.id`)

| Table | Key fields | Description |
|---|---|---|
| `entity_names` | `name_type`, `quality`, `full_name`, `first_name`, `last_name` | All names — primary, aka, fka, nka. `quality` = `"strong"` \| `"weak"` |
| `entity_addresses` | `address_line`, `city`, `state_province`, `postal_code`, `country` | Physical addresses |
| `entity_identifications` | `id_type`, `id_number`, `id_country` | Passports, national IDs, crypto wallet addresses |
| `entity_programs` | `program_code` | Sanctions program codes (e.g. `UKRAINE-EO13685`) |
| `entity_dates_of_birth` | `date_of_birth` | Kept as text — OFAC uses partial dates and ranges |
| `entity_nationalities` | `relation`, `country` | Nationality, citizenship, place of birth |

#### Transaction tables

| Table | Description |
|---|---|
| `entity_transactions` | Ledger movements per entity. Fields: `amount`, `currency`, `direction` (`"in"` / `"out"`), `channel`, `counterparty_name`, `counterparty_account`, `counterparty_country`, `status` (`pending` / `cleared` / `flagged`) |
| `transaction_decisions` | AML engine output: `score`, `outcome` (`approve` / `review` / `decline` / `block_and_review`) |
| `transaction_rule_hits` | Individual rule firings that contributed to a decision: `rule_id`, `severity`, `score`, `reason`, `explanation`, `evidence` |

---

## Ingestion Pipeline

Data flows into the database through a two-stage process: **source-specific parsing → shared upsert**.

### Shared Upsert Logic ([app/ingestion/common.py](app/ingestion/common.py))

Every adapter produces a list of dicts matching this shape and passes them to `upsert_entries()`:

```python
{
    "source_uid": str,
    "entity_type": "individual" | "entity" | "vessel" | "aircraft",
    "primary_name": str,
    "title": str | None,
    "remarks": str | None,
    "names": [{"name_type", "quality", "full_name", "first_name", "last_name"}, ...],
    "addresses": [{"address_line", "city", "state_province", "postal_code", "country"}, ...],
    "identifications": [{"id_type", "id_number", "id_country"}, ...],
    "programs": [str, ...],
    "dates_of_birth": [str, ...],
    "nationalities": [{"relation", "country"}, ...],
}
```

`upsert_entries()` applies a **full re-sync strategy**:
- For each record in the feed: create or update the entity, then replace all child rows wholesale.
- For entities present in the DB but absent from the current feed: set `is_active = False` (soft-delete). Pass `deactivate_missing=False` when ingesting a partial/capped feed.

### OFAC SDN Ingestion ([app/ingestion/ofac_sdn.py](app/ingestion/ofac_sdn.py))

- **Source:** `https://www.treasury.gov/ofac/downloads/sdn.xml` — Treasury's public XML feed
- **Format:** XML with namespace, parsed with `lxml`
- **Source list code:** `OFAC_SDN`
- **Type:** `"sanctions"`
- **Extracts:** names (primary + aka/fka/nka), addresses, IDs (passports, digital-currency wallet addresses), sanctions programs, dates of birth, nationalities and citizenships

Run standalone:
```bash
python -m app.ingestion.ofac_sdn
```

### OpenSanctions Ingestion ([app/ingestion/opensanctions.py](app/ingestion/opensanctions.py))

- **Source:** `https://data.opensanctions.org/datasets/latest/{dataset}/targets.simple.csv`
- **Format:** Streaming CSV (no full-file memory load)
- **Datasets wired up:**

| Dataset | Source list code | Type | Default limit |
|---|---|---|---|
| `peps` | `OPENSANCTIONS_PEPS` | `"pep"` | 20,000 rows |
| `eu_fsf` | `EU_FSF` | `"sanctions"` | Full feed |

Run standalone:
```bash
python -m app.ingestion.opensanctions --dataset peps
python -m app.ingestion.opensanctions --dataset peps --limit 0   # full 1M+ feed
python -m app.ingestion.opensanctions --dataset eu_fsf
```

---

## Sanctions Screening — v1 (`screening/`)

The v1 engine screens a `Transaction` (name + optional country) against a loaded `WatchlistEntity` list using a two-stage approach: fast C-level blocking, then detailed hybrid scoring.

### Models ([screening/models.py](screening/models.py))

```python
class WatchlistEntity:
    id: str                    # "{LIST_CODE}:{source_uid}"
    full_name: str
    entity_type: EntityType    # INDIVIDUAL | ORGANIZATION
    country: str | None
    aliases: list[str]
    list_source: str           # e.g. "OFAC_SDN"
    risk_category: str

class Transaction:
    transaction_id: str
    counterparty_name: str
    counterparty_country: str | None

class ScreeningResult:
    verdict: ScreeningVerdict  # MATCH | REVIEW | NO_MATCH
    confidence: float          # 0–100
    matched_entities: list[MatchedEntity]
    explanation: str
    audit: dict
```

**Verdict thresholds (default):**
- `≥ 92.0` → `MATCH` (block + escalate)
- `≥ 78.0` → `REVIEW` (route to analyst)
- `< 78.0` → `NO_MATCH`

### Normalizer ([screening/normalizer.py](screening/normalizer.py))

| Function | What it does |
|---|---|
| `normalize_text(value)` | Lowercase, `unidecode` (accents → ASCII), strip non-alphanumeric |
| `tokenize(value)` | Normalize + split + remove stop tokens (`mr`, `bin`, `von`, `co`, `ltd`, ...) |
| `token_sort_key(value)` | Sorted token string — catches name reorderings |
| `is_common_name(value)` | True if ≥ half the tokens are in the common-name list (`smith`, `ali`, `chen`, ...) |

### Matcher ([screening/matcher.py](screening/matcher.py))

**`NameMatcher`** — the primary matcher:

1. For each candidate name (primary + aliases): compute a weighted blend of five similarity metrics:

| Signal | Weight | Library |
|---|---|---|
| `token_set_ratio` | 0.30 | rapidfuzz |
| `token_sort_ratio` | 0.25 | rapidfuzz |
| `WRatio` | 0.20 | rapidfuzz |
| `partial_ratio` | 0.15 | rapidfuzz |
| Phonetic overlap | 0.10 | jellyfish (Soundex + Metaphone + NYSIIS) |

2. Token-order bonus: `+8.0` if both names share the same sorted token key.
3. Country boost: `+5.0` if counterparty country matches entity country.
4. Common-name penalty: `-12.0` if the query name is a common name and score < 98.

**`TokenSetMatcher`** — A/B baseline: token-set ratio only, no phonetic, same boosts/penalties.

### Engine ([screening/engine.py](screening/engine.py))

```
screen(transaction):
  1. BLOCKING PASS (C-level, via rapidfuzz.process.extract)
     – token_set_ratio against every name/alias in the flat index
     – cutoff = 55, limit = 300 candidates
  2. DETAILED SCORING (per candidate)
     – NameMatcher.compare() → confidence + signals
     – Keep only candidates ≥ review_threshold (78.0)
  3. RANK & RETURN
     – Sort by confidence descending
     – Return top max_results (default 5)
     – Determine verdict from top score
```

### Watchlist Loader ([screening/watchlist_repo.py](screening/watchlist_repo.py))

`load_watchlist_from_db(db_path)` — reads `data/aml.db` directly via raw SQLite, joining entities, names, nationalities, and programs into `WatchlistEntity` objects. This is a one-shot load into memory at startup.

---

## Sanctions Screening — v2 (`screening_v2/`)

The v2 engine addresses v1 limitations: type-aware normalization, patronym stripping, and a FAISS semantic vector fallback for transliteration variants and cross-script names.

### Normalizer ([screening_v2/normalizer.py](screening_v2/normalizer.py))

Replaces v1's generic normalizer with type-aware pipelines:

**Individual pipeline:**
- Strip punctuation → `unidecode` → lowercase
- Drop patronymic suffixes (`ovich`, `ovna`, `evich`, ...) — reduces noise from Russian/Slavic names
- Compute NYSIIS phonetic code for the cleaned string

**Entity pipeline:**
- Strip punctuation → `unidecode` → lowercase
- Drop legal suffixes (`llc`, `gmbh`, `holdings`, `trading`, ...) — focuses matching on the distinctive part
- Expand known abbreviations (e.g., `vtb` → `vneshtorgbank`)
- No phonetic code (inapplicable to organization names)

`detect_type(name)` auto-classifies based on legal suffix presence.

### Normal Search ([screening_v2/normal_search.py](screening_v2/normal_search.py))

Builds an in-memory index of all `(normalized_name, entity_pk, list_code, source_uid, raw_name, entity_type)` tuples from the database at startup.

**Search pipeline:**
1. **Blocking pass**: `token_set_ratio` against every entry; cutoff = 55
2. **Detailed scoring** on candidates that pass blocking:
   - `token_set_ratio` (TSR) + `reorder_resistant_jaro_winkler` (JW)
   - Individuals: `TSR×0.40 + JW×0.35 + phonetic×0.25`
   - Entities: `TSR×0.53 + JW×0.47` with coverage penalty applied
3. **Profile fetch**: batch-loads full `EntityProfile` for the top-5 candidates from the DB

**Thresholds:**
- `HIGH_CONFIDENCE = 0.85`
- `LOW_CONFIDENCE = 0.72`
- `BLOCK_THRESHOLD = 55` (raw token_set_ratio, 0–100 scale)

### Vector Search ([screening_v2/vector_search.py](screening_v2/vector_search.py))

Used only when normal search scores below `HIGH_CONFIDENCE` (0.85) — serves as a fallback for transliterations, scripts, and semantic synonyms.

- **Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers)
- **Index:** FAISS `IndexFlatIP` with L2-normalized vectors (inner product = cosine similarity)
- **Candidate pool:** `TOP_K = 50` semantic neighbors
- **Guard rails** to suppress false positives:
  - `VECTOR_MIN_FUZZY = 0.62` — fuzzy score must also be ≥ 0.62
  - `all_significant_tokens_match()` — each query token must fuzzy-match some candidate token (threshold 0.82) — applies to individuals only
  - Entity coverage penalty for single-token overlap
- **Final score:** `0.6 × fuzzy + 0.4 × cosine`

### Scoring Utilities ([screening_v2/scoring.py](screening_v2/scoring.py))

| Function | Purpose |
|---|---|
| `reorder_resistant_similarity(q, c)` | `max(JW(q,c), JW(sorted(q), sorted(c)))` — handles first/last name transposition |
| `all_significant_tokens_match(q, c)` | Each significant token in `q` must have a JW ≥ 0.82 match in `c` |
| `apply_entity_coverage_penalty(score, q, c)` | Multiplies score by token coverage fraction — prevents "logistics" matching "Al-Aqsa Logistics" |
| `token_coverage(q, c)` | Fraction of tokens matched on both sides |

### Engine v2 ([screening_v2/engine.py](screening_v2/engine.py))

```
screen(name, entity_type="auto"):
  1. detect/override entity_type
  2. normalize(name, entity_type) → NormalizedInput
  3. NormalSearcher.search(normalized) → candidates
  4. if top score < HIGH_CONFIDENCE (0.85):
       VectorSearcher.search(normalized, existing_candidates) → more candidates
       merge by entity_id, keep top 5
  5. build ScreeningResult:
       score ≥ 0.85:
         sanctions list → MATCH
         pep list       → REVIEW
       score ≥ 0.72 → REVIEW
       else         → NO_MATCH
```

**Verdict logic differs from v1:** list type matters — a high-confidence hit on a PEP list yields `REVIEW`, not `MATCH` (PEPs require human judgment, not an automatic block).

### Verdict Composer ([screening_v2/composer.py](screening_v2/composer.py))

Aggregates screening results across multiple parties and layers into a single payment-level decision.

**`compose(originator, beneficiary)`** — Layer A only:
- Takes the highest-priority verdict of the two parties
- `MATCH > REVIEW > NO_MATCH`

**`compose_payment(originator, beneficiary, behavioral_score, behavioral_outcome, behavioral_hits)`** — Full pipeline:

```
Layer A verdict = max(originator.verdict, beneficiary.verdict)
Layer B verdict = map(aml_detect_outcome → MATCH/REVIEW/NO_MATCH)
Final verdict   = max(layer_a, layer_b)
Confidence      = max(layer_a_confidence, behavioral_score / 100)
```

**Recommended action mapping:**
- `MATCH` → `BLOCK`
- `REVIEW` → `MANUAL_REVIEW`
- `NO_MATCH` → `PASS`

---

## AML Behavioral Detection ([app/aml_detect.py](app/aml_detect.py))

Marble-inspired rule engine that evaluates behavioral patterns in `EntityTransaction` history. Operates independently from name/sanctions matching — handles the **what is happening** dimension while screening handles the **who are they** dimension.

### Rules

| Rule ID | Severity | Score | Trigger |
|---|---|---|---|
| `amt_large` | high | 35 | Single transaction ≥ $10,000 |
| `velocity_24h` | medium | 25 | > 5 transactions in 24 hours |
| `structuring_7d` | high | 40 | ≥ 3 transactions between $9,000–$9,999 in 7 days ("smurfing") |
| `geo_high_risk` | high | 30 | Counterparty in `{IR, KP, SY, CU, RU, BY, MM, VE}` |
| `dormant_reawake` | medium | 20 | Account dormant ≥ 90 days, reactivated with ≥ $5,000 |

### Decision Thresholds

| Score range | Outcome |
|---|---|
| ≥ 90 | `block_and_review` |
| ≥ 60 | `decline` |
| ≥ 30 | `review` |
| < 30 | `approve` |

### API

```python
from app.aml_detect import scan
from app.database import SessionLocal

with SessionLocal() as session:
    decisions = scan(session)  # scans all "pending" transactions
    # or: scan(session, transactions=[...]) for explicit list
```

Each `TransactionDecision` includes: `score`, `outcome`, and a list of `TransactionRuleHit` objects with machine-readable `reason` and human-readable `explanation` fields.

---

## FastAPI HTTP Layer ([app/main.py](app/main.py))

Base URL: `http://localhost:8000` (default uvicorn)

All requests are logged with method, path, query params, status code, and latency.

### Endpoints

#### `POST /ingest/ofac-sdn`
Fetches and ingests the current OFAC SDN XML feed. Returns `IngestionResult`.

```json
{ "source_list": "OFAC_SDN", "entries_processed": 12543, "publish_date": "06/11/2025" }
```

#### `POST /ingest/opensanctions-peps?limit=20000`
Ingests the OpenSanctions PEPs collection (default cap: 20,000 rows). Pass `limit=0` for the full 1M+ feed.

#### `POST /ingest/eu-fsf`
Ingests the EU Financial Sanctions Files (EU consolidated list). Full feed, no limit.

#### `POST /export/vectorize`
Exports all active entities as a JSONL file to `data/vectorize_export.jsonl`. Returns `{ "output_path": "...", "entities_exported": N }`.

#### `GET /entities/search?name=<name>&limit=20`
Substring search across `entity_names.full_name` for active entities. Returns list of `EntitySearchResult` with matched names, entity type, source list, and sanction programs.

---

## Vectorization Export

[app/export/vectorize_export.py](app/export/vectorize_export.py) exports all active entities to a JSONL file where each line is:

```json
{
  "id": "OFAC_SDN:12345",
  "text": "Name: Vladimir Putin. Also known as: Владимир Путин. Type: individual. Country/nationality: RU. Programs/sources: UKRAINE-EO13685. List: OFAC_SDN.",
  "metadata": {
    "entity_id": 1,
    "source_list": "OFAC_SDN",
    "source_uid": "12345",
    "entity_type": "individual",
    "primary_name": "Vladimir Putin",
    "aliases": [...],
    "countries": ["RU"],
    "programs": ["UKRAINE-EO13685"],
    "list_type": "sanctions"
  }
}
```

The `text` field is designed as a high-quality embedding input — it packs identity-relevant information in natural prose without filler. The `metadata` dict enables post-retrieval filtering by list, type, or country.

This is the handoff point to external vector stores (Pinecone, Weaviate, pgvector, etc.) — the export does not write to any vector store itself.

---

## Evaluation Framework

Located in [screening/evaluation/](screening/evaluation/). Provides a rigorous A/B testing harness to compare screening algorithm variants against a labeled benchmark.

### Benchmark ([data/benchmark.json](data/benchmark.json))

Each case is a labeled transaction with an expected verdict:

```json
{
  "case_id": "bench-001",
  "transaction_id": "txn-b-001",
  "counterparty_name": "Vladimir Putin",
  "counterparty_country": "RU",
  "label": "positive",
  "expected_verdict": "MATCH",
  "expected_entity_id": "OFAC_SDN:35096",
  "category": "exact_match",
  "notes": "Simplified form of OFAC primary name Vladimir Vladimirovich PUTIN"
}
```

Categories represented: `exact_match`, `alias_transliteration`, `fuzzy_match`, `negative` (true negatives), etc.

### Algorithm Variants ([screening/evaluation/variants.py](screening/evaluation/variants.py))

| Variant | Description | match / review thresholds |
|---|---|---|
| `hybrid_default` | Hybrid fuzzy + phonetic, default thresholds | 92 / 78 |
| `hybrid_strict` | Same matcher, higher thresholds (fewer alerts) | 95 / 85 |
| `hybrid_sensitive` | Same matcher, lower thresholds (more alerts) | 88 / 72 |
| `token_set_baseline` | Token-set ratio only | 92 / 78 |
| `v2_cascade` | v2 engine: type-aware norm + patronym strip + FAISS fallback | 85% / 72% |

### Metrics ([screening/evaluation/models.py](screening/evaluation/models.py))

For each variant the framework computes:

**Flag metrics** (MATCH or REVIEW = flagged):
- Precision, Recall, F1, **F2** (recall-weighted — standard in compliance), **MCC** (robust for imbalanced classes), Accuracy
- False Positive Rate, False Negative Rate, Alert Rate

**Block metrics** (MATCH only = auto-blocked):
- Same metrics, binary: was the transaction hard-blocked?

**Entity hit rate**: of cases with a known `expected_entity_id`, fraction where the top match was the correct entity.

**Verdict metrics**: multi-class precision/recall/F1 per MATCH / REVIEW / NO_MATCH class.

---

## CLI (`manage.py`)

Unified management CLI. Run from `backend/`:

```bash
# Ingest watchlists
python manage.py fetch --source ofac-sdn
python manage.py fetch --source opensanctions-peps --limit 5000
python manage.py fetch --source opensanctions-eu

# Export entities for vectorization
python manage.py export
python manage.py export --output /tmp/entities.jsonl

# Screen a single name
python manage.py screen --name "Vladimir Putin" --country RU
python manage.py screen --name "Acme Trading LLC" --json

# Screen a batch from JSON
python manage.py screen --transactions txns.json

# Run A/B evaluation
python manage.py evaluate
python manage.py evaluate --variants hybrid_default v2_cascade --show-failures
python manage.py evaluate --output report.json
```

---

## Configuration & Environment

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/aml.db` | SQLAlchemy DB URL. Supports Postgres: `postgresql://user:pw@host/db` |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

For Postgres, remove the `check_same_thread` connect arg — it is applied automatically only for SQLite connections.

---

## Dependencies

```
fastapi>=0.115.0          # HTTP framework
uvicorn[standard]>=0.32.0 # ASGI server
sqlalchemy>=2.0           # ORM + query builder
httpx>=0.27.0             # HTTP client (ingestion feeds)
lxml                      # OFAC SDN XML parsing
pydantic>=2.9.0           # Data validation + serialization
rapidfuzz>=3.10.0         # Levenshtein / token fuzzy matching (C-level)
jellyfish>=1.1.0          # Phonetic algorithms: Soundex, Metaphone, NYSIIS, Jaro-Winkler
unidecode>=1.3.8          # Unicode → ASCII transliteration
sentence-transformers>=3.0.0  # Multilingual embedding model (v2 engine)
faiss-cpu>=1.8.0          # Approximate nearest-neighbor search (v2 engine)
pytest>=8.3.0             # Testing
```

---

## Running the System

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Ingest data

```bash
python manage.py fetch --source ofac-sdn
```

The database is created automatically at `data/aml.db` if it does not exist.

### 3. Start the API server

```bash
uvicorn app.main:app --reload
```

Swagger UI available at `http://localhost:8000/docs`.

### 4. Run tests

```bash
pytest tests/
```

### 5. Run the evaluation benchmark

```bash
python manage.py evaluate --show-failures
```
