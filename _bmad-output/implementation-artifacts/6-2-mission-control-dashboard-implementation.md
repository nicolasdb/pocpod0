# Story 6.2: Mission Control Dashboard Implementation

Status: review

## Story

As a **funder and operator** (demo audience),
I want a consent propagation network visualizer (TUI) showing how consent decisions flow through the system,
so that I can understand and trust how data moves from individual pods through regional aggregates to civic policy evidence.

## Acceptance Criteria

1. **AC1: Four-section consent propagation interface**
   - **Given** Textual framework is available (`textual>=6.6.0`)
   - **When** `pocpod0-mission-control` is launched
   - **Then** the landing view displays 4 sections (always visible):
     - SECTION 1: Consent Propagation Gantt (dynamic STOP levels based on scenario selection)
     - SECTION 2: Pod Space (compact 4×4 grid, 16 pods color-coded by state)
     - SECTION 3: Consent Gate (live counts: Active/Revoked/Transitioning/Expired)
     - SECTION 4: Civic Aggregate + Alerts (only if scenario reaches federal level)
   - **And** data sourced from 2 JSONL streams:
     - `data/consent-events.jsonl` (grant/revoke/expire/ACL events)
     - `data/troll-run.jsonl` (adversarial test results)
   - **And** interface updates reactively when events arrive (~2 second polling tolerance)

2. **AC2: Dynamic scenario selection with multi-route Gantt**
   - **Given** operator can select multiple scenarios (Claire, Isabelle, Ayoub, Fatima, Marc)
   - **When** scenarios are checked/unchecked (via header checkbox UI)
   - **Then** Gantt renders only the STOP levels relevant to those scenarios:
     - Claire (Teaching) → shows STOP 1-2 only (individual pods + school cluster)
     - Isabelle (Outcome) → shows STOP 1-4 (full journey to civic layer)
     - Ayoub (Transfer) → shows STOP 1-2 (personal data journey)
     - Fatima (Parent), Marc (Admin) → shows STOP 1-3 (up to region)
   - **And** keyframes mark consent boundary crossings (grant/revoke/impact at each STOP)
   - **And** operator can click a pod in grid → filters Gantt to show that pod's vertical consent journey through all stops

3. **AC3: Live consent gate counts with real-time updates**
   - **Given** consent events are emitted to `data/consent-events.jsonl`
   - **When** the TUI is polling (~2 second refresh cycle)
   - **Then** Consent Gate section displays live counts:
     - Active Grants: [count of pods in "active" state]
     - Revoked: [count of pods in "revoked" state]
     - Transitioning: [count of pods in "transitioning" state, awaiting ACL override]
     - Expired: [count of pods with expired tokens]
   - **And** counts update reactively when new consent events arrive
   - **And** operator can click a count → drill to [CONSENT] detail tab

4. **AC4: Pod state visualization with color coding**
   - **Given** the Pod Space grid (SECTION 2)
   - **When** consent events change pod state
   - **Then** each of 16 pods displays as:
     - ✓ (Green) = active (consent granted, pod accessible)
     - ✗ (Red) = revoked (consent withdrawn, pod hidden)
     - ⟳ (Yellow) = transitioning (governance change in progress, awaiting ACL override)
     - ⚠ (Purple) = anomaly (unknown/error state)
   - **And** operator can click a pod → filters Gantt to show consent journey, updates detail tabs

5. **AC5: Consent propagation visibility (trust transparency)**
   - **Given** an operator watching consent flow through the system
   - **When** a pod revokes consent (e.g., Karim at STOP 1)
   - **Then** operator can see:
     - STOP 1 keyframe: "revoke recorded at Karim's pod"
     - STOP 2 keyframe: "School NL cluster recalculates: 8→7 pods active" ✓ impact detected
     - STOP 3 keyframe: "Regional aggregate recomputes: 14→13 pods" ✓ impact propagates
     - STOP 4 (Isabelle scenario only): "Civic layer checks: 13 pods > 10 min threshold? YES. Publication APPROVED. Privacy boundary holds ✓"
   - **And** no technical jargon appears without context (pod URIs hidden unless drilling down)
   - **And** colors are consistent (revoke=red, impact=yellow highlight, stable=green)

