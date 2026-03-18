# Story 3.7: [foundation] Graph-Only vs Hybrid Query Results Comparison Display

Status: ready-for-dev

## Story

As a **demo audience member** (funder, partner, reviewer),
I want the system to display graph-only and hybrid query results side by side with clear provenance for both,
so that I can visually confirm the added value of semantic enrichment over structured queries alone.

## Acceptance Criteria

**AC1: Side-by-side comparison output for any query**
Given any agent executing a query that supports hybrid mode
When the comparison formatter receives both graph-only results (SPARQL skill) and hybrid results (SPARQL skill + Qdrant skill)
Then the output displays both result sets side by side in a clearly structured format (FR16)
And the graph-only column shows what SPARQL alone found (structured facts)
And the hybrid column shows what SPARQL + vector search found (semantically enriched insights)

**AC2: Provenance displayed for both result sets**
Given a comparison display
When the results are rendered
Then the graph-only results include provenance: which `.rq` template, which triples, which Pod resource URIs (`prov:wasDerivedFrom`) (FR20)
And the hybrid results include provenance for SPARQL results AND traceability metadata for Qdrant results (`triple_uris`, `pod_resource_uri`)
And each insight is traceable back to its source data

**AC3: Reusable comparison mechanism**
Given the comparison display capability
When any agent (not just Claire) triggers a comparison
Then the formatter works generically for any agent's query results
And the output is a reusable demo artifact (can be shown to funders for any scenario)

**AC4: Clear distinction between what each data source contributed**
Given the comparison output
When reviewed by a non-technical audience
Then the output clearly labels: "Graph-Only (SPARQL)" vs "Hybrid (SPARQL + Semantic Search)"
And the hybrid column visually highlights what vector search added that SPARQL alone could not surface
And the display is self-explanatory without technical narration

**AC5: Hybrid performance within budget**
Given a comparison query execution
When both graph-only and hybrid queries complete
Then the combined hybrid response time is < 2s (NFR2)
And the comparison formatter adds negligible overhead (formatting only, no additional queries)

## Tasks / Subtasks

### Task 1: Design comparison output data model (AC1, AC2, AC3)
- [ ] Define a `ComparisonResult` data class in `agents/skills/comparison-formatter/formatter.py`:
  ```python
  @dataclass
  class ComparisonResult:
      query_text: str              # Original natural language query
      agent_id: str                # Which agent triggered this comparison
      graph_only: GraphOnlyResult  # SPARQL-only results
      hybrid: HybridResult         # SPARQL + Qdrant results
      metadata: ComparisonMeta     # Timing, provenance summary
  ```
- [ ] Define `GraphOnlyResult`:
  ```python
  @dataclass
  class GraphOnlyResult:
      results: list[dict]          # Raw SPARQL results
      template_used: str           # Which .rq template was executed
      result_count: int
      latency_ms: int
      provenance: list[dict]       # List of { triple_uri, pod_resource_uri }
  ```
- [ ] Define `HybridResult`:
  ```python
  @dataclass
  class HybridResult:
      sparql_results: list[dict]   # SPARQL portion
      vector_results: list[dict]   # Qdrant portion with similarity scores
      merged_insights: list[dict]  # Agent-merged result set
      sparql_provenance: list[dict]
      vector_provenance: list[dict]  # { triple_uris, pod_resource_uri, score }
      combined_latency_ms: int
  ```
- [ ] Define `ComparisonMeta`:
  ```python
  @dataclass
  class ComparisonMeta:
      timestamp: str               # ISO-8601
      graph_only_latency_ms: int
      hybrid_latency_ms: int
      vector_added_count: int      # How many extra insights vector search contributed
      provenance_summary: str      # Human-readable provenance line
  ```

### Task 2: Create comparison formatter skill directory (AC1, AC3)
- [ ] Create `agents/skills/comparison-formatter/` directory
- [ ] Create `agents/skills/comparison-formatter/skill.yaml` with:
  - Skill name: `comparison-formatter`
  - Description: Formats graph-only vs hybrid query results for side-by-side comparison display
  - Input schema: `GraphOnlyResult` + `HybridResult` + agent context
  - Output schema: `ComparisonResult` formatted for display
