"""Full pipeline orchestrator: generate → ingest → load-graph → embed.

Usage (from repo root, with venv active):
    python pipeline/run_pipeline.py [--wipe]

--wipe clears Oxigraph (CLEAR ALL) and deletes the Qdrant collection before running.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

# Load .env from repo root if present (before reading env vars)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

OXIGRAPH_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")
QDRANT_COLLECTION = "pocpod0_embeddings"
CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

POD_SLUGS = [
    "ayoub",
    "claire",
    "claire-student-1",
    "claire-student-2",
    "fatima",
    "fatima-child-1",
    "fatima-child-2",
    "school-community",
]

_JSONL_LOG = Path(__file__).parent.parent / "data" / "pipeline-run.jsonl"


def _emit(event_type: str, **data) -> None:
    """Append a JSONL event line to data/pipeline-run.jsonl."""
    event = {"timestamp": time.time(), "event_type": event_type, **data}
    _JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _JSONL_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")


STAGES = [
    {
        "name": "provision",
        "label": "[0/6] Provision pods + seed data",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.provision_stage"],
    },
    {
        "name": "generate-troll",
        "label": "[1/6] Generate troll load",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.generate_troll_load"],
    },
    {
        "name": "generate-scenarios",
        "label": "[2/6] Generate scenario data",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.generate_scenarios"],
    },
    {
        "name": "ingest",
        "label": "[3/6] Ingest xAPI → CSS Pods (RDF)",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.ingest",
                "--input-dir", str(Path(__file__).parent.parent / "data" / "synthetic")],
    },
    {
        "name": "load-graph",
        "label": "[4/6] Load RDF → Oxigraph",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.load_graph"],
    },
    {
        "name": "embed",
        "label": "[5/6] Embed Oxigraph → Qdrant",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.embed"],
    },
]


def _header(text: str) -> None:
    bar = "─" * len(text)
    print(f"\n{bar}", flush=True)
    print(text, flush=True)
    print(bar, flush=True)


def _list_css_pod_slugs(css_base_url: str, provisioner_webid: str) -> list[str]:
    """Enumerate all pod slugs by listing the CSS root container.

    Fetches the CSS root as Turtle and extracts first-level path segments.
    Falls back to POD_SLUGS if the root listing fails.
    """
    headers = {
        "Authorization": f"WebID {provisioner_webid}",
        "Accept": "text/turtle",
    }
    try:
        resp = httpx.get(f"{css_base_url}/", headers=headers, timeout=10)
    except httpx.RequestError as exc:
        print(f"  CSS root listing failed ({exc}), falling back to known slugs")
        return POD_SLUGS

    if resp.status_code not in (200, 201):
        print(f"  CSS root listing returned {resp.status_code}, falling back to known slugs")
        return POD_SLUGS

    # CSS root uses relative URIs like <ayoub/> — extract slug from trailing-slash entries
    # Skip CSS system paths that are not user pods
    _CSS_SYSTEM_SLUGS = {".well-known", ".internal", ".oidc", "idp", ".account"}
    all_refs = re.findall(r"<([^>]+)>", resp.text)
    slugs = []
    for ref in all_refs:
        # Relative URI with single path segment and trailing slash = pod root
        stripped = ref.rstrip("/")
        if (stripped and "/" not in stripped
                and not stripped.startswith("http")
                and not stripped.startswith(".")
                and stripped not in _CSS_SYSTEM_SLUGS
                and stripped not in slugs):
            slugs.append(stripped)

    if not slugs:
        print("  CSS root listing returned no pods, falling back to known slugs")
        return POD_SLUGS

    print(f"  CSS root: found {len(slugs)} pods")
    return slugs


def _ldp_list_children(url: str, headers_get: dict) -> tuple[list[str], list[str]]:
    """List direct children of an LDP container.

    CSS returns relative URIs in Turtle. Returns (leaf_urls, sub_container_urls)
    where leaves are non-container resources and sub_containers end with '/'.
    """
    try:
        resp = httpx.get(url, headers=headers_get, timeout=10)
    except httpx.RequestError:
        return [], []
    if resp.status_code not in (200, 201):
        return [], []

    refs = re.findall(r"<([^>]+)>", resp.text)
    leaves, containers = [], []
    for ref in refs:
        if ref.startswith("http") or ref.startswith("#") or ref == "":
            continue
        # Relative URIs: sub-containers end with /, leaves don't
        full = url.rstrip("/") + "/" + ref.lstrip("/") if not ref.startswith("/") else url.split("//")[0] + "//" + url.split("//")[1].split("/")[0] + ref
        if ref.endswith("/"):
            containers.append(full)
        else:
            leaves.append(full)
    return leaves, containers


def _recursive_delete(container_url: str, headers_get: dict, headers_delete: dict) -> int:
    """Recursively delete all contents of an LDP container, then the container itself.

    Returns total number of resources deleted.
    """
    deleted = 0
    leaves, sub_containers = _ldp_list_children(container_url, headers_get)

    # Recurse into sub-containers first
    for sub in sub_containers:
        deleted += _recursive_delete(sub, headers_get, headers_delete)

    # Delete leaf resources
    for leaf in leaves:
        try:
            r = httpx.delete(leaf, headers=headers_delete, timeout=10)
            if r.status_code in (200, 204):
                deleted += 1
            # 404 = already gone, tolerate silently
        except httpx.RequestError:
            pass

    # Delete the now-empty container
    try:
        httpx.delete(container_url, headers=headers_delete, timeout=10)
    except httpx.RequestError:
        pass

    return deleted


def wipe_css_pods(css_base_url: str, emit_progress=None) -> None:
    """Recursive DELETE of learning/ containers in ALL CSS pods, and camp/ in school-community.

    Enumerates pods dynamically from the CSS root to catch troll-generated
    pods (student-XXXX, admin-XXXX, etc.) in addition to scenario pods.
    CSS LDP returns 409 on DELETE of non-empty containers, so we must
    recursively delete leaves first (learning/ → course/ → *.ttl).
    Tolerates 404 gracefully (already empty = OK).
    Also wipes camp/ container in school-community pod (seeded data).
    """
    provisioner_webid = f"{css_base_url}/provisioner/profile/card#me"
    headers_get = {
        "Authorization": f"WebID {provisioner_webid}",
        "Accept": "text/turtle",
    }
    headers_delete = {
        "Authorization": f"WebID {provisioner_webid}",
    }

    slugs = _list_css_pod_slugs(css_base_url, provisioner_webid)

    total_deleted = 0
    for slug in slugs:
        container_url = f"{css_base_url}/{slug}/learning/"
        try:
            resp = httpx.get(container_url, headers=headers_get, timeout=10)
        except httpx.RequestError as exc:
            print(f"  CSS pod {slug}/learning/: connection error ({exc}), skipping")
            continue

        if resp.status_code == 404:
            if emit_progress:
                emit_progress(slug, 0, len(slugs))
            continue  # already empty, no noise
        if resp.status_code not in (200, 201):
            print(f"  CSS pod {slug}/learning/: unexpected GET status {resp.status_code}, skipping")
            continue

        deleted = _recursive_delete(container_url, headers_get, headers_delete)
        total_deleted += deleted
        if emit_progress:
            emit_progress(slug, deleted, len(slugs))
        if deleted > 0:
            print(f"  CSS pod {slug}/learning/: deleted {deleted} resources")

    # Also wipe camp/ container in school-community pod (seeded data from Stage 0)
    camp_url = f"{css_base_url}/school-community/camp/"
    try:
        resp = httpx.get(camp_url, headers=headers_get, timeout=10)
        if resp.status_code in (200, 201):
            deleted = _recursive_delete(camp_url, headers_get, headers_delete)
            total_deleted += deleted
            if deleted > 0:
                print(f"  CSS pod school-community/camp/: deleted {deleted} resources")
    except httpx.RequestError as exc:
        print(f"  CSS pod school-community/camp/: connection error ({exc}), skipping")

    print(f"  CSS pods wiped: {total_deleted} total resources deleted across {len(slugs)} pods")


def wipe(oxigraph_url: str, qdrant_url: str) -> None:
    _header("Wiping existing data")
    _emit("pipeline.wipe.start")

    _wipe_pod_count = [0]

    def _on_pod_wiped(slug: str, deleted: int, total_pods: int) -> None:
        _wipe_pod_count[0] += 1
        _emit("pipeline.wipe.progress", pod=slug, deleted=deleted,
              pods_done=_wipe_pod_count[0], pods_total=total_pods)

    wipe_css_pods(CSS_BASE_URL, emit_progress=_on_pod_wiped)

    print("  Oxigraph: CLEAR ALL ... ", end="", flush=True)
    resp = httpx.post(
        f"{oxigraph_url}/update",
        content="CLEAR ALL",
        headers={"Content-Type": "application/sparql-update"},
        timeout=30,
    )
    if resp.status_code in (200, 204):
        print("done")
    else:
        print(f"FAILED ({resp.status_code})")
        _emit("pipeline.done", total_elapsed=0.0, failed="wipe-oxigraph")
        sys.exit(1)

    print(f"  Qdrant: delete collection '{QDRANT_COLLECTION}' ... ", end="", flush=True)
    resp = httpx.delete(f"{qdrant_url}/collections/{QDRANT_COLLECTION}", timeout=15)
    if resp.status_code in (200, 404):
        print("done" if resp.status_code == 200 else "not found (ok)")
    else:
        print(f"FAILED ({resp.status_code})")
        _emit("pipeline.done", total_elapsed=0.0, failed="wipe-qdrant")
        sys.exit(1)

    _emit("pipeline.wipe.done")


def run_stage(stage: dict, dry_run: bool = False, log_file=None) -> None:
    _header(stage["label"])
    t0 = time.monotonic()
    _emit("stage.start", stage=stage["name"], label=stage["label"])
    if dry_run:
        time.sleep(1.5)
        elapsed = time.monotonic() - t0
    else:
        kwargs = {"env": os.environ.copy()}
        if log_file is not None:
            kwargs["stdout"] = log_file
            kwargs["stderr"] = log_file
        result = subprocess.run(stage["cmd"], **kwargs)
        elapsed = time.monotonic() - t0
        if result.returncode != 0:
            _emit("stage.failed", stage=stage["name"], elapsed=elapsed, returncode=result.returncode)
            print(f"\n✗ Stage '{stage['name']}' failed (exit {result.returncode}). Aborting.", flush=True)
            sys.exit(result.returncode)
    _emit("stage.done", stage=stage["name"], elapsed=elapsed)
    print(f"\n  Completed in {elapsed:.1f}s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full pocpod0 data pipeline")
    parser.add_argument("--wipe", action="store_true",
                        help="Clear Oxigraph and Qdrant before running")
    parser.add_argument("--dry-run", action="store_true",
                        help="Emit JSONL events with fake 1.5s stages — no real work, for dashboard testing")
    parser.add_argument("--with-dashboard", action="store_true",
                        help="Launch the TUI dashboard automatically; pipeline stdout goes to data/pipeline.log")
    args = parser.parse_args()

    # Truncate JSONL log at start of each run
    _JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
    _JSONL_LOG.write_text("")

    _log_file = None
    _dashboard_proc = None
    if args.with_dashboard:
        _log_path = _JSONL_LOG.parent / "pipeline.log"
        _dashboard_proc = subprocess.Popen(
            [sys.executable, "-m", "pocpod0_pipeline.pipeline_dashboard"],
            env=os.environ.copy(),
        )
        _log_file = open(_log_path, "w")
        sys.stdout = _log_file
        sys.stderr = _log_file

    if args.wipe and not args.dry_run:
        wipe(OXIGRAPH_URL, QDRANT_URL)

    if args.dry_run:
        print("[DRY RUN] Emitting fake events — no real pipeline work will run.", flush=True)

    pipeline_start = time.monotonic()
    _emit("pipeline.start", stages=[s["name"] for s in STAGES], wipe=args.wipe)
    for stage in STAGES:
        run_stage(stage, dry_run=args.dry_run, log_file=_log_file)

    total = time.monotonic() - pipeline_start
    _emit("pipeline.done", total_elapsed=total)
    _header(f"Pipeline complete — {total:.1f}s total")

    if _dashboard_proc is not None:
        _dashboard_proc.wait()
    if _log_file is not None:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        _log_file.close()


if __name__ == "__main__":
    main()