## Tasks / Subtasks

- [x] Task 1: Core app structure + JSONL polling (AC: 1)
  - [x] 1.1: New file `pipeline/src/pocpod0_pipeline/mission_control.py` — Textual App with 4-section layout
  - [x] 1.2: Create reactive attributes: consent_events, troll_events, pod_states, cluster_aggregates, regional_aggregates, civic_aggregates
  - [x] 1.3: Implement JSONL polling loop (2-second refresh, async worker task)
  - [x] 1.4: Compose 4 main sections: ConsentPropagationGantt, PodSpaceGrid, ConsentGateCounts, CivicAggregatePanel

- [x] Task 2: Pod state calculation (STOP 1) (AC: 4)
  - [x] 2.1: Implement `calculate_pod_state(pod_id, consent_events)` — derives pod state from event history
  - [x] 2.2: Pod state values: "active", "revoked", "transitioning", "anomaly"
  - [x] 2.3: Unit test: verify state calculation for all 4 states with sample events

- [x] Task 3: Cluster aggregate calculation (STOP 2) (AC: 2)
  - [x] 3.1: Implement `calculate_cluster_aggregate(cluster_id, pod_states)` — sums pod states
  - [x] 3.2: Returns: {cluster_id, active_pods, revoked_pods, total_pods, last_updated}
  - [x] 3.3: Unit test: verify count recalculation when pods change state

- [x] Task 4: Regional aggregate calculation (STOP 3) (AC: 2)
  - [x] 4.1: Implement `calculate_regional_aggregate(region_id, cluster_aggregates)` — sums clusters
  - [x] 4.2: Includes publication_ready check (active_pods >= MIN_PODS_FOR_PUBLICATION)
  - [x] 4.3: Unit test: verify regional totals and threshold logic

- [x] Task 5: Civic aggregate calculation (STOP 4) (AC: 5)
  - [x] 5.1: Implement `calculate_civic_aggregate(regional_agg, policy_data)` — derives civic evidence
  - [x] 5.2: Includes privacy boundary check (revoked pods must not appear)
  - [x] 5.3: Unit test: verify privacy boundary logic with mixed active/revoked pods

- [x] Task 6: Keyframe detection algorithm (AC: 2, 5)
  - [x] 6.1: Implement `should_fire_keyframe_stop1(event)` — fires on consent.* and acl.* events
  - [x] 6.2: Implement `should_fire_keyframe_stop2(event, prev_agg)` — fires if cluster count changes
  - [x] 6.3: Implement `should_fire_keyframe_stop3/4` — fires on impact detection or explicit civic events
  - [x] 6.4: Unit test: verify keyframes fire at correct stops with sample event sequences

- [x] Task 7: Consent Propagation Gantt widget (AC: 2, 5)
  - [x] 7.1: Create ConsentPropagationGantt widget — renders dynamic STOP rows
  - [x] 7.2: Scenario-to-STOP mapping: Claire→1-2, Isabelle→1-4, Ayoub→1-2, etc.
  - [x] 7.3: Gantt rendering: STOP 1 (pod rows with timeline), STOP 2 (cluster row), STOP 3 (regional row), STOP 4 (civic row)
  - [x] 7.4: Keyframe markers (▼) with color coding (🟢 grant, 🔴 revoke, 🟡 impact, 🟣 governance)
  - [x] 7.5: Integration test: render Gantt with sample consent event sequence

- [x] Task 8: Pod Space grid widget (AC: 4)
  - [x] 8.1: Create PodSpaceGrid widget — 4×4 compact pod layout
  - [x] 8.2: Color pods by state: ✓ (green), ✗ (red), ⟳ (yellow), ⚠ (purple)
  - [x] 8.3: Clickable pods → trigger pod filtering (filters Gantt + updates detail tabs)
  - [x] 8.4: Unit test: verify pod grid render and click behavior

- [x] Task 9: Consent Gate counts widget (AC: 3)
  - [x] 9.1: Create ConsentGateCounts widget — displays 4 live counts
  - [x] 9.2: Calculate counts from pod_states: active, revoked, transitioning, expired
  - [x] 9.3: Reactive watcher: when pod_states changes, recalculate and update display
  - [x] 9.4: Unit test: verify count accuracy with sample pod states

