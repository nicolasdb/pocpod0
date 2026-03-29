"""SPARQL Query Skill handler for OpenClaw agents.

CLI invocation pattern (used by OpenClaw exec tool):
    python handler.py --query-type TEMPLATE_NAME \
                      --webid AGENT_WEBID \
                      --role AGENT_ROLE \
                      --params '{"param_name": "value", ...}'

Arguments:
    --query-type  Template name (student-progress, cross-context-query,
                  aggregate-anonymized, parental-view, transfer-profile)
    --webid       Agent WebID URI for CSS ACL validation
                  (e.g. http://localhost:3000/claire/profile/card#me)
    --role        Agent role (tutor, admin, regional, parental, student)
    --params      JSON object with template parameter name-value pairs

Output:
    Structured JSON log lines emitted first (timestamp, service, level, event, ...)
    Final result JSON printed last: {"status": "success|denied|error", ...}
    Exit code 0 on success, 1 on denied or error.

Environment variables (override defaults for Docker-internal execution):
    CSS_IDENTIFIER_URL   Identifier-space base URL for pod URI recognition and ACL path
                         computation. Must match CSS --baseUrl (default: http://localhost:3000).
                         On VPS: set to https://mypods.example.com
    CSS_CONNECT_URL    TCP target for CSS requests (default: http://localhost:3000)
                         On VPS/Docker: may differ from CSS_IDENTIFIER_URL
                         (e.g. http://community-solid-server:3000 inside Docker)
    CSS_IDENTIFIER_HOST  Host header to send to CSS (default: derived from CSS_IDENTIFIER_URL)
                         Required when CSS_CONNECT_URL differs from CSS_IDENTIFIER_URL.
    OXIGRAPH_URL       Oxigraph SPARQL endpoint base (default: http://localhost:7878)

Security:
    SEC-2: ACL check happens BEFORE any SPARQL execution.
    SEC-3: Template parameterization via parameterize.py — never string concat.
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Local imports: parameterize.py is in the same directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))
from parameterize import load_template, parameterize_query
from receipt import write_access_receipt

# ---------------------------------------------------------------------------
# Configuration (environment-overridable for Docker-internal execution)
# ---------------------------------------------------------------------------

# CSS: three-var model for identifier space vs. transport routing
#
# CSS_IDENTIFIER_URL  — the public base URL CSS uses for pod URIs (matches CSS --baseUrl).
#                       Used to recognise pod URIs in params and build ACL check paths.
#                       localhost dev: http://localhost:3000  (default)
#                       VPS:           https://mypods.example.com
#
# CSS_CONNECT_URL     — the TCP endpoint to actually connect to.
#                       Same as CSS_IDENTIFIER_URL unless routing differs (Docker-internal).
#                       Docker-internal: http://community-solid-server:3000
#
# CSS_IDENTIFIER_HOST — Host header to send when CSS_CONNECT_URL differs from
#                       CSS_IDENTIFIER_URL. CSS uses it to resolve resource identity.
#                       Defaults to the host part of CSS_IDENTIFIER_URL.
_CSS_IDENTIFIER_URL = os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000").rstrip("/")
_CSS_CONNECT_URL = os.environ.get("CSS_CONNECT_URL", _CSS_IDENTIFIER_URL).rstrip("/")
# Default Host header: host+port from the identifier URL
_CSS_IDENTIFIER_HOST = os.environ.get(
    "CSS_IDENTIFIER_HOST",
    _CSS_IDENTIFIER_URL.split("//", 1)[-1],  # strips scheme
)

# Oxigraph SPARQL query endpoint
_OXIGRAPH_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
_OXIGRAPH_QUERY_ENDPOINT = f"{_OXIGRAPH_URL}/query"

SERVICE_NAME = "sparql-query-skill"

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(
    level: str,
    event: str,
    agent: str,
    details: dict[str, Any],
    duration_ms: int = 0,
    result_count: int | None = None,
) -> None:
    """Emit a structured JSON log entry to stdout (captured by docker-compose).

    AC4 schema: timestamp, service, level, event, agent, duration_ms,
    result_count (top-level, success events only), details.
    """
    entry: dict[str, Any] = {
        "timestamp": _iso_now(),
        "service": SERVICE_NAME,
        "level": level,
        "event": event,
        "agent": agent,
        "duration_ms": duration_ms,
    }
    if result_count is not None:
        entry["result_count"] = result_count
    entry["details"] = details
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# ACL validation (SEC-2)
# ---------------------------------------------------------------------------


def _extract_pod_uris(params: dict[str, str]) -> list[str]:
    """Extract pod root URIs from skill parameters.

    Looks for URI-shaped values starting with CSS_IDENTIFIER_URL (the public pod base).
    Normalises profile card URIs to their pod root.

    Returns deduplicated list of pod root URIs for ACL checking.
    """
    css_base = _CSS_IDENTIFIER_URL  # from env — works on localhost and VPS
    pod_uris: list[str] = []
    for value in params.values():
        if not isinstance(value, str):
            continue
        if not value.startswith(css_base + "/"):
            continue
        # Normalise profile card to pod root
        if "/profile/card" in value:
            # http://localhost:3000/ayoub/profile/card#me → http://localhost:3000/ayoub/
            pod_root = value.split("/profile/card")[0] + "/"
        else:
            # For specific document URIs (.ttl), extract the pod root (first path segment)
            parts = value[len(css_base) + 1:].split("/")
            if parts:
                pod_root = css_base + "/" + parts[0] + "/"
            else:
                continue
        if pod_root not in pod_uris:
            pod_uris.append(pod_root)
    return pod_uris


def _check_acl(webid: str, pod_uris: list[str]) -> tuple[bool, str]:
    """Verify the agent WebID has read access to all target pod URIs.

    Makes a HEAD request to each pod root URI with the agent's WebID in the
    Authorization header. CSS WebACL enforces the check natively.

    Isolation note: uses CSS_CONNECT_URL (may be community-solid-server:3000)
    with Host header CSS_IDENTIFIER_HOST to work from within Docker while
    CSS identifier space uses CSS_IDENTIFIER_URL.

    Returns:
        (True, "ok") if access granted to all pods.
        (False, reason) if access denied to any pod.
    Raises:
        ValueError: if webid is not a valid URI (prevents header injection).
    """
    # P-5: validate WebID is a proper URI before embedding in Authorization header
    from urllib.parse import urlparse
    parsed = urlparse(webid)
    if not parsed.scheme or not parsed.netloc or "\n" in webid or "\r" in webid:
        raise ValueError(f"Invalid WebID URI: {webid!r}")

    for pod_uri in pod_uris:
        # Build the path relative to CSS identifier base, then append to connect URL
        # pod_uri = http://localhost:3000/ayoub/ → path = /ayoub/
        if pod_uri.startswith(_CSS_IDENTIFIER_URL):
            path = pod_uri[len(_CSS_IDENTIFIER_URL):]
        else:
            path = "/" + pod_uri.split("//", 1)[-1].split("/", 1)[-1]
        connect_url = _CSS_CONNECT_URL + path

        try:
            resp = requests.head(
                connect_url,
                headers={
                    "Authorization": f"WebID {webid}",
                    "Host": _CSS_IDENTIFIER_HOST,
                },
                timeout=5,
                allow_redirects=True,
            )
            if resp.status_code in (401, 403):
                return False, f"Access denied to {pod_uri} (HTTP {resp.status_code})"
            if resp.status_code >= 500:
                return False, f"CSS error for {pod_uri} (HTTP {resp.status_code})"
        except requests.RequestException as exc:
            return False, f"CSS connection error for {pod_uri}: {exc}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Oxigraph query execution
# ---------------------------------------------------------------------------


def _execute_query(sparql_query: str) -> tuple[list[dict], int]:
    """Execute a SPARQL SELECT query against Oxigraph via HTTP POST.

    Returns:
        (bindings_list, oxigraph_latency_ms)

    Raises:
        requests.HTTPError: on non-2xx response from Oxigraph.
        requests.RequestException: on connection failure.
    """
    t0 = time.monotonic()
    resp = requests.post(
        _OXIGRAPH_QUERY_ENDPOINT,
        data=sparql_query.encode("utf-8"),
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
        timeout=30,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp.raise_for_status()
    bindings = resp.json().get("results", {}).get("bindings", [])
    return bindings, latency_ms


# ---------------------------------------------------------------------------
# Result summarization (prevents token bloat when results fed to LLM)
# ---------------------------------------------------------------------------

_VERB_LABELS = {
    "http://adlnet.gov/expapi/verbs/attempted":   "attempted",
    "http://adlnet.gov/expapi/verbs/completed":   "completed",
    "http://adlnet.gov/expapi/verbs/passed":      "passed",
    "http://adlnet.gov/expapi/verbs/failed":      "failed",
    "http://adlnet.gov/expapi/verbs/scored":      "scored",
    "http://adlnet.gov/expapi/verbs/attended":    "attended",
    "http://adlnet.gov/expapi/verbs/progressed":  "progressed",
    "https://poc-pod0.edu/vocab/verb-mastered":      "mastered",
    "https://poc-pod0.edu/vocab/verb-struggled-with": "struggled",
    "https://poc-pod0.edu/vocab/verb-sought-help":    "sought-help",
    "https://poc-pod0.edu/vocab/verb-demonstrated":   "demonstrated",
}

_OBJECT_LABELS = {
    "https://poc-pod0.edu/vocab/activity-math-assessment-fractions": "math-assessment-fractions",
    "https://poc-pod0.edu/vocab/activity-gemeente-tutoring":         "gemeente-tutoring",
    "https://poc-pod0.edu/vocab/activity-khan-academy-session":      "khan-academy-self-study",
    "https://poc-pod0.edu/vocab/activity-robotics-workshop":         "robotics-workshop",
    "https://poc-pod0.edu/vocab/activity-school-transfer-nl":        "school-transfer-NL",
}


def _normalise_pod_uri(pod: str) -> str:
    """Normalise a pod URI to identifier-space (CSS_IDENTIFIER_URL).

    Oxigraph stores graph URIs under CSS_IDENTIFIER_URL. When callers pass
    pod URIs using CSS_CONNECT_URL (Docker-internal hostname), the prefix
    match would fail silently. Swapping the prefix here ensures grouping
    works regardless of which CSS URL variant the caller used.
    """
    pod = pod.rstrip("/") + "/"
    if _CSS_CONNECT_URL and _CSS_CONNECT_URL != _CSS_IDENTIFIER_URL:
        if pod.startswith(_CSS_CONNECT_URL.rstrip("/") + "/"):
            pod = _CSS_IDENTIFIER_URL.rstrip("/") + "/" + pod[len(_CSS_CONNECT_URL.rstrip("/")) + 1:]
    return pod


def _summarize_parental_view(bindings: list[dict], child_pods: list[str]) -> dict:
    """Build a unified parental view from multi-child bindings.

    Splits bindings by child pod prefix, produces per-child summaries, and
    detects structural gaps:
      - Activities with attendance but no scored outcome (platform gap)
      - Success flags that contradict the default 60% threshold (threshold signal)
      - Attendance anomalies: different session counts across children, or
        an activity present for only one child (unexpected asymmetry)

    Returns a dict with 'children' (list of per-child summaries) and 'gaps'.
    """
    # Normalise all pod URIs to identifier-space so prefix matching against
    # Oxigraph graph URIs works regardless of which CSS URL variant was passed.
    normalised_pods = [_normalise_pod_uri(p) for p in child_pods]

    # Group bindings by child pod (identifier-space keys)
    by_pod: dict[str, list[dict]] = {p: [] for p in normalised_pods}
    ungrouped: list[dict] = []
    for row in bindings:
        g = row.get("g", {}).get("value", "")
        matched = False
        for pod_key in by_pod:
            if g.startswith(pod_key):
                by_pod[pod_key].append(row)
                matched = True
                break
        if not matched:
            ungrouped.append(row)

    if ungrouped:
        import json as _json
        print(_json.dumps({
            "timestamp": _now_iso(),
            "service": SERVICE_NAME,
            "level": "WARN",
            "event": "sparql.parental_view.ungrouped_rows",
            "details": {"count": len(ungrouped), "sample_graph": ungrouped[0].get("g", {}).get("value", "")},
        }), flush=True)

    children = []
    all_gaps: list[dict] = []

    for pod_uri, rows in by_pod.items():
        child_summary = _summarize_bindings(rows, pod_uri)
        child_summary["pod_uri"] = pod_uri

        # Gap 1: attended with no score outcome
        attended_no_score = sum(
            1 for r in rows
            if "scaledScore" not in r
            and r.get("verb", {}).get("value", "").endswith("attended")
        )
        if attended_no_score > 0:
            child_summary["attended_no_outcome_count"] = attended_no_score

        # Gap 2: success=True with scaledScore < 0.6 (threshold signal)
        low_score_success = []
        for r in rows:
            score_val = r.get("scaledScore", {}).get("value") if r.get("scaledScore") else None
            success_val = r.get("success", {}).get("value") if r.get("success") else None
            obj_val = r.get("object", {}).get("value", "").rsplit("/", 1)[-1]
            if score_val and success_val == "true":
                try:
                    if float(score_val) < 0.6:
                        low_score_success.append({
                            "object": obj_val,
                            "score": float(score_val),
                        })
                except ValueError:
                    pass
        if low_score_success:
            child_summary["below_60_marked_success"] = low_score_success[:5]
            if len(low_score_success) > 5:
                child_summary["below_60_marked_success_truncated"] = True

        children.append(child_summary)

    # Gap: attendance anomalies across children for the same activity.
    # Flags two signals:
    #   - attendance_discrepancy: same activity, different session counts (≥2 children)
    #   - one_sided_activity: activity present for only one child (unexpected asymmetry)
    # The system surfaces unexpected patterns; it does not diagnose causes.
    activity_counts: dict[str, dict[str, int]] = {}
    for pod_uri, rows in by_pod.items():
        for r in rows:
            obj = r.get("object", {}).get("value", "").rsplit("/", 1)[-1]
            # Skip pure UUID/hash fragments (8-36 hex chars with dashes)
            if obj and not re.fullmatch(r"[0-9a-f\-]{8,36}", obj):
                if obj not in activity_counts:
                    activity_counts[obj] = {}
                activity_counts[obj][pod_uri] = activity_counts[obj].get(pod_uri, 0) + 1

    for activity, counts in activity_counts.items():
        child_labels = {p.split("/")[-2]: n for p, n in counts.items()}
        if len(counts) >= 2:
            values = list(counts.values())
            if max(values) != min(values):
                all_gaps.append({
                    "type": "attendance_discrepancy",
                    "activity": activity,
                    "counts_by_child": child_labels,
                })
        elif len(counts) == 1:
            # Activity visible for only one child — may indicate access asymmetry
            # or genuine participation difference. Surface for Fatima to interpret.
            all_gaps.append({
                "type": "one_sided_activity",
                "activity": activity,
                "counts_by_child": child_labels,
            })

    result: dict[str, Any] = {"children": children}
    if all_gaps:
        result["gaps"] = all_gaps
    return result


def _summarize_bindings(bindings: list[dict], pod_uri: str) -> dict:
    """Aggregate raw SPARQL bindings into a compact per-student summary.

    Returns a dict suitable for LLM consumption — far smaller than raw bindings.
    Preserves provenance (graph URIs) separately.
    """
    verb_counts: dict[str, int] = defaultdict(int)
    object_counts: dict[str, int] = defaultdict(int)
    scores: list[float] = []
    failures: list[dict] = []
    mastery_events: list[dict] = []
    graphs: set[str] = set()

    for row in bindings:
        g_val = row.get("g", {}).get("value", "")
        if g_val:
            graphs.add(g_val)

        verb_uri = row.get("verb", {}).get("value", "")
        verb_label = _VERB_LABELS.get(verb_uri, verb_uri.rsplit("/", 1)[-1])
        verb_counts[verb_label] += 1

        obj_uri = row.get("object", {}).get("value", "")
        obj_label = _OBJECT_LABELS.get(obj_uri, obj_uri.rsplit("/", 1)[-1])
        # Normalize label: strip trailing -hexhash suffixes (e.g. "dutch-language-726d2179" → "dutch-language")
        obj_label = re.sub(r"-[0-9a-f]{8}(-[0-9a-f]{4}){0,3}(-[0-9a-f]{12})?$", "", obj_label)
        # Skip pure UUID fragments
        if obj_label and not re.fullmatch(r"[0-9a-f\-]{8,36}", obj_label):
            object_counts[obj_label] += 1

        score_val = row.get("scaledScore", {}).get("value")
        success_val = row.get("success", {}).get("value")
        ts = row.get("timestamp", {}).get("value") or ""

        is_meaningful_label = bool(obj_label) and not re.fullmatch(r"[0-9a-f\-]{8,36}", obj_label)

        if score_val is not None:
            try:
                score = float(score_val)
                scores.append(score)
                if success_val == "false" and is_meaningful_label:
                    failures.append({"object": obj_label, "score": score, "timestamp": ts})
            except ValueError:
                pass

        if verb_label == "mastered" and is_meaningful_label:
            try:
                mastery_score = float(score_val) if score_val else None
            except ValueError:
                mastery_score = None
            mastery_events.append({"object": obj_label, "score": mastery_score, "timestamp": ts})

    summary: dict[str, Any] = {
        "pod_uri": pod_uri,
        "total_activities": len(bindings),
        "graphs_count": len(graphs),
        "activity_breakdown": dict(verb_counts),
        "content_breakdown": dict(object_counts),
    }

    if scores:
        summary["score_stats"] = {
            "count": len(scores),
            "avg": round(sum(scores) / len(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
        }

    if failures:
        # Keep top 5 most recent failures
        failures_sorted = sorted(failures, key=lambda x: x["timestamp"], reverse=True)
        summary["recent_failures"] = failures_sorted[:5]

    if mastery_events:
        summary["mastery_events"] = mastery_events[:5]

    return summary


# ---------------------------------------------------------------------------
# Aggregate result formatting (Story 3.6 — Isabelle policy view)
# ---------------------------------------------------------------------------


def _summarize_aggregate(bindings: list[dict]) -> dict:
    """Format aggregate SPARQL results for Isabelle's regional policy view.

    Converts one-row aggregate bindings into a structured summary with
    provenance narrative and structural anonymization guarantee (AC2, AC4).

    Returns a dict with participant_count, named_graph_count,
    scored_activity_count, score stats, provenance_narrative, and
    anonymization_guarantee.
    """
    if not bindings:
        return {
            "participant_count": 0,
            "named_graph_count": 0,
            "scored_activity_count": 0,
            "average_score": None,
            "min_score": None,
            "max_score": None,
            "provenance_narrative": (
                "No data found for the specified program. "
                "The program may have no attendance records in Oxigraph, "
                "or no participating students have scored activities."
            ),
            "anonymization_guarantee": (
                "No individual student data was accessed or returned. "
                "All results are aggregated at the program level."
            ),
        }

    row = bindings[0]

    def _int_val(key: str) -> int:
        v = row.get(key, {}).get("value")
        try:
            return int(float(v)) if v is not None else 0
        except (ValueError, TypeError):
            return 0

    def _float_val(key: str) -> float | None:
        v = row.get(key, {}).get("value")
        try:
            return round(float(v), 3) if v is not None else None
        except (ValueError, TypeError):
            return None

    participant_count = _int_val("participantCount")
    named_graph_count = _int_val("namedGraphCount")
    scored_activity_count = _int_val("scoredActivityCount")
    average_score = _float_val("averageScore")
    min_score = _float_val("minScore")
    max_score = _float_val("maxScore")

    provenance_narrative = (
        f"This aggregate is derived from {scored_activity_count} scored activities "
        f"across {named_graph_count} named graphs from {participant_count} student pods, "
        f"all with active regional-access consent grants."
    )

    return {
        "participant_count": participant_count,
        "named_graph_count": named_graph_count,
        "scored_activity_count": scored_activity_count,
        "average_score": average_score,
        "min_score": min_score,
        "max_score": max_score,
        "provenance_narrative": provenance_narrative,
        "anonymization_guarantee": (
            "No individual student data was accessed or returned. "
            "All results are aggregated at the program level."
        ),
    }


# ---------------------------------------------------------------------------
# Result shape description (for access receipt — BP-1)
# ---------------------------------------------------------------------------


def _build_result_shape(query_type: str, bindings: list[dict]) -> str:
    """Build a human-readable description of query result shape for receipt.

    No raw data — only metadata about what category of result was returned.
    """
    count = len(bindings)
    if count == 0:
        return f"{query_type}: no results returned"
    if query_type == "aggregate-anonymized":
        return f"aggregate count: {count} aggregate row(s), no individual records"
    if query_type == "parental-view":
        return f"parental-view: {count} activity record(s) across children, no raw scores"
    return f"{query_type}: {count} activity record(s), summarized"


# ---------------------------------------------------------------------------
# Main skill execution
# ---------------------------------------------------------------------------


def run_skill(
    query_type: str,
    webid: str,
    role: str,
    params: dict[str, str],
) -> dict[str, Any]:
    """Execute the SPARQL skill with ACL enforcement.

    Execution flow (see Dev Notes: Skill Flow):
      1. Extract pod URIs from params
      2. ACL check (SEC-2: must happen before any SPARQL)
      3. Load and parameterize .rq template (SEC-3: via parameterize.py)
      4. Execute parameterized query against Oxigraph
      5. Log execution with timing
      6. Return result with provenance

    Args:
        query_type: Template name (e.g. "student-progress")
        webid:      Agent WebID URI
        role:       Agent role string
        params:     Template parameter dict

    Returns:
        Result dict: {"status": "success|denied|error", ...}
    """
    t_start = time.monotonic()

    # Derive a short agent identifier for logging.
    # Callers may pass `agent_id` in params to override the WebID-derived name
    # (e.g. "fatima-parent" instead of "fatima" when the WebID is personal).
    agent_id = params.get("agent_id") or _agent_id_from_webid(webid)

    # ── Step 1: Extract pod URIs for ACL check ──────────────────────────────
    pod_uris = _extract_pod_uris(params)

    # ── Step 1.5: Aggregate-only enforcement for regional-policy role ────────
    # SEC-2 extension: role=regional-policy may ONLY execute aggregate templates.
    # Defense-in-depth: even if the LLM constructs a non-aggregate query, this blocks it.
    _AGGREGATE_ONLY_TEMPLATES = {"aggregate-anonymized"}
    if role in ("regional-policy",):
        if query_type not in _AGGREGATE_ONLY_TEMPLATES:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            reason = (
                f"Aggregate-only access: {agent_id} cannot execute individual-record queries. "
                f"Allowed templates: {sorted(_AGGREGATE_ONLY_TEMPLATES)}"
            )
            _log(
                "WARN",
                "sparql.query.denied",
                agent_id,
                {
                    "reason": reason,
                    "requested_template": f"{query_type}.rq",
                    "allowed_templates": [f"{t}.rq" for t in sorted(_AGGREGATE_ONLY_TEMPLATES)],
                    "acl_check": "denied",
                },
                duration_ms,
            )
            return {
                "status": "denied",
                "reason": reason,
                "agent": agent_id,
                "requested_template": f"{query_type}.rq",
                "allowed_templates": [f"{t}.rq" for t in sorted(_AGGREGATE_ONLY_TEMPLATES)],
            }

    # ── Step 2: ACL validation (must precede SPARQL, SEC-2) ──────────────────
    # P-1: templates that reference no pod URIs get an explicit "skipped" only
    # for aggregate-anonymized (community-scoped, non-personal). All personal-data
    # templates (student-progress, cross-context-query, parental-view,
    # transfer-profile) must have at least one pod URI in params or we error.
    _PERSONAL_TEMPLATES = {
        "student-progress", "cross-context-query", "parental-view", "transfer-profile"
    }
    if not pod_uris and query_type in _PERSONAL_TEMPLATES:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        msg = (
            f"Template '{query_type}' requires at least one pod URI in params "
            f"(must start with {_CSS_IDENTIFIER_URL}/). None found — refusing to "
            f"execute without ACL check (SEC-2)."
        )
        _log("ERROR", "sparql.query.error", agent_id,
             {"error": msg, "template": query_type, "acl_check": "skipped"}, duration_ms)
        return {"status": "error", "error": msg}

    if pod_uris:
        try:
            acl_ok, acl_reason = _check_acl(webid, pod_uris)
        except ValueError as exc:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            _log("ERROR", "sparql.query.error", agent_id,
                 {"error": str(exc), "template": query_type, "acl_check": "skipped"},
                 duration_ms)
            return {"status": "error", "error": str(exc)}
        if not acl_ok:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            denial = {
                "status": "denied",
                "reason": acl_reason,
                "agent": agent_id,
                "requested_resources": pod_uris,
            }
            # P-4: acl_check only takes values "passed"/"skipped" in the schema;
            # denial semantics are carried by event=sparql.query.denied
            _log(
                "WARN",
                "sparql.query.denied",
                agent_id,
                {
                    "template": query_type,
                    "reason": acl_reason,
                    "requested_resources": pod_uris,
                },
                duration_ms,
            )
            # BP-1: write a denial receipt to each target pod (non-blocking)
            _denial_timestamp = _iso_now()
            for _pod_uri in pod_uris:
                try:
                    write_access_receipt(
                        agent_webid=webid,
                        query_type=query_type,
                        pod_uri=_pod_uri,
                        consent_grant_uri=None,
                        result_shape="access denied",
                        named_graphs=[],
                        timestamp=_denial_timestamp,
                    )
                except Exception as _exc:  # noqa: BLE001
                    _log("WARN", "sparql.receipt.exception", agent_id,
                         {"error": str(_exc), "pod_uri": _pod_uri,
                          "note": "denial result unaffected"}, duration_ms)
            return denial
        acl_status = "passed"
    else:
        acl_status = "skipped"

    # ── Step 3: Load and parameterize template ────────────────────────────────
    # Normalize pod_uri to always have a trailing slash.
    # strstarts() prefix filter in SPARQL templates requires this to avoid
    # matching sibling pods (e.g. /ayoub/ must not match /ayoub-evil/).
    if "pod_uri" in params and not params["pod_uri"].endswith("/"):
        params = {**params, "pod_uri": params["pod_uri"] + "/"}
    try:
        template_content = load_template(query_type)
        parameterized_query = parameterize_query(template_content, params)
    except FileNotFoundError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "sparql.query.error", agent_id,
             {"error": str(exc), "template": query_type, "acl_check": acl_status},
             duration_ms)
        return {"status": "error", "error": str(exc)}
    except (ValueError, KeyError) as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "sparql.query.error", agent_id,
             {"error": str(exc), "template": query_type, "acl_check": acl_status},
             duration_ms)
        return {"status": "error", "error": str(exc)}

    # ── Step 3.5: Structural aggregate check for aggregate-only roles ────────
    # Belt-and-suspenders: verify the parameterized query uses SPARQL aggregate functions.
    # Detects non-aggregate queries that bypass Step 1.5 (e.g. template mutation).
    # NOTE: GROUP BY is NOT required — aggregate functions over the full result set are valid SPARQL.
    import re as _re
    _SPARQL_AGGREGATE_PATTERN = _re.compile(
        r'\b(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT|SAMPLE)\s*\(', _re.IGNORECASE
    )
    if role in ("regional-policy",) and not _SPARQL_AGGREGATE_PATTERN.search(parameterized_query):
        duration_ms = int((time.monotonic() - t_start) * 1000)
        reason = "Aggregate structure violation: query does not contain SPARQL aggregate functions (COUNT/AVG/MIN/MAX)"
        _log(
            "WARN",
            "sparql.query.denied",
            agent_id,
            {
                "reason": reason,
                "requested_template": f"{query_type}.rq",
                "allowed_templates": [f"{t}.rq" for t in sorted(_AGGREGATE_ONLY_TEMPLATES)],
                "acl_check": acl_status,
            },
            duration_ms,
        )
        return {"status": "denied", "reason": reason, "agent": agent_id}

    # ── Step 4: Execute against Oxigraph ─────────────────────────────────────
    try:
        bindings, oxigraph_latency_ms = _execute_query(parameterized_query)
    except requests.HTTPError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "sparql.query.error", agent_id,
             {"error": str(exc), "template": query_type, "acl_check": acl_status},
             duration_ms)
        return {"status": "error", "error": str(exc)}
    except requests.RequestException as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "sparql.query.error", agent_id,
             {"error": f"Oxigraph connection error: {exc}", "template": query_type,
              "acl_check": acl_status},
             duration_ms)
        return {"status": "error", "error": f"Oxigraph connection error: {exc}"}

    # ── Step 5: Extract provenance ────────────────────────────────────────────
    # Provenance = pod root URIs (not individual graph URIs — those can be 100s).
    # Pod root is derived by taking the first 3 path segments of each graph URI.
    # e.g. http://localhost:3000/ayoub/learning/course/uuid.ttl → http://localhost:3000/ayoub/
    _id_base = _CSS_IDENTIFIER_URL.rstrip("/")
    provenance_pods: set[str] = set()
    for row in bindings:
        for k, v in row.items():
            if k == "g" and v.get("type") == "uri":
                g = v["value"]
                if g.startswith(_id_base + "/"):
                    # Extract pod name: first path segment after base
                    rest = g[len(_id_base) + 1:]
                    pod_name = rest.split("/")[0]
                    if pod_name:
                        provenance_pods.add(f"{_id_base}/{pod_name}/")
    provenance = sorted(provenance_pods) or pod_uris

    duration_ms = int((time.monotonic() - t_start) * 1000)

    # ── Step 6: Log and return ────────────────────────────────────────────────
    # For aggregate queries, augment log with policy-specific fields (AC5).
    if query_type == "aggregate-anonymized":
        log_details: dict[str, Any] = {
            "template": f"{query_type}.rq",
            "query_type": "graph-only",
            "acl_check": acl_status,
            "oxigraph_latency_ms": oxigraph_latency_ms,
            "anonymization": "aggregate-only",
            "consent_verified": True,
        }
        # Annotate with aggregate counts if query returned results
        if bindings:
            row = bindings[0]
            for key, field in (
                ("participantCount", "participant_count"),
                ("namedGraphCount", "named_graph_count"),
                ("scoredActivityCount", "scored_activity_count"),
            ):
                v = row.get(key, {}).get("value")
                if v is not None:
                    try:
                        log_details[field] = int(float(v))
                    except (ValueError, TypeError):
                        pass
    else:
        log_details = {
            "template": f"{query_type}.rq",
            "acl_check": acl_status,
            "oxigraph_latency_ms": oxigraph_latency_ms,
        }

    _log(
        "INFO",
        "sparql.query.executed",
        agent_id,
        log_details,
        duration_ms,
        result_count=len(bindings),  # P-3: top-level field per AC4 schema
    )

    # Summarize results to prevent LLM token bloat.
    # aggregate-anonymized gets structured aggregate summary with provenance narrative.
    # parental-view gets per-child summaries with gap detection.
    # All other templates get single-pod summary.
    if query_type == "aggregate-anonymized":
        summary = _summarize_aggregate(bindings)
    elif query_type == "parental-view":
        # Require both child pod params; fallback to pod_uris only if neither is set.
        child_pods = []
        for key in ("child_pod_1", "child_pod_2"):
            val = params.get(key, "").strip()
            if val:
                child_pods.append(val if val.endswith("/") else val + "/")
        if len(child_pods) == 0:
            child_pods = pod_uris  # legacy fallback (no child_pod_* in params)
        elif len(child_pods) < 2:
            return {
                "status": "error",
                "error": "parental-view requires both child_pod_1 and child_pod_2 params",
            }
        summary = _summarize_parental_view(bindings, child_pods)
    else:
        pod_uri_param = params.get("pod_uri") or (pod_uris[0] if pod_uris else "")
        summary = _summarize_bindings(bindings, pod_uri_param)

    # ── Step 7: Write access receipt to pod (BP-1 Bidirectional Accountability) ─
    # Non-blocking side-effect: receipt write failure does NOT affect query result.
    # Consent grant URI: use ACL resource URI as proxy (PoC — no explicit grant model yet).
    # Timestamp captured once so all receipts from this query share the same instant.
    result_shape = _build_result_shape(query_type, bindings)
    named_graphs = sorted({
        row.get("g", {}).get("value", "")
        for row in bindings
        if row.get("g", {}).get("value")
    })
    _receipt_timestamp = _iso_now()
    _receipt_pods = provenance if provenance else pod_uris
    for receipt_pod_uri in _receipt_pods:
        consent_proxy = f"{receipt_pod_uri}.acl"
        try:
            write_access_receipt(
                agent_webid=webid,
                query_type=query_type,
                pod_uri=receipt_pod_uri,
                consent_grant_uri=consent_proxy,
                result_shape=result_shape,
                named_graphs=named_graphs,
                timestamp=_receipt_timestamp,
            )
        except Exception as _exc:  # noqa: BLE001
            _log("WARN", "sparql.receipt.exception", agent_id,
                 {"error": str(_exc), "pod_uri": receipt_pod_uri,
                  "note": "query result unaffected"}, duration_ms)

    return {
        "status": "success",
        "summary": summary,
        "provenance": provenance,
        "result_count": len(bindings),
    }


def _agent_id_from_webid(webid: str) -> str:
    """Extract a short agent identifier from a WebID URI.

    Examples:
        http://localhost:3000/claire/profile/card#me → "claire"
        http://localhost:3000/troll-adversary/profile/card#me → "troll-adversary"
    """
    if not webid:
        return "unknown"
    try:
        # Strip scheme+host, take first path segment
        path = webid.split("//", 1)[-1].split("/", 1)[-1]
        return path.split("/")[0]
    except (IndexError, AttributeError):
        return webid


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SPARQL Query Skill handler — ACL-validated queries against Oxigraph"
    )
    parser.add_argument(
        "--query-type",
        required=True,
        help="Template name (student-progress, cross-context-query, "
             "aggregate-anonymized, parental-view, transfer-profile)",
    )
    parser.add_argument(
        "--webid",
        required=True,
        help="Agent WebID URI (e.g. http://localhost:3000/claire/profile/card#me)",
    )
    parser.add_argument(
        "--role",
        required=True,
        help="Agent role (tutor, admin, regional, parental, student)",
    )
    parser.add_argument(
        "--params",
        required=True,
        help='JSON object of template parameters, e.g. \'{"student_uri": "..."}\'',
    )
    args = parser.parse_args()

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "error": f"Invalid --params JSON: {exc}"}))
        sys.exit(1)

    result = run_skill(
        query_type=args.query_type,
        webid=args.webid,
        role=args.role,
        params=params,
    )

    # Final result is the last JSON line output
    print(json.dumps(result))

    if result.get("status") in ("error", "denied"):
        sys.exit(1)


if __name__ == "__main__":
    main()
