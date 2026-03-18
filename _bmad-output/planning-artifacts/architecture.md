---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-03-17'
inputDocuments:
  - "product-brief-pocpod0-2026-03-16.md"
  - "prd.md"
project_name: pocpod0
user_name: Nicolas
date: '2026-03-17'
---

# Architecture Decision Document — pocpod0

_This document captures all architectural decisions for the pocpod0 PoC — a decentralized learning data architecture where learners own their data via Solid Pods, backed by a semantic graph engine and vector store._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
40 functional requirements organized into 9 categories:

| Category | FR Count | Architectural Implication |
|----------|----------|--------------------------|
| Data Sovereignty & Pod Management | FR1–FR7 | Solid/CSS pod provisioning, ACL engine, content negotiation |
| Data Ingestion & Transformation | FR8–FR13 | xAPI→OSLO RDF pipeline, Oxigraph storage, Qdrant embeddings, bidirectional traceability |
| Cross-Context Querying | FR14–FR20 | SPARQL skill, hybrid queries (SPARQL+vector), role-based ACL enforcement at query time |
| Transfer & Portability | FR21–FR23 | ACL grant/revocation workflows, cross-community (NL→FR) data handling |
| Governance & Data Lifecycle | FR24–FR27 | Programmable governance contracts, 3-layer deletion cascade |
| Adversarial Testing | FR28–FR34 | Troll agent with dual access model, categorized attack surfaces, report generation |
| Agent Infrastructure | FR35–FR37 | OpenClaw multi-agent orchestration, shared SPARQL sub-agent, 5 role personas |
| Demo & Presentation | FR38–FR39 | Funder intervention points, mission control dashboard |
| Infrastructure & Operations | FR40 | docker-compose health-check orchestration |

**Non-Functional Requirements:**
- Performance: SPARQL < 500ms, hybrid < 2s, startup < 60s, cascade in single routine
- Security: ACL pass required, SPARQL injection pass required, probabilistic surfaces assessed honestly
- Observability: query logging, troll activity logging, deletion cascade status
- Reproducibility: deterministic infra tests, NL cross-inference flagged as non-deterministic
- Deployment: Fedora (SELinux) + Ubuntu (VPS), single `docker-compose up`, 1-hour setup target

**Scale & Complexity:**
- Primary domain: Data infrastructure PoC (Docker-orchestrated services + AI agents)
- Complexity level: High — semantic web standards, privacy engineering, adversarial validation, multi-service orchestration
- Estimated architectural components: 7 services + 6 agent personas + pipeline tooling + dashboard

### Technical Constraints & Dependencies

- **Committed standards:** Solid/CSS, OSLO vocabularies (data.vlaanderen.be), Oxigraph, Qdrant
- **LLM dependency:** OpenRouter API (minimax/minimax-m2.5 for agents, qwen/qwen3-embedding-8b for embeddings)
- **Runtime:** Docker-compose, default Docker network, bind mounts with SELinux-aware volume flags
- **Solo developer + AI pair:** Architecture must be simple enough for one person to operate all components
- **No `latest` tags:** All images pinned to specific versions

### Cross-Cutting Concerns Identified

1. **ACL enforcement** — touches Pod layer, SPARQL skill, agent layer, troll validation
2. **Provenance traceability** — links Pod resources ↔ Oxigraph triples ↔ Qdrant embeddings bidirectionally
3. **Deletion cascade** — propagates across all three data layers
4. **OSLO vocabulary schema** — contract between ingestion pipeline and agent query layer
5. **Observability logging** — feeds mission control dashboard from all services
6. **SELinux/host compatibility** — `.env`-driven volume mount flags

---

## Starter Template Evaluation

### Primary Technology Domain

This is **not** a web application with a frontend framework. pocpod0 is a **Docker-orchestrated data infrastructure PoC** with:
- Pre-existing containerized services (CSS, Oxigraph, Qdrant, Nginx)
- Python glue code for data pipeline and orchestration scripts
- OpenClaw as the agent runtime (Node.js-based, self-contained)
- A lightweight dashboard (dev-mode, not production SPA)

**No starter template applies.** The project is composed from individual service containers + custom Python tooling + OpenClaw agent configuration. The "starter" is `docker-compose.yml` itself.

### Selected Approach: Compose-First Infrastructure