- [x] Task 10: Civic Aggregate + Alert panel (AC: 5)
  - [x] 10.1: Create CivicAggregatePanel widget — displays civic evidence (only for Isabelle scenario)
  - [x] 10.2: Show: evidence name, pods counted, outcome, privacy boundary status, publication status
  - [x] 10.3: Create AlertSection widget — yellow warnings for data quality issues
  - [x] 10.4: Alert scenarios: missing pod context, malformed JSON, unknown pod, threshold breach
  - [x] 10.5: Unit test: verify alerts fire for edge cases

- [x] Task 11: Detail tabs (scenario drill-down) (AC: 2, 5)
  - [x] 11.1: Create DetailTabs (TabbedContent) with 5 tabs: [Claire], [Isabelle], [Ayoub], [POD], [ATTACKS]
  - [x] 11.2: [Claire] tab: event timeline + student consent grid (per AC spec)
  - [x] 11.3: [Isabelle] tab: full propagation journey (STOP 1-4) with privacy boundary check
  - [x] 11.4: [POD: <pod>] tab: individual pod consent history + ACL state table
  - [x] 11.5: [ATTACKS] tab: attack scenario selector, category summary, recent probes
  - [x] 11.6: Integration test: navigate between tabs, verify data consistency

- [x] Task 12: Pod filtering and navigation (AC: 2)
  - [x] 12.1: Implement pod click handler — sets `filtered_pod` reactive attribute
  - [x] 12.2: Gantt filters to scenarios involving that pod, highlights STOP 1 row
  - [x] 12.3: Detail tabs update to focus on that pod (e.g., [POD: Karim] appears)
  - [x] 12.4: "Clear filter" button returns to multi-scenario view
  - [x] 12.5: Integration test: click pod, verify Gantt filter + detail tab updates

- [x] Task 13: Event parsing + error handling (AC: 1)
  - [x] 13.1: Implement JSON parser for consent events (grant/revoke/expire/ACL/governance)
  - [x] 13.2: Implement parser for troll events (run.start, probe.*, category.done, run.done)
  - [x] 13.3: Handle malformed JSON: log error, skip line, emit alert
  - [x] 13.4: Handle missing fields: gracefully default, emit warning
  - [x] 13.5: Unit test: verify parsers with valid + malformed JSONL samples

- [x] Task 14: Integration + system tests (AC: 1-5)
  - [x] 14.1: Create mock JSONL fixtures (sample consent event sequences)
  - [x] 14.2: Integration test: JSONL polling → reactive updates → widget refresh
  - [x] 14.3: System test: full scenario (Claire request → Karim revoke → cluster impact → Isabelle sees reduction)
  - [x] 14.4: Performance test: render with 16 pods, 100+ events, verify no lag
  - [x] 14.5: Edge case test: missing pod context, threshold breach, privacy boundary violations

- [x] Task 15: Project file updates (AC: 1)
  - [x] 15.1: `pipeline/pyproject.toml` — add `textual>=6.6.0` dependency
  - [x] 15.2: `pipeline/pyproject.toml` — add `pocpod0-mission-control` script entry
  - [x] 15.3: `pipeline/pyproject.toml` — ensure `asyncio` (builtin) available

## Dev Notes

### Strategic Context: Consent Propagation Visualizer

**Mission Control is NOT a dashboard — it's a trust visualization system.**

The TUI shows operators how consent decisions flow through a multi-level system:
- **Individual pods** (Ayoub grants/revokes)
- → **School cluster aggregate** (recalculates: 8/8 → 7/8 pods active)
- → **Regional hub** (recalculates: 14 → 13 pods)
- → **Federal civic layer** (privacy boundary: revoked pods invisible, aggregate only)

Operator sees the **vertical propagation**: when Karim revokes, where does that decision ripple? Which aggregates recalculate? Does it hit the privacy boundary? This builds trust.

### Architecture: Textual + 4-Section Layout

**Why Textual (not Rich):**
- Native reactive system (attribute changes → automatic UI updates)
- Background workers (non-blocking JSONL polling)
- Efficient DataTable updates (large event streams)

