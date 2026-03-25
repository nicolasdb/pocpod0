# Story 5.5: [backlog] Consent Grant as RDF Resource

Status: ready-for-dev

## Story

As **Ayoub** (data sovereign),
I want the consent I give to institutional actors to be a dereferenceable, inspectable document — not a boolean flag,
so that I can understand, at any time, exactly what I agreed to and why.

## Acceptance Criteria

**AC1: Consent grant resource created with full contract**
Given an institutional actor (e.g. Isabelle) requests aggregate access to Ayoub's data
When consent is granted via the `acl-manage` skill or `consent_grant.py` module
Then a Turtle resource is written to Ayoub's pod at `/ayoub/consent-grants/[grant-id].ttl` carrying:
- `poc:requestedBy` — the grantee WebID
- `poc:purpose` — plain-language statement of why access was requested
- `poc:scope` — what data they will see
- `poc:excluded` — what data they will NOT see
- `poc:consequenceOfRefusal` — what happens if consent is withheld
- `poc:grantedAt` — ISO-8601 timestamp (as `xsd:dateTime`)
- `poc:revokedAt` — empty string literal initially (tombstone field, filled on revocation)
- `poc:expiresAt` — ISO-8601 expiry timestamp (as `xsd:dateTime`; open-ended grants use a far-future date)
And a JSONL event is emitted to `data/consent-events.jsonl`:
```json
{"event_type": "consent.grant", "timestamp": "ISO-8601", "pod": "ayoub", "grant_id": "...", "grantee": "<isabelle-webid>", "purpose": "..."}
```
And the ACL grant is applied via the `acl-manage` skill (grantee WebID receives read access to the pod)

**AC2: Troll can answer "why does Isabelle have access?"**
Given a consent grant resource exists for Isabelle at a dereferenceable URI within the PoC
When Ayoub or the troll queries "why does Isabelle have access to my data?"
Then the troll dereferences the consent grant URI and returns `poc:purpose` and `poc:scope` in plain language
And the answer requires no human intermediary — the RDF resource is self-describing
And the troll response includes the grant URI, the grantee WebID, the purpose, the scope, and the excluded fields

**AC3: Revocation applies tombstone and removes ACL**
Given a consent grant resource exists with `poc:revokedAt` empty
When Ayoub revokes consent via the `consent_grant.py` module
Then the `poc:revokedAt` field in the Turtle is populated with the revocation timestamp (tombstone pattern)
And the ACL grant is removed via the `acl-manage` skill (grantee WebID loses read access)
And future SPARQL aggregate queries automatically exclude Ayoub's named graph (SPARQL filter on revoked consent)
And historical aggregates computed before revocation remain immutable — tombstone does NOT rewrite history
And a JSONL event is emitted to `data/consent-events.jsonl`:
```json
{"event_type": "consent.revoke", "timestamp": "ISO-8601", "pod": "ayoub", "grant_id": "...", "grantee": "<isabelle-webid>"}
```

## Tasks / Subtasks

### Task 1: Create `consent_grant.py` module (AC1, AC3)
- [ ] Create `pipeline/src/pocpod0_pipeline/consent_grant.py`
- [ ] Implement `generate_grant_id(pod_uri: str, grantee_webid: str, timestamp: str) -> str`: returns a short human-readable slug (e.g., `grant-ayoub-isabelle-20260325`) that is unique within the pod and filesystem-safe
- [ ] Implement `create_consent_grant(pod_name: str, grantee_webid: str, purpose: str, scope: str, excluded: str, consequence_of_refusal: str, expires_at: str) -> ConsentGrantResult`:
  1. Generate a grant ID and construct the grant URI: `http://localhost:3000/{pod_name}/consent-grants/{grant_id}`
  2. Render the Turtle template (Task 2) with all fields
  3. Write the Turtle file to the pod via HTTP PUT (CSS authenticated)
  4. Grant ACL access via the `acl-manage` skill handler (or direct call to `grant_acl_access`)
  5. Emit `consent.grant` JSONL event to `data/consent-events.jsonl`
  6. Return `ConsentGrantResult(grant_id, grant_uri, pod_name, grantee_webid, granted_at, status)`
