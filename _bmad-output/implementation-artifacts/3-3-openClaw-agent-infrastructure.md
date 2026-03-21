# Story 3.3: OpenClaw Agent Infrastructure & Role Persona Configurations

Status: review

## Story

As a **developer**,
I want the OpenClaw multi-agent runtime configured with all 5 role persona agents and a troll adversary agent,
so that every journey story can run its agent against the shared SPARQL and Qdrant skills with proper persona context, ACL identity, and query patterns.

## Acceptance Criteria

**AC1: OpenClaw runtime starts and connects to OpenRouter**
Given OpenClaw is configured with `agents/openclaw.config.yaml` pointing to OpenRouter API
When the runtime starts
Then it connects to OpenRouter using `minimax/minimax-m2.5` (NFR20)
And the single secret `OPENROUTER_API_KEY` is read from `.env` (NFR22)
And the runtime discovers all agent configs in `agents/*/agent.yaml`
And the runtime discovers all shared skills in `agents/skills/*/skill.yaml`

**AC2: Five role agents are spawnable with correct persona and ACL identity**
Given agent configs exist for claire-teacher, marc-admin, isabelle-policy, fatima-parent, and ayoub-student (FR35)
When each agent is spawned by the runtime
Then the agent has its persona description loaded (role, location, narrative context)
And the agent has its ACL role identity set (tutor, admin, regional, parental, student)
And the agent can invoke both shared skills (sparql-query, qdrant-search)

**AC3: Each agent has persona-specific query patterns**
Given a spawned role agent
When the agent processes a user query
Then the agent selects query patterns appropriate to its persona (e.g., Claire uses cross-context-query and student-progress templates; Isabelle uses aggregate-anonymized)
And the agent formats results using its persona's narrative voice

**AC4: Troll agent has dual access model**
Given the troll-adversary agent config exists (FR37)
When the troll agent is spawned
Then it can access data through the shared skills (sparql-query, qdrant-search) — the "through skill" path
And it can access data directly against service endpoints (CSS :3000, Oxigraph :7878, Qdrant :6333) — the "direct" path
And both access paths are explicitly configured in `agents/troll-adversary/agent.yaml`

**AC5: Agent lifecycle logging**
Given any agent spawn or skill invocation
When the event occurs
Then a structured JSON log entry is emitted to stdout with: timestamp, service, level, event, agent, duration_ms, details

## Tasks / Subtasks

### Task 1: Verify OpenClaw runtime configuration (AC1)
- [x] Create `agents/openclaw.json` (Story 3-3 runs before 3-1 per reorder; created here instead)
- [x] Verify the config references OpenRouter API with model (primary: `nvidia/nemotron-3-super-120b-a12b:free`, fallback: `minimax/minimax-m2.5`)
- [x] Verify the config reads `OPENROUTER_API_KEY` from `.env`
- [x] Verify the runtime discovers all 6 agents via `openclaw agents list`
- [x] Verify shared skills enabled in config (`sparql-query`, `qdrant-search`)
- [x] Add openclaw-gateway service to `docker-compose.yml` with GHCR image
- [x] Verify gateway starts healthy, web portal accessible and paired
- [x] Test runtime startup via `distrobox-host-exec podman compose`

### Task 2: Create Claire teacher agent config (AC2, AC3)
- [x] Create `agents/claire-teacher/agent.yaml` with:
  - **Agent ID:** `claire-teacher`
  - **Persona:** Secondary school math/science teacher, Brussels (Flemish school), 120 students across 5 classes
  - **ACL role:** `tutor` — read access to authorized student pods, school community pod
  - **Available skills:** `sparql-query`, `qdrant-search`
  - **Query patterns:** Primarily uses `cross-context-query.rq` and `student-progress.rq` templates
  - **Persona-specific behavior:**
    - Queries focus on individual student progress across learning contexts
    - Hybrid queries enrich structured results with semantic insights from tutoring notes, self-study logs
    - Results formatted as teacher-oriented observations ("Student X shows progress in...")
    - Can request side-by-side graph-only vs hybrid comparison
  - **Narrative context:** Claire notices students failing math but suspects they are learning differently outside school. She needs cross-institutional visibility.

