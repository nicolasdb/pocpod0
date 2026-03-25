# Post-POC Backlog

Ideas captured during the POC that are worth pursuing after the current scope closes.

---

## Idea: Medical Silos Domain Variant

**Captured:** 2026-03-20
**Status:** backlog

### Concept

Apply the same pod sovereignty + data silo architecture to a healthcare domain instead of education. The structural problem is identical — fragmented siloed data across providers, no unified view, strict access rules — but the domain makes GDPR stakes and consent friction much more visceral.

### Stakeholder map (mirrors education personas)

| Healthcare | Education analog |
|---|---|
| Patient (child) | Learner |
| Physician (GP) | Teacher |
| Kinésithérapeute | Tutoring provider |
| Logopède | Extracurricular provider |
| Dentist | Another school |
| Health insurance | Policy/aggregate role (Isabelle) |
| Divorced parents | Split custody = split consent authority |

### Why this is interesting

- **Divorced parents** = perfect analog to NL/FR school split (Fatima's scenario). Each parent has partial consent authority. The pod sovereignty model must handle: which parent can grant access to which provider? Can the child's GP see data from the kine without parent B's consent?
- **Health insurance** aggregate queries = Isabelle's policy role but with GDPR Article 9 (special category data) — much harder access rules, much stronger demo of why the architecture matters.
- **Cross-silo hidden data**: child struggling at school but kine records show motor development issue — same cross-context insight problem as Claire/Alex, but with real privacy stakes.
- **Deletion cascade**: right-to-erasure request from patient = Ayoub's governance scenario, but healthcare retention rules add conflict (you can't always delete medical records).

### Reuse from POC

- Pod provisioning, ACL, CSS auth patterns: 100% reusable
- OSLO vocabulary: replace with HL7 FHIR or a Belgian health ontology
- xAPI → replace with FHIR resources or HL7 messages
- Ingestion pipeline, Oxigraph, Qdrant: reusable with schema swap
- All agent journeys (cross-context, aggregate, transfer, governance) map 1:1

### Notes

- Belgium has a strong eHealth platform context (eHealthBox, Vitalink, RSW) — real institutional silos to reference
- Could be a compelling follow-up grant application or demo for a health-sector audience
- Same codebase, different vocabulary schema contract (Story 2.1 equivalent = define FHIR/OSLO health schema contract)

---

## Idea: Immutable Aggregate Publication via IPFS+IPLD

**Captured:** 2026-03-24
**Status:** backlog — pilot-phase architecture evolution

### Concept

Once an aggregate crosses the trust circle boundary (anonymized via GROUP BY), it ceases to be personal data and becomes a **public good**. Today it lives only in service logs. In the pilot, it should be published as immutable, content-addressed, append-only linked data.

**Protocol:** IPFS + IPLD
- IPLD is compatible with RDF via JSON-LD serialization — semantic data stored with Merkle DAG integrity
- Content-addressed: the aggregate is identified by its hash, not by a URL someone controls
- Append-only: historical records cannot be retroactively edited — the Word document is replaced by a hash
- Cryptographically verifiable: any external auditor can verify that "32 students, March 2026" is the exact record published without trusting the publisher

### The Temporal Civic Signal

Tombstone revocation (consent withdrawal) produces a measurable time series on aggregate pipelines. If revocations spike in a territory, the aggregate count drops without any individual being identifiable. This is a civic signal — a community expressing distrust through data sovereignty choices rather than surveys or votes.

Historical immutable aggregates (IPFS-anchored) provide the baseline for trend analysis: "participation was 32 in Q1, 28 in Q2, 19 in Q3 — what happened in Q2?" This is **liquid democracy at the data layer**: continuous preference expression, observable at aggregate level, untraceable at individual level.

### Reuse from PoC

- Oxigraph SPARQL aggregates: the query output is already JSON-LD-serializable
- Consent grant URIs: link directly from the IPFS record as provenance
- Tombstone revocation: already planned — IPFS publication happens *before* revocation check (aggregate was valid at publication time)

### Notes

- Requires IPFS node in pilot infrastructure (not in PoC docker-compose scope)
- IPLD + Solid convergence is active research area — Authenticated RDF on IPLD project relevant
- Connects to EU DGA "data altruism" framing: anonymized aggregates as public-interest datasets

---

## Idea: Personal PodGraphRAG — Shippable Container with BYOK OpenClaw

**Captured:** 2026-03-21 (Epic 2 Retrospective)
**Status:** backlog
**Depends on:** Epics 1-6 complete

### Concept

Package the full pocpod0 stack (CSS + Oxigraph + Qdrant + OpenClaw + Mission Control) as a single `docker compose up` deployment with onboarding flow. Target: alpha testing with low-tech real users who never touch SPARQL, ACLs, or config files.

### Two packaging tiers

**Tier 1 — Developer / evaluator:**
- Ship repo + `.env.template` + docs
- User edits `.env` (pod names, OpenRouter API key)
- `docker compose up` + `provision_pods.py` + pipeline
- OpenClaw installed separately, pointed at local stack

**Tier 2 — Non-technical user (target):**
- All-in-one compose with OpenClaw + mission control baked in
- First-run onboarding: "What's your name? Who are your students?" → auto-provisions pods, ACLs, agent configs
- `.env` only needs OpenRouter key (or local LLM endpoint)
- Mission control dashboard (Story 6-2) doubles as onboarding UI

### Multi-user: VPS + Domain unlock

