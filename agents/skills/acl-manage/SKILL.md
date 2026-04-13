---
name: acl-manage
description: Manages Web Access Control (WAC) ACL resources on Solid pods via Community Solid Server. Use when granting, revoking, or viewing pod access permissions, or when executing an age-based governance sovereignty transition that revokes all guardian access and makes the pod owner sole controller.
metadata:
  openclaw:
    emoji: "🔑"
    tags: ["solid", "acl", "privacy", "consent", "governance"]
    requires:
      bins: ["python3"]
      env: ["CSS_CONNECT_URL", "AGENT_POD_OWNERSHIP"]
---

# ACL Management Skill

This skill manages ACL lifecycle for Solid pods on Community Solid Server (CSS).
It wraps the ACL primitives from `provision_pods.py` and enforces ownership scope before any mutation.

## Invocation

Use your `exec` tool to run the handler as a subprocess:

```bash
python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
  --action ACTION \
  --pod-name POD_NAME \
  [--identity WEBID] \
  [--role ROLE_LABEL] \
  [--access-level read|read/write|control]
```

**Required arguments:**
- `--action`: One of `grant`, `revoke`, `view`, `transition`
- `--pod-name`: Target pod name (e.g. `ayoub`)

**Optional arguments:**
- `--identity`: Full WebID URI of the target identity (required for `grant` and `revoke`)
- `--role`: Role label for grant authorization block (required for `grant`)
- `--access-level`: Access level for grant — `read`, `read/write`, or `control` (default: `read`)

## Actions

### grant
Grants a WebID access to the pod at the specified access level.

```bash
python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
  --action grant \
  --pod-name ayoub \
  --identity http://localhost:3000/guardian/profile/card#me \
  --role guardian \
  --access-level read
```

Emits event: `acl.grant`

### revoke
Revokes a WebID's access from the pod.

```bash
python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
  --action revoke \
  --pod-name ayoub \
  --identity http://localhost:3000/guardian/profile/card#me
```

Emits event: `acl.revoke`

### view
Views the current ACL state for the pod (read-only, no mutation).

```bash
python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
  --action view \
  --pod-name ayoub
```

Emits event: `acl.view`

### transition
Age-based sovereignty transition — revokes all non-owner WebIDs, making the pod owner sole governor.

```bash
python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
  --action transition \
  --pod-name ayoub
```

Emits event: `acl.governance.transition`

## Ownership Scope Enforcement

The handler reads `AGENT_POD_OWNERSHIP` environment variable (comma-separated pod names)
to determine which pods the invoking agent may mutate. If the target pod is not in this list,
the action is denied and an `acl.denied` event is emitted.

- `view` action is permitted regardless of ownership scope.
- If `AGENT_POD_OWNERSHIP` is not set, all mutations are denied.

## JSONL Event Schema

All events are appended to `data/consent-events.jsonl`.

### acl.grant
```json
{"event_type": "acl.grant", "timestamp": "ISO-8601", "pod": "ayoub", "identity": "<webid>", "action": "grant", "role": "guardian", "access_level": "read"}
```

### acl.revoke
```json
{"event_type": "acl.revoke", "timestamp": "ISO-8601", "pod": "ayoub", "identity": "<webid>", "action": "revoke"}
```

### acl.view
```json
{"event_type": "acl.view", "timestamp": "ISO-8601", "pod": "ayoub", "action": "view", "grant_count": 2}
```

### acl.governance.transition
```json
{"event_type": "acl.governance.transition", "timestamp": "ISO-8601", "pod": "ayoub", "from_role": "shared_governance", "to_role": "sole_owner", "revoked_identities": ["<guardian-webid>"]}
```

### acl.denied
```json
{"event_type": "acl.denied", "timestamp": "ISO-8601", "pod": "ayoub", "agent_id": "<agent-id>", "action": "grant", "reason": "Authorization denied: agent <agent-id> does not own pod ayoub"}
```

## Output

**Success:**
```json
{"status": "ok", "action": "grant", "pod": "ayoub", "identity": "http://...", "event_type": "acl.grant", "message": "Granted guardian read access to ayoub"}
```

**Denied:**
```json
{"status": "denied", "action": "grant", "pod": "ayoub", "identity": "http://...", "event_type": "acl.denied", "message": "Authorization denied: agent claire-teacher does not own pod ayoub"}
```

**Error:**
```json
{"status": "error", "action": "grant", "pod": "ayoub", "message": "CSS returned HTTP 500"}
```

## Environment Variables

- `CSS_CONNECT_URL` — TCP endpoint for CSS (default: `http://localhost:3000`)
- `CSS_IDENTIFIER_URL` — Identifier-space base URL (default: same as `CSS_CONNECT_URL`)
- `AGENT_POD_OWNERSHIP` — Comma-separated pod names this agent owns (required for mutations)
- `AGENT_ID` — Agent identifier for logging (optional, used in denied event)

## Dependencies

- `provision_pods.py` — `grant_acl_access`, `revoke_acl_access`, `view_acl_state` primitives (Story 1.4)
- `data/consent-events.jsonl` — JSONL event stream (consumed by Mission Control TUI in Epic 6)
