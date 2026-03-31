---
title: Story 6.2 Mission Control — Complete UX Specification
author: Freya (Strategic UX Designer)
date: 2026-03-31
status: ready-for-dev
purpose: Developer-ready specification for Textual mission control TUI — consent propagation network visualization
---

# Story 6.2: Mission Control UX Specification

## Overview

Mission Control is a **consent propagation network visualizer** — not a dashboard. It shows operators (funders, demo observers) how consent decisions flow through a multi-level system and where privacy boundaries protect citizen data.

**Core metaphor:** A transit operations center watching bus routes in real-time. Each route (scenario) shows where consent is granted/revoked/inherited, how it propagates through system layers, and where it hits the privacy boundary.

**Operator mental model:**
- Current consent state across all scenarios
- How decisions (grant/revoke) ripple through the system
- Where privacy boundaries are respected
- Which test results validate the architecture

---

## Information Architecture

### Four-Section Layout (All Sections Always Visible)

```
╔════════════════════════════════════════════════════════════════════════════╗
║ SCENARIOS: ☑ Claire (Teaching)  ☑ Isabelle (Outcome)  ☑ Ayoub (Transfer)  ║
║            ☐ Fatima (Parent)    ☐ Marc (Admin)       [+ Dynamic Filter]   ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─ SECTION 1: CONSENT PROPAGATION GANTT (Dynamic Stops) ────────────────────┐
│ [Scenario: Claire — Teaching]                                              │
│                                                                             │
│ STOP 1: Individual Pods (Ayoub, Sofia, Fatima, Karim, +13)                │
│ └─ Ayoub ✓      ─────────────┬─ revoked ──────────                         │
│ └─ Sofia ✓      ─────────────────────────────                              │
│ └─ Karim ✗      ─────────────────────────────                              │
│ └─ ...          (others)                                                    │
│                                                                             │
│ STOP 2: School Cluster Aggregate (8 NL pods)                               │
│ └─ ACL Status: 8/8 pass    ─┬─ recalc: 7/8 pass ──                        │
│    [keyframe] aggregate.computed  [keyframe] impact detected               │
│                                                                             │
│ STOP 3: Regional Hub (14 pods: 8 NL + 6 FR)                                │
│ └─ ACL Status: 14/14 pass  ─┬─ recalc: 13/14 pass ──                      │
│    [keyframe] aggregate.computed  [keyframe] impact detected               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ SECTION 2: POD SPACE (Compact 4-Column Grid, 16 Pods) ─────────────────────┐
│ Ayoub ✓     Sofia ✓     Fatima ✓     Karim ✗                               │
│ active      active      active      revoked                                │
│                                                                             │
│ Mehdi ⟳     Yannick ✓   Amara ✓      Lucas ✓                               │
│ transition  active      active       active                                │
│                                                                             │
│ [4 more rows of compact pods] — click pod → filter Gantt to vertical journey│
└─────────────────────────────────────────────────────────────────────────────┘

┌─ SECTION 3: CONSENT GATE (Live Counts) ────────────────────────────────────┐
│ Active Grants: 14  |  Revoked: 2  |  Transitioning: 1  |  Expired: 0      │
│ [updates ~2 sec, sourced from JSONL polling]                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ SECTION 4: CIVIC AGGREGATE + WARNINGS ────────────────────────────────────┐
│ [Only if scenario reaches STOP 4 — dynamically hidden otherwise]           │
│                                                                             │
│ Isabelle's Evidence Base:                                                   │
│   NL Regional: 8/8 pods (stable after Ayoub revoke? CHECKING...)           │
│   FR Regional: 6/6 pods (stable)                                           │
│   Privacy Boundary: ✓ Respected (2 revoked = 0 civic impact)               │
│   Publication Status: "STEM +12% engagement" ✓ verified                    │
│                                                                             │
│ [Alert Section — if any]                                                   │
│ ⚠ Missing pod context in event line 47 (aggregate incomplete)              │
│ ⚠ Unknown pod: 'pod-test-xyz' (ignored — test data?)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Consent Propagation Model: The Four Stops

### **STOP 1: Individual Pods**
- **What lives here:** Individual learner (Ayoub, Sofia, etc.)
- **Consent events:** `consent.grant`, `consent.revoke`, `consent.expired`, `acl.grant`, `acl.revoke`
- **Keyframes fire when:**
  - `consent.grant` → Consent recorded for this pod
  - `consent.revoke` → Consent withdrawn for this pod
  - `consent.expired` → Token expired, query access denied
- **Pod state values:** ✓ (active), ✗ (revoked), ⟳ (transitioning), ⚠ (anomaly)
- **TUI display:** Compact grid (4 cols × 4 rows = 16 pods)

### **STOP 2: School/Cluster Aggregate**
- **What lives here:** Single school or learning cluster (e.g., "School NL — 8 students")
- **Inherits from:** STOP 1 — all pod consents in the cluster
- **Consent events:** `aggregate.computed`, `acl.governance.transition` (if school-wide policy changes)
- **Keyframes fire when:**
  - `aggregate.computed` → Cluster recalculation triggered (e.g., after a revoke at STOP 1)
  - Impact detected → Pod count changed from previous state (e.g., 8→7)
- **TUI calculation:** "Count active pods in cluster where ACL check passes"
- **Visibility rule:** Shows in Gantt when operator selects scenario involving this cluster

### **STOP 3: Regional Hub**
- **What lives here:** Multi-cluster aggregation (e.g., "Brussels Region — 14 pods: 8 NL + 6 FR schools")
- **Inherits from:** STOP 2 — all cluster aggregates in the region
- **Consent events:** `aggregate.computed` (regional roll-up)
- **Keyframes fire when:**
  - `aggregate.computed` at regional level
  - Impact detected → Total pod count changed (e.g., 14→13)
- **TUI calculation:** "Sum all clusters in region, verify each cluster's ACL status"
- **Visibility rule:** Shows only in Isabelle scenario (funder assessment)

### **STOP 4: Federal Civic Layer**
- **What lives here:** De-identified aggregate for public policy (Parliament, civic bodies)
- **Inherits from:** STOP 3 — regional data becomes input
- **Consent events:** `civic.aggregate.locked`, possibly `deletion.complete` (if a pod is tombstoned)
- **Keyframes fire when:**
  - `civic.aggregate.locked` → Evidence base published, privacy boundary sealed
  - Threshold breach detected → Pod count drops below minimum for publication
- **Privacy boundary:** Individual pod data is **invisible** at this level
  - Operator sees: "14 pods contribute to aggregate" + "Result: +12% engagement"
  - Operator does NOT see: Which pods, which students, which schools (only anonymized counts)
- **TUI calculation:** "Verify privacy boundary holds: revoked pods do not appear in civic output"
- **Visibility rule:** Shows only in Isabelle scenario AND only if consent data reaches STOP 3

---

## Scenario-Stop Mapping (Dynamic Visibility)

Each scenario activates only the stops relevant to that role's concerns:

| Scenario | STOP 1 | STOP 2 | STOP 3 | STOP 4 | Rationale |
|----------|--------|--------|--------|--------|-----------|
| **Claire (Teaching)** | ✓ | ✓ | — | — | Teacher sees her students + school aggregate; doesn't care about regional/civic |
| **Isabelle (Outcome Assessment)** | ✓ | ✓ | ✓ | ✓ | Funder sees full journey: pods → school → region → civic evidence |
| **Ayoub (Transfer)** | ✓ | ✓ | — | — | Student sees his data + how school uses it; not regional policy |
| **Fatima (Parent)** | ✓ | ✓ | — | — | Parent sees her children + school they attend; not broader regional |
| **Marc (Admin)** | ✓ | ✓ | ✓ | — | Admin manages schools across region; sees regional rollup but not civic publication |

**Implementation rule:** When scenario checkbox is selected, Gantt renders only STOP levels where that scenario's role has authority/visibility.

---

## Gantt Rendering Algorithm

### **Structure (Vertical Propagation)**

For each selected scenario:

1. **Header:** Scenario name + operator perspective
   - "Claire — Teaching: View from classroom teacher"
   - "Isabelle — Outcome: View from funder/policy advisor"

2. **STOP 1 Row(s):** Individual pods
   - One row per pod (name, state indicator, consent timeline bar)
   - Timeline bar shows: grant (green block) → revoke (red block) → expired (gray block)
   - Keyframes marked with ▼ at the moment consent event fires

3. **STOP 2 Row:** Cluster aggregate
   - Single row for "School NL" or "School FR"
   - Timeline bar shows: aggregate count (e.g., "8/8") → impact (e.g., "7/8") with red highlight
   - Keyframes marked with ▼ at the moment aggregate recalculates

4. **STOP 3 Row (if applicable):** Regional aggregate
   - Single row for "Regional Hub"
   - Timeline bar shows: aggregate count (e.g., "14/14") → impact (e.g., "13/14")
   - Keyframes marked with ▼

5. **STOP 4 Row (if applicable):** Civic layer
   - Single row for "Federal Civic Layer"
   - Timeline bar shows: evidence base locked (green) → threshold check (yellow if at risk)
   - Keyframes marked with ▼ when civic.aggregate.locked

6. **Spacing:** Vertical space between STOP rows (1-2 blank lines) to show hierarchy

### **Time Axis**

- Horizontal: Event timestamp (all events aligned by clock time)
- Keyframes marked at their exact event timestamp
- Zoom/pan: Optional (may be out of scope for 6.2, but space for future)

### **Keyframe Visual Indicators**

- **▼** = Keyframe event (consent granted/revoked, aggregate computed)
- **Color coding:**
  - 🟢 Green block = `consent.grant`, `aggregate.computed` (stable state)
  - 🔴 Red block = `consent.revoke`, `consent.expired` (revoked state)
  - 🟡 Yellow marker = Impact detected (count changed), threshold warning
  - 🟣 Purple marker = `acl.governance.transition` (policy change)

### **Overlapping Scenarios**

When multiple scenarios are selected, the Gantt can show them stacked or tabbed:

**Option 1 (Tabbed):** Scenario tab switcher above Gantt
- "Show: [Claire]  [Isabelle]  [Ayoub]"
- One scenario visible at a time
- **Simpler, recommended for 6.2**

**Option 2 (Stacked, Future):** All scenarios visible in parallel
- Claire's STOP 1-2 above, Isabelle's STOP 1-4 below
- Shared STOP 1 pods highlighted where both scenarios involve same student
- **Requires more space, consider for later iteration**

**For 6.2: Use Option 1 (Tabbed).**

---

## Keyframe Detection Algorithm

Keyframes are events that represent **consent boundary crossings** — moments where consent decision moves up or down the network.

### **STOP 1 Keyframes (Individual Pod)**

```python
def should_fire_keyframe_stop1(event: dict) -> bool:
    """Fire keyframe at STOP 1 when consent is granted/revoked/expired."""
    return event["event_type"] in [
        "consent.grant",
        "consent.revoke",
        "consent.expired",
        "acl.grant",
        "acl.revoke"
    ]
