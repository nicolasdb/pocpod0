# pocpod0 — project convenience targets
# All podman compose commands assume running inside distrobox.
# Use: distrobox-host-exec podman compose ... for host-level compose calls.

COMPOSE = distrobox-host-exec podman compose
PIPELINE_VENV = pipeline/.venv/bin/activate

.PHONY: help up down reset logs ps \
        pull build rebuild sync-workspaces backup \
        pipeline pipeline-dry dashboard troll \
        cli-devices cli-dashboard \
        setup

# ── Default ──────────────────────────────────────────────────────────────────

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Infrastructure:"
	@echo "  up            Start all services (detached)"
	@echo "  down          Stop all services"
	@echo "  reset         Full wipe (volumes + restart)"
	@echo "  logs          Follow logs for all services"
	@echo "  ps            Show running containers"
	@echo ""
	@echo "Image management:"
	@echo "  pull              Pull latest upstream images (CSS, Oxigraph, Qdrant, Nginx)"
	@echo "  build             Build local openclaw image"
	@echo "  rebuild           Pull upstream + rebuild openclaw image"
	@echo "  sync-workspaces   Rebuild + hot-patch agent files (no volume wipe, pod data safe)"
	@echo "  backup            Extract workspaces + config from container → backups/openclaw-<timestamp>/"
	@echo ""
	@echo "Pipeline & tools:"
	@echo "  pipeline      Run full xAPI-OSLO ingestion pipeline, dashboard included"
	@echo "  pipeline-dry  Dry-run pipeline (no writes)"
	@echo "  dashboard     Start ACL enforcement dashboard (http://localhost:8080)"
	@echo "  troll         Run comprehensive troll adversary test suite"
	@echo ""
	@echo "OpenClaw CLI:"
	@echo "  cli-devices   List/approve gateway devices"
	@echo "  cli-dashboard Show OpenClaw dashboard URL"
	@echo ""
	@echo "Setup:"
	@echo "  setup         One-time: create venv + install pipeline deps"
	@echo ""
	@echo "VPS deploy (run from local):"
	@echo "  vps-push      rsync local repo + .env to hetzner:/home/nicolas/pocpod0"
	@echo "  vps-build     docker compose build on VPS"
	@echo "  vps-deploy    push + build + up (full deploy)"
	@echo "  vps-up        docker compose up -d on VPS"
	@echo "  vps-down      docker compose down on VPS"
	@echo "  vps-logs      Follow VPS stack logs"
	@echo "  vps-ps        Show VPS container status"
	@echo "  vps-ssh       Open SSH session to VPS"

# ── Infrastructure ────────────────────────────────────────────────────────────

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

# ── Image management ──────────────────────────────────────────────────────────

# Hot-patch agent workspaces + skills in the running container.
# Rebuilds the image (so /app/agents-seed/ is current), recreates the container
# (volumes intact — pod data, Oxigraph, Qdrant are NOT touched), then copies
# seed files over the live workspaces while preserving evolved runtime state
# (MEMORY.md, HEARTBEAT.md and the memory/ + state/ dirs).
#
# Use this instead of `reset` whenever you only changed agents/ files.
# reset = full wipe (1h pipeline re-run). sync-workspaces = ~30s, no data loss.
# Extract agent workspaces + openclaw config from the running container for review/backup.
# Output: backups/openclaw-YYYY-MM-DDTHH-MM/
#   workspaces/   — full agent workspaces (MEMORY.md, HEARTBEAT.md, memory/, state/, …)
#   openclaw.json — live gateway config (may differ from repo if gateway evolved it)
#   exec-approvals.json — approved tool executions
#   devices/      — paired device records
#
# Safe to run at any time — read-only, no container state modified.
backup:
	$(eval BACKUP_DIR := backups/openclaw-$(shell date +%Y-%m-%dT%H-%M))
	@mkdir -p $(BACKUP_DIR)
	@echo "Backing up to $(BACKUP_DIR)/ ..."
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/workspaces $(BACKUP_DIR)/workspaces
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/openclaw.json $(BACKUP_DIR)/openclaw.json
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/exec-approvals.json $(BACKUP_DIR)/exec-approvals.json 2>/dev/null || true
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/devices $(BACKUP_DIR)/devices 2>/dev/null || true
	@echo "Done. Contents:"
	@find $(BACKUP_DIR) -type f | sort | sed 's|^|  |'