- [ ] Implement `revoke_consent_grant(pod_name: str, grant_id: str) -> RevokeGrantResult`:
  1. Fetch the existing Turtle resource from the pod
  2. Parse the Turtle and update `poc:revokedAt` with the current ISO-8601 timestamp
  3. Write the updated Turtle back to the pod via HTTP PUT
  4. Revoke ACL access via the `acl-manage` skill handler (or direct call to `revoke_acl_access`)
  5. Emit `consent.revoke` JSONL event to `data/consent-events.jsonl`
  6. Return `RevokeGrantResult(grant_id, pod_name, grantee_webid, revoked_at, status)`
- [ ] Implement `get_consent_grant(pod_name: str, grant_id: str) -> dict`: fetch and parse the Turtle resource, return a dict of all `poc:` fields
- [ ] Implement `list_consent_grants(pod_name: str) -> list[dict]`: list all `*.ttl` files under `/[pod_name]/consent-grants/` and return parsed summaries
- [ ] Use `dataclass ConsentGrantResult(grant_id, grant_uri, pod_name, grantee_webid, granted_at, status, error_message="")` and `dataclass RevokeGrantResult(grant_id, pod_name, grantee_webid, revoked_at, status, error_message="")`
- [ ] Log each operation with structured JSON to stdout using `utils.py` patterns

### Task 2: Create Turtle template for consent grant resource (AC1)
- [ ] Create `infra/css/pods/consent-grant.ttl.j2` (Jinja2 template)
- [ ] Template variables: `grant_uri`, `grantee_webid`, `purpose`, `scope`, `excluded`, `consequence_of_refusal`, `granted_at`, `expires_at`
- [ ] `poc:revokedAt` is always an empty string literal initially (tombstone field — present in the resource from day one, filled on revocation)
- [ ] Include correct `@prefix` declarations: `poc:`, `xsd:`, `rdf:`
- [ ] Rendered template:
```turtle
@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<{{ grant_uri }}> a poc:ConsentGrant ;
  poc:requestedBy   <{{ grantee_webid }}> ;
  poc:purpose       "{{ purpose }}" ;
  poc:scope         "{{ scope }}" ;
  poc:excluded      "{{ excluded }}" ;
  poc:consequenceOfRefusal "{{ consequence_of_refusal }}" ;
  poc:grantedAt     "{{ granted_at }}"^^xsd:dateTime ;
  poc:revokedAt     "" ;
  poc:expiresAt     "{{ expires_at }}"^^xsd:dateTime .
```
- [ ] Validate that the rendered Turtle parses cleanly with `rdflib` before writing to the pod

### Task 3: Integration with `acl-manage` skill (AC1, AC3)
- [ ] Verify that `agents/skills/acl-manage/handler.py` (Story 5.1) exposes the `grant` and `revoke` actions with the correct signature
- [ ] In `consent_grant.py`, call the acl-manage handler via subprocess CLI (consistent with skill invocation pattern from Stories 3.1/3.2) OR import `grant_acl_access`/`revoke_acl_access` directly from `provision_pods.py` — document which path is chosen and why
- [ ] Ensure ACL grant/revoke is atomic with Turtle write: if the Turtle write fails, do not apply the ACL change; if the ACL change fails, log the inconsistency as an error and do not leave a dangling Turtle file
- [ ] Add `acl-manage` as an available skill in `ayoub-student/agent.yaml` (agent needs access to manage its own pod consent)
- [ ] Test that `acl-manage` correctly scopes `AGENT_POD_OWNERSHIP` to `ayoub` for the ayoub-student agent (no other pod can be modified)

### Task 4: SPARQL exclusion filter for revoked consent (AC3)
- [ ] Identify all SPARQL `.rq` templates that query Ayoub's data (in `agents/*/prompts/` or `agents/skills/sparql-query/templates/`)
- [ ] Add a SPARQL filter that skips any named graph whose pod has a consent grant resource with a non-empty `poc:revokedAt`
- [ ] Preferred pattern: SERVICE or OPTIONAL pattern that checks Oxigraph for a revocation signal on the named graph before including it in the aggregate
- [ ] Alternatively: `consent_grant.py` exposes `get_revoked_pods() -> list[str]` which the pipeline can use to inject `FILTER(?pod NOT IN (...))` into aggregate queries at runtime
- [ ] Document the chosen exclusion approach in Dev Notes (below) — static FILTER injection vs. dynamic subquery
- [ ] Verify that Isabelle's aggregate query (Story 3.6 template) excludes Ayoub after his consent is revoked, and that the query still returns correct totals for the remaining participants

