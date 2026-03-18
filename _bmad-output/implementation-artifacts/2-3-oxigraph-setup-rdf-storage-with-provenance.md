# Story 2.3: Oxigraph Setup — RDF Storage with Provenance

Status: ready-for-dev

## Story

As a **developer**,
I want RDF triples loaded into Oxigraph with provenance links back to source Pod resources,
so that every triple is traceable to its origin and the graph layer serves as a queryable index over sovereign Pod data.

## Acceptance Criteria

**AC1: Graph loader loads triples from Pods into Oxigraph**
Given Turtle resources stored in learner Pods (from story 2-2 pipeline output)
When the graph loader (`pipeline/src/pocpod0_pipeline/load_graph.py`) executes
Then all RDF triples are loaded into Oxigraph
And each triple includes `prov:wasDerivedFrom <pod-resource-uri>` provenance metadata

**AC2: Performance meets NFR1**
Given 10K+ triples loaded in Oxigraph
When a simple SPARQL query is executed
Then the response time is < 500ms

**AC3: Provenance queries work correctly**
Given a specific Pod resource URI
When I query Oxigraph for all triples derived from that resource
Then all derived triples are returned with correct provenance links

**AC4: Oxigraph service is properly configured**
Given the Oxigraph container is running
When I access the SPARQL endpoint
Then HTTP POST queries to `http://localhost:7878/query` return results
And data can be loaded via `http://localhost:7878/store`

## Tasks / Subtasks

### Task 1: Verify Oxigraph service configuration (AC4)
- [ ] Confirm `docker-compose.yml` has Oxigraph service with image `oxigraph/oxigraph:0.5.6` on port 7878
- [ ] Confirm health check is configured for Oxigraph
- [ ] Create `infra/oxigraph/config.toml` if custom configuration is needed (otherwise document that defaults suffice)
- [ ] Verify Oxigraph SPARQL endpoint is accessible:
  - Query endpoint: `POST http://localhost:7878/query` (Content-Type: `application/sparql-query`)
  - Update endpoint: `POST http://localhost:7878/update` (Content-Type: `application/sparql-update`)
  - Store endpoint: `POST http://localhost:7878/store` (Content-Type: `text/turtle` for bulk loading)
- [ ] Test basic connectivity: load a small Turtle file, run a SELECT query, verify results

### Task 2: Build graph loader module (AC1, AC3)
- [ ] Create `pipeline/src/pocpod0_pipeline/load_graph.py`
- [ ] Implement `load_from_pods()` function:
  1. Enumerate learner Pod resources from CSS (GET requests to list pod contents)
  2. For each Turtle resource in a Pod:
     a. Fetch the Turtle content from CSS (GET `http://css:3000/{pod-name}/{resource-path}`)
     b. Parse the Turtle to extract RDF triples (using `rdflib`)
     c. Verify/add `prov:wasDerivedFrom <pod-resource-uri>` provenance triple for each statement
     d. The `<pod-resource-uri>` is the full CSS URL of the source resource (e.g., `http://css:3000/ayoub/learning/assessment/stmt-uuid.ttl`)
  3. Batch-load triples into Oxigraph via SPARQL UPDATE or store endpoint
- [ ] Implement provenance attachment:
  - For every triple `(s, p, o)` loaded from a Pod resource, also insert:
    `<s> prov:wasDerivedFrom <pod-resource-uri>`
  - Use named graphs (Oxigraph supports quads) as an alternative/complement: each Pod resource's triples go into a named graph identified by the Pod resource URI
  - Ensure the approach chosen supports efficient provenance queries
- [ ] Implement structured JSON logging:
  - `{"event": "load_graph.resource.loaded", "details": {"pod": "ayoub", "resource": "...", "triple_count": N}}`
  - `{"event": "load_graph.run.complete", "details": {"total_resources": N, "total_triples": M, "failed": K}}`

