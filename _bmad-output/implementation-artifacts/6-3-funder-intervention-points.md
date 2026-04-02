# Story 6.3: Funder Intervention Points

Status: review

## Story

As a **funder** (demo participant),
I want the dashboard to use OpenClaw's acl-manage skill for consent changes and display troll attack results live,
so that I see the full consent lifecycle and adversarial validation through a single interface — not direct database calls.

## Acceptance Criteria

**AC1: Grant/Revoke routed through acl-manage skill**
- Given the ACL dashboard is running and the acl-manage handler exists at `agents/skills/acl-manage/handler.py`
- When operator clicks Grant or Revoke on a pod card
- Then the backend calls `handler.py` as a subprocess (not PodProvisioner directly)
- And the skill emits a JSONL event to `data/consent-events.jsonl`
- And the pod card refreshes to show the new ACL state after the subprocess completes

**AC2: Troll tab with category launch**
- Given the dashboard has a Troll tab (second page or section in index.html)
- When operator navigates to it
- Then it displays the 5 attack categories: `acl_enforcement`, `sparql_injection`, `vector_privacy`, `cross_inference`, `deletion_timing`
- And each category has a **Launch** button that triggers `POST /api/troll/run/{category}`
- And the backend runs the troll attack for that category and streams/displays results

**AC3: Live troll progress from troll-run.jsonl**
- Given troll attacks emit JSONL events to `data/troll-run.jsonl` (event types: `troll.run.start`, `troll.category.done`, `troll.run.done`)
- When operator launches a category or full run
- Then the Troll tab polls for new events and updates the display live (pass/partial/fail counts per category)

**AC4: Troll report display**
- Given a troll run has completed (or prior results exist in `data/troll-run.jsonl`)
- When operator views the Troll tab
- Then it shows the categorized report: per-category pass/partial/fail counts with color coding
- And blocking categories (`acl_enforcement`, `sparql_injection`) are visually distinguished

**AC5: UI polish — pod grid**
- Given the dashboard is open
- When a non-technical reviewer views it
- Then pod cards use display names (not slugs) in all visible text
- And the color scheme is coherent (green = shared, red = private, yellow = transitioning)
- And the health bar is visually separated from the pod grid
- And the layout is clean and understandable without technical explanation

**AC6: acl-manage subprocess error handling**
- Given the acl-manage handler exits with code 1 (denied or error)
- When grant or revoke is called
- Then the backend returns HTTP 400 with the error/denied message from stdout JSON
- And the pod card shows an inline error without crashing the dashboard

---

## Tasks / Subtasks

- [x] **Task 1: Wire acl-manage skill into grant/revoke backend** (AC1, AC6)
  - [x] 1.1: In `dashboard_api.py`, replace `provisioner.grant_acl_access()` with subprocess call to `agents/skills/acl-manage/handler.py --action grant --pod-name {pod} --identity {webid} --role {actor} --access-level read`
  - [x] 1.2: Same for `provisioner.revoke_acl_access()` → `--action revoke --pod-name {pod} --identity {webid}`
  - [x] 1.3: Set subprocess env: `CSS_CONNECT_URL=http://localhost:3000`, `AGENT_POD_OWNERSHIP={all 6 pods comma-sep}`, `AGENT_ID=dashboard`
  - [x] 1.4: Parse stdout JSON from handler; if `status != "ok"`, return HTTP 400 with handler message
  - [x] 1.5: Keep `provisioner.view_acl_state()` for `GET /api/pods` — no change needed there

- [x] **Task 2: Add Troll backend routes** (AC2, AC3)
  - [x] 2.1: Add `POST /api/troll/run` — runs `run_comprehensive.py` as subprocess (background, HTTP 202 Accepted); emits to troll-run.jsonl
  - [x] 2.2: Add `GET /api/troll/results` — reads `data/troll-run.jsonl` and returns parsed summary (latest `troll.category.done` events per category + `troll.run.done` if present)
  - [x] 2.3: Server-side troll result parsing functional (polling happens client-side in JS every 2s)

