#!/usr/bin/env bash
# Run troll adversary ACL enforcement test suite.
# Exits with non-zero code if any test has result "fail" (blocking per NFR5).
#
# Usage (from project root):
#   bash scripts/run-troll.sh
#
# Environment:
#   CSS_BASE_URL  CSS base URL (default: http://localhost:3000)
#   VENV_PATH     Path to virtual environment (default: pipeline/.venv)
#
# Isolation note: when running from within a distrobox container,
# CSS containers are accessible via distrobox-host-exec if needed.
# Direct localhost access works when CSS port is mapped to the host.

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

echo "Running troll ACL enforcement suite against ${CSS_BASE_URL}..." >&2

python "${PROJECT_ROOT}/agents/troll-adversary/attacks/acl_enforcement.py"
