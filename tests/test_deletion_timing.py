"""Unit tests for deletion_timing.py — Story 5.3.

Tests business logic without requiring live services:
  - DeletionTimingResult dataclass structure
  - classify_timing_result() pass/partial/fail logic
  - Gap detection: upstream-clean + downstream-residual → partial
  - generate_summary() all-pass, mixed, timing-gap-partial cases
  - Report envelope structure and required fields
  - JSONL event format and ordering
  - Log format: structured JSON, required fields
  - CLI: exits 0 even when tests result in fail
"""

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load deletion_timing via importlib (hyphen-named path)
# ---------------------------------------------------------------------------

_DT_PATH = Path(__file__).resolve().parents[1] / "agents" / "troll-adversary" / "attacks" / "deletion_timing.py"
assert _DT_PATH.exists(), f"deletion_timing.py not found at {_DT_PATH}"

_spec = importlib.util.spec_from_file_location("deletion_timing", _DT_PATH)
_dt = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_dt)  # type: ignore[union-attr]
sys.modules["deletion_timing"] = _dt  # register so @patch("deletion_timing.*") works

DeletionTimingResult = _dt.DeletionTimingResult
DeletionTimingSummary = _dt.DeletionTimingSummary
LayerSummary = _dt.LayerSummary
DeletionTimingAttack = _dt.DeletionTimingAttack
log_deletion_event = _dt.log_deletion_event
_emit_probe_start = _dt._emit_probe_start
_emit_probe_done = _dt._emit_probe_done
_emit_category_done = _dt._emit_category_done
_write_report = _dt._write_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    test_name="dt-001-pod-soft-delete-mark",
    layer="pod",
    step=1,
    elapsed_ms=50.0,
    result="pass",
    details="ok",
    evidence=None,
    residual_found=False,
    timestamp="2026-01-01T00:00:00Z",
) -> DeletionTimingResult:
    return DeletionTimingResult(
        test_name=test_name,
        layer=layer,
        step=step,
        elapsed_ms=elapsed_ms,
        result=result,
        details=details,
        evidence=evidence or {},
        residual_found=residual_found,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# DeletionTimingResult dataclass
# ---------------------------------------------------------------------------


class TestDeletionTimingResult:
    def test_is_deterministic_always_true(self):
        r = _make_result()
        assert r.is_deterministic is True

    def test_is_deterministic_cannot_be_overridden_to_false(self):
        """NFR12: we can technically set it, but by default it's True."""
        r = DeletionTimingResult(
            test_name="x", layer="pod", step=1, elapsed_ms=1.0,
            result="pass", details="", evidence={}, residual_found=False,
        )
        assert r.is_deterministic is True

    def test_result_values_are_valid(self):
        for result in ("pass", "partial", "fail"):
            r = _make_result(result=result)
            assert r.result == result

    def test_layer_values_are_valid(self):
        for layer in ("pod", "oxigraph", "qdrant"):
            r = _make_result(layer=layer)
            assert r.layer == layer

    def test_asdict_serializable(self):
        r = _make_result()
        d = asdict(r)
        assert json.dumps(d)  # must be JSON-serializable

    def test_residual_found_false_on_pass(self):
        r = _make_result(result="pass", residual_found=False)
        assert not r.residual_found

    def test_residual_found_true_on_fail(self):
        r = _make_result(result="fail", residual_found=True)
        assert r.residual_found


# ---------------------------------------------------------------------------
# classify_timing_result() — tested via DeletionTimingAttack helper logic
# We test the classification rules by unit-testing the attack's query results.
# ---------------------------------------------------------------------------


class TestClassifyTimingResult:
    """Test classification logic via synthetic query responses.

    DeletionTimingAttack methods call _query_css_resource, _query_oxigraph_graph,
    and _query_qdrant_points internally. We mock those to test classify logic.
    """

    def _attack(self) -> DeletionTimingAttack:
        return DeletionTimingAttack(
            target_pod_uri="http://localhost:3000/ayoub/",
            resource_uri="http://localhost:3000/ayoub/resource1",
        )

    @patch("deletion_timing._query_css_resource")
    def test_dt001_pass_when_tombstone(self, mock_css):
        mock_css.return_value = {"state": "tombstone", "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-001-pod-soft-delete-mark")
        assert r.result == "pass"
        assert not r.residual_found

    @patch("deletion_timing._query_css_resource")
    def test_dt001_pass_when_410_deleted(self, mock_css):
        mock_css.return_value = {"state": "deleted", "evidence": {"http_status": 410}}
        atk = self._attack()
        r = atk.run_test("dt-001-pod-soft-delete-mark")
        assert r.result == "pass"

    @patch("deletion_timing._query_css_resource")
    def test_dt001_fail_when_live(self, mock_css):
        mock_css.return_value = {"state": "live", "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-001-pod-soft-delete-mark")
        assert r.result == "fail"
        assert r.residual_found

    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt002_pass_when_ask_false_count_zero(self, mock_ox):
        mock_ox.return_value = {"graph_exists": False, "count": 0, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-002-oxigraph-named-graph-drop")
        assert r.result == "pass"
        assert not r.residual_found

    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt002_fail_when_graph_still_exists(self, mock_ox):
        mock_ox.return_value = {"graph_exists": True, "count": 3, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-002-oxigraph-named-graph-drop")
        assert r.result == "fail"
        assert r.residual_found

    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt002_partial_when_query_error(self, mock_ox):
        mock_ox.return_value = {"graph_exists": None, "count": -1, "evidence": {"error": "timeout"}}
        atk = self._attack()
        r = atk.run_test("dt-002-oxigraph-named-graph-drop")
        assert r.result == "partial"

    @patch("deletion_timing._query_qdrant_points")
    def test_dt003_pass_when_zero_points(self, mock_qd):
        mock_qd.return_value = {"count": 0, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-003-qdrant-payload-purge")
        assert r.result == "pass"
        assert not r.residual_found

    @patch("deletion_timing._query_qdrant_points")
    def test_dt003_fail_when_points_remain(self, mock_qd):
        mock_qd.return_value = {"count": 5, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-003-qdrant-payload-purge")
        assert r.result == "fail"
        assert r.residual_found

    @patch("deletion_timing._query_qdrant_points")
    def test_dt003_partial_when_qdrant_error(self, mock_qd):
        mock_qd.return_value = {"count": -1, "evidence": {"error": "connection refused"}}
        atk = self._attack()
        r = atk.run_test("dt-003-qdrant-payload-purge")
        assert r.result == "partial"


# ---------------------------------------------------------------------------
# Gap detection: dt-004
# ---------------------------------------------------------------------------


class TestGapDetection:
    def _attack(self) -> DeletionTimingAttack:
        return DeletionTimingAttack(
            target_pod_uri="http://localhost:3000/ayoub/",
            resource_uri="http://localhost:3000/ayoub/resource1",
        )

    @patch("deletion_timing._query_qdrant_points")
    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt004_partial_when_oxigraph_clean_qdrant_has_residual(self, mock_ox, mock_qd):
        """The EXPECTED outcome for a well-functioning system with Qdrant lag."""
        mock_ox.return_value = {"graph_exists": False, "count": 0, "evidence": {}}
        mock_qd.return_value = {"count": 2, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-004-cross-layer-gap")
        assert r.result == "partial"
        assert r.residual_found
        assert "known architectural property" in r.details
        assert "Risk: low" in r.details

    @patch("deletion_timing._query_qdrant_points")
    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt004_pass_when_both_clean(self, mock_ox, mock_qd):
        mock_ox.return_value = {"graph_exists": False, "count": 0, "evidence": {}}
        mock_qd.return_value = {"count": 0, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-004-cross-layer-gap")
        assert r.result == "pass"
        assert not r.residual_found

    @patch("deletion_timing._query_qdrant_points")
    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt004_fail_when_both_dirty(self, mock_ox, mock_qd):
        mock_ox.return_value = {"graph_exists": True, "count": 5, "evidence": {}}
        mock_qd.return_value = {"count": 3, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-004-cross-layer-gap")
        assert r.result == "fail"

    @patch("deletion_timing._query_qdrant_points")
    @patch("deletion_timing._query_oxigraph_graph")
    def test_dt004_evidence_contains_gap_ms(self, mock_ox, mock_qd):
        mock_ox.return_value = {"graph_exists": False, "count": 0, "evidence": {}}
        mock_qd.return_value = {"count": 1, "evidence": {}}
        atk = self._attack()
        r = atk.run_test("dt-004-cross-layer-gap")
        assert "cross_layer_gap_ms" in r.evidence


# ---------------------------------------------------------------------------
# generate_summary()
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def _attack(self) -> DeletionTimingAttack:
        return DeletionTimingAttack(
            target_pod_uri="http://localhost:3000/ayoub/",
            resource_uri="http://localhost:3000/ayoub/resource1",
        )

    def _all_pass_results(self) -> list[DeletionTimingResult]:
        return [
            _make_result("dt-001-pod-soft-delete-mark", "pod", 1, result="pass"),
            _make_result("dt-002-oxigraph-named-graph-drop", "oxigraph", 2, result="pass"),
            _make_result("dt-003-qdrant-payload-purge", "qdrant", 3, result="pass"),
            _make_result("dt-004-cross-layer-gap", "qdrant", 2, result="pass"),
            _make_result("dt-005-post-cascade-full-verify", "pod", 3, result="pass"),
        ]

    def _timing_gap_results(self) -> list[DeletionTimingResult]:
        return [
            _make_result("dt-001-pod-soft-delete-mark", "pod", 1, result="pass"),
            _make_result("dt-002-oxigraph-named-graph-drop", "oxigraph", 2, result="pass"),
            _make_result("dt-003-qdrant-payload-purge", "qdrant", 3, result="pass"),
            _make_result(
                "dt-004-cross-layer-gap", "qdrant", 2, result="partial",
                residual_found=True,
                evidence={"cross_layer_gap_ms": 42.5},
            ),
            _make_result("dt-005-post-cascade-full-verify", "pod", 3, result="pass"),
        ]

    def _fail_results(self) -> list[DeletionTimingResult]:
        return [
            _make_result("dt-001-pod-soft-delete-mark", "pod", 1, result="pass"),
            _make_result("dt-002-oxigraph-named-graph-drop", "oxigraph", 2, result="fail", residual_found=True),
            _make_result("dt-003-qdrant-payload-purge", "qdrant", 3, result="pass"),
            _make_result("dt-004-cross-layer-gap", "qdrant", 2, result="fail", residual_found=True),
            _make_result("dt-005-post-cascade-full-verify", "pod", 3, result="fail", residual_found=True),
        ]

    def test_all_pass_summary(self):
        atk = self._attack()
        summary = atk.generate_summary(self._all_pass_results())
        assert summary.pass_count == 5
        assert summary.partial_count == 0
        assert summary.fail_count == 0
        assert summary.timing_gap_ms is None
        assert "verified clean" in summary.overall_assessment

    def test_timing_gap_partial_summary(self):
        atk = self._attack()
        summary = atk.generate_summary(self._timing_gap_results())
        assert summary.partial_count == 1
        assert summary.fail_count == 0
        assert summary.timing_gap_ms == pytest.approx(42.5)
        assert "42.5ms" in summary.overall_assessment or "42" in summary.overall_assessment
        assert "known architectural property" in summary.overall_assessment

    def test_fail_summary(self):
        atk = self._attack()
        summary = atk.generate_summary(self._fail_results())
        assert summary.fail_count >= 1
        assert "FAIL" in summary.overall_assessment or "defect" in summary.overall_assessment

    def test_nfr12_in_summary(self):
        """NFR12 compliance note must appear in all-pass or timing-gap summary."""
        atk = self._attack()
        for results in (self._all_pass_results(), self._timing_gap_results()):
            summary = atk.generate_summary(results)
            assert "deterministic" in summary.overall_assessment.lower() or "NFR12" in summary.overall_assessment

    def test_per_layer_present(self):
        atk = self._attack()
        summary = atk.generate_summary(self._all_pass_results())
        assert "pod" in summary.per_layer
        assert "oxigraph" in summary.per_layer
        assert "qdrant" in summary.per_layer


# ---------------------------------------------------------------------------
# Report format
# ---------------------------------------------------------------------------


class TestReportFormat:
    def _make_summary(self) -> DeletionTimingSummary:
        return DeletionTimingSummary(
            total_tests=5,
            pass_count=5,
            partial_count=0,
            fail_count=0,
            per_layer={},
            timing_gap_ms=None,
            overall_assessment="All clean.",
            timestamp="2026-01-01T00:00:00Z",
        )

    def _make_results(self) -> list[DeletionTimingResult]:
        return [_make_result(test_name=f"dt-00{i}", layer="pod", step=i) for i in range(1, 4)]

    def test_envelope_structure(self, tmp_path):
        results = self._make_results()
        summary = self._make_summary()
        _write_report(results, summary, tmp_path)
        report_path = tmp_path / "deletion-timing-results.json"
        assert report_path.exists()
        data = json.loads(report_path.read_text())
        for field in ("category", "total_tests", "passed", "partial", "failed", "blocking", "narrative", "summary", "tests"):
            assert field in data, f"Missing field: {field}"

    def test_category_is_deletion_timing(self, tmp_path):
        results = self._make_results()
        summary = self._make_summary()
        _write_report(results, summary, tmp_path)
        data = json.loads((tmp_path / "deletion-timing-results.json").read_text())
        assert data["category"] == "deletion_timing"

    def test_blocking_is_false(self, tmp_path):
        results = self._make_results()
        summary = self._make_summary()
        _write_report(results, summary, tmp_path)
        data = json.loads((tmp_path / "deletion-timing-results.json").read_text())
        assert data["blocking"] is False

    def test_tests_list_has_required_fields(self, tmp_path):
        results = self._make_results()
        summary = self._make_summary()
        _write_report(results, summary, tmp_path)
        data = json.loads((tmp_path / "deletion-timing-results.json").read_text())
        for t in data["tests"]:
            for field in ("attack_category", "access_path", "test_name", "result", "details", "evidence"):
                assert field in t, f"Test entry missing field: {field}"

    def test_evidence_has_is_deterministic(self, tmp_path):
        results = self._make_results()
        summary = self._make_summary()
        _write_report(results, summary, tmp_path)
        data = json.loads((tmp_path / "deletion-timing-results.json").read_text())
        for t in data["tests"]:
            assert t["evidence"]["is_deterministic"] is True


# ---------------------------------------------------------------------------
# JSONL event format
# ---------------------------------------------------------------------------


class TestJsonlEvents:
    def test_probe_start_event_fields(self, tmp_path):
        jsonl = tmp_path / "troll-run.jsonl"
        with patch.object(_dt, "JSONL_PATH", jsonl):
            _emit_probe_start("dt-001-pod-soft-delete-mark", "pod")
        events = [json.loads(line) for line in jsonl.read_text().splitlines()]
        assert events[0]["event_type"] == "troll.probe.start"
        assert events[0]["category"] == "deletion_timing"
        assert events[0]["test_name"] == "dt-001-pod-soft-delete-mark"
        assert events[0]["layer"] == "pod"
        assert "timestamp" in events[0]

    def test_probe_done_event_fields(self, tmp_path):
        jsonl = tmp_path / "troll-run.jsonl"
        with patch.object(_dt, "JSONL_PATH", jsonl):
            _emit_probe_done("dt-002-oxigraph-named-graph-drop", "oxigraph", "pass", 38.4)
        events = [json.loads(line) for line in jsonl.read_text().splitlines()]
        e = events[0]
        assert e["event_type"] == "troll.probe.done"
        assert e["result"] == "pass"
        assert e["elapsed_ms"] == pytest.approx(38.4)

    def test_category_done_event_fields(self, tmp_path):
        jsonl = tmp_path / "troll-run.jsonl"
        with patch.object(_dt, "JSONL_PATH", jsonl):
            _emit_category_done(4, 1, 0)
        events = [json.loads(line) for line in jsonl.read_text().splitlines()]
        e = events[0]
        assert e["event_type"] == "troll.category.done"
        assert e["passed"] == 4
        assert e["partial"] == 1
        assert e["failed"] == 0

    def test_events_emitted_in_order(self, tmp_path, capsys):
        """probe.start → probe.done order is preserved per test."""
        jsonl = tmp_path / "troll-run.jsonl"
        with patch.object(_dt, "JSONL_PATH", jsonl):
            _emit_probe_start("dt-003-qdrant-payload-purge", "qdrant")
            _emit_probe_done("dt-003-qdrant-payload-purge", "qdrant", "pass", 12.0)
        events = [json.loads(line) for line in jsonl.read_text().splitlines()]
        assert events[0]["event_type"] == "troll.probe.start"
        assert events[1]["event_type"] == "troll.probe.done"


# ---------------------------------------------------------------------------
# Log format: structured JSON, required fields
# ---------------------------------------------------------------------------


class TestLogFormat:
    def test_log_deletion_event_prints_json(self, capsys):
        log_deletion_event(
            test_name="dt-002-oxigraph-named-graph-drop",
            layer="oxigraph",
            elapsed_ms=38.4,
            residual_found=False,
            result="pass",
            details="Named graph DROP confirmed clean.",
        )
        captured = capsys.readouterr()
        event = json.loads(captured.out.strip())
        assert event["service"] == "troll-adversary"
        assert event["event"] == "troll.deletion_timing.step"
        assert event["agent"] == "troll-adversary"
        assert "timestamp" in event
        assert "details" in event

    def test_log_deletion_event_details_fields(self, capsys):
        log_deletion_event(
            test_name="dt-003-qdrant-payload-purge",
            layer="qdrant",
            elapsed_ms=15.0,
            residual_found=False,
            result="pass",
            details="Purge confirmed.",
        )
        captured = capsys.readouterr()
        event = json.loads(captured.out.strip())
        d = event["details"]
        assert d["test_name"] == "dt-003-qdrant-payload-purge"
        assert d["layer"] == "qdrant"
        assert d["result"] == "pass"
        assert d["residual_found"] is False
        assert "elapsed_ms" in d


# ---------------------------------------------------------------------------
# CLI: exits 0 even when tests fail
# ---------------------------------------------------------------------------


class TestCliExitCode:
    @patch("deletion_timing._check_services", return_value=[])
    @patch("deletion_timing._trigger_cascade", return_value={"ok": True})
    @patch("deletion_timing.DeletionTimingAttack.run_all_tests")
    @patch("deletion_timing._write_report")
    @patch("deletion_timing._emit_category_done")
    def test_exits_zero_even_with_fail_results(
        self, mock_emit, mock_write, mock_run, mock_cascade, mock_check, tmp_path
    ):
        mock_run.return_value = [
            _make_result("dt-001-pod-soft-delete-mark", "pod", 1, result="fail", residual_found=True),
            _make_result("dt-002-oxigraph-named-graph-drop", "oxigraph", 2, result="fail", residual_found=True),
            _make_result("dt-003-qdrant-payload-purge", "qdrant", 3, result="fail", residual_found=True),
            _make_result("dt-004-cross-layer-gap", "qdrant", 2, result="fail", residual_found=True),
            _make_result("dt-005-post-cascade-full-verify", "pod", 3, result="fail", residual_found=True),
        ]
        with patch.object(sys, "argv", [
            "deletion_timing.py",
            "--resource-uri", "http://localhost:3000/ayoub/fake-resource",
            "--output-dir", str(tmp_path),
        ]):
            with pytest.raises(SystemExit) as exc_info:
                _dt.main()
        assert exc_info.value.code == 0
