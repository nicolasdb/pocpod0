# Story 3.3: OpenClaw Agent Infrastructure & Role Persona Configurations

Status: ready-for-dev

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
- [ ] Confirm `agents/openclaw.config.yaml` was created in Story 3-1 and is valid
- [ ] Verify the config references OpenRouter API with model `minimax/minimax-m2.5`
- [ ] Verify the config reads `OPENROUTER_API_KEY` from `.env`
- [ ] Verify the runtime can discover agent directories under `agents/*/agent.yaml`
- [ ] Verify the runtime can discover shared skills under `agents/skills/*/skill.yaml`
- [ ] Test runtime startup with `distrobox-host-exec` if running inside distrobox

### Task 2: Create Claire teacher agent config (AC2, AC3)
- [ ] Create `agents/claire-teacher/agent.yaml` with:
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
- [ ] Create `agents/marc-admin/agent.yaml` with:
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
- [ ] Create `agents/isabelle-policy/agent.yaml` with:
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
- [ ] Create `agents/fatima-parent/agent.yaml` with:
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
- [ ] Create `agents/ayoub-student/agent.yaml` with:
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
- [ ] Create `agents/troll-adversary/agent.yaml` with:
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
- [ ] Start OpenClaw runtime and verify it discovers all 6 agent configs (5 role + 1 troll)
- [ ] Spawn each agent and verify persona and ACL role are loaded correctly
- [ ] Verify each agent can see both shared skills (sparql-query, qdrant-search)
- [ ] Verify troll agent can access direct service endpoints in addition to shared skills
- [ ] Verify structured JSON logging for agent spawn events

### Task 9: Validate agent-to-skill invocation (AC2, AC3, AC5)
- [ ] Have Claire agent invoke sparql-query skill with a student-progress query — verify it reaches Oxigraph
- [ ] Have Claire agent invoke qdrant-search skill with a semantic query — verify it reaches Qdrant
- [ ] Verify ACL role identity is passed from agent config to skill invocation
- [ ] Verify structured JSON logs capture agent name, skill invoked, and timing
- [ ] Test from within distrobox using `distrobox-host-exec` for podman container access

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
- OpenClaw runtime itself runs on the host (Node.js), connecting to Docker services via exposed ports or Docker network

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (SEC-1, SEC-2, API-2, INFRA-1, Agent Naming, Project Structure)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR35, FR37, NFR20, NFR22, User Journeys for all 5 personas)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.1 for runtime setup context, Epic 3 overview)
- Story 3-1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill, openclaw.config.yaml)
- Story 3-2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` (Qdrant skill, hybrid query protocol)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (story-3-3-openClaw-agent-infrastructure)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
