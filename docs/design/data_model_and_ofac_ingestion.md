# Data Model & OFAC Ingestion — Design

**Status:** First implementation slice for the AML/sanctions screening tool (iteration 1).
**Goal:** Get sanctioned-entity data into our own DB in a shape that supports name matching now, and
PEP / adverse media / beneficial-ownership / crypto-wallet checks later without a schema rewrite.

---

## 1. Data sources

Two OFAC-related sources, used together:

### A. Official Treasury SDN/Consolidated data feeds (primary, free, no key)

- SDN list (and the broader Consolidated list) are published as XML/CSV by
  `https://sanctionslistservice.ofac.treas.gov/...` (also mirrored on treasury.gov).
- No API key, no rate limit, updated ~daily. This is the authoritative source and gives us **every
  raw field** OFAC publishes: names, aliases, addresses, DOB/POB, nationalities, ID documents
  (passports, national IDs, tax IDs), **and digital currency addresses** (BTC/ETH/etc — the SDN
  `idList` includes `idType` values like `Digital Currency Address - XBT`, `... - ETH`, `... - XMR`).
  That last point matters: it means the *same ingestion pipeline* feeds both the fiat name-matching
  engine and the crypto wallet-lookup table (problem statement item #8/#9).
- We own the data → we own the matching/scoring logic, no per-request cost, works offline during
  the demo if needed.

### B. docs.ofac-api.com (secondary, optional, requires API key)

- Third-party wrapper exposing a "Sanctions Search API" (direct list search) and a "Sanctions
  Screening API" (fuzzy match with a score). Auth via `apiKey` header or body param.
- Treated as an **optional additional source / fallback**, not the system of record. If we get a
  key, it can either (a) seed/validate our own ingestion, or (b) act as a secondary screening
  signal we attach to a `screening_result`. Not required for the MVP.

---

## 2. Data model

Normalized around a generic "screening list entry" so that sanctions (OFAC SDN/Consolidated today,
EU/UN/OFSI later) and non-sanctions lists (PEP, adverse media hits, etc.) all plug into the same
shape. Everything that's specific to OFAC's XML structure lives in child tables; the matching engine
mostly queries `entities` + `entity_names` + `entity_identifications`.

```
source_lists
  id              PK
  code            text   unique   -- e.g. "OFAC_SDN", "OFAC_CONSOLIDATED", "EU_CONSOLIDATED", "PEP_XYZ"
  name            text            -- human readable
  list_type       text            -- "sanctions" | "pep" | "adverse_media" | ...
  url             text            -- source feed URL
  last_fetched_at timestamptz
  last_published_at  timestamptz  -- "Publish_Date" from the feed itself

entities
  id              PK
  source_list_id  FK -> source_lists.id
  source_uid      text            -- OFAC <uid>, stable across updates
  entity_type     text            -- "individual" | "entity" | "vessel" | "aircraft"
  primary_name    text
  title           text   nullable
  remarks         text   nullable
  is_active       bool            -- false once it disappears from a refreshed feed (soft delete)
  raw             jsonb           -- full raw record, for audit/debug
  first_seen_at   timestamptz
  last_seen_at    timestamptz
  UNIQUE(source_list_id, source_uid)

entity_names                       -- primary name + every alias, one row per matchable name
  id              PK
  entity_id       FK -> entities.id
  name_type       text            -- "primary" | "aka" | "fka" | "nka"
  quality         text   nullable -- OFAC aka "category": "strong" | "weak" (weak = lower match weight)
  full_name       text            -- normalized full string, used for matching
  first_name      text   nullable
  last_name       text   nullable

entity_addresses
  id              PK
  entity_id       FK -> entities.id
  address_line    text   nullable
  city            text   nullable
  state_province  text   nullable
  postal_code     text   nullable
  country         text   nullable

entity_identifications             -- passports, national IDs, tax IDs, AND crypto wallet addresses
  id              PK
  entity_id       FK -> entities.id
  id_type         text            -- e.g. "Passport", "National ID No.", "Digital Currency Address - XBT"
  id_number       text            -- the actual value (wallet address, doc number, ...)
  id_country      text   nullable

entity_programs                    -- sanctions program codes (SDGT, UKRAINE-EO13662, ...)
  id              PK
  entity_id       FK -> entities.id
  program_code    text

entity_dates_of_birth
  id              PK
  entity_id       FK -> entities.id
  date_of_birth   text            -- kept as text; OFAC gives ranges/partial dates ("circa 1965")

entity_nationalities
  id              PK
  entity_id       FK -> entities.id
  relation        text            -- "nationality" | "citizenship" | "place_of_birth"
  country         text
```

### Why this shape

- **`entity_identifications` doubles as the crypto wallet table.** A wallet lookup is just
  `WHERE id_type LIKE 'Digital Currency Address%' AND id_number = :address`. No separate crypto
  schema needed for the OFAC-sourced wallet list (problem statement crypto bonus, option #8).
- **`entity_names` is the only table the fuzzy/embedding matcher needs to read.** Adding a PEP list
  later means inserting rows into `source_lists` + `entities` + `entity_names` — the matcher doesn't
  change.
- **`source_list_id` on every entity** means a single payment can be screened against *all* active
  lists in one query, and the result can say which list(s) matched.
- **`raw jsonb`** keeps the full original record so nothing is lost to normalization mistakes, and
  gives the analyst review UI something to show ("here's exactly what OFAC published").
- **Soft delete (`is_active`)** because OFAC removes entries (delistings). We never hard-delete —
  audit trail requirement from the problem statement ("explain a verdict two years later").

### Out of scope for this slice (future tables, not built now)

- `screening_results` — one row per payment screened, referencing matched `entities`, score,
  verdict (MATCH/REVIEW/NO MATCH), reviewer decision. This is the next slice once the matcher exists.
- `payments` — incoming transactions to screen.

---

## 3. Ingestion pipeline (this slice)

1. Fetch the SDN.XML (and optionally Consolidated.XML) from the Treasury feed.
2. Parse with `lxml`/`xml.etree`, walk each `<sdnEntry>`.
3. Upsert into `entities` keyed on `(source_list_id, source_uid)`:
   - update `raw`, `last_seen_at`, re-sync child rows (`entity_names`, `entity_addresses`,
     `entity_identifications`, `entity_programs`, `entity_dates_of_birth`, `entity_nationalities`)
     by delete-and-reinsert (simplest correct approach for a list that refreshes daily).
   - any entity in DB but not in the new feed → `is_active = false`.
4. Update `source_lists.last_fetched_at` / `last_published_at`.

Runs as a script (`python -m app.ingestion.ofac_sdn`) for now; can be wired into a scheduled job
later (problem statement: "how do you refresh data without breaking live decisions" — soft-delete +
upsert means the table is queryable throughout the refresh, no downtime).

---

## 4. Stack

- Python, SQLAlchemy 2.x models, Postgres in prod / SQLite for local hackathon dev (same models,
  swap the connection string).
- Minimal FastAPI app exposing `POST /ingest/ofac-sdn` (trigger refresh) and
  `GET /entities/search?name=...` (placeholder exact/substring search until the fuzzy matcher
  exists) — matches the `Python, FastAPI` stack noted in `docs/design/iterations/iteration1.md`.
