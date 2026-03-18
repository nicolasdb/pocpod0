# Story 1.5: Troll ACL Enforcement Validation

Status: ready-for-dev

## Story

As a **security reviewer** (funder audience),
I want the troll agent to adversarially test ACL enforcement by directly accessing the data infrastructure,
so that I have evidence that the sovereignty primitive actually enforces its access controls.

## Acceptance Criteria

**Given** pods are provisioned with role-based ACLs
**When** the troll agent attempts to read a pod resource without a valid ACL grant (direct HTTP to CSS)
**Then** the request is denied (HTTP 403)
**And** the test result is logged as `pass` in structured JSON format

**Given** pods with multi-role ACLs
**When** the troll agent attempts to access pod resources using each role's credentials against pods they should NOT have access to
**Then** all unauthorized access attempts are denied
**And** each test is logged with category `acl_enforcement`, access path `direct`, and result `pass` or `fail`

**Given** all ACL enforcement tests have executed
**When** the troll test suite completes
**Then** a summary is produced with pass/fail counts per test
**And** the troll's dual access pattern is established (direct infrastructure access verified, skill-mediated access deferred to Epic 2)

**Given** any ACL enforcement test fails
**When** the test result is `fail`
**Then** the failure is a blocking issue -- ACL enforcement must pass per NFR5

## Tasks / Subtasks

### Task 1: Troll Agent Directory & Module Scaffold (all ACs)
- [ ] Create `agents/troll-adversary/attacks/` directory if it does not exist
- [ ] Create `agents/troll-adversary/attacks/__init__.py`
- [ ] Create `agents/troll-adversary/attacks/acl_enforcement.py` (note: Python module uses snake_case, the architecture doc shows `acl-enforcement.py` with hyphens but Python imports require underscores -- use `acl_enforcement.py`)
- [ ] Create `agents/troll-adversary/report/` directory if it does not exist
- [ ] Create `agents/troll-adversary/report/__init__.py`

### Task 2: Troll Report Data Model (AC2, AC3)
- [ ] Define the troll test result dataclass/dict structure in `agents/troll-adversary/attacks/acl_enforcement.py`:
  ```python
  @dataclass
  class TrollTestResult:
      attack_category: str    # "acl_enforcement"
      access_path: str        # "direct"
      test_name: str          # e.g. "unauthorized-read-ayoub-pod-as-troll"
      result: str             # "pass" | "partial" | "fail"
      details: str            # human-readable explanation
      evidence: dict          # e.g. {"http_status": 403, "url": "...", "identity": "..."}
  ```
- [ ] This data model matches the troll report format from the architecture doc exactly:
  ```json
  {
    "attack_category": "acl_enforcement",
    "access_path": "direct",
    "test_name": "descriptive-test-name",
    "result": "pass|partial|fail",
    "details": "human-readable explanation",
    "evidence": {}
  }
  ```
- [ ] Create a helper function `log_test_result(result: TrollTestResult)` that outputs the result in structured JSON logging format

### Task 3: No-Credential Access Tests (AC1)
- [ ] Implement test function `test_unauthenticated_access()` in `acl_enforcement.py`
- [ ] For each pod (ayoub, claire-student-1, claire-student-2, fatima-child-1, fatima-child-2, school-community):
  - Send HTTP GET to `{CSS_BASE_URL}/{pod_name}/` with NO credentials/identity
  - Assert HTTP 401 or 403 response
  - Log result with `test_name: "unauthenticated-read-{pod_name}"`
  - If response is 200, log as `fail` with evidence including response status and body excerpt
  - If response is 401/403, log as `pass`
- [ ] Errors during the test (network errors, timeouts) are findings, not failures -- log them as `partial` with the error details

### Task 4: Cross-Role Unauthorized Access Tests (AC2)
- [ ] Implement test function `test_cross_role_unauthorized_access()` in `acl_enforcement.py`
- [ ] Define the expected access matrix (who should NOT have access to what):
  - `claire-teacher` should NOT have access to `fatima-child-1`, `fatima-child-2` pods
  - `fatima-parent` should NOT have access to `claire-student-1`, `claire-student-2` pods
  - `isabelle-policy` should NOT have direct individual read access (only aggregate)
  - `ayoub-student` should NOT have access to other students' pods
  - `troll-adversary` should NOT have access to any pod
- [ ] For each (identity, pod) pair in the unauthorized matrix:
  - Send HTTP GET to `{CSS_BASE_URL}/{pod_name}/` with the identity's credentials
  - Assert HTTP 403 response
  - Log each test individually with `test_name: "cross-role-{identity}-reads-{pod_name}"`