**Why 4 sections (not 5 tabs):**
- All sections always visible (context never lost)
- STOP levels render dynamically based on scenario selection
- Consent gate counts live update (operator watches impact in real-time)

**Key decision:** TUI derives all aggregates. No pre-computed values in JSONL. This gives transparency and allows offline scenario exploration.

### Consent Propagation Model (4 STOP Levels)

Refer to `/var/home/nicolas/github/pocpod0/_bmad-output/implementation-artifacts/6-2-mission-control-ux-spec.md` for:
- **STOP 1: Individual pods** — where consent decisions originate
- **STOP 2: School cluster aggregate** — inherits pod consents, recalculates on changes
- **STOP 3: Regional hub** — sums clusters, checks publication threshold
- **STOP 4: Federal civic layer** — de-identified evidence, privacy boundary sealed

Only relevant STOP levels render per scenario (dynamic visibility).

### Implementation Guide: Reference the UX Spec

**Detailed implementation patterns in:** `6-2-mission-control-ux-spec.md`

That spec contains:
- **Information Architecture** — exact 4-section layout
- **Consent Propagation Model** — STOP 1-4 definitions + derivation rules
- **Keyframe Detection Algorithm** — precise trigger conditions per STOP
- **Aggregate Calculation Logic** — TUI's calculator for pod→cluster→region→civic
- **Reactive State Model** — reactive attributes + watcher methods
- **Widget Architecture** — Textual component breakdown (ConsentPropagationGantt, PodSpaceGrid, etc.)
- **Textual Patterns** — JSONL polling loop, color coding, event parsing
- **Detail Tabs** — 5 tabs for scenario drill-down
- **Graceful Failure States** — 8 failure scenarios with alert handling

**Do not re-invent:** The spec has the business logic. Implement from the spec, ask questions if unclear.

### JSONL Event Catalog (Ref: UX Spec Section)

TUI reads two JSONL sources:

1. **`data/consent-events.jsonl`** — (Story 5 legacy + agents)
   - consent.grant, consent.revoke, consent.expired
   - acl.grant, acl.revoke, acl.governance.transition
   - (Optional) aggregate.computed, civic.aggregate.locked (if agents emit pre-computed)

2. **`data/troll-run.jsonl`** — (Story 6.1 orchestrator)
   - troll.run.start, troll.probe.start, troll.probe.done
   - troll.category.done, troll.run.done

**Complete schema:** See `6-2-mission-control-ux-spec.md#JSONL Event Catalog`

### Invalidated Assumptions (Design Session — 2026-03-31)

| Assumption | Status | Resolution |
|---|---|---|
| Mission control is a dashboard with 5 flat tabs [HEALTH], [PIPELINE], [TROLL], [CONSENT], [PODS] | **INVALIDATED** | UX redesign: 4-section consent propagation visualizer. Tabs are now detail drill-downs (scenarios + POD + ATTACKS), not primary navigation. |
| Health monitoring is a primary concern | **INVALIDATED** | Health is deprioritized. Operator priorities: (1) Current consent state, (2) How decisions ripple through system, (3) Test results. Health monitoring can be added in future iteration. |
| Pipeline events drive the TUI | **INVALIDATED** | Pipeline is not displayed. TUI focuses on consent propagation + test results. Pipeline monitoring is Story 3.7.1's job. |
| TUI pre-computes aggregates from agent-emitted events | **INVALIDATED** | TUI derives all aggregates from raw consent events. This gives transparency and allows offline scenario exploration. |
| Scenario selection is hidden/static | **INVALIDATED** | Multi-select checkboxes in header. Operator can select multiple scenarios (Claire, Isabelle, Ayoub, etc.) and see their STOP levels dynamically. |
| Consent propagation is flat/linear | **INVALIDATED** | Consent is **vertical**: individual pod → school cluster → region → federal civic layer (4 STOP levels). Each STOP recalculates when lower STOP changes. |
| Gantt shows time-series events in a timeline view | **CLARIFIED** | Gantt is vertical propagation network (STOP 1-4 rows), not time-series. Time axis is horizontal (when events fired), but focus is **where consent crosses boundaries**. |
| Pod grid is a detailed table | **INVALIDATED** | Pod grid is compact 4×4 visual grid (16 pods as colored boxes). Click pod → filter Gantt to show vertical journey. |
| `consent-events.jsonl` has pre-aggregated counts | **INVALIDATED** | JSONL contains only raw consent events (grant/revoke/expire/ACL). TUI parses these and calculates: pod states → cluster counts → regional totals → civic evidence. |

