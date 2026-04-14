#!/bin/sh
# Seed-on-boot entrypoint for OpenClaw gateway.
#
# On first boot (named volume is empty), copies agent workspace seed files from
# /app/agents-seed/{id}/ to /home/node/.openclaw/workspaces/{id}/.
# On subsequent restarts the named volume already has these directories, so
# existing state (evolved MEMORY.md, etc.) is preserved.
# Factory reset: docker-compose down -v && docker-compose up
#
# AC1: seed-on-boot idempotency guarantee.

set -e

SEED_DIR="/app/agents-seed"
WORKSPACE_DIR="/home/node/.openclaw/workspaces"
SKILLS_TARGET="/home/node/.openclaw/workspaces/skills"

# Seed per-agent workspaces
for agent_seed in "${SEED_DIR}"/*/; do
    agent_id=$(basename "${agent_seed}")

    # Skip non-agent directories
    [ "${agent_id}" = "skills" ] && continue  # handled separately below
    [ "${agent_id}" = "data" ] && continue    # runtime data, not agent workspace
    [ -f "${agent_seed}" ] && continue

    target="${WORKSPACE_DIR}/${agent_id}"
    if [ ! -d "${target}" ]; then
        echo "[entrypoint] Seeding workspace: ${agent_id}"
        mkdir -p "${target}"
        cp -r "${agent_seed}." "${target}/"
    else
        echo "[entrypoint] Workspace exists, skipping: ${agent_id}"
    fi
done

# Seed skills directory
if [ ! -d "${SKILLS_TARGET}" ]; then
    if [ ! -d "${SEED_DIR}/skills" ]; then
        echo "[entrypoint] ERROR: skills seed directory missing at ${SEED_DIR}/skills"
        exit 1
    fi
    echo "[entrypoint] Seeding skills workspace"
    mkdir -p "${SKILLS_TARGET}"
    cp -r "${SEED_DIR}/skills/." "${SKILLS_TARGET}/"
else
    echo "[entrypoint] Skills workspace exists, skipping"
fi

# Always deploy fresh openclaw.json from the bind-mounted /tmp/openclaw.json.
# Config is not evolvable — always comes from the repo image at startup.
if [ ! -f /tmp/openclaw.json ]; then
    echo "[entrypoint] ERROR: /tmp/openclaw.json not found — is the bind-mount configured?"
    echo "[entrypoint] Expected: ./agents/openclaw.json:/tmp/openclaw.json:ro in docker-compose.yml"
    exit 1
fi
echo "[entrypoint] Deploying openclaw.json"
mkdir -p /home/node/.openclaw
cp /tmp/openclaw.json /home/node/.openclaw/openclaw.json

# Launch the gateway
# --bind auto: listen on loopback + lan (valid values: loopback|lan|tailnet|auto|custom).
#   - loopback: required for openclaw-cli (network_mode:service) to connect via ws://127.0.0.1
#   - lan: required for Docker port mapping (host:18789 → container:18789) to reach the gateway
echo "[entrypoint] Starting OpenClaw gateway"
exec node dist/index.js gateway \
    --bind "${OPENCLAW_GATEWAY_BIND:-auto}" \
    --port "${OPENCLAW_GATEWAY_PORT:-18789}" \
    --allow-unconfigured