sync-workspaces: build
	$(COMPOSE) up -d --force-recreate openclaw-gateway
	@echo "Waiting for openclaw-gateway to be healthy..."
	@until distrobox-host-exec podman exec openclaw-gateway true 2>/dev/null; do sleep 1; done
	@distrobox-host-exec podman exec openclaw-gateway sh -c '\
		for src in $$(find /app/agents-seed -type f); do \
			rel="$${src#/app/agents-seed/}"; \
			case "$$rel" in \
				*/MEMORY.md|*/HEARTBEAT.md) echo "  preserved: $$rel" ;; \
				*) dest="/home/node/.openclaw/workspaces/$$rel"; \
				   mkdir -p "$$(dirname $$dest)"; \
				   cp "$$src" "$$dest"; \
				   echo "  synced:    $$rel" ;; \
			esac; \
		done'
	@echo "Workspace sync complete. memory/ and state/ dirs untouched."

# Pull only the external (non-built) images.
pull:
	$(COMPOSE) pull community-solid-server oxigraph qdrant nginx

build:
	$(COMPOSE) build openclaw-gateway

# Pull external images first, then rebuild openclaw on top.
rebuild: pull build

# ── Pipeline & tools ──────────────────────────────────────────────────────────

pipeline:
	@bash scripts/run-pipeline.sh --with-dashboard

pipeline-dry:
	@bash scripts/run-pipeline.sh --dry-run

# Start the FastAPI ACL dashboard; relies on pipeline venv.
dashboard:
	@. $(PIPELINE_VENV) && pocpod0-acl-dashboard

troll:
	@bash scripts/run-troll.sh

# ── OpenClaw CLI ──────────────────────────────────────────────────────────────

# Pass extra args with: make cli-devices ARGS="approve <requestId>"
cli-devices:
	$(COMPOSE) --profile cli run --rm openclaw-cli devices $(ARGS)

cli-dashboard:
	$(COMPOSE) --profile cli run --rm openclaw-cli dashboard --no-open

# ── VPS deploy (run from local, deploys to Hetzner) ──────────────────────────
# VPS path: /home/nicolas/pocpod0  SSH alias: hetzner
# .env is included in rsync (contains secrets — never committed to git)

VPS_REMOTE := hetzner
VPS_PATH   := /home/nicolas/pocpod0

.PHONY: vps-push vps-build vps-deploy vps-up vps-down vps-logs vps-ps vps-ssh

## Sync local repo + .env to VPS (excludes .git, __pycache__, .pyc, backups)
vps-push:
	rsync -avz --delete-after \
		--exclude=".git" \
		--exclude="*__pycache__*" \
		--exclude="*.pyc" \
		--exclude="backups/" \
		--exclude="pipeline/.venv/" \
		./ $(VPS_REMOTE):$(VPS_PATH)/
	@echo "Sync complete."

## Build openclaw image on VPS (run after first vps-push or after Dockerfile changes)
vps-build:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose build"

## Full deploy: push + build + restart stack
vps-deploy: vps-push vps-build
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose up -d"

## Start stack on VPS (no rebuild)
vps-up:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose up -d"

## Stop stack on VPS
vps-down:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose down"

## Follow logs on VPS
vps-logs:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose logs -f"

## Show container status on VPS
vps-ps:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose ps"

## Open SSH session to VPS
vps-ssh:
	ssh $(VPS_REMOTE)
