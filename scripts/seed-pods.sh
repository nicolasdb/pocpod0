#!/usr/bin/env bash
# Provision all pods and apply ACL configuration
# This script activates the Python venv and calls the provisioning module

set -euo pipefail

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_DIR="$PROJECT_ROOT/pipeline"

# Check if venv exists
if [ ! -d "$PIPELINE_DIR/.venv" ]; then
    echo "❌ Python venv not found at $PIPELINE_DIR/.venv"
    echo "Please run: cd pipeline && python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

# Activate Python venv
source "$PIPELINE_DIR/.venv/bin/activate"

# Change to project root to ensure relative paths work
cd "$PROJECT_ROOT"

# Load environment variables if .env exists
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source ".env"
    set +a
fi

# Run provisioning
echo "Starting pod provisioning..."
python -m pocpod0_pipeline.provision_pods

echo ""
echo "✅ Pod provisioning complete."
