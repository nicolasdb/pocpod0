# Story 1.4: ACL Grant, Revocation & Audit

Status: ready-for-dev

## Story

As a **school administrator** (Marc),
I want to dynamically grant and revoke ACL access on Pod resources and view the current consent state,
so that access control reflects real-world events (transfers, enrollment changes) and consent is auditable.

## Acceptance Criteria

**Given** an existing pod with configured ACLs
**When** a new ACL grant is issued (e.g., new school gets read access)
**Then** the pod's `.acl` resource is updated to include the new grant
**And** the newly granted role can access the pod resource

**Given** an existing pod with an active ACL grant
**When** the grant is revoked (e.g., old school access removed)
**Then** the pod's `.acl` resource is updated to remove the grant
**And** the revoked role receives HTTP 403 on subsequent access attempts

**Given** an existing pod with configured ACLs
**When** an authorized user requests the ACL/consent state
**Then** the current access grants are displayed showing who has what level of access
**And** the output is human-readable (not raw Turtle unless requested)

## Tasks / Subtasks

### Task 1: ACL Grant Function (AC1)
- [ ] Create `grant_acl_access()` function in `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Function accepts: pod_path (str), agent_id (str), role (str), access_level (str: "read" | "read/write" | "control")
- [ ] Function reads the existing `.acl` Turtle file for the target pod
- [ ] Function appends a new `acl:Authorization` block granting the specified access
- [ ] Function writes the updated `.acl` file back to the pod via HTTP PUT to CSS
- [ ] Log the grant operation in structured JSON format: `{ timestamp, service: "provision", level: "INFO", event: "acl.grant", agent: agent_id, details: { pod, role, access_level } }`
- [ ] Verify the grant by performing an HTTP GET as the newly granted identity and confirming 200 response

### Task 2: ACL Revocation Function (AC2)
- [ ] Create `revoke_acl_access()` function in `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Function accepts: pod_path (str), agent_id (str)
- [ ] Function reads the existing `.acl` Turtle file for the target pod
- [ ] Function removes the `acl:Authorization` block matching the specified agent_id
- [ ] Function writes the updated `.acl` file back to the pod via HTTP PUT to CSS
- [ ] Log the revocation operation in structured JSON format: `{ timestamp, service: "provision", level: "INFO", event: "acl.revoke", agent: agent_id, details: { pod, revoked_agent } }`
- [ ] Verify the revocation by performing an HTTP GET as the revoked identity and confirming 403 response

### Task 3: ACL State Viewer Function (AC3)
- [ ] Create `view_acl_state()` function in `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Function accepts: pod_path (str), output_format (str: "human" | "turtle", default "human")
- [ ] Function reads the `.acl` Turtle file for the target pod via HTTP GET from CSS
- [ ] Function parses the Turtle using `rdflib` to extract all `acl:Authorization` blocks
- [ ] For `output_format="human"`: produce a structured dict/JSON with entries like `{ "agent": "claire-teacher", "role": "tutor", "access_level": "read", "resources": [...] }`
- [ ] For `output_format="turtle"`: return the raw Turtle content
- [ ] Log the view operation: `{ timestamp, service: "provision", level: "INFO", event: "acl.view", details: { pod, format } }`

### Task 4: Integration Verification Script (AC1, AC2, AC3)
- [ ] Create or extend `scripts/seed-pods.sh` (or a Python helper called from it) with a verification sequence:
  1. Grant a new role access to an existing pod
  2. Verify the grant succeeds (HTTP 200 from newly granted identity)
  3. View the ACL state and confirm the new grant appears
  4. Revoke the grant
  5. Verify the revocation succeeds (HTTP 403 from revoked identity)
  6. View the ACL state and confirm the grant is gone
- [ ] All steps produce structured JSON log output

### Task 5: Unit/Integration Tests (all ACs)
- [ ] Add tests in `tests/integration/test_css_pods.py` (or create if not existing):
  - `test_grant_acl_access_succeeds` -- grants access, verifies 200 response from granted identity
  - `test_revoke_acl_access_succeeds` -- revokes access, verifies 403 response from revoked identity
  - `test_view_acl_state_human_readable` -- views ACL state, asserts structured output contains expected grants
  - `test_view_acl_state_turtle_format` -- views ACL state as Turtle, asserts valid Turtle content
  - `test_grant_then_revoke_roundtrip` -- full grant/verify/revoke/verify cycle

## Dev Notes

### Architecture Decisions

- **SEC-1 (No Real Auth):** Agent identity is configured, not authenticated. Each agent has a fixed identity and ACL token. There is no Solid-OIDC -- identity is simulated via configured credentials/tokens in the PoC.
- **SEC-2 (ACL Enforcement at Two Levels):** Pod level uses CSS native WebACL (`.acl` files per Solid spec). This story implements Pod-level ACL manipulation. Query-level enforcement (SPARQL skill validates role) is a separate concern in Epic 3.
- **API-1 (No REST API):** Access CSS directly via its native HTTP/LDP protocol. No wrapper API needed.
- **Anti-pattern warning:** Never hardcode ACL rules in agent code. ACLs live exclusively in pod `.acl` resources managed by CSS.

### CSS WebACL Format

ACL files follow the Solid WebACL specification. Each `.acl` file contains `acl:Authorization` resources in Turtle format. Example structure:

```turtle
@prefix acl: <http://www.w3.org/ns/auth/acl#>.
@prefix foaf: <http://xmlns.com/foaf/0.1/>.

