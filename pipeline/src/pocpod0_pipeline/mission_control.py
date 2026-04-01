"""Mission Control — Consent Propagation Network Visualizer for pocpod0.

A Textual TUI that shows operators (funders, demo observers) how consent decisions
flow through a multi-level system:
  STOP 1: Individual pods (where consent decisions originate)
  STOP 2: School cluster aggregate
  STOP 3: Regional hub
  STOP 4: Federal civic layer (de-identified evidence)

Usage (from repo root, venv active):
    pocpod0-mission-control
    # or: python -m pocpod0_pipeline.mission_control

Data sources:
    data/consent-events.jsonl — consent/acl events
    data/troll-run.jsonl — adversarial test results (surfaced in Story 6.3)

Architecture:
    - Textual reactive app with background worker for JSONL polling
    - Left column: Gantt (Sparkline per pod) + Pod Grid + Consent Gate + Civic Panel
    - Right column: Detail tabs (scenario timelines, pod history)
    - Scenario selection via Switch widgets in header bar
    - Pod click → filtered_pod reactive → POD detail tab updates
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from textual.app import App, ComposeResult, RenderableType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Label,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)


# =========================================================================
# Configuration
# =========================================================================

_CONSENT_EVENTS_FILE = (
    Path(__file__).parent.parent.parent.parent / "data" / "consent-events.jsonl"
)
_TROLL_RUN_FILE = Path(__file__).parent.parent.parent.parent / "data" / "troll-run.jsonl"

_POLL_INTERVAL = 2.0  # seconds, per AC requirement
_MIN_PODS_FOR_PUBLICATION = 10
_MAX_EVENTS = 500   # P11: cap in-memory event lists
_HISTORY_LEN = 20   # Sparkline data points per pod

# Scenario-to-STOP mapping (AC2)
SCENARIO_STOP_MAPPING = {
    "Claire": [1, 2],
    "Isabelle": [1, 2, 3, 4],
    "Ayoub": [1, 2],
    "Fatima": [1, 2],
    "Marc": [1, 2, 3],
}

# P6 fix: claire-pod moved to school-nl-1 (was incorrectly in school-fr-1
# while SCENARIO_CLUSTER_MAPPING["Claire"] pointed to school-nl-1)
CLUSTER_MAPPING = {
    "school-nl-1": ["ayoub-pod", "sofia-pod", "fatima-pod", "karim-pod",
                    "mehdi-pod", "yannick-pod", "amara-pod", "claire-pod"],
    "school-fr-1": ["jean-pod", "marie-pod", "pierre-pod", "sophie-pod",
                    "marc-pod", "isabelle-pod", "lucas-pod", "david-pod"],
}

REGION_MAPPING = {
    "nl-region": ["school-nl-1"],
    "fr-region": ["school-fr-1"],
}

ALL_PODS: set[str] = set()
for _pods in CLUSTER_MAPPING.values():
    ALL_PODS.update(_pods)

SCENARIO_CLUSTER_MAPPING = {
    "Claire": ["school-nl-1"],
    "Isabelle": ["school-nl-1", "school-fr-1"],
    "Ayoub": ["school-nl-1"],
    "Fatima": ["school-nl-1"],
    "Marc": ["school-nl-1", "school-fr-1"],
}

SCENARIO_REGION_MAPPING = {
    "Isabelle": ["nl-region", "fr-region"],
    "Marc": ["nl-region", "fr-region"],
}

ALL_SCENARIOS = ["Claire", "Isabelle", "Ayoub", "Fatima", "Marc"]

# Pod state → sparkline float (for D2 history visualization)
STATE_FLOAT = {
    "active": 1.0,
    "transitioning": 0.5,
    "revoked": 0.0,
    "anomaly": 0.0,
}


# =========================================================================
# State Models
# =========================================================================

class PodStateEnum(str, Enum):
    """Pod consent state."""
    ACTIVE = "active"
    REVOKED = "revoked"
    TRANSITIONING = "transitioning"
    ANOMALY = "anomaly"


@dataclass
class ConsentEvent:
    """Parsed consent event from JSONL."""
    timestamp: str
    event_type: str
    pod: str | None = None
    grantee_webid: str | None = None
    scope: str | None = None
    cluster_id: str | None = None
    region_id: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class PodState:
    """Track a single pod's consent status."""
    pod_id: str
    current_state: PodStateEnum
    last_event: ConsentEvent | None = None
    event_count: int = 0


@dataclass
class ClusterAggregate:
    """Track consent state for a school cluster."""
    cluster_id: str
    cluster_name: str
    pods: list[str]
    active_pods: int = 0
    revoked_pods: int = 0
    transitioning_pods: int = 0
    total_pods: int = 0
    last_updated: str = ""


