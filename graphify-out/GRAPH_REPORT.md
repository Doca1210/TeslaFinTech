# Graph Report - TeslaFinTech  (2026-06-13)

## Corpus Check
- 20 files · ~16,254 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 30 nodes · 26 edges · 6 communities (5 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a07a9a1c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]

## God Nodes (most connected - your core abstractions)
1. `Questions — In Priority Order` - 7 edges
2. `Mentor Questions — Sokin VP of Engineering` - 6 edges
3. `Who Actually Uses a Sanctions Screening System` - 6 edges
4. `Iteracija 1` - 3 edges
5. `Sanctions Screening — User Landscape` - 3 edges
6. `Taskovi` - 1 edges
7. `Tech Stack` - 1 edges
8. `Detekcija` - 1 edges
9. `Review` - 1 edges
10. `Ostalo` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (6 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.29
Nodes (7): Block 1: Find the Pain (Most Important), Block 2: Understand the Crypto Gap, Block 3: Understand Operational Pain, Block 4: Understand Regulatory/Explainability Requirements, Block 5: Find the Dream Feature, Closing Ask (Important), Questions — In Priority Order

### Community 1 - "Community 1"
Cohesion: 0.33
Nodes (5): How to Open, Mentor Questions — Sokin VP of Engineering, The Decision This Conversation Must Answer, The Single Most Valuable Thing to Get, What You Should Know When You Walk Out

### Community 2 - "Community 2"
Cohesion: 0.33
Nodes (6): Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, Who Actually Uses a Sanctions Screening System

### Community 4 - "Community 4"
Cohesion: 0.50
Nodes (3): Detekcija, Ostalo, Review

### Community 5 - "Community 5"
Cohesion: 0.50
Nodes (3): Iteracija 1, Taskovi, Tech Stack

## Knowledge Gaps
- **21 isolated node(s):** `Taskovi`, `Tech Stack`, `Detekcija`, `Review`, `Ostalo` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Questions — In Priority Order` connect `Community 0` to `Community 1`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `Mentor Questions — Sokin VP of Engineering` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `Who Actually Uses a Sanctions Screening System` connect `Community 2` to `Community 3`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **What connects `Taskovi`, `Tech Stack`, `Detekcija` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._