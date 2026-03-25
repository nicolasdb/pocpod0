# Story 5.2: [foundation] Deletion Cascade & Verification

Status: ready-for-dev

## Story

As **Ayoub** (data sovereign),
I want to request deletion of a pod resource and have it cascade completely across all three data layers with verified completeness,
so that my right to erasure is architecturally enforced, not a manual process with gaps.

## Acceptance Criteria

**AC1: 3-layer deletion cascade**
Given a Pod resource with derived triples in Oxigraph and embeddings in Qdrant
When a soft-delete request is issued on the Pod resource URI
Then the resource is marked with a `pocpod0:deletedAt` triple in the CSS Pod (step 1 — soft-delete marker)
And all derived triples are removed from Oxigraph by executing `DROP GRAPH <pod-resource-uri>` (step 2) — uses the named graph pattern from Story 2.6, NOT prov:wasDerivedFrom
And all Qdrant points whose payload `pod_uri_hash` matches the SHA-256 hash of the pod resource URI are removed (step 3) — uses the UUID-based lookup from AC4
And the entire cascade completes atomically in a single execution of `delete_cascade.py`

**AC2: Deletion verification**
Given the deletion cascade has completed
When verification queries run against all three layers
Then the CSS resource is marked with `pocpod0:deletedAt` and `pocpod0:isDeleted true`
And zero Oxigraph triples reference the deleted named graph (SPARQL `ASK { GRAPH <pod-resource-uri> { ?s ?p ?o } }` returns false)
And zero Qdrant points exist with `pod_uri_hash` matching the deleted resource
And a verification result is logged as a structured JSONL event with `passed: true|false` and per-layer details

**AC3: Structured JSONL logging per step**
Given each step of the deletion cascade (soft-delete, Oxigraph DROP, Qdrant delete, verification)
When it executes
Then a structured JSONL event is emitted to `data/consent-events.jsonl` per step:
```json
{"event_type": "deletion.step", "timestamp": "ISO-8601", "pod": "ayoub", "resource_uri": "<uri>", "step": "1-css-soft-delete|2-oxigraph-drop|3-qdrant-delete|4-verification", "status": "ok|error", "details": "..."}
```
And a final `deletion.complete` event is emitted with `all_layers_clean: true|false`

**AC4 (PRIV-1 fix): Opaque UUID in Qdrant payload**
Given the PRIV-1 finding (Story 2.8): `pod_resource_uri` stored directly in Qdrant payload encodes the student name via the pod slug (e.g., `/ayoub/` in the URI)
When new embeddings are stored via `embed.py`
Then the `pod_resource_uri` field in Qdrant payload is replaced with an opaque `pod_uri_hash`: `hashlib.sha256(pod_resource_uri.encode()).hexdigest()[:16]`
And a lookup index is maintained in Oxigraph in the named graph `<urn:uuid-index>` as triples: `<urn:uuid-index:HASH> pocpod0:mapsTo <pod-resource-uri>`
And the deletion cascade uses this lookup index to resolve hash → URI and delete the correct Qdrant points
And the raw `pod_resource_uri` is no longer stored in any Qdrant payload field

## Tasks / Subtasks

### Task 1: Create `delete_cascade.py` — 3-layer cascade (AC1)
- [ ] Create `pipeline/src/pocpod0_pipeline/delete_cascade.py`
- [ ] Implement `dataclass DeletionResult(resource_uri, pod_name, step_results: list[StepResult], all_layers_clean: bool, timestamp)`
- [ ] Implement `dataclass StepResult(step: str, layer: str, status: str, details: str, duration_ms: int)`
- [ ] Implement `soft_delete_css(resource_uri: str, css_auth_token: str) -> StepResult`:
  - PATCH the CSS resource to add `pocpod0:deletedAt` (ISO-8601 timestamp) and `pocpod0:isDeleted true` triples
  - Use `Authorization: WebID <webid>` header from Story 1.4/1.5 CSS auth pattern
  - Return StepResult with `layer="css"`, `step="1-css-soft-delete"`
- [ ] Implement `drop_oxigraph_graph(resource_uri: str, oxigraph_url: str) -> StepResult`:
  - Execute SPARQL UPDATE: `DROP GRAPH <{resource_uri}>` via HTTP POST to Oxigraph `/update` endpoint
  - Confirm the named graph no longer exists with ASK query
  - Return StepResult with `layer="oxigraph"`, `step="2-oxigraph-drop"`
