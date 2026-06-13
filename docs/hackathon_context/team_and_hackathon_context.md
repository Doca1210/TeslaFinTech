# Context: Garaža FinTech AI Hackathon Application (Detailed)

This file is a complete handoff for another Claude instance. It contains the full hackathon context, full CV/background of each team member, and the **exact final text** of every application answer (as submitted), plus style conventions and assessment. The application has **already been submitted**; future help is likely hackathon preparation.

---

# 1. HACKATHON CONTEXT

**Event:** Garaža FinTech AI Hackathon
**URL:** hack.garaza.org
**Organizer:** Garaža (a community of Serbian tech startups; runs Request for Startups, Office Hours, Investor Reports, etc.)
**Contact:** george@garaza.org

## Logistics
- **Dates:** June 13–14, 2026
- **Duration:** 40 hours
- **Format:** In-person ONLY (no remote). All members must travel to Belgrade.
- **Location:** Palata Nauke, Kralja Milana 11, Belgrade, Serbia
- **Application deadline:** June 9, 2026, 23:59 CET — **ALREADY SUBMITTED**
- **Selectivity:** Only **10–12 teams pre-selected**. Competitive.

## Team rules / eligibility
- Teams of **2–4 people** (no individuals).
- **All members must be under 26** (slight leniency for those just turning 26).
- Open to students, AI engineers, first-time founders, PMs, designers, finance professionals from the **Balkan region**.
- Org **strongly encourages mixed backgrounds — finance + engineering combined.**
- Bring your own laptop/equipment; food and drinks provided.

## The challenge
- Every team works on the **SAME FinTech challenge**, revealed **on the day** of the hackathon.
- The problem statement comes pre-defined from the main partner (Sokin) — teams don't ideate the problem; they choose the technology and AI approach to attack it. (This is framed as a feature: no time wasted inventing an idea with no market potential.)
- Org wants solutions at the **AI × finance intersection** that can become **real businesses targeting global markets**.

## Prizes
- 1st: **$5,000**, 2nd: **$3,000**, 3rd: **$2,000** ($10,000 total).
- Distributed as **non-equity grants to legal entities** (or in-app credits if a team has no legal entity). Goal is to help teams kickstart projects.
- **Teams keep all intellectual property.**

## Partners (matter for stack choices and judging context)
- **Main partner:** **Sokin** — UK fintech startup with a Serbia office, ~$165M raised. Provides the problem statement. (Cross-border payments / fintech.)
- **Partners:** **Superteam Balkan** (Web3 / Solana ecosystem community), **Inovo** (European VC), **Day One Capital** (European VC). → VC presence means **business/product framing and investor-facing storytelling matter**.
- **Tech partners:** **ElevenLabs** (voice AI), **Google Cloud**, **Lovable** (AI app builder). → Using these tools may be favored or expected; worth being ready to incorporate them.
- **Community partners:** Palata Nauke, ETF (Elektrotehnički Fakultet), GDG Belgrade, Netokracija, Digital Serbia Initiative, IRC FON, RAF, {c}ontext (Insightful), ProtoNETF.

## Strategic implications (carried through the whole application)
- The hidden challenge means the application could NOT be about a specific idea — it was about **why this team is the right one**: technical strength, complementary skills, ability to ship in 40 hours, and fintech awareness.
- "Real businesses targeting global markets" + VC partners → they value **commercial/founder thinking**, not just a tech demo.
- The org's stated preference for **finance + engineering mixed teams** is the team's one structural weakness (all three are engineers). Mitigated via Pavle's fintech project + Algo Trade history + Igor's crypto/security background.
- At a fintech hackathon with VC judges, the team that wins is usually the most technical team that ALSO tells a clean business story. Pitch + demo ownership should be decided early.

---

# 2. TEAM CV CONTEXT (full detail)

3-person team. All from University of Belgrade, School of Electrical Engineering (ETF). All under 26. Belgrade-based.

