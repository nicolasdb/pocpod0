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

### Epic 3: Cross-Context Learning Insights
Role agents (Claire, Fatima, Isabelle) query across institutional silos, compare graph-only vs. hybrid results, and surface provenance — delivering the "aha moment" that makes the PoC compelling.
**FRs covered:** FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR30, FR35, FR36
**Story tags:** Stories tagged as [foundation] (agent infra, shared skills) or [journey] (Claire, Fatima, Isabelle scenarios)
**Priority tags:** Claire stories tagged [must-ship], Fatima and Isabelle stories tagged [target] per PRD fallback strategy (plan for 5, fallback to 3)
**Dashboard backlog:** Query monitor (SPARQL + hybrid), agent activity log, graph-vs-hybrid comparison display

### Epic 4: Student Transfer & Data Portability
The school transfer scenario (NL→FR) executes end-to-end — ACL grants, revocations, cross-community data handling — proving data moves with the learner, not the institution.
**FRs covered:** FR21, FR22, FR23
**Priority:** [must-ship] — Marc's journey is one of the 3 must-ship journeys
**Dashboard backlog:** Transfer workflow visualization, ACL change audit trail

### Epic 5: Data Sovereignty Lifecycle
Governance contracts execute (age-based sovereignty transition), deletion cascades propagate across all three data layers, and the system honestly reports its deletion timing — proving the architecture handles the full data lifecycle.
**FRs covered:** FR24, FR25, FR26, FR27, FR32
**Priority:** [must-ship] — Ayoub's journey is one of the 3 must-ship journeys
**Dashboard backlog:** Governance event log, deletion cascade status, timing metrics

### Epic 6: Adversarial Trust Report & Mission Control
The comprehensive troll run generates a funder-readable categorized report, the mission control dashboard surfaces all evidence from Epics 1-5, and intervention points let funders shift from audience to participant.
**FRs covered:** FR33, FR34, FR38, FR39
**Note:** Dashboard design happens here, informed by the component backlog built through Epics 1-5. UX Design spike precedes dashboard implementation.

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

### Story 2.2: Synthetic xAPI Dataset Generation

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

### Story 2.3: xAPI→OSLO RDF Ingestion Pipeline

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

### Story 2.4: Graph Layer Loading with Provenance

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

### Story 2.5: Vector Embeddings with Bidirectional Traceability

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

### Story 2.6: Troll SPARQL Injection & Vector Privacy Validation

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

## Epic 3: Cross-Context Learning Insights

Role agents (Claire, Fatima, Isabelle) query across institutional silos, compare graph-only vs. hybrid results, and surface provenance — delivering the "aha moment" that makes the PoC compelling. Stories tagged [foundation] vs [journey], priority [must-ship] vs [target].

### Story 3.1: [foundation] OpenClaw Agent Runtime & Shared SPARQL Skill

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

### Story 3.3: [journey] [must-ship] Claire — Cross-Context Insight Discovery

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

### Story 3.4: [journey] [target] Fatima — Unified Parental View

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

### Story 3.5: [journey] [target] Isabelle — Evidence-Based Policy

As **Isabelle** (regional education policy advisor, Brussels-Capital),
I want to query aggregate anonymized program impact across communities,
So that I can justify funding decisions with evidence-based data instead of self-reported narratives.

**Acceptance Criteria:**

**Given** Isabelle's agent is configured with regional aggregate-read ACL access
**When** Isabelle queries "What is the measurable impact of funded STEM programs on participating students?"
**Then** the system returns aggregate results across both NL and FR communities (FR19)
**And** no individual student data is exposed — results are anonymized at the aggregate level

**Given** aggregate query results
**When** Isabelle inspects provenance
**Then** the system shows: "this aggregate is derived from N triples across M student pods, all with active regional-access consent grants"
**And** anonymization guarantees are displayed alongside results

**Given** Isabelle attempts a query that would return individual student data
**When** the query executes
**Then** the system enforces aggregate-only access — no individual records returned

### Story 3.6: [foundation] Troll Cross-Inference Validation

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

### Story 4.1: [must-ship] Marc — School Transfer Scenario (NL→FR)

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

## Epic 5: Data Sovereignty Lifecycle

Governance contracts execute (age-based sovereignty transition), deletion cascades propagate across all three data layers, and the system honestly reports its deletion timing — proving the architecture handles the full data lifecycle. [must-ship] — Ayoub's journey.

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

### Story 5.2: [must-ship] Deletion Cascade & Verification

