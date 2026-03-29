"""UUID lookup index: opaque hash ↔ Pod resource URI mapping in Oxigraph.

Stores hash→URI mappings in a dedicated named graph <urn:uuid-index> so that
authorized services can resolve an opaque pod_uri_hash back to the original URI.

Design:
  - Named graph: <urn:uuid-index>
  - Triple pattern: <urn:uuid-index:{hash}> pocpod0:mapsTo <{pod_resource_uri}>
  - DROP GRAPH <pod-resource-uri> does NOT touch <urn:uuid-index> (separate graph).
  - deregister_hash cleans up the index after deletion cascade step 3 succeeds.

Isolation notes:
  - distrobox-host-exec works perfectly for accessing podman containers from within distrobox
"""

import hashlib
import re
from typing import Optional

import httpx

from pocpod0_pipeline.utils import log_event

POCPOD0_VOCAB = "https://poc-pod0.edu/vocab/"
UUID_INDEX_GRAPH = "urn:uuid-index"

_SAFE_URI_RE = re.compile(r"^https?://[^<>\s]+$")


def _safe_uri(uri: str) -> bool:
    return bool(_SAFE_URI_RE.match(uri))


def _compute_hash(pod_resource_uri: str) -> str:
    """SHA-256(uri)[:16] — 64 bits of entropy, stable identifier, not a security secret."""
    return hashlib.sha256(pod_resource_uri.encode()).hexdigest()[:16]


def register_hash(pod_resource_uri: str, oxigraph_url: str) -> str:
    """Compute hash and write <urn:uuid-index:{hash}> pocpod0:mapsTo <{uri}> into Oxigraph.

    Returns the computed hash.
    Idempotent: re-inserting the same triple is safe (SPARQL INSERT DATA is additive
    but Oxigraph deduplicates triples in named graphs).
    """
    if not _safe_uri(pod_resource_uri):
        raise ValueError(f"Unsafe URI rejected for uuid_index registration: {pod_resource_uri!r}")

    pod_uri_hash = _compute_hash(pod_resource_uri)
    subject_uri = f"urn:uuid-index:{pod_uri_hash}"

    sparql = (
        f"PREFIX pocpod0: <{POCPOD0_VOCAB}>\n"
        "INSERT DATA {\n"
        f"  GRAPH <{UUID_INDEX_GRAPH}> {{\n"
        f"    <{subject_uri}> pocpod0:mapsTo <{pod_resource_uri}> .\n"
        "  }\n"
        "}"
    )

    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/update",
            content=sparql.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            timeout=15,
        )
        resp.raise_for_status()
        log_event("uuid_index.register", "INFO", {
            "pod_uri_hash": pod_uri_hash,
            "pod_resource_uri": pod_resource_uri,
        })
    except Exception as exc:
        log_event("uuid_index.register", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_uri_hash": pod_uri_hash,
        })
        raise

    return pod_uri_hash


def resolve_hash(pod_uri_hash: str, oxigraph_url: str) -> Optional[str]:
    """Resolve an opaque hash back to the original Pod resource URI.

    Queries the <urn:uuid-index> named graph.
    Returns the URI string, or None if not found.
    """
    subject_uri = f"urn:uuid-index:{pod_uri_hash}"
    sparql = (
        f"PREFIX pocpod0: <{POCPOD0_VOCAB}>\n"
        "SELECT ?uri WHERE {\n"
        f"  GRAPH <{UUID_INDEX_GRAPH}> {{\n"
        f"    <{subject_uri}> pocpod0:mapsTo ?uri .\n"
        "  }\n"
        "}"
    )

    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/query",
            content=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        bindings = resp.json().get("results", {}).get("bindings", [])
        if bindings:
            return bindings[0]["uri"]["value"]
        return None
    except Exception as exc:
        log_event("uuid_index.resolve", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_uri_hash": pod_uri_hash,
        })
        return None


def deregister_hash(pod_uri_hash: str, oxigraph_url: str) -> None:
    """Remove the hash→URI mapping triple from <urn:uuid-index> after deletion cascade.

    Called after Qdrant delete succeeds (step 3) to clean up the index.
    Idempotent: deleting a non-existent triple is a no-op.
    """
    subject_uri = f"urn:uuid-index:{pod_uri_hash}"
    sparql = (
        f"PREFIX pocpod0: <{POCPOD0_VOCAB}>\n"
        "DELETE WHERE {\n"
        f"  GRAPH <{UUID_INDEX_GRAPH}> {{\n"
        f"    <{subject_uri}> pocpod0:mapsTo ?uri .\n"
        "  }\n"
        "}"
    )

    try:
        resp = httpx.post(
            f"{oxigraph_url.rstrip('/')}/update",
            content=sparql.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"},
            timeout=15,
        )
        resp.raise_for_status()
        log_event("uuid_index.deregister", "INFO", {
            "pod_uri_hash": pod_uri_hash,
        })
    except Exception as exc:
        log_event("uuid_index.deregister", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "pod_uri_hash": pod_uri_hash,
        })
        raise
