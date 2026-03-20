"""Bidirectional traceability: Embedding ↔ Triple ↔ Pod Resource.

Provenance model (DA-2, Story 2.3):
  Named graph URI == Pod resource URI.
  Qdrant payload: { "triple_uris": [...], "pod_resource_uri": "..." }

  Forward chain: Qdrant point → triple_uris → named graph in Oxigraph → pod_resource_uri
  Reverse chain: pod_resource_uri → GRAPH query in Oxigraph → Qdrant scroll by pod_resource_uri

NOTE: The original architecture anticipated prov:wasDerivedFrom triples, but the
actual Story 2.3 implementation uses named graphs (graph URI == Pod resource URI).
All SPARQL queries here use GRAPH <pod_resource_uri> { ... } accordingly.

Error handling: a broken traceability chain is a finding, not a crash.
Functions return typed result objects; callers decide what to do with inconsistencies.
"""

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from pocpod0_pipeline.utils import PROVISIONER_WEBID, log_event

QDRANT_COLLECTION = "pocpod0_embeddings"


# ---------------------------------------------------------------------------
# Data classes (Task 2)
# ---------------------------------------------------------------------------


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str


@dataclass
class TraceResult:
    point_id: str
    triple_uris: List[str]
    pod_resource_uri: str
    triples_found_in_oxigraph: bool
    pod_resource_exists: bool
    chain_complete: bool


@dataclass
class ReverseTraceResult:
    pod_resource_uri: str
    derived_triple_count: int
    derived_embedding_count: int
    triple_uris: List[str]
    embedding_point_ids: List[str]


@dataclass
class ConsistencyReport:
    pod_resource_uri: str
    oxigraph_triple_count: int
    qdrant_point_count: int
    orphaned_triples: List[str] = field(default_factory=list)
    orphaned_embeddings: List[str] = field(default_factory=list)
    consistent: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_SAFE_URI_RE = re.compile(r"^https?://[^<>\s]+$")


def _safe_uri(uri: str) -> bool:
    """Return True if uri is safe to interpolate into a SPARQL query."""
    return bool(_SAFE_URI_RE.match(uri))


def _css_auth_headers() -> dict:
    """Return CSS authentication headers (provisioner WebID)."""
    return {"Authorization": f"WebID {PROVISIONER_WEBID}"}


def _sparql_ask_graph(oxigraph_url: str, graph_uri: str) -> bool:
    """Return True if the named graph has at least one triple in Oxigraph."""
    if not _safe_uri(graph_uri):
        return False
    ask_query = f"ASK {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/query",
            content=ask_query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        return resp.status_code == 200 and resp.json().get("boolean", False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Task 4: trace_pod_to_triples (AC-2, AC-3)
# ---------------------------------------------------------------------------


def trace_pod_to_triples(oxigraph_url: str, pod_resource_uri: str) -> List[Triple]:
    """Return all triples in the named graph identified by pod_resource_uri.

    Uses GRAPH <pod_resource_uri> { ?s ?p ?o } — the actual provenance mechanism
    (named graph URI == Pod resource URI, per Story 2.3).
    """
    if not _safe_uri(pod_resource_uri):
        return []
    sparql = f"SELECT ?s ?p ?o WHERE {{ GRAPH <{pod_resource_uri}> {{ ?s ?p ?o }} }}"
    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/query",
            content=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        bindings = resp.json().get("results", {}).get("bindings", [])
        return [
            Triple(
                subject=b["s"]["value"],
                predicate=b["p"]["value"],
                object=b["o"]["value"],
            )
            for b in bindings
        ]
    except Exception as exc:
        log_event("traceability.pod_to_triples", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_resource_uri": pod_resource_uri,
        })
        return []


# ---------------------------------------------------------------------------
# Task 5: trace_triples_to_embeddings (AC-4)
# ---------------------------------------------------------------------------


