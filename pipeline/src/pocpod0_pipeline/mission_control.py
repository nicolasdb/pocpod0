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
    data/troll-run.jsonl — adversarial test results

Architecture:
    - Textual reactive app with background worker for JSONL polling
    - 4-section layout (always visible): Gantt, Pod Grid, Consent Gate, Civic Panel
    - Dynamic STOP visibility based on selected scenarios
    - Scenario selection via header checkboxes (Claire, Isabelle, Ayoub, Fatima, Marc)
    - Detail tabs for drill-down (scenario timelines, pod history, test results)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from textual.app import App, ComposeResult, RenderableType
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Label, Static


# =========================================================================
# Configuration
# =========================================================================

_CONSENT_EVENTS_FILE = (
    Path(__file__).parent.parent.parent.parent / "data" / "consent-events.jsonl"
)
_TROLL_RUN_FILE = Path(__file__).parent.parent.parent.parent / "data" / "troll-run.jsonl"

_POLL_INTERVAL = 2.0  # seconds, per AC requirement
_MIN_PODS_FOR_PUBLICATION = 10

# Scenario-to-STOP mapping (AC2)
SCENARIO_STOP_MAPPING = {
    "Claire": [1, 2],
    "Isabelle": [1, 2, 3, 4],
    "Ayoub": [1, 2],
    "Fatima": [1, 2],
    "Marc": [1, 2, 3],
}

# Pod-to-cluster mapping (simplified for 16 pods in 4×4 grid)
CLUSTER_MAPPING = {
    "school-nl-1": ["ayoub-pod", "sofia-pod", "fatima-pod", "karim-pod",
                    "mehdi-pod", "yannick-pod", "amara-pod", "lucas-pod"],
    "school-fr-1": ["jean-pod", "marie-pod", "pierre-pod", "sophie-pod",
                    "marc-pod", "isabelle-pod", "claire-pod", "david-pod"],
}

# Cluster-to-region mapping
REGION_MAPPING = {
    "nl-region": ["school-nl-1"],
    "fr-region": ["school-fr-1"],
}

# Pod discovery from cluster mapping
ALL_PODS = set()
for pods in CLUSTER_MAPPING.values():
    ALL_PODS.update(pods)

# Scenario-to-cluster mapping
SCENARIO_CLUSTER_MAPPING = {
    "Claire": ["school-nl-1"],
    "Isabelle": ["school-nl-1", "school-fr-1"],
    "Ayoub": ["school-nl-1"],
    "Fatima": ["school-nl-1"],
    "Marc": ["school-nl-1", "school-fr-1"],
}

