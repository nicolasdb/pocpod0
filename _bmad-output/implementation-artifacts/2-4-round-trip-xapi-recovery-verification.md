# Story 2.4: Round-Trip xAPI Recovery Verification

Status: ready-for-dev

## Story

As a **developer**,
I want to verify that any original xAPI statement can be recovered by following provenance links from Oxigraph back through Pod resources,
so that the "lossless" claim of the xAPI-to-OSLO pipeline is proven with a concrete round-trip test.

## Acceptance Criteria

**AC1: Round-trip recovery works for any triple**
Given any triple in Oxigraph
When I follow the provenance link (`prov:wasDerivedFrom`) back to the Pod resource
And extract the original data from that Pod resource
Then the original xAPI statement is recoverable in its entirety

**AC2: Recovery produces valid, identical xAPI**
Given a recovered xAPI statement
When compared to the original input statement from `data/synthetic/`
Then the two are semantically identical (same actor, verb, object, result, context, timestamp)
And the recovered statement is valid xAPI JSON

**AC3: Recovery works across all personas**
Given the full set of loaded triples in Oxigraph
When recovery is attempted for at least one statement per persona (Ayoub, Claire-student-1, Claire-student-2, Fatima-child-1, Fatima-child-2)
Then all recoveries succeed

**AC4: Verification is automated and repeatable**
Given the verification script/test suite
When executed against a populated Oxigraph + CSS environment
Then all recovery tests pass
And results are logged in structured JSON format

## Tasks / Subtasks

### Task 1: Design the recovery path (AC1)
- [ ] Document the exact recovery flow:
  1. Start with a triple (or set of triples sharing a subject) in Oxigraph
  2. Query for `?subject prov:wasDerivedFrom ?podResourceUri`
  3. HTTP GET the Pod resource from CSS at `?podResourceUri`
  4. Parse the returned Turtle content
  5. Extract the original xAPI JSON from the `pocpod0:originalXapi` literal property (or equivalent lossless storage mechanism from story 2-2)
  6. Parse and validate the recovered xAPI JSON
- [ ] Confirm the lossless storage mechanism used by story 2-2 (the `pocpod0:originalXapi` property or alternative)
- [ ] If story 2-2 used a different approach for preserving original xAPI, adapt the recovery logic accordingly

### Task 2: Build recovery utility function (AC1, AC2)
- [ ] Create `pipeline/src/pocpod0_pipeline/recover_xapi.py`
- [ ] Implement `recover_xapi_from_triple(subject_uri: str, oxigraph_url: str, css_base_url: str) -> dict`:
  1. Query Oxigraph: `SELECT ?podResourceUri WHERE { <subject_uri> prov:wasDerivedFrom ?podResourceUri . }`
  2. Fetch Pod resource: `GET {podResourceUri}` with `Accept: text/turtle`
  3. Parse Turtle, extract original xAPI from lossless storage property
  4. Return parsed xAPI dict
- [ ] Implement `recover_xapi_batch(oxigraph_url: str, css_base_url: str, limit: int = 100) -> list[dict]`:
  - Query Oxigraph for a sample of subjects with provenance links
  - Recover xAPI for each
  - Return list of `{"subject_uri": ..., "pod_resource_uri": ..., "recovered_xapi": ..., "success": bool}`
- [ ] Add structured JSON logging for each recovery attempt

### Task 3: Build comparison utility (AC2)
- [ ] Implement `compare_xapi_statements(original: dict, recovered: dict) -> dict`:
  - Compare actor (name, mbox/account)
  - Compare verb (id, display)
  - Compare object (id, definition type, name)
  - Compare result (score, success, completion)
  - Compare context (contextActivities, extensions)
  - Compare timestamp
  - Return `{"match": bool, "differences": [...]}`
- [ ] Handle JSON key ordering differences (use semantic comparison, not string equality)
- [ ] Handle minor serialization differences (e.g., float precision in scores)

### Task 4: Build verification test suite (AC1, AC2, AC3, AC4)
- [ ] Create `tests/integration/test_round_trip_recovery.py`
- [ ] Test: `test_single_statement_recovery` — pick one known statement, verify full round-trip
- [ ] Test: `test_recovery_per_persona` — recover at least one statement per persona:
  - Ayoub: recover a learning activity statement
  - Claire-student-1: recover an assessment statement (the failing math test)
  - Claire-student-2: recover a course activity statement
  - Fatima-child-1: recover a tutoring session statement
  - Fatima-child-2: recover an extracurricular statement
- [ ] Test: `test_batch_recovery` — recover a random sample of 50 statements, verify all match
- [ ] Test: `test_recovered_xapi_valid` — recovered statements pass xAPI validation
- [ ] Test: `test_comparison_detects_differences` — intentionally modify a recovered statement and verify comparison catches it

### Task 5: Create standalone verification script (AC4)
- [ ] Create `scripts/verify-round-trip.sh`:
  - Activates venv
  - Runs the integration test suite
  - Outputs summary: total tested, passed, failed