### Task 3: Create Marc admin agent config (AC2, AC3)
- [x] Create `agents/marc-admin/agent.yaml` with:
  - **Agent ID:** `marc-admin`
  - **Persona:** School administrator/IT coordinator, Liege (Wallonia), running Happi + Teams
  - **ACL role:** `admin` — read/write access to school community pod, read access to enrolled student pods, ACL management capability
  - **Available skills:** `sparql-query`, `qdrant-search`
  - **Query patterns:** Primarily uses `transfer-profile.rq` template
  - **Persona-specific behavior:**
    - Queries focus on complete student profiles for transfer scenarios
    - Can initiate ACL grant (new school access) and revocation (old school access)
    - Results formatted as administrative records
    - Handles cross-community (NL to FR) data seamlessly via structured RDF
  - **Narrative context:** Marc handles a mid-semester transfer from a Flemish school. He needs the student's full history instantly.

### Task 4: Create Isabelle policy advisor agent config (AC2, AC3)
- [x] Create `agents/isabelle-policy/agent.yaml` with:
  - **Agent ID:** `isabelle-policy`
  - **Persona:** Regional education policy advisor, Brussels-Capital, overseeing publicly funded extracurricular programs
  - **ACL role:** `regional` — aggregate-only read access across community pods, no individual student data
  - **Available skills:** `sparql-query`, `qdrant-search`
  - **Query patterns:** Primarily uses `aggregate-anonymized.rq` template
  - **Persona-specific behavior:**
    - Queries must return aggregate statistics only, never individual student records
    - Cross-community scope (both NL and FR communities)
    - Results formatted as policy evidence ("N students across M schools show improvement in...")
    - Provenance includes consent grant counts, not individual identifiers
  - **Narrative context:** Budget season. Isabelle needs evidence-based justification for STEM program funding, not self-reported narratives.

### Task 5: Create Fatima parent agent config (AC2, AC3)
- [x] Create `agents/fatima-parent/agent.yaml` with:
  - **Agent ID:** `fatima-parent`
  - **Persona:** Parent of 2 children, bilingual Brussels household — one child in Flemish school, one in French-speaking school
  - **ACL role:** `parental` — read access to her children's pods only
  - **Available skills:** `sparql-query`, `qdrant-search`
  - **Query patterns:** Primarily uses `parental-view.rq` template
  - **Persona-specific behavior:**
    - Queries focus on unified view of both children across all learning contexts
    - Results distinguish between children while presenting a unified view
    - Cross-linguistic data (NL/FR) handled transparently
    - Can verify consent/ACL state of children's pods
  - **Narrative context:** Fatima juggles two platforms and gets fragmented report cards. She needs one unified view of both children.

### Task 6: Create Ayoub student agent config (AC2, AC3)
- [x] Create `agents/ayoub-student/agent.yaml` with:
  - **Agent ID:** `ayoub-student`
  - **Persona:** 16-year-old student, Brussels, transferring from Flemish to French-speaking school
  - **ACL role:** `student` — full control over own pod (read/write/manage ACLs on own data)
  - **Available skills:** `sparql-query`, `qdrant-search`
  - **Query patterns:** Uses `student-progress.rq` for own data
  - **Persona-specific behavior:**
    - Queries are scoped exclusively to own pod
    - Full sovereignty: can view, query, and manage own learning data
    - Can inspect who has access to own pod (ACL audit)
    - Results formatted as student-oriented self-view
  - **Narrative context:** Ayoub's data follows him through a school transfer. He approaches governance transition age where control shifts from guardian to student.

### Task 7: Create troll adversary agent config (AC4)
- [x] Create `agents/troll-adversary/agent.yaml` with:
  - **Agent ID:** `troll-adversary`
  - **Persona:** Adversarial security tester — dual access model
  - **ACL role:** none / configurable per test — the troll impersonates various roles and tests boundaries
  - **Available skills:** `sparql-query`, `qdrant-search` (for "through skill" attack path)
  - **Direct access endpoints** (for "direct to infrastructure" attack path):
    - CSS: `http://community-solid-server:3000` — ACL enforcement tests
    - Oxigraph: `http://oxigraph:7878/query` — SPARQL injection tests (direct)
    - Qdrant: `http://qdrant:6333` — vector privacy tests (direct)
  - **Attack categories configured:**
    - `acl_enforcement` — direct to CSS/Oxigraph (tests infrastructure access control)
    - `sparql_injection` — through shared skill (tests query sanitization)
    - `cross_inference` — through agent layer with NL prompts (tests data leakage)
    - `vector_privacy` — direct to Qdrant (tests embedding PII exposure)
    - `deletion_timing` — direct to all 3 layers (tests cascade completeness)
  - **Troll report format per test:**
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
  - **Narrative context:** The troll is the built-in adversarial test suite. It validates that defenses hold and reports honestly where they do not.

