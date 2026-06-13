# Graph Report - TeslaFinTech  (2026-06-13)

## Corpus Check
- 23 files · ~20,537 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 65 nodes · 57 edges · 10 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ee1ce9d6`
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

## God Nodes (most connected - your core abstractions)
1. `Sanctions Screening Engine — Design Document` - 10 edges
2. `Iteration Plan` - 9 edges
3. `Transaction Model — Sanctions Screening` - 7 edges
4. `Questions — In Priority Order` - 7 edges
5. `Mentor Questions — Sokin VP of Engineering` - 6 edges
6. `Who Actually Uses a Sanctions Screening System` - 6 edges
7. `Iteracija 1` - 3 edges
8. `Iteracija 1` - 3 edges
9. `Sanctions Screening — User Landscape` - 3 edges
10. `Problem Statement` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (10 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.29
Nodes (7): Block 1: Find the Pain (Most Important), Block 2: Understand the Crypto Gap, Block 3: Understand Operational Pain, Block 4: Understand Regulatory/Explainability Requirements, Block 5: Find the Dream Feature, Closing Ask (Important), Questions — In Priority Order

### Community 1 - "Community 1"
Cohesion: 0.33
Nodes (5): How to Open, Mentor Questions — Sokin VP of Engineering, The Decision This Conversation Must Answer, The Single Most Valuable Thing to Get, What You Should Know When You Walk Out

### Community 2 - "Community 2"
Cohesion: 0.22
Nodes (8): Sanctions Screening — User Landscape, Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, What the VP Can and Cannot Tell You, Who Actually Uses a Sanctions Screening System

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (9): Architecture Overview, Core Innovation Thesis, Latency Budget, Problem Statement, Risk & Mitigations, Sanctions Screening Engine — Design Document, Technology Stack, Transaction Model (+1 more)

### Community 4 - "Community 4"
Cohesion: 0.50
Nodes (3): Detekcija, Ostalo, Review

### Community 5 - "Community 5"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (9): Iteration 0 — Baseline (already scoped), Iteration 1 — Fuzzy Name Matching + API, Iteration 2 — Live List Ingestion + Hot Reload, Iteration 3 — Behavioral Anomaly Detection, Iteration 4 — LLM Disambiguation Layer, Iteration 5 — Crypto Graph Traversal, Iteration 6 — Analyst Review Queue (Human-in-the-Loop UX), Iteration 7 — Explainability & Audit Trail (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (7): Crypto Transaction, Fiat Transaction, Key Observations for Screening Design, Screening Request, Screening Verdict, Transaction Model — Sanctions Screening, What Regulatory Lists Publish (Entity Schema)

### Community 8 - "Community 8"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

### Community 9 - "Community 9"
Cohesion: 0.50
Nodes (3): Detekcija, Ostalo, Review

## Knowledge Gaps
- **48 isolated node(s):** `Problem Statement`, `Core Innovation Thesis`, `Architecture Overview`, `Transaction Model`, `Iteration 0 — Baseline (already scoped)` (+43 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Sanctions Screening Engine — Design Document` connect `Community 3` to `Community 6`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `Iteration Plan` connect `Community 6` to `Community 3`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `Questions — In Priority Order` connect `Community 0` to `Community 1`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **What connects `Problem Statement`, `Core Innovation Thesis`, `Architecture Overview` to the rest of the system?**
  _48 weakly-connected nodes found - possible documentation gaps or missing edges._