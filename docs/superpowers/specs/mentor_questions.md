# Mentor Questions — Sokin VP of Engineering

**Event:** Garaža FinTech AI Hackathon, June 13–14, 2026
**Goal:** Identify the biggest unsolved pain to attack in 40 hours.

---

## The Decision This Conversation Must Answer

Every answer points at a different build direction:

| What they say | What to build |
|---------------|--------------|
| "False positives are killing us" | Better matching engine (embeddings) |
| "REVIEW queue is unusable" | Analyst UX + LLM case summaries |
| "Crypto is unsolved for us" | Wallet graph screening |
| "List updates are risky/manual" | Live ingestion pipeline |
| "We can't explain our decisions to regulators" | Explainability + audit trail |

---

## How to Open

Don't start with "we're thinking of building X." Start with:

> "Before we decide what to build, we want to understand where your current system actually hurts. Can you walk us through what a payment screening looks like end-to-end in your system today?"

This gets them talking. Listen for which pain point comes up first and loudest.

---

## Questions — In Priority Order

If time runs out, the top 5 are what matter most.

### Block 1: Find the Pain (Most Important)

**Q1: "Where does your current screening system break or frustrate people the most?"**
Outcome: Compass question. Whatever they say here is probably what to build.

**Q2: "Walk me through what happens when a payment gets flagged for REVIEW. Who deals with it, using what tools, and how long does it take?"**
Outcome: If this story is painful or slow → analyst UX is the right angle. If they clear it in 5 minutes → that angle is less valuable.

**Q3: "Do you measure your false positive rate? What is it?"**
Outcome: If they don't know or it's high (>10%) → matching quality is unsolved. If they know it precisely and it's low → matching is already good.

---

### Block 2: Understand the Crypto Gap

**Q4: "Do you screen crypto payments today? How?"**
Outcome: Three possible answers:
- "Yes, we use Chainalysis/Elliptic" → commercial tools exist, don't reinvent
- "Yes, but it's just an OFAC wallet list lookup" → graph analysis is the gap
- "No, we don't touch crypto" → either irrelevant to their business, or an open frontier

**Q5: "Is the link between a wallet address and a sanctioned entity something you can currently trace, or just direct OFAC matches?"**
Outcome: If only direct matches → N-hop graph traversal is a real, technically impressive gap.

---

### Block 3: Understand Operational Pain

**Q6: "How do you handle sanctions list updates? How often, how long does it take, what can go wrong?"**
Outcome: Manual process or downtime risk → live list ingestion is worth building. Fully automated and safe → not worth 40 hours.

**Q7: "What's your P99 latency for a screening decision right now?"**
Outcome: Gives a baseline. If they're at 800ms and struggling → speed is a real constraint. If headroom exists → performance isn't the problem.

---

### Block 4: Understand Regulatory/Explainability Requirements

**Q8: "If a regulator asked you to explain a specific screening decision from 18 months ago, what would you show them?"**
Outcome: "We'd struggle" or "we'd piece it together from logs" → explainability is genuinely unsolved. Clean audit trail already exists → don't build that.

---

### Block 5: Find the Dream Feature

**Q9: "What's the one thing you wish your screening system did that it doesn't do today?"**
Outcome: Direct signal on what impresses them. Also your best demo hint — build what they just described.

**Q10: "What would make you say 'I wish we had built that' watching a team's demo today?"**
Outcome: Directly tells you what wins. Ask this if time allows.

---

### Closing Ask (Important)

**"Is there an AML analyst or compliance officer here we could speak to for even 10 minutes? We want to understand what a flagged transaction looks like from the analyst's side."**
Outcome: If yes, that conversation is worth more than 2 hours of coding. Do it immediately after.

---

## The Single Most Valuable Thing to Get

Ask him to show you what a REVIEW case looks like in their current system. A screenshot, a walkthrough, anything. The gap between "what an analyst actually sees" and "what good tooling would look like" is often enormous and visible in 2 minutes.

---

## What You Should Know When You Walk Out

Fill in these blanks before starting to code:

- The biggest single pain point is: ___________
- Current crypto screening capability: [ none / OFAC list only / graph analysis ]
- False positive rate is approximately: ___________
- List updates are: [ manual and risky / automated and safe ]
- The thing they wish existed: ___________
- We should also talk to: [ analyst / compliance officer / no one else available ]

Those answers point directly at which direction to build.