<#owner>
    a acl:Authorization;
    acl:agent <agent-webid>;
    acl:accessTo <resource>;
    acl:mode acl:Read, acl:Write, acl:Control.
```

The grant function adds new `<#role-name>` authorization blocks. The revoke function removes them. CSS picks up `.acl` changes immediately -- no restart needed.

### Python Conventions

- Module: `provision_pods.py` (snake_case)
- Functions: `grant_acl_access()`, `revoke_acl_access()`, `view_acl_state()` (snake_case)
- Classes (if needed): `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_prefixed`
- Use `rdflib` for Turtle parsing/serialization
- Use `httpx` or `requests` for HTTP calls to CSS

### Logging Format

All log output must follow the structured JSON format from the architecture doc:

```json
{
  "timestamp": "ISO-8601",
  "service": "provision",
  "level": "INFO",
  "event": "acl.grant",
  "agent": "marc-admin",
  "duration_ms": 45,
  "details": {
    "pod": "ayoub",
    "granted_agent": "new-school-admin",
    "access_level": "read"
  }
}
```

### Human-Readable ACL Output Format

The `view_acl_state()` function with `output_format="human"` should produce output like:

```json
{
  "pod": "ayoub",
  "acl_grants": [
    {
      "agent": "ayoub-student",
      "role": "owner",
      "access_modes": ["Read", "Write", "Control"],
      "resources": ["/"]
    },
    {
      "agent": "claire-teacher",
      "role": "tutor",
      "access_modes": ["Read"],
      "resources": ["/"]
    }
  ]
}
```

### Downstream Dependency: Transfer Scenario (Epic 4)

This story's `grant_acl_access()` and `revoke_acl_access()` functions are the primitives that Marc's transfer scenario (Epic 4, Story 4.1) will call. In the transfer:
1. Marc grants the new (FR) school read access to the transferring student's pod
2. Marc revokes the old (NL) school's access
3. The ACL state is viewed to confirm the transfer completed

Design the functions to be callable both from scripts and from agent code.

### Project Structure Notes

**Files to create or modify:**

- `pipeline/src/pocpod0_pipeline/provision_pods.py` -- Add `grant_acl_access()`, `revoke_acl_access()`, `view_acl_state()` functions. This file should already exist from Story 1.3 with pod provisioning and initial ACL setup functions. Extend it.
- `tests/integration/test_css_pods.py` -- Add or create integration tests for grant/revoke/view operations.
- `scripts/seed-pods.sh` -- Optionally extend with a verification step that exercises grant/revoke/view cycle after initial provisioning.

**Pod paths on disk (bind-mounted into CSS container):**

- `infra/css/pods/ayoub/`
- `infra/css/pods/claire-student-1/`
- `infra/css/pods/claire-student-2/`
- `infra/css/pods/fatima-child-1/`
- `infra/css/pods/fatima-child-2/`
- `infra/css/pods/school-community/`

Each pod directory contains `.acl` files managed by CSS WebACL.

**CSS access via Docker network:**

- CSS container name: `community-solid-server`
- CSS port: `3000`
- Base URL (from within Docker network): `http://community-solid-server:3000`
- Base URL (from host/distrobox): configurable via `CSS_BASE_URL` in `.env`
- Use `distrobox-host-exec` if running Python from within distrobox to access podman containers

### Dependencies

- **Depends on Story 1.3:** Pods must be provisioned with initial ACLs before grant/revoke/view can be tested.
- **Enables Story 4.1 (Epic 4):** Marc's transfer scenario uses grant + revoke functions from this story.
- **Enables Story 1.5:** Troll ACL enforcement tests exercise the ACL state established and modified by this story.

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` -- Story 1.4 acceptance criteria
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` -- SEC-1, SEC-2, API-1, logging format, project structure, naming conventions
- PRD: `_bmad-output/planning-artifacts/prd.md` -- FR4 (grant), FR5 (revoke), FR6 (view ACL state)
- Solid WebACL spec: https://solidproject.org/TR/wac
- CSS documentation: https://communitysolidserver.github.io/CommunitySolidServer/

## Dev Agent Record

### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
