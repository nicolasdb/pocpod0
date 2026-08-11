# pocpod0 — project convenience targets
# Only commands that are long, multi-step, or easy to forget belong here.
# Simple one-liners (compose up/down/logs, ssh) run directly.
#
# Local stack uses distrobox-host-exec podman compose.
# VPS targets run from local via SSH — no make needed on the VPS.

COMPOSE        = distrobox-host-exec podman compose
PIPELINE_VENV  = pipeline/.venv/bin/activate
VPS_REMOTE     = hetzner
VPS_PATH       = /home/nicolas/pocpod0

.PHONY: help \
        pull rebuild sync-workspaces backup \
        pipeline pipeline-dry dashboard troll setup \
        cli-devices \
        vps-push vps-build vps-deploy vps-setup vps-pipeline \
        vps-devices-list vps-devices-approve vps-backup vps-backup-schedule

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "Local:"
	@echo "  pull              Pull latest upstream images (CSS, Oxigraph, Qdrant, Nginx)"
	@echo "  rebuild           Pull upstream + rebuild openclaw image"
	@echo "  sync-workspaces   Hot-patch agent files (no volume wipe, ~30s)"
	@echo "  backup            Extract workspaces + config → backups/openclaw-<ts>/"
	@echo "  pipeline          Run full xAPI-OSLO ingestion pipeline"
	@echo "  pipeline-dry      Dry-run pipeline (no writes)"
	@echo "  dashboard         Start FastAPI ACL dashboard (http://localhost:8080)"
	@echo "  troll             Run troll adversary test suite"
	@echo "  setup             One-time: create pipeline venv + install deps"
	@echo "  cli-devices       List/approve local OpenClaw gateway devices"
	@echo "                    Pass ARGS='approve <id>' to approve"
	@echo ""
	@echo "VPS (run from local):"
	@echo "  vps-push          rsync repo + .env → VPS, apply VPS .env overrides"
	@echo "  vps-build         docker compose build on VPS"
	@echo "  vps-deploy        push + build + up (full deploy)"
	@echo "  vps-setup         One-time: create pipeline venv on VPS"
	@echo "  vps-pipeline      Run ingestion pipeline on VPS (in tmux session)"
	@echo "  vps-devices-list  List pending/paired WebUI devices on VPS"
	@echo "  vps-devices-approve ID=<requestId>  Approve WebUI pairing on VPS"
	@echo "  vps-backup        Backup named volumes → VPS backups/ directory (manual, run now)"
	@echo "  vps-backup-schedule  Install nightly cron on VPS running vps-backup (keeps last 7 days)"

# ── Local: image management ───────────────────────────────────────────────────

pull:
	$(COMPOSE) pull community-solid-server oxigraph qdrant nginx

rebuild: pull
	$(COMPOSE) build openclaw-gateway

# Rebuild image + hot-patch agent files in running container.
# Preserves MEMORY.md, HEARTBEAT.md, memory/ and state/ dirs.
# Use instead of full reset when only agents/ files changed (~30s vs 1h pipeline).
sync-workspaces: rebuild
	$(COMPOSE) up -d --force-recreate openclaw-gateway
	@echo "Waiting for openclaw-gateway..."
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
	@echo "Workspace sync complete."

# Extract agent workspaces + config from running container.
# Output: backups/openclaw-YYYY-MM-DDTHH-MM/
backup:
	$(eval BACKUP_DIR := backups/openclaw-$(shell date +%Y-%m-%dT%H-%M))
	@mkdir -p $(BACKUP_DIR)
	@echo "Backing up to $(BACKUP_DIR)/ ..."
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/workspaces $(BACKUP_DIR)/workspaces
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/openclaw.json $(BACKUP_DIR)/openclaw.json
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/exec-approvals.json $(BACKUP_DIR)/exec-approvals.json 2>/dev/null || true
	@distrobox-host-exec podman cp openclaw-gateway:/home/node/.openclaw/devices $(BACKUP_DIR)/devices 2>/dev/null || true
	@echo "Done:"; find $(BACKUP_DIR) -type f | sort | sed 's|^|  |'

# ── Local: pipeline & tools ───────────────────────────────────────────────────

pipeline:
	@. $(PIPELINE_VENV) && python pipeline/run_pipeline.py

pipeline-dry:
	@. $(PIPELINE_VENV) && python pipeline/run_pipeline.py --dry-run

dashboard:
	@. $(PIPELINE_VENV) && pocpod0-acl-dashboard

troll:
	@bash scripts/run-troll.sh

setup:
	python3 -m venv pipeline/.venv
	pipeline/.venv/bin/pip install -e 'pipeline/[dev]' --quiet
	@echo "Venv ready: pipeline/.venv"

# Pass ARGS="approve <requestId>" to approve a device
cli-devices:
	distrobox-host-exec podman exec openclaw-gateway openclaw devices $(ARGS)

# ── VPS deploy (run from local) ───────────────────────────────────────────────
# SSH alias: hetzner  |  Path: /home/nicolas/pocpod0
# .env synced from local; VPS overrides auto-applied from infra/vps/.env.vps

RSYNC_EXCLUDES = \
	--exclude=".git" \
	--exclude=".claude/" \
	--exclude=".gemini/" \
	--exclude="_bmad/" \
	--exclude="_bmad-output/" \
	--exclude="__pycache__/" \
	--exclude="*.py[cod]" \
	--exclude=".venv/" \
	--exclude="venv/" \
	--exclude="pipeline/.venv/" \
	--exclude="pipeline/venv/" \
	--exclude="design-artifacts/" \
	--exclude=".pytest_cache/" \
	--exclude=".coverage" \
	--exclude="*.tmp" \
	--exclude="*.bak" \
	--exclude="mcp-connector/node_modules/" \
	--exclude="mcp-connector/identities.json" \
	--exclude="mcp-connector/audit/" \
	--exclude="backups/"

