# Story 2.7: Troll SPARQL Injection Validation

Status: ready-for-dev

## Story

As a **security reviewer** (funder audience),
I want the troll agent to test SPARQL injection resistance through the parameterized query template mechanism,
so that I have evidence the data intelligence layer resists query manipulation attacks.

## Acceptance Criteria

**AC-1: Injection test suite exists**
Given the troll adversary attack module at `agents/troll-adversary/attacks/sparql-injection.py`
When the test suite is executed
Then it tests the parameterized `.rq` query templates in `agents/skills/sparql-query/templates/`
And each test sends injection payloads through the skill interface

**AC-2: Parameterized template testing**
Given parameterized SPARQL query templates (`.rq` files with `$parameter` placeholders)
When the troll injects malicious values into the parameter positions
Then the parameterized template mechanism blocks all injection attempts
And the template substitution never allows raw SPARQL to be injected into the query

**AC-3: Injection payload coverage**
Given the injection test suite
When it runs
Then it tests at minimum the following injection categories:
- SPARQL clause injection (`; DROP ALL`, `UNION SELECT`, `OPTIONAL { ... }`)
- String escape attacks (unmatched quotes, backslash sequences)
- URI injection (malicious URIs in parameter positions)
- Comment injection (`#` to truncate queries)
- FILTER injection (`FILTER(?x = "admin")`)
- Nested query injection (`{ SELECT ... }`)

**AC-4: Structured troll report output**
Given each injection test execution
When the test completes
Then a structured JSON report entry is emitted:
```json
{
  "attack_category": "sparql_injection",
  "access_path": "through_skill",
  "test_name": "descriptive-test-name",
  "result": "pass|fail",
  "details": "human-readable explanation",
  "evidence": { "payload": "...", "response": "...", "expected": "...", "actual": "..." }
}
```

**AC-5: Injection failure is blocking (NFR6)**
Given any SPARQL injection test
When the result is `fail` (injection succeeded)
Then this is a blocking issue per NFR6
And the test suite exits with non-zero status
And the failure is prominently logged

**AC-6: Tests are deterministic and reproducible (NFR12)**
Given the same Oxigraph state and the same injection payloads
When the test suite runs multiple times
Then it produces identical pass/fail results every time

**AC-7: Prepare template mechanism test logic independent of skill runtime**
Given that the shared SPARQL skill (Story 3-1) does not yet exist
When this story is implemented
Then the injection tests target the template parameterization mechanism directly
And the `.rq` template files and parameter substitution logic are testable standalone
And when the shared SPARQL skill is implemented (Story 3-1), these tests can be wired to run through the skill interface

## Tasks / Subtasks

### Task 1: Create injection test module (AC-1)
- [ ] Create `agents/troll-adversary/attacks/sparql-injection.py`
- [ ] Structure the module with:
  - `InjectionTestSuite` class containing all test cases
  - `run_all()` method that executes all injection tests and returns results
  - `InjectionTestResult` dataclass matching the report format (AC-4)

### Task 2: Create parameterized SPARQL template files (AC-2, AC-7)
- [ ] Create or verify `.rq` template files in `agents/skills/sparql-query/templates/`:
  - `student-progress.rq` — query with `$student_uri` and `$context_uri` parameters
  - `cross-context-query.rq` — query with `$agent_role` and `$pod_uri` parameters
  - `aggregate-anonymized.rq` — query with `$program_uri` and `$community_uri` parameters
  - `parental-view.rq` — query with `$parent_uri` and `$child_uri` parameters
  - `transfer-profile.rq` — query with `$student_uri` and `$school_uri` parameters
- [ ] Each template uses `$parameter` placeholders (NOT string concatenation)
- [ ] Templates must be valid SPARQL when parameters are substituted with clean values

### Task 3: Implement template parameterization engine (AC-2, AC-7)
- [ ] Create `agents/skills/sparql-query/parameterize.py` (or equivalent):
  - `load_template(template_name: str) -> str` — reads `.rq` file
  - `parameterize_query(template: str, params: dict[str, str]) -> str` — safe substitution
  - Safe substitution MUST:
    - Validate parameter values (no SPARQL keywords, no unescaped quotes, no semicolons)
    - Escape string values properly for SPARQL
    - Reject parameter values that contain injection patterns
    - Only substitute declared `$parameter` placeholders
  - This is the security boundary that SEC-3 requires
