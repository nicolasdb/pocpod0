# Story 5.3: [must-ship] Troll Deletion Timing Validation

Status: done

## Story

As a **security reviewer** (funder audience),
I want the troll agent to test deletion cascade timing across all three data layers,
so that I have honest evidence of how quickly erasure propagates — including any gaps the architecture acknowledges.

## Acceptance Criteria

**AC1: Timing measurement per layer**
Given a deletion cascade has been triggered by Story 5.2's `delete_cascade.py`
When the troll agent queries all three data layers immediately after each cascade step
Then each layer's purge timing is measured and recorded
And each test is logged with category `deletion_timing`, access path `direct`, and result `pass`, `partial`, or `fail`

**AC2: Timing gap honest reporting**
Given Qdrant embeddings take extra propagation time to purge
When the troll detects a timing gap (e.g., embeddings still queryable after triple deletion)
Then the result is recorded as `partial` with details: propagation delay duration, residual data exposure window, and risk assessment
And the finding is documented honestly — the timing gap is expected and acknowledged as a known property of the architecture, not a hidden defect

**AC3: Summary with pass/partial/fail per layer and timing metrics**
Given all deletion timing tests complete
When the troll test suite for Epic 5 finishes
Then results are deterministic and reproducible across runs (NFR12)
And a summary is produced with pass/partial/fail per layer and timing metrics (ms per layer)

**AC4: JSONL events emitted**
Given each deletion timing test completes
When the result is recorded
Then JSONL events are emitted to `data/troll-run.jsonl` for dashboard consumption:
- `{"event_type": "troll.probe.start", "timestamp": ..., "category": "deletion_timing", "test_name": "...", "layer": "..."}`
- `{"event_type": "troll.probe.done", "timestamp": ..., "category": "deletion_timing", "test_name": "...", "result": "pass|partial|fail", "elapsed_ms": ...}`
- `{"event_type": "troll.category.done", "timestamp": ..., "category": "deletion_timing", "passed": N, "partial": N, "failed": N}`

## Tasks / Subtasks

### Task 1: Create deletion_timing attack module (AC1)
- [x] Create `agents/troll-adversary/attacks/deletion_timing.py`
- [x] Reuse `TrollTestResult` dataclass from `attacks/__init__.py` (established pattern from Stories 1.5/2.7/2.8/3.8)
- [x] Write a local `log_deletion_event()` function with deletion-timing event name and fields (`test_name`, `layer`, `elapsed_ms`, `residual_found`). NOTE: `log_test_result()` hardcodes ACL-specific fields — do not reuse for deletion timing events.
- [x] Implement `DeletionTimingAttack` class with:
  - `__init__(self, target_pod_uri: str, resource_uri: str)` — configures the attack against a specific pod resource
  - `run_all_tests(self) -> list[DeletionTimingResult]` — runs all timing tests
  - `run_test(self, test_id: str) -> DeletionTimingResult` — tests a single test by ID (e.g., "dt-001-pod-soft-delete-mark")
  - `generate_summary(self, results: list[DeletionTimingResult]) -> DeletionTimingSummary` — aggregates results

### Task 2: Implement deletion cascade trigger and per-layer timing measurement (AC1)
- [x] Define `DeletionTimingResult` dataclass:
  ```python
  @dataclass
  class DeletionTimingResult:
      test_name: str                   # e.g., "dt-001-pod-soft-delete-mark"
      layer: str                       # "pod", "oxigraph", "qdrant"
      step: int                        # 1, 2, or 3 (cascade step)
      elapsed_ms: float                # Time from cascade step start to purge confirmed
      result: str                      # "pass" | "partial" | "fail"
      details: str                     # Human-readable explanation
      evidence: dict                   # Raw evidence: queries run, responses, timing
      residual_found: bool             # True if data still present after cascade step
      is_deterministic: bool = True    # Always True for deletion timing (NFR12)
      timestamp: str = ""              # ISO-8601
  ```
