# Story 2.5: Qdrant Setup & Vector Embeddings

Status: ready-for-dev

## Story

As a **developer**,
I want vector embeddings generated for semantically significant content and stored in Qdrant with traceability metadata,
so that semantic search is possible and each embedding links back to its source triples and Pod resource.

## Acceptance Criteria

**AC-1: Qdrant collection creation and configuration**
Given the Qdrant service is healthy (port 6333 REST, port 6334 gRPC)
When the embedding pipeline initializes
Then a Qdrant collection is created with appropriate vector dimensions matching qwen/qwen3-embedding-8b output
And the collection configuration is defined in `infra/qdrant/config.yaml`

**AC-2: Embedding generation via OpenRouter API**
Given RDF triples loaded in Oxigraph with provenance (from Story 2-3)
When the embedding pipeline (`pipeline/src/pocpod0_pipeline/embed.py`) processes semantically significant content
Then embeddings are generated via OpenRouter API using model `qwen/qwen3-embedding-8b` (NFR21)
And the API key is read from `OPENROUTER_API_KEY` in `.env`

**AC-3: Batch upsert into Qdrant with payload metadata**
Given embeddings have been generated
When the pipeline writes to Qdrant
Then embeddings are batch-upserted into the Qdrant collection
And each point's payload contains `triple_uris` (array of source Oxigraph triple URIs) and `pod_resource_uri` (string, source Pod resource URI)

**AC-4: Forward traceability (embedding to Pod)**
Given any embedding stored in Qdrant
When I inspect its payload metadata
Then I can navigate: embedding -> `triple_uris` -> Oxigraph triples -> `pod_resource_uri` -> Pod resource

**AC-5: Reverse traceability (Pod to embeddings)**
Given a Pod resource URI
When I search Qdrant for points with matching `pod_resource_uri` in payload filter
Then all derived embeddings for that resource are returned

**AC-6: Pipeline is write-only for Qdrant**
Given the pipeline runs
When it interacts with Qdrant
Then it only writes (batch upsert) — it never queries Qdrant for search results
And read access to Qdrant is reserved for the shared Qdrant skill (Story 3-2) and the troll agent

**AC-7: Structured logging**
Given any pipeline operation (embedding generation, Qdrant upsert)
When the operation completes or fails
Then a structured JSON log entry is emitted: `{ timestamp, service: "pipeline", level, event: "embed.*", duration_ms, details: { batch_size, collection, model } }`

## Tasks / Subtasks

### Task 1: Define Qdrant collection configuration (AC-1)
- [ ] Update `infra/qdrant/config.yaml` with collection schema:
  - Collection name: `pocpod0_embeddings` (or similar snake_case name)
  - Vector size: determine from qwen/qwen3-embedding-8b output dimensions (check OpenRouter docs or test call)
  - Distance metric: cosine similarity
  - Payload index on `pod_resource_uri` for efficient reverse lookups (AC-5)
- [ ] Document the collection schema in the config file with comments

### Task 2: Implement OpenRouter embedding client (AC-2)
- [ ] Add OpenRouter API client code in `pipeline/src/pocpod0_pipeline/embed.py`
- [ ] Read `OPENROUTER_API_KEY` from environment
- [ ] Call OpenRouter API with model `qwen/qwen3-embedding-8b` for embedding generation
- [ ] Handle API rate limiting, retries, and errors gracefully (log + continue pattern)
- [ ] Accept a list of text strings, return list of embedding vectors
- [ ] Add `openai` or `httpx` to `pipeline/pyproject.toml` dependencies (OpenRouter is OpenAI-compatible)

### Task 3: Extract semantically significant content from Oxigraph (AC-2)
- [ ] Query Oxigraph via SPARQL to extract content suitable for embedding:
  - Text content from learning activities, assessment results, tutoring notes
  - Concatenate relevant triple values into embedding-worthy text chunks
- [ ] For each chunk, track the source `triple_uris` (array) and `pod_resource_uri` (string)
- [ ] Use the `prov:wasDerivedFrom` triples in Oxigraph to resolve Pod resource URIs

### Task 4: Implement batch upsert to Qdrant (AC-3)
- [ ] Use `qdrant-client` Python library to connect to Qdrant at `qdrant:6333`
- [ ] Create collection if it does not exist (idempotent)
- [ ] Batch upsert points with:
  - `id`: deterministic UUID derived from content hash or triple URIs
  - `vector`: embedding from OpenRouter
  - `payload`: `{ "triple_uris": [...], "pod_resource_uri": "..." }`
- [ ] Batch size: configurable, default reasonable (e.g., 100 points per batch)
- [ ] Add `qdrant-client` to `pipeline/pyproject.toml` dependencies

### Task 5: Implement forward traceability verification (AC-4)
- [ ] Write a utility function that given a Qdrant point ID:
  - Retrieves the point's payload
  - Extracts `triple_uris` and `pod_resource_uri`
  - Queries Oxigraph for each triple URI to confirm existence
  - Confirms the Pod resource URI resolves
- [ ] This is used by tests and by Story 2-6

### Task 6: Implement reverse traceability query (AC-5)
- [ ] Write a utility function that given a `pod_resource_uri`:
  - Queries Qdrant with payload filter `{ "must": [{ "key": "pod_resource_uri", "match": { "value": "<uri>" } }] }`
  - Returns all matching points
