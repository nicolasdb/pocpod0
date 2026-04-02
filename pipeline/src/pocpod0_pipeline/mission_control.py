"""Mission Control — Operations Control Room for pocpod0.

An offshore-operations-style TUI: default state is "all green."
When something turns red the operator sees: what, where, why, cascade impact.

Operator can answer 5 questions in <5 seconds each:
  1. Are all backend services alive?           → SERVICE HEALTH widget
  2. Are security boundaries holding?          → TROLL ALARM PANEL widget
  3. What's each pod's consent state?          → POD GRID widget (8 real pods)
  4. What's the overall consent distribution?  → CONSENT GATE widget
  5. What just happened?                       → EVENT LOG widget

Bonus: select a pod → CASCADE PREDICTOR shows downstream impact.

Usage (from repo root, venv active):
    pocpod0-mission-control
    # or: python -m pocpod0_pipeline.mission_control

Data sources:
    data/consent-events.jsonl  — consent/acl events (polled every 2 s)
    data/troll-run.jsonl       — adversarial test results (polled every 2 s)

Architecture:
    - Textual reactive app with background workers for JSONL polling
    - Single-screen layout (no tabs — operator sees everything at once)
    - 6 isolated widget classes, each with one data source and one render method
    - Pod click → selected_pod reactive → Cascade Predictor updates

Note (distrobox): use distrobox-host-exec to reach podman containers /
    localhost ports when running from inside a distrobox environment.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import httpx
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, Static


# =========================================================================
# Configuration
# =========================================================================

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_CONSENT_EVENTS_FILE = _REPO_ROOT / "data" / "consent-events.jsonl"
_TROLL_RUN_FILE = _REPO_ROOT / "data" / "troll-run.jsonl"

_POLL_INTERVAL = 2.0          # seconds
_MAX_EVENTS = 500             # cap in-memory event lists
_EVENT_LOG_LEN = 20           # events to show in Event Log widget
_HEALTH_POLL_INTERVAL = 5.0  # health checks less frequent

# Real CSS pod identifiers (8 pods including fatima parent pod).
# fatima is the co-consent authority over fatima-child-1 / fatima-child-2.
POD_SLUGS: list[str] = [
    "ayoub",
    "claire",
    "claire-student-1",
    "claire-student-2",
    "fatima",
    "fatima-child-1",
    "fatima-child-2",
    "school-community",
]

# Downstream cascade relationships: pod → [pods it affects if removed]
# Used by CascadePredictorWidget.
CASCADE_MAP: dict[str, list[str]] = {
    "fatima": ["fatima-child-1", "fatima-child-2"],  # co-consent authority
    "claire": ["claire-student-1", "claire-student-2"],  # classroom delegation
}

# Service health endpoints.  Override via env vars if needed.
HEALTH_ENDPOINTS: dict[str, str] = {
    "CSS": os.environ.get("CSS_BASE_URL", "http://localhost:3000") + "/",
    "Oxigraph": os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878") + "/",
    "Qdrant": os.environ.get("QDRANT_BASE_URL", "http://localhost:6333") + "/",
}

# Minimum consenting pods for aggregate to be "publication ready".
_MIN_PODS_FOR_PUBLICATION = 6


# =========================================================================
# State Models
# =========================================================================

class PodStateEnum(str, Enum):
    """Pod consent state."""
    ACTIVE = "active"
    REVOKED = "revoked"
    TRANSITIONING = "transitioning"
    NO_CONSENT = "no_consent"   # no events yet — not an error
    ANOMALY = "anomaly"         # unknown/error state


@dataclass
class ConsentEvent:
    """Parsed consent event from JSONL."""
    timestamp: str
    event_type: str
    pod: str | None = None
    grantee_webid: str | None = None
    scope: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class PodState:
    """Consent status for a single pod."""
    pod_id: str
    current_state: PodStateEnum
    last_event: ConsentEvent | None = None
    event_count: int = 0


@dataclass
class TrollCategoryResult:
    """Aggregated results for one troll attack category."""
    category: str
    passed: int = 0
    partial: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.partial + self.failed

    @property
    def severity(self) -> str:
        if self.total == 0:
            return "unknown"
        if self.failed == 0 and self.partial == 0:
            return "green"
        if self.failed == 0:
            return "yellow"
        return "red"


# =========================================================================
# Core Business Logic
# =========================================================================

def parse_consent_event(line: str) -> ConsentEvent | None:
    """Parse a JSONL line into a ConsentEvent. Returns None on parse error."""
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
            extra=data,
        )
    except json.JSONDecodeError:
        return None


def _parse_ts(ts: str) -> datetime:
    """Parse ISO 8601 timestamp robustly (tolerates Z suffix)."""
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def calculate_pod_state(pod_id: str, events: list[ConsentEvent]) -> PodState:
    """Determine pod's current consent state from event history.

    A pod with no events is NO_CONSENT (waiting), not ANOMALY.
    """
    pod_events = [e for e in events if e.pod == pod_id]
    if not pod_events:
        return PodState(pod_id=pod_id, current_state=PodStateEnum.NO_CONSENT, event_count=0)

    try:
        pod_events.sort(key=lambda e: _parse_ts(e.timestamp))
    except (ValueError, TypeError):
        pod_events.sort(key=lambda e: e.timestamp)
    last = pod_events[-1]

    if last.event_type in ("consent.revoke", "consent.expired"):
        state = PodStateEnum.REVOKED
    elif last.event_type == "acl.governance.transition":
        state = PodStateEnum.TRANSITIONING
    elif last.event_type in ("consent.grant", "acl.grant"):
        state = PodStateEnum.ACTIVE
    else:
        state = PodStateEnum.ANOMALY

    return PodState(pod_id=pod_id, current_state=state, last_event=last, event_count=len(pod_events))


def build_pod_states(events: list[ConsentEvent]) -> dict[str, PodState]:
    """Compute current state for every known pod."""
    return {pod: calculate_pod_state(pod, events) for pod in POD_SLUGS}


def compute_cascade_impact(
    selected_pod: str,
    pod_states: dict[str, PodState],
) -> str:
    """Describe downstream impact if selected_pod were to revoke consent.

    Shows how the school aggregate would change.
    """
    if selected_pod not in POD_SLUGS:
        return "No pod selected — click a pod in the grid."

    current_state = pod_states.get(selected_pod)
    if current_state is None:
        return f"Unknown pod: {selected_pod}"

    state_label = current_state.current_state.value.replace("_", " ")

    # Count currently active pods (excluding the selected one)
    active_without = sum(
        1 for p, s in pod_states.items()
        if p != selected_pod and s.current_state == PodStateEnum.ACTIVE
    )
    total = len(POD_SLUGS)

    # Direct cascade: pods this one controls
    cascaded = CASCADE_MAP.get(selected_pod, [])
    cascaded_active = [
        p for p in cascaded
        if pod_states.get(p, PodState(p, PodStateEnum.NO_CONSENT)).current_state == PodStateEnum.ACTIVE
    ]

    after_revoke = active_without - len(cascaded_active)
    threshold_met = after_revoke >= _MIN_PODS_FOR_PUBLICATION

    lines = [
        f"Selected: [bold]{selected_pod}[/bold] (state: {state_label})",
        "",
        "If this pod revokes consent:",
        f"  School: {active_without}/{total - 1} would remain consented",
    ]
    if cascaded_active:
        lines.append(f"  Also removes: {', '.join(cascaded_active)}")
        lines.append(f"  Net active: {after_revoke}/{total}")
    threshold_str = "[green]MET ✓[/green]" if threshold_met else "[red]NOT MET ✗[/red]"
    lines.append(f"  Publication threshold: {threshold_str}")

    return "\n".join(lines)


def aggregate_troll_results(lines: list[str]) -> dict[str, TrollCategoryResult]:
    """Parse troll JSONL lines and aggregate by category.

    Uses troll.probe.done events (result field) to compute counts.
    Falls back to troll.category.done summary events if probes absent.
    """
    # Prefer troll.category.done summary (authoritative)
    from_summary: dict[str, TrollCategoryResult] = {}
    from_probes: dict[str, TrollCategoryResult] = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = data.get("event_type", "")
        category = data.get("category", "unknown")

        if event_type == "troll.category.done":
            from_summary[category] = TrollCategoryResult(
                category=category,
                passed=data.get("passed", 0),
                partial=data.get("partial", 0),
                failed=data.get("failed", 0),
            )
        elif event_type == "troll.probe.done":
            result = data.get("result", "unknown")
            if category not in from_probes:
                from_probes[category] = TrollCategoryResult(category=category)
            r = from_probes[category]
            if result == "pass":
                r.passed += 1
            elif result == "partial":
                r.partial += 1
            elif result == "fail":
                r.failed += 1

    # troll.category.done takes precedence; fall back to probe aggregation
    return from_summary if from_summary else from_probes


# =========================================================================
# Widgets
# =========================================================================

_STATE_ICON: dict[PodStateEnum, tuple[str, str]] = {
    PodStateEnum.ACTIVE:      ("✓", "green"),
    PodStateEnum.REVOKED:     ("✗", "red"),
    PodStateEnum.TRANSITIONING: ("⟳", "yellow"),
    PodStateEnum.NO_CONSENT:  ("·", "red"),
    PodStateEnum.ANOMALY:     ("⚠", "magenta"),
}

_SEVERITY_COLOR: dict[str, str] = {
    "green": "green",
    "yellow": "yellow",
    "red": "red",
    "unknown": "dim",
}


class ServiceHealthWidget(Static):
    """Widget 1: Are all backend services alive?

    Polls HTTP health endpoints every _HEALTH_POLL_INTERVAL seconds.
    Answers: CSS ✓/✗  Oxigraph ✓/✗  Qdrant ✓/✗
    """

    DEFAULT_CSS = """
    ServiceHealthWidget {
        border: solid $accent;
        height: 6;
        padding: 0 1;
    }
    """

    # Map service name → True (up) / False (down) / None (unknown)
    _statuses: reactive[dict[str, bool | None]] = reactive(dict)

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[bold cyan]SERVICE HEALTH[/bold cyan]\n\n"
            "  [dim]? CSS[/dim]\n  [dim]? Oxigraph[/dim]\n  [dim]? Qdrant[/dim]",
            **kwargs,
        )
        self._statuses = {name: None for name in HEALTH_ENDPOINTS}

    def on_mount(self) -> None:
        self.run_worker(self._poll_health(), exclusive=False)

    async def _poll_health(self) -> None:
        async with httpx.AsyncClient(timeout=3.0) as client:
            while True:
                new_statuses: dict[str, bool | None] = {}
                for name, url in HEALTH_ENDPOINTS.items():
                    try:
                        resp = await client.get(url)
                        new_statuses[name] = resp.status_code < 500
                    except Exception:
                        new_statuses[name] = False
                self._statuses = new_statuses
                self._refresh_display()
                await asyncio.sleep(_HEALTH_POLL_INTERVAL)

    def _refresh_display(self) -> None:
        lines = ["[bold cyan]SERVICE HEALTH[/bold cyan]", ""]
        for name, up in self._statuses.items():
            if up is None:
                icon, color = "?", "dim"
            elif up:
                icon, color = "✓", "green"
            else:
                icon, color = "✗", "red"
            lines.append(f"  [{color}]{icon}[/{color}] {name}")
        self.update("\n".join(lines))


class TrollAlarmWidget(Static):
    """Widget 2: Are security boundaries holding?

    Shows one row per attack category with pass/partial/fail counts
    and color severity (green = all pass, yellow = some partial, red = any fail).
    """

    DEFAULT_CSS = """
    TrollAlarmWidget {
        border: solid $accent;
        height: 6;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[bold cyan]TROLL ALARM PANEL[/bold cyan]\n\n  [dim]Loading...[/dim]",
            **kwargs,
        )
        self._results: dict[str, TrollCategoryResult] = {}

    def update_results(self, results: dict[str, TrollCategoryResult]) -> None:
        self._results = results
        self._refresh_display()

    def _refresh_display(self) -> None:
        lines = ["[bold cyan]TROLL ALARM PANEL[/bold cyan]", ""]
        if not self._results:
            lines.append("  [dim]No troll run data.[/dim]")
        else:
            for name, r in sorted(self._results.items()):
                color = _SEVERITY_COLOR[r.severity]
                icon = "✓" if r.severity == "green" else ("⚠" if r.severity == "yellow" else "✗")
                lines.append(
                    f"  [{color}]{icon}[/{color}] {name:<22} "
                    f"[green]{r.passed}p[/green] "
                    f"[yellow]{r.partial}w[/yellow] "
                    f"[red]{r.failed}f[/red]"
                    f" / {r.total}"
                )
        self.update("\n".join(lines))


