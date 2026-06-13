# Graph Report - TeslaFinTech  (2026-06-13)

## Corpus Check
- 46 files · ~29,653 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 178 nodes · 163 edges · 18 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b89f0db2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]

## God Nodes (most connected - your core abstractions)
1. `AE890330000010123456789` - 20 edges
2. `RS35260005601001611379` - 17 edges
3. `SA0380000000608010167519` - 16 edges
4. `RS35260005601001611380` - 16 edges
5. `Sanctions Screening Engine — Design Document` - 10 edges
6. `Sanctions Screening — All Possible Options (40h Hackathon)` - 10 edges
7. `Sanctions Screening Engine — Design Document` - 10 edges
8. `Iteration Plan` - 9 edges
9. `Iteration Plan` - 9 edges
10. `Transaction Model — Sanctions Screening` - 7 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (18 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (20): AE890330000010123456789, account_id, avg_amount, holder_name, inbound_24h, max_single, min_amount, new_counterparty (+12 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (18): Architecture Overview, Core Innovation Thesis, Iteration 0 — Baseline (already scoped), Iteration 1 — Fuzzy Name Matching + API, Iteration 2 — Live List Ingestion + Hot Reload, Iteration 3 — Behavioral Anomaly Detection, Iteration 4 — LLM Disambiguation Layer, Iteration 5 — Crypto Graph Traversal (+10 more)

### Community 2 - "Community 2"
Cohesion: 0.22
Nodes (8): Sanctions Screening — User Landscape, Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, What the VP Can and Cannot Tell You, Who Actually Uses a Sanctions Screening System

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (18): Architecture Overview, Core Innovation Thesis, Iteration 0 — Baseline (already scoped), Iteration 1 — Fuzzy Name Matching + API, Iteration 2 — Live List Ingestion + Hot Reload, Iteration 3 — Behavioral Anomaly Detection, Iteration 4 — LLM Disambiguation Layer, Iteration 5 — Crypto Graph Traversal (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.50
Nodes (3): Detekcija, Ostalo, Review

### Community 5 - "Community 5"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (17): _comment, RS35260005601001611380, account_id, avg_amount, holder_name, max_single, min_amount, note (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (7): Crypto Transaction, Fiat Transaction, Key Observations for Screening Design, Screening Request, Screening Verdict, Transaction Model — Sanctions Screening, What Regulatory Lists Publish (Entity Schema)

### Community 8 - "Community 8"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (8): AML Workflow & Compliance, Business Model & Market Context, Detection & Screening, Emerging Markets & Crypto, KYB & Counterparty Risk, Product Strategy, Sokin Partner Context, Technical Architecture

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (17): RS35260005601001611379, account_id, avg_amount, holder_name, last_unusual_tx, max_single, min_amount, note (+9 more)

### Community 11 - "Community 11"
Cohesion: 0.12
Nodes (16): SA0380000000608010167519, account_id, avg_amount, holder_name, max_single, min_amount, note, profile_window_days (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (10): Crypto Screening, Data Infrastructure, Extended Risk Signals, Feasibility Matrix, Hardest / Most Impressive (High Risk), Product Wrappers, Sanctions Screening — All Possible Options (40h Hackathon), Team Skill Map (+2 more)

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (8): Sanctions Screening — User Landscape, Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, What the VP Can and Cannot Tell You, Who Actually Uses a Sanctions Screening System

### Community 14 - "Community 14"
Cohesion: 0.25
Nodes (7): Crypto Transaction, Fiat Transaction, Key Observations for Screening Design, Screening Request, Screening Verdict, Transaction Model — Sanctions Screening, What Regulatory Lists Publish (Entity Schema)

## Knowledge Gaps
- **144 isolated node(s):** `_comment`, `account_id`, `holder_name`, `profile_window_days`, `tx_count` (+139 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AE890330000010123456789` connect `Community 0` to `Community 6`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `RS35260005601001611379` connect `Community 10` to `Community 6`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `SA0380000000608010167519` connect `Community 11` to `Community 6`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **What connects `_comment`, `account_id`, `holder_name` to the rest of the system?**
  _144 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._