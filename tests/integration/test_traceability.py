"""Integration tests for bidirectional traceability (Story 2.6).

Requirements:
  - Oxigraph running at OXIGRAPH_BASE_URL (default: http://localhost:7878)
    with RDF triples loaded from Story 2.3
  - Qdrant running at QDRANT_BASE_URL (default: http://localhost:6333)
    with embeddings from Story 2.5
  - CSS running at CSS_BASE_URL (default: http://localhost:3000)

Run (from repo root, with venv active):
  pytest tests/integration/test_traceability.py -v

Isolation note: services run in podman containers.
  From distrobox: distrobox-host-exec podman compose up oxigraph qdrant css
"""

import os

import pytest
from qdrant_client import QdrantClient

from pocpod0_pipeline.traceability import (
    ConsistencyReport,
    ReverseTraceResult,
    TraceResult,
    trace_embedding_to_pod,
    trace_pod_to_embeddings,
    trace_pod_to_triples,
    trace_triples_to_embeddings,
    verify_provenance_consistency,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OXIGRAPH_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")
QDRANT_COLLECTION = "pocpod0_embeddings"

# A URI that was never ingested — used for negative tests
NONEXISTENT_URI = "http://localhost:3000/nonexistent-pod/learning/never-ingested.ttl"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qdrant_client():
    """Qdrant client connected to the live service."""
    from urllib.parse import urlparse
    parsed = urlparse(QDRANT_URL)
    client = QdrantClient(host=parsed.hostname or "localhost", port=parsed.port or 6333)
    yield client
    client.close()


def _find_point_with_fields(qdrant_client, *required_fields, scan_limit=20):
    """Return the first Qdrant point whose payload contains all required_fields.

    Scans up to scan_limit points so a single malformed first point doesn't
    cause all fixtures to skip on an otherwise healthy collection.
    """
    results, _ = qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        with_payload=True,
        with_vectors=False,
        limit=scan_limit,
    )
    for point in results:
        payload = point.payload or {}
        if all(payload.get(f) for f in required_fields):
            return point
    return None


@pytest.fixture(scope="module")
def any_point_id(qdrant_client):
    """Return the ID of any point in the Qdrant collection (for forward trace tests)."""
    point = _find_point_with_fields(qdrant_client, "triple_uris", "pod_resource_uri")
    if point is None:
        pytest.skip("No valid points found in Qdrant collection — run embedding pipeline first")
    return str(point.id)


@pytest.fixture(scope="module")
def any_pod_resource_uri(qdrant_client):
    """Return a pod_resource_uri that has embeddings in Qdrant."""
    point = _find_point_with_fields(qdrant_client, "pod_resource_uri")
    if point is None:
        pytest.skip("No points with pod_resource_uri found in Qdrant collection")
    return (point.payload or {})["pod_resource_uri"]


@pytest.fixture(scope="module")
def any_triple_uris(qdrant_client):
    """Return triple_uris from any Qdrant point."""
    point = _find_point_with_fields(qdrant_client, "triple_uris")
    if point is None:
        pytest.skip("No points with triple_uris found in Qdrant collection")
    return (point.payload or {})["triple_uris"]


# ---------------------------------------------------------------------------
# AC-1: Forward traceability — embedding to Pod
# ---------------------------------------------------------------------------


def test_forward_trace_embedding_to_pod(qdrant_client, any_point_id):
    """Pick a random Qdrant point, trace to Pod resource, assert chain complete."""
    result = trace_embedding_to_pod(
        qdrant_client=qdrant_client,
        oxigraph_url=OXIGRAPH_URL,
        point_id=any_point_id,
    )

    assert isinstance(result, TraceResult)
    assert result.point_id == any_point_id
    assert result.triple_uris, "triple_uris must be non-empty"
    assert result.pod_resource_uri, "pod_resource_uri must be non-empty"
    assert result.triples_found_in_oxigraph, (
        f"Named graphs {result.triple_uris} not found in Oxigraph"
    )
    assert result.pod_resource_exists, (
        f"Pod resource {result.pod_resource_uri} not accessible at CSS"
    )
    assert result.chain_complete, "Forward traceability chain must be complete"


# ---------------------------------------------------------------------------
# AC-2: Reverse traceability — Pod to embeddings
# ---------------------------------------------------------------------------


def test_reverse_trace_pod_to_all_derived(qdrant_client, any_pod_resource_uri):
    """Pick a known Pod resource URI, find all triples and embeddings, assert counts > 0."""
    result = trace_pod_to_embeddings(
        qdrant_client=qdrant_client,
        oxigraph_url=OXIGRAPH_URL,
        pod_resource_uri=any_pod_resource_uri,
    )

    assert isinstance(result, ReverseTraceResult)
    assert result.pod_resource_uri == any_pod_resource_uri
    assert result.derived_triple_count > 0, (
        f"No triples found in Oxigraph for {any_pod_resource_uri}"
    )
    assert result.derived_embedding_count > 0, (
        f"No embeddings found in Qdrant for {any_pod_resource_uri}"
    )
    assert result.embedding_point_ids, "embedding_point_ids must be non-empty"


