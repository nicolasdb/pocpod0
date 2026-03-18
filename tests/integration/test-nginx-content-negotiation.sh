#!/bin/bash
# Integration test: Nginx content negotiation (Story 1.2 — Spike PASS verification)
#
# Verifies that CSS 7 content negotiation works end-to-end through Nginx.
# Run after `docker-compose up` (or equivalent) with all services healthy.
#
# Usage:
#   ./tests/integration/test-nginx-content-negotiation.sh
#   NGINX_PORT=9090 ./tests/integration/test-nginx-content-negotiation.sh
#
# Isolation note: when running inside distrobox, uses distrobox-host-exec
# to reach host-side containers (podman/docker are on the host, not in the box).

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via env vars if needed
# ---------------------------------------------------------------------------
NGINX_PORT="${NGINX_HTTP_PORT:-${NGINX_PORT:-8080}}"
CSS_PORT="${CSS_PORT:-3000}"
NGINX_BASE="http://localhost:${NGINX_PORT}"
CSS_BASE="http://localhost:${CSS_PORT}"
TEST_PATH="/.meta"   # Public metadata endpoint — no auth required for header negotiation

# ---------------------------------------------------------------------------
# Distrobox detection (same pattern as scripts/setup.sh)
# ---------------------------------------------------------------------------
CURL_CMD="curl"
if [[ -f /.dockerenv ]] || [[ -f /run/.containerenv ]]; then
    if command -v distrobox-host-exec &>/dev/null; then
        CURL_CMD="distrobox-host-exec curl"
    fi
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS=0
FAIL=0

pass() { echo "  PASS  $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }

check_content_type() {
    local label="$1"
    local url="$2"
    local accept="$3"
    local expected="$4"

    actual=$(${CURL_CMD} -sI -H "Accept: ${accept}" "${url}" 2>/dev/null \
        | grep -i "^content-type:" | tr -d '\r' | sed 's/content-type: //i')

    if [[ "${actual}" == *"${expected}"* ]]; then
        pass "${label} → ${actual}"
    else
        fail "${label} — expected '${expected}', got '${actual:-<no header>}'"
    fi
}

check_header_present() {
    local label="$1"
    local url="$2"
    local accept="$3"
    local header="$4"

    present=$(${CURL_CMD} -sI -H "Accept: ${accept}" "${url}" 2>/dev/null \
        | grep -i "^${header}:" | tr -d '\r')

    if [[ -n "${present}" ]]; then
        pass "${label} — ${present}"
    else
        fail "${label} — header '${header}' missing from response"
    fi
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
echo ""
echo "Nginx Content Negotiation — Integration Tests"
echo "  Nginx: ${NGINX_BASE}"
echo "  CSS:   ${CSS_BASE}"
echo "  curl:  ${CURL_CMD}"
echo ""

echo "[ CSS direct — baseline ]"
check_content_type "CSS Turtle"   "${CSS_BASE}${TEST_PATH}" "text/turtle"          "text/turtle"
check_content_type "CSS JSON-LD"  "${CSS_BASE}${TEST_PATH}" "application/ld+json"  "application/ld+json"

echo ""
echo "[ Nginx proxy — content negotiation ]"
check_content_type "Nginx Turtle"  "${NGINX_BASE}${TEST_PATH}" "text/turtle"         "text/turtle"
check_content_type "Nginx JSON-LD" "${NGINX_BASE}${TEST_PATH}" "application/ld+json" "application/ld+json"

echo ""
echo "[ Solid headers preserved through Nginx ]"
check_header_present "Link header"         "${NGINX_BASE}${TEST_PATH}" "text/turtle" "Link"
check_header_present "Vary header"         "${NGINX_BASE}${TEST_PATH}" "text/turtle" "Vary"
check_header_present "Access-Control-Expose-Headers (Solid headers surfaced)" "${NGINX_BASE}${TEST_PATH}" "text/turtle" "Access-Control-Expose-Headers"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
TOTAL=$((PASS + FAIL))
echo "Results: ${PASS}/${TOTAL} passed"
if [[ ${FAIL} -gt 0 ]]; then
    echo "FAILED — ${FAIL} test(s) did not pass"
    exit 1
fi
echo "OK"