As **Ayoub** (data sovereign),
I want to request deletion of a pod resource and have it cascade completely across all three data layers with verified completeness,
So that my right to erasure is architecturally enforced, not a manual process with gaps.

**Acceptance Criteria:**

**Given** a Pod resource with derived triples in Oxigraph and embeddings in Qdrant
**When** a soft-delete request is issued on the Pod resource
**Then** the resource is marked with `pocpod0:deletedAt` triple (step 1)
**And** all derived triples are removed from Oxigraph matching `prov:wasDerivedFrom <pod-resource-uri>` (step 2)
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

## Epic 6: Adversarial Trust Report & Mission Control

The comprehensive troll run generates a funder-readable categorized report, the mission control dashboard surfaces all evidence from Epics 1-5, and intervention points let funders shift from audience to participant. Dashboard UX design spike precedes implementation, informed by component backlog from Epics 1-5.

### Story 6.1: Mission Control Dashboard

As a **funder** (demo audience),
I want a mission control dashboard showing live attack results, query monitoring, and Pod status,
So that I can follow the PoC demo narrative visually without needing technical explanation.

**Acceptance Criteria:**

**Given** the dashboard component backlog collected from Epics 1-5 (pod status, ACL state, pipeline ingestion, provenance navigation, query monitor, agent activity, transfer workflow, governance events, deletion cascade, troll test results)
**When** a lightweight UX design spike is completed
**Then** the dashboard layout and component list are defined based on actual evidence from prior phases

**Given** the UX design is defined
**When** the dashboard (`dashboard/src/pocpod0_dashboard/`) is implemented with FastAPI + HTMX
**Then** it reads from structured JSON observability logs (docker logs or shared log volume)
**And** it displays live-updating views for: query monitoring, pod ACL status, troll activity results, deletion cascade status

**Given** the dashboard is running
**When** any service emits a structured JSON log entry
**Then** the dashboard reflects the event without manual refresh (HTMX live updates)

**Given** a non-technical reviewer
**When** they view the dashboard during a demo
**Then** the display is understandable without technical explanation

### Story 6.2: Funder Intervention Points

As a **funder** (demo participant),
I want interactive intervention points where I can select queries, trigger transfers, and choose attack vectors,
So that I shift from passive audience to active participant in the demo — building conviction through direct interaction.

**Acceptance Criteria:**

**Given** the mission control dashboard is running
**When** a funder views the intervention panel
**Then** they see selectable options: role-based query menu, transfer scenario trigger, troll attack vector menu

**Given** a funder selects a role-based query (e.g., Claire's cross-context query)
**When** the query executes
**Then** both graph-only and hybrid results display on the dashboard in real-time

**Given** a funder triggers the transfer scenario
**When** the transfer protocol executes
**Then** ACL grant/revocation is visible on the dashboard in real-time

**Given** a funder selects a troll attack vector
**When** the attack executes
**Then** the result (pass/partial/fail) displays on the dashboard in real-time with details

**Given** any intervention
**When** the funder does nothing (observes passively)
**Then** the demo narrative continues — the system runs end-to-end whether funders intervene or not

### Story 6.3: Comprehensive Troll Run & Categorized Report

As a **funder** (investment decision-maker),
I want a comprehensive adversarial test run across all attack categories with results visible live on the dashboard and a categorized report generated for review,
So that I see exactly where the architecture holds, where it needs investment, and can make an informed funding decision.

**Acceptance Criteria:**

**Given** the mission control dashboard is running and all prior epic capabilities are deployed
**When** the comprehensive troll run executes (`scripts/run-troll.sh`)
**Then** all 5 attack categories are tested: ACL enforcement, SPARQL injection, cross-inference, vector privacy, deletion timing
**And** results display live on the mission control dashboard as each test completes

**Given** all attack categories have been tested
**When** the report generator (`agents/troll-adversary/report/generator.py`) executes
**Then** a categorized report is produced with pass/partial/fail ratings per attack surface
**And** each entry includes: attack category, access path, test name, result, human-readable explanation, and evidence

**Given** the generated troll report
**When** a non-technical reviewer reads it
**Then** the report is understandable without technical background (FR34)
**And** partial/fail results are presented as investment opportunities, not hidden failures
**And** the report follows the template in `agents/troll-adversary/report/template.md`

**Given** the comprehensive run
**When** compared to individual troll tests from Epics 1, 2, 3, and 5
**Then** results are consistent — the comprehensive run exercises the same tests with the addition of the unified report and live dashboard display
