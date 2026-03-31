# Story 6.1: Troll Comprehensive Run & Categorized Report

Status: ready-for-dev

## Story

As a **funder** (investment decision-maker),
I want a comprehensive adversarial test run across all 5 attack categories with a categorized report generated for review,
so that I see exactly where the architecture holds, where it needs investment, and can make an informed funding decision.

## Acceptance Criteria

1. **AC1: Orchestrator runs all 5 attack categories**
   - **Given** all services are running (CSS, Oxigraph, Qdrant, OpenClaw) and pipeline data is loaded
   - **When** `scripts/run-troll.sh` executes
   - **Then** all 5 attack categories run in sequence: `acl_enforcement`, `sparql_injection`, `vector_privacy`, `cross_inference`, `deletion_timing`
   - **And** each category emits JSONL events to `data/troll-run.jsonl` (`troll.probe.start`, `troll.probe.done`, `troll.category.done`)
   - **And** the orchestrator exits non-zero only if a **blocking** category fails (ACL enforcement or SPARQL injection per NFR5/NFR6)

2. **AC2: Categorized report generated**
   - **Given** all 5 attack categories have completed
   - **When** the report generator runs
   - **Then** a unified report JSON is produced at `agents/troll-adversary/report/comprehensive-results.json`
   - **And** the report contains: per-category summary (pass/partial/fail counts, blocking flag), individual test results with `{attack_category, access_path, test_name, result, details, evidence}`, overall assessment narrative, timestamp
   - **And** per-category JSON files are also produced (existing pattern: `sparql-injection-results.json`, etc.)

3. **AC3: Human-readable markdown report**
   - **Given** the comprehensive JSON results exist
   - **When** the report generator completes
   - **Then** a markdown report is produced at `agents/troll-adversary/report/troll-report.md`
   - **And** it is readable by a non-technical reviewer (FR34)
   - **And** partial/fail results are presented as investment opportunities, not hidden failures
   - **And** it includes: executive summary, per-category sections with pass/partial/fail ratings, explanations, and evidence highlights

4. **AC4: JSONL event stream for dashboard**
   - **Given** the troll run is in progress
   - **When** each probe starts and completes
   - **Then** events are emitted to `data/troll-run.jsonl` in the canonical format:
     ```json
     {"event_type": "troll.probe.start", "timestamp": "...", "category": "...", "test_name": "...", ...}
     {"event_type": "troll.probe.done", "timestamp": "...", "category": "...", "test_name": "...", "result": "pass|partial|fail", ...}
     {"event_type": "troll.category.done", "timestamp": "...", "category": "...", "passed": N, "partial": N, "failed": N}
     ```
   - **And** a `troll.run.start` event is emitted at the beginning with the list of categories
   - **And** a `troll.run.done` event is emitted at the end with the overall summary

5. **AC5: Results consistent with individual troll tests**
   - **Given** the comprehensive run exercises the same test suites as Stories 1.5, 2.7, 2.8, 3.8, 5.3
   - **When** compared to individual runs
   - **Then** results are consistent — no tests are added, removed, or modified

## Tasks / Subtasks

- [ ] Task 1: Create troll orchestrator module (AC: 1, 4)
  - [ ] 1.1: New file `agents/troll-adversary/attacks/run_comprehensive.py` — imports and invokes all 5 attack category entry points in sequence
  - [ ] 1.2: Emit `troll.run.start` and `troll.run.done` wrapper events to `data/troll-run.jsonl`
  - [ ] 1.3: Truncate `data/troll-run.jsonl` at start of comprehensive run (same pattern as `run_pipeline.py` truncates `pipeline-run.jsonl`)
  - [ ] 1.4: Collect all results into unified data structure
  - [ ] 1.5: Exit non-zero only if blocking categories (ACL, SPARQL) have failures
- [ ] Task 2: Create report generator (AC: 2, 3)
  - [ ] 2.1: New file `agents/troll-adversary/report/generator.py` — takes unified results, produces JSON + markdown
  - [ ] 2.2: JSON report: `comprehensive-results.json` with per-category summaries and all individual test results
  - [ ] 2.3: Markdown report: `troll-report.md` with executive summary, per-category sections, funder-friendly language
  - [ ] 2.4: Use existing `TrollTestResult` canonical format from `attacks/__init__.py`
- [ ] Task 3: Update `scripts/run-troll.sh` (AC: 1)
  - [ ] 3.1: Replace single `acl_enforcement.py` call with `run_comprehensive.py`
  - [ ] 3.2: Preserve env var handling and venv activation
