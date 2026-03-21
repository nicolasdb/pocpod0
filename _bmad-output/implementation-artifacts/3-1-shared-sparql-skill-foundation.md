# Story 3.1: [foundation] OpenClaw Agent Runtime & Shared SPARQL Skill

Status: ready-for-dev

## Story

As a **developer**,
I want the OpenClaw agent runtime configured with a shared SPARQL skill that validates ACLs and executes parameterized queries,
so that all role agents have a secure, reusable foundation for querying the graph layer.

## Acceptance Criteria

**AC1: OpenClaw runtime configured with OpenRouter**
Given OpenClaw is installed with `openclaw.json` pointing to OpenRouter API (minimax/minimax-m2.5)
When the agent runtime starts
Then the OpenRouter connection is verified and the runtime is ready to spawn agents

**AC2: SPARQL skill executes parameterized queries with ACL enforcement**
Given the shared SPARQL skill (`agents/skills/sparql-query/`)
When an agent calls the skill with a query request and role identity
Then the skill validates the agent's role against Pod ACLs before executing
And selects the appropriate parameterized `.rq` template
And executes the query against Oxigraph
And returns results with provenance metadata (named graph URI == Pod resource URI, using `GRAPH <uri> {}` scoping)

**AC3: Access denied on insufficient ACLs**
Given an agent with insufficient ACL permissions
When it calls the SPARQL skill for a resource it cannot access
Then the skill denies the query and returns an access-denied response
And the denial is logged in structured JSON format (NFR9)

**AC4: Query logging on every execution**
Given any SPARQL skill execution
When the query completes (success or denial)
Then a log entry is emitted with timestamp, requesting agent, latency, and result count (NFR9)

## Tasks / Subtasks

### Task 1: Install and configure OpenClaw runtime (AC1)
- [ ] Install OpenClaw (Node.js-based agent runtime) in the project
- [ ] Create `agents/openclaw.json` with OpenRouter API configuration
  - Model: `minimax/minimax-m2.5` (NFR20)
  - API endpoint: OpenRouter API
  - API key: reference `OPENROUTER_API_KEY` from `.env`
- [ ] Verify the runtime can start and connect to OpenRouter
- [ ] Confirm the runtime can discover and load skills from `agents/skills/`
- [ ] Document any OpenClaw-specific setup steps

### Task 2: Create SPARQL skill directory structure (AC2)
- [ ] Create `agents/skills/sparql-query/SKILL.md` — Skill definition file
- [ ] Create `agents/skills/sparql-query/handler.py` — Main skill handler
- [ ] Create `agents/skills/sparql-query/templates/` directory for .rq files

### Task 3: Implement SPARQL query templates (AC2)
- [ ] Create `agents/skills/sparql-query/templates/student-progress.rq`
  - Query: student learning progress across contexts, scoped by student Pod URI
  - Parameters: `$studentPodUri`, `$learningContext` (optional)
  - Must use `GRAPH <$studentPodUri> {}` scoping for provenance (named graph URI == Pod resource URI)
- [ ] Create `agents/skills/sparql-query/templates/cross-context-query.rq`
  - Query: cross-institutional data for a given subject/topic across authorized pods
  - Parameters: `$subject`, `$authorizedPodUris` (list)
  - Must include provenance metadata in results
- [ ] Create `agents/skills/sparql-query/templates/aggregate-anonymized.rq`
  - Query: aggregate statistics without individual identification
  - Parameters: `$programUri`, `$communityScope`
  - Results must be aggregate counts/averages, never individual records
- [ ] Create `agents/skills/sparql-query/templates/parental-view.rq`
  - Query: unified view of children's progress for a parent
  - Parameters: `$childPodUris` (list), `$parentRole`
  - Must include provenance per child
- [ ] Create `agents/skills/sparql-query/templates/transfer-profile.rq`
  - Query: complete learning profile for a student transfer scenario
  - Parameters: `$studentPodUri`
  - Must include full history with provenance

