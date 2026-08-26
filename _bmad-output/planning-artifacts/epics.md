---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "prd.md"
  - "architecture.md"
---

# pocpod0 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for pocpod0, decomposing the requirements from the PRD and Architecture requirements into implementable stories. UX Design was intentionally deferred — the dashboard design will be informed by evidence from earlier phases (fog-of-war approach).

## Requirements Inventory

### Functional Requirements

FR1: The system can provision individual Solid Pods for each learner persona
FR2: The system can provision a community Pod for a school entity
FR3: The system can configure role-based ACLs on Pod resources (tutor, parent, student, admin, regional)
FR4: The system can grant new ACL access to a Pod
FR5: The system can revoke ACL access from a Pod
FR6: An authorized user can view the current ACL/consent state of a Pod (makes consent auditable)
FR7: The system can serve Pod resources with appropriate Linked Data content negotiation
FR8: The system can ingest synthetic xAPI statements and convert them to OSLO-mapped RDF triples losslessly
FR9: The system can store RDF triples in Oxigraph with provenance links to source Pod resources
FR10: The system can recover any original xAPI statement from the RDF graph (round-trip verification)
FR11: The system can generate vector embeddings for semantically significant content and store them in Qdrant
FR12: The system can maintain bidirectional traceability between embeddings, triples, and Pod resources
FR13: The system can maintain a documented vocabulary schema mapping xAPI concepts to OSLO classes (the Phase 2→3 contract)
FR14: A role agent can execute SPARQL queries against Oxigraph, scoped to its ACL permissions
FR15: A role agent can execute hybrid queries (SPARQL + vector search) for semantically enriched results
FR16: The system can display graph-only vs. hybrid query results side by side for comparison
FR17: A tutor agent can query cross-institutional student progress across all authorized learning contexts
FR18: A parent agent can query a unified view of multiple children across schools and activities
FR19: A regional agent can query aggregate anonymized program impact across communities
FR20: The system can surface provenance for query results (which triples, from which Pod resources)
FR21: The system can execute a school transfer scenario (NL→FR) with ACL grant to new school and revocation from old school
FR22: The receiving school's agent can query the transferred student's complete learning profile
FR23: The system can handle cross-community data (NL/FR) seamlessly via structured RDF
FR24: The system can execute a programmable governance contract for age-based sovereignty transition (guardian → learner)
FR25: The system can process a soft-delete request on a Pod resource
FR26: The system can propagate deletion cascade across all data layers (Pod → Oxigraph → Qdrant)
FR27: The system can verify deletion completeness across all data layers
FR28: The troll agent can test ACL enforcement by directly accessing the data infrastructure
FR29: The troll agent can test SPARQL injection through the shared skill
FR30: The troll agent can test cross-inference via natural language prompts through the agent layer
FR31: The troll agent can test vector privacy by directly querying the vector store
FR32: The troll agent can test deletion timing across all data layers
FR33: The troll agent can generate a categorized report with pass/partial/fail ratings per attack surface
FR34: The troll report can be read and understood by a non-technical reviewer
FR35: The system can run OpenClaw agents simulating 5 role personas (Claire, Marc, Isabelle, Fatima, Ayoub)
FR36: The system can provide a shared SPARQL skill as a spawnable sub-agent callable by all role agents
FR37: The troll agent can access the data layer through both the shared skill and direct connections (dual access model)
FR38: The system can provide funder intervention points (query selection, transfer trigger, attack vector selection)
FR39: The system can display a mission control dashboard showing live attack results, query monitoring, and Pod status
FR40: The system can start all services with dependency ordering guaranteed

### NonFunctional Requirements

NFR1: Simple SPARQL queries respond in < 500ms at PoC data scale (10K triples)
NFR2: Hybrid SPARQL + vector queries respond in < 2s at PoC data scale
NFR3: Deletion cascade propagation completes across all three data layers in a single execution of the propagation routine
NFR4: All services healthy and responsive within 60s of docker-compose up
NFR5: No unauthorized data access at the Pod level — troll agent's ACL tests must pass
NFR6: The shared SPARQL skill must sanitize queries — troll agent's injection tests must pass
NFR7: Role agents can only access data their ACL permissions grant — no cross-role data leakage
NFR8: Cross-inference and vector privacy attacks are assessed and documented with findings, not required to pass — honest reporting is the bar
NFR9: Each SPARQL/hybrid query logged with timestamp, requesting agent, latency, result count
NFR10: Each attack attempt logged with category, access path, result (pass/partial/fail)
NFR11: Each deletion cascade propagation step logged with layer, resource, completion status
NFR12: Identical inputs produce identical pass/partial/fail ratings across runs for infrastructure-level tests (ACL, injection, vector, deletion)
NFR13: Cross-inference via NL prompts is explicitly flagged as the one probabilistic test category
NFR14: System runs on both Fedora (local dev, SELinux) and Ubuntu (VPS) via environment variable configuration
NFR15: Clone repo → single docker-compose up → all services running (reproducible startup)
NFR16: Developer unfamiliar with project has all services running and demo executable within 1 hour of cloning
NFR17: No external dependencies at runtime except LLM inference via OpenRouter API
NFR18: All container images use specific version tags, never latest
NFR19: Repository includes README, license, code of conduct, and contributing guide from first commit
NFR20: Agent LLM: minimax/minimax-m2.5 via OpenRouter API for all role agents and troll agent
NFR21: Embedding model: qwen/qwen3-embedding-8b via OpenRouter API for Qdrant vector generation
NFR22: Single secret: OpenRouter API key (OPENROUTER_API_KEY in .env) is the only required external credential

### Additional Requirements

- Compose-First Infrastructure: No starter template — project scaffold is docker-compose.yml + service-specific config directories + Python package + OpenClaw workspace (Architecture: Starter Template Evaluation)
- Pinned Service Versions: CSS 7, Oxigraph 0.5.6, Qdrant v1.17.0, Nginx 1.28.2-alpine (Architecture: INFRA-1)
- Three-Layer Data Model: Pod Layer (CSS) as source of truth, Graph Layer (Oxigraph) as queryable index, Vector Layer (Qdrant) as semantic index (Architecture: DA-1)
- Provenance & Traceability Schema: prov:wasDerivedFrom on Oxigraph triples, triple_uris + pod_resource_uri in Qdrant payloads (Architecture: DA-2)
- OSLO Vocabulary Schema Contract: Turtle files in data/schemas/ mapping xAPI → OSLO, serving as Phase 2→3 bridge (Architecture: DA-3)
- No User Authentication: Agent identity configured, not authenticated. CSS ACLs via WebACL. Real Solid-OIDC is pilot-phase (Architecture: SEC-1)
- ACL Enforcement at Two Levels: Pod level (CSS WebACL) + Query level (SPARQL skill validates role) (Architecture: SEC-2)
- SPARQL Injection Defense: Parameterized .rq templates, no string concatenation (Architecture: SEC-3)
- No REST API Layer: Services communicate via native protocols (LDP, SPARQL endpoint, Qdrant REST/gRPC) (Architecture: API-1)
- Two Shared Skills: SPARQL skill (graph queries) + Qdrant skill (semantic search), agents compose hybrid from both (Architecture: API-2)
- Qdrant REST vs gRPC: Fog-of-war — compare during Phase 2, pick one (Architecture: API-3)
- Nginx Content Negotiation Timebox: 3-day spike. Fallback: agents hit CSS directly (Architecture: INFRA-4)
- Dashboard: FastAPI + HTMX, reads from observability logs, dev-mode only (Architecture: INFRA-5)
- Structured JSON Logging: Uniform format across all components to stdout, captured by docker-compose (Architecture: Implementation Patterns)
- Deletion Cascade Protocol: 5-step process — soft-delete mark → Oxigraph removal → Qdrant removal → verification → logging (Architecture: Process Patterns)
- Agent Query Protocol: 3 paths (graph-only, semantic, hybrid), all through shared skills with ACL enforcement (Architecture: Process Patterns)
- distrobox-host-exec for accessing podman containers from within distrobox (Architecture: Enforcement Guidelines)
- Error Handling Strategy: Pipeline log+continue, Agent log+report, Troll errors-are-findings, Infra health-check catches (Architecture: Process Patterns)

### UX Design Requirements

No UX Design document provided. Dashboard UX will be designed during Phase 4 based on evidence from Phases 1-3 (fog-of-war approach). Earlier epics will backlog dashboard component needs as they emerge.

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Provision individual Solid Pods |
| FR2 | Epic 1 | Provision community Pod |
| FR3 | Epic 1 | Configure role-based ACLs |
| FR4 | Epic 1 | Grant ACL access |
| FR5 | Epic 1 | Revoke ACL access |
| FR6 | Epic 1 | View ACL/consent state |
| FR7 | Epic 1 | Linked Data content negotiation |
| FR8 | Epic 2 | xAPI → OSLO RDF ingestion |
| FR9 | Epic 2 | RDF storage with provenance |
| FR10 | Epic 2 | Round-trip xAPI recovery |
| FR11 | Epic 2 | Vector embeddings in Qdrant |
| FR12 | Epic 2 | Bidirectional traceability |
| FR13 | Epic 2 | OSLO vocabulary schema contract |
| FR14 | Epic 3 | ACL-scoped SPARQL queries |
| FR15 | Epic 3 | Hybrid queries (SPARQL + vector) |
| FR16 | Epic 3 | Graph-only vs hybrid comparison |
| FR17 | Epic 3 | Cross-institutional tutor queries |
| FR18 | Epic 3 | Unified parental view |
| FR19 | Epic 3 | Aggregate anonymized policy queries |
| FR20 | Epic 3 | Provenance for query results |
| FR21 | Epic 4 | School transfer scenario (NL→FR) |
| FR22 | Epic 4 | Transferred student profile query |
| FR23 | Epic 4 | Cross-community data handling |
| FR24 | Epic 5 | Age-based governance transition |
| FR25 | Epic 5 | Soft-delete request processing |
| FR26 | Epic 5 | Deletion cascade (3 layers) |
| FR27 | Epic 5 | Deletion completeness verification |
| FR28 | Epic 1 | Troll: ACL enforcement test |
| FR29 | Epic 2 | Troll: SPARQL injection test |
| FR30 | Epic 3 | Troll: Cross-inference test |
| FR31 | Epic 2 | Troll: Vector privacy test |
| FR32 | Epic 5 | Troll: Deletion timing test |
| FR33 | Epic 6 | Troll: Categorized report generation |
| FR34 | Epic 6 | Troll report non-technical readability |
| FR35 | Epic 3 | 5 OpenClaw role agents |
| FR36 | Epic 3 | Shared SPARQL skill |
| FR37 | Cross-cutting | Troll dual access model (pattern applied from Epic 1 onward) |
| FR38 | Epic 6 | Funder intervention points |
| FR39 | Epic 6 | Mission control dashboard |
| FR40 | Epic 1 | Service startup with dependency ordering |
| FR41 | Epic 5 | Ephemeral time-scoped consent with auto-revocation (Anagnorisis double-aveugle pattern) |

## Epic List

### Epic 1: Pod Sovereignty & Access Control
Learners own their data in Solid Pods with enforceable, auditable access control — the fundamental sovereignty primitive is proven and adversarially validated.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR28, FR40
**Cross-cutting applied:** FR37 (troll dual access pattern established here)
**Dashboard backlog:** Pod status view, ACL state visualization, troll ACL test results

### Epic 2: Semantic Data Intelligence
Learning data flows through a lossless xAPI→OSLO pipeline into a three-layer architecture (Pod→Graph→Vector) with full bidirectional provenance and adversarially validated query security.
**FRs covered:** FR8, FR9, FR10, FR11, FR12, FR13, FR29, FR31
**Dashboard backlog:** Pipeline ingestion status, provenance navigation, troll injection/vector test results

## Epic 3: Cross-Context Learning Insights
Role agents (Claire, Fatima, Isabelle) query across institutional silos, compare graph-only vs. hybrid results, and surface provenance — delivering the "aha moment" that makes the PoC compelling.
**FRs covered:** FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR30, FR35, FR36
**Story tags:** Stories tagged as [foundation] (agent infra, shared skills) or [journey] (Claire, Fatima, Isabelle scenarios)
**Priority tags:** Claire stories tagged [must-ship], Fatima and Isabelle stories tagged [target] per PRD fallback strategy (plan for 5, fallback to 3)
**Dashboard backlog:** Query monitor (SPARQL + hybrid), agent activity log, graph-vs-hybrid comparison display

### Epic 4: Student Transfer & Data Portability _(RESEQUENCED: now last / capstone — 2026-03-25; scope expanded 2026-04-02; architecture amended 2026-04-12)_
The school transfer scenario (NL→FR) executes end-to-end — ACL grants, revocations, cross-community data handling — proving data moves with the learner, not the institution. Built with dashboard running (Epic 6 complete): first epic where project lead watches the full stack live.

_(amended 2026-04-02: Epic 4 absorbs narrative context and stakeholder workflow scope deferred from Epic 6. Epic 6 proved the boundary (ACLs hold). Epic 4 proves the value inside the boundary — what resources are accessed, by whom, and why it matters to each stakeholder. OpenClaw agents become the primary interaction model. Fine-tune seeded data against scenarios.)_

