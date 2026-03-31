# Story 6.2: Mission Control Dashboard Implementation

Status: ready-for-dev

## Story

As a **funder** (demo audience),
I want a native-tabbed mission control TUI showing live attack results, pod/consent status, and service health,
so that I can follow the PoC demo narrative visually with a professional, interactive interface.

## Acceptance Criteria

1. **AC1: Multi-tab mission control TUI with native Textual tabs**
   - **Given** Textual framework is available (`textual>=6.6.0`)
   - **When** `pocpod0-mission-control` is launched
   - **Then** it displays 5 native tabs (via `TabbedContent`) reading from 3 JSONL event streams:
     - `data/pipeline-run.jsonl` (pipeline stages)
     - `data/troll-run.jsonl` (adversarial test results)
     - `data/consent-events.jsonl` (consent lifecycle events)
   - **And** tabs are: [HEALTH], [PIPELINE], [TROLL], [CONSENT], [PODS]
   - **And** tabs are interactive: arrow keys or mouse to switch; visual feedback on active tab

2. **AC2: Live troll results with reactive updates**
   - **Given** a troll probe completes and emits a JSONL event to `data/troll-run.jsonl`
   - **When** the TUI is running
   - **Then** the [TROLL] tab `DataTable` updates automatically with the new result (probe ID, category, result)
   - **And** per-category summary counts (pass/partial/fail/blocking) update reactively
   - **And** colors change live: green=pass, yellow=partial, red=fail

3. **AC3: Consent gate and pod state with reactive updates**
   - **Given** consent events are emitted to `data/consent-events.jsonl`
   - **When** the TUI is running
   - **Then** the [CONSENT] tab `DataTable` shows active, revoked, and expired grant counts per pod
   - **And** the [PODS] tab shows pod name, ACL state, last event type, timestamp
   - **And** tables update reactively as events arrive

4. **AC4: Service health monitoring**
   - **Given** the [HEALTH] tab is visible
   - **When** services are checked (CSS, Oxigraph, Qdrant, OpenClaw)
   - **Then** status indicators show ✓ (up) or ✗ (down) with last-checked timestamp
   - **And** colors are green (up), red (down)

5. **AC5: Non-technical readability and professional UX**
   - **Given** a non-technical funder watching the TUI during a demo
   - **When** they see the tabbed interface
   - **Then** tabs are labeled clearly (HEALTH, PIPELINE, TROLL, CONSENT, PODS)
   - **And** colors are consistent (green=pass/active, yellow=partial, red=fail/down)
   - **And** no technical jargon is visible without context
   - **And** the interface looks professional and responsive

## Tasks / Subtasks

- [ ] Task 1: Create mission_control.py Textual app (AC: 1, 2, 3, 4)
  - [ ] 1.1: New file `pipeline/src/pocpod0_pipeline/mission_control.py` — Textual App with TabbedContent
  - [ ] 1.2: Define 5 TabPane widgets (HEALTH, PIPELINE, TROLL, CONSENT, PODS) each containing a DataTable
  - [ ] 1.3: Implement reactive attributes for troll_events, consent_events, pipeline_events, health_status
  - [ ] 1.4: Background worker tasks to tail 3 JSONL files asynchronously (no blocking)
- [ ] Task 2: [HEALTH] tab (AC: 4)
  - [ ] 2.1: DataTable: Service, Status, Last Check columns
  - [ ] 2.2: Async health check loop (5s interval) for CSS, Oxigraph, Qdrant, OpenClaw
  - [ ] 2.3: Reactive watch: when health_status changes, update_cell() for the affected row
- [ ] Task 3: [PIPELINE] tab (AC: 1)
  - [ ] 3.1: DataTable: Stage, Status, Elapsed (s), Start Time columns
  - [ ] 3.2: Parse `pipeline.start`, `stage.start`, `stage.done`, `stage.failed`, `pipeline.done` events
  - [ ] 3.3: Reactive watch: when pipeline_events changes, update table