### Task 4: Implement ACL validation in handler (AC2, AC3)
- [ ] In `handler.py`, implement ACL check function:
  1. Receive agent role identity and target Pod resource URIs from skill invocation
  2. Query CSS Pod ACL resources to determine if role has access
  3. If access denied: return structured access-denied response, log denial
  4. If access granted: proceed to template selection and execution
- [ ] ACL check must happen BEFORE any SPARQL query is executed (SEC-2)
- [ ] Access-denied response format: `{ "status": "denied", "reason": "...", "agent": "...", "requested_resources": [...] }`

### Task 5: Implement template parameterization engine (AC2)
- [ ] In `handler.py`, implement template loader:
  1. Read `.rq` file from `templates/` directory
  2. Replace `$parameter` placeholders with provided values
  3. NEVER use string concatenation for query construction (SEC-3)
  4. Validate all parameters are provided before execution
  5. Validate parameter values against injection patterns (no SPARQL keywords in parameter values)
- [ ] Template selection logic: skill determines which `.rq` template based on the query type requested by the agent

### Task 6: Implement Oxigraph query execution (AC2)
- [ ] In `handler.py`, implement SPARQL execution:
  1. Send parameterized query via HTTP POST to Oxigraph at port 7878
  2. Oxigraph SPARQL endpoint: `http://oxigraph:7878/query` (Docker network hostname)
  3. Content-Type for request: `application/sparql-query`
  4. Accept header: `application/sparql-results+json`
  5. Parse JSON results
  6. Provenance is implicit: the named graph URI in `GRAPH <uri> {}` scoping IS the Pod resource URI (no separate `prov:wasDerivedFrom` extraction needed)
  7. Return results with provenance to the calling agent

### Task 7: Implement structured JSON logging (AC3, AC4)
- [ ] Every skill invocation logs a structured JSON entry to stdout:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "sparql-query-skill",
    "level": "INFO",
    "event": "sparql.query.executed",
    "agent": "claire-teacher",
    "duration_ms": 123,
    "details": {
      "template": "student-progress.rq",
      "result_count": 42,
      "acl_check": "passed",
      "oxigraph_latency_ms": 98
    }
  }
  ```
- [ ] Access denied events use `"event": "sparql.query.denied"` with `"level": "WARN"`
- [ ] Error events use `"event": "sparql.query.error"` with `"level": "ERROR"`
- [ ] Log to stdout so docker-compose captures it (feeds dashboard in Phase 4)

### Task 8: Create SKILL.md definition (AC1, AC2)
- [ ] Define `agents/skills/sparql-query/SKILL.md` with:
  - Skill name: `sparql-query`
  - Description: Shared SPARQL skill for ACL-validated graph queries
  - Input schema: query type, parameters, agent role identity
  - Output schema: results with provenance metadata, or access-denied response
  - Dependencies: Oxigraph endpoint, CSS Pod ACLs

### Task 9: Integration verification (AC1, AC2, AC3, AC4)
- [ ] Verify an agent can call the SPARQL skill and receive results with provenance
- [ ] Verify ACL denial works correctly for unauthorized access
- [ ] Verify all 5 `.rq` templates execute correctly against Oxigraph with test data
- [ ] Verify structured logging output for success, denial, and error cases
- [ ] Verify the skill works from within distrobox (use `distrobox-host-exec` for podman container access)

## Dev Notes

### Architecture Decisions Referenced

- **SEC-2:** ACL enforcement at query level — this skill IS the query-level enforcement. Pod-level enforcement is CSS native WebACL (Epic 1). This skill adds the second layer of defense-in-depth.
- **SEC-3:** Parameterized `.rq` templates, NEVER string concatenation. The troll agent (Story 3.x/Phase 4) will test injection through this skill interface.
- **API-1:** No REST API wrapper. The skill communicates directly with Oxigraph via its native SPARQL HTTP endpoint.
- **API-2:** Two separate skills (SPARQL and Qdrant) keep concerns clean. This story implements the SPARQL skill only.
- **NFR20:** Agent LLM model is `minimax/minimax-m2.5` via OpenRouter API.

### OpenClaw Runtime Details (updated post-Story 3-3)

- **Runtime already configured in Story 3-3** — `openclaw.json` exists, gateway running, agents listed
- OpenClaw uses **JSON5** config (`openclaw.json`), NOT YAML. Skills use **SKILL.md** (YAML frontmatter + Markdown), NOT `skill.yaml`.
- Global config: `agents/openclaw.json` (bind-mounted into container at `/home/node/.openclaw/openclaw.json`)
- Agent configs: defined in `agents.list[]` inside `openclaw.json` (NOT separate agent.yaml files)
- Skills shared across agents: `agents/skills/{skill-name}/SKILL.md`
- Skills are already enabled in `openclaw.json` → `skills.entries` → `sparql-query: { enabled: true }`
- The skill handler is Python (`handler.py`) — OpenClaw supports Python skill handlers
- OpenRouter API key comes from `OPENROUTER_API_KEY` in `.env` at project root
- **Task 1 of this story is partially done**: runtime install, config, OpenRouter connection, and skill discovery are all validated. This story only needs to create the SKILL.md and handler.py for the SPARQL skill.

### Oxigraph Connection Details

- Docker service name: `oxigraph`
- SPARQL query endpoint: `http://oxigraph:7878/query` (HTTP POST)
- SPARQL update endpoint: `http://oxigraph:7878/update` (HTTP POST, not needed for this skill)
- Image: `oxigraph/oxigraph:0.5.6`
- Port: 7878