def trace_triples_to_embeddings(
    qdrant_client: QdrantClient,
    triple_uris: List[str],
) -> List[dict]:
    """Return all Qdrant points whose triple_uris payload contains any of the given URIs.

    Iterates per URI and deduplicates (Qdrant v1.17 match.any on arrays is not
    relied upon for compatibility reasons).
    """
    seen_ids: set = set()
    points: List[dict] = []

    for uri in triple_uris:
        try:
            results, _ = qdrant_client.scroll(
                collection_name=QDRANT_COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="triple_uris",
                            match=MatchValue(value=uri),
                        )
                    ]
                ),
                with_payload=True,
                with_vectors=False,
                limit=1000,
            )
            for p in results:
                pid = str(p.id)
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    points.append({"id": pid, "payload": p.payload})
        except Exception as exc:
            log_event("traceability.triple_to_embedding", "ERROR", {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "triple_uri": uri,
            })

    return points


# ---------------------------------------------------------------------------
# Task 3: trace_embedding_to_pod (AC-1)
# ---------------------------------------------------------------------------


def trace_embedding_to_pod(
    qdrant_client: QdrantClient,
    oxigraph_url: str,
    point_id: str,
) -> TraceResult:
    """Forward traceability: Qdrant point → Oxigraph named graph → Pod resource.

    Chain:
      1. Retrieve Qdrant point by ID → extract triple_uris and pod_resource_uri
      2. For each triple_uri (named graph), verify it exists in Oxigraph (ASK)
      3. Verify Pod resource exists at CSS (HTTP HEAD with auth)
    """
    t0 = time.time()
    result = TraceResult(
        point_id=point_id,
        triple_uris=[],
        pod_resource_uri="",
        triples_found_in_oxigraph=False,
        pod_resource_exists=False,
        chain_complete=False,
    )

    try:
        points = qdrant_client.retrieve(
            collection_name=QDRANT_COLLECTION,
            ids=[point_id],
            with_payload=True,
        )
        if not points:
            log_event("traceability.forward_trace", "WARN", {
                "point_id": point_id,
                "chain_complete": False,
                "reason": "point_not_found",
                "duration_ms": int((time.time() - t0) * 1000),
            })
            return result

        payload = points[0].payload or {}
        triple_uris = payload.get("triple_uris", [])
        pod_uri = payload.get("pod_resource_uri", "")
        result.triple_uris = triple_uris
        result.pod_resource_uri = pod_uri

        # Verify each triple_uri (named graph) exists in Oxigraph
        if triple_uris:
            result.triples_found_in_oxigraph = all(
                _sparql_ask_graph(oxigraph_url, uri) for uri in triple_uris
            )

        # Verify Pod resource exists (HTTP HEAD with CSS auth)
        if pod_uri:
            try:
                head_resp = httpx.head(
                    pod_uri,
                    headers=_css_auth_headers(),
                    timeout=5,
                    follow_redirects=True,
                )
                result.pod_resource_exists = head_resp.status_code in (200, 204, 205)
            except Exception:
                result.pod_resource_exists = False

        result.chain_complete = (
            bool(triple_uris)
            and bool(pod_uri)
            and result.triples_found_in_oxigraph
            and result.pod_resource_exists
        )

    except Exception as exc:
        log_event("traceability.forward_trace", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "point_id": point_id,
        })

    duration_ms = int((time.time() - t0) * 1000)
    log_event("traceability.forward_trace", "INFO", {
        "point_id": point_id,
        "chain_complete": result.chain_complete,
        "duration_ms": duration_ms,
    })
    return result


# ---------------------------------------------------------------------------
# Task 4 (combined): trace_pod_to_embeddings (AC-2)
# ---------------------------------------------------------------------------


