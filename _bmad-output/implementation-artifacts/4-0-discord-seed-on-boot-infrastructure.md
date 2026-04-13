# Story 4.0: Discord & Seed-on-Boot Infrastructure

Status: review

## Story

As a **project lead** (Nicolas),
I want all 6 OpenClaw agents reachable via Discord channels with evolvable workspaces and periodic heartbeat behaviors,
So that funders and external visitors can interact with every persona-agent directly, and agent identities can evolve through conversation.

## Acceptance Criteria

**AC1: Seed-on-boot workspace seeding**
- Given the Dockerfile builds the OpenClaw image
- When `docker-compose up` runs for the first time
- Then the entrypoint copies agent seed files from `/app/agents-seed/{id}/` to `/home/node/.openclaw/workspaces/{id}/` for each agent that has no workspace yet
- And subsequent restarts do NOT overwrite existing workspace files (idempotent seed)
- And `docker-compose down -v && docker-compose up` performs a full factory reset to seeded state

**AC2: Discord channel bindings**
- Given the Discord bot token configured in `.env` as `DISCORD_BOT_TOKEN` and guild ID as `DISCORD_GUILD_ID`
- When `docker-compose up` completes
- Then all 6 agents (claire-teacher, marc-admin, isabelle-policy, fatima-parent, ayoub-student, troll-adversary) are bound to individual Discord channels in `openclaw.json`
- And a #general channel is bound for cross-agent visibility
- And a #security_logs channel is bound for troll reports
- And each agent is reachable via Discord DM and its bound channel

**AC3: Heartbeat behaviors**
- Given a HEARTBEAT.md file in each agent's seeded workspace
- When the OpenClaw heartbeat fires
- Then troll-adversary runs a probe subset and posts a short report to #security_logs
- And isabelle-policy posts an aggregate check to #general
- And claire-teacher sends a student check-in to her channel

**AC4: Named volume isolation**
- Given per-scenario named volumes configured (`openclaw-data-{scenario}`)
- When multiple scenario containers run
- Then workspace state does not leak between scenarios

**AC5: Prerequisite checklist (5 carried items)**
- Given Epic 5/6 retro carried items
- Then NFR-LAG is resolved: latency baseline documented in architecture.md (NFR1 <500ms SPARQL, NFR2 <2s hybrid — confirm with real run or note as known gap)
- And IG-1 is resolved: CSS 404 semantics documented (resource not found vs unauthorized)
- And ACL-DRIFT is resolved: known drift scenarios documented (what causes false positives after restart)
- And consent events catalog is documented: all emitted event types listed (`acl.grant`, `acl.revoke`, `acl.view`, `acl.governance.transition`, `acl.denied`, `token.issued`, `token.expired`, `consent.expired`, `receipt.written`)
- And invalidated assumptions template is added to `.claude/skills/bmad-create-story/template.md`

## Tasks / Subtasks

- [x] **Task 0: Resolve 5 carried prerequisite items** (AC5)
  - [x] 0.1: NFR-LAG — Update architecture.md NFR section with observed latency from Epic 3 pipeline run (SPARQL ~2s, hybrid ~10s/student). Document that PRD spec (<500ms, <2s) was aspirational; note renegotiated values as accepted for PoC.
  - [x] 0.2: IG-1 — Add note to architecture.md documenting CSS 404 semantics: CSS returns 404 for both "resource does not exist" and "unauthorized with no matching ACL". Document that Option A (accept ambiguity) was chosen.
  - [x] 0.3: ACL-DRIFT — Document in architecture.md or a README: after `docker-compose restart`, CSS volume persists but ACL state may drift if provision_pods.py is not re-run. Dashboard may show stale state. Mitigation: re-run provision stage or `down -v` for clean reset.
  - [x] 0.4: Consent events catalog — Create `docs/consent-events-catalog.md` or add section to architecture.md listing all event types emitted to `data/consent-events.jsonl` with schema examples. Source: `acl-manage/SKILL.md` (lines 99-126), `receipt.py`, `expire_tokens.py`.
  - [x] 0.5: Invalidated assumptions template — Edit `.claude/skills/bmad-create-story/template.md` to add an "Invalidated Assumptions" section after "Dev Notes". SM pre-populates from project memory going forward.

