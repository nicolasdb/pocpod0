"""Troll adversary comprehensive attack orchestrator.

Runs all 5 attack categories in sequence and aggregates results.
Emits JSONL events to data/troll-run.jsonl for dashboard streaming.
Exits non-zero only if blocking categories (ACL enforcement, SPARQL injection) fail.

Attack categories (in order):
1. acl_enforcement (NFR5, blocking) — infrastructure access control
2. sparql_injection (NFR6, blocking) — query sanitization
3. vector_privacy (NFR8, non-blocking) — embedding PII exposure
4. cross_inference (NFR13, non-blocking) — agent data leakage via LLM
5. deletion_timing (NFR12, non-blocking) — cascade completeness across layers

Determinism note: cross_inference uses LLM; all others are deterministic.
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Import attack modules
from acl_enforcement import run_acl_enforcement_suite, TrollTestResult
from cross_inference import CrossInferenceAttack
from deletion_timing import DeletionTimingAttack
from sparql_injection import InjectionTestSuite
from vector_privacy import VectorPrivacyTestSuite

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
OXIGRAPH_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
OPENCLAW_BASE_URL = os.environ.get("OPENCLAW_BASE_URL", "http://localhost:8000")
OPENCLAW_GATEWAY_TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

JSONL_LOG = Path(__file__).parent.parent.parent / "data" / "troll-run.jsonl"

# Deletion timing test parameters
DEFAULT_POD_URI = "http://localhost:3000/ayoub/"
DEFAULT_RESOURCE_URI = "http://localhost:3000/ayoub/profile/card"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CategorySummary:
    """Per-category result summary."""

    attack_category: str  # acl_enforcement, sparql_injection, vector_privacy, cross_inference, deletion_timing
    blocking: bool  # True if NFR5 (ACL) or NFR6 (SPARQL), False otherwise
    passed: int  # Number of tests with result="pass"
    partial: int  # Number of tests with result="partial"
    failed: int  # Number of tests with result="fail"
    total: int  # Total tests in category


@dataclass
class ComprehensiveRunResult:
    """Unified comprehensive run result."""

    timestamp: str  # ISO-8601
    categories: List[CategorySummary]
    total_tests: int
    total_passed: int
    total_partial: int
    total_failed: int
    blocking_pass: bool  # True if all blocking categories have zero failures
    tests: List[dict]  # All individual TrollTestResult as dicts


# ---------------------------------------------------------------------------
# JSONL event emission
# ---------------------------------------------------------------------------


def _emit_event(event_type: str, **data) -> None:
    """Emit a JSONL event to data/troll-run.jsonl."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": event_type,
        **data,
    }
    JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with JSONL_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# Individual attack orchestration
# ---------------------------------------------------------------------------


def run_acl_enforcement(css_base_url: str = CSS_BASE_URL) -> Tuple[CategorySummary, List[TrollTestResult]]:
    """Run ACL enforcement attack category.

    Returns: (CategorySummary, list of TrollTestResult)
    """
    summary_dict, results = run_acl_enforcement_suite(css_base_url)

    category = CategorySummary(
        attack_category="acl_enforcement",
        blocking=True,
        passed=summary_dict.get("pass", 0),
        partial=summary_dict.get("partial", 0),
        failed=summary_dict.get("fail", 0),
        total=summary_dict.get("total_tests", 0),
    )

    return category, results


def run_sparql_injection(oxigraph_url: str = OXIGRAPH_URL) -> Tuple[CategorySummary, List[TrollTestResult]]:
    """Run SPARQL injection attack category.

    Returns: (CategorySummary, list of TrollTestResult)
    """
    suite = InjectionTestSuite(oxigraph_url=oxigraph_url, template_dir=None)
    summary_dict, results = suite.run_all()

    category = CategorySummary(
        attack_category="sparql_injection",
        blocking=True,
        passed=summary_dict.get("passed", 0),
        partial=summary_dict.get("partial", 0),
        failed=summary_dict.get("failed", 0),
        total=summary_dict.get("total_tests", 0),
    )

    return category, results


