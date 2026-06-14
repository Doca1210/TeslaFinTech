# AI Suggestion for Review Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a compliance analyst selects a transaction in the Review Tool, automatically fetch an OpenAI-generated verdict suggestion (BLOCK / RELEASE / ESCALATE) and display it with reasoning above the verdict form.

**Architecture:** A new `backend/app/suggest.py` module builds a structured compliance prompt from transaction fields and calls OpenAI `gpt-4o-mini`. A new `POST /transactions/{tx_id}/suggest` FastAPI endpoint exposes this to the frontend. A new `AISuggestion` React component fetches on transaction selection and renders a verdict badge + reasoning paragraph.

**Tech Stack:** Python `openai>=1.0` (async client), `python-dotenv`, FastAPI, React (no new frontend deps)

---

### Task 1: Add dependencies and create .env

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/.env`
- Modify: `.gitignore`

- [ ] **Step 1: Add openai and python-dotenv to requirements**

Open `backend/requirements.txt` and append two lines so it reads:

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy>=2.0
httpx>=0.27.0
lxml
pydantic>=2.9.0
rapidfuzz>=3.10.0
jellyfish>=1.1.0
unidecode>=1.3.8
pytest>=8.3.0
sentence-transformers>=3.0.0
faiss-cpu>=1.8.0
openai>=1.0.0
python-dotenv>=1.0.0
```

- [ ] **Step 2: Create backend/.env**

Create `backend/.env` with your real OpenAI key:

```
OPENAI_API_KEY=your_key_here
```

- [ ] **Step 3: Add .env to .gitignore**

Open the root `.gitignore` and add:

```
backend/.env
```

- [ ] **Step 4: Install new dependencies**

```bash
cd backend && pip install openai>=1.0.0 python-dotenv>=1.0.0
```