### Task 3: Implement log+continue error handling (AC1)
- [ ] Wrap each resource load in try/except
- [ ] Log failures: `{"level": "ERROR", "event": "load_graph.resource.failed", "details": {"resource_uri": "...", "error": "..."}}`
- [ ] Continue processing remaining resources on failure
- [ ] Emit summary with totals at completion

### Task 4: Load OSLO schema into Oxigraph (AC1, AC3)
- [ ] Load the 4 schema files from `data/schemas/` into Oxigraph as part of the graph loading process
- [ ] Schema triples should be in a dedicated named graph (e.g., `pocpod0:schema`) to distinguish from data triples
- [ ] Verify schema classes are queryable after loading

### Task 5: Create sample SPARQL queries for verification (AC2, AC3)
- [ ] Create `data/queries/examples/` directory with sample `.rq` files
- [ ] Create `provenance-lookup.rq` — given a Pod resource URI, find all derived triples:
  ```sparql
  SELECT ?subject ?predicate ?object
  WHERE {
    ?subject prov:wasDerivedFrom <$podResourceUri> .
    ?subject ?predicate ?object .
  }
  ```
- [ ] Create `student-activities.rq` — query all learning activities for a student:
  ```sparql
  SELECT ?activityType ?verbLabel ?timestamp
  WHERE {
    ?statement oslo-educ:heeftDeelnemer ?student .
    ?statement oslo-educ:activiteitType ?activityType .
    ?statement xapi:verb ?verb .
    ?verb rdfs:label ?verbLabel .
    ?statement xapi:timestamp ?timestamp .
  }
  ```
- [ ] Create `cross-context-query.rq` — query activities across institutional contexts
- [ ] All queries use `?camelCase` variable naming convention

### Task 6: Performance validation (AC2)
- [ ] After loading 10K+ triples, measure SPARQL query response times
- [ ] Run at least 3 different query types and verify all complete < 500ms
- [ ] Log query latencies in structured JSON format
- [ ] If any query exceeds 500ms, investigate and optimize (add indexes, restructure named graphs, etc.)

### Task 7: Create CLI entry point (AC1)
- [ ] Add CLI entry point to `load_graph.py`:
  - `--css-base-url` (default from env: `CSS_BASE_URL`)
  - `--oxigraph-url` (default: `http://localhost:7878`)
  - `--load-schema` flag to also load schema files
- [ ] Update `scripts/run-pipeline.sh` to include graph loading step after ingestion

### Task 8: Write tests (AC1-AC4)
- [ ] Create `tests/pipeline/test_load_graph.py`:
  - Test: Turtle content is correctly parsed and loaded
  - Test: provenance triple (`prov:wasDerivedFrom`) is added for each resource
  - Test: log+continue — loader survives one bad resource
  - Test: summary counts are accurate
- [ ] Create `tests/integration/test_oxigraph_queries.py`:
  - Test: provenance lookup query returns correct triples for a known Pod resource
  - Test: simple SPARQL query completes < 500ms with 10K+ triples
  - Test: schema classes are queryable after loading

## Dev Notes

### Architecture Context
- **Three-Layer Data Model:** This story populates Layer 2 (Graph/Oxigraph). Layer 1 (Pod/CSS) is populated by story 2-2. Layer 3 (Vector/Qdrant) is story 2-5.
- **Oxigraph is NOT the source of truth** — it is a rebuildable queryable index. Pods are the source of truth. If Oxigraph data is lost, it can be rebuilt by re-running the graph loader against Pods.
- **Provenance is the architectural primitive** that enables deletion cascade (Pod -> Graph -> Vector) and bidirectional traceability (FR12).

### Provenance Strategy: Named Graphs vs. Provenance Triples
Two approaches are possible. Evaluate during implementation:

**Option A: Named Graphs (Quads)**
- Store each Pod resource's triples in a named graph identified by the Pod resource URI
- Provenance query: `SELECT ?s ?p ?o FROM <pod-resource-uri> WHERE { ?s ?p ?o }`
- Pro: Clean separation, efficient batch delete for cascade
- Con: More complex query patterns for cross-graph queries

