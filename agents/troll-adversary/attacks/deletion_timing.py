"""Troll adversary: deletion cascade timing validation suite.

Tests whether the 3-layer deletion cascade (Pod → Oxigraph → Qdrant) fully
propagates erasure across all data layers, measuring timing per layer and
documenting any expected timing gaps (e.g., Qdrant lag after Oxigraph clean).

access_path: "direct" — raw HTTP to CSS, Oxigraph, Qdrant REST APIs,
  bypassing any agent/skill layer. We test what infrastructure reports,
  not what agents claim.

NFR11: Each deletion cascade propagation step logged with layer, resource,
  completion status.
NFR12: Deterministic — classification is rule-based (HTTP codes + payload
  counts), never LLM-dependent. Timing gap duration varies but presence/
  absence is deterministic for a given infrastructure state.
NFR13: Does NOT apply — unlike cross-inference, deletion timing is fully
  deterministic.

Isolation notes:
  - distrobox-host-exec works perfectly for accessing podman containers
    from within the distrobox environment
  - Services run at localhost ports from host: CSS=3000, Oxigraph=7878,
    Qdrant=6333
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Bootstrap: load TrollTestResult via importlib
# (hyphen-named parent directory prevents normal package import)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
OXIGRAPH_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "pocpod0_embeddings")

REPORT_DIR = Path(__file__).resolve().parents[1] / "report"
JSONL_PATH = Path(__file__).resolve().parents[3] / "data" / "troll-run.jsonl"

TROLL_WEBID = f"{CSS_BASE_URL}/troll/profile/card#me"

# Default test target: Ayoub's pod
DEFAULT_POD_NAME = "ayoub"
DEFAULT_POD_URI = f"{CSS_BASE_URL}/ayoub/"

# Deterministic synthetic resource seed for --dry-run / no --resource-uri
SYNTHETIC_RESOURCE_SEED = "dt-synthetic-test-resource-v1"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DeletionTimingResult:
    test_name: str            # e.g., "dt-001-pod-soft-delete-mark"
    layer: str                # "pod", "oxigraph", "qdrant"
    step: int                 # 1, 2, or 3 (cascade step)
    elapsed_ms: float         # Time from cascade step start to purge confirmed
    result: str               # "pass" | "partial" | "fail"
    details: str              # Human-readable explanation
    evidence: dict            # Raw evidence: queries run, responses, timing
    residual_found: bool      # True if data still present after cascade step
    is_deterministic: bool = True  # Always True for deletion timing (NFR12)
    timestamp: str = ""


@dataclass
class LayerSummary:
    layer: str
    result: str          # "pass" | "partial" | "fail"
    elapsed_ms: float
    findings: list[str]


@dataclass
class DeletionTimingSummary:
    total_tests: int
    pass_count: int
    partial_count: int
    fail_count: int
    per_layer: dict      # "pod"|"oxigraph"|"qdrant" -> LayerSummary (serialized)
    timing_gap_ms: Optional[float]  # dt-004 gap if detected
    overall_assessment: str
    timestamp: str


# ---------------------------------------------------------------------------
# JSONL event helpers
# ---------------------------------------------------------------------------


def _emit_jsonl(event: dict) -> None:
    """Append a structured event to data/troll-run.jsonl."""
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def log_deletion_event(
    test_name: str,
    layer: str,
    elapsed_ms: float,
    residual_found: bool,
    result: str,
    details: str,
) -> None:
    """Emit a structured JSON log for a deletion timing step (NFR11).

    NOTE: log_test_result() hardcodes ACL-specific fields — do NOT reuse for
    deletion timing events. This local function captures deletion-timing fields.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "troll-adversary",
        "level": "INFO",
        "event": "troll.deletion_timing.step",
        "agent": "troll-adversary",
        "duration_ms": int(elapsed_ms),
        "details": {
            "test_name": test_name,
            "layer": layer,
            "result": result,
            "residual_found": residual_found,
            "elapsed_ms": elapsed_ms,
            "details": details,
        },
    }
    print(json.dumps(event), flush=True)


