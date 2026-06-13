# Sanctions Screening Engine — Design Document

**Project:** Garaža FinTech AI Hackathon — Sokin Problem Statement
**Team:** Pavle Prodanović, Dositej Cvetković, Igor Antonijević
**Date:** June 13, 2026
**Focus:** Real-time automated transaction screening with minimal false positives

---

## Problem Statement

Every payment that crosses a border must be screened against sanctions lists before it clears. The legal exposure for getting it wrong runs to ten-figure fines. The current state of the art is:

- Batch or near-real-time, not truly real-time
- High false positive rates (5-30% in practice) that destroy analyst productivity
- Name matching that breaks on transliteration, aliases, and shell companies
- Crypto screening that is limited to direct OFAC wallet lookups
- List updates that require manual processes and risk downtime
- Zero explainability — when a regulator asks "why did you flag this?" the answer is "because the score exceeded threshold"

The goal is an engine that produces a MATCH / REVIEW / NO MATCH verdict in under 500ms, at arbitrary throughput, with full explainability, across fiat and crypto.

---

## Core Innovation Thesis

Most screening systems are **lookup tables with fuzzy string matching bolted on**. The innovation space is:

1. **Multi-layer matching pipeline** that short-circuits on confidence — exact match exits immediately, fuzzy match exits on high confidence, only truly borderline cases reach the LLM. This achieves sub-second P99 without sacrificing recall.

2. **Behavioral profiling** per entity — transactions are not independent events. A $50K wire from an account that averages $2K is a different risk signal than a $50K wire from an account that regularly moves millions. Most screening systems ignore this dimension entirely.

3. **Graph-based risk propagation** — sanctions evasion routes through intermediaries. A direct match is easy. The hard problem is: this company is 3 hops from a sanctioned individual through shell companies. Graph traversal with risk decay solves this.

4. **Hot-reload list management** — lists update daily. A system that requires downtime to update is a liability. The architecture must support atomic in-place updates with zero-downtime rollover.

5. **Feedback loop** — analyst decisions are training signal. Every CONFIRM / DISMISS on a REVIEW case improves future scoring. Most systems throw this data away.

---

## Architecture Overview

```
Upstream Payment System
        │
        ▼
┌─────────────────────┐
│   Intake / Gateway  │  Normalize, validate, extract entities
│   (FastAPI)         │  Emit ScreeningRequest event
└────────┬────────────┘
         │  async event
         ▼
┌─────────────────────────────────────────────────────┐
│                  Screening Pipeline                  │
│                                                     │
│  Layer 1: Exact Match        ──► MATCH (exit fast)  │
│  Layer 2: Phonetic / Edit    ──► score              │
│  Layer 3: Embedding Lookup   ──► score              │
│  Layer 4: LLM Disambiguation ──► verdict (borderline│
│           (only borderline)       cases only)       │
│                                                     │
│  Parallel: Behavioral Check  ──► anomaly_score      │
│  Parallel: Crypto Graph      ──► hop_risk_score     │
│                                                     │
│  Score Composer              ──► final verdict      │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐      ┌──────────────────────┐
│   Verdict Store     │      │   REVIEW Queue        │
│   (audit trail)     │      │   (analyst UX)        │
└─────────────────────┘      └──────────────────────┘
         │
         ▼
  Upstream: release or block payment
```

---

## Transaction Model

See [transaction_model.md](transaction_model.md) for the full data model.

Key fields consumed by the screening engine:

| Field | Fiat | Crypto | Screening Use |
|-------|------|--------|---------------|
| `originator.full_name` | ✓ | optional | Primary name match |
| `originator.name_aliases` | ✓ | - | Alias expansion |
| `originator.account_number` | ✓ | - | Exact account match |
| `originator.wallet_address` | - | ✓ | OFAC wallet + graph |
| `originator.country_of_residence` | ✓ | - | Jurisdiction risk |
| `beneficiary.*` | ✓ | ✓ | Same as above |
| `amount` + `currency` | ✓ | ✓ | Anomaly detection |
| `countries_in_scope` | ✓ | - | Routing jurisdiction check |
| `tx_hash` | - | ✓ | On-chain graph traversal |