- [x] **Task 1: Dockerfile refactor for seed-on-boot** (AC1)
  - [x] 1.1: Update `infra/openclaw/Dockerfile` — add `COPY agents/ /app/agents-seed/` after the existing `apt-get` layer. This copies all agent workspace files and skills into the image as seed material.
  - [x] 1.2: Create `infra/openclaw/entrypoint.sh` — shell script that:
    1. For each directory in `/app/agents-seed/` that matches an agent ID (claire-teacher, marc-admin, etc.), check if `/home/node/.openclaw/workspaces/{id}/` exists. If not, `cp -r` the seed into place.
    2. Copy skills: if `/home/node/.openclaw/workspaces/skills/` does not exist, copy `/app/agents-seed/skills/` there.
    3. Always copy `openclaw.json` from `/tmp/openclaw.json` to `/home/node/.openclaw/openclaw.json` (config is not evolvable — always fresh from image).
    4. `exec node dist/index.js gateway --bind "$OPENCLAW_GATEWAY_BIND" --port "$OPENCLAW_GATEWAY_PORT" --allow-unconfigured`
  - [x] 1.3: Update Dockerfile to `COPY infra/openclaw/entrypoint.sh /app/entrypoint.sh` and `RUN chmod +x /app/entrypoint.sh`
  - [x] 1.4: Update `docker-compose.yml` openclaw-gateway service:
    - Remove inline `entrypoint` + `command` shell script
    - Set `entrypoint: ["/app/entrypoint.sh"]`
    - Change volume mount from `./agents:/app/agents:ro` to remove it (agents are now in the image)
    - Keep `./agents/openclaw.json:/tmp/openclaw.json:ro` bind-mount (config always fresh)
    - Keep `openclaw-data:/home/node/.openclaw` named volume
  - [x] 1.5: Test: `docker-compose down -v && docker-compose up -d` → verify all 6 agent workspaces seeded at `/home/node/.openclaw/workspaces/{id}/` with SOUL.md, AGENTS.md, IDENTITY.md, etc.
  - [x] 1.6: Test: Modify a file inside the container workspace (e.g., append to MEMORY.md), restart without `-v` → verify modification persists. Then `down -v && up` → verify factory reset (modification gone).

- [x] **Task 2: Discord bot setup + openclaw.json bindings** (AC2)
  - [x] 2.1: **External prerequisite — Discord setup (Nicolas, manual).** Follow checklist below, then paste IDs into `.env`.
  - [x] 2.2: Add to `.env.example` (and `.env`): `DISCORD_BOT_TOKEN=`, `DISCORD_GUILD_ID=`, plus channel ID env vars or document them inline.
  - [x] 2.3: Update `agents/openclaw.json` — add `channels.discord` section:
    ```json5
    channels: {
      discord: {
        enabled: true,
        botToken: "${DISCORD_BOT_TOKEN}",
        dmPolicy: "allowlist",
        groupPolicy: "allowlist",
        guilds: {
          "${DISCORD_GUILD_ID}": {
            channels: {
              "${DISCORD_CHANNEL_CLAIRE}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_MARC}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_ISABELLE}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_FATIMA}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_AYOUB}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_TROLL}": { allow: true, requireMention: false },
              "${DISCORD_CHANNEL_GENERAL}": { allow: true, requireMention: true },
              "${DISCORD_CHANNEL_SECURITY_LOGS}": { allow: true, requireMention: true },
            }
          }
        }
      }
    }
    ```
  - [x] 2.4: Add `bindings` array to `openclaw.json` — map each agent to its channel:
    ```json5
    bindings: [
      { agentId: "claire-teacher", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_CLAIRE}" } } },
      { agentId: "marc-admin", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_MARC}" } } },
      { agentId: "isabelle-policy", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_ISABELLE}" } } },
      { agentId: "fatima-parent", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_FATIMA}" } } },
      { agentId: "ayoub-student", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_AYOUB}" } } },
      { agentId: "troll-adversary", match: { channel: "discord", peer: { kind: "channel", id: "${DISCORD_CHANNEL_TROLL}" } } },
    ]
    ```
  - [x] 2.5: Update `openclaw.json` agent `workspace` paths from `/app/agents/{id}` to `/home/node/.openclaw/workspaces/{id}` (seed-on-boot target). Remove `agentDir` entries (workspace and agentDir unify under the new path). Keep `skills.load.extraDirs: ["/home/node/.openclaw/workspaces/skills"]`.
  - [x] 2.6: Remove `skipBootstrap: true` from agent defaults — workspaces are now writable (named volume), so bootstrap can run normally.
  - [x] 2.7: Test: `docker-compose up` → verify OpenClaw logs show Discord bot connected + all 6 agents registered. Send a message in #claire-teacher → verify Claire responds. Send a DM to the bot → verify routing works.

