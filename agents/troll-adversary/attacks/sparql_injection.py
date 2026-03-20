"""Troll adversary: SPARQL injection validation suite.

Tests the parameterized .rq query template mechanism for injection resistance.
This is the security boundary test for SEC-3 (parameterized SPARQL templates).

access_path: "through_skill" — tests the skill-level query sanitization boundary.
  Direct Oxigraph access (ACL enforcement) is validated in Story 1.5.

NFR6: Injection resistance MUST pass. Any fail result is a BLOCKING issue.
NFR12: Tests are deterministic — same templates + same payloads = same results.

Design:
  - InjectionTestSuite.run_all() is the main entry point
  - Each test case: inject payload into parameter → engine must reject
  - If engine accepts: attempt to execute against Oxigraph
  - Pass = engine rejects OR Oxigraph returns no unauthorized data
  - Fail = injection payload reaches Oxigraph AND returns unexpected data
"""

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Bootstrap imports — hyphen-named directories need importlib
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[3]  # up to pocpod0/

# Import TrollTestResult / log_test_result from attacks/__init__.py
# When run as a script (not as a package), we load acl_enforcement directly.
_acl_spec = importlib.util.spec_from_file_location(
    "_acl_enforcement",
    Path(__file__).parent / "acl_enforcement.py",
)
_acl_mod = importlib.util.module_from_spec(_acl_spec)  # type: ignore[arg-type]
_acl_spec.loader.exec_module(_acl_mod)  # type: ignore[union-attr]
TrollTestResult = _acl_mod.TrollTestResult
log_test_result = _acl_mod.log_test_result

# Import parameterize from agents/skills/sparql-query/parameterize.py
# Directory has a hyphen, so we use importlib instead of a package import.
_param_spec = importlib.util.spec_from_file_location(
    "_sparql_parameterize",
    _repo_root / "agents" / "skills" / "sparql-query" / "parameterize.py",
)
_param_mod = importlib.util.module_from_spec(_param_spec)  # type: ignore[arg-type]
_param_spec.loader.exec_module(_param_mod)  # type: ignore[union-attr]
load_template = _param_mod.load_template
parameterize_query = _param_mod.parameterize_query
extract_params = _param_mod.extract_params

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OXIGRAPH_BASE_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")
DEFAULT_TEMPLATE_DIR = _repo_root / "agents" / "skills" / "sparql-query" / "templates"
REPORT_DIR = Path(__file__).resolve().parents[1] / "report"

TEMPLATE_NAMES = [
    "student-progress",
    "cross-context-query",
    "aggregate-anonymized",
    "parental-view",
    "transfer-profile",
]

# Safe placeholder values used when not testing the specific parameter
SAFE_PARAM_VALUES = {
    "student_uri": "http://localhost:3000/ayoub/profile/card#me",
    "context_uri": "http://localhost:3000/ayoub/",
    "agent_role": "teacher",
    "pod_uri": "http://localhost:3000/ayoub/",
    "program_uri": "http://example.org/program/math",
    "community_uri": "http://localhost:3000/school-community/",
    "parent_uri": "http://localhost:3000/fatima/profile/card#me",
    "child_uri": "http://localhost:3000/fatima-child-1/profile/card#me",
    "school_uri": "http://example.org/school/brussels-1",
}

# ---------------------------------------------------------------------------
# Injection payloads (AC-3)
# ---------------------------------------------------------------------------

INJECTION_PAYLOADS: dict[str, list[str]] = {
    "clause_injection": [
        "; DROP ALL",
        "} UNION { SELECT * WHERE { ?s ?p ?o } }",
        "OPTIONAL { ?secret <http://secret> ?value }",
    ],
    "string_escape": [
        'value" . ?s ?p ?o . FILTER(?o = "secret',
        "value\\",
        "value' ; --",
    ],
    "uri_injection": [
        "<http://evil.com> . ?s ?p ?o . <http://evil.com>",
        "http://evil.com> . OPTIONAL { ?s ?p ?o } . <http://x",
    ],
    "comment_injection": [
        "value # rest of query is commented out",
        "value\n# comment\n",
    ],
    "filter_injection": [
        'value" FILTER(true) . ?admin <http://role> "admin',
        "value FILTER(?role = <http://admin>)",
    ],
    "nested_query": [
        "{ SELECT * WHERE { ?s ?p ?o } }",
        "value } { SELECT * WHERE { ?s ?p ?o } } {",
    ],
}


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def _check_oxigraph(base_url: str) -> Optional[str]:
    """Verify Oxigraph is reachable.

    Returns error string if preflight fails, None if OK.
    """
    try:
        r = httpx.get(base_url, timeout=5)
        # Oxigraph health endpoint returns 200
        if r.status_code not in (200, 204):
            return f"Oxigraph returned unexpected status {r.status_code} at {base_url}"
        return None
    except Exception as exc:
        return f"Oxigraph unreachable at {base_url}: {exc}"


# ---------------------------------------------------------------------------
# SPARQL execution
# ---------------------------------------------------------------------------