```

**Example events:**
```jsonl
{"timestamp": "2026-03-31T14:15:00Z", "event_type": "consent.grant", "pod": "ayoub-pod", "grantee_webid": "isabelle-webid", "scope": "STEM_PROGRESS"}
{"timestamp": "2026-03-31T14:32:00Z", "event_type": "consent.revoke", "pod": "karim-pod"}
```

### **STOP 2 Keyframes (Cluster Aggregate)**

```python
def should_fire_keyframe_stop2(event: dict, previous_aggregate: dict) -> bool:
    """Fire keyframe when cluster aggregate changes (pod count affected by consent change)."""
    current_aggregate = calculate_cluster_aggregate(event.pod)

    # Fire only if count changed from previous
    return current_aggregate["active_pods"] != previous_aggregate.get("active_pods", 0)
```

**Logic:** After a STOP 1 consent event (grant/revoke), TUI recalculates cluster pod count:
- If Ayoub revokes → check "School NL" cluster
- Count active pods in cluster where ACL check passes
- If count changed (8→7), fire keyframe at STOP 2

**Example:**
```
14:15 → Ayoub grants consent (STOP 1 keyframe)
        ↓
        TUI recalculates "School NL" cluster
        8 pods still pass ACL check
        ↓ No change, no STOP 2 keyframe