class PodGridWidget(Vertical):
    """Widget 3: What's each pod's consent state?

    Shows 8 real CSS pods as clickable buttons, color-coded:
      green  = active (consent granted)
      red    = revoked or no consent
      yellow = transitioning
      magenta = anomaly
    """

    DEFAULT_CSS = """
    PodGridWidget {
        border: solid $accent;
        height: auto;
        padding: 0 1;
    }
    PodGridWidget Horizontal {
        height: 3;
    }
    PodGridWidget Button {
        min-width: 15;
        height: 3;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[bold cyan]POD GRID[/bold cyan]")
        # 2 rows of 4 pods
        for row_start in range(0, len(POD_SLUGS), 4):
            with Horizontal():
                for pod_id in POD_SLUGS[row_start : row_start + 4]:
                    safe = pod_id.replace("-", "_")
                    yield Button(
                        f"{pod_id[:18]:18} ·",
                        id=f"pod-btn-{safe}",
                        variant="default",
                    )

    def update_state(self, pod_states: dict[str, PodState]) -> None:
        variant_map: dict[PodStateEnum, str] = {
            PodStateEnum.ACTIVE: "success",
            PodStateEnum.REVOKED: "error",
            PodStateEnum.TRANSITIONING: "warning",
            PodStateEnum.NO_CONSENT: "error",
            PodStateEnum.ANOMALY: "default",
        }
        for pod_id in POD_SLUGS:
            safe = pod_id.replace("-", "_")
            try:
                btn = self.query_one(f"#pod-btn-{safe}", Button)
                ps = pod_states.get(pod_id, PodState(pod_id, PodStateEnum.NO_CONSENT))
                icon, _ = _STATE_ICON[ps.current_state]
                btn.label = f"{pod_id[:18]:18} {icon}"
                btn.variant = variant_map[ps.current_state]
            except NoMatches:
                pass


class CascadePredictorWidget(Static):
    """Widget 4: What breaks if pod X revokes?

    Updates when a pod is selected in PodGridWidget.
    Shows downstream impact: which dependents lose consent, whether
    the school aggregate stays above the publication threshold.
    """

    DEFAULT_CSS = """
    CascadePredictorWidget {
        border: solid $accent;
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[bold cyan]CASCADE PREDICTOR[/bold cyan]\n\n"
            "[dim]Click a pod in the grid to predict cascade impact.[/dim]",
            **kwargs,
        )
        self._pod_states: dict[str, PodState] = {}
        self._selected: str | None = None

    def update_state(
        self,
        pod_states: dict[str, PodState],
        selected_pod: str | None,
    ) -> None:
        self._pod_states = pod_states
        self._selected = selected_pod
        self._refresh_display()

    def _refresh_display(self) -> None:
        header = "[bold cyan]CASCADE PREDICTOR[/bold cyan]\n"
        if self._selected is None:
            self.update(header + "\n[dim]Click a pod in the grid to predict cascade impact.[/dim]")
            return
        impact = compute_cascade_impact(self._selected, self._pod_states)
        self.update(header + "\n" + impact)


