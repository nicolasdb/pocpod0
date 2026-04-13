---
name: qdrant-search
description: Semantic similarity search against the Qdrant vector store. Generates embeddings for the search query via OpenRouter and returns results with triple_uris and pod_resource_uri traceability metadata.
---

# Qdrant Search Skill

This skill executes semantic similarity search against Qdrant (`http://qdrant:6333`)
using query embeddings generated via OpenRouter API (model: `qwen/qwen3-embedding-8b`).

## Usage

When an agent needs to enrich structured query results with semantic context, invoke this skill with:
- `query`: the natural-language semantic search query
- `collection`: Qdrant collection name (default: `pocpod0_embeddings`)
- `limit`: max results to return (default: 10)
- `score_threshold`: minimum similarity score (default: 0.7)
- `filters`: optional payload filters (e.g. filter by pod_resource_uri)

## Output

Returns results with:
- `score`: cosine similarity score
- `content_summary`: human-readable description of the matched content
- `triple_uris`: list of Oxigraph triple URIs this embedding was derived from
- `pod_resource_uri`: the source Pod resource URI (traceability back to Solid Pod)

## Implementation

Use your `exec` tool to run the handler as a subprocess:

```bash
python3 {baseDir}/handler.py \
  --query "your semantic search query" \
  --collection pocpod0_embeddings \
  --limit 10 \
  --score-threshold 0.7
```

Handler: `{baseDir}/handler.py`
