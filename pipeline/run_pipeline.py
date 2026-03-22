"""Full pipeline orchestrator: generate → ingest → load-graph → embed.

Usage (from repo root, with venv active):
    python pipeline/run_pipeline.py [--wipe]

--wipe clears Oxigraph (CLEAR ALL) and deletes the Qdrant collection before running.
"""
import argparse
import os
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

STAGES = [
    {
        "name": "generate-troll",
        "label": "[1/5] Generate troll load",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.generate_troll_load"],
    },
    {
        "name": "generate-scenarios",
        "label": "[2/5] Generate scenario data",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.generate_scenarios"],
    },
    {
        "name": "ingest",
        "label": "[3/5] Ingest xAPI → CSS Pods (RDF)",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.ingest"],
    },
    {
        "name": "load-graph",
        "label": "[4/5] Load RDF → Oxigraph",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.load_graph"],
    },
    {
        "name": "embed",
        "label": "[5/5] Embed Oxigraph → Qdrant",
        "cmd": [sys.executable, "-m", "pocpod0_pipeline.embed"],
    },
]


def _header(text: str) -> None:
    bar = "─" * len(text)
    print(f"\n{bar}", flush=True)
    print(text, flush=True)
    print(bar, flush=True)


def wipe(oxigraph_url: str, qdrant_url: str) -> None:
    _header("Wiping existing data")

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
        sys.exit(1)

    print(f"  Qdrant: delete collection '{QDRANT_COLLECTION}' ... ", end="", flush=True)
    resp = httpx.delete(f"{qdrant_url}/collections/{QDRANT_COLLECTION}", timeout=15)
    if resp.status_code in (200, 404):
        print("done" if resp.status_code == 200 else "not found (ok)")
    else:
        print(f"FAILED ({resp.status_code})")
        sys.exit(1)


def run_stage(stage: dict) -> None:
    _header(stage["label"])
    t0 = time.monotonic()
    result = subprocess.run(stage["cmd"], env=os.environ.copy())
    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        print(f"\n✗ Stage '{stage['name']}' failed (exit {result.returncode}). Aborting.", flush=True)
        sys.exit(result.returncode)
    print(f"\n  Completed in {elapsed:.1f}s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full pocpod0 data pipeline")
    parser.add_argument("--wipe", action="store_true",
                        help="Clear Oxigraph and Qdrant before running")
    args = parser.parse_args()

    if args.wipe:
        wipe(OXIGRAPH_URL, QDRANT_URL)

    pipeline_start = time.monotonic()
    for stage in STAGES:
        run_stage(stage)

    total = time.monotonic() - pipeline_start
    _header(f"Pipeline complete — {total:.1f}s total")


if __name__ == "__main__":
    main()
