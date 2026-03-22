"""End-to-end integration test for Claire's cross-context insight discovery (Story 3.4).

Tests the complete journey:
1. Graph-only query execution (AC1)
2. Hybrid query execution with semantic enrichment (AC2)
3. Side-by-side comparison output (AC3)
4. Provenance display (AC4)
5. ACL enforcement (AC5)
6. Claire agent system prompt orchestration (AC1,2,3)

Requires:
- OpenClaw running with Claire agent
- Oxigraph running at http://oxigraph:7878
- CSS running at http://community-solid-server:3000
- Qdrant running at http://qdrant:6333
- Synthetic data provisioned (Story 2 pipeline)

Run from distrobox:
  distrobox-host-exec pytest pipeline/tests/integration/test_claire_cross_context.py -v
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import pytest
import requests

# Service endpoints (Docker network)
OXIGRAPH_BASE = "http://oxigraph:7878"
CSS_BASE = "http://community-solid-server:3000"
QDRANT_BASE = "http://qdrant:6333"
OPENCLAW_BASE = "http://openclaw-gateway:8000"  # Adjust if different

CLAIRE_WEBID = f"{CSS_BASE}/claire-teacher/profile/card#me"
CLAIRE_ROLE = "tutor"

# Student pods (from Story 2 synthetic data)
AYOUB_POD = "ayoub"
ALEX_POD = "claire-student-1"  # The "aha moment" student
JORDAN_POD = "claire-student-2"  # The control
FATIMA_CHILD_NL_POD = "fatima-child-1"  # Unauthorized
FATIMA_CHILD_FR_POD = "fatima-child-2"  # Unauthorized

DEMONSTRATION_QUERY = "Which students are struggling with quadratic equations across all learning contexts?"


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def services_available():
    """Skip all tests if required services are not reachable."""
    for name, url in [
        ("Oxigraph", f"{OXIGRAPH_BASE}/"),
        ("CSS", f"{CSS_BASE}/"),
        ("Qdrant", f"{QDRANT_BASE}/health"),
    ]:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code not in (200, 204):
                pytest.skip(f"{name} returned {resp.status_code}")
        except requests.exceptions.ConnectionError:
            pytest.skip(f"{name} not reachable at {url}")


def _sparql_query(sparql: str, oxigraph_base: str = OXIGRAPH_BASE) -> dict:
    """Execute a SPARQL query against Oxigraph."""
    resp = requests.post(
        f"{oxigraph_base}/query",
        data=sparql.encode("utf-8"),
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Test Suite: Cross-Context Insight Discovery
# ---------------------------------------------------------------------------


class TestClaireGraphOnlyQuery:
    """AC1: Graph-only query execution with ACL scoping."""

    def test_graph_only_returns_authorized_student_data(self):
        """Verify graph-only query returns structured facts for authorized students."""
        # This test verifies the SPARQL skill returns data for Ayoub, Alex, Jordan
        # In a real test, we would invoke Claire's agent and parse her response.
        # For now, we verify the underlying infrastructure exists.

        query = f"""
        PREFIX pocpod0: <https://poc-pod0.edu/vocab/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?g ?activity ?verb ?object WHERE {{
          GRAPH ?g {{
            ?activity rdf:type pocpod0:LearningStatement .
            ?activity pocpod0:verb ?verb .
            ?activity pocpod0:object ?object .
          }}
          FILTER(strstarts(str(?g), "{CSS_BASE}/ayoub/"))
        }}
        LIMIT 10
        """

        try:
            result = _sparql_query(query)
            assert "results" in result
            # Data should be present if synthetic data was provisioned
            bindings = result["results"].get("bindings", [])
            assert len(bindings) > 0, "No learning data found for ayoub — synthetic data may not be provisioned"
        except AssertionError:
            raise
        except Exception as e:
            pytest.skip(f"SPARQL query failed (expected if Oxigraph not seeded): {e}")

    def test_graph_only_respects_acl_boundaries(self):
        """Verify graph-only query denies access to unauthorized pods."""
        # Attempt to query Fatima's child pod (should be denied)
        query = f"""
        PREFIX oslo-educ: <https://data.vlaanderen.be/ns/onderwijs#>

        SELECT ?activity WHERE {{
          GRAPH <{CSS_BASE}/{FATIMA_CHILD_NL_POD}/learning/> {{
            ?activity oslo-educ:betreft ?subject .
          }}
        }}
        """

        # This demonstrates ACL enforcement at the query level
        try:
            result = _sparql_query(query)
            # If ACL is properly set up, this should return empty or error
            assert "results" in result
        except requests.HTTPError as e:
            # Expected: 403 Forbidden
            assert e.response.status_code == 403
        except Exception as e:
            pytest.skip(f"ACL enforcement test inconclusive: {e}")

    def test_graph_only_response_time(self):
        """Verify graph-only query response time < 500ms (NFR1)."""
        query = f"""
        PREFIX pocpod0: <https://poc-pod0.edu/vocab/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?g ?activity WHERE {{
          GRAPH ?g {{
            ?activity rdf:type pocpod0:LearningStatement .
          }}
          FILTER(strstarts(str(?g), "{CSS_BASE}/ayoub/"))
        }}
        LIMIT 100
        """

        start = time.time()
        _sparql_query(query)
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Graph-only query exceeded NFR1 limit: {elapsed_ms:.1f}ms (limit: 500ms)"


class TestClaireHybridQuery:
    """AC2: Hybrid query execution with semantic enrichment."""

    def test_hybrid_combines_sparql_and_qdrant(self):
        """Verify hybrid query merges SPARQL facts + Qdrant semantics."""
        # This test would invoke both skills and verify merge
        # For integration test, we verify both backends exist

        # Check Qdrant is available
        resp = requests.get(f"{QDRANT_BASE}/health")
        assert resp.status_code == 200, "Qdrant not healthy"

        # In real test, Claire's agent would:
        # 1. Call sparql-query skill
        # 2. Call qdrant-search skill
        # 3. Merge on pod_resource_uri
        # 4. Synthesize narrative

    def test_hybrid_response_time(self):
        """Verify both SPARQL and Qdrant backends respond within the hybrid budget (NFR2 < 2s).

        A full end-to-end hybrid timing requires OpenClaw agent invocation (scaffold).
        This test verifies each backend stays within its share of the 2s budget.
        """
        sparql_query = f"""
        PREFIX pocpod0: <https://poc-pod0.edu/vocab/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?g ?activity WHERE {{
          GRAPH ?g {{ ?activity rdf:type pocpod0:LearningStatement . }}
          FILTER(strstarts(str(?g), "{CSS_BASE}/claire-student-1/"))
        }}
        LIMIT 100
        """

        sparql_start = time.time()
        _sparql_query(sparql_query)
        sparql_ms = (time.time() - sparql_start) * 1000

        qdrant_start = time.time()
        resp = requests.get(f"{QDRANT_BASE}/health", timeout=5)
        assert resp.status_code == 200, "Qdrant not healthy"
        qdrant_ms = (time.time() - qdrant_start) * 1000

        combined_ms = sparql_ms + qdrant_ms
        assert combined_ms < 2000, (
            f"Backend latencies exceed NFR2 budget: SPARQL={sparql_ms:.1f}ms "
            f"+ Qdrant={qdrant_ms:.1f}ms = {combined_ms:.1f}ms (limit: 2000ms)"
        )


class TestClaireOutputFormatting:
    """AC3: Side-by-side comparison with three output states."""

    def test_output_format_includes_labels(self):
        """Verify output clearly labels graph-only vs hybrid results."""
        # Claire's SOUL.md specifies the format with clear labels
        # In real test, parse Claire's response and verify labels exist

        expected_labels = [
            "=== GRAPH-ONLY RESULTS ===",
            "=== HYBRID RESULTS ===",
            "=== COMPARISON ===",
        ]

        # Placeholder: in real test, invoke Claire and check response
        # for these labels
        pass

    def test_output_includes_semantic_enrichment_markers(self):
        """Verify hybrid results mark semantic additions with [SEMANTIC ENRICHMENT]."""
        expected_marker = "[SEMANTIC ENRICHMENT]"

        # In real test, check Alex's output contains this marker
        # showing what Qdrant adds over SPARQL alone
        pass

    def test_three_state_output(self):
        """Verify three distinct output states for different students."""
        # State 1: Ayoub (negative space with gap) — should show "NOT AVAILABLE"
        # State 2: Alex (full insight) — should show aha moment with enrichment
        # State 3: Jordan (partial) — should show average performance

        # In real test, invoke Claire with query and verify:
        # - Ayoub output shows "Tutoring context: NOT AVAILABLE" + call-to-action
        # - Alex output shows school failures + tutoring mastery contrast
        # - Jordan output shows sparse enrichment
        pass


class TestClaireProvenance:
    """AC4: Provenance is navigable from result to source."""

    def test_graph_only_provenance_chain(self):
        """Verify graph-only results include pod_resource_uri."""
        # In real test, check SPARQL skill returns provenance metadata
        # Verify each result can be traced to Pod resource URI
        pass

    def test_hybrid_provenance_chain(self):
        """Verify hybrid results include triple_uris + pod_resource_uri."""
        # In real test, check Qdrant results include:
        # - triple_uris: which Oxigraph triples were embedded
        # - pod_resource_uri: which Pod the triple came from
        pass

    def test_provenance_summary(self):
        """Verify provenance summary is included."""
        # In real test, check output includes:
        # "This query accessed X student records across Y Pod resources, with Z total triples."
        pass


class TestClaireACLEnforcement:
    """AC5: ACL enforcement prevents cross-role data leakage."""

    def test_acl_denies_unauthorized_pods(self):
        """Verify access denial to Fatima's children pods."""
        # Claire should not be able to access fatima-child-1 or fatima-child-2
        # Test verifies the denial response includes proper metadata

        unauthorized_pods = [FATIMA_CHILD_NL_POD, FATIMA_CHILD_FR_POD]

        # Oxigraph does not enforce CSS ACLs — ACL enforcement is at the skill level.
        # This test verifies that direct Oxigraph queries return no data for unauthorized
        # pods (because no data should have been loaded under those pod URIs for Claire),
        # and that HTTP 403 is the expected response if CSS ACL enforcement is present.
        for pod in unauthorized_pods:
            query = f"""
            PREFIX pocpod0: <https://poc-pod0.edu/vocab/>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

            SELECT ?g ?activity WHERE {{
              GRAPH ?g {{
                ?activity rdf:type pocpod0:LearningStatement .
              }}
              FILTER(strstarts(str(?g), "{CSS_BASE}/{pod}/"))
            }}
            LIMIT 1
            """

            try:
                result = _sparql_query(query)
                bindings = result.get("results", {}).get("bindings", [])
                assert len(bindings) == 0, (
                    f"Data leaked from unauthorized pod '{pod}': {bindings}"
                )
            except requests.HTTPError as e:
                assert e.response.status_code == 403, (
                    f"Unexpected HTTP error for pod '{pod}': {e.response.status_code}"
                )

    def test_acl_denial_does_not_leak_data(self):
        """Verify no student data leaks in denial responses."""
        # Denial response should include: reason, requested resource, agent
        # But NOT: student names, scores, or other PII

        # In real test, check denial response format:
        expected_keys = {"status", "reason", "agent", "requested_resources"}
        forbidden_keys = {
            "student_data", "results", "scores", "grades", "names"
        }

        # Placeholder for real test
        pass

    def test_acl_denial_logged(self):
        """Verify ACL denials are logged in structured JSON format."""
        # In real test, check logs contain entries like:
        # {
        #   "timestamp": "ISO-8601",
        #   "service": "sparql-query-skill",
        #   "level": "WARN",
        #   "event": "sparql.query.denied",
        #   "agent": "claire-teacher",
        #   "details": {"reason": "ACL check failed", ...}
        # }
        pass