- [ ] This module is shared between the troll tests (this story) and the SPARQL skill (Story 3-1)

### Task 4: Implement injection payload library (AC-3)
- [ ] Create a catalog of injection payloads in the test module:
  ```python
  INJECTION_PAYLOADS = {
      "clause_injection": [
          "; DROP ALL",
          "} UNION { SELECT * WHERE { ?s ?p ?o } }",
          "OPTIONAL { ?secret <http://secret> ?value }",
      ],
      "string_escape": [
          'value" . ?s ?p ?o . FILTER(?o = "secret',
          "value\\",
          "value' ; --",
      ],
      "uri_injection": [
          "<http://evil.com> . ?s ?p ?o . <http://evil.com>",
          "http://evil.com> . OPTIONAL { ?s ?p ?o } . <http://x",
      ],
      "comment_injection": [
          "value # rest of query is commented out",
          "value\n# comment\n",
      ],
      "filter_injection": [
          'value" FILTER(true) . ?admin <http://role> "admin',
          "value FILTER(?role = <http://admin>)",
      ],
      "nested_query": [
          "{ SELECT * WHERE { ?s ?p ?o } }",
          "value } { SELECT * WHERE { ?s ?p ?o } } {",
      ],
  }
  ```

### Task 5: Implement injection test execution (AC-1, AC-2, AC-3)
- [ ] For each template file:
  - For each parameter in the template:
    - For each injection payload:
      - Substitute the injection payload as the parameter value
      - Attempt to parameterize the query using the engine (Task 3)
      - If the engine accepts the payload: attempt to execute against Oxigraph
      - A test PASSES if: the engine rejects the payload OR Oxigraph returns only expected results (no data leak)
      - A test FAILS if: the injection payload reaches Oxigraph AND returns unauthorized data
- [ ] Track results for each test case

### Task 6: Implement report generation (AC-4)
- [ ] Each test produces a JSON report entry with the exact schema from AC-4
- [ ] Aggregate results into a summary:
  ```json
  {
    "category": "sparql_injection",
    "total_tests": 42,
    "passed": 42,
    "failed": 0,
    "blocking": true
  }
  ```
- [ ] Write individual results to stdout as structured JSON logs
- [ ] Write summary to a report file: `agents/troll-adversary/report/sparql-injection-results.json`

### Task 7: Implement blocking failure behavior (AC-5)
- [ ] If any injection test fails:
  - Log at ERROR level with full evidence (payload, response, expected vs actual)
  - Set exit code to non-zero
  - Mark the overall suite result as `BLOCKING_FAILURE`
- [ ] This is per NFR6: injection resistance MUST pass

### Task 8: Write unit tests for parameterization engine (AC-2, AC-6)
- [ ] Create `agents/troll-adversary/tests/test_sparql_injection.py` (or colocate with attack module)
- [ ] Test that clean parameter values produce valid SPARQL
- [ ] Test that each injection payload category is rejected by the parameterization engine
- [ ] Test determinism: same inputs produce same results (NFR12)

### Task 9: Create runner script (AC-1)
- [ ] Create entry point to run the injection test suite:
  - Accept Oxigraph URL as argument (default: `http://oxigraph:7878`)
  - Accept template directory as argument (default: `agents/skills/sparql-query/templates/`)
  - Print summary to stdout
  - Exit with appropriate code (0 = all pass, 1 = failures)

## Dev Notes

### Security Architecture (SEC-3)

The defense against SPARQL injection is **parameterized query templates**. The `.rq` files contain `$parameter` placeholders that are substituted safely — never via string concatenation. The parameterization engine is the security boundary.

The troll tests this boundary by attempting to inject malicious SPARQL through parameter values. The test is "through_skill" access path because it tests the skill-level defense mechanism, even though the full skill runtime (Story 3-1) is not yet built.

### Shared SPARQL Skill Dependency Note

The shared SPARQL skill (Story 3-1, Epic 3) does not exist yet. This story creates:
1. The `.rq` template files (reused by Story 3-1)
2. The parameterization engine (reused by Story 3-1)
3. The injection test suite (can be re-run against the full skill later)

When Story 3-1 is implemented, it imports the parameterization engine from this story. The troll tests can then optionally be extended to test through the full skill HTTP interface.

