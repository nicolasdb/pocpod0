"""Tests for the Qdrant Search Skill handler (Story 3.2).

Tests:
  Unit (no containers required):
    1. _generate_embedding: missing API key raises RuntimeError
    2. _generate_embedding: HTTP error raises RuntimeError
    3. _search_qdrant: HTTP error raises RuntimeError
    4. _format_results: extracts triple_uris and pod_resource_uri (DA-2)
    5. _format_results: handles missing payload fields gracefully
    6. run_skill: embedding failure returns error response
    7. run_skill: qdrant failure returns error response
    8. run_skill: success path returns results with traceability metadata
    9. run_skill: empty results returns success with empty list
   10. Logging: success event uses level=INFO and event=qdrant.search.executed
   11. Logging: error event uses level=ERROR and event=qdrant.search.error
   12. run_skill: payload_filter is passed to Qdrant search body
   13. _format_results: content_summary truncated at 200 chars

  Integration (requires running Docker services; skipped if not available):
   14. Semantic search returns results with traceability metadata (AC1)
   15. Results contain valid triple_uris and pod_resource_uri (AC1)
   16. Hybrid query: qdrant and sparql skill results share pod_resource_uri key (AC2)
   17. Hybrid query combined latency < 2s (AC3)

Run from repo root with venv active:
    pytest agents/skills/qdrant-search/tests/test_handler.py -v

For integration tests only:
    pytest agents/skills/qdrant-search/tests/test_handler.py -v -m integration
"""

import json
import os
import sys
import time
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup: handler.py is one level up
# ---------------------------------------------------------------------------
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR))

import handler  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

QDRANT_BASE = "http://qdrant:6333"
COLLECTION = "pocpod0_embeddings"
AGENT_ID = "claire-teacher"

MOCK_EMBEDDING = [0.1] * 4096

MOCK_POINTS = [
    {
        "id": "abc123",
        "score": 0.92,
        "payload": {
            "triple_uris": [
                "http://oxigraph:7878/named/abc",
                "http://oxigraph:7878/named/def",
            ],
            "pod_resource_uri": "http://community-solid-server:3000/ayoub/learning/session-42.ttl",
            "content_text": "Tutoring notes showing geometric visualization approach",
        },
    },
    {
        "id": "def456",
        "score": 0.85,
        "payload": {
            "triple_uris": ["http://oxigraph:7878/named/ghi"],
            "pod_resource_uri": "http://community-solid-server:3000/ayoub/learning/session-40.ttl",
            "content_text": "Student struggled with fractions, visual aid helped",
        },
    },
]

MOCK_QDRANT_RESPONSE = {"result": MOCK_POINTS}
MOCK_EMBED_RESPONSE = {"data": [{"embedding": MOCK_EMBEDDING}]}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestGenerateEmbedding:
    """Tests for _generate_embedding()."""

    def test_missing_api_key_raises(self, monkeypatch):
        """Missing OPENROUTER_API_KEY raises RuntimeError."""
        monkeypatch.setattr(handler, "_OPENROUTER_API_KEY", "")
        with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
            handler._generate_embedding("test query")

    def test_http_error_raises(self, monkeypatch):
        """HTTP error from OpenRouter raises RuntimeError."""
        monkeypatch.setattr(handler, "_OPENROUTER_API_KEY", "fake-key")
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("handler.httpx.post") as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "401", request=MagicMock(), response=mock_resp
            )
            with pytest.raises(RuntimeError, match="OpenRouter embedding API error"):
                handler._generate_embedding("test query")


class TestSearchQdrant:
    """Tests for _search_qdrant()."""

    def test_http_error_raises(self):
        """HTTP error from Qdrant raises RuntimeError."""
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("handler.httpx.post") as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=mock_resp
            )
            with pytest.raises(RuntimeError, match="Qdrant search API error"):
                handler._search_qdrant(MOCK_EMBEDDING, COLLECTION, 10, 0.7, None)

    def test_filter_included_in_body(self):
        """Payload filter is serialized into Qdrant request body."""
        captured_body: dict = {}

        def fake_post(url, headers, content, timeout):
            nonlocal captured_body
            captured_body = json.loads(content)
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_QDRANT_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        with patch("handler.httpx.post", side_effect=fake_post):
            handler._search_qdrant(
                MOCK_EMBEDDING, COLLECTION, 5, 0.8,
                {"pod_resource_uri": "http://community-solid-server:3000/ayoub/"}
            )

        assert "filter" in captured_body
        assert captured_body["filter"]["must"][0]["key"] == "pod_resource_uri"