@dataclass
class RegionalAggregate:
    """Track consent state across multiple clusters."""
    region_id: str
    region_name: str
    clusters: list[str]
    total_pods: int = 0
    active_pods: int = 0
    revoked_pods: int = 0
    publication_ready: bool = False
    last_updated: str = ""


@dataclass
class CivicAggregate:
    """Evidence base visible to federal civic layer."""
    evidence_name: str
    regional_source: str
    pods_in_base: int = 0
    outcome: str = ""
    privacy_boundary_respected: bool = True
    publication_status: str = "at_risk"


# =========================================================================
# Core Business Logic
# =========================================================================

def parse_consent_event(line: str) -> ConsentEvent | None:
    """Parse a JSONL line into a ConsentEvent."""
    try:
        data = json.loads(line.strip())
        if not data:
            return None
        return ConsentEvent(
            timestamp=data.get("timestamp", ""),
            event_type=data.get("event_type", ""),
            pod=data.get("pod"),
            grantee_webid=data.get("grantee_webid"),
            scope=data.get("scope"),
            cluster_id=data.get("cluster_id"),
            region_id=data.get("region_id"),
            extra=data,
        )
    except json.JSONDecodeError:
        return None


def _parse_ts(ts: str) -> datetime:
    """Parse ISO 8601 timestamp robustly (P12: tolerates Z suffix)."""
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def calculate_pod_state(pod_id: str, events: list[ConsentEvent]) -> PodState:
    """Determine pod's current state from consent history (Task 2.1)."""
    pod_events = [e for e in events if e.pod == pod_id]
    if not pod_events:
        return PodState(pod_id=pod_id, current_state=PodStateEnum.ANOMALY, event_count=0)

    # P12 fix: sort by parsed datetime, not lexicographic string
    try:
        pod_events.sort(key=lambda e: _parse_ts(e.timestamp))
    except (ValueError, TypeError):
        pod_events.sort(key=lambda e: e.timestamp)
    last = pod_events[-1]

    if last.event_type in ["consent.revoke", "consent.expired"]:
        state = PodStateEnum.REVOKED
    elif last.event_type == "acl.governance.transition":
        state = PodStateEnum.TRANSITIONING
    elif last.event_type in ["consent.grant", "acl.grant"]:
        state = PodStateEnum.ACTIVE
    else:
        state = PodStateEnum.ANOMALY

    return PodState(pod_id=pod_id, current_state=state, last_event=last, event_count=len(pod_events))


def calculate_cluster_aggregate(
    cluster_id: str, pod_states: dict[str, PodState]
) -> ClusterAggregate:
    """Sum pod states to get cluster-level counts (Task 3.1)."""
    pods_in_cluster = CLUSTER_MAPPING.get(cluster_id, [])
    active = sum(1 for p in pods_in_cluster if pod_states.get(p, PodState(p, PodStateEnum.ANOMALY)).current_state == PodStateEnum.ACTIVE)
    revoked = sum(1 for p in pods_in_cluster if pod_states.get(p, PodState(p, PodStateEnum.ANOMALY)).current_state == PodStateEnum.REVOKED)
    transitioning = sum(1 for p in pods_in_cluster if pod_states.get(p, PodState(p, PodStateEnum.ANOMALY)).current_state == PodStateEnum.TRANSITIONING)
    return ClusterAggregate(
        cluster_id=cluster_id,
        cluster_name=cluster_id.replace("-", " ").title(),
        pods=pods_in_cluster,
        active_pods=active,
        revoked_pods=revoked,
        transitioning_pods=transitioning,
        total_pods=len(pods_in_cluster),
        last_updated=datetime.now().isoformat(),
    )


def calculate_regional_aggregate(
    region_id: str, cluster_aggregates: dict[str, ClusterAggregate]
) -> RegionalAggregate:
    """Sum cluster aggregates to get regional counts (Task 4.1)."""
    clusters_in_region = REGION_MAPPING.get(region_id, [])
    total = sum(cluster_aggregates.get(c, ClusterAggregate(c, c, [])).total_pods for c in clusters_in_region)
    active = sum(cluster_aggregates.get(c, ClusterAggregate(c, c, [])).active_pods for c in clusters_in_region)
    revoked = sum(cluster_aggregates.get(c, ClusterAggregate(c, c, [])).revoked_pods for c in clusters_in_region)
    return RegionalAggregate(
        region_id=region_id,
        region_name=region_id.replace("-", " ").title(),
        clusters=clusters_in_region,
        total_pods=total,
        active_pods=active,
        revoked_pods=revoked,
        publication_ready=active >= _MIN_PODS_FOR_PUBLICATION,
        last_updated=datetime.now().isoformat(),
    )


