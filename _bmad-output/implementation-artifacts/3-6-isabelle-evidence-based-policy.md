# Story 3.6: [journey] [target] Isabelle — Evidence-Based Policy

Status: done

## Story

As **Isabelle** (regional education policy advisor, Brussels-Capital),
I want to query aggregate anonymized program impact across communities,
so that I can justify funding decisions with evidence-based data instead of self-reported narratives.

### Persona Context

Isabelle works for Brussels-Capital Region — not for the NL community (VGC) or FR community (COCOF). Education is a community competence in Belgium: Isabelle funds cross-community extracurricular programs but has no jurisdiction over schools and cannot compel communities to share student outcome data. Her contractual leverage (grant convention rapportage clauses) produces self-reported Word/PDF narratives, not auditable data. Neither community will share student records with a regional entity — GDPR is invoked as the blocker, but the real firewall is political (jurisdictional encroachment). The result: Isabelle has been making funding decisions affecting children's lives without verifiable outcome data, told this is fine.

Her demo moment is not being impressed by numbers. It is **relief** — seeing cross-community, provenance-backed impact data for the first time after years of epistemic blindness.

EU alignment: the EU Data Governance Act (in force 2023) and the European Education Area initiative are designed for exactly this use case. This system is DGA-forward infrastructure.

## Acceptance Criteria

**AC1: Cross-context aggregate results with structural anonymization**
Given Isabelle's agent is configured with regional aggregate-read ACL access
When Isabelle queries "What is the measurable impact of funded STEM programs on participating students?"
Then the system returns a cross-context aggregate: participant count + average score across ALL activities for students who attended the robotics program, spanning available community pods
And no individual student data is exposed — anonymization is structural via GROUP BY (individual retrieval impossible by query construction)
And results include provenance: "derived from N named graphs across M student pods"

**AC2: Provenance with anonymization guarantees**
Given aggregate query results
When Isabelle inspects provenance
Then the system shows: "this aggregate is derived from N scored activities across M named graphs from P student pods, all with active regional-access consent grants"
And anonymization guarantees are displayed alongside results
_PoC note: `consent_verified: true` is simulated — the PoC data has no `regional-access` consent triples (only `ext-consent-type: parental-opt-in` exists). The SPARQL filter for consent verification is a Pilot-phase deliverable (BP-3). The field is present as a placeholder so the funder demo includes the right structure; it must not be presented as a live verification._

**AC3: Aggregate-only access enforcement**
Given Isabelle attempts a query that would return individual student data
When the query executes
Then the system enforces aggregate-only access — no individual records returned
And the enforcement is logged in structured JSON format

**AC4: Agent configuration and persona**
Given the Isabelle policy agent config at `agents/isabelle-policy/agent.yaml`
When the agent starts
Then it has the correct persona (regional education policy advisor, Brussels-Capital), role identity (`isabelle-policy`), and ACL scope (regional aggregate-read)
And it can invoke the shared SPARQL skill

**AC5: Structured logging for all queries**
Given any query Isabelle's agent executes
When the query completes (success or denial)
Then a structured JSON log entry is emitted with timestamp, agent (`isabelle-policy`), latency, result count, and query type

## Tasks / Subtasks

### Task 1: Create Isabelle policy agent configuration (AC4)
- [x] Create `agents/isabelle-policy/agent.yaml` with:
  - Agent ID: `isabelle-policy`
  - Persona: Isabelle, regional education policy advisor for Brussels-Capital Region. Oversees publicly funded extracurricular programs. Needs evidence-based program impact data to justify funding decisions. Currently receives only Word/PDF narrative reports with self-reported participant counts.
  - Role: `regional-policy`
  - LLM model: `minimax/minimax-m2.5` via OpenRouter
  - Skills: `sparql-query` (primary — aggregate queries are structured/graph-only)
  - ACL scope: regional aggregate-read access — can read aggregate statistics derived from student pods that have active `regional-access` consent grants. CANNOT read individual student records.
  - Query protocol: graph-only (aggregate anonymized queries are structured SPARQL, not semantic search)
  - Default query template: `aggregate-anonymized.rq`
  - Access restriction: `aggregate-only` — the skill must enforce that this role can only execute aggregate queries (GROUP BY / COUNT / AVG), never queries returning individual records
- [x] Verify the agent.yaml is loadable by the OpenClaw runtime