def run_vector_privacy(qdrant_url: str = QDRANT_URL) -> Tuple[CategorySummary, List[TrollTestResult]]:
    """Run vector privacy attack category.

    Returns: (CategorySummary, list of TrollTestResult)
    """
    suite = VectorPrivacyTestSuite(qdrant_url=qdrant_url)
    summary_dict = suite.run_all()

    # Extract individual results from the summary
    results = []
    for test_dict in summary_dict.get("tests", []):
        try:
            result = TrollTestResult(
                attack_category=test_dict.get("attack_category", "vector_privacy"),
                access_path=test_dict.get("access_path", "direct"),
                test_name=test_dict.get("test_name", "unknown"),
                result=test_dict.get("result", "fail"),
                details=test_dict.get("details", ""),
                evidence=test_dict.get("evidence", {}),
            )
            results.append(result)
        except Exception:
            # If conversion fails, skip this test
            pass

    category = CategorySummary(
        attack_category="vector_privacy",
        blocking=False,
        passed=summary_dict.get("passed", 0),
        partial=summary_dict.get("partial", 0),
        failed=summary_dict.get("failed", 0),
        total=summary_dict.get("total_tests", 0),
    )

    return category, results


def run_cross_inference(
    base_url: str = OPENCLAW_BASE_URL, token: str = OPENCLAW_GATEWAY_TOKEN
) -> Tuple[CategorySummary, List[TrollTestResult]]:
    """Run cross-inference attack category.

    Returns: (CategorySummary, list of TrollTestResult)
    """
    attack = CrossInferenceAttack(base_url=base_url, token=token)
    probe_results = attack.run_all_probes()
    summary = attack.generate_summary(probe_results)

    # Convert probe results to TrollTestResult format
    results = []
    for probe_result in probe_results:
        result = TrollTestResult(
            attack_category="cross_inference",
            access_path="through_agent",
            test_name=probe_result.probe_id,
            result=probe_result.result,
            details=probe_result.details,
            evidence=probe_result.evidence if isinstance(probe_result.evidence, dict) else {},
        )
        results.append(result)

    category = CategorySummary(
        attack_category="cross_inference",
        blocking=False,
        passed=summary.pass_count,
        partial=summary.partial_count,
        failed=summary.fail_count,
        total=summary.total_probes,
    )

    return category, results


def run_deletion_timing(
    target_pod_uri: str = DEFAULT_POD_URI, resource_uri: str = DEFAULT_RESOURCE_URI
) -> Tuple[CategorySummary, List[TrollTestResult]]:
    """Run deletion timing attack category.

    Returns: (CategorySummary, list of TrollTestResult)
    """
    attack = DeletionTimingAttack(target_pod_uri=target_pod_uri, resource_uri=resource_uri)
    timing_results = attack.run_all_tests()
    summary = attack.generate_summary(timing_results)

    # Convert timing results to TrollTestResult format
    results = []
    for timing_result in timing_results:
        result = TrollTestResult(
            attack_category="deletion_timing",
            access_path="direct",
            test_name=timing_result.test_name,
            result=timing_result.result,
            details=timing_result.details,
            evidence=timing_result.evidence,
        )
        results.append(result)

    category = CategorySummary(
        attack_category="deletion_timing",
        blocking=False,
        passed=summary.pass_count,
        partial=summary.partial_count,
        failed=summary.fail_count,
        total=summary.total_tests,
    )

    return category, results


# ---------------------------------------------------------------------------
# Comprehensive orchestration
# ---------------------------------------------------------------------------