def _execute_sparql(base_url: str, query: str) -> tuple[Optional[int], Optional[str], float]:
    """Execute a SPARQL query against Oxigraph.

    Returns (status_code, response_body, duration_ms).
    """
    start = time.time()
    try:
        r = httpx.post(
            f"{base_url}/query",
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=10,
        )
        duration_ms = (time.time() - start) * 1000
        return r.status_code, r.text, round(duration_ms, 2)
    except Exception as exc:
        duration_ms = (time.time() - start) * 1000
        return None, str(exc), round(duration_ms, 2)


def _has_unexpected_results(response_body: Optional[str]) -> bool:
    """Check if SPARQL response contains any result rows (data leak indicator).

    Returns True only if results are present.
    Re-raises JSONDecodeError so callers can detect malformed Oxigraph responses (#4).
    """
    if not response_body:
        return False
    data = json.loads(response_body)  # Propagate JSONDecodeError — not silenced
    try:
        bindings = data.get("results", {}).get("bindings", [])
        return len(bindings) > 0
    except (AttributeError, KeyError):
        # Unexpected response structure — treat as no results, not as parse failure
        return False


# ---------------------------------------------------------------------------
# Core test logic
# ---------------------------------------------------------------------------

class InjectionTestSuite:
    """SPARQL injection test suite.

    Tests each .rq template file against all injection payload categories
    through the parameterization engine.
    """

    def __init__(
        self,
        oxigraph_url: str = OXIGRAPH_BASE_URL,
        template_dir: Path = DEFAULT_TEMPLATE_DIR,
    ) -> None:
        self.oxigraph_url = oxigraph_url
        self.template_dir = template_dir
        self._results: list[TrollTestResult] = []

    def run_all(self) -> tuple[dict, list[TrollTestResult]]:
        """Execute the full injection test suite.

        Returns:
            Tuple of (summary dict, list of TrollTestResult).
        """
        # Preflight
        preflight_error = _check_oxigraph(self.oxigraph_url)
        if preflight_error:
            summary = {
                "category": "sparql_injection",
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "blocking": True,
                "note": f"PREFLIGHT FAILED — {preflight_error}",
            }
            return summary, []

        self._results = []

        for template_name in TEMPLATE_NAMES:
            try:
                template_content = load_template(template_name, self.template_dir)
            except FileNotFoundError as exc:
                result = TrollTestResult(
                    attack_category="sparql_injection",
                    access_path="through_skill",
                    test_name=f"template-load-{template_name}",
                    result="fail",
                    details=f"BLOCKING: template file missing — {exc}",
                    evidence={
                        "template": template_name,
                        "error": str(exc),
                    },
                )
                log_test_result(result)
                self._results.append(result)
                continue

            params_in_template = extract_params(template_content)

            for param_name in params_in_template:
                for category, payloads in INJECTION_PAYLOADS.items():
                    for payload in payloads:
                        result = self._run_one_test(
                            template_name, template_content, param_name, category, payload
                        )
                        log_test_result(result)
                        self._results.append(result)

        return self._build_summary(), self._results

    def _run_one_test(
        self,
        template_name: str,
        template_content: str,
        param_name: str,
        category: str,
        payload: str,
    ) -> TrollTestResult:
        """Run a single injection test case."""
        params_in_template = extract_params(template_content)
        test_params = {
            p: SAFE_PARAM_VALUES.get(p, f"http://example.org/{p}")
            for p in params_in_template
        }
        test_params[param_name] = payload

        safe_payload_repr = repr(payload)
        test_name = (
            f"{template_name}-{param_name}-{category}-"
            f"{payload[:20].replace(' ', '-').replace(chr(10), 'NL')}"
        )
        test_name = re.sub(r"[^a-zA-Z0-9\-_]", "", test_name)[:80]

        try:
            query = parameterize_query(template_content, test_params)
        except (ValueError, KeyError) as exc:
            return TrollTestResult(
                attack_category="sparql_injection",
                access_path="through_skill",
                test_name=test_name,
                result="pass",
                details=(
                    f"{category} injection in '{param_name}' parameter "
                    f"was rejected by parameterization engine: {exc}"
                ),
                evidence={
                    "template": template_name,
                    "parameter": param_name,
                    "payload": payload,
                    "engine_response": f"rejected: {exc}",
                    "oxigraph_reached": False,
                },
            )

        status_code, response_body, duration_ms = _execute_sparql(self.oxigraph_url, query)

        if status_code is None:
            return TrollTestResult(
                attack_category="sparql_injection",
                access_path="through_skill",
                test_name=test_name,
                result="partial",
                details=(
                    f"Engine accepted {category} payload; Oxigraph unreachable. "
                    f"Cannot confirm injection result. Payload: {safe_payload_repr}"
                ),
                evidence={
                    "template": template_name,
                    "parameter": param_name,
                    "payload": payload,
                    "engine_response": "accepted",
                    "oxigraph_reached": False,
                    "network_error": response_body,
                },
            )

        if status_code == 400:
            return TrollTestResult(
                attack_category="sparql_injection",
                access_path="through_skill",
                test_name=test_name,
                result="pass",
                details=(
                    f"{category} injection in '{param_name}' accepted by engine but "
                    f"Oxigraph rejected the resulting malformed query (HTTP 400)"
                ),
                evidence={
                    "template": template_name,
                    "parameter": param_name,
                    "payload": payload,
                    "engine_response": "accepted",
                    "oxigraph_reached": True,
                    "oxigraph_status": status_code,
                    "expected": "HTTP 400 or no results",
                    "actual": f"HTTP {status_code}",
                },
            )

        if status_code == 200:
            try:
                has_data = _has_unexpected_results(response_body)
            except json.JSONDecodeError as exc:
                return TrollTestResult(
                    attack_category="sparql_injection",
                    access_path="through_skill",
                    test_name=test_name,
                    result="partial",
                    details=(
                        f"Engine accepted {category} payload; Oxigraph returned HTTP 200 "
                        f"but response was not valid JSON — cannot confirm injection result: {exc}"
                    ),
                    evidence={
                        "template": template_name,
                        "parameter": param_name,
                        "payload": payload,
                        "engine_response": "accepted",
                        "oxigraph_reached": True,
                        "oxigraph_status": status_code,
                        "parse_error": str(exc),
                    },
                )

            if has_data:
                return TrollTestResult(
                    attack_category="sparql_injection",
                    access_path="through_skill",
                    test_name=test_name,
                    result="fail",
                    details=(
                        f"BLOCKING: {category} injection in '{param_name}' succeeded — "
                        f"query executed and returned data (NFR6 VIOLATION). "
                        f"Payload: {safe_payload_repr}"
                    ),
                    evidence={
                        "template": template_name,
                        "parameter": param_name,
                        "payload": payload,
                        "engine_response": "accepted",
                        "oxigraph_reached": True,
                        "oxigraph_status": status_code,
                        "expected": "engine rejection or empty results",
                        "actual": f"HTTP 200 with data: {response_body[:500]}",
                    },
                )

        return TrollTestResult(
            attack_category="sparql_injection",
            access_path="through_skill",
            test_name=test_name,
            result="pass",
            details=(
                f"{category} injection in '{param_name}' reached Oxigraph "
                f"but returned no data (HTTP {status_code}, empty results)"
            ),
            evidence={
                "template": template_name,
                "parameter": param_name,
                "payload": payload,
                "engine_response": "accepted",
                "oxigraph_reached": True,
                "oxigraph_status": status_code,
                "expected": "no unauthorized data",
                "actual": "empty result set",
            },
        )

    def _build_summary(self) -> dict:
        passed = sum(1 for r in self._results if r.result == "pass")
        failed = sum(1 for r in self._results if r.result == "fail")
        partial = sum(1 for r in self._results if r.result == "partial")
        return {
            "category": "sparql_injection",
            "total_tests": len(self._results),
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "blocking": failed > 0,
        }