- [ ] Also test positive cases (authorized access returns 200) to validate the test harness is working correctly:
  - `claire-teacher` CAN read `claire-student-1` and `claire-student-2`
  - `fatima-parent` CAN read `fatima-child-1` and `fatima-child-2`
  - `ayoub-student` CAN read `ayoub`

### Task 5: Test Summary & Blocking Failure Detection (AC3, AC4)
- [ ] Implement `run_acl_enforcement_suite()` as the main entry point in `acl_enforcement.py`
- [ ] Runs all test functions in sequence, collecting `TrollTestResult` objects
- [ ] After all tests complete, produce a summary:
  ```json
  {
    "attack_category": "acl_enforcement",
    "total_tests": 25,
    "pass": 23,
    "partial": 1,
    "fail": 1,
    "blocking": true,
    "tests": [...]
  }
  ```
- [ ] If any test has `result: "fail"`, the summary `blocking` field is `true` (per NFR5: ACL enforcement MUST pass)
- [ ] Print the summary to stdout in structured JSON
- [ ] Return the summary and full results list for downstream consumption (by report generator in Epic 6)
- [ ] Establish the dual access pattern note in the summary: `"note": "Direct infrastructure access validated. Skill-mediated access deferred to Epic 2."`

### Task 6: Runner Script (all ACs)
- [ ] Create or extend `scripts/run-troll.sh` to invoke the ACL enforcement suite:
  ```bash
  #!/usr/bin/env bash
  # Activate venv and run troll ACL enforcement tests
  source .venv/bin/activate
  python -m agents.troll_adversary.attacks.acl_enforcement
  ```
- [ ] Alternatively, add a `__main__` block to `acl_enforcement.py` that calls `run_acl_enforcement_suite()`
- [ ] Ensure the script can be run from the project root
- [ ] Script exits with non-zero code if any test has `result: "fail"` (blocking)

### Task 7: Structured JSON Logging Integration (AC1, AC2)
- [ ] Every test execution logs in the architecture's structured JSON format:
  ```json
  {
    "timestamp": "2026-03-18T14:30:00Z",
    "service": "troll-adversary",
    "level": "INFO",
    "event": "acl_enforcement.test",
    "agent": "troll-adversary",
    "duration_ms": 45,
    "details": {
      "test_name": "unauthenticated-read-ayoub",
      "result": "pass",
      "http_status": 403,
      "target_pod": "ayoub"
    }
  }
  ```
- [ ] Use `level: "WARN"` for `partial` results, `level: "ERROR"` for `fail` results
- [ ] All logging goes to stdout -- docker-compose captures it for the dashboard (Epic 6)

### Task 8: Determinism Verification (NFR12)
- [ ] Ensure all tests are deterministic: same pods + same ACLs = same results every run
- [ ] No LLM calls in this test suite (ACL enforcement is infrastructure-level, not NL-based)
- [ ] No randomness in test ordering or test data
- [ ] Add a comment/docstring noting this is a deterministic infrastructure test per NFR12

## Dev Notes

### Architecture Decisions

- **FR28:** The troll agent tests ACL enforcement by directly accessing the data infrastructure. This means raw HTTP requests to CSS, bypassing any agent skill layer.
- **FR37 (Dual Access Model):** The troll has two access paths: direct infrastructure access (tested here) and through the shared SPARQL skill (deferred to Epic 2, Story 2.6). This story establishes the "direct" path pattern.
- **SEC-1 (No Real Auth):** Agent identity is configured, not authenticated. The troll simulates identities by using the same credential/token mechanism other agents use. There is no Solid-OIDC.
- **SEC-2 (ACL Enforcement at Two Levels):** This story validates Pod-level enforcement (CSS WebACL). Query-level enforcement (SPARQL skill) is Epic 2+.
- **NFR5:** ACL enforcement MUST pass. Any `fail` result is a blocking issue for the entire PoC.
- **NFR12:** Tests must be deterministic and reproducible. Identical inputs produce identical results.
- **Error Handling:** For the troll, errors are findings, not failures. If a network error occurs during a test, log it as a `partial` result with the error details. The test suite should never crash -- it always produces a report.

### This is the First Troll Story

This story establishes patterns that all subsequent troll stories (2.6, 3.x, 5.x) must follow:

1. **Test result format:** The `TrollTestResult` dataclass/dict is the canonical format for all troll test results across all attack categories.
2. **Logging pattern:** Structured JSON to stdout with `service: "troll-adversary"` and `agent: "troll-adversary"`.
3. **Summary format:** Per-category summary with pass/partial/fail counts and blocking flag.
4. **Error handling:** Errors are findings. The suite always completes and always produces a report.
5. **Dual access tagging:** Every test result has `access_path: "direct"` or `access_path: "through_skill"`.