### Task 8: Validate agent discovery and spawn (AC1, AC2)
- [x] Start OpenClaw runtime and verify it discovers all 6 agent configs (5 role + 1 troll)
- [x] Spawn each agent and verify persona and ACL role are loaded correctly
- [x] Verify each agent can see both shared skills (sparql-query, qdrant-search)
- [x] Verify troll agent can access direct service endpoints in addition to shared skills
- [x] Verify structured JSON logging for agent spawn events

### Task 9: MVP troll direct-path connectivity validation (AC4, AC5)
*Scope adjusted: skill-mediated path (through_skill) deferred to Stories 3-1/3-2 when handlers exist. Direct path validates AC4 and service reachability from the Docker network.*
- [x] From inside openclaw-gateway container, hit CSS directly: `GET http://community-solid-server:3000/ayoub/` — verified 401 (reachable, unauthenticated access correctly denied)
- [x] From inside openclaw-gateway container, hit Oxigraph directly: `POST http://oxigraph:7878/query` with `SELECT * WHERE { ?s ?p ?o } LIMIT 1` — verified results JSON returned
- [x] From inside openclaw-gateway container, hit Qdrant directly: `GET http://qdrant:6333/collections` — verified collection list returned (pocpod0_embeddings)
- [x] Emit troll report JSON for each test (pass/fail/partial with details)
- [x] Verify all 3 services are reachable on the Docker network from OpenClaw container

## Dev Notes

### Architecture Decisions Referenced

- **FR35:** System runs 5 role persona agents (Claire, Marc, Isabelle, Fatima, Ayoub)
- **FR37:** Troll agent dual access model — through skills AND direct to services
- **NFR20:** Agent LLM: `minimax/minimax-m2.5` via OpenRouter API
- **NFR22:** Single secret: `OPENROUTER_API_KEY` in `.env`
- **SEC-1:** No user authentication in PoC. Agent identity is configured, not authenticated.
- **SEC-2:** ACL enforcement at two levels: Pod level (CSS WebACL) + Query level (SPARQL skill validates role). Agent configs declare the role; the skill enforces it.
- **API-2:** Two shared skills (sparql-query, qdrant-search). Agents compose hybrid queries by calling both.
- **INFRA-1:** All services on default Docker network, accessible by container name.

### OpenClaw Runtime Details

- OpenClaw is **Node.js-based**, self-contained agent runtime
- Global config: `agents/openclaw.config.yaml` (created in Story 3-1)
- Agent configs: `agents/{agent-name}/agent.yaml`
- Skills shared across agents: `agents/skills/{skill-name}/`
- Skills created in prior stories:
  - `agents/skills/sparql-query/` (Story 3-1): ACL-validated SPARQL queries against Oxigraph
  - `agents/skills/qdrant-search/` (Story 3-2): Semantic similarity search against Qdrant
- The OpenClaw config already points to OpenRouter API. This story creates the agent configs that the runtime discovers.

### Agent YAML Structure Pattern

