# Story 4.0.2: Deploy pocpod0 to Hetzner VPS (unblock WebUI + Epic 4)

Status: draft

## Story

As a **project lead** (Nicolas),
I want pocpod0 running on the Hetzner VPS at `~/pocpod0` with the OpenClaw WebUI reachable over the public internet (token-gated),
So that Epic 4 development continues without being blocked by local podman-compose/pasta networking bugs, and Discord agents + WebUI pairing work reliably.

## Context

Side quest 4.0 identified a rootless podman-compose+pasta bug as root cause of local WebUI unreachability (see deferred-work.md, 2026-04-14). Story 4.0.1 is a timeboxed last attempt at a local fix. This story is the strategic fallback: move to VPS, where rootful podman + real networking sidesteps the class of problems entirely. This also aligns with the pilot-bridge memory (POC → Alpha → Beta → Pilot).

Access: `ssh hetzner` (alias already configured). Target path: `/home/nicolas/pocpod0`.

## Acceptance Criteria

**AC1: VPS environment provisioned**
- Given a fresh `ssh hetzner` session
- Then podman (>=5.2), podman-compose, git, and python3.11+ are installed
- And a `nicolas` user owns `/home/nicolas/pocpod0`

**AC2: Repo cloned and configured**
- Given the VPS has ssh-agent forwarding or a deploy key to the pocpod0 git remote
- When `git clone` runs into `/home/nicolas/pocpod0`
- Then the working tree matches the current main branch
- And `.env` is created from `.env.example` with production values (Discord token, OpenClaw token, CSS secret, Qdrant key)

**AC3: Stack comes up cleanly**
- Given `.env` is populated
- When `podman compose up -d` runs
- Then all services are healthy within 2 minutes: CSS, Qdrant, Oxigraph, OpenClaw gateway
- And `podman compose ps` shows no restart loops

**AC4: WebUI reachable and paired**
- Given the VPS firewall opens port 18789 (or a reverse proxy at 443)
- When Nicolas opens the gateway URL from his laptop browser
- Then the WebUI pairing page loads over HTTPS (via Caddy/Nginx reverse proxy) with the `OPENCLAW_GATEWAY_TOKEN`
- And `openclaw devices approve` from the CLI container clears the pairing state
- And the WebUI shows all 6 agents connected (claire, marc, isabelle, fatima, ayoub, troll)

**AC5: Discord integration functional on VPS**
- Given `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` are set in VPS `.env`
- When an agent is DM'd from Discord
- Then the agent responds (validates Story 4.0 on production topology)
- And heartbeats fire on the 30m interval (validates 4.0 D4)

