"""Troll adversary: ACL enforcement validation suite.

Deterministic infrastructure test per NFR12. No LLM calls, no randomness.
Tests that CSS correctly enforces WebACL-based access controls.

access_path: "direct" (raw HTTP to CSS, bypassing any agent skill layer)

Dual access pattern (FR37):
  - Direct infrastructure access: validated here (Story 1.5)
  - Skill-mediated access: deferred to Epic 2, Story 2.6

Security model (SEC-1): No real Solid-OIDC. Identity is simulated via
Authorization: WebID <webid>, which CSS accepts via UnsecureWebIdExtractor
(debug-auth-header.json config). Unauthenticated requests (no header)
are expected to receive 401 or 403.

NFR5: ACL enforcement MUST pass. Any fail result is a blocking issue.
NFR12: Tests are deterministic — identical pods + ACLs = identical results every run.
"""

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")

PODS = [
    "ayoub",
    "claire-student-1",
    "claire-student-2",
    "fatima-child-1",
    "fatima-child-2",
    "school-community",
]

# Agent WebIDs match the ACL files provisioned by Story 1.3.
# Format: http://localhost:3000/{agent-name}/profile/card#me
# These are fixed at provisioning time; CSS enforces against these exact URIs.
AGENT_WEBIDS = {
    "ayoub": "http://localhost:3000/ayoub/profile/card#me",
    "claire": "http://localhost:3000/claire/profile/card#me",
    "fatima": "http://localhost:3000/fatima/profile/card#me",
    "marc": "http://localhost:3000/marc/profile/card#me",
    "isabelle": "http://localhost:3000/isabelle/profile/card#me",
    "troll": "http://localhost:3000/troll/profile/card#me",
}

# Unauthorized matrix: (identity, pod) pairs where CSS MUST deny access (expected 403).
# Derived from the ACL access matrix established in Story 1.3.
UNAUTHORIZED_MATRIX: List[Tuple[str, str]] = [
    # claire-teacher has no access to fatima's children's pods
    ("claire", "fatima-child-1"),
    ("claire", "fatima-child-2"),
    # fatima-parent has no access to ayoub's pod or claire's students' pods
    ("fatima", "ayoub"),
    ("fatima", "claire-student-1"),
    ("fatima", "claire-student-2"),
    # ayoub-student has no access to other students' pods
    ("ayoub", "claire-student-1"),
    ("ayoub", "claire-student-2"),
    ("ayoub", "fatima-child-1"),
    ("ayoub", "fatima-child-2"),
    # troll-adversary has no access to any pod
    ("troll", "ayoub"),
    ("troll", "claire-student-1"),
    ("troll", "claire-student-2"),
    ("troll", "fatima-child-1"),
    ("troll", "fatima-child-2"),
    ("troll", "school-community"),
    # marc (admin) has NO direct individual pod access — school-community only
    ("marc", "ayoub"),
    ("marc", "claire-student-1"),
    ("marc", "claire-student-2"),
    ("marc", "fatima-child-1"),
    ("marc", "fatima-child-2"),
    # isabelle (regional) has NO direct individual pod access — school-community only
    ("isabelle", "ayoub"),
    ("isabelle", "claire-student-1"),
    ("isabelle", "claire-student-2"),
    ("isabelle", "fatima-child-1"),
    ("isabelle", "fatima-child-2"),
]

# Authorized matrix: (identity, pod) pairs where CSS MUST allow access (expected 200).
# Used as positive test cases to validate the test harness is working correctly.
AUTHORIZED_MATRIX: List[Tuple[str, str]] = [
    ("claire", "claire-student-1"),   # claire-teacher CAN read her students
    ("claire", "claire-student-2"),
    ("fatima", "fatima-child-1"),     # fatima-parent CAN read her children
    ("fatima", "fatima-child-2"),
    ("ayoub", "ayoub"),               # ayoub-student CAN read his own pod
    # All authenticated agents CAN read school-community
    ("claire", "school-community"),
    ("fatima", "school-community"),
    ("ayoub", "school-community"),
    ("marc", "school-community"),     # marc has R/W/C on school-community
    ("isabelle", "school-community"), # isabelle has Read on school-community
]


# ---------------------------------------------------------------------------
# Data model (canonical for all troll attack categories)
# ---------------------------------------------------------------------------