## Pavle Prodanović
- **Email:** pavle.prodanovic249@gmail.com | **Phone:** +381 60 491 9009 | GitHub + LinkedIn (in CV)
- **Location:** Belgrade, Serbia
- **Education:** University of Belgrade, ETF — BSc in Computer Engineering and Informatics (Oct 2020 – Sept 2024)
- **Awards:** Extremely Gifted Students Scholarship (2020–2023); 4th place National Programming Competition (2020)
- **Team role:** Backend architecture + AI integration; de facto product/commercial lead; most frontend capability (React/React Native/Figma)

**Skills:**
- AI: Vector search & embeddings (Milvus), AI agent orchestration (Google ADK), prompt engineering
- Languages: Go, Python, C++
- Frontend: TypeScript, React, React Native, Figma
- Databases: PostgreSQL, Redis, MongoDB, ScyllaDB
- DevOps: Docker, Kubernetes, RabbitMQ, AWS (Athena, S3), GitHub Actions
- Observability: Prometheus, Grafana

**Experience:**
- **Medior Backend Developer, Nano Interactive (May 2025 – present):**
  - Built a pipeline turning unstructured movie/TV/podcast titles into ad-tech targeting signals: scrapes film databases for metadata/posters/ratings, orchestrates LLM enrichment to generate intent prompts, vectorizes and matches against campaign segments. ~176M requests/day.
  - Boosted client acquisition by 17% via an analytics system across multiple DB sources (Athena, MySQL, Milvus).
  - Created the App Intelligence platform powering all app traffic targeting (~67.5M daily requests): resolves raw app IDs across Apple/Google/Roku/Amazon, async metadata fetch + LLM enrichment → campaign-ready segments.
- **Tools Developer, Wargaming (June 2023 – May 2025):** pathfinding tool (Dijkstra, 3D) for map balancing; modern version control system for in-house editor; mentored an intern.

**Projects:**
- **PolyCopyBrain** (Go, React, AI agents; Mar 2026 – present): Polymarket copy-trading platform. Multi-stage pipeline: automated trader discovery via Polymarket Analytics API, data fetch (positions/trades/markets), custom metrics engine (Sharpe Ratio, HHI, MLF, Kelly Criterion deviation, FIFO-weighted hold times). Multi-agent pipeline (Google ADK) produces a copy/skip verdict. Rule-based "Gatekeeper" filters non-copyable traders before LLM analysis to cut cost/noise. **This is the team's strongest direct fintech signal.**
- **Daily Gamles** (React Native, TypeScript, Go, PostgreSQL, Figma; Oct 2025 – Jan 2026): mobile mini-games platform (Wordle, Contexto, etc.), full cycle, deployed to Hetzner + Google Play.
- **2D Tanks Strategy Game** (Python, PyGame): multiplayer game where players program bots; team of 3, won 1st place for best bot.

## Dositej Cvetković
- **Email:** doscve@gmail.com | **Phone:** +381 614477144 | LinkedIn in CV
- **Location:** Vidikovacki Venac 94, Belgrade
- **DOB:** 16/04/2001 (~25)
- **Education:** ETF, University of Belgrade — MSc in progress (Signals & Systems, from Nov 2025); BSc Signals & Systems (2020–2025, final grade 9.14)
- **Languages:** Serbian (native), English C2/C1, French A2
- **Team role:** AI/ML specialist (model selection, training, tuning); translates technical work for non-technical audiences; backup backend (FastAPI/PostgreSQL)

**Skills:** Python; AI platforms (PyTorch, TensorFlow, TensorRT, ONNX Runtime); deep learning; databases (MongoDB, MySQL, PostgreSQL); MATLAB/Simulink; Linux

