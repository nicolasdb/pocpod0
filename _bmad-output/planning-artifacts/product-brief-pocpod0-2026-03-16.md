---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - "user-provided: Architecture d'apprentissage décentralisée — Synthèse & Plan (inline message)"
date: 2026-03-16
author: Nicolas
---

# Product Brief: pocpod0

## Executive Summary

pocpod0 is a proof-of-concept for a decentralized learning data architecture that replaces the centralized LMS/LRS model with learner-sovereign data pods. It treats xAPI's Actor-Verb-Object structure as what it structurally is — degraded RDF — and builds natively on semantic web standards (RDF, SPARQL, OWL/SHACL) to unlock inference, graph navigation, and cross-domain analytics that xAPI cannot deliver.

The core proposition: **for the first time, every authorized stakeholder sees a coherent, complete picture of a learner's journey — across institutions, across time, across activities — because the data belongs to the learner, not the institution.** Today, a tutor can't fluidly see cross-institutional progress. A parent gets a report card twice a year. When a student changes schools, the data stays behind. Regional authorities fund extracurricular programs with zero visibility on outcomes. Each role looks through a keyhole at a fragment of the same learner's journey.

The PoC validates this architecture through a concrete demo sequence: ingest a synthetic xAPI dataset, prove lossless conversion, immediately demonstrate insights impossible with xAPI alone (latent competency inference, cross-role visibility, cross-institutional pattern detection), and unleash an adversarial troll agent against categorized attack surfaces — proving not invulnerability, but architectural maturity and honest understanding of where defenses hold and where investment is needed.

xAPI serves as both import and export format — a migration path, not a migration wall. Institutions can feed existing xAPI data in and immediately benefit from richer analytics, while maintaining backward compatibility with institutional LRS. The transition upgrades the existing stack rather than adding yet another layer on top.

The project follows a fog-of-war methodology: each phase reveals new options, questions the path, and surfaces decisions. Evidence-first engineering — build the case with simulated scenarios before committing real users.

---

## Core Vision

### Problem Statement

Learning data is institutionally captured, structurally impoverished, siloed between roles, and privacy-hostile by default. SCORM tracks pass/fail. xAPI tracks richer events but stores them in centralized LRS silos the learner doesn't control. The xAPI statement format mimics RDF (Subject-Predicate-Object) without delivering RDF's capabilities — no inference, no graph queries, no semantic linking. Every analytics layer built on xAPI is custom engineering from scratch.

The deeper problem is the **silo between roles**. A tutor doesn't have fluid access to student progress across contexts. A parent sees fragments. When a student changes schools, data stays behind. Regional authorities funding extracurricular activities have no visibility on outcomes. The K-12 ecosystem compounds this with a fragmented standards landscape (OneRoster, Ed-Fi, LTI, xAPI) where every integration is bespoke.

Meanwhile, xAPI captures geolocation, biometrics, and device IDs with zero native privacy governance — and education involves minors, making this the most demanding regulatory environment.

### Problem Impact

Learners have no sovereignty over their own learning history. Every stakeholder — tutor, parent, school, next school, regional authority — sees only their own fragment. Institutions build expensive custom analytics that remain siloed. Privacy compliance is bolted on after the fact rather than architected in. The gap between what learning data *could* reveal (latent competencies, cross-institutional patterns, personalized recommendations) and what current tooling *actually* delivers grows wider with each new standard layered on top.

### Why Existing Solutions Fall Short

xAPI improved on SCORM's binary tracking but inherited the centralized, institution-controlled data model. LRS vendors add analytics dashboards but these are proprietary layers on a structurally limited format. No existing solution gives learners control of their own data. No existing solution breaks the role silos — every system serves one institutional perspective. No existing solution treats learning events as first-class semantic graph nodes capable of inference and cross-domain linking.

### Proposed Solution

A three-layer architecture anchored in learner sovereignty:

- **Solid Pods (CSS)** — raw learning artifacts under exclusive learner control, with granular ACLs. The source of truth and legal proof.
- **Oxigraph** — persistent RDF triplestore for structured facts, SPARQL queries, and OWL/SHACL inference. The analytical engine.
- **Qdrant** — vector embeddings of semantically significant content, linked back to Oxigraph URIs and Pod resources. The semantic bridge.

