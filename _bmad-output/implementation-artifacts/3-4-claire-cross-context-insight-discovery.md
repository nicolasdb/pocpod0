# Story 3.4: [must-ship] Claire — Cross-Context Insight Discovery

Status: done

## Story

As **Claire** (secondary school teacher, Brussels),
I want to query cross-institutional student progress and see both graph-only and hybrid results side by side with provenance,
so that I discover the full picture of a struggling student — including learning contexts invisible to my school platform.

## Acceptance Criteria

**AC1: Graph-only query returns structured facts scoped to Claire's ACL**
Given Claire's agent is configured (`agents/claire-teacher/agent.yaml`) with tutor ACL role
When Claire queries "Which students are struggling with quadratic equations across all learning contexts?"
Then the SPARQL skill executes `cross-context-query.rq` scoped to Claire's authorized pods (FR14, FR17)
And returns structured facts: failed tests, attendance records, self-study module counts
And results include only data from pods Claire's tutor role can access
And each result includes provenance via named graph URI (graph URI == Pod resource URI, queried with `GRAPH <uri> {}` syntax)

**AC2: Hybrid query returns semantically enriched insights**
Given the same query as AC1
When executed as a hybrid query (SPARQL skill + Qdrant skill)
Then the SPARQL skill returns the same structured facts as AC1
And the Qdrant skill returns semantically similar content from vector search (e.g., "tutoring notes show student grasping concepts through geometric visualization")
And Claire's agent merges both result sets, synthesizing a narrative that reveals patterns invisible in school data alone (FR15)

**AC3: Side-by-side comparison is the "aha moment"**
Given both graph-only and hybrid results are available
When displayed to Claire (FR16)
Then graph-only results are presented as structured facts (flat, factual)
And hybrid results are presented as enriched narrative (contextual, insightful)
And the comparison is visually distinct — the hybrid result visibly adds value over graph-only
And the output format clearly labels which result came from which query type

**AC4: Provenance is navigable from result to source**
Given any query result (graph-only or hybrid)
When Claire inspects provenance (FR20)
Then each result shows which Oxigraph triples contributed to it
And each triple links back to its source Pod resource URI (named graph URI == Pod resource URI)
And the provenance chain is navigable: Qdrant Point -> `triple_uris` -> Oxigraph named graph -> Pod resource URI
And Qdrant results additionally show `triple_uris` linking back to the graph layer

**AC5: ACL enforcement prevents cross-role leakage**
Given Claire's agent has tutor ACL role
When Claire queries for students outside her ACL scope (e.g., students in pods she is not authorized for)
Then only data from authorized pods is returned (NFR7)
And no data from unauthorized pods appears in either graph-only or hybrid results
And the access denial is logged in structured JSON format

## Tasks / Subtasks

### Task 1: Prepare Claire's demonstration query scenario (AC1, AC2)
- [ ] Define the demonstration query: "Which students are struggling with quadratic equations across all learning contexts?"
- [ ] Identify the specific student pods and data Claire's query should hit:
  - Ayoub's pod: school assessment results (failed tests on quadratic equations)
  - Ayoub's pod: tutoring session records (attendance, tutor notes)
  - Ayoub's pod: self-study activity (Khan Academy modules on algebra)
  - Claire's other students' pods: similar cross-context data
- [ ] Verify the Epic 2 synthetic data includes sufficient cross-context data for this query:
  - School assessment failures (in Oxigraph as OSLO-mapped RDF)
  - Tutoring session notes with semantic content (in Qdrant as embeddings)
  - Self-study completion records (in Oxigraph)
- [ ] If synthetic data is insufficient for the demo, document what additional data seeding is needed

### Task 2: Implement graph-only query execution (AC1)
- [ ] Configure Claire's agent to execute a graph-only query flow:
  1. Agent receives user query (natural language)
  2. Agent determines this is a graph-only request (first pass)
  3. Agent calls `sparql-query` skill with:
     - `query_type`: `cross-context-query` (selects `cross-context-query.rq` template)
     - `parameters`: `{ subject: "quadratic equations", authorizedPodUris: [list from Claire's ACL config] }`
     - `agent_role`: `claire-teacher`
  4. SPARQL skill validates Claire's ACL, parameterizes template, executes against Oxigraph
  5. Agent receives structured results with provenance