- [ ] Ensure Qdrant payload index on `pod_resource_uri` is created (Task 1)

### Task 7: Add structured logging (AC-7)
- [ ] Use the project logging pattern: structured JSON to stdout
- [ ] Log events:
  - `embed.batch_start`: `{ batch_size, collection }`
  - `embed.openrouter_call`: `{ model, text_count, duration_ms }`
  - `embed.qdrant_upsert`: `{ point_count, collection, duration_ms }`
  - `embed.error`: `{ error_type, message, details }`
- [ ] Errors log and continue — do not halt the pipeline for a single failed embedding

### Task 8: REST vs gRPC fog-of-war comparison (AC-1)
- [ ] Start with REST (port 6333) as the default — simpler to debug
- [ ] Optionally test gRPC (port 6334) for batch upsert performance
- [ ] Document the comparison findings in a comment in `embed.py`
- [ ] Pick one protocol and use it consistently (API-3 decision)

### Task 9: Write unit tests (AC-2, AC-3)
- [ ] Create `pipeline/tests/test_embed.py`
- [ ] Test OpenRouter client (mock API responses)
- [ ] Test batch upsert logic (mock Qdrant client)
- [ ] Test payload metadata structure (`triple_uris` is array, `pod_resource_uri` is string)
- [ ] Test error handling (API failure, Qdrant connection failure)

### Task 10: Write integration test (AC-4, AC-5)
- [ ] Verify end-to-end: Oxigraph has triples -> embed.py generates embeddings -> Qdrant has points with correct payloads
- [ ] Verify forward traceability: pick a random point, follow chain to Pod resource
- [ ] Verify reverse traceability: pick a Pod resource URI, find all derived embeddings
- [ ] Place in `tests/integration/` or `pipeline/tests/` as appropriate

## Dev Notes

### Qdrant Configuration

- **Image:** `qdrant/qdrant:v1.17.0` (already in docker-compose from Story 1-1)
- **Ports:** 6333 (REST API), 6334 (gRPC)
- **Docker hostname:** `qdrant` (on default Docker network)
- **Config file:** `infra/qdrant/config.yaml`
- **Storage volume:** `qdrant-data:/qdrant/storage`

### Embedding Model

- **Model:** `qwen/qwen3-embedding-8b` via OpenRouter API
- **API endpoint:** `https://openrouter.ai/api/v1/embeddings` (OpenAI-compatible)
- **API key:** `OPENROUTER_API_KEY` from `.env`
- **Output:** verify vector dimensions from the model (likely 4096-dimensional, confirm with test call)

### Qdrant Point Payload Schema

```json
{
  "triple_uris": [
    "urn:oxigraph:triple:abc123",
    "urn:oxigraph:triple:def456"
  ],
  "pod_resource_uri": "http://localhost:3000/ayoub/learning/activity-001.ttl"
}
```

### REST vs gRPC (API-3 Fog-of-War)

Both protocols are available. Start with REST (simpler, easier to debug with curl). Compare gRPC for batch upsert performance if time allows. Pick one and document the decision.

### Write-Only Pattern (API-3)

The pipeline is the ONLY component that writes to Qdrant. The shared Qdrant skill (Story 3-2) and troll agent read from Qdrant. This separation is enforced by convention, not by Qdrant permissions.

### Error Handling Pattern

Pipeline errors: log + continue. Do not halt 10K ingestion for one failed embedding. Each failed embedding is logged with full error details for later investigation.

### Python Dependencies (add to `pipeline/pyproject.toml`)

- `qdrant-client` — Qdrant Python client
- `httpx` or `openai` — for OpenRouter API calls (OpenAI-compatible endpoint)

### Naming Conventions

- Python module: `embed.py` (snake_case)
- Collection name: `pocpod0_embeddings` (snake_case)
- Functions: `generate_embeddings()`, `batch_upsert_points()`, `get_points_for_resource()`
- Classes: `EmbeddingPipeline`, `QdrantWriter`
- Constants: `EMBEDDING_MODEL`, `QDRANT_COLLECTION`, `BATCH_SIZE`

### Distrobox Isolation Note

When running inside distrobox, use `distrobox-host-exec` to access podman containers on the host:
```bash
distrobox-host-exec podman compose up qdrant
```

### Project Structure Notes

**Files to create:**
- `pipeline/src/pocpod0_pipeline/embed.py` — main embedding pipeline module
- `pipeline/tests/test_embed.py` — unit tests
- `infra/qdrant/config.yaml` — update with collection configuration

**Files to modify:**
- `pipeline/pyproject.toml` — add `qdrant-client`, `httpx`/`openai` dependencies

**Depends on:**
- Story 2-3: Oxigraph must have RDF triples with `prov:wasDerivedFrom` provenance loaded
- Story 1-1: Qdrant service must be running and healthy in docker-compose

### References

- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` (sections: DA-1, DA-2, API-3, INFRA-1)
- PRD: `_bmad-output/planning-artifacts/prd.md` (sections: FR11, FR12, NFR21, LLM Configuration)
- Epics doc: `_bmad-output/planning-artifacts/epics.md` (Story 2.5 acceptance criteria)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` (key: `story-2-5-qdrant-setup-vector-embeddings`)

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