- [ ] Task 4: [TROLL] tab (AC: 2)
  - [ ] 4.1: Top section: Category Summary (DataTable with Category, Passed, Partial, Failed, Blocking columns)
  - [ ] 4.2: Bottom section: Recent Probes (DataTable with Probe ID, Category, Layer, Result, Elapsed (ms) columns)
  - [ ] 4.3: Parse `troll.run.start`, `troll.probe.start`, `troll.probe.done`, `troll.category.done` events
  - [ ] 4.4: Color-code results: Row style based on result value (pass=green, partial=yellow, fail=red)
- [ ] Task 5: [CONSENT] tab (AC: 3)
  - [ ] 5.1: DataTable: Pod, Active Grants, Revoked Grants, Expired Tokens, Last Event columns
  - [ ] 5.2: Parse `consent.grant`, `consent.revoke`, `consent.expired`, `acl.grant`, `acl.revoke`, `acl.governance.transition` events
  - [ ] 5.3: Reactive watch: accumulate counts per pod, update_cell() for affected rows
- [ ] Task 6: [PODS] tab (AC: 3)
  - [ ] 6.1: DataTable: Pod Name, ACL State, Last Event Type, Last Event Time columns
  - [ ] 6.2: Derive pod state from consent + acl events (track per-pod grant/revoke/governance events)
  - [ ] 6.3: Update table reactively as new events arrive
- [ ] Task 7: JSONL file tailing (AC: 1-3)
  - [ ] 7.1: Implement `_tail_jsonl(file_path)` async generator — yields new JSON objects as they appear
  - [ ] 7.2: Background worker tasks in `on_mount()` for each of 3 files: `self.run_worker(self._poll_troll_events())`
  - [ ] 7.3: Worker tasks parse JSON and append to reactive list attributes
- [ ] Task 8: Tests (AC: 1-5)
  - [ ] 8.1: Unit test for event parsers (pipeline, troll, consent)
  - [ ] 8.2: Unit test for reactive watchers (verify table updates on reactive change)
  - [ ] 8.3: Integration test with mock JSONL files

## Dev Notes

### Architecture Change: Rich → Textual

**Decision:** Story 6.2 uses **Textual, NOT Rich** (hybrid approach).

- Story 3.7.1's pipeline dashboard (Rich) remains standalone and untouched
- Story 6.2 creates NEW file: `mission_control.py` (Textual-based mission control)
- Both can run simultaneously in different terminals
- Demo setup: Terminal 1 = Mission Control (mission_control.py), Terminal 2 = OpenClaw/CLI/Optional Pipeline Dashboard

**Why Textual for 6.2:**
- Native `TabbedContent` widget (professional UX, no faking tabs with sections)
- Reactive system for automatic UI updates (no manual polling)
- `DataTable` with `update_cell()` efficiency (large datasets)
- Async/background workers (non-blocking JSONL tailing)

### Textual Framework Patterns

**File:** `pipeline/src/pocpod0_pipeline/mission_control.py` (NEW, ~600-800 lines)

**Structure:**

```python
from textual.app import App, ComposeResult
from textual.widgets import TabbedContent, TabPane, DataTable, Static, Label
from textual.reactive import reactive

class MissionControlApp(App):
    """Mission Control TUI for funder-facing demo monitoring."""

    # Reactive attributes — changes trigger watcher methods
    troll_events = reactive([])           # List of parsed troll events
    consent_events = reactive([])         # List of consent/ACL events
    pipeline_events = reactive([])        # List of pipeline stage events
    health_status = reactive({})          # {service_name: {status, last_check}}

    # Watch methods called when reactive attributes change
    def watch_troll_events(self, new_events):
        """Update [TROLL] tab when new probe events arrive."""
        self.update_troll_table()

    def watch_consent_events(self, new_events):
        """Update [CONSENT] and [PODS] tabs when new consent events arrive."""
        self.update_consent_table()
        self.update_pods_table()

    def watch_health_status(self, new_status):
        """Update [HEALTH] tab when service status changes."""
        self.update_health_table()

    def compose(self) -> ComposeResult:
        """Create the tabbed interface."""
        yield TabbedContent(
            TabPane("HEALTH", self.HealthTab()),      # id="health"
            TabPane("PIPELINE", self.PipelineTab()),  # id="pipeline"
            TabPane("TROLL", self.TrollTab()),        # id="troll"
            TabPane("CONSENT", self.ConsentTab()),    # id="consent"
            TabPane("PODS", self.PodsTab()),          # id="pods"
            id="tabs"
        )

    def on_mount(self) -> None:
        """Initialize background worker tasks."""
        # Start background workers for JSONL file tailing
        self.run_worker(self._poll_troll_events())
        self.run_worker(self._poll_consent_events())
        self.run_worker(self._poll_pipeline_events())
        self.run_worker(self._poll_health_status())

    async def _poll_troll_events(self) -> None:
        """Background worker: tail data/troll-run.jsonl and update reactive attribute."""
        async for new_events in self._tail_jsonl(TROLL_JSONL_PATH):
            self.troll_events = new_events
            self.mutate_reactive(self.troll_events)  # Notify watcher

    # Similar for consent, pipeline, health...
```