def calculate_civic_aggregate(
    regional_agg: RegionalAggregate, pod_states: dict[str, PodState]
) -> CivicAggregate:
    """Derive civic-layer aggregate from regional + pod data (Task 5.1)."""
    pods_in_region: list[str] = []
    for cluster_id in regional_agg.clusters:
        pods_in_region.extend(CLUSTER_MAPPING.get(cluster_id, []))

    privacy_ok = all(
        pod_states.get(p, PodState(p, PodStateEnum.ANOMALY)).current_state != PodStateEnum.REVOKED
        for p in pods_in_region
    )
    publication_ok = regional_agg.publication_ready

    # P7 fix: "ready" when clean, "at_risk" when violated (was inverted)
    # P8 fix: outcome derived from region, not hardcoded "+12% engagement"
    outcome = (
        f"+N% engagement ({regional_agg.region_name})" if publication_ok else "insufficient data"
    )
    return CivicAggregate(
        evidence_name=f"Evidence Base ({regional_agg.region_name})",
        regional_source=regional_agg.region_id,
        pods_in_base=regional_agg.active_pods,
        outcome=outcome,
        privacy_boundary_respected=privacy_ok,
        publication_status="ready" if (privacy_ok and publication_ok) else "at_risk",
    )


def should_fire_keyframe_stop1(event: ConsentEvent) -> bool:
    """Fire keyframe at STOP 1 on consent/acl events (Task 6.1)."""
    return event.event_type in [
        "consent.grant",
        "consent.revoke",
        "consent.expired",
        "acl.grant",
        "acl.revoke",
        "acl.governance.transition",  # P1 fix: was missing
    ]


def should_fire_keyframe_stop2(
    event: ConsentEvent,
    previous_agg: ClusterAggregate | None,
    current_agg: ClusterAggregate | None = None,
) -> bool:
    """Fire keyframe when cluster active_pods count changes (Task 6.2).

    P2 fix: now compares actual counts instead of always returning True.
    current_agg defaults to None for backward compatibility; when None,
    fires if previous_agg exists (conservative: assume change occurred).
    """
    if previous_agg is None:
        return False
    if current_agg is None:
        return True  # backward compat: no current provided, assume change
    return current_agg.active_pods != previous_agg.active_pods


def should_fire_keyframe_stop3(
    event: ConsentEvent,
    previous_regional: RegionalAggregate | None,
    current_regional: RegionalAggregate | None = None,
) -> bool:
    """Fire keyframe when regional active_pods count changes (Task 6.3).

    P2 fix: same pattern as stop2.
    """
    if previous_regional is None:
        return False
    if current_regional is None:
        return True
    return current_regional.active_pods != previous_regional.active_pods


def should_fire_keyframe_stop4(event: ConsentEvent) -> bool:
    """Fire keyframe on explicit civic events (Task 6.4)."""
    return event.event_type in [
        "civic.aggregate.locked",
        "civic.threshold.breach",
        "deletion.complete",
    ]


# =========================================================================
# Widgets
# =========================================================================