- [ ] Implement `delete_qdrant_points(pod_uri_hash: str, qdrant_url: str) -> StepResult`:
  - Use Qdrant filter delete: `DELETE /collections/{collection}/points` with filter `{"must": [{"key": "pod_uri_hash", "match": {"value": "<hash>"}}]}`
  - Return StepResult with `layer="qdrant"`, `step="3-qdrant-delete"`, include count of deleted points in details
- [ ] Implement `run_cascade(resource_uri: str, pod_name: str) -> DeletionResult`: orchestrates steps 1→2→3 sequentially; captures and logs each StepResult; does NOT abort on step failure (records error and continues)
- [ ] CLI entry point: `python -m pocpod0_pipeline.delete_cascade --resource-uri <uri> --pod <name>`

### Task 2: PRIV-1 fix — opaque UUID in `embed.py` (AC4)
- [ ] Read `pipeline/src/pocpod0_pipeline/embed.py` to locate where `pod_resource_uri` is written to Qdrant payload
- [ ] Replace `pod_resource_uri` in Qdrant payload with `pod_uri_hash = hashlib.sha256(pod_resource_uri.encode()).hexdigest()[:16]`
- [ ] Add a comment in `embed.py`: `# PRIV-1 fix (Story 5.2): store opaque hash, not raw URI, to prevent identity leak via pod slug`
- [ ] Remove `pod_resource_uri` from the Qdrant payload dict entirely — the hash is the only identifier
- [ ] Ensure `content_text` and other non-identifying payload fields are unchanged

### Task 3: UUID lookup index in Oxigraph (AC4)
- [ ] Create `pipeline/src/pocpod0_pipeline/uuid_index.py`
- [ ] Implement `register_hash(pod_resource_uri: str, oxigraph_url: str) -> str`: computes hash, writes triple `<urn:uuid-index:{hash}> pocpod0:mapsTo <{pod_resource_uri}>` into named graph `<urn:uuid-index>` via SPARQL INSERT, returns hash
- [ ] Implement `resolve_hash(pod_uri_hash: str, oxigraph_url: str) -> str | None`: queries named graph `<urn:uuid-index>` for the triple and returns the original URI, or None if not found
- [ ] Implement `deregister_hash(pod_uri_hash: str, oxigraph_url: str)`: removes the mapping triple from `<urn:uuid-index>` after deletion cascade (clean up index after erasure)
- [ ] Call `register_hash` from `embed.py` after computing the hash — so every embed also registers the lookup mapping
- [ ] Call `deregister_hash` from `delete_cascade.py` step 3 after Qdrant delete succeeds

### Task 4: Deletion verification queries (AC2)
- [ ] Implement `verify_deletion(resource_uri: str, pod_uri_hash: str) -> VerificationResult` in `delete_cascade.py`:
  - Layer 1 (CSS): HEAD or GET on the resource URI; check for `pocpod0:isDeleted true` in response body
  - Layer 2 (Oxigraph): SPARQL ASK `{ GRAPH <{resource_uri}> { ?s ?p ?o } }` → must return false
  - Layer 3 (Qdrant): scroll/count query filtered by `pod_uri_hash` → must return 0 points
- [ ] Implement `dataclass VerificationResult(resource_uri, css_deleted: bool, oxigraph_clean: bool, qdrant_clean: bool, all_layers_clean: bool, timestamp)`
- [ ] Log verification result as JSONL event: `{"event_type": "deletion.verification", ...}`
- [ ] Return verification result from `run_cascade` as the final step result

### Task 5: Structured JSONL logging (AC3)
- [ ] Ensure `data/consent-events.jsonl` exists (create if absent — see Story 5.1 Task 5)
- [ ] In `delete_cascade.py`: emit one JSONL line per step to `data/consent-events.jsonl` in append mode
- [ ] Emit final `deletion.complete` event after verification:
  ```json
  {"event_type": "deletion.complete", "timestamp": "ISO-8601", "pod": "ayoub", "resource_uri": "<uri>", "all_layers_clean": true, "steps_completed": 4, "verification": {"css_deleted": true, "oxigraph_clean": true, "qdrant_clean": true}}
  ```
