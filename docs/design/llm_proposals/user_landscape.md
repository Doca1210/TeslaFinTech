# Sanctions Screening — User Landscape

**Event:** Garaža FinTech AI Hackathon, June 13–14, 2026

---

## Who Actually Uses a Sanctions Screening System

5 distinct user types. The Sokin VP of Engineering is type 3 — useful but not the end user.

---

### Type 1: AML Analyst
**The primary end user. Most valuable person to understand.**

Sits in front of a queue of flagged transactions all day. Job is to clear it before end of business. 2-3 minutes per REVIEW case before the queue backs up.

What they care about:
- Is this a real match or noise? Enough context to decide in 60 seconds.
- Why was this flagged? Show evidence, not just a score.
- What happens if I get it wrong? (career risk, regulatory risk)
- How do I escalate a case above my authorization level?

Daily pain: 200 cases, 4pm on a Friday, half of them are "Mohammed" or "Kim" with no other context. Current tooling gives a name similarity score and nothing else.

**The VP almost certainly is not this person and may have limited insight into this UX.**

---

### Type 2: Compliance Officer
**The buyer. Sets policy. Deals with regulators directly.**

Not in the queue — manages the team and owns the risk. Gets called by regulators. Signs off on screening policy.

What they care about:
- Can I prove to a regulator in 2 years that we screened correctly?
- What's my false positive rate? (too high = lost customers, too low = regulatory risk)
- Did the list update happen? Am I current?
- If I get fined, can I prove the system worked correctly?

Daily pain: No confidence the audit trail is defensible. No way to tune sensitivity without breaking things. Can't answer "what is your false positive rate" in a regulatory examination.

---

### Type 3: Fintech Engineer (the Sokin VP)
**Your actual contact. Technical owner of the screening pipeline.**

Built or inherited the system. Deals with:
- List update process (often manual, risky, sometimes causes downtime)
- Performance under load (peak payment volumes, P99 latency SLAs)
- Integration complexity (payments come from multiple systems)
- Crypto payments (often bolted on as an afterthought or not solved at all)

Best source of: what's broken technically, latency targets, how list updates work today, current stack.

Not the best source of: what an analyst needs to clear a case, what regulators actually ask for, what false positive rate is acceptable.

---

### Type 4: Payment Operations / Customer Service
**The people who feel the false positives from the customer side.**

When a legitimate payment gets blocked, a customer calls. Ops staff have zero visibility into why. They can't tell the customer anything. They escalate to compliance → analyst → may take days to clear.

This is the business cost of over-blocking. Often invisible to engineers.

---

### Type 5: Crypto Compliance Specialist
**Emerging role, mostly at exchanges and crypto-native fintechs.**

Entirely different workflow from fiat. Works with wallet addresses, transaction graphs, chain analysis tools (Chainalysis, Elliptic). Most traditional banks don't have this role yet.

If Sokin handles crypto, the VP may cover this. If not, it's an open space.

---

## What the VP Can and Cannot Tell You

| Question | VP knows? |
|----------|-----------|
| Current stack architecture | Yes |
| Latency numbers and SLAs | Yes |
| How list updates work today | Yes |
| Where the pipeline breaks | Yes |
| Crypto screening approach | Probably yes |
| What analysts need to clear a case | Probably not |
| What regulators actually ask for | Partially |
| What the false positive rate is | Maybe (if they measure it) |
| What makes a REVIEW queue usable | Unlikely |