- [ ] Task 4: Tests (AC: 1-5)
  - [ ] 4.1: Unit test for orchestrator — mock all 5 attack modules, verify invocation order and result aggregation
  - [ ] 4.2: Unit test for report generator — verify JSON structure and markdown output
  - [ ] 4.3: Verify JSONL event format matches canonical spec

## Dev Notes

### Architecture Compliance

- **JSONL format:** All troll modules already emit to `data/troll-run.jsonl` via their own `_emit_jsonl()` helpers. The orchestrator adds wrapper events (`troll.run.start`, `troll.run.done`) but does NOT re-emit individual probe events — those come from the attack modules themselves.
- **Blocking vs non-blocking:** ACL enforcement (NFR5) and SPARQL injection (NFR6) are BLOCKING — failures mean the architecture is broken. Vector privacy (NFR8), cross-inference (NFR13), and deletion timing (NFR12) are NON-BLOCKING — partial/fail results are assessment findings, not showstoppers.
- **Deterministic vs non-deterministic:** Cross-inference (NFR13) uses LLM — results vary between runs. All other categories are deterministic. The report must flag this.

### Existing Attack Module Entry Points

```python
# ACL Enforcement (Story 1.5) — agents/troll-adversary/attacks/acl_enforcement.py
from attacks.acl_enforcement import run_acl_enforcement_suite
summary, results = run_acl_enforcement_suite(css_base_url)
# Returns: (dict, List[TrollTestResult])

# SPARQL Injection (Story 2.7) — agents/troll-adversary/attacks/sparql_injection.py
from attacks.sparql_injection import InjectionTestSuite
suite = InjectionTestSuite(oxigraph_url, template_dir)
summary, results = suite.run_all()
# Returns: (dict, list[TrollTestResult])

# Vector Privacy (Story 2.8) — agents/troll-adversary/attacks/vector_privacy.py
# Has main() entry point but no clean run_all() function — check actual file
# Individual attack functions: _attack_name_extraction(), _attack_identity_correlation(), etc.

# Cross-Inference (Story 3.8) — agents/troll-adversary/attacks/cross_inference.py
from attacks.cross_inference import CrossInferenceAttack
attack = CrossInferenceAttack(base_url, token)
results = attack.run_all_probes()
summary = attack.generate_summary(results)

# Deletion Timing (Story 5.3) — agents/troll-adversary/attacks/deletion_timing.py
from attacks.deletion_timing import DeletionTimingAttack
attack = DeletionTimingAttack(target_pod_uri, resource_uri)
results = attack.run_all_tests()
summary = attack.generate_summary(results)
```

**IMPORTANT:** Vector privacy module (`vector_privacy.py`) may not have a clean `run_all()` entry point like the others. Check the actual file — you may need to add a thin wrapper or call individual `_attack_*()` functions. Do NOT restructure the module; wrap it.

**IMPORTANT:** Deletion timing needs `target_pod_uri` and `resource_uri` parameters. The orchestrator must either:
- Use default values (`DEFAULT_POD_URI`, `DEFAULT_RESOURCE_URI` from the module)
- Or ingest test data first, then use a known resource URI
Check the module's `main()` or `if __name__` block for how it handles this today.

### Report Canonical Format

Each attack module already produces per-category JSON files in `agents/troll-adversary/report/`. The comprehensive report AGGREGATES these into a single envelope:

```json
{
  "report_type": "comprehensive_troll_run",
  "timestamp": "ISO-8601",
  "categories": {
    "acl_enforcement": {"blocking": true, "passed": N, "partial": N, "failed": N, "narrative": "..."},
    "sparql_injection": {"blocking": true, ...},
    "vector_privacy": {"blocking": false, ...},
    "cross_inference": {"blocking": false, "nfr13_disclaimer": "...", ...},
    "deletion_timing": {"blocking": false, ...}
  },
  "overall": {
    "total_tests": N,
    "passed": N, "partial": N, "failed": N,
    "blocking_pass": true|false,
    "assessment": "string"
  },
  "tests": [...]
}
```

### Markdown Report Template

The report follows the troll's philosophical stance (from SOUL.md): honest adversarial reporting where failure states are first-class citizens. Partial/fail results are framed as "investment opportunities" for funders — areas where additional engineering would strengthen the architecture — not as bugs to hide.