---

## Iteration Plan

### Iteration 0 — Baseline (already scoped)
**Goal:** Prove the concept. Run a list of transactions against blocked accounts. Flag exact name/account matches.

**What it does:**
- Download OFAC SDN list (XML), parse into a flat lookup table
- Accept a CSV or JSON batch of transactions
- For each transaction: check originator name, beneficiary name, account numbers against the table
- Return MATCH / NO MATCH per transaction

**What it deliberately does not do:**
- Fuzzy matching
- Real-time processing
- Crypto
- Explainability

**Stack:** Python, pandas or simple dict lookup

**Value:** Establishes data pipeline, list ingestion format, and output schema. Everything future iterations build on.

---

### Iteration 1 — Fuzzy Name Matching + API
**Goal:** Handle transliteration, spelling variants, aliases. Expose as a real API.

**Problem solved:**
> "Sergey Ivanov" and "Sergei Ivanoff" are the same person. Simple string comparison misses this. This is the most common reason real screening systems generate both false positives AND false negatives simultaneously.

**Approach — multi-layer matcher:**

```
Input name
    │
    ├─ Layer 1: Exact match (O(1) hash lookup)
    │           Hit → MATCH immediately
    │
    ├─ Layer 2: Phonetic normalization
    │           Soundex / Metaphone / Double Metaphone
    │           Catches: Sergei/Sergey, Gaddafi/Qaddafi
    │           Score > 0.95 → MATCH
    │
    ├─ Layer 3: Edit distance (Levenshtein / Jaro-Winkler)
    │           Catches: typos, character swaps
    │           Score > 0.90 → MATCH, 0.75-0.90 → REVIEW
    │
    └─ Layer 4: Embedding similarity (sentence-transformers)
               Embed both names, cosine similarity
               Handles multilingual transliteration
               Score > 0.85 → REVIEW, < 0.60 → NO MATCH
```

Each layer only runs if the previous layer didn't produce a high-confidence verdict. This keeps P99 latency low — most exact matches exit at Layer 1 in <1ms.

**Entity normalization before matching:**
- Strip legal suffixes: "Ltd", "LLC", "GmbH", "Inc", "S.A.", "Co."
- Normalize diacritics: "Müller" → "Muller"
- Expand abbreviations: "Intl" → "International"
- Latin transliteration of Cyrillic/Arabic: pre-compute for all entities in the list

