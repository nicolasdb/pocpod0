"""Unit tests for deletion cascade (Story 5.2).

Tests cover:
  - soft_delete_css: correct URL, payload, auth header, StepResult fields
  - drop_oxigraph_graph: DROP GRAPH statement parameterization
  - delete_qdrant_points: filter uses pod_uri_hash, not pod_resource_uri; count in details
  - verify_deletion: all-clean path and partial-failure path
  - run_cascade: step order, all four JSONL events emitted, partial failure does not abort
  - PRIV-1 fix in embed.py: payload has pod_uri_hash, NOT pod_resource_uri
  - uuid_index: register_hash → SPARQL INSERT; resolve_hash → SPARQL SELECT; deregister_hash → DELETE
  - Hash determinism: same URI always produces same 16-char hex hash
"""

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from pocpod0_pipeline.delete_cascade import (
    DeletionResult,
    StepResult,
    VerificationResult,
    delete_qdrant_points,
    drop_oxigraph_graph,
    run_cascade,
    soft_delete_css,
    verify_deletion,
)
from pocpod0_pipeline.uuid_index import (
    _compute_hash,
    deregister_hash,
    register_hash,
    resolve_hash,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RESOURCE_URI = "http://localhost:3000/ayoub/learning-records/"
_POD_NAME = "ayoub"
_HASH = hashlib.sha256(_RESOURCE_URI.encode()).hexdigest()[:16]
_OXIGRAPH_URL = "http://localhost:7878"
_QDRANT_URL = "http://localhost:6333"


def _mock_response(status_code: int, json_body: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ---------------------------------------------------------------------------
# Hash determinism
# ---------------------------------------------------------------------------


def test_hash_determinism():
    """Same URI always produces same 16-char hex hash."""
    uri = "http://localhost:3000/ayoub/learning-records/"
    h1 = _compute_hash(uri)
    h2 = _compute_hash(uri)
    assert h1 == h2
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


def test_different_uris_different_hashes():
    h1 = _compute_hash("http://localhost:3000/ayoub/learning-records/")
    h2 = _compute_hash("http://localhost:3000/fatima/learning-records/")
    assert h1 != h2


# ---------------------------------------------------------------------------
# soft_delete_css
# ---------------------------------------------------------------------------


class TestSoftDeleteCSS:
    @patch("pocpod0_pipeline.delete_cascade.httpx.patch")
    def test_success_returns_ok_step(self, mock_patch):
        mock_patch.return_value = _mock_response(204)
        result = soft_delete_css(_RESOURCE_URI, _POD_NAME)

        assert result.step == "1-css-soft-delete"
        assert result.layer == "css"
        assert result.status == "ok"
        assert result.duration_ms >= 0

    @patch("pocpod0_pipeline.delete_cascade.httpx.patch")
    def test_uses_webid_auth_header(self, mock_patch):
        mock_patch.return_value = _mock_response(204)
        soft_delete_css(_RESOURCE_URI, _POD_NAME)

        _, kwargs = mock_patch.call_args
        headers = kwargs.get("headers") or mock_patch.call_args[0][1] if len(mock_patch.call_args[0]) > 1 else {}
        # Check headers passed to httpx.patch
        call_kwargs = mock_patch.call_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"].startswith("WebID ")

    @patch("pocpod0_pipeline.delete_cascade.httpx.patch")
    def test_uses_correct_url(self, mock_patch):
        mock_patch.return_value = _mock_response(204)
        soft_delete_css(_RESOURCE_URI, _POD_NAME)
        assert mock_patch.call_args.args[0] == _RESOURCE_URI

    @patch("pocpod0_pipeline.delete_cascade.httpx.patch")
    def test_http_error_returns_error_step(self, mock_patch):
        mock_patch.return_value = _mock_response(403, text="Forbidden")
        result = soft_delete_css(_RESOURCE_URI, _POD_NAME)
        assert result.status == "error"
        assert "403" in result.details

    @patch("pocpod0_pipeline.delete_cascade.httpx.patch")
    def test_connection_error_returns_error_step(self, mock_patch):
        mock_patch.side_effect = ConnectionError("refused")
        result = soft_delete_css(_RESOURCE_URI, _POD_NAME)
        assert result.status == "error"
        assert result.layer == "css"


# ---------------------------------------------------------------------------
# drop_oxigraph_graph
# ---------------------------------------------------------------------------


class TestDropOxigraphGraph:
    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_success_path(self, mock_post):
        # First call: DROP UPDATE → 200
        # Second call: ASK query → {"boolean": false}
        mock_post.side_effect = [
            _mock_response(200),
            _mock_response(200, {"boolean": False}),
        ]
        result = drop_oxigraph_graph(_RESOURCE_URI, _OXIGRAPH_URL)
        assert result.step == "2-oxigraph-drop"
        assert result.layer == "oxigraph"
        assert result.status == "ok"

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_drop_statement_contains_resource_uri(self, mock_post):
        mock_post.side_effect = [
            _mock_response(200),
            _mock_response(200, {"boolean": False}),
        ]
        drop_oxigraph_graph(_RESOURCE_URI, _OXIGRAPH_URL)
        first_call = mock_post.call_args_list[0]
        body = first_call.kwargs.get("content", b"").decode("utf-8")
        assert "DROP GRAPH" in body
        assert _RESOURCE_URI in body

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_ask_confirms_graph_gone(self, mock_post):
        # DROP succeeds, ASK returns still-exists → error
        mock_post.side_effect = [
            _mock_response(200),
            _mock_response(200, {"boolean": True}),  # graph still present!
        ]
        result = drop_oxigraph_graph(_RESOURCE_URI, _OXIGRAPH_URL)
        assert result.status == "error"
        assert "still returns triples" in result.details

    def test_unsafe_uri_rejected(self):
        result = drop_oxigraph_graph("javascript:alert(1)", _OXIGRAPH_URL)
        assert result.status == "error"
        assert "Unsafe URI" in result.details

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_connection_error_returns_error_step(self, mock_post):
        mock_post.side_effect = ConnectionError("timeout")
        result = drop_oxigraph_graph(_RESOURCE_URI, _OXIGRAPH_URL)
        assert result.status == "error"
        assert result.layer == "oxigraph"


# ---------------------------------------------------------------------------
# delete_qdrant_points
# ---------------------------------------------------------------------------


class TestDeleteQdrantPoints:
    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_filter_uses_pod_uri_hash_not_raw_uri(self, mock_post):
        mock_post.return_value = _mock_response(200, {"result": {"status": "completed", "operation_id": 1}})
        delete_qdrant_points(_HASH, _QDRANT_URL)
        first_call = mock_post.call_args_list[0]
        body = json.loads(first_call.kwargs.get("content", b"{}"))
        # Verify filter uses pod_uri_hash
        must = body["filter"]["must"]
        keys = [c["key"] for c in must]
        assert "pod_uri_hash" in keys
        assert "pod_resource_uri" not in keys

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_success_returns_ok_step(self, mock_post):
        mock_post.return_value = _mock_response(200, {"result": {"status": "completed", "operation_id": 1}})
        result = delete_qdrant_points(_HASH, _QDRANT_URL)
        assert result.step == "3-qdrant-delete"
        assert result.layer == "qdrant"
        assert result.status == "ok"
        assert _HASH in result.details

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_http_error_returns_error_step(self, mock_post):
        mock_post.return_value = _mock_response(500, text="Internal Server Error")
        result = delete_qdrant_points(_HASH, _QDRANT_URL)
        assert result.status == "error"

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    def test_legacy_pod_resource_uri_deletion(self, mock_post):
        """When resource_uri provided, also attempts legacy deletion."""
        mock_post.return_value = _mock_response(200, {"result": {"status": "completed", "operation_id": 0}})
        delete_qdrant_points(_HASH, _QDRANT_URL, resource_uri=_RESOURCE_URI)
        # Should have made two calls: one for hash, one for legacy URI
        assert mock_post.call_count == 2
        second_body = json.loads(mock_post.call_args_list[1].kwargs.get("content", b"{}"))
        keys = [c["key"] for c in second_body["filter"]["must"]]
        assert "pod_resource_uri" in keys


# ---------------------------------------------------------------------------
# verify_deletion
# ---------------------------------------------------------------------------


class TestVerifyDeletion:
    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    @patch("pocpod0_pipeline.delete_cascade.httpx.get")
    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    def test_all_clean_path(self, mock_append, mock_get, mock_post):
        # CSS GET: returns body with isDeleted marker
        mock_get.return_value = _mock_response(200, text="pocpod0:isDeleted true .")
        # Oxigraph ASK: graph is gone
        # Qdrant count: 0 points
        mock_post.side_effect = [
            _mock_response(200, {"boolean": False}),       # ASK oxigraph
            _mock_response(200, {"result": {"count": 0}}), # qdrant count
        ]
        result = verify_deletion(_RESOURCE_URI, _HASH, _POD_NAME)
        assert result.css_deleted is True
        assert result.oxigraph_clean is True
        assert result.qdrant_clean is True
        assert result.all_layers_clean is True

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    @patch("pocpod0_pipeline.delete_cascade.httpx.get")
    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    def test_partial_failure_path(self, mock_append, mock_get, mock_post):
        # CSS GET: no isDeleted marker (soft-delete failed)
        mock_get.return_value = _mock_response(200, text="some triples, no deletion marker")
        # Oxigraph: clean
        # Qdrant: 2 points remain
        mock_post.side_effect = [
            _mock_response(200, {"boolean": False}),       # ASK oxigraph: clean
            _mock_response(200, {"result": {"count": 2}}), # qdrant: still has points
        ]
        result = verify_deletion(_RESOURCE_URI, _HASH, _POD_NAME)
        assert result.css_deleted is False
        assert result.oxigraph_clean is True
        assert result.qdrant_clean is False
        assert result.all_layers_clean is False

    @patch("pocpod0_pipeline.delete_cascade.httpx.post")
    @patch("pocpod0_pipeline.delete_cascade.httpx.get")
    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    def test_emits_verification_event(self, mock_append, mock_get, mock_post):
        mock_get.return_value = _mock_response(200, text="pocpod0:isDeleted true .")
        mock_post.side_effect = [
            _mock_response(200, {"boolean": False}),
            _mock_response(200, {"result": {"count": 0}}),
        ]
        verify_deletion(_RESOURCE_URI, _HASH, _POD_NAME)
        mock_append.assert_called()
        event = mock_append.call_args.args[0]
        # P-3: verification now emits deletion.step with step=4-verification (per AC3 schema)
        assert event["event_type"] == "deletion.step"
        assert event["step"] == "4-verification"
        assert "passed" in event  # P-4: passed field required by AC2


# ---------------------------------------------------------------------------
# run_cascade
# ---------------------------------------------------------------------------


class TestRunCascade:
    def _make_ok_step(self, step: str, layer: str) -> StepResult:
        return StepResult(step=step, layer=layer, status="ok", details="ok", duration_ms=1)

    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    @patch("pocpod0_pipeline.delete_cascade.verify_deletion")
    @patch("pocpod0_pipeline.delete_cascade.delete_qdrant_points")
    @patch("pocpod0_pipeline.delete_cascade.drop_oxigraph_graph")
    @patch("pocpod0_pipeline.delete_cascade.soft_delete_css")
    @patch("pocpod0_pipeline.delete_cascade.deregister_hash", side_effect=lambda h, u: None)
    def test_step_order(self, mock_dereg, mock_css, mock_oxi, mock_qdrant, mock_verify, mock_append):
        mock_css.return_value = self._make_ok_step("1-css-soft-delete", "css")
        mock_oxi.return_value = self._make_ok_step("2-oxigraph-drop", "oxigraph")
        mock_qdrant.return_value = self._make_ok_step("3-qdrant-delete", "qdrant")
        mock_verify.return_value = VerificationResult(
            resource_uri=_RESOURCE_URI, css_deleted=True,
            oxigraph_clean=True, qdrant_clean=True,
            all_layers_clean=True, timestamp="2026-01-01T00:00:00Z",
        )

        result = run_cascade(_RESOURCE_URI, _POD_NAME)

        # Verify call order
        assert mock_css.called
        assert mock_oxi.called
        assert mock_qdrant.called
        assert mock_verify.called

        # Verify step sequence via result
        steps = [s.step for s in result.step_results]
        assert steps == ["1-css-soft-delete", "2-oxigraph-drop", "3-qdrant-delete"]
        assert result.all_layers_clean is True

    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    @patch("pocpod0_pipeline.delete_cascade.verify_deletion")
    @patch("pocpod0_pipeline.delete_cascade.delete_qdrant_points")
    @patch("pocpod0_pipeline.delete_cascade.drop_oxigraph_graph")
    @patch("pocpod0_pipeline.delete_cascade.soft_delete_css")
    @patch("pocpod0_pipeline.delete_cascade.deregister_hash", side_effect=lambda h, u: None)
    def test_step2_failure_does_not_abort_step3(self, mock_dereg, mock_css, mock_oxi, mock_qdrant, mock_verify, mock_append):
        """Step 2 (Oxigraph) failure must not abort Step 3 (Qdrant)."""
        mock_css.return_value = self._make_ok_step("1-css-soft-delete", "css")
        mock_oxi.return_value = StepResult(
            step="2-oxigraph-drop", layer="oxigraph",
            status="error", details="connection refused", duration_ms=5,
        )
        mock_qdrant.return_value = self._make_ok_step("3-qdrant-delete", "qdrant")
        mock_verify.return_value = VerificationResult(
            resource_uri=_RESOURCE_URI, css_deleted=True,
            oxigraph_clean=False, qdrant_clean=True,
            all_layers_clean=False, timestamp="2026-01-01T00:00:00Z",
        )

        result = run_cascade(_RESOURCE_URI, _POD_NAME)

        # Step 3 must have been called despite Step 2 error
        assert mock_qdrant.called
        assert result.all_layers_clean is False
        steps = [s.step for s in result.step_results]
        assert "3-qdrant-delete" in steps

    @patch("pocpod0_pipeline.delete_cascade._append_consent_event")
    @patch("pocpod0_pipeline.delete_cascade.verify_deletion")
    @patch("pocpod0_pipeline.delete_cascade.delete_qdrant_points")
    @patch("pocpod0_pipeline.delete_cascade.drop_oxigraph_graph")
    @patch("pocpod0_pipeline.delete_cascade.soft_delete_css")
    @patch("pocpod0_pipeline.delete_cascade.deregister_hash", side_effect=lambda h, u: None)
    def test_four_jsonl_events_emitted(self, mock_dereg, mock_css, mock_oxi, mock_qdrant, mock_verify, mock_append):
        """run_cascade must emit 4 JSONL events: 3 steps + 1 deletion.complete."""
        mock_css.return_value = self._make_ok_step("1-css-soft-delete", "css")
        mock_oxi.return_value = self._make_ok_step("2-oxigraph-drop", "oxigraph")
        mock_qdrant.return_value = self._make_ok_step("3-qdrant-delete", "qdrant")
        mock_verify.return_value = VerificationResult(
            resource_uri=_RESOURCE_URI, css_deleted=True,
            oxigraph_clean=True, qdrant_clean=True,
            all_layers_clean=True, timestamp="2026-01-01T00:00:00Z",
        )

        run_cascade(_RESOURCE_URI, _POD_NAME)

        # 3 step events from _emit_step_event (steps 1-3) + 1 deletion.complete
        # Note: step 4-verification is emitted by verify_deletion (mocked here);
        # in a real run there are 4 deletion.step events + 1 deletion.complete = 5 total.
        event_types = [call.args[0]["event_type"] for call in mock_append.call_args_list]
        step_events = [e for e in event_types if e == "deletion.step"]
        complete_events = [e for e in event_types if e == "deletion.complete"]
        assert len(step_events) == 3
        assert len(complete_events) == 1


# ---------------------------------------------------------------------------
# PRIV-1 fix in embed.py
# ---------------------------------------------------------------------------


class TestPriv1Fix:
    def test_batch_upsert_payload_has_pod_uri_hash_not_raw_uri(self):
        """Qdrant payload must NOT contain pod_resource_uri after PRIV-1 fix."""
        from pocpod0_pipeline.embed import QdrantWriter, QDRANT_COLLECTION

        writer = QdrantWriter.__new__(QdrantWriter)
        writer._collection = QDRANT_COLLECTION

        mock_client = MagicMock()
        writer._client = mock_client

        chunks = [{"pod_resource_uri": _RESOURCE_URI, "text": "math homework", "triple_uris": [_RESOURCE_URI]}]
        vectors = [[0.1] * 4096]

        # P-9: patch register_hash to avoid live HTTP call in unit test
        with patch("pocpod0_pipeline.embed.register_hash"):
            writer.batch_upsert_points(chunks, vectors)

        assert mock_client.upsert.called
        upserted_points = mock_client.upsert.call_args.kwargs["points"]
        assert len(upserted_points) == 1
        payload = upserted_points[0].payload

        # PRIV-1: raw URI must NOT be in payload
        assert "pod_resource_uri" not in payload, "pod_resource_uri must not be stored (PRIV-1 fix)"
        # Hash must be present
        assert "pod_uri_hash" in payload, "pod_uri_hash must be in payload"
        assert len(payload["pod_uri_hash"]) == 16

    def test_hash_matches_expected_sha256(self):
        """pod_uri_hash in payload must be SHA-256(uri)[:16]."""
        from pocpod0_pipeline.embed import QdrantWriter, QDRANT_COLLECTION

        writer = QdrantWriter.__new__(QdrantWriter)
        writer._collection = QDRANT_COLLECTION
        mock_client = MagicMock()
        writer._client = mock_client

        chunks = [{"pod_resource_uri": _RESOURCE_URI, "text": "test", "triple_uris": []}]
        vectors = [[0.0] * 4096]

        with patch("pocpod0_pipeline.embed.register_hash"):
            writer.batch_upsert_points(chunks, vectors)

        payload = mock_client.upsert.call_args.kwargs["points"][0].payload
        expected_hash = hashlib.sha256(_RESOURCE_URI.encode()).hexdigest()[:16]
        assert payload["pod_uri_hash"] == expected_hash


# ---------------------------------------------------------------------------
# uuid_index
# ---------------------------------------------------------------------------


class TestUUIDIndex:
    @patch("pocpod0_pipeline.uuid_index.httpx.post")
    def test_register_hash_sends_sparql_insert(self, mock_post):
        mock_post.return_value = _mock_response(200)
        result_hash = register_hash(_RESOURCE_URI, _OXIGRAPH_URL)

        assert len(result_hash) == 16
        assert result_hash == _HASH

        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs.get("content", b"").decode("utf-8")
        assert "INSERT DATA" in body
        assert "urn:uuid-index" in body
        assert _RESOURCE_URI in body
        assert result_hash in body

    @patch("pocpod0_pipeline.uuid_index.httpx.post")
    def test_resolve_hash_returns_uri(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "results": {"bindings": [{"uri": {"value": _RESOURCE_URI}}]}
        })
        result = resolve_hash(_HASH, _OXIGRAPH_URL)
        assert result == _RESOURCE_URI

        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs.get("content", b"").decode("utf-8")
        assert "SELECT" in body
        assert _HASH in body

    @patch("pocpod0_pipeline.uuid_index.httpx.post")
    def test_resolve_hash_returns_none_when_not_found(self, mock_post):
        mock_post.return_value = _mock_response(200, {"results": {"bindings": []}})
        result = resolve_hash("nonexistent_hash", _OXIGRAPH_URL)
        assert result is None

    @patch("pocpod0_pipeline.uuid_index.httpx.post")
    def test_deregister_hash_sends_sparql_delete(self, mock_post):
        mock_post.return_value = _mock_response(200)
        deregister_hash(_HASH, _OXIGRAPH_URL)

        call_kwargs = mock_post.call_args.kwargs
        body = call_kwargs.get("content", b"").decode("utf-8")
        assert "DELETE" in body
        assert "urn:uuid-index" in body
        assert _HASH in body

    def test_register_unsafe_uri_raises(self):
        with pytest.raises(ValueError, match="Unsafe URI"):
            register_hash("javascript:xss()", _OXIGRAPH_URL)