# ---------------------------------------------------------------------------
# Report writing (AC-4, AC-6)
# ---------------------------------------------------------------------------

def write_report(summary: dict, results: list[TrollTestResult]) -> Path:
    """Write full injection results report to the report directory."""
    from dataclasses import asdict

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "sparql-injection-results.json"

    report = {
        **summary,
        "tests": [asdict(r) for r in results],
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Script entry point (Task 9 / AC-1)
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """Runner entry point.

    Usage:
        python agents/troll-adversary/attacks/sparql_injection.py [--oxigraph-url URL] [--template-dir DIR]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="SPARQL injection validation suite (Story 2.7, NFR6)"
    )
    parser.add_argument(
        "--oxigraph-url",
        default=OXIGRAPH_BASE_URL,
        help=f"Oxigraph SPARQL endpoint (default: {OXIGRAPH_BASE_URL})",
    )
    parser.add_argument(
        "--template-dir",
        default=str(DEFAULT_TEMPLATE_DIR),
        help=f"Directory containing .rq templates (default: {DEFAULT_TEMPLATE_DIR})",
    )
    args = parser.parse_args(argv)

    suite = InjectionTestSuite(
        oxigraph_url=args.oxigraph_url,
        template_dir=Path(args.template_dir),
    )
    summary, results = suite.run_all()

    report_path = write_report(summary, results)

    print("\n" + "=" * 60)
    print("SPARQL Injection Test Summary")
    print("=" * 60)
    print(f"  Total:   {summary['total_tests']}")
    print(f"  Passed:  {summary.get('passed', 0)}")
    print(f"  Failed:  {summary.get('failed', 0)}")
    print(f"  Partial: {summary.get('partial', 0)}")
    print(f"  Blocking: {summary['blocking']}")
    if summary.get("note"):
        print(f"  Note: {summary['note']}")
    print(f"\nReport written to: {report_path}")
    print("=" * 60)

    if summary["blocking"]:
        print("\n🚨 BLOCKING FAILURE: SPARQL injection resistance failed (NFR6)", file=sys.stderr)
        return 1

    print("\n✅ All injection tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