**Rationale:** Each service is an independent container with its own configuration. The project skeleton is a docker-compose file with service-specific config directories, a Python package for pipeline/orchestration, and OpenClaw workspace for agents.

**Initialization Command:**

```bash
# No CLI starter — manual scaffold
mkdir -p pocpod0/{infra,pipeline,agents,dashboard,scripts,data/{synthetic,schemas},tests}
```

**Architectural Decisions Provided by This Approach:**
- **Language & Runtime:** Python 3.12+ for pipeline/orchestration, OpenClaw (Node.js) for agents
- **Build Tooling:** docker-compose for services, pip/uv for Python dependencies
- **Testing:** pytest for pipeline tests, OpenClaw sub-agent tests for agent behavior, troll agent as adversarial test suite
- **Code Organization:** By concern (infra, pipeline, agents, dashboard, tests) not by layer

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
1. Service versions and Docker image tags
2. Python for pipeline vs. alternative
3. Agent runtime: OpenClaw via OpenRouter
4. Data flow: xAPI → RDF → embeddings pipeline architecture
5. ACL enforcement strategy
6. Inter-service communication patterns

**Important Decisions (Shape Architecture):**
7. Dashboard technology
8. OSLO vocabulary mapping approach
9. Troll agent access patterns
10. Governance contract implementation
11. Logging and observability approach

**Deferred Decisions (Post-MVP / Pilot Phase):**
- Production-grade deletion scheduling (nightly consolidation)
- Real user authentication (Solid-OIDC provider)
- Smartschool connector architecture
- Horizontal scaling strategy

### Data Architecture

**Decision DA-1: Three-Layer Data Model**
- **Pod Layer (CSS):** Source of truth. Raw xAPI-as-RDF stored as Turtle resources in per-learner pods. ACLs enforced here.
- **Graph Layer (Oxigraph):** Queryable index. OSLO-mapped RDF triples with provenance links back to Pod resource URIs. Not a source of truth — rebuildable from pods.
- **Vector Layer (Qdrant):** Semantic index. Embeddings of semantically significant content, with payload metadata linking back to Oxigraph triple URIs and Pod resource URIs.
- **Rationale:** Separation allows independent scaling, clear deletion cascade order (Pod → Graph → Vector), and honest about what each layer provides.

**Decision DA-2: Provenance & Traceability Schema**
- Every Oxigraph triple includes `prov:wasDerivedFrom <pod-resource-uri>` provenance
- Every Qdrant point payload includes `{ "triple_uris": [...], "pod_resource_uri": "..." }`
- Bidirectional: given any embedding, navigate to triples → pod resource. Given any pod resource, find all derived triples and embeddings.
- **Rationale:** FR12 requires bidirectional traceability. This is the architectural primitive that makes deletion cascade and provenance display possible.

**Decision DA-3: OSLO Vocabulary Schema Contract**
- Schema defined as Turtle files in `data/schemas/`
- Maps xAPI concepts (Actor, Verb, Object, Result, Context) to OSLO education classes (data.vlaanderen.be)
- Schema contract is the Phase 2→3 bridge: agents query OSLO classes, not xAPI fields
- **Rationale:** FR13 requires documented vocabulary mapping. Turtle files are versionable, validatable, and directly loadable into Oxigraph.

### Authentication & Security

**Decision SEC-1: No User Authentication in PoC**
- PoC uses synthetic data and simulated agents — no real users
- Agent identity is configured, not authenticated: each OpenClaw agent has a fixed identity and ACL token
- CSS ACLs enforced via WebACL resources on pods
- **Rationale:** Real Solid-OIDC is a pilot-phase concern. PoC validates ACL enforcement, not authentication flow.

**Decision SEC-2: ACL Enforcement Strategy**
- **Pod level:** CSS native WebACL — the ground truth for who can access what
- **Query level:** Shared SPARQL skill validates agent role against pod ACLs before executing queries
- **Troll validation:** Tests both levels independently (direct infra access tests CSS ACLs; skill-mediated tests query-level enforcement)
- **Rationale:** Defense in depth. The troll's dual access model (FR37) requires both levels to be testable independently.

**Decision SEC-3: SPARQL Injection Defense**
- Shared SPARQL skill uses parameterized query templates, not string concatenation
- Query templates stored as `.rq` files with named parameters
- Troll agent tests injection through the skill interface (FR29)
- **Rationale:** FR29 requires injection resistance. Parameterized templates are the simplest defense that's also testable.

