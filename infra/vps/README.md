# pocpod0 VPS Operations Runbook

**Host:** Hetzner VPS (`ssh hetzner` alias)  
**Path:** `/home/nicolas/pocpod0`  
**DNS:** `pod.nicolasdb.eu` (OpenClaw WebUI), `claw.nicolasdb.eu` (OpenClaw lab)  
**User:** root (VPS runs as root; `/home/nicolas/` is a directory, not a system user home)

---

## Common Operations

### Deploy from local

```bash
# Full deploy: rsync + docker build + up
make vps-deploy

# Push code only (no rebuild, no restart)
make vps-push

# Build image only (after Dockerfile changes)
make vps-build
```

> `vps-push` automatically applies VPS-specific `.env` overrides from `infra/vps/.env.vps`
> after the rsync. You do not need to manually patch `.env` on the VPS after each push.

### Stack lifecycle

```bash
make vps-up       # docker compose up -d (no rebuild)
make vps-down     # docker compose down (keeps volumes)
make vps-logs     # docker compose logs -f
make vps-ps       # docker compose ps
make vps-ssh      # open interactive SSH session
```

### Run pipeline on VPS

```bash
# Activate venv manually:
ssh hetzner
cd /home/nicolas/pocpod0
. pipeline/.venv/bin/activate
python pipeline/run_pipeline.py --stage provision
```

Or via Makefile:
```bash
make vps-pipeline          # full pipeline with TUI
make vps-pipeline-watch    # open TUI dashboard (second terminal)
```

---

## First-Time Setup (one-time)

```bash
# 1. Push repo + install pipeline deps
make vps-push
ssh hetzner "cd /home/nicolas/pocpod0 && python3.12 -m venv pipeline/.venv && . pipeline/.venv/bin/activate && pip install -e pipeline/"

# 2. Build OpenClaw image
make vps-build

# 3. Start stack
make vps-up

# 4. Run Stage 0 provision (creates CSS pods + seeds Oxigraph)
# Takes ~45-60 min — run in a tmux session
ssh hetzner
tmux new -s pipeline
cd /home/nicolas/pocpod0 && . pipeline/.venv/bin/activate && python pipeline/run_pipeline.py --stage provision
```

---

## Service Health Checks

```bash
ssh hetzner
curl http://localhost:3000/            # CSS → 200
curl http://localhost:6333/healthz     # Qdrant → "healthz check passed"
curl http://localhost:7878/            # Oxigraph → 200
curl http://localhost:18790/           # OpenClaw gateway → 200
```

External:
```bash
curl https://pod.nicolasdb.eu/        # OpenClaw WebUI → 200
```

---

## WebUI Pairing

1. Browser: open `https://pod.nicolasdb.eu/`, enter `OPENCLAW_GATEWAY_TOKEN` from VPS `.env`
2. On VPS (or via Makefile):
   ```bash
   docker exec openclaw-gateway openclaw devices list
   docker exec openclaw-gateway openclaw devices approve <id>
   ```
3. Verify agents in WebUI: claire, marc, isabelle, fatima, ayoub, troll (6 total)

---

## Rollback & Recovery

### Soft restart (keeps all data)

```bash
make vps-down
make vps-up
```

### Factory reset (wipes all volume data — irreversible)

```bash
ssh hetzner "cd /home/nicolas/pocpod0 && docker compose down -v"
```

This deletes: `pocpod0_css-data`, `pocpod0_openclaw-data-default`, `pocpod0_oxigraph-data`, `pocpod0_qdrant-data`.

After a factory reset you must re-run Stage 0 provision.

### Backup named volumes before reset (or any risky live test)

```bash
make vps-backup             # manual, run now — includes css-data
```

A nightly cron (03:00, 7-day retention) also runs automatically — installed via:

```bash
make vps-backup-schedule    # one-time: installs infra/vps/nightly-backup.sh + cron entry
```

Verify it's active: `ssh hetzner crontab -l`. Backups land in `/home/nicolas/pocpod0/backups/`.

> Installed 2026-07-22 after a code-review live test touched the root `.acl` with
> no backup to restore from (Story 7.1). Always run `make vps-backup` before any
> exploratory testing against the live CSS server, even with the cron in place.

### Fallback to local dev

If VPS is unreachable:
1. `git pull` locally
2. Edit `.env`: set `OPENCLAW_GATEWAY_HOST=127.0.0.1`, `OPENCLAW_GATEWAY_BIND=lan`
3. Start local stack (podman-compose / docker compose)
4. Accept that WebUI may be unreachable locally (rootless podman/pasta limitation — see deferred-work.md)

---

## Environment Variables Catalog

| Variable | Local value | VPS value | Purpose |
|---|---|---|---|
| `OPENCLAW_GATEWAY_HOST` | `127.0.0.1` | `0.0.0.0` | Bind address for OpenClaw gateway |
| `OPENCLAW_GATEWAY_BIND` | `lan` | `all` | OpenClaw bind mode |
| `OPENCLAW_GATEWAY_PORT` | `18790` | `18790` | Host port mapping |
| `OPENCLAW_GATEWAY_TOKEN` | — | (secret) | WebUI pairing token |
| `DISCORD_BOT_TOKEN` | — | (secret) | Discord bot auth |
| `DISCORD_GUILD_ID` | — | (secret) | Discord server ID |
| `DISCORD_ALLOW_FROM` | — | set to guild | DM allow-list guard |

VPS overrides are stored in `infra/vps/.env.vps` and auto-applied by `make vps-push`.

---

## Disk Management

VPS has ~38GB total. Docker can accumulate unused images/layers.

```bash
ssh hetzner "docker system prune -f"   # removes stopped containers + dangling images
ssh hetzner "df -h"                     # check disk usage
```
