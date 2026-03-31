#!/usr/bin/env bash
# Run troll adversary comprehensive test suite across all 5 attack categories.
# Orchestrates ACL enforcement, SPARQL injection, vector privacy, cross-inference, and deletion timing.
# Generates categorized JSON and markdown reports for funder review.
# Exits with non-zero code if blocking categories (ACL, SPARQL) fail per NFR5/NFR6.
#
# Usage (from project root):
#   bash scripts/run-troll.sh
#
# Environment:
#   CSS_BASE_URL  CSS base URL (default: http://localhost:3000)
#   OXIGRAPH_URL  Oxigraph SPARQL endpoint (default: http://localhost:7878)
#   QDRANT_URL    Qdrant vector DB (default: http://localhost:6333)
#   OPENCLAW_BASE_URL  OpenClaw agent gateway (default: http://localhost:8000)
#   OPENCLAW_GATEWAY_TOKEN  Optional OpenClaw auth token
#   VENV_PATH     Path to virtual environment (default: pipeline/.venv)
#
# Isolation note: when running from within a distrobox container,
# services are accessible via distrobox-host-exec if needed.
# Direct localhost access works when ports are mapped to the host.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_PATH="${VENV_PATH:-${PROJECT_ROOT}/pipeline/.venv}"

if [[ ! -f "${VENV_PATH}/bin/activate" ]]; then
    echo "ERROR: Virtual environment not found at ${VENV_PATH}" >&2
    echo "Run: cd pipeline && python -m venv .venv && pip install -e ." >&2
    exit 1
fi

# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"

export CSS_BASE_URL="${CSS_BASE_URL:-http://localhost:3000}"
export OXIGRAPH_URL="${OXIGRAPH_URL:-http://localhost:7878}"
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export OPENCLAW_BASE_URL="${OPENCLAW_BASE_URL:-http://localhost:8000}"
export OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-}"

echo "Running troll comprehensive adversarial test suite..." >&2
echo "  CSS_BASE_URL: ${CSS_BASE_URL}" >&2
echo "  OXIGRAPH_URL: ${OXIGRAPH_URL}" >&2
echo "  QDRANT_URL: ${QDRANT_URL}" >&2
echo "  OPENCLAW_BASE_URL: ${OPENCLAW_BASE_URL}" >&2

# Run comprehensive orchestrator and generate reports
python "${PROJECT_ROOT}/agents/troll-adversary/attacks/run_comprehensive.py"
