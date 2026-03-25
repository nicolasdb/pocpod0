# Story 5.6: [backlog] Ephemeral Time-Scoped Consent — Double-Aveugle Pattern

Status: ready-for-dev

## Story

As **Ayoub** (data sovereign),
I want to grant time-scoped access to sensitive context data using an opaque token — so the receiving service never knows whose data it is and access auto-revokes when the token expires,
so that I can participate in collective programs (like a summer camp) without permanently exposing my identity to every service involved.

## Acceptance Criteria

**AC1: Time-scoped consent grant with opaque token**
Given a consent grant resource (Story 5.5) is being created for a time-scoped context (e.g., summer camp food service)
When `create_ephemeral_consent_grant()` is called with `expires_at` (camp end date) and the grantee is a service (not an institutional WebID)
Then the consent grant Turtle includes `poc:expiresAt` set to the camp end date
And it includes an opaque `poc:token` alias — a 16-character SHA-256 hex digest of `(pod_uri + grant_timestamp)`
And the food service receives only the token value — not Ayoub's WebID or pod URI
And the token cannot be reversed to Ayoub's identity without the token lookup index (held by school admin only)

**AC2: Token expiry auto-revokes access**
Given a consent grant resource with `poc:expiresAt` set to a date that has now passed
When the expiry check script (pipeline step or cron) runs
Then the CSS ACL for the token-scoped resource is revoked (grantee loses read access)
And `poc:revokedAt` is populated in the Turtle with the expiry timestamp (tombstone — same pattern as Story 5.5)
And a `consent.expired` JSONL event is emitted to `data/consent-events.jsonl`:
```json
{"event_type": "consent.expired", "timestamp": "ISO-8601", "token_id": "7f3a1b2c4e5f6a7b", "pod": "ayoub", "grant_id": "grant-ayoub-camp-food-20260620"}
```
And a receipt is written to Ayoub's access log at `/ayoub/access-log/camp-food-[date].ttl` recording the full access window (granted_at → expired_at)

**AC3: Double-aveugle aggregate query**
Given the camp community pod (`school-community`) holds aggregate dietary restriction data for the camp
When Isabelle queries the camp community pod for the program aggregate
Then the query targets the community pod's named graph — NOT Ayoub's pod directly
And the query returns aggregate counts via `GROUP BY` (e.g., "32 registrations with dietary restrictions")
And no individual WebID or identity is exposed in the query result
And the double-aveugle principle holds: the food service is blind to identity, the policy actor (Isabelle) sees only counts

## Tasks / Subtasks

### Task 1: Extend `consent_grant.py` for ephemeral tokens (AC1)
- [ ] Add `create_ephemeral_consent_grant(pod_name: str, service_label: str, purpose: str, scope: str, excluded: str, consequence_of_refusal: str, expires_at: str) -> EphemeralGrantResult` to `pipeline/src/pocpod0_pipeline/consent_grant.py`
- [ ] Token generation: `hashlib.sha256(f"{pod_uri}{grant_timestamp}".encode()).hexdigest()[:16]`
  - `pod_uri` = `http://localhost:3000/{pod_name}/`
  - `grant_timestamp` = ISO-8601 UTC timestamp at the moment of grant (same value as `poc:grantedAt`)
  - Token is deterministic: same inputs always produce the same token (useful for testing)
  - Token is NOT reversible without the lookup index — SHA-256 preimage resistance holds
- [ ] Render the ephemeral Turtle template (Task 2) with all fields including `poc:token`
- [ ] Store the token→pod_uri mapping in the Oxigraph token index (Task 3) — one triple: `<urn:token:{token_id}> poc:tokenFor <{pod_uri}>`
- [ ] Emit `consent.grant` JSONL event with `token_id` field appended:
```json
{"event_type": "consent.grant", "timestamp": "ISO-8601", "pod": "ayoub", "grant_id": "...", "grantee": "camp-food-service", "purpose": "...", "token_id": "7f3a1b2c4e5f6a7b", "expires_at": "..."}
```
- [ ] Return `EphemeralGrantResult(grant_id, grant_uri, pod_name, token_id, expires_at, status, error_message="")`