Expected: installs without errors.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt .gitignore
git commit -m "feat: add openai and python-dotenv dependencies"
```

---

### Task 2: Create suggest.py — prompt builder and OpenAI call

**Files:**
- Create: `backend/app/suggest.py`
- Create: `backend/tests/test_suggest.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_suggest.py`:

```python
"""Tests for the AI suggestion module."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


SAMPLE_TX = {
    "id": 7,
    "label": "High-risk wire to Iran",
    "originator": "Alice Johnson",
    "beneficiary": "Caspian Oil Trading",
    "amount": 95000.0,
    "currency": "USD",
    "counterparty_country": "IR",
    "confidence": 0.88,
    "triggered_layers": ["layer_a_sanctions", "layer_b_behavioral"],
    "explanation": "Sanctions screening: Beneficiary matched OFAC SDN. Behavioral analysis: high-risk jurisdiction.",
    "layer_a": {
        "originator": {"verdict": "NO_MATCH", "confidence": 0.5, "matched_name": None, "matched_entity_id": None},
        "beneficiary": {"verdict": "MATCH", "confidence": 0.88, "matched_name": "Caspian Energy LLC", "matched_entity_id": "OFAC_SDN:9921"},
    },
    "layer_b": {
        "score": 55,
        "outcome": "review",
        "rules_fired": [
            {"rule_id": "geo_high_risk", "severity": "high", "score": 35, "reason": "Counterparty country IR is high-risk"},
            {"rule_id": "amt_large", "severity": "medium", "score": 20, "reason": "Amount 95000 exceeds threshold"},
        ],
    },
    "ownership_risk": None,
}


def _mock_openai_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


def test_get_ai_suggestion_returns_verdict_and_reasoning():
    from app.suggest import get_ai_suggestion

    async def run():
        with patch("app.suggest.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_openai_response(
                    '{"verdict": "BLOCK", "reasoning": "Beneficiary matched OFAC SDN list with high confidence."}'
                )
            )
            return await get_ai_suggestion(SAMPLE_TX)

    result = asyncio.run(run())
    assert result["verdict"] == "BLOCK"
    assert result["reasoning"] == "Beneficiary matched OFAC SDN list with high confidence."


def test_get_ai_suggestion_propagates_openai_exception():
    from app.suggest import get_ai_suggestion

    async def run():
        with patch("app.suggest.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))
            return await get_ai_suggestion(SAMPLE_TX)

    try:
        asyncio.run(run())
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "API error" in str(e)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_suggest.py -v
```

Expected: `ImportError` — `app.suggest` does not exist yet.

- [ ] **Step 3: Create backend/app/suggest.py**

```python
from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


def _build_prompt(tx: dict) -> str:
    la = tx["layer_a"]
    lb = tx["layer_b"]
    orig = la["originator"]
    bene = la["beneficiary"]

    orig_match = (
        f" → matched: {orig['matched_name']} [{orig['matched_entity_id']}]"
        if orig.get("matched_name")
        else ""
    )
    bene_match = (
        f" → matched: {bene['matched_name']} [{bene['matched_entity_id']}]"
        if bene.get("matched_name")
        else ""
    )

    rules = lb.get("rules_fired", [])
    rules_text = (
        "\n".join(
            f"  - {r['rule_id']} (severity={r['severity']}, score={r['score']}): {r['reason']}"
            for r in rules
        )
        or "  None"
    )

    return (
        f"Transaction under review:\n"
        f"- Label: {tx['label']}\n"
        f"- Originator: {tx['originator']}\n"
        f"- Beneficiary: {tx['beneficiary']}\n"
        f"- Amount: {tx['amount']:,.2f} {tx['currency']}\n"
        f"- Counterparty country: {tx['counterparty_country']}\n"
        f"- Confidence: {tx['confidence'] * 100:.0f}%\n"
        f"- Triggered layers: {', '.join(tx['triggered_layers']) or 'none'}\n\n"
        f"Layer A — Sanctions screening:\n"
        f"  Originator verdict: {orig['verdict']}{orig_match}\n"
        f"  Beneficiary verdict: {bene['verdict']}{bene_match}\n\n"
        f"Layer B — Behavioral AML:\n"
        f"  Score: {lb['score']} → {lb['outcome']}\n"
        f"  Rules fired:\n{rules_text}\n\n"
        f"System explanation: {tx['explanation']}\n\n"
        f'Respond with JSON only: {{"verdict": "BLOCK"|"RELEASE"|"ESCALATE", "reasoning": "<1-3 sentence rationale>"}}'
    )


async def get_ai_suggestion(tx: dict) -> dict:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a compliance AI assistant helping a human analyst review "
                    "flagged payment transactions. Based on the AML screening data, "
                    "suggest the most appropriate verdict: BLOCK (high risk, prevent payment), "
                    "RELEASE (low risk, allow payment), or ESCALATE (uncertain, needs senior review). "
                    "Be concise and evidence-based."
                ),
            },
            {"role": "user", "content": _build_prompt(tx)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_suggest.py -v
```

Expected:
```
tests/test_suggest.py::test_get_ai_suggestion_returns_verdict_and_reasoning PASSED
tests/test_suggest.py::test_get_ai_suggestion_propagates_openai_exception PASSED
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/suggest.py backend/tests/test_suggest.py
git commit -m "feat: add AI suggestion module with OpenAI prompt and call"
```

---

### Task 3: Add POST /transactions/{tx_id}/suggest endpoint

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_suggest_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_suggest_endpoint.py`:

```python
"""Integration tests for the /transactions/{tx_id}/suggest endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app

MINIMAL_TX = {
    "id": 5,
    "label": "Test wire",
    "originator": "Alice",
    "beneficiary": "Bob LLC",
    "amount": 10000.0,
    "currency": "USD",
    "counterparty_country": "DE",
    "confidence": 0.75,
    "triggered_layers": ["layer_b_behavioral"],
    "explanation": "Behavioral flag only.",
    "layer_a": {
        "originator": {"verdict": "NO_MATCH", "confidence": 0.4, "matched_name": None, "matched_entity_id": None},
        "beneficiary": {"verdict": "NO_MATCH", "confidence": 0.4, "matched_name": None, "matched_entity_id": None},
    },
    "layer_b": {"score": 30, "outcome": "review", "rules_fired": [{"rule_id": "amt_large", "severity": "medium", "score": 30, "reason": "Large amount"}]},
    "ownership_risk": None,
}