- [ ] Verify results include:
  - Student identifiers (within authorized scope)
  - Assessment results (failed/passed, scores)
  - Tutoring attendance counts
  - Self-study module completion counts
  - Named graph URIs (== Pod resource URIs) for each result row
- [ ] Verify response time < 500ms (NFR1)

### Task 3: Implement hybrid query execution (AC2)
- [ ] Configure Claire's agent to execute a hybrid query flow:
  1. Agent calls `sparql-query` skill (same as Task 2 — graph-only path)
  2. Agent calls `qdrant-search` skill with:
     - Semantic query text: "students struggling with quadratic equations learning approaches"
     - Optional filters: limit to relevant collection, score threshold for relevance
  3. Agent receives both result sets
  4. Agent merges results:
     - Correlate via `pod_resource_uri` (common key between both skills)
     - SPARQL provides facts: "Ayoub failed tests X, Y, Z. Attendance: 8/10."
     - Qdrant provides context: "Tutoring notes show Ayoub is grasping quadratic equations through geometric visualization — the school assessment does not capture his approach."
     - Agent synthesizes: combines facts with semantic context into enriched narrative
- [ ] Verify the Qdrant results actually add insight beyond the SPARQL results
- [ ] Verify combined response time < 2s (NFR2)
- [ ] If both skills are called in parallel, combined latency = max(SPARQL, Qdrant), not sum

### Task 4: Implement side-by-side comparison output (AC3)
- [ ] Design the output format for side-by-side comparison:
  ```
  === GRAPH-ONLY RESULTS ===
  Query: "Which students are struggling with quadratic equations across all learning contexts?"
  Source: SPARQL skill (cross-context-query.rq)

  Student: Ayoub
  - School assessments: Failed Test 3 (score: 42%), Failed Test 7 (score: 38%)
  - Tutoring attendance: 8/10 sessions attended
  - Self-study: 3 Khan Academy algebra modules completed
  Provenance: [pod-resource-uri-1, pod-resource-uri-2, ...]

  === HYBRID RESULTS (SPARQL + Semantic) ===
  Query: Same query, enriched with vector semantic search
  Sources: SPARQL skill + Qdrant skill

  Student: Ayoub
  - School assessments: Failed Test 3 (42%), Failed Test 7 (38%)
  - Tutoring attendance: 8/10 sessions
  - Self-study: 3 Khan Academy modules
  - [SEMANTIC ENRICHMENT] Tutoring notes show Ayoub is grasping quadratic
    equations through geometric visualization. His tutor reports he understands
    the concepts when presented spatially but struggles with the algebraic
    notation used in school assessments. The school assessment format does not
    capture his approach.
  Provenance: [pod-resource-uri-1, pod-resource-uri-2, qdrant-point-id -> triple-uris -> pod-uris]

  === COMPARISON ===
  Graph-only: Factual data — shows failure pattern but not the reason
  Hybrid adds: Semantic context — reveals Ayoub IS learning, just differently
  ```
- [ ] The comparison must be the emotional core of the demo — this is the "aha moment"
- [ ] Labels must clearly indicate which results came from which query type
- [ ] The hybrid enrichment should be visually distinct (e.g., labeled `[SEMANTIC ENRICHMENT]`)

### Task 5: Implement provenance display (AC4)
- [ ] For graph-only results, show provenance chain:
  - Result row -> Oxigraph named graph URI -> Pod resource path (named graph URI == Pod resource URI)
  - Example: "This result from named graph `http://community-solid-server:3000/ayoub/learning/assessment-3.ttl`"
