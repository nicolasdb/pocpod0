---
stepsCompleted: [1, 2]
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