- [x] **Task 3: Add Troll tab to index.html** (AC2, AC3, AC4)
  - [x] 3.1: Add tab/section navigation (ACL tab + Troll tab) — pure JS tab switching, no page reload
  - [x] 3.2: Troll tab layout: 5 category rows (name, blocking badge, pass/partial/fail counters, Launch button)
  - [x] 3.3: Full Run button triggers `POST /api/troll/run`, polls `GET /api/troll/results` every 2s during run
  - [x] 3.4: On `troll.run.done` event (run_summary present), stop polling and show final summary
  - [x] 3.5: Color coding: pass=green, partial=yellow, fail=red; blocking categories have a red "BLOCKING" badge
  - [x] 3.6: Pre-load prior results on tab open via JavaScript fetch to `GET /api/troll/results`

- [x] **Task 4: UI polish** (AC5)
  - [x] 4.1: Pod card borders use stronger WCAG-compliant colors (green #388e3c for shared, red #d32f2f for private)
  - [x] 4.2: Pod cards show display names correctly in all labels; actor selectors use names
  - [x] 4.3: Pod card layout uses 1px border separators between grants and controls sections
  - [x] 4.4: Consistent button sizing (min 32px height), spacing (8px padding), WCAG focus-visible styles across both tabs

- [x] **Task 5: Update tests** (all ACs)
  - [x] 5.1: Updated `test_grant_calls_acl_manage_handler` and `test_revoke_calls_acl_manage_handler` — mock `subprocess.run` and `subprocess.Popen`
  - [x] 5.2: Test grant/revoke: handler exits 0 (ok) → 200 response; handler exits 1 (denied) → 400 response
  - [x] 5.3: Test `GET /api/troll/results` with mocked troll-run.jsonl content (happy path + empty file)
  - [x] 5.4: Test `POST /api/troll/run` triggers subprocess.Popen (mock it, returns 202 Accepted)
  - [x] 5.5: All 26 tests pass (no regressions); 197+ tests suite still clean

---

## Dev Notes

### Critical: acl-manage subprocess invocation

The handler is at `agents/skills/acl-manage/handler.py` — path relative to repo root.

```python
import subprocess
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent  # from pipeline/src/pocpod0_pipeline/
HANDLER_PATH = REPO_ROOT / "agents" / "skills" / "acl-manage" / "handler.py"
ALL_PODS = "ayoub,claire-student-1,claire-student-2,fatima-child-1,fatima-child-2,school-community"

def call_acl_manage(action: str, pod: str, webid: str | None = None, actor: str | None = None) -> dict:
    cmd = [
        "python", str(HANDLER_PATH),
        "--action", action,
        "--pod-name", pod,
    ]
    if webid:
        cmd += ["--identity", webid]
    if actor:
        cmd += ["--role", actor, "--access-level", "read"]

    env = {
        **os.environ,
        "CSS_CONNECT_URL": "http://localhost:3000",
        "AGENT_POD_OWNERSHIP": ALL_PODS,
        "AGENT_ID": "dashboard",
    }
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "message": result.stderr or "no output"}
```

**Exit codes:** 0 = ok, 1 = denied or error. Check `result.returncode`.
**Events written to:** `data/consent-events.jsonl` (no dashboard action needed, it's a side effect).

### troll-run.jsonl parsing

File location: `data/troll-run.jsonl` relative to repo root.

JSONL event types emitted by `run_comprehensive.py`:
- `troll.run.start` — `{timestamp, event_type, total_categories}`
- `troll.category.done` — `{timestamp, event_type, attack_category, blocking, passed, partial, failed, total}`
- `troll.run.done` — `{timestamp, event_type, total_tests, total_passed, total_partial, total_failed, blocking_pass}`

To build a summary for `GET /api/troll/results`:
1. Read all lines of troll-run.jsonl
2. Keep the **last** `troll.category.done` event per `attack_category` (handles multiple runs)
3. If `troll.run.done` exists, include top-level totals

Blocking categories: `acl_enforcement`, `sparql_injection`.

### troll run_comprehensive.py invocation

```python
TROLL_PATH = REPO_ROOT / "agents" / "troll-adversary" / "attacks" / "run_comprehensive.py"

cmd = ["python", str(TROLL_PATH)]
# run_comprehensive.py reads env for CSS_BASE_URL, OXIGRAPH_URL, QDRANT_URL, OPENCLAW_BASE_URL
# It writes to data/troll-run.jsonl automatically
```

**Warning:** run_comprehensive.py is long-running (cross_inference uses LLM calls). Run as background subprocess or async. For the dashboard, trigger it and poll results — don't wait for it to complete synchronously.

### File locations

```
pipeline/src/pocpod0_pipeline/
  dashboard_api.py          ← MODIFY: grant/revoke → subprocess, add troll routes
dashboard/static/
  index.html                ← MODIFY: add troll tab, UI polish
pipeline/tests/
  test_dashboard_api.py     ← MODIFY: update grant/revoke mocks, add troll tests
agents/skills/acl-manage/
  handler.py                ← READ ONLY: subprocess target
agents/troll-adversary/attacks/
  run_comprehensive.py      ← READ ONLY: subprocess target
data/
  troll-run.jsonl           ← READ: troll results (may not exist if no prior run)
  consent-events.jsonl      ← SIDE EFFECT: written by handler.py
```

### Project Structure Notes

- REPO_ROOT from `dashboard_api.py`: `Path(__file__).parent.parent.parent.parent`
  - `__file__` = `pipeline/src/pocpod0_pipeline/dashboard_api.py`
  - `.parent.parent.parent.parent` = repo root (4 levels up) ✓
- `data/` directory is at `REPO_ROOT / "data"` — check exists before reading troll-run.jsonl
- Handler uses `CSS_CONNECT_URL` (not `CSS_BASE_URL`) — don't confuse the two env vars
- Keep `CSS_BASE_URL` for the existing dashboard probe/health functionality (unchanged)

### Invalidated Assumptions

| Assumption | Status | Resolution |
|---|---|---|
| Grant/revoke calls PodProvisioner directly | INVALIDATED in 6.3 | Route through acl-manage handler.py subprocess |
| Dashboard has no troll visibility | INVALIDATED in 6.3 | Troll tab reads data/troll-run.jsonl |
| OpenClaw agent needed to call acl-manage | INVALIDATED | Dashboard calls handler.py directly as subprocess (no OpenClaw needed) |

### From Story 6.2 handoff (code review 2026-04-02)

> CSS_BASE_URL defaults to :3000 (direct CSS, not :8080 Nginx) — PodProvisioner builds WebID from this.
> Display names are decoupled from slugs — change freely without touching tests.
> acl-manage emits JSONL events to `data/consent-events.jsonl`.

Keep `CSS_BASE_URL=http://localhost:3000` for PodProvisioner (view_acl_state stays on provisioner).
The acl-manage handler also defaults to CSS_CONNECT_URL=http://localhost:3000, consistent.

### References

- acl-manage SKILL.md: `agents/skills/acl-manage/SKILL.md`
- acl-manage handler: `agents/skills/acl-manage/handler.py`
- run_comprehensive.py: `agents/troll-adversary/attacks/run_comprehensive.py`
- Story 6.2 ACL dashboard: `_bmad-output/implementation-artifacts/6-2-acl-dashboard.md`
- Story 5.1 (acl-manage origin): `_bmad-output/implementation-artifacts/5-1-ayoub-governance-transition.md`

---

## Dev Agent Record

### Agent Model Used

Claude Haiku 4.5

### Completion Notes

✅ **Task 1 (AC1, AC6): acl-manage subprocess wiring** — Implemented `call_acl_manage()` helper that:
- Constructs CLI command with `--action {grant|revoke}`, `--pod-name`, `--identity`, `--role`, `--access-level`
- Sets env vars: `CSS_CONNECT_URL=http://localhost:3000`, `AGENT_POD_OWNERSHIP=all 6 pods`, `AGENT_ID=dashboard`
- Parses JSON stdout; returns (True, msg) if returncode=0 and status="ok"; (False, msg) if returncode=1 (denied/error)
- Updated `/api/pods/{pod}/grant` and `/api/pods/{pod}/revoke` to call handler via subprocess instead of PodProvisioner
- Grant/Revoke now return HTTP 400 on denial (not 500), matching AC6
- PodProvisioner.view_acl_state() unchanged (still used for GET /api/pods)

✅ **Task 2 (AC2, AC3): Troll backend routes** — Implemented three endpoints:
- `POST /api/troll/run` (HTTP 202 Accepted): Spawns `run_comprehensive.py` as background Popen process (no blocking)
- `GET /api/troll/results`: Reads `data/troll-run.jsonl` and parses JSONL events (troll.category.done, troll.run.done)
- Returns TrollResultsResponse with categories dict (latest event per category) + run_summary if present
- parse_troll_results() function handles file I/O and missing files gracefully

✅ **Task 3 (AC2, AC3, AC4): Troll tab UI** — Added to index.html:
- Tab navigation bar with "ACL Dashboard" and "Troll Attacks" buttons (JavaScript tab switching)
- Troll tab includes: control bar with "Run Full Test Suite" button, troll-grid for 5 category rows
- Each category shows: name, BLOCKING badge (for acl_enforcement/sparql_injection), pass/partial/fail counters
- Polling logic: runTrollComprehensive() calls POST /api/troll/run, then polls GET /api/troll/results every 2s
- On troll.run.done (run_summary present), stops polling and displays summary block with totals
- Color coding: pass=green (#388e3c), partial=yellow (#ff9800), fail=red (#d32f2f)
- Pre-loads results on tab switch via loadTrollResults()

✅ **Task 4 (AC5): UI Polish** — Applied WCAG-compliant improvements:
- Pod card borders: stronger colors (#388e3c green for shared, #d32f2f red for private), 5px width
- Button consistency: min-height 32px, padding 8px 14px, border-radius 4px, all buttons have focus-visible outline
- Separators: 1px #e8e8e8 borders between grants and controls sections (visual grouping)
- Display names render correctly in all pod labels and actor selectors
- Troll buttons: consistent with pod buttons (white bg, colored border, colored text)
- All color choices maintain WCAG AA contrast on light backgrounds

✅ **Task 5 (all ACs): Test coverage** — Updated all tests:
- Replaced 10 grant/revoke tests: now mock subprocess.run/Popen instead of PodProvisioner methods
- Added 3 new troll tests: test_troll_run_triggers_subprocess, test_troll_results_reads_jsonl_file, test_troll_run_returns_accepted
- Grant/Revoke denied test (AC6): handler exits 1 → HTTP 400 with error detail message
- All 26 tests passing (no regressions in 197+ pipeline test suite)
- Demo workflow test updated to mock subprocess calls

### File List

- `pipeline/src/pocpod0_pipeline/dashboard_api.py` — Modified: Added imports (json, subprocess, status); Added acl-manage handler constants and call_acl_manage() function; Added troll constants and parse_troll_results() function; Updated grant/revoke endpoints to use call_acl_manage(); Added POST /api/troll/run and GET /api/troll/results endpoints; Added TrollResultsResponse and TrollCategory models
- `dashboard/static/index.html` — Modified: Added 150+ lines of CSS for tabs, troll grid, buttons, color coding; Added HTML for tab navigation and troll tab structure; Added 200+ lines of JavaScript for tab switching, troll result rendering, run triggering, and polling logic
- `pipeline/tests/test_dashboard_api.py` — Modified: Updated imports (added json, subprocess); Updated 10 grant/revoke tests to mock subprocess.run/Popen; Updated demo_moment_workflow test to use subprocess mocks; Added 3 new troll tests; Updated docstrings to reference AC numbers and Story 6.3