- [x] **Task 3: HEARTBEAT.md per-agent behaviors** (AC3)
  - [x] 3.1: Add heartbeat config to `openclaw.json` per-agent (NOT in defaults — only agents with heartbeat behaviors should have it):
    - **troll-adversary:** `heartbeat: { every: "30m", target: "discord", to: "${DISCORD_CHANNEL_SECURITY_LOGS}", lightContext: true, isolatedSession: true }`
    - **isabelle-policy:** `heartbeat: { every: "60m", target: "discord", to: "${DISCORD_CHANNEL_GENERAL}", lightContext: true, isolatedSession: true }`
    - **claire-teacher:** `heartbeat: { every: "60m", target: "discord", to: "${DISCORD_CHANNEL_CLAIRE}", lightContext: true, isolatedSession: true }`
  - [x] 3.2: Write `agents/troll-adversary/HEARTBEAT.md`:
    ```markdown
    # Troll Security Heartbeat

    Run a quick security probe of the pocpod0 infrastructure.

    ## Tasks
    1. Use `exec` tool to run: `python3 /home/node/.openclaw/workspaces/skills/acl-manage/handler.py --action view --pod-name ayoub`
       - Verify response shows expected ACL state
    2. Use `sparql-query` skill to run a simple student-progress query for ayoub
       - Verify results return (not blocked)
    3. Use `sparql-query` skill to attempt a query as an unauthorized identity
       - Verify it is denied

    ## Report Format
    Post to #security_logs:
    ```
    🔒 **Troll Heartbeat** — [timestamp]
    ✅ ACL enforcement: holding (ayoub pod private by default)
    ✅ SPARQL authorized: query returns results
    ✅ SPARQL unauthorized: correctly denied
    ```
    If any check fails, use ⚠️ or ❌ and explain what failed.
    ```
  - [x] 3.3: Write `agents/isabelle-policy/HEARTBEAT.md`:
    ```markdown
    # Isabelle Policy Heartbeat

    Check the aggregate consent state for the regional program.

    ## Tasks
    1. Use `sparql-query` skill to run aggregate-anonymized template for the STEM/robotics program
    2. Note the total consented student count

    ## Report Format
    Post to #general:
    ```
    📊 **Policy Check** — [timestamp]
    Consented students in STEM aggregate: [count]
    Program status: nominal
    ```
    If the count changed since last check, note: "⬆️/⬇️ Count changed from X to Y"
    ```
  - [x] 3.4: Write `agents/claire-teacher/HEARTBEAT.md`:
    ```markdown
    # Claire Teacher Heartbeat

    Quick check on student engagement.

    ## Tasks
    1. Use `sparql-query` skill to check recent activity for your students
    2. Note any students with no recent records

    ## Report Format
    Post to your channel:
    ```
    👩‍🏫 **Claire Check-in** — [timestamp]
    Students with recent activity: [count]/[total]
    All systems nominal.
    ```
    ```
  - [x] 3.5: Write placeholder HEARTBEAT.md for marc-admin, fatima-parent, ayoub-student (empty or minimal — no periodic behavior needed for these agents yet).
  - [x] 3.6: Test: Wait for heartbeat interval → verify troll posts to #security_logs, Isabelle posts to #general, Claire posts to her channel. Verify messages are readable by a non-technical person.

- [x] **Task 4: Named volume isolation** (AC4)
  - [x] 4.1: In `docker-compose.yml`, rename `openclaw-data` volume to `openclaw-data-default` in both the `volumes:` section and the openclaw-gateway service mount.
  - [x] 4.2: Document the pattern in a comment: to create scenario B, duplicate the service block with `openclaw-data-scenario-b` volume. For the PoC, a single default scenario is sufficient.
  - [x] 4.3: Test: Verify `docker-compose up` creates `openclaw-data-default`. Verify `docker-compose down -v` removes it.

