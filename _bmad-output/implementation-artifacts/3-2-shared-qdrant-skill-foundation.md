# Story 3.2: [foundation] Shared Qdrant Skill & Hybrid Query Composition

Status: done

## Story

As a **developer**,
I want a shared Qdrant skill for semantic search and the ability for agents to compose hybrid queries by merging SPARQL and vector results,
so that agents can deliver semantically enriched insights beyond what structured queries alone provide.

## Acceptance Criteria

**AC1: Qdrant skill executes semantic search with traceability**
Given the shared Qdrant skill (`agents/skills/qdrant-search/`)
When an agent calls the skill with a semantic search query
Then the skill executes a similarity search against Qdrant
And returns results with `triple_uris` and `pod_resource_uri` traceability metadata

**AC2: Hybrid query composition by agents**
Given an agent wants a hybrid query result
When the agent calls both the SPARQL skill and the Qdrant skill
Then the agent receives both result sets
And the agent merges them based on its persona context and query intent

**AC3: Hybrid query performance**
Given a hybrid query execution
When both skills return results
Then the combined response time is < 2s (NFR2)

## Tasks / Subtasks

### Task 1: Create Qdrant skill directory structure (AC1)
- [x] Create `agents/skills/qdrant-search/SKILL.md` — Skill definition file
- [x] Create `agents/skills/qdrant-search/handler.py` — Main skill handler

### Task 2: Create SKILL.md definition (AC1)
- [x] Define `agents/skills/qdrant-search/SKILL.md` with:
  - Skill name: `qdrant-search`
  - Description: Shared Qdrant skill for semantic similarity search with provenance
  - Input schema: semantic query text, optional filters (collection, limit, score threshold)
  - Output schema: results with similarity scores, `triple_uris`, `pod_resource_uri` metadata
  - Dependencies: Qdrant endpoint, OpenRouter embedding API (for query embedding)

### Task 3: Implement query embedding generation (AC1)
- [x] In `handler.py`, implement function to generate embeddings for the search query:
  1. Call OpenRouter API with model `qwen/qwen3-embedding-8b`
  2. Send the semantic search query text
  3. Receive embedding vector
  4. Use this vector for Qdrant similarity search
- [x] OpenRouter API key: reference `OPENROUTER_API_KEY` from `.env`
- [x] Handle API errors gracefully: log error, return meaningful error response to agent

### Task 4: Implement Qdrant similarity search (AC1)
- [x] In `handler.py`, implement similarity search against Qdrant:
  1. Take the query embedding vector from Task 3
  2. Execute search against Qdrant REST API at `http://qdrant:6333`
  3. Qdrant search endpoint: `POST http://qdrant:6333/collections/{collection_name}/points/search`
  4. Request body:
     ```json
     {
       "vector": [0.1, 0.2, ...],
       "limit": 10,
       "with_payload": true
     }
     ```
  5. Parse response: extract points with similarity scores and payloads
  6. From each point's payload, extract traceability metadata:
     - `triple_uris`: list of Oxigraph triple URIs this embedding was derived from
     - `pod_resource_uri`: the source Pod resource URI
  7. Return structured results to the calling agent

### Task 5: Implement result formatting with provenance (AC1)
- [x] Format Qdrant search results as structured response:
  ```json
  {
    "status": "success",
    "results": [
      {
        "score": 0.92,
        "content_summary": "Tutoring notes showing geometric visualization approach",
        "triple_uris": [
          "http://oxigraph:7878/triple/abc123",
          "http://oxigraph:7878/triple/def456"
        ],
        "pod_resource_uri": "http://community-solid-server:3000/ayoub/learning/tutoring-session-42.ttl",
        "payload": { ... }
      }
    ],
    "query_embedding_model": "qwen/qwen3-embedding-8b",
    "result_count": 10
  }
  ```
- [x] Every result must include `triple_uris` and `pod_resource_uri` for bidirectional traceability (DA-2)
- [x] Include similarity score for each result so agents can use it for ranking/merging