- [ ] Also log each step to stdout using `utils.py` structured JSON logging pattern (same as pipeline modules)
- [ ] Verify all JSONL lines pass `json.loads(line)` without error

### Task 6: Update `traceability.py` if needed (AC1)
- [ ] Read `pipeline/src/pocpod0_pipeline/traceability.py` to check if it writes provenance links that reference `pod_resource_uri` directly
- [ ] If traceability writes to the named graph `<pod-resource-uri>`, confirm that `DROP GRAPH <pod-resource-uri>` in step 2 already removes all traceability triples for that graph — no separate traceability delete step needed
- [ ] If traceability writes to a SEPARATE named graph (e.g., `<urn:provenance>`) with references to `<pod-resource-uri>`, add a step to delete those cross-references too: SPARQL DELETE on the provenance graph where subject/object = `<pod-resource-uri>`
- [ ] Document the finding (either "DROP GRAPH is sufficient" or "additional provenance cleanup added") in Dev Notes

### Task 7: Tests (AC1–AC4)
- [ ] Create `tests/test_deletion_cascade.py`
- [ ] Test `soft_delete_css`: mock HTTP PATCH; verify correct URL, payload, and auth header; verify StepResult fields
- [ ] Test `drop_oxigraph_graph`: mock SPARQL UPDATE endpoint; verify DROP GRAPH statement is correctly parameterized with resource URI
- [ ] Test `delete_qdrant_points`: mock Qdrant delete endpoint; verify filter uses `pod_uri_hash`, NOT `pod_resource_uri`; verify deleted count in StepResult details
- [ ] Test `verify_deletion`: mock all three layer queries; test all-clean path and partial-failure path
- [ ] Test `run_cascade`: verify step order (1→2→3→verify); verify all four JSONL events emitted; verify partial failure (step 2 error) does not abort step 3
- [ ] Test PRIV-1 fix in `embed.py`: mock Qdrant upsert; verify payload does NOT contain `pod_resource_uri`; verify payload DOES contain `pod_uri_hash`
- [ ] Test `uuid_index.py`: `register_hash` → SPARQL INSERT into `<urn:uuid-index>`; `resolve_hash` → SPARQL SELECT; `deregister_hash` → SPARQL DELETE
- [ ] Test hash determinism: same URI always produces same 16-char hex hash

## Dev Notes

### Architecture Decisions Referenced

- **Right to Erasure (GDPR Article 17):** Deletion cascade is the architectural implementation of erasure. All three layers must be clean — partial deletion is not acceptable. The `all_layers_clean` flag makes completeness machine-verifiable.
- **Named graph per Pod URI (Story 2.6):** `DROP GRAPH <pod-resource-uri>` is the correct Oxigraph deletion mechanism. It removes ALL triples for that pod in one SPARQL UPDATE. This is NOT `DELETE WHERE { <uri> ?p ?o }` (which only removes subject triples). The named graph wraps the entire derived dataset for one pod resource.
- **PRIV-1 (Story 2.8):** The `pod_resource_uri` in Qdrant payload leaks student identity via the pod slug (`/ayoub/`, `/fatima/`). The fix is a one-way hash: `SHA-256(uri)[:16]`. The UUID index in Oxigraph is the authorized reverse-lookup, accessible only to services with the Oxigraph SPARQL endpoint.
- **Soft-delete in CSS (not hard-delete):** The CSS resource is marked `pocpod0:isDeleted true`, not physically removed. This preserves audit trail (the deletion event is itself a record). Hard-delete would leave no trace that erasure was requested and completed.

### Key Design Decisions

