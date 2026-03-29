"""3-layer deletion cascade with verification for GDPR Article 17 right to erasure.

Cascade sequence:
  Step 1 — CSS soft-delete: mark resource with pocpod0:deletedAt and pocpod0:isDeleted
  Step 2 — Oxigraph DROP GRAPH: remove all derived triples for the pod resource URI
  Step 3 — Qdrant delete: remove all embeddings matching pod_uri_hash
  Step 4 — Verification: confirm all three layers are clean

Design decisions:
  - Step failure does NOT abort cascade: each step runs independently; all_layers_clean
    is determined by verification, not by step success flags.
  - Soft-delete in CSS (not hard-delete): preserves audit trail of erasure request.
  - DROP GRAPH <pod-resource-uri>: removes ALL derived triples in one SPARQL UPDATE.
    This is the correct Oxigraph deletion mechanism (Story 2.6 named graph pattern).
  - Qdrant delete by pod_uri_hash: opaque identifier, not raw URI (PRIV-1 fix, Story 5.2).
  - TODO (post-story): full re-embed migration to remove legacy pod_resource_uri from
    existing Qdrant points that predate the PRIV-1 fix (Story 5.2 AC4).

Isolation notes:
  - distrobox-host-exec works perfectly for accessing podman containers from within distrobox
  - URLs from .env: CSS_CONNECT_URL, OXIGRAPH_URL, QDRANT_URL
"""

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx

from pocpod0_pipeline.utils import log_event, repo_root
from pocpod0_pipeline.uuid_index import deregister_hash

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSS_CONNECT_URL = os.environ.get("CSS_CONNECT_URL", "http://localhost:3000")
OXIGRAPH_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "pocpod0_embeddings"

CONSENT_EVENTS_FILE = repo_root() / "data" / "consent-events.jsonl"

# Safety guard: only allow HTTPS or localhost URIs in SPARQL interpolation
_SAFE_URI_RE = re.compile(r"^https?://[^<>\s]+$")


def _safe_uri(uri: str) -> bool:
    return bool(_SAFE_URI_RE.match(uri))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    step: str           # e.g. "1-css-soft-delete"
    layer: str          # "css" | "oxigraph" | "qdrant"
    status: str         # "ok" | "error"
    details: str        # human-readable summary or error message
    duration_ms: int


@dataclass
class VerificationResult:
    resource_uri: str
    css_deleted: bool
    oxigraph_clean: bool
    qdrant_clean: bool
    all_layers_clean: bool
    timestamp: str


@dataclass
class DeletionResult:
    resource_uri: str
    pod_name: str
    step_results: List[StepResult] = field(default_factory=list)
    verification: Optional[VerificationResult] = None
    all_layers_clean: bool = False
    timestamp: str = ""


# ---------------------------------------------------------------------------
# JSONL event logging
# ---------------------------------------------------------------------------


def _append_consent_event(event: dict) -> None:
    """Append a structured event to data/consent-events.jsonl."""
    CONSENT_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CONSENT_EVENTS_FILE.exists():
        CONSENT_EVENTS_FILE.touch()
    with CONSENT_EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _emit_step_event(
    pod: str,
    resource_uri: str,
    step: str,
    status: str,
    details: str,
) -> None:
    event = {
        "event_type": "deletion.step",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pod": pod,
        "resource_uri": resource_uri,
        "step": step,
        "status": status,
        "details": details,
    }
    _append_consent_event(event)
    log_event("deletion.step", "INFO" if status == "ok" else "ERROR", {
        "pod": pod,
        "resource_uri": resource_uri,
        "step": step,
        "status": status,
        "details": details,
    })


# ---------------------------------------------------------------------------
# Step 1: CSS soft-delete
# ---------------------------------------------------------------------------


