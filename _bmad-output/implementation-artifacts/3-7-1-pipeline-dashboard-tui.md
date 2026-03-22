# Story 3.7.1: Pipeline Dashboard TUI

Status: ready-for-dev

## Story

As a **developer running the pipeline**,
I want a live terminal dashboard showing stage progression, timing, and status,
so that I'm not blind during the ~10 minute pipeline run.

## Context

Quick side-story born from Story 3.7 frustration: the pipeline is a black box during execution. No progress, no stage timing, no error count mid-flight. This adds a JSONL event log + a `rich.live` TUI viewer. Feeds naturally into Story 6.2 (Mission Control) later.

---

## Acceptance Criteria

**AC1: Pipeline emits structured JSONL events**
When the pipeline runs, it writes events to `data/pipeline-run.jsonl` (overwritten each run)
Events include: `pipeline.start`, `pipeline.wipe.start/done`, `stage.start`, `stage.done`, `stage.failed`, `pipeline.done`
Each event has `timestamp`, `event_type`, and relevant payload

**AC2: Dashboard TUI renders live progress**
When `pocpod0-dashboard` runs in a separate terminal, it reads the JSONL log and displays a `rich.live` table showing per-stage status (pending/running/done/failed), elapsed time, and total elapsed

**AC3: Dashboard auto-exits on completion**
When pipeline finishes (success or failure), the dashboard detects `pipeline.done` or `stage.failed` and exits with a summary

**AC4: Service health shown**
Dashboard shows CSS/Oxigraph/Qdrant up/down status on startup

---

## Tasks / Subtasks

### Task 1: JSONL event emission in run_pipeline.py
- [ ] Add `_emit(event_type, **data)` helper that appends JSON line to `data/pipeline-run.jsonl`
- [ ] Emit `pipeline.start` at beginning (stages count, wipe flag)
- [ ] Emit `pipeline.wipe.start/done` around wipe
- [ ] Emit `stage.start` / `stage.done` / `stage.failed` around each stage
- [ ] Emit `pipeline.done` at end with total elapsed

### Task 2: Dashboard TUI
- [ ] Create `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py`
- [ ] Implement JSONL tail reader (seek to end, poll 0.5s)
- [ ] Implement `rich.live` table with stage status, elapsed, totals
- [ ] Add service health check row (HTTP ping CSS/Oxigraph/Qdrant)
- [ ] Auto-exit on pipeline completion event
- [ ] Add `pocpod0-dashboard` script entry to pyproject.toml
- [ ] Add `rich>=13.0` to dependencies

### Task 3: Verification
- [ ] Run pipeline in terminal 1, dashboard in terminal 2 — verify live updates
- [ ] Verify JSONL file is valid (one JSON object per line)

---

## Dev Notes

### Files to modify
- `pipeline/run_pipeline.py` — add `_emit()` + event calls
- `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` — NEW
- `pipeline/pyproject.toml` — add `rich>=13.0` dep + script entry

### Key decisions
- JSONL (not TOML) for the event log — append-friendly, `tail -f` compatible
- `rich.live` (not textual) — lighter, sufficient for a status table
- Separate from existing `log_event()` in utils.py — different audience (file vs stdout)
- Dashboard is read-only viewer — pipeline doesn't depend on it

---

## Dev Agent Record

### Agent Model Used
(pending)

### Debug Log References
(pending)

### Completion Notes List
(pending)

### File List
(pending)