- **Hash length 16 chars:** `hashlib.sha256(uri.encode()).hexdigest()[:16]` — 16 hex chars = 64 bits of entropy. Sufficient to prevent brute-force reversal; short enough for Qdrant filter performance. NOT a secret — it's a stable identifier, not a security secret.
- **UUID index in Oxigraph named graph `<urn:uuid-index>`:** This is a separate named graph from the per-pod data graphs. `DROP GRAPH <pod-resource-uri>` does NOT touch `<urn:uuid-index>`. The deregister step in `uuid_index.py` handles cleanup explicitly after Qdrant delete succeeds.
- **Step failure does NOT abort cascade:** If Oxigraph DROP fails (e.g., graph doesn't exist — idempotent), the cascade continues to Qdrant delete. Each step records its own StepResult. `all_layers_clean` is computed from all four verification results, not from step success flags.
- **No re-embed needed for PRIV-1 fix:** Existing Qdrant points still have the old `pod_resource_uri` field. The fix applies to NEW embeds only. The troll story (5.3) may flag this as a residual PRIV-1 exposure in existing data — that is an expected finding. A full re-embed can be added as a post-story migration task if required.
- **`delete_cascade.py` is a pipeline module, not an agent skill:** Deletion is triggered by a pipeline job or demo script, not by an agent. Agents use `acl-manage` (Story 5.1) for consent mutations. The full cascade is a privileged pipeline operation.

### SPARQL DROP GRAPH — Oxigraph Specific

Oxigraph accepts SPARQL 1.1 Update. The correct statement is:
```sparql
DROP GRAPH <http://example.css/ayoub/learning-records/>
```
This drops the named graph and all its triples. If the graph does not exist, Oxigraph returns success silently (idempotent). POST to `{OXIGRAPH_URL}/update` with `Content-Type: application/sparql-update` and the UPDATE body.

ASK query to verify the graph is gone:
```sparql
ASK { GRAPH <http://example.css/ayoub/learning-records/> { ?s ?p ?o } }
```
Expected response after DROP: `{"boolean": false}`.

### Qdrant Delete by Payload Filter

Qdrant delete endpoint: `POST /collections/{collection_name}/points/delete`
```json
{
  "filter": {
    "must": [{"key": "pod_uri_hash", "match": {"value": "a3f9c12b44e17d80"}}]
  }
}
```
This deletes ALL points matching the hash. The deletion is synchronous when `wait=true` is appended to the URL. Use canonical imports from Story 2.5: `from qdrant_client import QdrantClient`.

### PRIV-1 Fix — embed.py Change

Before (PRIV-1 vulnerable):
```python
payload = {"pod_resource_uri": pod_resource_uri, "content_text": text, ...}
```

After (PRIV-1 fixed):
```python
import hashlib
pod_uri_hash = hashlib.sha256(pod_resource_uri.encode()).hexdigest()[:16]
payload = {"pod_uri_hash": pod_uri_hash, "content_text": text, ...}
# PRIV-1 fix (Story 5.2): raw URI removed to prevent identity leak via pod slug
```

The `qdrant-search` skill (Story 3.2) currently returns `pod_resource_uri` in results for traceability (DA-2). After this fix, it will return `pod_uri_hash` instead. The `uuid_index.py` `resolve_hash` function is available for authorized lookups. Update the qdrant-search handler if it currently references `pod_resource_uri` in the result payload.

### CSS Auth Pattern

From Stories 1.4/1.5: use `Authorization: WebID <webid>` header. The CSS server URL for HTTP requests from outside Docker must use `CSS_CONNECT_URL` from `.env`, NOT the Docker-internal hostname (`CSS_IDENTIFIER_HOST`). See `story_3_1_css_identifier_model.md` memory note for the three-var model.

### Project Structure Notes

Directories/files to create:
```
pipeline/
└── src/
    └── pocpod0_pipeline/
        ├── delete_cascade.py   # NEW — 3-layer deletion cascade + verification
        └── uuid_index.py       # NEW — opaque UUID hash registration and lookup

tests/
└── test_deletion_cascade.py    # NEW — unit tests for cascade, PRIV-1, uuid_index
```

Files to modify:
```
pipeline/
└── src/
    └── pocpod0_pipeline/
        ├── embed.py            # MODIFY — PRIV-1 fix: replace pod_resource_uri with pod_uri_hash
        └── traceability.py     # INSPECT + possibly MODIFY — check if provenance needs cleanup

agents/
└── skills/
    └── qdrant-search/
        └── handler.py          # INSPECT + possibly MODIFY — if it returns pod_resource_uri in results
```

Files that must already exist (from previous stories):
```
pipeline/
└── src/
    └── pocpod0_pipeline/
        ├── provision_pods.py   # Story 1.4 — CSS auth patterns
        ├── traceability.py     # Story 2.6 — named graph pattern (one graph per Pod URI)
        ├── embed.py            # Story 2.5 — Qdrant embed pipeline (PRIV-1 lives here)
        └── utils.py            # Shared logging

agents/
└── skills/
    └── qdrant-search/          # Story 3.2 — may reference pod_resource_uri in results

data/
└── consent-events.jsonl        # Story 5.1 — JSONL event stream (must exist before cascade runs)
```

### Dependencies

- **Depends on Story 2.6:** Named graph per Pod URI pattern. `DROP GRAPH <pod-resource-uri>` is the Oxigraph deletion mechanism — this story uses it directly.
- **Depends on Story 2.5:** Qdrant embed pipeline. PRIV-1 fix modifies `embed.py` from this story.
- **Depends on Story 2.8:** PRIV-1 finding. This story is the architectural fix. Story 2.8 documented the problem; Story 5.2 fixes it.
- **Depends on Story 5.1:** `data/consent-events.jsonl` must exist (created in Story 5.1 Task 5). Deletion events append to the same file.
- **Consumed by Story 5.3 (Troll deletion cascade validation):** The troll will verify that cascade is complete and attempt to access "deleted" data. `all_layers_clean` verification must be accurate.
- **Consumed by Story 6.1 (Mission Control TUI):** `deletion.complete` events in `data/consent-events.jsonl` feed the dashboard's consent state panel.

### Error Handling

- **Step failure does NOT abort cascade:** Log the StepResult with `status="error"`, continue to next step. `all_layers_clean` will be false if any layer failed — this is the correct signal.
- **Idempotency:** `DROP GRAPH` on a non-existent graph is safe (Oxigraph returns 200). Qdrant delete with a filter that matches 0 points returns 0 deleted — not an error.
- **CSS PATCH failure:** If the CSS soft-delete PATCH returns non-2xx, log error and continue. The Oxigraph and Qdrant layers should still be cleaned even if the CSS marker failed.
- **Hash collision (theoretical):** SHA-256 truncated to 16 chars has negligible collision probability for the data scale of this POC. Not a practical concern; document as known limitation.
- **Re-embed migration:** Existing Qdrant points from before the PRIV-1 fix still contain `pod_resource_uri`. This is a known residual exposure. The deletion cascade checks BOTH `pod_uri_hash` (new) and `pod_resource_uri` (legacy) fields when deleting to ensure complete erasure during the transition period. Add a TODO comment in `delete_cascade.py` for a post-story full re-embed migration.

### Isolation Notes

- Use `distrobox-host-exec` for podman containers
- Example (Oxigraph SPARQL): `distrobox-host-exec podman exec oxigraph curl -s -X POST http://localhost:7878/update -H "Content-Type: application/sparql-update" --data "DROP GRAPH <uri>"`
- Example (Qdrant): `distrobox-host-exec podman exec qdrant curl -s http://localhost:6333/collections/`
- `delete_cascade.py` calls all three layers via HTTP — URLs from `.env` (`CSS_CONNECT_URL`, `OXIGRAPH_URL`, `QDRANT_URL`)

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md`
- Epics: `_bmad-output/planning-artifacts/epics.md`
- Story 2.5: `_bmad-output/implementation-artifacts/2-5-qdrant-setup-vector-embeddings.md` — Qdrant canonical imports, collection schema
- Story 2.6: `_bmad-output/implementation-artifacts/2-6-bidirectional-traceability-embedding-triple-pod.md` — named graph per Pod URI, NOT prov:wasDerivedFrom
- Story 2.8: `_bmad-output/implementation-artifacts/2-8-troll-vector-privacy-validation.md` — PRIV-1 finding, pod_resource_uri identity leak
- Story 3.2: `_bmad-output/implementation-artifacts/3-2-shared-qdrant-skill-foundation.md` — Qdrant skill result format with pod_resource_uri (check if update needed)
- Story 5.1: `_bmad-output/implementation-artifacts/5-1-ayoub-governance-transition.md` — consent-events.jsonl JSONL pattern
- Memory: `story_2_8_vector_privacy_patterns.md` — PRIV-1/PRIV-2 findings, reuse map
- Memory: `story_2_6_traceability_patterns.md` — named graph pattern, CSS auth on HEAD, consistency semantics
- Memory: `story_2_5_qdrant_embed_patterns.md` — Qdrant v1.17 canonical imports, payload schema

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