### Task 2: Ephemeral consent grant Turtle template (AC1)
- [ ] Create `infra/css/pods/ephemeral-consent-grant.ttl.j2` (Jinja2 template — separate from `consent-grant.ttl.j2` to avoid breaking Story 5.5 baseline)
- [ ] Template variables: `grant_uri`, `service_label`, `token_id`, `purpose`, `scope`, `excluded`, `consequence_of_refusal`, `granted_at`, `expires_at`
- [ ] Include `poc:token` predicate alongside `poc:requestedBy` (the token IS the identity of the requestor — the service has no WebID)
- [ ] Rendered template:
```turtle
@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<{{ grant_uri }}> a poc:ConsentGrant , poc:EphemeralConsentGrant ;
  poc:token         "{{ token_id }}" ;
  poc:serviceLabel  "{{ service_label }}" ;
  poc:purpose       "{{ purpose }}" ;
  poc:scope         "{{ scope }}" ;
  poc:excluded      "{{ excluded }}" ;
  poc:consequenceOfRefusal "{{ consequence_of_refusal }}" ;
  poc:grantedAt     "{{ granted_at }}"^^xsd:dateTime ;
  poc:revokedAt     "" ;
  poc:expiresAt     "{{ expires_at }}"^^xsd:dateTime .
```
- [ ] Declare `poc:EphemeralConsentGrant` (subclass of `poc:ConsentGrant`), `poc:token`, and `poc:serviceLabel` in `data/schemas/pocpod0-vocab.ttl`
- [ ] Validate rendered Turtle with `rdflib` before writing to pod

### Task 3: Token lookup index in Oxigraph (AC1, AC3)
- [ ] Implement `register_token(token_id: str, pod_uri: str) -> None` in `consent_grant.py`:
  - Issue SPARQL UPDATE to Oxigraph named graph `<urn:token-index>`:
    ```sparql
    PREFIX poc: <http://localhost:3000/vocab/pocpod0#>
    INSERT DATA {
      GRAPH <urn:token-index> {
        <urn:token:{{ token_id }}> poc:tokenFor <{{ pod_uri }}> ;
                                   poc:grantId "{{ grant_id }}" ;
                                   poc:issuedAt "{{ issued_at }}"^^xsd:dateTime ;
                                   poc:expiresAt "{{ expires_at }}"^^xsd:dateTime .
      }
    }
    ```
  - The named graph `<urn:token-index>` is readable only by the school admin WebID (enforced at the CSS/Oxigraph level — the food service cannot query this graph)
- [ ] Implement `lookup_token(token_id: str) -> dict | None` in `consent_grant.py`:
  - SPARQL SELECT on `<urn:token-index>` graph: return `{pod_uri, grant_id, issued_at, expires_at}` or `None` if not found
  - This function is used by the expiry check script and by the school admin only
- [ ] Implement `deregister_token(token_id: str) -> None` in `consent_grant.py`:
  - Issue SPARQL UPDATE to DELETE the token triple from `<urn:token-index>` (called on revocation/expiry)
  - The triple is removed — the token no longer resolves — but the pod's Turtle tombstone remains
- [ ] Document that the food service NEVER queries `<urn:token-index>` — it only presents the token value when requesting data. The token lookup is a school-admin-only operation.

### Task 4: Expiry check script — pipeline step (AC2)
- [ ] Create `pipeline/src/pocpod0_pipeline/expire_tokens.py`
- [ ] Implement `check_expired_tokens() -> list[ExpiryResult]`:
  1. Query Oxigraph `<urn:token-index>` for all tokens where `poc:expiresAt` <= NOW()
  2. For each expired token: call `revoke_expired_token(token_id, grant_id, pod_name)`
  3. Return list of `ExpiryResult(token_id, pod_name, grant_id, expired_at, status)`
- [ ] Implement `revoke_expired_token(token_id: str, grant_id: str, pod_name: str) -> ExpiryResult`:
  1. Fetch and update the Turtle in the pod: populate `poc:revokedAt` with the expiry timestamp
  2. Call `revoke_acl_access(pod_name, token_id)` from `provision_pods.py` (or equivalent)
  3. Deregister the token from `<urn:token-index>` via `deregister_token(token_id)`
  4. Write access log receipt to pod (Task 6)
  5. Emit `consent.expired` JSONL event (Task 5)
  6. Return `ExpiryResult(token_id, pod_name, grant_id, expired_at, status="revoked")`