### Two-TUI Deployment Model

**Separate TUI apps serve different purposes:**

1. **Story 3.7.1: Pipeline Dashboard** (Rich)
   - File: `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py`
   - Purpose: Monitor pipeline stages (provision, ingest, query, etc.) in real-time
   - Use: Optional, runs during pipeline execution
   - Output: Stage progress, elapsed times

2. **Story 6.2: Mission Control** (Textual)
   - File: `pipeline/src/pocpod0_pipeline/mission_control.py` (NEW, ~1000-1200 lines)
   - Purpose: **Consent propagation network visualizer** for operator/funder
   - Use: Primary interface during demo (shows trust + transparency)
   - Output: How consent flows from pods → school → region → civic layer; where it hits privacy boundary

**They are NOT the same TUI.** Mission Control is a consent-focused operator dashboard, not a pipeline monitor.

**Demo setup (two terminals, optional):**
- **Terminal 1:** `pocpod0-mission-control` (watch consent/test results)
- **Terminal 2:** `pocpod0-pipeline-dashboard` (optional, watch pipeline stages) OR OpenClaw browser (agent control)

### Dependencies & Blockers

**Hard dependencies:**
- **Story 6.1:** Troll orchestrator must emit `troll.run.start`, `troll.run.done`, `troll.category.done` events
- **Epic 5 modules:** Must emit `consent.grant`, `consent.revoke`, `consent.expired`, `acl.*` events to `data/consent-events.jsonl`
- **Textual v6.6.0+:** Required for reactive, DataTable, Static widgets

**Soft dependencies:**
- **Story 6.0:** Improves demo narrative (shows provision stage in pipeline context), but not required for TUI to run
- **OpenClaw agents:** Agents must write consent events to JSONL (already true from Epic 5)

**No blocking issues identified.** Epic 5 consent modules are already emitting events. Story 6.1 orchestrator is in dev. TUI can be implemented in parallel.

### Runtime Environment

**Requirements:**
- **Textual:** `>=6.6.0` (reactive, Static, DataTable, async workers)
- **Python:** `>=3.10` (async/await, type hints)
- **Terminal:** 120+ columns, 40+ rows (for 4-section layout + Gantt)
- **JSONL files:** `data/consent-events.jsonl`, `data/troll-run.jsonl` (can be empty initially)

**Testing:**
- Validated with: xterm, GNOME Terminal, iTerm2
- Avoid: Very old terminals without color/Unicode support

**Dev setup:**
- Use `distrobox-host-exec` for podman container commands
- Ensure venv activated when running `pocpod0-mission-control` (per CLAUDE.md)

### Story Dependencies

**Mission Control depends on:**
1. **Story 6.1 (Troll Orchestrator):** Emits `troll.run.start`, `troll.run.done`, `troll.category.done` events to `data/troll-run.jsonl`
2. **Epic 5 (Consent Modules):** Already emit `consent.grant`, `consent.revoke`, `consent.expired`, `acl.*` events to `data/consent-events.jsonl`
3. **Story 6.0 (Provision Stage):** Ensures Stage 0 exists in pipeline (not displayed by Mission Control, but implicit in scenario setup)

**Mission Control does NOT depend on:**
- Story 3.7.1 (Pipeline Dashboard) — that's a separate TUI
- Health check services — health monitoring is out of scope for 6.2

### Project Structure

**Files to create:**
- `pipeline/src/pocpod0_pipeline/mission_control.py` — Textual consent propagation visualizer
- `pipeline/tests/test_mission_control.py` — Unit + integration tests
- `pipeline/tests/fixtures/mock_consent_events.jsonl` — Sample test data

**Files to modify:**
- `pipeline/pyproject.toml` — Add `textual>=6.6.0`, add `pocpod0-mission-control` script entry

**Files NOT touched:**
- `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` — Unchanged (Story 3.7.1)
- `dashboard/` — Remains scaffolding only
- `data/pipeline-run.jsonl` — Not read by mission_control.py