### API & Communication Patterns

**Decision API-1: No REST API Layer**
- Services communicate via their native protocols:
  - CSS: HTTP/LDP (Linked Data Platform)
  - Oxigraph: SPARQL endpoint (HTTP POST)
  - Qdrant: REST API (HTTP) or gRPC
- Agents access services directly via Docker network hostnames
- **Rationale:** Adding a REST API gateway is unnecessary complexity for a PoC. Each service already has a well-defined API.

**Decision API-2: Agent-to-Data Communication — Two Shared Skills**
- **Shared SPARQL skill:** ACL validation → parameterized SPARQL query → Oxigraph execution → results with provenance
- **Shared Qdrant skill:** Semantic similarity search → vector results with triple/pod URI metadata
- Agents compose queries from either or both skills (hybrid = SPARQL + Qdrant results merged)
- Troll agent has dual access: through skills (tests boundaries) AND direct to services (tests infrastructure)
- **Rationale:** Two separate skills keep concerns clean — graph queries and vector queries have different interfaces and failure modes. Both shared across all agents. Agents decide when to use one or both.

**Decision API-3: Qdrant Access Pattern**
- Pipeline writes to Qdrant during ingestion (batch upsert)
- Shared Qdrant skill reads from Qdrant for semantic search
- Troll agent reads directly from Qdrant for vector privacy tests (bypasses skill)
- Embedding generation: call OpenRouter API (qwen/qwen3-embedding-8b) from pipeline Python code
- REST vs gRPC: **fog-of-war** — both protocols available (ports 6333/6334), compare during Phase 2 implementation and pick one
- **Rationale:** Clear read/write separation. Only the pipeline writes; skills and troll only read. Protocol choice deferred to hands-on comparison.

### Infrastructure & Deployment

**Decision INFRA-1: Pinned Service Versions**

| Service | Image | Version | Port |
|---------|-------|---------|------|
| CSS (Community Solid Server) | `communitysolidserver/community-solid-server` | `7` | 3000 |
| Oxigraph | `oxigraph/oxigraph` | `0.5.6` | 7878 |
| Qdrant | `qdrant/qdrant` | `v1.17.0` | 6333 (REST), 6334 (gRPC) |
| Nginx | `nginx` | `1.28.2-alpine` | 80/443 |

- **Rationale:** PRD requires no `latest` tags. These are the latest stable versions as of 2026-03-17.

**Decision INFRA-2: Docker Compose Orchestration**
- Single `docker-compose.yml` at project root
- Default Docker network (services communicate via container names)
- Bind mounts for persistent data with `.env`-driven volume flags (SELinux `:Z` on Fedora, none on Ubuntu)
- Health checks on all services with `depends_on: condition: service_healthy`
- **Rationale:** PRD FR40 and NFRs require reproducible startup with dependency ordering.

**Decision INFRA-3: Environment Configuration**
- Single `.env` file at project root
- `.env.example` committed to repo with all variables documented
- Variables: `OPENROUTER_API_KEY`, `VOLUME_FLAGS` (`:Z` or empty), `CSS_BASE_URL`, ports
- **Rationale:** Minimal config surface. One secret (OpenRouter key), one host-specific flag (SELinux).

**Decision INFRA-4: Nginx Content Negotiation — SPIKE PASSED (Day 1)**
- Nginx reverse proxy fronts CSS for Linked Data content negotiation (Turtle, JSON-LD)
- **Spike verdict:** PASS — completed 2026-03-18 (Day 1 of 3-day timebox)
- **Key finding:** CSS 7 handles HTTP content negotiation natively via `AcceptPreferenceParser` (RFC 7231). Nginx requires only two changes: `proxy_set_header Accept $http_accept;` to pass the Accept header, and explicit `proxy_pass_header` directives for Solid-specific response headers.
- **Known limitation:** CSS returns `Link` headers with internal Docker network URLs (`localhost:3000`). Agents must treat these as discovery metadata only, not as dereferenceable URLs — use `CSS_BASE_URL` (port 8080) for all actual requests.
- **Integration test:** `tests/integration/test-nginx-content-negotiation.sh` — run after `docker-compose up` to verify.
- Fallback path (not taken): agents hit CSS directly on port 3000
- **Rationale:** PRD identifies this as the first critical risk. The timebox prevents infrastructure plumbing from consuming PoC time.

