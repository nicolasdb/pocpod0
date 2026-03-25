# Story 5.1: [foundation] Ayoub — Age-Based Sovereignty Transition

Status: ready-for-dev

## Story

As **Ayoub** (16-year-old student, Brussels),
I want the governance contract to transfer full control of my pod from shared parent/guardian governance to me alone when I reach the age threshold,
so that my data sovereignty is structurally guaranteed by the architecture, not by policy promises.

## Acceptance Criteria

**AC1: Age-based governance transition executes**
Given Ayoub's pod has shared parent/guardian governance (read access ACL for guardian WebID)
When the age-based threshold condition is met (date of birth + minimum age from governance contract)
Then the governance transition executes atomically
And Ayoub becomes the sole governor of his pod
And parent/guardian co-governance permissions are revoked via the `acl-manage` skill

**AC2: Post-transition state verifiable**
Given the sovereignty transition has executed
When Ayoub or an authorized service inspects his pod's ACL/consent state
Then the ACL shows Ayoub as sole owner with full control
And zero guardian WebIDs retain any access
And a structured JSONL event is emitted to `data/consent-events.jsonl`:
```json
{"event_type": "acl.governance.transition", "timestamp": "ISO-8601", "pod": "ayoub", "from_role": "shared_governance", "to_role": "sole_owner", "revoked_identities": ["<guardian-webid>"]}
```

**AC3: Former guardian denied modification**
Given the sovereignty transition has executed
When a former guardian WebID attempts to modify Ayoub's pod governance via the `acl-manage` skill
Then the skill refuses with a `403 Forbidden` authorization error
And the refusal is logged as a structured JSONL event to `data/consent-events.jsonl`
And Ayoub remains the sole governor — his ACL is unchanged

**AC4: Agent-callable ACL management skill (`acl-manage`)**
Given an agent with appropriate pod ownership (Ayoub for his own pod)
When the agent invokes the `acl-manage` skill with a `grant` or `revoke` action and target WebID
Then the CSS ACL on the target pod is updated accordingly
And a structured JSONL event is emitted:
```json
{"event_type": "acl.grant|acl.revoke", "timestamp": "ISO-8601", "pod": "ayoub", "identity": "<target-webid>", "action": "grant|revoke", "role": "reader|writer|owner"}
```
And the event is appended to `data/consent-events.jsonl` for mission control TUI consumption