# ---------------------------------------------------------------------------
# AC-3: Reverse traceability — Pod to triples
# ---------------------------------------------------------------------------


def test_reverse_trace_pod_to_triples(any_pod_resource_uri):
    """Verify SPARQL returns triples from the named graph for the Pod resource."""
    triples = trace_pod_to_triples(
        oxigraph_url=OXIGRAPH_URL,
        pod_resource_uri=any_pod_resource_uri,
    )

    assert triples, f"No triples returned from named graph <{any_pod_resource_uri}>"
    # Each triple must have non-empty subject, predicate, object
    for t in triples:
        assert t.subject, "Triple subject must be non-empty"
        assert t.predicate, "Triple predicate must be non-empty"
        assert t.object, "Triple object must be non-empty"


# ---------------------------------------------------------------------------
# AC-4: Triple to embedding mapping
# ---------------------------------------------------------------------------


def test_triple_to_embedding_mapping(qdrant_client, any_triple_uris):
    """Pick triple URIs, find corresponding embeddings."""
    points = trace_triples_to_embeddings(
        qdrant_client=qdrant_client,
        triple_uris=any_triple_uris,
    )

    assert points, (
        f"No embeddings found for triple_uris {any_triple_uris}"
    )
    for p in points:
        assert p["id"], "Point must have an ID"
        assert p["payload"], "Point must have a payload"
        assert "triple_uris" in p["payload"], "Payload must contain triple_uris"
        assert "pod_resource_uri" in p["payload"], "Payload must contain pod_resource_uri"


# ---------------------------------------------------------------------------
# AC-5: Provenance consistency check
# ---------------------------------------------------------------------------


def test_provenance_consistency(qdrant_client, any_pod_resource_uri):
    """Run consistency check, assert no orphaned embeddings."""
    report = verify_provenance_consistency(
        qdrant_client=qdrant_client,
        oxigraph_url=OXIGRAPH_URL,
        pod_resource_uri=any_pod_resource_uri,
    )

    assert isinstance(report, ConsistencyReport)
    assert report.pod_resource_uri == any_pod_resource_uri
    assert report.oxigraph_triple_count > 0, "Oxigraph must have triples for this resource"
    assert report.qdrant_point_count > 0, "Qdrant must have points for this resource"
    assert not report.orphaned_embeddings, (
        f"Orphaned embeddings found (data integrity issue): {report.orphaned_embeddings}"
    )
    assert report.consistent, "Provenance consistency check must pass"


# ---------------------------------------------------------------------------
# Negative test: non-existent Pod returns empty results
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Broken-chain contract: broken chain is a finding, not a crash
# ---------------------------------------------------------------------------


def test_broken_chain_returns_incomplete_not_exception(qdrant_client):
    """A point_id that does not exist must return chain_complete=False, not raise.

    Verifies the core error-handling contract stated in the module docstring:
    'a broken traceability chain is a finding, not a crash'.
    """
    result = trace_embedding_to_pod(
        qdrant_client=qdrant_client,
        oxigraph_url=OXIGRAPH_URL,
        point_id="00000000-0000-0000-0000-000000000000",
    )
    assert isinstance(result, TraceResult)
    assert result.chain_complete is False
    assert result.triple_uris == []
    assert result.pod_resource_uri == ""


# ---------------------------------------------------------------------------
# Negative test: non-existent Pod returns empty results
# ---------------------------------------------------------------------------


def test_nonexistent_pod_returns_empty(qdrant_client):
    """Traceability for a URI that was never ingested returns empty results."""
    triples = trace_pod_to_triples(
        oxigraph_url=OXIGRAPH_URL,
        pod_resource_uri=NONEXISTENT_URI,
    )
    assert triples == [], "Should return empty list for non-existent Pod URI"

    reverse = trace_pod_to_embeddings(
        qdrant_client=qdrant_client,
        oxigraph_url=OXIGRAPH_URL,
        pod_resource_uri=NONEXISTENT_URI,
    )
    assert reverse.derived_triple_count == 0
    assert reverse.derived_embedding_count == 0
    assert reverse.embedding_point_ids == []

    points = trace_triples_to_embeddings(
        qdrant_client=qdrant_client,
        triple_uris=[NONEXISTENT_URI],
    )
    assert points == [], "Should return empty list for non-existent triple URI"