### JSONL Event Catalog (All Sources)

**Pipeline events** (`data/pipeline-run.jsonl`):
| Event Type | Key Fields |
|---|---|
| `pipeline.start` | stages, wipe |
| `stage.start` | stage, label |
| `stage.done` | stage, elapsed |
| `stage.failed` | stage, elapsed |
| `pipeline.done` | total_elapsed |

**Troll events** (`data/troll-run.jsonl`):
| Event Type | Key Fields |
|---|---|
| `troll.run.start` | categories (Story 6.1 adds this) |
| `troll.probe.start` | category, test_name, layer (optional) |
| `troll.probe.done` | category, test_name, result, elapsed_ms |
| `troll.category.done` | category, passed, partial, failed |
| `troll.run.done` | total_elapsed, blocking_pass (Story 6.1 adds this) |

**Consent events** (`data/consent-events.jsonl`):
| Event Type | Key Fields |
|---|---|
| `consent.grant` | grant_id, pod, grantee_webid, purpose, scope |
| `consent.revoke` | grant_id, pod |
| `consent.expired` | token_id, pod, grant_id |
| `acl.grant` | pod, identity, action, role |
| `acl.revoke` | pod, identity |
| `acl.governance.transition` | pod, from_role, to_role, revoked_identities |
| `deletion.step` | pod, resource_uri, step, status |
| `deletion.complete` | resource_uri, pod, all_layers_clean |

### Textual Widget Patterns

**TabbedContent Example:**
```python
from textual.widgets import TabbedContent, TabPane, DataTable

def compose(self) -> ComposeResult:
    with TabbedContent(id="tabs"):
        with TabPane("HEALTH", id="health"):
            yield DataTable(id="health_table")
        with TabPane("PIPELINE", id="pipeline"):
            yield DataTable(id="pipeline_table")
        with TabPane("TROLL", id="troll"):
            yield DataTable(id="troll_table")
        with TabPane("CONSENT", id="consent"):
            yield DataTable(id="consent_table")
        with TabPane("PODS", id="pods"):
            yield DataTable(id="pods_table")
```

**Reactive Updates Example:**
```python
class TrollTab(Static):
    troll_events = reactive([])

    def watch_troll_events(self, new_events: list[dict]) -> None:
        """Called when troll_events reactive attribute changes."""
        table = self.query_one(DataTable)
        # Clear and rebuild, or use update_cell() for efficiency
        self._rebuild_troll_table(new_events)

    def _rebuild_troll_table(self, events: list[dict]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for event in events:
            row_key = str(event.get("probe_id", ""))
            result = event.get("result", "unknown")
            style = "green" if result == "pass" else ("yellow" if result == "partial" else "red")
            table.add_row(
                event.get("test_name", ""),
                event.get("category", ""),
                result,
                style=style,
                key=row_key
            )
```

