---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - "user-provided: Architecture d'apprentissage décentralisée — Synthèse & Plan (inline message)"
date: 2026-03-16
author: Nicolas
revised: 2026-03-17
purpose: "Non-technical communication document — executive summary, funder brief, project README"
---

# Product Brief: pocpod0

## TL;DR

Learning data is trapped in institutional silos. Students, parents, and teachers each see only a fragment of a learner's journey — and when a student changes schools, the data stays behind. pocpod0 is a proof-of-concept for a new model: learners own their data in personal data pods, and every authorized person — teacher, parent, school, regional authority — sees a coherent, complete picture. Built for the hardest case first (K-12 minors under European privacy law), the project proves this architecture works before involving real users. It is currently in active development as a solo-dev PoC targeting funder conviction and a first pilot partnership.

---

## The Problem

Every school, tutoring platform, and extracurricular provider maintains its own database. None of them talk to each other. The result:

- **Teachers** spend hours manually compiling student progress from different systems — and still can't see what happens outside their classroom.
- **Parents** get a report card twice a year and have no unified view of their children's learning across schools and activities.
- **Students** who change schools lose their learning history. The new school starts from zero.
- **Regional authorities** fund after-school programmes but receive only self-reported PDF narratives — no way to measure actual impact on learning outcomes.
- **The data itself** is structurally limited. The most widely adopted standard (xAPI) tracks events but can't connect them, infer patterns, or answer cross-context questions.

And all of this involves children's personal data, under the strictest privacy regulations in the world.

---

## Why Existing Solutions Fall Short

The current standard for learning data (xAPI) was a step forward from simple pass/fail tracking, but it inherited a fundamental design flaw: the data lives in institutional databases the learner doesn't control. Analytics vendors build dashboards on top, but each dashboard sees only its own silo. No existing solution gives learners ownership of their data. No existing solution breaks the walls between institutions. And no existing solution can answer questions that span multiple learning contexts — because the data was never designed to be connected.

---

## The Approach

pocpod0 builds on three layers, each serving a distinct purpose:

- **The Passport** (Solid Pods) — Each learner gets a personal data pod. Like a passport, it belongs to them, travels with them, and they control who sees it. Raw learning records are stored here under the learner's exclusive control.

- **The Encyclopedia** (Oxigraph) — A structured knowledge graph that connects learning events, enabling questions like "show me this student's progress across all contexts." It can infer patterns and relationships that flat event logs cannot.

- **The Memory** (Qdrant) — A semantic layer that understands meaning, not just structure. It powers natural-language questions and surfaces insights that pure database queries miss — like recognising that a student struggling on school tests is actually grasping the concept through a different approach in tutoring.

On top of this architecture, **simulated role agents** stand in for real users during the PoC — a teacher, a school administrator, a regional policy advisor, a parent, and a student. They exercise the system through realistic scenarios. An **adversarial "troll" agent** then deliberately tries to break things: accessing unauthorized data, exploiting queries, finding privacy leaks. The troll's report is a deliverable — an honest map of what holds and where investment is needed.

Existing institutional data (in xAPI format) flows into this architecture through a lossless conversion pipeline. Schools don't need to rip out their current systems — they upgrade what they already have.

---

## Who This Is For

**Claire — Secondary School Teacher (Brussels)**
Claire teaches 120 students across 5 classes. Some transfer mid-year from French-speaking schools with zero learning history. She spends 3 hours a week manually compiling progress notes. She can't see what her struggling students learn in their publicly funded after-school tutoring. Her moment: asking "which students are struggling with fractions across all their learning contexts?" and getting an answer that includes school, tutoring, and self-study data — in seconds.

**Marc — School Administrator (Liège)**
Marc's school runs different platforms for admin and classwork. Student transfers mean re-entering everything by hand. Compliance reporting is a quarterly ordeal of compiling PDFs. 25% of his admin staff's time goes to data re-entry. His moment: a student transfers in and their learning profile is instantly available, with parental consent visible and auditable.

**Isabelle — Regional Education Policy Advisor (Brussels)**
Isabelle oversees publicly funded extracurricular programmes. She needs to assess outcomes to justify budgets, but receives only narrative reports with self-reported numbers. She cannot connect programme participation to actual learning outcomes. Her moment: asking "what is the measurable impact of after-school STEM programmes?" and getting an evidence-based, anonymised, consent-verified answer. This question is currently unanswerable by anyone in Belgium.

**Fatima — Parent (Brussels, bilingual household)**
Fatima has one child in a Flemish school and one in a French-speaking school. She uses two different platforms and gets report cards twice a year. She can't see a unified picture of her children's progress, nor what the robotics workshop is actually teaching them. Her moment: one view, both children, all contexts — with her controlling exactly who else can see what.

**Ayoub — 16-year-old Student (Brussels)**
Ayoub doesn't think about data sovereignty. He thinks about grades, friends, and basketball. But when he transfers schools, his learning history follows him seamlessly. When he turns 18, control of his data shifts to him automatically. Years later, when he applies for university, his complete, verified learning portfolio is available in one click.

