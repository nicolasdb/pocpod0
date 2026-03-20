"""Integration tests for Oxigraph SPARQL queries.

Requires:
- Oxigraph running at http://localhost:7878
- CSS running at http://localhost:3000 with pod data from story 2-2 pipeline

Skip automatically when Oxigraph is unreachable.
"""

import time
from pathlib import Path
from urllib.parse import quote

import pytest
import requests

OXIGRAPH_BASE = "http://localhost:7878"
CSS_BASE = "http://localhost:3000"
PROVISIONER_WEBID = f"{CSS_BASE}/provisioner/profile/card#me"

SCHEMA_GRAPH_URI = "https://poc-pod0.edu/vocab/schema"

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _sparql_query(sparql: str, oxigraph_base: str = OXIGRAPH_BASE) -> dict:
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


def _store_turtle(turtle: str, graph_uri: str, oxigraph_base: str = OXIGRAPH_BASE) -> None:
    resp = requests.post(
        f"{oxigraph_base}/store",
        params={"graph": graph_uri},
        data=turtle.encode("utf-8"),
        headers={"Content-Type": "text/turtle"},
        timeout=10,
    )
    resp.raise_for_status()


def _delete_graph(graph_uri: str, oxigraph_base: str = OXIGRAPH_BASE) -> None:
    resp = requests.delete(
        f"{oxigraph_base}/store",
        params={"graph": graph_uri},
        timeout=10,
    )
    if resp.status_code not in (200, 204, 404):
        raise RuntimeError(
            f"Failed to delete graph <{graph_uri}>: HTTP {resp.status_code} — {resp.text[:100]}"
        )


@pytest.fixture(scope="module", autouse=True)
def oxigraph_available():
    """Skip all integration tests if Oxigraph is not reachable."""
    try:
        resp = requests.get(OXIGRAPH_BASE, timeout=3)
        if resp.status_code not in (200, 204):
            pytest.skip(f"Oxigraph returned {resp.status_code}")
    except requests.exceptions.ConnectionError:
        pytest.skip("Oxigraph not reachable at http://localhost:7878")


# ---------------------------------------------------------------------------
# Test: provenance lookup query returns correct triples for a known Pod resource
# ---------------------------------------------------------------------------

class TestProvenanceLookup:
    TEST_GRAPH = "http://test.provenance/resource-001.ttl"
    TURTLE = """
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xapi: <https://poc-pod0.edu/vocab/> .

<http://test.provenance/stmt/001>
    a xapi:Statement ;
    prov:wasDerivedFrom <http://test.provenance/resource-001.ttl> .

<http://test.provenance/stmt/001>
    xapi:verb <http://adlnet.gov/expapi/verbs/completed> .
"""

    def setup_method(self):
        _store_turtle(self.TURTLE, self.TEST_GRAPH)

    def teardown_method(self):
        _delete_graph(self.TEST_GRAPH)

    def test_provenance_lookup_returns_triples_from_named_graph(self):
        """Querying with FROM <graph_uri> returns all triples in that named graph."""
        result = _sparql_query(f"""
            SELECT ?subject ?predicate ?object
            FROM <{self.TEST_GRAPH}>
            WHERE {{
                ?subject ?predicate ?object .
            }}
        """)
        bindings = result["results"]["bindings"]
        assert len(bindings) > 0, "Expected triples in named graph, got none"

        subjects = {b["subject"]["value"] for b in bindings}
        assert "http://test.provenance/stmt/001" in subjects

    def test_graph_pattern_returns_same_triples(self):
        """GRAPH ?g {} pattern also works for provenance lookup."""
        result = _sparql_query(f"""
            SELECT ?subject ?predicate ?object
            WHERE {{
                GRAPH <{self.TEST_GRAPH}> {{
                    ?subject ?predicate ?object .
                }}
            }}
        """)
        bindings = result["results"]["bindings"]
        assert len(bindings) > 0


# ---------------------------------------------------------------------------
# Test: simple SPARQL query completes < 500ms with current data volume
# ---------------------------------------------------------------------------

class TestQueryPerformance:
    """AC2: SPARQL response time < 500ms at actual data volume (~303 statements)."""

    def test_select_all_graphs_completes_under_500ms(self):
        """Simple SELECT across all named graphs completes < 500ms."""
        start = time.monotonic()
        result = _sparql_query("""
            SELECT ?g ?s ?p ?o
            WHERE {
                GRAPH ?g { ?s ?p ?o }
            }
            LIMIT 1000
        """)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 500, (
            f"Query took {elapsed_ms:.1f}ms, expected < 500ms"
        )

    def test_count_query_completes_under_500ms(self):
        """COUNT query across all named graphs completes < 500ms."""
        start = time.monotonic()
        result = _sparql_query("""
            SELECT (COUNT(*) AS ?tripleCount)
            WHERE {
                GRAPH ?g { ?s ?p ?o }
            }
        """)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 500, (
            f"Count query took {elapsed_ms:.1f}ms, expected < 500ms"
        )

    def test_provenance_query_completes_under_500ms(self):
        """Provenance lookup by graph URI completes < 500ms."""
        # Use any named graph that exists (test graph or real data)
        test_graph = "http://test.perf/resource.ttl"
        _store_turtle(
            "<http://test.perf/s> <http://test.perf/p> <http://test.perf/o> .",
            test_graph,
        )

        try:
            start = time.monotonic()
            result = _sparql_query(f"""
                SELECT ?subject ?predicate ?object
                FROM <{test_graph}>
                WHERE {{
                    ?subject ?predicate ?object .
                }}
            """)
            elapsed_ms = (time.monotonic() - start) * 1000

            assert elapsed_ms < 500, (
                f"Provenance query took {elapsed_ms:.1f}ms, expected < 500ms"
            )
        finally:
            _delete_graph(test_graph)


# ---------------------------------------------------------------------------
# Test: schema classes are queryable after loading
# ---------------------------------------------------------------------------

class TestSchemaQueryable:
    def test_schema_triples_loadable_and_queryable(self):
        """Load schema from data/schemas/ and verify classes are queryable."""
        from pocpod0_pipeline.load_graph import load_schemas
        from rdflib import Graph

        schemas_path = Path(__file__).parents[3] / "data" / "schemas"
        if not schemas_path.exists():
            pytest.skip(f"Schema directory not found: {schemas_path}")

        # Load schemas into Oxigraph
        count = load_schemas(schemas_path=schemas_path, oxigraph_base=OXIGRAPH_BASE)
        assert count > 0, "Expected at least one schema triple loaded"

        # Query for RDF classes in the schema graph
        result = _sparql_query(f"""
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl:  <http://www.w3.org/2002/07/owl#>

            SELECT ?class
            FROM <{SCHEMA_GRAPH_URI}>
            WHERE {{
                {{ ?class a rdfs:Class }} UNION {{ ?class a owl:Class }}
            }}
            LIMIT 10
        """)
        bindings = result["results"]["bindings"]
        assert len(bindings) > 0, (
            f"Expected queryable classes in schema graph <{SCHEMA_GRAPH_URI}>, got none"
        )