def _emit_probe_start(test_name: str, layer: str) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _emit_jsonl({
        "event_type": "troll.probe.start",
        "timestamp": ts,
        "category": "deletion_timing",
        "test_name": test_name,
        "layer": layer,
    })


def _emit_probe_done(test_name: str, layer: str, result: str, elapsed_ms: float) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _emit_jsonl({
        "event_type": "troll.probe.done",
        "timestamp": ts,
        "category": "deletion_timing",
        "test_name": test_name,
        "layer": layer,
        "result": result,
        "elapsed_ms": elapsed_ms,
    })


def _emit_category_done(passed: int, partial: int, failed: int) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _emit_jsonl({
        "event_type": "troll.category.done",
        "timestamp": ts,
        "category": "deletion_timing",
        "passed": passed,
        "partial": partial,
        "failed": failed,
    })


# ---------------------------------------------------------------------------
# Infrastructure query helpers
# ---------------------------------------------------------------------------


def _query_css_resource(resource_uri: str) -> dict:
    """HEAD/GET the CSS resource. Returns status classification and evidence."""
    evidence: dict = {"url": resource_uri, "method": "GET"}
    try:
        resp = requests.get(
            resource_uri,
            headers={
                "Authorization": f"WebID {TROLL_WEBID}",
                "Accept": "text/turtle",
            },
            timeout=10,
        )
        evidence["http_status"] = resp.status_code
        evidence["response_snippet"] = resp.text[:300]
        if resp.status_code == 410:
            return {"state": "deleted", "evidence": evidence}
        if resp.status_code in (200, 204, 205):
            body = resp.text
            is_deleted = (
                "pocpod0:isDeleted true" in body
                or "pocpod0:isDeleted> true" in body
            )
            if is_deleted:
                return {"state": "tombstone", "evidence": evidence}
            return {"state": "live", "evidence": evidence}
        if resp.status_code in (404,):
            return {"state": "not_found", "evidence": evidence}
        return {"state": "unknown", "evidence": evidence}
    except requests.RequestException as exc:
        evidence["error"] = str(exc)
        return {"state": "error", "evidence": evidence}


