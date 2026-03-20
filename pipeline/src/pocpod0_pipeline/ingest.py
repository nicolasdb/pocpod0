"""xAPI → OSLO RDF ingestion pipeline.

Reads synthetic xAPI statements from data/synthetic/, converts each to
OSLO-mapped RDF (Turtle), and stores the result in the appropriate learner
Pod via the CSS HTTP API (PUT).

Error handling: log+continue — individual statement failures never abort the run.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from pocpod0_pipeline.oslo_mapper import xapi_to_rdf
from pocpod0_pipeline.utils import (
    CSS_BASE_URL,
    log_event,
    provisioner_headers,
    synthetic_dir,
)

# ---------------------------------------------------------------------------
# CSS storage helpers
# ---------------------------------------------------------------------------

CSS_SUCCESS_CODES = {200, 201, 204, 205}


def _pod_for_statement(stmt: Dict) -> Optional[str]:
    """Determine the CSS pod name for a statement.

    Priority:
    1. Internal routing hint  _pocpod0_pod (set by scenario generator)
    2. Inferred from actor WebID path segment
    """
    hint = stmt.get("_pocpod0_pod")
    if hint:
        return hint

    actor = stmt.get("actor", {})
    account = actor.get("account", {})
    webid = account.get("name", "")
    # http://localhost:3000/{pod}/profile/card#me
    parts = webid.rstrip("/").split("/")
    if len(parts) >= 4 and parts[3]:
        return parts[3]
    return None


def _resource_path(pod_name: str, stmt_id: str, activity_type: str) -> str:
    """Build the CSS Pod resource path for a statement Turtle file."""
    # Derive a safe activity-type slug
    slug = (
        activity_type.rstrip("/").split("/")[-1]
        .replace(" ", "-")
        .lower()
    ) or "activity"
    return f"{pod_name}/learning/{slug}/{stmt_id}.ttl"


def _put_to_css(resource_path: str, turtle_data: str, css_base: str) -> Tuple[int, str]:
    """PUT Turtle resource to CSS Pod. Returns (status_code, error_or_empty)."""
    url = f"{css_base.rstrip('/')}/{resource_path}"
    headers = provisioner_headers("text/turtle")
    try:
        resp = requests.put(url, data=turtle_data.encode("utf-8"), headers=headers, timeout=10)
        if resp.status_code not in CSS_SUCCESS_CODES:
            return resp.status_code, f"HTTP {resp.status_code}: {resp.text[:200]}"
        return resp.status_code, ""
    except requests.RequestException as exc:
        return 0, str(exc)


# ---------------------------------------------------------------------------
# Statement processing
# ---------------------------------------------------------------------------

def process_statement(
    stmt: Dict,
    css_base: str,
    dry_run: bool = False,
) -> bool:
    """Convert and store a single xAPI statement. Returns True on success."""
    stmt_id = stmt.get("id", "")
    if not stmt_id:
        log_event("ingest.statement.skipped", "WARN",
                  {"reason": "missing_id", "actor": str(stmt.get("actor", {}))[:80]})
        return False

    pod = _pod_for_statement(stmt)
    if not pod:
        log_event("ingest.statement.skipped", "WARN",
                  {"reason": "no_pod_resolved", "statement_id": stmt_id})
        return False

    obj = stmt.get("object", {})
    act_type = obj.get("definition", {}).get("type", "activity")
    resource_path = _resource_path(pod, stmt_id, act_type)
    pod_resource_uri = f"{css_base.rstrip('/')}/{resource_path}"

    try:
        graph = xapi_to_rdf(stmt, pod_resource_uri=pod_resource_uri)
        turtle_data = graph.serialize(format="turtle")
    except Exception as exc:
        log_event("ingest.statement.failed", "ERROR",
                  {"statement_id": stmt_id, "phase": "conversion", "error": str(exc)})
        return False

    if dry_run:
        return True

    status_code, error = _put_to_css(resource_path, turtle_data, css_base)
    if error:
        log_event("ingest.statement.failed", "ERROR",
                  {"statement_id": stmt_id, "phase": "css_put",
                   "resource_path": resource_path, "error": error})
        return False

    log_event("ingest.statement.stored", "DEBUG",
              {"statement_id": stmt_id, "resource_path": resource_path,
               "http_status": status_code})
    return True


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def load_statements(input_dir: Path) -> List[Dict]:
    """Load all xAPI statements from JSON files in input_dir (non-recursive)."""
    statements: List[Dict] = []
    for json_file in sorted(input_dir.glob("**/*.json")):
        if json_file.name == "troll-load-manifest.json":
            continue
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                statements.extend(s for s in data if isinstance(s, dict))
            elif isinstance(data, dict):
                statements.append(data)
        except Exception as exc:
            log_event("ingest.load.error", "WARN",
                      {"file": str(json_file), "error": str(exc)})
    return statements


def run_pipeline(
    input_dir: Path,
    css_base: str,
    dry_run: bool = False,
) -> Dict:
    """Run the full ingestion pipeline. Returns summary dict."""
    log_event("ingest.run.start", "INFO",
              {"input_dir": str(input_dir), "css_base": css_base, "dry_run": dry_run})

    statements = load_statements(input_dir)
    total = len(statements)
    log_event("ingest.statements.loaded", "INFO", {"total": total})

    succeeded = 0
    failed = 0

    for stmt in statements:
        ok = process_statement(stmt, css_base, dry_run=dry_run)
        if ok:
            succeeded += 1
        else:
            failed += 1

    summary = {"event": "ingest.run.complete",
               "details": {"total": total, "succeeded": succeeded, "failed": failed}}
    log_event("ingest.run.complete", "INFO",
              {"total": total, "succeeded": succeeded, "failed": failed})
    print(json.dumps(summary))
    return summary["details"]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="xAPI → OSLO RDF ingestion pipeline")
    parser.add_argument(
        "--input-dir",
        default=str(synthetic_dir() / "scenarios"),
        help="Directory containing xAPI JSON files (default: data/synthetic/scenarios/)",
    )
    parser.add_argument(
        "--css-base-url",
        default=os.environ.get("CSS_BASE_URL", CSS_BASE_URL),
        help="CSS base URL (default: http://localhost:3000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Convert statements but do not PUT to CSS",
    )
    args = parser.parse_args()

    result = run_pipeline(
        input_dir=Path(args.input_dir),
        css_base=args.css_base_url,
        dry_run=args.dry_run,
    )
    # Exit non-zero if any failures
    sys.exit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