### CSS (Solid Server) Connection Details

- Docker service name: `community-solid-server`
- Port: 3000
- ACL resources: `.acl` files per Solid spec on each Pod resource
- Image: `communitysolidserver/community-solid-server:7`

### SPARQL Template Pattern

Templates use `$parameter` placeholders. Example pattern for `student-progress.rq`:

```sparql
PREFIX oslo-educ: <https://data.vlaanderen.be/ns/onderwijs#>
PREFIX oslo-person: <https://data.vlaanderen.be/ns/persoon#>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX pocpod0: <http://pocpod0.local/vocab#>

SELECT ?activity ?result ?context
WHERE {
  GRAPH <$studentPodUri> {
    ?activity oslo-educ:heeftDeelnemer ?student .
    ?activity oslo-educ:heeftResultaat ?result .
    OPTIONAL { ?activity oslo-educ:context ?context }
  }
}
```

The handler reads the `.rq` file, replaces `$studentPodUri` with the actual value (properly escaped as an IRI), and sends the resulting query to Oxigraph.

### Naming Conventions

- Skill directory: `sparql-query` (lowercase hyphen)
- Agent IDs: `claire-teacher`, `marc-admin`, `isabelle-policy`, `fatima-parent`, `ayoub-student`, `troll-adversary`
- Python files: `handler.py` (snake_case)
- Python functions: `snake_case`
- Python classes: `PascalCase`
- SPARQL variables: `?camelCase` (e.g., `?studentName`, `?learningContext`)
- Template files: `{query-name}.rq` (lowercase hyphen)

### Skill Flow (Complete)

1. Agent calls skill with: `{ query_type: "student-progress", parameters: { studentPodUri: "..." }, agent_role: "claire-teacher" }`
2. Skill extracts `agent_role` and target Pod URIs from parameters
3. Skill checks CSS Pod ACLs: does `claire-teacher` role have read access to the target pods?
4. If NO: return `{ status: "denied", ... }`, log denial, done
5. If YES: select `.rq` template based on `query_type`
6. Parameterize template: replace `$studentPodUri` etc. with actual values
7. Execute parameterized SPARQL query against `http://oxigraph:7878/query` via HTTP POST
8. Parse results (provenance is the named graph URI used in `GRAPH <uri> {}` scoping)
9. Return: `{ status: "success", results: [...], provenance: [...] }`
10. Log execution with timing

