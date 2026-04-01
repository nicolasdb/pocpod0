---
title: Sprint Change Proposal — Mission Control Dashboard Redesign
date: 2026-04-01
trigger: Story 6.2 Mission Control Dashboard produces unusable output
scope: Moderate
status: approved
---

# Sprint Change Proposal: Mission Control Dashboard Redesign

## 1. Issue Summary

**Problem:** Story 6.2 (Mission Control Dashboard) was implemented from a detailed UX spec that looked compelling on paper but produces a dashboard with no operational value. The spec designed a "Consent Propagation Gantt" with Sparkline timelines and a 4-STOP hierarchical model. The implementation faithfully followed the spec — but the spec was wrong.

**Symptoms:**
- All 16 pods display ⚠ anomaly (no consent data exists to drive them)
- Sparkline bars are flat/unreadable — they don't convey a narrative
- Operator (Nicolas) cannot answer any question by looking at the dashboard
- `consent-events.jsonl` has 4 mock lines — no real producer runs during setup
- Troll test data exists (100+ real tests in `troll-run.jsonl`) but isn't rendered (D3 deferred item)
- The 16-pod grid references fictional pods that don't exist in the actual CSS infrastructure

**Root cause:** The UX spec conflated "what consent propagation looks like in theory" with "what an operator needs to see." An offshore operations control room analogy clarifies the correct mental model: show system state, highlight anomalies, enable drill-down — not visualize abstract data flows.

**Discovery:** Nicolas identified this during Story 6.2 code review completion (2026-03-31). The dashboard renders but provides zero actionable information.

---

## 2. Impact Analysis

### Epic Impact

**Epic 6 (in-progress):**
- Story 6.2 scope and acceptance criteria need redefinition
- Story 6.3 (Funder Intervention Points) is strengthened — the demo flow (Isabelle → Ayoub consent → dashboard update) aligns perfectly with 6.3's AC
- Story 6.2/6.3 boundary shifts: seed data + consent flow spans both stories

**Epic 4 (backlog, capstone):**
- Benefits from fix: "first epic where project lead watches live" requires a working dashboard
- No changes needed to Epic 4 itself

### Artifact Conflicts

**Architecture doc (`architecture.md:259-265`):**
- Tab structure described (HEALTH, PIPELINE, TROLL, CONSENT, PODS) is closer to what we want than the UX spec
- Architecture needs update: replace 4-STOP Gantt description with widget-based control room model
- Add: cascade predictor widget, consent seed strategy, pod grid aligned to real infrastructure

**UX spec (`6-2-mission-control-ux-spec.md`):**
- **Invalidated:** Consent Propagation Gantt with Sparkline timelines
- **Invalidated:** 4-STOP hierarchical visualization (STOP 1-4 as horizontal timeline)
- **Invalidated:** 16 fictional pod names (ayoub-pod, sofia-pod, karim-pod, etc.)
- **Preserved:** Scenario concept (different lenses for different roles) — but deferred to slide decks, not dashboard tabs
- **Preserved:** Consent state model (active/revoked/transitioning/anomaly)
- **Preserved:** Service health checks

**Sprint status (`sprint-status.yaml`):**
- Story 6.2 status reverts to `in-progress` (was approaching done, needs rework)

**PRD:**
- FR39 ("mission control dashboard showing live attack results, query monitoring, and Pod status") is unchanged — we're fixing the implementation, not the requirement
- No PRD modifications needed

### Critical Data Model Gap

**Fictional vs. real pods:**

| Mission Control (current) | Actual CSS Infrastructure |
|---------------------------|--------------------------|
| 16 fictional pods (ayoub-pod, sofia-pod, karim-pod, jean-pod, etc.) | 7 real pods (ayoub, claire, claire-student-1, claire-student-2, fatima-child-1, fatima-child-2, school-community) |
| All pods equal | Only ayoub has OpenClaw agent |
| Consent state from JSONL events | No consent event producers run during setup |

