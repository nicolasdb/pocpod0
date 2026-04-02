# Story 6.3: Funder Intervention Points

Status: ready-for-dev

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

- [ ] **Task 1: Wire acl-manage skill into grant/revoke backend** (AC1, AC6)
  - [ ] 1.1: In `dashboard_api.py`, replace `provisioner.grant_acl_access()` with subprocess call to `agents/skills/acl-manage/handler.py --action grant --pod-name {pod} --identity {webid} --role {actor} --access-level read`
  - [ ] 1.2: Same for `provisioner.revoke_acl_access()` → `--action revoke --pod-name {pod} --identity {webid}`
  - [ ] 1.3: Set subprocess env: `CSS_CONNECT_URL=http://localhost:3000`, `AGENT_POD_OWNERSHIP={all 6 pods comma-sep}`, `AGENT_ID=dashboard`
  - [ ] 1.4: Parse stdout JSON from handler; if `status != "ok"`, return HTTP 400 with handler message
  - [ ] 1.5: Keep `provisioner.view_acl_state()` for `GET /api/pods` — no change needed there

- [ ] **Task 2: Add Troll backend routes** (AC2, AC3)
  - [ ] 2.1: Add `POST /api/troll/run` — runs `run_comprehensive.py` as subprocess (all categories); streams to troll-run.jsonl
  - [ ] 2.2: Add `GET /api/troll/results` — reads `data/troll-run.jsonl` and returns parsed summary (latest `troll.category.done` events per category + `troll.run.done` if present)
  - [ ] 2.3: Add `GET /api/troll/stream` — server-sent events or polling endpoint that returns new lines from troll-run.jsonl since last offset

- [ ] **Task 3: Add Troll tab to index.html** (AC2, AC3, AC4)
  - [ ] 3.1: Add tab/section navigation (ACL tab + Troll tab) — pure JS tab switching, no page reload
  - [ ] 3.2: Troll tab layout: 5 category rows (name, blocking badge, pass/partial/fail counters, Launch button)
  - [ ] 3.3: Full Run button triggers `POST /api/troll/run`, polls `GET /api/troll/results` every 2s during run
  - [ ] 3.4: On `troll.run.done` event, stop polling and show final summary
  - [ ] 3.5: Color coding: pass=green, partial=yellow, fail=red; blocking categories have a red "BLOCKING" badge
  - [ ] 3.6: Pre-load prior results on tab open via `GET /api/troll/results` (show last run if troll-run.jsonl exists)

- [ ] **Task 4: UI polish** (AC5)
  - [ ] 4.1: Health bar: add a thin colored border/stripe (green=all up, yellow=partial, red=CSS down) rather than just ✓/✗ text
  - [ ] 4.2: Pod cards: ensure display names render correctly in all labels (actor dropdown shows display names, not slugs where possible)
  - [ ] 4.3: Pod card layout: group probe controls and grant/revoke controls visually (e.g. thin separator)
  - [ ] 4.4: Consistent spacing, font sizes, and button styles across both tabs

- [ ] **Task 5: Update tests** (all ACs)
  - [ ] 5.1: Update `test_AC4_grant_access` and `test_AC5_revoke_access` — mock `subprocess.run` instead of `PodProvisioner.grant_acl_access` / `revoke_acl_access`
  - [ ] 5.2: Test grant → handler exits 0 (ok) → 200 response; handler exits 1 (denied) → 400 response
  - [ ] 5.3: Test `GET /api/troll/results` with mocked troll-run.jsonl content (happy path + empty file)
  - [ ] 5.4: Test `POST /api/troll/run` triggers subprocess (mock it, don't actually run troll)
  - [ ] 5.5: Ensure all 197+ existing tests still pass (no regressions)

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

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