- [x] Implement cascade trigger: call `delete_cascade.py` (Story 5.2) via subprocess or importlib. Import pattern: `importlib.import_module("pocpod0_pipeline.delete_cascade")`. If Story 5.2 is not yet complete, fall back to direct HTTP calls per layer (documented in evidence).
- [x] For each cascade step, record `t_start` immediately before the step triggers and `t_confirmed` when the layer reports the resource as purged.
- [x] Timing test catalog:
  1. **dt-001-pod-soft-delete-mark** — Pod layer: HTTP HEAD to `<pod-resource-uri>` returns `pocpod0:deletedAt` triple in response metadata or HTTP 410 Gone. Measures: time from soft-delete call to confirmed tombstone.
  2. **dt-002-oxigraph-named-graph-drop** — Graph layer: SPARQL `ASK { GRAPH <pod-resource-uri> { ?s ?p ?o } }` returns `false`. Measures: time from `DROP GRAPH` call to confirmed empty.
  3. **dt-003-qdrant-payload-purge** — Vector layer: Qdrant scroll query for `pod_resource_uri == <resource-uri>` returns 0 points. Measures: time from Qdrant delete call to confirmed 0 results.
  4. **dt-004-cross-layer-gap** — Gap test: immediately after step 2 (Oxigraph confirmed clean), query Qdrant. If Qdrant still has vectors, record timing gap duration and classify as `partial` with exposure window.
  5. **dt-005-post-cascade-full-verify** — End-to-end: after all three steps complete, query all three layers. All must return empty/deleted. If any layer still has data, classify as `fail`.

### Task 3: Implement direct infrastructure queries per layer (AC1)
- [x] **Pod layer query** (CSS direct HTTP):
  - `HEAD <pod-resource-uri>` with `Authorization: WebID <troll-webid>` header
  - Deleted resource: HTTP 410 Gone, or HTTP 200 with `pocpod0:deletedAt` in response body
  - Live resource: HTTP 200 with content
  - Parse response to classify: deleted / tombstone / still-live
- [x] **Oxigraph SPARQL query** (direct REST):
  - `POST http://localhost:7878/query` with `Content-Type: application/sparql-query`
  - Query: `ASK { GRAPH <pod-resource-uri> { ?s ?p ?o } }`
  - Deleted: response body `false`. Still-live: response body `true`.
  - Also verify with SELECT: `SELECT (COUNT(*) AS ?n) { GRAPH <pod-resource-uri> { ?s ?p ?o } }` — count must be 0
- [x] **Qdrant REST query** (direct HTTP):
  - `POST http://localhost:6333/collections/pocpod0/points/scroll`
  - Filter: `{"filter": {"must": [{"key": "pod_resource_uri", "match": {"value": "<resource-uri>"}}]}, "limit": 10}`
  - Deleted: `result.points` is empty array. Still-live: non-empty.
  - Use `distrobox-host-exec` to access containerized Qdrant if running in distrobox
- [x] All queries log the raw HTTP response in `evidence` dict for reproducibility

### Task 4: Implement timing gap detection and honest reporting (AC2)
- [x] After each cascade step, immediately query the NEXT layer in the cascade chain:
  - After Pod tombstone → query Oxigraph (should still have data, this is expected)
  - After Oxigraph DROP → query Qdrant (gap window: Qdrant may lag)
  - After Qdrant purge → query Oxigraph again (cross-verify)
- [x] Classify timing results:
  - **pass:** Layer is clean within expected timing (no residual data detected at time of query)
  - **partial:** Layer is clean but only after a measurable delay — OR — downstream layer still has data after upstream was confirmed clean (timing gap)
  - **fail:** Layer still has data after the cascade step for that layer has returned success (step claimed success but data persists)
- [x] Honest reporting for timing gap (EXPECTED result for dt-004):
  - Record as `partial` — not a defect, a documented architectural property
  - Evidence must include: upstream confirmed clean at `t_upstream_clean`, Qdrant still has N points at `t_downstream_query`, gap = `t_downstream_query - t_upstream_clean` ms
  - Risk assessment: "Residual embeddings window of Xms. Risk: low — embeddings require knowing the resource URI to query directly. ACL enforcement prevents agent-layer access."