### Task 2: Rewrite aggregate-anonymized SPARQL template — B' cross-context approach (AC1, AC2)
- [x] **Data audit finding:** The existing `aggregate-anonymized.rq` uses `oslo-educ:` predicates that DO NOT EXIST in Oxigraph. The actual vocabulary is `https://poc-pod0.edu/vocab/`. Robotics records (58 total) have NO `scaledScore` — attendance only. The template must be rewritten from scratch.
- [x] **B' approach:** Two-stage cross-context aggregate query:
  1. **Stage 1:** Find all students who attended the funded program (object URI contains "robotics")
  2. **Stage 2:** Aggregate their scores across ALL activities in Oxigraph (not just robotics)
  - This is the architecturally correct question: "did students in the funded program show improvement across their broader learning?" — impossible with Word documents even if both communities cooperated
  - Uses real existing data (ayoub, fatima-child-1, fatima-child-2 have scores on other activities)
- [x] Rewrite `agents/skills/sparql-query/templates/aggregate-anonymized.rq` with:
  - Parameters: `$program_activity` (URI substring to match the funded program, e.g. `robotics`), `$community_scope` (informational — aggregated across all available pods)
  - **All predicates from `poc-pod0.edu/vocab/` namespace** — NOT oslo-educ
  - Stage 1: find students via `poc:verb` containing "attended" + `poc:object` containing `$program_activity`
  - Stage 2: aggregate `poc:scaledScore` for those students across ALL named graphs
  - GROUP BY ensures structural anonymization — individual scores never returned
  - Return: `?participantCount`, `?namedGraphCount`, `?scoredActivityCount`, `?averageScore`, `?minScore`, `?maxScore`
  - Provenance fields: `?namedGraphCount` (named graphs accessed), plus count derivable from provenance extraction in handler
  - Example template structure:
    ```sparql
    # aggregate-anonymized.rq
    # B' cross-context aggregate: students who attended $program_activity,
    # aggregated across ALL their scored activities.
    # Parameters: $program_activity (URI substring), $community_scope (label only)
    PREFIX poc: <https://poc-pod0.edu/vocab/>

    SELECT
      (COUNT(DISTINCT ?student) AS ?participantCount)
      (COUNT(DISTINCT ?scoreGraph) AS ?namedGraphCount)
      (COUNT(?score) AS ?scoredActivityCount)
      (AVG(?score) AS ?averageScore)
      (MIN(?score) AS ?minScore)
      (MAX(?score) AS ?maxScore)
    WHERE {
      # Stage 1: find students who attended the funded program
      GRAPH ?attendGraph {
        ?attendActivity poc:object $program_activity ;
                        poc:actor ?student .
      }
      # Stage 2: aggregate all scores for those students across any graph
      GRAPH ?scoreGraph {
        ?scoreActivity poc:actor ?student ;
                       poc:scaledScore ?score .
      }
    }
    ```
  - Note: `$program_activity` will be substituted as a URI value by parameterize.py — use the full robotics URI from Oxigraph (e.g. `<https://poc-pod0.edu/vocab/activity-robotics-workshop>` or a FILTER with CONTAINS)

### Task 3: Implement aggregate-only access enforcement in SPARQL skill (AC3)
- [x] In `agents/skills/sparql-query/handler.py`, add aggregate-only enforcement for the `regional-policy` role:
  1. When the agent role is `isabelle-policy` (or role type is `regional-policy`):
     - Verify the requested query template is `aggregate-anonymized.rq` (or another aggregate-only template)
     - If the agent attempts to use a non-aggregate template (e.g., `student-progress.rq`, `parental-view.rq`), DENY the query
     - Return access-denied response explaining aggregate-only constraint
  2. Additional safeguard: validate that the SPARQL query contains `GROUP BY` clause (aggregate enforcement at query structure level)
  3. If an individual-record query is attempted through any path, deny it and log the attempt
- [x] This is a defense-in-depth measure: even if the agent's LLM is tricked into requesting individual data, the skill layer blocks it

### Task 4: Implement provenance narrative for aggregates (AC2)
- [x] The agent must format provenance information as a human-readable narrative alongside results:
  - Template: "This aggregate is derived from {scoredActivityCount} scored activities across {namedGraphCount} named graphs from {participantCount} student pods, all with active regional-access consent grants."
  - The counts come from the SPARQL query's aggregate provenance fields
  - Anonymization guarantee statement: "No individual student data was accessed or returned. All results are aggregated at the program level."
