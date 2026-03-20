#!/usr/bin/env bash
# Run the xAPI-OSLO RDF ingestion pipeline.
# Activates the pipeline venv, generates synthetic data, then ingests into CSS Pods.
#
# Usage:
#   ./scripts/run-pipeline.sh [--dry-run] [--count N] [--input-dir PATH]
#
# Environment:
#   CSS_BASE_URL  - CSS base URL (default: http://localhost:3000)
#   INPUT_DIR     - Override input directory (default: data/synthetic/)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIPELINE_DIR="$REPO_ROOT/pipeline"
VENV="$PIPELINE_DIR/.venv"

export CSS_BASE_URL="${CSS_BASE_URL:-http://localhost:3000}"

DRY_RUN=""
TROLL_COUNT=5000
INPUT_DIR="${INPUT_DIR:-$REPO_ROOT/data/synthetic}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    --count)   TROLL_COUNT="$2"; shift 2 ;;
    --input-dir) INPUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -d "$VENV" ]]; then
  echo "ERROR: venv not found at $VENV. Run: cd $PIPELINE_DIR && python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

echo "=== Step 1: Generate scenario dataset ==="
python -m pocpod0_pipeline.generate_scenarios

echo "=== Step 2: Generate troll load dataset (count=$TROLL_COUNT) ==="
python -m pocpod0_pipeline.generate_troll_load --count "$TROLL_COUNT"

echo "=== Step 3: Ingest into CSS Pods ==="
python -m pocpod0_pipeline.ingest \
  --input-dir "$INPUT_DIR" \
  --css-base-url "$CSS_BASE_URL" \
  $DRY_RUN

echo "=== Step 4: Load RDF graph into Oxigraph ==="
OXIGRAPH_BASE_URL="${OXIGRAPH_BASE_URL:-http://localhost:7878}"
python -m pocpod0_pipeline.load_graph \
  --css-base-url "$CSS_BASE_URL" \
  --oxigraph-url "$OXIGRAPH_BASE_URL" \
  --load-schema

echo "=== Pipeline complete ==="