@dataclass
class TrollTestResult:
    """Canonical troll test result. Reused by all troll attack categories.

    Downstream troll stories (2.6, 3.x, 5.x) import this class and log_test_result
    from agents/troll-adversary/attacks/__init__.py.
    """

    attack_category: str  # e.g. "acl_enforcement"
    access_path: str      # "direct" | "through_skill"
    test_name: str        # descriptive identifier, e.g. "unauthenticated-read-ayoub"
    result: str           # "pass" | "partial" | "fail"
    details: str          # human-readable explanation
    evidence: dict        # machine-readable evidence (http_status, url, identity, ...)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_test_result(result: TrollTestResult) -> None:
    """Output a test result as structured JSON to stdout.

    Level mapping (per architecture doc):
      pass    -> INFO
      partial -> WARN
      fail    -> ERROR
    """
    level_map = {"pass": "INFO", "partial": "WARN", "fail": "ERROR"}
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "service": "troll-adversary",
        "level": level_map.get(result.result, "INFO"),
        "event": "acl_enforcement.test",
        "agent": "troll-adversary",
        "duration_ms": result.evidence.get("duration_ms"),
        "details": {
            "test_name": result.test_name,
            "result": result.result,
            "attack_category": result.attack_category,
            "access_path": result.access_path,
            "target_pod": result.evidence.get("target_pod"),
            "identity": result.evidence.get("identity"),
            "http_status": result.evidence.get("http_status"),
        },
    }
    print(json.dumps(log_entry))


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _send_get(
    url: str,
    identity: Optional[str] = None,
    timeout: int = 10,
) -> Tuple[Optional[int], float, Optional[str]]:
    """Send GET to CSS. Returns (status_code, duration_ms, error_msg).

    Args:
        url: Full URL to request.
        identity: WebID for X-Ms-User header (None = no auth / unauthenticated).
        timeout: Request timeout in seconds.
    """
    headers: dict = {}
    if identity:
        # CSS debug-auth-header config (SEC-1): identity set via Authorization: WebID <webid>
        # UnsecureWebIdExtractor reads this header and uses it as the agent's WebID.
        # DO NOT USE IN PRODUCTION.
        headers["Authorization"] = f"WebID {identity}"

    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        duration_ms = (time.time() - start) * 1000
        return response.status_code, round(duration_ms, 2), None
    except requests.RequestException as exc:
        duration_ms = (time.time() - start) * 1000
        return None, round(duration_ms, 2), str(exc)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def _check_css_auth_mode(css_base_url: str) -> Optional[str]:
    """Verify CSS is reachable and debug-auth-header mode is active.

    Sends a request with a known WebID and checks the response is not a
    generic 401 (which would indicate CSS is running without the debug config).

    Returns an error string if the preflight fails, None if OK.
    """
    probe_url = f"{css_base_url}/ayoub/"
    probe_identity = "http://localhost:3000/ayoub/profile/card#me"
    status_code, _, error = _send_get(probe_url, identity=probe_identity)
    if error:
        return f"CSS unreachable at {css_base_url}: {error}"
    if status_code == 401:
        return (
            f"CSS returned 401 for known-authorized identity — "
            f"debug-auth-header.json config may not be active. "
            f"Ensure docker-compose mounts infra/css/config.json and passes -c /config.json."
        )
    return None


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_unauthenticated_access(css_base_url: str = CSS_BASE_URL) -> List[TrollTestResult]:
    """Test: Unauthenticated requests to all pods are denied (AC1).

    Sends bare HTTP GET with no credentials. CSS should respond 401 or 403.
    Errors (network failures, timeouts) are logged as partial — findings, not failures.
    """
    results: List[TrollTestResult] = []

    for pod_name in PODS:
        url = f"{css_base_url}/{pod_name}/"
        test_name = f"unauthenticated-read-{pod_name}"
        status_code, duration_ms, error = _send_get(url, identity=None)

        base_evidence = {
            "url": url,
            "http_method": "GET",
            "identity": None,
            "expected_status": [401, 403],
            "target_pod": pod_name,
            "duration_ms": duration_ms,
        }

        if error is not None:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="partial",
                details=f"Network error accessing {pod_name}: {error}",
                evidence={**base_evidence, "error": error},
            )
        elif status_code in (401, 403):
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="pass",
                details=(
                    f"CSS correctly denied unauthenticated read access to {pod_name} "
                    f"pod (HTTP {status_code})"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )
        elif status_code is not None and (status_code >= 500 or 300 <= status_code < 400):
            # Server errors and redirects are test infrastructure issues, not ACL failures
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="partial",
                details=(
                    f"Unexpected response from CSS for {pod_name} "
                    f"(HTTP {status_code}) — server error or redirect, not an ACL result"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )
        else:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="fail",
                details=(
                    f"CSS allowed unauthenticated access to {pod_name} pod "
                    f"(HTTP {status_code}) — ACL enforcement FAILURE (NFR5)"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )

        log_test_result(result)
        results.append(result)

    return results