**Option B: Explicit Provenance Triples**
- For every subject `s` loaded from a Pod resource, add `<s> prov:wasDerivedFrom <pod-resource-uri>`
- Provenance query: `SELECT ?s ?p ?o WHERE { ?s prov:wasDerivedFrom <pod-resource-uri> . ?s ?p ?o }`
- Pro: Simple flat graph, standard SPARQL patterns
- Con: More triples, potentially slower cascade delete

**Recommended:** Use Option A (named graphs) as primary mechanism, with Option B provenance triples as metadata. This gives the best of both approaches.

### Technical Constraints
- **Oxigraph image:** `oxigraph/oxigraph:0.5.6`
- **Oxigraph port:** 7878
- **SPARQL endpoint:** HTTP POST to `http://localhost:7878/query` (outside Docker) or `http://oxigraph:7878/query` (inside Docker)
- **Data loading:** HTTP POST to `http://localhost:7878/store` with `Content-Type: text/turtle`
- **NFR1:** Simple SPARQL queries < 500ms at 10K triples
- **Structured JSON logging to stdout**
- **Python naming:** `snake_case` modules/functions, `PascalCase` classes
- **SPARQL variables:** `?camelCase`
- **Error handling:** log+continue pattern (same as pipeline)
- **Always activate venv** for Python commands

### Oxigraph HTTP API Reference
```
# Load Turtle data
POST http://localhost:7878/store
Content-Type: text/turtle
Body: <turtle-content>

# Load into named graph
POST http://localhost:7878/store?graph=<graph-uri>
Content-Type: text/turtle
Body: <turtle-content>

# Query
POST http://localhost:7878/query
Content-Type: application/sparql-query
Accept: application/sparql-results+json
Body: SELECT ...

# Update
POST http://localhost:7878/update
Content-Type: application/sparql-update
Body: INSERT DATA { ... }
```

### Isolation Notes
- Use `distrobox-host-exec` for accessing podman containers from within distrobox
- Oxigraph container must be running and healthy before graph loading can proceed
- CSS container must be running to read Pod resources

### Project Structure Notes

Files to create:
- `pipeline/src/pocpod0_pipeline/load_graph.py`
- `infra/oxigraph/config.toml` (if needed, otherwise document that defaults are used)
- `data/queries/examples/provenance-lookup.rq`
- `data/queries/examples/student-activities.rq`
- `data/queries/examples/cross-context-query.rq`
- `tests/pipeline/test_load_graph.py`
- `tests/integration/test_oxigraph_queries.py`

Directories to create (if not existing):
- `infra/oxigraph/`
- `data/queries/examples/`
- `tests/integration/`

Files to modify:
- `scripts/run-pipeline.sh` — add graph loading step
- `pipeline/pyproject.toml` — add any new dependencies if needed

### Dependencies on Other Stories
- **Depends on Story 2-1:** OSLO schema files must exist in `data/schemas/`
- **Depends on Story 2-2:** Turtle resources must exist in CSS Pods (pipeline output)
- **Depends on Story 1-1:** Oxigraph must be configured in `docker-compose.yml` and healthy
- **Depended on by Story 2-4:** Round-trip recovery reads from Oxigraph
- **Depended on by Story 2-5 (Qdrant):** Embeddings reference Oxigraph triple URIs
- **Depended on by Story 3-1 (SPARQL Skill):** Agents query Oxigraph via the shared skill

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` — Story 2.4 acceptance criteria (line ~397-421, minus FR10 round-trip part)
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` — Decision DA-1 (Three-Layer Data Model), DA-2 (Provenance & Traceability Schema), INFRA-1 (Oxigraph 0.5.6, port 7878), API-1 (native protocol communication)
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR9 (RDF storage with provenance), NFR Performance (< 500ms SPARQL)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — story-2-3-oxigraph-setup-rdf-storage-with-provenance

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
