# pocpod0 — project convenience targets
# All podman compose commands assume running inside distrobox.
# Use: distrobox-host-exec podman compose ... for host-level compose calls.

COMPOSE = distrobox-host-exec podman compose
PIPELINE_VENV = pipeline/.venv/bin/activate

.PHONY: help up down reset logs ps \
        pull build rebuild \
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
	@echo "  pull          Pull latest upstream images (CSS, Oxigraph, Qdrant, Nginx)"
	@echo "  build         Build local openclaw image"
	@echo "  rebuild       Pull upstream + rebuild openclaw image"
	@echo ""
	@echo "Pipeline & tools:"
	@echo "  pipeline      Run full xAPI-OSLO ingestion pipeline"
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
