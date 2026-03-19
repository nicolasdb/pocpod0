# Story 2.8: Troll Vector Privacy Validation

Status: ready-for-dev

## Story

As a **security reviewer** (funder audience),
I want the troll agent to test vector store privacy by directly querying Qdrant with semantic similarity searches designed to extract PII from embeddings,
so that I have an honest assessment of whether embeddings leak personally identifiable information.

## Acceptance Criteria

**AC-1: Vector privacy test suite exists**
Given the troll adversary attack module at `agents/troll-adversary/attacks/vector-privacy.py`
When the test suite is executed
Then it directly queries Qdrant's REST API at port 6333 (bypasses any skill layer)
And each test attempts to extract PII through semantic similarity searches

**AC-2: Direct Qdrant access (bypasses skill)**
Given the troll agent's dual access model
When the vector privacy tests run
Then they connect directly to `http://qdrant:6333` (or `http://localhost:6333` from host)
And they do NOT use the shared Qdrant skill — access_path is `direct`
And this tests infrastructure-level privacy, not skill-level boundaries

**AC-3: PII extraction attack coverage**
Given the vector privacy test suite
When it runs
Then it tests at minimum the following attack categories:
- **Name extraction:** semantic search with queries like "student named [name]", "who is the student"
- **Identity correlation:** search with known facts to find related embeddings about the same person
- **Location/school extraction:** queries targeting institutional or geographic information
- **Grade/assessment extraction:** queries targeting specific learning outcomes or scores
- **Cross-person correlation:** similarity searches between embeddings of different students to detect data leakage across pod boundaries
- **Embedding inversion:** attempts to reconstruct input text from embedding vectors (mathematical approaches)

**AC-4: Structured troll report output**
Given each vector privacy test execution
When the test completes
Then a structured JSON report entry is emitted:
```json
{
  "attack_category": "vector_privacy",
  "access_path": "direct",
  "test_name": "descriptive-test-name",
  "result": "pass|partial|fail",
  "details": "human-readable explanation",
  "evidence": {
    "query": "...",
    "top_k_results": [...],
    "pii_detected": true|false,
    "pii_type": "name|location|grade|identity|null",
    "confidence": 0.0-1.0
  }
}
```

**AC-5: Findings are non-blocking (NFR8)**
Given any vector privacy test
When the result is `partial` or `fail`
Then this is an assessment finding, NOT a blocking issue
And the finding is documented honestly with full evidence
And the test suite continues running all remaining tests
And the exit code is 0 (success) regardless of findings

**AC-6: Tests are deterministic and reproducible (NFR12)**
Given the same Qdrant embeddings and the same attack queries
When the test suite runs multiple times
Then it produces identical results every time
And similarity scores are deterministic for identical vector queries

**AC-7: Summary report with honest assessment**
Given all vector privacy tests complete
When the test suite finishes
Then a summary report is generated with:
- Total tests run, pass/partial/fail counts
- Per-attack-category breakdown
- Honest narrative: what defenses hold, what risks exist, what mitigations are recommended
- Written for a non-technical reader (FR34)

## Tasks / Subtasks

### Task 1: Create vector privacy test module (AC-1)
- [ ] Create `agents/troll-adversary/attacks/vector-privacy.py`
- [ ] Import `TrollTestResult` and `log_test_result()` from `agents/troll-adversary/attacks/__init__.py` — do NOT define a new dataclass; reuse the shared troll reporting infrastructure from Story 1.5
- [ ] Structure the module with:
  - `VectorPrivacyTestSuite` class containing all test cases
  - `run_all(qdrant_url: str) -> VectorPrivacyReport` method using `TrollTestResult` for individual results
- [ ] Add a **preflight check** before running any privacy tests: verify Qdrant is reachable, the `pocpod0_embeddings` collection exists, and it contains points. If preflight fails, abort with a clear error.

### Task 2: Implement Qdrant direct access client (AC-2)
- [ ] Use `httpx` or `qdrant-client` to connect directly to Qdrant REST API
- [ ] Connect to `http://qdrant:6333` (Docker network) or configurable URL
- [ ] Collection name: must match what Story 2-5 created (e.g., `pocpod0_embeddings`)
- [ ] Operations needed:
  - `search` — similarity search with a query vector
  - `scroll` — iterate through points to inspect payloads
  - `get_collection` — verify collection exists and get metadata
- [ ] The troll needs its own embedding capability to generate query vectors:
  - Use the same OpenRouter API (`qwen/qwen3-embedding-8b`) to embed attack queries
  - Read `OPENROUTER_API_KEY` from environment

### Task 3: Implement PII extraction attacks — name extraction (AC-3)
- [ ] Generate query embeddings for name-related prompts:
  - "student named Ayoub"
  - "personal information about the student"
  - "who is the learner in this data"
  - "full name of the student"
- [ ] Search Qdrant with each query embedding (top-k = 10)
- [ ] Analyze returned payloads and associated triples for PII content
- [ ] Score: `pass` if no PII in results, `partial` if PII exists but requires multi-step inference, `fail` if PII is directly exposed

