#!/usr/bin/env bash
# verify-round-trip.sh — Standalone round-trip xAPI recovery verification
#
# Runs the Story 2.4 integration test suite against a populated
# Oxigraph + CSS environment. Outputs structured JSON summary to stdout.
#
# Prerequisites:
#   - Oxigraph running at http://localhost:7878
#   - CSS running at http://localhost:3000 (pods populated by pipeline)
#   - Virtual environment at .venv/
#
# Usage:
#   ./scripts/verify-round-trip.sh
#   OXIGRAPH_BASE_URL=http://localhost:7878 CSS_BASE_URL=http://localhost:3000 ./scripts/verify-round-trip.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$REPO_ROOT/.venv"

# Activate venv
if [[ -f "$VENV/bin/activate" ]]; then
    source "$VENV/bin/activate"
else
    echo '{"event":"verify.error","level":"error","details":{"error":"venv not found at .venv/"}}' >&2
    exit 1
fi

export PYTHONPATH="$REPO_ROOT/pipeline/src:${PYTHONPATH:-}"
export CSS_BASE_URL="${CSS_BASE_URL:-http://localhost:3000}"
export OXIGRAPH_BASE_URL="${OXIGRAPH_BASE_URL:-http://localhost:7878}"

# Run pytest on round-trip tests, capture JSON output
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
START_MS=$(($(date +%s%N) / 1000000))

REPORT_FILE="/tmp/round-trip-report-$$.json"

set +e
python -m pytest \
    "$REPO_ROOT/pipeline/tests/integration/test_round_trip_recovery.py" \
    -v --tb=short \
    --json-report --json-report-file="$REPORT_FILE" \
    2>&1
PYTEST_EXIT=${?}
set -e

END_MS=$(($(date +%s%N) / 1000000))
ELAPSED_MS=$((END_MS - START_MS))

# Parse results from pytest JSON report if available
if [[ -f "$REPORT_FILE" ]]; then
    TOTAL=$(python3 -c "import json; d=json.load(open('$REPORT_FILE')); print(d['summary'].get('total', 0))" 2>/dev/null || echo 0)
    PASSED=$(python3 -c "import json; d=json.load(open('$REPORT_FILE')); print(d['summary'].get('passed', 0))" 2>/dev/null || echo 0)
    FAILED=$(python3 -c "import json; d=json.load(open('$REPORT_FILE')); print(d['summary'].get('failed', 0) + d['summary'].get('error', 0))" 2>/dev/null || echo 0)
    SKIPPED=$(python3 -c "import json; d=json.load(open('$REPORT_FILE')); print(d['summary'].get('skipped', 0))" 2>/dev/null || echo 0)
    rm -f "$REPORT_FILE"
    # Guard: if pytest passed but reported 0 tests, the JSON plugin may be missing
    if [[ "$PYTEST_EXIT" -eq 0 && "$TOTAL" -eq 0 ]]; then
        echo '{"event":"verify.error","level":"error","details":{"error":"pytest-json-report plugin missing or produced no output — install pytest-json-report"}}' >&2
        exit 2
    fi
else
    # No report file: pytest binary not found or crashed before writing output
    echo '{"event":"verify.error","level":"error","details":{"error":"No JSON report produced — check that pytest and pytest-json-report are installed in the venv"}}' >&2
    exit 2
fi

PERSONAS_JSON='["ayoub","claire-student-1","claire-student-2","fatima-child-1","fatima-child-2"]'

python3 - <<EOF
import json
result = {
    "event": "round_trip.verification.complete",
    "timestamp": "$TIMESTAMP",
    "details": {
        "total_tested": $TOTAL,
        "passed": $PASSED,
        "failed": $FAILED,
        "skipped": $SKIPPED,
        "personas_verified": $PERSONAS_JSON,
        "sample_recovery_ms": $ELAPSED_MS,
        "pytest_exit_code": $PYTEST_EXIT,
        "status": "PASS" if $PYTEST_EXIT == 0 else "FAIL"
    }
}
print(json.dumps(result, indent=2))
EOF

exit $PYTEST_EXIT