---

## What Success Looks Like

The PoC builds an evidence case through a single, end-to-end demo narrative:

1. **Ingest** — Import a realistic synthetic dataset and prove nothing is lost in translation.
2. **Query** — Claire, Isabelle, and Fatima each ask questions that are impossible to answer with current tools — and get answers.
3. **Transfer** — Ayoub changes schools. His learning history follows him. The old school loses access. The new school gains it — with consent.
4. **Stress-test** — The troll agent attacks the system across multiple categories. Each category is honestly rated: holds, partially holds, or needs investment.
5. **Govern** — Data lifecycle works: Ayoub's control transfers at the right age, deletions propagate correctly through all layers.

**The PoC succeeds when** this narrative runs end-to-end, the troll report is readable by a non-technical reviewer, and the evidence case is strong enough to pursue pilot funding and partnerships.

**Go/No-Go decision point:** After the demo, review evidence against funder conviction criteria. If architecture holds and demo is compelling — pursue funding and pilot. If fundamental issues emerge — pivot before committing resources.

---

## Why Now / Why Belgium

Belgium is uniquely positioned for this project:

- **The hardest compliance case.** K-12 education with minors under EU RGPD and the incoming AI Act. If the architecture works here, it works anywhere.
- **Athumi** — the Flemish government's data utility company — is building citizen-scale Solid infrastructure. Education is on their roadmap but not yet deployed. pocpod0 aligns directly with their strategy.
- **OSLO vocabularies** (data.vlaanderen.be) provide standardised data schemas for education, already maintained by the Flemish government. Native compatibility with government infrastructure is built in.
- **A fragmented landscape begging for a solution.** Three education communities (Flemish, French, German-speaking), multiple incompatible platforms (Smartschool ~90% in Flanders, Happi in Wallonia), no cross-community data portability.
- **Active funding ecosystem.** EU Digital Education Action Plan, Horizon Europe, VLAIO (Flanders Innovation), and the Belgian Recovery and Resilience Plan all have relevant open calls.

---

## Competitive Landscape

| Player | What They Do | Relationship |
|--------|-------------|--------------|
| **Athumi** | Flemish government Solid infrastructure at citizen scale | Strategic alignment partner |
| **Inrupt** | Enterprise Solid Server, Data Wallet | Infrastructure provider (not competitor) |
| **TrustFlows (imec/UGent/KU Leuven)** | Solid ecosystem community, successor to SolidLab Vlaanderen | Research collaboration opportunity |
| **Traq.be** | Belgian startup, "lifelong digital backpack" bridging education-health-family | Ecosystem ally — more pod services = more value |
| **Smartschool** | Dominant Flemish LMS (~90%) | Integration target for pilot phase |
| **xAPI/LRS vendors** | Centralised learning record stores | Import/export compatibility — migration source |

---

## Funding and Partnership Opportunities

- **Athumi partnership/pilot programme** — most advanced Solid adopter globally
- **EU Digital Education Action Plan** — funding calls for education data innovation
- **Horizon Europe** — digital education and data spaces clusters
- **VLAIO** (Flanders Innovation & Entrepreneurship) — R&D subsidies
- **Innoviris** (Brussels-Capital Region) — R&D and innovation grants, including AI and digital projects
- **SPW Recherche / Digital Wallonia** (Wallonia) — industrial research funding and the "Digital School" programme
- **Belgian Recovery and Resilience Plan** — education digitalisation budget
- **Eduvik** (Hoeilaart, Flemish Brabant) — target pilot partner, a tutoring network (500+ teachers across Flanders and Brussels) sitting at the tutor-parent-student intersection with zero current data infrastructure to prove tutoring impact

---

## Future Vision

**Near-term (post-funding, ~6 months):**
First real data flowing through pods via an Eduvik pilot — real tutors, parents, and students. A connector to Smartschool brings Flemish school data in. Real consent management with minors and guardians.

**Medium-term (~12 months):**
Multiple services writing to pods — the network effect begins. Alignment with Athumi for pod hosting at scale. Production-grade data lifecycle (automated cleanup, deletion propagation, versioning).

**Long-term (18-36 months):**
An "LMS a la carte" — modular education services composed on pod infrastructure. Community pods for school governance and budget transparency. Cross-domain expansion into healthcare and professional certification. The pod becomes a platform primitive: the foundational data layer upon which an ecosystem of services composes.

---

## Learn More

- **Technical Architecture and Requirements:** See the [Product Requirements Document (PRD)](prd.md)
- **Implementation Plan:** Epics and Stories (forthcoming)
- **Architecture Decisions:** Technical Decisions Document (forthcoming)

---

*pocpod0 is an open-source project. LICENSE, CODE_OF_CONDUCT, and CONTRIBUTING documents will be published as the project matures.*