An **OpenClaw agent layer** provides the agentic LLM runtime — simulating roles (tutor, student, parent, admin) for the PoC, executing SPARQL queries via a shared skill, and powering the adversarial troll agent. Discord integration is the human interface layer for later phases when real users are involved.

A **xAPI ingestion pipeline** converts existing institutional xAPI data into native RDF, proving lossless conversion and immediately unlocking richer analytics. xAPI export preserves backward compatibility.

A **data lifecycle & governance layer** manages:
- **Soft-delete** (30-day bin) → **hard-delete** (consent ceremony with strong confirmation protocol) → **nightly cascade propagation** to Oxigraph and Qdrant
- **Temporal versioning** of triples (learning progress is growth, not just state), replacement of embeddings, archival of Pod resources
- **Programmable governance contracts** (Solid-native, multisig pattern) for ownership lifecycle: minor/guardian shared control, age-based transfer to adult learner (per EU residence), inheritance/testament, voluntary transfer to NGO/foundation

A **mission control dashboard** serves dual purposes: dev monitoring during development (logs, raw metrics, propagation status, deletion bin) and presentation mode for demos and funders (role-based scenario panels, troll attack results live).

### Key Differentiators

- **Sovereignty-native**: Solid Pods give learners real, granular, RGPD-compatible control — not a privacy dashboard on someone else's database.
- **Silo-breaking**: Every authorized stakeholder sees a coherent picture of the learner's journey across institutions, time, and activity types. The tutor sees cross-institutional progress. The parent gets a real synthesis. The next school gets instant context. The region sees program outcomes.
- **Semantically native**: RDF/SPARQL/OWL from the ground up means inference, pattern detection, and cross-domain linking are architectural capabilities, not custom builds.
- **Migration path, not migration wall**: xAPI import + export means institutions upgrade without ripping out existing infrastructure.
- **Designed for the hardest compliance case first**: K-12 with minors under EU RGPD + AI Act. If the architecture passes here, healthcare, corporate training, and professional certification are easier variants. Design for neurodiversity = design for everyone. Design for the hardest compliance = compliant for all.
- **Programmable data governance**: Multisig governance contracts handle minor/guardian transitions, inheritance, voluntary transfer — knowledge sovereignty that extends beyond the individual's lifetime.
- **Evidence-first validation**: Adversarial troll agent with categorized attack surfaces (ACL enforcement, SPARQL injection, cross-inference, vector privacy, deletion timing, contract forgery) — demonstrating honest architectural maturity, not perfection claims.
- **Matryoshka growth model**: Each PoC phase is nested inside the next — not sequential steps left behind, but shells that the next phase grows around.

### Compliance Architecture (Known & Unknown)

**RGPD — Strong positioning, gaps identified:**
- Rights to access, erasure, portability are architecturally native via Solid Pods
- Cascade deletion (Pod → Oxigraph → Qdrant) requires provenance tracking per-source and nightly propagation pipeline
- Derived data (triples, embeddings) classification as processing vs. new data — needs legal clarification
- Anonymization vs. pseudonymization for aggregate regional queries — re-identification risk must be assessed
- Children's data (Art. 8): Pod ownership for minors handled via governance contracts, but age thresholds vary by EU member state

**AI Act — High-risk classification acknowledged:**
- Education is Annex III high-risk domain. Agent recommendations and assessments trigger full obligations.
- Transparency: AI-generated insights must be disclosed as such
- Human oversight: Mission control dashboard designed to serve this requirement
- Explainability advantage: OWL inference chains are more transparent than neural network reasoning
- Embedding opacity: Qdrant embeddings are not interpretable — risk of PII leakage via semantic similarity needs research

**Known unknowns for research phase:**
- PoC with synthetic data likely exempt from AI Act obligations, but architecture must be designed for compliance transition
- Cross-border learner mobility: jurisdictional differences in national RGPD implementations
- Embedding PII leakage: can private content be recovered via semantic similarity with known content?
- Guardian disagreement scenarios in multisig contracts

---

## Target Users

### Primary Users (Data Consumers)

