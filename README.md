# TeslaFinTech — Sanctions & PEP Screening

Python screening engine for the Garaža FinTech AI Hackathon. Screens incoming payment counterparties against live OFAC SDN and PEP watchlists, returning one of three verdicts:

- **MATCH** — high-confidence hit; block and escalate
- **REVIEW** — plausible hit; send to analyst queue
- **NO MATCH** — clean result; release payment

## Features

- Live OFAC SDN ingestion from the US Treasury XML feed into SQLite
- Hybrid fuzzy + phonetic name matching (RapidFuzz + Soundex/Metaphone/NYSIIS)
- Transliteration and alias handling (`Vladimir Poutine` → `Vladimir Putin`)
- Token reordering support (`Shoigu Sergei` vs `Sergei Shoigu`)
- Country-aware confidence boost
- Common-name penalty to reduce false positives (`Kim Lee`, `John Smith`)
- Audit trail on every decision
- REST API (FastAPI) and unified management CLI

## Quick start

```bash
cd backend
python -m venv ../venv
source ../venv/bin/activate   # Windows: ..\venv\Scripts\activate
pip install -r requirements.txt
```

Populate the database with the live OFAC SDN list:

```bash
python manage.py fetch
```

## Management CLI

All commands run from the `backend/` directory via `manage.py`.

### fetch

Download and ingest the OFAC SDN list from the US Treasury feed:

```bash
python manage.py fetch
```

### screen

Screen a single counterparty name:

```bash
python manage.py screen --name "Sergey Shoygu" --country RU
```

Screen a batch from a JSON file:

```bash
python manage.py screen --transactions data/sample_transactions.json
```

JSON output:

```bash
python manage.py screen --name "Vladimir Poutine" --country RU --json
```

### evaluate

Compare algorithm variants against a labeled benchmark:

```bash
# All built-in variants
python manage.py evaluate

# Specific variants with failure details
python manage.py evaluate --variants hybrid_default token_set_baseline --show-failures

# Full JSON report written to disk
python manage.py evaluate --output reports/ab_report.json
```

## REST API

```bash
uvicorn app.main:app --reload
```

Screen a transaction:

```bash
curl -X POST http://127.0.0.1:8000/screen \
  -H "Content-Type: application/json" \
  -d '{"transaction_id":"demo-1","counterparty_name":"Muammar al Qadhafi","counterparty_country":"LY"}'
```

Interactive docs: `http://127.0.0.1:8000/docs`

## Project layout

```
backend/
  manage.py                  Unified CLI (fetch / screen / evaluate)
  screening_api.py           FastAPI application factory
  app/
    main.py                  FastAPI routes
    models.py                SQLAlchemy ORM models
    database.py              DB session / engine setup
    schemas.py               Pydantic request/response schemas
    ingestion/
      ofac_sdn.py            OFAC SDN XML fetch & upsert pipeline
  screening/
    engine.py                Orchestrates watchlist screening
    matcher.py               Fuzzy + phonetic scoring
    normalizer.py            Name normalisation helpers
    models.py                Pydantic transaction/result models
    watchlist_repo.py        Loads watchlist from SQLite
    pep_loader.py            PEP list loader
    evaluation/
      pipeline.py            A/B test runner
      variants.py            Built-in algorithm variants
      metrics.py             Precision / recall / F1 helpers
      benchmark_loader.py    Benchmark JSON loader
      models.py              Evaluation result models
  tests/
    test_screening.py
    test_evaluation.py
```

## Thresholds

Default scoring thresholds in `ScreeningEngine`:

| Score   | Verdict   |
|---------|-----------|
| ≥ 92%   | MATCH     |
| 78–91%  | REVIEW    |
| < 78%   | NO MATCH  |

Tune via constructor args for your false-positive / false-negative tradeoff.

## Tests

```bash
pytest -q
```

## Evaluation & A/B testing

### Built-in variants

| Variant | Description |
|---------|-------------|
| `hybrid_default` | Fuzzy + phonetic matcher (production default) |
| `hybrid_strict` | Higher thresholds, fewer false positives |
| `hybrid_sensitive` | Lower thresholds, catches more edge cases |
| `token_set_baseline` | Token-set only baseline for comparison |

### Metrics reported

**Flag metrics** (primary): treats MATCH and REVIEW as positive. Reports accuracy, precision, recall, F1, FPR, FNR.

**Block metrics**: treats only MATCH as positive — useful when auto-blocks must be precise.

**Entity hit rate**: fraction of cases where the top matched entity equals the labeled target.

**Verdict metrics**: macro/weighted F1 across MATCH / REVIEW / NO_MATCH.

### Benchmark format

```json
{
  "case_id": "bench-001",
  "transaction_id": "txn-b-001",
  "counterparty_name": "Vladimir Poutine",
  "counterparty_country": "RU",
  "label": "positive",
  "expected_verdict": "MATCH",
  "expected_entity_id": "pep-001",
  "category": "alias_transliteration"
}
```

Labels: `positive` (should flag) or `negative` (should not).

## Hackathon context

Built for sanctions/PEP screening against incoming fiat payment instructions. Emphasises transliteration, aliases, false-positive control, speed, and explainability — with a path to extend into crypto wallet screening, adverse media, and analyst review queues.