14:32 → Karim revokes consent (STOP 1 keyframe)
        ↓
        TUI recalculates "School NL" cluster
        Now 7/8 pods pass ACL check (Karim excluded)
        ↓ Count changed! Fire STOP 2 keyframe
```

### **STOP 3 Keyframes (Regional Aggregate)**

```python
def should_fire_keyframe_stop3(event: dict, previous_regional: dict) -> bool:
    """Fire keyframe when regional aggregate changes."""
    # After STOP 2 triggers, recalculate regional roll-up
    current_regional = calculate_regional_aggregate()

    return current_regional["total_pods"] != previous_regional.get("total_pods", 0)
```

**Logic:** After STOP 2 cluster recalculation, recalculate regional:
- Sum all clusters in region
- If total count changed (14→13), fire keyframe at STOP 3

### **STOP 4 Keyframes (Civic Layer)**

```python
def should_fire_keyframe_stop4(event: dict) -> bool:
    """Fire keyframe when civic aggregate is locked or threshold breached."""
    return event["event_type"] in [
        "civic.aggregate.locked",
        "civic.threshold.breach",
        "deletion.complete"
    ]
```

**Logic:** Civic layer fires keyframes only on explicit events (from agents/skills):
- `civic.aggregate.locked` → Evidence base published
- `civic.threshold.breach` → Pod count dropped below minimum (publish at risk)

### **Keyframe Summary**

| STOP | Fires On | Condition |
|------|----------|-----------|
| 1 | `consent.*`, `acl.*` events | Always (these events live at STOP 1) |
| 2 | Cluster count changes | After STOP 1 event, if cluster aggregate affected |
| 3 | Regional count changes | After STOP 2 event, if regional aggregate affected |
| 4 | Explicit civic events | Only on `civic.aggregate.locked`, threshold breach, deletion |

---

## Aggregate Calculation Logic (TUI Derives All)

TUI reads JSONL events and calculates all aggregates in real-time. No pre-computed values in events.

### **STOP 1: Pod State Calculation**

```python
class PodState:
    """Track a single pod's consent status."""
    pod_id: str
    current_state: Literal["active", "revoked", "transitioning", "anomaly"]
    grants: list[dict]  # All consent.grant events for this pod
    revokes: list[dict]  # All consent.revoke events
    last_event: dict    # Most recent event

def calculate_pod_state(pod_id: str, consent_events: list[dict]) -> PodState:
    """Determine pod's current state from consent history."""
    pod_events = [e for e in consent_events if e.get("pod") == pod_id]

    if not pod_events:
        return PodState(pod_id=pod_id, current_state="anomaly")  # Unknown pod

    # Sort by timestamp
    pod_events.sort(key=lambda e: e.get("timestamp", ""))

    last = pod_events[-1]

    if last["event_type"] == "consent.revoke":
        return PodState(pod_id=pod_id, current_state="revoked", last_event=last)
    elif last["event_type"] == "consent.expired":
        return PodState(pod_id=pod_id, current_state="revoked", last_event=last)
    elif last["event_type"] == "acl.governance.transition":
        return PodState(pod_id=pod_id, current_state="transitioning", last_event=last)
    elif last["event_type"] == "consent.grant":
        return PodState(pod_id=pod_id, current_state="active", last_event=last)
    else:
        return PodState(pod_id=pod_id, current_state="anomaly", last_event=last)
```

**Rules:**
- Pod is **active** if last event is `consent.grant` or `acl.grant`
- Pod is **revoked** if last event is `consent.revoke` or `consent.expired`
- Pod is **transitioning** if last event is `acl.governance.transition` (awaiting ACL override)
- Pod is **anomaly** if unknown or no events

### **STOP 2: Cluster Aggregate Calculation**

```python
class ClusterAggregate:
    """Track consent state for a school cluster."""
    cluster_id: str  # e.g., "school-nl-1"
    cluster_name: str  # e.g., "School NL"
    pods: list[str]  # Pod IDs in this cluster
    active_pods: int
    revoked_pods: int
    total_pods: int
    last_updated: str

def calculate_cluster_aggregate(cluster_id: str, pod_states: dict[str, PodState]) -> ClusterAggregate:
    """Sum pod states to get cluster-level counts."""
    pods_in_cluster = CLUSTER_MAPPING[cluster_id]  # Pre-defined pod→cluster mapping

    active = sum(1 for p in pods_in_cluster if pod_states[p].current_state == "active")
    revoked = sum(1 for p in pods_in_cluster if pod_states[p].current_state == "revoked")
    total = len(pods_in_cluster)

    return ClusterAggregate(
        cluster_id=cluster_id,
        active_pods=active,
        revoked_pods=revoked,
        total_pods=total
    )
```

**Rules:**
- Count pods where state == "active"
- Count pods where state == "revoked"
- Transitioning pods = intermediate state (count separately, exclude from pass/fail)

### **STOP 3: Regional Aggregate Calculation**

```python
class RegionalAggregate:
    """Track consent state across multiple clusters."""
    region_id: str  # e.g., "nl-region"
    region_name: str  # e.g., "Brussels NL"
    clusters: list[str]
    total_pods: int
    active_pods: int
    revoked_pods: int
    publication_ready: bool  # Can civic layer publish?

def calculate_regional_aggregate(region_id: str, cluster_aggregates: dict[str, ClusterAggregate]) -> RegionalAggregate:
    """Sum cluster aggregates to get regional counts."""
    clusters_in_region = REGION_MAPPING[region_id]

    total = sum(cluster_aggregates[c].total_pods for c in clusters_in_region)
    active = sum(cluster_aggregates[c].active_pods for c in clusters_in_region)
    revoked = sum(cluster_aggregates[c].revoked_pods for c in clusters_in_region)

    # Publication check: does regional aggregate meet minimum pod count?
    publication_ready = active >= MIN_PODS_FOR_PUBLICATION  # e.g., 10

    return RegionalAggregate(
        region_id=region_id,
        total_pods=total,
        active_pods=active,
        revoked_pods=revoked,
        publication_ready=publication_ready
    )
