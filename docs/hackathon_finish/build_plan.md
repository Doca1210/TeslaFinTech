# FinTech Hackathon: 10-Hour Build Plan

For the next **10 hours**, I would not add more generic sanctions matching. You already have that. The highest-value move is to turn the backend into a **complete payment-risk decision engine**: one API, richer AML behavior, ownership/indirect exposure, and an evidence package that makes the `REVIEW` flow useful.

Your strongest current gap is that the backend has good internals, but the documented HTTP layer exposes ingestion/search/export, not a single end-to-end payment screening endpoint. Meanwhile Sokin’s context says the real problem is real-time suspicious transaction detection, account behavior monitoring, money-in/money-out patterns, location anomalies, source-of-funds, KYB ownership, and human review.

---

## Final 10-hour feature priority

### 1. Build one end-to-end `/screen/payment` endpoint

**Impact: extremely high**  
**Difficulty: medium**  
**Time: 2 to 3 hours**  
**Do this first.**

Right now your system sounds powerful, but fragmented. You have sanctions screening, behavioral AML, verdict composition, and rule hits, but judges need to see one product action:

> Can this payment go through?

The problem statement asks teams to take a payment instruction and return `MATCH`, `REVIEW`, or `NO MATCH`; payments must be checked fast and explainably before clearing. Your backend already has the `VerdictComposer`, where Layer A is sanctions and Layer B is behavioral AML, and maps final results to `BLOCK`, `MANUAL_REVIEW`, or `PASS`.

Implement:

```http
POST /screen/payment
```

Example request:

```json
{
  "payment_id": "pay_001",
  "amount": 20000000,
  "currency": "EUR",
  "direction": "out",
  "channel": "swift",
  "originator": {
    "entity_id": "company_123",
    "name": "Tesla Export DOO",
    "account_name": "Tesla Export DOO",
    "country": "RS",
    "registered_country": "RS"
  },
  "beneficiary": {
    "name": "Al Quds Trading LLC",
    "account_name": "Al Quds Trading Limited",
    "country": "AE",
    "registered_country": "AE",
    "account": "AE123..."
  },
  "initiated_from_country": "RU",
  "source_of_funds": null
}
```

Response should be very judge-friendly:

```json
{
  "payment_id": "pay_001",
  "final_verdict": "REVIEW",
  "recommended_action": "MANUAL_REVIEW",
  "confidence": 0.87,
  "decision_summary": "Beneficiary is a possible sanctions alias match and transaction is anomalous for this account.",
  "layers": {
    "sanctions_screening": {
      "verdict": "REVIEW",
      "top_match": {
        "name": "Al Quds Trading",
        "source_list": "OFAC_SDN",
        "score": 0.81,
        "matched_tokens": ["al", "quds", "trading"]
      }
    },
    "behavioral_aml": {
      "outcome": "review",
      "score": 55,
      "rule_hits": [
        {
          "rule_id": "amount_vs_baseline",
          "severity": "high",
          "reason": "Payment is 18.4x larger than this account's historical average."
        },
        {
          "rule_id": "geo_initiation_mismatch",
          "severity": "medium",
          "reason": "Company registered in RS, payment initiated from RU."
        }
      ]
    }
  },
  "case_id": "case_001"
}
```

Why this separates you: most hackathon teams will demo either a matcher or a UI. This makes your project feel like **payment infrastructure**. It also removes the biggest product weakness: no obvious single workflow.

Minimum implementation:

- Add Pydantic request/response models.
- Screen both originator and beneficiary with v2.
- Run behavioral rules on the payment plus history.
- Use `compose_payment`.
- Return structured `layers`, `rule_hits`, `matched_entities`, and `recommended_action`.
- Store the response as a `transaction_decision` or simple `screening_cases` row.

Do not over-engineer. Hardcode or fixture account histories if needed.

---

### 2. Add Sokin-specific behavioral rules v2

**Impact: extremely high**  
**Difficulty: low to medium**  
**Time: 2 to 3 hours**  
**Do this second.**

Your current behavioral rules are good, but generic: large amount, velocity, structuring, high-risk geo, dormant reawake. The mentor notes give you much more specific signals that Sokin actually cares about: large transaction relative to average, money in equals money out, location anomaly, trend analysis, and source-of-funds.

Add these 5 rules:

#### `amount_vs_baseline`

Detects payments abnormally large for that company.

Logic:

