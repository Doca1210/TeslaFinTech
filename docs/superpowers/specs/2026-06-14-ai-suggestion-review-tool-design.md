# AI Suggestion for Review Tool — Design Spec

**Date:** 2026-06-14
**Status:** Approved

## Overview

When a compliance analyst opens a flagged transaction in the Review Tool, the UI automatically fetches an AI-generated verdict suggestion and displays it above the verdict form. The analyst reads the AI opinion, then independently records their own verdict. The AI never pre-fills or overrides the form.

---

## Backend

### New module: `backend/app/suggest.py`

Single async function:

```python
async def get_ai_suggestion(tx_data: dict) -> dict:
    # Returns {"verdict": "BLOCK"|"RELEASE"|"ESCALATE", "reasoning": "..."}
```

Responsibilities:
- Build a structured prompt from the transaction data
- Call OpenAI chat completions API (model: `gpt-4o-mini`)
- Parse and return the JSON response
- Raise an exception on failure (caller handles HTTP error)

**Prompt design:**

System message: establishes the AI as a compliance analyst assistant reviewing flagged payment transactions.

User message: structured plain-text summary including:
- Originator name, beneficiary name, amount + currency, counterparty country
- Layer A — sanctions screening results: originator verdict + matched entity (if any), beneficiary verdict + matched entity (if any)
- Layer B — behavioral AML: total score, outcome, each rule fired (rule_id, severity, score, reason)
- Verdict Composer: triggered layers, confidence score, existing system explanation
- Instruction to respond as JSON: `{ "verdict": "BLOCK"|"RELEASE"|"ESCALATE", "reasoning": "<1-3 sentence plain-text rationale>" }`

### New endpoint: `POST /transactions/{tx_id}/suggest`

Added to `backend/app/main.py`.

- Looks up transaction by integer `tx_id` from `_transactions_cache` (the same in-memory list used by `GET /transactions`) — no DB query needed
- Calls `get_ai_suggestion(tx_data)`
- Returns `{ "verdict": "...", "reasoning": "..." }` on success
- Returns HTTP 404 if transaction not found in cache
- Returns HTTP 502 with `{ "detail": "AI suggestion unavailable" }` if OpenAI call fails

### Environment

New file: `backend/.env` (gitignored)

```
OPENAI_API_KEY=your_key_here
```

Read via `python-dotenv`. If not already a dependency, add `python-dotenv` and `openai` to `backend/requirements.txt`.

---

## Frontend

### New component: `AISuggestion`

Lives in `frontend/src/App.jsx` alongside existing components.

```jsx
function AISuggestion({ tx }) { ... }
```

**State shape:**
```js
{ status: 'loading' | 'ready' | 'error', verdict: null | string, reasoning: null | string }
```

**Behaviour:**
- `useEffect` triggers on `tx.id` change → fetches `POST /transactions/{tx.id}/suggest`
- Resets to `loading` state on each new transaction selection
- On success: sets `ready` with verdict + reasoning
- On failure: sets `error`

**Rendering:**

| State | UI |
|---|---|
| `loading` | Pulsing placeholder card: "AI is analyzing this transaction…" |
| `ready` | Card with "AI Suggestion" header, verdict badge (reuses existing badge color scheme: BLOCK=red, RELEASE=green, ESCALATE=amber), reasoning paragraph |
| `error` | Dimmed card: "AI suggestion unavailable" |

**Placement:** Rendered in the `review-detail` column, between `TransactionCard` and `ReviewVerdictForm`.

**No form interaction:** The component is read-only. It does not pre-fill the reasoning textarea or select a verdict radio button.

---

## Data Flow

```
Analyst selects transaction
        ↓
ReviewTool sets activeTx
        ↓
AISuggestion useEffect fires (tx.id changed)
        ↓
POST /transactions/{id}/suggest
        ↓
Backend builds prompt from tx fields
        ↓
OpenAI chat completions (`gpt-4o-mini`)
        ↓
Backend parses JSON response → returns verdict + reasoning
        ↓
AISuggestion renders suggestion card
        ↓
Analyst reads suggestion, writes own verdict in ReviewVerdictForm
```

---

## Out of Scope

- Streaming the response token-by-token
- Pre-filling the verdict form from the AI suggestion
- Persisting AI suggestions to the database
- Allowing the analyst to rate or flag AI suggestions