- [ ] For hybrid results, show extended provenance chain:
  - SPARQL portion: same as graph-only
  - Qdrant portion: result -> `triple_uris` -> `pod_resource_uri`
  - Example: "Semantic insight derived from embedding of triple `http://oxigraph:7878/triple/xyz`, sourced from `http://community-solid-server:3000/ayoub/learning/tutoring-session-8.ttl`"
- [ ] Provenance must be navigable: a reader can follow the chain from display result back to the original Pod resource
- [ ] Include provenance summary: "This query accessed N triples from M pod resources"

### Task 6: Implement ACL enforcement verification (AC5)
- [ ] Test Claire's agent querying for a student pod she is NOT authorized for:
  - Attempt to query Fatima's children's pods (Claire has no parental access)
  - Attempt to query Isabelle's regional aggregate scope
- [ ] Verify the SPARQL skill denies the query and returns access-denied response
- [ ] Verify no data from unauthorized pods leaks into results
- [ ] Verify the Qdrant skill results are also scoped — if Qdrant returns results referencing unauthorized pod URIs, the agent must filter them out
- [ ] Verify denial events are logged:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "sparql-query-skill",
    "level": "WARN",
    "event": "sparql.query.denied",
    "agent": "claire-teacher",
    "duration_ms": 5,
    "details": {
      "reason": "ACL check failed",
      "requested_pods": ["http://community-solid-server:3000/fatima-child-1/"],
      "agent_role": "tutor"
    }
  }
  ```

### Task 7: Implement Claire's agent system prompt and query orchestration (AC1, AC2, AC3)
- [ ] Finalize Claire's agent system prompt in `agents/claire-teacher/agent.yaml` (created in Story 3-3):
  - Instruct the agent to always execute both graph-only and hybrid for demonstration purposes
  - Instruct the agent to present results side-by-side
  - Instruct the agent to always include provenance
  - Instruct the agent to highlight what the hybrid adds over graph-only
- [ ] Implement the query orchestration flow in the agent's behavior:
  1. Parse user query intent
  2. Execute graph-only pass (SPARQL skill)
  3. Execute hybrid pass (SPARQL + Qdrant skills)
  4. Format side-by-side comparison
  5. Include provenance for both
  6. Present with narrative voice appropriate to Claire's persona

### Task 8: End-to-end integration test (all ACs)
- [ ] Run the complete Claire journey end-to-end:
  1. Start OpenClaw runtime
  2. Spawn Claire's agent
  3. Submit the demonstration query
  4. Verify graph-only results are correct and scoped to ACL
  5. Verify hybrid results include semantic enrichment
  6. Verify side-by-side output format
  7. Verify provenance is present and navigable
  8. Verify no cross-role data leakage
- [ ] Verify all structured JSON logs are emitted for the journey
- [ ] Verify performance: graph-only < 500ms, hybrid < 2s
- [ ] Test from within distrobox using `distrobox-host-exec` for podman container access
- [ ] Document any issues or findings in completion notes

## Completion Notes (2026-03-22)

### What was built
- `agents/claire-teacher/SOUL.md` — full query orchestration: graph-only pass, hybrid pass, three-state output (full/partial/honest gap), provenance display, ACL boundaries, WebID
- `agents/skills/sparql-query/templates/cross-context-query.rq` — rewritten: `pocpod0:` vocab, `strstarts` prefix filter, all learning statement fields
- `agents/skills/sparql-query/handler.py` — `_summarize_bindings()`: aggregates 700+ raw rows → compact summary (verb counts, content breakdown, score stats, failures, mastery events); provenance → pod roots only
- `agents/skills/qdrant-search/handler.py` — `content_summary` truncation bumped to 500 chars
- `pipeline/src/pocpod0_pipeline/embed.py` — `content_text` added to Qdrant payload so semantic match text is returned to agent
- `infra/openclaw/Dockerfile` — new: extends OpenClaw image with `python3-requests` + `python3-httpx`
- `docker-compose.yml` — openclaw-gateway: `image:` → `build:`, CSS three-var env vars wired
- `.env` — added `CSS_IDENTIFIER_URL`, `CSS_CONNECT_URL`, `CSS_IDENTIFIER_HOST`, `OXIGRAPH_URL`, `QDRANT_URL`
- `.dockerignore` — new: build context 93MB → ~2MB
- `pipeline/tests/integration/test_claire_cross_context.py` — e2e test scaffold for all ACs

### Bugs fixed during launch
1. **OpenClaw missing Python deps** — Dockerfile with apt-get as root at image build time
2. **CSS env vars missing from container** — `.env` additions via `env_file:`
3. **SPARQL template wrong vocab + wrong graph selector** — `oslo-educ:` → `pocpod0:`, `GRAPH $pod_uri` → `strstarts` prefix filter; `str($pod_uri)` in FILTER context (parameterize.py wraps URIs in `<>`)
4. **Claire WebID mismatch** — SOUL.md had `claire-teacher`; ACLs and pod-config.yaml use `claire`
5. **529KB SPARQL result bloat** — summary aggregation in handler (529KB → ~1KB)
6. **Qdrant `content_summary` empty** — `content_text` now stored in payload; embed re-run required after schema change

### Verified working
- ACL: claire→ayoub ✓, claire→student-1 ✓, claire→student-2 ✓, claire→fatima-child-1 → 403 ✓
- SPARQL summary for Alex: `82 failures + 12 mastery_events on gemeente-tutoring` — aha moment in data
- Qdrant: 5617 points; top semantic hit "students struggling fractions" → claire-student-1 assessment (score 0.79) ✓
- Claire answered in French with three-state output (GRAPH-ONLY / HYBRID / HONEST GAP for Ayoub) ✓

### Post-review fixes applied (2026-03-22)
- **Code review patches** applied (12 patches): mastery_events float guard, timestamp None guard, pod_uri trailing-slash normalization, embed.py chunk.get guard, pod_uri_param multi-pod fix, SOUL.md hostname consistency, test vocab fix (oslo-educ→pocpod0), NFR1/NFR2 assertions, ACL test assertion, Qdrant health path, .dockerignore
- **BCP 47 lang tag bug** fixed in `oslo_mapper.py` — `lang.replace("-", "")` removed (was corrupting all RDF labels: `"en-US"` → `"enUS"`)
- **`generate_troll_load.py` success/score fix** — `rng.choice([True, False])` → `scaled >= 0.5` (was producing 115/239 random success flags for claire-student-1)
- **Full pipeline regen** — `pipeline/run_pipeline.py --wipe` added as orchestrator with tqdm progress in embed step; pipeline ran clean: 5917 resources, 124,611 triples, 5916 Qdrant points
- **`content_text` payload** now populated in Qdrant (embed re-run completed)
- **IG-1 resolved** — pod-level provenance accepted for demo (AC1/AC4 amended)
- **BS-1 resolved** — `$agent_role` SPARQL filter removed; role scoping via CSS ACL checks

### Known gap → deferred to Story 3.7
**CSS pod data accumulation between pipeline runs**: `run_pipeline.py --wipe` clears Oxigraph and Qdrant, but CSS pods accumulate old resources (each statement gets a deterministic UUID path via `ingest.py`; DELETE on non-empty LDP containers returns 409). On re-run, `load_graph.py` fetches both old and new troll data from CSS pods → Oxigraph contains stale records. Confirmed: 119 ADL-verb success/score mismatches remain in Oxigraph from pre-fix troll data.

Story 3.7 pre-requisites:
1. **Fix pipeline wipe** to clear CSS pod `*/learning/` containers (leaf-first LDP DELETE sequence) OR use SPARQL UPDATE `DELETE/INSERT` to correct `pocpod0:success` from `pocpod0:scaledScore` at Oxigraph level
2. **Fix ingest stage** in `run_pipeline.py` to point at `data/synthetic/` (parent dir) so both troll-load and scenario data are ingested on regen
3. **Verify** 0 mismatches after fix: `SELECT ?scaledScore ?success (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?a pocpod0:result ?r . ?r pocpod0:scaledScore ?scaledScore . ?r pocpod0:success ?success . } } GROUP BY ?scaledScore ?success`

Performance baseline: `content_breakdown` has duplicate subject keys (cosmetic, not blocking).

## Dev Notes

### Pre-Implementation Decisions (2026-03-22)

**Decision 1 — Ayoub's missing tutor data is intentional, not a seed gap.**
Ayoub has no tutoring records in his pod. The reason is unknown — tutor access not requested, data not yet shared, provider not connected, or simply no tutoring context exists. The system does NOT assert a cause. It surfaces the gap and proposes the most probable next action given available context. Do NOT seed tutoring data for Ayoub. Preserve the negative space.

**Decision 2 — Three-state output required (not two).**
The side-by-side comparison (Task 4) must support three distinct output states:
1. **Full hybrid insight** (Alex / `claire-student-1`): school failure + tutoring mastery + semantic enrichment → "struggling differently" narrative
2. **Partial / structured only** (Jordan / `claire-student-2`): average school data + sparse gemeente tutoring → structured facts, limited semantic depth
3. **Negative space with call-to-action** (Ayoub): school records present, tutoring context absent → explicit gap acknowledgment + "Request Ayoub's tutor to share access" prompt

This third state is the trust argument: the system knows what it doesn't know and tells you.

**Decision 3 — SPARQL is broad (Design A confirmed), Qdrant adds context richness.**
The `cross-context-query.rq` template returns all authorized facts for the agent role across a pod — no topic filter. Topic-specificity lives in the Qdrant semantic query. The agent merges both. This is intentional: SPARQL answers "what happened?", Qdrant answers "what does it mean?".
The current template only takes `$agent_role` and `$pod_uri`. This is correct for Design A. Do not add a `$subject` topic filter to the SPARQL template.

**Decision 4 — Multilingual is a Qdrant value, not a translation table.**
The semantic layer collapses multilingual vocabulary gaps natively (NL `breuken` ≈ FR `fractions` ≈ EN `fractions` via embedding space). Do NOT implement keyword translation. The agent's job is synthesis and presentation in Claire's language. Provenance output should note when insights were synthesized from cross-language sources (e.g., "synthesized from a French tutoring note and a Flemish school assessment record").

**Decision 5 — Demo student mapping.**
- **Alex** (`claire-student-1`): the "aha moment" student — seeded with school failure + tutoring mastery contrast
- **Jordan** (`claire-student-2`): the control — average, sparse tutoring
- **Ayoub**: the "honest gap" student — school + robotics + Khan Academy, no tutor access → call-to-action
- **Sam** (`fatima-child-1`, NL school): ACL boundary test — must be denied (Fatima's child, not Claire's student)
- **Léa** (`fatima-child-2`, FR school): ACL boundary test — must be denied (Fatima's child, not Claire's student)

**Decision 6 — Negative space output format.**
When SPARQL returns data but Qdrant returns zero semantic context for a student:
```
=== HONEST GAP ===
Student: Ayoub
School data: [structured facts from SPARQL]
Tutoring context: NOT AVAILABLE
→ No tutoring context found in Ayoub's authorized data.
→ Possible reasons: tutor access not yet requested, provider not connected, or no tutoring context exists.
→ Suggested next action: [Request Ayoub's tutoring context] — ask Ayoub or his guardian to share tutor access.
```
The agent proposes the most probable next action; it does not assert a cause for the gap.

---

### This Is the Emotional Core of the Demo

Claire's journey is the "aha moment" for funders. The side-by-side comparison of graph-only vs hybrid results must be visibly compelling. The graph-only result shows "student failed tests" — useful but flat. The hybrid result reveals "student IS learning, just differently" — the insight that justifies the entire architecture.

From the PRD:
> Emotional resonance moment: Claire's struggling-student scenario — graph-only returns "failed tests X, Y, Z"; hybrid returns "struggling at school but tutoring notes show they're grasping it differently"

This is not just a technical query — it is a demonstration that the architecture enables insights impossible with any single data silo.

### Architecture Decisions Referenced

- **FR14:** Role agent executes SPARQL queries scoped to ACL permissions
- **FR15:** Role agent executes hybrid queries (SPARQL + vector) for enriched results
- **FR16:** Graph-only vs hybrid displayed side by side for comparison
- **FR17:** Tutor agent queries cross-institutional student progress across authorized contexts
- **FR20:** Provenance surfaced for query results (triples, Pod resources)
- **NFR1:** SPARQL queries < 500ms
- **NFR2:** Hybrid queries < 2s
- **NFR7:** No cross-role data leakage
- **NFR9:** Query logging with timestamp, agent, latency, result count
- **SEC-2:** ACL enforcement at query level via SPARQL skill
- **API-2:** Two shared skills, agents compose hybrid by calling both
- **DA-2:** Provenance schema — named graph URI == Pod resource URI (queried with `GRAPH <uri> {}` syntax), `triple_uris` + `pod_resource_uri` on Qdrant points. Use `parameterize.py` (Story 2.7) for safe query construction.

### Agent Query Protocol (from Architecture)

1. Agent determines query type: graph-only, semantic, or hybrid
2. **Graph path:** Agent calls SPARQL skill -> skill validates ACL -> selects `.rq` template -> parameterizes via `parameterize.py` (Story 2.7) -> executes against Oxigraph -> returns results with named graph provenance (graph URI == Pod resource URI)
3. **Semantic path:** Agent calls Qdrant skill -> skill generates query embedding -> similarity search against Qdrant -> returns results with `triple_uris` and `pod_resource_uri` traceability
4. **Hybrid path:** Agent calls BOTH skills (can be parallel), receives two result sets, merges them itself based on persona context
5. **Agent formats results** for its persona's narrative

Key design point: **the agent does the merge, not the skills**. Each skill has a single responsibility. Claire's agent has the context to judge relevance and combine insights.

### Result Correlation Between Skills

Both skills return `pod_resource_uri` as a common identifier:
- SPARQL skill: `{ results: [...], provenance: [{ pod_resource_uri: "..." }] }`
- Qdrant skill: `{ results: [{ pod_resource_uri: "...", triple_uris: [...] }] }`

Claire's agent correlates by matching on `pod_resource_uri`. Example:
- SPARQL: "Ayoub failed test X" (from `ayoub/learning/assessment-3.ttl`)
- Qdrant: "tutoring notes show geometric visualization approach" (from `ayoub/learning/tutoring-session-8.ttl`)
- Both reference Ayoub's pod -> agent merges into unified narrative

### Synthetic Data Requirements

This journey requires the following data to exist from Epic 2:

**In Oxigraph (OSLO-mapped RDF with provenance):**
- Ayoub's school assessments on quadratic equations (with failure results)
- Ayoub's tutoring session attendance records
- Ayoub's self-study activity (Khan Academy module completions)
- Similar data for at least 1-2 other students in Claire's authorized scope

**In Qdrant (embeddings with payload metadata):**
- Embedded tutoring session notes mentioning learning approaches (geometric visualization, spatial reasoning)
- Embedded self-study activity descriptions
- Each embedding has `triple_uris` and `pod_resource_uri` in payload

**In CSS Pods:**
- Ayoub's pod with school, tutoring, and self-study resources as Turtle files
- Claire's authorized student pods with similar cross-context data
- ACLs granting Claire's tutor role read access to these pods

If this data does not exist or is insufficient, the dev agent must seed additional synthetic data. Check Epic 2 story implementations for what was loaded.

### SPARQL Templates Used

From Story 3-1, the following templates are relevant:

- `agents/skills/sparql-query/templates/cross-context-query.rq` — primary template for Claire's query
  - Parameters: `$subject` (e.g., "quadratic equations"), `$authorizedPodUris` (list of pod URIs from Claire's ACL)
  - Returns: cross-institutional data with provenance

- `agents/skills/sparql-query/templates/student-progress.rq` — secondary template for individual student detail
  - Parameters: `$studentPodUri`, `$learningContext` (optional)
  - Returns: student progress with provenance

### Performance Targets

| Query Type | Target | Measurement |
|-----------|--------|-------------|
| Graph-only (SPARQL) | < 500ms | From agent skill call to result return |
| Hybrid (SPARQL + Qdrant) | < 2s | From agent initiating both calls to merged result |
| Provenance resolution | included in query time | Provenance URIs returned as part of query results |

### Qdrant Semantic Search Details

- The Qdrant skill generates an embedding of Claire's query text using `qwen/qwen3-embedding-8b` via OpenRouter
- Similarity search finds content semantically related to "students struggling with quadratic equations"
- Top results should include tutoring notes, learning approach descriptions, and contextual observations
- Each result includes `triple_uris` and `pod_resource_uri` for traceability back to the graph and pod layers

### Service Endpoints

| Service | Hostname | Port | Used By |
|---------|----------|------|---------|
| Oxigraph | `oxigraph` | 7878 | SPARQL skill (graph-only queries) |
| Qdrant | `qdrant` | 6333 | Qdrant skill (semantic search) |
| CSS | `community-solid-server` | 3000 | SPARQL skill (ACL check) |

### Project Structure Notes

Files that must already exist:

```
agents/
├── openclaw.config.yaml               # Story 3-1
├── skills/
│   ├── sparql-query/                   # Story 3-1
│   │   ├── skill.yaml
│   │   ├── handler.py
│   │   └── templates/
│   │       ├── cross-context-query.rq
│   │       ├── student-progress.rq
│   │       └── ...
│   └── qdrant-search/                  # Story 3-2
│       ├── skill.yaml
│       └── handler.py
└── claire-teacher/
    └── agent.yaml                      # Story 3-3
```

Files this story may modify:
- `agents/claire-teacher/agent.yaml` — refine system prompt and query orchestration for the demo scenario
- May need to add demo-specific query patterns or scripts

### Dependencies

- **Depends on Story 3-1:** SPARQL skill with templates and ACL enforcement
- **Depends on Story 3-2:** Qdrant skill for semantic search
- **Depends on Story 3-3:** Claire's agent config (agent.yaml) with persona and ACL role
- **Depends on Epic 1:** Pods with ACLs (for ACL enforcement to work)
- **Depends on Epic 2:** Synthetic data loaded in Oxigraph and Qdrant (for queries to return meaningful results)
- **Blocks Story 3-7:** Graph-only vs hybrid comparison (this story IS the comparison for Claire, but 3-7 may generalize it)

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman logs oxigraph` to check Oxigraph query logs
- Example: `distrobox-host-exec podman exec qdrant curl localhost:6333/collections` to check Qdrant state

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-2, SEC-2, API-2, Agent Query Protocol, Implementation Patterns)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR14, FR15, FR16, FR17, FR20, NFR1, NFR2, NFR7, NFR9, Journey 2: Claire)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.3 acceptance criteria)
- Story 3-1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill, templates, ACL enforcement)
- Story 3-2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` (Qdrant skill, hybrid query protocol, result correlation)
- Story 3-3: `_bmad-output/implementation-artifacts/3-3-openClaw-agent-infrastructure.md` (Claire's agent config, all agent configs)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (story-3-4-claire-cross-context-insight-discovery)

## Code Review Decisions (2026-03-22)

**IG-1 resolved: Pod-level provenance is acceptable for the demo.**
AC1/AC4 spec language referencing individual named-graph URIs is superseded by this decision.
Provenance returns pod root URIs (e.g. `http://community-solid-server:3000/ayoub/`) — sufficient for demo traceability. Individual TTL graph URIs are not surfaced to avoid 529KB token bloat.

**BS-1 resolved: `$agent_role` query filter removed — role scoping is at the CSS ACL layer.**
The SPARQL template no longer includes a `$agent_role` filter. Role enforcement happens via pod-level CSS ACL checks (HTTP 403) before any query executes. The template parameter has been removed from the template header and handler call sites.

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
