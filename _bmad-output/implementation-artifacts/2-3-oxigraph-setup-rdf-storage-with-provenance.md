# Story 2.3: Oxigraph Setup — RDF Storage with Provenance

Status: review

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
- [x] Confirm `docker-compose.yml` has Oxigraph service with image `oxigraph/oxigraph:0.5.6` on port 7878
- [x] Confirm health check is configured for Oxigraph
- [x] Create `infra/oxigraph/config.toml` if custom configuration is needed (otherwise document that defaults suffice)
- [x] Verify Oxigraph SPARQL endpoint is accessible:
  - Query endpoint: `POST http://localhost:7878/query` (Content-Type: `application/sparql-query`)
  - Update endpoint: `POST http://localhost:7878/update` (Content-Type: `application/sparql-update`)
  - Store endpoint: `POST http://localhost:7878/store` (Content-Type: `text/turtle` for bulk loading)
- [x] Test basic connectivity: load a small Turtle file, run a SELECT query, verify results

### Task 2: Build graph loader module (AC1, AC3)
- [x] Create `pipeline/src/pocpod0_pipeline/load_graph.py`
- [x] Implement `load_from_pods()` function:
  1. Enumerate learner Pod resources from CSS (GET requests to list pod contents)
  2. For each Turtle resource in a Pod:
     a. Fetch the Turtle content from CSS (GET `http://css:3000/{pod-name}/{resource-path}`)
     b. Parse the Turtle to extract RDF triples (using `rdflib`)
     c. Verify/add `prov:wasDerivedFrom <pod-resource-uri>` provenance triple for each statement
     d. The `<pod-resource-uri>` is the full CSS URL of the source resource (e.g., `http://css:3000/ayoub/learning/assessment/stmt-uuid.ttl`)
  3. Batch-load triples into Oxigraph via SPARQL UPDATE or store endpoint
- [x] Implement provenance attachment:
  - For every triple `(s, p, o)` loaded from a Pod resource, also insert:
    `<s> prov:wasDerivedFrom <pod-resource-uri>`
  - Use named graphs (Oxigraph supports quads) as an alternative/complement: each Pod resource's triples go into a named graph identified by the Pod resource URI
  - Ensure the approach chosen supports efficient provenance queries
- [x] Implement structured JSON logging:
  - `{"event": "load_graph.resource.loaded", "details": {"pod": "ayoub", "resource": "...", "triple_count": N}}`
  - `{"event": "load_graph.run.complete", "details": {"total_resources": N, "total_triples": M, "failed": K}}`

### Task 3: Implement log+continue error handling (AC1)
- [x] Wrap each resource load in try/except
- [x] Log failures: `{"level": "ERROR", "event": "load_graph.resource.failed", "details": {"resource_uri": "...", "error": "..."}}`
- [x] Continue processing remaining resources on failure
- [x] Emit summary with totals at completion

### Task 4: Load OSLO schema into Oxigraph (AC1, AC3)
- [x] Load the 4 schema files from `data/schemas/` into Oxigraph as part of the graph loading process
- [x] Schema triples should be in a dedicated named graph (e.g., `pocpod0:schema`) to distinguish from data triples
- [x] Verify schema classes are queryable after loading

### Task 5: Create sample SPARQL queries for verification (AC2, AC3)
- [x] Create `data/queries/examples/` directory with sample `.rq` files
- [x] Create `provenance-lookup.rq` — given a Pod resource URI, find all derived triples
- [x] Create `student-activities.rq` — query all learning activities for a student
- [x] Create `cross-context-query.rq` — query activities across institutional contexts
- [x] All queries use `?camelCase` variable naming convention

### Task 6: Performance validation (AC2)
- [x] After loading 10K+ triples, measure SPARQL query response times
- [x] Run at least 3 different query types and verify all complete < 500ms
- [x] Log query latencies in structured JSON format
- [x] If any query exceeds 500ms, investigate and optimize (add indexes, restructure named graphs, etc.)

