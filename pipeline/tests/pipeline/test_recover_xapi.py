"""Unit tests for recover_xapi.py.

Fully offline — all HTTP calls mocked.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from pocpod0_pipeline.recover_xapi import (
    _extract_original_xapi,
    compare_xapi_statements,
    recover_xapi_batch,
    recover_xapi_from_triple,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SUBJECT_URI = "https://poc-pod0.edu/stmt/test-uuid"
POD_RESOURCE_URI = "http://localhost:3000/ayoub/learning/assessment/test-uuid.ttl"
OXIGRAPH_URL = "http://localhost:7878"
CSS_BASE_URL = "http://localhost:3000"

SAMPLE_XAPI = {
    "id": "test-uuid",
    "actor": {
        "objectType": "Agent",
        "name": "Ayoub",
        "account": {"homePage": "http://localhost:3000", "name": "ayoub"},
    },
    "verb": {
        "id": "http://adlnet.gov/expapi/verbs/completed",
        "display": {"en-US": "completed"},
    },
    "object": {
        "id": "http://example.org/activity/math-test",
        "definition": {"type": "http://adlnet.gov/expapi/activities/assessment"},
    },
    "result": {"success": True, "completion": True, "score": {"scaled": 0.85}},
    "timestamp": "2024-01-15T10:00:00Z",
}

SAMPLE_TURTLE = f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix pocpod0: <https://poc-pod0.edu/vocab/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<{SUBJECT_URI}>
    prov:wasDerivedFrom <{POD_RESOURCE_URI}> ;
    pocpod0:originalXapiJson "{json.dumps(SAMPLE_XAPI).replace(chr(34), chr(92)+chr(34))}"^^xsd:string .
""".strip()


def _sparql_binding(subject_uri: str, pod_resource_uri: str):
    return [
        {
            "subject": {"value": subject_uri},
            "podResourceUri": {"value": pod_resource_uri},
        }
    ]


def _mock_sparql_resp(bindings):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"results": {"bindings": bindings}}
    mock.raise_for_status.return_value = None
    return mock


def _mock_css_resp(turtle_text, status=200):
    mock = MagicMock()
    mock.status_code = status
    mock.text = turtle_text
    mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# _extract_original_xapi
# ---------------------------------------------------------------------------

class TestExtractOriginalXapi:
    def _make_turtle(self, xapi_dict):
        raw = json.dumps(xapi_dict).replace('"', '\\"')
        return f"""
@prefix pocpod0: <https://poc-pod0.edu/vocab/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<{SUBJECT_URI}> pocpod0:originalXapiJson "{raw}"^^xsd:string .
"""

    def test_extracts_json_string(self):
        turtle = self._make_turtle(SAMPLE_XAPI)
        raw = _extract_original_xapi(turtle, POD_RESOURCE_URI)
        assert raw is not None
        parsed = json.loads(raw)
        assert parsed["id"] == SAMPLE_XAPI["id"]

    def test_returns_none_when_property_absent(self):
        turtle = f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
<{SUBJECT_URI}> prov:wasDerivedFrom <{POD_RESOURCE_URI}> .
"""
        result = _extract_original_xapi(turtle, POD_RESOURCE_URI)
        assert result is None


# ---------------------------------------------------------------------------
# recover_xapi_from_triple — success path
# ---------------------------------------------------------------------------

class TestRecoverXapiFromTriple:
    def _make_turtle_content(self):
        raw = json.dumps(SAMPLE_XAPI).replace('"', '\\"')
        return f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix pocpod0: <https://poc-pod0.edu/vocab/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<{SUBJECT_URI}> prov:wasDerivedFrom <{POD_RESOURCE_URI}> ;
    pocpod0:originalXapiJson "{raw}"^^xsd:string .
"""

    def test_full_success(self):
        sparql_resp = _mock_sparql_resp(_sparql_binding(SUBJECT_URI, POD_RESOURCE_URI))
        css_resp = _mock_css_resp(self._make_turtle_content())

        with patch("pocpod0_pipeline.recover_xapi.requests.get") as mock_get:
            mock_get.side_effect = [sparql_resp, css_resp]
            result = recover_xapi_from_triple(SUBJECT_URI, OXIGRAPH_URL, CSS_BASE_URL)

        assert result["success"] is True
        assert result["pod_resource_uri"] == POD_RESOURCE_URI
        assert result["recovered_xapi"]["id"] == SAMPLE_XAPI["id"]
        assert result["error"] is None

    def test_no_provenance_triple(self):
        sparql_resp = _mock_sparql_resp([])

        with patch("pocpod0_pipeline.recover_xapi.requests.get", return_value=sparql_resp):
            result = recover_xapi_from_triple(SUBJECT_URI, OXIGRAPH_URL, CSS_BASE_URL)

        assert result["success"] is False
        assert "No prov:wasDerivedFrom" in result["error"]

    def test_pod_resource_404(self):
        sparql_resp = _mock_sparql_resp(_sparql_binding(SUBJECT_URI, POD_RESOURCE_URI))
        css_resp = _mock_css_resp("", status=404)

        with patch("pocpod0_pipeline.recover_xapi.requests.get") as mock_get:
            mock_get.side_effect = [sparql_resp, css_resp]
            result = recover_xapi_from_triple(SUBJECT_URI, OXIGRAPH_URL, CSS_BASE_URL)

        assert result["success"] is False
        assert "404" in result["error"]

    def test_sparql_failure(self):
        with patch("pocpod0_pipeline.recover_xapi.requests.get", side_effect=Exception("connection refused")):
            result = recover_xapi_from_triple(SUBJECT_URI, OXIGRAPH_URL, CSS_BASE_URL)

        assert result["success"] is False
        assert "SPARQL query failed" in result["error"]

    def test_missing_original_xapi_literal(self):
        sparql_resp = _mock_sparql_resp(_sparql_binding(SUBJECT_URI, POD_RESOURCE_URI))
        turtle_no_literal = f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