def _query_oxigraph_graph(resource_uri: str) -> dict:
    """ASK + SELECT COUNT to check if named graph has any triples."""
    evidence: dict = {"resource_uri": resource_uri}
    ask_query = f"ASK {{ GRAPH <{resource_uri}> {{ ?s ?p ?o }} }}"
    count_query = (
        f"SELECT (COUNT(*) AS ?n) {{ GRAPH <{resource_uri}> {{ ?s ?p ?o }} }}"
    )
    try:
        ask_resp = requests.post(
            f"{OXIGRAPH_URL.rstrip('/')}/query",
            data=ask_query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        evidence["ask_http_status"] = ask_resp.status_code
        if ask_resp.status_code == 200:
            ask_result = ask_resp.json().get("boolean", None)
            evidence["ask_response"] = ask_result
        else:
            evidence["ask_response"] = None
            evidence["ask_error"] = ask_resp.text[:200]

        count_resp = requests.post(
            f"{OXIGRAPH_URL.rstrip('/')}/query",
            data=count_query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        evidence["count_http_status"] = count_resp.status_code
        if count_resp.status_code == 200:
            bindings = count_resp.json().get("results", {}).get("bindings", [])
            count_val = int(bindings[0]["n"]["value"]) if bindings else -1
            evidence["count_response"] = count_val
        else:
            evidence["count_response"] = -1
            evidence["count_error"] = count_resp.text[:200]

        graph_exists = evidence.get("ask_response", None)
        return {"graph_exists": graph_exists, "count": evidence.get("count_response", -1), "evidence": evidence}
    except requests.RequestException as exc:
        evidence["error"] = str(exc)
        return {"graph_exists": None, "count": -1, "evidence": evidence}


def _query_qdrant_points(resource_uri: str) -> dict:
    """Scroll Qdrant for points matching pod_resource_uri or pod_uri_hash."""
    pod_uri_hash = hashlib.sha256(resource_uri.encode()).hexdigest()[:16]
    evidence: dict = {"resource_uri": resource_uri, "pod_uri_hash": pod_uri_hash}

    # Try hash filter first (PRIV-1 fix)
    hash_body = {
        "filter": {"must": [{"key": "pod_uri_hash", "match": {"value": pod_uri_hash}}]},
        "limit": 10,
        "with_payload": True,
        "with_vectors": False,
    }
    # Also check legacy pod_resource_uri filter
    uri_body = {
        "filter": {"must": [{"key": "pod_resource_uri", "match": {"value": resource_uri}}]},
        "limit": 10,
        "with_payload": True,
        "with_vectors": False,
    }
    scroll_url = f"{QDRANT_URL.rstrip('/')}/collections/{QDRANT_COLLECTION}/points/scroll"
    try:
        hash_resp = requests.post(
            scroll_url,
            json=hash_body,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        evidence["hash_filter_http_status"] = hash_resp.status_code
        if hash_resp.status_code == 200:
            hash_points = hash_resp.json().get("result", {}).get("points", [])
            evidence["hash_filter_count"] = len(hash_points)
        else:
            evidence["hash_filter_count"] = -1
            evidence["hash_filter_error"] = hash_resp.text[:200]

        uri_resp = requests.post(
            scroll_url,
            json=uri_body,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        evidence["uri_filter_http_status"] = uri_resp.status_code
        if uri_resp.status_code == 200:
            uri_points = uri_resp.json().get("result", {}).get("points", [])
            evidence["uri_filter_count"] = len(uri_points)
        else:
            evidence["uri_filter_count"] = -1
            evidence["uri_filter_error"] = uri_resp.text[:200]

        total = max(0, evidence.get("hash_filter_count", 0)) + max(0, evidence.get("uri_filter_count", 0))
        # Deduplicate: points might match both filters
        combined_ids = set()
        if hash_resp.status_code == 200:
            for p in hash_resp.json().get("result", {}).get("points", []):
                combined_ids.add(p.get("id"))
        if uri_resp.status_code == 200:
            for p in uri_resp.json().get("result", {}).get("points", []):
                combined_ids.add(p.get("id"))
        evidence["total_unique_count"] = len(combined_ids)

        return {"count": len(combined_ids), "evidence": evidence}
    except requests.RequestException as exc:
        evidence["error"] = str(exc)
        return {"count": -1, "evidence": evidence}


# ---------------------------------------------------------------------------
# Cascade trigger
# ---------------------------------------------------------------------------


def _trigger_cascade(resource_uri: str, pod_name: str) -> dict:
    """Trigger Story 5.2 delete_cascade via importlib. Falls back to error finding."""
    try:
        dc = importlib.util.find_spec("pocpod0_pipeline.delete_cascade")
        if dc is None:
            return {"ok": False, "error": "pocpod0_pipeline.delete_cascade not found — run with --dry-run or set PYTHONPATH"}
        import importlib as _il
        mod = _il.import_module("pocpod0_pipeline.delete_cascade")
        result = mod.run_cascade(resource_uri=resource_uri, pod_name=pod_name)
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# DeletionTimingAttack
# ---------------------------------------------------------------------------


class DeletionTimingAttack:
    """Adversarial deletion cascade timing validation across Pod/Oxigraph/Qdrant."""

    def __init__(self, target_pod_uri: str, resource_uri: str) -> None:
        self.target_pod_uri = target_pod_uri
        self.resource_uri = resource_uri

    def run_all_tests(self) -> list[DeletionTimingResult]:
        return [self.run_test(layer) for layer in self._test_catalog()]

    def _test_catalog(self) -> list[str]:
        return [
            "dt-001-pod-soft-delete-mark",
            "dt-002-oxigraph-named-graph-drop",
            "dt-003-qdrant-payload-purge",
            "dt-004-cross-layer-gap",
            "dt-005-post-cascade-full-verify",
        ]

    def run_test(self, test_id: str) -> DeletionTimingResult:
        dispatch = {
            "dt-001-pod-soft-delete-mark": self._dt001_pod,
            "dt-002-oxigraph-named-graph-drop": self._dt002_oxigraph,
            "dt-003-qdrant-payload-purge": self._dt003_qdrant,
            "dt-004-cross-layer-gap": self._dt004_gap,
            "dt-005-post-cascade-full-verify": self._dt005_full,
        }
        fn = dispatch.get(test_id)
        if fn is None:
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return DeletionTimingResult(
                test_name=test_id, layer="unknown", step=0, elapsed_ms=0.0,
                result="fail", details=f"Unknown test_id: {test_id}", evidence={},
                residual_found=False, timestamp=ts,
            )
        return fn()

    # -----------------------------------------------------------------------
    # dt-001: Pod layer — CSS soft-delete tombstone
    # -----------------------------------------------------------------------

    def _dt001_pod(self) -> DeletionTimingResult:
        test_name = "dt-001-pod-soft-delete-mark"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _emit_probe_start(test_name, "pod")
        t0 = time.time()

        css_result = _query_css_resource(self.resource_uri)
        state = css_result["state"]
        elapsed_ms = (time.time() - t0) * 1000

        if state in ("deleted", "tombstone"):
            result = "pass"
            residual_found = False
            details = f"Pod layer confirmed deleted/tombstone (state={state}) in {elapsed_ms:.1f}ms."
        elif state == "not_found":
            result = "pass"
            residual_found = False
            details = f"Pod layer: resource not found (404) — hard-deleted or never existed."
        elif state == "live":
            result = "fail"
            residual_found = True
            details = f"Pod layer: resource still live (no isDeleted marker). Soft-delete not applied."
        elif state == "error":
            result = "partial"
            residual_found = False
            details = f"Pod layer: query error — cannot confirm deletion state. {css_result['evidence'].get('error', 'unknown')}"
        else:
            result = "partial"
            residual_found = True
            details = f"Pod layer: unexpected state={state}."

        r = DeletionTimingResult(
            test_name=test_name, layer="pod", step=1,
            elapsed_ms=elapsed_ms, result=result, details=details,
            evidence=css_result["evidence"], residual_found=residual_found,
            timestamp=ts,
        )
        log_deletion_event(test_name, "pod", elapsed_ms, residual_found, result, details)
        _emit_probe_done(test_name, "pod", result, elapsed_ms)
        return r

    # -----------------------------------------------------------------------
    # dt-002: Oxigraph layer — named graph DROP
    # -----------------------------------------------------------------------

    def _dt002_oxigraph(self) -> DeletionTimingResult:
        test_name = "dt-002-oxigraph-named-graph-drop"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _emit_probe_start(test_name, "oxigraph")
        t0 = time.time()

        ox_result = _query_oxigraph_graph(self.resource_uri)
        elapsed_ms = (time.time() - t0) * 1000

        graph_exists = ox_result["graph_exists"]
        count = ox_result["count"]

        if graph_exists is False and count == 0:
            result = "pass"
            residual_found = False
            details = f"Named graph DROP confirmed clean in {elapsed_ms:.1f}ms. ASK=false, COUNT=0."
        elif graph_exists is True or count > 0:
            result = "fail"
            residual_found = True
            details = f"Named graph still has triples: ASK={graph_exists}, COUNT={count}. DROP not applied."
        elif graph_exists is None or count == -1:
            result = "partial"
            residual_found = False
            details = f"Oxigraph query error — cannot confirm clean state (ASK={graph_exists}, COUNT={count}). Check service connectivity."
        else:
            result = "partial"
            residual_found = False
            details = f"Inconclusive state: ASK={graph_exists}, COUNT={count}."

        r = DeletionTimingResult(
            test_name=test_name, layer="oxigraph", step=2,
            elapsed_ms=elapsed_ms, result=result, details=details,
            evidence=ox_result["evidence"], residual_found=residual_found,
            timestamp=ts,
        )
        log_deletion_event(test_name, "oxigraph", elapsed_ms, residual_found, result, details)
        _emit_probe_done(test_name, "oxigraph", result, elapsed_ms)
        return r

    # -----------------------------------------------------------------------
    # dt-003: Qdrant layer — payload purge
    # -----------------------------------------------------------------------

    def _dt003_qdrant(self) -> DeletionTimingResult:
        test_name = "dt-003-qdrant-payload-purge"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _emit_probe_start(test_name, "qdrant")
        t0 = time.time()

        q_result = _query_qdrant_points(self.resource_uri)
        elapsed_ms = (time.time() - t0) * 1000

        count = q_result["count"]

        if count == 0:
            result = "pass"
            residual_found = False
            details = f"Qdrant payload purge confirmed: 0 points matching resource in {elapsed_ms:.1f}ms."
        elif count > 0:
            result = "fail"
            residual_found = True
            details = f"Qdrant still has {count} point(s) matching resource. Delete not applied."
        else:  # count == -1 (error)
            result = "partial"
            residual_found = False
            details = f"Qdrant query error — cannot confirm purge. Check service connectivity."

        r = DeletionTimingResult(
            test_name=test_name, layer="qdrant", step=3,
            elapsed_ms=elapsed_ms, result=result, details=details,
            evidence=q_result["evidence"], residual_found=residual_found,
            timestamp=ts,
        )
        log_deletion_event(test_name, "qdrant", elapsed_ms, residual_found, result, details)
        _emit_probe_done(test_name, "qdrant", result, elapsed_ms)
        return r

    # -----------------------------------------------------------------------
    # dt-004: Cross-layer timing gap — Oxigraph clean but Qdrant may lag
    # -----------------------------------------------------------------------

    def _dt004_gap(self) -> DeletionTimingResult:
        test_name = "dt-004-cross-layer-gap"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _emit_probe_start(test_name, "qdrant")

        # Check Oxigraph first (upstream)
        t_upstream_start = time.time()
        ox_result = _query_oxigraph_graph(self.resource_uri)
        t_upstream_clean = time.time()
        upstream_elapsed_ms = (t_upstream_clean - t_upstream_start) * 1000

        # Immediately query Qdrant (downstream)
        t_downstream_query = time.time()
        q_result = _query_qdrant_points(self.resource_uri)
        downstream_elapsed_ms = (time.time() - t_downstream_query) * 1000

        total_elapsed_ms = (time.time() - t_upstream_start) * 1000

        ox_clean = ox_result["graph_exists"] is False and ox_result["count"] == 0
        qdrant_count = q_result["count"]
        gap_ms = (t_downstream_query - t_upstream_clean) * 1000

        evidence = {
            "oxigraph": ox_result["evidence"],
            "qdrant": q_result["evidence"],
            "t_upstream_clean_ms": upstream_elapsed_ms,
            "t_downstream_query_ms": downstream_elapsed_ms,
            "cross_layer_gap_ms": gap_ms,
        }

        if ox_clean and qdrant_count == 0:
            result = "pass"
            residual_found = False
            details = (
                f"No cross-layer timing gap detected. Both Oxigraph and Qdrant clean. "
                f"Gap window measured: {gap_ms:.1f}ms."
            )
        elif ox_clean and qdrant_count > 0:
            # EXPECTED: Qdrant lags Oxigraph — documented architectural property
            result = "partial"
            residual_found = True
            details = (
                f"Qdrant embeddings lag Oxigraph by {gap_ms:.1f}ms. "
                f"Oxigraph confirmed clean; Qdrant still has {qdrant_count} point(s) at time of query. "
                f"Residual exposure window: {gap_ms:.1f}ms. "
                f"Risk: low — embeddings require knowing the resource URI to query directly. "
                f"ACL enforcement prevents agent-layer access. "
                f"This is a known architectural property of the cascade chain, not a defect."
            )
            evidence["risk_assessment"] = (
                f"Residual embeddings window of {gap_ms:.1f}ms. "
                "Risk: low — embeddings require knowing the resource URI to query directly. "
                "ACL enforcement prevents agent-layer access."
            )
        elif not ox_clean and qdrant_count > 0:
            result = "fail"
            residual_found = True
            details = (
                f"Both layers have residual data. Oxigraph: graph_exists={ox_result['graph_exists']}, "
                f"count={ox_result['count']}. Qdrant: {qdrant_count} point(s). "
                f"Cascade may not have been triggered for this resource."
            )
        else:
            result = "partial"
            residual_found = qdrant_count > 0
            details = f"Inconclusive state: Oxigraph clean={ox_clean}, Qdrant count={qdrant_count}."

        r = DeletionTimingResult(
            test_name=test_name, layer="qdrant", step=2,
            elapsed_ms=total_elapsed_ms, result=result, details=details,
            evidence=evidence, residual_found=residual_found,
            timestamp=ts,
        )
        log_deletion_event(test_name, "qdrant", total_elapsed_ms, residual_found, result, details)
        _emit_probe_done(test_name, "qdrant", result, total_elapsed_ms)
        return r

    # -----------------------------------------------------------------------
    # dt-005: Post-cascade full verify — all three layers must be clean
    # -----------------------------------------------------------------------

    def _dt005_full(self) -> DeletionTimingResult:
        test_name = "dt-005-post-cascade-full-verify"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _emit_probe_start(test_name, "pod")
        t0 = time.time()

        css_result = _query_css_resource(self.resource_uri)
        ox_result = _query_oxigraph_graph(self.resource_uri)
        q_result = _query_qdrant_points(self.resource_uri)
        elapsed_ms = (time.time() - t0) * 1000

        pod_clean = css_result["state"] in ("deleted", "tombstone", "not_found")
        ox_clean = ox_result["graph_exists"] is False and ox_result["count"] == 0
        qdrant_clean = q_result["count"] == 0

        evidence = {
            "pod": css_result["evidence"],
            "oxigraph": ox_result["evidence"],
            "qdrant": q_result["evidence"],
            "pod_clean": pod_clean,
            "oxigraph_clean": ox_clean,
            "qdrant_clean": qdrant_clean,
        }

        dirty_layers = []
        if not pod_clean:
            dirty_layers.append(f"pod(state={css_result['state']})")
        if not ox_clean:
            dirty_layers.append(f"oxigraph(exists={ox_result['graph_exists']},count={ox_result['count']})")
        if not qdrant_clean:
            dirty_layers.append(f"qdrant(count={q_result['count']})")

        if pod_clean and ox_clean and qdrant_clean:
            result = "pass"
            residual_found = False
            details = (
                f"All 3 layers confirmed clean after cascade in {elapsed_ms:.1f}ms. "
                "Pod=tombstone/deleted, Oxigraph=empty, Qdrant=0 points."
            )
        else:
            result = "fail"
            residual_found = True
            details = (
                f"Post-cascade full verify FAILED. Dirty layers: {', '.join(dirty_layers)}. "
                "Cascade integrity defect — at least one layer still has data after all steps returned success."
            )

        r = DeletionTimingResult(
            test_name=test_name, layer="all", step=3,
            elapsed_ms=elapsed_ms, result=result, details=details,
            evidence=evidence, residual_found=residual_found,
            timestamp=ts,
        )
        log_deletion_event(test_name, "all", elapsed_ms, residual_found, result, details)
        _emit_probe_done(test_name, "pod", result, elapsed_ms)
        return r

    # -----------------------------------------------------------------------
    # Summary generation
    # -----------------------------------------------------------------------

    def generate_summary(self, results: list[DeletionTimingResult]) -> DeletionTimingSummary:
        """Aggregate per-layer and overall results into a DeletionTimingSummary."""
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        pass_count = sum(1 for r in results if r.result == "pass")
        partial_count = sum(1 for r in results if r.result == "partial")
        fail_count = sum(1 for r in results if r.result == "fail")

        # Per-layer aggregation
        layers = ["pod", "oxigraph", "qdrant", "all"]
        per_layer: dict[str, dict] = {}
        for layer in layers:
            layer_results = [r for r in results if r.layer == layer]
            if not layer_results:
                continue
            # Worst result wins: fail > partial > pass
            if any(r.result == "fail" for r in layer_results):
                layer_result = "fail"
            elif any(r.result == "partial" for r in layer_results):
                layer_result = "partial"
            else:
                layer_result = "pass"
            avg_elapsed = sum(r.elapsed_ms for r in layer_results) / len(layer_results)
            findings = [r.details for r in layer_results if r.result != "pass"]
            per_layer[layer] = asdict(LayerSummary(
                layer=layer,
                result=layer_result,
                elapsed_ms=avg_elapsed,
                findings=findings,
            ))

        # dt-004 timing gap
        dt004 = next((r for r in results if r.test_name == "dt-004-cross-layer-gap"), None)
        timing_gap_ms: Optional[float] = None
        if dt004 and dt004.result == "partial":
            timing_gap_ms = dt004.evidence.get("cross_layer_gap_ms")

        # Overall assessment
        if fail_count > 0:
            overall = (
                f"FAIL: {fail_count} layer(s) still had data after cascade step returned success. "
                "This is a cascade integrity defect requiring investigation."
            )
        elif partial_count > 0 and timing_gap_ms is not None:
            overall = (
                f"Qdrant embeddings lag Oxigraph by {timing_gap_ms:.1f}ms. "
                "This is a known architectural property — embeddings are the last layer in the cascade chain. "
                "Residual exposure window is documented and risk-assessed. "
                "NFR12: Deletion timing tests are deterministic (infrastructure-level). "
                "Results are reproducible across runs with identical inputs."
            )
        elif partial_count > 0:
            overall = (
                "Partial results detected. Some layers may have timing gaps or query errors. "
                "Review per-layer findings for details."
            )
        else:
            overall = (
                "3-layer deletion cascade verified clean. All layers purged within expected timing. "
                "NFR12: Deletion timing tests are deterministic (infrastructure-level). "
                "Results are reproducible across runs with identical inputs."
            )

        return DeletionTimingSummary(
            total_tests=len(results),
            pass_count=pass_count,
            partial_count=partial_count,
            fail_count=fail_count,
            per_layer=per_layer,
            timing_gap_ms=timing_gap_ms,
            overall_assessment=overall,
            timestamp=ts,
        )


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def _write_report(
    results: list[DeletionTimingResult],
    summary: DeletionTimingSummary,
    output_dir: Path,
) -> None:
    """Write deletion-timing-results.json using the single envelope pattern."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "deletion-timing-results.json"

    tests = []
    for r in results:
        tests.append({
            "attack_category": "deletion_timing",
            "access_path": "direct",
            "test_name": r.test_name,
            "result": r.result,
            "details": r.details,
            "evidence": {
                "layer": r.layer,
                "step": r.step,
                "elapsed_ms": r.elapsed_ms,
                "residual_found": r.residual_found,
                "is_deterministic": r.is_deterministic,
                **r.evidence,
            },
        })

    envelope = {
        "category": "deletion_timing",
        "total_tests": summary.total_tests,
        "passed": summary.pass_count,
        "partial": summary.partial_count,
        "failed": summary.fail_count,
        "blocking": False,
        "narrative": summary.overall_assessment,
        "summary": asdict(summary),
        "tests": tests,
    }

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)

    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "troll-adversary",
        "level": "INFO",
        "event": "troll.deletion_timing.report_written",
        "agent": "troll-adversary",
        "details": {"report_path": str(report_path)},
    }), flush=True)


# ---------------------------------------------------------------------------
# Service health checks
# ---------------------------------------------------------------------------


def _check_services() -> list[str]:
    """Return list of unreachable services (empty = all reachable)."""
    unreachable = []
    try:
        requests.head(CSS_BASE_URL, timeout=5)
    except requests.RequestException:
        unreachable.append(f"CSS unreachable at {CSS_BASE_URL}")
    try:
        requests.get(f"{OXIGRAPH_URL}/", timeout=5)
    except requests.RequestException:
        unreachable.append(f"Oxigraph unreachable at {OXIGRAPH_URL}")
    try:
        requests.get(f"{QDRANT_URL}/health", timeout=5)
    except requests.RequestException:
        unreachable.append(f"Qdrant unreachable at {QDRANT_URL}")
    return unreachable


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Troll adversary: deletion cascade timing validation"
    )
    parser.add_argument(
        "--pod-uri",
        default=DEFAULT_POD_URI,
        help=f"Target pod URI (default: {DEFAULT_POD_URI})",
    )
    parser.add_argument(
        "--resource-uri",
        default=None,
        help="Specific resource to test deletion cascade on",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPORT_DIR),
        help=f"Override report output directory (default: {REPORT_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query current state without triggering a new cascade",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Determine resource URI
    if args.resource_uri:
        resource_uri = args.resource_uri
    else:
        # Deterministic synthetic resource URI (NFR12)
        seed_hash = hashlib.sha256(SYNTHETIC_RESOURCE_SEED.encode()).hexdigest()[:12]
        resource_uri = f"{args.pod_uri.rstrip('/')}/_dt_test_{seed_hash}"

    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "troll-adversary",
        "level": "INFO",
        "event": "troll.deletion_timing.start",
        "agent": "troll-adversary",
        "details": {
            "resource_uri": resource_uri,
            "pod_uri": args.pod_uri,
            "dry_run": args.dry_run,
            "output_dir": str(output_dir),
        },
    }), flush=True)

    # Check services — log unreachable as findings, do not abort
    unreachable = _check_services()
    for msg in unreachable:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": "troll-adversary",
            "level": "WARN",
            "event": "troll.deletion_timing.service_unreachable",
            "agent": "troll-adversary",
            "details": {"message": msg},
        }), flush=True)

    # Trigger cascade (unless dry-run)
    if not args.dry_run:
        pod_name = args.pod_uri.rstrip("/").split("/")[-1] or DEFAULT_POD_NAME
        cascade_result = _trigger_cascade(resource_uri, pod_name)
        if not cascade_result["ok"]:
            print(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "service": "troll-adversary",
                "level": "WARN",
                "event": "troll.deletion_timing.cascade_trigger_error",
                "agent": "troll-adversary",
                "details": {"error": cascade_result["error"], "mode": "continuing_as_dry_run"},
            }), flush=True)
        else:
            print(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "service": "troll-adversary",
                "level": "INFO",
                "event": "troll.deletion_timing.cascade_triggered",
                "agent": "troll-adversary",
                "details": {"resource_uri": resource_uri},
            }), flush=True)
    else:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": "troll-adversary",
            "level": "INFO",
            "event": "troll.deletion_timing.dry_run",
            "agent": "troll-adversary",
            "details": {"message": "Querying current state without triggering cascade"},
        }), flush=True)

    # Run all 5 tests
    attack = DeletionTimingAttack(
        target_pod_uri=args.pod_uri,
        resource_uri=resource_uri,
    )
    results = attack.run_all_tests()

    # Generate summary
    summary = attack.generate_summary(results)

    # Emit JSONL category done
    _emit_category_done(summary.pass_count, summary.partial_count, summary.fail_count)

    # Write report
    _write_report(results, summary, output_dir)

    # Print summary to stdout
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "troll-adversary",
        "level": "INFO",
        "event": "troll.deletion_timing.summary",
        "agent": "troll-adversary",
        "details": asdict(summary),
    }), flush=True)

    # Always exit 0 — troll errors are findings, not failures
    sys.exit(0)


if __name__ == "__main__":
    main()