class ConsentGateWidget(Static):
    """Widget 5: Overall consent distribution.

    Counts: Active | No consent | Revoked | Transitioning
    """

    DEFAULT_CSS = """
    ConsentGateWidget {
        border: solid $accent;
        height: 4;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[bold cyan]CONSENT GATE[/bold cyan]\n\n[dim]Waiting for consent events...[/dim]",
            **kwargs,
        )
        self._pod_states: dict[str, PodState] = {}

    def update_state(self, pod_states: dict[str, PodState]) -> None:
        self._pod_states = pod_states
        self._refresh_display()

    def _refresh_display(self) -> None:
        ps = self._pod_states
        active = sum(1 for s in ps.values() if s.current_state == PodStateEnum.ACTIVE)
        no_consent = sum(1 for s in ps.values() if s.current_state == PodStateEnum.NO_CONSENT)
        revoked = sum(1 for s in ps.values() if s.current_state == PodStateEnum.REVOKED)
        transitioning = sum(1 for s in ps.values() if s.current_state == PodStateEnum.TRANSITIONING)
        anomaly = sum(1 for s in ps.values() if s.current_state == PodStateEnum.ANOMALY)
        total = len(POD_SLUGS)

        if not ps:
            self.update(
                "[bold cyan]CONSENT GATE[/bold cyan]\n\n"
                "[dim]Waiting for consent events...[/dim]"
            )
            return

        self.update(
            "[bold cyan]CONSENT GATE[/bold cyan]  [dim]— how many pods have consented?[/dim]\n\n"
            f"  [green]✓ Active: {active}[/green]"
            f"  [red]· No consent: {no_consent}[/red]"
            f"  [red]✗ Revoked: {revoked}[/red]"
            f"  [yellow]⟳ Transitioning: {transitioning}[/yellow]"
            f"  [magenta]⚠ Anomaly: {anomaly}[/magenta]"
            f"  [dim]/ {total} pods total[/dim]"
        )


class EventLogWidget(Static):
    """Widget 6: What just happened?

    Shows last _EVENT_LOG_LEN consent events, newest first.
    """

    DEFAULT_CSS = """
    EventLogWidget {
        border: solid $accent;
        height: 10;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            "[bold cyan]EVENT LOG[/bold cyan]\n\n[dim]  Waiting for consent events...[/dim]",
            **kwargs,
        )
        self._events: list[ConsentEvent] = []

    def update_events(self, events: list[ConsentEvent]) -> None:
        self._events = events
        self._refresh_display()

    def _refresh_display(self) -> None:
        lines = ["[bold cyan]EVENT LOG[/bold cyan]  (newest first)"]
        if not self._events:
            lines.append("")
            lines.append("[dim]  Waiting for consent events...[/dim]")
        else:
            # newest first
            for ev in reversed(self._events[-_EVENT_LOG_LEN:]):
                ts = ev.timestamp[:19] if len(ev.timestamp) >= 19 else ev.timestamp
                pod_str = f"[bold]{ev.pod}[/bold]" if ev.pod else "[dim]—[/dim]"
                color = "green" if "grant" in ev.event_type else (
                    "red" if "revok" in ev.event_type or "expir" in ev.event_type else "dim"
                )
                lines.append(
                    f"  [{color}]{ev.event_type}[/{color}]"
                    f"  {pod_str}"
                    f"  [dim]{ts}[/dim]"
                )
        self.update("\n".join(lines))