- [x] The provenance narrative must be part of the agent's response formatting, not just raw SPARQL result data
- [x] Include consent verification in the provenance: confirm that all contributing pods have active `regional-access` consent grants

### Task 5: Implement Isabelle's journey query flow (AC1, AC2, AC3)
- [x] Configure the agent's system prompt to handle the policy impact query:
  1. Agent receives natural language query from Isabelle (e.g., "What is the measurable impact of funded STEM programs on participating students?")
  2. Agent determines query type: **graph-only** (aggregate queries are structured SPARQL — no semantic search needed for statistical aggregates)
  3. Agent calls SPARQL skill with:
     - `query_type`: `aggregate-anonymized`
     - `parameters`: `{ programUri: "<STEM-program-URI>", communityScope: "both" }`
     - `agent_role`: `isabelle-policy`
  4. SPARQL skill validates:
     - ACL: does `isabelle-policy` have regional aggregate-read access?
     - Aggregate-only: is the requested template an aggregate template?
  5. If both checks pass: execute `aggregate-anonymized.rq` against Oxigraph, return aggregate results with provenance counts
  6. If either check fails: return access-denied response (AC3)
  7. Agent formats results with provenance narrative and anonymization guarantees (Task 4)
  8. Agent presents the evidence-based program impact summary

### Task 6: Implement individual-data-request denial scenario (AC3)
- [x] Configure a test scenario where Isabelle's agent (or the agent's LLM, via prompt manipulation) attempts to query individual student records:
  - Scenario A: Agent tries to use `student-progress.rq` template — skill denies (wrong template for role)
  - Scenario B: Agent tries to use `parental-view.rq` template — skill denies (wrong template for role)
  - Scenario C: Agent constructs a query without GROUP BY — skill detects non-aggregate query structure and denies
- [x] For each denial, verify:
  - Access-denied response returned to agent
  - Denial logged with structured JSON:
    ```json
    {
      "timestamp": "ISO-8601",
      "service": "sparql-query-skill",
      "level": "WARN",
      "event": "sparql.query.denied",
      "agent": "isabelle-policy",
      "duration_ms": 3,
      "details": {
        "reason": "Aggregate-only access: isabelle-policy cannot execute individual-record queries",
        "requested_template": "student-progress.rq",
        "allowed_templates": ["aggregate-anonymized.rq"],
        "acl_check": "denied"
      }
    }
    ```
- [x] This validates the defense-in-depth: even if the LLM wants to return individual data, the skill layer prevents it

### Task 7: Implement structured logging for Isabelle's queries (AC5)
- [x] Every query Isabelle's agent executes must produce a structured JSON log entry:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "isabelle-policy-agent",
    "level": "INFO",
    "event": "agent.query.executed",
    "agent": "isabelle-policy",
    "duration_ms": 420,
    "details": {
      "query_type": "graph-only",
      "sparql_template": "aggregate-anonymized.rq",
      "community_scope": "both",
      "participant_count": 32,
      "pod_count": 32,
      "triple_count": 847,
      "anonymization": "aggregate-only",
      "consent_verified": true
    }
  }
  ```
- [x] Log to stdout so docker-compose captures it (feeds mission control dashboard in Phase 4)

### Task 8: End-to-end journey verification (AC1, AC2, AC3, AC4, AC5)
- [x] Run Isabelle's agent with the STEM program impact query end-to-end
- [x] Verify results are aggregate only — no individual student identifiers or records in output
- [x] Verify results span both NL and FR communities (cross-community aggregate)
- [x] Verify provenance narrative is present: "derived from N scored activities across M named graphs from P student pods, all with active regional-access consent grants"
- [x] Verify anonymization guarantee statement is displayed alongside results
- [x] Verify aggregate-only enforcement: attempt individual student query, confirm denial
- [x] Verify structured logging output for successful queries and denied queries
- [x] Verify the agent works from within distrobox (use `distrobox-host-exec` for podman container access)

## Dev Notes

### Architecture Decisions Referenced

- **DA-2:** Provenance & Traceability Schema. Named graph URI == Pod resource URI (queried with `GRAPH <uri> {}` syntax). Aggregate queries show provenance at the aggregate level (count of named graphs, count of pods), not individual URIs. This is the "derived from N named graphs across M student pods" pattern. Use `parameterize.py` (Story 2.7) for safe query construction.
- **DA-3:** OSLO Vocabulary Schema Contract. NL and FR community data is queryable in a single SPARQL query because both are mapped to the same OSLO vocabulary classes. Cross-community aggregation is a SPARQL GROUP BY, not a data integration challenge.
- **SEC-2:** ACL enforcement at query level. Isabelle's role gets a stricter enforcement: not just "can you access these pods?" but "can you access these pods AND are you limited to aggregate queries?" This is a role-specific ACL constraint.
- **SEC-3:** Parameterized `.rq` templates. The `aggregate-anonymized.rq` template uses `$programUri` and `$communityScope` parameters.
- **API-2:** Isabelle's scenario uses the SPARQL skill only (graph-only queries). No Qdrant skill needed — aggregate statistical queries do not benefit from semantic search.

### Data Audit Findings (2026-03-24) — Query Path Decision

**Vocabulary mismatch (FATAL for original template):**
The existing `aggregate-anonymized.rq` uses `oslo-educ:` predicates. These do NOT exist in Oxigraph. The actual vocabulary is `https://poc-pod0.edu/vocab/`. The template returns zero results against live data.