**Decision INFRA-5: Dashboard — Python + HTMX (Lightweight)**
- FastAPI backend serving HTMX-powered pages
- Reads from observability logs (structured JSON) for live display
- Dev-mode only — no authentication, no production concerns
- Displays: live attack results, query monitoring, pod ACL status
- **Rationale:** FR39 requires a mission control dashboard. FastAPI+HTMX is the simplest stack that delivers live updates without a frontend build step. Nicolas already uses Python for the pipeline.

### Decision Impact Analysis

**Implementation Sequence (Vertical Slices per Phase):**

1. **Phase 1 Slice:** docker-compose.yml → CSS + Nginx spike → Pod provisioning → ACL config → Troll ACL tests
2. **Phase 2 Slice:** OSLO schema contract → xAPI synthetic data → RDF pipeline → Oxigraph load → Qdrant embeddings → Troll injection + vector tests
3. **Phase 3 Slice:** OpenClaw agent config → Shared SPARQL skill → Role agents (Claire/Marc/Isabelle/Fatima/Ayoub) → Journey scenarios → Troll cross-inference tests
4. **Phase 4 Slice:** Comprehensive troll run → Report generation → Dashboard → Funder intervention points

**Cross-Component Dependencies:**
- OSLO schema (Phase 2) is the contract that agents (Phase 3) query against
- Provenance links (Phase 2) enable dashboard traceability display (Phase 4)
- ACL enforcement (Phase 1) is validated by troll (Phase 1, 2, 4) at each phase
- Observability logging (all phases) feeds dashboard (Phase 4)

---

## Implementation Patterns & Consistency Rules

### Naming Patterns

**File & Directory Naming:**
- All lowercase, hyphen-separated: `xapi-to-rdf.py`, `sparql-skill/`, `troll-agent/`
- Config files: `{service}.config.json` or `{service}.yml`
- SPARQL templates: `{query-name}.rq`
- Schema files: `oslo-{domain}.ttl`