_(amended 2026-04-12 — Epic 6 Retro decisions:)_
- _**Discord as interaction layer:** One Discord server, one channel per agent + #general + #security_logs. All agents reachable via Discord DM/channels. Replaces webui single-agent limitation._
- _**Seed-on-boot agent workspaces:** Dockerfile COPY agents to image, entrypoint seeds writable named volume on first boot. Agents evolve through interaction (MEMORY.md, SOUL.md). Factory reset = `compose down -v`._
- _**Troll on Discord:** Troll uses HEARTBEAT.md for periodic probe runs, posts short reports to #security_logs. Funders interact via DM. Replaces dashboard troll tab._
- _**Nicolas as new user:** Own pod + own agent-assistant proves onboarding flow. Tests: add content, grant/revoke, observe propagation._
- _**Named volume isolation:** Per-scenario volumes enable parallel simulation without contamination._
- _**ACL dashboard (keeper):** Runs alongside Discord — first POC artifact that persists across epics._

**FRs covered:** FR21, FR22, FR23
**Priority:** [must-ship] — Marc's journey is one of the 3 must-ship journeys
**Additional scope (from Epic 6 deferral + retro):** Narrative context on dashboard cards, pod content exploration, stakeholder workflows via OpenClaw agents, scenario fine-tuning, Discord multi-agent interaction, agent workspace evolution, Nicolas onboarding proof

### Epic 5: Data Sovereignty Lifecycle _(RESEQUENCED: now before Epic 6 and 4 — 2026-03-25)_
Governance contracts execute (age-based sovereignty transition), deletion cascades propagate across all three data layers, the consent lifecycle is agent-driven (acl-manage skill), and ephemeral time-scoped consent (Anagnorisis double-aveugle pattern) demonstrates that sensitive data can flow without identity exposure.
**FRs covered:** FR24, FR25, FR26, FR27, FR32, FR41
**Priority:** [must-ship] — Ayoub's journey is one of the 3 must-ship journeys
**Dashboard backlog:** Governance event log, deletion cascade status, consent gate counts, timing metrics
**Anagnorisis integration:** Stories 5.4, 5.5, 5.6 implement the consent-as-architecture principles from the Anagnorisis narrative — access receipts (BP-1), consent grant as RDF (BP-3), ephemeral time-scoped tokens (BP-5)