**Persona 1: Claire — Secondary School Teacher (Flanders)**
Claire teaches math and science at a secondary school in Brussels using Smartschool. She has 120 students across 5 classes, some transferring from French-speaking schools mid-year with zero learning history. She spends ~3 hours/week manually compiling progress notes and reporting. She currently cannot see what extracurricular math tutoring her struggling students receive (funded by the Gemeente), nor access prior school records beyond a thin DISCIMUS transfer. Her "aha moment": asking the system "which students are struggling with concept X across all their learning contexts?" and getting an answer that includes school, tutoring, and self-study data — in seconds.

**Persona 2: Marc — School Administrator / IT Coordinator (Wallonia)**
Marc manages a school in Liège running Happi for admin and Teams for classwork. No xAPI, minimal SCORM (only from Bingel exercises). Student transfers between schools mean re-entering everything by hand. Compliance reporting for the Fédération Wallonie-Bruxelles is a quarterly ordeal of compiling PDFs. His pain: 25% of admin staff time goes to data re-entry and reporting. His "aha moment": a student transfers in and their learning profile is instantly available — with parental consent visible and auditable.

**Persona 3: Isabelle — Regional Education Policy Advisor (Brussels-Capital)**
Isabelle oversees publicly funded extracurricular education programs across Brussels. She needs to assess outcomes to justify budgets, but currently receives Word/PDF narrative reports from providers with self-reported participant counts. She cannot connect program participation to actual learning outcomes. Cross-community visibility (NL/FR) is nonexistent. Her "aha moment": querying "what is the measurable impact of after-school STEM programs on participating students' school performance?" and getting an evidence-based answer aggregated from learner pods — anonymized, consent-verified. This is a policy-level demo: currently unanswerable by anyone in Belgium.

### Secondary Users (Sovereignty Beneficiaries)

**Persona 4: Fatima — Parent of Two (Brussels, bilingual household)**
Fatima has one child in a Flemish school and one in a French-speaking school. She uses Smartschool for one and Happi for the other. She gets report cards twice a year and sporadic messages in between. She cannot see a unified picture of her children's progress, nor what the publicly-funded robotics workshop is actually teaching them. Her "aha moment": one view, both children, all contexts — school, extracurricular, tutoring — with her controlling exactly who else can see what.

**Persona 5: Ayoub — 16-year-old Student (Brussels)**
Ayoub doesn't think about data sovereignty — he thinks about grades, friends, and basketball. His pod exists because his school and parents set it up. He barely notices it. But when he transfers from a Flemish school to a French-speaking one for his last two years, his learning history follows him seamlessly. When he turns 18, governance control shifts to him automatically via the programmable contract his parents signed at pod creation. His "aha moment" comes years later when he applies for university and his complete, verified learning portfolio is available in one click. **Future opportunity (not PoC):** making the pod valuable to teenagers on their own terms — verified skills portfolio for summer jobs, coaching hours as civic engagement credit. "My stuff, my proof, my flex."

### Tertiary / Ecosystem (Future Scope)

**Extracurricular Providers** — sports clubs, arts academies, language schools, STEM workshops funded by public money. They push participation and outcome data to learner pods. They benefit from being visible in the learner's graph. Currently reporting via paper/PDF.

**Athumi / Government Infrastructure** — not a user, but a deployment partner. The Flemish Solid infrastructure (Athumi/Vlaams Datanutsbedrijf) could host pods at scale. OSLO education vocabularies (data.vlaanderen.be) provide the RDF schemas. Alignment here is strategic — all learning events modeled using OSLO vocabularies ensure native compatibility with Flemish government data infrastructure.

**Traq.be and Similar Startups** — early-stage Belgian players exploring the education-health-family data bridge. Connected to UGent/imec/Athumi ecosystem. Network effect allies: more services writing to Solid pods = richer data for everyone. Potential integration partners rather than competitors.

**Community Pods** — the same Pod + governance architecture extends to institutional use. A school pod with role-based access: accounting has CRU access, budget expenses are RO for parents (transparency), directors inherit logs from predecessors via governance contracts. This is the same primitive — individual pod, community pod, same pattern.

### Platform Primitive Vision

The Pod is not a product — it is a **platform primitive**. Like S3 is to AWS, the Pod is the foundational data layer upon which an ecosystem of services can be composed. An "LMS à la carte" — modular, configurable to each school's needs, built on top of learner and community pods as data sources. This ecosystem play is out of PoC scope but is the strategic endgame the PoC unlocks.

