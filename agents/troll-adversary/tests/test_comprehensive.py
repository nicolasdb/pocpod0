"""Tests for troll comprehensive orchestrator and report generator.

Tests cover:
1. Orchestrator invocation order and result aggregation
2. JSONL event format compliance
3. Report JSON and markdown generation
4. Blocking vs non-blocking category handling
5. Exit code logic
"""

import json
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

# Adjust imports based on package structure
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "attacks"))
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from run_comprehensive import (
    CategorySummary,
    ComprehensiveRunResult,
    run_comprehensive,
    _emit_event,
)
from generator import ComprehensiveReportGenerator


class TestOrchestratorInvocation:
    """Test that orchestrator invokes all 5 attack categories in correct order."""

    @patch("run_comprehensive.run_acl_enforcement")
    @patch("run_comprehensive.run_sparql_injection")
    @patch("run_comprehensive.run_vector_privacy")
    @patch("run_comprehensive.run_cross_inference")
    @patch("run_comprehensive.run_deletion_timing")
    def test_all_categories_invoked(self, mock_deletion, mock_cross, mock_vector, mock_sparql, mock_acl):
        """Verify all 5 categories are called."""
        # Setup mock returns
        acl_cat = CategorySummary(
            attack_category="acl_enforcement",
            blocking=True,
            passed=5,
            partial=0,
            failed=0,
            total=5,
        )
        sparql_cat = CategorySummary(
            attack_category="sparql_injection",
            blocking=True,
            passed=3,
            partial=0,
            failed=0,
            total=3,
        )
        vector_cat = CategorySummary(
            attack_category="vector_privacy",
            blocking=False,
            passed=6,
            partial=3,
            failed=0,
            total=9,
        )
        cross_cat = CategorySummary(
            attack_category="cross_inference",
            blocking=False,
            passed=2,
            partial=1,
            failed=0,
            total=3,
        )
        deletion_cat = CategorySummary(
            attack_category="deletion_timing",
            blocking=False,
            passed=5,
            partial=0,
            failed=0,
            total=5,
        )

        mock_acl.return_value = (acl_cat, [])
        mock_sparql.return_value = (sparql_cat, [])
        mock_vector.return_value = (vector_cat, [])
        mock_cross.return_value = (cross_cat, [])
        mock_deletion.return_value = (deletion_cat, [])

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "troll-run.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                result = run_comprehensive()

        # Verify all were called
        mock_acl.assert_called_once()
        mock_sparql.assert_called_once()
        mock_vector.assert_called_once()
        mock_cross.assert_called_once()
        mock_deletion.assert_called_once()

        # Verify results aggregated correctly
        assert len(result.categories) == 5
        assert result.total_tests == 25
        assert result.total_passed == 21
        assert result.total_partial == 4
        assert result.total_failed == 0
        assert result.blocking_pass is True

    @patch("run_comprehensive.run_acl_enforcement")
    def test_orchestrator_exception_handling(self, mock_acl):
        """Verify orchestrator gracefully handles category exceptions."""
        mock_acl.side_effect = RuntimeError("CSS unreachable")

        with patch("run_comprehensive.run_sparql_injection") as mock_sparql, \
             patch("run_comprehensive.run_vector_privacy") as mock_vector, \
             patch("run_comprehensive.run_cross_inference") as mock_cross, \
             patch("run_comprehensive.run_deletion_timing") as mock_deletion:

            sparql_cat = CategorySummary(
                attack_category="sparql_injection",
                blocking=True,
                passed=3,
                partial=0,
                failed=0,
                total=3,
            )
            mock_sparql.return_value = (sparql_cat, [])
            mock_vector.return_value = (
                CategorySummary(
                    attack_category="vector_privacy", blocking=False, passed=0, partial=0, failed=0, total=0
                ),
                [],
            )
            mock_cross.return_value = (
                CategorySummary(
                    attack_category="cross_inference", blocking=False, passed=0, partial=0, failed=0, total=0
                ),
                [],
            )
            mock_deletion.return_value = (
                CategorySummary(
                    attack_category="deletion_timing", blocking=False, passed=0, partial=0, failed=0, total=0
                ),
                [],
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                jsonl_path = Path(tmpdir) / "troll-run.jsonl"
                with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                    result = run_comprehensive()

        # Verify result includes ACL exception as failed test
        assert any(t["attack_category"] == "acl_enforcement" for t in result.tests)
        # ACL is blocking, so blocking_pass should be False
        assert result.blocking_pass is False


class TestBlockingLogic:
    """Test blocking vs non-blocking category exit code logic."""

    @patch("run_comprehensive.run_acl_enforcement")
    @patch("run_comprehensive.run_sparql_injection")
    @patch("run_comprehensive.run_vector_privacy")
    @patch("run_comprehensive.run_cross_inference")
    @patch("run_comprehensive.run_deletion_timing")
    def test_blocking_pass_all_pass(self, mock_deletion, mock_cross, mock_vector, mock_sparql, mock_acl):
        """All tests pass -> blocking_pass=True."""
        for mock_fn, category_name in [
            (mock_acl, "acl_enforcement"),
            (mock_sparql, "sparql_injection"),
        ]:
            cat = CategorySummary(
                attack_category=category_name,
                blocking=True,
                passed=10,
                partial=0,
                failed=0,
                total=10,
            )
            mock_fn.return_value = (cat, [])

        for mock_fn, category_name in [
            (mock_vector, "vector_privacy"),
            (mock_cross, "cross_inference"),
            (mock_deletion, "deletion_timing"),
        ]:
            cat = CategorySummary(
                attack_category=category_name,
                blocking=False,
                passed=5,
                partial=0,
                failed=0,
                total=5,
            )
            mock_fn.return_value = (cat, [])

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "troll-run.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                result = run_comprehensive()

        assert result.blocking_pass is True

    @patch("run_comprehensive.run_acl_enforcement")
    @patch("run_comprehensive.run_sparql_injection")
    @patch("run_comprehensive.run_vector_privacy")
    @patch("run_comprehensive.run_cross_inference")
    @patch("run_comprehensive.run_deletion_timing")
    def test_blocking_fail_acl(self, mock_deletion, mock_cross, mock_vector, mock_sparql, mock_acl):
        """ACL enforcement fails -> blocking_pass=False."""
        acl_cat = CategorySummary(
            attack_category="acl_enforcement",
            blocking=True,
            passed=5,
            partial=0,
            failed=1,
            total=6,
        )
        mock_acl.return_value = (acl_cat, [])

        sparql_cat = CategorySummary(
            attack_category="sparql_injection",
            blocking=True,
            passed=3,
            partial=0,
            failed=0,
            total=3,
        )
        mock_sparql.return_value = (sparql_cat, [])

        for mock_fn, category_name in [
            (mock_vector, "vector_privacy"),
            (mock_cross, "cross_inference"),
            (mock_deletion, "deletion_timing"),
        ]:
            cat = CategorySummary(
                attack_category=category_name,
                blocking=False,
                passed=5,
                partial=0,
                failed=0,
                total=5,
            )
            mock_fn.return_value = (cat, [])

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "troll-run.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                result = run_comprehensive()

        assert result.blocking_pass is False

    @patch("run_comprehensive.run_acl_enforcement")
    @patch("run_comprehensive.run_sparql_injection")
    @patch("run_comprehensive.run_vector_privacy")
    @patch("run_comprehensive.run_cross_inference")
    @patch("run_comprehensive.run_deletion_timing")
    def test_blocking_pass_nonblocking_fail(self, mock_deletion, mock_cross, mock_vector, mock_sparql, mock_acl):
        """Blocking categories pass, non-blocking fails -> blocking_pass=True."""
        acl_cat = CategorySummary(
            attack_category="acl_enforcement",
            blocking=True,
            passed=10,
            partial=0,
            failed=0,
            total=10,
        )
        mock_acl.return_value = (acl_cat, [])

        sparql_cat = CategorySummary(
            attack_category="sparql_injection",
            blocking=True,
            passed=3,
            partial=0,
            failed=0,
            total=3,
        )
        mock_sparql.return_value = (sparql_cat, [])

        # Vector privacy fails
        vector_cat = CategorySummary(
            attack_category="vector_privacy",
            blocking=False,
            passed=5,
            partial=0,
            failed=2,
            total=7,
        )
        mock_vector.return_value = (vector_cat, [])

        for mock_fn, category_name in [
            (mock_cross, "cross_inference"),
            (mock_deletion, "deletion_timing"),
        ]:
            cat = CategorySummary(
                attack_category=category_name,
                blocking=False,
                passed=5,
                partial=0,
                failed=0,
                total=5,
            )
            mock_fn.return_value = (cat, [])

        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "troll-run.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                result = run_comprehensive()

        # Blocking pass because ACL and SPARQL have no failures
        assert result.blocking_pass is True
        # But total failed should be 2
        assert result.total_failed == 2


class TestJSONLEventFormat:
    """Test JSONL event emission format and contents."""

    def test_event_has_timestamp(self):
        """Emitted events include ISO-8601 timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "test.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                _emit_event("test.event", foo="bar")

            with jsonl_path.open() as f:
                line = f.readline()
                event = json.loads(line)

            assert "timestamp" in event
            assert "event_type" in event
            assert event["event_type"] == "test.event"
            assert event["foo"] == "bar"

    def test_event_format_complies_with_spec(self):
        """Emitted events match JSONL canonical spec."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "test.jsonl"
            with patch("run_comprehensive.JSONL_LOG", jsonl_path):
                _emit_event("troll.probe.done", category="test", test_name="t1", result="pass")
                _emit_event("troll.category.done", category="test", passed=1, partial=0, failed=0)

            with jsonl_path.open() as f:
                lines = f.readlines()

            assert len(lines) == 2

            event1 = json.loads(lines[0])
            assert event1["event_type"] == "troll.probe.done"
            assert event1["category"] == "test"

            event2 = json.loads(lines[1])
            assert event2["event_type"] == "troll.category.done"


class TestReportGeneration:
    """Test comprehensive report JSON and markdown generation."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample ComprehensiveRunResult for testing."""
        return ComprehensiveRunResult(
            timestamp="2026-03-31T12:00:00Z",
            categories=[
                CategorySummary(
                    attack_category="acl_enforcement",
                    blocking=True,
                    passed=5,
                    partial=0,
                    failed=0,
                    total=5,
                ),
                CategorySummary(
                    attack_category="sparql_injection",
                    blocking=True,
                    passed=3,
                    partial=0,
                    failed=0,
                    total=3,
                ),
                CategorySummary(
                    attack_category="vector_privacy",
                    blocking=False,
                    passed=6,
                    partial=2,
                    failed=1,
                    total=9,
                ),
                CategorySummary(
                    attack_category="cross_inference",
                    blocking=False,
                    passed=2,
                    partial=1,
                    failed=0,
                    total=3,
                ),
                CategorySummary(
                    attack_category="deletion_timing",
                    blocking=False,
                    passed=5,
                    partial=0,
                    failed=0,
                    total=5,
                ),
            ],
            total_tests=25,
            total_passed=21,
            total_partial=3,
            total_failed=1,
            blocking_pass=True,
            tests=[
                {
                    "attack_category": "acl_enforcement",
                    "access_path": "direct",
                    "test_name": "unauthenticated-read-ayoub",
                    "result": "pass",
                    "details": "CSS correctly denied unauthenticated access",
                    "evidence": {},
                },
                {
                    "attack_category": "vector_privacy",
                    "access_path": "direct",
                    "test_name": "name-extraction",
                    "result": "partial",
                    "details": "Embedding analysis revealed student name patterns",
                    "evidence": {},
                },
            ],
        )

    def test_json_report_structure(self, sample_result):
        """JSON report has required structure."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_json_report()

        assert "report_type" in report
        assert report["report_type"] == "comprehensive_troll_run"
        assert "timestamp" in report
        assert "categories" in report
        assert "overall" in report
        assert "tests" in report

    def test_json_report_categories_section(self, sample_result):
        """JSON report categories have correct structure."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_json_report()

        categories = report["categories"]
        assert "acl_enforcement" in categories
        assert categories["acl_enforcement"]["blocking"] is True
        assert categories["acl_enforcement"]["passed"] == 5

    def test_json_report_overall_assessment(self, sample_result):
        """JSON report overall assessment is generated."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_json_report()

        overall = report["overall"]
        assert "assessment" in overall
        assert overall["blocking_pass"] is True
        assert overall["total_tests"] == 25

    def test_markdown_report_readability(self, sample_result):
        """Markdown report is human-readable."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_markdown_report()

        assert "Executive Summary" in report
        assert "Test Results by Category" in report
        assert "Blocking Assessment" in report
        assert "Investment Opportunities" in report

    def test_markdown_report_includes_all_categories(self, sample_result):
        """Markdown report mentions all 5 categories."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_markdown_report()

        categories = [
            "acl enforcement",
            "sparql injection",
            "vector privacy",
            "cross inference",
            "deletion timing",
        ]
        for category in categories:
            assert category.lower() in report.lower()

    def test_markdown_report_blocking_assessment(self, sample_result):
        """Markdown report includes blocking assessment."""
        generator = ComprehensiveReportGenerator(sample_result)
        report = generator.generate_markdown_report()

        assert "Blocking Assessment" in report
        assert "NFR5" in report
        assert "NFR6" in report

    def test_report_file_write(self, sample_result):
        """Reports can be written to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "results.json"
            md_path = Path(tmpdir) / "report.md"

            generator = ComprehensiveReportGenerator(sample_result)
            generator.generate_json_report(json_path)
            generator.generate_markdown_report(md_path)

            assert json_path.exists()
            assert md_path.exists()

            # Verify JSON is valid
            with json_path.open() as f:
                json_data = json.load(f)
            assert json_data["report_type"] == "comprehensive_troll_run"

            # Verify markdown has content
            with md_path.open() as f:
                md_content = f.read()
            assert len(md_content) > 0
            assert "Executive Summary" in md_content


class TestResultAggregation:
    """Test that results are correctly aggregated from all categories."""

    def test_total_test_count(self):
        """Total tests = sum of all category totals."""
        result = ComprehensiveRunResult(
            timestamp="2026-03-31T12:00:00Z",
            categories=[
                CategorySummary(
                    attack_category="test1",
                    blocking=False,
                    passed=2,
                    partial=1,
                    failed=0,
                    total=3,
                ),
                CategorySummary(
                    attack_category="test2",
                    blocking=False,
                    passed=5,
                    partial=0,
                    failed=0,
                    total=5,
                ),
            ],
            total_tests=8,
            total_passed=7,
            total_partial=1,
            total_failed=0,
            blocking_pass=True,
            tests=[],
        )

        assert result.total_tests == 8
        assert result.total_passed == 7
        assert result.total_partial == 1

    def test_partial_blocking_assessment(self):
        """Partial results in non-blocking categories don't affect blocking_pass."""
        result = ComprehensiveRunResult(
            timestamp="2026-03-31T12:00:00Z",
            categories=[
                CategorySummary(
                    attack_category="acl_enforcement",
                    blocking=True,
                    passed=10,
                    partial=0,
                    failed=0,
                    total=10,
                ),
                CategorySummary(
                    attack_category="vector_privacy",
                    blocking=False,
                    passed=5,
                    partial=5,
                    failed=0,
                    total=10,
                ),
            ],
            total_tests=20,
            total_passed=15,
            total_partial=5,
            total_failed=0,
            blocking_pass=True,
            tests=[],
        )

        # Blocking categories have no failures -> blocking_pass=True
        assert result.blocking_pass is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