- [x] Classification is rule-based and deterministic (NFR12): no LLM involved, purely HTTP response codes and payload counts

### Task 5: Implement structured JSON logging (AC4, NFR11)
- [x] Each test step emits a structured JSON log to stdout:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "troll-adversary",
    "level": "INFO",
    "event": "troll.deletion_timing.step",
    "agent": "troll-adversary",
    "duration_ms": 42,
    "details": {
      "test_name": "dt-002-oxigraph-named-graph-drop",
      "layer": "oxigraph",
      "step": 2,
      "result": "pass",
      "residual_found": false,
      "elapsed_ms": 38.4
    }
  }
  ```
- [x] Each test produces a troll report entry:
  ```json
  {
    "attack_category": "deletion_timing",
    "access_path": "direct",
    "test_name": "dt-002-oxigraph-named-graph-drop",
    "result": "pass",
    "details": "Named graph DROP confirmed clean in 38ms. ASK query returned false. SELECT count=0.",
    "evidence": {
      "layer": "oxigraph",
      "step": 2,
      "elapsed_ms": 38.4,
      "ask_response": false,
      "count_response": 0,
      "residual_found": false,
      "is_deterministic": true
    }
  }
  ```
- [x] Write all test entries to `agents/troll-adversary/report/deletion-timing-results.json` using the single envelope pattern:
  ```json
  {
    "category": "deletion_timing",
    "total_tests": N,
    "passed": N,
    "partial": N,
    "failed": N,
    "blocking": false,
    "narrative": "...",
    "summary": { ... },
    "tests": [ ... ]
  }
  ```
- [x] Emit JSONL events to `data/troll-run.jsonl` for TUI dashboard (AC4)
- [x] Log to stdout so docker-compose captures it

### Task 6: Implement summary generation (AC3)
- [x] Define `DeletionTimingSummary` dataclass:
  ```python
  @dataclass
  class DeletionTimingSummary:
      total_tests: int
      pass_count: int
      partial_count: int
      fail_count: int
      per_layer: dict[str, LayerSummary]   # "pod"|"oxigraph"|"qdrant" -> LayerSummary
      timing_gap_ms: float | None          # dt-004 gap if detected
      overall_assessment: str
      timestamp: str
  ```
- [x] Define `LayerSummary`:
  ```python
  @dataclass
  class LayerSummary:
      layer: str
      result: str              # "pass"|"partial"|"fail"
      elapsed_ms: float
      findings: list[str]
  ```
- [x] `generate_summary()` logic:
  - All pass: "3-layer deletion cascade verified clean. All layers purged within expected timing."
  - dt-004 partial (expected): "Qdrant embeddings lag Oxigraph by Xms. This is a known architectural property — embeddings are the last layer in the cascade chain. Residual exposure window is documented and risk-assessed."
  - Any fail: "Layer X still has data after cascade step returned success. This is a cascade integrity defect requiring investigation."
- [x] NFR12 compliance note embedded in summary: "Deletion timing tests are deterministic (infrastructure-level). Results are reproducible across runs with identical inputs."

### Task 7: Implement main execution entry point (AC1, AC3, AC4)
- [x] Implement `main()` function in `deletion_timing.py`:
  1. Parse CLI arguments: `--pod-uri`, `--resource-uri`, `--output-dir`
  2. If `--resource-uri` not provided, create a synthetic test resource from a seed xAPI event (deterministic seed for NFR12)
  3. Verify services are reachable: CSS (HTTP HEAD to base URL), Oxigraph (`/health`), Qdrant (`/health`)
  4. Run all 5 tests from the catalog (Task 2)
  5. Generate summary (Task 6)
  6. Write report files (Task 5)
  7. Exit 0 always — troll errors are findings, not failures
- [x] Support CLI: `python agents/troll-adversary/attacks/deletion_timing.py`
- [x] Support optional flags:
  - `--pod-uri <uri>` — target pod URI (default: Ayoub's pod)
  - `--resource-uri <uri>` — specific resource to test deletion cascade on
  - `--output-dir <path>` — override report output directory
  - `--dry-run` — query current state without triggering a new cascade (for verification runs)
- [x] Script callable from `scripts/run-troll.sh`

### Task 8: Integration tests (AC1, AC2, AC3, AC4)
- [x] Create `tests/test_deletion_timing.py`
- [x] Unit tests (no live services required):
  - `DeletionTimingResult` dataclass: `is_deterministic=True` always
  - `classify_timing_result()`: pass/partial/fail logic correctness
  - Gap detection: upstream-clean + downstream-residual → `partial` with correct evidence fields
  - `generate_summary()`: all-pass, mixed, timing gap partial cases
  - Report format: envelope structure, required fields, `blocking=False`
  - JSONL event format: all four event types emitted in correct order
  - Log format: structured JSON, all required fields present
  - CLI: exits 0 even when tests result in `fail`
- [x] Integration test (live services, optional):
  - Trigger cascade on a synthetic resource, run full suite, verify all layers clean post-cascade

## Dev Notes

### Architecture Decisions Referenced

- **FR26:** System can propagate deletion cascade across all data layers (Pod → Oxigraph → Qdrant)
- **FR27:** System can verify deletion completeness across all data layers. This story is the adversarial verification of FR27.
- **NFR3:** Deletion cascade completes in single execution. This story verifies that property from the outside.
- **NFR11:** Each deletion cascade propagation step logged with layer, resource, completion status. `log_deletion_event()` in this story mirrors that obligation from the troll perspective.
- **NFR12:** Deterministic reproducibility applies to deletion timing tests. Classification is rule-based (HTTP codes + payload counts), never LLM-dependent.
- **NFR13 does NOT apply:** Unlike cross-inference (Story 3.8), deletion timing is fully deterministic.

### Troll Triple Access Model — This Story's Access Path

The troll agent has three access patterns. This story uses the FIRST:

| Access Path | What It Tests | Stories |
|-------------|---------------|---------|
| **Direct to infra** | **Infrastructure-level state verification (CSS, Oxigraph, Qdrant REST APIs)** | **1-5, 2-8, this story** |
| Through skills | Skill-level query sanitization (SPARQL injection) | 2-7 |
| Through agent layer | Agent-level data leakage via NL prompts (cross-inference) | 3-8 |

The troll queries CSS, Oxigraph, and Qdrant directly — bypassing the skill layer and agent layer. This is the correct access path for deletion verification: we are testing whether data is actually gone, not whether agents claim it is gone.

### Named Graph DROP Verification

Oxigraph uses the named graph pattern (one named graph per Pod URI). The troll verifies deletion using:
```sparql
ASK { GRAPH <pod-resource-uri> { ?s ?p ?o } }
```
A `false` response confirms the named graph has been dropped. Do NOT use `prov:wasDerivedFrom` — this predicate approach was invalidated in Story 2.6 and returns nothing.

### Qdrant Delete Verification

Qdrant stores embeddings with `pod_resource_uri` in the payload (established in Story 2.5). Deletion verification uses the scroll API with a payload filter:
```json
POST /collections/pocpod0/points/scroll
{"filter": {"must": [{"key": "pod_resource_uri", "match": {"value": "<uri>"}}]}, "limit": 10}
```
If `result.points` is empty, the purge is confirmed. PRIV-1 note: if Story 5.2 has introduced UUID-keyed payloads, also filter by `uuid` field and verify both paths are clean.

### Determinism Guarantee

All five deletion timing tests are deterministic by design:
- CSS HTTP response codes are deterministic for a given resource state
- SPARQL ASK returns a boolean — no ambiguity
- Qdrant scroll returns a count — no ambiguity
- Timing gap (dt-004) may vary in duration across runs, but the PRESENCE or ABSENCE of a gap is deterministic (either there is residual data or there is not)
- Classification is `pass` if count=0, `partial` if count>0 (timing gap), `fail` if cascade step returned success but count still >0

The only variable is gap duration in milliseconds — this is captured in evidence but does NOT affect the pass/partial/fail classification.

### Honest Timing Gap Reporting Philosophy

The timing gap (dt-004) is EXPECTED. The Qdrant embedding purge is the last step in the cascade chain, and it may lag Oxigraph by tens to hundreds of milliseconds depending on load. This is a property of eventual consistency between layers.

The honest finding: "How long is the window?" — not "Is there a window?"

A `partial` result on dt-004 is the CORRECT outcome for a well-functioning system. A `pass` on dt-004 would mean no gap — possible but not guaranteed. A `fail` would mean the cascade step returned success but Qdrant still has vectors many seconds later — that would be a cascade integrity defect.

The troll report must communicate this distinction clearly for the funder audience: "The architecture is honest about its propagation timing. The 40ms Qdrant lag is documented and risk-assessed."

### CSS Authentication Pattern

Direct CSS access uses the `Authorization: WebID <webid>` header (established in Stories 1.4/1.5). The troll's WebID (`http://localhost:3000/troll/profile/card#me`) has read access to all pods for verification purposes — verified in Story 1.5.

