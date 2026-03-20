"""Unit tests for load_graph.py.

Tests are fully offline — no real CSS or Oxigraph needed.
All HTTP calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from rdflib import Graph, Literal, Namespace, URIRef

from pocpod0_pipeline.load_graph import (
    SCHEMA_GRAPH_URI,
    _fetch_turtle,
    _list_pod_resources,
    _load_turtle_to_graph,
    load_from_pods,
    load_resource,
    load_schemas,
)

CSS_BASE = "http://localhost:3000"
OXIGRAPH_BASE = "http://localhost:7878"
POD_NAME = "ayoub"
RESOURCE_URI = f"{CSS_BASE}/{POD_NAME}/learning/assessment/stmt-abc.ttl"

SAMPLE_TURTLE = """
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xapi: <https://poc-pod0.edu/vocab/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/stmt/abc>
    a xapi:Statement ;
    prov:wasDerivedFrom <{resource_uri}> .
""".format(resource_uri=RESOURCE_URI)


# ---------------------------------------------------------------------------
# _fetch_turtle
# ---------------------------------------------------------------------------

class TestFetchTurtle:
    def test_returns_content_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_TURTLE

        with patch("pocpod0_pipeline.load_graph.requests.get", return_value=mock_resp):
            result = _fetch_turtle(RESOURCE_URI)

        assert result == SAMPLE_TURTLE

    def test_returns_none_on_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("pocpod0_pipeline.load_graph.requests.get", return_value=mock_resp):
            result = _fetch_turtle(RESOURCE_URI)

        assert result is None

    def test_returns_none_on_request_exception(self):
        import requests as req
        with patch("pocpod0_pipeline.load_graph.requests.get",
                   side_effect=req.RequestException("timeout")):
            result = _fetch_turtle(RESOURCE_URI)

        assert result is None


# ---------------------------------------------------------------------------
# _load_turtle_to_graph
# ---------------------------------------------------------------------------

class TestLoadTurtleToGraph:
    def test_returns_true_on_204(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("pocpod0_pipeline.load_graph.requests.post", return_value=mock_resp):
            result = _load_turtle_to_graph(SAMPLE_TURTLE, RESOURCE_URI, OXIGRAPH_BASE)

        assert result is True

    def test_returns_false_on_error_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("pocpod0_pipeline.load_graph.requests.post", return_value=mock_resp):
            result = _load_turtle_to_graph(SAMPLE_TURTLE, RESOURCE_URI, OXIGRAPH_BASE)

        assert result is False

    def test_posts_to_correct_url_with_graph_param(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("pocpod0_pipeline.load_graph.requests.post", return_value=mock_resp) as mock_post:
            _load_turtle_to_graph(SAMPLE_TURTLE, RESOURCE_URI, OXIGRAPH_BASE)

        call_kwargs = mock_post.call_args
        assert "/store" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["graph"] == RESOURCE_URI


# ---------------------------------------------------------------------------
# load_resource
# ---------------------------------------------------------------------------

class TestLoadResource:
    def test_loads_turtle_and_returns_triple_count(self):
        mock_fetch = MagicMock(return_value=SAMPLE_TURTLE)
        mock_load = MagicMock(return_value=True)

        with patch("pocpod0_pipeline.load_graph._fetch_turtle", mock_fetch), \
             patch("pocpod0_pipeline.load_graph._load_turtle_to_graph", mock_load):
            count = load_resource(RESOURCE_URI, POD_NAME, OXIGRAPH_BASE)

        assert count > 0
        mock_load.assert_called_once_with(SAMPLE_TURTLE, RESOURCE_URI, OXIGRAPH_BASE)

    def test_returns_minus_one_when_fetch_fails(self):
        with patch("pocpod0_pipeline.load_graph._fetch_turtle", return_value=None):
            count = load_resource(RESOURCE_URI, POD_NAME, OXIGRAPH_BASE)

        assert count == -1

    def test_returns_minus_one_when_store_fails(self):
        mock_fetch = MagicMock(return_value=SAMPLE_TURTLE)
        mock_load = MagicMock(return_value=False)

        with patch("pocpod0_pipeline.load_graph._fetch_turtle", mock_fetch), \
             patch("pocpod0_pipeline.load_graph._load_turtle_to_graph", mock_load):
            count = load_resource(RESOURCE_URI, POD_NAME, OXIGRAPH_BASE)

        assert count == -1


# ---------------------------------------------------------------------------
# load_from_pods — log+continue error handling
# ---------------------------------------------------------------------------

class TestLoadFromPods:
    def test_survives_one_bad_resource(self):
        """Loader continues when one resource fails; summary counts are accurate."""
        good_resource = (POD_NAME, RESOURCE_URI)
        bad_resource = (POD_NAME, f"{CSS_BASE}/{POD_NAME}/learning/assessment/bad.ttl")
        all_resources = [good_resource, bad_resource]

        def mock_load_resource(resource_uri, pod_name, oxigraph_base):
            if "bad.ttl" in resource_uri:
                return -1
            return 2  # 2 triples for good resource

        with patch("pocpod0_pipeline.load_graph._list_all_pod_resources",
                   return_value=all_resources), \
             patch("pocpod0_pipeline.load_graph.load_resource",
                   side_effect=mock_load_resource):
            result = load_from_pods(CSS_BASE, OXIGRAPH_BASE)

        assert result["total_resources"] == 2
        assert result["total_triples"] == 2
        assert result["failed"] == 1

    def test_summary_counts_all_resources(self):
        resources = [(POD_NAME, f"{CSS_BASE}/{POD_NAME}/learning/a/{i}.ttl")
                     for i in range(5)]

        with patch("pocpod0_pipeline.load_graph._list_all_pod_resources",
                   return_value=resources), \
             patch("pocpod0_pipeline.load_graph.load_resource", return_value=3):
            result = load_from_pods(CSS_BASE, OXIGRAPH_BASE)

        assert result["total_resources"] == 5
        assert result["total_triples"] == 15
        assert result["failed"] == 0

    def test_exception_in_load_resource_counts_as_failed(self):
        resources = [(POD_NAME, RESOURCE_URI)]

        with patch("pocpod0_pipeline.load_graph._list_all_pod_resources",
                   return_value=resources), \
             patch("pocpod0_pipeline.load_graph.load_resource",
                   side_effect=RuntimeError("unexpected")):
            result = load_from_pods(CSS_BASE, OXIGRAPH_BASE)

        assert result["failed"] == 1
        assert result["total_triples"] == 0


# ---------------------------------------------------------------------------
# load_schemas
# ---------------------------------------------------------------------------

class TestLoadSchemas:
    def test_loads_all_ttl_files_into_schema_graph(self, tmp_path):
        # Write two minimal schema files
        (tmp_path / "schema1.ttl").write_text(
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "<http://example.org/ClassA> a rdfs:Class .\n"
        )
        (tmp_path / "schema2.ttl").write_text(
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "<http://example.org/ClassB> a rdfs:Class .\n"
        )

        mock_load = MagicMock(return_value=True)
        with patch("pocpod0_pipeline.load_graph._load_turtle_to_graph", mock_load):
            count = load_schemas(schemas_path=tmp_path, oxigraph_base=OXIGRAPH_BASE)

        assert count == 2  # 2 triples (one per schema file)
        # Must load into the schema named graph
        called_graph_uri = mock_load.call_args[0][1]
        assert called_graph_uri == SCHEMA_GRAPH_URI

    def test_returns_zero_when_no_files(self, tmp_path):
        count = load_schemas(schemas_path=tmp_path, oxigraph_base=OXIGRAPH_BASE)
        assert count == 0