**Experience:**
- **Software Engineer, EPAM (Oct 2025 – present), Belgrade**
- **Computer Vision Intern, Vlatacom (Feb 2025 – Aug 2025):** crowd counting via thermal imaging (estimating crowd sizes at large public gatherings incl. student protests in Serbia); fine-tuned deep learning models for human detection in thermal imagery; domain adaptation of pretrained nets to thermal data; integrated detection with multi-object tracking (MOT); reduced double counting; privacy-preserving low-visibility estimation; deployed neural nets on Hailo AI accelerator for edge inference. Tech: Python, PyTorch, YOLO, HailoAI.
- **Python Summer Internship, EPAM (Jun–Aug 2025):** e-commerce bookstore backend from scratch; Scrum/Agile; RESTful APIs with FastAPI; data models/business logic; Git, code reviews. Tech: Python, FastAPI, Git, PostgreSQL, SQLAlchemy.

**Other experience / projects:**
- Formula Student team Road Arrow (drivetrain & battery subteam): battery cell selection/config, fuse ratings, helped qualify team.
- XIII Spring School on Clinical Engineering (Trieste, 2025); Python Summer School RT-RK (2023).
- Project: pipeline for extraction of visually evoked potentials (ERP/P300, EEGLAB).
- Project: control & trajectory planning of a 2-DOF robot (feedforward torque + PD feedback).
- Project: hydraulic actuator modeling (state-space, trapezoidal velocity profile).
- **HackUPC:** embedded AI / sensor fusion — tree-health monitoring + "interaction" system on Arduino UNO Q; LLM-based interactions driven by sensor data; low-power inference under tight constraints.
- **201:GO! Hackathon (Hub201):** Outlook plugin for spam mail detection.
- **Hobbies:** cycling, skiing, reading, mountain rescue training.

## Igor Antonijević
- **Email:** igorantonijevic15@gmail.com | **Phone:** +381 63 759 68 11 | LinkedIn + github.com/IgorAnton
- **Location:** Belgrade, Serbia
- **Education:** ETF, University of Belgrade — MSc Software Engineering (Oct 2024 – present); BSc Electrical & Computer Engineering (2020–2024, module Computer Engineering & Information Theory; thesis: simulation of Kyber post-quantum key-encapsulation algorithm). High School of Electrical Engineering Nikola Tesla (Computer Networks Admin); competition placements; gifted-students scholarship.
- **Languages:** English, Serbian, Russian, German
- **Team role:** Infrastructure, performance, security/crypto (deployment, reliability under load, the trust side any fintech product needs)

**Skills:**
- C#, .NET Core/Framework, Azure, virtualization, Docker, Kubernetes, SQL Server, SQLite, Git, GitHub Actions, CI/CD, Prometheus, Grafana, DataDog, backend & distributed systems
- C/C++, STL, x86, RISC-V, QEMU, ARM, OpenMP, OpenGL, embedded systems, OS dev (xv6), Linux device drivers, STM32, Makefile, GCC, GDB, CMake, Valgrind, eBPF, XDP, POSIX
- Go, Python, Java, Raft, Kafka, Redis, microservices
- Algorithms & data structures, competitive programming, mathematics, cryptography, compilers