Design the data model and helpers to be reusable. Later troll stories (sparql-injection, vector-privacy, cross-inference, deletion-timing) will import and reuse them.

### Python Module Naming

The architecture doc lists the file as `acl-enforcement.py` (hyphen-case for file naming). However, Python cannot import modules with hyphens. Use `acl_enforcement.py` (snake_case) as the actual filename. This is the one exception to the hyphen-case file naming convention -- Python module files use snake_case per the Python naming pattern in the architecture doc.

Similarly, if creating a package structure:
- Directory: `agents/troll-adversary/` (hyphen-case, matches agent naming convention)
- Python files within: `acl_enforcement.py`, `__init__.py` (snake_case)

### Agent Identity Simulation

Since there is no real authentication (SEC-1), the troll simulates identities. How identities are represented depends on how Story 1.3 configures CSS:

- If CSS uses simple token-based auth: the troll sends (or omits) the appropriate token header
- If CSS uses WebID: the troll uses (or omits) the appropriate WebID in requests
- The "no credential" test sends a bare HTTP GET with no auth headers at all

Check how Story 1.3 implemented identity -- the troll must use the same mechanism.

### CSS Access Details

- **CSS Docker image:** `communitysolidserver/community-solid-server:7`
- **CSS port:** 3000
- **CSS base URL (from host/distrobox):** Configurable via `CSS_BASE_URL` in `.env`, default `http://localhost:3000`
- **CSS base URL (from Docker network):** `http://community-solid-server:3000`
- **Use `distrobox-host-exec`** if running Python from within distrobox to reach podman containers

### Pod Names and Paths

The troll must test against all 6 pods:
- `ayoub` -- individual student pod
- `claire-student-1` -- individual student pod
- `claire-student-2` -- individual student pod
- `fatima-child-1` -- individual student pod
- `fatima-child-2` -- individual student pod
- `school-community` -- community pod

### Troll Report Format (from Architecture Doc)

Every individual test result must conform to:

```json
{
  "attack_category": "acl_enforcement",
  "access_path": "direct",
  "test_name": "descriptive-test-name",
  "result": "pass",
  "details": "CSS correctly denied unauthenticated read access to ayoub pod",
  "evidence": {
    "url": "http://community-solid-server:3000/ayoub/",
    "http_method": "GET",
    "http_status": 403,
    "identity": null,
    "expected_status": 403
  }
}
```

Result meanings:
- `pass` -- CSS correctly denied unauthorized access (403) or correctly allowed authorized access (200)
- `partial` -- test encountered an unexpected condition (e.g., network error, unexpected HTTP status)
- `fail` -- CSS allowed unauthorized access (200 when 403 expected) -- this is a BLOCKING issue

### Structured JSON Logging Format (from Architecture Doc)

```json
{
  "timestamp": "ISO-8601",
  "service": "troll-adversary",
  "level": "INFO|WARN|ERROR",
  "event": "acl_enforcement.test",
  "agent": "troll-adversary",
  "duration_ms": 123,
  "details": {}
}
```

### Project Structure Notes

**Files to create:**

- `agents/troll-adversary/attacks/__init__.py` -- Package init, export shared data model (`TrollTestResult`, `log_test_result`)
- `agents/troll-adversary/attacks/acl_enforcement.py` -- Main ACL enforcement test suite
- `agents/troll-adversary/report/__init__.py` -- Empty init for future report generator (Epic 6)

**Files to modify:**

- `scripts/run-troll.sh` -- Add invocation of ACL enforcement suite (create if not existing)

**Directories that must exist (create if needed):**

- `agents/troll-adversary/`
- `agents/troll-adversary/attacks/`
- `agents/troll-adversary/report/`

### Dependencies

- **Depends on Story 1.3:** Pods must be provisioned with role-based ACLs. The troll tests that those ACLs are actually enforced.
- **Depends on Story 1.4:** The grant/revoke functions from 1.4 establish ACL state that the troll validates. However, the troll can also run against the initial ACL state from 1.3 alone -- 1.4 dependency is soft.
- **Enables Story 2.6:** The troll data model and patterns established here are reused for SPARQL injection and vector privacy tests.
- **Enables Epic 6:** The test results feed into the comprehensive troll report (Story 6.1).

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` -- Story 1.5 acceptance criteria
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` -- SEC-1, SEC-2, FR28, FR37, troll report format, structured logging format, project structure, error handling patterns
- PRD: `_bmad-output/planning-artifacts/prd.md` -- FR28 (troll ACL test), FR37 (dual access model), NFR5 (ACL must pass), NFR12 (deterministic tests)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
