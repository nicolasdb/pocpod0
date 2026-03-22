# Story 3.7: Graph-Only vs Hybrid Comparison

Status: ready-for-dev

## Story

As a **researcher / funder audience**,
I want a systematic, reproducible comparison of graph-only and hybrid query results across all students in Claire's scope,
so that the architectural benefit of combining Oxigraph SPARQL with Qdrant vector search is measurable, not just anecdotal.

## Context

Story 3.4 demonstrated the "aha moment" conversationally (Claire's agent session). Story 3.7 makes it **scientific**: a standalone comparison script produces a structured report with per-student deltas and aggregate enrichment metrics, suitable for funder review. This story also closes the two data integrity issues deferred from Story 3.4.

---

## Pre-Requisite Fixes (carry-over from Story 3.4)

> **AC-GATE:** AC-P3 verification must pass (0 mismatches) before the comparison story ACs are tested.

### P1: Fix pipeline wipe — CSS pod data accumulates between `--wipe` runs

**Problem:** `run_pipeline.py --wipe` clears Oxigraph (`CLEAR ALL`) and Qdrant but NOT CSS pods. CSS pods accumulate old UUID resources between runs because CSS LDP returns 409 on DELETE of non-empty containers. `load_graph.py` then re-loads both old and new RDF → stale data persists. Currently 119 success/score mismatches in Oxigraph from pre-fix troll data.

**Fix — leaf-first LDP DELETE:**
Add `wipe_css_pods(pod_slugs, css_base_url)` to `pipeline/run_pipeline.py`. Algorithm:
1. Hard-code pod slugs from known synthetic actors: `["ayoub", "claire-student-1", "claire-student-2", "claire", "fatima-child-1", "fatima-child-2", "school-community"]`
2. For each slug: `GET {css_base}/{slug}/learning/` with provisioner auth → parse `ldp:contains` member URIs from Turtle response body
3. `DELETE` each member URI individually (leaf resources)
4. `DELETE` the now-empty `{css_base}/{slug}/learning/` container
5. Tolerate 404 gracefully (already empty = OK)
6. Call this inside `wipe()` before the Oxigraph CLEAR ALL

Auth pattern: use `provisioner_headers()` from `pipeline/src/pocpod0_pipeline/utils.py` — same Authorization WebID header used throughout the pipeline. Reference `provision_pods.py` for how CSS HTTP requests are structured.

LDP member URI parsing: CSS returns Turtle; simplest parse — regex `<(http[^>]+\.ttl)>` against response body (no rdflib needed). Or use `requests` with `Accept: text/turtle` and parse the `ldp:contains` triples.

### P2: Fix ingest default `--input-dir` to include troll-load data

**File:** `pipeline/run_pipeline.py`, the `ingest` stage `cmd`
**Problem:** `ingest.py` defaults to `data/synthetic/scenarios` — troll-load data in `data/synthetic/troll-load/` is never re-ingested after a wipe.
**Fix:** Pass explicit `--input-dir` to the ingest stage:
```python
{
    "name": "ingest",
    "label": "[3/5] Ingest xAPI → CSS Pods (RDF)",
    "cmd": [sys.executable, "-m", "pocpod0_pipeline.ingest",
            "--input-dir", str(Path(__file__).parent / "data" / "synthetic")],
},
```
`run_pipeline.py` is at repo root, so `Path(__file__).parent / "data" / "synthetic"` resolves correctly.
`ingest.py:137` already uses `input_dir.glob("**/*.json")` (recursive) — picks up both subdirs.

### P3: Verification after P1+P2 + pipeline regen

Run: `python pipeline/run_pipeline.py --wipe` (full regen, ~10min)

Then verify:
```bash
# Isolation note: runs fine on host; services exposed on localhost ports
source pipeline/.venv/bin/activate
python3 -c "
import httpx, json
resp = httpx.post('http://localhost:7878/query',
    content='PREFIX pocpod0: <https://poc-pod0.edu/vocab/> SELECT ?sc ?s (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?a pocpod0:result ?r . ?r pocpod0:scaledScore ?sc . ?r pocpod0:success ?s . } } GROUP BY ?sc ?s',
    headers={'Content-Type':'application/sparql-query','Accept':'application/sparql-results+json'}, timeout=30)
data = resp.json()
mismatches = [(b['sc']['value'], b['s']['value'], b['n']['value'])
  for b in data['results']['bindings']
  if (float(b['sc']['value']) >= 0.5) != (b['s']['value'] == 'true')]
print(f'Mismatches: {len(mismatches)} (expect 0)')
for m in mismatches[:5]: print(' ', m)
"
```
**Gate: must print `Mismatches: 0`.**

---

## Acceptance Criteria

**AC1: Graph-only results captured per student**
Given the pipeline has been re-run with P1+P2 fixes (clean data, 0 mismatches per P3 gate)
When the comparison script runs a graph-only SPARQL query for each of the 3 students in Claire's scope (Ayoub, claire-student-1/Alex, claire-student-2/Jordan)
Then structured results are captured per student: `activity_breakdown`, `score_stats`, `recent_failures`, `mastery_events` (from handler `_summarize_bindings()`)
And results are scoped to Claire's authorized pods only (unauthorized pods return empty/403)
And per-student SPARQL latency is < 500ms (NFR1)

**AC2: Hybrid results captured per student**
Given the same 3-student scope
When the comparison script runs a hybrid query (SPARQL + Qdrant, same student)
Then hybrid results include SPARQL structured facts AND Qdrant semantic enrichments with `content_text`
And Qdrant results are filtered to `pod_resource_uri` matching the target student's pod prefix
And combined latency per student is < 2s (NFR2)

**AC3: Comparison report produced**
Given both graph-only and hybrid results for all 3 students
When the comparison script generates the report
Then the report contains per-student sections:
  - `graph_only`: `activity_breakdown`, `score_stats`, `mastery_events_count`, `latency_ms`
  - `hybrid.qdrant_enrichments`: list of `{content_text, score, pod_resource_uri}` items
  - `delta.novel_insights`: semantic content from Qdrant not captured as structured triples
  - `delta.hybrid_adds_value`: bool
And the report contains an `aggregate` section: students queried, students with hybrid enrichment, avg Qdrant results per student
And the report is saved to `data/reports/graph-vs-hybrid-<timestamp>.json`
And a human-readable Markdown summary is printed to stdout

**AC4: ACL enforcement correct in comparison context**
Given the script attempts to query a pod outside Claire's authorized scope
When it runs both graph-only and hybrid for that pod
Then graph-only returns 0 results (CSS returns 403 → skill converts to empty results)
And Qdrant results for that pod_resource_uri prefix are excluded from hybrid merge
And the report notes these students as "access denied: not in scope"

**AC5: Total comparison run for 3 students completes in < 30s**
Per-student: graph-only < 500ms + hybrid < 2s = < 2.5s × 3 students + overhead < 30s total.

---

## Tasks / Subtasks

### Task 1: Fix P1 — `wipe_css_pods()` in run_pipeline.py

- [ ] Add `POD_SLUGS = ["ayoub", "claire-student-1", "claire-student-2", "claire", "fatima-child-1", "fatima-child-2", "school-community"]` constant near top of `run_pipeline.py`
- [ ] Implement `wipe_css_pods(css_base_url: str) -> None`:
  - [ ] For each slug: GET `{css_base}/{slug}/learning/` with provisioner auth headers
  - [ ] Parse response body for member URIs (regex `<(http[^>]+)>` on Turtle, filter `.ttl` paths)
  - [ ] DELETE each member URI; tolerate 404
  - [ ] DELETE empty `{css_base}/{slug}/learning/`; tolerate 404
  - [ ] Print progress per pod: `"  CSS pod {slug}/learning/: deleted N resources"`
- [ ] Add call to `wipe_css_pods(OXIGRAPH_URL.replace("7878", "3000"))` at start of `wipe()` function
  - Actually: read CSS base from `.env` `CSS_BASE_URL` or default `http://localhost:3000`
  - Add `CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")` constant
- [ ] Test: run `python pipeline/run_pipeline.py --wipe` and verify CSS pods are wiped before Oxigraph

### Task 2: Fix P2 — ingest `--input-dir`

- [ ] In `run_pipeline.py` STAGES list, update `ingest` entry:
  ```python
  "cmd": [sys.executable, "-m", "pocpod0_pipeline.ingest",
          "--input-dir", str(Path(__file__).parent / "data" / "synthetic")],
  ```
- [ ] Verify with dry run: `python -m pocpod0_pipeline.ingest --input-dir data/synthetic --dry-run` counts both troll-load and scenarios JSON files

### Task 3: Run full pipeline regen + P3 verification gate

- [ ] `source pipeline/.venv/bin/activate && python pipeline/run_pipeline.py --wipe`
- [ ] Run P3 verification script → confirm `Mismatches: 0`
- [ ] Note final counts: expected ~5900+ Qdrant points, ~120K+ triples, 0 failures

### Task 4: Implement `compare_query_modes.py`

- [ ] Create `pipeline/src/pocpod0_pipeline/compare_query_modes.py`
- [ ] Define `CLAIRE_SCOPE`:
  ```python
  CLAIRE_SCOPE = [
      {"name": "ayoub",           "pod_uri": "http://localhost:3000/ayoub/"},
      {"name": "claire-student-1","pod_uri": "http://localhost:3000/claire-student-1/"},
      {"name": "claire-student-2","pod_uri": "http://localhost:3000/claire-student-2/"},
  ]
  CLAIRE_WEBID = "http://localhost:3000/claire/profile/card#me"
  ```
- [ ] Implement `run_graph_only(pod_uri, agent_webid) -> dict`:
  - Import `handle` from `agents/skills/sparql-query/handler.py` via `sys.path.insert(0, ...)`
  - Call `handle({"pod_uri": pod_uri, "query_type": "cross-context-query", "agent_webid": agent_webid})`
  - Record `latency_ms`; return `{summary, result_count, latency_ms}`
- [ ] Implement `run_hybrid(pod_uri, query_text, agent_webid) -> dict`:
  - Call `run_graph_only()` as above
  - Import `handle` from `agents/skills/qdrant-search/handler.py`
  - Call `handle({"query_text": query_text, "pod_uri": pod_uri, "limit": 10})`
  - Filter Qdrant results: keep only entries where `result["pod_resource_uri"].startswith(pod_uri)`
  - Return `{sparql_summary, qdrant_results, latency_ms}`
- [ ] Implement `compute_delta(graph_result, hybrid_result) -> dict`:
  - "Novel insight": Qdrant `content_text` entries where the text contains substantive content beyond what `activity_breakdown` keys describe
  - Simplest heuristic: any Qdrant result with `score > 0.7` is a novel enrichment
  - Return `{novel_insights: [...], hybrid_adds_value: bool}`
- [ ] Implement `generate_report(student_results: list) -> dict` — full JSON report structure (see Dev Notes)
- [ ] Implement `render_markdown(report: dict) -> str` — human-readable Markdown to stdout
- [ ] Add `main()` with argparse:
  - `--query-text` (default: `"struggling students quadratic equations"`)
  - `--output-dir` (default: `data/reports/`)
  - `--students` (default: `ayoub,claire-student-1,claire-student-2`)
- [ ] Add to `pipeline/pyproject.toml` scripts: `pocpod0-compare = "pocpod0_pipeline.compare_query_modes:main"`

### Task 5: Integration test

- [ ] Create `pipeline/tests/integration/test_graph_vs_hybrid.py`
  - [ ] `test_graph_only_returns_results_for_ayoub()` — assert `result_count > 0`, `activity_breakdown` non-empty
  - [ ] `test_hybrid_adds_qdrant_enrichments()` — assert ≥1 student has `hybrid_adds_value: True`
  - [ ] `test_acl_scoping_excludes_fatima_children()` — assert `fatima-child-1` pod returns 0 results for Claire (not in scope)
  - [ ] `test_latency_within_nfr()` — assert per-student SPARQL < 500ms, per-student hybrid < 2s
  - [ ] `test_report_saved_to_disk()` — assert JSON file created with correct top-level keys
  - [ ] `test_p3_zero_mismatches()` — the P3 mismatch query: assert 0 mismatches (guards against regression)

---

## Dev Notes

### Critical: Do NOT create a new skill directory

The original (pre-implementation) story draft proposed `agents/skills/comparison-formatter/`. **Do NOT create this.** The comparison is a standalone pipeline script (`compare_query_modes.py`), not an OpenClaw skill. OpenClaw skills are Python subprocess handlers invoked by the agent runtime — adding a formatting wrapper skill adds no value and breaks the existing clean skill architecture.

### Handler invocation pattern (validated in Story 3.4 integration tests)

```python
import sys
from pathlib import Path

# Add skill directory to path
sys.path.insert(0, str(Path("agents/skills/sparql-query").resolve()))
from handler import handle as sparql_handle

result = sparql_handle({
    "pod_uri": "http://localhost:3000/ayoub/",   # must end with /
    "query_type": "cross-context-query",
    "agent_webid": "http://localhost:3000/claire/profile/card#me"
})
# result["summary"] = {activity_breakdown, score_stats, recent_failures, mastery_events}
# result["result_count"] = N
# result["provenance"] = [pod root URIs]
```

```python
sys.path.insert(0, str(Path("agents/skills/qdrant-search").resolve()))
from handler import handle as qdrant_handle

result = qdrant_handle({
    "query_text": "student struggling quadratic equations",
    "pod_uri": "http://localhost:3000/ayoub/",
    "limit": 10
})
# result["results"] = [{content_text, score, triple_uris, pod_resource_uri}, ...]
```

### Critical: `prov:wasDerivedFrom` is WRONG — use named graphs

The old story draft mentioned `prov:wasDerivedFrom`. **This was invalidated in Story 2.6.** The correct provenance model is:
- Named graph URI == Pod resource URI (e.g., `http://localhost:3000/ayoub/learning/abc.ttl`)
- `GRAPH <uri> { ?s ?p ?o }` scoping — NOT `prov:wasDerivedFrom`
- Provenance in SPARQL handler returns `pod_uri` root (not individual named graph URIs — IG-1 from Story 3.4 code review accepted pod-level)
- Qdrant payload: `pod_resource_uri` (individual TTL file URI) + `triple_uris` list

### pod_uri must end with "/"

The SPARQL handler has a P-4 normalization fix (Story 3.4 code review):
```python
if "pod_uri" in params and not params["pod_uri"].endswith("/"):
    params = {**params, "pod_uri": params["pod_uri"] + "/"}
```
Pass pod URIs with trailing slash in `CLAIRE_SCOPE` to be explicit.

### CLAIRE_WEBID canonical value

`http://localhost:3000/claire/profile/card#me` — this was fixed in Story 3.4 (SOUL.md had wrong hostname; ACLs use `claire` not `claire-teacher`). The comparison script runs on host (not in Docker), so use `localhost:3000` not `community-solid-server:3000`.

### Report JSON structure

```json
{
  "generated_at": "2026-03-22T14:00:00Z",
  "query": "struggling students quadratic equations",
  "students": {
    "ayoub": {
      "pod_uri": "http://localhost:3000/ayoub/",
      "graph_only": {
        "result_count": 82,
        "activity_breakdown": {"failed": 60, "attempted": 22},
        "score_stats": {"avg": 0.31, "min": 0.0, "max": 0.85},
        "mastery_events_count": 12,
        "latency_ms": 312
      },
      "hybrid": {
        "sparql_summary": {"result_count": 82, "activity_breakdown": {...}},
        "qdrant_enrichments": [
          {"content_text": "...", "score": 0.87, "pod_resource_uri": "..."}
        ],
        "qdrant_result_count": 5,
        "latency_ms": 1450
      },
      "delta": {
        "novel_insights": ["tutoring notes: geometric visualization approach"],
        "hybrid_adds_value": true
      }
    }
  },
  "aggregate": {
    "students_queried": 3,
    "students_with_hybrid_enrichment": 2,
    "avg_qdrant_results_per_student": 3.7,
    "total_latency_ms": 8200
  }
}
```

### Markdown stdout example

```markdown
# Graph-Only vs Hybrid Comparison Report
Generated: 2026-03-22 | Query: "struggling students quadratic equations"

## Ayoub (ayoub/)
**Graph-only:** 82 activities — 60 failures, avg score 0.31, 12 mastery events
**Hybrid enrichment:** 5 Qdrant results (e.g. "tutoring notes: geometric visualization")
**Delta:** ✓ Hybrid adds semantic context invisible in school data

## claire-student-1 / Alex (claire-student-1/)
...

## Aggregate
- 3 students queried, 2 with hybrid enrichment (67%)
- Avg 3.7 Qdrant enrichments per student
- Total elapsed: 8.2s
```

### Files to Create/Modify

| File | Change |
|------|--------|
| `pipeline/run_pipeline.py` | Add `wipe_css_pods()` + P2 ingest `--input-dir` fix |
| `pipeline/src/pocpod0_pipeline/compare_query_modes.py` | New — comparison script |
| `pipeline/pyproject.toml` | Add `pocpod0-compare` script entry |
| `pipeline/tests/integration/test_graph_vs_hybrid.py` | New integration tests |
| `data/reports/.gitkeep` | New — create dir, gitkeep |

**Do NOT modify:**
- `agents/skills/sparql-query/handler.py` — correct from Story 3.4 review
- `agents/skills/qdrant-search/handler.py` — correct from Story 3.4 review
- `agents/skills/sparql-query/templates/cross-context-query.rq` — correct
- Any agent SOUL.md or agent.yaml files
- Do NOT create `agents/skills/comparison-formatter/`

### Service Endpoints (host-side)

```
Oxigraph: http://localhost:7878  (env: OXIGRAPH_BASE_URL)
Qdrant:   http://localhost:6333  (env: QDRANT_BASE_URL)
CSS:      http://localhost:3000  (env: CSS_BASE_URL)
```

Isolation note: `distrobox-host-exec` not needed for HTTP calls from host — all services expose ports on localhost. Only needed for `podman` commands (e.g., `podman logs`). The comparison script runs on host with venv: `source pipeline/.venv/bin/activate`.

### Previous Story Intelligence (Story 3.4)

1. **`_summarize_bindings()`** in `sparql-query/handler.py` already returns `activity_breakdown`, `score_stats`, `recent_failures`, `mastery_events` — reuse directly.
2. **`content_text` populated in Qdrant** — Bug 5 fixed in Story 3.4. After clean regen (P1+P2), all points have `content_text`.
3. **BCP 47 lang tags fixed** — oslo_mapper.py no longer strips hyphens from `"en-US"`. Valid after regen.
4. **troll success/score correlation fixed** — generate_troll_load.py now uses `scaled >= 0.5`. Valid after regen.
5. **CSS three-var model** — comparison script runs on host, use `CSS_BASE_URL=http://localhost:3000`. `CSS_CONNECT_URL` is for container-to-container (not needed here).

### References

- Architecture DA-2: named graph provenance, `triple_uris` in Qdrant payload [Source: architecture.md]
- Architecture API-2: Two shared skills, hybrid = compose both [Source: architecture.md]
- FR16: Graph-only vs hybrid side-by-side [Source: epics.md]
- FR20: Provenance navigable from result to source [Source: epics.md]
- NFR1: SPARQL < 500ms; NFR2: Hybrid < 2s [Source: architecture.md]
- Story 3.4: Bug 2 (CSS env vars), Bug 5 (content_text), P-4 (trailing slash), IG-1 (pod-level provenance) [Source: 3-4-claire-cross-context-insight-discovery.md]
- Memory: `story_3_4_integration_patterns.md` — all 7 bugs, P3 fix deferred, CSS accumulation issue

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