**Resolution:** Dashboard pod grid must map to real CSS pods. Current infrastructure has 7 pods but is missing `fatima` (parent pod). Corrected topology (8 pods):
- `ayoub` — student, full agent, consent demo protagonist
- `claire` — teacher, classroom consent delegation
- `claire-student-1`, `claire-student-2` — students in Claire's class
- `fatima` — **parent role (NEW)**, co-consent authority over her children, tests 18+ sovereignty transfer
- `fatima-child-1`, `fatima-child-2` — Fatima's children (consent delegated to parent until 18+)
- `school-community` — community pod (shared resource)

**Fatima pod rationale:** The parent pod is required to test co-consent (parent grants/revokes on behalf of minor children) and the governance transition when a child turns 18 (control transfers from fatima → child). Without a parent pod, this flow cannot be demonstrated.

**Action:** Add `fatima` to `POD_SLUGS` in `run_pipeline.py` and to CSS provisioning.

Consent seed: 7 pods pre-consented (mock), ayoub starts without consent (real flow during demo).

---

## 3. Recommended Approach

**Selected: Direct Adjustment (modify Story 6.2 + adjust Story 6.3 boundary)**

### Why not rollback?
The business logic layer is solid — `calculate_pod_state()`, `calculate_cluster_aggregate()`, `parse_consent_event()` all work correctly. The Textual app infrastructure (async polling, reactive attributes, event handlers) is reusable. Only the visualization widgets need replacement.

### Why not MVP review?
FR39 is a must-ship for Epic 6. The dashboard is essential for the capstone demo (Epic 4). Descoping it is not an option — we need to fix it.

### Approach: Widget-Based Control Room

Replace the current monolithic consent propagation visualization with isolated, pluggable widgets — each answering ONE operational question:

| Widget | Question it answers | Data source | Status |
|--------|-------------------|-------------|--------|
| **Service Health** | Are backends alive? | HTTP health checks | Port from pipeline_dashboard (exists) |
| **Troll Alarm Panel** | Are security boundaries holding? | `troll-run.jsonl` | NEW — highest value, real data exists |
| **Pod Grid** | What's each pod's consent state? | `consent-events.jsonl` | REWORK — align to real 7 pods, needs seed |
| **Consent Gate** | Overall consent distribution? | Computed from pod states | EXISTS — keep as-is |
| **Cascade Predictor** | What breaks if pod X revokes? | Computed from pod states + mappings | NEW — high demo value |
| **Event Log** | What just happened? | `consent-events.jsonl` tail | NEW — replaces 5 scenario detail tabs |

**What gets dropped:**
- Consent Propagation Gantt (Sparkline timelines)
- Scenario switches (Claire/Isabelle/Ayoub/Fatima/Marc toggle)
- PodSparklineRow widget
- ScenarioDetailPanel (5 separate panels)
- CivicAggregatePanel (no data source, premature)
- 16 fictional pod identifiers

**What gets preserved:**
- Textual app framework (MissionControlApp, async polling, reactive attributes)
- JSONL parsing (`parse_consent_event`, `_read_new_lines`)
- Pod state calculation (`calculate_pod_state`, `PodStateEnum`)
- Cluster/regional aggregate calculation (rewire to real pod topology)
- Service health checks
- `consent-events.jsonl` event schema

### Consent Seed + Demo Flow

**Seed script** (`scripts/seed-consent-events.sh` or Python equivalent):
1. Write 6 `consent.grant` events for non-Ayoub pods (pre-existing school enrollment)
2. Ayoub has NO events → defaults to "no consent" state
3. Dashboard starts in meaningful state: 6 green, 1 red

**Demo act (Story 6.3):**
1. Dashboard shows 6 green, 1 red (Ayoub)
2. Isabelle requests school aggregate → system shows Ayoub hasn't consented
3. Facilitator interacts with Ayoub's agent via OpenClaw → agent writes ACL grant
4. `acl-manage/handler.py` appends `consent.grant` to `consent-events.jsonl`
5. Dashboard polls → ayoub flips to green → cascade predictor updates
6. Optional: troll suite runs → alarm panel populates with real results