### Task 7: Create CLI entry point (AC1)
- [x] Add CLI entry point to `load_graph.py`:
  - `--css-base-url` (default from env: `CSS_BASE_URL`)
  - `--oxigraph-url` (default: `http://localhost:7878`)
  - `--load-schema` flag to also load schema files
- [x] Update `scripts/run-pipeline.sh` to include graph loading step after ingestion

### Task 8: Write tests (AC1-AC4)
- [x] Create `tests/pipeline/test_load_graph.py`:
  - Test: Turtle content is correctly parsed and loaded
  - Test: provenance triple (`prov:wasDerivedFrom`) is added for each resource
  - Test: log+continue — loader survives one bad resource
  - Test: summary counts are accurate
- [x] Create `tests/integration/test_oxigraph_queries.py`:
  - Test: provenance lookup query returns correct triples for a known Pod resource
  - Test: simple SPARQL query completes < 500ms with 10K+ triples
  - Test: schema classes are queryable after loading

## Dev Notes

> **Handoff from Story 2.1 (schema) + 2.2 (ingestion):** This story is the merge point — start only after both 2.1 and 2.2 are done. See `_bmad-output/implementation-artifacts/2-1-oslo-vocabulary-schema-contract.md` — Handoff Notes section.
> Key gotcha: Oxigraph `POST /store` creates one named graph per request. Each Pod resource should be loaded into its own named graph for isolation. All SPARQL queries must use `GRAPH ?g { }` pattern.

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
- **Oxigraph health endpoint (FOG-OF-WAR):** The correct health endpoint name is unknown — verify empirically in Task 1. Try `/ready` first, then `/health`. Document the result for downstream stories.
- **CSS Auth (CRITICAL):** ALL CSS requests (GET to read pod resources) MUST include `Authorization: WebID http://localhost:3000/provisioner/profile/card#me` header. `X-Ms-User` does NOT work. CSS must be configured with `debug-auth-header.json` (UnsecureWebIdExtractor). Without this header, GET requests to pod resources return 401.
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

> **Handoff from Story 2.2:** See `_bmad-output/implementation-artifacts/2-2-xapi-oslo-rdf-ingestion-pipeline.md` — Handoff Notes section for gotchas and recommendations.
> **⚠️ Dataset size correction:** AC2 references "10K+ triples" but the actual pipeline output is **~303 scenario statements** (not 10K). The 10K target in `pocpod0-xapi-profile.jsonld` is aspirational and not a POC requirement. Relax AC2 to match actual data volume — SPARQL performance at 303-statement scale is the real target.
> **Key facts from 2.2:** CSS auth = `Authorization: WebID {webid}` (provisioner). Pod path pattern = `{pod}/learning/{activity-type}/{uuid}.ttl`. Each Turtle file contains `prov:wasDerivedFrom <pod-resource-uri>` + `pocpod0:originalXapiJson` literal. Oxigraph `POST /store` creates named graphs — always query with `GRAPH ?g { }`.

### Handoff Notes (for Stories 2.4, 2.5, 2.6, 3.1+)

**Oxigraph health endpoint:** `/health` returns 404. Use `/` (root) — returns 200. docker-compose healthcheck already fixed.

**Oxigraph HTTP status codes:** Store endpoint returns 201 for new named graphs, 204 for updates. Both are success. Accept `(200, 201, 204)`.

**Named graph == Pod resource URI (CRITICAL):** Every Pod resource is stored in a named graph identified by its full CSS URL, e.g.:
  `http://localhost:3000/ayoub/learning/assessment/stmt-uuid.ttl`
Queries MUST use `GRAPH <uri> { }` or `FROM <uri>` pattern — default graph is empty.

**Query pattern for provenance (correct):**
```sparql
SELECT ?s ?p ?o FROM <http://localhost:3000/ayoub/learning/assessment/stmt-uuid.ttl> WHERE { ?s ?p ?o }
# or
SELECT ?s ?p ?o WHERE { GRAPH <http://localhost:3000/ayoub/learning/assessment/stmt-uuid.ttl> { ?s ?p ?o } }
```

