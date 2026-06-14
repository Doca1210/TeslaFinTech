# Veritas Screening Pitch Knowledge Base

## Core Pitch

Veritas Screening is not just a sanctions matcher. It is an explainable payment-compliance decision flow for cross-border fintechs.

It combines watchlist screening, behavioral AML signals, beneficial-ownership risk, and human analyst review into one workflow.

Strongest pitch line:

> We help payment companies decide whether a transfer should pass, be blocked, or go to human review by combining identity risk, transaction behavior, ownership exposure, and analyst-ready evidence in one explainable flow.

## Mandatory Feature Status

| Feature | Status | Notes |
|---|---:|---|
| End-to-end payment decision flow | Mostly done | Exposed as the `/transactions` demo feed, not yet as a generic `POST /screen/payment` endpoint. |
| Sokin-specific AML rules | Done | Includes amount-vs-baseline, pass-through in/out, geo initiation mismatch, and Verification-of-Payee-style name mismatch. |
| KYB / ownership graph | Done | A beneficiary can be clean by name but risky through an owner, UBO, PEP, or sanctioned party. |
| Evidence pack / explainability | Mostly done | Evidence is embedded in transaction cards, rule hits, ownership paths, graph payloads, and explanations. There is no standalone `/cases/{id}/evidence` endpoint yet. |
| Analyst workflow | Partially done | Frontend review queue, AI suggestion, evidence attachment, and manual verdict form exist. Review state is frontend-local, not fully persisted as backend case management. |

## System Mental Model

### Layer A: Watchlist Screening

Screens both originator and beneficiary against sanctions and PEP data.

Key points:

- Uses normalization, fuzzy matching, alias handling, and semantic/vector fallback.
- Handles transliteration, reordered tokens, aliases, and common-name false positives.
- High-confidence sanctions hits become `MATCH`.
- PEP hits usually become `REVIEW`, not automatic block.

Mentor answer:

> This layer answers: are the parties themselves risky according to sanctions or PEP lists?

### Layer B: Behavioral AML

Looks at transaction behavior, not just names.

Implemented signals include:

- Large amount.
- Velocity burst.
- Structuring or repeated sub-threshold transfers.
- High-risk jurisdiction.
- Dormant account reactivation.
- Amount versus account baseline.
- Pass-through money in / money out.
- Payment initiated from an unusual or high-risk country.
- Beneficiary name versus account-name mismatch.

Mentor answer:

> This layer answers: even if the names are clean, does the payment behavior look suspicious for this customer?

### Layer C: Ownership / KYB Graph

Traces who owns or controls the beneficiary.

Key points:

- Walks ownership/control links up to a configurable depth.
- Computes effective ownership across chains.
- Treats ownership above 25 percent as UBO-relevant.
- Can use seeded KYB risk or live re-screening of owners against the watchlist.
- Supports reverse exposure: given a risky party, show which companies they stand behind.

Mentor answer:

> This layer catches the shell-company problem: a company can look clean directly, but still be controlled by a sanctioned or politically exposed person.

### Verdict Composer

Combines the strongest result across all layers.

Verdicts:

- `MATCH` -> `BLOCK`
- `REVIEW` -> `MANUAL_REVIEW`
- `NO_MATCH` -> `PASS`

The composer preserves the triggered layers and explanation, so analysts can see why the final action happened.

### Analyst Review Tool

The frontend shows:

- Transaction history.
- Review queue.
- Watchlist screening evidence.
- Behavioral rule hits.
- Ownership graph and risky paths.
- AI-generated suggestion.
- Manual analyst verdict form.
- Supporting evidence attachment.

Important framing:

> The AI does not make the final compliance decision. It gives a suggestion, and the analyst records their own verdict.

## Competition Positioning

The assessment identifies these main competitors:

- ComplyAdvantage
- HAWK
- Flagright
- Napier AI
- Unit21
- Feedzai
- Salv
- Neterium

Do not pitch against them as "we built better name matching." That is a crowded and mature category.

Better positioning:

- More payment-specific than generic AML platforms.
- More explainable than black-box scoring.
- Stronger KYB/ownership story than simple transaction monitoring.
- Built for human-in-the-loop review, not just automated alerts.
- Lightweight and fast to integrate compared with enterprise AML suites.

Competitive wedge:

> Existing vendors are broad AML platforms. Our hackathon wedge is a focused cross-border payment decisioning copilot that combines identity, behavior, ownership, and analyst evidence in one review-ready flow.

## Best Demo Story

Use labels, not transaction IDs, because cached demo IDs may change.

Recommended flow:

1. Clean payment passes.
2. Direct sanctions match blocks.
3. Clean names but suspicious behavior routes to review.
4. Clean beneficiary but sanctioned or PEP owner triggers review/block through KYB graph.
5. Analyst opens the review tool, reads evidence and AI suggestion, attaches support, and records a verdict.

This proves the system understands real evasion patterns, not only string matching.

## Mentor Q&A Cheatsheet

### Why not just use a sanctions API?

Because the real operational problem is not only matching a name. It is deciding whether a payment should move, with enough evidence for an analyst or regulator. We combine name screening, behavior, ownership, and review workflow.

### Where is AI used?

AI assists the analyst by summarizing the evidence and suggesting a verdict. The deterministic layers still produce the core evidence and audit trail, and the human analyst makes the final decision.

### What is your biggest limitation?

The demo uses curated payment and ownership fixtures, and the analyst workflow is not fully backend-persisted yet. The next production step would be a generic `POST /screen/payment` endpoint plus persistent case management, authentication, RBAC, and audit-grade review state.

### What makes this relevant to Sokin?

The Sokin mentor notes highlighted real-time suspicious transaction detection, account behavior monitoring, money-in/money-out patterns, location anomalies, source of funds, KYB ownership, and human review. The system maps directly to those points through behavioral rules, ownership tracing, and analyst workflow.

### How do you reduce false positives?

We do not block on weak signals alone. The system separates `MATCH`, `REVIEW`, and `NO_MATCH`; applies PEP-aware verdicting; uses confidence thresholds; and routes ambiguous cases to human review with evidence instead of blindly blocking.

### How do you handle shell companies?

The ownership graph traces related parties behind a beneficiary. If a clean company is owned or controlled by a sanctioned person, PEP, or risky entity, the final verdict can escalate even when direct name screening is clean.

### Why is this explainable?

Each layer returns structured evidence: matched names and source lists, behavioral rule hits, ownership paths, risk scores, and natural-language explanations. The frontend exposes that evidence to the analyst.

### Is this production-ready?

It is a credible hackathon prototype and pilot foundation, not a finished production compliance platform. Production work would include persistent case APIs, auth/RBAC, stronger data governance, latency benchmarking, scheduled list refresh, and integration with payment rails or case-management systems.

## What To Say And What Not To Say

Say:

- "Explainable payment decisioning."
- "Human-in-the-loop compliance."
- "Identity, behavior, and ownership risk in one flow."
- "A clean beneficiary can still be risky through ownership."
- "AI assists the analyst, but does not replace the analyst."

Avoid:

- "We are just a better sanctions matcher."
- "The AI decides whether to block payments."
- "This is fully production-ready."
- "We ingest all global ownership registries."
- "Crypto tracing is fully implemented."

## Current Implementation Notes

Backend anchors:

- `backend/app/main.py` - FastAPI routes for transactions, ownership screening, exposure lookup, ingestion, export, and AI suggestion.
- `backend/app/aml_detect.py` - behavioral AML rules.
- `backend/app/ownership.py` - KYB and beneficial-ownership graph risk engine.
- `backend/screening_v2/composer.py` - combines sanctions, behavioral, and ownership signals.
- `backend/app/payment_demo.py` - demo transaction scenarios.
- `backend/app/suggest.py` - LLM suggestion for review cases.

Frontend anchors:

- `frontend/src/App.jsx` - workspace, review queue, AI suggestion, verdict form.
- `frontend/src/TransactionCard.jsx` - evidence display for each transaction.
- `frontend/src/OwnershipExplorer.jsx` - KYB ownership tracing UI.
- `frontend/src/OwnershipGraph.jsx` - visual ownership graph.

## Verification Notes

Focused backend tests were run for behavioral and ownership internals:

```text
pytest -q tests/test_aml_detect_v2.py tests/test_ownership.py -k 'not endpoint'
38 passed, 2 deselected
```

Endpoint tests that import `app.main` failed in the current local environment because `google-genai` was missing from the active Python environment. The project requirement exists in `backend/requirements.txt`.