**Experience:**
- **Software Development Engineer, Wärtsilä (Feb 2024 – present):** Fleet Optimization Solution (ship usage/maritime travel optimization for decarbonization + safety); high-throughput backend/distributed systems (C/C++, C#, .NET, SQL Server, SQLite, Docker, k8s, microservices, Azure, Kafka, Redis, Linux); developed/optimized 7zip/LZMA library for high-frequency IoT sensor data; protocol to minimize vessel satellite data usage; Scrum/Agile with SAFe 6.0.
- **Embedded Software Engineer, Beoavia (Oct 2023 – Feb 2024):** LTE comms firmware for ground-to-drone communication (commands + telemetry); drone parameter control; STM32 + UBlox via UART (C/C++, FreeRTOS, HAL).
- **Software Engineer Intern, Quiddita (Jul–Oct 2023):** backend API for storing/fetching m-ary trees in MS SQL (.NET/C#, NHibernate); efficient large-tree storage algorithm.

**Projects:**
- **High Performance Message Broker (Sept 2025 – present):** bypasses Linux networking stack to maximize throughput (XDP hooks + eBPF), low-level packet processing at the NIC, used for pub/sub + message queues. Tools: C/C++, Go, XDP, eBPF, LLVM.
- **Custom GNU-like Assembler, Linker & Emulator (Sept 2023):** custom toolchain for an ARM/RISC-like assembly language; Flex/Bison; custom ELF-like format; CPU emulation.
- **Custom OS kernel (Aug 2022):** memory management, multithreading, scheduler, console I/O; for RISC-V; xv6, QEMU.
- **Compiler for Micro-Java (Feb 2024):** lexer/parser/grammar + small JVM-like VM; Java, JFlex, CUP, Ant.

## Collaboration history (for "have you worked together")
- All three have prior hackathon experience.
- **Pavle + Dositej** built a trading bot together at the **Algo Trade hackathon, Zagreb 2025** (direct fintech + same-team proof).
- Igor participated in a **Tech+FPGA hackathon** (Piano Tiles on FPGA hardware) and has built with teammates before.
- **OPEN ITEM TO VERIFY:** exactly who was on which prior team, so collaboration claims across the three answers don't contradict each other.

---

# 3. APPLICATION QUESTIONS & FINAL ANSWERS (exact submitted text)

## Q1. "What's their superpower — the one thing they're genuinely better at than 90% of people their age?" (plus member email/LinkedIn/background/role, and whether they've worked together before)

**Pavle:**
> My superpower is taking huge amounts of messy, raw data and turning it into signals you can actually trust — at real production scale. At Nano Interactive I build pipelines that handle 176 million requests a day: scraping unstructured content, running it through LLMs, and turning it into ad-tech targeting signals that clients pay for.
> I'm now pointing that same skill at finance with my own project, PolyCopyBrain. It screens thousands of trader accounts, computes quantitative risk metrics, and runs them through a multi-agent pipeline that spits out a clear copy-or-skip verdict on each trader. Not many people my age have built LLM-driven data systems at this scale — and even fewer have aimed them straight at financial decisions.
> On the team I'd own backend architecture and AI integration.

**Dositej:**
> My superpower is juggling many demanding things at once without ever letting the quality slip — and I do it better than anyone I know. In a single month I finished my final exams, defended my bachelor's thesis, worked full-time, and got through mountain rescue training, all at the same time. That ability to stay sharp when everything's happening at once is exactly what a 40-hour build needs.
> On the team I own the machine learning: model selection, training, and tuning. I'm also the one who can take something technical and make it land clearly for a non-technical audience.

**Igor:**
> My superpower is being completely stack-agnostic. I'll pick up whatever technology the problem needs and find a way to ship it in the short timeframe. I've worked across distributed backends, embedded firmware, and kernel-level networking. I go low-level or high-level, whatever gets the job done.
> On the team I own infrastructure, performance, and security: deployment, and making the system fast, reliable, and secure under load — the trust side any fintech product needs.

## Q2. "What's the thing you've built with AI that you're proudest of? Describe the most technically challenging thing you've worked on in the last 12 months (non-AI allowed). What did you have to learn that you didn't know before, and how did you figure it out?"

**Pavle:**
> The thing I'm most proud of is the Cinema & App Intelligence systems I built at Nano Interactive. We enrich ad data for Connected TV (CTV) and mobile apps. Advertisers send us only the ID of an app or sometimes title of the content (movie, tv show, podcast name). With only that information our goal is to enrich that data and convert it into ad-tech signals, without gathering user information.
> For example: Nike wants to reach young, active people who care about fitness. My two systems show them exactly where their ad will run, alongside sports content and inside fitness apps like Strava, purely from content and app context.
> The hard part wasn't the scraping, it was making an LLM produce signals reliable at this scale (200-300M daily in total). I had to learn how to keep prompts consistent across millions of varied inputs, and a lot of the production side I picked up on the way: prompt batching, system prompt caching, and other cost reductions plus proper testing and A/B testing to know the signals actually held up. I figured it out by iterating on prompts and comparing outputs against real campaigns until they were stable.

**Igor:**
> The most technically challenging thing I've built recently is a high-performance message broker that operates at layer 3 of the OSI stack on Linux, using Go, C++, eBPF and XDP. The idea is to bypass the entire kernel networking stack so pub/sub packet distribution is far faster than standard layer-7 brokers like Kafka.
> What I had to learn was a whole layer of the system I'd never touched: eBPF and XDP, which let you process packets the moment they arrive at the NIC, before the OS networking stack gets involved. It's almost a field of its own. I figured it out by digging through the Linux networking internals, reading kernel and XDP documentation, studying existing eBPF programs, and benchmarking my broker against standard ones to see whether the bypass actually paid off.

**Dositej:**
> The AI project I'm most proud of was my bachelor thesis and internship work on crowd counting in thermal video streams. The goal was estimating the number of people in large gatherings using thermal cameras, especially in low visibility conditions where RGB cameras fail. What made it meaningful was that it gives objective crowd estimates while preserving privacy, since thermal data doesn't reveal identities.
> The hardest part was adapting modern crowd counting methods, which are usually trained on RGB data, to thermal imagery, where textures and visual cues are completely different. I started with density map methods, but their localization on thermal data was weak, so after reading papers and benchmarking I switched to P2PNet, which predicts point locations directly instead of density maps.
> I had to learn a lot from scratch: transfer learning for domain adaptation, annotation strategies for thermal datasets, training stability, and how to debug a deep learning pipeline when the bug could be in preprocessing, labels, or the model itself. I figured it out by reading papers, reproducing results, visualizing intermediate outputs, and changing one thing at a time instead of everything at once. Eventually I fine tuned the network to get accurate localization and counting despite limited, noisy data. It changed how I think about AI: less about training models, more about building robust systems around imperfect real world data.

## Q3. "What's something you've built or worked on just because you found it fascinating, not because you had to? What rabbit hole did it lead you down and what did you learn?"

**Pavle:**
> This one's PolyCopyBrain, and it started purely as a fascination with trading. It's something I've always wanted to know more about, and I've done deep research about the math behind it: edge, expected value, the metrics that actually separate a good bet from a lucky one.
> I eventually locked in on Polymarket specifically since it was most fun. That is where I noticed the gap: everyone ranks traders by total profit, but profit lies. Someone can look great and just be lucky, or be one oversized bet away from blowing up. What I actually wanted was a way to find traders with a real edge, not lucky ones, so I decided to build it.
> That sent me deep into the quant side I didn't know before: Sharpe ratio, max drawdown, consistency patterns and other metrics that tell you whether someone is genuinely skilled or just riding variance.
> I decided to use the skill I already had: taking messy data and turning it into a real signal. I pull raw trader data, run it through a metrics engine, filter out the obvious junk with deterministic checks, and let an LLM make the final read on who's actually worth copying.

**Igor:**
> During my bachelor's I got pulled into post-quantum cryptography and ended up doing my thesis on simulating the Kyber algorithm for key encapsulation. It's basically how you keep encryption secure once quantum computers can break today's methods.
> The rabbit hole was deep: to implement it I had to actually understand the math behind lattice-based cryptography. I learned why other techniques are vulnerable, how lattice problems resist quantum attacks, and how Kyber turns that into a usable key-exchange scheme. I figured it out by working through the original Kyber specification and academic papers.

**Dositej:**
> One project I built purely out of curiosity was at the HackUPC hackathon: a system for monitoring tree health and "interacting" with trees using sensors connected to an Arduino UNO Q. What fascinated me was combining very constrained hardware with modern AI ideas.
> We integrated multiple sensors, processed noisy environmental signals, and experimented with LLM based interactions driven by the sensor data. That sent me down rabbit holes into embedded systems, signal processing for noisy streams, low power inference, and designing systems when memory and compute are extremely limited. The big lesson: constraints force more creativity than abundance does. You can't brute force a microcontroller, so you have to understand what actually matters in the pipeline, filtering signals efficiently, minimizing latency and memory, and simplifying models while keeping them useful.
> It also pushed me toward robotics and edge AI, because I realized I love building systems where software interacts directly with the physical world.

## Q4. "Have you already participated in hackathons before? Why do you want to join this hackathon?" (+ how many members have prior experience)

**Lead line:** All members participated in multiple hackathons before, and sometimes in the same team.

**Pavle:**
> Yes. I participated in the Algo Trade hackathon in Zagreb in 2025 (with Dositej), where we built a trading bot competing on a simulated stock market. I want to join this event because I'm genuinely into fintech and want to start my own startup one day. I also respect Garaža, and their articles on startups have been really useful for learning about business and how startups work. This would be a great opportunity to kickstart my startup career and meet people with a lot more experience than me.

**Igor:**
> Yes. I've participated in the Tech+FPGA hackathon before where we built a Piano Tiles game running on FPGA hardware with the same teammates, so we already know how to build together under pressure. For this one I'm genuinely excited: it's a chance to solve a real-world problem with industry experts, using AI together with our own skills, under real time pressure.

**Dositej:**
> Yes. I've participated in hackathons before, including HackUPC (embedded AI and sensor fusion on Arduino hardware) and the 201:GO! Hackathon by Hub201 (an Outlook plugin for spam detection). They taught me how to prototype ambitious ideas fast and work well in mixed teams. I want to join this one because fintech is full of the problems I find most interesting: real systems where AI has to be reliable. Finance touches everyone and still runs on outdated infrastructure, so there's real room to build something that matters, alongside industry mentors and a real company problem.

## Q5 (optional). "Have you identified a specific problem you would like to build a product/startup around?"

> Not a specific idea, but all 3 of us are keen to idea of having our own startup one day, and we want to work on it. Mostly we worked on our individual ideas, we did market research, but nothing specific to show off right now.
> Pavle is working on project PolyCopyBrain that is in fintech space, but for this startup we like the idea that we will hear about the problem and have a chance to solve it.

---

# 4. STYLE / VOICE CONVENTIONS
- **First person** for all member answers (consistency matters — never mix "my" and "their").
- **Concise and informal**, human tone, not resume-speak. Contractions OK.
- **No em-dashes or sentence dashes** (user dislikes them). Compound-word hyphens like "ad-tech" / "real-time" are acceptable.
- Always answer **both halves** of two-part questions, especially "what did you learn AND how."
- Back claims with concrete evidence/numbers; avoid generic statements.
- Don't echo the hackathon site's exact wording (Dositej's Q4 lightly does this with "finance touches everyone / outdated infrastructure" — could be reworded to original phrasing).

---

# 5. OBJECTIVE ASSESSMENT GIVEN TO THE TEAM
- **~88–90/100**, high probability of selection.
- **Strengths:** verifiable production experience (not just coursework); complementary, non-overlapping roles (applied ML + production AI/data + low-level systems/security); real fintech signal (PolyCopyBrain, Algo Trade trading bot, Igor's crypto); answered the actual questions including the "what did you learn + how" parts most applicants skip; founder framing fits Garaža's startup/VC context.
- **Main weakness:** no dedicated finance/business person, while the org explicitly prefers mixed finance+engineering teams. Also some homogeneity (all ETF Belgrade, backend/systems-leaning). This is a cohort-composition risk, not a quality problem.
- **If selected — the real build risk is product/market framing and demo storytelling, NOT engineering.** At a fintech hackathon with VC judges (Inovo, Day One), the winning team is usually the most technical team that ALSO tells a clean business story.

---

# 6. LIKELY NEXT STEPS (if continuing)
- Application is submitted. Future help is probably **hackathon preparation:**
  - Decide who owns the **pitch/demo storytelling** and the **UI** (Pavle has the most frontend: React/RN/Figma).
  - Get familiar with the **tech-partner stack**: Google Cloud, ElevenLabs (voice AI), Lovable (AI app builder) — these may earn favor.
  - Practice framing a fintech build **commercially** (problem → user → value → market), since VC judges reward that.
  - Be ready for a **payments / cross-border / financial-data** flavored problem given Sokin's domain.
- **Open item:** verify exactly who was on which prior hackathon team so collaboration claims stay consistent.