### Task 4: Implement PII extraction attacks — identity correlation (AC-3)
- [ ] Given a known fact (e.g., "student who attends tutoring at location X"):
  - Embed the fact as a query
  - Search Qdrant for similar embeddings
  - Check if results allow correlating to a specific individual
- [ ] Test whether combining multiple non-PII queries can build an identity profile
- [ ] Score: `pass` if correlation fails, `partial` if weak correlation, `fail` if identity reconstructed

### Task 5: Implement PII extraction attacks — location/school extraction (AC-3)
- [ ] Queries targeting geographic/institutional data:
  - "which school does the student attend"
  - "students in Brussels Flemish school"
  - "learning activities at [specific location]"
- [ ] Check if similarity results expose institution names, locations, or addresses
- [ ] Score results per the pass/partial/fail scale

### Task 6: Implement PII extraction attacks — grade/assessment extraction (AC-3)
- [ ] Queries targeting learning outcomes:
  - "student failing mathematics"
  - "assessment results for quadratic equations"
  - "learning difficulties in math"
- [ ] Check if similarity results expose specific grades, scores, or assessment details linked to identifiable individuals
- [ ] Score results per the pass/partial/fail scale

### Task 7: Implement PII extraction attacks — cross-person correlation (AC-3)
- [ ] For each pair of known student pod URIs:
  - Retrieve embeddings for student A (via `pod_resource_uri` payload filter)
  - Search Qdrant using student A's embeddings as queries
  - Check if results return student B's data (cross-pod leakage)
- [ ] This tests whether embedding similarity creates unintended cross-student data bridges
- [ ] Score: `pass` if no cross-pod leakage, `partial` if weak correlation, `fail` if direct leakage

### Task 8: Implement PII extraction attacks — embedding inversion (AC-3)
- [ ] Attempt basic embedding inversion techniques:
  - Check if embedding vectors cluster in ways that reveal input text patterns
  - Compare embedding distances for known-similar vs known-different content
  - Note: full mathematical inversion of qwen3-embedding-8b is likely infeasible; document this honestly
- [ ] This category is expected to produce `partial` or `pass` — the point is honest assessment
- [ ] Score based on whether any meaningful text can be recovered from vectors alone

### Task 9: Implement PII detection in results (AC-3, AC-4)
- [ ] Create a PII detection helper:
  - Check returned Qdrant payloads for known PII patterns (names, locations from synthetic data)
  - Optionally follow `triple_uris` to Oxigraph to inspect actual triple content
  - Flag any result that contains or strongly implies personally identifiable information
- [ ] The synthetic data includes known names (Ayoub, Claire's students, Fatima's children) — use these as ground truth for PII detection
- [ ] Return structured evidence with PII type and confidence

### Task 10: Implement report generation (AC-4, AC-7)
- [ ] Each test produces a JSON report entry with the exact schema from AC-4
- [ ] Aggregate results into a summary report:
  ```json
  {
    "category": "vector_privacy",
    "total_tests": 24,
    "passed": 18,
    "partial": 4,
    "failed": 2,
    "blocking": false,
    "narrative": "Embedding-level privacy assessment: direct name extraction blocked (6/6 pass). Identity correlation shows weak signal in 2/4 cases (partial). Cross-person correlation clean (4/4 pass). Recommendation: monitor embedding model output for PII leakage in production deployment."
  }
  ```
- [ ] Write individual results to stdout as structured JSON logs
- [ ] Write summary to `agents/troll-adversary/report/vector-privacy-results.json`
- [ ] The narrative must be readable by a non-technical reviewer (FR34)

### Task 11: Implement non-blocking exit behavior (AC-5)
- [ ] The test suite always exits with code 0 (success) regardless of findings
- [ ] `partial` and `fail` results are assessment findings, logged at WARN level
- [ ] The summary report clearly distinguishes between:
  - Infrastructure defenses that held (pass)
  - Areas needing further investigation (partial)
  - Confirmed privacy risks (fail) — documented as investment recommendations, not blockers

### Task 12: Write unit tests (AC-6)
- [ ] Create `agents/troll-adversary/tests/test_vector_privacy.py` (or colocate)
- [ ] Test PII detection helper with known PII and non-PII content
- [ ] Test report generation format
- [ ] Test that results are deterministic for the same inputs (NFR12)

## Dev Notes

### Shared Troll Infrastructure (CRITICAL)

Import and reuse from `agents/troll-adversary/attacks/__init__.py`:
- `TrollTestResult` dataclass — the shared result type across all troll stories (1.5, 2.7, 2.8, 3.8, 5.3)
- `log_test_result()` — shared structured logging function

Do NOT define `VectorPrivacyTestResult` or any local dataclass — this breaks result aggregation across epics. The `result` field accepts `"pass"`, `"partial"`, `"fail"` — all three are valid for vector privacy (NFR8 non-blocking).

### Troll Dual Access Model — Direct Access

