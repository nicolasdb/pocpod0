# Story 4.1: Marc — School Transfer Scenario (NL→FR)

Status: ready-for-dev

## Story

As **Marc** (school administrator, Liège),
I want to execute a complete school transfer — granting my school access to the student's pod, revoking the old school's access, and querying the student's full learning profile — all via a natural language Discord message to my agent,
So that the student's data follows them seamlessly across the NL→FR community boundary with zero re-entry, and funders watching #marc-admin see the full consent lifecycle without a terminal.

**Prerequisite:** Story 4.0 complete ✓ (Discord bindings, seed-on-boot, VPS live at pod.nicolasdb.eu)

## Acceptance Criteria

**AC1: Pre-transfer scenario state**
- Given the demo needs a meaningful starting state
- When the setup script runs (`scripts/demo-transfer-setup.sh`)
- Then school-nl WebID (`$CSS_IDENTIFIER_URL/school-nl/profile/card#me`) has read access on Ayoub's pod
- And Marc's WebID (`$CSS_IDENTIFIER_URL/marc/profile/card#me`) has NO access to Ayoub's pod
- And `acl-manage --action view --pod-name ayoub` confirms this state

**AC2: Marc executes transfer via Discord**
- Given Marc's agent is running with `AGENT_POD_OWNERSHIP=ayoub` and `AGENT_ID=marc-admin` in openclaw.json
- When Nicolas sends a message to #marc-admin: "Transfer Ayoub to Liège school — grant us access, revoke the old NL school"
- Then Marc's agent invokes `acl-manage --action grant --pod-name ayoub --identity $CSS_IDENTIFIER_URL/marc/profile/card#me --role new-school --access-level read`
- And Marc's agent invokes `acl-manage --action revoke --pod-name ayoub --identity $CSS_IDENTIFIER_URL/school-nl/profile/card#me`
- And both consent events are appended to `data/consent-events.jsonl`
- And Marc's response in Discord is signed with his identity (not generic "pocpod0-bot")

**AC3: Marc queries Ayoub's full learning profile**
- Given the transfer is complete (AC2)
- When Marc's agent invokes `sparql-query --query-type transfer-profile --agent marc --role admin --params '{"student_uri": "$CSS_IDENTIFIER_URL/ayoub/profile/card#me"}'`
- Then the query returns Ayoub's complete learning history (activities, results, dates, source school per triple)
- And the response includes cross-community data from both NL and FR contexts (FR22, FR23)
- And Marc posts a human-readable summary to #marc-admin

**AC4: Old school access denied**
- Given the transfer is complete (AC2)
- When a request is made to Ayoub's pod with the school-nl WebID (`Authorization: WebID $CSS_IDENTIFIER_URL/school-nl/profile/card#me`)
- Then CSS returns HTTP 403
- And this is verified either by the troll agent or by the `demo-transfer-setup.sh` validation step

**AC5: Third party access denied**
- Given a WebID with no ACL entry on Ayoub's pod
- When a direct HTTP request is made to Ayoub's pod
- Then CSS returns HTTP 403 (or 404 per the CSS 404/403 ambiguity documented in IG-1)

**AC6: ACL audit state visible**
- Given the transfer is complete
- When `acl-manage --action view --pod-name ayoub` runs
- Then the output shows: Marc's school has read access, school-nl has no access
- And `data/consent-events.jsonl` shows the full trace: `acl.grant` + `acl.revoke` events from the transfer

**AC7: Marc's agent identity visible in Discord**
- Given Marc posts any message to #marc-admin
- Then the message is signed with Marc's identity — either via Discord display name or a consistent signature pattern in the message body (e.g., "— 🏫 Marc, Liège school")
- And heartbeat messages (if any) are also signed

## Tasks / Subtasks

- [ ] **Task 0: Understand current state** (blocker)
  - [ ] 0.1: Run `acl-manage --action view --pod-name ayoub` from VPS to confirm Ayoub's pod ACL has no marc or school-nl entry. Expected: only `ayoub` (owner), `claire` (tutor), `provisioner`. Confirm before any changes.
  - [ ] 0.2: Send "hello marc" to #marc-admin on Discord. Observe response. Note: does Marc sign his response? Does he mention acl-manage or transfer capability? This baseline sets the gap for Tasks 1-2.