# `--delete-after` deletes anything present on the VPS but not in this local
# checkout — including files that only ever existed VPS-side, like
# identities.json before the exclude above was added (story 8.4 AC9: an
# unguarded push deleted a secrets file on the exact pattern hetzner-gateway
# hit first, see its Makefile). The dry-run refusal is the actual guard;
# the exclude list is defense in depth, not a substitute for it.
#
# mcp-connector/audit/ is VPS-side only and was excluded on 2026-08-11, when
# the guard refused a Story 8.9 deploy over it. The live journal is in the
# `mcp-audit` named volume, not this path — the host directory is an empty
# leftover, so deleting it would have been harmless. Excluded anyway: a guard
# that cries wolf on a known-safe path every deploy is a guard people learn to
# FORCE past, and the next thing it refuses might be identities.json.
vps-push:
	@dels=$$(rsync -avzn --delete-after $(RSYNC_EXCLUDES) ./ $(VPS_REMOTE):$(VPS_PATH)/ \
		| grep '^deleting' || true); \
	if [ -n "$$dels" ] && [ -z "$(FORCE)" ]; then \
		echo "REFUSING TO PUSH — this would delete files on the VPS:"; \
		echo "$$dels" | sed 's/^/    /'; \
		echo; \
		echo "If they are genuinely retired, re-run: make vps-push FORCE=1"; \
		echo "If they are server-authored (e.g. identities.json), exclude them or pull them into the repo first."; \
		exit 1; \
	fi; \
	rsync -avz --delete-after $(RSYNC_EXCLUDES) ./ $(VPS_REMOTE):$(VPS_PATH)/
	@echo "Applying VPS .env overrides..."
	@ssh $(VPS_REMOTE) 'cd $(VPS_PATH) && \
		grep -v "^#" infra/vps/.env.vps | grep "=" | while IFS="=" read -r key value; do \
			sed -i "s|^$$key=.*|$$key=$$value|" .env; \
		done'
	@echo "Sync complete."

vps-build:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose build"

vps-deploy: vps-push vps-build
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && docker compose up -d"

# One-time: bootstrap pipeline venv on VPS after first vps-push
vps-setup:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH)/pipeline && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' --quiet && echo 'venv ready'"

# Run pipeline on VPS inside a tmux session (detaches; check progress via vps logs)
vps-pipeline:
	ssh $(VPS_REMOTE) "cd $(VPS_PATH) && tmux new-session -d -s pipeline '. pipeline/.venv/bin/activate && python pipeline/run_pipeline.py' && echo 'Pipeline running in tmux session: pipeline' && echo 'Check: ssh hetzner tmux attach -t pipeline'"

vps-devices-list:
	ssh $(VPS_REMOTE) "docker exec openclaw-gateway openclaw devices list"

# Usage: make vps-devices-approve ID=<requestId>
vps-devices-approve:
	ssh $(VPS_REMOTE) "docker exec openclaw-gateway openclaw devices approve $(ID)"

# Backup all named volumes to VPS backups/ directory (manual, run now)
vps-backup:
	ssh $(VPS_REMOTE) "mkdir -p $(VPS_PATH)/backups"
	ssh $(VPS_REMOTE) "docker run --rm -v pocpod0_css-data:/data alpine tar czf - /data > $(VPS_PATH)/backups/css-data-$$(date +%F).tar.gz && echo 'css-data backed up'"
	ssh $(VPS_REMOTE) "docker run --rm -v pocpod0_openclaw-data-default:/data alpine tar czf - /data > $(VPS_PATH)/backups/openclaw-data-$$(date +%F).tar.gz && echo 'openclaw-data backed up'"
	ssh $(VPS_REMOTE) "docker run --rm -v pocpod0_oxigraph-data:/data alpine tar czf - /data > $(VPS_PATH)/backups/oxigraph-data-$$(date +%F).tar.gz && echo 'oxigraph-data backed up'"
	ssh $(VPS_REMOTE) "docker run --rm -v pocpod0_qdrant-data:/data alpine tar czf - /data > $(VPS_PATH)/backups/qdrant-data-$$(date +%F).tar.gz && echo 'qdrant-data backed up'"

# Install a nightly cron on the VPS that runs the same backups as `vps-backup`
# and trims anything older than 7 days. vps-backup itself was previously a
# manual-only command — nobody had ever run it, so no css-data backup existed
# before a code-review incident touched the live root .acl with none to
# restore from (Story 7.1, 2026-07-22). This closes that gap going forward.
vps-backup-schedule:
	ssh $(VPS_REMOTE) "mkdir -p $(VPS_PATH)/backups"
	scp infra/vps/nightly-backup.sh $(VPS_REMOTE):$(VPS_PATH)/backups/nightly-backup.sh
	ssh $(VPS_REMOTE) "chmod +x $(VPS_PATH)/backups/nightly-backup.sh"
	ssh $(VPS_REMOTE) '(crontab -l 2>/dev/null | grep -v nightly-backup.sh; echo "0 3 * * * $(VPS_PATH)/backups/nightly-backup.sh >> $(VPS_PATH)/backups/nightly-backup.log 2>&1") | crontab -'
	@echo "Nightly backup cron installed (03:00 daily, 7-day retention). Verify: ssh $(VPS_REMOTE) crontab -l"
