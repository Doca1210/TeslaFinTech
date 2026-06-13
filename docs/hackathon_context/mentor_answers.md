# Sokin Partner Context

Merged from mentor Q&A session notes and Sokin AI interview notes (`sokin_ai.md`).

---

## Detection & Screening

- **Core problem:** Detect suspicious transactions in real-time or near-real-time, in an innovative way.
- **Name matching:** Small name differences and cross-language variants are handled via an external service. Account name must match the name on the transaction.
- **Account behavior monitoring:** Company accounts are tracked over time. Anomalies trigger flags:
  - Large transaction relative to the account's average transaction size
  - Money in = money out (same amount entering and leaving) → money laundering signal
- **Amount anomaly example:** If a company earns €10M/year and suddenly receives a €20M transfer, an alarm fires.
- **Location anomaly:** Company registered in the US, but payment order comes from China or Russia → risk level elevated, board/ownership manual review triggered.
- **Trend analysis:** AML system tracks payment patterns over time: transaction volume, time delta between inflows and outflows.
- **Source of funds:** Strict regulation requires knowing exactly who the money comes from (e.g., third-party payments on someone's behalf).

---

## AML Workflow & Compliance

- **Current model:** "Stop and wait" — AML engine flags, then human reviews. Risk-based approach with mandatory **human-in-the-loop**.
- **Manual work:** A significant percentage of transactions are automated, but manual work persists via **4-eyes or 6-eyes checks** (multiple sign-offs required per transaction).
- **Suspicious transaction flow (Money Out):**
  1. Pre-execution checks: Can we process this? Do beneficiary details match? Are funds covered?
  2. If suspicious → sent to Compliance team for approval.
  3. If confirmed fraud → reported to the relevant regulatory body.
- **No automatic resolution:** Suspicious transactions go to manual review; the review platform itself is not a priority (something to iterate on later).
- **Ethical restrictions:** Some partners refuse to work with businesses connected to crypto or gambling.

### KYB & Counterparty Risk

- **Individual checks:** Straightforward.
- **KYB (Know Your Business):** Complex — who actually owns the company? What other companies stand behind the transacting entity?
- **Regional risk:** Risk factors vary by region. Sanction lists and PEPs (Politically Exposed Persons — politicians, directors, etc.) are monitored.
- **EU focus:** Preventing terrorism financing, assessing risk on outgoing transactions.
- **Payee verification:** Advanced Verification of Payee (VoP) services being introduced.

---

## Business Model & Market Context

- **Clients:** B2B customers transacting globally who want to pay in foreign currencies, not just local ones.
- **Liquidity problem:** Some markets lack large liquidity pools — currency-to-currency (or gold-to-currency) balancing required. Money must always be available locally.
- **Instant FX:** If a client has sufficient balance, FX trades execute in real-time.
- **Funding use:** Financing rounds go exclusively toward business growth, not operational float.
- **Long-term goal:** Obtain banking licenses in each region for full regulated control.

---

## Emerging Markets & Crypto

- **Africa:** Transactions take up to 3 days. Goal is to remove friction from global payments.
- **Stablecoin strategy:** Crypto and stablecoins are the proposed solution for Africa — strong demand for holding money in stable currencies rather than local African currencies. Sokin is negotiating with banks to regulate this.
- **Traditional banks:** No bank currently uses crypto; FX rates remain extremely high.

---

## Technical Architecture

```
[Client / App] ──> [Push Notifications]
                         │
                         ▼
        [Transaction Processing System]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[Region: UAE]                    [Other Regions]
(Local data processing)           (Cloud Shards)
        │                                 │
        └───────────────┬─────────────────┘
                        ▼
            [Multi-shard Relational DB]
```

- **Migration:** AWS → Azure. Sharding architecture for background processes.
- **UAE data localization:** UAE regulations require local data processing. Two separate UAE systems = bad solution (already tried).
- **Scaling lesson:** Horizontal scaling attempt yielded **0% speedup** — bottleneck was elsewhere. Profile before scaling.

---

## Product Strategy

- **"DO LESS":** Deliver less-polished functionality fast → collect real usage data → build a better version. Short feedback loop.
- **Push notifications:** Strong mobile asset — better user contact, easier upselling of side services.
- **Platform extensibility:** Making it easier to build on top of the platform is a current pain point.
- **New partners:** Finding vendors with large customer balance sheets to expand liquidity coverage.