```python
avg = average(amount over last 90 days for same entity)
if current_amount > max(10000, avg * 5):
    score += 35
if current_amount > avg * 10:
    score += 50
```

Demo line:

> Not every €20M payment is suspicious. It is suspicious when this company normally sends €80k.

This directly matches the mentor example: a company earning €10M/year suddenly receiving €20M should trigger an alarm.

#### `pass_through_money_in_out`

Detects “money in = money out.”

Logic:

```python
recent_in = incoming transactions in last 48h
if outgoing amount is within 1-3% of recent incoming amount
and outgoing happens within 0-48h:
    score += 40
```

Demo line:

> The account receives €500k and sends €498k out 35 minutes later. That is a laundering pattern, even if the names are clean.

This is one of the clearest Sokin-specific differentiators because they explicitly mentioned it.

#### `geo_initiation_mismatch`

Detects weird payment origin.

Logic:

```python
if initiated_from_country not in [registered_country, usual_operating_countries]:
    score += 25
if initiated_from_country in high_risk_countries:
    score += 35
```

Demo line:

> Company is registered in the US, but the payment order comes from China or Russia. That triggers manual board/ownership review.

This maps directly to the partner note.

#### `missing_source_of_funds`

Simple but very compliance-relevant.

Logic:

```python
if amount > threshold and source_of_funds is null:
    score += 20
```

For high-value transfers:

```python
if amount > 100000 and source_of_funds is null:
    REVIEW
```

The partner notes say strict regulation requires knowing exactly who the money comes from.

#### `beneficiary_account_name_mismatch`

Basic Verification of Payee style check.

Logic:

```python
similarity = fuzzy(account_name, beneficiary_name)
if similarity < 0.75:
    score += 25
```

The mentor notes mention that account name must match transaction name and that Verification of Payee is emerging.

Output each rule as:

```json
{
  "rule_id": "pass_through_money_in_out",
  "severity": "high",
  "score": 40,
  "reason": "Outgoing transfer closely matches incoming transfer from 42 minutes earlier.",
  "evidence": {
    "incoming_amount": 500000,
    "outgoing_amount": 498700,
    "time_delta_minutes": 42,
    "amount_delta_pct": 0.26
  }
}
```

Why this separates you: it shifts your product from “sanctions search” to **real AML transaction intelligence**. That is much closer to Sokin than pure watchlist matching.

---

### 3. Add a minimal KYB / ownership exposure graph

**Impact: very high**  
**Difficulty: medium**  
**Time: 2 to 3 hours**  
**Do this after endpoint + behavioral v2.**

This is probably your best “wow” differentiator. The problem statement explicitly says sanctioned people use shell companies, proxies, intermediaries, and that the link can be several degrees removed. The mentor notes also say KYB is complex because you need to know who owns the company and what other companies stand behind it.

Do not try to ingest real registries now. Build a clean, credible graph module with demo fixtures.

Data model can be tiny:

```sql
ownership_links
- parent_entity_id
- child_entity_id
- relation_type      -- owner, director, ubo, subsidiary, intermediary
- ownership_pct
- source             -- demo_registry, companies_house_fixture, manual_kyb
```

Or just a JSON fixture:

```json
[
  {
    "from": "person_ivan_petrov",
    "to": "company_blue_trade_ltd",
    "relation": "beneficial_owner",
    "ownership_pct": 35
  },
  {
    "from": "company_blue_trade_ltd",
    "to": "company_beneficiary_123",
    "relation": "parent_company",
    "ownership_pct": 80
  }
]
```

Add a function:

```python
trace_related_parties(entity_id, max_depth=2)
```

Risk rules:

```python
if direct_owner is sanctions MATCH:
    final_verdict = MATCH or REVIEW depending confidence

if beneficial_owner is PEP:
    final_verdict = REVIEW

if owner path depth <= 2 and sanctions score >= 0.85:
    final_verdict = REVIEW

if ownership_pct >= 25:
    include as UBO evidence
```

Response example:

```json
"ownership_risk": {
  "verdict": "REVIEW",
  "reason": "Beneficiary is 35% owned by a politically exposed person.",
  "paths": [
    {
      "path": [
        "Blue Trade LLC",
        "Ivan Petrov"
      ],
      "relation": "beneficial_owner",
      "ownership_pct": 35,
      "risk": "PEP_MATCH",
      "source": "OpenSanctions PEPs"
    }
  ]
}
```