### Task 5: JSONL consent events (AC1, AC3)
- [ ] Implement `emit_consent_event(event_type: str, pod: str, grant_id: str, grantee: str, purpose: str = "", timestamp: str = "") -> None` in `consent_grant.py`
- [ ] Append JSONL events to `data/consent-events.jsonl` (create file if absent, always append)
- [ ] `consent.grant` event schema:
```json
{"event_type": "consent.grant", "timestamp": "ISO-8601", "pod": "ayoub", "grant_id": "grant-ayoub-isabelle-20260325", "grantee": "http://localhost:3000/isabelle/profile/card#me", "purpose": "Justify funding renewal for robotics program"}
```
- [ ] `consent.revoke` event schema:
```json
{"event_type": "consent.revoke", "timestamp": "ISO-8601", "pod": "ayoub", "grant_id": "grant-ayoub-isabelle-20260325", "grantee": "http://localhost:3000/isabelle/profile/card#me"}
```
- [ ] Events are consumed by the mission control TUI (Story 3.7.1) — ensure timestamp is always ISO-8601 with UTC `Z` suffix

### Task 6: Troll verification — "why does X have access?" (AC2)
- [ ] Create a troll verification script `agents/troll-adversary/attacks/consent_grant_audit.py` (or add to existing troll audit module)
- [ ] Implement `audit_consent_grant(pod_name: str, grantee_webid: str) -> AuditResult`:
  1. Fetch all consent grants for the pod via `list_consent_grants(pod_name)`
  2. Find the grant matching the grantee WebID
  3. If found: return `AuditResult(found=True, grant_uri=..., purpose=..., scope=..., excluded=..., granted_at=..., revoked_at=..., expires_at=...)`
  4. If not found: return `AuditResult(found=False, message="No active consent grant found for <grantee>")`
- [ ] Implement plain-language summary: `format_audit_answer(audit_result: AuditResult) -> str` — returns a human-readable paragraph suitable for display in the TUI or troll report
- [ ] Verify the troll can answer "why does Isabelle have access?" without querying CSS ACLs directly — the consent grant RDF resource is sufficient
- [ ] Log audit result as structured JSON to stdout

### Task 7: Tests (AC1, AC2, AC3)
- [ ] Create `tests/test_consent_grant.py`
- [ ] Test `create_consent_grant`: mock CSS HTTP PUT and acl-manage call; verify Turtle content, JSONL event, and return value
- [ ] Test `revoke_consent_grant`: mock CSS GET + PUT and acl-manage call; verify `poc:revokedAt` is populated, JSONL event emitted, return value correct
- [ ] Test `get_consent_grant`: mock CSS GET response; verify field parsing returns correct dict
- [ ] Test `list_consent_grants`: mock CSS directory listing response; verify returns list of grant summaries
- [ ] Test Turtle template rendering: verify rendered Turtle parses cleanly with `rdflib`; verify `poc:revokedAt` is empty string initially; verify all required fields present
- [ ] Test SPARQL exclusion filter: create a mock scenario where one pod has a revoked grant; verify that the aggregate query excludes that pod's named graph and returns the correct count for remaining pods
- [ ] Test `audit_consent_grant`: verify plain-language output contains purpose, scope, and excluded fields; verify "not found" case
- [ ] Test JSONL event emission: verify `consent.grant` and `consent.revoke` events are appended correctly with ISO-8601 timestamps
- [ ] Minimum 10 unit tests; all must pass

## Dev Notes

### Architecture Decisions Referenced

- **BP-3: Consent Grant as RDF Resource** (`_bmad-output/planning-artifacts/architecture.md`, line ~302): The boolean ACL flag evolves into a dereferenceable RDF resource carrying the full consent contract. This story implements BP-3 for the PoC. The URI is `localhost:3000`-scoped (not production-dereferenceable), but the data model is pilot-ready.
- **BP-4: Tombstone Revocation** (`_bmad-output/planning-artifacts/architecture.md`, line ~340): Revocation populates `poc:revokedAt` rather than deleting the resource. Historical aggregates remain immutable. The tombstone is a permanent record — it proves consent was granted and when it was withdrawn.
- **BP-1: Bidirectional Accountability**: The consent grant URI is the "receipt" link. Access log entries reference the grant URI, enabling audit trails from pod to purpose.
- **FR-Governance-5 / FR-Sovereignty**: Ayoub can inspect, grant, and revoke consent without institutional intermediary. The RDF resource is the governance document.

### Key Design Decisions

