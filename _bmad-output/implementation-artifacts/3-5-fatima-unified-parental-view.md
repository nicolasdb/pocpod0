# Story 3.5: [journey] [target] Fatima — Unified Parental View

Status: ready-for-dev

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
- [ ] Create `agents/fatima-parent/agent.yaml` with:
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
- [ ] Verify the agent.yaml is loadable by the OpenClaw runtime

### Task 2: Create/verify parental-view SPARQL template (AC1, AC2)
- [ ] Create or verify `agents/skills/sparql-query/templates/parental-view.rq` with:
  - Parameters: `$childPodUris` (list of child Pod URIs), `$parentRole`
  - Query must return learning activities for ALL specified children across ALL learning contexts (school, tutoring, extracurricular)
  - Results must include:
    - Child identifier (distinguishable per child within results)
    - Activity type / learning context (school, tutoring, extracurricular)
    - Subject / topic
    - Result / assessment outcome
    - Provenance: `prov:wasDerivedFrom` URI for each result row
  - Query must handle both NL and FR school data seamlessly because it queries OSLO-mapped RDF (language-neutral structured data)
  - Example template structure:
    ```sparql
    PREFIX oslo-educ: <https://data.vlaanderen.be/ns/onderwijs#>
    PREFIX oslo-person: <https://data.vlaanderen.be/ns/persoon#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX pocpod0: <http://pocpod0.local/vocab#>

    SELECT ?child ?childName ?activity ?activityType ?subject ?result ?learningContext ?provenanceUri
    WHERE {
      VALUES ?childPod { $childPodUris }
      ?child pocpod0:podUri ?childPod .
      ?child oslo-person:volledigeNaam ?childName .
      ?activity oslo-educ:heeftDeelnemer ?child .
      ?activity a ?activityType .
      ?activity oslo-educ:heeftResultaat ?result .
      ?activity prov:wasDerivedFrom ?provenanceUri .
      OPTIONAL { ?activity oslo-educ:context ?learningContext }
      OPTIONAL { ?activity oslo-educ:onderwerp ?subject }
    }
    ORDER BY ?child ?activityType
    ```
  - The `VALUES` clause with `$childPodUris` scopes the query to ONLY Fatima's children — this is the parameterized ACL constraint

### Task 3: Implement Fatima's journey query flow (AC1, AC2, AC3)
- [ ] Configure the agent's system prompt to handle the unified parental view query:
  1. Agent receives natural language query from Fatima (e.g., "Show me both my children's progress across all their schools and activities")
  2. Agent determines query type: **hybrid** (SPARQL for structured cross-context data + Qdrant for semantic enrichment)
  3. **Graph path:** Agent calls SPARQL skill with:
     - `query_type`: `parental-view`
     - `parameters`: `{ childPodUris: ["<http://community-solid-server:3000/fatima-child-1/>", "<http://community-solid-server:3000/fatima-child-2/>"], parentRole: "fatima-parent" }`
     - `agent_role`: `fatima-parent`
  4. SPARQL skill validates ACL: does `fatima-parent` have parental read access to both child pods?
  5. If YES: execute `parental-view.rq` template against Oxigraph, return results with provenance
  6. If NO: return access-denied response (AC3)
  7. **Semantic path:** Agent calls Qdrant skill with semantic search query related to children's learning progress
  8. Agent merges both result sets, organizing by child and learning context
  9. Agent formats the unified view distinguishing each child's progress (AC2)

### Task 4: Implement unified view result formatting (AC2)
- [ ] Agent must format results so each child's progress is clearly distinguishable:
  - Group results by child (Child 1 — NL school, Child 2 — FR school)
  - Within each child, group by learning context (school, tutoring, extracurricular)
  - Show activity details: subject, assessment result, date/period
  - Show provenance for each result: which Pod resource contributed this data
- [ ] The NL and FR school data must appear seamlessly — no language barrier in the structured view because OSLO-mapped RDF uses standardized vocabulary classes (not free-text labels)
- [ ] If hybrid results add semantic insights (e.g., "child 1 shows improvement pattern in tutoring"), include them alongside structured results with clear labeling

### Task 5: Implement ACL boundary enforcement test (AC3)
- [ ] Configure a test scenario where Fatima's agent attempts to query a pod it does NOT have access to (e.g., another student's pod, Isabelle's policy data, Claire's class data)
- [ ] Verify the SPARQL skill denies the query and returns an access-denied response
- [ ] Verify ONLY data from her two children's pods is returned — no data leakage from other pods
- [ ] Log the denial event with structured JSON:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "sparql-query-skill",
    "level": "WARN",
    "event": "sparql.query.denied",
    "agent": "fatima-parent",
    "duration_ms": 5,
    "details": {
      "reason": "ACL check failed: fatima-parent does not have access to requested pod",
      "requested_resources": ["http://community-solid-server:3000/ayoub/"],
      "acl_check": "denied"
    }
  }
  ```

### Task 6: Implement structured logging for Fatima's queries (AC5)
- [ ] Every query Fatima's agent executes must produce a structured JSON log entry:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "fatima-parent-agent",
    "level": "INFO",
    "event": "agent.query.executed",
    "agent": "fatima-parent",
    "duration_ms": 850,
    "details": {
      "query_type": "hybrid",
      "sparql_template": "parental-view.rq",
      "children_queried": 2,
      "contexts_returned": ["school-nl", "school-fr", "tutoring", "extracurricular"],
      "result_count": 24,
      "provenance_uris_count": 24
    }
  }
  ```
- [ ] Log to stdout so docker-compose captures it (feeds mission control dashboard in Phase 4)

### Task 7: End-to-end journey verification (AC1, AC2, AC3, AC4, AC5)
- [ ] Run Fatima's agent with the unified parental view query end-to-end
- [ ] Verify both children's data is returned from both NL and FR school contexts
- [ ] Verify each child's progress is distinguishable in the formatted output
- [ ] Verify provenance URIs are present for each result, pointing to correct Pod resources
- [ ] Verify ACL enforcement: attempt unauthorized query, confirm denial
- [ ] Verify structured logging output for successful queries and denied queries
- [ ] Verify the agent works from within distrobox (use `distrobox-host-exec` for podman container access)
- [ ] Verify hybrid results (if Qdrant has relevant embeddings) add semantic enrichment beyond SPARQL-only results

## Dev Notes

### Architecture Decisions Referenced

- **DA-2:** Provenance & Traceability Schema. Every result must include `prov:wasDerivedFrom` URIs linking back to Pod resources. Fatima must see which Pod resources contributed to her unified view.
- **SEC-2:** ACL enforcement at query level. The SPARQL skill validates `fatima-parent` role against Pod ACLs BEFORE executing queries. This is the second layer of defense-in-depth (Pod-level WebACL is the first layer from Epic 1).
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
### Debug Log References
### Completion Notes List
### File List