Demo scenario:

1. Payment to `Blue Trade LLC`.
2. Name screening on `Blue Trade LLC` returns clean.
3. Ownership graph finds `Ivan Petrov`, a PEP or sanctioned person.
4. Final verdict becomes `REVIEW`.
5. Evidence says: “Clean beneficiary, risky beneficial owner.”

Why this separates you: competitors and hackathon teams often stop at direct name matching. This proves you understand how laundering actually hides behind companies.

---

### 4. Create an “Evidence Pack” for every decision

**Impact: very high**  
**Difficulty: low**  
**Time: 1 to 1.5 hours**  
**Do this before any UI polish.**

The problem statement asks how to explain a verdict in a way a compliance officer could defend years later, and asks what makes a `REVIEW` queue usable. Your backend already stores raw entity records, rule hits, explanations, and evidence. Surface that as a first-class feature.

Add:

```http
GET /cases/{case_id}/evidence
```

Return:

```json
{
  "case_id": "case_001",
  "payment_id": "pay_001",
  "created_at": "2026-06-13T22:15:00Z",
  "final_verdict": "REVIEW",
  "recommended_action": "MANUAL_REVIEW",
  "executive_summary": [
    "Beneficiary has an 81% sanctions alias similarity.",
    "Payment is 18.4x larger than account baseline.",
    "Payment was initiated from a high-risk country."
  ],
  "decision_timeline": [
    {
      "step": "sanctions_screening",
      "result": "REVIEW",
      "latency_ms": 142
    },
    {
      "step": "behavioral_aml",
      "result": "REVIEW",
      "latency_ms": 18
    },
    {
      "step": "ownership_trace",
      "result": "NO_MATCH",
      "latency_ms": 7
    }
  ],
  "evidence": {
    "matched_entities": [],
    "rule_hits": [],
    "ownership_paths": [],
    "raw_source_refs": []
  }
}
```

Add a simple `explainability_score`:

```json
"explainability_score": 0.92
```

Based on whether the case has:

- source list
- match score
- rule hits
- evidence fields
- timestamps
- final action
- analyst action status

Why this separates you: a judge can immediately understand that this is not a black box. It is a compliance decision system.

---

### 5. Add a minimal analyst action workflow, not a full case management product

**Impact: high**  
**Difficulty: low**  
**Time: 1.5 to 2 hours**

Do not build a huge review platform. Sokin notes say suspicious transactions go to manual review, but the review platform itself is not the priority. So build the smallest possible “human-in-the-loop proof.”

Endpoints:

```http
GET /cases?status=open
POST /cases/{case_id}/assign
POST /cases/{case_id}/decision
```

Decision request:

```json
{
  "analyst_id": "analyst_1",
  "decision": "approve_after_review",
  "comment": "False positive. Beneficiary company is unrelated to matched sanctioned entity.",
  "requires_second_approval": true
}
```

For 4-eyes:

```json
{
  "status": "pending_second_approval",
  "required_approvals": 2,
  "current_approvals": 1
}
```

Then second analyst:

```json
{
  "analyst_id": "analyst_2",
  "decision": "confirm_block",
  "comment": "Ownership path confirms sanctioned beneficial owner."
}
```

Why this separates you: you show that `REVIEW` is not a dead end. It becomes an auditable decision process.

---

## Recommended 10-hour execution plan

Assuming 3 people:

|          Time | Pavle                                        | Dositej                                        | Igor                                 |
| ------------: | -------------------------------------------- | ---------------------------------------------- | ------------------------------------ |
|  0:00 to 0:30 | Freeze scope, define request/response schema | Define behavioral v2 rules                     | Define case/evidence tables          |
|  0:30 to 2:30 | Build `/screen/payment`                      | Implement `amount_vs_baseline`, `pass_through` | Wire persistence and latency timing  |
|  2:30 to 4:30 | Compose final response object                | Add geo/source-of-funds/VoP rules              | Add `/cases/{id}/evidence`           |
|  4:30 to 6:30 | Integrate ownership risk into final verdict  | Build ownership fixture and graph traversal    | Add audit timeline and case status   |
|  6:30 to 8:00 | Add 4 demo scenarios and seed data           | Validate scoring thresholds                    | Add simple benchmark/latency numbers |
|  8:00 to 9:00 | Polish API outputs and Swagger examples      | Fix explanations                               | Fix edge cases                       |
| 9:00 to 10:00 | End-to-end test                              | End-to-end test                                | End-to-end test                      |

