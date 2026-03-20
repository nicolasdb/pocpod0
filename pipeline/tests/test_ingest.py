"""Tests for ingest.py — conversion, lossless recovery, log+continue, summary counts."""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pocpod0_pipeline.ingest import (
    _pod_for_statement,
    _resource_path,
    load_statements,
    process_statement,
    run_pipeline,
)

POCPOD0 = "https://poc-pod0.edu/vocab/"

GOOD_STMT = {
    "id": str(uuid.uuid4()),
    "actor": {
        "objectType": "Agent",
        "account": {
            "homePage": "http://localhost:3000",
            "name": "http://localhost:3000/ayoub/profile/card#me",
        },
        "name": "Ayoub",
    },
    "verb": {
        "id": "http://adlnet.gov/expapi/verbs/completed",
        "display": {"en-US": "completed"},
    },
    "object": {
        "objectType": "Activity",
        "id": f"{POCPOD0}activity-math-assessment",
        "definition": {
            "name": {"en-US": "Math Assessment"},
            "type": "http://adlnet.gov/expapi/activities/assessment",
        },
    },
    "timestamp": "2025-10-01T09:00:00Z",
    "_pocpod0_pod": "ayoub",
}

MALFORMED_STMT = {"id": "bad", "actor": {}, "verb": {}, "object": {}}


# ---------------------------------------------------------------------------
# Single statement: converts to valid Turtle (dry_run)
# ---------------------------------------------------------------------------

def test_single_statement_converts_to_turtle():
    ok = process_statement(GOOD_STMT, css_base="http://localhost:3000", dry_run=True)
    assert ok is True


def test_malformed_statement_does_not_crash():
    # Should return False (skipped due to no pod resolution) without raising
    ok = process_statement(MALFORMED_STMT, css_base="http://localhost:3000", dry_run=True)
    assert ok is False


# ---------------------------------------------------------------------------
# Lossless: original xAPI recoverable from Turtle
# ---------------------------------------------------------------------------

def test_lossless_recovery():
    from pocpod0_pipeline.oslo_mapper import xapi_to_rdf
    from rdflib import Namespace, URIRef

    VOCAB = Namespace("https://poc-pod0.edu/vocab/")
    stmt_id = GOOD_STMT["id"]
    g = xapi_to_rdf(GOOD_STMT, pod_resource_uri="http://localhost:3000/ayoub/test.ttl")

    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    originals = list(g.objects(stmt_uri, VOCAB.originalXapiJson))
    assert len(originals) == 1

    recovered = json.loads(str(originals[0]))
    assert recovered["id"] == stmt_id
    assert recovered["verb"]["id"] == "http://adlnet.gov/expapi/verbs/completed"
    # Internal hint should be stripped
    assert "_pocpod0_pod" not in recovered


# ---------------------------------------------------------------------------
# log+continue: pipeline survives malformed input
# ---------------------------------------------------------------------------

def test_pipeline_survives_malformed_input():
    with tempfile.TemporaryDirectory() as tmp:
        input_dir = Path(tmp)
        mixed = [GOOD_STMT, MALFORMED_STMT, GOOD_STMT]
        (input_dir / "test.json").write_text(json.dumps(mixed))

        summary = run_pipeline(input_dir, css_base="http://localhost:3000", dry_run=True)

    assert summary["total"] == 3
    assert summary["succeeded"] >= 1
    # Pipeline must not raise; failed + succeeded = total (minus skipped)
    assert summary["succeeded"] + summary["failed"] == summary["total"]


# ---------------------------------------------------------------------------
# Summary counts are accurate
# ---------------------------------------------------------------------------

def test_summary_counts_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        input_dir = Path(tmp)
        stmts = [GOOD_STMT, GOOD_STMT]
        (input_dir / "test.json").write_text(json.dumps(stmts))

        summary = run_pipeline(input_dir, css_base="http://localhost:3000", dry_run=True)

    assert summary["total"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# Pod resolution helpers
# ---------------------------------------------------------------------------

def test_pod_from_routing_hint():
    stmt = dict(GOOD_STMT)
    assert _pod_for_statement(stmt) == "ayoub"


def test_pod_from_webid_fallback():
    stmt = {**GOOD_STMT}
    del stmt["_pocpod0_pod"]
    assert _pod_for_statement(stmt) == "ayoub"


def test_pod_none_for_missing_webid():
    stmt = {
        "id": str(uuid.uuid4()),
        "actor": {"objectType": "Agent"},
        "verb": {"id": "http://adlnet.gov/expapi/verbs/completed"},
        "object": {"id": "http://example.com/act"},
    }
    assert _pod_for_statement(stmt) is None


# ---------------------------------------------------------------------------
# load_statements ignores manifest file
# ---------------------------------------------------------------------------

def test_load_statements_ignores_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "stmts.json").write_text(json.dumps([GOOD_STMT]))
        (d / "troll-load-manifest.json").write_text(json.dumps({"total": 1}))

        stmts = load_statements(d)
    assert len(stmts) == 1
