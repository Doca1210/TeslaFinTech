# Payment Screening Pipeline — Implementation Approach (First Pass)

**Status:** Draft — first-pass implementation plan for `backend/app/payments/`
**Scope:** How to fill in the architecture skeleton from section 2.3 of
`docs/design/priority_backlog.md`, optimized for hackathon time constraints.
**Related:** `docs/design/priority_backlog.md` (section 2.3 diagram, section 4
data model, task backlog T-001 through T-018)

---

## 1. Guiding principles

- **Sync first, async later.** Layers run sequentially (`for layer in self.layers`).
  The cited ~43ms screening benchmark means three sequential layers won't get
  close to the 1s budget. Async/`asyncio.gather` is a documented stretch item
  (section 6), not a prerequisite — see section 7 below.
- **SQLite only, no new infra.** `Base.metadata.create_all()` already
  auto-creates tables on startup — no Alembic, no Postgres, no Docker required
  for the data layer. Docker is at most a "demo insurance" wrapper around
  uvicorn + the SQLite file.
- **Persist what's load-bearing for the demo story.** `payments` and
  `screening_results` must be real DB rows (success criterion: "every decision
  has a persisted, queryable audit record"). `review_cases` /
  `analyst_decisions` are also plain tables — `create_all()` makes this nearly
  free, so don't fall back to in-memory dicts for these.
- **Don't gold-plate the optional pieces.** Post-MATCH workflow and the LLM
  case summary (T-015) should be the cheapest possible implementation with a
  safe fallback — they're narrative color, not core verdict logic.

---

## 2. Data model additions (`app/models.py`)

Add SQLAlchemy models for the five new tables from section 4 of the priority
backlog:

| Table | Notes for first pass |
|-------|----------------------|
| `payments` | Add `account_id` (used by Layer B) — derive from `originator_account` for the demo. |
| `screening_results` | Append-only. Never `UPDATE` after insert. |
| `entity_transaction_history` | Seeded by T-011's `seed-history` script. |
| `review_cases` | Mutable — `status`/`assigned_to`/`summary` get updated. |
| `analyst_decisions` | One row per decide call. |

No migration tooling — `create_all()` on the existing `Base` picks these up
automatically, same as the current `entities`/`source_lists` tables.

---

## 3. `PaymentIntake`

- Let Pydantic do most validation via the request model (required fields,
  types) — don't hand-roll checks FastAPI gives for free.
- `normalize()` responsibilities:
  - Compute `countries_in_scope` = dedup'd, non-null union of
    `originator_country`, `beneficiary_country`, `originator_bank_country`,
    `beneficiary_bank_country`.
  - Set `account_id` (defaults to `originator_account`).
  - Preserve the original request body in `raw_payload`.
- **Legacy adapter:** if the payload matches the old
  `{counterparty_name, counterparty_country}` shape, map
  `counterparty_*` → `beneficiary_*` and default `originator_*` to a fixed
  "demo company" identity. One `if`/`else` branch, not a separate class.

---

## 4. Layer A — `SanctionsLayer`

- `ScreeningEngine` is expensive to build (loads ~7k watchlist entries) — build
  it **once** in `lifespan` (as `screening_api.py` already does) and pass it via
  `LayerContext.extra["engine"]`. Never construct it per-request.
- Build two ad-hoc `Transaction` objects (originator, beneficiary), call
  `engine.screen()` on each, and take the **higher-confidence** result as the
  layer verdict.
- Merge `matched_entities`/signals from both sides into `LayerResult.details`
  so the explanation can say "originator: clean; beneficiary: REVIEW at 82%"
  (T-018).
- **Do not** touch matcher weights/thresholds — frozen per T-004.

---

## 5. Layer B — `BehavioralLayer`

- Pure Python + `statistics` module — the per-account history is at most ~90
  rows, no need for pandas/numpy.
- Three signals, each a small standalone function:
  1. **Amount anomaly** — z-score of `payment.amount` vs 90-day rolling
     mean/stddev for `account_id`; `z > 3` → REVIEW.
  2. **Pass-through** — an opposite-direction transaction within 24h where
     `min(amounts)/max(amounts) > 0.85` → REVIEW.
  3. **New counterparty** — `beneficiary_name` not seen before for this
     account → minor REVIEW signal (lower weight than 1/2).
- **Safety rule:** if `entity_transaction_history` has zero rows for
  `account_id`, return `NO_MATCH` immediately. Don't let "no data" look
  anomalous — this is an explicit acceptance criterion (T-006).

---

## 6. Layer C — `JurisdictionLayer`

- No DB access at all. Load a static `risk_tiers.json`
  (`{"IR": "HIGH", "KP": "HIGH", ...}`) once at layer construction.
- Three rules from the priority backlog, each a simple lookup:
  - `beneficiary_country` is HIGH → REVIEW
  - `originator_bank_country != originator_country` → REVIEW
  - any HIGH country in `countries_in_scope` → REVIEW
- Config file is hand-editable without redeploying — this *is* the acceptance
  criterion, no need for an admin UI.

---

## 7. `VerdictComposer`

- Pure function, no I/O:
  - Overall verdict: any layer `MATCH` → `MATCH`; else any `REVIEW` → `REVIEW`;
    else `NO_MATCH`.
  - `confidence`: max confidence among the layers that produced the winning
    verdict.
- `list_versions`: one read of `SourceList.last_published_at` (e.g. for
  `OFAC_SDN`, and `PEP` if T-020 lands).
- `engine_version`: a `GIT_SHA`/version env var, or a hardcoded string for the
  demo — not real CI metadata.
- `explanation`: concatenate each layer's `reason` with a short per-layer
  header. This alone satisfies T-009 — the LLM summary (T-015) is a *separate*
  enrichment for the review queue, not part of this explanation.

---

## 8. `AuditStore`

- One DB transaction: insert `payments` row, insert `screening_results` row,
  commit. That's the entire implementation — `screening_results` is
  append-only by construction, so no update/upsert paths needed.

---

## 9. `ReviewQueue`

- `priority` derivation: simple threshold table on `(confidence, amount)` —
  e.g. `confidence > 0.9 or amount > X` → `HIGH`, else `MEDIUM`/`LOW`. A lookup
  table, not a model.
- **T-015 LLM summary** (optional, do last): generate *after* the
  `review_cases` row is committed, via FastAPI `BackgroundTasks`. Write the
  summary back with a normal `UPDATE` (this table isn't append-only). Always
  have a template-string fallback so a flaky API key can't break the demo.

---

## 10. `PostMatchWorkflow`

- Lowest-effort component on purpose:
  `logger.info("Compliance notified at %s for payment %s", ...)` plus either a
  small `compliance_events` table **or** just a JSON field on
  `screening_results` (simpler — avoids a new table). No real
  webhook/notification system; explicitly out of scope.

---

## 11. Future: async layers (not in this pass)

If time allows after the sequential version works end-to-end:

- `ScreeningLayer.run` becomes `async def`.
- `ScreeningPipeline.screen` becomes `async def` and uses
  `asyncio.gather(*(layer.run(payment, ctx) for layer, ctx in ...))`.
- `LayerContext` changes from holding one shared `Session` to a per-layer
  session factory (`db_factory: Callable[[], Session]`) — SQLAlchemy sessions
  aren't safe to share across concurrent coroutines. SQLite handles multiple
  read connections fine given the existing `check_same_thread: False`.
- The CPU-bound `SanctionsLayer` (~40ms rapidfuzz scoring) should be wrapped in
  `asyncio.to_thread(engine.screen, ...)` so it doesn't block the event loop —
  `async def` alone doesn't make CPU-bound work concurrent.
- Treat this as a P2/stretch item (Phase 4 buffer): it's a clean, contained
  change but the latency win is marginal (~tens of ms) and not worth debugging
  async stack traces under demo pressure.

---

## 12. Suggested build order

1. Data models (`app/models.py` additions) — unblocks everything else.
2. `PaymentIntake` + `JurisdictionLayer` (no dependencies, fast wins).
3. `SanctionsLayer` (wire existing engine, frozen thresholds).
4. `VerdictComposer` (can be exercised with A + C only initially).
5. `AuditStore` — get `/screen` persisting end-to-end.
6. T-011 seed script, then `BehavioralLayer`.
7. `ReviewQueue` (without LLM summary), then `PostMatchWorkflow`.
8. T-015 LLM summary as a final enrichment, with fallback.