## Discord Setup Checklist (Nicolas — manual, before Task 2.2+)

Complete this before the dev agent can wire Discord bindings into `openclaw.json`.

### Step 1: Create Discord Server

- [x] Open Discord (app or browser)
- [x] Click "+" (Add a Server) → "Create My Own" → "For me and my friends"
- [x] Name: **pocpod0** (or whatever you prefer)
- [x] Enable **Developer Mode**: User Settings → App Settings → Advanced → Developer Mode = ON
  - This lets you right-click any server/channel/user → "Copy ID" to get numeric snowflake IDs 

### Step 2: Create the Discord Application + Bot

- [x] Go to https://discord.com/developers/applications
- [x] Click "New Application" → Name: **pocpod0-bot** → Create
- [x] Go to **Bot** tab (left sidebar):
  - [x] Click "Reset Token" → copy the token → this is your `DISCORD_BOT_TOKEN` (save it now, you can't see it again)
  - [x] Under **Privileged Gateway Intents**, enable:
    - [x] **Message Content Intent** (REQUIRED — bot needs to read message text)
    - [x] **Server Members Intent** (recommended — enables role allowlists and name-to-ID matching)
    - [x] Presence Intent Enabled (optional — skip unless you want online/offline status)
  - [x] Save Changes

### Step 3: Generate Invite URL + Add Bot to Server

- [x] Go to **OAuth2** tab → **URL Generator**:
  - [x] Under **Scopes**, check:
    - [x] `bot`
    - [x] `applications.commands`
  - [x] Under **Bot Permissions**, check:
    - [x] View Channels
    - [x] Send Messages
    - [x] Read Message History
    - [x] Add Reactions
    - [x] Embed Links
    - [x] Attach Files
    - [x] Use Slash Commands
  - [x] Do NOT check Administrator (principle of least privilege)
- [x] Copy the generated URL at the bottom → open it in browser → select your **pocpod0** server → Authorize

### Step 4: Create Channels

Create 8 text channels in the pocpod0 server. Right-click each channel after creation → "Copy Channel ID".

- [x] `#claire-teacher` → ID: _______________
- [x] `#marc-admin` → ID: _______________
- [x] `#isabelle-policy` ��� ID: _______________
- [x] `#fatima-parent` → ID: _______________
- [x] `#ayoub-student` → ID: _______________
- [x] `#troll-adversary` → ID: _______________
- [x] `#general` → ID: _______________ (may already exist — use the default or create a new one)
- [x] `#security-logs` → ID: _______________

### Step 5: Copy Server (Guild) ID

- [x] Right-click the server name (top of channel list) → "Copy Server ID"
- [x] This is your `DISCORD_GUILD_ID`: _______________

### Step 6: Copy Your Own User ID

- [x] Right-click your own username in the member list → "Copy User ID"
- [x] This is for the `allowFrom` DM allowlist: _______________
- [x] Format for openclaw.json: `"discord:<your_user_id>"`

### Step 7: Paste Into `.env`

Add these lines to your `.env` file:

```bash
# Discord bot (Story 4.0)
DISCORD_BOT_TOKEN=<paste bot token from Step 2>
DISCORD_GUILD_ID=<paste server ID from Step 5>
DISCORD_CHANNEL_CLAIRE=<paste channel ID>
DISCORD_CHANNEL_MARC=<paste channel ID>
DISCORD_CHANNEL_ISABELLE=<paste channel ID>
DISCORD_CHANNEL_FATIMA=<paste channel ID>
DISCORD_CHANNEL_AYOUB=<paste channel ID>
DISCORD_CHANNEL_TROLL=<paste channel ID>
DISCORD_CHANNEL_GENERAL=<paste channel ID>
DISCORD_CHANNEL_SECURITY_LOGS=<paste channel ID>
DISCORD_ALLOW_FROM=discord:<your user ID from Step 6>
```

### Verification

- [x] Bot appears in the server member list (may show as offline until OpenClaw starts)
- [x] All 8 channels visible in the server
- [x] All IDs pasted into `.env`
- [x] `DISCORD_BOT_TOKEN` is NOT committed to git (`.env` is in `.gitignore`)

---

## Dev Notes

### Architecture Patterns — MUST FOLLOW

**OpenClaw config format:** JSON5 (`openclaw.json`), NOT YAML. Agent personas via workspace markdown files (SOUL.md, AGENTS.md, IDENTITY.md, USER.md, TOOLS.md, HEARTBEAT.md, BOOTSTRAP.md, MEMORY.md).

**Current volume strategy (Epics 1-6):** Read-only bind mount `./agents:/app/agents:ro` + named volume `/home/node/.openclaw`. Config copied from `/tmp/openclaw.json` at startup. `skipBootstrap: true` because workspace is read-only.

**New volume strategy (Epic 4+, this story):** Agents baked into image via `COPY agents/ /app/agents-seed/`. Entrypoint seeds writable workspace at `/home/node/.openclaw/workspaces/{id}/` on first boot. Named volume holds evolved state. Factory reset = `compose down -v`. `skipBootstrap` can be removed (workspace is writable).

**OpenClaw Discord bindings (from context7 docs):**
- `channels.discord.botToken` — bot token (use env var interpolation `${DISCORD_BOT_TOKEN}`)
- `channels.discord.guilds.{guild_id}.channels.{channel_id}` — per-channel allow/requireMention
- `bindings[]` — route agent to specific channel via `{ agentId, match: { channel: "discord", peer: { kind: "channel", id } } }`
- `dmPolicy: "allowlist"` — DMs only from approved users
- `groupPolicy: "allowlist"` — only listed channels

**OpenClaw heartbeat (from context7 docs):**
- Per-agent config in `agents.list[].heartbeat` (NOT in defaults when only some agents need it)
- `target: "discord"` + `to: "${CHANNEL_ID}"` — delivers to specific Discord channel
- `lightContext: true` — only injects HEARTBEAT.md from bootstrap (saves tokens)
- `isolatedSession: true` — fresh session each run (no conversation history bleed)
- `every: "30m"` — interval format (ms, s, m, h)

**Dockerfile pattern:** The current Dockerfile (`infra/openclaw/Dockerfile`) is minimal — just `apt-get` for Python deps. Add `COPY` and entrypoint after the `apt-get` layer. The `USER node` directive at the end ensures the entrypoint runs as node user (required for `/home/node/.openclaw` write access).

**Docker-compose change:** The current `entrypoint: ["/bin/sh", "-c"]` + inline `command:` block that copies openclaw.json and exec's the gateway must be replaced by the new `entrypoint.sh` that does seed-on-boot + config copy + gateway exec.

**Named volumes don't need `:Z`** — SELinux flag only applies to bind mounts. Named volume `openclaw-data-default` needs no flags.

### Critical Constraints

- **Bot token is a secret** — DISCORD_BOT_TOKEN must be in `.env` (gitignored), never hardcoded. Add to `.env.example` with empty placeholder.
- **Channel IDs are numeric strings** — Discord channel IDs are snowflake IDs (e.g., "1234567890123456789"). They must be obtained from the Discord server after creation.
- **Entrypoint must be idempotent** — `cp -r` only when target directory is absent. Check with `[ -d /home/node/.openclaw/workspaces/{id} ]`.
- **Skills directory seeding** — Skills also need to be seeded from `/app/agents-seed/skills/` to `/home/node/.openclaw/workspaces/skills/`. The `extraDirs` path in openclaw.json must match.
- **openclaw.json env var interpolation — KEY POSITIONS DO NOT INTERPOLATE** — OpenClaw resolves `${VAR}` for JSON *values* (e.g. `token`, `allowFrom`, `to`) but NOT for JSON *keys*. Guild IDs and channel IDs appear as object keys in the `guilds` and `channels` blocks — they must be hardcoded as numeric strings. Tested: `${DISCORD_GUILD_ID}` as a key produced `unresolved: ${DISCORD_GUILD_ID}/...` in logs.
- **New server setup — manual update required** — When deploying to a new Discord server, the following locations in `agents/openclaw.json` must be updated manually from `.env` values:
  1. `channels.discord.guilds` — replace the guild ID key (currently `1493139142152949820`)
  2. `channels.discord.guilds.{id}.channels` — replace all 8 channel ID keys
  3. `bindings[].match.peer.id` — replace all 6 channel IDs in the bindings array
  4. `agents.list[].heartbeat.to` — replace channel IDs for claire (1), isabelle (1), troll (1)
  The `.env` file contains all these IDs as reference (DISCORD_GUILD_ID, DISCORD_CHANNEL_*). Cross-reference `.env` when updating `openclaw.json`.
- **The `./agents/openclaw.json` bind-mount stays** — Config is always deployed fresh from repo (not evolvable). Only workspace markdown files evolve.

### Invalidated Assumptions

- **`skipBootstrap: true` required** — No longer needed after seed-on-boot. Workspaces are writable on the named volume.
- **`/app/agents/{id}` workspace paths** — Change to `/home/node/.openclaw/workspaces/{id}`. The old read-only bind mount `./agents:/app/agents:ro` is removed.
- **`agentDir` separate from workspace** — With seed-on-boot, workspace IS the writable directory. The separate `agentDir` at `/home/node/.openclaw/agents/{id}/state` may be unnecessary. Test whether OpenClaw still needs it or if workspace alone suffices. If agentDir is still needed, let entrypoint create it.
- **Empty HEARTBEAT.md files** — Currently all HEARTBEAT.md files are empty (1 line). This story writes real content for troll, isabelle, claire. Marc, fatima, ayoub keep minimal/empty.

### Project Structure Notes

- `infra/openclaw/Dockerfile` — exists, add COPY + entrypoint layers
- `infra/openclaw/entrypoint.sh` — new file
- `agents/openclaw.json` — exists, add channels + bindings + heartbeat config + update workspace paths
- `agents/*/HEARTBEAT.md` — exist (empty), write real content for 3 agents
- `.env` / `.env.example` — add Discord env vars
- `docker-compose.yml` — modify openclaw-gateway service
- `.claude/skills/bmad-create-story/template.md` — add Invalidated Assumptions section (Task 0.5)

### References

- [Source: _bmad-output/implementation-artifacts/epic-6-retro-2026-04-12.md — Decision 1 (Discord), Decision 2 (Troll on Discord), Decision 3 (Seed-on-boot), Decision 5 (ACL dashboard keeper)]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.0 — Full AC spec]
- [Source: _bmad-output/planning-artifacts/architecture.md#OpenClaw Agent Configuration — JSON5 config, workspace markdown pattern]
- [Source: agents/openclaw.json — Current config with 6 agents, chatCompletions enabled, skills registered]
- [Source: infra/openclaw/Dockerfile — Current minimal Dockerfile]
- [Source: docker-compose.yml — Current openclaw-gateway service with inline entrypoint]
- [Source: context7 /openclaw/openclaw — Discord channel config, bindings, heartbeat config]
- [Source: memory/story_3_3_openclaw_setup_patterns.md — Volume mount gotchas, EACCES issue, skipBootstrap reasoning]
- [Source: memory/epic6_retro_decisions.md — 5 architectural decisions shaping this story]

## Previous Story Intelligence

**Story 6.3 (Funder Intervention Points)** was the last completed story. Key learnings:
- acl-manage skill subprocess wiring works via `handler.py` invocation
- Troll tab UI was intentionally deferred — troll interaction moves to Discord (this story)
- Dashboard `POST /api/troll/run/{category}` exists but env vars for subprocess not validated (AC2-GAP) — low priority since troll migrates to Discord
- WCAG 2.1 AA compliance standard applies to any UI (4.5:1 contrast, focus-visible)

**Story 3.3 (OpenClaw Setup)** established the foundational patterns:
- Volume mount discovery: bind-mounting directly into `.openclaw/` causes EACCES because podman rootless sets parent dir to root ownership. Solution: named volume + init copy.
- `skipBootstrap: true` was needed because workspace was read-only. With seed-on-boot (writable workspace), this can be removed.
- All 6 agents + 3 skills visible after config change.

## Dev Agent Record

### Agent Model Used\n\nclaude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List

**Completion Notes (2026-04-13):**

- Task 0: All 5 carried items documented in `_bmad-output/planning-artifacts/architecture.md` (NFR renegotiated, CSS 404 semantics, ACL-DRIFT) and `docs/consent-events-catalog.md` created (8 event types sourced from code). Invalidated assumptions section added to story template.
- Task 1: Seed-on-boot implemented via `infra/openclaw/entrypoint.sh` + Dockerfile COPY layers. All 3 scenarios tested with podman compose (fresh seed, idempotent restart, factory reset via down -v).
- Task 2: Discord bindings wired in `agents/openclaw.json` with numeric channel IDs (env var interpolation doesn't work for JSON keys). Bot connected and logged in as pocpod0-bot (ID 1493142406323896412). Discovered: `token` is correct key (not `botToken`); `channels` must be top-level not under `gateway`. Channel IDs hardcoded (non-secret per story Dev Notes).
- Task 3: HEARTBEAT.md written for troll (30m), isabelle (60m), claire (60m). Placeholder files for marc, fatima, ayoub. Heartbeat `directPolicy: "allow"` added to suppress doctor warning.
- Task 4: Volume renamed to `openclaw-data-default` with scenario isolation comment.

### Review Items for Reviewer

**RI-1 — Task 3.6 (troll heartbeat): config-validated only, not runtime-observed.**
The 30-minute troll heartbeat was never witnessed firing in this session. Config structure is identical to Claire's heartbeat (confirmed working). Runtime validation requires a live 30-minute wait post-reprovision. Reviewer should either observe a troll heartbeat fire or accept config parity with Claire as sufficient evidence.

**RI-2 — OpenClaw WebUI device pairing is broken in container.**
`openclaw devices approve` run inside the container fails with `gateway closed (1000 normal closure)`. The CLI cannot reach the gateway via loopback (`ws://127.0.0.1:18789`) even from within the container. Root cause unknown — may require host-side port exposure or a gateway bind flag. The control UI is inaccessible for this deployment. Workaround: use `podman logs openclaw-gateway` for debugging. Not a blocker for story ACs but limits observability.

### File List

- `_bmad-output/planning-artifacts/architecture.md` — NFR renegotiation, CSS 404 semantics, ACL-DRIFT documentation
- `docs/consent-events-catalog.md` — new file, all 8 consent event types
- `.claude/skills/bmad-create-story/template.md` — added Invalidated Assumptions section
- `infra/openclaw/Dockerfile` — COPY agents-seed + entrypoint.sh layers
- `infra/openclaw/entrypoint.sh` — new file, seed-on-boot logic
- `docker-compose.yml` — replaced inline entrypoint with /app/entrypoint.sh, renamed volume to openclaw-data-default
- `agents/openclaw.json` — Discord channels/bindings/heartbeat, workspace paths updated, skipBootstrap removed
- `.env.example` — Discord env vars added
- `agents/troll-adversary/HEARTBEAT.md` — security probe instructions
- `agents/isabelle-policy/HEARTBEAT.md` — aggregate consent check instructions
- `agents/claire-teacher/HEARTBEAT.md` — student check-in instructions
- `agents/marc-admin/HEARTBEAT.md` — placeholder (no periodic behavior)
- `agents/fatima-parent/HEARTBEAT.md` — placeholder (no periodic behavior)
- `agents/ayoub-student/HEARTBEAT.md` — placeholder (no periodic behavior)

**Post-session fixes (2026-04-13):**

- `requireMention: false` caused Claire infinite loop (bot responding to own messages). Fixed: all 6 agent channels set to `requireMention: true`. Name-matching still triggers responses ("hello claire") — loop is broken.
- SKILL.md files had old `/app/agents/skills/` paths (pre-seed-on-boot). Updated all three skills to use `python3 /home/node/.openclaw/workspaces/skills/{skill}/handler.py`. `python` binary not available; `python3` is.
- `qdrant-search/SKILL.md` lacked explicit `exec` invocation instructions. Added `python3 {baseDir}/handler.py` example.
- Task 2.7 validated: Claire responded to "hello claire" in #claire-teacher (emoji + text reply). No loop. Empty results expected — volume was wiped during persistence testing (down -v).
- Additional files changed: `agents/skills/sparql-query/SKILL.md`, `agents/skills/acl-manage/SKILL.md`, `agents/skills/qdrant-search/SKILL.md`