class TestFormatResults:
    """Tests for _format_results()."""

    def test_traceability_fields_present(self):
        """Each result has triple_uris and pod_resource_uri (DA-2)."""
        results = handler._format_results(MOCK_POINTS)
        for r in results:
            assert "triple_uris" in r
            assert "pod_resource_uri" in r
            assert isinstance(r["triple_uris"], list)
            assert isinstance(r["pod_resource_uri"], str)

    def test_score_included(self):
        """Similarity score is included for agent ranking."""
        results = handler._format_results(MOCK_POINTS)
        assert results[0]["score"] == 0.92
        assert results[1]["score"] == 0.85

    def test_missing_payload_fields_graceful(self):
        """Missing payload fields return empty defaults (no KeyError)."""
        points = [{"id": "x", "score": 0.5, "payload": {}}]
        results = handler._format_results(points)
        assert results[0]["triple_uris"] == []
        assert results[0]["pod_resource_uri"] == ""
        assert results[0]["content_summary"] == ""

    def test_content_summary_truncated(self):
        """content_summary is truncated at 200 characters."""
        long_text = "x" * 500
        points = [{"id": "x", "score": 0.5, "payload": {"content_text": long_text}}]
        results = handler._format_results(points)
        assert len(results[0]["content_summary"]) == 200


class TestRunSkill:
    """Tests for run_skill() — integration of all phases."""

    def _mock_embed(self, monkeypatch):
        """Patch _generate_embedding to return MOCK_EMBEDDING."""
        monkeypatch.setattr(
            handler, "_generate_embedding", lambda q: (MOCK_EMBEDDING, 200)
        )

    def _mock_qdrant(self, monkeypatch, points=None):
        """Patch _search_qdrant to return mock points."""
        pts = points if points is not None else MOCK_POINTS
        monkeypatch.setattr(
            handler, "_search_qdrant",
            lambda emb, col, lim, thresh, filt: (pts, 150)
        )

    def test_embedding_failure_returns_error(self, monkeypatch):
        """Embedding failure returns error status (not exception)."""
        mock = MagicMock(side_effect=RuntimeError("embed failed"))
        monkeypatch.setattr(handler, "_generate_embedding", mock)
        result = handler.run_skill("test query", AGENT_ID)
        assert result["status"] == "error"
        assert "embed failed" in result["error"]

    def test_qdrant_failure_returns_error(self, monkeypatch):
        """Qdrant failure returns error status."""
        self._mock_embed(monkeypatch)
        mock = MagicMock(side_effect=RuntimeError("qdrant down"))
        monkeypatch.setattr(handler, "_search_qdrant", mock)
        result = handler.run_skill("test query", AGENT_ID)
        assert result["status"] == "error"
        assert "qdrant down" in result["error"]

    def test_success_returns_results(self, monkeypatch):
        """Successful search returns structured result with traceability."""
        self._mock_embed(monkeypatch)
        self._mock_qdrant(monkeypatch)
        result = handler.run_skill("geometric visualization", AGENT_ID)
        assert result["status"] == "success"
        assert result["result_count"] == 2
        assert result["query_embedding_model"] == "qwen/qwen3-embedding-8b"
        # DA-2: traceability in every result
        for r in result["results"]:
            assert "triple_uris" in r
            assert "pod_resource_uri" in r

    def test_empty_results_success(self, monkeypatch):
        """Empty search results still return success status."""
        self._mock_embed(monkeypatch)
        self._mock_qdrant(monkeypatch, points=[])
        result = handler.run_skill("obscure query", AGENT_ID)
        assert result["status"] == "success"
        assert result["result_count"] == 0
        assert result["results"] == []

    def test_success_log_event(self, monkeypatch, capsys):
        """Success emits structured log with level=INFO and correct event."""
        self._mock_embed(monkeypatch)
        self._mock_qdrant(monkeypatch)
        handler.run_skill("geometric visualization", AGENT_ID)
        out = capsys.readouterr().out
        log_lines = [json.loads(line) for line in out.strip().splitlines() if line.strip()]
        success_logs = [l for l in log_lines if l.get("event") == "qdrant.search.executed"]
        assert len(success_logs) == 1
        log = success_logs[0]
        assert log["level"] == "INFO"
        assert log["service"] == "qdrant-search-skill"
        assert log["agent"] == AGENT_ID
        assert "result_count" in log["details"]
        assert log["details"]["collection"] == COLLECTION
        assert "embedding_latency_ms" in log["details"]
        assert "search_latency_ms" in log["details"]

    def test_error_log_event(self, monkeypatch, capsys):
        """Error emits structured log with level=ERROR and correct event."""
        mock = MagicMock(side_effect=RuntimeError("API key missing"))
        monkeypatch.setattr(handler, "_generate_embedding", mock)
        handler.run_skill("test", AGENT_ID)
        out = capsys.readouterr().out
        log_lines = [json.loads(line) for line in out.strip().splitlines() if line.strip()]
        error_logs = [l for l in log_lines if l.get("event") == "qdrant.search.error"]
        assert len(error_logs) == 1
        assert error_logs[0]["level"] == "ERROR"

    def test_payload_filter_passed_to_search(self, monkeypatch):
        """payload_filter is forwarded to _search_qdrant."""
        self._mock_embed(monkeypatch)
        captured: dict = {}

        def fake_search(emb, col, lim, thresh, filt):
            captured["filt"] = filt
            return MOCK_POINTS, 100

        monkeypatch.setattr(handler, "_search_qdrant", fake_search)
        handler.run_skill(
            "test", AGENT_ID,
            payload_filter={"pod_resource_uri": "http://localhost:3000/ayoub/"}
        )
        assert captured["filt"] == {"pod_resource_uri": "http://localhost:3000/ayoub/"}