- [ ] Create `agents/skills/comparison-formatter/formatter.py` — Main formatting logic

### Task 3: Implement comparison formatting logic (AC1, AC4)
- [ ] In `formatter.py`, implement `format_comparison(graph_only, hybrid, query_text, agent_id) -> ComparisonResult`:
  1. Accept raw results from SPARQL skill (graph-only) and merged SPARQL+Qdrant results (hybrid)
  2. Structure them into the `ComparisonResult` data model
  3. Calculate `vector_added_count`: count of insights in hybrid that are NOT in graph-only
  4. Generate `provenance_summary`: human-readable sentence describing data sources
- [ ] Implement `render_text(comparison: ComparisonResult) -> str`:
  - Render a structured text comparison with two columns
  - Header: query text, agent ID, timestamp
  - Left column: "GRAPH-ONLY (SPARQL)" with structured facts and provenance
  - Right column: "HYBRID (SPARQL + SEMANTIC SEARCH)" with enriched insights and provenance
  - Footer: "Vector search added N additional insights" summary
  - Provenance section: list of Pod resource URIs referenced by each result set
- [ ] Implement `render_json(comparison: ComparisonResult) -> dict`:
  - Machine-readable JSON output for dashboard consumption (Phase 4)
  - Same data as text render but structured as JSON
  - Suitable for HTMX partial rendering in the mission control dashboard

### Task 4: Implement provenance display for both result sets (AC2)
- [ ] For graph-only results, extract and display:
  - Template name used (e.g., `student-progress.rq`)
  - `prov:wasDerivedFrom` URIs from SPARQL results (which Pod resources contributed)
  - Triple count contributing to the answer
- [ ] For hybrid results, extract and display:
  - Everything from graph-only provenance PLUS:
  - Qdrant similarity scores per vector result
  - `triple_uris` and `pod_resource_uri` from each Qdrant point payload
  - Embedding model used (`qwen/qwen3-embedding-8b`)
- [ ] Provenance format per result item:
  ```
  Source: [Pod Resource URI]
  Via: [SPARQL template | Qdrant semantic search (score: 0.92)]
  Triples: [count] triples from [N] pod resources
  ```

### Task 5: Implement non-technical display labels (AC4)
- [ ] Replace technical labels with audience-friendly labels in `render_text`:
  - "SPARQL" -> "Structured Data Query" (with "SPARQL" in parentheses for technical readers)
  - "Qdrant" -> "Semantic Search" (with "Qdrant" in parentheses)
  - "prov:wasDerivedFrom" -> "Data Source"
  - "triple_uris" -> "Related Data Points"
  - "pod_resource_uri" -> "Student Pod Source"
- [ ] Add a "What This Means" summary line for each result set:
  - Graph-only: "These are structured facts from the knowledge graph — precise but limited to what was explicitly recorded."
  - Hybrid addition: "These additional insights were found by semantic similarity search — the system found related information that structured queries alone would miss."
- [ ] Visually mark the delta: items present in hybrid but absent from graph-only should be clearly flagged as "Added by Semantic Search"

### Task 6: Implement agent-agnostic comparison protocol (AC3)
- [ ] The formatter must work with any agent's results, not just Claire's:
  - Accept agent_id as parameter (e.g., `claire-teacher`, `fatima-parent`, `isabelle-policy`)
  - Do not hardcode any agent-specific logic
  - The formatter is a utility — agents call it after they've gathered their results
- [ ] Define the comparison invocation protocol for agent configs:
  1. Agent calls SPARQL skill with query -> receives `graph_only_results`
  2. Agent calls SPARQL skill + Qdrant skill with same query -> receives `hybrid_results`
  3. Agent calls comparison formatter with both result sets -> receives `ComparisonResult`
  4. Agent presents the comparison to its audience
- [ ] Document this protocol in `skill.yaml` so future agent story dev agents can reference it

