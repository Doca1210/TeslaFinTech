# Graph Report - TeslaFinTech  (2026-06-13)

## Corpus Check
- 51 files · ~27,944 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 445 nodes · 888 edges · 33 communities (28 shown, 5 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 168 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d8db2675`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 39|Community 39]]

## God Nodes (most connected - your core abstractions)
1. `ScreeningEngine` - 41 edges
2. `NameMatcher` - 33 edges
3. `ABTestPipeline` - 21 edges
4. `Transaction` - 21 edges
5. `BenchmarkCase` - 20 edges
6. `AlgorithmVariant` - 18 edges
7. `Base` - 17 edges
8. `VerdictMetrics` - 13 edges
9. `Transaction` - 13 edges
10. `CasePrediction` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Namespace` --uses--> `ABTestPipeline`  [INFERRED]
  evaluate.py → backend/screening/evaluation/pipeline.py
- `Path` --uses--> `ABTestPipeline`  [INFERRED]
  tests/test_evaluation.py → backend/screening/evaluation/pipeline.py
- `Path` --uses--> `ScreeningEngine`  [INFERRED]
  app.py → backend/screening/engine.py
- `ScreeningEngine` --uses--> `ScreeningEngine`  [INFERRED]
  app.py → backend/screening/engine.py
- `Transaction` --uses--> `ScreeningEngine`  [INFERRED]
  cli.py → backend/screening/engine.py

## Import Cycles
- 1-file cycle: `backend/app/models.py -> backend/app/models.py`
- 1-file cycle: `backend/screening_api.py -> backend/screening_api.py`

## Communities (33 total, 5 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (18): Architecture Overview, Core Innovation Thesis, Iteration 0 — Baseline (already scoped), Iteration 1 — Fuzzy Name Matching + API, Iteration 2 — Live List Ingestion + Hot Reload, Iteration 3 — Behavioral Anomaly Detection, Iteration 4 — LLM Disambiguation Layer, Iteration 5 — Crypto Graph Traversal (+10 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (40): Base, get_session(), ingest_ofac_sdn(), log_requests(), Placeholder substring search until the fuzzy/embedding matcher exists., search_entities(), Entity, EntityAddress (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.13
Nodes (35): ScreeningResult, ScreeningVerdict, Transaction, WatchlistEntity, Transaction, ScreeningEngine, WatchlistEntity, WatchlistEntity (+27 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (31): AlgorithmVariant, BenchmarkCase, Path, Path, WatchlistEntity, Path, BaseModel, BenchmarkCase (+23 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (47): build_engine(), lifespan(), Path, ScreeningEngine, ScreeningResult, Transaction, screen_batch(), screen_transaction() (+39 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (23): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (22): 1. HACKATHON CONTEXT, 2. TEAM CV CONTEXT (full detail), 3. APPLICATION QUESTIONS & FINAL ANSWERS (exact submitted text), 4. STYLE / VOICE CONVENTIONS, 5. OBJECTIVE ASSESSMENT GIVEN TO THE TEAM, 6. LIKELY NEXT STEPS (if continuing), Collaboration history (for "have you worked together"), Context: Garaža FinTech AI Hackathon Application (Detailed) (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (8): AML Workflow & Compliance, Business Model & Market Context, Detection & Screening, Emerging Markets & Crypto, KYB & Counterparty Risk, Product Strategy, Sokin Partner Context, Technical Architecture

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (10): Crypto Screening, Data Infrastructure, Extended Risk Signals, Feasibility Matrix, Hardest / Most Impressive (High Risk), Product Wrappers, Sanctions Screening — All Possible Options (40h Hackathon), Team Skill Map (+2 more)

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (8): Sanctions Screening — User Landscape, Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, What the VP Can and Cannot Tell You, Who Actually Uses a Sanctions Screening System

### Community 14 - "Community 14"
Cohesion: 0.25
Nodes (7): Crypto Transaction, Fiat Transaction, Key Observations for Screening Design, Screening Request, Screening Verdict, Transaction Model — Sanctions Screening, What Regulatory Lists Publish (Entity Schema)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (32): main(), parse_args(), print_failures(), print_summary(), Namespace, ScreeningVerdict, ClassificationMetrics, main() (+24 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (14): API, Benchmark format, Built-in variants, CLI, Evaluation & A/B testing, Features, Hackathon context, Metrics reported (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (10): enabledPlugins, claude-mem@thedotmack, context7@claude-plugins-official, extraKnownMarketplaces, thedotmack, hooks, PreToolUse, repo (+2 more)

### Community 21 - "Community 21"
Cohesion: 0.20
Nodes (9): 1. Data sources, 2. Data model, 3. Ingestion pipeline (this slice), 4. Stack, A. Official Treasury SDN/Consolidated data feeds (primary, free, no key), B. docs.ofac-api.com (secondary, optional, requires API key), Data Model & OFAC Ingestion — Design, Out of scope for this slice (future tables, not built now) (+1 more)

### Community 22 - "Community 22"
Cohesion: 0.20
Nodes (9): **Bonus: crypto**, **Go deeper on the data**, **Talk to people**, **The mess underneath**, **The other cost**, **Think about the full system**, **What you're solving**, **Where to be creative** (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.25
Nodes (7): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 24 - "Community 24"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 25 - "Community 25"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 26 - "Community 26"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 27 - "Community 27"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 39 - "Community 39"
Cohesion: 0.22
Nodes (10): WatchlistEntity, MatchSignal, WatchlistEntity, MatchSignal, initials(), is_common_name(), normalize_text(), Lowercase, strip accents, and remove punctuation for comparison. (+2 more)

## Knowledge Gaps
- **142 isolated node(s):** `Session`, `WatchlistEntity`, `ScreeningEngine`, `WatchlistEntity`, `context7@claude-plugins-official` (+137 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScreeningEngine` connect `Community 3` to `Community 4`, `Community 5`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `datetime` connect `Community 2` to `Community 5`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `NameMatcher` connect `Community 3` to `Community 4`, `Community 5`, `Community 39`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `ScreeningEngine` (e.g. with `Path` and `ScreeningEngine`) actually correct?**
  _`ScreeningEngine` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `NameMatcher` (e.g. with `ScreeningResult` and `ScreeningVerdict`) actually correct?**
  _`NameMatcher` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `ABTestPipeline` (e.g. with `Namespace` and `Path`) actually correct?**
  _`ABTestPipeline` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Transaction` (e.g. with `Namespace` and `Path`) actually correct?**
  _`Transaction` has 19 INFERRED edges - model-reasoned connections that need verification._