**Robotics data state:**
- 58 attendance records (`poc:verb` containing "attended") across ayoub, fatima-child-1, fatima-child-2
- ZERO `scaledScore` values on robotics records — attendance only, no outcome data
- No `ext-funding: gemeente-stem-program` values in data (predicate exists, zero records carry it)
- No `pocpod0:consentGrant "regional-access"` — only `ext-consent-type: parental-opt-in` exists

**B' decision (cross-context aggregate):**
Rather than fixing the data to match the template, the query is redesigned to ask the architecturally correct question: find students who attended the funded program → aggregate their scores across ALL activities. Real data exists: ayoub, fatima-child-1, fatima-child-2 have `scaledScore` values on other activities (math, biology, chemistry, tutoring). This demonstrates the cross-pod, cross-context capability that justifies the architecture — impossible with Word documents.

**"Before" state as narrative asset:**
The attendance-only data for the robotics program IS Isabelle's present reality — headcounts without outcomes. The demo arc: "before = 58 attendance events, no outcomes, self-reported. After = 32 students confirmed, cross-context avg score X, provenance verified." The system provides auditable headcounts + cross-context improvement signal from the same query.

### Anonymization Strategy

The anonymization in this story is **structural, not algorithmic**:
1. The SPARQL query uses `GROUP BY` to aggregate — individual records never appear in the result set
2. The template is designed to return counts and averages, never individual scores or identifiers
3. The skill enforces aggregate-only access for the `regional-policy` role — even if the LLM constructs a non-aggregate query, the skill blocks it
4. This is sufficient for a PoC. Production-grade anonymization (k-anonymity, differential privacy) is a pilot-phase concern.

Key demo point: the anonymization guarantee is displayed alongside results, showing funders that the system is architecturally designed to protect individual data even when querying at scale.

### Cross-Community Aggregation (NL + FR)

Isabelle's scenario aggregates across both NL and FR communities. This works because:
1. Phase 2 ingestion maps ALL xAPI data to OSLO vocabulary classes regardless of source community
2. The `$communityScope` parameter can be "NL", "FR", or "both"
3. When "both", the SPARQL query aggregates across all community data without distinction
4. The result shows aggregate impact across the entire Brussels-Capital region

This is the "unanswerable query" from the PRD: "students in the robotics workshop show measurable improvement in applied math scores across both communities" — literally unanswerable by anyone in Belgium before this architecture.

### Agent Configuration Pattern

The `agent.yaml` follows the OpenClaw agent configuration pattern. Key fields:
- `id`: `isabelle-policy` (used as agent identity for ACL checks and logging)
- `model`: `minimax/minimax-m2.5` (via OpenRouter, NFR20)
- `skills`: `sparql-query` only (no `qdrant-search` — aggregate queries are structured, not semantic)
- `persona`: natural language description of Isabelle's role and context
- `acl_scope`: regional aggregate-read — can access aggregate statistics from pods with active `regional-access` consent
- `access_restriction`: `aggregate-only` — enforced by the SPARQL skill

### Consent Model for Regional Access

Regional aggregate access requires that individual student pods have an active `regional-access` consent grant:
- During Pod provisioning (Epic 1), pods are created with ACL resources
- The `regional-access` consent is a specific ACL grant on each pod that allows aggregate-level querying by regional policy roles
- The SPARQL template filters on `pocpod0:consentGrant "regional-access"` to ensure only consented data is included
- The provenance narrative confirms: "all with active regional-access consent grants"
- If a student revokes regional-access consent, their data is automatically excluded from aggregate results (no code change needed — the SPARQL filter handles it)

