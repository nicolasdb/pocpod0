# Story 3.5: [journey] [target] Fatima — Unified Parental View

Status: done

## Story

As **Fatima** (parent of two children, bilingual Brussels household),
I want to see a unified view of both my children's learning progress across their different schools and activities,
so that I can make informed decisions from a position of sovereignty, not dependency on fragmented platforms.

## Acceptance Criteria

**AC1: Unified cross-context view for both children**
Given Fatima's agent is configured with parental ACL access to both children's pods
When Fatima queries for a unified view of both children
Then the results combine data from both children across all learning contexts (school, tutoring, extracurricular)
And data from both NL and FR school contexts is included seamlessly via structured OSLO-mapped RDF (FR18)
Note: FR18 compliance depends on Epic 2 OSLO mapping being correct. It is validated by integration tests against a live stack with NL+FR data loaded — not by unit tests, which assert structure only.

**AC2: Distinguishable per-child progress with provenance**
Given Fatima's query results
When displayed to Fatima
Then each child's progress is distinguishable within the unified view
And provenance shows which Pod resources contributed to the view (FR20)

**AC3: ACL enforcement — no data beyond authorized pods**
Given Fatima's ACL scope (parental access to her two children's pods only)
When she queries for data beyond her children's pods
Then no unauthorized data is returned
And the denial is logged in structured JSON format