**JSONL File Tailing with Async:**
```python
import json

async def _tail_jsonl(self, file_path: Path) -> AsyncIterator[list[dict]]:
    """Tail a JSONL file and yield new events as list."""
    events = []
    with open(file_path, "r") as f:
        # Read existing lines first
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        # Now follow new lines
        while True:
            line = f.readline()
            if line:
                try:
                    events.append(json.loads(line.strip()))
                    yield list(events)  # Yield accumulated events
                except json.JSONDecodeError:
                    pass
            else:
                await asyncio.sleep(0.1)  # Poll interval

async def _poll_troll_events(self) -> None:
    """Background worker: tail troll events and update reactive attribute."""
    async for new_events in self._tail_jsonl(TROLL_JSONL_PATH):
        self.troll_events = new_events
        self.mutate_reactive(self.troll_events)  # Notify watcher
```

### DataTable Color Coding

```python
from rich.style import Style

# Add row with style based on result
if result == "pass":
    style = Style(color="green")
elif result == "partial":
    style = Style(color="yellow")
else:
    style = Style(color="red")

table.add_row(*row_data, style=style, key=row_key)

# Or update an existing cell
table.update_cell(row_key, "result_column", Text(result, style=style))
```

### Key Files to Touch

| File | Action |
|------|--------|
| `pipeline/src/pocpod0_pipeline/mission_control.py` | **CREATE** — Textual mission control app (NEW, not extending pipeline_dashboard.py) |
| `pipeline/pyproject.toml` | **EDIT** — Add textual>=6.6.0 dependency, add `pocpod0-mission-control` script entry |
| `pipeline/tests/test_mission_control.py` | **CREATE** — Unit tests for event parsing and reactive updates |

### Key Files to Reference (READ ONLY)

| File | What to Extract |
|------|-----------------|
| `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` | Reference only — Rich TUI patterns (DO NOT EXTEND) |
| `pipeline/run_pipeline.py:46-51` | `_emit()` — pipeline JSONL format |
| `agents/troll-adversary/attacks/deletion_timing.py:150-180` | `_emit_jsonl()` — troll JSONL format |
| `pipeline/src/pocpod0_pipeline/consent_grant.py:118-128` | `_emit_consent_event()` — consent JSONL format |
| `pipeline/src/pocpod0_pipeline/governance_transition.py:64-72` | `_append_consent_event()` — governance event format |
| `agents/skills/acl-manage/handler.py:72-80` | ACL skill consent event format |
| `data/troll-run.jsonl` | 289 real events to validate parser against |
| `data/pipeline-run.jsonl` | 12 real events to validate parser against |
| `_bmad-output/planning-artifacts/architecture.md#INFRA-5` | Architecture decision (amended for hybrid approach) |
| `_bmad-output/implementation-artifacts/3-7-1-pipeline-dashboard-tui.md` | Reference for JSONL pattern, but not extending |
| **Textual Docs** | Context7: `/textualize/textual` — TabbedContent, DataTable, reactive patterns |

### Invalidated Assumptions

| Assumption | Status | Correction |
|---|---|---|
| Dashboard extends pipeline_dashboard.py (Rich) | INVALIDATED (by hybrid decision) | Mission control is NEW file (mission_control.py, Textual), separate from pipeline dashboard |
| Rich is the TUI framework for mission control | INVALIDATED (by hybrid decision) | **Textual** is now the framework for Story 6.2. Rich remains for Story 3.7.1 pipeline dashboard only. |
| Architecture INFRA-5 forbids Textual | CLARIFIED | INFRA-5 says "Rich TUI + JSONL" but hybrid approach splits this: Pipeline Dashboard (Rich, Story 3.7.1) + Mission Control (Textual, Story 6.2). Both use JSONL. Textual is appropriate for advanced dashboard features. |
| `agent.yaml` is the agent config | INVALIDATED (Epic 3.3) | Agents use SOUL.md / AGENTS.md / IDENTITY.md |
| `dashboard/` directory holds TUI code | PARTIAL | Both TUI modules live in `pipeline/src/pocpod0_pipeline/`: `pipeline_dashboard.py` (Rich) and `mission_control.py` (Textual). The `dashboard/` dir remains scaffolding only. |
| `consent-events.jsonl` has data | UNVERIFIED | File exists at 0 bytes — events are emitted during pipeline runs that exercise consent operations. May need a pipeline run first to populate |