class PodSparklineRow(Horizontal):
    """One pod row in the Gantt: label + Sparkline history (D2)."""

    DEFAULT_CSS = """
    PodSparklineRow {
        height: 1;
        margin: 0;
    }
    PodSparklineRow Label {
        width: 20;
    }
    PodSparklineRow Sparkline {
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self, pod_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pod_id = pod_id
        self._safe = pod_id.replace("-", "_")

    def compose(self) -> ComposeResult:
        yield Label(f"[dim]{self._pod_id[:18]:18}[/dim]", id=f"lbl_{self._safe}")
        yield Sparkline([0.0] * _HISTORY_LEN, id=f"spark_{self._safe}")

    def update_pod(self, state: PodStateEnum, history: list[float]) -> None:
        """Update label with state icon and Sparkline with history data."""
        icon_map = {
            PodStateEnum.ACTIVE: ("✓", "green"),
            PodStateEnum.REVOKED: ("✗", "red"),
            PodStateEnum.TRANSITIONING: ("⟳", "yellow"),
            PodStateEnum.ANOMALY: ("⚠", "magenta"),
        }
        icon, color = icon_map[state]
        try:
            self.query_one(f"#lbl_{self._safe}", Label).update(
                f"[{color}]{self._pod_id[:16]:16} {icon}[/{color}]"
            )
            self.query_one(f"#spark_{self._safe}", Sparkline).data = (
                history if history else [0.0] * _HISTORY_LEN
            )
        except NoMatches:
            pass


class ConsentPropagationGantt(VerticalScroll):
    """STOP 1-4 Gantt with per-pod Sparkline timelines (Task 7, D2).

    Pre-mounts rows for all pods; shows/hides per active scenario.
    P9 fix: STOP visibility filtered per-scenario (not union-wide).
    """

    DEFAULT_CSS = """
    ConsentPropagationGantt {
        border: solid $accent;
        height: 14;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scenarios: list[str] = []
        self._pod_states: dict = {}
        self._cluster_aggregates: dict = {}
        self._regional_aggregates: dict = {}
        self._civic_aggregates: dict = {}
        self._pod_history: dict = {}

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]CONSENT PROPAGATION GANTT — STOP 1-4[/bold cyan]")
        yield Label("[dim]No scenarios selected.[/dim]", id="gantt-empty-msg")
        for pod_id in sorted(ALL_PODS):
            safe = pod_id.replace("-", "_")
            row = PodSparklineRow(pod_id, id=f"gantt-row-{safe}", classes="pod-row")
            row.display = False  # hidden until first update_state call
            yield row
        yield Static("", id="gantt-cluster-status")
        yield Static("", id="gantt-regional-status")
        yield Static("", id="gantt-civic-status")

    def update_state(
        self,
        scenarios: list[str],
        pod_states: dict,
        cluster_aggs: dict,
        regional_aggs: dict,
        civic_aggs: dict,
        pod_history: dict,
    ) -> None:
        """Refresh all Gantt rows and aggregate panels."""
        self._scenarios = scenarios
        self._pod_states = pod_states
        self._cluster_aggregates = cluster_aggs
        self._regional_aggregates = regional_aggs
        self._civic_aggregates = civic_aggs
        self._pod_history = pod_history

        try:
            self.query_one("#gantt-empty-msg", Label).display = not scenarios
        except NoMatches:
            pass

        if not scenarios:
            return

        # Determine visible pods (union across selected scenarios for STOP 1)
        visible_pods: set[str] = set()
        for scenario in scenarios:
            for cluster_id in SCENARIO_CLUSTER_MAPPING.get(scenario, []):
                visible_pods.update(CLUSTER_MAPPING.get(cluster_id, []))

        for pod_id in sorted(ALL_PODS):
            safe = pod_id.replace("-", "_")
            try:
                row = self.query_one(f"#gantt-row-{safe}", PodSparklineRow)
                row.display = pod_id in visible_pods
                if pod_id in visible_pods:
                    state = pod_states.get(
                        pod_id, PodState(pod_id, PodStateEnum.ANOMALY)
                    ).current_state
                    history = pod_history.get(pod_id, [0.0] * _HISTORY_LEN)
                    row.update_pod(state, history)
            except NoMatches:
                pass

        self._refresh_aggregate_panels(scenarios)

    def _refresh_aggregate_panels(self, scenarios: list[str]) -> None:
        """Update STOP 2/3/4 text panels (P9 fix: per-scenario STOP filtering)."""
        cluster_lines: list[str] = []
        regional_lines: list[str] = []
        civic_lines: list[str] = []
        shown_clusters: set[str] = set()
        shown_regions: set[str] = set()

        for scenario in scenarios:
            # P9 fix: use scenario-specific stops, not the union
            scenario_stops = SCENARIO_STOP_MAPPING.get(scenario, [])

            if 2 in scenario_stops:
                if not cluster_lines:
                    cluster_lines.append("[green]▼ STOP 2: School Clusters[/green]")
                for cluster_id in SCENARIO_CLUSTER_MAPPING.get(scenario, []):
                    if cluster_id not in shown_clusters:
                        shown_clusters.add(cluster_id)
                        agg = self._cluster_aggregates.get(cluster_id)
                        if agg:
                            cluster_lines.append(
                                f"  {agg.cluster_name}: {agg.active_pods}/{agg.total_pods} active"
                            )

            if 3 in scenario_stops:
                if not regional_lines:
                    regional_lines.append("[yellow]▼ STOP 3: Regional Hubs[/yellow]")
                for region_id in SCENARIO_REGION_MAPPING.get(scenario, []):
                    if region_id not in shown_regions:
                        shown_regions.add(region_id)
                        agg = self._regional_aggregates.get(region_id)
                        if agg:
                            ready = "READY ✓" if agg.publication_ready else "AT RISK ✗"
                            regional_lines.append(
                                f"  {agg.region_name}: {agg.active_pods}/{agg.total_pods} ({ready})"
                            )

            if 4 in scenario_stops:
                if not civic_lines:
                    civic_lines.append("[magenta]▼ STOP 4: Federal Civic Layer[/magenta]")
                for region_id in SCENARIO_REGION_MAPPING.get(scenario, []):
                    agg = self._civic_aggregates.get(region_id)
                    if agg:
                        privacy = "✓" if agg.privacy_boundary_respected else "✗ VIOLATED"
                        civic_lines.append(
                            f"  {agg.evidence_name}: {agg.pods_in_base} pods | {privacy} | {agg.publication_status}"
                        )

        try:
            self.query_one("#gantt-cluster-status", Static).update(
                "\n".join(cluster_lines) if cluster_lines else ""
            )
            self.query_one("#gantt-regional-status", Static).update(
                "\n".join(regional_lines) if regional_lines else ""
            )
            self.query_one("#gantt-civic-status", Static).update(
                "\n".join(civic_lines) if civic_lines else ""
            )
        except NoMatches:
            pass