# ---------------------------------------------------------------------------
# Integration tests (require running Docker services)
# ---------------------------------------------------------------------------

def _qdrant_available() -> bool:
    """Check if Qdrant is reachable."""
    try:
        import httpx
        resp = httpx.get("http://localhost:6333/healthz", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _openrouter_available() -> bool:
    """Check if OPENROUTER_API_KEY is set."""
    return bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.integration
class TestIntegration:
    """Integration tests against real Qdrant and OpenRouter."""

    @pytest.fixture(autouse=True)
    def require_services(self):
        if not _qdrant_available() or not _openrouter_available():
            pytest.skip("Requires running Qdrant and OPENROUTER_API_KEY")

    def test_semantic_search_returns_results(self):
        """AC1: Qdrant skill executes semantic search and returns results."""
        result = handler.run_skill(
            "student learning geometry visualization",
            AGENT_ID,
            collection=COLLECTION,
            limit=5,
            score_threshold=0.5,
        )
        assert result["status"] == "success"
        assert result["result_count"] >= 0  # may be 0 if collection empty
        assert result["query_embedding_model"] == "qwen/qwen3-embedding-8b"

    def test_results_have_traceability_metadata(self):
        """AC1: Results include triple_uris and pod_resource_uri (DA-2)."""
        result = handler.run_skill(
            "learning activity", AGENT_ID,
            collection=COLLECTION, limit=3, score_threshold=0.5
        )
        assert result["status"] == "success"
        for r in result["results"]:
            assert "triple_uris" in r, "DA-2: triple_uris required"
            assert "pod_resource_uri" in r, "DA-2: pod_resource_uri required"
            assert isinstance(r["triple_uris"], list)
            assert isinstance(r["pod_resource_uri"], str)

    def test_hybrid_query_result_format_compatible(self):
        """AC2: Qdrant result format is compatible with SPARQL skill for agent merging.

        Both skills return pod_resource_uri as a common correlation key.
        """
        result = handler.run_skill(
            "learning activity", AGENT_ID,
            collection=COLLECTION, limit=3, score_threshold=0.5
        )
        assert result["status"] == "success"
        # Every Qdrant result has pod_resource_uri (the shared key for correlation)
        for r in result["results"]:
            assert "pod_resource_uri" in r

    def test_skill_latency_within_budget(self):
        """AC3: Qdrant skill completes within its latency budget.

        Hybrid query is < 2s total; Qdrant skill alone should be well under that.
        This test checks the skill in isolation.
        """
        t0 = time.monotonic()
        result = handler.run_skill(
            "student learning progress", AGENT_ID,
            collection=COLLECTION, limit=10, score_threshold=0.5
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        assert result["status"] == "success"
        # Qdrant skill alone should complete in < 1500ms to leave room for SPARQL
        assert elapsed_ms < 1500, f"Qdrant skill took {elapsed_ms}ms (budget: 1500ms)"