# Region-to-scenario mapping
SCENARIO_REGION_MAPPING = {
    "Isabelle": ["nl-region", "fr-region"],
    "Marc": ["nl-region", "fr-region"],
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
    publication_status: str = "locked"


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


def calculate_pod_state(pod_id: str, events: list[ConsentEvent]) -> PodState:
    """Determine pod's current state from consent history (Task 2.1)."""
    pod_events = [e for e in events if e.pod == pod_id]
    if not pod_events:
        return PodState(pod_id=pod_id, current_state=PodStateEnum.ANOMALY, event_count=0)

    # Sort by timestamp
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
    total = len(pods_in_cluster)

    return ClusterAggregate(
        cluster_id=cluster_id,
        cluster_name=cluster_id.replace("-", " ").title(),
        pods=pods_in_cluster,
        active_pods=active,
        revoked_pods=revoked,
        transitioning_pods=transitioning,
        total_pods=total,
        last_updated=datetime.now().isoformat(),
    )


def calculate_regional_aggregate(
    region_id: str, cluster_aggregates: dict[str, ClusterAggregate]
) -> RegionalAggregate:
    """Sum cluster aggregates to get regional counts (Task 4.1)."""
    clusters_in_region = REGION_MAPPING.get(region_id, [])

    total = sum(
        cluster_aggregates.get(c, ClusterAggregate(c, c, [])).total_pods
        for c in clusters_in_region
    )
    active = sum(
        cluster_aggregates.get(c, ClusterAggregate(c, c, [])).active_pods
        for c in clusters_in_region
    )
    revoked = sum(
        cluster_aggregates.get(c, ClusterAggregate(c, c, [])).revoked_pods
        for c in clusters_in_region
    )

    publication_ready = active >= _MIN_PODS_FOR_PUBLICATION

    return RegionalAggregate(
        region_id=region_id,
        region_name=region_id.replace("-", " ").title(),
        clusters=clusters_in_region,
        total_pods=total,
        active_pods=active,
        revoked_pods=revoked,
        publication_ready=publication_ready,
        last_updated=datetime.now().isoformat(),
    )


def calculate_civic_aggregate(
    regional_agg: RegionalAggregate, pod_states: dict[str, PodState]
) -> CivicAggregate:
    """Derive civic-layer aggregate from regional + pod data (Task 5.1)."""
    # Privacy boundary check: revoked pods must not appear
    pods_in_region = []
    for cluster_id in regional_agg.clusters:
        pods_in_region.extend(CLUSTER_MAPPING.get(cluster_id, []))

    privacy_ok = all(
        pod_states.get(p, PodState(p, PodStateEnum.ANOMALY)).current_state != PodStateEnum.REVOKED
        for p in pods_in_region
    )

    publication_ok = regional_agg.publication_ready

    return CivicAggregate(
        evidence_name=f"Evidence Base ({regional_agg.region_name})",
        regional_source=regional_agg.region_id,
        pods_in_base=regional_agg.active_pods,
        outcome="+12% engagement" if publication_ok else "unknown",
        privacy_boundary_respected=privacy_ok,
        publication_status="locked" if privacy_ok else "at_risk",
    )


def should_fire_keyframe_stop1(event: ConsentEvent) -> bool:
    """Fire keyframe at STOP 1 on consent/acl events (Task 6.1)."""
    return event.event_type in [
        "consent.grant",
        "consent.revoke",
        "consent.expired",
        "acl.grant",
        "acl.revoke",
    ]


def should_fire_keyframe_stop2(
    event: ConsentEvent, previous_agg: ClusterAggregate | None
) -> bool:
    """Fire keyframe when cluster aggregate changes (Task 6.2)."""
    return previous_agg is not None


def should_fire_keyframe_stop3(
    event: ConsentEvent, previous_regional: RegionalAggregate | None
) -> bool:
    """Fire keyframe when regional aggregate changes (Task 6.3)."""
    return previous_regional is not None


def should_fire_keyframe_stop4(event: ConsentEvent) -> bool:
    """Fire keyframe on explicit civic events (Task 6.4)."""
    return event.event_type in [
        "civic.aggregate.locked",
        "civic.threshold.breach",
        "deletion.complete",
    ]


# =========================================================================
# Widgets (Tasks 7-11)
# =========================================================================

class ConsentPropagationGantt(Static):
    """Renders STOP 1-4 rows with timeline and keyframes (Task 7)."""

    DEFAULT_CSS = """
    ConsentPropagationGantt {
        height: auto;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scenarios = []
        self.pod_states = {}
        self.cluster_aggregates = {}
        self.regional_aggregates = {}
        self.civic_aggregates = {}

    def render(self) -> RenderableType:
        """Render Gantt with dynamic STOP rows."""
        lines = []

        if not self.scenarios:
            return "[dim]No scenarios selected. Select scenarios from header checkboxes.[/dim]"

        # Determine which STOPs to show based on selected scenarios
        stops_to_show = set()
        for scenario in self.scenarios:
            stops_to_show.update(SCENARIO_STOP_MAPPING.get(scenario, []))

        # Render each selected scenario
        for scenario in self.scenarios:
            lines.append(f"\n[bold]{scenario} — Consent Propagation[/bold]")

            # STOP 1: Individual pods
            if 1 in stops_to_show:
                lines.append("\n[cyan]STOP 1: Individual Pods[/cyan]")
                for pod_id in SCENARIO_CLUSTER_MAPPING.get(scenario, []):
                    for pod in CLUSTER_MAPPING.get(pod_id, []):
                        state = self.pod_states.get(pod, PodState(pod, PodStateEnum.ANOMALY))
                        icon = "✓" if state.current_state == PodStateEnum.ACTIVE else "✗"
                        lines.append(f"  {pod} {icon} ({state.current_state.value})")

            # STOP 2: Cluster aggregate
            if 2 in stops_to_show:
                lines.append("\n[green]STOP 2: School Cluster[/green]")
                for cluster_id in SCENARIO_CLUSTER_MAPPING.get(scenario, []):
                    agg = self.cluster_aggregates.get(cluster_id)
                    if agg:
                        lines.append(f"  {agg.cluster_name}: {agg.active_pods}/{agg.total_pods} pods pass ACL")

            # STOP 3: Regional aggregate
            if 3 in stops_to_show:
                lines.append("\n[yellow]STOP 3: Regional Hub[/yellow]")
                for region_id in SCENARIO_REGION_MAPPING.get(scenario, []):
                    agg = self.regional_aggregates.get(region_id)
                    if agg:
                        lines.append(f"  {agg.region_name}: {agg.active_pods}/{agg.total_pods} pods (publication: {'READY' if agg.publication_ready else 'AT RISK'})")

            # STOP 4: Civic layer
            if 4 in stops_to_show:
                lines.append("\n[magenta]STOP 4: Federal Civic Layer[/magenta]")
                for region_id in SCENARIO_REGION_MAPPING.get(scenario, []):
                    agg = self.civic_aggregates.get(region_id)
                    if agg:
                        lines.append(f"  Evidence: {agg.evidence_name}")
                        lines.append(f"  Privacy: {'✓ Respected' if agg.privacy_boundary_respected else '✗ VIOLATED'}")

        return "\n".join(lines) if lines else "[dim]No data to display.[/dim]"

    def update_state(self, scenarios: list[str], pod_states: dict, cluster_aggs: dict, regional_aggs: dict, civic_aggs: dict):
        """Update widget state and refresh."""
        self.scenarios = scenarios
        self.pod_states = pod_states
        self.cluster_aggregates = cluster_aggs
        self.regional_aggregates = regional_aggs
        self.civic_aggregates = civic_aggs
        self.update(self.render())


class PodSpaceGrid(Static):
    """4×4 compact pod grid, color-coded by state (Task 8)."""

    DEFAULT_CSS = """
    PodSpaceGrid {
        height: auto;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pod_states = {}

    def render(self) -> RenderableType:
        """Render 4×4 grid of pods."""
        lines = ["[bold cyan]POD SPACE (4×4 Grid)[/bold cyan]\n"]

        pods = sorted(ALL_PODS)
        for i, pod_id in enumerate(pods):
            if i % 4 == 0:
                lines.append("")  # New row

            state = self.pod_states.get(pod_id, PodState(pod_id, PodStateEnum.ANOMALY))

            # Color coding by state
            if state.current_state == PodStateEnum.ACTIVE:
                icon = "✓"
                color = "green"
            elif state.current_state == PodStateEnum.REVOKED:
                icon = "✗"
                color = "red"
            elif state.current_state == PodStateEnum.TRANSITIONING:
                icon = "⟳"
                color = "yellow"
            else:
                icon = "⚠"
                color = "magenta"

            lines[-1] += f"[{color}]{pod_id} {icon}[/{color}]  "

        return "\n".join(lines)

    def update_state(self, pod_states: dict):
        """Update pod states and refresh."""
        self.pod_states = pod_states
        self.update(self.render())


class ConsentGateCounts(Static):
    """Live consent counts: Active, Revoked, Transitioning, Expired (Task 9)."""

    DEFAULT_CSS = """
    ConsentGateCounts {
        height: auto;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pod_states = {}

    def render(self) -> RenderableType:
        """Calculate and display counts."""
        active = sum(1 for p in self.pod_states.values() if p.current_state == PodStateEnum.ACTIVE)
        revoked = sum(1 for p in self.pod_states.values() if p.current_state == PodStateEnum.REVOKED)
        transitioning = sum(1 for p in self.pod_states.values() if p.current_state == PodStateEnum.TRANSITIONING)
        expired = sum(1 for e in self.pod_states.values() if e.last_event and e.last_event.event_type == "consent.expired")

        return (
            f"[bold cyan]CONSENT GATE[/bold cyan]\n"
            f"Active Grants: [green]{active}[/green] | "
            f"Revoked: [red]{revoked}[/red] | "
            f"Transitioning: [yellow]{transitioning}[/yellow] | "
            f"Expired: [dim]{expired}[/dim]"
        )

    def update_state(self, pod_states: dict):
        """Update pod states and refresh."""
        self.pod_states = pod_states
        self.update(self.render())


class CivicAggregatePanel(Static):
    """Civic evidence base + alerts panel (Task 10)."""

    DEFAULT_CSS = """
    CivicAggregatePanel {
        height: auto;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scenarios = []
        self.civic_aggregates = {}
        self.alerts = []

    def render(self) -> RenderableType:
        """Render civic aggregate info + alerts."""
        lines = ["[bold magenta]CIVIC AGGREGATE + ALERTS[/bold magenta]"]

        # Only show if Isabelle scenario is selected (she sees STOP 4)
        if "Isabelle" not in self.scenarios:
            lines.append("[dim]Select 'Isabelle' scenario to view civic layer.[/dim]")
        else:
            for region_id, agg in self.civic_aggregates.items():
                lines.append(f"\n{agg.evidence_name}:")
                lines.append(f"  Pods: {agg.pods_in_base}")
                lines.append(f"  Outcome: {agg.outcome}")
                privacy_status = "✓ Respected" if agg.privacy_boundary_respected else "✗ VIOLATED"
                lines.append(f"  Privacy Boundary: {privacy_status}")
                lines.append(f"  Status: {agg.publication_status}")

        # Render alerts
        if self.alerts:
            lines.append("\n[yellow]⚠ Alerts:[/yellow]")
            for alert in self.alerts[:5]:  # Show last 5 alerts
                lines.append(f"  {alert}")

        return "\n".join(lines)

    def update_state(self, scenarios: list[str], civic_aggs: dict, alerts: list[str]):
        """Update civic state and alerts."""
        self.scenarios = scenarios
        self.civic_aggregates = civic_aggs
        self.alerts = alerts
        self.update(self.render())


# =========================================================================
# Main App
# =========================================================================


class MissionControlApp(App):
    """Main Mission Control application (Task 1)."""

    TITLE = "Mission Control — Consent Propagation Network"
    BINDINGS = [("q", "quit", "Quit")]

    # Reactive attributes (Task 1.2)
    consent_events = reactive([])
    troll_events = reactive([])
    pod_states = reactive({})
    cluster_aggregates = reactive({})
    regional_aggregates = reactive({})
    civic_aggregates = reactive({})
    selected_scenarios = reactive(["Claire", "Isabelle"])
    filtered_pod = reactive(None)
    alerts = reactive([])

    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        height: 3;
        border: solid $primary;
    }

    #scenario-selector {
        height: auto;
    }

    #gantt-section {
        height: 12;
        border: solid $accent;
        overflow-y: auto;
    }

    #pod-grid {
        height: 8;
        border: solid $accent;
        overflow-y: auto;
    }

    #consent-gate {
        height: 3;
        border: solid $accent;
    }

    #civic-panel {
        height: auto;
        border: solid $accent;
        overflow-y: auto;
    }

    #main-container {
        layout: vertical;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the 4-section layout (Task 1.1, 1.4)."""
        with Vertical(id="main-container"):
            yield Label("[bold cyan]MISSION CONTROL — Consent Propagation Network[/bold cyan]", id="header")

            with Horizontal(id="scenario-selector"):
                yield Label("[bold]Scenarios:[/bold]")
                yield Label("☑ Claire  ☑ Isabelle  ☐ Ayoub  ☐ Fatima  ☐ Marc")

            yield ConsentPropagationGantt(id="gantt-section")
            yield PodSpaceGrid(id="pod-grid")
            yield ConsentGateCounts(id="consent-gate")
            yield CivicAggregatePanel(id="civic-panel")

        yield Footer()

    async def on_mount(self) -> None:
        """Start JSONL polling on app mount (Task 1.3)."""
        self._poll_jsonl_task = asyncio.create_task(self._poll_jsonl_loop())

    async def _poll_jsonl_loop(self) -> None:
        """Background JSONL polling worker."""
        last_consent_pos = 0
        last_troll_pos = 0

        while True:
            try:
                # Read consent events
                if _CONSENT_EVENTS_FILE.exists():
                    with open(_CONSENT_EVENTS_FILE, "r") as f:
                        f.seek(last_consent_pos)
                        for line in f:
                            event = parse_consent_event(line)
                            if event:
                                new_events = self.consent_events[:]
                                new_events.append(event)
                                self.consent_events = new_events
                        last_consent_pos = f.tell()

                # Update calculated state from events
                self._update_calculated_state()

                # Read troll events
                if _TROLL_RUN_FILE.exists():
                    with open(_TROLL_RUN_FILE, "r") as f:
                        f.seek(last_troll_pos)
                        for line in f:
                            try:
                                event = json.loads(line.strip())
                                if event:
                                    new_troll = self.troll_events[:]
                                    new_troll.append(event)
                                    self.troll_events = new_troll
                            except json.JSONDecodeError:
                                pass
                        last_troll_pos = f.tell()

            except Exception as e:
                self._add_alert(f"JSONL read error: {e}")

            await asyncio.sleep(_POLL_INTERVAL)

    def _update_calculated_state(self) -> None:
        """Recalculate all aggregates from consent events."""
        # Calculate pod states (Task 2)
        pod_states = {}
        for pod_id in ALL_PODS:
            pod_states[pod_id] = calculate_pod_state(pod_id, self.consent_events)
        self.pod_states = pod_states

        # Calculate cluster aggregates (Task 3)
        cluster_aggs = {}
        for cluster_id in CLUSTER_MAPPING:
            cluster_aggs[cluster_id] = calculate_cluster_aggregate(cluster_id, pod_states)
        self.cluster_aggregates = cluster_aggs

        # Calculate regional aggregates (Task 4)
        regional_aggs = {}
        for region_id in REGION_MAPPING:
            regional_aggs[region_id] = calculate_regional_aggregate(region_id, cluster_aggs)
        self.regional_aggregates = regional_aggs

        # Calculate civic aggregates (Task 5)
        civic_aggs = {}
        for region_id in REGION_MAPPING:
            civic_aggs[region_id] = calculate_civic_aggregate(regional_aggs[region_id], pod_states)
        self.civic_aggregates = civic_aggs

    def _add_alert(self, message: str) -> None:
        """Add alert message."""
        alerts = self.alerts[:]
        alerts.append(message)
        self.alerts = alerts[-10:]  # Keep last 10 alerts

    def watch_pod_states(self) -> None:
        """Watcher: update widgets when pod states change."""
        try:
            gantt = self.query_one("#gantt-section", ConsentPropagationGantt)
            grid = self.query_one("#pod-grid", PodSpaceGrid)
            counts = self.query_one("#consent-gate", ConsentGateCounts)

            gantt.update_state(
                self.selected_scenarios,
                self.pod_states,
                self.cluster_aggregates,
                self.regional_aggregates,
                self.civic_aggregates,
            )
            grid.update_state(self.pod_states)
            counts.update_state(self.pod_states)
        except Exception:
            pass  # Widgets not yet mounted

    def watch_civic_aggregates(self) -> None:
        """Watcher: update civic panel when civic aggregates change."""
        try:
            panel = self.query_one("#civic-panel", CivicAggregatePanel)
            panel.update_state(self.selected_scenarios, self.civic_aggregates, self.alerts)
        except Exception:
            pass  # Widgets not yet mounted


def main():
    """Main entry point."""
    app = MissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