- [ ] Script should be runnable independently after pipeline + graph loading have completed
- [ ] Output structured JSON results:
  ```json
  {
    "event": "round_trip.verification.complete",
    "details": {
      "total_tested": N,
      "passed": M,
      "failed": K,
      "personas_verified": ["ayoub", "claire-student-1", ...],
      "sample_recovery_ms": 123
    }
  }
  ```

### Task 6: Write unit tests for recovery utilities (AC1, AC2)
- [ ] Create `tests/pipeline/test_recover_xapi.py`:
  - Test: `recover_xapi_from_triple` correctly follows provenance (mock Oxigraph + CSS responses)
  - Test: `compare_xapi_statements` returns match=true for identical statements
  - Test: `compare_xapi_statements` returns match=false with correct diff for modified statements
  - Test: recovery handles missing provenance gracefully (logs error, returns failure)
  - Test: recovery handles missing Pod resource gracefully (CSS returns 404)

## Dev Notes

### Architecture Context
- **This story proves FR10:** "The system can recover any original xAPI statement from the RDF graph (round-trip verification)"
- **The round-trip path is:** xAPI JSON -> oslo_mapper.py -> Turtle in Pod -> load_graph.py -> Oxigraph triples -> provenance link -> Pod resource -> original xAPI
- **This is a critical PoC deliverable:** The PRD Technical Success criteria requires "Any original statement recoverable"
- **Measurable Outcome from PRD:** "10K+ xAPI -> OSLO RDF in Oxigraph, provenance verified, any statement recoverable"

### Recovery Path Diagram
```
Oxigraph Triple
    |
    | SPARQL: SELECT ?podUri WHERE { <subject> prov:wasDerivedFrom ?podUri }
    v
Pod Resource URI (e.g., http://css:3000/ayoub/learning/assessment/stmt-uuid.ttl)
    |
    | HTTP GET with Accept: text/turtle
    v
Turtle Content (from CSS Pod)
    |
    | Parse RDF, extract pocpod0:originalXapi literal
    v
Original xAPI JSON (recovered)
    |
    | Compare with data/synthetic/ input
    v
Match/Mismatch Result
```

### Technical Constraints
- **Oxigraph SPARQL endpoint:** `http://localhost:7878/query` (outside Docker) or `http://oxigraph:7878/query` (inside Docker)
- **CSS endpoint:** `http://localhost:3000` (outside Docker) or `http://css:3000` (inside Docker)
- **Python naming:** `snake_case` modules/functions, `PascalCase` classes
- **Structured JSON logging to stdout**
- **Always activate venv** for Python commands
- **SPARQL variables:** `?camelCase` (e.g., `?podResourceUri`, `?subjectUri`)

### Key Dependency: Lossless Storage Mechanism
This story depends critically on HOW story 2-2 preserved the original xAPI data within the RDF representation. The expected mechanism is:
- A `pocpod0:originalXapi` property on the statement subject containing the serialized original xAPI JSON as an `xsd:string` literal
- If story 2-2 used a different approach, this story's recovery logic must adapt

**Before implementing:** Check how `pipeline/src/pocpod0_pipeline/oslo_mapper.py` (from story 2-2) stores the original xAPI data.

### Edge Cases to Handle
- Pod resource returns 404 (resource deleted or moved) — log error, mark as failed recovery
- Oxigraph has no provenance triple for a given subject — log warning, mark as failed
- Original xAPI in `data/synthetic/` not found for comparison — skip comparison, only verify recovery succeeds
- Multiple provenance links for same subject (shouldn't happen, but handle gracefully)
- Turtle parse errors on recovered content — log and mark as failed

### Isolation Notes
- Use `distrobox-host-exec` for accessing podman containers from within distrobox
- Both Oxigraph and CSS containers must be running for integration tests
- Unit tests should mock HTTP responses (no container dependency)

### Project Structure Notes

Files to create:
- `pipeline/src/pocpod0_pipeline/recover_xapi.py`
- `tests/integration/test_round_trip_recovery.py`
- `tests/pipeline/test_recover_xapi.py`
- `scripts/verify-round-trip.sh`

Directories to create (if not existing):
- `tests/integration/`

Files to modify:
- `pipeline/pyproject.toml` — add any new dependencies if needed

### Dependencies on Other Stories
- **Depends on Story 2-2:** Pipeline must have stored Turtle resources in CSS Pods with lossless xAPI preservation
- **Depends on Story 2-3:** Graph loader must have loaded triples into Oxigraph with provenance links
- **Depends on Story 1-1:** CSS and Oxigraph must be running in Docker
- **No downstream dependents** for this specific story — it is a verification/proof story

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` — Story 2.4 AC (line ~418-421, the FR10 round-trip part specifically)
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` — Decision DA-2 (Provenance & Traceability Schema), Data Flow diagram
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR10 (round-trip xAPI recovery), Technical Success ("Any original statement recoverable"), Measurable Outcomes table
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — story-2-4-round-trip-xapi-recovery-verification

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
