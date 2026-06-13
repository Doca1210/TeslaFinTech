# TeslaFinTech — PEP / Suspicious Name Screening

Python screening engine for the Garaža FinTech AI Hackathon. Matches incoming payment counterparties against PEP and suspicious-name watchlists, then returns one of three verdicts:

- **MATCH** — high-confidence hit; block and escalate
- **REVIEW** — plausible hit; send to analyst queue
- **NO MATCH** — clean result; release payment

## Features

- Hybrid fuzzy + phonetic name matching (RapidFuzz + Soundex/Metaphone/NYSIIS)
- Transliteration and alias handling (`Vladimir Poutine` → `Vladimir Putin`)
- Token reordering support (`Shoigu Sergei` vs `Sergei Shoigu`)
- Country-aware confidence boost
- Common-name penalty to reduce false positives (`Kim Lee`, `John Smith`)
- Audit trail on every decision
- REST API (FastAPI) and CLI

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### CLI

Screen a single name:

```bash
python cli.py --name "Sergey Shoygu" --country RU
```

Screen sample transactions:

```bash
python cli.py --transactions data/sample_transactions.json
```

JSON output:

```bash
python cli.py --name "Vladimir Poutine" --country RU --json
```

### API

```bash
uvicorn app:app --reload
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/screen ^
  -H "Content-Type: application/json" ^
  -d "{\"transaction_id\":\"demo-1\",\"counterparty_name\":\"Muammar al Qadhafi\",\"counterparty_country\":\"LY\"}"
```

Interactive docs: `http://127.0.0.1:8000/docs`

## Project layout

```
app.py                     FastAPI service
cli.py                     Command-line screener
screening/
  engine.py                Orchestrates watchlist screening
  matcher.py               Fuzzy + phonetic scoring
  normalizer.py            Name normalization helpers
  models.py                Pydantic models
  pep_loader.py            Watchlist loader
data/
  pep_list.json            Sample PEP / suspicious entities
  sample_transactions.json Demo inbound payments
tests/
  test_screening.py
```

## Watchlist format

Each entity in `data/pep_list.json`:

```json
{
  "id": "pep-001",
  "full_name": "Vladimir Putin",
  "entity_type": "individual",
  "country": "RU",
  "aliases": ["Vladimir Poutine"],
  "list_source": "PEP",
  "risk_category": "Head of State"
}
```

Replace or extend this file with real OFAC/OFSI/EU/UN or PEP feeds for production use.

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

## Hackathon context

Built for sanctions/PEP screening against incoming fiat payment instructions. The problem brief emphasizes transliteration, aliases, false positives, speed, and explainability — this MVP focuses on the name-matching core with a path to extend into crypto wallet screening, adverse media, and analyst review queues.