@pytest.fixture(autouse=True)
def set_tx_cache(monkeypatch):
    monkeypatch.setattr(main_module, "_transactions_cache", [MINIMAL_TX])


def test_suggest_endpoint_returns_suggestion():
    with patch("app.main.get_ai_suggestion", new=AsyncMock(return_value={"verdict": "ESCALATE", "reasoning": "Behavioral flag only, no sanctions hit."})):
        client = TestClient(app)
        response = client.post("/transactions/5/suggest")

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "ESCALATE"
    assert data["reasoning"] == "Behavioral flag only, no sanctions hit."


def test_suggest_endpoint_404_for_unknown_id():
    client = TestClient(app)
    response = client.post("/transactions/999/suggest")
    assert response.status_code == 404


def test_suggest_endpoint_502_when_openai_fails():
    with patch("app.main.get_ai_suggestion", new=AsyncMock(side_effect=RuntimeError("OpenAI down"))):
        client = TestClient(app)
        response = client.post("/transactions/5/suggest")

    assert response.status_code == 502
    assert response.json()["detail"] == "AI suggestion unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_suggest_endpoint.py -v
```

Expected: `404` for all — endpoint doesn't exist yet.

- [ ] **Step 3: Add the endpoint to main.py**

At the top of `backend/app/main.py`, add the import alongside other app imports:

```python
from app.suggest import get_ai_suggestion
```

Then add the following endpoint after the `list_transactions` endpoint (after line ~222):

```python
@app.post("/transactions/{tx_id}/suggest")
async def suggest_transaction(tx_id: int) -> dict:
    """Call OpenAI to suggest a compliance verdict for a flagged transaction."""
    transactions = list_transactions()
    tx = next((t for t in transactions if t["id"] == tx_id), None)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        return await get_ai_suggestion(tx)
    except Exception:
        logger.exception("AI suggestion failed for tx_id=%s", tx_id)
        raise HTTPException(status_code=502, detail="AI suggestion unavailable")
```

Also add `HTTPException` to the FastAPI import at the top of `main.py` (it's already imported if used elsewhere, otherwise add it):

```python
from fastapi import FastAPI, HTTPException, Request
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_suggest_endpoint.py -v
```

Expected:
```
tests/test_suggest_endpoint.py::test_suggest_endpoint_returns_suggestion PASSED
tests/test_suggest_endpoint.py::test_suggest_endpoint_404_for_unknown_id PASSED
tests/test_suggest_endpoint.py::test_suggest_endpoint_502_when_openai_fails PASSED
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_suggest_endpoint.py
git commit -m "feat: add POST /transactions/{tx_id}/suggest endpoint"
```

---

### Task 4: Add AISuggestion component to the frontend

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Add the AISuggestion component to App.jsx**

In `frontend/src/App.jsx`, add this new component directly before the `ReviewTool` function definition (around line 247):

```jsx
function AISuggestion({ tx }) {
  const [state, setState] = useState({ status: 'loading', verdict: null, reasoning: null })

  useEffect(() => {
    setState({ status: 'loading', verdict: null, reasoning: null })
    fetch(`${API_URL}/transactions/${tx.id}/suggest`, { method: 'POST' })
      .then((res) => {
        if (!res.ok) throw new Error('suggest failed')
        return res.json()
      })
      .then((data) =>
        setState({ status: 'ready', verdict: data.verdict, reasoning: data.reasoning }),
      )
      .catch(() => setState({ status: 'error', verdict: null, reasoning: null }))
  }, [tx.id])

  if (state.status === 'loading') {
    return (
      <div className="ai-suggestion ai-suggestion-loading">
        <span className="ai-suggestion-label">AI Suggestion</span>
        <p className="ai-suggestion-body">Analyzing transaction…</p>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="ai-suggestion ai-suggestion-error">
        <span className="ai-suggestion-label">AI Suggestion</span>
        <p className="ai-suggestion-body">AI suggestion unavailable.</p>
      </div>
    )
  }

  return (
    <div className="ai-suggestion ai-suggestion-ready">
      <div className="ai-suggestion-header">
        <span className="ai-suggestion-label">AI Suggestion</span>
        <span className={`badge ai-verdict-${state.verdict}`}>{state.verdict}</span>
      </div>
      <p className="ai-suggestion-body">{state.reasoning}</p>
    </div>
  )
}
```

- [ ] **Step 2: Wire AISuggestion into ReviewTool**

In the `ReviewTool` function (around line 286), find the `review-detail` column JSX:

```jsx
<div className="review-column review-detail">
  {activeTx ? (
    <>
      <TransactionCard tx={activeTx} decision={reviewDrafts[activeTx.id] ? manualDecisionFromDraft(reviewDrafts[activeTx.id]) : null} />
      <ReviewVerdictForm
        key={activeTx.id}
        tx={activeTx}
        draft={reviewDrafts[activeTx.id]}
        onSave={onSaveReview}
      />
    </>
  ) : (
    <p className="status">Select a review case to write a verdict.</p>
  )}