**AC5: Ownership scope enforcement**
Given an agent without pod ownership (e.g., Claire attempting to modify Ayoub's ACL)
When the agent invokes the `acl-manage` skill with any action targeting a pod it does not own
Then the skill refuses with a structured authorization error
And the refusal message states: `"Authorization denied: agent <agent-id> does not own pod <pod-name>"`
And no ACL mutation is made on the CSS server

## Tasks / Subtasks

### Task 1: Create `acl-manage` skill — SKILL.md (AC4, AC5)
- [ ] Create `agents/skills/acl-manage/SKILL.md` with YAML frontmatter: `name`, `version`, `description`, `inputs` (action, pod_name, identity, role), `outputs` (status, event)
- [ ] Document the ownership scope enforcement rule in SKILL.md instructions: the handler checks `AGENT_POD_OWNERSHIP` env var to determine which pod(s) the invoking agent owns
- [ ] Document the four actions: `grant`, `revoke`, `view`, `transition` (transition is the special age-sovereignty path)
- [ ] Document JSONL event schema for each action in SKILL.md
- [ ] Follow OpenClaw skill format: YAML frontmatter + Markdown instructions, exactly as `agents/skills/sparql-query/SKILL.md`

### Task 2: Create `acl-manage` skill — handler.py (AC4, AC5)
- [ ] Create `agents/skills/acl-manage/handler.py` with CLI interface matching the established skill pattern (sys.argv parsing, stdout JSON output)
- [ ] Import and wrap `grant_acl_access(pod_name, agent_webid, role, access_level)` from `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Import and wrap `revoke_acl_access(pod_name, agent_webid)` from `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Import and wrap `view_acl_state()` from `pipeline/src/pocpod0_pipeline/provision_pods.py`
- [ ] Implement ownership scope check: read `AGENT_POD_OWNERSHIP` env var (comma-separated list of pod names the agent owns); reject any action on a pod not in the list
- [ ] Emit JSONL event to `data/consent-events.jsonl` on every action (grant, revoke, view, transition) — append-mode write
- [ ] Output structured JSON to stdout: `{"status": "ok|denied|error", "action": "...", "pod": "...", "identity": "...", "event_type": "..."}`
- [ ] Handle CSS auth errors: return `{"status": "error", "message": "CSS returned <code>"}` without crashing

### Task 3: Implement `governance_transition.py` — age-based transition routine (AC1, AC2)
- [ ] Create `pipeline/src/pocpod0_pipeline/governance_transition.py`
- [ ] Implement `check_transition_eligibility(pod_name: str, date_of_birth: str, min_age_years: int) -> bool`: compute age from DOB, return True if age >= min_age_years
- [ ] Implement `get_guardian_webids(pod_name: str) -> list[str]`: query the CSS ACL for the pod and return all WebIDs that are NOT the pod owner — these are guardians to be revoked
- [ ] Implement `execute_transition(pod_name: str, owner_webid: str, guardian_webids: list[str]) -> TransitionResult`: calls `revoke_acl_access` for each guardian WebID, then emits the `acl.governance.transition` JSONL event
- [ ] Use `dataclass TransitionResult(pod_name, owner_webid, revoked_count, success, timestamp, error_message)`
- [ ] Log each step with structured JSON to stdout using `utils.py` patterns
- [ ] Emit JSONL event to `data/consent-events.jsonl` on transition completion (AC2)
- [ ] Handle partial failure: if one revoke fails, log the failure and continue — do not abort mid-transition

### Task 4: Wire Ayoub's agent to the `acl-manage` skill (AC4)
- [ ] Add `acl-manage` skill to Ayoub's agent config in `agents/openclaw.json`: add `agents/skills/acl-manage` to `skills.load.extraDirs` for the `ayoub-student` agent entry
- [ ] Set `AGENT_POD_OWNERSHIP=ayoub` in Ayoub's agent environment block in `agents/openclaw.json` so the ownership scope check grants Ayoub rights over his own pod only
- [ ] Confirm the skill is listed in Ayoub's AGENTS.md under available tools (update `agents/ayoub-student/AGENTS.md`)
- [ ] Verify the SKILL.md `name` field matches the skill reference in the agent config

### Task 5: Emit JSONL events for mission control TUI (AC2, AC3, AC4)
- [ ] Ensure `data/consent-events.jsonl` exists (create empty file if absent — same pattern as `data/troll-run.jsonl` and `data/pipeline-run.jsonl`)
- [ ] Confirm every `acl-manage` handler action appends one JSONL line (newline-delimited, no trailing comma)
- [ ] Add `event_type` values to the event schema:
  - `acl.grant` — a WebID was granted access
  - `acl.revoke` — a WebID's access was revoked
  - `acl.view` — ACL state was queried (read-only, no mutation)
  - `acl.governance.transition` — age-based full transition executed
  - `acl.denied` — an unauthorized agent attempted an ACL mutation
- [ ] Verify JSONL lines are machine-parseable: `json.loads(line)` must succeed for every line

### Task 6: Governance transition demo script (AC1, AC2, AC3)
- [ ] Create `scripts/demo-governance-transition.sh`: a narrated shell script that runs the full Ayoub sovereignty transition demo
  1. Show current ACL state (guardian has read access)
  2. Call `governance_transition.py` with Ayoub's DOB and min_age threshold
  3. Show updated ACL state (guardian revoked, Ayoub sole owner)
  4. Attempt a guardian ACL mutation via `acl-manage` skill and confirm it is denied
  5. Display the JSONL events logged to `data/consent-events.jsonl`
- [ ] Script must activate venv before calling any Python
- [ ] Use `distrobox-host-exec` for any podman container access (CSS server)

### Task 7: Tests (AC1–AC5)
- [ ] Create `tests/test_governance_transition.py`
- [ ] Test `check_transition_eligibility`: age below threshold → False, age at threshold → True, age above → True
- [ ] Test `execute_transition`: mock `revoke_acl_access`; verify called once per guardian WebID; verify JSONL event emitted
- [ ] Test `acl-manage` handler ownership scope: agent with matching pod → allowed; agent with non-matching pod → denied with correct error message
- [ ] Test JSONL event format: every emitted event passes `json.loads`; `event_type` is in the allowed set; `timestamp` is ISO-8601
- [ ] Test partial failure in `execute_transition`: one revoke raises exception → transition logs error and continues

## Dev Notes

### Architecture Decisions Referenced

- **FR-ACL-MANAGE (Epic 5 gap):** No agent currently has a skill to write ACL changes. This story delivers the `acl-manage` skill as the foundational capability for consent lifecycle management.
- **Trust architecture:** Bidirectional accountability principle — the sovereignty transition is a structural guarantee, not a policy promise. The architecture enforces it via ACL mutation, not documentation.
- **Consent-as-RDF (4 questions):** The governance contract answers: who has access, under what conditions, until when, and who can revoke. The transition event answers "until when" with a timestamp.
- **Named graph per Pod URI:** Traceability module uses one named graph per Pod URI (NOT prov:wasDerivedFrom). The transition event does NOT write to Oxigraph — it writes to the JSONL event stream only. Oxigraph is the query layer; JSONL is the event/consent audit layer.

### Key Design Decisions

- **`acl-manage` wraps `provision_pods.py`:** The skill does NOT re-implement ACL logic. It wraps the already-tested `grant_acl_access`, `revoke_acl_access`, and `view_acl_state` functions from Story 1.4. No duplication.
- **Ownership scope via env var:** `AGENT_POD_OWNERSHIP` is set per-agent in `openclaw.json`. This is a simple, auditable approach — no dynamic permission resolution. Each agent's scope is declared statically in the config.
- **`governance_transition.py` is a pipeline module:** It runs outside the agent layer (called from `scripts/demo-governance-transition.sh` or by a pipeline job). It does NOT run inside OpenClaw. Agents invoke `acl-manage` skill for individual grant/revoke; the full transition is a pipeline-level operation.
- **JSONL append pattern:** All events append to `data/consent-events.jsonl` (same pattern as `data/troll-run.jsonl`). The mission control TUI (Epic 6) tails this file for live updates.
- **No Oxigraph writes from this story:** ACL state lives in the CSS server. The transition event is audited via JSONL only. Oxigraph is read-only from the perspective of this story.

### Project Structure Notes

Directories/files to create:
```
agents/
└── skills/
    └── acl-manage/
        ├── SKILL.md          # NEW — OpenClaw skill definition (YAML frontmatter + Markdown)
        └── handler.py        # NEW — CLI handler wrapping provision_pods.py ACL functions

pipeline/
└── src/
    └── pocpod0_pipeline/
        └── governance_transition.py  # NEW — age-based transition logic

scripts/
└── demo-governance-transition.sh     # NEW — narrated demo script

data/
└── consent-events.jsonl              # NEW (empty) — JSONL event stream for consent lifecycle

tests/
└── test_governance_transition.py     # NEW — unit tests
```

Files that must already exist (from previous stories):
```
pipeline/
└── src/
    └── pocpod0_pipeline/
        ├── provision_pods.py      # Story 1.4 — grant_acl_access, revoke_acl_access, view_acl_state
        └── utils.py               # Shared logging utilities

agents/
├── openclaw.json                  # Story 3.3 — JSON5 agent config (NOT yaml)
├── skills/
│   ├── sparql-query/SKILL.md      # Story 3.1 — reference format for new skill
│   └── qdrant-search/SKILL.md     # Story 3.2 — reference format for new skill
└── ayoub-student/
    ├── SOUL.md                    # Story 3.3
    ├── AGENTS.md                  # Story 3.3 — update to add acl-manage
    └── IDENTITY.md                # Story 3.3

data/
├── troll-run.jsonl                # Story 3.8 — reference JSONL pattern
└── pipeline-run.jsonl             # Pipeline — reference JSONL pattern
```

### Dependencies

- **Depends on Story 1.4:** `grant_acl_access`, `revoke_acl_access`, `view_acl_state` must exist in `provision_pods.py`. These are the ACL primitives this story wraps.
- **Depends on Story 3.3:** `agents/openclaw.json` must exist. Ayoub's agent entry must be present. OpenClaw runtime must be running for live skill invocations.
- **Depends on Story 1.3:** Ayoub's pod and guardian ACL must be provisioned (guardian WebID with read access on Ayoub's pod).
- **Consumed by Story 6.1 (Mission Control TUI):** `data/consent-events.jsonl` is the event stream the dashboard tails. Events must be machine-parseable JSONL.
- **Consumed by Story 5.3 (Troll ACL validation):** The `acl-manage` skill's ownership scope enforcement is the boundary the troll will probe.