- [ ] Implement CLI entrypoint: `python pipeline/src/pocpod0_pipeline/expire_tokens.py` — runs the expiry check once and exits
- [ ] This script is intended to be called periodically by the pipeline or manually during demo — it is NOT a long-running daemon
- [ ] Log each expiry with structured JSON to stdout

### Task 5: JSONL expiry event (AC2)
- [ ] `expire_tokens.py` emits `consent.expired` event to `data/consent-events.jsonl` on each expired token:
```json
{"event_type": "consent.expired", "timestamp": "ISO-8601", "token_id": "7f3a1b2c4e5f6a7b", "pod": "ayoub", "grant_id": "grant-ayoub-camp-food-20260620", "expired_at": "2026-08-31T23:59:59Z"}
```
- [ ] Reuse `emit_consent_event()` from `consent_grant.py` (extend its signature if needed to support `token_id` and `expired_at` fields)
- [ ] Emit events are append-only to `data/consent-events.jsonl` — never overwrite
- [ ] The mission control TUI (Story 3.7.1) should display `consent.expired` events in the consent events stream

### Task 6: Access log receipt written to Ayoub's pod (AC2)
- [ ] On token expiry, write a Turtle receipt to `/ayoub/access-log/camp-food-[date].ttl` in the pod:
```turtle
@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://localhost:3000/ayoub/access-log/camp-food-{{ date }}> a poc:AccessReceipt ;
  poc:token         "{{ token_id }}" ;
  poc:serviceLabel  "{{ service_label }}" ;
  poc:grantId       "{{ grant_id }}" ;
  poc:accessGrantedAt "{{ granted_at }}"^^xsd:dateTime ;
  poc:accessExpiredAt "{{ expired_at }}"^^xsd:dateTime ;
  poc:receiptType   "ephemeral-expiry" .
```
- [ ] Create `infra/css/pods/access-receipt.ttl.j2` Jinja2 template for the receipt
- [ ] The receipt is written to the pod via HTTP PUT (CSS authenticated as pod owner)
- [ ] The receipt is append-style: if a receipt already exists for the same `camp-food-[date]`, use a unique suffix (e.g., `camp-food-[date]-2.ttl`)
- [ ] Document that in the PoC, receipts are written by the pipeline (server-side); in the pilot, receipts would be generated by the CSS server automatically on access

### Task 7: Community pod setup for food service scenario (AC3)
- [ ] Ensure the `school-community` pod exists in the CSS provisioning scripts (verify in `infra/css/pods/` and `pipeline/src/pocpod0_pipeline/provision_pods.py`)
- [ ] Seed the community pod with aggregate dietary restriction data representing the camp enrollment:
  - Create `data/seeds/camp-dietary-aggregate.ttl` with mock aggregate counts:
    - total camp enrollments
    - count with no dietary restriction
    - count with gluten intolerance
    - count with nut allergy
    - count with lactose intolerance
  - Data uses `GROUP BY`-style aggregate triples (counts, not individual records)
  - No individual WebIDs or names appear in the community pod data
- [ ] Create or verify a SPARQL template `agents/skills/sparql-query/templates/camp-aggregate.rq` that queries the community pod named graph for dietary restriction counts
- [ ] Verify the template returns aggregate counts only — no individual identification possible by query construction (structural anonymization per BP-2)
- [ ] ACL on community pod: Isabelle's WebID has read access; food service token does NOT have access to the community pod (food service only receives its per-token data, not aggregates)

### Task 8: Double-aveugle demonstration test (AC1, AC2, AC3)
- [ ] Create `tests/test_ephemeral_consent.py`
- [ ] Test `create_ephemeral_consent_grant`: verify token is a 16-char hex string; verify Turtle contains `poc:token` and `poc:expiresAt`; verify token registered in Oxigraph index
- [ ] Test token generation determinism: same `pod_uri` + `grant_timestamp` always produces same token
- [ ] Test `lookup_token`: mock Oxigraph SPARQL response; verify correct `pod_uri` returned
- [ ] Test `deregister_token`: verify SPARQL DELETE issued to `<urn:token-index>` with correct token URI
- [ ] Test `check_expired_tokens`: mock Oxigraph response with 2 expired tokens + 1 active token; verify only the 2 expired tokens are revoked
- [ ] Test `revoke_expired_token`: verify Turtle `poc:revokedAt` populated; ACL revoked; token deregistered; JSONL event emitted; access log receipt written
- [ ] Test double-aveugle property: verify that the food service token value does NOT appear as a WebID in Ayoub's pod — the token is an opaque string, not a dereferenceable identity
- [ ] Test aggregate query (community pod): verify camp-aggregate.rq returns only counts; verify no individual WebID appears in query result
- [ ] Test access log receipt: verify receipt Turtle is written to correct path with correct `poc:accessGrantedAt` and `poc:accessExpiredAt` values
- [ ] Minimum 12 unit tests; all must pass

