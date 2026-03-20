"""Shared utilities: structured JSON logging and config loading."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
PROVISIONER_WEBID = f"{CSS_BASE_URL}/provisioner/profile/card#me"


def log_event(
    event: str,
    level: str,
    details: Optional[Dict[str, Any]] = None,
    service: str = "pipeline",
) -> None:
    """Emit a structured JSON log entry to stdout."""
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": service,
        "level": level,
        "event": event,
    }
    if details:
        entry["details"] = details
    print(json.dumps(entry), flush=True)


def css_headers(pod_name: str) -> Dict[str, str]:
    """Return HTTP headers for CSS authenticated requests."""
    webid = f"{CSS_BASE_URL}/{pod_name}/profile/card#me"
    return {
        "Authorization": f"WebID {webid}",
        "Content-Type": "text/turtle",
    }


def provisioner_headers(content_type: str = "text/turtle") -> Dict[str, str]:
    """Return headers authenticated as provisioner agent."""
    return {
        "Authorization": f"WebID {PROVISIONER_WEBID}",
        "Content-Type": content_type,
    }


def repo_root() -> Path:
    """Return the repository root (pocpod0/).

    File location: pocpod0/pipeline/src/pocpod0_pipeline/utils.py
    parents[0] = pocpod0_pipeline/
    parents[1] = src/
    parents[2] = pipeline/
    parents[3] = pocpod0/   ← repo root
    """
    return Path(__file__).parents[3]


def schemas_dir() -> Path:
    return repo_root() / "data" / "schemas"


def synthetic_dir() -> Path:
    return repo_root() / "data" / "synthetic"