def trace_pod_to_embeddings(
    qdrant_client: QdrantClient,
    oxigraph_url: str,
    pod_resource_uri: str,
) -> ReverseTraceResult:
    """Reverse traceability: Pod resource URI → all derived triples and embeddings.

    1. Query Oxigraph: GRAPH <pod_resource_uri> { ?s ?p ?o } → derived triples
    2. Query Qdrant: scroll filter pod_resource_uri == uri → derived embeddings
    """
    t0 = time.time()

    triples = trace_pod_to_triples(oxigraph_url, pod_resource_uri)
    triple_uris = list({t.subject for t in triples})  # unique subject URIs

    # Qdrant scroll by pod_resource_uri
    embedding_points: List[dict] = []
    try:
        results, _ = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="pod_resource_uri",
                        match=MatchValue(value=pod_resource_uri),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )
        embedding_points = [{"id": str(p.id), "payload": p.payload} for p in results]
    except Exception as exc:
        log_event("traceability.reverse_trace", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_resource_uri": pod_resource_uri,
        })

    duration_ms = int((time.time() - t0) * 1000)
    log_event("traceability.reverse_trace", "INFO", {
        "pod_resource_uri": pod_resource_uri,
        "triple_count": len(triples),
        "embedding_count": len(embedding_points),
        "duration_ms": duration_ms,
    })

    return ReverseTraceResult(
        pod_resource_uri=pod_resource_uri,
        derived_triple_count=len(triples),
        derived_embedding_count=len(embedding_points),
        triple_uris=triple_uris,
        embedding_point_ids=[p["id"] for p in embedding_points],
    )


# ---------------------------------------------------------------------------
# Task 6: verify_provenance_consistency (AC-5)
# ---------------------------------------------------------------------------


def verify_provenance_consistency(
    qdrant_client: QdrantClient,
    oxigraph_url: str,
    pod_resource_uri: str,
) -> ConsistencyReport:
    """Cross-check that Oxigraph named graph and Qdrant payloads agree.

    Orphaned triples: triples in Oxigraph with no corresponding embedding.
      (acceptable — not all triples are semantically embedded)
    Orphaned embeddings: embeddings referencing triple_uris that don't exist in Oxigraph.
      (NOT acceptable — means data integrity issue)

    Consistency == no orphaned embeddings.
    """
    t0 = time.time()
    report = ConsistencyReport(
        pod_resource_uri=pod_resource_uri,
        oxigraph_triple_count=0,
        qdrant_point_count=0,
    )

    # Oxigraph side: all triples in the named graph
    triples = trace_pod_to_triples(oxigraph_url, pod_resource_uri)
    report.oxigraph_triple_count = len(triples)

    # Qdrant side: all embeddings for this pod_resource_uri
    try:
        results, _ = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="pod_resource_uri",
                        match=MatchValue(value=pod_resource_uri),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )
        embedding_points = results
    except Exception as exc:
        log_event("traceability.consistency_check", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_resource_uri": pod_resource_uri,
        })
        embedding_points = []

    report.qdrant_point_count = len(embedding_points)

    # Check orphaned embeddings: embedding references a named graph that doesn't exist
    for point in embedding_points:
        payload = point.payload or {}
        for uri in payload.get("triple_uris", []):
            if not _sparql_ask_graph(oxigraph_url, uri):
                report.orphaned_embeddings.append(str(point.id))
                break

    # Check orphaned triples: triples in the Oxigraph named graph that have no
    # embedding referencing them (informational only — not all content is embedded).
    # Compare triple subject URIs from Oxigraph against the triple_uris collected
    # from all embedding payloads.
    embedding_triple_uris: set = set()
    for point in embedding_points:
        payload = point.payload or {}
        embedding_triple_uris.update(payload.get("triple_uris", []))

    for triple in triples:
        if triple.subject not in embedding_triple_uris:
            report.orphaned_triples.append(triple.subject)

    # Consistent == no orphaned embeddings (orphaned triples are acceptable)
    report.consistent = len(report.orphaned_embeddings) == 0

    duration_ms = int((time.time() - t0) * 1000)
    log_event("traceability.consistency_check", "INFO", {
        "pod_resource_uri": pod_resource_uri,
        "consistent": report.consistent,
        "orphaned_triples": len(report.orphaned_triples),
        "orphaned_embeddings": len(report.orphaned_embeddings),
        "duration_ms": duration_ms,
    })

    return report
