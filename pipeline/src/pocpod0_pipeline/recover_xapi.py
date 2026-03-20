"""Round-trip xAPI recovery from Oxigraph + CSS.

Recovery path:
  1. Query Oxigraph SPARQL for ?subject prov:wasDerivedFrom ?podResourceUri
  2. HTTP GET the Pod resource from CSS (with provisioner WebID auth)
  3. Parse Turtle, extract pocpod0:originalXapiJson literal
  4. Parse and return original xAPI JSON dict

Structured JSON logging to stdout for all recovery attempts.
"""

import json
import os
from typing import Dict, List, Optional

import requests
from rdflib import Graph, Namespace, URIRef

from pocpod0_pipeline.utils import CSS_BASE_URL, PROVISIONER_WEBID, log_event

# ---------------------------------------------------------------------------
# Namespaces / constants
# ---------------------------------------------------------------------------

POCPOD0 = Namespace("https://poc-pod0.edu/vocab/")
OXIGRAPH_BASE_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")

_PROV_QUERY = """
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?podResourceUri WHERE {{
  GRAPH ?g {{
    <{subject_uri}> prov:wasDerivedFrom ?podResourceUri .
  }}
}}
LIMIT 1
"""

_BATCH_QUERY = """
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT DISTINCT ?subject ?podResourceUri WHERE {{
  GRAPH ?g {{
    ?subject prov:wasDerivedFrom ?podResourceUri .
  }}
}}
LIMIT {limit}
"""


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _sparql_select(oxigraph_url: str, query: str) -> List[Dict]:
    """Execute a SPARQL SELECT and return bindings as list of dicts."""
    resp = requests.get(
        f"{oxigraph_url}/query",
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", {}).get("bindings", [])


def _fetch_pod_resource(pod_resource_uri: str) -> Optional[str]:
    """Fetch Turtle from CSS Pod resource with provisioner auth. Returns text or None."""
    resp = requests.get(
        pod_resource_uri,
        headers={
            "Authorization": f"WebID {PROVISIONER_WEBID}",
            "Accept": "text/turtle",
        },
        timeout=30,
    )
    if resp.status_code in (404, 410):
        return None
    if resp.status_code in (401, 403):
        raise requests.HTTPError(
            f"CSS denied access to {pod_resource_uri}: HTTP {resp.status_code}",
            response=resp,
        )
    resp.raise_for_status()
    return resp.text


def _extract_original_xapi(turtle_content: str, pod_resource_uri: str) -> Optional[str]:
    """Parse Turtle and extract pocpod0:originalXapiJson literal. Returns raw JSON string or None."""
    g = Graph()
    g.parse(data=turtle_content, format="turtle")
    subject = URIRef(pod_resource_uri)
    for _s, _p, o in g.triples((subject, POCPOD0.originalXapiJson, None)):
        return str(o)
    # Fallback: accept any subject (handles cases where subject URI differs from resource URI)
    for _s, _p, o in g.triples((None, POCPOD0.originalXapiJson, None)):
        return str(o)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recover_xapi_from_triple(
    subject_uri: str,
    oxigraph_url: str = OXIGRAPH_BASE_URL,
    css_base_url: str = CSS_BASE_URL,  # unused — pod URI comes from Oxigraph provenance link
) -> dict:
    """Recover original xAPI statement for a given RDF subject URI.

    Returns:
        {
            "subject_uri": str,
            "pod_resource_uri": str | None,
            "recovered_xapi": dict | None,
            "success": bool,
            "error": str | None,
        }
    """
    result: dict = {
        "subject_uri": subject_uri,
        "pod_resource_uri": None,
        "recovered_xapi": None,
        "success": False,
        "error": None,
    }

    # Step 1: Find provenance link in Oxigraph
    try:
        bindings = _sparql_select(oxigraph_url, _PROV_QUERY.format(subject_uri=subject_uri))
    except Exception as exc:
        result["error"] = f"SPARQL query failed: {exc}"
        log_event("round_trip.recovery.failed", "error", {"subject_uri": subject_uri, "error": result["error"]})
        return result

    if not bindings:
        result["error"] = "No prov:wasDerivedFrom triple found for subject"
        log_event("round_trip.recovery.no_provenance", "warning", {"subject_uri": subject_uri})
        return result

    pod_resource_uri = bindings[0]["podResourceUri"]["value"]
    result["pod_resource_uri"] = pod_resource_uri

    # Step 2: Fetch Pod resource from CSS
    try:
        turtle_content = _fetch_pod_resource(pod_resource_uri)
    except Exception as exc:
        result["error"] = f"CSS fetch failed: {exc}"
        log_event("round_trip.recovery.failed", "error", {"subject_uri": subject_uri, "pod_resource_uri": pod_resource_uri, "error": result["error"]})
        return result

    if turtle_content is None:
        result["error"] = "Pod resource returned 404"
        log_event("round_trip.recovery.not_found", "warning", {"subject_uri": subject_uri, "pod_resource_uri": pod_resource_uri})
        return result

    # Step 3: Extract originalXapiJson literal
    try:
        raw_json = _extract_original_xapi(turtle_content, pod_resource_uri)
    except Exception as exc:
        result["error"] = f"Turtle parse error: {exc}"
        log_event("round_trip.recovery.parse_error", "error", {"subject_uri": subject_uri, "pod_resource_uri": pod_resource_uri, "error": result["error"]})
        return result

    if raw_json is None:
        result["error"] = "pocpod0:originalXapiJson not found in Turtle"
        log_event("round_trip.recovery.missing_literal", "warning", {"subject_uri": subject_uri, "pod_resource_uri": pod_resource_uri})
        return result

    # Step 4: Parse JSON
    try:
        xapi_dict = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        result["error"] = f"JSON parse error: {exc}"
        log_event("round_trip.recovery.json_error", "error", {"subject_uri": subject_uri, "error": result["error"]})
        return result

    result["recovered_xapi"] = xapi_dict
    result["success"] = True
    log_event("round_trip.recovery.success", "info", {"subject_uri": subject_uri, "pod_resource_uri": pod_resource_uri})
    return result


def recover_xapi_batch(
    oxigraph_url: str = OXIGRAPH_BASE_URL,
    css_base_url: str = CSS_BASE_URL,
    limit: int = 100,
) -> List[dict]:
    """Recover xAPI for a sample of subjects with provenance links in Oxigraph.

    Returns list of recovery result dicts (same shape as recover_xapi_from_triple).
    """
    try:
        bindings = _sparql_select(oxigraph_url, _BATCH_QUERY.format(limit=limit))
    except Exception as exc:
        log_event("round_trip.batch.sparql_failed", "error", {"error": str(exc)})
        return []

    results = []
    for b in bindings:
        subject_uri = b["subject"]["value"]
        result = recover_xapi_from_triple(subject_uri, oxigraph_url, css_base_url)
        results.append(result)

    passed = sum(1 for r in results if r["success"])
    log_event(
        "round_trip.batch.complete",
        "info",
        {"total": len(results), "passed": passed, "failed": len(results) - passed},
    )
    return results


# ---------------------------------------------------------------------------
# Comparison utility
# ---------------------------------------------------------------------------

def compare_xapi_statements(original: dict, recovered: dict) -> dict:
    """Semantically compare two xAPI statement dicts.

    Returns:
        {"match": bool, "differences": list[str]}
    """
    differences = []

    def _compare_field(path: str, a, b):
        if a != b:
            differences.append(f"{path}: expected {a!r}, got {b!r}")

    # Actor
    orig_actor = original.get("actor", {})
    rec_actor = recovered.get("actor", {})
    _compare_field("actor.name", orig_actor.get("name"), rec_actor.get("name"))
    _compare_field("actor.mbox", orig_actor.get("mbox"), rec_actor.get("mbox"))
    orig_acct = orig_actor.get("account", {})
    rec_acct = rec_actor.get("account", {})
    _compare_field("actor.account.homePage", orig_acct.get("homePage"), rec_acct.get("homePage"))
    _compare_field("actor.account.name", orig_acct.get("name"), rec_acct.get("name"))

    # Verb
    orig_verb = original.get("verb", {})
    rec_verb = recovered.get("verb", {})
    _compare_field("verb.id", orig_verb.get("id"), rec_verb.get("id"))
    orig_verb_display = orig_verb.get("display", {})
    rec_verb_display = rec_verb.get("display", {})
    for lang in set(list(orig_verb_display.keys()) + list(rec_verb_display.keys())):
        _compare_field(f"verb.display.{lang}", orig_verb_display.get(lang), rec_verb_display.get(lang))

    # Object
    orig_obj = original.get("object", {})
    rec_obj = recovered.get("object", {})
    _compare_field("object.id", orig_obj.get("id"), rec_obj.get("id"))
    orig_def = orig_obj.get("definition", {})
    rec_def = rec_obj.get("definition", {})
    _compare_field("object.definition.type", orig_def.get("type"), rec_def.get("type"))
    # Compare definition.name (multilingual dict)
    orig_def_name = orig_def.get("name", {})
    rec_def_name = rec_def.get("name", {})
    if orig_def_name != rec_def_name:
        differences.append(f"object.definition.name: expected {orig_def_name!r}, got {rec_def_name!r}")

    # Result — check presence explicitly to distinguish missing vs empty
    orig_result = original.get("result")
    rec_result = recovered.get("result")
    if orig_result is not None or rec_result is not None:
        orig_result = orig_result or {}
        rec_result = rec_result or {}
        _compare_field("result.success", orig_result.get("success"), rec_result.get("success"))
        _compare_field("result.completion", orig_result.get("completion"), rec_result.get("completion"))
        # Score: handle float precision
        orig_score = orig_result.get("score", {})
        rec_score = rec_result.get("score", {})
        for k in set(list(orig_score.keys()) + list(rec_score.keys())):
            ov = orig_score.get(k)
            rv = rec_score.get(k)
            if isinstance(ov, float) and isinstance(rv, float):
                if abs(ov - rv) > 1e-9:
                    differences.append(f"result.score.{k}: expected {ov!r}, got {rv!r}")
            else:
                _compare_field(f"result.score.{k}", ov, rv)

    # Context
    orig_ctx = original.get("context", {})
    rec_ctx = recovered.get("context", {})
    if orig_ctx or rec_ctx:
        orig_ctx_acts = orig_ctx.get("contextActivities", {})
        rec_ctx_acts = rec_ctx.get("contextActivities", {})
        if orig_ctx_acts != rec_ctx_acts:
            differences.append(f"context.contextActivities: expected {orig_ctx_acts!r}, got {rec_ctx_acts!r}")
        orig_ext = orig_ctx.get("extensions", {})
        rec_ext = rec_ctx.get("extensions", {})
        if orig_ext != rec_ext:
            differences.append(f"context.extensions: expected {orig_ext!r}, got {rec_ext!r}")

    # Timestamp
    _compare_field("timestamp", original.get("timestamp"), recovered.get("timestamp"))

    return {"match": len(differences) == 0, "differences": differences}