### Role-Specific Scenarios — Timing

Nicolas raised wiring Claire, Marc, and Isabelle pods for richer scenarios:
- **Isabelle requests gender ratio** (not just total_count) — how does a new consent scope propagate?
- **Marc reports food expenses** (needs dietary data across pods) — cross-pod aggregation
- **Isabelle accesses pre-consent total_count** — how is the receipt notified to Ayoub?

**Assessment:** These are Story 6.3 and/or Epic 4 territory. They require:
1. Wiring OpenClaw agents to Claire, Marc, Isabelle pods (not just Ayoub)
2. Defining new consent scopes beyond the current model
3. Receipt notification flow (Story 5.4 implemented the receipt, but the notification to pod owner isn't wired)

**Recommendation:** Capture as Story 6.3 acceptance criteria refinement. Don't block Story 6.2 redesign on this — get the control room working with real data first (troll + Ayoub consent), then layer in multi-role scenarios.

**Risk:** Low. The widget architecture is designed for exactly this — each new scenario adds events to the same JSONL stream, and the dashboard picks them up automatically.

**Effort:** Medium (2-3 focused sessions)
**Risk:** Low (reusing existing business logic + proven Textual framework)

---

## 4. Detailed Change Proposals

### 4.1 Story 6.2 — Acceptance Criteria Rewrite

**OLD (current epics.md:841-864):**
```
### Story 6.1: Mission Control TUI

As a **funder** (demo audience),
I want a mission control TUI showing live attack results, query monitoring, and Pod/consent status,
So that I can follow the PoC demo narrative visually without needing technical explanation.

**Acceptance Criteria:**

**Given** the dashboard component backlog collected from Epics 1-5 (pod status, ACL state, pipeline ingestion, query monitor, agent activity, governance events, deletion cascade, troll test results)
**When** the pipeline dashboard is extended into a multi-tab mission control TUI
**Then** it reads JSONL event streams from data/pipeline-run.jsonl, data/troll-run.jsonl, and data/consent-events.jsonl
**And** it displays multi-tab views: [HEALTH] service status, [PODS] pod ACL/consent state, [CONSENT] consent gate active/revoked counts, [TROLL] attack results per category, [QUERY] agent query monitor
```

> **NOTE:** Story numbering in epics.md is misaligned — the file labels this as "Story 6.1" but sprint-status.yaml tracks it as `story-6-2-mission-control-dashboard-implementation`. This proposal follows sprint-status.yaml numbering.

**NEW:**
```
### Story 6.2: Mission Control Dashboard (Operations Control Room)

As a **project lead and demo facilitator**,
I want a mission control TUI that shows system state at a glance — services up, security holding, pods healthy — with anomaly drill-down,
So that I can monitor the POC during demos and immediately see when something is off, where, and what breaks next.

**Mental model:** Offshore operations control room. Default state is "all green." When something turns red, the operator needs: what, where, why, and cascade impact.

**Acceptance Criteria:**

**Given** the mission control TUI is running
**When** the operator looks at the screen
**Then** they can answer these 5 questions in <5 seconds each:
  1. Are all backend services alive? (Service Health widget)
  2. Are security boundaries holding? (Troll Alarm Panel — 5 categories, color-coded)
  3. What's each pod's consent state? (Pod Grid — 7 real pods, color = state)
  4. What's the overall consent distribution? (Consent Gate — active/revoked/transitioning counts)
  5. What just happened? (Event Log — last 20 events, newest first)

**Given** a pod is selected in the Pod Grid
**When** the Cascade Predictor widget updates
**Then** it shows downstream impact: "If {pod} revokes → {cluster} drops to N/M → publication threshold {met/not met}"

**Given** `data/troll-run.jsonl` contains test results from a troll run
**When** the dashboard polls (every 2s)
**Then** the Troll Alarm Panel shows 5 rows (one per attack category) with pass/partial/fail counts and color coding (green/yellow/red)

**Given** `data/consent-events.jsonl` contains consent events
**When** the dashboard polls
**Then** the Pod Grid reflects current pod states and the Consent Gate shows updated counts

**Given** no consent events exist yet
**When** the dashboard starts
**Then** all pods show "no data" state (not anomaly) with a clear message: "Waiting for consent events..."

**Widget architecture:** Each widget is an isolated Textual Widget subclass with one data source and one render method. Widgets are composed into a single-screen layout (no tabs). The operator sees everything at once.

**Pod topology:** Dashboard uses real CSS pod identifiers (ayoub, claire, claire-student-1, claire-student-2, fatima-child-1, fatima-child-2, school-community), NOT fictional 16-pod grid.

**Data sources:**
- Service health: HTTP health checks (CSS, Oxigraph, Qdrant)
- Troll results: `data/troll-run.jsonl` (troll.category.done events)
- Consent state: `data/consent-events.jsonl` (consent.grant/revoke/expired events)

**Consent seed:** A seed script writes initial consent.grant events for 6 pods (all except ayoub). Dashboard starts with 6 green, 1 "no consent" — meaningful initial state.
```

### 4.2 Story 6.3 — Refinement (not rewrite)

**ADD to existing AC (epics.md:866-892):**
```
**Given** the consent seed has been run (6 pods consented, ayoub pending)
**When** a facilitator interacts with Ayoub's agent via OpenClaw and requests consent grant
**Then** the acl-manage skill writes a consent.grant event to consent-events.jsonl
**And** the dashboard Pod Grid flips ayoub from red to green within 2 seconds
**And** the Cascade Predictor updates all downstream counts

**Given** a funder wants to explore role-specific data flows
**When** Isabelle requests a new scope (e.g., gender ratio vs. total_count)
**Then** the consent propagation for that scope is visible on the dashboard as new events
**(NOTE: requires wiring Isabelle's pod to OpenClaw — scope this during 6.3 implementation)**
```

### 4.3 Architecture Doc Update

**Section: `architecture.md:259-265` (Tabs in Mission Control)**

**OLD:**
```
**Tabs in Mission Control (Textual, Story 6.2):**
- [HEALTH] service status (CSS, Oxigraph, Qdrant, OpenClaw)
- [PIPELINE] pipeline stages progress
- [TROLL] per-category attack results (pass/partial/fail counts, blocking flag)
- [CONSENT] consent grant counts per pod (active/revoked/expired)
- [PODS] pod ACL state and last event timestamp
```

**NEW:**
```
**Widgets in Mission Control (Textual, Story 6.2):**

Single-screen layout (no tabs — operator sees everything at once):

┌─────────────────────────────────┬──────────────────────────────────┐
│ SERVICE HEALTH                  │ TROLL ALARM PANEL                │
│ CSS ✓  Oxigraph ✓  Qdrant ✓    │ Access Control  ✓ 23/23         │
│                                 │ Query Safety    ✓ 12/12         │
│                                 │ Embedding Priv  ✓  8/8          │
│                                 │ Agent Bounds    ⚠  5/7          │
│                                 │ Data Lifecycle  ✓  4/4          │
├─────────────────────────────────┼──────────────────────────────────┤
│ POD GRID (8 real pods)          │ CASCADE PREDICTOR                │
│ ayoub ✗  claire ✓               │ Selected: ayoub (no consent)     │
│ student-1 ✓  student-2 ✓       │ → school: 7/8 consented          │
│ fatima ✓  child-1 ✓            │ → aggregate: incomplete          │
│ child-2 ✓  community ✓         │                                  │
├─────────────────────────────────┴──────────────────────────────────┤
│ CONSENT GATE: Active 6 │ No consent 1 │ Revoked 0                 │
├───────────────────────────────────────────────────────────────────┤
│ EVENT LOG (last 10)                                               │
│ [seed] claire → consent.grant (school-enrollment)                 │
│ [seed] claire-student-1 → consent.grant (school-enrollment)       │
└───────────────────────────────────────────────────────────────────┘

Each widget is an isolated Textual Widget subclass:
- ServiceHealthWidget: polls HTTP endpoints every 5s
- TrollAlarmWidget: reads troll-run.jsonl, shows 5 category rows
- PodGridWidget: reads consent-events.jsonl, shows 7 real pods
- CascadePredictorWidget: computes downstream impact for selected pod
- ConsentGateWidget: computed counts from pod states
- EventLogWidget: tails consent-events.jsonl, last 20 events

Pod topology matches real CSS infrastructure (8 pods incl. fatima parent pod), not fictional 16-pod grid.
Role-specific scenario slides (Isabelle lens, Marc lens, Claire lens) are separate presentation artifacts, not dashboard views.
```

### 4.4 UX Spec — Deprecate

**Action:** Add deprecation header to `6-2-mission-control-ux-spec.md`:

```markdown
---
status: deprecated
superseded_by: sprint-change-proposal-2026-04-01.md
deprecation_reason: >
  Spec designed theoretical consent propagation visualization (4-STOP Gantt with Sparklines)
  that produced unusable output. Replaced by operations control room model with isolated widgets.
  Business logic (pod state calculation, cluster aggregation, event parsing) is preserved.
  Visualization layer rebuilt from scratch.
---
```

### 4.5 Deferred Work Update

**ADD to `deferred-work.md`:**

```markdown
## Deferred from: Story 6.2 course correction (2026-04-01)

- **Multi-role scenario flows:** Wiring Claire, Marc, Isabelle pods to OpenClaw agents for richer demo scenarios (gender ratio requests, food expense cross-pod aggregation, receipt notification to pod owner). Captured as Story 6.3 scope. Dashboard widget architecture supports this without changes — new events flow through same JSONL stream.
- **Scenario-specific slides/views:** Per-role data lifecycle explanations (Isabelle lens, Marc lens) as presentation artifacts rather than dashboard tabs. Post-6.2 deliverable.
- **"Blocking" label in troll display:** Replaced with color severity (red/yellow/green). No gatekeeping behavior — purely observational.
```

---

## 5. Implementation Handoff

### Scope Classification: **Moderate**

Story 6.2 AC rewrite + architecture doc update + new widget implementations. Backlog reorg (6.2/6.3 boundary) needs SM coordination.

### Handoff Plan

| Role | Responsibility |
|------|----------------|
| **SM (this session)** | Approve proposal, update sprint-status.yaml, update epics.md |
| **Dev (next session)** | Implement 6 widgets, consent seed script, rework mission_control.py |
| **QA (after dev)** | Validate: dashboard starts with seed data, troll panel shows real results, cascade predictor computes correctly |

### Implementation Sequence (Dev)

1. **Consent seed script** — write `scripts/seed-consent-events.py` (15 min)
2. **TrollAlarmWidget** — parse `troll-run.jsonl`, render 5-category table (highest value, real data exists)
3. **ServiceHealthWidget** — port from pipeline_dashboard.py
4. **PodGridWidget** — rework to 7 real pods, consume consent-events.jsonl
5. **ConsentGateWidget** — already exists, minor update for new pod topology
6. **CascadePredictorWidget** — new, computes downstream impact
7. **EventLogWidget** — new, tails consent-events.jsonl
8. **Compose layout** — single-screen, no tabs
9. **Drop deprecated widgets** — remove Gantt, Sparklines, ScenarioDetailPanels, CivicAggregatePanel

### Success Criteria

- [ ] Dashboard starts with seed data: 6 green pods, 1 "no consent" pod (ayoub)
- [ ] Troll alarm panel shows real results from `troll-run.jsonl`
- [ ] Pod grid uses real CSS pod identifiers (8 pods incl. fatima parent)
- [ ] Cascade predictor shows downstream impact when pod is selected
- [ ] Event log shows last 20 consent events
- [ ] Service health shows CSS/Oxigraph/Qdrant status
- [ ] Operator (Nicolas) can answer 5 key questions in <5 seconds each
