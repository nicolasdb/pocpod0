# Story 2.6: Bidirectional Traceability — Embedding, Triple, Pod

Status: ready-for-dev

## Story

As a **developer**,
I want full bidirectional traceability between embeddings, triples, and Pod resources verified end-to-end,
so that any component in the three-layer data model can be navigated to its source or derived artifacts, enabling deletion cascade and provenance display.

## Acceptance Criteria

**AC-1: Forward traceability — embedding to Pod**
Given any embedding stored in Qdrant
When I follow the traceability chain
Then I can navigate: embedding -> `triple_uris` (from Qdrant payload) -> Oxigraph triples (via SPARQL) -> `prov:wasDerivedFrom` -> Pod resource URI -> CSS Pod resource
And each step in the chain returns valid, non-empty results

**AC-2: Reverse traceability — Pod to embeddings**
Given any Pod resource URI that has been ingested
When I query Oxigraph for triples with `prov:wasDerivedFrom <pod-resource-uri>`
Then all derived triples are returned
And when I query Qdrant for points with `pod_resource_uri` matching that URI
Then all derived embeddings are returned

**AC-3: Reverse traceability — Pod to triples**
Given a Pod resource URI
When I execute a SPARQL query against Oxigraph: `SELECT ?s ?p ?o WHERE { ?s ?p ?o . ?s prov:wasDerivedFrom <pod-resource-uri> }`
Then all triples derived from that Pod resource are returned with their subjects, predicates, and objects

**AC-4: Triple to embedding mapping**
Given a set of triple URIs from Oxigraph
When I query Qdrant for points whose `triple_uris` payload contains any of those URIs
Then the corresponding embeddings are returned
And this confirms the triple-to-embedding direction of traceability

**AC-5: Provenance schema consistency (DA-2)**
Given the provenance schema defined in architecture decision DA-2
When I inspect any triple in Oxigraph
Then it has a `prov:wasDerivedFrom <pod-resource-uri>` triple linking it to its source Pod resource
And when I inspect any point in Qdrant
Then its payload contains both `triple_uris` (array) and `pod_resource_uri` (string)
And the `pod_resource_uri` in Qdrant matches the object of `prov:wasDerivedFrom` in Oxigraph for the corresponding triples

**AC-6: Integration test passes**
Given the traceability verification code
When the integration test suite runs against live services (Oxigraph + Qdrant + CSS)
Then all forward and reverse traceability assertions pass
And the test is placed in `tests/integration/test_traceability.py`

**AC-7: Traceability utility is reusable**
Given the traceability verification functions
When other components need to verify provenance (deletion cascade, dashboard display, agent queries)
Then the functions are importable from a shared module in the pipeline package

## Tasks / Subtasks

### Task 1: Create traceability utility module (AC-1, AC-2, AC-7)
- [ ] Create `pipeline/src/pocpod0_pipeline/traceability.py` with reusable functions:
  - `trace_embedding_to_pod(qdrant_client, oxigraph_url, point_id) -> TraceResult`
    - Retrieve Qdrant point -> extract `triple_uris` and `pod_resource_uri` -> verify triples in Oxigraph -> verify `prov:wasDerivedFrom` links -> return full chain
  - `trace_pod_to_embeddings(qdrant_client, oxigraph_url, pod_resource_uri) -> ReverseTraceResult`
    - Query Oxigraph for triples with `prov:wasDerivedFrom` -> query Qdrant for points with matching `pod_resource_uri` -> return all derived triples and embeddings
  - `trace_pod_to_triples(oxigraph_url, pod_resource_uri) -> list[Triple]`
    - SPARQL query for all triples derived from a Pod resource
  - `trace_triples_to_embeddings(qdrant_client, triple_uris) -> list[QdrantPoint]`
    - Query Qdrant payload filter for points containing any of the given triple URIs
  - `verify_provenance_consistency(qdrant_client, oxigraph_url, pod_resource_uri) -> ConsistencyReport`
    - Cross-check that Oxigraph provenance and Qdrant payloads agree