- [ ] **Task 1: Marc agent finetuning — workspace files** (AC2, AC3, AC7)
  - [ ] 1.1: Update `agents/marc-admin/AGENTS.md` — add `acl-manage` skill entry with invocation examples. Add transfer scenario context: Marc knows Ayoub's pod name and school-nl WebID pattern. Full invocation templates for grant, revoke, view, and transfer-profile query.
  - [ ] 1.2: Update `agents/marc-admin/SOUL.md` — add transfer scenario details: "You are handling a mid-semester NL→FR transfer for Ayoub. The old NL school WebID is `$CSS_IDENTIFIER_URL/school-nl/profile/card#me`. Your school's (new/FR) WebID is `$CSS_IDENTIFIER_URL/marc/profile/card#me`. When asked to execute a transfer, you must: 1) grant your WebID access, 2) revoke old school access, 3) query and summarize the student's profile." Add identity signature to all Discord posts: end messages with "— 🏫 Marc, Liège school" or equivalent.
  - [ ] 1.3: Populate `agents/marc-admin/USER.md` — "You are talking to Nicolas, the project lead. He may be demoing to funders observing in the #marc-admin channel. Keep responses clear and non-technical: explain what you did and what it means for the student's data continuity. Funders are education policy stakeholders, not developers."
  - [ ] 1.4: Populate `agents/marc-admin/TOOLS.md` — list both skills (sparql-query, acl-manage) with the exact exec invocations Marc should use for the transfer scenario. Include the `--agent marc` vs `--webid` distinction. Reminder: `python3` not `python`.
  - [ ] 1.5: Populate `agents/marc-admin/HEARTBEAT.md` — "Check transfer status: run `acl-manage --action view --pod-name ayoub` and summarize who currently has access to Ayoub's pod. Post to #marc-admin: 'Status check — Ayoub's pod: [X] entities have read access. Transfer state: [pending/complete].'" Heartbeat interval: 60m (passive, low-noise).

- [ ] **Task 2: openclaw.json — Marc ownership scope** (AC2)
  - [ ] 2.1: Add `env` block to marc-admin agent entry in `agents/openclaw.json`:
    ```json
    "env": {
      "AGENT_POD_OWNERSHIP": "ayoub",
      "AGENT_ID": "marc-admin"
    }
    ```
    **Note on PoC compromise:** AGENT_POD_OWNERSHIP=ayoub means Marc can mutate Ayoub's ACL. This is a PoC simplification — in production, Ayoub would issue explicit consent before any school can modify his pod ACL. Document this in a code comment in openclaw.json.
  - [ ] 2.2: Apply openclaw.json to VPS using the seed-on-first-boot patch command:
    ```bash
    ssh hetzner "cp /home/nicolas/pocpod0/agents/openclaw.json /var/lib/docker/volumes/pocpod0_openclaw-data-default/_data/openclaw.json && docker restart openclaw-gateway"
    ```
    Wait 15s for restart. Verify: `docker compose logs openclaw-gateway | tail -20` — look for "Discord connected" and no errors.

- [ ] **Task 3: Sync workspace files to VPS** (AC2, AC3, AC7)
  - [ ] 3.1: Run `make sync-workspaces` from local. This rebuilds the openclaw image and recreates the openclaw-gateway container WITHOUT wiping volumes. CSS/Qdrant/Oxigraph data is preserved.
    - **Before running:** Verify `make sync-workspaces` does NOT call `down -v`. Check the Makefile target. If it wipes volumes, use the manual approach instead:
      ```bash
      make vps-push && make vps-build
      ssh hetzner "cd /home/nicolas/pocpod0 && docker compose up -d --force-recreate --no-deps openclaw-gateway"
      ```
  - [ ] 3.2: After sync, verify workspace files landed. From VPS:
    ```bash
    docker exec openclaw-gateway ls /home/node/.openclaw/workspaces/marc-admin/
    docker exec openclaw-gateway cat /home/node/.openclaw/workspaces/marc-admin/AGENTS.md
    ```
    **Note:** Seed-on-boot only seeds workspaces that don't exist yet. If marc-admin workspace already exists on the volume, new files won't appear. In that case, manually copy:
    ```bash
    ssh hetzner "docker exec openclaw-gateway cp /app/agents-seed/marc-admin/AGENTS.md /home/node/.openclaw/workspaces/marc-admin/AGENTS.md"
    ```
    Repeat for SOUL.md, USER.md, TOOLS.md, HEARTBEAT.md.