- Current: `localhost:3000/ayoub/` — meaningless outside this machine
- With VPS + domain: `https://pods.family.be/ayoub/` — real dereferenceable WebID
- CSS `baseUrl` config is the only change; no code hardcodes localhost
- Enables: cross-machine pod access, real ACL enforcement (WebID-TLS/OIDC), federation between PodGraphRAG instances
- URI portability (domain migration) handled by Solid protocol (`owl:sameAs` in WebID profile) — not our problem to solve

### North star: family.be

Nicolas's family running their own PodGraphRAG on a ~5€/month VPS. Personal pods for each family member, collective memory pod, personal agent bridging technical work into accessible updates. Proof of success: non-technical family members receiving fresh news without vulgarization overhead.

### Reuse from POC

- 100% of Epics 1-6 code reusable
- Onboarding = `provision_pods.py` with a UI skin
- Agent config = OpenClaw preset pointing at local compose services
- Pipeline = same ingestion/embed flow, triggered by onboarding

---

## Improvement: Live progress indicator for long-running pipeline jobs

**Captured:** 2026-03-20
**Status:** backlog
**Target story:** 6.2 Mission Control Dashboard

### Problem

The embed pipeline (and load_graph) buffers all work before writing to the data store, making mid-run progress invisible. Specifically:

- `embed.py` generates all embeddings first, then batch-upserts to Qdrant at the end — Qdrant point count stays at 0 throughout the entire embedding phase
- `load_graph.py` loads resources one by one into Oxigraph — queryable mid-run but no counter surface
- Both are long-running black boxes from the dashboard's perspective

### Required change in embed.py

Move the `batch_upsert_points()` call inside the embedding loop — upsert each batch immediately after it's embedded, rather than buffering all vectors:

```python
# Current (buffered — dashboard-unfriendly):
for i in range(0, len(texts), batch_size):
    vectors = embedder.generate_embeddings(texts[i:i+batch_size])
    all_vectors.extend(vectors)
upserted = writer.batch_upsert_points(chunks, all_vectors)

# Target (streaming — live Qdrant counter):
for i in range(0, len(chunks), batch_size):
    batch_chunks = chunks[i:i+batch_size]
    vectors = embedder.generate_embeddings([c["text"] for c in batch_chunks])
    writer.batch_upsert_points(batch_chunks, vectors)
    # Dashboard can now poll: GET /collections/pocpod0_embeddings → points_count
```

### Dashboard probe

```bash
curl -s http://localhost:6333/collections/pocpod0_embeddings \
  | jq '.result.points_count'
# Returns live count during run; compare to total chunks_extracted from pipeline start log
```

### Notes

- Total chunks extracted is logged at pipeline start (`embed.extract` event) — dashboard can use that as the denominator
- Same pattern applies to load_graph: Oxigraph triple count is already queryable mid-run via SPARQL COUNT — just needs surfacing in the dashboard
- Matches the mission control UX note: "pipeline jobs are long-running black boxes; needs live progress indicators"

---

## Idea: Stakeholder Simulation System — Autonomous Multi-Agent Scenario Runner

**Captured:** 2026-03-25 (Story 3.8 party mode review)
**Status:** backlog — post-POC phase
**Depends on:** Epics 1-6 complete

### Concept

A true simulation system where agents act autonomously over simulated time periods (e.g., 6-week school term + 2-week holiday). Each role generates realistic activities, writes data to their own pod, and responds to events. The system models a full semester of stakeholder interaction.

### What it does

- **Scenario runner:** Configurable time-compressed simulation (8 weeks → minutes). Each agent acts according to their role: Claire generates learning observations, Ayoub submits assessments, Fatima checks parental views, Marc processes transfers, Isabelle pulls aggregate reports.
- **Agent-generated data:** Agents write xAPI events to their own pods using an `xapi-write` skill. Data flows through the pipeline (RDF conversion → Oxigraph → Qdrant) and becomes queryable by other agents.
- **Interactive inspection:** Pause the simulation at any point. Talk to any agent in isolation. Ask questions. Introduce new queries. See how data propagation affects each perspective. Watch how Isabelle's aggregate view changes when Fatima revokes consent for one child.
- **Troll as benevolent guardian:** The troll runs on a heartbeat (using `HEARTBEAT.md`), periodically poking boundaries. Tries new attack approaches between probes. Reports successes and especially failures with full detail. Can even suggest patches.

### Why this matters

- Accelerates testing: run a semester of stakeholder interactions in minutes
- Surfaces emergent behavior: what happens when 3 agents write to the same pod simultaneously?
- Demonstrates data sovereignty at scale: consent changes propagate through the simulation, affecting all downstream views
- Provides a playground for exploring new scenarios without manual setup

### Reuse from POC

- 100% of Epics 1-6 infrastructure
- OpenClaw `/v1/chat/completions` API for programmatic agent interaction
- JSONL event streams for dashboard observation
- Troll attack modules as the guardian heartbeat
- New: `xapi-write` skill (agents generating data), scenario configuration YAML, time-compression engine

### Notes

- The two-terminal model (TUI + OpenClaw) scales directly: TUI shows simulation progress, OpenClaw allows intervention at any point
- Could be the research tool that makes the POC investable: "we built a system that can simulate a semester of educational data flow in 5 minutes"
- Connects to the consortium pitch (Syntonie/OpenFab/Politype): each partner could run their own simulation with domain-specific agents