### Task 2: Define data classes for trace results (AC-7)
- [ ] Define typed result classes (dataclasses or Pydantic models):
  ```python
  @dataclass
  class TraceResult:
      point_id: str
      triple_uris: list[str]
      pod_resource_uri: str
      triples_found_in_oxigraph: bool
      pod_resource_exists: bool
      chain_complete: bool

  @dataclass
  class ReverseTraceResult:
      pod_resource_uri: str
      derived_triple_count: int
      derived_embedding_count: int
      triple_uris: list[str]
      embedding_point_ids: list[str]

  @dataclass
  class ConsistencyReport:
      pod_resource_uri: str
      oxigraph_triple_count: int
      qdrant_point_count: int
      orphaned_triples: list[str]  # triples with no corresponding embedding
      orphaned_embeddings: list[str]  # embeddings with no matching triple
      consistent: bool
  ```

### Task 3: Implement forward traceability (AC-1)
- [ ] `trace_embedding_to_pod()`:
  - Call Qdrant REST API to retrieve point by ID
  - Extract `triple_uris` and `pod_resource_uri` from payload
  - For each triple URI, execute SPARQL ASK query against Oxigraph to confirm existence
  - Verify `prov:wasDerivedFrom` triple exists linking the triples to the `pod_resource_uri`
  - Optionally verify Pod resource exists at CSS (HTTP HEAD request to `pod_resource_uri`)
  - Return `TraceResult` with chain completeness flag

### Task 4: Implement reverse traceability (AC-2, AC-3)
- [ ] `trace_pod_to_triples()`:
  - SPARQL query: `SELECT ?s ?p ?o WHERE { ?s ?p ?o . ?s prov:wasDerivedFrom <pod_resource_uri> }`
  - Execute against Oxigraph at `http://oxigraph:7878/query`
  - Parse SPARQL JSON results
- [ ] `trace_pod_to_embeddings()`:
  - Call Qdrant scroll/search with payload filter: `{ "must": [{ "key": "pod_resource_uri", "match": { "value": "<uri>" } }] }`
  - Return all matching points
- [ ] Combine both into `trace_pod_to_embeddings()` returning full `ReverseTraceResult`

### Task 5: Implement triple-to-embedding lookup (AC-4)
- [ ] `trace_triples_to_embeddings()`:
  - For each triple URI, query Qdrant with payload filter on `triple_uris` array contains the URI
  - Qdrant filter: `{ "must": [{ "key": "triple_uris", "match": { "any": ["<triple_uri>"] } }] }`
  - Note: verify Qdrant v1.17.0 supports `match.any` on array fields; if not, iterate individual matches
  - Return deduplicated list of matching points

### Task 6: Implement provenance consistency check (AC-5)
- [ ] `verify_provenance_consistency()`:
  - Get all triple URIs from Oxigraph for a given Pod resource (Task 4)
  - Get all embedding points from Qdrant for the same Pod resource (Task 4)
  - Cross-reference: every triple should have at least one embedding referencing it (unless the content was not semantically significant)
  - Every embedding's `triple_uris` should reference triples that exist in Oxigraph
  - Report orphaned triples and orphaned embeddings
  - Note: orphaned triples (triples without embeddings) are acceptable for non-semantic content. Orphaned embeddings (embeddings referencing non-existent triples) are NOT acceptable.

### Task 7: Write integration test (AC-6)
- [ ] Create `tests/integration/test_traceability.py`
- [ ] Test requires live services: Oxigraph (with loaded triples from Story 2-3) and Qdrant (with embeddings from Story 2-5)
- [ ] Test cases:
  - `test_forward_trace_embedding_to_pod`: pick a random Qdrant point, trace to Pod resource, assert chain complete
  - `test_reverse_trace_pod_to_all_derived`: pick a known Pod resource URI, find all triples and embeddings, assert counts > 0
  - `test_reverse_trace_pod_to_triples`: verify SPARQL returns triples with correct provenance
  - `test_triple_to_embedding_mapping`: pick triple URIs, find corresponding embeddings
  - `test_provenance_consistency`: run consistency check, assert no orphaned embeddings
  - `test_nonexistent_pod_returns_empty`: verify traceability for a URI that was never ingested returns empty results
- [ ] Use pytest fixtures for Qdrant client and Oxigraph URL configuration
- [ ] Tests must be deterministic and reproducible (NFR12)

### Task 8: Add structured logging (AC-7)
- [ ] Log traceability operations:
  - `traceability.forward_trace`: `{ point_id, chain_complete, duration_ms }`
  - `traceability.reverse_trace`: `{ pod_resource_uri, triple_count, embedding_count, duration_ms }`
  - `traceability.consistency_check`: `{ pod_resource_uri, consistent, orphaned_triples, orphaned_embeddings }`

