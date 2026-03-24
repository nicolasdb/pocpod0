---
stepsCompleted: [1, 2, 2b, 2c, 3, 4, 5, 6, 7, 8, 9, 10, 11, step-12-complete]
inputDocuments:
  - "product-brief-pocpod0-2026-03-16.md"
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
classification:
  projectType: "PoC / Research Platform"
  domain: "Education Data Sovereignty"
  domainTags: ["edtech", "data sovereignty", "privacy engineering"]
  complexity: high
  projectContext: "greenfield with ecosystem constraints"
workflowType: 'prd'
---

# Product Requirements Document - pocpod0

**Author:** Nicolas
**Date:** 2026-03-16

## Executive Summary

pocpod0 validates a decentralized learning data architecture where learners — not institutions — own their data. It replaces the centralized LMS/LRS model with Solid Pods under exclusive learner control, backed by a semantic graph engine (Oxigraph) and vector store (Qdrant) that deliver inference, cross-domain analytics, and semantic search impossible with xAPI alone.

The PoC targets the Belgian K-12 ecosystem — multilingual education communities (Flanders, Wallonia, Brussels), fragmented standards (Smartschool, Happi, OneRoster, Ed-Fi, xAPI), and the strictest regulatory intersection in Europe (RGPD with minors). It proves the architecture with synthetic data and simulated role agents before committing real users, following an evidence-first methodology where each phase builds the case for the next.

The audience is funders and strategic partners (Athumi, EU programme officers, Eduvik). The PoC either builds the evidence case and unlocks pilot funding, or it doesn't — there is no separate product MVP.

### What Makes This Special

1. **Learner sovereignty is structural, not cosmetic.** Solid Pods deliver real, granular, RGPD-native data control — not a privacy dashboard on someone else's database. Rights to access, erasure, and portability are architectural, not bolted on.

2. **Every keyhole becomes a window.** Today, each stakeholder sees a fragment. pocpod0 breaks the silos: Claire sees cross-institutional student progress in seconds instead of 3 hours of manual compilation. Fatima sees both children across schools in one view. Isabelle gets evidence-based program impact instead of self-reported PDF narratives.

3. **Built for the hardest room first.** K-12 minors under EU RGPD is the most demanding compliance environment. The primitive is a data architecture (Pods, triples, ACLs), but the ecosystem it enables will include an agentic layer triggering AI Act Annex III obligations. Designing compliance into the primitive's governance now means the agentic layer can be added without retrofitting.

4. **Migration path, not migration wall.** Existing xAPI data flows in via lossless RDF conversion. Richer analytics flow out immediately. Backward-compatible xAPI export preserves institutional LRS compatibility.

5. **Honest evidence over perfection claims.** An adversarial troll agent attacks categorized surfaces (ACL enforcement, SPARQL injection, cross-inference, vector privacy, deletion timing). Each surface rated pass/partial/fail. The troll report is a deliverable — structured for non-technical funders.

6. **Tracking works in both directions.** Every data flow serving an institution generates a readable receipt for the person whose data flowed. Ayoub can ask "who has my data and why?" and get a machine-readable, human-legible answer. Institutions see aggregate impact; data subjects see what institutions saw. This is the anti-bossware guarantee — and it aligns the system with the EU Data Governance Act's data intermediary and data altruism frameworks, making the PoC DGA-forward infrastructure.

**Core insight:** The Pod is a platform primitive — like a passport (yours, portable, recognized everywhere, you control who sees it) or like S3 to AWS (the foundational data layer upon which an ecosystem composes). The PoC validates the primitive. The ecosystem builds on top.

## Project Classification

- **Project Type:** PoC / Research Platform
- **Domain:** Education Data Sovereignty (edtech + data sovereignty + privacy engineering)
- **Complexity:** High — K-12 minors, EU RGPD, AI Act readiness, cross-jurisdictional (BE trilingual), semantic web standards, adversarial security validation
- **Project Context:** Greenfield with ecosystem constraints — building on committed standards (Solid/CSS, OSLO vocabularies, Oxigraph, Qdrant) aligned with Athumi/Flemish government infrastructure

## Success Criteria

### User Success (Funder Conviction)

The PoC has no end users — it has an audience. Success = the demo narrative convinces funders to invest in the pilot phase.