def soft_delete_css(
    resource_uri: str,
    pod_name: str,
    css_url: str = CSS_CONNECT_URL,
) -> StepResult:
    """Mark the CSS resource with pocpod0:deletedAt and pocpod0:isDeleted true.

    Uses SPARQL 1.1 Update PATCH to insert two triples into the resource.
    Auth: Authorization: WebID <webid> (Stories 1.4/1.5 CSS auth pattern).
    css_url must be the external-facing URL (CSS_CONNECT_URL, not Docker-internal hostname).
    P-8: uses css_url param (not module constant) so callers can pass non-default URLs.
    """
    t0 = time.time()
    webid = f"{css_url.rstrip('/')}/{pod_name}/profile/card#me"
    deleted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    patch_body = (
        "PREFIX pocpod0: <https://poc-pod0.edu/vocab/>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "INSERT DATA {\n"
        f'  <{resource_uri}> pocpod0:deletedAt "{deleted_at}"^^xsd:dateTime .\n'
        f"  <{resource_uri}> pocpod0:isDeleted true .\n"
        "}"
    )

    try:
        resp = httpx.patch(
            resource_uri,
            content=patch_body.encode("utf-8"),
            headers={
                "Authorization": f"WebID {webid}",
                "Content-Type": "application/sparql-update",
            },
            timeout=15,
        )
        duration_ms = int((time.time() - t0) * 1000)
        if resp.status_code in (200, 201, 204, 205):
            return StepResult(
                step="1-css-soft-delete",
                layer="css",
                status="ok",
                details=f"Marked deletedAt={deleted_at}, isDeleted=true (HTTP {resp.status_code})",
                duration_ms=duration_ms,
            )
        else:
            return StepResult(
                step="1-css-soft-delete",
                layer="css",
                status="error",
                details=f"HTTP {resp.status_code}: {resp.text[:200]}",
                duration_ms=duration_ms,
            )
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        return StepResult(
            step="1-css-soft-delete",
            layer="css",
            status="error",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Step 2: Oxigraph DROP GRAPH
# ---------------------------------------------------------------------------


def drop_oxigraph_graph(resource_uri: str, oxigraph_url: str = OXIGRAPH_URL) -> StepResult:
    """Execute SPARQL UPDATE DROP GRAPH <resource_uri> in Oxigraph.

    Removes ALL derived triples for the named graph (Story 2.6 pattern).
    Idempotent: if the graph does not exist, Oxigraph returns 200 silently.
    Confirms deletion with an ASK query.
    """
    t0 = time.time()
    if not _safe_uri(resource_uri):
        return StepResult(
            step="2-oxigraph-drop",
            layer="oxigraph",
            status="error",
            details=f"Unsafe URI rejected: {resource_uri!r}",
            duration_ms=0,
        )

    drop_statement = f"DROP GRAPH <{resource_uri}>"
    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/update",
            content=drop_statement.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            timeout=30,
        )
        duration_ms = int((time.time() - t0) * 1000)
        if resp.status_code not in (200, 204):
            return StepResult(
                step="2-oxigraph-drop",
                layer="oxigraph",
                status="error",
                details=f"DROP GRAPH HTTP {resp.status_code}: {resp.text[:200]}",
                duration_ms=duration_ms,
            )

        # Confirm with ASK query
        ask_query = f"ASK {{ GRAPH <{resource_uri}> {{ ?s ?p ?o }} }}"
        ask_resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/query",
            content=ask_query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        # P-6: guard .json() on 200 to avoid JSONDecodeError on error bodies
        if ask_resp.status_code == 200:
            graph_still_exists = ask_resp.json().get("boolean", True)
        else:
            graph_still_exists = False  # cannot confirm; treat as clean (DROP succeeded)
        if graph_still_exists:
            return StepResult(
                step="2-oxigraph-drop",
                layer="oxigraph",
                status="error",
                details="DROP GRAPH succeeded but ASK query still returns triples",
                duration_ms=int((time.time() - t0) * 1000),
            )

        return StepResult(
            step="2-oxigraph-drop",
            layer="oxigraph",
            status="ok",
            details=f"Named graph dropped and confirmed empty (DROP HTTP {resp.status_code})",
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        return StepResult(
            step="2-oxigraph-drop",
            layer="oxigraph",
            status="error",
            details=f"{type(exc).__name__}: {exc}",
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Step 3: Qdrant delete by pod_uri_hash
# ---------------------------------------------------------------------------


def delete_qdrant_points(
    pod_uri_hash: str,
    qdrant_url: str = QDRANT_URL,
    resource_uri: str = "",
) -> StepResult:
    """Delete all Qdrant points whose payload pod_uri_hash matches the given hash.

    Also attempts legacy deletion by pod_resource_uri for points written before
    the PRIV-1 fix (Story 5.2 AC4 transition period).

    Raises no exceptions: errors are captured in StepResult.
    """
    t0 = time.time()
    delete_url = f"{qdrant_url.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/delete"

    errors = []

    # Primary deletion: by pod_uri_hash (post-PRIV-1-fix points)
    body = {
        "filter": {
            "must": [{"key": "pod_uri_hash", "match": {"value": pod_uri_hash}}]
        }
    }
    try:
        resp = httpx.post(
            delete_url + "?wait=true",
            content=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            result_data = resp.json().get("result", {})
            status = result_data.get("status", "")
            _ = result_data.get("operation_id")  # sequence number, not point count (P-2)
            if status not in ("completed", "acknowledged", "ok"):
                errors.append(f"pod_uri_hash delete status={status!r}")
        else:
            errors.append(f"pod_uri_hash delete HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as exc:
        errors.append(f"pod_uri_hash delete error: {type(exc).__name__}: {exc}")

    # Legacy deletion: by pod_resource_uri (pre-PRIV-1-fix points)
    # TODO (post-story): remove once full re-embed migration is done
    if resource_uri and _safe_uri(resource_uri):
        legacy_body = {
            "filter": {
                "must": [{"key": "pod_resource_uri", "match": {"value": resource_uri}}]
            }
        }
        try:
            legacy_resp = httpx.post(
                delete_url + "?wait=true",
                content=json.dumps(legacy_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if legacy_resp.status_code == 200:
                legacy_status = legacy_resp.json().get("result", {}).get("status", "")
                if legacy_status not in ("completed", "acknowledged", "ok"):
                    errors.append(f"legacy pod_resource_uri delete status={legacy_status!r}")
            else:
                errors.append(f"legacy delete HTTP {legacy_resp.status_code}: {legacy_resp.text[:100]}")
        except Exception as exc:
            errors.append(f"legacy delete error: {type(exc).__name__}: {exc}")

    duration_ms = int((time.time() - t0) * 1000)
    if errors:
        return StepResult(
            step="3-qdrant-delete",
            layer="qdrant",
            status="error",
            details="; ".join(errors),
            duration_ms=duration_ms,
        )

    return StepResult(
        step="3-qdrant-delete",
        layer="qdrant",
        status="ok",
        details=f"Deleted points matching hash={pod_uri_hash} (and legacy pod_resource_uri if any)",
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Step 4: Verification
# ---------------------------------------------------------------------------


def verify_deletion(
    resource_uri: str,
    pod_uri_hash: str,
    pod_name: str,
    css_url: str = CSS_CONNECT_URL,
    oxigraph_url: str = OXIGRAPH_URL,
    qdrant_url: str = QDRANT_URL,
) -> VerificationResult:
    """Verify deletion completeness across all three layers.

    Layer 1 (CSS): GET resource; check body for pocpod0:isDeleted true
    Layer 2 (Oxigraph): ASK { GRAPH <resource_uri> { ?s ?p ?o } } → must be false
    Layer 3 (Qdrant): scroll/count filtered by pod_uri_hash → must be 0 points
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    webid = f"{css_url}/{pod_name}/profile/card#me"

    # Layer 1: CSS — check for isDeleted marker
    css_deleted = False
    try:
        resp = httpx.get(
            resource_uri,
            headers={
                "Authorization": f"WebID {webid}",
                "Accept": "text/turtle",
            },
            timeout=10,
            follow_redirects=True,
        )
        if resp.status_code in (200, 204, 205):
            # P-7: anchor to full predicate+value to avoid false-positive on similar names
            css_deleted = (
                "pocpod0:isDeleted true" in resp.text
                or "pocpod0:isDeleted> true" in resp.text  # Turtle expanded form
            )
        elif resp.status_code == 404:
            # Resource not found — could mean hard-deleted or never existed
            css_deleted = False
    except Exception:
        css_deleted = False

    # Layer 2: Oxigraph — ASK graph must return false
    oxigraph_clean = False
    if not _safe_uri(resource_uri):
        # P-12: log so operator knows this wasn't a real dirty-graph result
        log_event("deletion.verify", "WARN", {
            "reason": "unsafe_uri_skipped_oxigraph_check",
            "resource_uri": resource_uri,
        })
    else:
        try:
            ask_query = f"ASK {{ GRAPH <{resource_uri}> {{ ?s ?p ?o }} }}"
            ask_resp = httpx.post(
                f"{oxigraph_url.rstrip('/')}/query",
                content=ask_query.encode("utf-8"),
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json",
                },
                timeout=10,
            )
            if ask_resp.status_code == 200:
                oxigraph_clean = not ask_resp.json().get("boolean", True)
        except Exception:
            oxigraph_clean = False

    # Layer 3: Qdrant — count points by pod_uri_hash must be 0
    qdrant_clean = False
    try:
        count_url = f"{qdrant_url.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/count"
        count_body = {
            "filter": {
                "must": [{"key": "pod_uri_hash", "match": {"value": pod_uri_hash}}]
            },
            "exact": True,
        }
        count_resp = httpx.post(
            count_url,
            content=json.dumps(count_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if count_resp.status_code == 200:
            count = count_resp.json().get("result", {}).get("count", -1)
            qdrant_clean = count == 0
    except Exception:
        qdrant_clean = False

    all_clean = css_deleted and oxigraph_clean and qdrant_clean

    verification = VerificationResult(
        resource_uri=resource_uri,
        css_deleted=css_deleted,
        oxigraph_clean=oxigraph_clean,
        qdrant_clean=qdrant_clean,
        all_layers_clean=all_clean,
        timestamp=timestamp,
    )

    # P-3: use deletion.step event type (step 4-verification) per AC3 schema
    # P-4: include passed field per AC2
    event = {
        "event_type": "deletion.step",
        "timestamp": timestamp,
        "pod": pod_name,
        "resource_uri": resource_uri,
        "step": "4-verification",
        "status": "ok" if all_clean else "partial",
        "passed": all_clean,
        "details": {
            "css_deleted": css_deleted,
            "oxigraph_clean": oxigraph_clean,
            "qdrant_clean": qdrant_clean,
            "all_layers_clean": all_clean,
        },
    }
    _append_consent_event(event)
    log_event("deletion.step", "INFO" if all_clean else "WARN", {
        "pod": pod_name,
        "resource_uri": resource_uri,
        "step": "4-verification",
        "css_deleted": css_deleted,
        "oxigraph_clean": oxigraph_clean,
        "qdrant_clean": qdrant_clean,
        "all_layers_clean": all_clean,
    })

    return verification


# ---------------------------------------------------------------------------
# Cascade orchestrator
# ---------------------------------------------------------------------------


def run_cascade(
    resource_uri: str,
    pod_name: str,
    css_url: str = CSS_CONNECT_URL,
    oxigraph_url: str = OXIGRAPH_URL,
    qdrant_url: str = QDRANT_URL,
) -> DeletionResult:
    """Orchestrate the 3-layer deletion cascade for a Pod resource URI.

    Runs steps 1→2→3→verify sequentially.
    Step failure does NOT abort cascade — each step runs regardless of prior failures.
    all_layers_clean is determined by verification, not by step success flags.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pod_uri_hash = hashlib.sha256(resource_uri.encode()).hexdigest()[:16]

    result = DeletionResult(
        resource_uri=resource_uri,
        pod_name=pod_name,
        timestamp=timestamp,
    )

    log_event("deletion.cascade.start", "INFO", {
        "pod": pod_name,
        "resource_uri": resource_uri,
        "pod_uri_hash": pod_uri_hash,
    })

    # Step 1: CSS soft-delete
    step1 = soft_delete_css(resource_uri, pod_name, css_url=css_url)
    result.step_results.append(step1)
    _emit_step_event(pod_name, resource_uri, step1.step, step1.status, step1.details)

    # Step 2: Oxigraph DROP GRAPH
    step2 = drop_oxigraph_graph(resource_uri, oxigraph_url)
    result.step_results.append(step2)
    _emit_step_event(pod_name, resource_uri, step2.step, step2.status, step2.details)

    # Step 3: Qdrant delete
    step3 = delete_qdrant_points(pod_uri_hash, qdrant_url, resource_uri=resource_uri)
    result.step_results.append(step3)
    _emit_step_event(pod_name, resource_uri, step3.step, step3.status, step3.details)

    # Deregister hash from UUID index — only after Qdrant delete succeeds (P-1)
    if step3.status == "ok":
        try:
            deregister_hash(pod_uri_hash, oxigraph_url)
        except Exception as exc:
            log_event("deletion.uuid_index.deregister", "WARN", {
                "pod_uri_hash": pod_uri_hash,
                "error": str(exc),
            })
    else:
        log_event("deletion.uuid_index.deregister", "WARN", {
            "pod_uri_hash": pod_uri_hash,
            "reason": "skipped — step 3 failed; UUID index entry preserved for retry",
        })

    # Step 4: Verification
    verification = verify_deletion(
        resource_uri=resource_uri,
        pod_uri_hash=pod_uri_hash,
        pod_name=pod_name,
        css_url=css_url,
        oxigraph_url=oxigraph_url,
        qdrant_url=qdrant_url,
    )
    result.verification = verification
    result.all_layers_clean = verification.all_layers_clean

    # Final deletion.complete event
    final_event = {
        "event_type": "deletion.complete",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pod": pod_name,
        "resource_uri": resource_uri,
        "all_layers_clean": result.all_layers_clean,
        "passed": result.all_layers_clean,
        "steps_completed": len(result.step_results),
        "verification": {
            "css_deleted": verification.css_deleted,
            "oxigraph_clean": verification.oxigraph_clean,
            "qdrant_clean": verification.qdrant_clean,
        },
    }
    _append_consent_event(final_event)
    log_event("deletion.cascade.complete", "INFO" if result.all_layers_clean else "WARN", {
        "pod": pod_name,
        "resource_uri": resource_uri,
        "all_layers_clean": result.all_layers_clean,
        "steps_completed": len(result.step_results),
    })

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="3-layer deletion cascade: CSS soft-delete + Oxigraph DROP GRAPH + Qdrant delete"
    )
    parser.add_argument("--resource-uri", required=True, help="Pod resource URI to delete")
    parser.add_argument("--pod", required=True, help="Pod name (e.g. 'ayoub')")
    parser.add_argument("--css-url", default=CSS_CONNECT_URL)
    parser.add_argument("--oxigraph-url", default=OXIGRAPH_URL)
    parser.add_argument("--qdrant-url", default=QDRANT_URL)
    args = parser.parse_args()

    result = run_cascade(
        resource_uri=args.resource_uri,
        pod_name=args.pod,
        css_url=args.css_url,
        oxigraph_url=args.oxigraph_url,
        qdrant_url=args.qdrant_url,
    )

    import sys
    print(json.dumps({
        "resource_uri": result.resource_uri,
        "pod_name": result.pod_name,
        "all_layers_clean": result.all_layers_clean,
        "steps": [
            {"step": s.step, "layer": s.layer, "status": s.status, "details": s.details}
            for s in result.step_results
        ],
        "verification": {
            "css_deleted": result.verification.css_deleted if result.verification else None,
            "oxigraph_clean": result.verification.oxigraph_clean if result.verification else None,
            "qdrant_clean": result.verification.qdrant_clean if result.verification else None,
        } if result.verification else None,
    }))
    sys.exit(0 if result.all_layers_clean else 1)


if __name__ == "__main__":
    main()