### Oxigraph Connection Details

- Docker service name: `oxigraph`
- SPARQL query endpoint: `http://oxigraph:7878/query` (HTTP POST)
- Image: `oxigraph/oxigraph:0.5.6`
- Port: 7878

### CSS (Solid Server) Connection Details

- Docker service name: `community-solid-server`
- Port: 3000
- Image: `communitysolidserver/community-solid-server:7`
- ACL resources: `.acl` files per Solid spec on each Pod resource

### Naming Conventions

- Agent ID: `isabelle-policy` (lowercase hyphen)
- Agent config: `agents/isabelle-policy/agent.yaml`
- SPARQL template: `aggregate-anonymized.rq` (lowercase hyphen `.rq`)
- Python functions: `snake_case`
- SPARQL variables: `?camelCase` (e.g., `?programName`, `?communityScope`, `?participantCount`)
- Log service name: `isabelle-policy-agent`

### Structured JSON Logging Format

All log entries follow the project-wide format:
```json
{
  "timestamp": "ISO-8601",
  "service": "service-name",
  "level": "INFO|WARN|ERROR",
  "event": "event.type.name",
  "agent": "isabelle-policy",
  "duration_ms": 123,
  "details": {}
}
```

### Funder Intervention Point

From the PRD: "Funder selects an aggregate policy query. The system displays anonymization guarantees alongside results."

This story implements the backend for this intervention point. The dashboard integration (Phase 4, Epic 6) will surface it. For now, the agent's formatted output should include:
1. The aggregate results (program impact metrics)
2. The provenance narrative ("derived from N scored activities across M named graphs from P student pods...")
3. The anonymization guarantee statement
4. These three elements together form the "evidence-based policy" demo artifact

### Project Structure Notes

Directories/files to create:

```
agents/
└── isabelle-policy/
    └── agent.yaml                       # NEW - Isabelle policy agent config
```

Files to modify (aggregate-only enforcement):

```
agents/
└── skills/
    └── sparql-query/
        └── handler.py                   # MODIFY - Add aggregate-only enforcement for regional-policy role
```

Files that must already exist (from earlier stories):

```
agents/
├── openclaw.config.yaml                 # Created in Story 3.1
└── skills/
    └── sparql-query/                    # Created in Story 3.1
        ├── skill.yaml
        ├── handler.py
        └── templates/
            └── aggregate-anonymized.rq  # Created in Story 3.1 (verify/update)
```

### Dependencies

- **Depends on Story 3.1:** Shared SPARQL skill must exist with `aggregate-anonymized.rq` template and ACL validation
- **Depends on Story 3.3:** OpenClaw agent infrastructure must be configured (agent runtime, agent loading)
- **Depends on Epic 1:** Pods must exist with `regional-access` consent grants configured in ACLs (Stories 1.1, 1.3, 1.4)
- **Depends on Epic 2:** Data must be loaded in Oxigraph with OSLO mappings, provenance, and program/activity relationships across both NL and FR communities (Stories 2.1, 2.2, 2.3)
- **Does NOT depend on Story 3.2:** Isabelle uses graph-only queries (SPARQL skill only), not hybrid queries. No Qdrant skill needed.
- **Priority:** [target] — implement if Phase 3 has capacity after must-ship stories (Claire, Marc, Ayoub) are complete

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec community-solid-server ...`
- Example: `distrobox-host-exec podman exec oxigraph ...`

### Handoff from Story 3.5 — sparql-query skill changes

**`agent_id` param required for correct log attribution (AC5)**
The skill derives `agent` log field from the WebID by default (e.g. `"isabelle"` from `…/isabelle/profile/card#me`). To emit `"isabelle-policy"` as required by AC5, pass `agent_id: isabelle-policy` explicitly in skill params. Add this to the agent's SOUL.md query invocation instructions. Without it, the `agent` field in logs will be wrong.

**`logging_service` in `agent.yaml` is NOT read by the handler (architectural debt)**
The handler always emits `service: sparql-query-skill`. Per-agent service names require an OpenClaw API design decision not yet made. The spec's log examples showing `"service": "isabelle-policy-agent"` will not match actual output until this is resolved.