<{SUBJECT_URI}> prov:wasDerivedFrom <{POD_RESOURCE_URI}> .
"""
        css_resp = _mock_css_resp(turtle_no_literal)

        with patch("pocpod0_pipeline.recover_xapi.requests.get") as mock_get:
            mock_get.side_effect = [sparql_resp, css_resp]
            result = recover_xapi_from_triple(SUBJECT_URI, OXIGRAPH_URL, CSS_BASE_URL)

        assert result["success"] is False
        assert "originalXapiJson" in result["error"]


# ---------------------------------------------------------------------------
# recover_xapi_batch
# ---------------------------------------------------------------------------

class TestRecoverXapiBatch:
    def _make_turtle_content(self):
        raw = json.dumps(SAMPLE_XAPI).replace('"', '\\"')
        return f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix pocpod0: <https://poc-pod0.edu/vocab/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<{SUBJECT_URI}> prov:wasDerivedFrom <{POD_RESOURCE_URI}> ;
    pocpod0:originalXapiJson "{raw}"^^xsd:string .
"""

    def test_batch_returns_list(self):
        batch_bindings = [
            {"subject": {"value": f"{SUBJECT_URI}-{i}"}, "podResourceUri": {"value": POD_RESOURCE_URI}}
            for i in range(3)
        ]
        sparql_resp = _mock_sparql_resp(batch_bindings)
        css_resp = _mock_css_resp(self._make_turtle_content())

        with patch("pocpod0_pipeline.recover_xapi.requests.get") as mock_get:
            # First call: batch SPARQL; subsequent: individual SPARQL + CSS for each
            individual_sparql = _mock_sparql_resp(
                [{"podResourceUri": {"value": POD_RESOURCE_URI}}]
            )
            mock_get.side_effect = (
                [sparql_resp]
                + [individual_sparql, _mock_css_resp(self._make_turtle_content())] * 3
            )
            results = recover_xapi_batch(OXIGRAPH_URL, CSS_BASE_URL, limit=3)

        assert len(results) == 3

    def test_batch_sparql_failure_returns_empty(self):
        with patch("pocpod0_pipeline.recover_xapi.requests.get", side_effect=Exception("no connection")):
            results = recover_xapi_batch(OXIGRAPH_URL, CSS_BASE_URL)
        assert results == []


# ---------------------------------------------------------------------------
# compare_xapi_statements
# ---------------------------------------------------------------------------

class TestCompareXapiStatements:
    def test_identical_statements_match(self):
        result = compare_xapi_statements(SAMPLE_XAPI, SAMPLE_XAPI.copy())
        assert result["match"] is True
        assert result["differences"] == []

    def test_different_actor_name_detected(self):
        modified = json.loads(json.dumps(SAMPLE_XAPI))
        modified["actor"]["name"] = "Lucas"
        result = compare_xapi_statements(SAMPLE_XAPI, modified)
        assert result["match"] is False
        assert any("actor.name" in d for d in result["differences"])

    def test_different_verb_detected(self):
        modified = json.loads(json.dumps(SAMPLE_XAPI))
        modified["verb"]["id"] = "http://adlnet.gov/expapi/verbs/attempted"
        result = compare_xapi_statements(SAMPLE_XAPI, modified)
        assert result["match"] is False
        assert any("verb.id" in d for d in result["differences"])

    def test_different_timestamp_detected(self):
        modified = json.loads(json.dumps(SAMPLE_XAPI))
        modified["timestamp"] = "2024-06-01T00:00:00Z"
        result = compare_xapi_statements(SAMPLE_XAPI, modified)
        assert result["match"] is False
        assert any("timestamp" in d for d in result["differences"])

    def test_float_precision_tolerance(self):
        a = {"result": {"score": {"scaled": 0.8500000000000001}}}
        b = {"result": {"score": {"scaled": 0.85}}}
        # Fill required fields to avoid false positives
        for d in [a, b]:
            d.update({"actor": {}, "verb": {}, "object": {}})
        result = compare_xapi_statements(a, b)
        assert result["match"] is True

    def test_significant_score_difference_detected(self):
        a = {"result": {"score": {"scaled": 0.85}}}
        b = {"result": {"score": {"scaled": 0.75}}}
        for d in [a, b]:
            d.update({"actor": {}, "verb": {}, "object": {}})
        result = compare_xapi_statements(a, b)
        assert result["match"] is False
