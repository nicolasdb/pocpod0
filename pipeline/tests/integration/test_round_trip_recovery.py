"""Integration tests: round-trip xAPI recovery (Story 2.4).

Requires:
- Oxigraph running at http://localhost:7878 (populated by Story 2-3 pipeline)
- CSS running at http://localhost:3000 (populated by Story 2-2 pipeline)

Tests skip automatically when services are unreachable.

Actual personas in synthetic data:
  ayoub        → actor name "Ayoub"
  claire-student-1 → actor name "Alex"
  claire-student-2 → actor name "Jordan"
  fatima-child-1   → actor name "Sam"
  fatima-child-2   → actor name "Léa"
"""

import json
import time

import pytest
import requests

from pocpod0_pipeline.recover_xapi import (
    compare_xapi_statements,
    recover_xapi_batch,
    recover_xapi_from_triple,
)

OXIGRAPH_BASE = "http://localhost:7878"
CSS_BASE = "http://localhost:3000"
SCHEMA_GRAPH_URI = "https://poc-pod0.edu/vocab/schema"

# Mapping: pod name → expected actor account.name (WebID URL) in xAPI
# Actor uses account.name (WebID URL), not a human-readable name field
PERSONA_PODS = {
    "ayoub": f"{CSS_BASE}/ayoub/profile/card#me",
    "claire-student-1": f"{CSS_BASE}/claire-student-1/profile/card#me",
    "claire-student-2": f"{CSS_BASE}/claire-student-2/profile/card#me",
    "fatima-child-1": f"{CSS_BASE}/fatima-child-1/profile/card#me",
    "fatima-child-2": f"{CSS_BASE}/fatima-child-2/profile/card#me",
}


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _sparql_get(sparql: str) -> dict:
    resp = requests.get(
        f"{OXIGRAPH_BASE}/query",
        params={"query": sparql},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _oxigraph_reachable() -> bool:
    try:
        resp = requests.get(OXIGRAPH_BASE + "/", timeout=5)
        return resp.status_code < 500
    except Exception:
        return False


def _css_reachable() -> bool:
    try:
        resp = requests.head(CSS_BASE + "/", timeout=5)
        return resp.status_code < 500
    except Exception:
        return False


def _count_data_graphs() -> int:
    q = f"""
SELECT (COUNT(*) AS ?n) WHERE {{
  GRAPH ?g {{}}
  FILTER(?g != <{SCHEMA_GRAPH_URI}>)
}}
"""
    result = _sparql_get(q)
    return int(result["results"]["bindings"][0]["n"]["value"])


def _find_subject_for_pod(pod_name: str):
    """Find one statement subject URI from a given pod's named graphs."""
    pod_prefix = f"{CSS_BASE}/{pod_name}/"
    q = f"""
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?subject ?podResourceUri WHERE {{
  GRAPH ?g {{
    ?subject prov:wasDerivedFrom ?podResourceUri .
  }}
  FILTER(STRSTARTS(STR(?podResourceUri), "{pod_prefix}"))
}}
LIMIT 1
"""
    result = _sparql_get(q)
    bindings = result["results"]["bindings"]
    if not bindings:
        return None, None
    return bindings[0]["subject"]["value"], bindings[0]["podResourceUri"]["value"]


# ---------------------------------------------------------------------------
# Pytest skip decorators
# ---------------------------------------------------------------------------

requires_services = pytest.mark.skipif(
    not (_oxigraph_reachable() and _css_reachable()),
    reason="Oxigraph or CSS not reachable — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Test: single statement round-trip (AC1, AC2)
# ---------------------------------------------------------------------------

@requires_services
class TestSingleStatementRecovery:
    def test_single_statement_recovery(self):
        """Pick one known statement from ayoub pod, verify full round-trip."""
        subject_uri, pod_resource_uri = _find_subject_for_pod("ayoub")
        assert subject_uri is not None, "No statements found in ayoub pod — pipeline not loaded?"

        t0 = time.monotonic()
        result = recover_xapi_from_triple(subject_uri, OXIGRAPH_BASE, CSS_BASE)
        elapsed_ms = (time.monotonic() - t0) * 1000

        assert result["success"] is True, f"Recovery failed: {result['error']}"
        assert result["recovered_xapi"] is not None
        assert result["pod_resource_uri"] == pod_resource_uri

        xapi = result["recovered_xapi"]
        # Validate recovered xAPI has required fields
        assert "actor" in xapi, "Recovered xAPI missing 'actor'"
        assert "verb" in xapi, "Recovered xAPI missing 'verb'"
        assert "object" in xapi, "Recovered xAPI missing 'object'"

        # Performance: single recovery < 2s
        assert elapsed_ms < 2000, f"Recovery too slow: {elapsed_ms:.0f}ms"

    def test_recovered_xapi_valid(self):
        """Recovered statement passes structural xAPI validation."""
        subject_uri, _ = _find_subject_for_pod("ayoub")
        assert subject_uri is not None

        result = recover_xapi_from_triple(subject_uri, OXIGRAPH_BASE, CSS_BASE)
        assert result["success"] is True

        xapi = result["recovered_xapi"]
        # xAPI minimal validity: actor, verb, object all present
        assert isinstance(xapi.get("actor"), dict)
        assert isinstance(xapi.get("verb"), dict)
        assert isinstance(xapi.get("object"), dict)
        assert "id" in xapi.get("verb", {}), "verb must have 'id'"
        assert "id" in xapi.get("object", {}), "object must have 'id'"


# ---------------------------------------------------------------------------
# Test: recovery per persona (AC3)
# ---------------------------------------------------------------------------

@requires_services
class TestRecoveryPerPersona:
    @pytest.mark.parametrize("pod_name,expected_actor", list(PERSONA_PODS.items()))
    def test_recovery_per_persona(self, pod_name, expected_actor):
        """Recover at least one statement per persona and verify actor name."""
        subject_uri, _ = _find_subject_for_pod(pod_name)
        if subject_uri is None:
            pytest.skip(f"No statements for pod {pod_name}")

        result = recover_xapi_from_triple(subject_uri, OXIGRAPH_BASE, CSS_BASE)
        assert result["success"] is True, f"Recovery failed for {pod_name}: {result['error']}"

        actor = result["recovered_xapi"].get("actor", {})
        # Actor identity stored as account.name (WebID URL)
        actor_webid = actor.get("account", {}).get("name", "")
        assert actor_webid == expected_actor, (
            f"Pod {pod_name}: expected actor WebID '{expected_actor}', got '{actor_webid}'"
        )


# ---------------------------------------------------------------------------
# Test: batch recovery (AC1, AC2, AC4)
# ---------------------------------------------------------------------------

@requires_services
class TestBatchRecovery:
    def test_batch_recovery_50_statements(self):
        """Recover a random sample of 50 statements, verify all succeed."""
        results = recover_xapi_batch(OXIGRAPH_BASE, CSS_BASE, limit=50)

        assert len(results) > 0, "No results returned from batch recovery"
        passed = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        # All should succeed in a healthy environment
        assert len(passed) == len(results), (
            f"{len(failed)} recoveries failed:\n"
            + "\n".join(f"  {r['subject_uri']}: {r['error']}" for r in failed[:5])
        )

    def test_batch_recovery_produces_valid_xapi(self):
        """All recovered statements in batch are structurally valid xAPI."""
        results = recover_xapi_batch(OXIGRAPH_BASE, CSS_BASE, limit=20)
        assert len(results) > 0

        for r in results:
            if not r["success"]:
                continue
            xapi = r["recovered_xapi"]
            assert "actor" in xapi, f"Missing 'actor' in {r['subject_uri']}"
            assert "verb" in xapi, f"Missing 'verb' in {r['subject_uri']}"
            assert "object" in xapi, f"Missing 'object' in {r['subject_uri']}"


# ---------------------------------------------------------------------------
# Test: comparison utility catches differences (AC2)
# ---------------------------------------------------------------------------

@requires_services
class TestComparisonWithRealData:
    def test_comparison_detects_differences(self):
        """Recover a statement, modify it, verify compare_xapi_statements catches it."""
        subject_uri, _ = _find_subject_for_pod("ayoub")
        assert subject_uri is not None

        result = recover_xapi_from_triple(subject_uri, OXIGRAPH_BASE, CSS_BASE)
        assert result["success"] is True

        original = result["recovered_xapi"]
        modified = json.loads(json.dumps(original))  # deep copy
        modified["verb"]["id"] = "http://adlnet.gov/expapi/verbs/MODIFIED"

        cmp_result = compare_xapi_statements(original, modified)
        assert cmp_result["match"] is False
        assert any("verb.id" in d for d in cmp_result["differences"])

    def test_recovered_matches_original_from_synthetic(self):
        """Recovered statement matches original from data/synthetic/ for ayoub."""
        import json
        from pathlib import Path
        try:
            from pocpod0_pipeline.utils import repo_root
        except ImportError:
            pytest.skip("pocpod0_pipeline.utils.repo_root not available")

        synthetic_path = repo_root() / "data" / "synthetic" / "scenarios" / "ayoub.json"
        assert synthetic_path.exists(), f"Synthetic file not found: {synthetic_path}"

        with open(synthetic_path) as f:
            raw = json.load(f)
        originals = raw if isinstance(raw, list) else raw.get("statements", [raw])
        assert len(originals) > 0, "No statements in ayoub.json"

        # Use first statement whose ID we can find in Oxigraph
        subject_uri, _ = _find_subject_for_pod("ayoub")
        assert subject_uri is not None

        result = recover_xapi_from_triple(subject_uri, OXIGRAPH_BASE, CSS_BASE)
        assert result["success"] is True

        recovered = result["recovered_xapi"]
        recovered_id = recovered.get("id")

        # Find the matching original
        original = next((s for s in originals if s.get("id") == recovered_id), None)
        if original is None:
            pytest.skip(f"Statement {recovered_id} not found in synthetic data (may be troll data)")

        # Strip internal routing key before comparison
        clean_original = {k: v for k, v in original.items() if k != "_pocpod0_pod"}
        cmp_result = compare_xapi_statements(clean_original, recovered)
        assert cmp_result["match"] is True, (
            f"Round-trip mismatch for {recovered_id}:\n"
            + "\n".join(f"  {d}" for d in cmp_result["differences"])
        )