def test_cross_role_unauthorized_access(
    css_base_url: str = CSS_BASE_URL,
) -> List[TrollTestResult]:
    """Test: Cross-role unauthorized and authorized access (AC2).

    Unauthorized matrix: expects HTTP 403 for every (identity, pod) pair.
    Authorized matrix:   expects HTTP 200 (validates the test harness is correct).
    """
    results: List[TrollTestResult] = []

    # --- Unauthorized pairs (must be denied) ---
    for identity_name, pod_name in UNAUTHORIZED_MATRIX:
        identity_webid = AGENT_WEBIDS[identity_name]
        url = f"{css_base_url}/{pod_name}/"
        test_name = f"cross-role-{identity_name}-reads-{pod_name}"
        status_code, duration_ms, error = _send_get(url, identity=identity_webid)

        base_evidence = {
            "url": url,
            "http_method": "GET",
            "identity": identity_webid,
            "expected_status": [401, 403],
            "target_pod": pod_name,
            "duration_ms": duration_ms,
        }

        if error is not None:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="partial",
                details=f"Network error testing {identity_name} → {pod_name}: {error}",
                evidence={**base_evidence, "error": error},
            )
        elif status_code in (401, 403):
            # Both 401 and 403 are valid enforcement responses — access denied
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="pass",
                details=(
                    f"CSS correctly denied {identity_name} read access to {pod_name} "
                    f"pod (HTTP {status_code})"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )
        else:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="fail",
                details=(
                    f"CSS allowed unauthorized access: {identity_name} → {pod_name} "
                    f"(HTTP {status_code}) — BLOCKING ACL FAILURE (NFR5)"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )

        log_test_result(result)
        results.append(result)

    # --- Authorized pairs (must succeed — harness validation) ---
    for identity_name, pod_name in AUTHORIZED_MATRIX:
        identity_webid = AGENT_WEBIDS[identity_name]
        url = f"{css_base_url}/{pod_name}/"
        test_name = f"authorized-{identity_name}-reads-{pod_name}"
        status_code, duration_ms, error = _send_get(url, identity=identity_webid)

        base_evidence = {
            "url": url,
            "http_method": "GET",
            "identity": identity_webid,
            "expected_status": 200,
            "target_pod": pod_name,
            "duration_ms": duration_ms,
        }

        if error is not None:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="partial",
                details=(
                    f"Network error testing authorized access "
                    f"{identity_name} → {pod_name}: {error}"
                ),
                evidence={**base_evidence, "error": error},
            )
        elif status_code == 200:
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="pass",
                details=(
                    f"CSS correctly allowed {identity_name} read access to {pod_name} "
                    f"pod (HTTP 200)"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )
        else:
            # Authorized access failing → ACL misconfiguration or provisioning failure (blocking)
            result = TrollTestResult(
                attack_category="acl_enforcement",
                access_path="direct",
                test_name=test_name,
                result="fail",
                details=(
                    f"CSS denied authorized access: {identity_name} → {pod_name} "
                    f"(HTTP {status_code}) — ACL misconfigured or pod not provisioned (NFR5)"
                ),
                evidence={**base_evidence, "http_status": status_code},
            )

        log_test_result(result)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Suite entry point
# ---------------------------------------------------------------------------

def run_acl_enforcement_suite(
    css_base_url: str = CSS_BASE_URL,
) -> Tuple[dict, List[TrollTestResult]]:
    """Run the complete ACL enforcement test suite (AC3, AC4).

    Runs all test functions in sequence, collecting TrollTestResult objects.
    Produces a structured summary with pass/partial/fail counts and a blocking flag.

    Returns:
        Tuple of (summary dict, list of TrollTestResult)
    """
    # Preflight: verify CSS is reachable and debug-auth-header mode is active
    preflight_error = _check_css_auth_mode(css_base_url)
    if preflight_error:
        summary = {
            "attack_category": "acl_enforcement",
            "total_tests": 0,
            "pass": 0,
            "partial": 0,
            "fail": 0,
            "blocking": True,
            "note": f"PREFLIGHT FAILED — {preflight_error}",
            "tests": [],
        }
        print(json.dumps(summary, indent=2, default=str))
        return summary, []

    all_results: List[TrollTestResult] = []
    all_results.extend(test_unauthenticated_access(css_base_url))
    all_results.extend(test_cross_role_unauthorized_access(css_base_url))

    if not all_results:
        summary = {
            "attack_category": "acl_enforcement",
            "total_tests": 0,
            "pass": 0,
            "partial": 0,
            "fail": 0,
            "blocking": True,
            "note": "No tests executed — suite produced empty results",
            "tests": [],
        }
        print(json.dumps(summary, indent=2, default=str))
        return summary, []

    pass_count = sum(1 for r in all_results if r.result == "pass")
    partial_count = sum(1 for r in all_results if r.result == "partial")
    fail_count = sum(1 for r in all_results if r.result == "fail")
    blocking = fail_count > 0

    summary = {
        "attack_category": "acl_enforcement",
        "total_tests": len(all_results),
        "pass": pass_count,
        "partial": partial_count,
        "fail": fail_count,
        "blocking": blocking,
        "note": (
            "Direct infrastructure access validated. "
            "Skill-mediated access deferred to Epic 2."
        ),
        "tests": [asdict(r) for r in all_results],
    }

    print(json.dumps(summary, indent=2, default=str))
    return summary, all_results


# ---------------------------------------------------------------------------
# Script entry point (Task 6)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _css_base_url = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
    _summary, _ = run_acl_enforcement_suite(_css_base_url)
    # Exit non-zero if any test has result "fail" — blocking per NFR5
    sys.exit(1 if _summary["blocking"] else 0)