### Task 6: Implement structured JSON logging (AC1, AC3)
- [x] Every skill invocation logs a structured JSON entry to stdout:
  ```json
  {
    "timestamp": "ISO-8601",
    "service": "qdrant-search-skill",
    "level": "INFO",
    "event": "qdrant.search.executed",
    "agent": "claire-teacher",
    "duration_ms": 350,
    "details": {
      "collection": "learning_content",
      "result_count": 10,
      "top_score": 0.92,
      "embedding_latency_ms": 200,
      "search_latency_ms": 150
    }
  }
  ```
- [x] Log embedding generation latency and search latency separately for performance diagnosis
- [x] Error events use `"event": "qdrant.search.error"` with `"level": "ERROR"`
- [x] Log to stdout so docker-compose captures it

### Task 7: Implement hybrid query composition support (AC2)
- [x] The Qdrant skill itself does NOT merge results — it returns its own results independently
- [x] Document the hybrid query protocol for agents (to be used in agent.yaml configs for Stories 3.3+):
  1. Agent determines query type: graph-only, semantic, or hybrid
  2. **Graph-only:** Agent calls SPARQL skill only (`sparql-query`)
  3. **Semantic-only:** Agent calls Qdrant skill only (`qdrant-search`)
  4. **Hybrid:** Agent calls BOTH skills, receives two result sets, merges them itself
  5. Agent merges based on persona context (e.g., Claire prioritizes cross-institutional insights)
  6. Agent formats the merged results for its persona's narrative
- [x] The skill's response format must be compatible with the SPARQL skill's response format so agents can correlate results via `pod_resource_uri` fields present in both
- [x] Ensure both skills return `pod_resource_uri` as a common key for result correlation

### Task 8: Performance validation (AC3)
- [x] Measure end-to-end latency for a hybrid query (SPARQL skill + Qdrant skill):
  - SPARQL skill: query execution < 500ms (NFR1)
  - Qdrant skill: embedding generation + similarity search
  - Combined: < 2s total (NFR2)
- [x] If the two skills are called in parallel by the agent, the combined latency is max(SPARQL, Qdrant) not sum
- [x] Log timing breakdown in structured logs for performance monitoring
- [x] If latency exceeds 2s, investigate: is it embedding generation (OpenRouter API) or search (Qdrant local)?

### Task 9: Integration verification (AC1, AC2, AC3)
- [x] Verify the Qdrant skill can execute a semantic search and return results with traceability
- [x] Verify results contain valid `triple_uris` and `pod_resource_uri` matching data loaded in Story 2.5
- [x] Verify an agent can call both SPARQL skill and Qdrant skill and receive compatible result formats
- [x] Verify combined hybrid query latency < 2s
- [x] Verify structured logging output for success and error cases
- [x] Verify the skill works from within distrobox (use `distrobox-host-exec` for podman container access)

## Dev Notes

### Architecture Decisions Referenced

- **DA-2:** Provenance & Traceability Schema. Every Qdrant point payload includes `{ "triple_uris": [...], "pod_resource_uri": "..." }`. This skill reads that metadata and returns it to agents.
- **API-1:** No REST API wrapper. The skill communicates directly with Qdrant via its native REST API.
- **API-2:** Two separate skills keep concerns clean. SPARQL skill (Story 3.1) handles graph queries with ACL enforcement. This Qdrant skill handles vector similarity search. Agents compose hybrid queries by calling both.
- **API-3:** Qdrant Access Pattern. Pipeline writes to Qdrant during ingestion. This skill only reads. Troll agent reads directly (bypasses skill). REST vs gRPC: the protocol choice may have been resolved during Story 2.5 implementation. If REST was chosen, use port 6333. If gRPC was chosen, use port 6334. Check Story 2.5 implementation for the protocol decision.
- **NFR2:** Hybrid SPARQL + vector queries < 2s response time at PoC scale.

### Qdrant Connection Details

