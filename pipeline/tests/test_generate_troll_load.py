"""Tests for generate_troll_load.py — AC4, AC3."""

import json
import tempfile
from pathlib import Path

import pytest

from pocpod0_pipeline.generate_troll_load import (
    TIER_DISTRIBUTION,
    generate_troll_load,
)


@pytest.fixture(scope="module")
def default_run():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_troll_load(5000, out, seed=42)
        stmts_file = out / "troll-load.json"
        manifest_file = out / "troll-load-manifest.json"
        with open(stmts_file) as f:
            stmts = json.load(f)
        with open(manifest_file) as f:
            manifest = json.load(f)
    return stmts, manifest


# ---------------------------------------------------------------------------
# AC4: Default run generates 5000 statements
# ---------------------------------------------------------------------------

def test_default_generates_5000(default_run):
    stmts, _ = default_run
    assert len(stmts) == 5000


# ---------------------------------------------------------------------------
# AC4: Custom --count respected
# ---------------------------------------------------------------------------

def test_custom_count():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_troll_load(250, out, seed=1)
        with open(out / "troll-load.json") as f:
            stmts = json.load(f)
        assert len(stmts) == 250


# ---------------------------------------------------------------------------
# AC4: WebID distribution roughly matches target percentages
# ---------------------------------------------------------------------------

def test_webid_tier_distribution_roughly_correct(default_run):
    _, manifest = default_run
    dist = manifest["webid_tier_distribution"]
    tolerance = 5.0  # ±5 percentage points

    targets = {tier: pct * 100 for tier, pct in TIER_DISTRIBUTION}
    for tier, target_pct in targets.items():
        actual_pct = dist[tier]["pct"]
        assert abs(actual_pct - target_pct) <= tolerance, (
            f"Tier {tier}: expected ~{target_pct}%, got {actual_pct}%"
        )


# ---------------------------------------------------------------------------
# AC3: All statements are structurally valid xAPI
# ---------------------------------------------------------------------------

def test_all_statements_valid_xapi(default_run):
    stmts, _ = default_run
    invalid = [
        s for s in stmts
        if not (
            s.get("actor")
            and s.get("verb", {}).get("id")
            and s.get("object", {}).get("id")
        )
    ]
    assert len(invalid) == 0, f"{len(invalid)} invalid troll statements"


def test_all_statements_have_id(default_run):
    stmts, _ = default_run
    missing = [s for s in stmts if not s.get("id")]
    assert len(missing) == 0


def test_all_statements_have_timestamp(default_run):
    stmts, _ = default_run
    missing = [s for s in stmts if not s.get("timestamp")]
    assert len(missing) == 0


# ---------------------------------------------------------------------------
# Manifest file generated with distribution stats
# ---------------------------------------------------------------------------

def test_manifest_has_required_fields(default_run):
    _, manifest = default_run
    assert "total_statements" in manifest
    assert "webid_tier_distribution" in manifest
    assert "verb_distribution" in manifest
    assert manifest["total_statements"] == 5000


def test_manifest_has_all_tiers(default_run):
    _, manifest = default_run
    dist = manifest["webid_tier_distribution"]
    for tier, _ in TIER_DISTRIBUTION:
        assert tier in dist, f"Missing tier in manifest: {tier}"