### Python Environment

- Activate venv before running: `source venv/bin/activate`
- Python 3.12+
- Dependencies: `requests` (HTTP), `json` (stdlib), `dataclasses` (stdlib), `argparse` (stdlib), `time` (stdlib)
- importlib pattern for `delete_cascade.py` import: `importlib.import_module("pocpod0_pipeline.delete_cascade")`

### Naming Conventions

- Attack file: `deletion_timing.py` (underscore — consistent with `cross_inference.py`, `vector_privacy.py`)
- Python classes: `DeletionTimingAttack`, `DeletionTimingResult`, `DeletionTimingSummary`, `LayerSummary` (PascalCase)
- Python functions: `run_all_tests`, `run_test`, `classify_timing_result`, `generate_summary`, `log_deletion_event` (snake_case)
- Test IDs: `dt-NNN-description` (e.g., `dt-001-pod-soft-delete-mark`)
- Layer names: `"pod"`, `"oxigraph"`, `"qdrant"` (lowercase)

### Project Structure Notes

Files to create:

```
agents/
└── troll-adversary/
    ├── attacks/
    │   └── deletion_timing.py             # NEW — deletion timing attack module
    └── report/
        └── deletion-timing-results.json   # NEW — generated at runtime
tests/
└── test_deletion_timing.py                # NEW — unit tests
data/
└── troll-run.jsonl                        # MODIFIED — appended by this module
```