- Docker service name: `qdrant`
- REST API endpoint: `http://qdrant:6333` (preferred unless Story 2.5 chose gRPC)
- gRPC endpoint: `qdrant:6334` (alternative)
- Image: `qdrant/qdrant:v1.17.0`
- Collection name: check Story 2.5 implementation for the collection name used during embedding ingestion
- Payload schema per point (set up in Story 2.5):
  ```json
  {
    "triple_uris": ["http://oxigraph:7878/...", ...],
    "pod_resource_uri": "http://community-solid-server:3000/ayoub/learning/...",
    "content_text": "Original text that was embedded",
    "...": "other metadata from ingestion"
  }
  ```

### OpenRouter Embedding API

- Model: `qwen/qwen3-embedding-8b`
- Used for: converting the agent's semantic search query into an embedding vector
- API key: `OPENROUTER_API_KEY` from `.env`
- The pipeline (Story 2.5) uses the same model for ingestion embeddings, ensuring query vectors are in the same embedding space as stored vectors

### Agent Query Protocol (Complete Flow)

This is the full protocol from the architecture doc that agents follow:

1. **Agent determines query type:** graph-only, semantic, or hybrid
2. **Graph path:** Agent calls SPARQL skill (`sparql-query`) -> skill validates ACL -> selects `.rq` template -> parameterizes -> executes against Oxigraph -> returns results with provenance metadata (named graph URI == Pod resource URI, `GRAPH <uri> {}` scoping)
3. **Semantic path:** Agent calls Qdrant skill (`qdrant-search`) -> skill generates query embedding -> similarity search against Qdrant -> returns results with `triple_uris` and `pod_resource_uri` traceability metadata
4. **Hybrid path:** Agent calls BOTH skills (can be parallel), receives two result sets, merges them itself based on persona context
5. **Agent formats results** for its persona's narrative

The key design point: **the agent does the merge, not the skills**. Each skill has a single responsibility. The agent has the context to judge relevance and combine insights.

### Result Correlation Between Skills

Both skills return `pod_resource_uri` as a common identifier:

- SPARQL skill returns: `{ results: [...], provenance: [{ pod_resource_uri: "..." }] }`
- Qdrant skill returns: `{ results: [{ pod_resource_uri: "...", triple_uris: [...] }] }`

Agents can correlate results by matching on `pod_resource_uri`. For example, a SPARQL result about "Ayoub failed test X" and a Qdrant result about "tutoring notes show geometric visualization" can be linked because both reference the same student's Pod resources.

### Naming Conventions

- Skill directory: `qdrant-search` (lowercase hyphen)
- Python files: `handler.py` (snake_case)
- Python functions: `snake_case`
- Python classes: `PascalCase`
- Qdrant collection names: `snake_case` (check Story 2.5)

### Skill Does NOT Perform ACL Checks

Unlike the SPARQL skill, the Qdrant skill does NOT perform ACL checks. Rationale:
- Qdrant stores embeddings derived from data that was already ACL-checked during ingestion
- The SPARQL skill enforces ACL at query time because it queries the graph directly
- For hybrid queries, the SPARQL skill provides the ACL-scoped structured data; the Qdrant skill provides semantic enrichment
- The troll agent tests vector privacy by accessing Qdrant directly (bypasses this skill entirely), which is a separate concern (Story 3.x troll)

This is a deliberate architectural choice, not an oversight. If the dev agent has concerns about this, flag it in completion notes.

### Project Structure Notes

Directories/files to create:

```
agents/
└── skills/
    └── qdrant-search/                 # NEW - Shared Qdrant skill
        ├── SKILL.md                 # NEW - Skill definition
        └── handler.py                 # NEW - Vector similarity search + provenance
```

Files that must already exist (from Stories 3-3 and 3-1):

```
agents/
├── openclaw.json               # Created in Story 3-3 (runtime, agents, skills enabled)
└── skills/
    └── sparql-query/                   # Created in Story 3-1
        ├── SKILL.md
        ├── handler.py
        └── templates/*.rq
```

