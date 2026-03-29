"""Qdrant Search Skill handler for OpenClaw agents.

CLI invocation pattern (used by OpenClaw exec tool):
    python handler.py --query TEXT \
                      --agent AGENT_ID \
                      [--collection COLLECTION_NAME] \
                      [--limit N] \
                      [--score-threshold F] \
                      [--filters '{"key": "value"}']

Arguments:
    --query           Natural-language semantic search query text
    --agent           Short agent identifier for logging (e.g. "claire-teacher")
    --collection      Qdrant collection name (default: pocpod0_embeddings)
    --limit           Max results to return (default: 10)
    --score-threshold Minimum similarity score threshold (default: 0.7)
    --filters         JSON object for payload pre-filter (e.g. {"pod_resource_uri": "..."})

Output:
    Structured JSON log lines emitted first (timestamp, service, level, event, ...)
    Final result JSON printed last: {"status": "success|error", ...}
    Exit code 0 on success, 1 on error.

Environment variables:
    QDRANT_URL         Qdrant REST API base URL (default: http://qdrant:6333)
    OPENROUTER_API_KEY OpenRouter API key for embedding generation (required)

Architecture notes:
    - DA-2: Every result includes triple_uris and pod_resource_uri for bidirectional traceability.
    - API-1: No REST wrapper; communicates directly with Qdrant REST API.
    - API-2: This skill handles only vector search. SPARQL skill handles graph queries.
             Agents compose hybrid queries by calling both skills and merging results.
    - No ACL check: embeddings are derived from data already ACL-checked at ingestion.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

# ---------------------------------------------------------------------------
# Configuration (environment-overridable for Docker-internal execution)
# ---------------------------------------------------------------------------

_QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
_OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"
_EMBED_MODEL = "qwen/qwen3-embedding-8b"

DEFAULT_COLLECTION = "pocpod0_embeddings"
DEFAULT_LIMIT = 10
DEFAULT_SCORE_THRESHOLD = 0.7

SERVICE_NAME = "qdrant-search-skill"

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(
    level: str,
    event: str,
    agent: str,
    details: dict[str, Any],
    duration_ms: int = 0,
    result_count: int | None = None,
) -> None:
    """Emit a structured JSON log entry to stdout (captured by docker-compose)."""
    entry: dict[str, Any] = {
        "timestamp": _iso_now(),
        "service": SERVICE_NAME,
        "level": level,
        "event": event,
        "agent": agent,
        "duration_ms": duration_ms,
    }
    if result_count is not None:
        details = dict(details)
        details["result_count"] = result_count
    entry["details"] = details
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# Embedding generation (OpenRouter)
# ---------------------------------------------------------------------------


def _generate_embedding(query_text: str) -> tuple[list[float], int]:
    """Generate an embedding vector for the search query via OpenRouter.

    Args:
        query_text: Natural-language query to embed.

    Returns:
        (embedding_vector, latency_ms)

    Raises:
        RuntimeError: if OPENROUTER_API_KEY is missing or API call fails.
    """
    if not _OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is required for embedding generation"
        )

    t0 = time.monotonic()
    try:
        resp = httpx.post(
            _OPENROUTER_EMBED_URL,
            headers={
                "Authorization": f"Bearer {_OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            content=json.dumps({
                "model": _EMBED_MODEL,
                "input": query_text,
            }).encode("utf-8"),
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"OpenRouter embedding API error (HTTP {exc.response.status_code}): {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"OpenRouter connection error: {exc}") from exc

    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        data = resp.json()
        embedding = data["data"][0]["embedding"]
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter embedding response: {exc}") from exc
    return embedding, latency_ms


# ---------------------------------------------------------------------------
# Qdrant similarity search
# ---------------------------------------------------------------------------


def _search_qdrant(
    embedding: list[float],
    collection: str,
    limit: int,
    score_threshold: float,
    payload_filter: dict[str, str] | None,
) -> tuple[list[dict], int]:
    """Execute similarity search against Qdrant REST API.

    Args:
        embedding:       Query embedding vector.
        collection:      Qdrant collection name.
        limit:           Maximum number of results to return.
        score_threshold: Minimum similarity score to include.
        payload_filter:  Optional key→value filter on payload fields.

    Returns:
        (points_list, latency_ms) where each point has id, score, payload.

    Raises:
        RuntimeError: on HTTP or connection error.
    """
    body: dict[str, Any] = {
        "vector": embedding,
        "limit": limit,
        "with_payload": True,
        "score_threshold": score_threshold,
    }

    # Build Qdrant filter from payload_filter dict
    if payload_filter:
        must_conditions = [
            {"key": k, "match": {"value": v}}
            for k, v in payload_filter.items()
        ]
        body["filter"] = {"must": must_conditions}

    search_url = f"{_QDRANT_URL}/collections/{quote(collection, safe='')}/points/search"
    t0 = time.monotonic()
    try:
        resp = httpx.post(
            search_url,
            headers={"Content-Type": "application/json"},
            content=json.dumps(body).encode("utf-8"),
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Qdrant search API error (HTTP {exc.response.status_code}): {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Qdrant connection error: {exc}") from exc

    latency_ms = int((time.monotonic() - t0) * 1000)
    try:
        points = resp.json().get("result", [])
    except ValueError as exc:
        raise RuntimeError(f"Unexpected Qdrant response (not JSON): {exc}") from exc
    return points, latency_ms


# ---------------------------------------------------------------------------
# Result formatting (DA-2: traceability metadata required)
# ---------------------------------------------------------------------------


def _format_results(points: list[dict]) -> list[dict]:
    """Format Qdrant points into structured results with traceability metadata.

    Every result includes triple_uris and pod_resource_uri (DA-2).
    content_summary is derived from payload content_text if available.
    """
    results = []
    for point in points:
        payload = point.get("payload", {})
        result: dict[str, Any] = {
            "score": point.get("score", 0.0),
            "content_summary": payload.get("content_text", "")[:500],
            "triple_uris": payload.get("triple_uris", []),
            # PRIV-1 fix (Story 5.2): new points store pod_uri_hash (opaque); legacy points have pod_resource_uri
            "pod_uri_hash": payload.get("pod_uri_hash") or None,
            # P-10: None (not "") for new post-fix points so consumers can distinguish absence from empty
            "pod_resource_uri": payload.get("pod_resource_uri") or None,
            "payload": payload,
        }
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Main skill execution
# ---------------------------------------------------------------------------


def run_skill(
    query: str,
    agent: str,
    collection: str = DEFAULT_COLLECTION,
    limit: int = DEFAULT_LIMIT,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    payload_filter: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute the Qdrant semantic search skill.

    Flow:
      1. Generate query embedding via OpenRouter API
      2. Execute similarity search against Qdrant
      3. Format results with traceability metadata (DA-2)
      4. Emit structured log with timing breakdown
      5. Return structured result

    Args:
        query:           Natural-language semantic search query.
        agent:           Short agent identifier for logging.
        collection:      Qdrant collection name.
        limit:           Maximum number of results.
        score_threshold: Minimum similarity score.
        payload_filter:  Optional payload key→value filter.

    Returns:
        Result dict: {"status": "success|error", ...}
    """
    t_start = time.monotonic()

    # ── Step 1: Generate query embedding ─────────────────────────────────────
    try:
        embedding, embed_latency_ms = _generate_embedding(query)
    except RuntimeError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "qdrant.search.error", agent,
             {"error": str(exc), "collection": collection, "phase": "embedding"},
             duration_ms)
        return {"status": "error", "error": str(exc)}

    # ── Step 2: Execute Qdrant similarity search ──────────────────────────────
    try:
        points, search_latency_ms = _search_qdrant(
            embedding, collection, limit, score_threshold, payload_filter
        )
    except RuntimeError as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        _log("ERROR", "qdrant.search.error", agent,
             {"error": str(exc), "collection": collection, "phase": "search",
              "embedding_latency_ms": embed_latency_ms},
             duration_ms)
        return {"status": "error", "error": str(exc)}

    # ── Step 3: Format results with traceability ──────────────────────────────
    results = _format_results(points)

    duration_ms = int((time.monotonic() - t_start) * 1000)
    top_score = results[0]["score"] if results else 0.0

    # ── Step 4: Emit structured log ────────────────────────────────────────────
    _log(
        "INFO",
        "qdrant.search.executed",
        agent,
        {
            "collection": collection,
            "embedding_latency_ms": embed_latency_ms,
            "search_latency_ms": search_latency_ms,
            "top_score": top_score,
        },
        duration_ms,
        result_count=len(results),
    )

    return {
        "status": "success",
        "results": results,
        "query_embedding_model": _EMBED_MODEL,
        "result_count": len(results),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qdrant Search Skill handler — semantic similarity search with provenance"
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language semantic search query text",
    )
    parser.add_argument(
        "--agent",
        required=True,
        help='Short agent identifier for logging (e.g. "claire-teacher")',
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Qdrant collection name (default: {DEFAULT_COLLECTION})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max results to return (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=DEFAULT_SCORE_THRESHOLD,
        dest="score_threshold",
        help=f"Minimum similarity score (default: {DEFAULT_SCORE_THRESHOLD})",
    )
    parser.add_argument(
        "--filters",
        default="{}",
        help='JSON object for payload filter (e.g. \'{"pod_resource_uri": "..."}\')' ,
    )
    args = parser.parse_args()

    try:
        payload_filter = json.loads(args.filters)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "error": f"Invalid --filters JSON: {exc}"}))
        sys.exit(1)
    if payload_filter and not isinstance(payload_filter, dict):
        print(json.dumps({"status": "error", "error": "--filters must be a JSON object, not a list or scalar"}))
        sys.exit(1)

    result = run_skill(
        query=args.query,
        agent=args.agent,
        collection=args.collection,
        limit=args.limit,
        score_threshold=args.score_threshold,
        payload_filter=payload_filter or None,
    )

    # Final result is the last JSON line output
    print(json.dumps(result))

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
