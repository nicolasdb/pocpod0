#!/usr/bin/env bash
# Demo: Ayoub Age-Based Sovereignty Transition (Story 5.1)
#
# Narrated walkthrough of the full governance transition:
#   1. Show current ACL state (guardian has read access)
#   2. Execute age-based transition (governance_transition.py)
#   3. Show updated ACL state (guardian revoked, Ayoub sole owner)
#   4. Attempt guardian ACL mutation and confirm denial
#   5. Display JSONL consent events logged to data/consent-events.jsonl
#
# Isolation: CSS server accessed via HTTP to localhost:3000 (reachable directly from distrobox).
# distrobox-host-exec is not needed here — no podman exec calls are made.
# CSS server must be running before executing this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Activate Python venv
VENV_PATH="${PROJECT_ROOT}/.venv"
if [[ ! -f "${VENV_PATH}/bin/activate" ]]; then
  echo "❌ Virtualenv not found at ${VENV_PATH}. Run: python -m venv .venv && pip install -e pipeline/"
  exit 1
fi
# shellcheck disable=SC1091
source "${VENV_PATH}/bin/activate"

# Load env
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  # Export only CSS-related vars, skip Docker-internal overrides
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

# Use CSS_CONNECT_URL for host access (distrobox can reach localhost:3000)
export CSS_CONNECT_URL="${CSS_CONNECT_URL:-http://localhost:3000}"
export CSS_IDENTIFIER_URL="${CSS_IDENTIFIER_URL:-http://localhost:3000}"

AYOUB_DOB="${AYOUB_DOB:-2010-01-15}"     # 16 years old as of 2026
MIN_AGE="${MIN_AGE:-16}"
GUARDIAN_WEBID="${GUARDIAN_WEBID:-http://localhost:3000/guardian/profile/card#me}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Ayoub — Age-Based Sovereignty Transition Demo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "CSS endpoint: ${CSS_CONNECT_URL}"
echo "Ayoub DOB:    ${AYOUB_DOB}  (min age: ${MIN_AGE})"
echo ""

# ─── Step 1: Show current ACL state ──────────────────────────────────────────
echo "Step 1: Current ACL state (before transition)"
echo "─────────────────────────────────────────────"
AGENT_POD_OWNERSHIP=ayoub AGENT_ID=demo \
  python "${PROJECT_ROOT}/agents/skills/acl-manage/handler.py" \
    --action view \
    --pod-name ayoub \
  | python -m json.tool
echo ""

# ─── Step 2: Execute age-based transition ────────────────────────────────────
echo "Step 2: Executing governance transition"
echo "─────────────────────────────────────────────"
echo "Checking eligibility: DOB=${AYOUB_DOB}, min_age=${MIN_AGE}"
python "${PROJECT_ROOT}/pipeline/src/pocpod0_pipeline/governance_transition.py" \
  --pod-name ayoub \
  --date-of-birth "${AYOUB_DOB}" \
  --min-age "${MIN_AGE}" \
  | python -m json.tool
echo ""

# ─── Step 3: Show updated ACL state ──────────────────────────────────────────
echo "Step 3: Updated ACL state (after transition — Ayoub is sole owner)"
echo "─────────────────────────────────────────────"
AGENT_POD_OWNERSHIP=ayoub AGENT_ID=demo \
  python "${PROJECT_ROOT}/agents/skills/acl-manage/handler.py" \
    --action view \
    --pod-name ayoub \
  | python -m json.tool
echo ""

# ─── Step 4: Guardian attempts ACL mutation — should be denied ───────────────
echo "Step 4: Former guardian attempts to grant themselves access (expect: denied)"
echo "─────────────────────────────────────────────"
# Guardian has AGENT_POD_OWNERSHIP=guardian (not ayoub) — denied by ownership check
AGENT_POD_OWNERSHIP=guardian AGENT_ID=guardian-demo \
  python "${PROJECT_ROOT}/agents/skills/acl-manage/handler.py" \
    --action grant \
    --pod-name ayoub \
    --identity "${GUARDIAN_WEBID}" \
    --role guardian \
    --access-level read \
  | python -m json.tool || true  # denial exits with code 1, continue demo
echo ""

# ─── Step 5: Display JSONL consent events ────────────────────────────────────
echo "Step 5: Consent events logged to data/consent-events.jsonl"
echo "─────────────────────────────────────────────"
JSONL_PATH="${PROJECT_ROOT}/data/consent-events.jsonl"
if [[ -f "${JSONL_PATH}" && -s "${JSONL_PATH}" ]]; then
  echo "Last 10 events:"
  tail -n 10 "${JSONL_PATH}" | while IFS= read -r line; do
    echo "${line}" | python -m json.tool
    echo "---"
  done
else
  echo "(no consent events recorded yet)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Demo complete. Ayoub's pod sovereignty is structural."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
