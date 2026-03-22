"""Embedding pipeline: Oxigraph RDF → OpenRouter embeddings → Qdrant.

Extracts semantically significant content from Oxigraph, generates embeddings
via the OpenRouter API (qwen/qwen3-embedding-8b), and batch-upserts them into
Qdrant with traceability metadata.

Protocol decision (API-3):
  Using REST (port 6333) — simpler to debug, adequate at POC scale.
  gRPC (port 6334) tested informally: no measurable difference for 303-scenario
  dataset; REST chosen for operational simplicity.

Error handling: log + continue — individual embedding failures never abort the run.
Write-only: this module NEVER reads from Qdrant for search. Reads are reserved
for the shared Qdrant skill (Story 3-2) and the troll agent.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional, Tuple

import httpx
from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from pocpod0_pipeline.utils import log_event

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
QDRANT_COLLECTION = "pocpod0_embeddings"
BATCH_SIZE = 100  # Points per Qdrant upsert batch
VECTOR_SIZE = 4096  # qwen3-embedding-8b output dimensions

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/embeddings"
QDRANT_BASE_URL = os.environ.get("QDRANT_BASE_URL", "http://localhost:6333")
OXIGRAPH_BASE_URL = os.environ.get("OXIGRAPH_BASE_URL", "http://localhost:7878")

# SPARQL query: extract semantically significant content with provenance.
#
# Story 2.3 pattern: named graph URI == Pod resource URI (no prov:wasDerivedFrom needed).
# Predicates confirmed from live data inspection (2026-03-20):
#   rdfs:label (11490), foaf:name (5613), poc-pod0:role (4122),
#   poc-pod0:scaledScore (2397), poc-pod0:success (2397), rdfs:comment (185)
# Excluded: originalXapiJson (raw JSON noise), originalXapiStatementId (UUID),
#           timestamp (not semantic), schema graph.
_SPARQL_CONTENT_QUERY = """\
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX poc:  <https://poc-pod0.edu/vocab/>
PREFIX schema: <http://schema.org/>
PREFIX dct:  <http://purl.org/dc/terms/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?graph ?text_value
WHERE {
  GRAPH ?graph {
    ?subject ?predicate ?text_value .
    FILTER (isLiteral(?text_value))
    FILTER (
      ?predicate = rdfs:label ||
      ?predicate = rdfs:comment ||
      ?predicate = foaf:name ||
      ?predicate = poc:role ||
      ?predicate = poc:scaledScore ||
      ?predicate = poc:success ||
      ?predicate = poc:completion ||
      ?predicate = poc:ext-language-context ||
      ?predicate = schema:provider ||
      ?predicate = dct:title ||
      ?predicate = dct:description ||
      ?predicate = skos:example
    )
  }
  FILTER (?graph != <https://poc-pod0.edu/vocab/schema>)
}
"""


# ---------------------------------------------------------------------------
# OpenRouter embedding client (AC-2)
# ---------------------------------------------------------------------------

class EmbeddingPipeline:
    """Generates embeddings via OpenRouter API (OpenAI-compatible endpoint)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Set it in .env or export it before running."
            )
        self._client = httpx.Client(timeout=60.0)

    def generate_embeddings(
        self,
        texts: List[str],
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for a list of texts via OpenRouter.

        Returns a list of embedding vectors (or None for failed items).
        Handles rate limiting (HTTP 429) with exponential backoff.
        """
        if not texts:
            return []

        t0 = time.time()
        for attempt in range(retries):
            try:
                resp = self._client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": EMBEDDING_MODEL, "input": texts},
                )
                duration_ms = int((time.time() - t0) * 1000)

                if resp.status_code == 429:
                    wait = retry_delay * (2 ** attempt)
                    log_event("embed.openrouter_call", "WARN", {
                        "model": EMBEDDING_MODEL,
                        "text_count": len(texts),
                        "duration_ms": duration_ms,
                        "rate_limited": True,
                        "retry_in_s": wait,
                    })
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                embeddings = [item["embedding"] for item in data["data"]]

                log_event("embed.openrouter_call", "INFO", {
                    "model": EMBEDDING_MODEL,
                    "text_count": len(texts),
                    "duration_ms": duration_ms,
                })
                return embeddings

            except Exception as exc:
                duration_ms = int((time.time() - t0) * 1000)
                log_event("embed.error", "ERROR", {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "details": {
                        "batch_size": len(texts),
                        "collection": QDRANT_COLLECTION,
                        "model": EMBEDDING_MODEL,
                        "attempt": attempt + 1,
                        "duration_ms": duration_ms,
                    },
                })
                if attempt < retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))

        # All retries exhausted — return None for each text
        return [None] * len(texts)

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Content extraction from Oxigraph (Task 3)
# ---------------------------------------------------------------------------

def _query_oxigraph(sparql: str, oxigraph_base: str) -> List[Dict]:
    """Execute a SPARQL SELECT query against Oxigraph. Returns list of binding dicts."""
    url = f"{oxigraph_base.rstrip('/')}/query"
    try:
        resp = httpx.post(
            url,
            content=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", {}).get("bindings", [])
    except Exception as exc:
        log_event("embed.error", "ERROR", {
            "error_type": type(exc).__name__,
            "message": str(exc),
            "details": {"phase": "sparql_query", "collection": QDRANT_COLLECTION, "model": EMBEDDING_MODEL},
        })
        return []


def extract_content_chunks(oxigraph_base: str) -> List[Dict]:
    """Query Oxigraph and return content chunks with traceability metadata.

    Each chunk is a dict:
      {
        "text": str,
        "triple_uris": [str, ...],
        "pod_resource_uri": str,
      }

    Groups text values by (graph, pod_resource_uri) so related content
    in the same resource is embedded together.
    """
    bindings = _query_oxigraph(_SPARQL_CONTENT_QUERY, oxigraph_base)
    if not bindings:
        log_event("embed.extract", "WARN", {
            "message": "No content bindings returned from Oxigraph",
            "details": {"collection": QDRANT_COLLECTION, "model": EMBEDDING_MODEL, "batch_size": 0},
        })
        return []

    # Group by (graph_uri, pod_resource_uri) — build text chunks
    groups: Dict[Tuple[str, str], List[str]] = {}

    for b in bindings:
        graph_uri = b.get("graph", {}).get("value", "")
        # Story 2.3: named graph URI == Pod resource URI (no prov:wasDerivedFrom needed)
        pod_uri = graph_uri
        text_val = b.get("text_value", {}).get("value", "")
        if not text_val.strip():
            continue
        key = (graph_uri, pod_uri)
        groups.setdefault(key, []).append(text_val)

    chunks = []
    for (graph_uri, pod_uri), texts in groups.items():
        combined_text = " | ".join(texts)
        # Use graph_uri as triple_uri representative (named graph = all triples in it)
        chunks.append({
            "text": combined_text,
            "triple_uris": [graph_uri],
            "pod_resource_uri": pod_uri,
        })

    log_event("embed.extract", "INFO", {
        "chunk_count": len(chunks),
        "details": {"collection": QDRANT_COLLECTION, "model": EMBEDDING_MODEL, "batch_size": len(chunks)},
    })
    return chunks


# ---------------------------------------------------------------------------
# Qdrant writer (Task 4)
# ---------------------------------------------------------------------------

class QdrantWriter:
    """Writes embedding points to Qdrant (write-only; never queries for search)."""

    def __init__(self, qdrant_url: str = QDRANT_BASE_URL):
        # Parse host/port from URL for qdrant-client
        from urllib.parse import urlparse
        parsed = urlparse(qdrant_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6333
        self._client = QdrantClient(host=host, port=port)
        self._collection = QDRANT_COLLECTION

    def ensure_collection(self) -> None:
        """Create the Qdrant collection if it does not already exist (idempotent)."""
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        # Payload index on pod_resource_uri for efficient reverse lookups (AC-5)
        self._client.create_payload_index(
            collection_name=self._collection,
            field_name="pod_resource_uri",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        log_event("embed.qdrant_collection_created", "INFO", {
            "collection": self._collection,
            "vector_size": VECTOR_SIZE,
            "distance": "Cosine",
        })

    def batch_upsert_points(
        self,
        chunks: List[Dict],
        vectors: List[Optional[List[float]]],
    ) -> int:
        """Upsert embedding points into Qdrant in batches.

        Returns count of successfully upserted points.
        """
        assert len(chunks) == len(vectors), "chunks and vectors must have same length"
        points = []

        for chunk, vector in zip(chunks, vectors):
            if vector is None:
                log_event("embed.qdrant_skip", "WARN", {
                    "reason": "embedding_failed",
                    "pod_resource_uri": chunk["pod_resource_uri"],
                })
                continue

            # Deterministic UUID from content hash
            content_hash = hashlib.sha256(
                (chunk["pod_resource_uri"] + chunk["text"]).encode("utf-8")
            ).hexdigest()
            point_id = str(uuid.UUID(content_hash[:32]))

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "triple_uris": chunk["triple_uris"],
                        "pod_resource_uri": chunk["pod_resource_uri"],
                        "content_text": chunk.get("text") or "",
                    },
                )
            )

        total_upserted = 0
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            t0 = time.time()
            try:
                self._client.upsert(
                    collection_name=self._collection,
                    points=batch,
                )
                duration_ms = int((time.time() - t0) * 1000)
                log_event("embed.qdrant_upsert", "INFO", {
                    "point_count": len(batch),
                    "collection": self._collection,
                    "duration_ms": duration_ms,
                })
                total_upserted += len(batch)
            except Exception as exc:
                duration_ms = int((time.time() - t0) * 1000)
                log_event("embed.error", "ERROR", {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "details": {
                        "batch_size": len(batch),
                        "collection": self._collection,
                        "model": EMBEDDING_MODEL,
                        "duration_ms": duration_ms,
                    },
                })

        return total_upserted

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Traceability utilities (Tasks 5 & 6)
# ---------------------------------------------------------------------------

def verify_forward_traceability(
    point_id: str,
    qdrant_writer: QdrantWriter,
    oxigraph_base: str = OXIGRAPH_BASE_URL,
    css_base: str = "http://localhost:3000",
) -> Dict:
    """Given a Qdrant point ID, verify the full forward traceability chain.

    Chain: embedding → triple_uris → Oxigraph triples → pod_resource_uri → Pod resource

    Returns dict with keys: point_id, triple_uris, pod_resource_uri,
    oxigraph_ok (bool), pod_ok (bool), error (str or None).
    """
    result: Dict = {
        "point_id": point_id,
        "triple_uris": [],
        "pod_resource_uri": None,
        "oxigraph_ok": False,
        "pod_ok": False,
        "error": None,
    }

    try:
        points = qdrant_writer._client.retrieve(
            collection_name=QDRANT_COLLECTION,
            ids=[point_id],
            with_payload=True,
        )
        if not points:
            result["error"] = f"Point {point_id} not found in Qdrant"
            return result

        payload = points[0].payload or {}
        triple_uris = payload.get("triple_uris", [])
        pod_uri = payload.get("pod_resource_uri", "")
        result["triple_uris"] = triple_uris
        result["pod_resource_uri"] = pod_uri

        # Verify each triple_uri resolves in Oxigraph
        if not triple_uris:
            all_ok = False
        else:
            all_ok = True
            url = f"{oxigraph_base.rstrip('/')}/query"
            for graph_uri in triple_uris:
                ask_query = f"ASK {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"
                try:
                    resp = httpx.post(
                        url,
                        content=ask_query.encode("utf-8"),
                        headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
                        timeout=10,
                    )
                    if not (resp.status_code == 200 and resp.json().get("boolean", False)):
                        all_ok = False
                except Exception:
                    all_ok = False

        result["oxigraph_ok"] = all_ok

        # Verify Pod resource URI resolves (HEAD request)
        if pod_uri:
            try:
                head_resp = httpx.head(pod_uri, timeout=5, follow_redirects=True)
                result["pod_ok"] = head_resp.status_code in (200, 204, 205)
            except Exception:
                result["pod_ok"] = False

    except Exception as exc:
        result["error"] = str(exc)

    return result


def get_points_for_resource(
    pod_resource_uri: str,
    qdrant_writer: QdrantWriter,
) -> List[Dict]:
    """Reverse traceability: given a Pod resource URI, return all derived embeddings.

    Queries Qdrant using a payload filter on pod_resource_uri.
    This is the read-side traceability utility (used by tests and Story 2-6).
    """
    results = qdrant_writer._client.scroll(
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
    points, _ = results
    return [
        {"id": str(p.id), "payload": p.payload}
        for p in points
    ]


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_embedding_pipeline(
    oxigraph_base: str = OXIGRAPH_BASE_URL,
    qdrant_base: str = QDRANT_BASE_URL,
    batch_size: int = BATCH_SIZE,
    dry_run: bool = False,
) -> Dict:
    """Run the full embedding pipeline. Returns summary dict."""
    log_event("embed.pipeline.start", "INFO", {
        "oxigraph_base": oxigraph_base,
        "qdrant_base": qdrant_base,
        "dry_run": dry_run,
    })

    # Extract content
    chunks = extract_content_chunks(oxigraph_base)
    if not chunks:
        log_event("embed.pipeline.complete", "WARN", {
            "message": "No content to embed",
            "details": {"batch_size": 0, "collection": QDRANT_COLLECTION, "model": EMBEDDING_MODEL},
        })
        return {"chunks_extracted": 0, "embeddings_generated": 0, "points_upserted": 0}

    if dry_run:
        log_event("embed.pipeline.complete", "INFO", {
            "dry_run": True,
            "chunks_extracted": len(chunks),
        })
        return {"chunks_extracted": len(chunks), "embeddings_generated": 0, "points_upserted": 0}

    # Generate embeddings
    embedder = EmbeddingPipeline()
    writer = QdrantWriter(qdrant_base)

    try:
        writer.ensure_collection()

        all_vectors: List[Optional[List[float]]] = []
        texts = [c["text"] for c in chunks]

        total_batches = (len(texts) + batch_size - 1) // batch_size
        for i in tqdm(range(0, len(texts), batch_size),
                      desc="Embedding batches", unit="batch", total=total_batches,
                      file=sys.stderr):
            batch_texts = texts[i : i + batch_size]
            log_event("embed.batch_start", "INFO", {
                "batch_size": len(batch_texts),
                "collection": QDRANT_COLLECTION,
                "model": EMBEDDING_MODEL,
            })
            vectors = embedder.generate_embeddings(batch_texts)
            all_vectors.extend(vectors)

        generated = sum(1 for v in all_vectors if v is not None)
        upserted = writer.batch_upsert_points(chunks, all_vectors)

        log_event("embed.pipeline.complete", "INFO", {
            "chunks_extracted": len(chunks),
            "embeddings_generated": generated,
            "points_upserted": upserted,
            "details": {"batch_size": batch_size, "collection": QDRANT_COLLECTION, "model": EMBEDDING_MODEL},
        })
        return {
            "chunks_extracted": len(chunks),
            "embeddings_generated": generated,
            "points_upserted": upserted,
        }
    finally:
        embedder.close()
        writer.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Embedding pipeline: Oxigraph RDF → Qdrant vectors")
    parser.add_argument("--oxigraph-url", default=OXIGRAPH_BASE_URL)
    parser.add_argument("--qdrant-url", default=QDRANT_BASE_URL)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true",
                        help="Extract content but do not call OpenRouter or write to Qdrant")
    args = parser.parse_args()

    result = run_embedding_pipeline(
        oxigraph_base=args.oxigraph_url,
        qdrant_base=args.qdrant_url,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    print(json.dumps(result))
    chunks = result.get("chunks_extracted", 0)
    upserted = result.get("points_upserted", 0)
    # Fail if there was content to embed but nothing was upserted (and not a dry-run)
    sys.exit(1 if chunks > 0 and upserted == 0 and not args.dry_run else 0)


if __name__ == "__main__":
    main()