Each agent config should follow this structure (adapt per OpenClaw's actual schema):

```yaml
agent:
  id: claire-teacher
  name: Claire
  description: |
    Secondary school math/science teacher in Brussels (Flemish school).
    120 students across 5 classes. Needs cross-institutional visibility
    into student progress beyond what Smartschool shows.

  persona:
    role: tutor
    location: Brussels
    institution_type: secondary_school
    language_context: NL (Flemish)

  acl:
    role_identity: tutor
    authorized_pods:
      - "http://community-solid-server:3000/ayoub/"
      - "http://community-solid-server:3000/claire-student-1/"
      - "http://community-solid-server:3000/claire-student-2/"
    community_pods:
      - "http://community-solid-server:3000/school-community/"

  skills:
    - sparql-query
    - qdrant-search

  query_patterns:
    preferred_templates:
      - cross-context-query.rq
      - student-progress.rq
    default_query_type: hybrid
    merge_strategy: "Prioritize cross-institutional insights. When SPARQL returns structured facts and Qdrant returns semantic context, synthesize into a narrative that reveals learning patterns invisible in school data alone."

  system_prompt: |
    You are Claire, a secondary school math/science teacher in Brussels.
    You have 120 students across 5 classes. You use the pocpod0 system
    to query student progress across all learning contexts — school,
    tutoring, self-study, extracurricular.

    When answering queries:
    1. First execute a graph-only SPARQL query for structured facts
    2. Then execute a hybrid query (SPARQL + Qdrant) for enriched insights
    3. Present both results, highlighting what the hybrid adds
    4. Always show provenance: which data sources contributed
    5. Only access data from pods your ACL role authorizes
```

### Service Endpoints (Docker Network)

| Service | Hostname | Port | Protocol |
|---------|----------|------|----------|
| CSS (Solid Pods) | `community-solid-server` | 3000 | HTTP/LDP |
| Oxigraph (SPARQL) | `oxigraph` | 7878 | SPARQL HTTP |
| Qdrant (Vector) | `qdrant` | 6333 | REST API |

### ACL Role Mapping

| Agent | ACL Role | Access Scope |
|-------|----------|-------------|
| claire-teacher | tutor | Authorized student pods + school community pod |
| marc-admin | admin | School community pod + enrolled student pods + ACL management |
| isabelle-policy | regional | Aggregate-only across community pods, no individual data |
| fatima-parent | parental | Her children's pods only |
| ayoub-student | student | Full control over own pod |
| troll-adversary | none/variable | Both skill-mediated and direct infrastructure access |

### Naming Conventions

- Agent directories: lowercase hyphen (`claire-teacher`, `marc-admin`, etc.)
- Agent IDs in configs: lowercase hyphen (same as directory name)
- Config files: `agent.yaml` (one per agent directory)
- Skill references in configs: match skill directory names (`sparql-query`, `qdrant-search`)

### Structured JSON Logging Format

All agent lifecycle events must use this format (to stdout, captured by docker-compose):

```json
{
  "timestamp": "ISO-8601",
  "service": "openclaw-runtime",
  "level": "INFO",
  "event": "agent.spawned",
  "agent": "claire-teacher",
  "duration_ms": 0,
  "details": {
    "acl_role": "tutor",
    "skills_loaded": ["sparql-query", "qdrant-search"]
  }
}
```

### Project Structure Notes

Directories/files to create:

```
agents/
├── openclaw.config.yaml              # EXISTS (Story 3-1) — verify/update if needed
├── skills/
│   ├── sparql-query/                  # EXISTS (Story 3-1)
│   └── qdrant-search/                 # EXISTS (Story 3-2)
├── claire-teacher/
│   └── agent.yaml                     # NEW — tutor persona
├── marc-admin/
│   └── agent.yaml                     # NEW — admin persona
├── isabelle-policy/
│   └── agent.yaml                     # NEW — regional policy persona
├── fatima-parent/
│   └── agent.yaml                     # NEW — parental persona
├── ayoub-student/
│   └── agent.yaml                     # NEW — student persona
└── troll-adversary/
    └── agent.yaml                     # NEW — adversarial tester persona
```

### Dependencies

- **Depends on Story 3-1:** SPARQL skill and OpenClaw runtime config must exist
- **Depends on Story 3-2:** Qdrant skill must exist
- **Depends on Epic 1:** Pods must exist with ACLs configured (for authorized_pods references in agent configs)
- **Depends on Epic 2:** Data must be loaded in Oxigraph and Qdrant (for agents to have data to query)
- **Blocks Story 3-4:** Claire's journey depends on her agent config existing
- **Blocks Story 3-5:** Fatima's journey depends on her agent config
- **Blocks Story 3-6:** Isabelle's journey depends on her agent config
- **Blocks Story 4-1:** Marc's transfer journey depends on his agent config
- **Blocks Story 5-1:** Ayoub's sovereignty journey depends on his agent config
- **Blocks all troll stories:** Troll agent config required for adversarial testing

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec community-solid-server ...`
- OpenClaw runtime MUST be added as a Docker service in the existing `docker-compose.yml`, running on the internal Docker network only, accessible via local web portal. It does NOT run on the host.

### Validated Patterns from Epic 2

- **CSS auth pattern (Story 1.5):** Use `Authorization: WebID <webid>` header for CSS authentication (NOT `X-Ms-User`)
- **Oxigraph health endpoint (Story 2.3):** Health check is `GET /` (root, returns 200), NOT `/health`

### OpenClaw Resources

- **GitHub:** https://github.com/openclaw/openclaw
- **Docker deployment guide:** https://openclaws.io/blog/openclaw-docker-deployment/
- **Docker Hub:** https://hub.docker.com/r/alpine/openclaw

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (SEC-1, SEC-2, API-2, INFRA-1, Agent Naming, Project Structure)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR35, FR37, NFR20, NFR22, User Journeys for all 5 personas)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.1 for runtime setup context, Epic 3 overview)
- Story 3-1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill, openclaw.config.yaml)
- Story 3-2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` (Qdrant skill, hybrid query protocol)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (story-3-3-openClaw-agent-infrastructure)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

#### OpenClaw Docker Setup — Getting Started Handoff

**Context:** Story 3-3 is the first story to integrate OpenClaw into the pocpod0 stack. The story spec was written with assumptions about OpenClaw's config format that turned out to be wrong (YAML agent files vs actual JSON5 + SKILL.md). This log captures every gotcha so future stories and a getting-started guide can skip the pain.

**1. Image registry — use GHCR, not Docker Hub**
- Story referenced `hub.docker.com/r/alpine/openclaw` — this is a community mirror, not official.
- Official image: `ghcr.io/openclaw/openclaw:latest` (published from GitHub, verified at `docs.openclaw.ai/install/docker`).
- Pin to a date tag (e.g. `2026.3.13`) for reproducibility once stabilized.

**2. Config format — JSON5, not YAML**
- Story spec assumed `agents/openclaw.config.yaml` + per-agent `agent.yaml` files.
- Reality: OpenClaw uses a single `openclaw.json` (JSON5 format) for all config: gateway settings, agents list, skills, model, env vars.
- Per-agent customization: agents are objects in `agents.list[]`, each with `id`, `name`, `identity`, optional `systemPrompt`.
- Skills use `SKILL.md` files (YAML frontmatter + Markdown instructions), NOT `skill.yaml`.

**3. Entrypoint — compiled binary, not `node dist/index.js`**
- The GHCR image ships a compiled `openclaw` / `openclaw-gateway` binary at `/usr/local/bin/openclaw`.
- The docs show `node dist/index.js gateway ...` as command — this also works (file exists at `/app/dist/index.js`, workdir is `/app`).
- To override the command in docker-compose, use `entrypoint: ["/bin/sh", "-c"]` with a shell command block, because the default entrypoint is `docker-entrypoint.sh` which delegates to the binary.

**4. Gateway `--bind lan` requires origin config**
- Error: `non-loopback Control UI requires gateway.controlUi.allowedOrigins`
- Fix: set `gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback: true` in `openclaw.json`. Acceptable for local PoC; production should use explicit `allowedOrigins`.
- Without this, the gateway crashes in a restart loop.

**5. Permission errors (EACCES) — volume mount strategy**
- **Root cause:** Bind-mounting `openclaw.json` directly to `/home/node/.openclaw/openclaw.json` causes podman (rootless + SELinux) to set the parent directory ownership to root. The `node` user (UID 1000 inside container) cannot then `mkdir` sibling directories (`canvas/`, `cron/`, `devices/`).
- **Failed approaches:**
  - Bind-mount file only → EACCES on `mkdir /home/node/.openclaw/canvas`
  - Bind-mount file + named volume at subpath → named volume shadows bind mount
- **Working solution:** Named volume at `/home/node/.openclaw` (writable by `node` user) + bind-mount `openclaw.json` to `/tmp/openclaw.json` (staging) + init copy via entrypoint:
  ```yaml
  volumes:
    - ./agents/openclaw.json:/tmp/openclaw.json:ro${VOLUME_FLAGS:-}
    - openclaw-data:/home/node/.openclaw
  entrypoint: ["/bin/sh", "-c"]
  command:
    - |
      cp /tmp/openclaw.json /home/node/.openclaw/openclaw.json
      exec node dist/index.js gateway ...
  ```
- Named volumes do NOT need `:Z` SELinux flag (podman handles internally). Only bind mounts need `${VOLUME_FLAGS:-}`.
- **Future (production):** Replace bind-mount+copy with a custom Dockerfile that COPYs `openclaw.json` at build time.

**6. Device pairing — two-step process**
- The web portal at `http://localhost:18789` shows a pairing screen on first connect.
- Pairing is NOT automatic even with `OPENCLAW_GATEWAY_TOKEN`. The token authenticates CLI commands, not browser sessions.
- Flow:
  1. Open web portal → it sends a pairing request (visible in gateway logs as `reason=pairing required`)
  2. From inside the container, approve the request:
     ```bash
     podman exec openclaw-gateway openclaw devices approve --latest \
       --url ws://127.0.0.1:18789 \
       --token $OPENCLAW_GATEWAY_TOKEN
     ```
  3. Refresh browser → connected.
- Pairing state persists in the named volume (`/home/node/.openclaw/devices/`). Survives restarts but not volume deletion.

**7. Required environment variables**
All of these must be set (from `.env` via `env_file` + explicit `environment` block):
| Variable | Purpose | Example |
|----------|---------|---------|
| `OPENROUTER_API_KEY` | LLM API access via OpenRouter | `sk-or-v1-...` |
| `OPENCLAW_GATEWAY_TOKEN` | Gateway auth for CLI + pairing | `openssl rand -hex 32` |
| `OPENCLAW_GATEWAY_BIND` | Network bind (`lan` or `loopback`) | `lan` |
| `OPENCLAW_GATEWAY_PORT` | Gateway port | `18789` |
| `GOG_KEYRING_PASSWORD` | Encrypts keyring at rest | `openssl rand -hex 32` |
| `HOME` | Node.js home dir | `/home/node` |
| `XDG_CONFIG_HOME` | OpenClaw config dir | `/home/node/.openclaw` |
| `NODE_ENV` | Runtime mode | `production` |

**8. Validated startup sequence**
After `podman compose up -d openclaw-gateway`, healthy startup logs show:
```
[canvas] host mounted at http://0.0.0.0:18789/__openclaw__/canvas/
[heartbeat] started
[health-monitor] started (interval: 300s)
[gateway] agent model: openrouter/minimax/minimax-m2.5
[gateway] listening on ws://0.0.0.0:18789 (PID 1)
[browser/server] Browser control listening on http://127.0.0.1:18791/
```
No `EACCES` errors. Healthcheck passes (TCP 18789).

### Completion Notes List

- Task 1 complete: OpenClaw gateway running as docker-compose service, 6 agents discovered, web portal paired. See Debug Log for full setup handoff.
- Tasks 2-7 complete: All 6 agent workspaces created using OpenClaw's actual config format — SOUL.md (persona), AGENTS.md (instructions), IDENTITY.md, and empty placeholder files for TOOLS.md/USER.md/HEARTBEAT.md/BOOTSTRAP.md/MEMORY.md. openclaw.json wired with workspace + agentDir per agent. Key findings: (1) agent.yaml does not exist in OpenClaw — workspace markdown files are the correct pattern; (2) skipBootstrap: true required for read-only workspace mounts; (3) skills.load.extraDirs needed for custom skill discovery; (4) all workspace files must be pre-seeded (UI shows MISSING badge otherwise).
- Task 8 complete: All 6 agents discovered via `openclaw agents list`, IDENTITY.md loaded per agent, sparql-query and qdrant-search skills eligible (source: openclaw-extra).
- Task 9 complete: MVP troll direct-path tests — all 3 services reachable from openclaw-gateway container. CSS returned 401 (fixed baseUrl mismatch: CSS must start with `--baseUrl http://community-solid-server:3000/` or Docker-internal requests fall outside identifier space and return 500). Oxigraph and Qdrant both pass. Troll report JSON emitted in correct format for all tests.

### File List

- `agents/openclaw.json` — MODIFIED: added workspace/agentDir per agent, skills.load.extraDirs, skipBootstrap
- `agents/skills/sparql-query/SKILL.md` — NEW: skill definition stub (full handler in Story 3-1)
- `agents/skills/qdrant-search/SKILL.md` — NEW: skill definition stub (full handler in Story 3-2)
- `agents/claire-teacher/SOUL.md` — NEW: teacher persona
- `agents/claire-teacher/AGENTS.md` — NEW: operating instructions
- `agents/claire-teacher/IDENTITY.md` — NEW: name/emoji
- `agents/claire-teacher/TOOLS.md` — NEW: empty placeholder
- `agents/claire-teacher/USER.md` — NEW: empty placeholder
- `agents/claire-teacher/HEARTBEAT.md` — NEW: empty placeholder
- `agents/claire-teacher/BOOTSTRAP.md` — NEW: empty placeholder
- `agents/claire-teacher/MEMORY.md` — NEW: empty placeholder
- `agents/marc-admin/SOUL.md` — NEW
- `agents/marc-admin/AGENTS.md` — NEW
- `agents/marc-admin/IDENTITY.md` — NEW
- `agents/marc-admin/TOOLS.md` — NEW (empty)
- `agents/marc-admin/USER.md` — NEW (empty)
- `agents/marc-admin/HEARTBEAT.md` — NEW (empty)
- `agents/marc-admin/BOOTSTRAP.md` — NEW (empty)
- `agents/marc-admin/MEMORY.md` — NEW (empty)
- `agents/isabelle-policy/SOUL.md` — NEW
- `agents/isabelle-policy/AGENTS.md` — NEW
- `agents/isabelle-policy/IDENTITY.md` — NEW
- `agents/isabelle-policy/TOOLS.md` — NEW (empty)
- `agents/isabelle-policy/USER.md` — NEW (empty)
- `agents/isabelle-policy/HEARTBEAT.md` — NEW (empty)
- `agents/isabelle-policy/BOOTSTRAP.md` — NEW (empty)
- `agents/isabelle-policy/MEMORY.md` — NEW (empty)
- `agents/fatima-parent/SOUL.md` — NEW
- `agents/fatima-parent/AGENTS.md` — NEW
- `agents/fatima-parent/IDENTITY.md` — NEW
- `agents/fatima-parent/TOOLS.md` — NEW (empty)
- `agents/fatima-parent/USER.md` — NEW (empty)
- `agents/fatima-parent/HEARTBEAT.md` — NEW (empty)
- `agents/fatima-parent/BOOTSTRAP.md` — NEW (empty)
- `agents/fatima-parent/MEMORY.md` — NEW (empty)
- `agents/ayoub-student/SOUL.md` — NEW
- `agents/ayoub-student/AGENTS.md` — NEW
- `agents/ayoub-student/IDENTITY.md` — NEW
- `agents/ayoub-student/TOOLS.md` — NEW (empty)
- `agents/ayoub-student/USER.md` — NEW (empty)
- `agents/ayoub-student/HEARTBEAT.md` — NEW (empty)
- `agents/ayoub-student/BOOTSTRAP.md` — NEW (empty)
- `agents/ayoub-student/MEMORY.md` — NEW (empty)
- `agents/troll-adversary/SOUL.md` — NEW
- `agents/troll-adversary/AGENTS.md` — NEW
- `agents/troll-adversary/IDENTITY.md` — NEW
- `agents/troll-adversary/TOOLS.md` — NEW (empty)
- `agents/troll-adversary/USER.md` — NEW (empty)
- `agents/troll-adversary/HEARTBEAT.md` — NEW (empty)
- `agents/troll-adversary/BOOTSTRAP.md` — NEW (empty)
- `agents/troll-adversary/MEMORY.md` — NEW (empty)
- `docker-compose.yml` — MODIFIED: added `./agents:/app/agents:ro` volume mount; added `--baseUrl http://community-solid-server:3000/` to CSS command (fixes Docker-internal identifier space error)

### Change Log

- 2026-03-21: Task 1 complete — OpenClaw gateway service added to docker-compose, runtime verified with 6 agents and OpenRouter model. Updated Stories 3-1 and 3-2 to reflect actual OpenClaw format (JSON5 + SKILL.md, not YAML).
- 2026-03-21: Tasks 2-9 complete — All 6 agent workspaces created (SOUL.md/AGENTS.md/IDENTITY.md + placeholders). Skills discovered via extraDirs. CSS baseUrl fixed for Docker-internal access. MVP troll direct-path tests pass for all 3 services.