**Turtle storage in pod vs. Oxigraph**
Consent grant resources are written directly to Ayoub's CSS pod (HTTP PUT), NOT to Oxigraph. Rationale: the pod IS the source of truth for personal governance documents. Oxigraph holds learning activity data. Mixing consent governance into the SPARQL store would blur the trust boundary. The troll dereferences the pod URL, not a SPARQL endpoint.

**`poc:revokedAt` as empty string (not absent)**
The `poc:revokedAt` predicate is ALWAYS present in the Turtle from the moment of grant — it is initialized to an empty string literal `""`. This means:
- A SPARQL `FILTER(?revokedAt = "")` detects active grants
- A SPARQL `FILTER(?revokedAt != "")` detects revoked grants
- The tombstone field is never absent — checking for absence would require `NOT EXISTS` patterns that are more fragile
Consequence: parsers must handle empty string as "not yet revoked" (truthy check on string length, not on predicate presence).

**Grant ID format**
`grant-{pod_name}-{grantee_slug}-{date}` (e.g., `grant-ayoub-isabelle-20260325`). If the same grantee is granted twice on the same day, append a counter suffix (`-2`). The grant ID is part of the URI path and must be filesystem-safe (no spaces, no special characters beyond hyphens).

**ACL call strategy**
`consent_grant.py` imports `grant_acl_access` and `revoke_acl_access` directly from `provision_pods.py` (not via subprocess CLI). Rationale: pipeline-internal call avoids subprocess overhead and simplifies error propagation. The `acl-manage` skill is the agent-callable layer; `consent_grant.py` is the pipeline-internal layer. Both ultimately call the same CSS ACL functions.

**SPARQL exclusion filter — runtime injection approach**
The recommended approach is runtime FILTER injection via `consent_grant.py#get_revoked_pods()`. At query execution time, the pipeline checks which pods have non-empty `poc:revokedAt` and injects `FILTER(?pod NOT IN (<pod1>, <pod2>, ...))` into aggregate templates. This avoids coupling the SPARQL templates to the CSS pod structure and keeps templates readable. If no pods are revoked, the FILTER is omitted entirely (no performance cost).

### Turtle Schema for Consent Grant

```turtle
@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325>
  a poc:ConsentGrant ;
  poc:requestedBy   <http://localhost:3000/isabelle/profile/card#me> ;
  poc:purpose       "Justify funding renewal for robotics program to Brussels-Capital parliament" ;
  poc:scope         "Aggregate participant count, avg session attendance, community distribution" ;
  poc:excluded      "Individual names, scores, school identifiers, addresses" ;
  poc:consequenceOfRefusal "Data excluded from aggregate; decision made on remaining N-1 participants" ;
  poc:grantedAt     "2026-03-25T10:00:00Z"^^xsd:dateTime ;
  poc:revokedAt     "" ;
  poc:expiresAt     "2027-03-25T00:00:00Z"^^xsd:dateTime .
```

The `poc:` namespace `http://localhost:3000/vocab/pocpod0#` matches `data/schemas/pocpod0-vocab.ttl`. New terms (`ConsentGrant`, `requestedBy`, `purpose`, `scope`, `excluded`, `consequenceOfRefusal`, `grantedAt`, `revokedAt`, `expiresAt`) must be declared in `pocpod0-vocab.ttl` if not already present.

### Revocation Tombstone Pattern

On revocation:
1. Fetch the Turtle via HTTP GET (CSS authenticated)
2. Parse with `rdflib`; locate the `poc:revokedAt` triple
3. Replace the empty string object with the current ISO-8601 UTC timestamp
4. Re-serialize to Turtle; write back via HTTP PUT (same URI — idempotent resource update)
5. Call `revoke_acl_access(pod_name, grantee_webid)` from `provision_pods.py`
6. Emit `consent.revoke` JSONL event

The tombstone approach means the consent grant resource is immutable in terms of existence — it is never deleted, only marked as revoked. A `GET` on the URI after revocation returns the full history including when it was granted and when it was revoked. This satisfies GDPR Article 7(3) audit requirements.

### Dereferenceable URI Concept in PoC

Within the PoC, "dereferenceable" means: `GET http://localhost:3000/ayoub/consent-grants/[grant-id].ttl` returns valid Turtle with CSS authentication. This is the CSS pod HTTP interface. For the pilot, the same pattern applies with real domain names. The troll's `audit_consent_grant()` uses this HTTP GET, not a SPARQL query — this is the key architectural distinction from Oxigraph-based data.