```

### **STOP 4: Civic Aggregate Calculation**

```python
class CivicAggregate:
    """Evidence base visible to federal civic layer."""
    evidence_base_name: str  # e.g., "STEM programmes"
    regional_source: str  # e.g., "brussels-nl"
    pods_in_base: int
    outcome: str  # e.g., "+12% engagement"
    privacy_boundary_respected: bool
    publication_status: str  # "locked", "at_risk", "published"

def calculate_civic_aggregate(regional_agg: RegionalAggregate, policy_data: dict) -> CivicAggregate:
    """Derive civic-layer aggregate from regional + policy data."""

    # Privacy boundary check: revoked pods must not appear
    privacy_ok = all(
        pod.state != "revoked"
        for pod in get_pods_in_aggregate(regional_agg)
    )

    # Threshold check: do we have enough pods to publish?
    publication_ok = regional_agg.publication_ready

    # Outcome lookup: from policy_data (pre-defined, e.g., "STEM +12%")
    outcome = policy_data.get(regional_agg.region_id, "unknown impact")

    return CivicAggregate(
        evidence_base_name=policy_data.get("name", ""),
        regional_source=regional_agg.region_id,
        pods_in_base=regional_agg.active_pods,
        outcome=outcome,
        privacy_boundary_respected=privacy_ok,
        publication_status="locked" if (privacy_ok and publication_ok) else "at_risk"
    )
```

**Privacy boundary rule:** The civic layer receives only aggregate counts and outcomes, never individual pod identities. If any pod is revoked, it must be **excluded** from the aggregate before publication.

### **Aggregate Recalculation Trigger**

When a new event arrives (from JSONL tail):

```python
async def _on_consent_event(event: dict):
    """When a new consent event arrives, recalculate affected aggregates."""

    # 1. Update STOP 1 (pod state)
    pod_id = event.get("pod")
    pod_state = calculate_pod_state(pod_id, self.all_consent_events)

    # 2. Find which clusters include this pod, update STOP 2
    affected_clusters = CLUSTER_MAPPING.get_clusters_with_pod(pod_id)
    for cluster_id in affected_clusters:
        cluster_agg = calculate_cluster_aggregate(cluster_id, self.pod_states)
        # Check if count changed
        if cluster_agg.active_pods != self.previous_cluster_state[cluster_id].active_pods:
            fire_keyframe(STOP=2, event=event)

    # 3. Find which regions include these clusters, update STOP 3
    affected_regions = REGION_MAPPING.get_regions_with_clusters(affected_clusters)
    for region_id in affected_regions:
        regional_agg = calculate_regional_aggregate(region_id, self.cluster_aggregates)
        if regional_agg.active_pods != self.previous_regional_state[region_id].active_pods:
            fire_keyframe(STOP=3, event=event)

    # 4. Update STOP 4 if regional aggregate affects civic publication
    civic_agg = calculate_civic_aggregate(regional_agg, self.policy_data)
    if civic_agg.publication_status != self.previous_civic_state.get(region_id, {}).get("status"):
        fire_keyframe(STOP=4, event=event)

    # Update reactive attributes (triggers watchers → UI updates)
    self.pod_states = {**self.pod_states, pod_id: pod_state}
    self.cluster_aggregates = {**self.cluster_aggregates, **updated_clusters}
    self.regional_aggregates = {**self.regional_aggregates, **updated_regions}
```

---

## Reactive State Model

TUI maintains reactive attributes that trigger UI updates when changed:

```python
from textual.reactive import reactive

class MissionControlApp(App):
    # Raw events (sourced from JSONL)
    consent_events = reactive([])  # List[dict] from consent-events.jsonl
    pipeline_events = reactive([])  # List[dict] from pipeline-run.jsonl

    # Derived state (calculated by TUI)
    pod_states = reactive({})  # Dict[pod_id, PodState]
    cluster_aggregates = reactive({})  # Dict[cluster_id, ClusterAggregate]
    regional_aggregates = reactive({})  # Dict[region_id, RegionalAggregate]
    civic_aggregates = reactive({})  # Dict[region_id, CivicAggregate]

    # UI state
    selected_scenarios = reactive([])  # List[scenario_id] — which routes are checked
    filtered_pod = reactive(None)  # If operator clicked a pod, show its vertical journey

    # Watch methods (called when reactive attributes change)
    def watch_consent_events(self):
        """When new consent events arrive, recalculate all aggregates."""
        self._recalculate_all_aggregates()
        self._update_gantt()
        self._update_consent_gate_counts()
        self._update_civic_layer()

    def watch_selected_scenarios(self):
        """When operator checks/unchecks scenarios, update Gantt."""
        self._update_gantt()

    def watch_filtered_pod(self):
        """When operator clicks a pod, filter Gantt to show its vertical journey."""
        self._update_gantt()
        self._update_pod_grid_highlight()
```

---

## Pod Grid Interactivity

### **Pod Grid Click Behavior (Option B: Filter Gantt)**

When operator clicks a pod in the compact grid:

```python
def on_click_pod(pod_id: str):
    """Operator clicked a pod — show its vertical consent journey."""
    self.filtered_pod = pod_id
    # This triggers watch_filtered_pod()
    # Which filters Gantt to show only scenarios involving this pod
    # And highlights pod in grid
```

**Gantt behavior when filtered to a pod:**

1. **Show only scenarios involving this pod**
   - Example: Click "Ayoub" → Show only "Claire (Teaching)" and "Isabelle (Outcome)" scenarios
   - Hide "Fatima (Parent)" if Fatima's children are different pods

2. **Highlight STOP 1 row for that pod**
   - "Ayoub ✓ active" row highlighted in yellow/bold
   - Other pods in grid grayed out

3. **Show all affected aggregates upstream**
   - STOP 2: "School NL (8 students)" where Ayoub's data flows
   - STOP 3: "Regional (14 pods)" if scenario reaches that level
   - STOP 4: "Federal Civic Layer" with privacy boundary check

4. **Button to clear filter**
   - "← Show All Routes" clears `filtered_pod`, returns to multi-scenario view

**Example:**
```
Click "Karim" pod (✗ revoked)
  ↓