### Hybrid Deployment Model

**Two separate TUI apps:**
1. **Story 3.7.1: Pipeline Dashboard** (Rich)
   - File: `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` (259 lines)
   - Entry: `pocpod0-pipeline-dashboard` script
   - Purpose: Monitor pipeline stages in real-time
   - Use: Optional, can run alone during pipeline runs

2. **Story 6.2: Mission Control** (Textual)
   - File: `pipeline/src/pocpod0_pipeline/mission_control.py` (NEW, ~600-800 lines)
   - Entry: `pocpod0-mission-control` script (NEW in pyproject.toml)
   - Purpose: Multi-tab funder-facing demo dashboard
   - Use: Primary demo interface during funder presentation

**Demo setup (two terminals):**
- Terminal 1: `pocpod0-mission-control` (mission_control.py)
- Terminal 2: OpenClaw browser, pipeline CLI, or optional `pocpod0-pipeline-dashboard`

### Dependencies

- **Story 6.0:** Stage 0 must exist for pipeline events to include provision step
- **Story 6.1:** Troll orchestrator must emit `troll.run.start`/`troll.run.done` wrapper events and `troll.category.done` per category
- **Consent modules (Epic 5):** Already emit events — no changes needed
- **Textual dependency:** Add `textual>=6.6.0` to `pipeline/pyproject.toml` dependencies

### Environment

- **Textual version:** `>=6.6.0` (latest stable with TabbedContent and DataTable optimizations)
- **Rich version:** `>=13.0` (pipeline_dashboard.py already has this)
- **Terminal size:** Demo terminal should be at least 120 columns wide, 40+ rows tall for readable multi-tab display
- **Distrobox note:** `distrobox-host-exec podman compose` for container commands
- **Terminal emulator:** Tested with xterm, GNOME Terminal, iTerm2. Avoid very old terminals without color/Unicode support.

### Previous Story Intelligence (Story 6.1)

- Story 6.1 creates the troll orchestrator with `troll.run.start`/`troll.run.done` JSONL wrapper events — mission_control.py depends on these for [TROLL] tab header/footer
- Existing `troll.probe.start`/`troll.probe.done`/`troll.category.done` events already exist from individual attack modules (Stories 1.5, 2.7, 2.8, 3.8, 5.3)

### Project Structure Notes

**New files:**
- `pipeline/src/pocpod0_pipeline/mission_control.py` — Textual mission control app (NEW)

**Modified files:**
- `pipeline/pyproject.toml` — Add `textual>=6.6.0` dependency, add `pocpod0-mission-control` script entry

**Unchanged files:**
- `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` — Remains as Story 3.7.1 (Rich, standalone)
- `dashboard/` — Remains scaffolding only

**Entry points:**
- `pocpod0-pipeline-dashboard` = `pocpod0_pipeline.pipeline_dashboard:main` (existing, Story 3.7.1)
- `pocpod0-mission-control` = `pocpod0_pipeline.mission_control:main` (NEW, Story 6.2)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.1 Mission Control TUI] — AC for mission control
- [Source: _bmad-output/planning-artifacts/architecture.md#INFRA-5] — Original dashboard architecture (Rich + JSONL) — amended for hybrid: Rich (pipeline) + Textual (mission control)
- [Source: _bmad-output/implementation-artifacts/3-7-1-pipeline-dashboard-tui.md] — Story 3.7.1 foundation (Rich, reference only)
- [Source: pipeline/src/pocpod0_pipeline/pipeline_dashboard.py] — Story 3.7.1 (Rich, reference only — do NOT extend)
- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-03-30.md#Epic 6 Preview] — Consent-events.jsonl event catalog action item
- [Source: Context7 Textual docs via /textualize/textual] — TabbedContent, DataTable, reactive patterns, async workers
  - TabbedContent: native tabs with interactive switching
  - DataTable: efficient rendering with update_cell() for live updates
  - reactive: automatic watcher methods for state changes
  - workers: background tasks for non-blocking JSONL tailing

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