Structure:
1. Executive Summary (2-3 sentences)
2. Per-Category Sections (5 sections, each with: result rating, test count, narrative, notable findings)
3. Blocking Assessment (pass/fail for ACL + SPARQL)
4. Investment Opportunities (partial/fail items from non-blocking categories)
5. Technical Appendix (raw test counts, determinism flags)

### Key Files to Touch

| File | Action |
|------|--------|
| `agents/troll-adversary/attacks/run_comprehensive.py` | **CREATE** — Orchestrator |
| `agents/troll-adversary/report/generator.py` | **CREATE** — Report generator (JSON + markdown) |
| `scripts/run-troll.sh` | **EDIT** — Point to orchestrator |
| `agents/troll-adversary/tests/test_comprehensive.py` | **CREATE** — Unit tests |

### Key Files to Reference (READ ONLY)

| File | What to Extract |
|------|-----------------|
| `agents/troll-adversary/attacks/acl_enforcement.py` | `run_acl_enforcement_suite()` signature and return type |
| `agents/troll-adversary/attacks/sparql_injection.py` | `InjectionTestSuite` API |
| `agents/troll-adversary/attacks/vector_privacy.py` | Entry point — check for `run_all()` or `main()` |
| `agents/troll-adversary/attacks/cross_inference.py` | `CrossInferenceAttack` API, `PROBE_CATALOG` |
| `agents/troll-adversary/attacks/deletion_timing.py` | `DeletionTimingAttack` API, default params |
| `agents/troll-adversary/attacks/__init__.py` | `TrollTestResult`, `log_test_result` — canonical types |
| `agents/troll-adversary/SOUL.md` | Report format canonical spec, triple access model |
| `agents/troll-adversary/AGENTS.md` | Attack categories, structured logging format |
| `scripts/run-troll.sh` | Current orchestration (single category only) |
| `pipeline/run_pipeline.py:295-297` | JSONL truncation pattern to reuse |

### JSONL Event Patterns (Already Emitted by Modules)

All 5 attack modules already emit their own events to `data/troll-run.jsonl`. The orchestrator adds two wrapper events:

```json
{"event_type": "troll.run.start", "timestamp": ..., "categories": ["acl_enforcement", "sparql_injection", "vector_privacy", "cross_inference", "deletion_timing"]}
{"event_type": "troll.run.done", "timestamp": ..., "total_elapsed": ..., "blocking_pass": true|false, "summary": {...}}
```

### Invalidated Assumptions

| Assumption | Status | Correction |
|---|---|---|
| `run-troll.sh` runs all categories | INVALIDATED | Currently only runs `acl_enforcement.py` — this story fixes that |
| `agent.yaml` is the agent config format | INVALIDATED (Epic 3.3) | Agents use `SOUL.md` / `AGENTS.md` / `IDENTITY.md` workspace |
| Report template exists at `agents/troll-adversary/report/template.md` | NOT YET | Epics reference it but it doesn't exist — generator creates the report directly |
| Vector privacy has a clean `run_all()` API | UNVERIFIED | Check the actual file before assuming — may need wrapper |

### Environment

- **OpenRouter API key required** for vector privacy (embedding generation) and cross-inference (via OpenClaw → LLM)
- **OpenClaw must be running** for cross-inference probes
- **Distrobox note:** `distrobox-host-exec podman compose` for container commands
- All services must be healthy before troll run

### Previous Story Intelligence (Story 6.0)

- Story 6.0 adds Stage 0 to pipeline — troll run should happen AFTER pipeline completes (pods provisioned, data loaded)
- `data/troll-run.jsonl` is separate from `data/pipeline-run.jsonl` — troll orchestrator truncates its own file

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.3] — Comprehensive troll run AC (epics numbering: troll = 6.3)
- [Source: _bmad-output/planning-artifacts/architecture.md#INFRA-5] — JSONL event format spec
- [Source: agents/troll-adversary/SOUL.md] — Report format, triple access model, attack categories
- [Source: _bmad-output/implementation-artifacts/1-5-troll-acl-enforcement-validation.md] — ACL enforcement patterns
- [Source: _bmad-output/implementation-artifacts/2-7-troll-sparql-injection-validation.md] — SPARQL injection patterns
- [Source: _bmad-output/implementation-artifacts/2-8-troll-vector-privacy-validation.md] — Vector privacy patterns
- [Source: _bmad-output/implementation-artifacts/3-8-troll-cross-inference-validation.md] — Cross-inference patterns
- [Source: _bmad-output/implementation-artifacts/5-3-troll-deletion-timing-validation.md] — Deletion timing patterns
- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-03-30.md] — Error swallowing + atomicity review checklist

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