### Data Ingestion Tiers

| Tier | Source | Method | PoC Scope |
|------|--------|--------|-----------|
| **Tier 0** | Synthetic dataset | Hand-crafted xAPI → RDF | Yes — PoC validation |
| **Tier 1** | xAPI-producing systems | Direct ingestion pipeline | Architecture proven by Tier 0 |
| **Tier 2** | SCORM-producing systems (Bingel, Scoodle) | SCORM-to-RDF converter | Future |
| **Tier 3** | Proprietary platforms (Smartschool, Happi) | Per-platform API connector | Pilot phase (Smartschool first, ~90% Flemish market) |
| **Tier 4** | Manual/paper-based | Structured data entry interface | Future — data capture UX |

Data capture, collection, and validation UX is a full avenue unlocked by the PoC but deliberately out of scope. It addresses the learning experience design problem — how data enters the system in the first place.

### User Journey (PoC Scope)

The PoC simulates these personas via OpenClaw agents to validate the architecture before involving real users:

| Phase | What Happens | What It Proves |
|-------|-------------|----------------|
| **Ingest** | Synthetic xAPI dataset imported, mapped to RDF via OSLO vocabularies, stored in Oxigraph with provenance linking to Solid Pods | Lossless migration, no data left behind |
| **Query** | Simulated Claire asks cross-context question; simulated Isabelle asks aggregate impact question; simulated Fatima asks unified child view | Silo-breaking analytics, role-based access |
| **Transfer** | Simulated Ayoub transfers from NL school to FR school; new school queries his pod | Cross-community data portability works, ACLs respect the new school's access grant |
| **Protect** | Troll agent attacks ACLs, attempts SPARQL injection, cross-inference, vector privacy leaks, deletion timing exploits | Privacy architecture holds under adversarial pressure |
| **Govern** | Simulated Ayoub's pod governance shifts at age threshold; simulated deletion cascade propagates correctly; community pod director succession tested | Data lifecycle and programmable governance contracts work |

Each simulated scenario that passes builds the evidence case for moving to a small pilot with real users — likely one Brussels school, one extracurricular provider, and a handful of willing families.

### Competitive Landscape

| Player | What They Do | Relationship to pocpod0 |
|--------|-------------|------------------------|
| **Inrupt (ESS)** | Enterprise Solid Server (ESS), Data Wallet. Enterprise pricing, Kubernetes. Government/finance focus, no education deployments. | Infrastructure provider, not competitor. Community Solid Server for PoC, ESS for scale. |
| **Athumi** | Flemish government Solid infrastructure at citizen scale. Education on roadmap, not yet deployed. | Strategic alignment partner. OSLO vocabularies + Pod hosting. |
| **SolidLab (imec/KU Leuven/UGent)** | Solid ecosystem research. | Research collaboration opportunity. |
| **Traq.be** | Belgian startup, "lifelong digital backpack" bridging education-health-family. Early stage, connected to UGent/imec/Athumi. | Ecosystem ally. Network effect: more Pod services = more value. |
| **Smartschool** | Dominant Flemish LMS (~90%). Proprietary. | Tier 3 connector target for pilot phase. |
| **xAPI/LRS vendors** | Centralized learning record stores. | Our import/export compatibility layer. Migration source, not competitor. |

### Funding Avenues

- **Athumi partnership/pilot program** — Flemish government, most advanced Solid adopter globally
- **EU Digital Education Action Plan** — funding calls for education data innovation
- **Horizon Europe** — digital education and data spaces clusters
- **VLAIO** (Flanders Innovation & Entrepreneurship) — R&D subsidies
- **Belgian Recovery and Resilience Plan** — education digitalization budget

---

## Success Metrics

### PoC Quantitative Benchmarks

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Ingestion scale** | 10,000+ synthetic xAPI statements | Realistic school semester: 5 classes, 120 students, 15 weeks of activity |
| **Query latency (simple SPARQL)** | < 500ms | Sanity baseline — if we can't hit this at PoC scale, something is architecturally wrong |
| **Query latency (hybrid SPARQL+vector)** | < 2s | Generous threshold establishing baseline for optimization |
| **Pod count** | 5 individual + 1 community (school) | Enough to test ACL complexity without infrastructure bloat |
| **Troll attack categories tested** | Minimum 4 (ACL, SPARQL injection, cross-inference, vector privacy) | Categorized, not exhaustive — deferred surfaces explicitly documented |