- **Demo narrative follows a scripted arc** (ingest → query → transfer → attack → govern) with **intervention points** where funders shift from audience to participant. The narrative completes whether funders intervene or observe passively.
- **The demo surfaces failures** — the troll agent maps where defenses hold and where investment is needed. Graceful failure acknowledgment is the trust-building mechanism: partial/fail ratings are the investment thesis for the next phase.
- **Non-technical reviewer** can follow the mission control dashboard and troll report without technical explanation
- **Hybrid query comparison** clearly demonstrates added value over graph-only
- **Emotional resonance moment:** Claire's struggling-student scenario — graph-only returns "failed tests X, Y, Z"; hybrid returns "struggling at school but tutoring notes show they're grasping it differently"

### Business Success

- **Evidence case strong enough** to pursue Eduvik pilot partnership and funding applications (Athumi, VLAIO, EU Digital Education Action Plan, Horizon Europe)
- **Architecture proven compatible** with Athumi/OSLO ecosystem
- **Go/No-Go decision** can be made with confidence after Phase 4

### Technical Success

- **Ingestion:** 10K+ synthetic xAPI statements as OSLO-mapped RDF with provenance. Any original statement recoverable.
- **Pod infrastructure:** 5 individual + 1 community (school) pod, ACLs per role
- **Bidirectional traceability:** embedding → triple → Pod resource, fully navigable
- **Troll coverage:** Minimum 4 attack categories tested. ACL + SPARQL injection must pass. Probabilistic surfaces assessed with findings documented.
- **Performance and latency targets:** See [Non-Functional Requirements > Performance](#performance)
- **Developer experience:** See [Non-Functional Requirements > Deployment & Portability](#deployment--portability)

### Measurable Outcomes

| Proof Area | Done When |
|------------|-----------|
| **Architecture** | 10K+ xAPI → OSLO RDF in Oxigraph, provenance verified, any statement recoverable, Qdrant embeddings bidirectionally linked |
| **Silo-Breaking** | 3+ cross-context queries correct, role-based access enforced per query |
| **Transfer** | NL→FR school transfer completes, new school sees full history, old school access revoked |
| **Security** | Troll report generated, all tested categories rated, ACL + SPARQL injection pass, report readable by non-technical reviewer |
| **Governance** | Age-based governance transfer executes, deletion cascade propagates to all three layers |

**The PoC is complete when** all 5 proof areas meet their criteria above AND the demo narrative runs end-to-end (ingest → query → transfer → attack → govern) with the troll report generated and readable by a non-technical reviewer.

## Product Scope

### PoC = MVP

The PoC is the MVP. Hard boundary — the walking skeleton:

- **Phase 1 — Infrastructure:** docker-compose with CSS, Oxigraph, Qdrant, Nginx. 5+1 pods. ACLs. Troll tests ACLs immediately.
- **Phase 2 — Data & Intelligence:** Synthetic xAPI dataset. OSLO vocabulary schema contract. xAPI→RDF pipeline. Embeddings in Qdrant. Troll tests SPARQL injection + vector privacy.
- **Phase 3 — Agents & Scenarios:** OpenClaw role agents (Claire, Marc, Isabelle, Fatima, Ayoub). Shared SPARQL skill. 3+ silo-breaking queries. Transfer scenario. Graph-only vs. hybrid comparison. Troll tests cross-inference.
- **Phase 4 — Adversarial Testing & Dashboard:** Comprehensive troll run with selectable attack menu. Categorized report. Mission control dashboard (dev mode). Intervention points for funder participation.

### Growth Features (Post-MVP — Pilot Phase)

- Eduvik pilot: real tutor-parent-student data flowing through pods
- Smartschool connector (Tier 3 ingestion)
- Programmable governance contracts for real minor/guardian onboarding
- Nightly consolidation + cascade deletion (production-grade)
- Dashboard presentation mode
- Discord integration for real user interaction
- Nicolas's personal portfolio bridge (patient zero cross-domain validation)

### Vision (Future)

- "LMS à la carte": modular education services composed on pod infrastructure
- Community pods: school governance, budget transparency, director succession
- Cross-domain expansion: healthcare (Traq.be), professional certification
- Multiple services writing to pods (network effect)
- Business model resolved through evidence: standard body, open-core, infrastructure, or hybrid

## User Journeys

*Ordered for demo narrative crescendo: operational → analytical → personal → systemic → sovereign.*

### Journey 1: Marc — Seamless Student Transfer

**Persona:** Marc, school administrator/IT coordinator, Liège (Wallonia), running Happi + Teams.

**Opening Scene:** A student transfers in from a Flemish school mid-semester. Normally, Marc's admin staff spend hours on data re-entry — calling the previous school, requesting paper records, manually entering grades. The student's learning history starts from zero.

**Rising Action:** Marc's agent initiates the transfer protocol. The student's pod receives a new ACL grant for Marc's school. The previous school's access is revoked. Marc's agent queries the student's pod for their complete learning profile.

**Climax:** The student's full history — courses, assessments, extracurricular participation, competency trajectory — is instantly available. Parental consent is visible and auditable in the pod's governance log. The NL→FR language boundary is crossed seamlessly because the data is structured as OSLO-mapped RDF, not free text.

**Resolution:** Zero re-entry. The student continues without an administrative gap.

**Funder Intervention Point:** Funder triggers the transfer scenario and observes ACL grant/revocation in real-time on the mission control dashboard.

**Proof Areas:** Cross-community data portability (NL→FR), ACL grant/revocation, transfer scenario, provenance verification.

### Journey 2: Claire — Cross-Context Insight Discovery

**Persona:** Claire, secondary school math/science teacher, Brussels (Flemish school), 120 students across 5 classes.

**Opening Scene:** Claire notices three students failing her latest math assessment. She suspects they're not actually behind — one attends Gemeente-funded tutoring, another does self-study via Khan Academy, a third transferred mid-year from a French-speaking school. But she can't see any of that from Smartschool.

**Rising Action:** Claire's agent queries: "Which students are struggling with quadratic equations across all their learning contexts?" The SPARQL skill hits Oxigraph, pulling cross-institutional data from student pods — school records, tutoring sessions, self-study activity — all under ACL-enforced access.

**Beat 1 — Graph-only answer:** SPARQL returns structured facts: "Ayoub failed tests X, Y, Z. Attendance at tutoring sessions: 8/10. Self-study: 3 Khan Academy modules completed." Useful, but flat.

**Beat 2 — Hybrid reveal:** The same query enriched with Qdrant vector search returns: "Ayoub failed the school tests, but tutoring notes show he's grasping quadratic equations through geometric visualization — the school assessment doesn't capture his approach." The system shows provenance: *this insight came from these triples, sourced from these Pod resources* — traceability made tangible.

**Climax:** Claire sees the full picture for the first time. The hybrid comparison is the proof moment: same question, visibly richer answer.

**Resolution:** Claire adjusts her assessment approach. The graph-only vs. hybrid comparison becomes a reusable demo artifact.

**Funder Intervention Point:** Funder selects a role-based query from a menu. The system displays both graph-only and hybrid results side by side.

**Proof Areas:** Cross-context queries, hybrid vs. graph-only comparison, role-based ACL enforcement, silo-breaking, bidirectional traceability.

### Journey 3: Fatima — Unified Parental View

**Persona:** Fatima, parent of two children, bilingual Brussels household — one child in a Flemish school, one in a French-speaking school.

**Opening Scene:** Fatima juggles two platforms (Smartschool and Happi), gets report cards twice a year, and has no idea what the robotics workshop is actually teaching her kids.

**Rising Action:** Fatima's agent queries her children's pods — both grant parental access via ACL. She asks for a unified view: both children, all contexts.

**Climax:** One view. Both children. All contexts. The system surfaces not just successes but gaps:
- Sam attended 18 robotics sessions; Léa attended 16 — Fatima registered them both, so she notices the discrepancy.
- The workshop records sessions as attended but has no outcome scores — the system surfaces this gap and suggests petitioning the workshop to connect their platform.
- The FR school marks activities below 60% as successful (vs NL school's 60% threshold) — same score passes one child, fails the other. The system flags this as a data quality signal worth verifying.
- A Léa science record appears in semantic search but not in structured data — stale record or migration artifact; Fatima has RGPD rights to request clarification or deletion.
- The school-community pod exists but has no connected data yet — if the workshop publishes outcome data with parental access, Fatima will see it automatically with no additional permission needed.

She controls exactly who else can see what — and can verify access grants match her consent.

**Resolution:** Fatima makes informed decisions from a position of sovereignty, not dependency. The system's value is not just the data it has — it is the gaps it surfaces and the actions it proposes.

**Proof Areas:** Multi-pod queries, parental ACL access patterns, negative-space gap detection, governance call-to-action, cross-institutional unified view.

**Implementation note (Story 3.5):** The narrative uses the actual dataset as-is. Dataset imperfection is intentional — it demonstrates real-world conditions where NL schools use OSLO-mapped data and FR schools may rely on paper assessment or non-standard platforms. The system's response to these gaps is the trust argument.

### Journey 4: Isabelle — Evidence-Based Policy

**Persona:** Isabelle, regional education policy advisor, Brussels-Capital, overseeing publicly funded extracurricular programs.

**Opening Scene:** Budget season. Isabelle needs to justify continued funding for after-school STEM programs. She currently receives Word/PDF narrative reports with self-reported participant counts. No way to connect program participation to learning outcomes. Cross-community visibility (NL/FR) is nonexistent.

**Rising Action:** Isabelle's agent queries: "What is the measurable impact of funded STEM programs on participating students' school performance?" The query hits Oxigraph with aggregate anonymization — no individual student data exposed, consent-verified, cross-community. The system surfaces provenance: *this aggregate is derived from 847 triples across 32 student pods, all with active regional-access consent grants.*

**Climax:** Evidence-based program impact: students in the robotics workshop show measurable improvement in applied math scores across both communities. This query was literally unanswerable by anyone in Belgium before.

**Resolution:** Budget justification backed by data, not narratives. Policy decisions become evidence-driven.

**Funder Intervention Point:** Funder selects an aggregate policy query. The system displays anonymization guarantees alongside results.

**Proof Areas:** Aggregate anonymized queries, cross-community visibility, regional role access, silo-breaking at policy scale, provenance traceability for aggregates.

### Journey 5: Ayoub — Sovereignty Transition

**Persona:** Ayoub, 16-year-old student, Brussels, transferring from a Flemish to a French-speaking school.

**Opening Scene:** Ayoub doesn't think about data sovereignty. His pod exists because his school and parents set it up. He barely notices it.

**Rising Action:** Ayoub transfers schools. His learning history follows him — no gap, no re-entry (Marc's side of this is Journey 1). His new school sees his full profile. His old school's access is cleanly revoked.

**Climax:** The governance transition. Ayoub's pod has a programmable governance contract: when he reaches the age threshold (per Belgian/EU residence rules), control transfers from shared parent/guardian to Ayoub alone. The contract executes. Ayoub is now the sole governor of his learning data.

**Secondary climax — Deletion cascade:** A deletion request propagates: Pod resource marked → Oxigraph triples removed → Qdrant embeddings purged. Verified end-to-end.

**Failure branch — Honest vulnerability:** The troll agent discovers that Qdrant embeddings take an extra propagation cycle to purge — a "partial" rating on deletion timing. The system reports honestly: *"Embedding purge completed in 2 cycles instead of 1. Risk: residual semantic similarity available for ~24h after triple deletion. Mitigation: acceptable for PoC, requires optimization for production."* This is the trust-building moment — the architecture acknowledges its gaps.

**Resolution:** Ayoub's data is his. The demo ends not on perfection but on honest architectural maturity.

**Funder Intervention Point:** Funder selects an attack vector from the troll agent's menu. The system runs the attack and displays results — including partial failures — in real-time.

**Proof Areas:** Governance contract execution, age-based sovereignty transition, deletion cascade propagation, adversarial failure transparency, data lifecycle.

### Journey Requirements Summary

| Journey | Capabilities Revealed | PoC Phase Required |
|---------|----------------------|-------------------|
| **Marc — Transfer** | Transfer protocol, ACL grant/revocation, cross-community (NL→FR) portability, provenance audit | Phase 1 + 2 + 3 |
| **Claire — Cross-Context** | SPARQL cross-context query, hybrid query, role-based ACL, graph-only vs. hybrid comparison, bidirectional traceability | Phase 2 + 3 |
| **Fatima — Parental View** | Multi-pod parental queries, consent management, cross-institutional unified view, ACL verification | Phase 1 + 3 |
| **Isabelle — Policy Evidence** | Aggregate anonymized queries, cross-community analytics, regional role access, provenance for aggregates | Phase 2 + 3 |
| **Ayoub — Sovereignty** | Governance contracts, age-based transition, deletion cascade (3-layer), adversarial failure transparency, data lifecycle | Phase 1–4 |

**Cross-cutting capabilities:** OSLO-mapped RDF as universal format. ACL enforcement at Pod level. Provenance linking. OpenClaw agent simulation with shared SPARQL skill. Troll agent validates each capability under adversarial conditions.

**Demo narrative arc:** Marc (operational "wow") → Claire (analytical depth + emotional resonance) → Fatima (personal sovereignty) → Isabelle (systemic impact) → Ayoub (principled architecture + honest failure). The sequence ends not on perfection but on trust.

## Domain-Specific Requirements

### Compliance & Regulatory (Known Positioning)

- **RGPD with minors** — architecturally native via Solid Pods (access, erasure, portability). Cascade deletion timing is a PoC validation target, not a pre-defined requirement.
- **AI Act Annex III** — education is high-risk. The PoC primitive is a data architecture, not AI, but designed so the agentic layer can be added without retrofitting compliance (transparency, provenance, human oversight).
- **Age-based governance** — Belgium-specific threshold to be confirmed during implementation. Governance contract pattern validated in PoC, precise legal parameters are a pilot-phase input.

### Technical Constraints (Committed Standards)

- **Solid/CSS** — Community Solid Server with content negotiation (Turtle, JSON-LD). Known friction point budgeted.
- **OSLO vocabularies** — alignment with Flemish government data infrastructure (data.vlaanderen.be). Specific education vocabulary mapping is a Phase 2 deliverable (schema contract).
- **Oxigraph + Qdrant** — RDF triplestore + vector store. Bidirectional traceability is an architectural requirement.

### Deliberate Unknowns (Fog-of-War Discovery Points)

These are questions the PoC is designed to answer, not gaps:

- Derived data classification (triples, embeddings as processing vs. new data)
- Embedding PII leakage via semantic similarity
- Cross-border jurisdictional differences in RGPD national implementations
- Guardian disagreement scenarios in multisig governance contracts
- Anonymization vs. pseudonymization threshold for aggregate regional queries

Each unknown becomes a requirement *if and when* the PoC evidence surfaces it.

## PoC Platform Specific Requirements

### Infrastructure Model

- **Orchestration:** docker-compose with latest stable pinned versions (no `latest` tags)
- **Networking:** default Docker network, services communicate via container names
- **Volumes:** bind mounts for persistent data (Oxigraph, Qdrant, CSS Pod storage). Host-specific volume flags managed via `.env` variable.
- **Health checks:** `healthcheck` directives on all services with `depends_on: condition: service_healthy`. Non-optional for reproducible startup.

### Agent-to-Data Communication

- Agents access Oxigraph and Qdrant via local Docker network
- Shared SPARQL skill as spawnable sub-agent — called by all role agents
- **Troll agent: dual access model**
  - **Through shared skill:** SPARQL injection and cross-inference attacks (tests skill-level boundaries)
  - **Direct to data layer:** ACL enforcement, vector privacy, and deletion timing attacks (tests infrastructure-level access control)

### Troll Attack Path Mapping

| Attack Category | Access Path | What It Tests |
|----------------|-------------|---------------|
| ACL enforcement | Direct to CSS/Oxigraph | Infrastructure-level access control |
| SPARQL injection | Through shared skill | Skill-level query sanitization |
| Cross-inference | Through agent layer (NL prompts) | Agent-level data leakage |
| Vector privacy | Direct to Qdrant | Embedding-level PII exposure |
| Deletion timing | Direct to all 3 layers | Cascade propagation completeness |

### Data Pipeline Architecture

xAPI → OSLO-mapped RDF conversion pipeline: architecture to be discovered during Phase 2 (fog-of-war). Batch vs. streaming, transformation tooling, error handling — all Phase 2 decisions.

## Project Scoping & Phased Development

### Resource Reality

Solo developer (Nicolas) + AI-assisted development (Claude Code as pair programmer). The effective team is 1 human + AI pair — materially expanding what a solo developer can deliver. This model scales naturally: if additional human developers join, the AI pair model extends to each, and phase work can potentially parallelize.

### Critical Path & Risks

**First risk to spike: Phase 1 CSS/Nginx content negotiation.**

Nginx reverse proxy with Linked Data headers is a known friction point in Solid deployments. If CSS doesn't serve pods correctly through Nginx, nothing else works. Spike this first, before provisioning pods.

**Timebox mitigation:** If Nginx content negotiation exceeds 3 days, skip the reverse proxy for the PoC and have agents hit CSS directly.

**Second critical dependency: Phase 2 OSLO vocabulary mapping.**

The schema contract bridges the data layer and the agent layer. This is a **knowable** risk — a half-day spike (10 xAPI statements → manual OSLO mapping → SPARQL queries in Oxigraph UI) validates the approach before committing to full 10K ingestion.

### Solo Dev Execution Guidance

- **No phase interleaving.** Finish one phase completely before starting the next. Checkpoints force closure.
- **Timebox Phase 1 hard.** Infrastructure plumbing — necessary but not where the PoC's value lives.
- **Invest most time in Phase 2.** OSLO mapping + ingestion pipeline is the intellectual core. If solid, Phase 3 agents consume good data. If shaky, Phase 3 produces garbage.
- **Context switching cost is real.** Each phase uses different tech. Budget a ramp-up day per phase transition.

### Demo Scope: Plan for 5, Fallback to 3

**Target: all 5 journeys.** Full demo arc for maximum funder impact.

**Fallback (if resources run short): 3 must-ship journeys.**

| Priority | Journey | Why |
|----------|---------|-----|
| **Must-ship** | Claire — Cross-Context | Emotional core. Hybrid vs. graph-only. The "aha moment." |
| **Must-ship** | Marc — Transfer | Operational proof. Data moves, ACLs work. |
| **Must-ship** | Ayoub — Sovereignty | Principled architecture. Governance + troll + honest failure. |
| Target | Isabelle — Policy Evidence | Policy-level demo. Speaks institutional funder language (Athumi, EU). |
| Target | Fatima — Parental View | Personal sovereignty. Emotionally compelling but overlaps with Claire. |

**Decision rule:** If Phase 3 is running late, implement Claire + Marc + Ayoub first. Isabelle and Fatima added in priority order if time permits.

## Functional Requirements

*Pre-requirement: A synthetic xAPI dataset (~10K statements, realistic school semester) must be generated before Phase 2. This is an external input, not a system capability.*

### Data Sovereignty & Pod Management

- FR1: The system can provision individual Solid Pods for each learner persona
- FR2: The system can provision a community Pod for a school entity
- FR3: The system can configure role-based ACLs on Pod resources (tutor, parent, student, admin, regional)
- FR4: The system can grant new ACL access to a Pod
- FR5: The system can revoke ACL access from a Pod
- FR6: An authorized user can view the current ACL/consent state of a Pod (makes consent auditable)
- FR7: The system can serve Pod resources with appropriate Linked Data content negotiation

### Data Ingestion & Transformation

- FR8: The system can ingest synthetic xAPI statements and convert them to OSLO-mapped RDF triples losslessly
- FR9: The system can store RDF triples in Oxigraph with provenance links to source Pod resources
- FR10: The system can recover any original xAPI statement from the RDF graph (round-trip verification)
- FR11: The system can generate vector embeddings for semantically significant content and store them in Qdrant
- FR12: The system can maintain bidirectional traceability between embeddings, triples, and Pod resources
- FR13: The system can maintain a documented vocabulary schema mapping xAPI concepts to OSLO classes (the Phase 2→3 contract)

### Cross-Context Querying

- FR14: A role agent can execute SPARQL queries against Oxigraph, scoped to its ACL permissions
- FR15: A role agent can execute hybrid queries (SPARQL + vector search) for semantically enriched results
- FR16: The system can display graph-only vs. hybrid query results side by side for comparison
- FR17: A tutor agent can query cross-institutional student progress across all authorized learning contexts
- FR18: A parent agent can query a unified view of multiple children across schools and activities
- FR19: A regional agent can query aggregate anonymized program impact across communities
- FR20: The system can surface provenance for query results (which triples, from which Pod resources)

### Transfer & Portability

- FR21: The system can execute a school transfer scenario (NL→FR) with ACL grant to new school and revocation from old school
- FR22: The receiving school's agent can query the transferred student's complete learning profile
- FR23: The system can handle cross-community data (NL/FR) seamlessly via structured RDF

### Governance & Data Lifecycle

- FR24: The system can execute a programmable governance contract for age-based sovereignty transition (guardian → learner)
- FR25: The system can process a soft-delete request on a Pod resource
- FR26: The system can propagate deletion cascade across all data layers (Pod → Oxigraph → Qdrant)
- FR27: The system can verify deletion completeness across all data layers

### Adversarial Testing (Troll Agent)

- FR28: The troll agent can test ACL enforcement by directly accessing the data infrastructure
- FR29: The troll agent can test SPARQL injection through the shared skill
- FR30: The troll agent can test cross-inference via natural language prompts through the agent layer
- FR31: The troll agent can test vector privacy by directly querying the vector store
- FR32: The troll agent can test deletion timing across all data layers
- FR33: The troll agent can generate a categorized report with pass/partial/fail ratings per attack surface
- FR34: The troll report can be read and understood by a non-technical reviewer

### Agent Infrastructure

- FR35: The system can run OpenClaw agents simulating 5 role personas (Claire, Marc, Isabelle, Fatima, Ayoub)
- FR36: The system can provide a shared SPARQL skill as a spawnable sub-agent callable by all role agents
- FR37: The troll agent can access the data layer through both the shared skill and direct connections (dual access model)

### Demo & Presentation

- FR38: The system can provide funder intervention points (query selection, transfer trigger, attack vector selection)
- FR39: The system can display a mission control dashboard showing live attack results, query monitoring, and Pod status

### Infrastructure & Operations

- FR40: The system can start all services with dependency ordering guaranteed

## Non-Functional Requirements

### Performance

- **Simple SPARQL queries:** < 500ms response time at PoC data scale (10K triples)
- **Hybrid SPARQL + vector queries:** < 2s response time at PoC data scale
- **Deletion cascade propagation:** All three data layers purged in a single execution of the propagation routine
- **Service startup:** All services healthy and responsive within 60s of `docker-compose up`

### Security

- **ACL enforcement:** No unauthorized data access at the Pod level — troll agent's ACL tests must pass
- **SPARQL injection resistance:** The shared skill must sanitize queries — troll agent's injection tests must pass
- **Data isolation:** Role agents can only access data their ACL permissions grant — no cross-role data leakage
- **Probabilistic surfaces acknowledged:** Cross-inference and vector privacy attacks are assessed and documented with findings, not required to pass — honest reporting is the bar

### Observability (Demo)

- **Query logging:** Each SPARQL/hybrid query logged with timestamp, requesting agent, latency, result count
- **Troll activity logging:** Each attack attempt logged with category, access path, result (pass/partial/fail)
- **Deletion cascade status:** Each propagation step logged with layer, resource, completion status
- These logs are the raw material the mission control dashboard (FR39) renders

### Reproducibility

- **Deterministic adversarial tests:** Identical inputs produce identical pass/partial/fail ratings across runs for infrastructure-level tests (ACL, injection, vector, deletion)
- **Exception:** Cross-inference via NL prompts (FR30) is inherently non-deterministic (LLM-dependent) — explicitly flagged as the one probabilistic test category

### LLM Configuration

- **Agent LLM:** minimax/minimax-m2.5 via OpenRouter API as primary model for all role agents and troll agent
- **Embedding model:** qwen/qwen3-embedding-8b via OpenRouter API for Qdrant vector generation
- **Single secret:** OpenRouter API key (`OPENROUTER_API_KEY` in `.env`) is the only required external credential
- **Model flexibility:** OpenRouter API abstraction allows model swapping without code changes
- **Runtime dependency:** OpenRouter API availability required — demo needs active internet connection
- **Post-PoC research (out of scope):** Systematic comparison of models across quantization, size, and cost dimensions — to be funded separately

### Deployment & Portability

- **Host compatibility:** System runs on both Fedora (local dev, SELinux) and Ubuntu (VPS) via environment variable configuration
- **Reproducible startup:** Clone repo → single `docker-compose up` → all services running
- **Setup time target:** Developer unfamiliar with project has all services running and demo executable within 1 hour of cloning (documentation quality metric)
- **External dependencies:** No external dependencies at runtime except LLM inference via OpenRouter API. All data infrastructure runs locally within Docker network.
- **Pinned versions:** All container images use specific version tags, never `latest`
- **Community standards:** Repository includes README, license, code of conduct, and contributing guide from first commit. License choice must account for OSLO vocabulary's ISA Open Metadata Licence v1.1 compatibility — to be resolved during implementation with legal review.