### Error Handling

- **CSS auth failure (4xx/5xx):** `acl-manage` handler catches HTTP errors from `provision_pods.py` and returns `{"status": "error", "message": "..."}` to the agent. Never crash.
- **Partial transition failure:** If one guardian revoke fails in `governance_transition.py`, log the failure with the guardian WebID, continue with remaining revokes, and record `partial_success: true` in the transition result.
- **`AGENT_POD_OWNERSHIP` not set:** Treat as empty list — deny all mutations with clear error: `"Authorization denied: AGENT_POD_OWNERSHIP not configured for this agent"`.
- **JSONL write failure:** If `data/consent-events.jsonl` cannot be written (permissions, disk full), log to stderr and continue — do not abort the ACL operation itself.

### Isolation Notes

- Use `distrobox-host-exec` for podman containers
- Example: `distrobox-host-exec podman exec community-solid-server curl -s http://localhost:3000/.acl`
- `governance_transition.py` and `acl-manage/handler.py` call the CSS HTTP API via `requests` — the CSS server URL must be reachable from within the distrobox (use `CSS_CONNECT_URL` from `.env`, NOT the Docker-internal hostname)

### References

- Architecture: `_bmad-output/planning-artifacts/architecture.md`
- Epics: `_bmad-output/planning-artifacts/epics.md`
- Story 1.4: `_bmad-output/implementation-artifacts/1-4-acl-grant-revocation-audit.md` — ACL grant/revoke/view API patterns, `Authorization: WebID <webid>` header
- Story 1.5: `_bmad-output/implementation-artifacts/1-5-troll-acl-enforcement-validation.md` — CSS auth pattern, ACL matrix
- Story 3.3: `_bmad-output/implementation-artifacts/3-3-openClaw-agent-infrastructure.md` — OpenClaw JSON5 config, `skills.load.extraDirs`, env var pattern
- Story 3.8: `_bmad-output/implementation-artifacts/3-8-troll-cross-inference-validation.md` — JSONL event stream pattern (`data/troll-run.jsonl`)
- Memory: `project_epic5_wiring_gap.md` — "no agent can currently write ACLs"; acl-manage skill required

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