**Schema graph URI:** `https://poc-pod0.edu/vocab/schema` — contains 479 OSLO triples (oslo-education, xapi-to-oslo, pocpod0-vocab, oslo-person). Filter this out when counting data named graphs: `FILTER(?g != <https://poc-pod0.edu/vocab/schema>)`.

**Pod discovery:** CSS root `ldp:contains` includes non-container resources (e.g. `index.html`). Always filter to URIs ending with `/` before treating as pods. Pod resources nested under `learning/{activity-type}/` subcontainers — requires recursive LDP walk.

**Data scale (actual):** 5,614 Pod resources, 117,306 triples at 117K scale — all queries < 500ms. AC2 "10K+" target is exceeded.

**Progress monitoring (dashboard):** Count named graphs via `SELECT (COUNT(*) AS ?g) WHERE { GRAPH ?g {} }` — subtract 1 for schema graph. Compare against total resources from ingestion run.

**Provenance design decision (Option A only):** The loader uses named graphs exclusively (Option A). `prov:wasDerivedFrom` triples are present inside each named graph because Story 2.2 writes them into the Turtle files — the loader does NOT inject them. If data is ever loaded from a source other than Story 2.2, verify it also includes `prov:wasDerivedFrom` triples, or query provenance via named graph URI only.

**PROVISIONER_WEBID fail-fast:** `load_graph.py` raises `RuntimeError` at import time if `PROVISIONER_WEBID` is empty. Ensure `CSS_BASE_URL` is set before importing or running the module.

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
claude-sonnet-4-6

### Debug Log References
- Oxigraph `/health` returns 404; correct health endpoint is `/` (root). Fixed docker-compose healthcheck.
- Oxigraph store returns HTTP 201 (not 204) for new named graphs; updated success codes to include 201.
- CSS root listing includes `index.html` as `ldp:contains` member; fixed pod discovery to skip non-container (non-`/`) URIs.
- Pod resources nested in activity-type subcontainers (`learning/assessment/`, `learning/course/`, etc.) — LDP recursive walk required.
- AC2 relaxed per handoff note: actual data is ~5,606 resources / 117,306 triples (not 10K+); all queries < 500ms confirmed.

### Completion Notes List
- Implemented named-graph provenance strategy (Option A): each Pod resource URI = its named graph in Oxigraph
- 5,614 resources loaded, 117,306 triples, 0 failures on live run
- 479 OSLO schema triples loaded into `https://poc-pod0.edu/vocab/schema` named graph
- 20/20 tests pass (14 unit + 6 integration); 61/61 full regression suite
- All 3 SPARQL query types < 500ms at 117K triple scale
- `run-pipeline.sh` updated with Step 4 (graph loading)
- No new dependencies required (rdflib already in pyproject.toml)

### File List
- `pipeline/src/pocpod0_pipeline/load_graph.py` (new)
- `pipeline/tests/pipeline/__init__.py` (new)
- `pipeline/tests/pipeline/test_load_graph.py` (new)
- `pipeline/tests/integration/test_oxigraph_queries.py` (new)
- `data/queries/examples/provenance-lookup.rq` (new)
- `data/queries/examples/student-activities.rq` (new)
- `data/queries/examples/cross-context-query.rq` (new)
- `docker-compose.yml` (modified — fixed Oxigraph health check endpoint)
- `scripts/run-pipeline.sh` (modified — added Step 4: graph loading)
- `pipeline/pyproject.toml` (modified — added `pocpod0-load-graph` CLI entry point)

## Change Log
- 2026-03-20: Story 2.3 implemented — Oxigraph graph loader with named-graph provenance, schema loading, SPARQL query examples, CLI, tests
- 2026-03-20: Code review patches applied — cycle detection, SSRF guard, PROVISIONER_WEBID fail-fast, dead code removed, schema empty-graph guard, _delete_graph error handling, Oxigraph 4xx logging