def run_comprehensive(
    css_base_url: str = CSS_BASE_URL,
    oxigraph_url: str = OXIGRAPH_URL,
    qdrant_url: str = QDRANT_URL,
    openclaw_base_url: str = OPENCLAW_BASE_URL,
    openclaw_token: str = OPENCLAW_GATEWAY_TOKEN,
) -> ComprehensiveRunResult:
    """Run all 5 attack categories in sequence and aggregate results.

    Emits JSONL events to data/troll-run.jsonl as each category completes.
    Truncates the JSONL file at the start to avoid stale data.

    Returns: ComprehensiveRunResult with aggregated summary.
    """
    # Truncate JSONL file at start (same pattern as run_pipeline.py)
    JSONL_LOG.parent.mkdir(parents=True, exist_ok=True)
    JSONL_LOG.write_text("")

    # Emit run start event
    _emit_event(
        "troll.run.start",
        categories=["acl_enforcement", "sparql_injection", "vector_privacy", "cross_inference", "deletion_timing"],
    )

    run_start = time.time()

    # Collect results from all categories
    all_categories: List[CategorySummary] = []
    all_tests: List[dict] = []

    # 1. ACL Enforcement
    try:
        print("Running acl_enforcement...", file=sys.stderr, flush=True)
        acl_category, acl_results = run_acl_enforcement(css_base_url)
        all_categories.append(acl_category)
        all_tests.extend([asdict(r) for r in acl_results])
        _emit_event(
            "troll.category.done",
            category="acl_enforcement",
            passed=acl_category.passed,
            partial=acl_category.partial,
            failed=acl_category.failed,
        )
    except Exception as exc:
        print(f"ERROR in acl_enforcement: {exc}", file=sys.stderr, flush=True)
        all_categories.append(
            CategorySummary(
                attack_category="acl_enforcement",
                blocking=True,
                passed=0,
                partial=0,
                failed=1,
                total=1,
            )
        )
        all_tests.append(
            {
                "attack_category": "acl_enforcement",
                "access_path": "direct",
                "test_name": "orchestrator-exception",
                "result": "fail",
                "details": f"Exception during acl_enforcement orchestration: {exc}",
                "evidence": {},
            }
        )

    # 2. SPARQL Injection
    try:
        print("Running sparql_injection...", file=sys.stderr, flush=True)
        sparql_category, sparql_results = run_sparql_injection(oxigraph_url)
        all_categories.append(sparql_category)
        all_tests.extend([asdict(r) for r in sparql_results])
        _emit_event(
            "troll.category.done",
            category="sparql_injection",
            passed=sparql_category.passed,
            partial=sparql_category.partial,
            failed=sparql_category.failed,
        )
    except Exception as exc:
        print(f"ERROR in sparql_injection: {exc}", file=sys.stderr, flush=True)
        all_categories.append(
            CategorySummary(
                attack_category="sparql_injection",
                blocking=True,
                passed=0,
                partial=0,
                failed=1,
                total=1,
            )
        )
        all_tests.append(
            {
                "attack_category": "sparql_injection",
                "access_path": "direct",
                "test_name": "orchestrator-exception",
                "result": "fail",
                "details": f"Exception during sparql_injection orchestration: {exc}",
                "evidence": {},
            }
        )

    # 3. Vector Privacy
    try:
        print("Running vector_privacy...", file=sys.stderr, flush=True)
        vector_category, vector_results = run_vector_privacy(qdrant_url)
        all_categories.append(vector_category)
        all_tests.extend([asdict(r) for r in vector_results])
        _emit_event(
            "troll.category.done",
            category="vector_privacy",
            passed=vector_category.passed,
            partial=vector_category.partial,
            failed=vector_category.failed,
        )
    except Exception as exc:
        print(f"ERROR in vector_privacy: {exc}", file=sys.stderr, flush=True)
        all_categories.append(
            CategorySummary(
                attack_category="vector_privacy",
                blocking=False,
                passed=0,
                partial=0,
                failed=1,
                total=1,
            )
        )
        all_tests.append(
            {
                "attack_category": "vector_privacy",
                "access_path": "direct",
                "test_name": "orchestrator-exception",
                "result": "fail",
                "details": f"Exception during vector_privacy orchestration: {exc}",
                "evidence": {},
            }
        )

    # 4. Cross-Inference
    try:
        print("Running cross_inference...", file=sys.stderr, flush=True)
        cross_category, cross_results = run_cross_inference(openclaw_base_url, openclaw_token)
        all_categories.append(cross_category)
        all_tests.extend([asdict(r) for r in cross_results])
        _emit_event(
            "troll.category.done",
            category="cross_inference",
            passed=cross_category.passed,
            partial=cross_category.partial,
            failed=cross_category.failed,
        )
    except Exception as exc:
        print(f"ERROR in cross_inference: {exc}", file=sys.stderr, flush=True)
        all_categories.append(
            CategorySummary(
                attack_category="cross_inference",
                blocking=False,
                passed=0,
                partial=0,
                failed=1,
                total=1,
            )
        )
        all_tests.append(
            {
                "attack_category": "cross_inference",
                "access_path": "through_agent",
                "test_name": "orchestrator-exception",
                "result": "fail",
                "details": f"Exception during cross_inference orchestration: {exc}",
                "evidence": {},
            }
        )

    # 5. Deletion Timing
    try:
        print("Running deletion_timing...", file=sys.stderr, flush=True)
        deletion_category, deletion_results = run_deletion_timing()
        all_categories.append(deletion_category)
        all_tests.extend([asdict(r) for r in deletion_results])
        _emit_event(
            "troll.category.done",
            category="deletion_timing",
            passed=deletion_category.passed,
            partial=deletion_category.partial,
            failed=deletion_category.failed,
        )
    except Exception as exc:
        print(f"ERROR in deletion_timing: {exc}", file=sys.stderr, flush=True)
        all_categories.append(
            CategorySummary(
                attack_category="deletion_timing",
                blocking=False,
                passed=0,
                partial=0,
                failed=1,
                total=1,
            )
        )
        all_tests.append(
            {
                "attack_category": "deletion_timing",
                "access_path": "direct",
                "test_name": "orchestrator-exception",
                "result": "fail",
                "details": f"Exception during deletion_timing orchestration: {exc}",
                "evidence": {},
            }
        )

    # Aggregate results
    total_elapsed = (time.time() - run_start) * 1000
    total_passed = sum(cat.passed for cat in all_categories)
    total_partial = sum(cat.partial for cat in all_categories)
    total_failed = sum(cat.failed for cat in all_categories)
    total_tests = sum(cat.total for cat in all_categories)

    # Determine if blocking categories passed
    blocking_pass = True
    for cat in all_categories:
        if cat.blocking and cat.failed > 0:
            blocking_pass = False
            break

    # Create comprehensive result
    result = ComprehensiveRunResult(
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        categories=all_categories,
        total_tests=total_tests,
        total_passed=total_passed,
        total_partial=total_partial,
        total_failed=total_failed,
        blocking_pass=blocking_pass,
        tests=all_tests,
    )

    # Emit run completion event
    _emit_event(
        "troll.run.done",
        total_elapsed_ms=round(total_elapsed, 2),
        blocking_pass=blocking_pass,
        total_tests=total_tests,
        passed=total_passed,
        partial=total_partial,
        failed=total_failed,
    )

    return result


def main() -> int:
    """Main entry point. Runs comprehensive test and returns exit code."""
    result = run_comprehensive()

    # Print summary to stdout
    result_dict = asdict(result)
    result_dict["categories"] = [asdict(cat) for cat in result.categories]
    print(json.dumps(result_dict, indent=2, default=str))

    # Generate reports (JSON + markdown)
    try:
        # Add report directory to path to find generator module
        report_dir = Path(__file__).parent.parent / "report"
        if str(report_dir) not in sys.path:
            sys.path.insert(0, str(report_dir))

        # Import and generate reports
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "generator",
            str(report_dir / "generator.py")
        )
        gen_module = importlib.util.module_from_spec(spec)
        sys.modules["generator"] = gen_module
        spec.loader.exec_module(gen_module)

        gen_module.generate_reports(result)
        print("\n✅ Reports generated successfully!", file=sys.stderr)
        print(f"   JSON: {report_dir / 'comprehensive-results.json'}", file=sys.stderr)
        print(f"   Markdown: {report_dir / 'troll-report.md'}", file=sys.stderr)
    except Exception as exc:
        print(f"⚠️  Report generation failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    # Exit non-zero only if blocking categories failed
    if not result.blocking_pass:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
