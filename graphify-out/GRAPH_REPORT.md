# Graph Report - TeslaFinTech  (2026-06-13)

## Corpus Check
- 18 files · ~16,010 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 22 nodes · 20 edges · 4 communities (3 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `555953e9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]

## God Nodes (most connected - your core abstractions)
1. `Questions — In Priority Order` - 7 edges
2. `Mentor Questions — Sokin VP of Engineering` - 6 edges
3. `Who Actually Uses a Sanctions Screening System` - 6 edges
4. `Sanctions Screening — User Landscape` - 3 edges
5. `The Decision This Conversation Must Answer` - 1 edges
6. `How to Open` - 1 edges
7. `Block 1: Find the Pain (Most Important)` - 1 edges
8. `Block 2: Understand the Crypto Gap` - 1 edges
9. `Block 3: Understand Operational Pain` - 1 edges
10. `Block 4: Understand Regulatory/Explainability Requirements` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (4 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.29
Nodes (7): Block 1: Find the Pain (Most Important), Block 2: Understand the Crypto Gap, Block 3: Understand Operational Pain, Block 4: Understand Regulatory/Explainability Requirements, Block 5: Find the Dream Feature, Closing Ask (Important), Questions — In Priority Order

### Community 1 - "Community 1"
Cohesion: 0.33
Nodes (5): How to Open, Mentor Questions — Sokin VP of Engineering, The Decision This Conversation Must Answer, The Single Most Valuable Thing to Get, What You Should Know When You Walk Out

### Community 2 - "Community 2"
Cohesion: 0.33
Nodes (6): Type 1: AML Analyst, Type 2: Compliance Officer, Type 3: Fintech Engineer (the Sokin VP), Type 4: Payment Operations / Customer Service, Type 5: Crypto Compliance Specialist, Who Actually Uses a Sanctions Screening System

## Knowledge Gaps
- **16 isolated node(s):** `The Decision This Conversation Must Answer`, `How to Open`, `Block 1: Find the Pain (Most Important)`, `Block 2: Understand the Crypto Gap`, `Block 3: Understand Operational Pain` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Questions — In Priority Order` connect `Community 0` to `Community 1`?**
  _High betweenness centrality (0.243) - this node is a cross-community bridge._
- **Why does `Mentor Questions — Sokin VP of Engineering` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.214) - this node is a cross-community bridge._
- **Why does `Who Actually Uses a Sanctions Screening System` connect `Community 2` to `Community 3`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **What connects `The Decision This Conversation Must Answer`, `How to Open`, `Block 1: Find the Pain (Most Important)` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._