**Embedding index:**
- Embed all 40,000+ OFAC SDN names + aliases at startup
- Store in FAISS or Milvus (Pavle's exact skill set)
- At query time: embed incoming name, top-K ANN search in <10ms

**API:**
```
POST /screen/fiat
{
  "originator_name": "Sergei Ivanoff",
  "originator_account": "GB29NWBK60161331926819",
  "beneficiary_name": "Muammar Kadaffi",
  "amount": 50000,
  "currency": "USD"
}

Response:
{
  "verdict": "REVIEW",
  "confidence": 0.84,
  "hits": [
    {
      "matched_entity": "MUAMMAR GADDAFI",
      "list": "OFAC_SDN",
      "match_type": "EMBEDDING",
      "similarity": 0.84,
      "match_field": "beneficiary_name"
    }
  ],
  "explanation": "Beneficiary name matches OFAC SDN entry 'MUAMMAR GADDAFI' with 84% embedding similarity. Flagged for analyst review.",
  "latency_ms": 47
}
```

**Stack:** Python, FastAPI, sentence-transformers, FAISS, PostgreSQL (audit log)

**Success metric:** False positive rate below 5% on a test set of common names (Kim, Mohammed, Wagner).

---

### Iteration 2 — Live List Ingestion + Hot Reload
**Goal:** Keep sanctions data current without downtime. Lists update daily — a system that needs a restart to update is a liability.

**Problem solved:**
> OFAC added a new SDN entry at 9am. Your system updated its list at 2am. A payment to that entity cleared at 10am. You just violated sanctions law.

**Approach:**

```
Scheduled Poller (every 6h, on OFAC change event if webhook available)
    │
    ▼
List Fetcher
    ├── OFAC SDN (XML) — https://ofac.treasury.gov/
    ├── EU Consolidated (XML)
    ├── UN Consolidated (XML)
    └── OFSI (UK) (CSV/XML)
    │
    ▼
Normalizer — parse raw XML/CSV into canonical SanctionedEntity records
    │
    ▼
Deduplicator — same person on 3 lists = one entry with 3 source tags
    │
    ▼
Embedder — compute embedding for every name + alias
    │
    ▼
Staging Index (new version)
    │
    ▼  atomic swap — in-memory pointer switch, zero downtime
Active Index (current version)
    │
    ▼
Changelog — what was added / removed / updated, for audit
```

**Hot reload without downtime:**
- Maintain two indexes: active and staging
- Build new index in the background while active index serves traffic
- Atomic pointer swap when staging is ready
- Old index kept alive until all in-flight requests complete

**Change notification:**
- Log every add/remove/update with timestamp
- Expose `GET /lists/changelog?since=2026-06-12` for compliance reporting
- Alert if a list hasn't refreshed in >24h (circuit breaker)

**Stack:** Python background scheduler (APScheduler), Redis for index state, atomic swap via Redis RENAME

---

### Iteration 3 — Behavioral Anomaly Detection
**Goal:** Flag suspicious patterns even when no name matches a sanctions list.

**Problem solved:**
> A company moves $500K. It's not on any list. But it normally moves $5K/month, and this wire goes to a counterparty it has never transacted with before. This is how money laundering actually looks — not as a match to a list, but as a behavioral anomaly.

**Two anomaly signals:**

**Signal A — Transaction amount anomaly:**
```python
# Per originator account, maintain rolling statistics
entity_stats = {
    "account_id": "...",
    "avg_amount_90d": 4800.00,
    "stddev_amount_90d": 1200.00,
    "max_single_90d": 12000.00,
    "tx_count_90d": 47
}

# Z-score for current transaction
z_score = (transaction.amount - avg) / stddev
# z > 3.0 → unusual, z > 5.0 → very unusual
anomaly_score = sigmoid(z_score)
```

**Signal B — Pass-through detection (layering):**
```python
# Money laundering pattern: $X in, $X±small% out, same timeframe
# Detect: same account receives N and sends ~N within 24h
inbound = sum(tx.amount for tx in account_txs if tx.direction == "IN" and tx.timestamp > now - 24h)
outbound = sum(tx.amount for tx in account_txs if tx.direction == "OUT" and tx.timestamp > now - 24h)

passthrough_ratio = min(inbound, outbound) / max(inbound, outbound)
# ratio > 0.85 and both > threshold → layering flag
```

**Integration with main pipeline:**
- Behavioral scores are computed in parallel with name matching
- Combined into the final risk score:
  ```
  final_score = 0.60 * name_match_score
              + 0.25 * behavioral_anomaly_score
              + 0.15 * jurisdiction_risk_score
  ```
- A transaction with no name match but extreme behavioral anomaly → REVIEW

**Stack:** PostgreSQL with sliding window queries + Redis for hot entity stats cache

---

### Iteration 4 — LLM Disambiguation Layer
**Goal:** Use an LLM to resolve the truly borderline REVIEW cases that rules and embeddings can't settle.

**Problem solved:**
> Embedding similarity says 0.78. Edit distance says 0.81. Is "Acme Trading International Ltd" the same as "Acme International Trading"? Rules can't tell. An LLM with the right context can.

**Approach — LLM as the final arbiter, not the first line:**

```python
# Only called for cases where 0.65 < score < 0.88 (the "grey zone")
def llm_disambiguate(candidate: str, sanctions_hit: SanctionedEntity, transaction: ScreeningRequest) -> LLMVerdict:
    prompt = f"""
You are a sanctions compliance analyst. Determine whether the following transaction
involves a person or entity that matches a sanctioned entity.

TRANSACTION PARTY: {candidate}
Country: {transaction.originator.country_of_residence}
Payment context: {transaction.amount} {transaction.currency} to {transaction.beneficiary.full_name}

POTENTIAL SANCTIONS MATCH:
Name: {sanctions_hit.primary_name}
Aliases: {', '.join(sanctions_hit.aliases[:10])}
DOB: {sanctions_hit.date_of_birth}
Nationalities: {', '.join(sanctions_hit.nationalities)}
Sanctions program: {', '.join(sanctions_hit.programs)}

Question: Is the transaction party the same person/entity as the sanctioned entity?
Answer MATCH, REVIEW, or NO_MATCH with a one-sentence justification.
    """
    
    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",  # Fast + cheap for high volume
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_verdict(response)
```

**Cost control:**
- LLM called only for grey-zone cases (estimated ~5% of total volume)
- Haiku model: fast (~200ms), cheap (~$0.00025/call)
- Cache LLM responses for identical inputs (Redis, 1h TTL)
- Rate limit and fallback: if LLM is slow, escalate to REVIEW rather than block

**Explainability output:**
- LLM response becomes the `explanation` field in the verdict
- Stored verbatim in audit log with model version + timestamp
- Regulators can read the reasoning in plain English

**Stack:** Claude API (Haiku), prompt caching for repeated entity patterns

---

### Iteration 5 — Crypto Graph Traversal
**Goal:** Screen cryptocurrency transactions beyond direct OFAC wallet list lookup.

**Problem solved:**
> Wallet A sends to Wallet B which sends to Wallet C which is on OFAC's list. Direct lookup of A finds nothing. Graph traversal with N-hop analysis catches this.

**Three-layer crypto screening:**

**Layer 1 — Direct OFAC wallet lookup (< 1ms):**
```python
# Igor's domain: bloom filter for O(1) sub-millisecond lookup
# OFAC publishes ~1500 sanctioned wallet addresses
# Bloom filter: false positive rate < 0.001%, no false negatives
bloom_filter = BloomFilter(capacity=100_000, error_rate=0.001)
for address in ofac_wallet_list:
    bloom_filter.add(address.lower())

def check_direct(wallet: str) -> bool:
    return wallet.lower() in bloom_filter
```

**Layer 2 — 1-hop exposure (direct counterparty check):**
```python
# Via public blockchain APIs (Etherscan, Blockstream, Solana RPC)
def check_one_hop(wallet: str, chain: str) -> list[str]:
    transactions = blockchain_api.get_transactions(wallet, limit=100)
    counterparties = {tx.from_address for tx in transactions} | {tx.to_address for tx in transactions}
    return [addr for addr in counterparties if check_direct(addr)]
```

**Layer 3 — N-hop graph traversal with risk decay:**
```python
# BFS up to N hops, score decays with distance
def graph_risk_score(wallet: str, max_hops: int = 3) -> float:
    visited = set()
    queue = deque([(wallet, 0, 1.0)])  # (address, hop, risk_weight)
    total_risk = 0.0
    
    while queue:
        addr, hop, weight = queue.popleft()
        if hop > max_hops or addr in visited:
            continue
        visited.add(addr)
        
        if check_direct(addr):
            total_risk += weight  # Full risk at direct match
            continue              # Don't traverse further from OFAC address
        
        if hop < max_hops:
            neighbors = blockchain_api.get_neighbors(addr)
            decay = 0.5  # Each hop halves the risk weight
            for neighbor in neighbors[:20]:  # Cap fan-out
                queue.append((neighbor, hop + 1, weight * decay))
    
    return min(total_risk, 1.0)
```

Risk decay by hop:
- Hop 0 (direct): 1.0 → MATCH
- Hop 1: 0.5 → REVIEW
- Hop 2: 0.25 → REVIEW (if > 0.2)
- Hop 3: 0.125 → NO MATCH (noise, not actionable)

**Unified fiat + crypto API:**
```
POST /screen          # Auto-detects type from payload
POST /screen/fiat     # Explicit fiat screening
POST /screen/crypto   # Explicit crypto screening
POST /screen/batch    # Batch screening (re-screening existing customers)
```

**Stack:** Python, public blockchain RPC endpoints (Etherscan API, Blockstream for BTC), Redis graph cache for recently-traversed addresses, bloom filter in memory (C extension for speed)

---

### Iteration 6 — Analyst Review Queue (Human-in-the-Loop UX)
**Goal:** Make the REVIEW queue workable at scale. A queue an analyst can't clear before 5pm is a liability.

**Problem solved:**
> 200 flagged transactions. 4pm Friday. Each one shows a name similarity score and nothing else. Analyst has to decide in 2 minutes per case or go into overtime. Current tooling gives no context. Wrong decisions have regulatory consequences.

**Review queue interface features:**

```
┌─────────────────────────────────────────────────────────────────┐
│  REVIEW QUEUE                        47 pending | SLA: 4h       │
├─────────────────────────────────────────────────────────────────┤
│  [HIGH] $230,000 USD → "Muammar Kadaffi", Egypt    [12:04pm]   │
│         ⚠ 84% match: MUAMMAR GADDAFI (OFAC SDN, IRAN program)  │
│         Evidence: name embedding 0.84, same country             │
│         [BLOCK PAYMENT] [RELEASE] [ESCALATE]                    │
├─────────────────────────────────────────────────────────────────┤
│  [MED] $1,200 USD → "Mohammed Al-Rashid", UAE      [12:31pm]   │
│        ⚠ 71% match: MOHAMMED AL-RASHID (UN list)               │
│        Evidence: name phonetic 0.71, DOB mismatch              │
│        AI Summary: "Common name match. UN entity DOB 1965;      │
│        account holder DOB 1989. Low probability of match."      │
│        [BLOCK PAYMENT] [RELEASE] [ESCALATE]                     │
└─────────────────────────────────────────────────────────────────┘
```

**Per-case information shown:**
1. Matched entity full profile (from sanctions list)
2. Similarity breakdown by layer (exact / phonetic / embedding / LLM)
3. LLM-generated natural language summary (why flagged, what doesn't fit)
4. Transaction context (amount, purpose, history with this counterparty)
5. Behavioral signals (is this amount unusual for this account?)
6. One-click actions with mandatory reason field

**Audit trail per decision:**
```python
@dataclass
class AnalystDecision:
    review_case_id: str
    analyst_id: str
    decision: str           # "BLOCKED" | "RELEASED" | "ESCALATED"
    reason: str             # Free text, mandatory
    decided_at: datetime
    time_to_decide_s: int   # How long analyst spent on this case
    # Feeds back into scoring model
    was_correct: bool | None  # Set later if regulatory outcome known
```

**Stack:** React (Pavle), FastAPI, PostgreSQL, Server-Sent Events for real-time queue updates

---

### Iteration 7 — Explainability & Audit Trail
**Goal:** Produce an explanation a compliance officer can defend to a regulator two years later.

**Problem solved:**
> OFAC fines include cases where the institution screened but could not prove it. "We checked" is not enough. "Here is the exact decision, the data used, the version of the list, and the reasoning" is.

**Immutable decision record:**
```python
@dataclass
class AuditRecord:
    decision_id: str                    # UUID, immutable
    transaction_id: str
    verdict: str
    confidence: float

    # Snapshot of inputs at decision time
    transaction_snapshot: dict          # Full transaction as received
    entity_snapshot: dict | None        # Matched entity record from list

    # Snapshot of system state at decision time
    list_versions: dict[str, str]       # {"OFAC_SDN": "2026-06-12-v3", ...}
    engine_version: str                 # Git SHA of screening code
    model_version: str                  # Embedding model version

    # Decision chain
    layers_executed: list[LayerResult]  # Each matching layer's output
    llm_prompt: str | None
    llm_response: str | None

    # Final disposition
    analyst_decision: AnalystDecision | None
    downstream_action: str              # "BLOCKED" | "RELEASED" | "PENDING"
    action_taken_at: datetime

    # Timestamps
    screened_at: datetime
    record_hash: str                    # SHA-256 of record for tamper detection
```

Records are append-only. No update, no delete. Query via:
```
GET /audit/{transaction_id}
GET /audit/range?from=2024-01-01&to=2024-12-31
GET /audit/entity/{entity_name}
```

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| API layer | FastAPI (Python) | Team's primary stack; async; fast |
| Embedding index | FAISS (in-process) or Milvus | Pavle's production experience |
| Embedding model | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | Multilingual, handles Cyrillic/Arabic/Chinese |
| Phonetic matching | `jellyfish` (Jaro-Winkler, Soundex, Metaphone) | Python, well-tested |
| Behavioral store | PostgreSQL + Redis | Durable stats + hot cache |
| Bloom filter | `pybloom-live` or C extension | Igor: can do this in memory with minimal deps |
| Blockchain APIs | Etherscan, Blockstream, Solana RPC | Free tier sufficient for hackathon |
| LLM | Claude API (Haiku model) | Fast, cheap, explainable output |
| Review queue | React + SSE | Pavle's strongest frontend skill |
| Audit store | PostgreSQL (append-only table) | Simple, durable, queryable |
| List ingestion | Python scheduler + lxml | OFAC/EU/UN are XML; lxml is fast |

---

## Latency Budget

Target: P99 < 500ms end-to-end for fiat transactions under load.

| Layer | Expected P50 | Expected P99 | Notes |
|-------|-------------|-------------|-------|
| Exact match | < 1ms | < 2ms | Hash lookup |
| Phonetic + edit distance | 2ms | 5ms | CPU-bound |
| Embedding ANN search | 5ms | 15ms | FAISS in-process |
| LLM (only ~5% of cases) | 200ms | 400ms | Haiku model |
| Behavioral check (parallel) | 3ms | 10ms | Redis lookup |
| Crypto hop-1 check | 50ms | 150ms | External API |
| Crypto N-hop traversal | 500ms | 2000ms | Only on REVIEW path |
| **Total (no LLM path)** | **~10ms** | **~30ms** | **Typical case** |
| **Total (LLM path)** | **~210ms** | **~420ms** | **Grey-zone case** |

---

## What We Are Not Building

To keep scope achievable in 40 hours and focus on the most innovative parts:

- PEP (politically exposed persons) lists — same matching problem, different data source, add in post-hackathon
- Adverse media classifier — requires news API + NLP pipeline; a future iteration
- Beneficial ownership graph — corporate registry data is complex; future iteration
- Full shell company mapping — requires commercial corporate registry data
- SEPA / ACH-specific field parsing — normalize everything to canonical model at intake

---

## Risk & Mitigations

| Risk | Mitigation |
|------|-----------|
| Embedding model too slow for P99 target | Use quantized model (int8); FAISS is sub-10ms at 40K vectors |
| Blockchain API rate limits | Cache recent lookups in Redis; fail open (REVIEW) if rate-limited |
| OFAC XML format changes | Schema validation on ingest; alert on parse error |
| LLM latency spike | Hard timeout at 300ms; fall back to REVIEW on timeout |
| False positive on common names | Tune thresholds on test set of "Mohammed", "Kim", "Wagner" before demo |
| List update causes downtime | Staging/active dual-index pattern with atomic swap |
