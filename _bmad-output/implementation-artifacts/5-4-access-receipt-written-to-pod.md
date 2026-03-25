# Story 5.4: [backlog] Access Receipt Written to Pod

Status: ready-for-dev

## Story

As **Ayoub** (data sovereign),
I want every query that accesses my pod's data to generate a readable receipt stored in my pod,
so that I can audit who accessed what, when, and why — without asking anyone.

## Acceptance Criteria

**AC1: Receipt written on query execution**
Given any agent query executes against data derived from Ayoub's pod
When the query completes (success or denial)
Then a receipt is written to `/ayoub/access-log/[timestamp].ttl` containing: who queried (agent WebID), when, which consent grant authorized it, result shape (not raw data), which named graphs contributed
And writing the receipt does NOT block query execution — if the PUT fails, the failure is logged and the query result is returned normally

**AC2: Receipt is human-legible and machine-readable**
Given the receipt is written
When Ayoub (or the troll on Ayoub's behalf) queries the access log
Then the receipt is in Turtle format, human-legible without tooling
And the receipt is machine-readable — the troll can SPARQL-query the access log container
And the troll can answer "why does Isabelle have my data?" by dereferencing the consent grant URI in the receipt

## Tasks / Subtasks

### Task 1: Add receipt writing side-effect to sparql-query handler (AC1)
- [ ] In `agents/skills/sparql-query/handler.py`, after query execution (success or denial), call `write_access_receipt()`
- [ ] The receipt must be written AFTER the query result is determined — it should not gate the response
- [ ] Wrap the entire receipt-writing call in `try/except`: on any exception, log a structured warning and continue; the query result is returned regardless
- [ ] Pass to `write_access_receipt()`:
  - `agent_webid: str` — from `--webid` argument
  - `query_type: str` — from `--query-type` argument
  - `pod_uri: str` — the pod URI whose data was accessed (derived from query parameters)
  - `consent_grant_uri: str | None` — the consent grant URI that authorized the query (or `None` if denied)
  - `result_shape: str` — human-readable description of what was returned (e.g., "aggregate count: 3 sessions, no individual records" or "access denied")
  - `named_graphs: list[str]` — which named graph URIs were read in executing the query
  - `timestamp: str` — ISO-8601 of query execution

### Task 2: Derive pod URI and named graphs from query context (AC1)
- [ ] For each query template, implement logic to extract the target pod URI:
  - `student-progress`: pod URI = `CSS_IDENTIFIER_URL/<student_id>/` (from `--params`)
  - `parental-view`: pod URIs = all pods belonging to the parent's children
  - `cross-context-query`: pod URIs = all named graphs queried in Oxigraph
  - `aggregate-anonymized`: pod URIs = all unique `pod_resource_uri` values in query scope
  - `transfer-profile`: pod URI = `CSS_IDENTIFIER_URL/<student_id>/`
- [ ] Extract named graphs from the SPARQL response if available (Oxigraph returns graph metadata in some formats), otherwise derive from the template's `GRAPH <?>` clauses using the resolved parameters
- [ ] If pod URI cannot be derived (e.g., aggregate query spans multiple pods), write one receipt per pod URI in the result set, or write a single receipt to the querying agent's pod with `poc:multiPodQuery "true"^^xsd:boolean`

### Task 3: Implement `write_access_receipt()` function (AC1, AC2)
- [ ] Create `agents/skills/sparql-query/receipt.py` (separate module to keep handler.py focused)
- [ ] Implement `write_access_receipt(agent_webid, query_type, pod_uri, consent_grant_uri, result_shape, named_graphs, timestamp) -> bool`:
  1. Determine the access-log container URI: `{pod_uri}access-log/` (trailing slash = container)
  2. Ensure the access-log container exists: issue `PUT {pod_uri}access-log/` with `Content-Type: text/turtle` and empty body. CSS creates the container if absent; 200/201/405 are all acceptable.
  3. Build the receipt Turtle document (see Task 4)
  4. PUT the receipt: `PUT {pod_uri}access-log/{timestamp_slug}.ttl` with `Content-Type: text/turtle`
  5. Return `True` on HTTP 201/200/204, `False` otherwise; log the HTTP status in all cases
- [ ] Use the same CSS authentication pattern as `handler.py`: `Authorization: WebID <skill-webid>` header. The skill must have write access to the access-log container — this requires ACL configuration (see Task 5).
- [ ] Timestamp slug: ISO-8601 with colons replaced by hyphens and milliseconds included: `2026-03-25T14-32-17-432Z`

### Task 4: Implement Turtle receipt format (AC2)
- [ ] Receipt Turtle document structure:
  ```turtle
  @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
  @prefix poc: <https://pocpod0.example/vocab#> .
  @prefix dcterms: <http://purl.org/dc/terms/> .

  <urn:receipt:{timestamp_slug}> a poc:AccessReceipt ;
      poc:queriedBy <{agent_webid}> ;
      poc:accessedAt "{timestamp}"^^xsd:dateTime ;
      poc:queryType "{query_type}" ;
      poc:resultShape "{result_shape}" ;
      poc:consentGrant <{consent_grant_uri}> ;
      poc:namedGraphsContributed {named_graphs_turtle} ;
      dcterms:created "{timestamp}"^^xsd:dateTime .
  ```
  Where `named_graphs_turtle` is a Turtle list: `(<graph1>) , (<graph2>)` or `() .` if empty.
- [ ] If `consent_grant_uri` is None (denied query), omit `poc:consentGrant` and add `poc:accessDenied "true"^^xsd:boolean`
- [ ] The receipt URI uses `urn:receipt:` prefix (not an HTTP URL) — this makes it portable and dereferenceable via Turtle base URI
- [ ] No raw data in the receipt — only metadata about what was accessed and under what authority

### Task 5: Configure ACL for access-log container (AC1)
- [ ] The skill's WebID (SPARQL query skill service account) must have WRITE access to `{pod_uri}access-log/` for each pod
- [ ] Add ACL configuration to `pipeline/src/pocpod0_pipeline/provision_pods.py` or `scripts/seed-pods.sh`:
  - Grant WRITE on `{pod_uri}access-log/` to the SPARQL skill WebID
  - The pod owner (Ayoub's WebID) retains READ and WRITE on the access-log container
  - Other agents: READ only (so agents can see what was logged about their own queries)
- [ ] Use the `grant_acl()` function from `provision_pods.py` (established pattern from Stories 1.3/1.4)
- [ ] Add the skill WebID to `.env` as `SPARQL_SKILL_WEBID` if not already present

### Task 6: Verify receipt is readable by pod owner (AC2)
- [ ] Implement a verification function `verify_receipt_readable(pod_uri, timestamp_slug) -> bool`:
  - HTTP GET `{pod_uri}access-log/{timestamp_slug}.ttl` with pod owner's WebID credentials
  - Returns True if HTTP 200 and body is valid Turtle
  - Logs the receipt content as evidence in structured JSON
- [ ] Add this verification call to the integration test (Task 7)
- [ ] Verify the troll can query the access log as a SPARQL query via Oxigraph (if access-log content is indexed), or via CSS direct GET on each receipt file

### Task 7: Tests (AC1, AC2)
- [ ] Create `agents/skills/sparql-query/tests/test_receipt.py`
- [ ] Unit tests (no live CSS required):
  - `build_receipt_turtle()`: output is valid Turtle, all required fields present
  - `build_receipt_turtle()` with `consent_grant_uri=None`: `poc:accessDenied` present, `poc:consentGrant` absent
  - `build_receipt_turtle()` with multiple named graphs: Turtle list is correctly formatted
  - Timestamp slug generation: colons replaced, milliseconds included, no special characters
  - `write_access_receipt()` returns `False` on HTTP error without raising exception (non-blocking)
- [ ] Integration tests (live CSS required, optional flag):
  - PUT a receipt to Ayoub's pod, verify HTTP 201
  - GET the receipt back with Ayoub's WebID, verify content matches
  - Verify troll WebID can read (but not write) the receipt
  - Verify a third-party WebID (e.g., Claire's) cannot read the receipt without explicit ACL

## Dev Notes

### Architecture Decisions Referenced

- **BP-1 (Bidirectional Accountability):** "Every data flow that serves an institution must generate a readable receipt for the person whose data flowed." This story IS the PoC implementation of BP-1.
- **PoC scope boundary:** Architecture.md explicitly states: "PoC: structured logs capture execution (service-side only). Pilot: receipts written back to pods." This story implements the PoC version — receipts written to pods. This advances the PoC one step toward the Pilot vision while remaining within PoC scope.
- **Anagnorisis integration note:** Architecture.md lists this story under Stories 5.4/5.5/5.6 as implementing "access receipts (BP-1), consent grant as RDF (BP-3), ephemeral time-scoped tokens (BP-5)." The receipt's `poc:consentGrant` URI is the link to BP-3.
- **FR24:** Programmable governance contract for age-based sovereignty transition. The access log created by this story becomes auditable evidence for sovereignty transition: Ayoub can see exactly who accessed his data before he takes full control.

### BP-1 Principle — Why This Matters for the Funder Demo

The killer demo moment for BP-1: Ayoub opens his pod in a browser, navigates to `/access-log/`, and sees a list of `.ttl` files — one per query. He opens one: "Isabelle queried aggregate counts from my pod at 14:32 under consent grant X. Result shape: aggregate count, no individual records."

The troll then demonstrates: "I can answer 'why does Isabelle have your data?' by dereferencing `<consent-grant-uri>` from the receipt." This closes the accountability loop without requiring Ayoub to trust any intermediary.

This is the architectural argument: accountability is not a feature you add — it is a property of the data flow architecture.

### CSS PUT Pattern for Writing Back to Pods

CSS accepts authenticated PUT requests to write resources. The pattern (established in Stories 1.3/1.4):

```http
PUT /ayoub/access-log/2026-03-25T14-32-17-432Z.ttl HTTP/1.1
Host: localhost:3000
Authorization: WebID http://localhost:3000/sparql-skill/profile/card#me
Content-Type: text/turtle

@prefix poc: ...
<urn:receipt:...> a poc:AccessReceipt ; ...
```

HTTP responses:
- `201 Created`: resource written successfully (new resource)
- `200 OK` or `204 No Content`: resource overwritten (idempotent on re-run)
- `401 Unauthorized`: skill WebID not in ACL — configuration error in Task 5
- `403 Forbidden`: ACL exists but skill WebID not granted WRITE — fix provision_pods.py

The `Authorization: WebID` header is used throughout this project (not Solid-OIDC bearer tokens — that is Pilot scope). Verified working in Story 1.5.

### Non-Blocking Side-Effect

The receipt write MUST NOT block query execution or degrade query latency. Implementation pattern:

```python
# After query result is determined:
try:
    written = write_access_receipt(...)
    if not written:
        log_warning("receipt write failed — query result unaffected")
except Exception as e:
    log_warning(f"receipt write exception: {e} — query result unaffected")
# Return query result regardless
```

If CSS is temporarily unavailable, the query still returns its result. The receipt write failure is a warning, not an error. This is critical for NFR7 (no cross-role leakage via denial of service — a receipt write failure should not become a query denial).

### Consent Grant URI Derivation

The consent grant URI that authorized the query comes from the ACL check in `handler.py`. Currently `handler.py` performs the ACL check and returns pass/deny — it does NOT return the grant URI. Task 1 requires extending the ACL check result to also return the grant URI when the check passes.

If no consent grant URI is available (ACL check does not model explicit grants), use the ACL resource URI itself as a proxy: `{pod_uri}.acl` — it is still a dereferenceable URI that shows who has access and why.

### PoC vs Pilot Scope Distinction

| PoC (this story) | Pilot (future) |
|------------------|----------------|
| Receipts written by skill service account | Receipts written under data subject's consent |
| Turtle format, human-readable | May include JSON-LD for interop |
| Stored in `/access-log/` container | Distributed receipt registry (IPFS/IPLD per architecture trust principles) |
| troll queries receipts via CSS GET | Full SPARQL indexing of access log |
| Single pod (Ayoub) | All data subjects in the system |

This story implements the left column only. The right column is documented in `_bmad-output/planning-artifacts/post-poc-backlog.md`.

### Python Environment

- Activate venv before running: `source venv/bin/activate`
- Python 3.12+
- New file `receipt.py` in `agents/skills/sparql-query/` — same directory as `handler.py`
- Dependencies: `requests` (HTTP, already in `requirements.txt`), `datetime` (stdlib)
- No new package dependencies needed

### Naming Conventions

- Module file: `receipt.py` (new file in sparql-query skill directory)
- Python functions: `write_access_receipt`, `build_receipt_turtle`, `ensure_access_log_container`, `verify_receipt_readable` (snake_case)
- Receipt URI scheme: `urn:receipt:{timestamp_slug}` (URN, not HTTP URL)
- Access-log container: `/access-log/` (trailing slash = Solid container convention)
- Timestamp slug: `YYYY-MM-DDTHH-MM-SS-mmmZ` (colons replaced with hyphens for URL safety)

### Project Structure Notes

Files to create:

```
agents/skills/sparql-query/
└── receipt.py                         # NEW — receipt writing module
agents/skills/sparql-query/tests/
└── test_receipt.py                    # NEW — unit tests for receipt module
```

Files to modify:

```
agents/skills/sparql-query/handler.py  # MODIFIED — add write_access_receipt() call as side-effect
pipeline/src/pocpod0_pipeline/provision_pods.py  # MODIFIED — add ACL grant for skill WebID on access-log container
```

Files that must already exist (from previous stories):

```
agents/skills/sparql-query/handler.py          # Created in Story 3.1
agents/skills/sparql-query/parameterize.py     # Created in Story 3.1
pipeline/src/pocpod0_pipeline/provision_pods.py  # Created in Story 1.3
.env                                            # CSS credentials, pod WebIDs
```

### Dependencies

- **Depends on Story 3.1:** `sparql-query/handler.py` must exist. Receipt writing is a side-effect added to the existing handler execution path.
- **Depends on Story 1.3/1.4:** `provision_pods.py` ACL grant functions must exist. The access-log container ACL is configured using the same `grant_acl()` function.
- **Depends on Story 5.1:** `consent-events.jsonl` exists and consent grant URIs are resolvable (the receipt links to consent grants). If Story 5.1 is not complete, fall back to using the ACL resource URI as the grant URI proxy.
- **Related to Story 5.3:** The troll (Story 5.3) can query the access log as part of its deletion timing verification — if a receipt exists for a deleted resource, is it also deleted? (out of scope for 5.3 but noted for future story).
- **Consumed by Story 6.1/6.2:** Mission control dashboard may surface the access log count or last receipt timestamp as a pod health indicator.

### Error Handling

- **CSS unreachable:** Log warning, return False, continue. Query execution unaffected.
- **ACL denied on PUT:** Log warning with HTTP status, return False. This indicates a configuration error in provision_pods.py — not a runtime data error.
- **Turtle serialization error:** Log warning with exception details, return False. Robustness: if `build_receipt_turtle()` raises, the exception is caught before the PUT is attempted.
- **Access-log container creation failure:** Log warning. Attempt the PUT anyway — CSS may auto-create intermediate containers depending on configuration.
- **Never raise from `write_access_receipt()`:** All exceptions are caught and logged. The function always returns a bool.

### Isolation Notes

- Use `distrobox-host-exec` for accessing podman containers from within the distrobox environment
- CSS runs in a Docker/podman container — the skill's HTTP PUT goes to `http://localhost:3000` (or `$CSS_CONNECT_URL` inside Docker)
- The `Authorization: WebID` header must use the `CSS_IDENTIFIER_URL` base (identifier space), not the `CSS_CONNECT_URL` base (TCP connection space)
- Example: if `CSS_IDENTIFIER_URL=http://localhost:3000` and `CSS_CONNECT_URL=http://community-solid-server:3000`, the PUT goes to `CSS_CONNECT_URL` but the WebID URI uses `CSS_IDENTIFIER_URL`

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (BP-1 Bidirectional Accountability, BP-3 consent-as-RDF, PoC vs Pilot scope table, Section "Design Principles: Bidirectional Accountability & Trust Architecture")
- Epics: `_bmad-output/planning-artifacts/epics.md` (Story 5.4 acceptance criteria, Anagnorisis integration note)
- Story 1.4: `_bmad-output/implementation-artifacts/1-4-acl-grant-revocation-audit.md` (`grant_acl()` function, ACL Turtle format)
- Story 1.5: `_bmad-output/implementation-artifacts/1-5-troll-acl-enforcement-validation.md` (CSS auth header pattern, `Authorization: WebID`)
- Story 3.1: `_bmad-output/implementation-artifacts/3-1-shared-sparql-skill-foundation.md` (handler.py structure, ACL check flow, parameterize.py)
- Story 5.1: `_bmad-output/implementation-artifacts/` (consent events and consent grant URI schema — needed for `poc:consentGrant` linking)
- Post-POC backlog: `_bmad-output/planning-artifacts/post-poc-backlog.md` (Pilot-phase receipt registry vision)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List

---