### Task 7: Implement structured JSON logging (AC5)
- [ ] Log comparison formatting events to stdout:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "comparison-formatter",
    "level": "INFO",
    "event": "comparison.formatted",
    "agent": "claire-teacher",
    "duration_ms": 5,
    "details": {
      "query_text": "Which students are struggling...",
      "graph_only_result_count": 3,
      "hybrid_result_count": 7,
      "vector_added_count": 4,
      "graph_only_latency_ms": 320,
      "hybrid_latency_ms": 1450,
      "render_format": "text"
    }
  }
  ```
- [ ] Log to stdout so docker-compose captures it (feeds dashboard in Phase 4)

### Task 8: Integration verification (AC1, AC2, AC3, AC4, AC5)
- [ ] Verify the formatter produces correct side-by-side output for Claire's cross-context query
- [ ] Verify the formatter works for a different agent (e.g., Fatima's parental view query) to confirm agent-agnostic design
- [ ] Verify provenance metadata is correctly extracted and displayed for both result sets
- [ ] Verify non-technical labels are present and comprehensible
- [ ] Verify the "Added by Semantic Search" delta highlighting works correctly
- [ ] Verify the JSON render output is valid JSON suitable for dashboard consumption
- [ ] Verify the formatting adds negligible latency (< 50ms — it's string formatting, not querying)
- [ ] Verify the formatter works from within distrobox (use `distrobox-host-exec` for podman container access)

## Dev Notes

### Architecture Decisions Referenced

- **FR16:** The system can display graph-only vs. hybrid query results side by side for comparison. This story IS the implementation of FR16.
- **FR20:** The system can surface provenance for query results. This story ensures provenance is displayed in the comparison view.
- **API-2:** Two separate skills (SPARQL and Qdrant). The comparison formatter is a third utility skill that consumes output from both.
- **DA-2:** Provenance & Traceability Schema. The formatter displays `prov:wasDerivedFrom` from SPARQL and `triple_uris`/`pod_resource_uri` from Qdrant.
- **NFR2:** Hybrid SPARQL + vector queries < 2s. The formatter itself must not add meaningful latency; the 2s budget is for the data queries.

### Key Design Point: Formatter Is Not a Query Skill

The comparison formatter does NOT execute queries. It takes results that an agent has already gathered from the SPARQL skill and Qdrant skill, and structures them for side-by-side display. The query execution (and the 2s latency budget) belongs to the skills in Stories 3.1 and 3.2.

The flow is:
```
Agent                          Skills                       Formatter
  |                              |                              |
  |-- call SPARQL skill -------->|                              |
  |<--- graph_only_results ------|                              |
  |                              |                              |
  |-- call SPARQL + Qdrant ----->|                              |
  |<--- hybrid_results ----------|                              |
  |                              |                              |
  |-- call comparison formatter -------------------------------->|
  |<--- formatted ComparisonResult ------------------------------|
  |                              |                              |
  |-- present to audience        |                              |
```

### Connection to Claire's Journey (Story 3.4)

Claire's journey (Story 3.4) is the primary consumer of this comparison display. The PRD describes the "proof moment": same question, visibly richer hybrid answer. However, this formatter is built as a reusable component so that:
- Fatima's parental view can also show graph-only vs. hybrid
- Isabelle's policy queries can show the comparison
- Funder intervention points (FR38) can trigger comparisons for any agent
- The comparison becomes a reusable demo artifact per PRD

### Connection to Dashboard (Phase 4)

The `render_json()` output is designed to be consumable by the FastAPI + HTMX mission control dashboard (Story 6.2). The JSON structure should be directly usable as an HTMX partial template data source.

### Naming Conventions

- Skill directory: `comparison-formatter` (lowercase hyphen)
- Python file: `formatter.py` (snake_case)
- Python classes: `ComparisonResult`, `GraphOnlyResult`, `HybridResult`, `ComparisonMeta` (PascalCase)
- Python functions: `format_comparison`, `render_text`, `render_json` (snake_case)
- Agent IDs: `claire-teacher`, `marc-admin`, `isabelle-policy`, `fatima-parent`, `ayoub-student` (lowercase hyphen)

### Example Comparison Output (Text Render)

```
================================================================================
QUERY COMPARISON: "Which students are struggling with quadratic equations?"
Agent: claire-teacher | Timestamp: 2026-03-20T14:32:05Z
================================================================================