**Note (post-Story 3-3):** OpenClaw uses JSON5 config (`openclaw.json`), NOT YAML. Skills use `SKILL.md` (YAML frontmatter + Markdown), NOT `skill.yaml`. The Qdrant skill is already enabled in `openclaw.json` → `skills.entries` → `qdrant-search: { enabled: true }`. This story only needs to create the `SKILL.md` and `handler.py`.

### Dependencies

- **Depends on Story 3.1:** SPARQL skill must exist for hybrid query composition. The Qdrant skill is the second half of the hybrid pattern.
- **Depends on Story 2.5:** Qdrant must have embeddings loaded with the correct payload schema (`triple_uris`, `pod_resource_uri`). Check Story 2.5 implementation for collection name, payload schema, and protocol choice (REST vs gRPC).
- **Depends on Epic 1:** Pods must exist (for `pod_resource_uri` references to be valid).
- **Depends on Epic 2:** Oxigraph must have data loaded (for `triple_uris` references to be valid).
- **Story 2.6 traceability.py:** Not required by this skill. The skill reads `triple_uris` and `pod_resource_uri` directly from the Qdrant payload (written by Story 2.5 embed pipeline). No reverse-navigation calls needed. Import traceability.py only if a future story requires `verify_provenance_consistency()` or similar traversal.
- **Blocks Stories 3.3-3.7:** All role agent journey stories depend on both skills for hybrid queries.

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- Example: `distrobox-host-exec podman exec qdrant ...`

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (DA-2, API-1, API-2, API-3, INFRA-1, Agent Query Protocol)
- PRD: `_bmad-output/planning-artifacts/prd.md` (FR15, NFR Performance — hybrid < 2s)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 3.2 acceptance criteria)
- Story 3.1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (SPARQL skill this story depends on)
- Story 2.5: embedding ingestion into Qdrant (for collection name, payload schema, protocol choice)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References
- Integration tests initially skipped: OPENROUTER_API_KEY not exported in shell. Required `source .env` before running. Not a code issue.
- Qdrant healthz endpoint confirmed reachable via `distrobox-host-exec curl http://localhost:6333/healthz`.
- Collection `pocpod0_embeddings` has 5617 points (from Story 2.5 ingestion).

### Completion Notes List
- Implemented `agents/skills/qdrant-search/handler.py` with full embedding→search→format pipeline.
- Used `httpx` (matching embed pipeline conventions), direct Qdrant REST API (API-1).
- No ACL check by design (deliberate architectural choice per story Dev Notes).
- DA-2 enforced: every result includes `triple_uris` and `pod_resource_uri`.
- Structured logging matches AC4 schema: `qdrant.search.executed` / `qdrant.search.error`.
- Latency breakdown logged separately: `embedding_latency_ms` and `search_latency_ms`.
- CLI interface mirrors sparql-query handler pattern; compatible for OpenClaw exec tool.
- `pod_resource_uri` is common key for agent-side hybrid query correlation with SPARQL skill.
- Integration tests (4 live) passed in 4.75s total. Qdrant skill alone < 1500ms.
- SKILL.md was already created (from Story 3-3 setup); no modification needed.

### File List
- `agents/skills/qdrant-search/handler.py` — NEW: Qdrant search skill handler
- `agents/skills/qdrant-search/tests/__init__.py` — NEW: test package init
- `agents/skills/qdrant-search/tests/conftest.py` — NEW: pytest path setup
- `agents/skills/qdrant-search/tests/test_handler.py` — NEW: 15 unit + 4 integration tests

## Change Log
- 2026-03-22: Story 3.2 implemented. Created Qdrant search skill with embedding generation, similarity search, provenance formatting, structured logging, and test suite (15 unit + 4 integration). All tests pass.
- 2026-03-22: Code review patches applied. result_count moved into details dict (AC4). Guarded KeyError/IndexError/json.JSONDecodeError from API response parsing. Added --filters type-check. URL-encode collection name. Replaced generator-throw idiom with MagicMock(side_effect=...). Integration skip moved to autouse fixture (no network call at collection time).