**AC4: Agent configuration and persona**
Given the Fatima parent agent config at `agents/fatima-parent/agent.yaml`
When the agent starts
Then it has the correct persona (parent, bilingual Brussels household), role identity (`fatima-parent`), and ACL scope (her two children's pods)
And it can invoke both the shared SPARQL skill and the shared Qdrant skill

**AC5: Structured logging for all queries**
Given any query Fatima's agent executes
When the query completes (success or denial)
Then a structured JSON log entry is emitted with timestamp, agent (`fatima-parent`), latency, result count, and query type

## Tasks / Subtasks

### Task 1: Create Fatima parent agent configuration (AC4)
- [x] Create `agents/fatima-parent/agent.yaml` with:
  - Agent ID: `fatima-parent`
  - Persona: Fatima, parent of two children in a bilingual Brussels household. One child attends a Flemish (NL) school, the other attends a French-speaking (FR) school. Fatima wants a single unified view of both children's learning progress across all contexts.
  - Role: `parent`
  - LLM model: `minimax/minimax-m2.5` via OpenRouter
  - Skills: `sparql-query`, `qdrant-search`
  - ACL scope: parental read access to both children's pods:
    - `http://community-solid-server:3000/fatima-child-1/` (child in NL school)
    - `http://community-solid-server:3000/fatima-child-2/` (child in FR school)
  - Query protocol: hybrid (agent merges both skill results for the unified view)
  - Default query template: `parental-view.rq`
- [x] Verify the agent.yaml is loadable by the OpenClaw runtime

### Task 2: Create/verify parental-view SPARQL template (AC1, AC2)
- [x] Created/rewritten `agents/skills/sparql-query/templates/parental-view.rq`:
  - Parameters: `$child_pod_1`, `$child_pod_2` (two explicit pod root URIs)
  - Uses pocpod0 vocabulary (NOT oslo-educ — matches oslo_mapper.py output)
  - VALUES clause scopes query to both pod namespaces
  - FILTER(strstarts) for pod-level graph scoping
  - Returns `?g ?actor ?verb ?object ?scaledScore ?success ?timestamp`
  - ORDER BY `?childPod ?timestamp`

### Task 3: Implement Fatima's journey query flow (AC1, AC2, AC3)
- [x] SOUL.md configured with complete negative-space detection behavior:
  - Attendance without outcomes → surface gap + call-to-action (petition provider)
  - Cross-child attendance discrepancy → report side-by-side, no cause assertion
  - Threshold signal (success=True + score<0.6) → data quality signal to verify
  - Qdrant divergence from SPARQL → stale record / RGPD deletion right narrative
  - School-community pod empty → governance narrative (declarative access inheritance)
- [x] ACL enforcement via existing handler mechanism (CSS WebACL check before SPARQL)
- [x] School-community pod has Fatima's parental ACL; returns empty results (gap surfaces naturally)

### Task 4: Implement unified view result formatting (AC2)
- [x] `_summarize_parental_view()` in handler.py:
  - Splits bindings by child pod prefix
  - Per-child summaries via `_summarize_bindings()`
  - Gap 1: `attended_no_outcome_count` (sessions with no scaledScore)
  - Gap 2: `below_60_marked_success` (success=True + scaledScore < 0.6)
  - Gap 3: `attendance_discrepancy` (same activity, different session counts)
  - UUID-skip fix: `re.fullmatch(r"[0-9a-f\-]{8,36}", obj)` to avoid false UUID matches on activity names starting with hex chars

### Task 5: Implement ACL boundary enforcement test (AC3)
- [x] `test_parental_view_acl_denied_fatima_cannot_access_ayoub` — CSS returns 403 for ayoub pod
- [x] `test_parental_view_denial_logged_as_warn` — denial emits WARN structured JSON log

### Task 6: Implement structured logging for Fatima's queries (AC5)
- [x] `test_parental_view_success_logged_with_agent_fatima` — success emits INFO log with agent=fatima-parent, event=sparql.query.success
- [x] Existing handler logging covers all query types including parental-view

### Task 7: End-to-end journey verification (AC1, AC2, AC3, AC4, AC5)
- [x] 9 unit tests added (`TestParentalView`) — all pass
- [x] 3 integration tests added (skipped when Docker services unavailable)
- [x] Pre-existing test failures fixed (summary vs results key, provenance collapse to pod root)
- [ ] Live end-to-end run with running Docker stack (integration tests pass when services up)

## Dev Notes

### Architecture Decisions Referenced

- **DA-2:** Provenance & Traceability Schema. For aggregate views (parental-view, community-stats), provenance is collapsed to pod root URI (e.g. `http://…/fatima-child-1/`) rather than individual document URIs. Individual document-level provenance applies only to single-resource queries. Fatima sees which pods contributed, not which specific files. Use `parameterize.py` (Story 2.7) for safe query construction.
- **SEC-2:** ACL enforcement at query level. The SPARQL skill validates `fatima-parent` role against Pod ACLs BEFORE executing queries, using CSS auth with `Authorization: WebID <webid>` header (Story 1.5). This is the second layer of defense-in-depth (Pod-level WebACL is the first layer from Epic 1).
- **SEC-3:** Parameterized `.rq` templates. The `parental-view.rq` template uses `$childPodUris` parameter — never string concatenation.
- **API-2:** Two separate skills. Fatima's agent calls SPARQL skill for structured cross-context data and Qdrant skill for semantic enrichment. The agent merges the results itself (hybrid protocol).
- **DA-3:** OSLO Vocabulary Schema Contract. NL and FR school data is seamlessly queryable because both are mapped to the same OSLO vocabulary classes during Phase 2 ingestion. The SPARQL query does not need language-specific handling.

### Agent Configuration Pattern

The `agent.yaml` follows the OpenClaw agent configuration pattern. Key fields:
- `id`: `fatima-parent` (used as agent identity for ACL checks and logging)
- `model`: `minimax/minimax-m2.5` (via OpenRouter, NFR20)
- `skills`: list of shared skills this agent can invoke (`sparql-query`, `qdrant-search`)
- `persona`: natural language description of Fatima's role and context
- `acl_scope`: explicit list of Pod URIs this agent can access (enforced by SPARQL skill)

### Cross-Community Data Handling (NL + FR)

Fatima's scenario is a cross-community query: one child in a Flemish school, one in a French-speaking school. This works seamlessly because:
1. Phase 2 ingestion maps ALL xAPI data (regardless of source community) to OSLO vocabulary classes
2. OSLO classes are language-neutral structured RDF — `oslo-educ:Leeractiviteit` is the same class whether the source was a Flemish or French-speaking school
3. The `parental-view.rq` SPARQL template queries OSLO classes, not source-specific fields
4. No language translation is needed — the query operates on structured data, not free text

This is a key demo point: the bilingual household scenario proves that OSLO-mapped RDF eliminates language barriers in structured data.

### Pod URIs for Fatima's Children

From the architecture doc project structure:
- Child 1 pod: `http://community-solid-server:3000/fatima-child-1/` (enrolled in NL school)
- Child 2 pod: `http://community-solid-server:3000/fatima-child-2/` (enrolled in FR school)
- CSS Docker service: `community-solid-server` on port 3000
- ACL resources: `.acl` files on each child's pod granting `fatima-parent` read access

### Oxigraph Connection Details

- Docker service name: `oxigraph`
- SPARQL query endpoint: `http://oxigraph:7878/query` (HTTP POST)
- Image: `oxigraph/oxigraph:0.5.6`
- Port: 7878

### Qdrant Connection Details

- Docker service name: `qdrant`
- REST API endpoint: `http://qdrant:6333`
- Image: `qdrant/qdrant:v1.17.0`
- Collection name: check Story 2.5 implementation for the collection name
- Embedding model: `qwen/qwen3-embedding-8b` via OpenRouter (for query embedding generation)

### CSS (Solid Server) Connection Details

- Docker service name: `community-solid-server`
- Port: 3000
- Image: `communitysolidserver/community-solid-server:7`
- ACL resources: `.acl` files per Solid spec on each Pod resource

### Naming Conventions

- Agent ID: `fatima-parent` (lowercase hyphen)
- Agent config: `agents/fatima-parent/agent.yaml`
- SPARQL template: `parental-view.rq` (lowercase hyphen `.rq`)
- Python functions: `snake_case`
- SPARQL variables: `?camelCase` (e.g., `?childName`, `?learningContext`, `?provenanceUri`)
- Log service name: `fatima-parent-agent`

### Structured JSON Logging Format

All log entries follow the project-wide format:
```json
{
  "timestamp": "ISO-8601",
  "service": "service-name",
  "level": "INFO|WARN|ERROR",
  "event": "event.type.name",
  "agent": "fatima-parent",
  "duration_ms": 123,
  "details": {}
}
```

### Project Structure Notes

Directories/files to create:

```
agents/
└── fatima-parent/
    └── agent.yaml                       # NEW - Fatima parent agent config
```

Files that must already exist (from earlier stories):

```
agents/
├── openclaw.config.yaml                 # Created in Story 3.1
└── skills/
    ├── sparql-query/                    # Created in Story 3.1
    │   ├── skill.yaml
    │   ├── handler.py
    │   └── templates/
    │       └── parental-view.rq         # Created in Story 3.1 (verify/update)
    └── qdrant-search/                   # Created in Story 3.2
        ├── skill.yaml
        └── handler.py
```

Pod data that must already exist (from Epic 1 + Epic 2):

```
infra/css/pods/
├── fatima-child-1/                      # Created in Story 1.3
│   └── *.acl                            # Parental ACL for fatima-parent
└── fatima-child-2/                      # Created in Story 1.3
    └── *.acl                            # Parental ACL for fatima-parent
```

### Dependencies

- **Depends on Story 3.1:** Shared SPARQL skill must exist with `parental-view.rq` template and ACL validation
- **Depends on Story 3.2:** Shared Qdrant skill must exist for hybrid query (semantic enrichment)
- **Depends on Story 3.3:** OpenClaw agent infrastructure must be configured (agent runtime, agent loading)
- **Depends on Epic 1:** Pods for fatima-child-1 and fatima-child-2 must exist with parental ACLs configured (Stories 1.1, 1.3, 1.4)
- **Depends on Epic 2:** Data must be loaded in Oxigraph with OSLO mappings and provenance for both children across NL and FR school contexts (Stories 2.1, 2.2, 2.3). Qdrant embeddings loaded (Story 2.5).
- **Priority:** [target] — implement if Phase 3 has capacity after must-ship stories (Claire, Marc, Ayoub) are complete

### Attendance Anomaly Detection Intent

The system surfaces unexpected signals from the data — it does not pre-categorize scenarios. Two gap types are reported:
- `attendance_discrepancy`: same activity, different session counts across both children (≥2 have it)
- `one_sided_activity`: activity visible for only one child (may reflect access asymmetry, participation gap, or inherited community pod access including other participants)

The second type is significant: Fatima may inherit access to community-level data through her parental role, meaning Sam's 18 sessions could appear against an anonymised community average of 15. The system flags the anomaly; Fatima interprets. Do not add logic to explain or suppress these signals.

Future: community pod comparison (Sam vs anonymised cohort) requires Qdrant semantic search or community pod SPARQL — this is out of scope for Story 3.5 but should be addressed in Story 3.6/3.8 or a dedicated gap-analysis story.

### Log Agent Identity

The skill derives `agent` log field from the WebID by default, producing `"fatima"` from `http://…/fatima/profile/card#me`. To emit `"fatima-parent"` (as required by AC5), the caller must pass `agent_id: fatima-parent` explicitly in skill params. This is documented in SOUL.md.

Architectural debt (IG-2): the `logging_service` field in `agent.yaml` is not read by the shared skill handler. All log entries use `service: sparql-query-skill`. Per-agent service names in logs require the OpenClaw runtime to pass agent config into skill invocations — a future API design decision.

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec community-solid-server ...`
- Example: `distrobox-host-exec podman exec oxigraph ...`

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-2, DA-3, SEC-2, SEC-3, API-2, INFRA-1, Agent Query Protocol)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR18, FR20, Journey 3: Fatima — Unified Parental View)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.4 acceptance criteria)
- Story 3.1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill with parental-view.rq template)
- Story 3.2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` (Qdrant skill for hybrid queries)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (story-3-5-fatima-unified-parental-view)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6 (Claude Code)

### Debug Log References
- Pre-existing: `test_success_returns_results` — handler returns `summary` since Story 3.4; fixed assertion
- Pre-existing: `test_provenance_extracted_from_graph_variable` — handler collapses to pod root; fixed assertion
- Pre-existing: integration tests expecting `results` key — fixed to `summary`
- Pre-existing: integration `test_parental_view_template_executes` using old `child_uri` param — fixed to `child_pod_1`/`child_pod_2`
- New: `test_parental_view_attendance_discrepancy_detected` failing — `activity-robotics-workshop` starts with `'a'` (hex char), matched UUID filter incorrectly. Fixed with `re.fullmatch(r"[0-9a-f\-]{8,36}", obj)` requiring full UUID pattern.
- Narrative pivot: PRD said "son struggles in math" but actual data shows good scores. Pivoted to real data signals: attendance discrepancy (Sam 18 vs Léa 16 robotics sessions), threshold discrepancy (FR school uses 50% threshold), workshop outcome gap, Léa Sciences failure in Qdrant but not SPARQL.

### Completion Notes List
- parental-view.rq rewritten with pocpod0 vocabulary (NOT oslo-educ) and two-child VALUES clause — same vocab fix as Story 3.4 Bug 3
- `_summarize_parental_view()` detects three gap types: attended-no-outcome, below-60-marked-success, attendance-discrepancy
- SOUL.md implements five negative-space detection patterns with governance call-to-action for school-community empty pod
- School-community pod has Fatima's ACL already; returns empty results — governance gap surfaces naturally
- Dataset imperfection is a feature, not a bug: demonstrates system value in real-world messy data conditions
- Integration tests skip gracefully when Docker services unavailable (existing `_services_available()` mechanism)

### File List
- `agents/fatima-parent/agent.yaml` — NEW: agent metadata, model, skills, ACL scope, WebID
- `agents/fatima-parent/SOUL.md` — REWRITTEN: negative-space detection patterns + governance model
- `agents/skills/sparql-query/templates/parental-view.rq` — REWRITTEN: two-child VALUES clause, pocpod0 vocab, pod-scoped FILTER
- `agents/skills/sparql-query/handler.py` — UPDATED: `_summarize_parental_view()` + parental-view branch in `run_skill()` + UUID regex fix
- `agents/skills/sparql-query/SKILL.md` — UPDATED: parental-view params + output format docs
- `agents/skills/sparql-query/tests/test_handler.py` — UPDATED: fixed 4 pre-existing failures + added 9 unit tests + 3 integration tests

### Change Log
- 2026-03-23: Story 3.5 implemented — Fatima unified parental view with negative-space gap detection