**Python Code Naming:**
- Modules: `snake_case.py`
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_prefixed`

**Docker/Compose Naming:**
- Service names: lowercase, hyphen-separated (`community-solid-server`, `oxigraph`, `qdrant`)
- Volume names: `{service}-data` (e.g., `oxigraph-data`, `qdrant-data`, `css-pods`)
- Network: default (no custom network needed for single compose file)

**RDF/SPARQL Naming:**
- Namespace prefixes follow OSLO conventions: `oslo-educ:`, `oslo-person:`, `xapi:`
- Custom namespace: `pocpod0:` for project-specific classes
- SPARQL variables: `?camelCase` (e.g., `?studentName`, `?learningContext`)

**Agent Naming:**
- OpenClaw agent IDs: lowercase hyphen (`claire-teacher`, `marc-admin`, `troll-adversary`)
- Skill names: lowercase hyphen (`sparql-query`, `hybrid-search`)

### Structure Patterns

**Configuration Co-location:**
- Each service's config lives in `infra/{service}/` alongside its Dockerfile (if custom) and config files
- Agent configurations live in `agents/{agent-name}/`
- Shared across agents: `agents/skills/sparql-query/` and `agents/skills/qdrant-search/`

**Test Co-location:**
- Pipeline tests: `tests/pipeline/` (pytest)
- Integration tests: `tests/integration/` (docker-compose based, pytest)
- Troll tests are the adversarial test suite, not co-located — they live in `agents/troll-adversary/`

**Data Files:**
- Synthetic xAPI input: `data/synthetic/`
- OSLO schema contracts: `data/schemas/`
- Sample queries: `data/queries/`

### Format Patterns

**Logging Format (All Components):**
```json
{
  "timestamp": "ISO-8601",
  "service": "service-name",
  "level": "INFO|WARN|ERROR",
  "event": "event.type.name",
  "agent": "agent-id-if-applicable",
  "duration_ms": 123,
  "details": {}
}
```
- Structured JSON to stdout — docker-compose captures it
- Dashboard reads from docker logs or a shared log volume

**SPARQL Query Templates:**
- Stored as `.rq` files with `$parameter` placeholders
- Parameterized by the shared skill before execution
- Never constructed via string concatenation

**Troll Report Format:**
```json
{
  "attack_category": "acl_enforcement|sparql_injection|cross_inference|vector_privacy|deletion_timing",
  "access_path": "direct|through_skill",
  "test_name": "descriptive-test-name",
  "result": "pass|partial|fail",
  "details": "human-readable explanation",
  "evidence": {}
}
```

**Pod Resource Format:**
- Turtle (`.ttl`) as primary serialization in pods
- JSON-LD available via CSS content negotiation for debugging
- ACL resources as `.acl` files per Solid spec

### Process Patterns

**Error Handling:**
- Pipeline errors: log + continue (don't halt 10K ingestion for one bad statement)
- Agent errors: log + report to user (agent explains what went wrong)
- Troll errors: log as test results (errors are findings, not failures)
- Infrastructure errors: health check catches them, `depends_on` prevents cascading startup failures

**Deletion Cascade Protocol:**
1. Mark Pod resource as soft-deleted (add `pocpod0:deletedAt` triple)
2. Remove all derived triples from Oxigraph matching `prov:wasDerivedFrom <pod-resource-uri>`
3. Remove all Qdrant points with matching `pod_resource_uri` in payload
4. Verify: query all three layers, confirm zero results for the resource
5. Log each step with completion status for dashboard display

**Agent Query Protocol:**
1. Agent determines query type: graph-only, semantic, or hybrid
2. **Graph path:** Agent calls SPARQL skill → skill validates ACL → selects `.rq` template → executes against Oxigraph → returns results with provenance
3. **Semantic path:** Agent calls Qdrant skill → similarity search → returns results with triple/pod URI metadata
4. **Hybrid path:** Agent calls both skills, merges results itself (the agent has context to judge relevance)
5. Agent formats results for its persona's narrative

### Enforcement Guidelines

**All AI Agents Implementing This Project MUST:**
- Use pinned Docker image versions from the table in INFRA-1
- Follow the deletion cascade protocol exactly (3 layers, ordered, verified)
- Use parameterized `.rq` templates for all SPARQL queries (never string concatenation)
- Log all significant operations in the structured JSON format
- Store OSLO vocabulary mappings as Turtle files in `data/schemas/`
- Use `distrobox-host-exec` for accessing podman containers from within distrobox

**Anti-Patterns:**
- Building a REST API wrapper around services that already have APIs
- Hardcoding ACL rules in agent code (ACLs live in pod `.acl` resources)
- Storing derived data as source of truth (Oxigraph and Qdrant are rebuildable indexes)
- Using `latest` Docker tags
- Skipping health checks in docker-compose

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
pocpod0/
├── docker-compose.yml              # All services orchestrated here
├── .env.example                     # Documented environment variables
├── .env                             # Local config (gitignored)
├── README.md
├── LICENSE
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
│
├── infra/                           # Service-specific configuration
│   ├── css/                         # Community Solid Server
│   │   ├── config.json              # CSS server configuration
│   │   └── pods/                    # Pod seed data / ACL templates
│   │       ├── ayoub/
│   │       ├── claire-student-1/
│   │       ├── claire-student-2/
│   │       ├── fatima-child-1/
│   │       ├── fatima-child-2/
│   │       └── school-community/
│   ├── nginx/
│   │   ├── nginx.conf               # Reverse proxy + content negotiation
│   │   └── ssl/                     # Self-signed certs if needed
│   ├── oxigraph/
│   │   └── config.toml              # Oxigraph server config (if needed)
│   └── qdrant/
│       └── config.yaml              # Qdrant collection config
│
├── pipeline/                        # Python package: data ingestion & transformation
│   ├── pyproject.toml               # Python project config (uv/pip)
│   ├── src/
│   │   └── pocpod0_pipeline/
│   │       ├── __init__.py
│   │       ├── ingest.py            # xAPI → OSLO RDF conversion
│   │       ├── load_graph.py        # RDF → Oxigraph loader with provenance
│   │       ├── embed.py             # Content → Qdrant embeddings via OpenRouter
│   │       ├── delete_cascade.py    # 3-layer deletion cascade
│   │       ├── provision_pods.py    # CSS pod provisioning + ACL setup
│   │       ├── oslo_mapper.py       # OSLO vocabulary mapping logic
│   │       └── utils.py             # Shared utilities (logging, config)
│   └── tests/
│       ├── test_ingest.py
│       ├── test_load_graph.py
│       ├── test_embed.py
│       ├── test_delete_cascade.py
│       └── conftest.py              # Shared fixtures
│
├── agents/                          # OpenClaw agent workspace
│   ├── openclaw.config.yaml         # OpenClaw global config (OpenRouter, models)
│   ├── skills/
│   │   ├── sparql-query/            # Shared SPARQL skill (graph queries)
│   │   │   ├── skill.yaml           # Skill definition
│   │   │   ├── handler.py           # SPARQL execution + ACL check
│   │   │   └── templates/           # Parameterized .rq files
│   │   │       ├── student-progress.rq
│   │   │       ├── cross-context-query.rq
│   │   │       ├── aggregate-anonymized.rq
│   │   │       ├── parental-view.rq
│   │   │       └── transfer-profile.rq
│   │   └── qdrant-search/           # Shared Qdrant skill (semantic search)
│   │       ├── skill.yaml           # Skill definition
│   │       └── handler.py           # Vector similarity search + provenance
│   ├── claire-teacher/
│   │   └── agent.yaml               # Claire persona + journey config
│   ├── marc-admin/
│   │   └── agent.yaml
│   ├── isabelle-policy/
│   │   └── agent.yaml
│   ├── fatima-parent/
│   │   └── agent.yaml
│   ├── ayoub-student/
│   │   └── agent.yaml
│   └── troll-adversary/
│       ├── agent.yaml               # Troll persona + dual access config
│       ├── attacks/
│       │   ├── acl-enforcement.py    # Direct infra ACL tests
│       │   ├── sparql-injection.py   # Through-skill injection tests
│       │   ├── cross-inference.py    # Agent-layer NL inference tests
│       │   ├── vector-privacy.py     # Direct Qdrant privacy tests
│       │   └── deletion-timing.py    # 3-layer cascade timing tests
│       └── report/
│           ├── generator.py          # Troll report generation
│           └── template.md           # Report template (non-technical)
│
├── dashboard/                       # Mission control (dev mode)
│   ├── pyproject.toml
│   ├── src/
│   │   └── pocpod0_dashboard/
│   │       ├── __init__.py
│   │       ├── app.py               # FastAPI application
│   │       ├── routes.py            # Dashboard endpoints
│   │       └── templates/           # HTMX templates
│   │           ├── base.html
│   │           ├── mission-control.html
│   │           ├── troll-report.html
│   │           └── query-monitor.html
│   └── static/
│       └── style.css
│
├── data/
│   ├── synthetic/                   # Generated xAPI dataset
│   │   └── README.md                # Dataset generation instructions
│   ├── schemas/                     # OSLO vocabulary mappings
│   │   ├── oslo-education.ttl       # Education domain mapping
│   │   ├── oslo-person.ttl          # Person domain mapping
│   │   ├── xapi-to-oslo.ttl         # xAPI → OSLO mapping rules
│   │   └── pocpod0-vocab.ttl        # Project-specific extensions
│   └── queries/                     # Reference SPARQL queries
│       └── examples/
│
├── scripts/                         # Orchestration scripts
│   ├── setup.sh                     # First-time setup (env check, volume prep)
│   ├── seed-pods.sh                 # Provision pods + ACLs after CSS is healthy
│   ├── run-pipeline.sh              # Full ingestion pipeline
│   ├── run-demo.sh                  # Demo narrative orchestration
│   └── run-troll.sh                 # Adversarial test suite
│
└── tests/                           # Integration tests
    ├── integration/
    │   ├── test_css_pods.py          # Pod provisioning + ACL enforcement
    │   ├── test_oxigraph_queries.py  # SPARQL query correctness
    │   ├── test_qdrant_embeddings.py # Embedding storage + retrieval
    │   ├── test_traceability.py      # Bidirectional provenance links
    │   └── test_deletion_cascade.py  # 3-layer deletion verification
    └── conftest.py                   # Docker-compose test fixtures
```