### PoC Success Criteria (Evidence-First)

The PoC succeeds when it produces a self-balancing body of evidence — each proof reinforcing the others. Not every attack surface needs testing, but the scope and what is deliberately deferred must be explicitly acknowledged.

**Architecture Proof:**
- Synthetic xAPI dataset ingested with zero data loss (every original xAPI statement recoverable from the RDF graph)
- OSLO-mapped triples in Oxigraph produce at least 3 queries impossible with xAPI alone (cross-context, inference, aggregate)
- Qdrant embeddings linked to Oxigraph URIs and Pod resources with full bidirectional traceability
- Nightly consolidation routine runs: deduplication, versioning, cascade deletion propagation

**Silo-Breaking Proof:**
- Simulated tutor agent queries cross-institutional student progress and receives a coherent answer
- Simulated parent agent sees unified view across two schools and one extracurricular provider
- Simulated regional agent queries aggregate anonymized program impact
- Simulated student transfers between NL and FR schools with learning history intact

**Security & Governance Proof:**
- Troll agent report with categorized attack surfaces: ACL enforcement, SPARQL injection, cross-inference, vector privacy, deletion timing
- Each category rated: pass (out-of-the-box), partial (mitigations identified), fail (investment needed)
- Honest acknowledgment of deferred attack surfaces with rationale
- At minimum, ACL enforcement and SPARQL injection must pass; probabilistic surfaces (cross-inference, vector privacy) must be assessed with findings documented
- **Troll agent report is a deliverable:** structured, comprehensible to a non-technical funder

**Governance Contract Proof:**
- At least one programmable governance contract demonstrated (minor/guardian → adult transfer)
- Soft-delete → hard-delete cascade propagation verified end-to-end

**Funder Conviction Criteria:**
- Mission control dashboard operational in both dev and presentation mode
- Complete demo narrative runnable end-to-end: ingest → query → transfer → attack → govern
- Deferred scope explicitly documented with rationale (not hidden)
- Architecture proven compatible with Athumi/OSLO ecosystem

**Definition of Done per PoC Phase:**

| Phase | Done When |
|-------|-----------|
| **Ingest** | 10K+ xAPI statements in Oxigraph as OSLO-mapped RDF, provenance links to Pods verified, any original statement recoverable |
| **Query** | 3+ cross-context queries return correct results under 500ms, role-based access enforced per query |
| **Transfer** | NL→FR school transfer scenario completes, new school sees full history, old school access revoked |
| **Protect** | Troll report generated with all tested categories rated, ACL + SPARQL injection pass, report readable by non-technical reviewer |
| **Govern** | Age-based governance transfer executes, deletion cascade propagates to all three layers within one nightly cycle |

### Patient Zero: Personal Side Quest

Nicolas's evidence-based portfolio (nicolasdb.netlify.app) uses the same architectural pattern: timestamped knowledge blocks, confidence scores, skill trajectory indicators. Post-PoC, Nicolas builds his own pod and bridges evidence blocks to his portfolio — demonstrating cross-domain applicability beyond education. This is a personal side quest, out of PoC scope, but validates that the architecture is domain-agnostic. If the same pod model produces a professional evidence-based portfolio, the primitive is proven universal.

### Pilot Success Criteria (Post-Funding)

Target pilot: partnership with Eduvik (tutoring platform, Brussels) + one school + willing families. Eduvik sits at the tutor-parent-student intersection, cares about transparency and outcomes, and currently has zero data infrastructure to prove tutoring impact.