### Project Structure Notes

Only `handler.py` needs to be created. Everything else already exists (created in Stories 2.7 and 3.3):

```
agents/
├── openclaw.json              # EXISTS (Story 3.3)
└── skills/
    └── sparql-query/          # EXISTS
        ├── SKILL.md           # EXISTS stub (Story 3.3) — UPDATE with invocation pattern
        ├── parameterize.py    # EXISTS (Story 2.7) — reuse as-is
        ├── handler.py         # NEW — only file to create
        └── templates/         # EXISTS — all 5 templates already created
            ├── student-progress.rq    # EXISTS
            ├── cross-context-query.rq # EXISTS
            ├── aggregate-anonymized.rq # EXISTS
            ├── parental-view.rq       # EXISTS
            └── transfer-profile.rq    # EXISTS
```

### Dependencies

- **Depends on Epic 1:** Pods must exist with ACLs configured (Story 1.1, 1.4)
- **Depends on Epic 2:** Data must be loaded in Oxigraph with OSLO mappings and provenance (Stories 2.1, 2.2, 2.3)
- **Reuses Story 2.7 parameterize.py:** Import the parameterization engine from `agents/skills/sparql-query/parameterize.py` (SEC-3 security constraints: whitelist-only parameter substitution, no string concatenation). This is the validated engine for safe `.rq` template parameterization.
- **Reuses Story 2.6 traceability.py:** Import provenance navigation functions from `pipeline/src/pocpod0_pipeline/traceability.py` — functions: `trace_embedding_to_pod()`, `trace_pod_to_triples()`, `trace_triples_to_embeddings()`, `verify_provenance_consistency()`. Named graph URI == Pod resource URI; queries use `GRAPH <uri> {}` syntax.
- **Blocks Story 3.2:** Qdrant skill depends on SPARQL skill existing for hybrid query composition
- **Blocks Stories 3.3-3.7:** All role agent journey stories depend on this skill

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec oxigraph ...`

### Handoff from Story 3.3

The following was discovered during Story 3-3 implementation and directly affects this story:

**1. SKILL.md already exists — update, don't create**
`agents/skills/sparql-query/SKILL.md` was created as a stub in Story 3-3 to make the skill discoverable by the runtime. Task 2 says "create" it — update the existing file instead.

**2. `parameterize.py` already exists**
`agents/skills/sparql-query/parameterize.py` was carried over from Story 2.7. Confirm it is intact before building the handler around it.

**3. How OpenClaw invokes skill handlers**
OpenClaw agents use their `exec` tool to run `handler.py` via command line — the LLM reads SKILL.md instructions and executes the handler as a subprocess. The handler must be invocable via CLI (accept args or stdin), not just importable as a library. Update SKILL.md to include the exact invocation pattern (e.g. `python handler.py --query-type student-progress --role tutor --params '{...}'`).

**4. CSS baseUrl is `http://community-solid-server:3000/` for Docker-internal calls**
CSS was restarted in Story 3-3 with `--baseUrl http://community-solid-server:3000/`. All CSS calls from within the Docker network (including from `handler.py` running inside the openclaw-gateway container) must use this hostname — never `localhost:3000`. Using localhost returns HTTP 500 ("identifier outside configured identifier space").

**5. Re-provision pods after CSS restart**
CSS was restarted in Story 3-3 (baseUrl fix). ACLs will have drifted. Run `provision_pods.py` before any ACL-sensitive handler tests:
```bash
source .venv/bin/activate && python -m pocpod0_pipeline.provision_pods
```

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (SEC-2, SEC-3, API-1, API-2, INFRA-1)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR14, FR36, NFR Performance, NFR Security, NFR Observability)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.1 acceptance criteria)
- OSLO vocabulary schema: `data/schemas/` (created in Story 2.1)
- Project structure: Architecture doc, "Complete Project Directory Structure" section

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