### Architectural Boundaries

**Service Boundaries (Docker Network):**
```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │   CSS    │  │ Oxigraph │  │  Qdrant  │  │ Nginx  │ │
│  │  :3000   │  │  :7878   │  │  :6333   │  │  :80   │ │
│  │  (Pods)  │  │ (SPARQL) │  │ (Vector) │  │(Proxy) │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│       │    ┌─────────┴──────────────┤             │      │
│       │    │                        │             │      │
│  ┌────┴────┴────────────────────────┴─────────────┘     │
│  │              Agent Layer (OpenClaw)                   │
│  │  ┌─────────────────────────────┐                     │
│  │  │    Shared SPARQL Skill      │ ← All agents route  │
│  │  │  (ACL check → query → merge)│    queries here     │
│  │  └─────────────────────────────┘                     │
│  │  ┌───────┐ ┌────┐ ┌────────┐ ┌──────┐ ┌─────┐      │
│  │  │Claire │ │Marc│ │Isabelle│ │Fatima│ │Ayoub│      │
│  │  └───────┘ └────┘ └────────┘ └──────┘ └─────┘      │
│  │  ┌─────────────────────────────┐                     │
│  │  │      Troll Adversary        │ ← Dual access:      │
│  │  │  (skill + direct infra)     │    skill + direct    │
│  │  └─────────────────────────────┘                     │
│  └──────────────────────────────────────────────────────│
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │          Pipeline (Python)                        │   │
│  │  xAPI → RDF → Oxigraph + Qdrant                 │   │
│  │  (runs as script, not long-running service)      │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │          Dashboard (FastAPI + HTMX)              │   │
│  │  Mission control, troll report, query monitor    │   │
│  │  (dev mode, reads from logs)                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Data Flow:**
```
xAPI statements (synthetic)
    │
    ▼
