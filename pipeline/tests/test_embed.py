"""Unit tests for embed.py — OpenRouter client, Qdrant upsert, payload schema, error handling."""

import hashlib
import uuid
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from pocpod0_pipeline.embed import (
    BATCH_SIZE,
    EMBEDDING_MODEL,
    QDRANT_COLLECTION,
    VECTOR_SIZE,
    EmbeddingPipeline,
    QdrantWriter,
    extract_content_chunks,
    get_points_for_resource,
    run_embedding_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_vector(size: int = VECTOR_SIZE) -> List[float]:
    return [0.01] * size


def _make_chunk(pod_uri: str = "http://localhost:3000/ayoub/learning/a.ttl") -> Dict:
    return {
        "text": "Ayoub completed a math assessment with score 85%",
        "triple_uris": ["http://localhost:3000/ayoub/learning/a.ttl"],
        "pod_resource_uri": pod_uri,
    }


# ---------------------------------------------------------------------------
# EmbeddingPipeline: constructor
# ---------------------------------------------------------------------------

def test_embedding_pipeline_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        EmbeddingPipeline(api_key="")


def test_embedding_pipeline_accepts_explicit_key():
    pipeline = EmbeddingPipeline(api_key="test-key")
    assert pipeline.api_key == "test-key"
    pipeline.close()


# ---------------------------------------------------------------------------
# EmbeddingPipeline: generate_embeddings (mocked HTTP)
# ---------------------------------------------------------------------------

def test_generate_embeddings_success(monkeypatch):
    pipeline = EmbeddingPipeline(api_key="test-key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [{"embedding": _fake_vector()}, {"embedding": _fake_vector()}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(pipeline._client, "post", return_value=mock_response):
        result = pipeline.generate_embeddings(["text one", "text two"])

    assert len(result) == 2
    assert all(v is not None for v in result)
    assert len(result[0]) == VECTOR_SIZE
    pipeline.close()


def test_generate_embeddings_returns_empty_for_empty_input():
    pipeline = EmbeddingPipeline(api_key="test-key")
    result = pipeline.generate_embeddings([])
    assert result == []
    pipeline.close()


def test_generate_embeddings_returns_none_on_api_failure(monkeypatch):
    pipeline = EmbeddingPipeline(api_key="test-key")

    with patch.object(pipeline._client, "post", side_effect=Exception("connection refused")):
        result = pipeline.generate_embeddings(["some text"], retries=1)

    assert result == [None]
    pipeline.close()


def test_generate_embeddings_retries_on_rate_limit(monkeypatch):
    """HTTP 429 triggers retry; second attempt succeeds."""
    pipeline = EmbeddingPipeline(api_key="test-key")

    rate_limited = MagicMock()
    rate_limited.status_code = 429

    success = MagicMock()
    success.status_code = 200
    success.raise_for_status = MagicMock()
    success.json.return_value = {"data": [{"embedding": _fake_vector()}]}

    with patch.object(pipeline._client, "post", side_effect=[rate_limited, success]):
        with patch("time.sleep"):  # don't actually sleep
            result = pipeline.generate_embeddings(["text"], retries=2, retry_delay=0.0)

    assert len(result) == 1
    assert result[0] is not None
    pipeline.close()


# ---------------------------------------------------------------------------
# QdrantWriter: payload metadata structure (AC-3)
# ---------------------------------------------------------------------------

def test_batch_upsert_payload_structure():
    """Verify triple_uris is list and pod_resource_uri is string in payload."""
    writer = QdrantWriter.__new__(QdrantWriter)
    writer._collection = QDRANT_COLLECTION

    upserted_points = []

    mock_client = MagicMock()
    def capture_upsert(collection_name, points):
        upserted_points.extend(points)

    mock_client.upsert.side_effect = capture_upsert
    writer._client = mock_client

    chunk = _make_chunk()
    vector = _fake_vector()

    writer.batch_upsert_points([chunk], [vector])

    assert len(upserted_points) == 1
    payload = upserted_points[0].payload
    assert isinstance(payload["triple_uris"], list)
    assert isinstance(payload["pod_resource_uri"], str)
    assert payload["pod_resource_uri"] == chunk["pod_resource_uri"]
    assert payload["triple_uris"] == chunk["triple_uris"]


def test_batch_upsert_skips_none_vectors():
    """Points with None vector are skipped, not upserted."""
    writer = QdrantWriter.__new__(QdrantWriter)
    writer._collection = QDRANT_COLLECTION

    upserted_points = []
    mock_client = MagicMock()
    mock_client.upsert.side_effect = lambda collection_name, points: upserted_points.extend(points)
    writer._client = mock_client

    chunks = [_make_chunk("http://localhost:3000/ayoub/a.ttl"),
              _make_chunk("http://localhost:3000/ayoub/b.ttl")]
    vectors = [_fake_vector(), None]

    count = writer.batch_upsert_points(chunks, vectors)

    assert count == 1
    assert len(upserted_points) == 1


def test_batch_upsert_deterministic_ids():
    """Same content produces same point UUID (idempotent upserts)."""
    writer = QdrantWriter.__new__(QdrantWriter)
    writer._collection = QDRANT_COLLECTION

    ids_seen = []
    mock_client = MagicMock()
    mock_client.upsert.side_effect = lambda collection_name, points: ids_seen.extend(
        [p.id for p in points]
    )
    writer._client = mock_client

    chunk = _make_chunk()
    vector = _fake_vector()

    writer.batch_upsert_points([chunk], [vector])
    writer.batch_upsert_points([chunk], [vector])

    assert ids_seen[0] == ids_seen[1], "Same content must produce same point ID"


def test_batch_upsert_handles_qdrant_error(capfd):
    """Qdrant connection failure logs error and continues without raising."""
    writer = QdrantWriter.__new__(QdrantWriter)
    writer._collection = QDRANT_COLLECTION

    mock_client = MagicMock()
    mock_client.upsert.side_effect = Exception("Qdrant unavailable")
    writer._client = mock_client

    chunk = _make_chunk()
    count = writer.batch_upsert_points([chunk], [_fake_vector()])

    # Does not raise, returns 0 upserted
    assert count == 0


# ---------------------------------------------------------------------------
# extract_content_chunks: mocked SPARQL query
# ---------------------------------------------------------------------------

def test_extract_content_chunks_groups_by_graph():
    """Multiple text values in same graph are concatenated into one chunk."""
    fake_bindings = [
        {
            "graph": {"value": "http://localhost:3000/ayoub/learning/a.ttl"},
            "pod_resource_uri": {"value": "http://localhost:3000/ayoub/learning/a.ttl"},
            "text_value": {"value": "Math Assessment"},
        },
        {
            "graph": {"value": "http://localhost:3000/ayoub/learning/a.ttl"},
            "pod_resource_uri": {"value": "http://localhost:3000/ayoub/learning/a.ttl"},
            "text_value": {"value": "completed"},
        },
    ]

    with patch("pocpod0_pipeline.embed._query_oxigraph", return_value=fake_bindings):
        chunks = extract_content_chunks("http://localhost:7878")

    assert len(chunks) == 1
    assert "Math Assessment" in chunks[0]["text"]
    assert "completed" in chunks[0]["text"]
    assert chunks[0]["pod_resource_uri"] == "http://localhost:3000/ayoub/learning/a.ttl"
    assert isinstance(chunks[0]["triple_uris"], list)


def test_extract_content_chunks_returns_empty_on_no_data():
    with patch("pocpod0_pipeline.embed._query_oxigraph", return_value=[]):
        chunks = extract_content_chunks("http://localhost:7878")
    assert chunks == []


def test_extract_content_chunks_skips_blank_text():
    fake_bindings = [
        {
            "graph": {"value": "http://g1"},
            "pod_resource_uri": {"value": "http://pod/r1"},
            "text_value": {"value": "   "},  # blank — should be skipped
        },
    ]
    with patch("pocpod0_pipeline.embed._query_oxigraph", return_value=fake_bindings):
        chunks = extract_content_chunks("http://localhost:7878")
    assert chunks == []


# ---------------------------------------------------------------------------
# get_points_for_resource: reverse traceability (AC-5)
# ---------------------------------------------------------------------------

def test_get_points_for_resource_returns_matching_points():
    writer = QdrantWriter.__new__(QdrantWriter)
    writer._collection = QDRANT_COLLECTION

    pod_uri = "http://localhost:3000/ayoub/learning/a.ttl"

    mock_point = MagicMock()
    mock_point.id = "abc-123"
    mock_point.payload = {
        "triple_uris": [pod_uri],
        "pod_resource_uri": pod_uri,
    }

    mock_client = MagicMock()
    mock_client.scroll.return_value = ([mock_point], None)
    writer._client = mock_client

    results = get_points_for_resource(pod_uri, writer)

    assert len(results) == 1
    assert results[0]["payload"]["pod_resource_uri"] == pod_uri

    # Verify the scroll was called with correct filter
    call_kwargs = mock_client.scroll.call_args[1]
    assert call_kwargs["collection_name"] == QDRANT_COLLECTION


# ---------------------------------------------------------------------------
# run_embedding_pipeline: dry_run mode
# ---------------------------------------------------------------------------

def test_run_embedding_pipeline_dry_run():
    fake_chunks = [_make_chunk(), _make_chunk("http://localhost:3000/claire/a.ttl")]

    with patch("pocpod0_pipeline.embed.extract_content_chunks", return_value=fake_chunks):
        result = run_embedding_pipeline(dry_run=True)

    assert result["chunks_extracted"] == 2
    assert result["embeddings_generated"] == 0
    assert result["points_upserted"] == 0


def test_run_embedding_pipeline_empty_oxigraph():
    with patch("pocpod0_pipeline.embed.extract_content_chunks", return_value=[]):
        result = run_embedding_pipeline()

    assert result["chunks_extracted"] == 0
    assert result["points_upserted"] == 0