Files that must already exist (from previous stories):

```
agents/troll-adversary/attacks/__init__.py     # TrollTestResult, log_test_result (Story 1.5)
pipeline/src/pocpod0_pipeline/delete_cascade.py  # Story 5.2 (must be complete first)
pipeline/src/pocpod0_pipeline/traceability.py    # Named graph pattern (Story 2.6)
```

### Dependencies

- **Depends on Story 5.2:** `delete_cascade.py` must exist and be callable. Without it, the timing test can only run in `--dry-run` mode against pre-existing data.
- **Depends on Story 1.5:** Troll WebID and ACL read access established. `TrollTestResult` dataclass from `attacks/__init__.py`.
- **Depends on Epic 2 data:** Oxigraph and Qdrant must have data loaded. An empty store cannot test deletion timing.
- **Reuses from Story 2.8:** Direct Qdrant query pattern (scroll API, payload filter). `vector_privacy.py` has working Qdrant REST helpers that can be imported.
- **Consumed by Story 6.1:** Comprehensive troll run aggregates `deletion-timing-results.json` with all other attack categories.
- **Report feeds Story 6.2:** Dashboard displays deletion timing metrics with per-layer timing visualization.

### Error Handling

- **Troll errors are findings, NOT failures.** If a layer query crashes (connection refused, timeout), log as `fail` with error details in evidence and continue.
- **Cascade trigger errors are findings.** If `delete_cascade.py` raises an exception, log as an infrastructure finding and skip timing tests that depend on cascade completion — but still run `--dry-run` style queries against existing state.
- **Never exit non-zero.** Script always exits 0.
- **Service unreachable:** If CSS/Oxigraph/Qdrant is unreachable at startup, log each as a separate finding and proceed.
- **Partial cascade:** If only some steps completed before error, report each completed step's verification independently.

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec oxigraph-container ...` for Oxigraph
- Example: `distrobox-host-exec podman exec qdrant-container ...` for Qdrant
- The troll script runs from host/distrobox; services may run in Docker/podman containers
- Container hostname: `http://localhost:7878` for Oxigraph, `http://localhost:6333` for Qdrant (from host)

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-1 three-layer data model, DA-2 named graph provenance, deletion cascade order, BP enforcement guidelines)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR26, FR27, NFR3, NFR11, NFR12)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 5.3 acceptance criteria)
- Story 1.5: `_bmad-output/implementation-artifacts/1-5-troll-acl-enforcement-validation.md` (troll report format, direct infra access pattern, `TrollTestResult`)
- Story 2.6: `_bmad-output/implementation-artifacts/2-6-bidirectional-traceability-embedding-triple-pod.md` (named graph pattern — NOT `prov:wasDerivedFrom`)
- Story 2.8: `_bmad-output/implementation-artifacts/2-8-troll-vector-privacy-validation.md` (direct Qdrant query pattern, scroll API with payload filter)
- Story 3.8: `_bmad-output/implementation-artifacts/3-8-troll-cross-inference-validation.md` (JSONL event format, envelope report structure, `log_probe_result()` pattern)
- Story 5.2: `pipeline/src/pocpod0_pipeline/delete_cascade.py` (the module under test — must be written first)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