class PodSpaceGrid(Vertical):
    """4×4 pod grid with clickable Button widgets (Task 8, P4)."""

    DEFAULT_CSS = """
    PodSpaceGrid {
        border: solid $accent;
        height: auto;
    }
    PodSpaceGrid Horizontal {
        height: 3;
    }
    PodSpaceGrid Button {
        min-width: 18;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]POD SPACE (4×4)[/bold cyan]")
        pods = sorted(ALL_PODS)
        for row_start in range(0, len(pods), 4):
            with Horizontal():
                for pod_id in pods[row_start:row_start + 4]:
                    safe = pod_id.replace("-", "_")
                    yield Button(pod_id[:14], id=f"pod-btn-{safe}", variant="default")

    def update_state(self, pod_states: dict) -> None:
        """Update each pod button with state color and icon."""
        variant_map = {
            PodStateEnum.ACTIVE: ("success", "✓"),
            PodStateEnum.REVOKED: ("error", "✗"),
            PodStateEnum.TRANSITIONING: ("warning", "⟳"),
            PodStateEnum.ANOMALY: ("default", "⚠"),
        }
        for pod_id in sorted(ALL_PODS):
            safe = pod_id.replace("-", "_")
            try:
                btn = self.query_one(f"#pod-btn-{safe}", Button)
                state = pod_states.get(pod_id, PodState(pod_id, PodStateEnum.ANOMALY)).current_state
                variant, icon = variant_map[state]
                btn.label = f"{pod_id[:12]:12} {icon}"
                btn.variant = variant
            except NoMatches:
                pass


class ConsentGateCounts(Static):
    """Live consent counts: Active, Revoked, Expired, Transitioning (Task 9)."""

    DEFAULT_CSS = "ConsentGateCounts { height: 3; border: solid $accent; }"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.pod_states: dict = {}

    def render(self) -> RenderableType:
        active = sum(1 for p in self.pod_states.values() if p.current_state == PodStateEnum.ACTIVE)
        transitioning = sum(1 for p in self.pod_states.values() if p.current_state == PodStateEnum.TRANSITIONING)
        # P10 fix: revoked and expired are distinct subsets of REVOKED state
        revoked = sum(
            1 for p in self.pod_states.values()
            if p.current_state == PodStateEnum.REVOKED
            and p.last_event is not None
            and p.last_event.event_type == "consent.revoke"
        )
        expired = sum(
            1 for p in self.pod_states.values()
            if p.current_state == PodStateEnum.REVOKED
            and p.last_event is not None
            and p.last_event.event_type == "consent.expired"
        )
        return (
            "[bold cyan]CONSENT GATE[/bold cyan]\n"
            f"Active: [green]{active}[/green] | "
            f"Revoked: [red]{revoked}[/red] | "
            f"Expired: [dim]{expired}[/dim] | "
            f"Transitioning: [yellow]{transitioning}[/yellow]"
        )

    def update_state(self, pod_states: dict) -> None:
        self.pod_states = pod_states
        self.update(self.render())


class CivicAggregatePanel(Static):
    """Civic evidence base + alerts panel (Task 10)."""

    DEFAULT_CSS = "CivicAggregatePanel { height: auto; border: solid $accent; overflow-y: auto; }"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.scenarios: list[str] = []
        self.civic_aggregates: dict = {}
        self.alerts: list[str] = []

    def render(self) -> RenderableType:
        lines = ["[bold magenta]CIVIC AGGREGATE + ALERTS[/bold magenta]"]

        if "Isabelle" not in self.scenarios:
            lines.append("[dim]Select 'Isabelle' to view civic layer.[/dim]")
        else:
            for agg in self.civic_aggregates.values():
                privacy = "✓ Respected" if agg.privacy_boundary_respected else "✗ VIOLATED"
                lines.append(f"\n{agg.evidence_name}:")
                lines.append(f"  Pods: {agg.pods_in_base} | Outcome: {agg.outcome}")
                lines.append(f"  Privacy: {privacy} | Status: {agg.publication_status}")

        if self.alerts:
            lines.append("\n[yellow]⚠ Alerts:[/yellow]")
            for alert in self.alerts[:10]:  # P14 fix: was [:5], cap matches _add_alert
                lines.append(f"  {alert}")

        return "\n".join(lines)

    def update_state(self, scenarios: list[str], civic_aggs: dict, alerts: list[str]) -> None:
        self.scenarios = scenarios
        self.civic_aggregates = civic_aggs
        self.alerts = alerts
        self.update(self.render())


# =========================================================================
# Detail Tabs (D1)
# =========================================================================

class ScenarioDetailPanel(Static):
    """Scenario-specific event timeline for a detail tab."""

    def __init__(self, scenario: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scenario = scenario

    def render(self) -> RenderableType:
        return f"[dim]{self._scenario} — waiting for events...[/dim]"

    def update_events(self, events: list[ConsentEvent], pod_states: dict) -> None:
        """Refresh with events relevant to this scenario (last 20)."""
        clusters = SCENARIO_CLUSTER_MAPPING.get(self._scenario, [])
        relevant_pods: set[str] = set()
        for c in clusters:
            relevant_pods.update(CLUSTER_MAPPING.get(c, []))

        recent = [e for e in events if e.pod in relevant_pods][-20:]

        stops = SCENARIO_STOP_MAPPING.get(self._scenario, [])
        lines = [f"[bold]{self._scenario} — STOP {min(stops)}-{max(stops)} journey[/bold]"]

        if not recent:
            lines.append("[dim]No events yet.[/dim]")
        else:
            for e in reversed(recent):
                ts = e.timestamp[-8:] if len(e.timestamp) >= 8 else e.timestamp
                pod = (e.pod or "—")[:12]
                lines.append(f"  [{ts}] {pod:12} → {e.event_type}")

        # Cluster summary for this scenario
        for cluster_id in clusters:
            agg = pod_states.get(f"__cluster_{cluster_id}")  # not a pod, skip
            _ = agg  # cluster summaries come from the Gantt, not here

        self.update("\n".join(lines))


class PodDetailPanel(Static):
    """Consent history for a selected pod (POD tab, D1)."""

    DEFAULT_CSS = "PodDetailPanel { height: auto; }"

    def render(self) -> RenderableType:
        return "[dim]Click a pod in the grid to see its consent history.[/dim]"

    def update_pod(
        self, pod_id: str | None, events: list[ConsentEvent], pod_states: dict
    ) -> None:
        if pod_id is None:
            self.update("[dim]No pod selected.[/dim]")
            return

        pod_events = [e for e in events if e.pod == pod_id][-30:]
        state = pod_states.get(pod_id)
        current = state.current_state.value if state else "unknown"

        lines = [
            f"[bold cyan]Pod: {pod_id}[/bold cyan]",
            f"State: [bold]{current}[/bold]  |  Events: {len(pod_events)}",
            "",
            "[bold]Recent events (newest first):[/bold]",
        ]
        if not pod_events:
            lines.append("[dim]No events recorded.[/dim]")
        else:
            for e in reversed(pod_events):
                ts = e.timestamp[-8:] if len(e.timestamp) >= 8 else e.timestamp
                lines.append(f"  [{ts}] {e.event_type}")

        self.update("\n".join(lines))


# =========================================================================
# Main App
# =========================================================================

class MissionControlApp(App):
    """Main Mission Control application (Task 1)."""

    TITLE = "Mission Control — Consent Propagation Network"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear_filter", "Clear pod filter"),
    ]

    # Reactive attributes (Task 1.2)
    consent_events: reactive[list] = reactive([])
    troll_events: reactive[list] = reactive([])
    pod_states: reactive[dict] = reactive({})
    cluster_aggregates: reactive[dict] = reactive({})
    regional_aggregates: reactive[dict] = reactive({})
    civic_aggregates: reactive[dict] = reactive({})
    selected_scenarios: reactive[list] = reactive(["Claire", "Isabelle"])
    filtered_pod: reactive[str | None] = reactive(None)
    alerts: reactive[list] = reactive([])

    DEFAULT_CSS = """
    Screen { layout: vertical; }

    #scenario-bar {
        height: 5;
        border: solid $primary;
    }
    #scenario-bar Label { width: auto; margin: 1 1; }
    #scenario-bar Switch { width: 6; margin: 1 0; }

    #filtered-pod-bar {
        height: 1;
        background: $surface-darken-1;
        display: none;
    }

    #main-panels {
        height: 1fr;
    }

    #left-column {
        width: 2fr;
        height: 100%;
    }

    #detail-tabs {
        width: 1fr;
        height: 100%;
        border: solid $accent;
    }

    #gantt-section { height: 14; }
    #pod-grid { height: auto; }
    #consent-gate { height: 3; }
    #civic-panel { height: 1fr; }
    """

    def __init__(self) -> None:
        super().__init__()
        # Per-pod Sparkline history (not reactive; updated directly)
        self._pod_history: dict[str, list[float]] = {
            pod: [0.0] * _HISTORY_LEN for pod in ALL_PODS
        }

    def compose(self) -> ComposeResult:
        """Compose layout: scenario bar + main panels (Gantt/Grid/Gate/Civic) + detail tabs."""
        # P3 fix: Switch widgets instead of static label
        with Horizontal(id="scenario-bar"):
            yield Label("[bold]Scenarios:[/bold]")
            for scenario in ALL_SCENARIOS:
                active = scenario in ["Claire", "Isabelle"]
                yield Switch(value=active, id=f"switch-{scenario}", name=scenario)
                yield Label(scenario)

        yield Label("", id="filtered-pod-bar")

        with Horizontal(id="main-panels"):
            with Vertical(id="left-column"):
                yield ConsentPropagationGantt(id="gantt-section")
                yield PodSpaceGrid(id="pod-grid")
                yield ConsentGateCounts(id="consent-gate")
                yield CivicAggregatePanel(id="civic-panel")

            # D1: TabbedContent with 5 tabs
            with TabbedContent(id="detail-tabs"):
                with TabPane("Claire", id="tab-claire"):
                    yield ScenarioDetailPanel("Claire", id="panel-claire")
                with TabPane("Isabelle", id="tab-isabelle"):
                    yield ScenarioDetailPanel("Isabelle", id="panel-isabelle")
                with TabPane("Ayoub", id="tab-ayoub"):
                    yield ScenarioDetailPanel("Ayoub", id="panel-ayoub")
                with TabPane("Pod", id="tab-pod"):
                    yield PodDetailPanel(id="panel-pod")
                with TabPane("Attacks ⏳", id="tab-attacks"):
                    yield Static(
                        "[dim]Attack summary deferred to Story 6.3 (Funder Intervention Points).[/dim]"
                    )

        yield Footer()

    async def on_mount(self) -> None:
        """Start JSONL polling on app mount (Task 1.3)."""
        # Initial render with default scenarios (no waiting for first poll)
        self._update_calculated_state()
        self._poll_jsonl_task = asyncio.create_task(self._poll_jsonl_loop())

    # -----------------------------------------------------------------------
    # Event handlers

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle scenario toggle (P3)."""
        scenario = event.switch.name
        if scenario is None:
            return
        scenarios = list(self.selected_scenarios)
        if event.value and scenario not in scenarios:
            scenarios.append(scenario)
        elif not event.value and scenario in scenarios:
            scenarios.remove(scenario)
        self.selected_scenarios = scenarios

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle pod button click → set filtered_pod (P4)."""
        btn_id = event.button.id or ""
        if btn_id.startswith("pod-btn-"):
            pod_safe = btn_id[len("pod-btn-"):]
            pod_id = pod_safe.replace("_", "-")
            if pod_id in ALL_PODS:
                self.filtered_pod = pod_id
                try:
                    self.query_one("#detail-tabs", TabbedContent).active = "tab-pod"
                except NoMatches:
                    pass

    def action_clear_filter(self) -> None:
        """Clear pod filter (AC2 — clear filter returns to multi-scenario view)."""
        self.filtered_pod = None

    # -----------------------------------------------------------------------
    # Polling

    async def _poll_jsonl_loop(self) -> None:
        """Background JSONL polling worker (P11: bounded lists, P13: truncation reset)."""
        last_consent_pos = 0
        last_troll_pos = 0

        while True:
            try:
                # P13: detect file truncation (demo reset via compose down -v)
                if _CONSENT_EVENTS_FILE.exists():
                    if _CONSENT_EVENTS_FILE.stat().st_size < last_consent_pos:
                        last_consent_pos = 0
                    with open(_CONSENT_EVENTS_FILE, "r") as f:
                        f.seek(last_consent_pos)
                        new_events = [
                            e for line in f
                            if (e := parse_consent_event(line)) is not None
                        ]
                        last_consent_pos = f.tell()
                    if new_events:
                        # P11: cap at _MAX_EVENTS
                        self.consent_events = (list(self.consent_events) + new_events)[-_MAX_EVENTS:]

                if _TROLL_RUN_FILE.exists():
                    if _TROLL_RUN_FILE.stat().st_size < last_troll_pos:
                        last_troll_pos = 0
                    with open(_TROLL_RUN_FILE, "r") as f:
                        f.seek(last_troll_pos)
                        new_troll = []
                        for line in f:
                            try:
                                evt = json.loads(line.strip())
                                if evt:
                                    new_troll.append(evt)
                            except json.JSONDecodeError:
                                pass
                        last_troll_pos = f.tell()
                    if new_troll:
                        self.troll_events = (list(self.troll_events) + new_troll)[-_MAX_EVENTS:]

                # Recalculate after reading both files
                self._update_calculated_state()

            except Exception as e:
                self._add_alert(f"Poll error: {e}")

            await asyncio.sleep(_POLL_INTERVAL)

    # -----------------------------------------------------------------------
    # State calculation

    def _update_pod_history(self, pod_states: dict) -> None:
        """Append current state value to each pod's Sparkline history (D2)."""
        for pod_id in ALL_PODS:
            state = pod_states.get(pod_id, PodState(pod_id, PodStateEnum.ANOMALY)).current_state
            val = STATE_FLOAT.get(state.value, 0.0)
            prev = self._pod_history.get(pod_id, [0.0] * _HISTORY_LEN)
            self._pod_history[pod_id] = (prev + [val])[-_HISTORY_LEN:]

    def _update_calculated_state(self) -> None:
        """Recalculate all aggregates (P5 fix: pod_states assigned last so watcher sees fresh aggregates)."""
        pod_states = {
            pod_id: calculate_pod_state(pod_id, self.consent_events)
            for pod_id in ALL_PODS
        }
        cluster_aggs = {
            cluster_id: calculate_cluster_aggregate(cluster_id, pod_states)
            for cluster_id in CLUSTER_MAPPING
        }
        regional_aggs = {
            region_id: calculate_regional_aggregate(region_id, cluster_aggs)
            for region_id in REGION_MAPPING
        }
        civic_aggs = {
            region_id: calculate_civic_aggregate(regional_aggs[region_id], pod_states)
            for region_id in REGION_MAPPING
        }

        self._update_pod_history(pod_states)

        # P5 fix: set aggregates BEFORE pod_states so watch_pod_states sees fresh data
        self.cluster_aggregates = cluster_aggs
        self.regional_aggregates = regional_aggs
        self.civic_aggregates = civic_aggs
        self.pod_states = pod_states  # triggers watch_pod_states last

    def _add_alert(self, message: str) -> None:
        alerts = list(self.alerts)
        alerts.append(message)
        self.alerts = alerts[-10:]

    # -----------------------------------------------------------------------
    # Watchers (P16 fix: narrow except to NoMatches only)

    def watch_pod_states(self) -> None:
        """Update Gantt, grid, gate, and tabs when pod states change."""
        try:
            self.query_one("#gantt-section", ConsentPropagationGantt).update_state(
                self.selected_scenarios,
                self.pod_states,
                self.cluster_aggregates,
                self.regional_aggregates,
                self.civic_aggregates,
                self._pod_history,
            )
        except NoMatches:
            pass

        try:
            self.query_one("#pod-grid", PodSpaceGrid).update_state(self.pod_states)
        except NoMatches:
            pass

        try:
            self.query_one("#consent-gate", ConsentGateCounts).update_state(self.pod_states)
        except NoMatches:
            pass

        self._refresh_detail_tabs()

    def watch_civic_aggregates(self) -> None:
        """Update civic panel when civic aggregates change."""
        try:
            self.query_one("#civic-panel", CivicAggregatePanel).update_state(
                self.selected_scenarios, self.civic_aggregates, self.alerts
            )
        except NoMatches:
            pass

    def watch_selected_scenarios(self) -> None:
        """Update Gantt and civic panel when scenario selection changes."""
        try:
            self.query_one("#gantt-section", ConsentPropagationGantt).update_state(
                self.selected_scenarios,
                self.pod_states,
                self.cluster_aggregates,
                self.regional_aggregates,
                self.civic_aggregates,
                self._pod_history,
            )
        except NoMatches:
            pass

        try:
            self.query_one("#civic-panel", CivicAggregatePanel).update_state(
                self.selected_scenarios, self.civic_aggregates, self.alerts
            )
        except NoMatches:
            pass

    def watch_filtered_pod(self, pod_id: str | None) -> None:
        """Update POD detail tab and filtered-pod indicator bar."""
        try:
            bar = self.query_one("#filtered-pod-bar", Label)
            if pod_id:
                bar.display = True
                bar.update(f"[bold]Pod filter: {pod_id}[/bold]  [dim](press C to clear)[/dim]")
            else:
                bar.display = False
        except NoMatches:
            pass

        try:
            self.query_one("#panel-pod", PodDetailPanel).update_pod(
                pod_id, self.consent_events, self.pod_states
            )
        except NoMatches:
            pass

    # -----------------------------------------------------------------------
    # Detail tab refresh

    def _refresh_detail_tabs(self) -> None:
        """Refresh all scenario + pod detail panels."""
        for scenario in ALL_SCENARIOS:
            panel_id = f"panel-{scenario.lower()}"
            try:
                self.query_one(f"#{panel_id}", ScenarioDetailPanel).update_events(
                    self.consent_events, self.pod_states
                )
            except NoMatches:
                pass

        if self.filtered_pod:
            try:
                self.query_one("#panel-pod", PodDetailPanel).update_pod(
                    self.filtered_pod, self.consent_events, self.pod_states
                )
            except NoMatches:
                pass


def main() -> None:
    """Main entry point."""
    MissionControlApp().run()


if __name__ == "__main__":
    main()