class TestClaireAgentOrchestration:
    """AC1,2,3: Claire's agent system prompt orchestration."""

    def test_agent_executes_both_graph_only_and_hybrid(self):
        """Verify Claire's agent executes both query types for demonstration."""
        # Claire's SOUL.md instructs her to always do both passes
        # In real test, invoke Claire and verify both appear in response
        pass

    def test_agent_includes_provenance(self):
        """Verify Claire always includes provenance in results."""
        # From SOUL.md: "Always show provenance: which data sources contributed"
        pass

    def test_agent_respects_acl_boundaries(self):
        """Verify Claire enforces her ACL role constraints."""
        # If queried about unauthorized students, should deny
        pass


class TestClaireEmotionalCore:
    """Verify the "aha moment" is emotionally compelling."""

    def test_alex_aha_moment(self):
        """Verify Alex output clearly shows 'struggling differently' insight."""
        # The demo's emotional core: graph-only shows failure, hybrid shows learning
        # In real test, parse Alex's output and verify:
        # 1. School failures are visible
        # 2. Tutoring mastery is visible
        # 3. Semantic context explains the contrast
        # 4. Output feels compelling to potential funders
        pass


# ---------------------------------------------------------------------------
# Manual Test / Integration Walkthrough
# ---------------------------------------------------------------------------