### Troll Dual Access Model

For SPARQL injection, the troll uses `access_path: "through_skill"` — it tests the skill-level query sanitization boundary, not direct Oxigraph access. Direct Oxigraph access is a different attack category (ACL enforcement, Story 1-5).

### Troll Report Format (from Architecture)

```json
{
  "attack_category": "sparql_injection",
  "access_path": "through_skill",
  "test_name": "clause-injection-union-select",
  "result": "pass",
  "details": "UNION SELECT injection in student_uri parameter was rejected by parameterization engine",
  "evidence": {
    "template": "student-progress.rq",
    "parameter": "student_uri",
    "payload": "} UNION { SELECT * WHERE { ?s ?p ?o } }",
    "engine_response": "rejected: contains SPARQL keyword UNION",
    "oxigraph_reached": false
  }
}
```

### NFR6: Injection Resistance is BLOCKING

Unlike vector privacy (NFR8, non-blocking), SPARQL injection resistance MUST pass. A `fail` result means the parameterization engine has a vulnerability and must be fixed before proceeding.

### SPARQL Template Format

Templates use `$parameter` syntax (dollar-sign prefix):
```sparql
# student-progress.rq
PREFIX oslo-educ: <https://data.vlaanderen.be/ns/onderwijs#>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?activity ?result ?date WHERE {
  ?activity oslo-educ:betreft $student_uri .
  ?activity oslo-educ:resultaat ?result .
  ?activity oslo-educ:datum ?date .
  ?activity prov:wasDerivedFrom ?pod_resource .
}
ORDER BY DESC(?date)
```

### Structured Logging

All troll test events use the project logging format:
```json
{
  "timestamp": "ISO-8601",
  "service": "troll-adversary",
  "level": "INFO",
  "event": "injection_test.execute",
  "agent": "troll-adversary",
  "duration_ms": 12,
  "details": { "template": "student-progress.rq", "parameter": "student_uri", "payload_category": "clause_injection" }
}
```

### Python Environment

The troll attack scripts are Python. They need:
- `httpx` — for Oxigraph SPARQL queries
- `json` (stdlib) — for report generation
- No Qdrant dependency (that is Story 2-8)

Consider creating a `agents/troll-adversary/requirements.txt` or adding to the pipeline's `pyproject.toml`.

### Naming Conventions

- Attack module: `sparql-injection.py` (hyphen-separated per architecture doc file naming)
- Note: Python import requires underscore — if importing is needed, name it `sparql_injection.py` and use the hyphen name for the directory only
- Classes: `InjectionTestSuite`, `InjectionTestResult` (PascalCase)
- Functions: `run_injection_tests()`, `parameterize_query()` (snake_case)
- Test names in report: lowercase hyphen-separated (`clause-injection-union-select`)

### Distrobox Isolation Note

When running troll tests against Oxigraph, ensure the service is accessible. From distrobox:
```bash
distrobox-host-exec podman compose up oxigraph
# Then run tests from within distrobox, accessing Oxigraph at localhost:7878
```

### Project Structure Notes

**Files to create:**
- `agents/troll-adversary/attacks/sparql-injection.py` — injection test suite
- `agents/skills/sparql-query/parameterize.py` — template parameterization engine (shared with Story 3-1)
- `agents/skills/sparql-query/templates/student-progress.rq` — parameterized SPARQL template
- `agents/skills/sparql-query/templates/cross-context-query.rq`
- `agents/skills/sparql-query/templates/aggregate-anonymized.rq`
- `agents/skills/sparql-query/templates/parental-view.rq`
- `agents/skills/sparql-query/templates/transfer-profile.rq`
- `agents/troll-adversary/report/sparql-injection-results.json` — generated output (gitignored)

**Files to modify:**
- None required (new files only)

**Depends on:**
- Story 2-3: Oxigraph must be running with data loaded (needed for end-to-end injection tests)
- Story 1-1: Infrastructure services must be running

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: SEC-3, API-2, Troll Report Format, SPARQL Query Templates)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: FR29, NFR6 injection resistance, NFR12 reproducibility, Troll Attack Path Mapping)
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 2.6 acceptance criteria — SPARQL injection portion)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-2-7-troll-sparql-injection-validation`)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