# =========================================================================
# Main App
# =========================================================================

class MissionControlApp(App):
    """pocpod0 Mission Control — single-screen operations control room."""

    TITLE = "pocpod0 Mission Control"
    SUB_TITLE = "Operations Control Room"

    CSS = """
    Screen {
        layout: vertical;
    }
    #top-row {
        height: 8;
        layout: horizontal;
    }
    #top-row ServiceHealthWidget {
        width: 1fr;
    }
    #top-row TrollAlarmWidget {
        width: 2fr;
    }
    #mid-row {
        height: auto;
        layout: horizontal;
    }
    #mid-row PodGridWidget {
        width: 1fr;
    }
    #mid-row CascadePredictorWidget {
        width: 1fr;
    }
    ConsentGateWidget {
        width: 100%;
    }
    EventLogWidget {
        width: 100%;
    }
    """

    # Reactive state
    _consent_events: reactive[list[ConsentEvent]] = reactive(list)
    _troll_lines: reactive[list[str]] = reactive(list)
    _pod_states: reactive[dict[str, PodState]] = reactive(dict)
    _troll_results: reactive[dict[str, TrollCategoryResult]] = reactive(dict)
    _selected_pod: reactive[str | None] = reactive(None)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._consent_events = []
        self._troll_lines = []
        self._pod_states = {}
        self._troll_results = {}
        self._selected_pod = None
        self._consent_seek = 0
        self._troll_seek = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-row"):
            yield ServiceHealthWidget(id="service-health")
            yield TrollAlarmWidget(id="troll-alarm")
        with Horizontal(id="mid-row"):
            yield PodGridWidget(id="pod-grid")
            yield CascadePredictorWidget(id="cascade-predictor")
        yield ConsentGateWidget(id="consent-gate")
        yield EventLogWidget(id="event-log")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._poll_jsonl_task(), exclusive=False, name="jsonl-poller")

    async def _poll_jsonl_task(self) -> None:
        """Background worker: poll both JSONL files every _POLL_INTERVAL seconds."""
        while True:
            await self._read_consent_events()
            await self._read_troll_events()
            await asyncio.sleep(_POLL_INTERVAL)

    async def _read_consent_events(self) -> None:
        """Read new lines from consent-events.jsonl since last seek position."""
        if not _CONSENT_EVENTS_FILE.exists():
            return
        try:
            with _CONSENT_EVENTS_FILE.open() as f:
                size = _CONSENT_EVENTS_FILE.stat().st_size
                # P13: detect truncation (demo reset via compose down -v)
                if self._consent_seek > size:
                    self._consent_seek = 0
                    self._consent_events = []
                f.seek(self._consent_seek)
                new_lines = f.readlines()
                self._consent_seek = f.tell()

            new_events: list[ConsentEvent] = []
            for line in new_lines:
                ev = parse_consent_event(line)
                if ev and ev.event_type.startswith("consent.") or (
                    ev and ev.event_type.startswith("acl.")
                ):
                    new_events.append(ev)

            if new_events:
                all_events = self._consent_events + new_events
                # Cap to prevent unbounded growth
                if len(all_events) > _MAX_EVENTS:
                    all_events = all_events[-_MAX_EVENTS:]
                self._consent_events = all_events
                self._pod_states = build_pod_states(self._consent_events)
                self._refresh_consent_widgets()
        except OSError:
            pass

    async def _read_troll_events(self) -> None:
        """Read new lines from troll-run.jsonl since last seek position."""
        if not _TROLL_RUN_FILE.exists():
            return
        try:
            with _TROLL_RUN_FILE.open() as f:
                size = _TROLL_RUN_FILE.stat().st_size
                if self._troll_seek > size:
                    self._troll_seek = 0
                    self._troll_lines = []
                f.seek(self._troll_seek)
                new_lines = f.readlines()
                self._troll_seek = f.tell()

            if new_lines:
                all_lines = self._troll_lines + new_lines
                if len(all_lines) > _MAX_EVENTS:
                    all_lines = all_lines[-_MAX_EVENTS:]
                self._troll_lines = all_lines
                self._troll_results = aggregate_troll_results(self._troll_lines)
                self._refresh_troll_widget()
        except OSError:
            pass

    def _refresh_consent_widgets(self) -> None:
        """Push updated pod state to consent-related widgets."""
        try:
            self.query_one("#pod-grid", PodGridWidget).update_state(self._pod_states)
            self.query_one("#cascade-predictor", CascadePredictorWidget).update_state(
                self._pod_states, self._selected_pod
            )
            self.query_one("#consent-gate", ConsentGateWidget).update_state(self._pod_states)
            self.query_one("#event-log", EventLogWidget).update_events(self._consent_events)
        except (NoMatches, Exception):
            pass

    def _refresh_troll_widget(self) -> None:
        """Push troll results to the alarm panel."""
        try:
            self.query_one("#troll-alarm", TrollAlarmWidget).update_results(self._troll_results)
        except (NoMatches, Exception):
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle pod grid button clicks → update selected_pod + cascade predictor."""
        btn_id: str = event.button.id or ""
        if not btn_id.startswith("pod-btn-"):
            return
        safe = btn_id[len("pod-btn-"):]
        pod_id = safe.replace("_", "-")
        # Toggle: clicking the same pod again deselects
        if self._selected_pod == pod_id:
            self._selected_pod = None
        else:
            self._selected_pod = pod_id
        try:
            self.query_one("#cascade-predictor", CascadePredictorWidget).update_state(
                self._pod_states, self._selected_pod
            )
        except NoMatches:
            pass


def main() -> None:
    """Entry point: pocpod0-mission-control."""
    app = MissionControlApp()
    app.run()


if __name__ == "__main__":
    main()