### Task 9: Integration tests (AC1, AC2, AC3)
- [ ] Create `tests/test_ephemeral_consent_integration.py` (or extend `test_ephemeral_consent.py` with integration markers)
- [ ] Integration test: full lifecycle — create ephemeral grant → verify token in Oxigraph index → simulate expiry (mock `datetime.now()` past `expires_at`) → run expiry check → verify tombstone in Turtle → verify JSONL event emitted → verify receipt written → verify ACL revoked
- [ ] Integration test: double-aveugle — verify food service cannot query `<urn:token-index>` (SPARQL ACL enforcement on the named graph)
- [ ] Integration test: aggregate query still works after Ayoub's individual token expires (community pod data is independent of Ayoub's pod lifecycle)
- [ ] Mark integration tests with `@pytest.mark.integration` to allow selective exclusion from unit-test-only runs

## Dev Notes

### Architecture Decisions Referenced

- **BP-5: Ephemeral Time-Scoped Consent (Double-Aveugle Pattern)** (`_bmad-output/planning-artifacts/architecture.md`, line ~322): This story IS the implementation of BP-5. The food regime / summer camp scenario is the canonical demonstration.
- **BP-3: Consent Grant as RDF Resource**: Story 5.6 builds directly on Story 5.5. The `poc:token` and `poc:expiresAt` fields are additions to the BP-3 Turtle schema — not a replacement. `poc:EphemeralConsentGrant` is a subclass of `poc:ConsentGrant`.
- **BP-2: Trustless Anonymization**: The community pod aggregate query is structural anonymization — `GROUP BY` makes individual retrieval impossible by construction, not by policy. The food service scenario demonstrates BP-2 at the community pod level.
- **BP-4: Tombstone Revocation**: Token expiry applies the same tombstone pattern as explicit revocation (Story 5.5) — `poc:revokedAt` is populated, the resource is not deleted.

### Double-Aveugle Design

The double-aveugle principle has two distinct blindnesses:

| Actor | What they see | What they are blind to |
|---|---|---|
| Food service | Token value → dietary restriction (yes/no) | Whose data it is (Ayoub's identity) |
| Isabelle (policy) | Aggregate counts in community pod | Individual dietary choices and identities |
| School admin | Token → learner mapping in `<urn:token-index>` | Food service queries (they never see what the service does with the data) |
| Ayoub | Full receipt in access log | That the food service exists beyond the token string |

This is NOT "the service is malicious and we're stopping it." The service is legitimate — it just doesn't NEED to know whose data it is. The architecture enforces this structurally, without requiring the food service to be trusted.

### Token Generation Algorithm

```python
import hashlib

def generate_token(pod_uri: str, grant_timestamp: str) -> str:
    """
    Generate a deterministic opaque token for an ephemeral consent grant.

    Inputs:
      pod_uri: e.g. "http://localhost:3000/ayoub/"
      grant_timestamp: ISO-8601 UTC string, e.g. "2026-06-20T08:00:00Z"

    Returns: 16-character lowercase hex string (64 bits of SHA-256)
    """
    raw = f"{pod_uri}{grant_timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
```

Properties:
- **Deterministic:** same inputs → same token (enables re-derivation for testing)
- **Opaque:** the food service sees `7f3a1b2c4e5f6a7b` — without the pod URI and timestamp, it cannot identify Ayoub
- **Not a WebID:** the token is a plain string literal in RDF (`poc:token "7f3a1b2c4e5f6a7b"`), not a URI. The food service cannot dereference it.
- **16 chars sufficient for PoC:** 64 bits of SHA-256 → collision probability negligible for the PoC scenario (< 100 tokens total)

### Oxigraph Token Index

The token index is a named graph in Oxigraph, used exclusively for school-admin-level lookup:

```
Named graph URI: <urn:token-index>
ACL: readable by school admin WebID only
     NOT readable by food service, Isabelle, Fatima, Claire, or Ayoub directly
```

Triple pattern per token:
```turtle
<urn:token:7f3a1b2c4e5f6a7b> poc:tokenFor   <http://localhost:3000/ayoub/> ;
                               poc:grantId    "grant-ayoub-camp-food-20260620" ;
                               poc:issuedAt   "2026-06-20T08:00:00Z"^^xsd:dateTime ;
                               poc:expiresAt  "2026-08-31T23:59:59Z"^^xsd:dateTime .
```

The named graph approach (consistent with Story 2.3 patterns) allows per-graph ACL enforcement. The food service NEVER needs to query this graph — it only presents the token string when requesting data, and the pod's ACL (time-scoped) is what grants or denies access.

**Why Oxigraph and not the pod?**
The token index contains the reverse mapping (token→identity). Storing it in the pod would expose it to anyone who can read the pod. Oxigraph's named graph is an infrastructure-level store that can enforce stricter access control. This mirrors how CSS pods hold personal data while Oxigraph holds derived/indexed data.

### Expiry Enforcement Mechanism

The `expire_tokens.py` script is the enforcement mechanism. It is not a daemon — it runs as a pipeline step (analogous to `provision_pods.py`). In a production system, this would be a scheduled job (cron or Kubernetes CronJob). For the PoC demo, it is triggered manually to demonstrate the expiry event.

Demo sequence:
1. `python pipeline/src/pocpod0_pipeline/consent_grant.py create-ephemeral --pod ayoub --expires 2026-08-31` → creates grant, registers token, ACL active
2. `python pipeline/src/pocpod0_pipeline/expire_tokens.py` (run after mocking the date past expiry) → revokes token, writes receipt, emits JSONL event
3. Dashboard (TUI) shows `consent.expired` event in the consent stream

### Community Pod Aggregate Query

The food service scenario requires a community pod holding camp enrollment data. The structural separation is:

- **Ayoub's pod** (`/ayoub/`): holds his individual dietary restriction. The food service receives an ephemeral token scoped to a specific resource in this pod (e.g., `/ayoub/health/food-regime.ttl`).
- **Community pod** (`/school-community/`): holds aggregate counts for the camp. This is what Isabelle queries. It is populated from enrollment data, not by querying individual pods at query time.
- **Separation principle**: The food service uses the ephemeral token to access Ayoub's pod directly. Isabelle queries the community pod for aggregates. These are two separate data flows — the community pod does NOT contain Ayoub's individual record, only counts.

The `camp-aggregate.rq` SPARQL template demonstrates BP-2: `GROUP BY` on the community pod returns counts without individual identification.

### Project Structure Notes

Files to create:

```
pipeline/
└── src/pocpod0_pipeline/
    ├── consent_grant.py              # MODIFIED (Story 5.5) — add create_ephemeral_consent_grant,
    │                                 #   register_token, lookup_token, deregister_token
    └── expire_tokens.py              # NEW — expiry check script / pipeline step

infra/
└── css/pods/
    ├── ephemeral-consent-grant.ttl.j2  # NEW — Jinja2 Turtle template for ephemeral grant
    └── access-receipt.ttl.j2           # NEW — Jinja2 Turtle template for access log receipt

data/
├── seeds/
│   └── camp-dietary-aggregate.ttl    # NEW — community pod seed data (aggregate counts)
└── consent-events.jsonl              # MODIFIED (append) — consent.expired events

agents/
└── skills/
    └── sparql-query/
        └── templates/
            └── camp-aggregate.rq     # NEW — SPARQL template for community pod dietary counts

tests/
├── test_ephemeral_consent.py         # NEW — unit tests for ephemeral consent + token lifecycle
└── test_ephemeral_consent_integration.py  # NEW — integration tests (full lifecycle + double-aveugle)
```

Files to modify:

```
pipeline/src/pocpod0_pipeline/consent_grant.py  # MODIFIED — add ephemeral grant functions
data/schemas/pocpod0-vocab.ttl                  # MODIFIED — add EphemeralConsentGrant, poc:token,
                                                #   poc:serviceLabel, poc:AccessReceipt terms
```

### Dependencies

- **Depends on Story 5.5 (this sprint):** `consent_grant.py` module and Turtle schema must exist. Story 5.6 extends them — it does NOT replace them. The `create_consent_grant()` function from Story 5.5 remains the baseline; `create_ephemeral_consent_grant()` is an extension.
- **Depends on Story 5.1:** `acl-manage` skill and `provision_pods.py` ACL functions.
- **Depends on Story 2.3:** Oxigraph must be running and accepting SPARQL UPDATEs. The `<urn:token-index>` named graph requires Oxigraph v1.x+ (named graph SPARQL support — verified in Story 2.3).
- **Depends on Story 3.6:** Isabelle's aggregate query scenario is the context for the community pod aggregate (AC3). The food service scenario is a parallel demo — both demonstrate data flowing to institutions without individual exposure.
- **Consumed by Epic 6:** The demo run (Story 6.1) should include the ephemeral token lifecycle as a narrated step — token grant, access, expiry, receipt. This is a high-impact demonstration moment for funders.

### Error Handling

- **Token registration fails (Oxigraph UPDATE fails):** Abort the ephemeral grant creation. Do NOT write the Turtle to the pod and do NOT apply the ACL. Return `EphemeralGrantResult(status="error", error_message="Token index registration failed")`. Atomicity: all three operations (Turtle write, ACL grant, token registration) must succeed or all must be rolled back.
- **Expiry check finds no expired tokens:** `check_expired_tokens()` returns an empty list and exits 0 — this is not an error.
- **Revocation of an already-expired/revoked token:** Idempotent. If `poc:revokedAt` is already non-empty, log a warning and skip. Do not error.
- **Access log receipt write fails:** Log the error to stderr but do NOT fail the revocation. The receipt is telemetry; the revocation is the critical operation.
- **Community pod not provisioned:** `expire_tokens.py` checks for the `school-community` pod on startup and logs a warning if absent. It does not fail — ephemeral token expiry is independent of the community pod.
- **Token not found in index on expiry:** Log as `{"level": "WARN", "event": "consent.expired.token_not_in_index", "token_id": "..."}` — the Turtle tombstone and ACL revocation still proceed; the index entry may have already been cleaned up.

### Isolation Notes

- Use `distrobox-host-exec` for podman containers when running from within the distrobox environment
- Oxigraph SPARQL UPDATE endpoint: `distrobox-host-exec curl -X POST http://localhost:7878/update` (if Oxigraph is containerized)
- CSS pod HTTP PUT for Turtle and receipt: `distrobox-host-exec curl -X PUT http://localhost:3000/ayoub/consent-grants/...`
- The `expire_tokens.py` script runs as a host/distrobox process and communicates with containerized services via `localhost` ports

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md` (BP-5 Ephemeral Time-Scoped Consent, BP-3 Consent Grant as RDF Resource, BP-2 Trustless Anonymization, BP-4 Tombstone Revocation)
- Epics: `_bmad-output/planning-artifacts/epics.md` (Epic 5 — Story 5.6, Anagnorisis narrative from Epic 3 retrospective 2026-03-25)
- Epic 3 Retrospective: `_bmad-output/implementation-artifacts/epic-3-retro-2026-03-25.md` (food regime / double-aveugle scenario origin, Anagnorisis narrative)
- Story 5.5: `_bmad-output/implementation-artifacts/5-5-consent-grant-as-rdf-resource.md` (BP-3 Turtle schema, tombstone pattern, consent_grant.py baseline)
- Story 5.1: `_bmad-output/implementation-artifacts/5-1-ayoub-governance-transition.md` (acl-manage skill, consent-events.jsonl)
- Story 2.3: `_bmad-output/implementation-artifacts/2-3-oxigraph-setup-rdf-storage-with-provenance.md` (named graph pattern, Oxigraph SPARQL UPDATE API)
- Story 3.6: `_bmad-output/implementation-artifacts/3-6-isabelle-evidence-based-policy.md` (aggregate query scenario that the community pod supports)
- Vocab: `data/schemas/pocpod0-vocab.ttl` (poc: namespace, extend with EphemeralConsentGrant terms)

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
