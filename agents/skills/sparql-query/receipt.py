"""Access receipt writer for the sparql-query skill.

Implements BP-1 (Bidirectional Accountability): every institutional query that
reads data derived from a student pod generates a human-legible, machine-readable
Turtle receipt stored in `{pod_uri}access-log/{timestamp_slug}.ttl`.

Design constraints:
  - write_access_receipt() NEVER raises — all exceptions are caught and logged.
  - Receipt writing is a non-blocking side-effect; the query result is returned
    regardless of whether the receipt write succeeds.
  - Receipt format: Turtle (text/turtle), `urn:receipt:` URN scheme.
  - CSS auth: Authorization: WebID <skill-webid> (PoC debug-auth-header pattern).

Isolation note:
  - CSS runs in a Docker/podman container. Use CSS_CONNECT_URL for HTTP PUT
    but CSS_IDENTIFIER_URL for WebID URIs (three-var model, Story 3.1).
  - Use `distrobox-host-exec` if running podman containers from within distrobox.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Environment — CSS three-var model (Story 3.1)
# ---------------------------------------------------------------------------

_CSS_IDENTIFIER_URL = os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000").rstrip("/")
_CSS_CONNECT_URL = os.environ.get("CSS_CONNECT_URL", _CSS_IDENTIFIER_URL).rstrip("/")
_CSS_IDENTIFIER_HOST = os.environ.get(
    "CSS_IDENTIFIER_HOST",
    _CSS_IDENTIFIER_URL.split("//", 1)[-1],
)

# SPARQL skill service-account WebID for writing receipts.
# Must have acl:Write on {pod_uri}access-log/ (provisioned via provision_pods.py).
_SPARQL_SKILL_WEBID = os.environ.get(
    "SPARQL_SKILL_WEBID",
    f"{_CSS_IDENTIFIER_URL}/sparql-skill/profile/card#me",
)

SERVICE_NAME = "sparql-query-skill"


# ---------------------------------------------------------------------------
# Structured logging helper (mirrors handler.py)
# ---------------------------------------------------------------------------


def _log_warning(event: str, details: dict) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "level": "WARN",
        "event": event,
        "details": details,
    }
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# Timestamp slug
# ---------------------------------------------------------------------------


def _make_timestamp_slug(timestamp: str) -> str:
    """Convert ISO-8601 timestamp to URL-safe slug.

    Replaces colons with hyphens and normalises to millisecond precision.
    e.g. "2026-03-25T14:32:17.432Z" → "2026-03-25T14-32-17-432Z"
    """
    # Remove trailing Z, split on fractional seconds
    ts = timestamp.rstrip("Z")
    if "." in ts:
        base, frac = ts.split(".", 1)
        # Pad or trim fractional to 3 digits (milliseconds)
        frac = (frac + "000")[:3]
    else:
        base = ts
        frac = "000"
    # Replace colons in time portion only (after T)
    if "T" in base:
        date_part, time_part = base.split("T", 1)
        time_part = time_part.replace(":", "-")
        base = f"{date_part}T{time_part}"
    return f"{base}-{frac}Z"


# ---------------------------------------------------------------------------
# Turtle receipt builder
# ---------------------------------------------------------------------------


def build_receipt_turtle(
    agent_webid: str,
    query_type: str,
    pod_uri: str,
    consent_grant_uri: Optional[str],
    result_shape: str,
    named_graphs: list,
    timestamp: str,
    timestamp_slug: str,
) -> str:
    """Build Turtle document for an access receipt.

    Returns a valid Turtle string. No raw data — only metadata about what
    was accessed, by whom, under what authority, and with what result shape.

    Args:
        agent_webid:       WebID URI of the querying agent.
        query_type:        SPARQL template name (e.g. "student-progress").
        pod_uri:           Pod root URI whose data was accessed.
        consent_grant_uri: URI of the consent grant that authorized the query,
                           or None if the query was denied.
        result_shape:      Human-readable description of what was returned.
        named_graphs:      List of named graph URIs that contributed to the result.
        timestamp:         ISO-8601 datetime of query execution.
        timestamp_slug:    URL-safe slug derived from timestamp.

    Returns:
        Turtle string.
    """
    receipt_uri = f"urn:receipt:{timestamp_slug}"

    # Escape strings for Turtle (no quotes or backslashes in user-controlled fields)
    def _escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    # Strip URI-breaking characters from URI fields (P-4: prevent Turtle injection)
    def _safe_uri(u: str) -> str:
        return u.replace("<", "").replace(">", "")

    lines = [
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix poc: <https://pocpod0.example/vocab#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "",
        f"<{receipt_uri}> a poc:AccessReceipt ;",
        f'    poc:queriedBy <{_safe_uri(agent_webid)}> ;',
        f'    poc:accessedAt "{_escape(timestamp)}"^^xsd:dateTime ;',
        f'    poc:queryType "{_escape(query_type)}" ;',
        f'    poc:resultShape "{_escape(result_shape)}" ;',
    ]

    if consent_grant_uri is not None:
        lines.append(f"    poc:consentGrant <{_safe_uri(consent_grant_uri)}> ;")
    else:
        lines.append('    poc:accessDenied "true"^^xsd:boolean ;')

    # Named graphs as a single RDF list: (<g1> <g2> ...) for proper SPARQL traversal
    if named_graphs:
        graph_items = " ".join(f"<{g}>" for g in named_graphs)
        lines.append(f"    poc:namedGraphsContributed ({graph_items}) ;")
    else:
        lines.append("    poc:namedGraphsContributed () ;")

    lines.append(f'    dcterms:created "{_escape(timestamp)}"^^xsd:dateTime .')
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Container ensure + receipt PUT
# ---------------------------------------------------------------------------


def _css_put_headers(webid: str) -> dict:
    """Build CSS HTTP headers for authenticated PUT."""
    headers = {
        "Authorization": f"WebID {webid}",
        "Content-Type": "text/turtle",
    }
    if _CSS_IDENTIFIER_HOST:
        headers["Host"] = _CSS_IDENTIFIER_HOST
    return headers


def _pod_uri_to_connect_url(pod_uri: str) -> str:
    """Translate a pod URI from identifier-space to connect-space URL.

    pod_uri uses CSS_IDENTIFIER_URL; CSS_CONNECT_URL is the actual TCP target.
    """
    if _CSS_CONNECT_URL != _CSS_IDENTIFIER_URL and pod_uri.startswith(_CSS_IDENTIFIER_URL):
        return _CSS_CONNECT_URL + pod_uri[len(_CSS_IDENTIFIER_URL):]
    return pod_uri


def ensure_access_log_container(pod_uri: str) -> bool:
    """Ensure the access-log container exists in the pod.

    Issues a PUT to `{pod_uri}access-log/` — CSS creates the container if absent.
    200/201/204/405 are all acceptable (405 = container already exists on some CSS versions).

    Returns True if the container is ready; False on unexpected error.
    """
    container_uri = pod_uri.rstrip("/") + "/access-log/"
    connect_uri = _pod_uri_to_connect_url(container_uri)
    try:
        resp = requests.put(
            connect_uri,
            headers=_css_put_headers(_SPARQL_SKILL_WEBID),
            data=b"",
            timeout=10,
        )
        if resp.status_code in (200, 201, 204, 405):
            return True
        _log_warning("receipt.container.ensure_failed", {
            "container_uri": container_uri,
            "http_status": resp.status_code,
            "response_body": resp.text[:200],
        })
        # Attempt the receipt PUT anyway — CSS may auto-create intermediates.
        return False
    except requests.RequestException as exc:
        _log_warning("receipt.container.ensure_error", {
            "container_uri": container_uri,
            "error": str(exc),
        })
        return False


def write_access_receipt(
    agent_webid: str,
    query_type: str,
    pod_uri: str,
    consent_grant_uri: Optional[str],
    result_shape: str,
    named_graphs: list,
    timestamp: str,
) -> bool:
    """Write an access receipt to the data subject's pod.

    This function NEVER raises. All exceptions are caught and logged as warnings.
    The query result is returned by the caller regardless of this function's return value.

    Args:
        agent_webid:       WebID of the querying agent.
        query_type:        SPARQL template name.
        pod_uri:           Pod root URI whose data was accessed.
        consent_grant_uri: Authorizing consent grant URI, or None if denied.
        result_shape:      Human-readable description of result.
        named_graphs:      Named graph URIs that contributed.
        timestamp:         ISO-8601 query execution timestamp.

    Returns:
        True if receipt was successfully written (HTTP 200/201/204).
        False on any failure — the caller logs a warning and continues.
    """
    try:
        timestamp_slug = _make_timestamp_slug(timestamp)

        turtle_doc = build_receipt_turtle(
            agent_webid=agent_webid,
            query_type=query_type,
            pod_uri=pod_uri,
            consent_grant_uri=consent_grant_uri,
            result_shape=result_shape,
            named_graphs=named_graphs,
            timestamp=timestamp,
            timestamp_slug=timestamp_slug,
        )

        # Best-effort: ensure container exists (failure doesn't abort the PUT)
        ensure_access_log_container(pod_uri)

        receipt_path = f"access-log/{timestamp_slug}.ttl"
        receipt_uri = pod_uri.rstrip("/") + "/" + receipt_path
        connect_uri = _pod_uri_to_connect_url(receipt_uri)

        resp = requests.put(
            connect_uri,
            headers=_css_put_headers(_SPARQL_SKILL_WEBID),
            data=turtle_doc.encode("utf-8"),
            timeout=10,
        )

        if resp.status_code in (200, 201, 204, 205):
            # Log success at INFO level using the same structured format
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": SERVICE_NAME,
                "level": "INFO",
                "event": "receipt.write.success",
                "details": {
                    "pod_uri": pod_uri,
                    "receipt_uri": receipt_uri,
                    "agent_webid": agent_webid,
                    "query_type": query_type,
                    "http_status": resp.status_code,
                },
            }
            print(json.dumps(entry), flush=True)
            return True

        _log_warning("receipt.write.failed", {
            "pod_uri": pod_uri,
            "receipt_uri": receipt_uri,
            "http_status": resp.status_code,
            "response_body": resp.text[:200],
            "note": "query result unaffected",
        })
        return False

    except Exception as exc:  # noqa: BLE001
        _log_warning("receipt.write.exception", {
            "pod_uri": pod_uri,
            "agent_webid": agent_webid,
            "error": str(exc),
            "note": "query result unaffected",
        })
        return False


# ---------------------------------------------------------------------------
# Verification helper (AC2 — used in integration tests)
# ---------------------------------------------------------------------------


def verify_receipt_readable(pod_uri: str, timestamp_slug: str, reader_webid: str) -> bool:
    """Verify a receipt can be read by the given WebID.

    HTTP GET `{pod_uri}access-log/{timestamp_slug}.ttl` with reader's WebID credentials.

    Returns True if HTTP 200 and body is non-empty Turtle.
    Logs receipt content as structured JSON evidence.
    """
    receipt_uri = pod_uri.rstrip("/") + f"/access-log/{timestamp_slug}.ttl"
    connect_uri = _pod_uri_to_connect_url(receipt_uri)
    try:
        resp = requests.get(
            connect_uri,
            headers={
                "Authorization": f"WebID {reader_webid}",
                "Accept": "text/turtle",
                "Host": _CSS_IDENTIFIER_HOST,
            },
            timeout=10,
        )
        if resp.status_code == 200 and resp.text.strip():
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": SERVICE_NAME,
                "level": "INFO",
                "event": "receipt.verify.success",
                "details": {
                    "receipt_uri": receipt_uri,
                    "reader_webid": reader_webid,
                    "content_length": len(resp.text),
                    "receipt_content": resp.text[:500],
                },
            }
            print(json.dumps(entry), flush=True)
            return True
        _log_warning("receipt.verify.failed", {
            "receipt_uri": receipt_uri,
            "reader_webid": reader_webid,
            "http_status": resp.status_code,
        })
        return False
    except requests.RequestException as exc:
        _log_warning("receipt.verify.error", {
            "receipt_uri": receipt_uri,
            "reader_webid": reader_webid,
            "error": str(exc),
        })
        return False