</div>
```

Replace it with:

```jsx
<div className="review-column review-detail">
  {activeTx ? (
    <>
      <TransactionCard tx={activeTx} decision={reviewDrafts[activeTx.id] ? manualDecisionFromDraft(reviewDrafts[activeTx.id]) : null} />
      <AISuggestion tx={activeTx} />
      <ReviewVerdictForm
        key={activeTx.id}
        tx={activeTx}
        draft={reviewDrafts[activeTx.id]}
        onSave={onSaveReview}
      />
    </>
  ) : (
    <p className="status">Select a review case to write a verdict.</p>
  )}
</div>
```

- [ ] **Step 3: Add CSS for AISuggestion to App.css**

Append to the end of `frontend/src/App.css`:

```css
/* ── AI Suggestion ─────────────────────────────────────────── */
.ai-suggestion {
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  background: var(--card-bg);
  border-radius: 6px;
  padding: 12px 16px;
  margin-top: 12px;
}

.ai-suggestion-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.ai-suggestion-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-h);
}

.ai-suggestion-body {
  color: var(--text);
  font-size: 14px;
  line-height: 1.5;
  margin: 0;
}

.ai-suggestion-loading .ai-suggestion-label {
  display: block;
  margin-bottom: 6px;
}

.ai-suggestion-loading {
  animation: ai-pulse 1.5s ease-in-out infinite;
}

.ai-suggestion-error {
  border-left-color: var(--border);
  opacity: 0.6;
}

.ai-suggestion-error .ai-suggestion-label {
  display: block;
  margin-bottom: 6px;
}

@keyframes ai-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 0.35; }
}

.ai-verdict-BLOCK    { background: var(--red-bg);   color: var(--red); }
.ai-verdict-RELEASE  { background: var(--green-bg); color: var(--green); }
.ai-verdict-ESCALATE { background: var(--amber-bg); color: var(--amber); }
```

- [ ] **Step 4: Start the dev server and verify**

```bash
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev
```

Open the Review Tool tab. Select a flagged transaction. Verify:
- Loading state appears immediately ("Analyzing transaction…" with pulse animation)
- After a few seconds the AI suggestion card appears with a colored BLOCK / RELEASE / ESCALATE badge and a reasoning paragraph
- Selecting a different transaction resets the suggestion and re-fetches
- The verdict form below is unaffected and fully functional

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/App.css
git commit -m "feat: add AISuggestion component to Review Tool"
```
