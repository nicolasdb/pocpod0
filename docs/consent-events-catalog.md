# Consent Events Catalog

All consent-related events are appended as JSONL lines to `data/consent-events.jsonl`.

This catalog documents every event type emitted by the pocpod0 pipeline, with schema examples and source references.

---

## Event Types

### `acl.grant`

Emitted when an agent grants ACL access to a pod.

**Source:** `agents/skills/acl-manage/handler.py` → `acl-manage/SKILL.md` lines 103–106

```json
{"event_type": "acl.grant", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "identity": "http://localhost:3000/marc-admin/profile/card#me", "action": "grant", "role": "guardian", "access_level": "read"}
```

---

### `acl.revoke`

Emitted when an agent revokes ACL access from a pod.

**Source:** `agents/skills/acl-manage/handler.py` → `acl-manage/SKILL.md` lines 108–111

```json
{"event_type": "acl.revoke", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "identity": "http://localhost:3000/marc-admin/profile/card#me", "action": "revoke"}
```

---

### `acl.view`

Emitted when an agent reads the current ACL state of a pod.

**Source:** `agents/skills/acl-manage/handler.py` → `acl-manage/SKILL.md` lines 113–116

```json
{"event_type": "acl.view", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "action": "view", "grant_count": 2}
```

---

### `acl.governance.transition`

Emitted when a pod transitions governance mode (e.g., shared_governance → sole_owner). Triggers revocation of all guardian identities.

**Source:** `pipeline/src/pocpod0_pipeline/governance_transition.py` → `acl-manage/SKILL.md` lines 118–121

```json
{"event_type": "acl.governance.transition", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "from_role": "shared_governance", "to_role": "sole_owner", "revoked_identities": ["http://localhost:3000/marc-admin/profile/card#me"]}
```

---

### `acl.denied`

Emitted when an agent attempts a mutation (grant/revoke) but is not authorized (not in `AGENT_POD_OWNERSHIP`).

**Source:** `agents/skills/acl-manage/handler.py` → `acl-manage/SKILL.md` lines 123–126

```json
{"event_type": "acl.denied", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "agent_id": "claire-teacher", "action": "grant", "reason": "Authorization denied: agent claire-teacher does not own pod ayoub"}
```

---

### `consent.grant`

Emitted when a time-scoped ephemeral consent grant is created (Story 5.6).

**Source:** `pipeline/src/pocpod0_pipeline/consent_grant.py` lines 342–350

```json
{"event_type": "consent.grant", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "identity": "http://localhost:3000/isabelle-policy/profile/card#me", "grant_id": "urn:consent:ayoub:abc123", "expires_at": "2026-04-14T10:00:00Z"}
```

---

### `consent.revoke`

Emitted when a consent grant is explicitly revoked before expiry.

**Source:** `pipeline/src/pocpod0_pipeline/consent_grant.py` lines 426–434

```json
{"event_type": "consent.revoke", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "identity": "http://localhost:3000/isabelle-policy/profile/card#me", "grant_id": "urn:consent:ayoub:abc123"}
```

---

### `consent.expired`

Emitted by `expire_tokens.py` when an ephemeral token's `poc:expiresAt` has passed during the pipeline's expiry check stage.

**Source:** `pipeline/src/pocpod0_pipeline/expire_tokens.py` lines 312–316

```json
{"event_type": "consent.expired", "timestamp": "2026-04-13T10:00:00Z", "token_id": "urn:token:ayoub:def456", "pod": "ayoub", "grant_id": "urn:consent:ayoub:abc123", "expired_at": "2026-04-13T09:00:00Z"}
```

---

### `deletion.step`

Emitted at each step of the three-layer deletion cascade (CSS pod, Oxigraph graph, Qdrant vectors).

**Source:** `pipeline/src/pocpod0_pipeline/delete_cascade.py` lines 113–116, 478–481

```json
{"event_type": "deletion.step", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "step": "css", "status": "ok"}
```

---

### `deletion.complete`

Emitted when all three deletion cascade layers complete successfully.

**Source:** `pipeline/src/pocpod0_pipeline/delete_cascade.py` lines 583–586

```json
{"event_type": "deletion.complete", "timestamp": "2026-04-13T10:00:00Z", "pod": "ayoub", "steps_completed": ["css", "oxigraph", "qdrant"]}
```

---

## Notes

- All events are **append-only** — never modified after emission.
- `data/consent-events.jsonl` is created on first write (directory auto-created).
- The ACL dashboard (`dashboard_api.py`) reads this file for real-time consent state.
- `token.issued`, `token.expired`, and `receipt.written` appear as **aspirational event names** in some planning documents (AC5 of Story 4.0) but are **not implemented** in the current codebase. The implemented token lifecycle is: consent grant → `consent.grant`, expiry sweep → `consent.expired`, explicit revocation → `consent.revoke`.