### Epic 6: Adversarial Trust Report & Mission Control _(RESEQUENCED: before Epic 4 — 2026-03-25; COMPLETED 2026-04-12)_
The comprehensive troll run generates a funder-readable categorized report, the ACL enforcement dashboard proves boundaries are real and visible, and intervention points let funders shift from audience to participant.
**FRs covered:** FR33, FR34, FR38, FR39
**Note:** Original TUI approach (mission_control.py) superseded by FastAPI + HTML ACL dashboard pivot (Story 6.2). ACL dashboard is a keeper into Epic 4. Troll interaction migrates to Discord (#security_logs + DM) per Epic 6 retro decision.

### Epic 7: Pod Owner Experience _(ADDED 2026-07-21 — sprint change: Epic 4 parked, first-user UX prioritized)_
Real users can create an account and pod on our CSS instance and manage their pod content and ACLs through a cognitive-ergonomics-first backoffice — the first user-facing product surface of the stack.
**Origin:** High-fidelity runnable mockup (SOLID Pod Management Interface, Claude design). Design principles: Miller's Law (≤4 chunks), Hick's Law (one primary action), progressive disclosure (friendly ACL → raw WAC on demand), reversibility.
**Relationship:** Prerequisite-sibling of Story 4.3 (Nicolas onboarding proof). ACL dashboard (6.2) = observer view; backoffice sharing = owner view — both kept.
**Dashboard backlog:** none (this IS a user surface)

### Epic 8: Solid MCP Connector _(ADDED 2026-07-30 — Quest B handoff, MISSION_BRIEF_solid-mcp-connector.md)_
A self-hosted MCP server lets Claude.ai (or any MCP client) read/write pod resources and inspect WAC permissions on `pod.nicolasdb.eu`, scoped per-person to each team member's own AGENT WebID — HyperScope using its own pod tooling internally before offering it to Singelijn/partners.
**Origin:** Claude-chat planning handoff, `solid-pod-agent.zip` toolkit (validated offline, never run against a real pod).
**Relationship:** Independent of Epic 7 (pod-owner backoffice UI) and Epic 4 (parked pilot capstone) — different codebase (Node MCP server), same CSS instance and WAC model. Story 8.1 live-verifies `wacManager.js`'s WAC-specific Inrupt calls against the exact bug patterns Story 7.3 found, falling back to 7.3's hand-rolled ACL Turtle only if they reproduce.
**Non-negotiables:** two-token model (OWNER never deployed, AGENT is runtime identity, agent never self-grants), one CSS account per person, grants always container-scoped with `scope: 'both'`, permission-writing tools require explicit human approval.
**Dashboard backlog:** none (server-side connector, no UI of its own)
**Identity & role model (settled 2026-08-02, see architecture.md BP-6):** only your own AGENT writes your pod; everything else is a grant you hold on someone else's pod. Three identity classes — personal agent (one human, conscious capture), collective service agent (nobody holds it, runs as cron), role-assigned control (`directeur` held by whoever is currently assigned). Roles are named grant bundles applied to personal-agent WebIDs, not identities in themselves — so succession reassigns Control without moving any credential. `identityRegistry.js`'s one-WebID-one-slug guard was validated against this model, not merely assumed. **What scales is grants, not credentials.**
**Positioning:** this connector is the **first line of conscious input** — a person deliberately externalizing their own thinking into their own pod — as distinct from the ambient/observed input the xAPI pipeline (Epic 2) ingests. Different provenance class, different consent texture.

**Auth posture — amended 2026-08-11** _(source: `security-hardening-brief-2026-08-09.md` §11, §16; live verification 2026-07-30→08-05)_

The slug is not a stopgap. It was adopted believing Anthropic's connector surface blocked OAuth; that diagnosis was half wrong and the correction cuts the other way. Claude's remote connectors *do* support OAuth 2.1 at the product level (DCR, CIMD, PKCE S256, RFC 9728 discovery) — but **those fields are not exposed on this account**, verified absent, and the connector was accepted by claude.ai with no OAuth configuration at all (`8-5-live-verification.md:141,143`; `8-4-vps-deploy-hardening.md:315`).

**Consequence for this epic:** the URL-slug is the load-bearing auth mechanism for the claude.ai path **for an indefinite period**, not a transitional one. Every hardening item around it — non-owner AGENT WebID, container-scoped grants, log suppression, IP allowlist, rate limiting, the access journal — is the **actual security posture**, not interim scaffolding to be thrown away at migration. Budget and review them accordingly.

**The OAuth target splits in two:**
- **claude.ai path — blocked externally.** No work here closes it. Removed from the roadmap; re-enters only on the trigger below.
- **Self-hosted path (Hermes, any self-hosted MCP client) — available now.** These clients support OAuth and arbitrary headers independently of claude.ai. Recorded in `post-poc-backlog.md`, not scheduled in the PoC.

**Trigger to re-evaluate:** Anthropic exposes connector OAuth fields on this account → immediately reassess a resource-server migration (RFC 9728 PRM, 401 discovery, audience validation per RFC 8707, CSS DPoP token server-side only, no token passthrough).

**Open, unowned:** does CSS's `AcpReader` actually evaluate `acp:client` matchers? CSS's own `access-token-verifier` lists client-id application as future work. Must be tested on a toy policy before any authorization design depends on it.

**Scope note:** credential-at-rest (architecture.md SEC-4) is *not* solved by the OAuth target — the DPoP token would sit in the same plaintext store. SEC-4 records an explicit PoC **risk acceptance** (2026-08-11: SSH-key-only access, sole key holder, own data); Story 8.8 is the pre-pilot gate that revisits it when someone else's data lands on the host.

_Story list added 2026-08-02 — Epic 8 executed with only this header in epics.md; the entries below are reconciled from `sprint-status.yaml` and the story files, which remain authoritative for detail._

### Story 8.1: WAC Hardening & Verification
As the connector's runtime (AGENT identity), I want `wacManager.js`'s grant/revoke/read proven correct against the real `pod.nicolasdb.eu` CSS instance using **only** the AGENT credential, so that the connector never silently writes an ineffective `.acl` (the failure class Story 7.3 found in the backoffice) — and the verification environment never holds the one credential able to grant itself arbitrary access.

### Story 8.2: HTTP Transport
As a team member on Claude Pro, I want the connector served over HTTP instead of stdio, so that claude.ai can reach it from Anthropic's infrastructure at a public URL — the only transport that works, since claude.ai's code sandbox cannot reach `pod.nicolasdb.eu` at all.

### Story 8.3: Per-Person Endpoints
As a team member with my own Solid pod, I want my own MCP endpoint URL bound to my own AGENT token, so that adding the connector in claude.ai acts as *me* — reaching my pod and not my colleagues' — without the server holding one shared identity for everybody.
- Per-person secret slug (`/mcp/<slug>`, 22 chars CSPRNG) carries auth, because claude.ai's connector dialog has **no request-headers field**
- Boot-time all-or-nothing identity login: any failed login refuses process start (revisited by Story 8.6.1)

### Story 8.4: VPS Deploy & Hardening
As the operator, I want the connector on the VPS behind TLS on its own subdomain, auto-restarted, rate-limited, reachable only from Anthropic (plus me), keeping an audit journal that never contains a secret — so a team member can add it in claude.ai against a real URL without handing the internet a credential-bearing access log or an unbounded write surface.

### Story 8.5: Live Verification from claude.ai
As a team member on Claude Pro, I want to add the deployed connector in claude.ai and, from a real conversation, list/read/write/inspect permissions on exactly the containers my WebID is granted — and nothing more — so the brief's Definition of Done is met or disproven **by a real MCP client**, not by our own scripts talking to our own server.

### Story 8.6: Capture Surface — Append-First Tools, Destructive Ceremony, Capture Skill
As someone thinking out loud in a conversation, I want "save this to my pod" to land in the right container, appended rather than clobbered, with real ceremony before anything is destroyed — so my pod becomes where my thinking accumulates.
- `solid_append_resource` (append is the safety mechanism while pods have no versioning), `destructiveHint` + existence probe on write, `solid_delete_resource`
- The user-facing **capture skill** — Epic 8 had built only the MCP half of a plugin
- **Read receipts** (FR42 / BP-1): `acl:Append`-only into the subject's `access-log/`

### Story 8.6.1: Lazy Identity Loading _(added 2026-08-02)_
As the operator, I want a newly-configured person to work without restarting the connector, so onboarding isn't gated on a service restart. Keeps 8.3's fail-fast boot for known identities **and** adds lazy login on cache miss for new ones. Must land before 8.7. Storage backend unchanged (that's Story 7.9).

### Story 8.7: Team Onboarding — Your Pod, Your Agent, Your Grants
As a teammate told "you should put your notes in a pod", I want a short page explaining what I actually own, walking me from zero to a working connector, and stating honestly what the system does and does not guarantee — so I can start without a call, and without mistaking a convention for an enforcement.
- Leads with the model (BP-6), walkthrough scoped to **personal** accounts, slug minting documented as manual (Story 7.9 automates it)
- Central claim: a real second person completes it following **only the page** — every operator intervention is logged as a page defect
- **Honest-boundaries section must state SEC-4** _(added 2026-08-11, party-mode review)_: credentials are stored in plaintext on an unencrypted disk, so the guarantee is "the agent cannot self-elevate over the network", not "over the host". Say who holds host access (SSH-key only, Nicolas sole key holder) and what would change that. A page that tells a second person what the system does and does not guarantee cannot omit a known exposure — the project's whole claim is that it names its limits before a user finds them.
- **State the `access-log/` tamper property as VERIFIED** (Story 8.9, 2026-08-11, live): the agent holds `acl:Append` only — it can add receipts and is denied read, overwrite, and delete on existing ones (403 on all three). State it with both limits attached: it is a voluntary convention (a reader that writes no receipt leaves no trace), and it constrains the reader, not the pod owner, who retains Control over their own log.

### Story 8.8: Credential-at-Rest Hardening _(ADDED 2026-08-11 — security brief §16; **DEFERRED to pre-pilot gate 2026-08-11**, party-mode review)_

**Status: not scheduled in the PoC. Risk accepted — see architecture.md SEC-4.**

Deferred on a risk-based call, not dropped. The threat requires host/root access or a snapshot; VPS access is SSH-key only with Nicolas as sole key holder, and the only data at risk today is his own. Remediation is disproportionate at this stage — LUKS on a running root filesystem is a rebuild-and-migrate, and the app-side alternative may need an upstream fork whose feasibility is itself unknown. Contribution to the newcomer journey: none.

**Gate — this story is drafted when, and only when:** the first non-Nicolas person's real data lands on the VPS. Custody of someone else's data is what changes the calculus.

As the operator, I want the CSS client-credentials secrets on the VPS to survive a stolen disk image or a snapshot leak, so that "the agent can't self-elevate" stops being undermined by "anyone with the volume reads its credential in plaintext."
- **The finding, both layers, both verified in source on the live host (2026-08-11):** `BaseClientCredentialsStore.js` declares `secret: 'string'` with no hash/digest field and no KDF import — `create()` hands `randomBytes(64).toString('hex')` straight to `storage.create(...)`. And `sda1` is plain ext4 with no LUKS device mapped (`cryptsetup status`). Neither layer mitigates the other.
- **Not a pocpod0 defect:** the plaintext store is the upstream OIDC library's convention, inherited by CSS. This story does not "fix a bug we wrote" — it decides what pocpod0 does about a property of its dependency.
- **Open unknown this story must close first (do not skip to implementation):** is an application-side hash/KDF even compatible with the CSS client-credentials flow as implemented, or does verification require the plaintext secret on hand? If it requires a fork/patch of the upstream library, that cost is the deciding input, not a detail.
- **Decide and record the layer:** disk-level LUKS (deployment-only, no library contract broken, protects a stolen image but not a live root) vs. application-side hash (protects against live root too, breaks the library contract). Not necessarily either/or. The decision updates **architecture.md SEC-4**, which currently records an explicit PoC risk acceptance — this story replaces that acceptance with a remediation, and is not done while SEC-4 still reads "risk accepted."
- **Scope is wider than the slug scheme.** Any CSS client-credentials secret inherits this, including the server-side DPoP token an OAuth 2.1 migration would hold. Do not scope this as slug-era cleanup.
- **Honest boundary:** this protects credentials at rest. It does not protect them from a live compromised host, and the story must say so rather than implying encryption-at-rest means the secrets are safe.

### Story 8.9: Access Journal — Tamper-Evidence Spike _(ADDED 2026-08-11 — security brief §4.4; **SPLIT 2026-08-11**, party-mode review)_

Originally drafted as a full journal-as-control story. Split on a value-per-effort call: the tamper-evidence question is minutes of work and closes a possible real hole, while the detection half is a SIEM for a two-user system and its signal-to-noise at current volume (≈10 entries/week) is unusable. **The spike stays here and runs first. Attribution moved into Story 7.9. Detection, alerting and identity-level rate limiting moved to `post-poc-backlog.md`.**

As a pod owner, I want to know whether the agent that writes to my `access-log/` can also rewrite it — because a journal the audited party can edit is not a journal.

- **What exists (Story 8.6):** `receipt.js` appends JSONL to the *data subject's* `access-log/receipts.jsonl` via `acl:Append`, correctly located per BP-1. That is the honest half.
- **The tamper question is already answered — corrected during story creation, 2026-08-11.** Story 8.6 recorded live that the `access-log/` grant is **RW, not Append-only** (`8-6-capture-surface-and-skill.md:109,212,219`), and `docs/team-onboarding.md` already discloses it. The journal *is* rewritable by the agent today. This was a documented deviation, not an unexamined assumption — the earlier "hypothesis, not a confirmed defect" framing was wrong.
- **RESOLVED 2026-08-11 (spike executed, live against `pod.nicolasdb.eu`). Decision: Path A — POST-per-receipt, Append-only grant applied.**
- **The real open question was: can it be Append-only at all?** `podClient.appendFile` is a **read-then-overwrite** — `getFile` then `overwriteFile` — so the old receipt path structurally needed Read **+** Write. Granting `acl:Append` alone would not have tightened the journal; it would have stopped receipts working. Grant and write path had to move together, and did.
- **Ground truth recorded (AC1, AC2):** `access-log/` carries its **own** `.acl`; it does **not** inherit from pod root, and root grants the agent nothing — so the RW was an explicit leaf grant, not an accidental cascade. Proof of Write: a `PUT` of the file's own bytes returned **205** and the file's mtime moved. The journal was genuinely rewritable by the party it audits.
- **Both Append-only paths verified live (AC3, AC4), 8/8 on a scratch container:** Path A `POST` → 201 while `PUT`/`GET`/`DELETE` on an existing child are denied; Path B insert-only N3 `PATCH` → 205 while a `deletes`-bearing PATCH is denied. Append-only is real and CSS enforces it per-mode.
- **The backoffice gap was never the real blocker (confirmed).** `wacManager.grantAccess({append:true})` authored a clean Append-only ACL end-to-end, run as the pod's own controller — never the agent (Story 8.1 AC4's 403 stands). The Epic 7 UI gap blocks the *self-service* path only. This downgrades the deferral of 7.6/7.11b from "blocks Append-only" to "makes it a scripted step rather than a UI step."
- **Path A chosen over B** because format is the reversible part and the tamper property is not: a weekly consolidation job can turn JSON receipts into triples later, but a receipt written while the writer held Write is untrustworthy forever. Path A is also already the house pattern — Epic 5's `receipt.py:271` writes one Turtle resource per receipt, so the two systems now agree on shape, not just field names. **The epic's earlier claim that Path A "diverges from Epic 5's JSONL convention" was backwards.**
- **Applied:** `podClient.postResource()` added; `receipt.js` POSTs one JSON resource per receipt and reserves an `underGrant` field (null today — this connector's grants are raw WAC ACLs with no `poc:ConsentGrant` URI to point at); the live `access-log/` grant tightened to `acl:Append` only. Regression verified to Story 8.6's standard: cross-pod read → receipt POST 201, and the agent is now denied listing, read-back, overwrite, and delete of its own receipt (403 on all four).
- **Cost of the decision, stated:** the journal is many small resources instead of one file, so reading it means listing a container. The agent also loses Read on `access-log/` — a privacy gain (it can no longer see other readers' entries) that forecloses any future design needing the agent to read receipts back.
- **What it does not solve:** (1) still a voluntary convention — CSS surfaces no server-side per-resource read log, so a reader that declines to write receipts leaves no trace, and Append-only makes the cooperative path trustworthy without making the record complete; (2) it constrains the **reader**, not the pod owner, who holds `acl:Control` over their own `access-log/` — inherent to BP-1 and the price of putting evidence where the audited party cannot retract it; (3) a receipt records that a read happened, never what was done with the data afterwards.
- **Reframing surfaced during the spike (Nicolas, 2026-08-11):** receipts exist to inform a *permission decision* — the audit half of a consent loop (request → review → grant → audit → revoke), not a standalone log. `poc:ConsentGrant` already ships that vocabulary (Story 5.5: requestedBy, purpose, scope, excluded, consequenceOfRefusal, revokedAt tombstone, expiresAt) but only in the pipeline; the connector knows nothing of it, and request intake does not exist (the backoffice "Requests" tab is a hardcoded stub, known since 7.2). **Carried to a sprint change proposal, out of scope for this spike.**

### Story 7.1: Backoffice Deploy & Real Account Registration
As a new user, I can reach the pod backoffice at `https://pod.nicolasdb.eu/` (replacing the CSS default welcome page), create a real CSS account + pod from the onboarding flow, and manage my files and sharing against my live pod.
- Import mockup bundle into repo (new `backoffice/` dir); serve at `https://pod.nicolasdb.eu/` root via CSS `StaticAssetHandler` config (`/` → index.html, `/pod-api.js`, `/support.js`), replacing the default CSS welcome page. Same-origin: no CORS, `redirectUrl: window.location.href` works unchanged.
- Wire onboarding "Create my pod" to CSS `.account/` controls API: `GET /.account/` → `POST /.account/account` (cookie) → `controls.password.create {email,password}` → `controls.account.pod {name}`; auth via `Authorization: CSS-Account-Token $VALUE`
- Decide + implement Inrupt lib strategy (esm.sh runtime import vs bundled self-host). Keep pinned versions (authn-browser 2.3.0 / solid-client 2.1.0); npm latest are 5.0.0 / 3.0.0 major bumps — upgrade out of scope
- Verify live mode E2E on VPS: login, file CRUD, sharing drawer grants/revokes, WAC panel reads real .acl
- Fallback (timebox): link-out to CSS registration page, "I already have a pod" path takes over
- No HTML rewrite — mockup deploys as-is, only demo-provisioning call swapped for real API calls

### Story 7.2: CSS Registration Pages Restyle
As a new user landing on the CSS-served registration/login/consent pages, I experience the same visual language and cognitive care as the backoffice.
- Override CSS registration/login/consent templates (CSS template customization mechanism)
- Apply backoffice tokens: daylight theme, Lexend / Atkinson Hyperlegible / JetBrains Mono, sage accent `#3d6b52`, ≤4 chunks per step, one primary action per screen
- Keep flows functional: account create, pod provisioning, OIDC consent (client name "Pod Backoffice")
- WCAG 2.1 AA (4.5:1 contrast, focus-visible)

### Story 7.3: My Things — File Upload, CRUD & ACL Fix
As a pod owner, I can create, upload (real files, any type), read, overwrite and delete my files/folders, and set sharing permissions that actually take effect against my live pod.
- Fix the client-side ACL write bug: live audit proved CSS honors public Read+Write (anon PUT → 205), so the backoffice is writing an ineffective `.acl` — container grants must include `acl:default` (inheritance), not just `accessTo`
- Add file-upload UI (`overwriteFile` already accepts any Blob/content-type — only the picker is missing)
- CRUD completeness + reversibility (confirm on delete); ACL read must distinguish explicit grant vs inherited-from-parent
- Root-`Control` self-lockout guard (root `.acl` is the single inheritance anchor; its loss is a potential irreversible lockout)
- WCAG 2.1 AA

### Story 7.4: Apps & Credentials — Connect External Apps to Your Pod
As a pod owner, I can see who has access, and mint/name/revoke machine credentials (client-credentials) so a Discord/Matrix bot or script can act on my pod and be cut off at will.
- Mint (`POST .../client-credentials/ {name, webId}`), list (`GET`), revoke (`DELETE {resourceUrl}` → 200, live-confirmed) client-credentials; one-time secret reveal (never stored/logged)
- Connection recipe for bot authors (token endpoint + grant + scope + DPoP required)
- Split People & apps into inbound access grants vs outbound issued credentials
- Honest WAC framing: a credential acts with the owner's identity (per-app scoping needs ACP, not CSS default) — least-privilege ACLs + revocation are the real controls
- Enables Epic 4 Discord/Matrix bridges; WCAG 2.1 AA

### Story 7.5: Export & Backup — Download Your Pod
As a pod owner, I can download my pod as an archive and understand how portability really works.
- Owner-facing export via authenticated LDP crawl (`ldp:contains`) → client-side `.zip` preserving tree, bytes, content-types; binaries as Blob
- Per-resource access-metadata sidecars (`.acl` or inherits-note) + success/failure manifest; graceful partial-crawl
- Honest portability explainer: no standard pod archive / no CSS export endpoint; cross-provider move breaks `.acl` agent URIs (WebID changes) — needs re-applying permissions
- Distinct from operator-level `make vps-backup` (whole-server volume tar). Cross-provider import/restore (WebID/ACL rebinding) deferred to a follow-on
- WCAG 2.1 AA
- **Sequencing (2026-08-03, amended 2026-08-11): runs LAST in Epic 7.** The per-resource access-metadata sidecars depend on the effective-access resolver, now scoped to **Story 7.11a**. Shipping before it would emit `inherited` for most resources — technically true, operationally useless, and permanently baked into an archive users keep. The 7.11 split moves this story earlier in wall-clock terms without changing its position in the order.

### Story 7.6: My Things — File-Manager Hardening _(**DEFERRED to post-PoC — 2026-08-11**, party-mode review)_

**Deferred on its own premise.** The story opens "as a pod owner with a real, growing pod" — nobody in the PoC has one. Bulk multi-select, cross-folder move and transfer progress are for a pod with enough files that single-item operations hurt; a newcomer's first hour never reaches that. The 7.3 CRUD/ACL spine already covers create, upload, read, overwrite, delete, rename. Re-enters when a real pod's file count makes single-item operations the complaint. Recorded in `post-poc-backlog.md`.

As a pod owner with a real, growing pod, file operations are as robust as a dedicated Solid file manager — without losing our ACL UI, inline edit, or reversibility.
- Cross-folder **move** (generalize 7.3 `rename`: copy bytes+content-type+explicit-ACL, recurse, collision-confirm, copy-verify-delete ordering so a partial move never loses data)
- **Bulk** multi-select delete/move with count-aware confirm + per-item graceful failure
- **Transfer progress** for many/large files; large-folder listing stays responsive (batch/throttle parallel ACL fetch)
- **Reference, not dependency:** learn move/copy/bulk/progress patterns from `solid-contrib/solid-file-manager` + `solid-file-client`; deliberately NOT adopted (it lacks ACL UI + inline edit + two-tap delete — our differentiators). Audit "adopted/rejected/why" captured
- Hardening on top of 7.3; keep pinned Inrupt libs; WCAG 2.1 AA + no regression

### Story 7.7: Delete My Pod _(MERGED into Story 7.10 — 2026-08-03)_
Superseded. Scope moved wholesale into **Story 7.10: Account & Pod Lifecycle**, where create-pod and delete-pod are designed as one reversibility problem rather than two. No scope was dropped in the merge; the recursive-delete ceremony, the "show what is destroyed, not just a name" requirement, and the no-HTTP-delete-path context all carry over.

### Story 7.8: Roles & Grants — Permission UI _(MERGED into Story 7.11 — 2026-08-03)_
Superseded. Scope moved wholesale into **Story 7.11: Effective Access & Roles**, which pairs the roles UI with the effective-access resolver it silently depended on. No scope was dropped: role-as-grant-bundle, the single-writer invariant made visible, the collective-account Control view, and FR42 read-receipt surfacing all carry over.

### Story 7.9: Backoffice-Minted Connector Credentials _(DRAFT — added 2026-08-02; CODE COMPLETE 2026-08-12, VPS deploy pending user go-ahead)_

**Shipped outcome (2026-08-12):** `/onboard/mint`, `/onboard/grants`, `/onboard/revoke` in `mcp-connector` (mounted outside `/mcp`, own rate limiter), routed via a new `hetzner-gateway` nginx location (config written, not yet deployed). `identityRegistry.js` extended with the full AC4 grant shape, atomic validated writes (`writeIdentity`/`updateIdentity`), and skip-revoked duplicate checks. Backoffice UI: mint dialog, one-time URL reveal, grants list with revoke, both on the People & apps screen. `grantId` now threads into read receipts (never the raw slug — it's a bearer credential, receipts land in someone else's pod). **The four reserved `poc:ConsentGrant` fields (`purpose`, `scope`, `excluded`, `consequenceOfRefusal`) plus `grantUri` are written and stay explicitly `null` on every entry — this story does NOT populate them, mint request-intake, or build an approval step. Do not mistake their presence for a shipped consent loop; they exist only so the next story (undrafted) doesn't have to migrate a live table.** `expiresAt` shipped as `null` everywhere — AC12's three-part UX (warn/renew/name-on-doc) wasn't built this pass, which is the AC's own named acceptable outcome. `containers[]` stays `[]` in practice — granting a container to an agent remains a manual, owner-driven act this story only *records* the intent of, never applies. Two deploy-relevant findings surfaced mid-implementation, not anticipated by the draft: `docker-compose.yml`'s `identities.json` mount had to move from `:ro` to read-write, and the atomic-write path needed an EXDEV fallback because a single-file bind mount can put the temp file and the target on different devices (rename() then fails cross-device) — unverified against the real VPS mount shape until Task 7's live check runs.

As a person onboarding, I click one button in the backoffice and receive my ready-to-paste MCP connector URL, instead of minting credentials by hand and asking an operator to edit a secrets file.
- **Why:** Story 8.7 documents today's manual path (person mints AGENT client-credentials → operator adds an `identities.json` entry + `npm run slug` → container restart). That path does not scale past a handful of teammates and puts an operator in the middle of every onboarding.
- Server-side endpoint mints AGENT client-credentials against the CSS account API using the person's **own** authenticated session, writes the `identities.json` entry, and returns the assembled connector URL **once** (reuse Story 7.4's one-time-secret UX)
- **Depends on Story 7.10** for the account session (no password re-entry) and for pod creation — without 7.10 this button automates the middle of a journey that still forces the user out of the product
- **Secrets must never flow through the browser** — minting happens server-side; the person never sees a `clientSecret`, never edits a file
- Show the person's **pod root URL** next to the connector URL — closes the live-verified gap where the agent cannot guess it and has to ask cold (8.5 finding)
- ~~Blocker: boot-time singletons~~ **RESOLVED by Story 8.6.1** (2026-08-02): lazy login on cache miss means a new identity works on its first request. **Do not build a reload path; do not add a restart step.**
- Collapses onboarding steps 4–6 of Story 8.7 into a single action
- **Redraft input, added 2026-08-11** _(security brief §5)_: the grant record this endpoint writes is the same persistence layer a future OAuth grant store needs — so give it that shape now rather than a bare `{webId, slug}` pair. Target: `slug → { credentialRef, webId, containers[], createdAt, expiresAt, lastUsedAt, revoked }`. `lastUsedAt` and `revoked` are what turn Story 8.9's journal into an actionable revocation decision; `expiresAt` is the only mechanism by which a slug ever stops being valid, since the token itself carries no expiry. This is explicitly **not** throwaway work, and the redraft should say why.
- **Revocation UI is the open question the redraft must answer** (brief, Known unknowns, still open): minting a slug is one button, but killing a leaked one has no surface at all today. Minimum shape — list of live grants (identity, scope, last used, revoke) — mints and revokes being the same screen. A mint button without a revoke path ships the leak with no exit.
- **Expiry needs a legible failure path, or it is a UX regression** _(added 2026-08-11, party-mode review)_. Today's slug never expires, so this cliff does not exist; `expiresAt` creates it. When a slug lapses, the person's connector stops answering inside claude.ai with an opaque MCP error on a surface we do not own and cannot style. She cannot read it, cannot self-serve, and what she remembers is that the pod thing broke. Required: the grants list shows remaining validity and warns *before* the wall (e.g. "expires in 4 days — renew"), renewal is one action from that same screen, and the onboarding page names the expiry so it is never a surprise. **Do not ship `expiresAt` without this.**
- **Carry the slug into the receipt entry** _(moved here from Story 8.9, 2026-08-11)_: each journal entry records which slug acted, not only the WebID. One WebID with two live slugs is currently indistinguishable in the journal — and per-slug revocation is undecidable without it. Cheap here because this story already owns the slug↔identity table; expensive anywhere else.

### Story 7.10: Account & Pod Lifecycle — Create, Protect, Delete _(ADDED 2026-08-03 — absorbs 7.7)_
As a pod owner, I can create a pod, see and set its top-level permissions, and delete it — all without leaving the backoffice or re-typing my password — so that the lifecycle of the thing I own is managed where I own it.
- **Kill the unlock gate.** VERIFIED: CSS's account cookie and the `CSS-Account-Token` are the same value (`ResolveLoginHandler.js:35-36`), and the backoffice is same-origin with CSS — the browser already holds it. Remove `accountLogin(email,password)` and the "Unlock app management" prompt; read the authed `/.account/` index with `credentials: 'include'`. Net code deletion. **Trap: that GET must carry no `content-type` header** or CSS content-negotiates a controls-less body (7.4's live finding).
- **Create a pod from the backoffice** via `controls.account.pod`. Pod names collide **globally across the instance**, not per-account — a duplicate is refused `409 Conflict` (verified in `TemplatedPodGenerator.generate`, 2026-08-03). Surface that as a name-availability affordance, not a raw error.
- **Show the pod-root ACL as a real row.** CSS's pod template grants `foaf:Agent` `acl:Read` on `<./>` with no `acl:default` — the pod root is publicly *listable* while its children are not. Today no UI row exists for it. Make it visible, explain it, make it editable.
- **Protected-resource guardrails.** `profile/card` is the WebID document; deleting it breaks OIDC login and orphans every `.acl` that names that WebID, with no versioning and no undo. It currently carries the same delete affordance as a throwaway note. Distinct treatment + an explanation of what breaks — not a scary modal.
- **Delete a pod** (absorbed from 7.7): owner-driven recursive deletion, ceremony proportional to what is lost, confirmation shows what is about to be destroyed rather than just a name. Closes the orphan-accumulation gap — CSS exposes no HTTP delete path for accounts or pods.
- **Welcoming README template.** Override CSS's stock `README` (no extension, reads as `text`, says nothing) with a `README.md` that explains ownership, what is public by default, and where the identity document lives. **Lockstep requirement:** `README.acl.hbs` hardcodes `acl:accessTo <./README>` — rename without overriding it in the same change and the welcome file loses its public ACL. Same bind-mount mechanism as Story 7.2.
- WCAG 2.1 AA

### Story 7.11: Effective Access & Roles _(ADDED 2026-08-03 — absorbs 7.8; **SPLIT into 7.11a / 7.11b 2026-08-11**, party-mode review)_

Split on scope: the resolver and the badge fix are load-bearing for the PoC (7.5 depends on the resolver, and the badge currently tells users something unanswerable). Roles-as-grant-bundles is a *team* concern — a newcomer has one pod and one agent, and nothing in the newcomer journey exercises a role. Shipping them together put the MVP's critical path behind a collective-access UI nobody in the PoC uses.

### Story 7.11a: Effective Access — Resolver & Badge Truth _(IN SCOPE)_
As a pod owner, I can see what access actually applies to a resource — not just that it "inherits from parent".
- **Effective-access resolver.** `pod-api.js:253` returns `inherited: true` with empty agents/public when no standalone `.acl` exists, and nothing ever walks upward to resolve what the parent's `acl:default` actually grants. Build that walk once. Consumed here and by Story 7.5's export sidecars.
- **Finish the sentence the badge starts.** "Inherits from parent" is accurate but unanswerable — it must state what the parent grants, or link to the row that does.
- Surface the **single-writer invariant** visibly: "my pod, my agent writes" vs "someone else's pod, I hold a grant" are different mental objects that currently render identically. Kept in scope because it is the mental model a *single* newcomer needs, not a team feature.
- **Honesty constraint:** never offer an "only me" control at pod scope that the protocol will not honour. `profile/card` stays public by necessity (WebID discovery). If a user restricts the pod root, tell them why that one resource remains public rather than letting them find the inconsistency later.
- **Sequencing:** runs after 7.9, before 7.5.
- WCAG 2.1 AA

### Story 7.11b: Roles & Collective Access _(DEFERRED to post-PoC — 2026-08-11)_
Role = named grant bundle (absorbed from 7.8): define once (containers + modes), assign/unassign personal-agent WebIDs, revoke an assignment without touching the underlying identity. Collective-account view: which role holds `acl:Control`, who is assigned, how succession reassigns it. Read receipts (FR42, built in Story 8.6) surfaced to the data subject.

**Why deferred, not dropped:** roles are how the model scales to Singelijn and partner orgs — architecture.md BP-6 is written and the invariant is real. But no PoC journey has two people sharing a pod, so the UI would ship untested against its own use case. Recorded in `post-poc-backlog.md`; re-enters at the first multi-person pod. The receipt-surfacing bullet travels with it — a receipts view for a pod nobody else reads shows an empty list.

### Story 7.12: Agent Identity Lifecycle _(ADDED 2026-08-19 — live CSS investigation; found missing from this file by the planning-docs-consolidation drift check, 2026-08-20)_

As a pod owner, I can mint a dedicated agent WebID inside my own pod (instead of an agent's connector binding to my personal WebID) so an agent's blast radius is confined to what I explicitly grant it.

- **Finding that motivated the story:** WebID:Pod is n:1, not 1:1. CSS keeps two independent registrations that were being conflated — `webIdLink` (WebID→Account, gates credential minting via `isLinked`) and pod ownership (WebID→Pod, full Control). `LinkWebIdHandler` links any WebID under a pod your account created with no ownership challenge, so one pod can host many agent WebIDs.
- **Corrects our own mint gate:** `accountControlsWebId()` previously prefix-matched pod `baseUrl`s; CSS's real rule is `isLinked`.
- **Hard constraint:** the resource server dereferences the WebID anonymously for `solid:oidcIssuer`, so a non-public WebID doc cannot authenticate — verified at creation time rather than surfacing inside claude.ai hours later.
- **Out of scope, stated as such:** pod deletion (no `DeletePodHandler` in CSS) and "Add owner" (full Control — wrong tool for a scoped agent). Orphaned pods are recoverable: unlinking doesn't delete the profile doc, re-linking restores control.
- **Shipped 2026-08-20:** agent identities UI in the backoffice, corrected mint gate, deployed to VPS, code-reviewed (7 patches applied, 7 deferred). Task 6.4 (retiring `agent-smithwhite`) deliberately left open, non-blocking. See `7-12-agent-identity-lifecycle.md`.

### Story 7.13: Origin Split — Backoffice & Valisette Off pod.nicolasdb.eu _(ADDED 2026-08-26 — live SSO-bounce investigation, commit 6432771)_

As a pod owner running two Solid apps (backoffice, Valisette) on my own server, I want each app on its own subdomain instead of sharing `pod.nicolasdb.eu` with the CSS provider, so the apps stop fighting over browser-global session state and `pod.nicolasdb.eu` can be a plain Solid provider any client can trust.

- **Finding that motivated the story:** `@inrupt/solid-client-authn-browser@2.3.0`'s `session.login()` calls `clearOidcPersistentStorage()` at the start of every login, which wipes every `oidc.*` and `solidClientAuthenticationUser:*` localStorage key **origin-wide, with no per-app scoping** — confirmed against the library's own npm dist source. Logging into one app silently deletes the other's session. The `solidClientAuthn:currentSession` pointer (also one per origin) compounds it by making `restorePreviousSession` redirect to whichever app logged in most recently. Story 7.1's `Solid.namedSession`/`canRestore` guard (commit 6432771) reduces the second mechanism but cannot touch the first — confirmed live by Nicolas: signing out of Valisette restored backoffice access.
- **The only real fix:** all three mechanisms read/write `window.localStorage`, which is origin-scoped by the browser itself. Two origins, two independent storages, problem gone — not patched around.
- **Not in scope:** the cookie→token auth rework and provider-agnostic pod management (Story 7.14) — found in the same investigation but independent of the origin split.
- See `7-13-origin-split-portable-apps.md`.

### Story 7.14: Backoffice Auth — Token Header + Provider-Agnostic Pod Management _(ADDED 2026-08-26 — same investigation as 7.13)_

As a pod owner, I want the backoffice to authenticate with a portable `Authorization` header instead of a same-site cookie, and to manage a pod on any Solid provider (not just this CSS instance), so the app is genuinely hostable anywhere and genuinely Solid-spec-compliant where the underlying operation is.

- **Finding that motivated the story:** all 13 `credentials:'include'` call sites in `backoffice/pod-api.js` rely on the `css-account` cookie's `SameSite=Lax` behaviour, which only survives being split across subdomains (Story 7.13) because both stay under `nicolasdb.eu`. CSS's own docs (confirmed current, Context7 2026-08-26) document `Authorization: CSS-Account-Token <value>` as the header equivalent of that cookie — issued by the same login call, accepted everywhere the cookie is. Switching removes the same-site coupling entirely.
- **Second, independent finding:** the backoffice's file-manager half (browse/CRUD/upload/ACL) is plain LDP+WAC — spec-compliant, works against any Solid provider — but `pod-api.js` hardcodes `ISSUER = "https://pod.nicolasdb.eu/"` and derives the pod root from CSS's one-pod-per-top-level-segment URL convention rather than the WebID profile's `pim:storage`. The account-console half (register/create-pod/mint-credential) is genuinely CSS-proprietary — no equivalent API exists on other providers — and must be hidden, not broken, when the connected provider isn't CSS.
- **`mcp-connector`'s `/onboard/*` routes read the `css-account` cookie directly** (`onboardRouter.js`, stated in its own header comment) and carry zero CORS headers today (confirmed live: cross-origin probe → 401, no `access-control-*`). These break the moment backoffice moves origin under 7.13 unless they move to the same header scheme.
- **Depends on 7.13** shipping first (origin split is what makes the cookie's limits visible/blocking in the first place, and `/onboard/`'s CORS gap only bites once backoffice is cross-origin).
- See `7-14-token-auth-provider-agnostic-pods.md`.

### Story 7.15: Valisette — TOML Write-Back for Rate Compatibility _(ADDED 2026-08-26 — Rate pipeline handoff, party-mode UX review)_

As the person triaging Otis gists in Valisette, I want each swipe to patch the `validation` field of the gist directly in the grouped `capture/gists/YYYY-MM-DD.toml` file the cleanup pass already writes, so the 9h Rate pipeline can ingest straight from that one buffer instead of a separate aggregate file Valisette used to build.

- **Contract change:** Valisette no longer rebuilds and writes its own `triage-YYYY-MM-DD.toml` into a separate `triage/` folder (`buildTOML`, deleted). It string-patches the single `validation = "..."` line for one gist, in place, in the source file — read → patch → PUT with `If-Match`, re-read on every swipe (never a cached copy) so a Rate run landing mid-session can't be clobbered.
- **Deck scope widened:** loads every `pending` gist across all non-ingested `.toml` files in the source folder, newest file first — a backlog never gates tonight's fresh gists, and never disappears unannounced (resurfaced gists show their original date).
- **Third outcome:** swipe-up now commits `anagnorisis` directly (peer to validated/rejected), replacing the old multi-select flag tray. Flags (`revisit`/`priority`) and the comment field are dropped — nothing in the new contract has anywhere for them to land.
- **Undo re-patches** the file back to `pending` rather than only rolling back local state, and its enable-gate moved off "unsaved batch" (which no longer exists) onto "there is a last swipe."
- **Rate-side dependency (assumed, not built here):** the Rate must stamp a file's `ingested = true` only once no gist in it remains `pending`, so nothing is stranded behind an early stamp. Out of scope for this story.
- See `7-15-valisette-rate-toml-writeback.md`.

## Epic 1: Pod Sovereignty & Access Control

Learners own their data in Solid Pods with enforceable, auditable access control — the fundamental sovereignty primitive is proven and adversarially validated.

### Story 1.1: Project Scaffold & Service Orchestration

As a **developer**,
I want a single `docker-compose up` command that starts all infrastructure services with health checks and dependency ordering,
So that I have a reproducible, portable development environment from the first commit.

**Acceptance Criteria:**

**Given** a fresh clone of the repository with `.env` configured
**When** I run `docker-compose up`
**Then** CSS, Oxigraph, Qdrant, and Nginx containers start with pinned versions (CSS 7, Oxigraph 0.5.6, Qdrant v1.17.0, Nginx 1.28.2-alpine)
**And** all services report healthy within 60s
**And** `depends_on: condition: service_healthy` enforces startup order

**Given** the repository is cloned on Fedora (SELinux) or Ubuntu
**When** `VOLUME_FLAGS` is set to `:Z` (Fedora) or empty (Ubuntu) in `.env`
**Then** bind mounts for persistent data work correctly on both hosts

**Given** the project root
**When** I inspect the repository
**Then** README.md, LICENSE, CODE_OF_CONDUCT.md, CONTRIBUTING.md, and `.env.example` exist
**And** the project directory structure matches the Architecture doc scaffold (`infra/`, `pipeline/`, `agents/`, `dashboard/`, `scripts/`, `data/`, `tests/`)

### Story 1.2: Nginx Content Negotiation Spike

As a **developer**,
I want Nginx to reverse-proxy CSS with Linked Data content negotiation (Turtle, JSON-LD),
So that Pod resources are served with appropriate RDF serialization formats.

**Acceptance Criteria:**

**Given** CSS is running behind Nginx
**When** a client requests a Pod resource with `Accept: text/turtle`
**Then** the response is served as Turtle (`.ttl`)

**Given** CSS is running behind Nginx
**When** a client requests a Pod resource with `Accept: application/ld+json`
**Then** the response is served as JSON-LD

**Given** the spike exceeds 3 calendar days without working content negotiation
**When** the timebox expires
**Then** Nginx is removed from the request path and agents access CSS directly on port 3000
**And** the decision is documented in the Architecture doc

**Given** content negotiation works (spike succeeds) or fallback is applied (spike fails)
**When** the story is complete
**Then** a clear verdict (pass/fallback) is recorded and the rest of the epics proceed on the chosen path

### Story 1.3: Pod Provisioning & ACL Configuration

As a **learner persona** (Ayoub, Claire's students, Fatima's children),
I want my own Solid Pod provisioned with role-based access controls,
So that my learning data is stored under my exclusive control with appropriate access granted to authorized roles.

**Acceptance Criteria:**

**Given** CSS is running and healthy
**When** the provisioning script (`scripts/seed-pods.sh`) executes
**Then** 5 individual pods are created (Ayoub, Lucas, Emma, Youssef, Nour)
**And** 1 community pod is created (school-community)

**Given** pods are provisioned
**When** ACL configuration is applied
**Then** each pod has WebACL resources (`.acl` files) granting access per role:
- Tutor (Claire): read access to her students' pods
- Parent (Fatima): read access to her children's pods
- Admin (Marc): read/write on school-community pod, read on student pods
- Regional (Isabelle): aggregate read access
- Student (Ayoub): full control of own pod

**Given** a provisioned pod with ACLs
**When** an authorized role accesses a pod resource
**Then** the response is returned successfully

**Given** a provisioned pod with ACLs
**When** an unauthorized role accesses a pod resource
**Then** the request is denied (HTTP 403)

### Story 1.4: ACL Grant, Revocation & Audit

As a **school administrator** (Marc),
I want to dynamically grant and revoke ACL access on Pod resources and view the current consent state,
So that access control reflects real-world events (transfers, enrollment changes) and consent is auditable.

**Acceptance Criteria:**

**Given** an existing pod with configured ACLs
**When** a new ACL grant is issued (e.g., new school gets read access)
**Then** the pod's `.acl` resource is updated to include the new grant
**And** the newly granted role can access the pod resource

**Given** an existing pod with an active ACL grant
**When** the grant is revoked (e.g., old school access removed)
**Then** the pod's `.acl` resource is updated to remove the grant
**And** the revoked role receives HTTP 403 on subsequent access attempts

**Given** an existing pod with configured ACLs
**When** an authorized user requests the ACL/consent state
**Then** the current access grants are displayed showing who has what level of access
**And** the output is human-readable (not raw Turtle unless requested)

### Story 1.5: Troll ACL Enforcement Validation

As a **security reviewer** (funder audience),
I want the troll agent to adversarially test ACL enforcement by directly accessing the data infrastructure,
So that I have evidence that the sovereignty primitive actually enforces its access controls.

**Acceptance Criteria:**

**Given** pods are provisioned with role-based ACLs
**When** the troll agent attempts to read a pod resource without a valid ACL grant (direct HTTP to CSS)
**Then** the request is denied (HTTP 403)
**And** the test result is logged as `pass` in structured JSON format

**Given** pods with multi-role ACLs
**When** the troll agent attempts to access pod resources using each role's credentials against pods they should NOT have access to
**Then** all unauthorized access attempts are denied
**And** each test is logged with category `acl_enforcement`, access path `direct`, and result `pass` or `fail`

**Given** all ACL enforcement tests have executed
**When** the troll test suite completes
**Then** a summary is produced with pass/fail counts per test
**And** the troll's dual access pattern is established (direct infrastructure access verified, skill-mediated access deferred to Epic 2)

**Given** any ACL enforcement test fails
**When** the test result is `fail`
**Then** the failure is a blocking issue — ACL enforcement must pass per NFR5

## Epic 2: Semantic Data Intelligence

Learning data flows through a lossless xAPI→OSLO pipeline into a three-layer architecture (Pod→Graph→Vector) with full bidirectional provenance and adversarially validated query security.

_Plan→execution reconciliation (2026-08-02): renumbered to match what was actually built. Planned 2.2 (dataset generation) was never a story — the PRD classes it as an external input. Planned 2.5 split into executed 2.5 + 2.6; planned 2.6 split into executed 2.7 + 2.8; executed 2.4 (round-trip recovery) had no plan entry. Story files are authoritative for detail._

### Story 2.1: OSLO Vocabulary Schema Contract

As a **developer**,
I want a documented vocabulary schema mapping xAPI concepts to OSLO education classes,
So that the ingestion pipeline and agent query layer share a common semantic contract (the Phase 2→3 bridge).

**Acceptance Criteria:**

**Given** the OSLO education vocabularies (data.vlaanderen.be) and xAPI statement structure
**When** the schema contract is defined
**Then** Turtle files exist in `data/schemas/` mapping xAPI Actor, Verb, Object, Result, Context to OSLO education classes
**And** `oslo-education.ttl`, `oslo-person.ttl`, `xapi-to-oslo.ttl`, and `pocpod0-vocab.ttl` are created

**Given** the schema contract files
**When** a developer or agent reads them
**Then** namespace prefixes follow OSLO conventions (`oslo-educ:`, `oslo-person:`, `xapi:`, `pocpod0:`)
**And** the mapping is sufficient to convert any xAPI statement in the synthetic dataset to OSLO-mapped RDF

**Given** the schema contract
**When** loaded into Oxigraph
**Then** the schema validates without errors and SPARQL queries using OSLO classes return correct results

### Pre-requirement: Synthetic xAPI Dataset Generation _(never executed as a story)_
_Reconciled 2026-08-02: the PRD classes the dataset as "an external input, not a system capability", and execution treated it that way. Kept here as the input the pipeline stories assume._

As a **developer**,
I want a synthetic xAPI dataset (~10K statements) representing a realistic Belgian K-12 school semester,
So that the ingestion pipeline has realistic input data covering all 5 persona scenarios.

**Acceptance Criteria:**

**Given** the 5 learner personas (Ayoub, Claire's 2 students, Fatima's 2 children)
**When** the dataset is generated
**Then** ~10K xAPI statements are produced in `data/synthetic/`
**And** statements cover: course activities, assessments, tutoring sessions, self-study, extracurricular (robotics workshop), cross-institutional contexts

**Given** the generated dataset
**When** analyzed for scenario coverage
**Then** data supports Claire's cross-context query (struggling student with hidden tutoring progress)
**And** data supports Fatima's multi-child unified view (two children, two schools, NL+FR)
**And** data supports Marc's transfer scenario (student transferring NL→FR)
**And** data supports Isabelle's aggregate policy query (STEM program impact across communities)
**And** data supports Ayoub's full learning history for governance/deletion scenarios

**Given** the dataset
**When** validated against xAPI specification
**Then** all statements are valid xAPI JSON

### Story 2.2: xAPI→OSLO RDF Ingestion Pipeline

As a **developer**,
I want a pipeline that converts xAPI statements to OSLO-mapped RDF triples and stores them as Turtle resources in learner Pods,
So that raw learning data is losslessly transformed into a semantically rich format under learner sovereignty.

**Acceptance Criteria:**

**Given** the synthetic xAPI dataset and the OSLO schema contract
**When** the ingestion pipeline (`pipeline/src/pocpod0_pipeline/ingest.py`) processes the dataset
**Then** each xAPI statement is converted to OSLO-mapped RDF triples using the schema contract
**And** the resulting Turtle resources are stored in the appropriate learner Pod via CSS

**Given** a pipeline run processing ~10K statements
**When** individual statements fail conversion
**Then** the failure is logged and the pipeline continues (log+continue error handling)
**And** a summary reports total processed, succeeded, and failed counts

**Given** the pipeline has completed
**When** I inspect the Pod resources
**Then** each learner Pod contains Turtle resources representing their learning activities
**And** the conversion is lossless — original xAPI data is preserved within the RDF representation

### Story 2.3: Oxigraph Setup — RDF Storage with Provenance

As a **developer**,
I want RDF triples loaded into Oxigraph with provenance links back to source Pod resources,
So that every triple is traceable to its origin and any original xAPI statement can be recovered from the graph.

**Acceptance Criteria:**

**Given** Turtle resources stored in learner Pods
**When** the graph loader (`pipeline/src/pocpod0_pipeline/load_graph.py`) executes
**Then** all RDF triples are loaded into Oxigraph
**And** each triple includes `prov:wasDerivedFrom <pod-resource-uri>` provenance metadata

**Given** 10K+ triples loaded in Oxigraph
**When** a simple SPARQL query is executed
**Then** the response time is < 500ms (NFR1)

**Given** a specific Pod resource URI
**When** I query Oxigraph for all triples derived from that resource
**Then** all derived triples are returned with correct provenance links

**Given** any triple in Oxigraph
**When** I follow the provenance link back to the Pod resource and extract the original data
**Then** the original xAPI statement is recoverable (round-trip verification, FR10)

### Story 2.4: Round-Trip xAPI Recovery Verification _(added in execution — recorded 2026-08-02)_
As a developer, I want to verify that any original xAPI statement can be recovered by following provenance links from Oxigraph back through Pod resources, so that the pipeline's "lossless" claim is proven by a concrete round-trip test rather than asserted.
- Proves FR10; the evidence behind the PRD's "any original statement recoverable" measurable outcome

### Story 2.5: Qdrant Setup & Vector Embeddings
_Reconciled 2026-08-02: planned as one story ("Vector Embeddings with Bidirectional Traceability"); execution split it into 2.5 (embeddings) and 2.6 (traceability verified end-to-end). The criteria below cover both._

As a **developer**,
I want vector embeddings generated for semantically significant content and stored in Qdrant with full traceability metadata,
So that semantic search is possible while maintaining bidirectional links between embeddings, triples, and Pod resources.

**Acceptance Criteria:**

**Given** RDF triples loaded in Oxigraph with provenance
**When** the embedding pipeline (`pipeline/src/pocpod0_pipeline/embed.py`) processes semantically significant content
**Then** embeddings are generated via OpenRouter API (qwen/qwen3-embedding-8b, NFR21)
**And** embeddings are batch-upserted into Qdrant

**Given** an embedding stored in Qdrant
**When** I inspect its payload metadata
**Then** it contains `triple_uris` (array of source Oxigraph triple URIs) and `pod_resource_uri` (source Pod resource)

**Given** any embedding in Qdrant
**When** I follow the traceability chain
**Then** I can navigate: embedding → triple URIs → Oxigraph triples → Pod resource URI → Pod resource (full bidirectional traceability, FR12)

**Given** a Pod resource URI
**When** I search Qdrant for points with matching `pod_resource_uri` in payload
**Then** all derived embeddings are returned (reverse traceability)

### Story 2.6: Bidirectional Traceability — Embedding, Triple, Pod _(split from planned 2.5 — recorded 2026-08-02)_
As a developer, I want full bidirectional traceability between embeddings, triples and Pod resources verified end-to-end, so that any component of the three-layer model can be navigated to its source or derived artifacts — the precondition for deletion cascade and provenance display.
- Proves FR12; load-bearing for Epic 5's deletion cascade

### Story 2.7: Troll SPARQL Injection Validation
_Reconciled 2026-08-02: planned as one story ("Troll SPARQL Injection & Vector Privacy Validation"); execution split it into 2.7 (injection) and 2.8 (vector privacy). The criteria below cover both._

As a **security reviewer** (funder audience),
I want the troll agent to test SPARQL injection resistance and vector store privacy,
So that I have evidence the data intelligence layer resists query manipulation and doesn't leak PII through embeddings.

**Acceptance Criteria:**

**Given** the parameterized SPARQL query templates (`.rq` files) in `agents/skills/sparql-query/templates/`
**When** the troll agent sends injection payloads through the shared SPARQL skill interface
**Then** all injection attempts are blocked by the parameterized template mechanism
**And** each test is logged with category `sparql_injection`, access path `through_skill`, and result `pass` or `fail`

**Given** any SPARQL injection test fails
**When** the test result is `fail`
**Then** the failure is a blocking issue — injection resistance must pass per NFR6

**Given** embeddings stored in Qdrant
**When** the troll agent directly queries Qdrant with semantic similarity searches designed to extract PII
**Then** each probe is logged with category `vector_privacy`, access path `direct`, and result `pass`, `partial`, or `fail`
**And** findings are documented honestly — partial/fail results are assessment findings, not blocking issues (NFR8)

**Given** all injection and vector privacy tests complete
**When** the troll test suite for Epic 2 finishes
**Then** a summary is produced with pass/partial/fail counts per category

### Story 2.8: Troll Vector Privacy Validation _(split from planned 2.6 — recorded 2026-08-02)_
As a security reviewer (funder audience), I want the troll agent to query Qdrant directly with semantic-similarity searches designed to extract PII from embeddings, so that I get an honest assessment of whether embeddings leak personally identifiable information.
- Proves FR31. A **probabilistic surface**: assessed and documented, not required to pass — honest reporting is the bar (NFR Security)


## Epic 3: Cross-Context Learning Insights

Role agents (Claire, Fatima, Isabelle) query across institutional silos, compare graph-only vs. hybrid results, and surface provenance — delivering the "aha moment" that makes the PoC compelling. Stories tagged [foundation] vs [journey], priority [must-ship] vs [target].

_Plan→execution reconciliation (2026-08-02): renumbered to match what was actually built. Planned 3.1 split into executed 3.1 (SPARQL skill) + 3.3 (OpenClaw runtime, done FIRST to de-risk); journeys shifted 3.3→3.4, 3.4→3.5, 3.5→3.6; executed 3.7 (graph-vs-hybrid) and 3.7.1 (TUI, later abandoned) had no plan entries; planned 3.6 became executed 3.8. Execution order was 3.3→3.1→3.2→3.4→3.7→3.5→3.6→3.8. Story files are authoritative for detail._

### Story 3.1: [foundation] Shared SPARQL Skill Foundation
_Reconciled 2026-08-02: planned as "OpenClaw Agent Runtime & Shared SPARQL Skill"; execution split the runtime out into Story 3.3, which was then done FIRST to de-risk OpenClaw. The criteria below cover both._

As a **developer**,
I want the OpenClaw agent runtime configured with a shared SPARQL skill that validates ACLs and executes parameterized queries,
So that all role agents have a secure, reusable foundation for querying the graph layer.

**Acceptance Criteria:**

**Given** OpenClaw is installed with `openclaw.config.yaml` pointing to OpenRouter API (minimax/minimax-m2.5)
**When** the agent runtime starts
**Then** the OpenRouter connection is verified and the runtime is ready to spawn agents

**Given** the shared SPARQL skill (`agents/skills/sparql-query/`)
**When** an agent calls the skill with a query request and role identity
**Then** the skill validates the agent's role against Pod ACLs before executing
**And** selects the appropriate parameterized `.rq` template
**And** executes the query against Oxigraph
**And** returns results with provenance metadata (`prov:wasDerivedFrom` URIs)

**Given** an agent with insufficient ACL permissions
**When** it calls the SPARQL skill for a resource it cannot access
**Then** the skill denies the query and returns an access-denied response
**And** the denial is logged in structured JSON format (NFR9)

**Given** any SPARQL skill execution
**When** the query completes
**Then** a log entry is emitted with timestamp, requesting agent, latency, and result count (NFR9)

### Story 3.2: [foundation] Shared Qdrant Skill & Hybrid Query Composition

As a **developer**,
I want a shared Qdrant skill for semantic search and the ability for agents to compose hybrid queries by merging SPARQL and vector results,
So that agents can deliver semantically enriched insights beyond what structured queries alone provide.

**Acceptance Criteria:**

**Given** the shared Qdrant skill (`agents/skills/qdrant-search/`)
**When** an agent calls the skill with a semantic search query
**Then** the skill executes a similarity search against Qdrant
**And** returns results with `triple_uris` and `pod_resource_uri` traceability metadata

**Given** an agent wants a hybrid query result
**When** the agent calls both the SPARQL skill and the Qdrant skill
**Then** the agent receives both result sets
**And** the agent merges them based on its persona context and query intent

**Given** a hybrid query execution
**When** both skills return results
**Then** the combined response time is < 2s (NFR2)

### Story 3.3: OpenClaw Agent Infrastructure & Role Persona Configurations _(split from planned 3.1 — recorded 2026-08-02)_
As a developer, I want the OpenClaw multi-agent runtime configured with all 5 role personas and the troll adversary, so that every journey story can run its agent against the shared SPARQL and Qdrant skills with proper persona context, ACL identity and query patterns.
- **Executed FIRST in Epic 3** (order 3.3 → 3.1 → 3.2 → 3.4 → 3.7 → 3.5 → 3.6 → 3.8) to de-risk OpenClaw before journey work depended on it

### Story 3.4: [journey] [must-ship] Claire — Cross-Context Insight Discovery

As **Claire** (secondary school teacher, Brussels),
I want to query cross-institutional student progress and see both graph-only and hybrid results side by side with provenance,
So that I discover the full picture of a struggling student — including learning contexts invisible to my school platform.

**Acceptance Criteria:**

**Given** Claire's agent is configured (`agents/claire-teacher/agent.yaml`) with her persona and ACL role
**When** Claire queries "Which students are struggling with quadratic equations across all learning contexts?"
**Then** the SPARQL skill returns graph-only results scoped to Claire's ACL permissions (FR14, FR17)

**Given** the same query
**When** executed as a hybrid query (SPARQL + Qdrant)
**Then** the hybrid results include semantically enriched insights (e.g., "tutoring notes show student is grasping concepts through geometric visualization")

**Given** both graph-only and hybrid results
**When** displayed to Claire
**Then** the results are shown side by side for comparison (FR16)
**And** the hybrid result visibly adds value over graph-only (the "aha moment")

**Given** any query result
**When** Claire inspects provenance
**Then** the system shows which triples, from which Pod resources, contributed to the result (FR20)
**And** the provenance chain is navigable: result → triples → Pod resources

**Given** Claire queries for students outside her ACL scope
**When** the query executes
**Then** only data from authorized pods is returned — no cross-role leakage (NFR7)

### Story 3.5: [journey] [target] Fatima — Unified Parental View

As **Fatima** (parent of two children, bilingual Brussels household),
I want to see a unified view of both my children's learning progress across their different schools and activities,
So that I can make informed decisions from a position of sovereignty, not dependency on fragmented platforms.

**Acceptance Criteria:**

**Given** Fatima's agent is configured with parental ACL access to both children's pods
**When** Fatima queries for a unified view of both children
**Then** the results combine data from both children across all learning contexts (school, tutoring, extracurricular)
**And** data from both NL and FR school contexts is included seamlessly via structured RDF (FR18)

**Given** Fatima's query results
**When** displayed to Fatima
**Then** each child's progress is distinguishable within the unified view
**And** provenance shows which Pod resources contributed to the view

**Given** Fatima's ACL scope
**When** she queries for data beyond her children's pods
**Then** no unauthorized data is returned

### Story 3.6: [journey] [target] Isabelle — Evidence-Based Policy

**Persona context:** Isabelle is a regional education policy advisor for Brussels-Capital Region. Education is a community competence (VGC/COCOF) — Isabelle funds cross-community extracurricular programs but has no jurisdiction over schools and cannot compel communities to share student outcome data. Her contractual leverage (grant conventions with rapportage obligations) produces Word/PDF self-reported narratives, not auditable data. Her demo moment is not being impressed by numbers — it is **relief**: seeing cross-community impact data for the first time after years of making funding decisions blind. EU alignment: the EU Data Governance Act (in force 2023) is designed for exactly this — federated consent-based aggregation across institutional boundaries. This system is DGA-forward infrastructure.

**Query approach (B' — cross-context aggregate):** The aggregate does not query robotics scores (none exist in the data). Instead it finds students who attended the funded robotics program and aggregates their scores across ALL their activities. This is the architecturally correct question: "did students who participated in the funded program show improvement across their broader learning?" This requires no synthetic data and demonstrates the system's cross-pod, cross-context capability — impossible with Word documents even if both communities cooperated. Vocabulary: all predicates use `poc-pod0.edu/vocab/` (NOT oslo-educ, which is not present in the data).

As **Isabelle** (regional education policy advisor, Brussels-Capital),
I want to query aggregate anonymized program impact across communities,
So that I can justify funding decisions with evidence-based data instead of self-reported narratives.

**Acceptance Criteria:**

**Given** Isabelle's agent is configured with regional aggregate-read ACL access
**When** Isabelle queries "What is the measurable impact of funded STEM programs on participating students?"
**Then** the system returns cross-context aggregate results: participant count + avg scores across ALL activities for students who attended the robotics program, spanning both NL and FR communities (FR19)
**And** no individual student data is exposed — results are anonymized via GROUP BY at the aggregate level
**And** anonymization is structural (GROUP BY makes individual retrieval impossible by query construction, not by policy)

**Given** aggregate query results
**When** Isabelle inspects provenance
**Then** the system shows: "this aggregate is derived from N named graphs across M student pods, all with active regional-access consent grants"
**And** anonymization guarantee statement is displayed: "No individual student data was accessed or returned. All results are aggregated across all learning activities."

**Given** Isabelle attempts a query that would return individual student data
**When** the query executes
**Then** the system enforces aggregate-only access — no individual records returned
**And** the denial is logged with structured JSON including reason and allowed templates

### Story 3.7: Graph-Only vs Hybrid Comparison _(added in execution — recorded 2026-08-02)_
As a researcher / funder audience, I want a systematic, reproducible comparison of graph-only and hybrid query results across all students in Claire's scope, so that the benefit of combining SPARQL with vector search is measurable, not anecdotal.
- Proves FR16; the reusable demo artifact behind Journey 2's "aha moment"

### Story 3.7.1: Pipeline Dashboard TUI _(added in execution, direction later abandoned — recorded 2026-08-02)_
Done, then superseded: the TUI approach was dropped in favour of the ACL dashboard (Story 6.2). Retained as history — see the archived `architecture_dashboard_tui_decision` note.

### Story 3.8: [foundation] Troll Cross-Inference Validation

As a **security reviewer** (funder audience),
I want the troll agent to test cross-inference data leakage via natural language prompts through the agent layer,
So that I understand whether an agent can be tricked into revealing data it shouldn't have access to.

**Acceptance Criteria:**

**Given** role agents are running with their configured ACL scopes
**When** the troll agent sends NL prompts through the agent layer designed to elicit cross-role data (e.g., asking Claire's agent about Isabelle's policy data)
**Then** each probe is logged with category `cross_inference`, access path `through_agent`, and result `pass`, `partial`, or `fail`

**Given** this is an LLM-dependent test
**When** results are recorded
**Then** the test category is explicitly flagged as probabilistic/non-deterministic (NFR13)
**And** findings are documented honestly — partial/fail results are assessment findings, not blocking issues (NFR8)

**Given** all cross-inference tests complete
**When** the troll test suite for Epic 3 finishes
**Then** a summary is produced documenting each probe, the agent tested, and the result

## Epic 4: Student Transfer & Data Portability

The school transfer scenario (NL→FR) executes end-to-end — ACL grants, revocations, cross-community data handling — proving data moves with the learner, not the institution. [must-ship] — Marc's journey.

### Story 4.0: [must-ship] Discord & Seed-on-Boot Infrastructure

As **project lead** (Nicolas),
I want all 6 OpenClaw agents reachable via Discord channels with evolvable workspaces and periodic heartbeat behaviors,
So that funders and external visitors can interact with every persona-agent directly, and agent identities can evolve through conversation.

**Prerequisite checklist (5 Epic 5/6 carried items — resolve before dev starts):**
- [ ] NFR-LAG: Latency baseline documented (NFR1 <500ms, NFR2 <2s — confirm with real run or note as known gap)
- [ ] IG-1: CSS 404 semantics documented (resource not found vs. unauthorized — note behavior in architecture.md)
- [ ] ACL-DRIFT: ACL dashboard known drift scenario documented (what causes false positives — noted in Story 6.2 code review)
- [ ] Consent events catalog: All emitted event types listed (`acl.grant`, `acl.revoke`, `token.issued`, `token.expired`, `receipt.written`) in architecture.md or a dedicated doc
- [ ] Invalidated assumptions template: Added to story template in `.claude/skills/bmad-create-story/` so SM pre-populates from memory going forward

**Acceptance Criteria:**

**Given** the Dockerfile
**When** `docker-compose up` runs for the first time
**Then** the entrypoint copies agent seed files from `/app/agents-seed/{id}/` to `/home/node/.openclaw/workspaces/{id}/` for each agent that has no workspace yet
**And** subsequent restarts do NOT overwrite existing workspace files (idempotent seed)
**And** `docker-compose down -v && docker-compose up` performs a full factory reset to seeded state

**Given** the Discord bot token configured in `.env`
**When** `docker-compose up` completes
**Then** all 6 agents (claire-teacher, marc-admin, isabelle-policy, fatima-parent, ayoub-student, troll-adversary) are bound to individual Discord channels in `openclaw.json`
**And** a #general channel is bound for cross-agent visibility
**And** a #security_logs channel is bound for troll reports
**And** each agent is reachable via Discord DM and its bound channel

**Given** a HEARTBEAT.md file in each agent's seeded workspace
**When** the OpenClaw heartbeat fires
**Then** troll-adversary runs a probe subset and posts a short report to #security_logs
**And** isabelle-policy posts an aggregate check to #general
**And** claire-teacher sends a student check-in to her channel

**Given** per-scenario named volumes configured (`openclaw-data-{scenario}`)
**When** multiple scenario containers run
**Then** workspace state does not leak between scenarios

**Implementation notes:**
- Dockerfile: `COPY agents/ /app/agents-seed/` + entrypoint script seeds on first boot
- `openclaw.json`: add `bindings` array per agent with Discord channel IDs
- Discord bot: bot token in `.env` as `DISCORD_BOT_TOKEN`, server ID as `DISCORD_GUILD_ID`
- HEARTBEAT.md: per-agent schedule + behavior description (troll: probe 3 categories; Isabelle: aggregate query; Claire: check-in message)
- Named volumes: `openclaw-data` → `openclaw-data-default` (rename), document pattern in README

---

### Story 4.0.1: [infra] Force-Pasta Local Fix _(inserted during execution — recorded here 2026-08-02)_
As project lead, I want the OpenClaw gateway WebUI reachable on `http://localhost:18789` via `podman compose up` on Fedora Kinoite 42, so that local Epic 4 iteration is unblocked without deploying to VPS.
- Unplanned insertion: local podman-compose/pasta networking bug, not foreseen at epic-planning time

### Story 4.0.2: [infra] VPS Deploy — Hetzner _(inserted during execution — recorded here 2026-08-02)_
As project lead, I want pocpod0 running on the Hetzner VPS at `~/pocpod0` with the OpenClaw WebUI reachable over the public internet (token-gated), so that Epic 4 continues unblocked by local networking bugs and Discord agents + WebUI pairing work reliably.
- Consequence of 4.0.1: local podman path abandoned as the primary dev target; VPS became the reference environment
- Established the deploy tooling (`make vps-push/build/deploy`) every later epic relies on

### Story 4.1: [must-ship] Marc — School Transfer Scenario (NL→FR)

**Prerequisite:** Story 4.0 complete (Discord bindings + seed-on-boot).

As **Marc** (school administrator, Liège),
I want to execute a complete school transfer — granting my school access to the student's pod, revoking the old school's access, and querying the student's full learning profile,
So that the student's data follows them seamlessly across the NL→FR community boundary with zero re-entry.

**Acceptance Criteria:**

**Given** a student (Ayoub) currently enrolled in a Flemish (NL) school with active ACLs
**When** the transfer protocol executes
**Then** Marc's new school receives an ACL grant on Ayoub's pod
**And** the old school's ACL access is revoked

**Given** the transfer is complete
**When** Marc's agent queries Ayoub's pod for the complete learning profile
**Then** the full history is returned — courses, assessments, extracurricular, competency trajectory (FR22)
**And** cross-community data (NL→FR) renders seamlessly via structured OSLO-mapped RDF (FR23)

**Given** the transfer is complete
**When** the old school attempts to access Ayoub's pod (direct HTTP request)
**Then** the request is denied (HTTP 403)

**Given** the transfer is complete
**When** an uninvolved third party (no ACL grant) attempts to access Ayoub's pod
**Then** the request is denied (HTTP 403)

**Given** the transfer scenario
**When** the ACL state is audited (FR6, from Epic 1)
**Then** the audit shows: Marc's school has read access, old school has no access, consent history is traceable

**Discord interaction note:** Marc executes the transfer by sending a natural language instruction to his agent via the #marc-admin Discord channel (e.g., "Transfer Ayoub to Liège school — grant access, revoke old school"). The agent calls the `acl-manage` skill. The ACL dashboard updates in real time. Funders observe the full flow without a terminal.

---

### Story 4.2: [must-ship] Cross-Community Data Handling

**Prerequisite:** Story 4.1 complete (transfer executed, ACLs updated).

As **Marc** (school administrator, Liège),
I want to verify that Ayoub's complete learning history — gathered across Flemish (NL) and French-speaking (FR) institutions — is fully accessible and coherent after the transfer,
So that the receiving school never needs to ask the student to re-submit records that already exist.

**Acceptance Criteria:**

**Given** the transfer is complete and Marc's school has ACL read access
**When** Marc's agent queries Ayoub's pod for the full learning profile
**Then** records from NL institutions and FR institutions are returned in a single coherent response (FR22)
**And** no records are missing or duplicated due to community boundary

**Given** Ayoub's records use both NL-language and FR-language content fields
**When** Marc's agent retrieves the profile
**Then** OSLO-mapped RDF renders cross-community data seamlessly — language field is preserved, not stripped (FR23)
**And** provenance shows source institution (school-nl, school-fr) per triple (FR20)

**Given** the NL school's ACL has been revoked
**When** Marc's agent queries data that originated from the NL school
**Then** the data is still accessible — revocation removes institutional *write* access, not the *data already transferred to Ayoub's pod*
**And** this distinction is explicitly visible in the ACL audit trail

**Given** a SPARQL query against Oxigraph for Ayoub's post-transfer profile
**When** executed with Marc's WebID authorization
**Then** triples from both NL and FR named graphs are returned
**And** query completes in < 500ms (NFR1)

---

### Story 4.3: [must-ship] Nicolas — Onboarding Proof

**Prerequisite:** Story 4.0 complete (Discord bindings + seed-on-boot).

As **Nicolas** (project lead, first real user),
I want to onboard as a new user — provisioning my own pod and pairing my own agent-assistant — and execute the full consent lifecycle via Discord,
So that I can demonstrate "you could do this too" to funders, and prove the onboarding flow works for a real person beyond the 6 seeded personas.

**Acceptance Criteria:**

**Given** a new pod slug (`nicolas`) provisioned in CSS
**When** the provisioning runs
**Then** Nicolas's pod is accessible at the expected CSS URL
**And** an agent-assistant (`nicolas-assistant`) is seeded in OpenClaw with a workspace and Discord channel binding

**Given** Nicolas's pod and agent are live
**When** Nicolas sends a message to his agent via Discord DM
**Then** the agent responds in character — knows who Nicolas is (from IDENTITY.md / USER.md) and can answer questions about his pod

**Given** Nicolas wants to grant a researcher access to his pod
**When** Nicolas instructs his agent via Discord ("grant read access to isabelle")
**Then** the `acl-manage` skill executes the grant
**And** the ACL dashboard shows Nicolas's pod with Isabelle's WebID listed as a reader
**And** a consent event is emitted to `data/consent-events.jsonl`

**Given** Nicolas wants to revoke that access
**When** Nicolas instructs his agent via Discord ("revoke isabelle's access")
**Then** the `acl-manage` skill executes the revocation
**And** the ACL dashboard updates within 2 seconds
**And** Isabelle's subsequent query attempt returns HTTP 403

**Funder narrative:** Nicolas walks a funder through this flow live on Discord. The funder sees: pod creation → agent pairing → grant → watch dashboard → revoke → watch dashboard. "This is what you'd do for your own institution's data."

---

### Story 4.4: [must-ship] Troll — Heartbeat Security Monitor on Discord

**Prerequisite:** Story 4.0 complete (HEARTBEAT.md seeded, #security_logs channel bound).

As a **funder** (demo audience),
I want the troll agent to run periodic security probes automatically and post readable reports to #security_logs,
So that I can see the boundary being actively tested at all times — not just during a scripted demo moment.

**Acceptance Criteria:**

**Given** the troll's HEARTBEAT.md defines a probe schedule
**When** the heartbeat fires
**Then** the troll runs at least 3 attack categories (ACL enforcement, SPARQL injection, cross-inference sample)
**And** posts a short structured report to #security_logs within 60 seconds of the heartbeat firing

**Given** a heartbeat report is posted to #security_logs
**When** a funder reads it
**Then** each category shows: status (✅ holding / ⚠️ partial / ❌ breach), count (X/Y tests passed), and one-line finding
**And** the report is readable by a non-technical person (FR34)

**Given** a funder wants to ask the troll about a finding
**When** the funder sends a Discord DM to the troll agent
**Then** the troll responds with context — what the test does, what "partial" means for that category, what risk it represents

**Given** a new run completes with a different result than the previous run
**When** the troll posts the next heartbeat report
**Then** the change is flagged ("⬆️ ACL: was 22/23, now 23/23 — SPARQL injection fix applied")

**Implementation note:** HEARTBEAT.md defines: interval (e.g., every 30 min), which attack modules to run, output format for #security_logs. The troll does NOT run the full suite on every heartbeat — a representative subset (fast, reproducible categories only; cross-inference excluded from heartbeat due to non-determinism).

---

### Story 4.4.1: [infra] Nginx/OpenClaw Retirement & CSS Hardening _(inserted during execution — recorded here 2026-08-02)_
As project lead, I want VPS nginx routing consolidated onto the shared `nginx-gateway` container, OpenClaw's local dependencies removed from the pocpod0 stack, and CSS reachable at a real public subdomain, so that the VPS stops carrying dead/duplicate infrastructure, teammates can register real Solid pods on `pod.nicolasdb.eu` for multi-user ACL testing, and the pod stack isn't exposed to identity-spoofing over the public internet.
- **Load-bearing for Epics 7 and 8:** `pod.nicolasdb.eu` as a real public subdomain is the precondition for the backoffice (7.1) and every live connector story (8.2–8.7)
- Removed the debug-auth-header exposure that made WebID spoofing possible over the public internet

### Story 4.5: [must-ship] Consent Revocation Scenario — Ayoub Revokes, Isabelle Reacts

**Prerequisite:** Stories 4.1 (Marc transfer complete), 4.3 (Nicolas onboarded), 4.4 (troll heartbeat live).

As **Ayoub** (data sovereign, Brussels),
I want to revoke Isabelle's regional-access consent via a Discord DM to my agent-assistant,
So that my withdrawal of consent is immediately reflected in the aggregate data Isabelle sees — proving that my sovereignty decision has real, instant consequences.

**Acceptance Criteria:**

**Given** Isabelle has active `regional-access` consent on Ayoub's pod
**When** Ayoub sends his agent a Discord DM: "revoke Isabelle's access to my data"
**Then** the `acl-manage` skill removes the regional-access grant from Ayoub's pod
**And** a `consent.revoke` event is emitted to `data/consent-events.jsonl`
**And** the ACL dashboard shows Ayoub's pod with Isabelle's access removed within 2 seconds

**Given** Ayoub's consent has been revoked
**When** Isabelle's agent queries the school aggregate (total consented students)
**Then** the aggregate count drops by 1 (Ayoub excluded from aggregate)
**And** the SPARQL filter excludes Ayoub automatically — no admin action required

**Given** the aggregate drops
**When** Isabelle's HEARTBEAT fires (or Isabelle is interacted with via Discord)
**Then** Isabelle's agent posts to #general: "I noticed the consented student count dropped — is everything OK at the school? Should I be aware of anything?"
**And** the message is in character — institutional concern, not a technical error

**Given** the full scenario has run
**When** a funder observes the #general channel and ACL dashboard together
**Then** they see: one student's DM → real-time dashboard change → Isabelle's institutional response
**And** this is "The Inversion" made visible: a 16-year-old's data sovereignty decision causes an institutional reaction

**Demo script companion:** This story ships with `_bmad-output/implementation-artifacts/demo-script-epic4.md` — the narrative checklist for open-door Discord demos. The demo script covers: setup, all 6 agents introduction, Marc transfer walkthrough, Ayoub revocation scenario, troll heartbeat reading, funder free interaction.

## Epic 5: Data Sovereignty Lifecycle

Governance contracts execute (age-based sovereignty transition), deletion cascades propagate across all three data layers, and the system honestly reports its deletion timing — proving the architecture handles the full data lifecycle. [must-ship] — Ayoub's journey.

**Epic 5 is the wiring epic.** This is where agent-driven ACL mutation, consent lifecycle, and the observable impact of sovereignty decisions come together. The demo narrative depends on agents being able to act on data — not just read it. Key capability gap identified (2026-03-25 party mode review): no agent currently has a skill to write ACL changes. Story 1.4 built grant/revoke as pipeline scripts; Epic 5 must expose this as an agent-callable skill so the demo narrative works end-to-end (user talks to agent → agent mutates ACL → dashboard shows consent state change → downstream queries reflect new boundaries).

**Critical path for Epic 6:** The mission control TUI (Story 6.1) needs to show consent state changes live. This means Epic 5 must emit JSONL events for every ACL mutation, and the acl-manage skill must be agent-invocable. Without this, the funder demo has no interactive consent lifecycle.

**OpenClaw chat completions API prerequisite:** The `/v1/chat/completions` endpoint must be enabled in `openclaw.json` (Story 3.8 enables this for troll probes; Epic 5 benefits from it for agent interaction scripting).

### Story 5.1: [must-ship] Ayoub — Age-Based Sovereignty Transition

As **Ayoub** (16-year-old student, Brussels),
I want the governance contract to transfer full control of my pod from shared parent/guardian governance to me alone when I reach the age threshold,
So that my data sovereignty is structurally guaranteed by the architecture, not by policy promises.

**Acceptance Criteria:**

**Given** Ayoub's pod has a programmable governance contract with shared parent/guardian control
**When** the age-based threshold condition is met (per Belgian/EU residence rules)
**Then** the governance contract executes
**And** Ayoub becomes the sole governor of his pod
**And** parent/guardian co-governance permissions are removed

**Given** the sovereignty transition has executed
**When** Ayoub inspects his pod's ACL/consent state
**Then** he sees himself as sole owner with full control
**And** the governance transition event is logged with timestamp and details

**Given** the sovereignty transition has executed
**When** a former guardian attempts to modify Ayoub's pod governance
**Then** the request is denied — Ayoub is now sole governor

**AC-NEW: Agent-callable ACL management skill** _(added 2026-03-25)_

**Given** an agent with appropriate pod ownership (e.g., Ayoub for his own pod)
**When** the agent invokes the `acl-manage` skill with a grant or revoke action
**Then** the CSS ACL on the target pod is updated accordingly
**And** a structured JSONL event is emitted: `{"event_type": "acl.grant|acl.revoke", "timestamp": ..., "pod": "...", "identity": "...", "action": "grant|revoke"}`
**And** the mission control TUI can display the change live

**Given** an agent without pod ownership (e.g., Claire trying to modify Ayoub's ACL)
**When** the agent invokes the `acl-manage` skill
**Then** the skill refuses with an authorization error — only pod owners can mutate their own ACLs

**Implementation note:** The `acl-manage` skill wraps the grant/revoke logic from Story 1.4 (`scripts/seed-pods.sh` / pipeline ACL functions) as an OpenClaw skill with a `SKILL.md` file. It must enforce scope: each agent can only modify ACLs on pods they own. The skill emits JSONL events to `data/consent-events.jsonl` for dashboard consumption.

### Story 5.2: [must-ship] Deletion Cascade & Verification

As **Ayoub** (data sovereign),
I want to request deletion of a pod resource and have it cascade completely across all three data layers with verified completeness,
So that my right to erasure is architecturally enforced, not a manual process with gaps.

**Acceptance Criteria:**

**Given** a Pod resource with derived triples in Oxigraph and embeddings in Qdrant
**When** a soft-delete request is issued on the Pod resource
**Then** the resource is marked with `pocpod0:deletedAt` triple (step 1)
**And** all derived triples are removed from Oxigraph by dropping the named graph: `DROP GRAPH <pod-resource-uri>` (step 2) _(corrected 2026-03-25: uses named graph pattern per Story 2.6, NOT prov:wasDerivedFrom)_
**And** all Qdrant points with matching `pod_resource_uri` in payload are removed (step 3)
**And** the entire cascade completes in a single execution of the propagation routine (NFR3)

**Given** the deletion cascade has completed
**When** verification queries run against all three layers
**Then** the Pod resource is marked as deleted
**And** zero Oxigraph triples reference the deleted resource
**And** zero Qdrant points reference the deleted resource
**And** verification result is logged as pass or fail (step 4)

**Given** each step of the deletion cascade
**When** it executes
**Then** a structured JSON log entry is emitted with layer, resource URI, and completion status (NFR11, step 5)

### Story 5.3: [must-ship] Troll Deletion Timing Validation

As a **security reviewer** (funder audience),
I want the troll agent to test deletion cascade timing across all three data layers,
So that I have honest evidence of how quickly erasure propagates — including any gaps the architecture acknowledges.

**Acceptance Criteria:**

**Given** a deletion cascade has been triggered
**When** the troll agent queries all three data layers immediately after each cascade step
**Then** each layer's purge timing is measured and recorded
**And** each test is logged with category `deletion_timing`, access path `direct`, and result `pass`, `partial`, or `fail`

**Given** Qdrant embeddings take extra propagation time to purge
**When** the troll detects a timing gap (e.g., embeddings still queryable after triple deletion)
**Then** the result is recorded as `partial` with details: propagation delay duration, residual data exposure window, and risk assessment
**And** the finding is documented honestly — this is the trust-building moment, not a failure to hide

**Given** all deletion timing tests complete
**When** the troll test suite for Epic 5 finishes
**Then** results are deterministic and reproducible across runs (NFR12)
**And** a summary is produced with pass/partial/fail per layer and timing metrics

### Story 5.4: [backlog] Access Receipt Written to Pod

_Discovered during Story 3.6 deep dive. Implements BP-1 (Bidirectional Accountability) from architecture.md._

As **Ayoub** (data sovereign),
I want every query that accesses my pod's data to generate a readable receipt stored in my pod,
So that I can audit who accessed what, when, and why — without asking anyone.

**Acceptance Criteria:**

**Given** any agent query executes against data derived from Ayoub's pod
**When** the query completes (success or denial)
**Then** a receipt is written to `/ayoub/access-log/[timestamp].ttl` containing: who queried (agent WebID), when, which consent grant authorized it, result shape (not raw data), which named graphs contributed

**Given** the receipt is written
**When** Ayoub (or the troll on Ayoub's behalf) queries the access log
**Then** the receipt is human-legible and machine-readable (Turtle format)
**And** the troll can answer "why does Isabelle have my data?" by dereferencing the consent grant URI in the receipt

### Story 5.5: [backlog] Consent Grant as RDF Resource

_Discovered during Story 3.6 deep dive. Implements BP-3 (Consent Grant as RDF Resource) from architecture.md._

As **Ayoub** (data sovereign),
I want the consent I give to institutional actors to be a dereferenceable, inspectable document — not a boolean flag,
So that I can understand, at any time, exactly what I agreed to and why.

**Acceptance Criteria:**

**Given** an institutional actor (e.g. Isabelle) requests aggregate access
**When** consent is granted
**Then** a consent grant resource is created at a dereferenceable URI carrying: requestedBy, purpose, scope (what they will see), excluded (what they will NOT see), consequenceOfRefusal, grantedAt, revokedAt (tombstone), expiresAt

**Given** the consent grant resource exists
**When** Ayoub or the troll queries "why does Isabelle have access?"
**Then** the troll dereferences the consent grant URI and returns the purpose and scope in plain language — no human intermediary required

**Given** Ayoub revokes consent
**When** the revocation executes
**Then** the `revokedAt` field is populated (tombstone), the ACL grant is removed, and future aggregate queries automatically exclude Ayoub's data
**And** historical aggregates computed before revocation remain immutable

### Story 5.6: [backlog] Ephemeral Time-Scoped Consent — Double-Aveugle Pattern

_Discovered during Anagnorisis narrative (Epic 3 retrospective, 2026-03-25). Implements BP-5 from architecture.md._

As **Ayoub** (data sovereign),
I want to grant time-scoped access to sensitive context data using an opaque token — so the receiving service never knows whose data it is and access auto-revokes when the token expires.

**The scenario:** Ayoub attends a summer camp. The food service needs to know his dietary restrictions. His parents grant a camp-duration token — the food service sees "gluten-free for token-7f3a" not "gluten-free for Ayoub". The school community pod holds the token→learner mapping, invisible to the food service. After camp, the token expires and access is revoked.

**Acceptance Criteria:**

**Given** a consent grant resource (Story 5.5) for a time-scoped context (e.g., summer camp food service)
**When** the grant is created
**Then** it includes `poc:expiresAt` (camp end date) and an opaque `poc:token` alias (not Ayoub's WebID)
**And** the food service receives only the token — it cannot dereference the token to Ayoub's identity

**Given** the token expiry date has passed
**When** any service attempts to use the token
**Then** the CSS ACL check fails (token-scoped resource is no longer accessible)
**And** a `consent.expired` JSONL event is emitted: `{"event_type": "consent.expired", "timestamp": ..., "token_id": "...", "pod": "..."}`
**And** the receipt in Ayoub's access log (`/ayoub/access-log/camp-food-[date].ttl`) records the full access window (granted→expired)

**Given** Isabelle queries the camp community pod for program aggregate
**When** the query runs
**Then** it hits the camp community pod (not Ayoub's pod) and returns counts via `GROUP BY`
**And** no individual identity is exposed — double-aveugle (service is blind to identity, policy actor is blind to individual)

**Implementation note:** Builds on Story 5.5 consent grant resource. Adds `poc:token` alias field and expiry check in the ACL enforcement path. The opaque token is a SHA-256 hash of `(pod_uri + grant_timestamp)` — deterministic but not reversible without the lookup index (held in school community pod, authorized access only).

## Epic 6: Adversarial Trust Report & ACL Dashboard

_(amended 2026-04-02: TUI approach abandoned after two pivots. FastAPI + vanilla HTML dashboard queries CSS ACLs directly, proves enforcement live. Troll comprehensive run shipped as Story 6.1. Dashboard shipped as Story 6.2. Story 6.3 adds acl-manage skill integration, troll tab, and UI polish.)_

The comprehensive troll run generates a funder-readable categorized report, the ACL dashboard surfaces live pod ACL state and enforcement probes, and intervention points let funders observe consent changes in real-time.

**Demo model:**
- **Browser: ACL Dashboard** (localhost:8000) — live pod grid, probe enforcement, grant/revoke, troll attack tab.
- **Browser: OpenClaw** (localhost:18789) — interactive. User picks an agent, talks to them in NL. Agent actions (queries, ACL changes) reflect on dashboard.

### Story 6.0: Pipeline Provision as Stage 0
_Done. Adds provision_pods.py + camp-dietary-aggregate.ttl seed as Stage 0 in run_pipeline.py._

### Story 6.1: Troll Comprehensive Run & Report
_Done. `run_comprehensive.py` orchestrates all 5 attack categories, writes `data/troll-run.jsonl`, generates funder-readable categorized report._

**FRs covered:** FR33, FR34

### Story 6.2: ACL Enforcement Dashboard (PIVOT)

_(Original 6.1/6.2 TUI stories superseded. This story replaces them with a FastAPI + HTML dashboard.)_

As a **project lead and demo facilitator**,
I want a web dashboard that queries CSS pod ACL state live and lets me probe enforcement,
So that I can demonstrate to a funder that "private by default" is real and enforced.

_Done. See `_bmad-output/implementation-artifacts/6-2-acl-dashboard.md` for full spec and dev record._

**FRs covered:** FR39 (dashboard), FR6 (ACL state visibility)

### Story 6.3: Funder Intervention Points

As a **funder** (demo participant),
I want the dashboard to use OpenClaw's acl-manage skill for consent changes and display troll attack results live,
So that I see the full consent lifecycle and adversarial validation through a single interface — not direct database calls.

_(amended 2026-04-02: scoped to acl-manage skill wiring, troll dashboard tab, and UI polish. Narrative context and stakeholder workflows deferred to Epic 4.)_

**Acceptance Criteria:**

**Given** the ACL dashboard is running and OpenClaw is available
**When** operator clicks Grant or Revoke on a pod card
**Then** the action is routed through the OpenClaw acl-manage skill (Story 5.1), not direct PodProvisioner calls
**And** the skill emits a JSONL event to `data/consent-events.jsonl`
**And** the pod card refreshes to reflect the new ACL state

**Given** the dashboard has a Troll tab/page
**When** operator navigates to it
**Then** it displays troll attack categories with a launch button per category
**And** shows progress as attacks run (reading `data/troll-run.jsonl`)
**And** displays the categorized report with pass/partial/fail per attack surface

**Given** a troll attack completes
**When** results are written to `data/troll-run.jsonl`
**Then** the Troll tab updates live with the new result

**Given** the dashboard after UI polish
**When** a non-technical reviewer views it
**Then** the interface is clean, visually coherent, and understandable without technical explanation

**Deferred to Epic 4:**
- Narrative context on pod cards (who is Ayoub, why does consent matter)
- Pod content exploration (what resources are inside, who accesses what)
- OpenClaw agent interaction for stakeholder workflows (Claire queries, Fatima views, etc.)
- Fine-tune scenarios per stakeholder goals

**FRs covered:** FR38 (intervention points)