For vector privacy, the troll uses `access_path: "direct"` — it connects directly to Qdrant's REST API, bypassing the shared Qdrant skill entirely. This tests infrastructure-level privacy: can raw Qdrant queries extract PII from embeddings?

This is different from SPARQL injection (Story 2-7) which uses `access_path: "through_skill"`.

### Honest Assessment Philosophy (NFR8)

Vector privacy is a **probabilistic** attack surface. Unlike SPARQL injection (which must pass), vector privacy findings are:
- **Informational**: they tell the funder where the architecture is strong and where investment is needed
- **Non-blocking**: partial/fail results do NOT stop the PoC
- **Trust-building**: honest acknowledgment of limitations is the funder trust mechanism

From the PRD: "Graceful failure acknowledgment is the trust-building mechanism: partial/fail ratings are the investment thesis for the next phase."

### Qdrant REST API Reference

**Search endpoint:**
```
POST http://qdrant:6333/collections/{collection_name}/points/search
{
  "vector": [0.1, 0.2, ...],
  "limit": 10,
  "with_payload": true
}
```

**Scroll endpoint (iterate all points):**
```
POST http://qdrant:6333/collections/{collection_name}/points/scroll
{
  "limit": 100,
  "with_payload": true,
  "with_vectors": false
}
```

**Filter by payload:**
```
POST http://qdrant:6333/collections/{collection_name}/points/scroll
{
  "filter": {
    "must": [
      { "key": "pod_resource_uri", "match": { "value": "http://..." } }
    ]
  },
  "limit": 100,
  "with_payload": true
}
```

### Embedding Generation for Attack Queries

The troll needs to generate its own embeddings to perform similarity searches. It uses the same model (`qwen/qwen3-embedding-8b` via OpenRouter) as the pipeline. This is by design — the troll uses the same embedding space to test whether semantically similar queries can extract PII.

```python
# Generate attack query embedding
response = httpx.post(
    "https://openrouter.ai/api/v1/embeddings",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": "qwen/qwen3-embedding-8b", "input": "student named Ayoub"}
)
query_vector = response.json()["data"][0]["embedding"]
```

### Known Synthetic Data Names (Ground Truth for PII Detection)

From the PRD and architecture docs, the synthetic dataset includes:
- **Students:** Ayoub, Lucas and Emma (Claire's students), Youssef and Nour (Fatima's children)
- **Parents:** Fatima
- **Teachers:** Claire
- **Administrators:** Marc
- **Schools:** Brussels Flemish school, Liege Wallonia school
- **Locations:** Brussels, Liege

Use these as known PII targets when scoring attack results.

### Structured Logging

All troll test events use the project logging format:
```json
{
  "timestamp": "ISO-8601",
  "service": "troll-adversary",
  "level": "WARN",
  "event": "vector_privacy.finding",
  "agent": "troll-adversary",
  "duration_ms": 340,
  "details": {
    "test_name": "name-extraction-direct-query",
    "result": "partial",
    "pii_type": "name",
    "confidence": 0.6
  }
}
```

### Python Dependencies

- `httpx` — for Qdrant REST API and OpenRouter API calls
- `qdrant-client` — optional, can use raw REST instead for explicit direct access
- `json` (stdlib) — for report generation

Consider creating `agents/troll-adversary/requirements.txt`:
```
httpx>=0.27.0
qdrant-client>=1.9.0
```

### Naming Conventions

- Attack module: `vector-privacy.py` (hyphen-separated per file naming convention)
- Note on Python imports: if the module needs to be imported, use `vector_privacy.py` (underscore)
- Classes: `VectorPrivacyTestSuite`, `VectorPrivacyTestResult` (PascalCase)
- Functions: `run_privacy_tests()`, `detect_pii()`, `generate_attack_embedding()` (snake_case)
- Test names in report: lowercase hyphen-separated (`name-extraction-direct-query`)

### Distrobox Isolation Note

When running troll tests against Qdrant, ensure the service is accessible. From distrobox:
```bash
distrobox-host-exec podman compose up qdrant
# Then run tests from within distrobox, accessing Qdrant at localhost:6333
```

### Project Structure Notes

**Files to create:**
- `agents/troll-adversary/attacks/vector-privacy.py` — vector privacy test suite
- `agents/troll-adversary/report/vector-privacy-results.json` — generated output (gitignored)
- `agents/troll-adversary/requirements.txt` — Python dependencies for troll agent (if not already created by Story 2-7)

**Files to modify:**
- None required (new files only)

**Depends on:**
- Story 2-5: Qdrant must have embeddings loaded with payload metadata (`triple_uris`, `pod_resource_uri`)
- Story 1-1: Qdrant service must be running and healthy

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: API-2, API-3, Troll Report Format, Error Handling — troll errors are findings)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: FR31, NFR8 probabilistic surfaces, FR34 non-technical readability, Troll Attack Path Mapping)
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 2.6 acceptance criteria — vector privacy portion)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-2-8-troll-vector-privacy-validation`)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