Gantt filters to scenarios involving Karim
  ↓
Show: Claire (Teaching), Isabelle (Outcome)
  ↓
Highlight Karim's row at STOP 1
  ↓
Show School cluster recalculation: "8/8 → 7/8 after revoke"
  ↓
Show Regional impact: "14/14 → 13/14 NL pods"
  ↓
Show Civic check: "Privacy boundary? YES — Karim's pod excluded from aggregate"
```

---

## Detail Tabs

When operator clicks a scenario row in the Gantt, it opens a detail tab for that scenario.

### **Tab: [SCENARIO: Claire — Teaching]**

**Purpose:** Deep view of consent decisions from Claire's (teacher) perspective.

**Layout:**

```
┌─ Header ──────────────────────────────────────────────────────────────────┐
│ Claire — Secondary School Teacher | Brussels NL School                     │
│ Her Question: "Which students struggle with fractions across all contexts?"│
└───────────────────────────────────────────────────────────────────────────┘

┌─ Timeline Section ─────────────────────────────────────────────────────────┐
│ Event Timeline (Consent Events in Chronological Order)                     │
│                                                                             │
│ 14:32 ▼ [REVOKE] Karim's consent withdrawn                                │
│       ↳ Impact: Claire's fractions query now excludes Karim's tutoring data│
│       ↳ Action: Ask Karim's parent for re-consent via OpenClaw            │
│                                                                             │
│ 14:15 ▼ [GRANT] Ayoub renewed consent for STEM progress visibility        │
│       ↳ Impact: Ayoub's after-school tutoring now visible to Claire       │
│       ↳ Scope: "STEM_PROGRESS" for 1 subject, 4 weeks                     │
│                                                                             │
│ 13:52 ▼ [ACL.GRANT] School NL cluster approved for Claire's query         │
│       ↳ Impact: All 8 NL pods now accessible (with individual consent)    │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Student Grid Section ─────────────────────────────────────────────────────┐
│ Student | Consent | Query Grant | Fractions Data | Last Consent Event     │
│─────────┼─────────┼─────────────┼────────────────┼────────────────────────│
│ Ayoub   | ✓       | ✓           | ✓ visible      | 14:15 — renewed        │
│ Sofia   | ✓       | ✓           | ✓ visible      | 13:30 — initial        │
│ Fatima  | ✓       | ✓           | ✓ visible      | 13:30 — initial        │
│ Karim   | ✗       | ✗           | ✗ excluded     | 14:32 — revoked        │
│ +4 more | ...     | ...         | ...            | ...                    │
│                                                                             │
│ [Click student → drill to pod detail]                                      │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Action Section ──────────────────────────────────────────────────────────┐
│ [Ask Karim's parent for consent] (opens OpenClaw webchat modal)           │
│ [Refine query filters] (e.g., show only data from last 4 weeks)          │
└───────────────────────────────────────────────────────────────────────────┘
```

**Reactive updates:**
- When a new `consent.grant` or `consent.revoke` event arrives, timeline updates immediately
- Student grid counts update in real-time

### **Tab: [SCENARIO: Isabelle — Outcome Assessment]**

**Purpose:** Full consent propagation journey — individual → school → region → civic layer.

**Layout:**

```
┌─ Header ──────────────────────────────────────────────────────────────────┐
│ Isabelle — Regional Policy Advisor | Brussels Outcome Assessment          │
│ Her Question: "What is the measurable impact of after-school STEM?"        │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Propagation Journey ──────────────────────────────────────────────────────┐
│ STOP 1: Individual Pods (14 active, 2 revoked)                             │
│ └─ Consent grants collected from Ayoub, Sofia, Fatima, ... (show list)    │
│    ↳ Last event: 14:32 — Karim revoke (now excluded from aggregate)       │
│                                                                             │
│ STOP 2: School Clusters (8 NL + 6 FR = 14 total)                           │
│ └─ School NL:  8/8 pods pass ACL ✓ [was 9/9 before Karim revoke]         │
│ └─ School FR:  6/6 pods pass ACL ✓ (stable)                               │
│    ↳ Keyframe: 14:32 — cluster recalc triggered (School NL: 9→8)          │
│                                                                             │
│ STOP 3: Regional Hub (13/14 active after revoke)                          │
│ └─ Brussels NL: 8/8 pass ✓                                                │
│ └─ Brussels FR: 6/6 pass ✓                                                │
│ └─ Total: 14 pods (after Karim revoke, 13 counted for aggregate) ⚠        │
│    ↳ Keyframe: 14:32 — regional impact check (threshold: 10 pods min)    │
│    ↳ Status: Publication APPROVED (13 > 10) ✓                             │
│                                                                             │
│ STOP 4: Federal Civic Layer (De-identified Evidence Base)                 │
│ └─ Evidence Title: "STEM After-School Programmes"                         │
│ └─ Data Input: 13 pods from Brussels region (revoked pods = 0 visibility) │
│ └─ Finding: "+12% engagement in STEM subjects"                            │
│ └─ Privacy Boundary: ✓ RESPECTED (2 revoked pods invisible at civic layer)│
│ └─ Publication Status: LOCKED & PUBLISHED ✓                               │
│    ↳ Parliament, civic bodies can now cite this evidence                  │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Publication Safety Check ─────────────────────────────────────────────────┐
│ Consent Flow Verified: Individual decisions → aggregate → civic layer      │
│                                                                             │
│ ✓ Revoked pods excluded from aggregate (Karim = not counted)              │
│ ✓ Regional threshold met (13 ≥ 10 minimum)                                │
│ ✓ Privacy boundary sealed (no individual data at civic level)             │
│ ✓ Evidence base locked (no further updates without new consent round)     │
│                                                                             │
│ Ready for policy use: Parliament can rely on "+12% engagement" claim      │
└───────────────────────────────────────────────────────────────────────────┘
```

### **Tab: [POD: <pod-name>]** (Drill-down from Grid Click)

**Purpose:** Individual pod's consent history and ACL state.

**Layout:**

```
┌─ Header ──────────────────────────────────────────────────────────────────┐
│ Karim — Learner Pod | Mehdi School (French NL)                            │
│ Current State: ✗ REVOKED                                                   │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Consent History (Reverse Chronological) ──────────────────────────────────┐
│ 14:32 ▼ [CONSENT.REVOKE]                                                   │
│         Event: Karim's parent (via WebChat) revoked all consent            │
│         Reason: "Do not share my child's data further"                     │
│         Impact: NL school aggregate now 8/8, regional impact detected      │
│         Propagation: [STOP 1] → [STOP 2] recalc → [STOP 3] recount        │
│                                                                             │
│ 13:52 ▼ [CONSENT.GRANT]                                                    │
│         Event: Karim's parent granted initial consent                      │
│         Scope: "LEARNING_PROGRESS" for Claire's classroom queries          │
│         Duration: 30 days (expires 2026-04-30)                             │
│                                                                             │
│ 13:30 ▼ [ACL.GRANT]                                                        │
│         Event: Mehdi school ACL approved for Claire's role                │
│         Role: Teacher                                                       │
│         Action: Read learner data in school pod                            │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Current ACL State ────────────────────────────────────────────────────────┐
│ Identity | Role | Action | Grant Status | Expiry                           │
│──────────┼──────┼────────┼──────────────┼─────────────────────────────────│
│ Claire   | Teacher | Read | ✗ REVOKED | n/a (consent withdrawn)          │
│ Isabelle | Funder | Read | ✗ REVOKED | n/a (consent withdrawn)           │
│ Mehdi School | Admin | Maintain | ✓ ACTIVE | 2026-06-30                  │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Recovery Actions ────────────────────────────────────────────────────────┐
│ [Request re-consent from Karim's parent] (via OpenClaw)                   │
│ [View detailed consent request template]                                   │
│ [Schedule follow-up conversation]                                          │
└───────────────────────────────────────────────────────────────────────────┘
```

### **Tab: [ATTACKS] — Troll Control & Results**

**Purpose:** Trigger and monitor adversarial tests.

**Layout:**

```
┌─ Header ──────────────────────────────────────────────────────────────────┐
│ Adversarial Testing (Troll Probes) | Monitor attack validation            │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Attack Scenario Selector ────────────────────────────────────────────────┐
│ [Dropdown] Select attack scenario:                                        │
│   ☑ deletion.cascade (Karim pod — test revocation ripple)                │
│   ☐ privacy.boundary (Attempt unauthorized civic layer access)           │
│   ☐ consent.forge (Try to grant consent without authorization)           │
│   ☐ aggregate.poison (Corrupt regional count data)                       │
│                                                                             │
│ Active Scenario: deletion.cascade on karim-pod                            │
│ Status: Ready | Last Run: 2026-03-31 14:15 UTC | Elapsed: 17 minutes     │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Test Results Summary ─────────────────────────────────────────────────────┐
│ Category Summary:                                                           │
│ ┌─────────────────────────────────────────────────────────────────────────┐
│ │ Category        │ Passed │ Partial │ Failed │ Blocking                  │
│ ├─────────────────┼────────┼─────────┼────────┼──────────────────────────┤
│ │ Consent Gate    │   3    │   1     │   0    │         0                 │
│ │ Privacy Boundary│   2    │   0     │   0    │         0                 │
│ │ ACL Revocation  │   4    │   1     │   0    │         0                 │
│ │ Aggregate Update│   2    │   1     │   0    │         0                 │
│ │ TOTAL           │  11    │   3     │   0    │         0 ✓ PASS         │
│ └─────────────────────────────────────────────────────────────────────────┘
│                                                                             │
│ Color Legend: 🟢 Pass  🟡 Partial  🔴 Fail  🔵 Blocking                   │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Recent Probes ────────────────────────────────────────────────────────────┐
│ Probe ID | Category | Layer | Result | Elapsed (ms) | Timestamp            │
│──────────┼──────────┼───────┼────────┼──────────────┼─────────────────────│
│ probe-47 | Consent Gate | ACL | ✓ pass | 142 ms | 14:32:15 UTC         │
│ probe-46 | Consent Gate | STOP2 | 🟡 partial | 89 ms | 14:31:20 UTC      │
│ probe-45 | Privacy Boundary | STOP4 | ✓ pass | 234 ms | 14:30:05 UTC      │
│ probe-44 | ACL Revocation | ACL | ✓ pass | 156 ms | 14:29:40 UTC         │
│          |          |       |        |              |                     │
│ [+7 more probes, scroll for details]                                      │
│                                                                             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ Control Panel ────────────────────────────────────────────────────────────┐
│ [Launch Attack] (starts troll adversary for selected scenario)            │
│ [Pause / Resume] (if attack in progress)                                  │
│ [View Full Report] (opens detailed troll report document)                 │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Visual Language & Color Coding

### **Pod State Colors (Pod Grid)**

| State | Symbol | Color | Meaning |
|-------|--------|-------|---------|
| Active | ✓ | 🟢 Green | Consent granted, pod accessible |
| Revoked | ✗ | 🔴 Red | Consent withdrawn, pod hidden |
| Transitioning | ⟳ | 🟡 Yellow | Governance change in progress (awaiting ACL override) |
| Anomaly | ⚠ | 🟣 Purple | Unknown/error state, requires investigation |

### **Event Timeline Colors (Gantt & Detail Tabs)**

| Event | Symbol | Color | Meaning |
|-------|--------|-------|---------|
| Consent granted | 🟢 Block | Green | Data access enabled |
| Consent revoked | 🔴 Block | Red | Data access disabled |
| Consent expired | ⚠ Block | Gray | Token expired, access denied |
| Aggregate computed | ▼ Keyframe | Green | Cluster/regional count updated (stable) |
| Impact detected | ▼ Keyframe | 🟡 Yellow | Count changed from previous (e.g., 8→7) |
| Governance transition | 🟣 Marker | Purple | ACL override pending |
| Civic aggregate locked | ▼ Keyframe | 🟣 Purple | Evidence base published, privacy boundary sealed |

### **Consent Gate Counts (Live Display)**

- **Active Grants:** 🟢 Green text
- **Revoked:** 🔴 Red text
- **Transitioning:** 🟡 Yellow text
- **Expired:** Gray text

### **Result Colors (Attacks Tab)**

| Result | Color |
|--------|-------|
| Pass | 🟢 Green |
| Partial | 🟡 Yellow |
| Fail | 🔴 Red |
| Blocking | 🔵 Blue (requires action) |

---

## Graceful Failure States

### **Missing JSONL File**

```
⚠ Alert (yellow warning)
"No events yet for this scenario — waiting for data."

Visual effect:
- Gantt: Empty (no rows)
- Pod Grid: Grayed out, all pods marked ⚠ (unknown state)
- Consent Gate Counts: All zero
- Detail tabs: "No data available"
- Action: Operator knows to start pipeline or ensure agent is emitting events
```

### **Malformed JSON in JSONL**

```
⚠ Alert (yellow warning, dismissible)
"Event parse error at line 47 — skipped (expected valid JSON)"

Visual effect:
- Events before line 47 still display correctly
- Timeline continues, but with gap
- Aggregate calculations use valid events only
- Action: Operator can investigate source, re-run if needed
```

### **Missing Pod Context in Event**

```
⚠ Alert (yellow warning, in Civic Aggregate section)
"Aggregate incomplete — 1 event(s) missing pod context (line 47)"

Visual effect:
- Cluster count shows: "7/8 active (1 uncertain)"
- Civic layer shows: "13/14 pods ⚠ (1 event unverified)"
- Privacy boundary still checked ✓ (partial data treated conservatively)
- Action: Operator knows aggregate is partial but valid
```

### **Unknown Pod in Event**

```
⚠ Alert (yellow warning)
"Unknown pod: 'pod-test-xyz' detected (ignored — test data?)"

Visual effect:
- Pod grid unchanged (doesn't appear)
- Event recorded but marked as anomalous
- Pod counts unchanged
- Action: Operator can choose to dismiss or investigate
```

### **Consent Event References Non-Existent Pod Scope**

```
⚠ Alert (yellow warning)
"Event references unknown scope 'INVALID_SCOPE' — treated as generic consent"

Visual effect:
- Event still processed (pod marked as granted/revoked)
- Scope field left blank in detail tabs
- Aggregate counts still update
- Action: Operator sees event is processed despite data quality issue
```

### **Aggregate Calculation Fails (Edge Case)**

```
⚠ Alert (red error)
"Failed to calculate cluster aggregate for 'school-nl-1' — check pod list"

Visual effect:
- Cluster row in Gantt marked ⚠ with red background
- Count displays: "? / 8 active (calculation error)"
- Privacy boundary check skipped (conservative — assume failure means incomplete data)
- Action: Operator pauses and reports; system continues with other clusters
```

---

## JSONL Event Catalog (TUI Ingests These)

### **Consent Events** (from `data/consent-events.jsonl`)

```jsonl
{"timestamp": "2026-03-31T14:32:00Z", "event_type": "consent.revoke", "pod": "karim-pod", "pod_owner": "karim-parent", "reason": "Do not share"}
{"timestamp": "2026-03-31T14:15:00Z", "event_type": "consent.grant", "pod": "ayoub-pod", "grantee_webid": "isabelle-webid", "scope": "STEM_PROGRESS", "duration_days": 30}
{"timestamp": "2026-03-31T14:05:00Z", "event_type": "consent.expired", "pod": "fatima-pod", "token_id": "token-456", "grant_id": "grant-123"}
{"timestamp": "2026-03-31T13:52:00Z", "event_type": "acl.grant", "pod": "karim-pod", "identity": "claire-webid", "role": "Teacher", "action": "Read"}
{"timestamp": "2026-03-31T13:30:00Z", "event_type": "acl.revoke", "pod": "ayoub-pod", "identity": "old-teacher-webid"}
{"timestamp": "2026-03-31T13:00:00Z", "event_type": "acl.governance.transition", "pod": "mehdi-pod", "from_role": "ParentGuardian", "to_role": "StudentSelf", "reason": "Age 18"}
```

### **Aggregate Events** (emitted by pipeline/agents)

```jsonl
{"timestamp": "2026-03-31T14:32:15Z", "event_type": "aggregate.computed", "cluster_id": "school-nl-1", "cluster_name": "School NL", "active_pods": 7, "revoked_pods": 1, "total_pods": 8, "change_from_previous": 8}
{"timestamp": "2026-03-31T14:33:00Z", "event_type": "aggregate.computed", "region_id": "brussels-nl", "region_name": "Brussels NL", "active_pods": 13, "revoked_pods": 1, "total_pods": 14, "publication_ready": true}
{"timestamp": "2026-03-31T14:35:00Z", "event_type": "civic.aggregate.locked", "region_id": "brussels-nl", "evidence_name": "STEM After-School", "pods_counted": 13, "outcome": "+12% engagement", "privacy_boundary_ok": true}
```

### **Troll Events** (from `data/troll-run.jsonl`, Story 6.1)

```jsonl
{"timestamp": "2026-03-31T14:00:00Z", "event_type": "troll.run.start", "categories": ["Consent Gate", "Privacy Boundary", "ACL Revocation", "Aggregate Update"]}
{"timestamp": "2026-03-31T14:15:00Z", "event_type": "troll.probe.start", "probe_id": "probe-45", "category": "Privacy Boundary", "test_name": "access_civic_layer_unauthorized", "layer": "STOP4"}
{"timestamp": "2026-03-31T14:15:30Z", "event_type": "troll.probe.done", "probe_id": "probe-45", "result": "pass", "elapsed_ms": 234}
{"timestamp": "2026-03-31T14:32:00Z", "event_type": "troll.category.done", "category": "Consent Gate", "passed": 3, "partial": 1, "failed": 0}
{"timestamp": "2026-03-31T14:45:00Z", "event_type": "troll.run.done", "total_elapsed_ms": 45000, "blocking_pass": true}
```

---

## Textual Widget Architecture

### **App Structure**

```python
class MissionControlApp(App):
    """Root Textual app — four-section layout."""

    def compose(self) -> ComposeResult:
        """Layout: Header + 4 main sections + Footer."""
        yield Header()
        yield ScenarioSelector()  # Checkbox row + Pod filter indicator
        yield ConsentPropagationGantt()  # SECTION 1
        yield PodSpaceGrid()  # SECTION 2
        yield ConsentGateCounts()  # SECTION 3
        yield CivicAggregatePanel()  # SECTION 4 (hidden if not applicable)
        yield Footer()

class ScenarioSelector(Static):
    """Header: Multi-select scenarios, pod filter status."""

    def render(self) -> str:
        scenarios = [
            "☑ Claire (Teaching)",
            "☑ Isabelle (Outcome)",
            "☐ Ayoub (Transfer)",
            "☐ Fatima (Parent)",
            "☐ Marc (Admin)"
        ]
        if self.app.filtered_pod:
            scenarios.append(f" | Focused on: {self.app.filtered_pod}")
        return "\n".join(scenarios)

class ConsentPropagationGantt(Static):
    """SECTION 1: Gantt timeline showing consent journey through stops."""

    def render(self) -> str:
        # Dynamically render based on selected_scenarios + filtered_pod
        # Shows STOP 1-4 rows with timeline bars and keyframes
        pass

class PodSpaceGrid(Static):
    """SECTION 2: 4-col × 4-row compact pod grid."""

    def render_grid(self) -> str:
        # Render 16 pods as compact boxes
        # Colors based on pod_states
        # Bindable to click action
        pass

class ConsentGateCounts(Static):
    """SECTION 3: Live count summary."""

    def render(self) -> str:
        return (
            f"Active Grants: {len([p for p in self.app.pod_states.values() if p.state == 'active'])} | "
            f"Revoked: {len([p for p in self.app.pod_states.values() if p.state == 'revoked'])} | "
            f"..."
        )

class CivicAggregatePanel(Static):
    """SECTION 4: Civic layer + warnings."""

    def render(self) -> str:
        # Display civic aggregate if applicable
        # Show privacy boundary check result
        # Show alerts section
        pass

class DetailTabs(TabbedContent):
    """Tabs for scenario drill-down and [ATTACKS] control."""

    def compose(self) -> ComposeResult:
        yield TabPane("[SCENARIO: Claire]", ClaireDetailTab())
        yield TabPane("[SCENARIO: Isabelle]", IsabelleDetailTab())
        yield TabPane("[POD: <selected>]", PodDetailTab())
        yield TabPane("[ATTACKS]", AttacksControlTab())
```

---

## Reactive Update Loop (2-Second Polling)

```python
async def _poll_jsonl_events(self):
    """Background task: tail JSONL files every 2 seconds."""
    while True:
        # Read new events from JSONL files
        new_consent_events = await self._read_jsonl(CONSENT_JSONL_PATH)
        new_attack_events = await self._read_jsonl(TROLL_JSONL_PATH)

        # Update reactive attributes (triggers watchers)
        if new_consent_events != self.consent_events:
            self.consent_events = new_consent_events
            # watch_consent_events() fires automatically

        if new_attack_events != self.attack_events:
            self.attack_events = new_attack_events

        # Wait 2 seconds before next poll
        await asyncio.sleep(2)

def watch_consent_events(self):
    """Called when consent_events reactive attribute changes."""
    # 1. Recalculate all aggregates
    self._recalculate_aggregates()

    # 2. Refresh all sections
    self.query_one(ConsentPropagationGantt).refresh()
    self.query_one(PodSpaceGrid).refresh()
    self.query_one(ConsentGateCounts).refresh()
    self.query_one(CivicAggregatePanel).refresh()

    # 3. Check for alerts/failures
    self._check_data_quality()
```

---

## Summary: Dev Handoff Checklist

**Files to create:**
- [ ] `pipeline/src/pocpod0_pipeline/mission_control.py` — Main Textual app
- [ ] `pipeline/tests/test_mission_control.py` — Unit tests
- [ ] `pipeline/tests/fixtures/mock_consent_events.jsonl` — Test data

**Files to modify:**
- [ ] `pipeline/pyproject.toml` — Add `textual>=6.6.0`, add `pocpod0-mission-control` script entry

**Specification completeness:**
- ✅ Information architecture (4 sections, dynamic stops)
- ✅ Consent propagation model (4 stops with definitions)
- ✅ Scenario-stop mapping (which scenarios see which stops)
- ✅ Gantt rendering algorithm (vertical propagation, keyframes)
- ✅ Keyframe detection algorithm (per-stop trigger rules)
- ✅ Aggregate calculation logic (STOP 1-4 derivation, TUI owns all)
- ✅ Reactive state model (attributes + watchers)
- ✅ Pod grid interactivity (click behavior → filter Gantt)
- ✅ Detail tabs (4 scenario tabs + POD tab + ATTACKS tab)
- ✅ Visual language (color coding, typography)
- ✅ Graceful failure states (8 failure scenarios + alert handling)
- ✅ JSONL event catalog (all event types expected)
- ✅ Textual widget architecture (component breakdown)
- ✅ 2-second polling loop (async JSONL tailing)

**Unknowns (fog-of-war for later):**
- Key frame "impact" threshold — when is a count change "significant enough"? (Recommend: any change fires keyframe for now)
- Scenario multi-select tab behavior — Option 1 (tabbed) or Option 2 (stacked)? (Recommend: Option 1 for 6.2)
- Pod click drill-down — how deep (just pod detail tab, or multi-level)?
- ATTACKS tab control — manual button, or auto-trigger based on scenario?
- Textual performance at scale — validated against 200+ pods?

---

*Ready for dev. Reference this spec during implementation — it has the answers.* 🎯
