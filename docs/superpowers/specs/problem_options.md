# Sanctions Screening — All Possible Options (40h Hackathon)

**Event:** Garaža FinTech AI Hackathon, June 13–14, 2026
**Problem:** Given a payment (name+country for fiat, wallet address for crypto), return MATCH / REVIEW / NO MATCH.

---

## The Screening Engine (Core Logic)

**1. Embedding-based fuzzy name matching**
Take the sanctions list, embed every entity. At query time, embed the incoming name and find nearest neighbors. Handles transliteration naturally. Pavle's exact skill set (Milvus, vector search). Most technically interesting fiat approach.

**2. Hybrid matcher: rule-based + semantic**
Edit distance / phonetic (Soundex, Metaphone) for speed, embeddings for recall, LLM for disambiguation of borderline cases. Best accuracy, more complex to build.

**3. LLM-only disambiguation**
Skip traditional matching. Feed borderline cases directly to a model with the sanctions list context and ask for a verdict. Simple but expensive and slow at scale.

**4. Fine-tuned similarity model**
Train a custom model specifically for name-matching across scripts (Arabic → Latin, Cyrillic → Latin). Dositej's domain. Probably too slow to train in 40h but possible if using a small pre-trained base.

---

## The Analyst Review Queue (Human-in-the-Loop UX)

**5. Review queue interface**
The REVIEW cases land somewhere. Build the analyst UI: show why the case was flagged, side-by-side comparison with the matched entity, confidence score, one-click APPROVE/BLOCK, audit log. Pure product differentiator that technical teams often skip.

**6. LLM-generated case summary**
For each REVIEW case, auto-generate a short paragraph: "This payment matches Sergey Ivanov (OFAC SDN list) with 84% confidence. Primary signal: name phonetic similarity. Secondary: same country of origin." Huge time-saver for analysts.

**7. Explainability / audit trail**
Every decision (even NO MATCH) produces a structured record: which lists were checked, what score was produced, which rule triggered. This is what regulators ask for two years later.

---

## Crypto Screening

**8. OFAC wallet list direct lookup**
Simplest crypto path: OFAC publishes sanctioned wallet addresses. Build a fast lookup against that list. No graph analysis needed. Igor can make this sub-millisecond with a bloom filter or hash map.

**9. 1-hop transaction graph risk**
Check if the wallet has sent/received directly from any sanctioned wallet. Use a public blockchain API (Etherscan, Blockstream). Moderate complexity, doable in 40h.

**10. N-hop graph traversal with risk decay**
Full graph analysis: trace up to N hops from the wallet, calculate a risk score that decays with distance. "This wallet received funds 2 hops from a known sanctioned address." Computationally heavy, needs a smart cutoff. Most impressive crypto approach.

**11. Fiat + Crypto unified API**
Single endpoint. Detects input type (wallet address vs name). Routes to appropriate screening path. Returns same MATCH/REVIEW/NO MATCH format. Clean product story.

---

## Extended Risk Signals

**12. PEP (Politically Exposed Persons) screening**
Heads of state, senior officials, their families. Not sanctioned but high-risk. Separate lists. Essentially the same matching problem as sanctions but different data source.

**13. Adverse media screening**
Query a news API for the name. Run a classifier over results: does this person appear in stories about money laundering, corruption, fraud? Combine with sanctions score for a richer risk signal. Dositej's NLP skills apply here.

**14. Beneficial ownership tracing**
UK/EU publish corporate ownership registries. Given a company name, trace back to its ultimate beneficial owner. If that person is sanctioned, flag it. Graph traversal through corporate structures.

---

## Data Infrastructure

**15. Live list ingestion pipeline**
Auto-download OFAC/OFSI/EU/UN list updates daily (or on-demand). Parse the XML/CSV formats, normalize entity records, hot-reload into the search index without downtime. Solves a real operational problem most teams ignore.

**16. Multi-jurisdictional unified index**
Build a single normalized entity index across all four major lists. Deduplicate (the same person often appears on multiple lists). Return which lists matched and with what confidence.

**17. Batch re-screening API**
Existing customers need periodic re-screening as lists update. Accept a bulk list of names/wallets, return verdicts for all. This is how banks actually use these systems.

---

## Product Wrappers

**18. API-first product**
Clean REST API with docs. Simple to demo to a VC judge: `POST /screen` with a name or wallet, get a verdict back. Screenable live on stage.

**19. Dashboard / monitoring**
Real-time view of screening decisions, false positive rate, REVIEW queue depth, average resolution time. Judges can see the system working visually.

**20. ElevenLabs voice integration (tech partner)**
Analyst speaks a name, system screens it. Or: analyst reviews a case by voice. ElevenLabs is a tech partner — using them may earn favor with organizers.

**21. Embeddable React widget / SDK**
Drop-in component a fintech can embed in their payment flow. Pavle can build this in React. Shows product thinking.

---

## Hardest / Most Impressive (High Risk)

**22. Shell company / alias graph**
Build a knowledge graph connecting entities: individuals → companies they control → aliases they use. Flag a payment if the recipient is a known shell for a sanctioned person.

**23. Sanctions evasion pattern detection**
Train a classifier to detect deliberate evasion patterns: slightly altered spelling, routing through a sanctioned-adjacent intermediary. Adversarial framing, very compelling story for judges.

---

## Feasibility Matrix

| Option | Effort | Wow Factor | Business Story |
|--------|--------|------------|----------------|
| Embedding fuzzy match + API | Medium | High | Strong |
| Analyst review queue UI | Medium | Medium | Very strong |
| Crypto OFAC lookup + 1-hop graph | Medium | High | Strong |
| Live list ingestion pipeline | Medium | Low | Strong |
| LLM case summary for analysts | Low | High | Strong |
| Unified fiat+crypto API | Medium | High | Very strong |
| N-hop graph traversal | High | Very high | Strong |
| Adverse media classifier | High | High | Strong |
| Beneficial ownership graph | Very high | High | Strong |

---

## Team Skill Map

| Team member | Natural fit |
|-------------|-------------|
| Pavle | Embedding search, LLM pipelines, REST API, React frontend, product framing |
| Dositej | ML model selection/training, NLP classifiers, adverse media, explaining tech to judges |
| Igor | Crypto graph traversal, infrastructure, performance, bloom filters, wallet lookup |