- [ ] **Task 4: Scenario setup** (AC1, AC4, AC5)
  - [ ] 4.1: Create `scripts/demo-transfer-setup.sh` — shell script that:
    1. Grants school-nl read access to Ayoub's pod via acl-manage (or direct CSS HTTP if running outside container)
    2. Prints the pre-transfer ACL state via `acl-manage --action view --pod-name ayoub`
    3. Optionally verifies school-nl has 200 access and marc has 403 (pre-transfer)
    The script is the "before" state for the demo. Run it to reset the demo for another funder visit.
    ```bash
    #!/usr/bin/env bash
    set -e
    echo "=== Demo Transfer Setup ==="
    echo "Step 1: Grant school-nl read access to Ayoub's pod (simulates pre-transfer NL school)"
    docker exec openclaw-gateway python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
      --action grant \
      --pod-name ayoub \
      --identity "${CSS_IDENTIFIER_URL:-http://localhost:3000}/school-nl/profile/card#me" \
      --role school-nl \
      --access-level read
    echo ""
    echo "Step 2: Verify pre-transfer state"
    docker exec openclaw-gateway python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py \
      --action view \
      --pod-name ayoub
    echo ""
    echo "=== Setup complete. Demo state: school-nl has read access, marc has no access ==="
    ```
    **Ownership scope issue:** `demo-transfer-setup.sh` uses provisioner-level access (runs outside OpenClaw). The acl-manage handler checks `AGENT_POD_OWNERSHIP` only if invoked via OpenClaw. Running from shell with `docker exec` bypasses the ownership check. Alternatively, if AGENT_POD_OWNERSHIP includes "ayoub" for a setup agent, this also works. For the setup script, use `docker exec` with the provisioner WebID approach from `provision_pods.py` directly.
    **Alternative approach** (simpler): Call `grant_acl_access()` from `provision_pods.py` directly via a Python wrapper in the setup script, bypassing the AGENT_POD_OWNERSHIP check (which is only enforced in acl-manage handler, not in provision_pods.py primitives).
  - [ ] 4.2: Test the setup script on VPS. Verify:
    - Pre-transfer: `acl-manage view` shows school-nl with read access, marc with no access
    - Setup script is idempotent (running twice is safe)
  - [ ] 4.3: Document in `infra/vps/README.md` under "Demo reset": `bash scripts/demo-transfer-setup.sh` as the demo prep command.

- [ ] **Task 5: End-to-end transfer test via Discord** (AC2, AC3)
  - [ ] 5.1: In #marc-admin Discord channel, send: "Transfer Ayoub to Liège school — grant us access, revoke the old NL school"
  - [ ] 5.2: Observe Marc's response. Verify:
    - Marc calls acl-manage (grant + revoke), not just describing what he'd do
    - Marc signs the response with his identity (not generic "pocpod0-bot")
    - No error messages about AGENT_POD_OWNERSHIP (Task 2 must be done first)
  - [ ] 5.3: After transfer, verify via `acl-manage --action view --pod-name ayoub`:
    - Marc's WebID present with read access
    - school-nl WebID absent
    - `data/consent-events.jsonl` has 2 new events: `acl.grant` + `acl.revoke`
  - [ ] 5.4: In #marc-admin, send: "Can you show me Ayoub's learning profile?" — observe Marc invoke `transfer-profile` query and return a human-readable summary.
  - [ ] 5.5: Take a screenshot or note the Discord exchange for the story record.

- [ ] **Task 6: Old school 403 validation** (AC4)
  - [ ] 6.1: From VPS, test school-nl access after transfer:
    ```bash
    curl -I -H "Authorization: WebID ${CSS_IDENTIFIER_URL:-http://localhost:3000}/school-nl/profile/card#me" \
      "${CSS_CONNECT_URL:-http://localhost:3000}/ayoub/"
    ```
    Expected: 401 or 404 (CSS returns 404 for both "no resource" and "unauthorized" per IG-1 — either is acceptable per architecture decision).
  - [ ] 6.2: Document result in story completion notes.

- [ ] **Task 7: Deploy updates to VPS (if not done in Tasks 2-3)** (VPS)
  - [ ] 7.1: Run `make vps-push` to sync workspace file changes.
  - [ ] 7.2: Run `make vps-build && make vps-deploy` OR `--force-recreate openclaw-gateway` to pick up new agent workspace seed.
  - [ ] 7.3: Verify stack healthy: `make vps-ps` — all services up, no restarts.

