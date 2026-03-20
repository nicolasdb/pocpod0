"""Integration tests for embed.py — end-to-end Oxigraph → embeddings → Qdrant.

Requires live services:
  - Oxigraph at OXIGRAPH_BASE_URL (default: http://localhost:7878) with RDF triples loaded
  - Qdrant at QDRANT_BASE_URL (default: http://localhost:6333)
  - OPENROUTER_API_KEY set in environment (or .env)

These tests are skipped if services are unavailable.

Isolation note: distrobox-host-exec provides access to podman containers
from within the distrobox dev environment (see dev_workflow_distrobox.md).
"""

import os
import time

import pytest
import requests

from pocpod0_pipeline.embed import (
    QDRANT_COLLECTION,
    QdrantWriter,
    extract_content_chunks,
    get_points_for_resource,
    run_embedding_pipeline,
    verify_forward_traceability,
)

OXIGRAPH_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")


# ---------------------------------------------------------------------------
# Service availability fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def oxigraph_healthy():
    try:
        resp = requests.get(OXIGRAPH_URL, timeout=5)
        return resp.status_code < 500
    except Exception:
        return False


@pytest.fixture(scope="session")
def qdrant_healthy():
    try:
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def openrouter_key():
    return os.environ.get("OPENROUTER_API_KEY", "")


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_extract_content_chunks_from_live_oxigraph(oxigraph_healthy):
    """Oxigraph has triples loaded → extract_content_chunks returns non-empty list."""
    if not oxigraph_healthy:
        pytest.skip("Oxigraph not available")

    chunks = extract_content_chunks(OXIGRAPH_URL)
    assert len(chunks) > 0, "Expected at least 1 content chunk from Oxigraph"

    # Validate structure of each chunk
    for chunk in chunks:
        assert isinstance(chunk["text"], str) and chunk["text"].strip()
        assert isinstance(chunk["triple_uris"], list) and len(chunk["triple_uris"]) > 0
        assert isinstance(chunk["pod_resource_uri"], str) and chunk["pod_resource_uri"]


def test_end_to_end_embedding_pipeline(oxigraph_healthy, qdrant_healthy, openrouter_key):
    """Full pipeline: Oxigraph → embeddings → Qdrant points with correct payloads."""
    if not oxigraph_healthy:
        pytest.skip("Oxigraph not available")
    if not qdrant_healthy:
        pytest.skip("Qdrant not available")
    if not openrouter_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    result = run_embedding_pipeline(
        oxigraph_base=OXIGRAPH_URL,
        qdrant_base=QDRANT_URL,
    )

    assert result["chunks_extracted"] > 0
    assert result["embeddings_generated"] > 0
    assert result["points_upserted"] > 0


def test_forward_traceability(oxigraph_healthy, qdrant_healthy, openrouter_key):
    """AC-4: Pick a random Qdrant point, follow chain to Pod resource."""
    if not oxigraph_healthy:
        pytest.skip("Oxigraph not available")
    if not qdrant_healthy:
        pytest.skip("Qdrant not available")
    if not openrouter_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    writer = QdrantWriter(QDRANT_URL)
    try:
        # Scroll to find any existing point
        points, _ = writer._client.scroll(
            collection_name=QDRANT_COLLECTION,
            with_payload=True,
            limit=1,
        )
        if not points:
            pytest.skip("No points in Qdrant collection — run pipeline first")

        point_id = str(points[0].id)
        result = verify_forward_traceability(point_id, writer, OXIGRAPH_URL)

        assert result["error"] is None, f"Traceability error: {result['error']}"
        assert len(result["triple_uris"]) > 0
        assert result["pod_resource_uri"]
        assert result["oxigraph_ok"], (
            f"Triple URIs not found in Oxigraph: {result['triple_uris']}"
        )
    finally:
        writer.close()


def test_reverse_traceability(oxigraph_healthy, qdrant_healthy, openrouter_key):
    """AC-5: Given a Pod resource URI, find all derived embeddings via payload filter."""
    if not oxigraph_healthy:
        pytest.skip("Oxigraph not available")
    if not qdrant_healthy:
        pytest.skip("Qdrant not available")
    if not openrouter_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    writer = QdrantWriter(QDRANT_URL)
    try:
        # Pick the pod_resource_uri from any existing point
        points, _ = writer._client.scroll(
            collection_name=QDRANT_COLLECTION,
            with_payload=True,
            limit=1,
        )
        if not points:
            pytest.skip("No points in Qdrant collection — run pipeline first")

        pod_uri = points[0].payload["pod_resource_uri"]
        results = get_points_for_resource(pod_uri, writer)

        assert len(results) >= 1
        for r in results:
            assert r["payload"]["pod_resource_uri"] == pod_uri
    finally:
        writer.close()
