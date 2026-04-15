"""Live pipeline dashboard — reads data/pipeline-run.jsonl and renders a rich.live table.

Usage (from repo root, venv active):
    pocpod0-dashboard
    # or: python -m pocpod0_pipeline.pipeline_dashboard

Run in a separate terminal while the pipeline is executing.
Auto-exits when pipeline.done or stage.failed is detected.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_JSONL_LOG = Path(__file__).parent.parent.parent.parent / "data" / "pipeline-run.jsonl"
_PIPELINE_LOG = Path(__file__).parent.parent.parent.parent / "data" / "pipeline.log"
_POLL_INTERVAL = 0.5  # seconds

# Maps log event name → (stage_name, role, detail_key)
# role "total":      set total from details[detail_key]
# role "done":       increment done (by details[detail_key] if set, else 1)
# role "discovery":  show "discovering…" label until total is known
_PROGRESS_EVENTS: dict[str, tuple[str, str, str | None]] = {
    "ingest.statements.loaded":        ("ingest",      "total",     "total"),
    "ingest.statement.stored":         ("ingest",      "done",      None),
    "load_graph.discovery.start":      ("load-graph",  "discovery", None),
    "load_graph.resources.discovered": ("load-graph",  "total",     "total"),
    "load_graph.resource.loaded":      ("load-graph",  "done",      None),
    "embed.discovery.start":           ("embed",       "discovery", None),
    "embed.extract":                   ("embed",       "total",     "chunk_count"),
    "embed.qdrant_upsert":             ("embed",       "done",      "point_count"),
}

OXIGRAPH_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")
CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

# Load .env from repo root if present
_env_file = Path(__file__).parent.parent.parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Re-read after .env load
OXIGRAPH_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")
CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Service health
# ---------------------------------------------------------------------------

SERVICES = [
    ("CSS", CSS_BASE_URL + "/"),
    ("Oxigraph", OXIGRAPH_URL + "/"),
    ("Qdrant", QDRANT_URL + "/healthz"),
]


def _check_service(url: str) -> bool:
    try:
        resp = httpx.get(url, timeout=3)
        return resp.status_code < 500
    except Exception:
        return False


def _health_row() -> dict[str, bool]:
    return {name: _check_service(url) for name, url in SERVICES}


# ---------------------------------------------------------------------------
# JSONL reading
# ---------------------------------------------------------------------------

def _read_new_lines(f) -> list[dict]:
    events = []
    for raw in f:
        raw = raw.strip()
        if raw:
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
    return events


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

STATUS_STYLE = {
    "pending": "dim",
    "running": "bold yellow",
    "done": "bold green",
    "failed": "bold red",
}

STATUS_ICON = {
    "pending": "○",
    "running": "⟳",
    "done": "✓",
    "failed": "✗",
}


def _progress_bar(done: int, total: int, width: int = 16) -> str:
    """Render a compact ASCII progress bar: ████░░░░ 45/120"""
    frac = min(done / total, 1.0) if total > 0 else 0.0
    filled = round(frac * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(frac * 100)
    return f"{bar} {done}/{total} ({pct}%)"


def _build_table(
    stage_order: list[str],
    stage_status: dict[str, str],
    stage_elapsed: dict[str, float],
    stage_start_ts: dict[str, float],
    stage_detail: dict[str, str],
    stage_progress: dict[str, tuple[int, int]],
    health: dict[str, bool],
    pipeline_start_ts: float,
    total_elapsed: float | None,
) -> Table:
    now = time.time()

    table = Table(title="pocpod0 Pipeline Dashboard", show_header=True, header_style="bold cyan")
    table.add_column("Stage", style="white", min_width=20)
    table.add_column("Progress", min_width=32)
    table.add_column("Status", justify="center", min_width=10)
    table.add_column("Elapsed", justify="right", min_width=8)

    for name in stage_order:
        status = stage_status.get(name, "pending")
        style = STATUS_STYLE.get(status, "")
        icon = STATUS_ICON.get(status, "?")

        if status == "running" and name in stage_start_ts:
            elapsed_s = now - stage_start_ts[name]
            elapsed_str = f"{elapsed_s:.1f}s"
        elif name in stage_elapsed:
            elapsed_str = f"{stage_elapsed[name]:.1f}s"
        else:
            elapsed_str = "—"

        detail = stage_detail.get(name, "")
        label = f"{name}  [dim]{detail}[/dim]" if detail else name

        prog_text = ""
        if name in stage_progress:
            done, total = stage_progress[name]
            if total > 0:
                bar = _progress_bar(done, total)
                prog_style = "green" if status == "done" else "yellow"
                prog_text = f"[{prog_style}]{bar}[/{prog_style}]"

        table.add_row(label, prog_text, Text(f"{icon} {status}", style=style), elapsed_str)

    # Separator + total elapsed
    if total_elapsed is not None:
        total_str = f"{total_elapsed:.1f}s"
    elif pipeline_start_ts:
        total_str = f"{now - pipeline_start_ts:.1f}s (running)"
    else:
        total_str = "waiting…"

    table.add_section()
    table.add_row("[bold]TOTAL[/bold]", "", total_str)

    # Service health rows
    table.add_section()
    for svc, up in health.items():
        icon = "✓" if up else "✗"
        style = "green" if up else "red"
        table.add_row(f"  {svc}", Text(f"{icon} {'up' if up else 'down'}", style=style), "")

    return table


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    console = Console()

    # Resolve JSONL path from CWD (handles invocation from repo root or pipeline/)
    jsonl_path = Path("data/pipeline-run.jsonl")
    if not jsonl_path.parent.exists():
        # Try relative to this file (dev invocation)
        jsonl_path = _JSONL_LOG

    console.print(f"[cyan]Watching:[/cyan] {jsonl_path}")
    console.print("[dim]Waiting for pipeline to start... (Ctrl+C to quit)[/dim]\n")

    # Initial service health check
    health = _health_row()

    stage_order: list[str] = []
    stage_status: dict[str, str] = {}
    stage_elapsed: dict[str, float] = {}
    stage_start_ts: dict[str, float] = {}
    stage_detail: dict[str, str] = {}
    stage_progress: dict[str, tuple[int, int]] = {}  # stage → (done, total)
    pipeline_start_ts: float = 0.0
    pipeline_done = False
    total_elapsed: float | None = None

    # Wait for JSONL file to exist
    while not jsonl_path.exists():
        time.sleep(_POLL_INTERVAL)

    log_path = Path("data/pipeline.log")
    if not log_path.parent.exists():
        log_path = _PIPELINE_LOG

    with Live(console=console, refresh_per_second=4, screen=False) as live:
        log_path.touch()  # create if not yet present
        with open(jsonl_path) as f, open(log_path, "a+") as lf:
            f.seek(0, 2)   # start at end — only watch new events, not previous runs
            lf.seek(0, 2)  # start at end — only tail new lines
            while True:
                # Read progress events from pipeline.log
                for raw in lf:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        ev = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    ename = ev.get("event", "")
                    if ename in _PROGRESS_EVENTS:
                        stage, role, detail_key = _PROGRESS_EVENTS[ename]
                        details = ev.get("details", {})
                        done, total = stage_progress.get(stage, (0, 0))
                        if role == "discovery":
                            stage_detail[stage] = "discovering…"
                        elif role == "total":
                            total = details.get(detail_key, 0) if detail_key else 0
                            stage_detail.pop(stage, None)
                        elif role == "done":
                            increment = details.get(detail_key, 1) if detail_key else 1
                            done += increment
                        stage_progress[stage] = (done, total)

                events = _read_new_lines(f)
                for ev in events:
                    etype = ev.get("event_type", "")

                    if etype == "pipeline.wipe.start":
                        stage_order = ["wipe"]
                        stage_status["wipe"] = "running"
                        stage_start_ts["wipe"] = ev.get("timestamp", time.time())
                        pipeline_start_ts = stage_start_ts["wipe"]

                    elif etype == "pipeline.wipe.progress":
                        done = ev.get("pods_done", 0)
                        total = ev.get("pods_total", 0)
                        pod = ev.get("pod", "")
                        stage_detail["wipe"] = f"{pod} ({done}/{total} pods)"

                    elif etype == "pipeline.wipe.done":
                        stage_status["wipe"] = "done"
                        if "wipe" in stage_start_ts:
                            stage_elapsed["wipe"] = ev.get("timestamp", time.time()) - stage_start_ts["wipe"]
                        stage_detail.pop("wipe", None)

                    elif etype == "pipeline.start":
                        stage_order = ev.get("stages", [])
                        stage_status = {s: "pending" for s in stage_order}
                        pipeline_start_ts = ev.get("timestamp", time.time())
                        # Re-check health at pipeline start
                        health = _health_row()

                    elif etype == "stage.start":
                        name = ev.get("stage", "")
                        stage_status[name] = "running"
                        stage_start_ts[name] = ev.get("timestamp", time.time())
                        if name not in stage_order:
                            stage_order.append(name)

                    elif etype == "stage.done":
                        name = ev.get("stage", "")
                        stage_status[name] = "done"
                        stage_elapsed[name] = ev.get("elapsed", 0.0)

                    elif etype == "stage.failed":
                        name = ev.get("stage", "")
                        stage_status[name] = "failed"
                        stage_elapsed[name] = ev.get("elapsed", 0.0)
                        pipeline_done = True

                    elif etype == "pipeline.done":
                        pipeline_done = True
                        total_elapsed = ev.get("total_elapsed")

                table = _build_table(
                    stage_order,
                    stage_status,
                    stage_elapsed,
                    stage_start_ts,
                    stage_detail,
                    stage_progress,
                    health,
                    pipeline_start_ts,
                    total_elapsed,
                )
                live.update(table)

                if pipeline_done:
                    break

                time.sleep(_POLL_INTERVAL)

    # Final summary — stays visible until user dismisses
    failed = [s for s, st in stage_status.items() if st == "failed"]
    if failed:
        console.print(f"\n[bold red]Pipeline FAILED at stage(s): {', '.join(failed)}[/bold red]")
    else:
        total_str = f"{total_elapsed:.1f}s" if total_elapsed is not None else "unknown"
        console.print(f"\n[bold green]Pipeline completed successfully! Total: {total_str}[/bold green]")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