## Dev Notes

### This Story's Architectural Significance

This is the architectural primitive that makes deletion cascade (Story 5-2) and provenance display (dashboard, agent queries) possible. The traceability module created here is reused by:
- **Deletion cascade** (`delete_cascade.py`): uses reverse traceability to find all derived data for a Pod resource
- **Dashboard**: uses forward traceability to show provenance chains in the UI
- **Agent queries**: return provenance metadata alongside query results
- **Troll agent**: verifies traceability as part of deletion timing tests

### DA-2 Provenance Schema (Architecture Decision)

Two provenance mechanisms work together:
1. **Oxigraph side:** Every triple has `prov:wasDerivedFrom <pod-resource-uri>` — this is a triple in the graph, not a quad/named graph
2. **Qdrant side:** Every point payload has `{ "triple_uris": [...], "pod_resource_uri": "..." }`

The `pod_resource_uri` value MUST be identical in both systems for the same data lineage.

### Three-Layer Data Model Navigation

```
                 Forward (→)                    Reverse (←)
Qdrant Point  ──────────────→  Oxigraph Triple  ──────────────→  CSS Pod Resource
  payload.triple_uris           prov:wasDerivedFrom              HTTP resource
  payload.pod_resource_uri      ←────────────────               ←────────────────
                               SPARQL query                     Qdrant filter on
                               for provenance                   pod_resource_uri
```

### SPARQL Queries Used

Forward trace (verify triple exists):
```sparql
ASK WHERE { <triple_uri> ?p ?o }
```

Reverse trace (find all triples for a Pod resource):
```sparql
SELECT ?s ?p ?o WHERE {
  ?s ?p ?o .
  ?s prov:wasDerivedFrom <pod_resource_uri> .
}
```

### Qdrant Payload Filters Used

Reverse trace (find embeddings for a Pod resource):
```json
{
  "filter": {
    "must": [
      { "key": "pod_resource_uri", "match": { "value": "http://..." } }
    ]
  }
}
```

Triple-to-embedding lookup:
```json
{
  "filter": {
    "must": [
      { "key": "triple_uris", "match": { "any": ["urn:triple:abc"] } }
    ]
  }
}
```

### Service Endpoints

- **Oxigraph SPARQL:** `http://oxigraph:7878/query` (POST, `application/sparql-query`)
- **Qdrant REST:** `http://qdrant:6333` (REST API)
- **CSS Pods:** `http://community-solid-server:3000/{pod-name}/{resource-path}`

### Error Handling

- Traceability checks are informational — a broken chain is a finding, not a crash
- Log broken chains with full details for debugging
- The consistency check returns a report; callers decide what to do with inconsistencies

### Python Dependencies

No new dependencies beyond what Story 2-5 adds (`qdrant-client`, `httpx`). The traceability module uses the same clients.

### Naming Conventions

- Module: `traceability.py` (snake_case)
- Functions: `trace_embedding_to_pod()`, `trace_pod_to_embeddings()`, `verify_provenance_consistency()`
- Classes: `TraceResult`, `ReverseTraceResult`, `ConsistencyReport` (PascalCase)
- Test file: `test_traceability.py`

### Distrobox Isolation Note

When running integration tests that need access to Docker services, use `distrobox-host-exec` to reach the containers:
```bash
distrobox-host-exec podman compose up oxigraph qdrant
```

### Project Structure Notes

**Files to create:**
- `pipeline/src/pocpod0_pipeline/traceability.py` — reusable traceability utility module
- `tests/integration/test_traceability.py` — integration test

**Files to modify:**
- None (uses existing dependencies from Story 2-5)

**Depends on:**
- Story 2-3: Oxigraph must have RDF triples loaded with `prov:wasDerivedFrom` provenance
- Story 2-5: Qdrant must have embeddings with `triple_uris` and `pod_resource_uri` payload metadata

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: DA-1, DA-2, Deletion Cascade Protocol)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: FR12, Technical Success criteria on bidirectional traceability)
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 2.5 acceptance criteria — the FR12 traceability portion)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-2-6-bidirectional-traceability-embedding-triple-pod`)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