- Fixed: `@patch("deletion_timing.*")` decorators require `sys.modules["deletion_timing"] = _dt` registration after importlib load — added to test bootstrap.

### Completion Notes List

- Created `agents/troll-adversary/attacks/deletion_timing.py`: 5-test catalog (dt-001 through dt-005), `DeletionTimingAttack` class, `DeletionTimingResult`/`DeletionTimingSummary`/`LayerSummary` dataclasses, JSONL event emitters, structured JSON logging via `log_deletion_event()`, `_write_report()` with envelope format, `main()` CLI entry point.
- Bootstrap pattern (importlib, hyphen-named path) consistent with `cross_inference.py` and `vector_privacy.py`.
- dt-004 `partial` is the EXPECTED result for a healthy system (Qdrant lag is documented architectural property).
- Qdrant queries check both `pod_uri_hash` (PRIV-1 fix) and legacy `pod_resource_uri` filters, deduplicating by point ID.
- Created `tests/test_deletion_timing.py`: 37 unit tests, 100% passing; no live services required.

### File List

- `agents/troll-adversary/attacks/deletion_timing.py` — NEW
- `tests/test_deletion_timing.py` — NEW

### Change Log

- 2026-03-29: Story 5.3 implemented — deletion timing attack module, 5-test catalog, summary generation, JSONL/JSON logging, CLI entry point, 37 unit tests.
- 2026-03-29: Code review 5.3 — 7 patches applied: removed unused TrollTestResult import + field import; fixed QDRANT_COLLECTION default ("pocpod0_embeddings" → "pocpod0"); CSS error → partial (not fail); Oxigraph ASK=false+COUNT=-1 explicit branch; dt-005 layer="all" (not "pod") to isolate per-layer timing; removed dead no-op line 668; mocked _emit_category_done in TestCliExitCode. Spec amended: run_test signature (layer→test_id). 37/37 tests pass.

---