## Dev Notes

### Architecture Patterns — MUST FOLLOW

**VPS is primary development target (Story 4.0.2 complete):**
- All testing happens on VPS (`ssh hetzner`). Local dev is a fallback only.
- VPS path: `/home/nicolas/pocpod0` (running as root, Docker Compose v2, rootful Docker)
- Services: `make vps-ssh` or `ssh hetzner && cd /home/nicolas/pocpod0`

**Workspace file update path (seed-on-boot model):**
- `make sync-workspaces` = safe update (volumes intact, only openclaw-gateway recreated)
- **NEVER** `docker compose down -v` to push workspace changes — this wipes CSS pods, Qdrant, Oxigraph (1h pipeline re-run to recover)
- If workspace already exists on volume, seed-on-boot skips it → must copy manually via `docker exec cp`

**openclaw.json changes on VPS:**
```bash
ssh hetzner "cp /home/nicolas/pocpod0/agents/openclaw.json /var/lib/docker/volumes/pocpod0_openclaw-data-default/_data/openclaw.json && docker restart openclaw-gateway"
```
This is required because openclaw.json is seeded on first boot only (changed in Story 4.0.2 debug session). The bind-mount is `:rw${VOLUME_FLAGS:-}` — always include the flag suffix.

**acl-manage ownership scope enforcement:**
- Handler reads `AGENT_POD_OWNERSHIP` env var from the agent's env block in openclaw.json
- Marc needs `"AGENT_POD_OWNERSHIP": "ayoub"` to execute grant/revoke on Ayoub's pod
- PoC compromise: in production, Ayoub would consent first. Document this clearly in openclaw.json comment.
- `view` action is always permitted regardless of ownership scope.

**CSS ACL reality for Ayoub's pod (checked 2026-04-16):**
```
# Ayoub .acl — CURRENT STATE (from infra/css/pods/ayoub/.acl)
acl:agent <$CSS_IDENTIFIER_URL/ayoub/profile/card#me>  → Control (owner)
acl:agent <$CSS_IDENTIFIER_URL/claire/profile/card#me> → Read (tutor)
acl:agent <$CSS_IDENTIFIER_URL/provisioner/profile/card#me> → Control (SEC-1 PoC)
# Marc has NO access. school-nl has NO access. (pre-story state)
```
The SOUL.md comment "Marc: no direct individual pod access — school-community only (review fix P4)" confirms this story must fix it.

**sparql-query ACL validation sequence:**
The handler validates Marc's WebID against Ayoub's CSS pod ACL BEFORE executing the SPARQL query against Oxigraph. This means:
1. Story setup must grant Marc's WebID on Ayoub's pod (AC2) BEFORE the transfer-profile query (AC3) can succeed.
2. Correct order: grant → query → verify → revoke-old-school (or grant + revoke atomically, then query).

**WebID construction:**
- Always use `$CSS_IDENTIFIER_URL` namespace, not Docker TCP hostname
- Local: `http://localhost:3000/marc/profile/card#me`
- VPS: `https://mypods.example.com/marc/profile/card#me` (whatever CSS_IDENTIFIER_URL is set to)
- The `--agent marc` flag in sparql-query constructs this automatically from env var
- For acl-manage `--identity`: must be constructed manually or via shell expansion: `--identity "${CSS_IDENTIFIER_URL}/marc/profile/card#me"`

**transfer-profile.rq template:**
Queries Oxigraph for all activities involving a student URI across all named graphs. Uses `oslo-educ:betreft`, `oslo-educ:resultaat`, `oslo-educ:datum`, `dct:source`, `prov:wasGeneratedBy`. The template exists at `agents/skills/sparql-query/templates/transfer-profile.rq`.

**Agent signature gap (from Story 4.0.2 retro):**
All agents currently post as "pocpod0-bot" in Discord. Fix: add a signature line to SOUL.md: "End every message with: — 🏫 Marc, Liège school". This is the simplest approach; no code change needed.

**Discord channel ID:**
Marc's channel ID is hardcoded in `agents/openclaw.json` (numeric snowflake, not env var). When targeting heartbeat changes for Marc, reference the hardcoded value.