Pipeline: ingest.py (xAPI → OSLO RDF with provenance)
    │
    ├──▶ CSS Pods (raw Turtle resources + ACLs)
    │
    ├──▶ Oxigraph (OSLO-mapped triples + prov:wasDerivedFrom)
    │
    └──▶ OpenRouter API (embedding generation)
            │
            └──▶ Qdrant (vectors + payload with triple/pod URIs)

Agent query (graph-only):
    Agent → SPARQL Skill → ACL check → Oxigraph SPARQL → results with provenance

Agent query (semantic):
    Agent → Qdrant Skill → similarity search → results with triple/pod URIs

Agent query (hybrid):
    Agent → SPARQL Skill + Qdrant Skill → agent merges both result sets
```

### Requirements to Structure Mapping

| FR Category | Primary Location | Supporting Files |
|-------------|-----------------|------------------|
| Pod Management (FR1–7) | `pipeline/src/.../provision_pods.py` | `infra/css/`, `scripts/seed-pods.sh` |
| Ingestion (FR8–13) | `pipeline/src/.../ingest.py`, `load_graph.py`, `embed.py` | `data/schemas/`, `data/synthetic/` |
| Cross-Context Queries (FR14–20) | `agents/skills/sparql-query/` + `agents/skills/qdrant-search/` | `data/queries/`, agent configs |
| Transfer (FR21–23) | `agents/marc-admin/`, SPARQL skill | `agents/skills/sparql-query/templates/` |
| Governance (FR24–27) | `pipeline/src/.../delete_cascade.py` | Agent configs for governance scenario |
| Adversarial (FR28–34) | `agents/troll-adversary/` | `agents/troll-adversary/attacks/`, `report/` |
| Agent Infra (FR35–37) | `agents/` (all) | `agents/openclaw.config.yaml` |
| Demo/Dashboard (FR38–39) | `dashboard/`, `scripts/run-demo.sh` | `agents/` (intervention routing) |
| Infrastructure (FR40) | `docker-compose.yml` | `infra/`, `.env`, `scripts/setup.sh` |

---

## Architecture Validation Results

### Coherence Validation

**Decision Compatibility:**
- All services are independent containers communicating over Docker network — no version conflicts
- Python pipeline writes to all three data layers; agents read through the SPARQL skill — clean separation
- OpenClaw agents use OpenRouter for LLM inference; pipeline uses OpenRouter for embeddings — single API key
- Dashboard reads logs — no bidirectional dependency with services

**Pattern Consistency:**
- Naming conventions are consistent: hyphen-case for files/services, snake_case for Python, camelCase for SPARQL variables
- All data access follows the same pattern: either through SPARQL skill (agents) or direct Python client (pipeline/troll)
- Logging format is uniform across all components

**Structure Alignment:**
- Project structure maps cleanly to the 4-phase implementation plan
- Each phase adds to the structure without restructuring previous work
- Vertical slices: each phase produces a testable, demonstrable increment

### Requirements Coverage Validation

**Functional Requirements: 40/40 covered**

| FR | Architectural Support | Component |
|----|----------------------|-----------|
| FR1–7 | CSS pods + WebACL + provision script | `pipeline/`, `infra/css/` |
| FR8–13 | Python pipeline + OSLO schemas + provenance | `pipeline/`, `data/schemas/` |
| FR14–20 | SPARQL skill + hybrid search + ACL enforcement | `agents/skills/sparql-query/` |
| FR21–23 | Transfer scenario via agent + ACL grant/revoke | `agents/marc-admin/`, skill |
| FR24–27 | Governance contract + deletion cascade | `pipeline/`, agent scenarios |
| FR28–34 | Troll dual access + attack scripts + report gen | `agents/troll-adversary/` |
| FR35–37 | OpenClaw multi-agent + shared skill + troll dual | `agents/` |
| FR38–39 | Dashboard + demo script + intervention routing | `dashboard/`, `scripts/` |
| FR40 | docker-compose healthchecks + depends_on | `docker-compose.yml` |

**Non-Functional Requirements: All addressed**
- Performance: Docker-local network, Oxigraph is fast at 10K scale, Qdrant is fast for similarity search
- Security: ACL enforcement at pod + query level, parameterized SPARQL, troll validates both
- Observability: Structured JSON logging from all components, dashboard consumes logs
- Reproducibility: Pinned versions, docker-compose up, deterministic pipeline
- Deployment: `.env` for host-specific config, single compose file, < 1 hour setup target

### Implementation Readiness Validation

**Decision Completeness:** All critical decisions documented with specific versions and rationale.

**Structure Completeness:** Full directory tree with every file mapped to a requirement.

**Pattern Completeness:** Naming, logging, error handling, query patterns, deletion protocol all specified.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed (40 FRs, 5 NFR categories)
- [x] Scale and complexity assessed (high — semantic web + adversarial + multi-service)
- [x] Technical constraints identified (committed standards, solo dev, Docker-only)
- [x] Cross-cutting concerns mapped (ACL, provenance, deletion, OSLO, logging, SELinux)

**Architectural Decisions**
- [x] Critical decisions documented with versions (CSS 7, Oxigraph 0.5.6, Qdrant v1.17.0, Nginx 1.28.2)
- [x] Technology stack fully specified (Python pipeline, OpenClaw agents, FastAPI dashboard)
- [x] Integration patterns defined (Docker network, SPARQL skill gateway, dual troll access)
- [x] Performance considerations addressed (local network, appropriate tech at PoC scale)

**Implementation Patterns**
- [x] Naming conventions established (files, Python, Docker, RDF, agents)
- [x] Structure patterns defined (config co-location, test organization, data files)
- [x] Communication patterns specified (agent→skill→service, pipeline→services, troll dual)
- [x] Process patterns documented (error handling, deletion cascade, query protocol)

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established (service, agent, pipeline, dashboard)
- [x] Integration points mapped (data flow diagram, boundary diagram)
- [x] Requirements to structure mapping complete (40 FRs → specific directories)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — technology stack is proven (CSS, Oxigraph, Qdrant are production software), architecture is straightforward (containers + Python + OpenClaw), and the main risk (Nginx content negotiation) has an explicit timebox and fallback.

**Key Strengths:**
- Clean separation of concerns: pods for sovereignty, graph for queries, vectors for semantics
- Troll agent as built-in adversarial validation — architecture tests itself
- Vertical slice implementation — each phase produces a demonstrable increment
- Single `.env` + single `docker-compose up` — minimal operational complexity

**Areas for Future Enhancement (Pilot Phase):**
- Real Solid-OIDC authentication
- Production-grade deletion scheduling (nightly batch vs. immediate cascade)
- Horizontal scaling (Oxigraph federation, Qdrant sharding)
- Real-time event streaming (currently batch pipeline)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions
- Use `distrobox-host-exec` for accessing podman containers from within distrobox

**First Implementation Priority:**
Phase 1 vertical slice: `docker-compose.yml` with CSS + Nginx content negotiation spike → pod provisioning → ACL setup → troll ACL tests.
