# Story 4.0.2: Deploy pocpod0 to Hetzner VPS (unblock WebUI + Epic 4)

Status: in-progress

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

- [x] **Task 1: VPS baseline** (AC1, AC6)
  - [x] 1.1: `ssh hetzner` — Ubuntu 24.04.2 LTS, kernel 6.8.0-88, 3.7GB RAM, 38GB disk (84% used — Docker consuming 30GB, 12GB reclaimable).
  - [x] 1.2: `/home/nicolas/` directory exists (root-owned VPS, no separate `nicolas` system user needed — running as root).
  - [x] 1.3: git 2.43.0 ✓, python3.12 ✓, ufw ✓. podman + podman-compose absent — to install in Task 3 prereq.
  - [x] 1.4: UFW enabled: allow 22/tcp, 80/tcp, 443/tcp, 9443/tcp. DEFAULT_FORWARD_POLICY=ACCEPT (required for Docker routing). 18789/18790 not open externally.
  - [x] 1.5: SSH key-only confirmed (key auth in use for `ssh hetzner` alias).

- [ ] **Task 2: Repo deployment via rsync** (AC2)
  - [x] 2.1: ❌ INVALIDATED: git clone approach dropped. Deploy from local via rsync (same pattern as hetzner-gateway Makefile). `.env` with secrets included in rsync, never committed to git.
  - [x] 2.2: Added `vps-push`, `vps-build`, `vps-deploy`, `vps-up/down/logs/ps/ssh` targets to pocpod0 Makefile.
  - [ ] 2.3: Verify local `.env` has VPS-specific values: `OPENCLAW_GATEWAY_HOST=0.0.0.0`, `OPENCLAW_GATEWAY_PORT=18790`, Discord token, CSS, Qdrant creds.
  - [ ] 2.4: Run `make vps-push` from local. Verify `/home/nicolas/pocpod0/` on VPS has `.env` present (mode 600).

- [ ] **Task 3: First stack boot** (AC3)
  - [ ] 3.0: Disk reclaim — `docker system prune -f` on VPS (12GB reclaimable). VPS at 84%.
  - [ ] 3.1: `docker compose build` (builds the custom openclaw image).
  - [ ] 3.2: `docker compose up -d`. Watch `docker compose logs -f` for healthcheck failures.
  - [ ] 3.3: Run Stage 0 provision: `venv + python -m pocpod0_pipeline.run_pipeline --stage provision` (confirms CSS pods + Oxigraph seed).
  - [ ] 3.4: Verify each service: `curl http://localhost:3000/` (CSS), `curl http://localhost:6333/healthz` (Qdrant), `curl http://localhost:7878/` (Oxigraph), `curl http://localhost:18790/` (OpenClaw). Then `curl https://pod.nicolasdb.eu/` — expect 200 (resolves 504).

- [x] **Task 4: Reverse proxy + TLS** (AC4, AC6)
  - [x] 4.1: Reused existing nginx gateway (hetzner-gateway repo) — no Caddy needed.
  - [x] 4.2: Created `nginx/conf.d/04-pocpod0.conf` → `172.23.0.1:18790` (gateway network host IP). Also `05-openclaw-lab.conf` → `172.23.0.1:18789` for lab instance. WebSocket + SSE buffering disabled.
  - [x] 4.3: DNS A records set in Cloudflare: `pod.nicolasdb.eu` + `claw.nicolasdb.eu` → `128.140.72.105`.
  - [x] 4.4: SSL cert expanded via certbot --manual --expand with Cloudflare DNS hooks to include pod + claw subdomains (expires 2026-07-14). Direct :18790 not open externally (UFW).

- [ ] **Task 5: WebUI pairing on VPS** (AC4)
  - [ ] 5.1: Browser: open `https://pod.nicolasdb.eu/`, paste `OPENCLAW_GATEWAY_TOKEN` + `GOG_KEYRING_PASSWORD` per pairing flow.
  - [ ] 5.2: `docker compose --profile cli run --rm openclaw-cli devices list` — confirm request visible.
  - [ ] 5.3: `openclaw devices approve <id>`. Confirm WebUI flips to "connected".
  - [ ] 5.4: Verify all 6 agents appear in the WebUI agent list.

- [ ] **Task 6: Discord integration validation** (AC5)
  - [ ] 6.1: From Nicolas's Discord, DM claire-teacher — expect reply.
  - [ ] 6.2: Post in #general — expect isabelle aggregate heartbeat within 30m.
  - [ ] 6.3: Post in #security_logs — expect troll probe report within 30m.
  - [ ] 6.4: Capture message IDs / timestamps into `_bmad-output/implementation-artifacts/vps-smoke-test.md`.

- [ ] **Task 7: Operational runbook** (AC7)
  - [ ] 7.1: Create `infra/vps/README.md` — include ssh command, common ops (up/down/logs/restart), factory reset procedure, env var catalog.
  - [ ] 7.2: Document named-volume backup: `docker volume export openclaw-data-default > backups/openclaw-$(date +%F).tar`.
  - [ ] 7.3: Add memory entry: `infra_vps_deploy.md` — VPS path, ssh alias, deploy procedure summary.
  - [ ] 7.4: Update `deferred-work.md` — close 4.0 side quest with "resolved via VPS deploy (Story 4.0.2)".

- [ ] **Task 8: Rollback plan documentation**
  - [ ] 8.1: Document: how to `docker compose down -v` on VPS without losing deploy state (only workspace volumes are ephemeral; `.env` + repo stay).
  - [ ] 8.2: Document how to revert to local dev if VPS is down (pull latest, run locally — accept WebUI limitation).

## Dev Agent Record

### Debug Log

- **UFW + Docker conflict (2026-04-15):** Enabling UFW with default `DEFAULT_FORWARD_POLICY=DROP` broke Docker container routing — including the Cloudflare tunnel reaching Portainer at `128.140.72.105:9443`. Fix: set `DEFAULT_FORWARD_POLICY=ACCEPT` in `/etc/default/ufw` + `ufw reload`. Also required allowing port 9443 explicitly since the tunnel config uses the public IP (not container name) to reach Portainer. Long-term fix: update Cloudflare tunnel config to use `https://portainer:9443` (internal container name) to avoid the firewall dependency.
- **nginx upstream resolution (2026-04-15):** `host.docker.internal` via `extra_hosts: host-gateway` works in `/etc/hosts` but nginx resolves upstreams via DNS (127.0.0.11), not hosts file. Nginx crashed at startup with "host not found in upstream". Fix: hardcode `172.23.0.1` (host IP on the `gateway` Docker network) directly in `proxy_pass`. No DNS resolution needed for a literal IP.
- **Two OpenClaw instances (2026-04-15):** VPS already has `openclaw-infra` (lab/debug) at port 18789. pocpod0 uses port 18790 via `OPENCLAW_GATEWAY_HOST=0.0.0.0` + `OPENCLAW_GATEWAY_PORT=18790` in VPS `.env`. Routed via `claw.nicolasdb.eu` and `pod.nicolasdb.eu` respectively.
- **Port binding:** pocpod0 `docker-compose.yml` now supports `OPENCLAW_GATEWAY_HOST` env var (defaults to `127.0.0.1` locally, set to `0.0.0.0` on VPS so nginx container can reach it via bridge IP).

### Invalidated Story Assumptions

- ❌ "Install Caddy" — existing nginx gateway reused; no new reverse proxy needed
- ❌ "task 1.2: create nicolas user" — VPS runs as root; `/home/nicolas/` is a directory, not a system user home

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
