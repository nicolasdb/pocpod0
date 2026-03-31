"""Troll adversary comprehensive report generator.

Converts unified orchestrator results into JSON and markdown reports for funders.
Implements FR34: readable by non-technical reviewers.

Report philosophy (from SOUL.md):
- Failure states are first-class citizens with full detail (root cause, source, violated policy)
- Success can be terse
- Partial/fail results are investment opportunities, not hidden failures
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# If run_comprehensive.py is in the same package
try:
    from run_comprehensive import ComprehensiveRunResult, CategorySummary
except ImportError:
    # Fallback: define minimal stub
    from dataclasses import dataclass

    @dataclass
    class CategorySummary:
        attack_category: str
        blocking: bool
        passed: int
        partial: int
        failed: int
        total: int

    @dataclass
    class ComprehensiveRunResult:
        timestamp: str
        categories: List[CategorySummary]
        total_tests: int
        total_passed: int
        total_partial: int
        total_failed: int
        blocking_pass: bool
        tests: List[dict]


REPORT_DIR = Path(__file__).parent


class ComprehensiveReportGenerator:
    """Generate JSON and markdown comprehensive troll reports."""

    def __init__(self, result: ComprehensiveRunResult):
        self.result = result

    def generate_json_report(self, output_path: Optional[Path] = None) -> dict:
        """Generate comprehensive JSON report.

        Returns the JSON dict (and optionally writes to file).
        """
        # Per-category summaries
        categories_summary = {}
        for cat in self.result.categories:
            categories_summary[cat.attack_category] = {
                "blocking": cat.blocking,
                "passed": cat.passed,
                "partial": cat.partial,
                "failed": cat.failed,
                "total": cat.total,
                "narrative": self._category_narrative(cat),
            }

        # Filter tests by severity for highlights
        fail_tests = [t for t in self.result.tests if t["result"] == "fail"]
        partial_tests = [t for t in self.result.tests if t["result"] == "partial"]

        # Overall assessment
        if self.result.blocking_pass:
            if self.result.total_failed == 0 and self.result.total_partial == 0:
                overall = "All defenses held strong under adversarial testing."
            elif self.result.total_failed == 0:
                overall = (
                    f"{self.result.total_partial} informational findings identified in non-blocking categories. "
                    f"Core defenses (ACL enforcement, SPARQL injection) passed. "
                    f"Findings are assessment areas for future hardening."
                )
            else:
                overall = (
                    f"{self.result.total_failed} failure(s) and {self.result.total_partial} partial finding(s) "
                    f"identified in non-blocking categories. "
                    f"Core defenses (ACL enforcement, SPARQL injection) passed. "
                    f"Failures and findings are investment opportunities for future hardening."
                )
        else:
            overall = (
                f"BLOCKING FAILURES DETECTED: {self.result.total_failed} test(s) failed in blocking categories. "
                f"ACL enforcement and/or SPARQL injection defenses require immediate investigation."
            )

        json_report = {
            "report_type": "comprehensive_troll_run",
            "timestamp": self.result.timestamp,
            "categories": categories_summary,
            "overall": {
                "total_tests": self.result.total_tests,
                "passed": self.result.total_passed,
                "partial": self.result.total_partial,
                "failed": self.result.total_failed,
                "blocking_pass": self.result.blocking_pass,
                "assessment": overall,
            },
            "highlights": {
                "fail_count": len(fail_tests),
                "partial_count": len(partial_tests),
                "fail_tests": fail_tests[:5],  # Top 5 failures
                "partial_tests": partial_tests[:5],  # Top 5 partials
            },
            "tests": self.result.tests,
        }

        # Write to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w") as f:
                json.dump(json_report, f, indent=2, default=str)

        return json_report

    def generate_markdown_report(self, output_path: Optional[Path] = None) -> str:
        """Generate human-readable markdown report for funders.

        Implements FR34: non-technical language, investment framing.
        """
        lines = []

        # Title and timestamp
        lines.append("# Troll Comprehensive Adversarial Test Report")
        lines.append(f"\n**Generated:** {self.result.timestamp}")
        lines.append(f"**Total Tests:** {self.result.total_tests}\n")

        # Executive Summary
        lines.append("## Executive Summary")
        if self.result.blocking_pass:
            if self.result.total_failed == 0 and self.result.total_partial == 0:
                lines.append(
                    "✅ **Architecture Holds Strong**\n"
                    "All adversarial probes resulted in successful defense. "
                    "Core security mechanisms (access control, injection prevention) are functioning as designed."
                )
            else:
                lines.append(
                    f"✅ **Core Defenses Intact** | ⚠️ **{self.result.total_partial} Assessment Findings**\n"
                    "Access control and SPARQL injection defenses passed all tests. "
                    f"The {self.result.total_partial} findings identified in non-blocking categories "
                    "are assessment opportunities for future hardening, not immediate defects."
                )
        else:
            lines.append(
                f"🚨 **Blocking Issues Detected** | {self.result.total_failed} Defenses Failed\n"
                "Adversarial testing found failures in core defense mechanisms. "
                "These require investigation before pilot deployment."
            )

        lines.append("")

        # Per-category sections
        lines.append("## Test Results by Category")

        for cat in self.result.categories:
            lines.append(self._category_section(cat))

        # Blocking Assessment
        lines.append("\n## Blocking Assessment\n")
        lines.append("**ACL Enforcement (NFR5) - Blocking**")
        acl_cat = next((c for c in self.result.categories if c.attack_category == "acl_enforcement"), None)
        if acl_cat:
            if acl_cat.failed == 0:
                lines.append(f"✅ PASS — {acl_cat.total} tests, all passed")
            else:
                lines.append(f"🚨 FAIL — {acl_cat.failed}/{acl_cat.total} tests failed")
        lines.append("")

        lines.append("**SPARQL Injection (NFR6) - Blocking**")
        sparql_cat = next((c for c in self.result.categories if c.attack_category == "sparql_injection"), None)
        if sparql_cat:
            if sparql_cat.failed == 0:
                lines.append(f"✅ PASS — {sparql_cat.total} tests, all passed")
            else:
                lines.append(f"🚨 FAIL — {sparql_cat.failed}/{sparql_cat.total} tests failed")
        lines.append("")

        # Investment Opportunities (non-blocking findings)
        if self.result.total_partial > 0 or self.result.total_failed > 0:
            lines.append("## Investment Opportunities\n")
            lines.append(
                "Non-blocking categories identified findings that represent opportunities "
                "for architectural investment. These are not defects, but areas where "
                "additional engineering would strengthen the system.\n"
            )

            # Partial findings
            partial_tests = [t for t in self.result.tests if t["result"] == "partial"]
            if partial_tests:
                lines.append("### Partial Results (Assessment Findings)\n")
                for test in partial_tests[:10]:  # Show top 10
                    lines.append(
                        f"- **{test.get('test_name', 'unknown')}** ({test.get('attack_category', 'unknown')})"
                    )
                    lines.append(f"  - {test.get('details', 'No details provided')}")
                    lines.append("")

            # Failure findings (non-blocking)
            fail_tests = [
                t for t in self.result.tests if t["result"] == "fail" and not self._is_blocking_category(t)
            ]
            if fail_tests:
                lines.append("### Failure Findings (Non-Blocking Categories)\n")
                for test in fail_tests[:10]:
                    lines.append(
                        f"- **{test.get('test_name', 'unknown')}** ({test.get('attack_category', 'unknown')})"
                    )
                    lines.append(f"  - {test.get('details', 'No details provided')}")
                    lines.append("")

        # Technical Appendix
        lines.append("## Technical Appendix\n")
        lines.append("### Test Counts by Category\n")
        lines.append("| Category | Pass | Partial | Fail | Total | Blocking |")
        lines.append("|----------|------|---------|------|-------|----------|")
        for cat in self.result.categories:
            blocking_str = "Yes" if cat.blocking else "No"
            lines.append(
                f"| {cat.attack_category} | {cat.passed} | {cat.partial} | {cat.failed} | {cat.total} | {blocking_str} |"
            )
        lines.append("")

        # Determinism note
        lines.append("### Determinism\n")
        cross_inf = next((c for c in self.result.categories if c.attack_category == "cross_inference"), None)
        if cross_inf:
            lines.append(
                "**Cross-Inference (NFR13):** Tests are LLM-dependent and non-deterministic. "
                "Results may vary between runs. This is expected behavior and documented in the NFR.\n"
            )

        lines.append("**Other Categories:** All other tests are deterministic and reproducible.\n")

        # Report metadata
        lines.append("---\n")
        lines.append("*Report generated by Troll Adversary Suite*")
        lines.append(f"*Timestamp: {datetime.now().isoformat()}*")

        md_report = "\n".join(lines)

        # Write to file if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w") as f:
                f.write(md_report)

        return md_report

    def _category_narrative(self, cat: CategorySummary) -> str:
        """Generate a brief narrative for a category."""
        if cat.failed > 0:
            return f"{cat.failed} test(s) failed — {cat.partial} partial findings"
        elif cat.partial > 0:
            return f"{cat.partial} test(s) had partial findings — assessment areas identified"
        else:
            return f"All {cat.total} test(s) passed"

    def _category_section(self, cat: CategorySummary) -> str:
        """Generate markdown section for a category."""
        lines = []

        # Category heading with emoji
        status_icon = "✅" if cat.failed == 0 else "🚨"
        lines.append(f"\n### {status_icon} {cat.attack_category.replace('_', ' ').title()}")

        if cat.blocking:
            lines.append("**Blocking Category**\n")
        else:
            lines.append("**Non-Blocking Category** (assessment findings)\n")

        # Result line
        if cat.failed > 0:
            result = f"**{cat.failed} Failed**, {cat.partial} Partial, {cat.passed} Passed"
        elif cat.partial > 0:
            result = f"**{cat.partial} Partial**, {cat.passed} Passed"
        else:
            result = f"**All {cat.total} Passed**"

        lines.append(f"**Result:** {result} (out of {cat.total} tests)\n")

        # Category-specific narrative
        if cat.attack_category == "acl_enforcement":
            lines.append(
                "Tests access control enforcement at the Solid Pod layer. "
                "Verifies that CSS correctly denies unauthorized access and permits authorized access."
            )
        elif cat.attack_category == "sparql_injection":
            lines.append(
                "Tests SPARQL query injection prevention at the Oxigraph layer. "
                "Verifies that malicious query patterns are detected and rejected."
            )
        elif cat.attack_category == "vector_privacy":
            lines.append(
                "Tests vector embedding privacy against direct Qdrant access. "
                "Probes for student identity leakage through embedding analysis."
            )
        elif cat.attack_category == "cross_inference":
            lines.append(
                "Tests agent-layer data leakage through natural language prompts via OpenClaw. "
                "Verifies role boundaries are enforced when agents process user queries. "
                "(LLM-dependent; results vary between runs.)"
            )
        elif cat.attack_category == "deletion_timing":
            lines.append(
                "Tests data deletion cascade across Pod, Oxigraph, and Qdrant layers. "
                "Verifies that deleted data is removed from all layers within acceptable timing."
            )

        lines.append("")
        return "\n".join(lines)

    def _is_blocking_category(self, test: dict) -> bool:
        """Check if a test is from a blocking category."""
        category = test.get("attack_category", "")
        return category in ("acl_enforcement", "sparql_injection")


def generate_reports(
    result: ComprehensiveRunResult,
    json_path: Optional[Path] = None,
    markdown_path: Optional[Path] = None,
) -> tuple[dict, str]:
    """Generate both JSON and markdown reports.

    Returns: (json_dict, markdown_str)
    """
    if json_path is None:
        json_path = REPORT_DIR / "comprehensive-results.json"
    if markdown_path is None:
        markdown_path = REPORT_DIR / "troll-report.md"

    generator = ComprehensiveReportGenerator(result)

    json_report = generator.generate_json_report(json_path)
    markdown_report = generator.generate_markdown_report(markdown_path)

    return json_report, markdown_report


if __name__ == "__main__":
    # Example: read result from orchestrator and generate reports
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generator.py <orchestrator_output_json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        result_dict = json.load(f)

    # Reconstruct ComprehensiveRunResult from dict
    # (simplified; in real use, the orchestrator would pass the object directly)
    result = ComprehensiveRunResult(
        timestamp=result_dict.get("timestamp", ""),
        categories=[
            CategorySummary(
                attack_category=cat_dict.get("attack_category", ""),
                blocking=cat_dict.get("blocking", False),
                passed=cat_dict.get("passed", 0),
                partial=cat_dict.get("partial", 0),
                failed=cat_dict.get("failed", 0),
                total=cat_dict.get("total", 0),
            )
            for cat_dict in result_dict.get("categories", [])
        ],
        total_tests=result_dict.get("total_tests", 0),
        total_passed=result_dict.get("total_passed", 0),
        total_partial=result_dict.get("total_partial", 0),
        total_failed=result_dict.get("total_failed", 0),
        blocking_pass=result_dict.get("blocking_pass", False),
        tests=result_dict.get("tests", []),
    )

    json_report, md_report = generate_reports(result)
    print("Reports generated successfully!")
    print(f"JSON report: {REPORT_DIR / 'comprehensive-results.json'}")
    print(f"Markdown report: {REPORT_DIR / 'troll-report.md'}")