Cut anything that is not part of this flow.

---

## The exact feature set I would ship

### Must ship

1. `POST /screen/payment`
2. Behavioral v2 rules:
   - `amount_vs_baseline`
   - `pass_through_money_in_out`
   - `geo_initiation_mismatch`
   - `missing_source_of_funds`
   - `beneficiary_account_name_mismatch`
3. `GET /cases/{case_id}/evidence`
4. Basic case status:
   - `open`
   - `pending_second_approval`
   - `approved`
   - `blocked`
5. 4 demo fixtures:
   - clean payment
   - direct sanctions match
   - clean name but suspicious behavior
   - clean company but risky owner

### Should ship

6. Ownership graph to depth 2
7. Latency timings per layer
8. JSON examples in Swagger/OpenAPI
9. One simple dashboard or frontend screen only if backend is stable

### Do not ship unless everything above is done

10. Crypto wallet tracing
11. Full adverse media
12. Real corporate registry ingestion
13. Cloud deployment
14. Complex ML model training
15. Full analyst dashboard

Crypto is tempting because the problem statement mentions wallets and Sokin has stablecoin interest, but in 10 hours it is risky. A fake ownership graph is more relevant to B2B cross-border payments and easier to make credible.

---

## Scoring logic I’d use

Keep it understandable. Do not invent a complex model now.

```python
final_score = max(
    sanctions_score * 100,
    behavioral_score,
    ownership_score,
    vop_score
)
```

Verdict:

```python
if sanctions_match_high_confidence:
    MATCH

elif ownership_sanctions_direct:
    MATCH

elif behavioral_score >= 60:
    REVIEW

elif ownership_pep_or_indirect_sanctions:
    REVIEW

elif vop_mismatch and amount_high:
    REVIEW

elif sanctions_score >= review_threshold:
    REVIEW

else:
    NO_MATCH
```

Recommended action:

```python
MATCH -> BLOCK
REVIEW -> MANUAL_REVIEW
NO_MATCH -> PASS
```

This is easy to explain and consistent with your existing `VerdictComposer` design.

---

## Demo scenarios to seed

### Scenario 1: Clean payment

```json
{
  "beneficiary": "Milan Textile GmbH",
  "amount": 12000,
  "country": "DE"
}
```

Expected:

```json
"final_verdict": "NO_MATCH",
"recommended_action": "PASS"
```

Purpose: prove you do not block everyone.

---

### Scenario 2: Direct sanctions / alias match

```json
{
  "beneficiary": "Vneshtorgbank",
  "amount": 25000,
  "country": "RU"
}
```

Expected:

```json
"final_verdict": "MATCH",
"recommended_action": "BLOCK"
```

Purpose: show matching engine.

---

### Scenario 3: Clean name, suspicious behavior

Company history:

- Usually sends €20k to €50k
- Receives €500k
- Sends €498k out 42 minutes later

Expected:

```json
"final_verdict": "REVIEW",
"reason": "Pass-through transaction and amount 12.4x above account baseline."
```

Purpose: show you solve AML, not only sanctions.

---

### Scenario 4: Clean company, risky owner

Payment to:

```json
"Blue Horizon Trading LLC"
```

Direct screening:

```json
"NO_MATCH"
```

Ownership graph:

```json
"35% owned by Ivan Petrov, PEP/sanctions candidate"
```

Expected:

```json
"final_verdict": "REVIEW"
```

Purpose: this is your separator. It demonstrates shell-company / KYB reasoning.

---

## One thing to be careful about

Do not claim this is production-ready. Claim it is a **working prototype of an explainable payment compliance decision engine**. Your backend uses SQLite and demo fixtures, so production claims may invite hard questions.

But it is completely fair to say:

> The important part is the decision architecture: sanctions, behavior, ownership, and human review are combined into one explainable payment verdict.

That is strong and defensible.

---

## Final recommendation

Build in this order:

1. **`/screen/payment`**
2. **Sokin-specific behavioral AML rules**
3. **Evidence Pack**
4. **Mini KYB ownership graph**
5. **Minimal 4-eyes case action**

That gives you the strongest product by the end: not just “we match names,” but **we prevent risky cross-border payments from slipping through direct screening by combining identity, behavior, ownership, and human review into one explainable decision.**