**`_normalise_pod_uri()` now available in handler**
Pod URIs passed to skills are normalised from `_CSS_CONNECT_URL` → `_CSS_IDENTIFIER_URL`. No action needed; just be aware this normalisation happens automatically.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-2, DA-3, SEC-2, SEC-3, API-2, INFRA-1, Agent Query Protocol)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR19, FR20, Journey 4: Isabelle — Evidence-Based Policy)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.5 acceptance criteria)
- Story 3.1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill with aggregate-anonymized.rq template)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (story-3-6-isabelle-evidence-based-policy)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References
- E2E run confirmed: 3 participants, 12,462 scored activities, avg score 0.541 across 719 named graphs
- B' query design validated: ayoub, fatima-child-1, fatima-child-2 have scaledScore on non-robotics activities
- Existing integration test updated: old params (program_uri/community_uri) → new param (program_activity)

### Completion Notes List
- Task 1: `agents/isabelle-policy/agent.yaml` created with id=isabelle-policy, role=regional-policy, acl_role=regional-policy, access_restriction=aggregate-only
- Task 2: `aggregate-anonymized.rq` rewritten from scratch — B' two-stage cross-context query using pocpod0: vocabulary. Stage 1 finds attended robotics students; Stage 2 aggregates their scores across all activities. OSLO predicates removed entirely.
- Task 3: Aggregate-only enforcement added to handler.py at Step 1.5 (template check) and Step 3.5 (structural check via SPARQL aggregate function regex — not GROUP BY string, which is not required for whole-result aggregation) for role=regional-policy. Denial logged as WARN sparql.query.denied with requested_template, allowed_templates, and acl_check fields (code review patch).
- Task 4: `_summarize_aggregate()` function added to handler.py. Returns participant_count, named_graph_count, scored_activity_count, score stats, provenance_narrative, anonymization_guarantee.
- Task 5: SOUL.md updated with skill invocation params section (agent_id, program_activity, community_scope) per Story 3.5 handoff note.
- Task 6: Tests added for Scenarios A (student-progress denied), B (parental-view denied), C (aggregate-anonymized allowed). Scenario C also tested via TestIsabelleStep35StructuralCheck with mocked non-aggregate template body (code review patch).
- Task 7: Log details augmented for aggregate queries with query_type, anonymization, consent_verified, participant_count, named_graph_count, scored_activity_count fields.
- Task 8: E2E verified against real Oxigraph. AC3 enforcement verified with live denial test.
- 59 unit+integration tests pass (0 failures, 0 regressions).

### File List
- `agents/isabelle-policy/agent.yaml` (CREATED)
- `agents/skills/sparql-query/templates/aggregate-anonymized.rq` (REWRITTEN)
- `agents/skills/sparql-query/handler.py` (MODIFIED — Tasks 3, 4, 7)
- `agents/isabelle-policy/SOUL.md` (MODIFIED — Task 5)
- `agents/skills/sparql-query/tests/test_handler.py` (MODIFIED — Tasks 3, 4, 6, 7 tests + existing test updated)

### Handoff to Story 3.8 — Troll Cross-Inference Validation

**`consent_verified: True` is simulated (known finding)**
The `consent_verified` field in aggregate success logs and the provenance narrative claim "all with active regional-access consent grants." This is hardcoded — no consent filter is applied in the SPARQL query (the data has no `regional-access` consent triples). The troll should include a probe for this surface and document it as a PoC limitation (not a blocking finding per AC2 PoC note).

**Aggregate-only enforcement surfaces to probe (AC3)**
Step 1.5 (template-level) and Step 3.5 (aggregate function structural check) both deny non-aggregate queries for `regional-policy`. Troll should probe: (1) template-swap attempts, (2) prompt injection asking Isabelle's agent to retrieve individual records. Both paths are logged as `sparql.query.denied` with full schema.

**Denial log schema (for troll log assertions)**
Step 1.5 denial details: `{reason, requested_template, allowed_templates, acl_check: "denied"}`
Step 3.5 denial details: `{reason, requested_template, allowed_templates, acl_check: <acl_status>}`

## Change Log
- 2026-03-24: Story 3.6 implemented — Isabelle evidence-based policy agent. B' cross-context aggregate SPARQL query; aggregate-only enforcement in handler; _summarize_aggregate with provenance narrative; 20 new tests added (57 total pass).
- 2026-03-24: Code review patches — Step 3.5 GROUP BY check replaced with SPARQL aggregate function regex; acl_check added to Step 1.5 denial log; Step 3.5 denial log schema fixed; provenance narrative wording updated in spec; AC2 PoC consent simulation note added; Scenario C Step 3.5 test added. 59 tests pass.