**Pilot proves real-world viability when:**
- Eduvik tutors can see student progress from school context (with parental consent) — reducing "starting from zero" at each session
- Parents see tutoring impact integrated with school performance in their child's pod
- At least one data ingestion connector works with a real platform (Smartschool or Eduvik's system)
- Real users (not simulated agents) successfully manage consent: grant, revoke, verify
- No privacy incident — troll agent suite passes against real (not synthetic) data

**Pilot is a "learning failure" (still valuable) if:**
- Architecture holds but UX/onboarding is too complex for non-technical users
- Consent management is correct but unintuitive for parents
- Data quality from real sources is too inconsistent for meaningful inference

### Strategic Success (12+ Month Horizon)

**Propagation model:** Eduvik → parents/learners → schools → extracurricular providers → regional services. Bottom-up adoption driven by demonstrated value, not top-down mandates.

**Strategic indicators (directional, not OKR-precise — fog of war acknowledged):**
- Solution (name TBD) recognized as valid, safe, and cross-compliant (RGPD + AI Act)
- Eduvik integration operational and producing real cross-context insights
- At least one additional service building on the pod ecosystem (network effect begins)
- Athumi or equivalent government partner engaged for infrastructure alignment
- Business model clarified through pilot learnings

### Business Model (Deliberately Unresolved)

The PoC does not need to answer the business model question. It needs to prove the primitive works so the question *can* be answered with evidence. Options on the table:

| Model | Description | Analogy |
|-------|-------------|---------|
| **Infrastructure provider** | Host and manage pod+graph+vector for institutions | AWS for education data |
| **Certification authority** | Certify systems as compliant with the pod standard | SSL certificate model |
| **Standard body** | Define the specification for learning data on Solid; revenue from certification, reference implementations, consulting | W3C / ADL (xAPI) model |
| **Open-source core + paid modules** | Primitive is free, integrations and analytics are paid | Odoo model |
| **Integration services** | Build connectors between existing systems and pods | Consulting/SaaS hybrid |

The pilot phase should generate evidence for which model (or combination) is viable. This is a strategic decision to be made with data, not assumed upfront.

---

## MVP Scope (PoC = MVP)

The PoC is the MVP. There is no separate product MVP — the PoC either builds the evidence case and unlocks funding, or it doesn't. Scope follows the fog-of-war principle: the walking skeleton is the hard boundary, everything else is backlog revealed by execution.

### Core Features (Walking Skeleton — Hard Boundary)

**Phase 1 — Infrastructure**
- `docker-compose.yml` with Community Solid Server, Oxigraph, Qdrant, Nginx — all services responding with correct headers
- Pin all container image versions (no `latest` tags — prevents random breakage)
- 5 individual Solid Pods + 1 community Pod (school) provisioned via Community Solid Server API
- ACLs configured per role (tutor, parent, student, admin, regional)
- Nginx reverse proxy with Linked Data headers for Community Solid Server (content negotiation for `text/turtle`, `application/ld+json` — budget real time for this, it's a known friction point in Solid deployments)
- **Phase 1 checkpoint:** Troll agent tests ACLs immediately. If ACLs are broken at the Pod level, discover it before investing in Phase 2. Fail fast.

**Phase 2 — Data & Intelligence**
- Synthetic xAPI dataset (~10K statements, realistic school semester)
- **OSLO vocabulary schema document** — explicit mapping contract between the data layer and the agent layer. Defines the RDF vocabulary used. Doesn't need to be perfect, but must be explicit. This is the contract Phase 3 agents depend on.
- xAPI → OSLO-mapped RDF ingestion pipeline (lossless, every statement recoverable)
- Triples stored in Oxigraph with provenance linking to source Pod resources
- Embeddings generated for semantically significant content, stored in Qdrant with Oxigraph URI + Pod reference metadata
- Full bidirectional traceability: embedding → triple → Pod resource
- **Phase 2 checkpoint:** Manually run SPARQL queries in Oxigraph UI and see OSLO-mapped triples with provenance. Validate the data layer independently before agents touch it. Troll agent tests SPARQL injection + vector privacy at this stage.

**Phase 3 — Agents & Scenarios**
- OpenClaw agents simulating 5 roles (tutor Claire, admin Marc, regional Isabelle, parent Fatima, student Ayoub)
- Shared SPARQL skill as spawnable sub-agent
- 3+ cross-context queries demonstrating silo-breaking:
  - Claire: "which students struggle with concept X across all contexts?"
  - Isabelle: "what's the impact of funded STEM programs?" (aggregate, anonymized)
  - Fatima: "unified view of both children across schools and activities"
- NL→FR school transfer scenario (Ayoub)
- **Graph-only vs. hybrid query comparison** as explicit demo deliverable — same question answered by SPARQL alone, then by SPARQL+vector, showing the added value of the semantic layer. Use Claire's struggling-student scenario for maximum emotional resonance: graph-only returns "student failed tests X, Y, Z"; hybrid returns "student failed tests but tutoring notes show they're grasping the concept through a different approach — the school assessment doesn't capture their progress."
- **Phase 3 checkpoint:** Troll agent tests cross-inference via natural language (can agents be tricked into revealing unauthorized data?).

**Phase 4 — Adversarial Testing & Dashboard**
- Troll agent comprehensive run with full playbook: ACL enforcement, SPARQL injection, cross-inference, vector privacy leaks
- Each attack surface categorized and rated (pass / partial / fail)
- Structured troll report comprehensible to non-technical funder
- Mission control dashboard (dev mode): live attack results, query monitoring, Pod status, ingestion metrics

**Incremental troll testing dependency chain:**
1. ACLs → testable after Phase 1
2. SPARQL injection → testable after Phase 2
3. Vector privacy → testable after Phase 2
4. Cross-inference via NL → testable after Phase 3
5. Phase 4 = comprehensive final run + report generation

### Out of Scope for PoC (Phase 5 Backlog — Known Unknowns)

| Deferred Item | Rationale | When It Becomes Relevant |
|---------------|-----------|--------------------------|
| **Programmable governance contracts** | Conceptually validated, full implementation deferred | Pilot phase — needed for real minor/guardian onboarding |
| **Nightly consolidation routine** | Can be manual/scripted for demo; automation is operational polish | Pre-pilot — needed before real user data |
| **Cascade deletion pipeline** | Soft-delete/hard-delete can be demonstrated manually | Pre-pilot — RGPD compliance requires this before real data |
| **Dashboard presentation mode** | Dev mode sufficient for PoC; presentation polish for funder meetings | Funding pitch preparation |
| **Discord integration** | Human interface layer, not architectural dependency | When real users interact with their agents |
| **SCORM-to-RDF converter** | Tier 2 ingestion, not needed for synthetic data PoC | Pilot phase with real schools |
| **Platform connectors (Smartschool, Happi)** | Tier 3 ingestion, per-platform engineering | Pilot phase — Smartschool first |
| **Data capture/collection UX** | Full learning experience design problem | Post-pilot product development |
| **Consumer-facing pod management UI** | Learners/parents need an interface eventually | Post-pilot, informed by pilot UX learnings |
| **AI Act compliance documentation** | Architecture designed for it, formal documentation deferred | Pre-production, required before real assessments/recommendations |

### MVP Success Criteria

The PoC is successful when:
1. All 4 phases complete with Definition of Done met (see Success Metrics)
2. The demo narrative runs end-to-end without manual intervention: ingest → query → transfer → attack → report
3. Hybrid query comparison clearly shows added value over graph-only
4. Troll report honestly maps what holds, what's partial, and what's deferred
5. A non-technical reviewer (potential funder) can follow the mission control dashboard and troll report
6. The evidence case is strong enough to pursue Eduvik pilot partnership and funding applications

**Go/No-Go Decision Point:** After Phase 4, review evidence against funder conviction criteria. If architecture holds and demo is compelling → pursue funding + Eduvik pilot. If fundamental architectural issues emerge → pivot or redesign before committing resources.

### Future Vision

**Near-term (post-funding, 6 months):**
- Eduvik pilot: first real tutor-parent-student data flowing through pods
- Smartschool connector: Tier 3 ingestion for Flemish schools
- Governance contracts: real minor/guardian onboarding
- Nicolas's personal portfolio bridge: patient zero cross-domain validation

**Medium-term (12 months):**
- Multiple services writing to pods (network effect begins)
- Athumi alignment: OSLO vocabulary contribution, potential pod hosting partnership
- Nightly consolidation + cascade deletion: production-grade data lifecycle
- Dashboard presentation mode: fundable demo toolkit

**Long-term (18-36 months):**
- "LMS à la carte": modular education services composed on pod infrastructure
- Community pods: school governance, budget transparency, director succession
- Cross-domain expansion: healthcare (Traq.be alignment), professional certification
- Business model resolved through evidence: standard body, open-core, infrastructure, or hybrid
- Pod ecosystem with network effects: more services → more value → more adoption