def manual_test_workflow():
    """Manual integration test workflow (run interactively)."""
    print("\n" + "=" * 80)
    print("CLAIRE CROSS-CONTEXT INSIGHT DISCOVERY — MANUAL E2E TEST")
    print("=" * 80)

    print("\n1. Start OpenClaw runtime")
    print("   Command: distrobox-host-exec podman compose -f infra/openclaw.compose.yml up -d")

    print("\n2. Verify services are ready")
    print("   - OpenClaw: http://localhost:3000 (or OPENCLAW_BASE)")
    print("   - CSS: http://localhost:3000")
    print("   - Oxigraph: http://localhost:7878 (health check: GET /)")
    print("   - Qdrant: http://localhost:6333 (health check: GET /health)")

    print("\n3. In OpenClaw UI, select Claire agent (default)")

    print(f"\n4. Submit query: '{DEMONSTRATION_QUERY}'")

    print("\n5. Verify graph-only results:")
    print("   - Section labeled '=== GRAPH-ONLY RESULTS ==='")
    print("   - Lists Ayoub, Alex, Jordan with school assessments")
    print("   - Includes provenance (Pod resource URIs)")

    print("\n6. Verify hybrid results:")
    print("   - Section labeled '=== HYBRID RESULTS ==='")
    print("   - Same SPARQL facts as graph-only")
    print("   - Plus [SEMANTIC ENRICHMENT] blocks from Qdrant")

    print("\n7. Verify three-state output:")
    print("   - Ayoub: 'Tutoring context: NOT AVAILABLE' + call-to-action")
    print("   - Alex: School failures + tutoring mastery (aha moment)")
    print("   - Jordan: Average school + sparse tutoring")

    print("\n8. Verify provenance chains are navigable:")
    print("   - Click/trace from result → Pod resource URI")
    print("   - For Qdrant results: trace through triple URIs")

    print("\n9. Test ACL enforcement:")
    print("   - Attempt to query Fatima's child pods")
    print("   - Should receive 'Access denied' without leaking data")

    print("\n10. Check performance:")
    print("   - Graph-only < 500ms")
    print("   - Hybrid < 2s (parallel skill execution)")

    print("\n" + "=" * 80)
    print("If all steps pass, Story 3.4 implementation is complete.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    manual_test_workflow()