GRAPH-ONLY (Structured Data Query / SPARQL)           | HYBRID (Structured + Semantic Search / SPARQL + Qdrant)
-------------------------------------------------------+-------------------------------------------------------
Ayoub:                                                 | Ayoub:
  - Failed assessment: Math Test 3 (quadratic eq.)     |   - Failed assessment: Math Test 3 (quadratic eq.)
  - Failed assessment: Math Test 4 (quadratic eq.)     |   - Failed assessment: Math Test 4 (quadratic eq.)
  - Tutoring attendance: 8/10 sessions                 |   - Tutoring attendance: 8/10 sessions
  - Self-study: 3 Khan Academy modules completed       |   - Self-study: 3 Khan Academy modules completed
                                                       |   + [ADDED BY SEMANTIC SEARCH]
                                                       |   + Tutoring notes: "Ayoub grasps quadratic equations
                                                       |     through geometric visualization — the school
                                                       |     assessment doesn't capture his approach"
                                                       |     (score: 0.92, source: tutoring-session-42.ttl)
-------------------------------------------------------+-------------------------------------------------------
Results: 4 structured facts                            | Results: 4 structured facts + 1 semantic insight
Latency: 320ms                                         | Latency: 1,450ms (320ms SPARQL + 1,130ms semantic)
Template: student-progress.rq                          | Template: student-progress.rq + semantic search

PROVENANCE:
  Graph-only sources: ayoub/learning/math-test-3.ttl, ayoub/learning/math-test-4.ttl,
                      ayoub/learning/tutoring-log.ttl, ayoub/learning/khan-progress.ttl
  Semantic sources:   ayoub/learning/tutoring-session-42.ttl (via embedding similarity)

SUMMARY: Semantic search added 1 additional insight that structured queries alone could not surface.
  - Graph-only: precise structured facts from the knowledge graph
  - Semantic addition: related information found by meaning similarity, not explicit structure
================================================================================
```

### Project Structure Notes

Directories/files to create:

```
agents/
└── skills/
    └── comparison-formatter/           # NEW - Comparison display utility
        ├── skill.yaml                  # NEW - Skill definition
        └── formatter.py               # NEW - Formatting logic + data models
```

Files that must already exist (from Stories 3.1, 3.2):

```
agents/
├── openclaw.config.yaml                # Created in Story 3.1
└── skills/
    ├── sparql-query/                    # Created in Story 3.1
    │   ├── skill.yaml
    │   ├── handler.py
    │   └── templates/*.rq
    └── qdrant-search/                   # Created in Story 3.2
        ├── skill.yaml
        └── handler.py
```

### Dependencies

- **Depends on Story 3.1:** SPARQL skill must exist — the formatter consumes its output format (`{ status, results, provenance }`)
- **Depends on Story 3.2:** Qdrant skill must exist — the formatter consumes its output format (`{ status, results: [{ score, triple_uris, pod_resource_uri }] }`)
- **Depends on Story 3.3:** Agent configs must exist — at least one agent must be able to invoke skills and pass results to the formatter
- **Depends on Epic 2:** Data must be loaded in Oxigraph and Qdrant for meaningful comparison results
- **Consumed by Story 3.4:** Claire's journey uses this formatter for the "proof moment"
- **Consumed by Phase 4:** Dashboard renders the JSON output from this formatter

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman logs community-solid-server`

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-2, API-2, NFR2, Agent Query Protocol)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR16, FR20, NFR Performance — hybrid < 2s, Claire Journey "Beat 1" and "Beat 2")
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.3 AC for side-by-side display, FR16 mapping)
- Story 3.1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill output format)
- Story 3.2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` (Qdrant skill output format, hybrid query protocol)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