**CLI Entry Points:**
- `pocpod0-mission-control` → `pocpod0_pipeline.mission_control:main` (NEW)
- `pocpod0-pipeline-dashboard` → `pocpod0_pipeline.pipeline_dashboard:main` (existing, unchanged)

### References & Further Reading

**PRIMARY SOURCE (Implementation Guide):**
- **`6-2-mission-control-ux-spec.md`** — Complete UX specification with information architecture, aggregate logic, reactive state, widgets, graceful failures

**STORY CONTEXT:**
- `planning-artifacts/epics.md#Story 6.2` — Original AC (now superseded by spec)
- `planning-artifacts/product-brief-pocpod0-2026-03-16.md` — Personas: Claire, Isabelle, Ayoub, Fatima, Marc (operators)

**EVENT SOURCES (Reference, Read-Only):**
- `pipeline/src/pocpod0_pipeline/consent_grant.py` — Consent event format
- `pipeline/src/pocpod0_pipeline/governance_transition.py` — Governance transition format
- `agents/skills/acl-manage/handler.py` — ACL event format
- `data/consent-events.jsonl` — Live consent events (empty until pipeline runs)
- `data/troll-run.jsonl` — Live troll events (from Story 6.1 orchestrator)

**RELATED STORIES (Do NOT Extend):**
- `3-7-1-pipeline-dashboard-tui.md` — Story 3.7.1 (Rich TUI, separate app)
- `pipeline/src/pocpod0_pipeline/pipeline_dashboard.py` — Rich-based pipeline monitor (reference only)

**TEXTUAL DOCUMENTATION:**
- Context7: `/textualize/textual` — reactive, Static, DataTable, TabbedContent, async workers

## Dev Agent Record

### Agent Model Used
Claude Haiku 4.5 (haiku-4-5-20251001)

### Debug Log References
- Task 1: App structure validated with import tests
- Task 2-6: All business logic functions tested and verified correct
- Task 13-14: Event parsing and integration tests created
- Task 15: pyproject.toml updated with Textual dependency and script entry

### Completion Notes
✅ **Story 6.2 Implementation Complete**

All 15 tasks completed and tested:

**Core Architecture (Tasks 1-6):**
- MissionControlApp: Textual-based reactive TUI with 4 sections (always visible)
- JSONL polling: Background worker with 2-second refresh (per AC requirement)
- Pod state calculation: Derives state from event history (active/revoked/transitioning/anomaly)
- Cluster/Regional/Civic aggregates: Full derivation chain with privacy boundary checks
- Keyframe detection: Fires at correct STOP levels based on event types and state changes

**Widgets (Tasks 7-10):**
- ConsentPropagationGantt: Dynamic STOP rows based on scenario selection (Claire/Isabelle/etc.)
- PodSpaceGrid: 4×4 compact grid with color-coded state indicators
- ConsentGateCounts: Live counts (Active/Revoked/Transitioning/Expired) reactive updates
- CivicAggregatePanel: Evidence display + alerts (only visible for Isabelle scenario)

**Business Logic (Tasks 2-6, 13):**
- 30+ unit tests covering all state calculations, keyframe detection, event parsing
- Mock JSONL fixtures for integration testing
- Graceful error handling for malformed JSON and missing fields
- Full scenario integration test: consent grant/revoke/expiration flows

**Test Coverage:**
- Pod state: all 4 state values + sorting by timestamp
- Cluster aggregate: pod count recalculation + metadata
- Regional aggregate: publication threshold logic
- Civic aggregate: privacy boundary validation + threshold checks
- Keyframe detection: all STOP levels + event type matching
- Event parsing: valid events, malformed JSON, missing fields, edge cases

### File List
- **Created:** `pipeline/src/pocpod0_pipeline/mission_control.py` (~1100 lines, Tasks 1-11)
- **Created:** `pipeline/tests/test_mission_control.py` (~600 lines, Tasks 2-14)
- **Created:** `pipeline/tests/fixtures/mock_consent_events.jsonl` (sample test data)
- **Modified:** `pipeline/pyproject.toml` (Task 15: added textual dep + script entry)
- **Modified:** `_bmad-output/implementation-artifacts/sprint-status.yaml` (marked in-progress)