### Project Structure Notes

Files to create:

```
pipeline/
└── src/pocpod0_pipeline/
    └── consent_grant.py              # NEW — consent grant create/revoke/list/audit module

infra/
└── css/pods/
    └── consent-grant.ttl.j2          # NEW — Jinja2 Turtle template for consent grant resource

agents/
├── troll-adversary/
│   └── attacks/
│       └── consent_grant_audit.py    # NEW — troll verification "why does X have access?"
└── ayoub-student/
    └── agent.yaml                    # MODIFIED — add acl-manage to available skills

tests/
└── test_consent_grant.py             # NEW — unit tests for consent_grant.py and audit
```

Files to modify:

```
data/schemas/pocpod0-vocab.ttl        # MODIFIED — add ConsentGrant class and poc: predicates
agents/skills/acl-manage/SKILL.md    # REVIEW — verify grant/revoke actions exist (Story 5.1)
agents/skills/sparql-query/templates/ # MODIFIED — add revocation exclusion filter where applicable
```

### Dependencies

- **Depends on Story 5.1:** `acl-manage` skill (`agents/skills/acl-manage/handler.py`) and `provision_pods.py` ACL functions (`grant_acl_access`, `revoke_acl_access`) must exist. `data/consent-events.jsonl` must exist (created in Story 5.1).
- **Depends on Story 3.6:** Isabelle's aggregate SPARQL templates must be identifiable for revocation filter injection.
- **Reuses from Story 2.3:** Oxigraph named graph pattern — revocation exclusion filter must reference the same named graph URIs used during ingestion.
- **Reuses from Story 2.6:** CSS auth pattern (Authorization WebID header on HTTP PUT/GET to pod resources).
- **Consumed by Story 5.6:** `poc:expiresAt` and `poc:token` fields in the Turtle are extended in Story 5.6 — the Jinja2 template and `consent_grant.py` must be extensible for those additions without rewriting from scratch.

### Error Handling

- **CSS PUT fails:** Log the error, do NOT apply the ACL change, return `ConsentGrantResult(status="error")`. Never leave a dangling ACL without a corresponding Turtle resource.
- **ACL grant fails after Turtle write:** Log the inconsistency as `{"level": "ERROR", "event": "consent.grant.inconsistency", "pod": ..., "action": "acl_grant_failed_after_turtle_write"}`. Attempt to delete the Turtle resource to restore consistency. Alert the operator.
- **Turtle parse error on revocation:** Return `RevokeGrantResult(status="error", error_message="Turtle parse failed")`. Do NOT proceed with ACL revocation if the grant state cannot be read — the tombstone write would be unsafe.
- **JSONL event write fails:** Log to stderr but do NOT fail the operation. Events are telemetry — they must not block governance actions.
- **Grant ID collision:** If `grant-{pod}-{grantee}-{date}.ttl` already exists at the target URI, append `-2`, `-3`, etc. until a free slot is found (max 9 attempts before returning error).

### Isolation Notes

- Use `distrobox-host-exec` for podman containers when running from within the distrobox environment
- Example: `distrobox-host-exec podman exec community-solid-server curl -H "Authorization: WebID <webid>" http://localhost:3000/ayoub/consent-grants/`
- CSS HTTP operations run against `localhost:3000` — accessible from the host via `distrobox-host-exec` if CSS is containerized

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (BP-3 Consent Grant as RDF Resource, BP-4 Tombstone Revocation, BP-1 Bidirectional Accountability)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Epic 5 stories — Story 5.5 acceptance criteria)
- Story 5.1: `_bmad-output/implementation-artifacts/5-1-ayoub-governance-transition.md` (acl-manage skill, consent-events.jsonl)
- Story 3.6: `_bmad-output/implementation-artifacts/3-6-isabelle-evidence-based-policy.md` (Isabelle aggregate SPARQL templates subject to revocation filter)
- Story 2.3: `_bmad-output/implementation-artifacts/2-3-oxigraph-setup-rdf-storage-with-provenance.md` (named graph pattern for SPARQL exclusion)
- Story 2.6: `_bmad-output/implementation-artifacts/2-6-bidirectional-traceability-embedding-triple-pod.md` (CSS auth pattern on pod HTTP operations)
- Vocab: `data/schemas/pocpod0-vocab.ttl` (poc: namespace, extend with ConsentGrant terms)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