**HEARTBEAT.md for Marc:**
Marc currently has an empty/placeholder HEARTBEAT.md. Adding a real one (ACL state check) gives funders a live "transfer status" view without having to ask Marc directly.

**Python binary on VPS:**
`python3` — NOT `python`. The `python` symlink does not exist in the openclaw-gateway container. All SKILL.md and TOOLS.md invocations must use `python3`.

**VOLUME_FLAGS bind-mount pattern:**
Always use `:rw${VOLUME_FLAGS:-}` or `:ro${VOLUME_FLAGS:-}`. On SELinux (local dev), VOLUME_FLAGS=`,Z`. On VPS (rootful Docker), VOLUME_FLAGS is empty. Never omit the variable or `,Z` appends to destination path.

### Invalidated Assumptions

- **Assumption:** `Marc (admin) has read access on individual student pods` → **Reality:** Marc currently has NO access to Ayoub's pod (only school-community pod). The `.acl` comment says "review fix P4" — this story IS that fix. Pre-transfer state: no marc entry in Ayoub's ACL. Must be granted as part of the transfer scenario.
- **Assumption:** `AGENT_POD_OWNERSHIP already set for marc-admin` → **Reality:** No `env` block exists for marc-admin in openclaw.json. Must be added in Task 2 before acl-manage mutations can work.
- **Assumption:** `school-nl pod exists in CSS` → **Reality:** No school-nl pod is provisioned. The NL school is represented only as a WebID string in ACLs. CSS validates ACL via WebID string matching — the pod does not need to exist.
- **Assumption:** `marc-admin AGENTS.md lists acl-manage` → **Reality:** Marc's AGENTS.md only mentions `sparql-query` and `qdrant-search`. Must add `acl-manage` explicitly.
- **Assumption:** `Env var interpolation works for channel/guild IDs in openclaw.json` → **Reality:** OpenClaw resolves `${VAR}` for values only, NOT for JSON object keys. Guild IDs and channel IDs used as keys are hardcoded numerics. (Source: Story 4.0 review notes.)
- **Assumption:** `make sync-workspaces safely updates existing workspaces` → **Reality:** Seed-on-boot only runs when workspace dir is ABSENT. If marc-admin workspace already exists on the named volume, updated files must be manually copied via `docker exec cp`. Verify after `make sync-workspaces`.

### Project Structure Notes

- `agents/marc-admin/AGENTS.md` — update with acl-manage skill entry
- `agents/marc-admin/SOUL.md` — update with transfer scenario details + signature
- `agents/marc-admin/USER.md` — populate (currently 1 empty line)
- `agents/marc-admin/TOOLS.md` — populate (currently 1 empty line)
- `agents/marc-admin/HEARTBEAT.md` — write real ACL-check behavior (currently placeholder)
- `agents/openclaw.json` — add env block to marc-admin agent entry
- `agents/skills/acl-manage/handler.py` — no changes needed (existing implementation covers this story)
- `agents/skills/sparql-query/templates/transfer-profile.rq` — no changes needed
- `scripts/demo-transfer-setup.sh` — new file (scenario reset script)
- `infra/vps/README.md` — add "Demo reset" entry for transfer scenario

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.1 — Full AC spec and Discord interaction note]
- [Source: infra/css/pods/ayoub/.acl — Ayoub's current ACL state (no marc, no school-nl)]
- [Source: agents/skills/acl-manage/SKILL.md — Full invocation reference, ownership scope, JSONL events]
- [Source: agents/skills/sparql-query/SKILL.md — transfer-profile template, --agent flag, ACL validation sequence]
- [Source: agents/marc-admin/SOUL.md — Current persona, "review fix P4" note confirmed]
- [Source: agents/openclaw.json — marc-admin agent entry (no env block)]
- [Source: memory/story_4_0_2_vps_patterns.md — openclaw.json update path, finetuning gaps]
- [Source: memory/story_4_0_workspace_mgmt_patterns.md — sync-workspaces vs factory reset, manual copy fallback]
- [Source: memory/story_4_0_openclaw_discord_patterns.md — Discord config, hardcoded keys, AGENT_POD_OWNERSHIP pattern]
- [Source: memory/story_5_1_acl_manage_patterns.md — SKILL.md format, AGENT_POD_OWNERSHIP scope enforcement]
- [Source: memory/infra_vps_structure.md — VPS paths, volumes, openclaw.json patch command]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