**AC6: Security hardening minimums**
- Given the gateway is public-internet reachable
- Then it is behind a reverse proxy terminating TLS (Caddy or Nginx + Let's Encrypt)
- And direct port 18789 is NOT open to the public internet (bound to localhost on VPS, proxied)
- And SSH uses key auth only (password auth disabled)
- And UFW / firewalld allows only 22, 80, 443

**AC7: Operational runbook**
- Given a new operator (or future-Nicolas) needs to restart the stack
- Then `infra/vps/README.md` documents: ssh, pull, `podman compose up/down/logs`, factory reset (`down -v`), backup/restore of named volumes
- And a `.claude/agents/CLAUDE.md` note or memory entry points to `ssh hetzner` + path

## Tasks / Subtasks

- [ ] **Task 1: VPS baseline** (AC1, AC6)
  - [ ] 1.1: `ssh hetzner` — verify access, capture OS version (`cat /etc/os-release`), kernel, memory, disk.
  - [ ] 1.2: Create `nicolas` user if absent; add to appropriate groups (podman socket, docker-compat if applicable).
  - [ ] 1.3: Install prerequisites: `podman`, `podman-compose` (or `docker-compose-plugin` with podman backend), `git`, `python3.11`, `python3-pip`, `curl`, `jq`, `ufw`.
  - [ ] 1.4: Configure firewall: allow 22/tcp, 80/tcp, 443/tcp. Deny 18789/tcp from public.
  - [ ] 1.5: Disable SSH password auth if still enabled; confirm key-only.

- [ ] **Task 2: Repo deployment** (AC2)
  - [ ] 2.1: Set up deploy key or ssh-agent forwarding for git clone.
  - [ ] 2.2: `git clone <origin> /home/nicolas/pocpod0` as `nicolas`.
  - [ ] 2.3: Copy `.env.example` → `.env`. Populate: `OPENCLAW_GATEWAY_TOKEN`, `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_ALLOW_FROM`, `CSS_*`, `QDRANT_API_KEY`, `GOG_KEYRING_PASSWORD`.
  - [ ] 2.4: Decide `OPENCLAW_GATEWAY_BIND` for VPS — recommend `lan` (rootful) or `all`. Document choice.
  - [ ] 2.5: Ensure `.env` is mode 600, owned by `nicolas`.

- [ ] **Task 3: First stack boot** (AC3)
  - [ ] 3.1: `podman compose build` (builds the custom openclaw image). Capture build time.
  - [ ] 3.2: `podman compose up -d`. Watch `podman compose logs -f` for healthcheck failures.
  - [ ] 3.3: Run Stage 0 provision: `venv + python -m pocpod0_pipeline.run_pipeline --stage provision` (confirms CSS pods + Oxigraph seed).
  - [ ] 3.4: Verify each service: `curl http://localhost:3000/` (CSS), `curl http://localhost:6333/healthz` (Qdrant), `curl http://localhost:7878/` (Oxigraph), `curl http://localhost:18789/` (OpenClaw).

- [ ] **Task 4: Reverse proxy + TLS** (AC4, AC6)
  - [ ] 4.1: Install Caddy (preferred — auto-TLS). Alternative: nginx + certbot.
  - [ ] 4.2: Configure Caddy to proxy `openclaw.<domain>` → `127.0.0.1:18789`. Add basic-auth or rely on OpenClaw's token.
  - [ ] 4.3: Point DNS A record at VPS public IP.
  - [ ] 4.4: Verify HTTPS works; verify direct `:18789` from public is refused.

- [ ] **Task 5: WebUI pairing on VPS** (AC4)
  - [ ] 5.1: Browser: open `https://openclaw.<domain>/`, paste `OPENCLAW_GATEWAY_TOKEN` + `GOG_KEYRING_PASSWORD` per pairing flow.
  - [ ] 5.2: `podman compose --profile cli run --rm openclaw-cli devices list` — confirm request visible.
  - [ ] 5.3: `openclaw devices approve <id>`. Confirm WebUI flips to "connected".
  - [ ] 5.4: Verify all 6 agents appear in the WebUI agent list.

- [ ] **Task 6: Discord integration validation** (AC5)
  - [ ] 6.1: From Nicolas's Discord, DM claire-teacher — expect reply.
  - [ ] 6.2: Post in #general — expect isabelle aggregate heartbeat within 30m.
  - [ ] 6.3: Post in #security_logs — expect troll probe report within 30m.
  - [ ] 6.4: Capture message IDs / timestamps into `_bmad-output/implementation-artifacts/vps-smoke-test.md`.

- [ ] **Task 7: Operational runbook** (AC7)
  - [ ] 7.1: Create `infra/vps/README.md` — include ssh command, common ops (up/down/logs/restart), factory reset procedure, env var catalog.
  - [ ] 7.2: Document named-volume backup: `podman volume export openclaw-data-default > backups/openclaw-$(date +%F).tar`.
  - [ ] 7.3: Add memory entry: `infra_vps_deploy.md` — VPS path, ssh alias, deploy procedure summary.
  - [ ] 7.4: Update `deferred-work.md` — close 4.0 side quest with "resolved via VPS deploy (Story 4.0.2)".

- [ ] **Task 8: Rollback plan documentation**
  - [ ] 8.1: Document: how to `podman compose down -v` on VPS without losing deploy state (only workspace volumes are ephemeral; `.env` + repo stay).
  - [ ] 8.2: Document how to revert to local dev if VPS is down (pull latest, run locally — accept WebUI limitation).

## Dev Notes

- **Why VPS fixes it:** Rootful podman on a proper Linux VPS uses netavark + iptables natively. No pasta/compose interaction. No rootless port-forwarding limitations.
- **Non-goal:** This is not an "Alpha" pilot deployment. It's a dev topology that happens to live on a VPS. No multi-operator concerns, no HA.
- **Cost discipline:** Use the smallest Hetzner instance that runs the stack (4 services + 6 agents). Validate RAM: CSS ~300MB, Qdrant ~500MB, Oxigraph ~200MB, OpenClaw ~500MB + agent runtime. CX22 (4GB) likely sufficient; CX32 (8GB) safer.
- **Invalidated assumptions from 4.0 side quest:**
  - ❌ "Bug is in `bind` setting" — it's in podman-compose network selection
  - ❌ "Epic 3 compose/entrypoint delta broke it" — podman/pasta version drift on host is the likely trigger, not repo changes
- **Prerequisite before running Task 5:** 4.0 D1 (`DISCORD_ALLOW_FROM`) should be set on VPS `.env` or DMs will silently reject.

## References

- deferred-work.md "Side Quest: OpenClaw gateway bind / WebUI + CLI pairing (2026-04-14)"
- Memory: `project_pilot_bridge.md` — container → VPS migration path
- Memory: `story_4_0_openclaw_discord_patterns.md` — Discord config patterns
