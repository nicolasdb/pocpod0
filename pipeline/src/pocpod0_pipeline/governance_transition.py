"""Age-based governance sovereignty transition for Solid pods.

This module implements the structural guarantee that a student's pod transitions
from shared parent/guardian governance to sole ownership when the age threshold
is reached. The transition is enforced via ACL mutation (not policy promises).

Called from:
    scripts/demo-governance-transition.sh
    (NOT from inside OpenClaw — agents use the acl-manage skill for individual
     grant/revoke; the full transition is a pipeline-level operation)

Usage:
    from pocpod0_pipeline.governance_transition import (
        check_transition_eligibility,
        get_guardian_webids,
        execute_transition,
    )
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


# Compute project root: this file is at {root}/pipeline/src/pocpod0_pipeline/
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent  # pipeline/src/pocpod0_pipeline -> root

from pocpod0_pipeline.provision_pods import PodProvisioner


@dataclass
class TransitionResult:
    pod_name: str
    owner_webid: str
    revoked_count: int
    success: bool
    timestamp: str
    error_message: Optional[str] = None
    partial_success: bool = False
    revoked_identities: list = field(default_factory=list)
    failed_revokes: list = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, level: str, details: dict) -> None:
    entry = {
        "timestamp": _now_iso(),
        "service": "governance_transition",
        "level": level,
        "event": event,
        "details": details,
    }
    print(json.dumps(entry), file=sys.stderr)


def _append_consent_event(event: dict) -> None:
    """Append one JSONL line to data/consent-events.jsonl. Never raises."""
    jsonl_path = _PROJECT_ROOT / "data" / "consent-events.jsonl"
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        _log("consent_event_write_failed", "WARN", {"error": str(e), "path": str(jsonl_path)})


def _get_provisioner(css_url: Optional[str] = None) -> PodProvisioner:
    if css_url is None:
        css_url = os.environ.get("CSS_CONNECT_URL", os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000"))
    config_path = _PROJECT_ROOT / "infra" / "css" / "pods" / "pod-config.yaml"
    return PodProvisioner(css_url, str(config_path))


def check_transition_eligibility(pod_name: str, date_of_birth: str, min_age_years: int) -> bool:
    """Check if the pod owner is old enough for sovereignty transition.

    Args:
        pod_name: Pod name (for logging)
        date_of_birth: ISO-8601 date string (YYYY-MM-DD)
        min_age_years: Minimum age in years for full sovereignty (e.g. 16)

    Returns:
        True if age >= min_age_years, False otherwise

    Raises:
        ValueError: if date_of_birth is not a valid ISO-8601 date string
    """
    try:
        dob = date.fromisoformat(date_of_birth)
    except ValueError:
        raise ValueError(f"Invalid date_of_birth format: '{date_of_birth}'. Expected YYYY-MM-DD.")
    today = date.today()

    # Compute age in full years
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    eligible = age >= min_age_years
    _log("eligibility_check", "INFO", {
        "pod": pod_name,
        "date_of_birth": date_of_birth,
        "min_age_years": min_age_years,
        "computed_age": age,
        "eligible": eligible,
    })
    return eligible


def get_guardian_webids(pod_name: str, css_url: Optional[str] = None) -> list[str]:
    """Query the CSS ACL for the pod and return all non-owner WebIDs.

    The pod owner WebID follows the pattern: {CSS_IDENTIFIER_URL}/{pod_name}/profile/card#me
    All other WebIDs in the ACL are guardians to be revoked on transition.

    Args:
        pod_name: Pod name to inspect
        css_url: Override CSS URL (defaults to CSS_CONNECT_URL env var)

    Returns:
        List of guardian WebID URIs (excludes the pod owner WebID)
    """
    # Use same priority as _get_provisioner: CSS_CONNECT_URL first
    css_base_url = os.environ.get("CSS_CONNECT_URL", os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000"))
    owner_webid = f"{css_base_url.rstrip('/')}/{pod_name}/profile/card#me"

    provisioner = _get_provisioner(css_url)
    success, result = provisioner.view_acl_state(pod_name, output_format="human")

    if not success:
        error_msg = result.get("error", "unknown") if isinstance(result, dict) else str(result)
        _log("get_guardian_webids_failed", "ERROR", {
            "pod": pod_name,
            "error": error_msg,
        })
        raise RuntimeError(f"Failed to read ACL for pod '{pod_name}': {error_msg}")

    grants = result.get("acl_grants", [])
    guardians = []
    for g in grants:
        webid = g.get("agent_webid")
        if not webid:
            _log("acl_grant_missing_webid", "WARN", {"pod": pod_name, "grant": g})
            continue
        if webid != owner_webid:
            guardians.append(webid)

    _log("guardian_webids_found", "INFO", {
        "pod": pod_name,
        "owner_webid": owner_webid,
        "guardian_count": len(guardians),
        "guardians": guardians,
    })
    return guardians


def execute_transition(
    pod_name: str,
    owner_webid: str,
    guardian_webids: list[str],
    css_url: Optional[str] = None,
) -> TransitionResult:
    """Execute the sovereignty transition: revoke each guardian, emit audit event.

    Handles partial failure: if one revoke fails, logs the failure and continues
    with remaining revokes. Does not abort mid-transition.

    Args:
        pod_name: Pod name to transition
        owner_webid: WebID of the pod owner (Ayoub)
        guardian_webids: List of guardian WebIDs to revoke
        css_url: Override CSS URL (defaults to CSS_CONNECT_URL env var)

    Returns:
        TransitionResult dataclass with full outcome
    """
    timestamp = _now_iso()
    provisioner = _get_provisioner(css_url)

    _log("transition_started", "INFO", {
        "pod": pod_name,
        "owner_webid": owner_webid,
        "guardian_count": len(guardian_webids),
    })

    revoked = []
    failed = []

    for webid in guardian_webids:
        _log("revoking_guardian", "INFO", {"pod": pod_name, "guardian_webid": webid})
        try:
            success, message = provisioner.revoke_acl_access(pod_name, webid)
            if success:
                revoked.append(webid)
                _log("guardian_revoked", "INFO", {"pod": pod_name, "guardian_webid": webid})
            else:
                failed.append({"webid": webid, "error": message})
                _log("guardian_revoke_failed", "ERROR", {
                    "pod": pod_name,
                    "guardian_webid": webid,
                    "error": message,
                })
        except Exception as e:
            failed.append({"webid": webid, "error": str(e)})
            _log("guardian_revoke_exception", "ERROR", {
                "pod": pod_name,
                "guardian_webid": webid,
                "error": str(e),
            })

    overall_success = len(revoked) > 0 or len(guardian_webids) == 0
    partial = len(failed) > 0 and len(revoked) > 0  # partial = some succeeded AND some failed

    # Emit consent audit event (AC2)
    consent_event = {
        "event_type": "acl.governance.transition",
        "timestamp": timestamp,
        "pod": pod_name,
        "from_role": "shared_governance",
        "to_role": "sole_owner",
        "revoked_identities": revoked,
    }
    if partial:
        consent_event["partial_success"] = True
        consent_event["failed_revokes"] = failed
    _append_consent_event(consent_event)

    result = TransitionResult(
        pod_name=pod_name,
        owner_webid=owner_webid,
        revoked_count=len(revoked),
        success=overall_success,
        timestamp=timestamp,
        partial_success=partial,
        revoked_identities=revoked,
        failed_revokes=failed,
        error_message=f"{len(failed)} revoke(s) failed" if partial else None,
    )

    _log("transition_complete", "INFO", {
        "pod": pod_name,
        "revoked_count": len(revoked),
        "failed_count": len(failed),
        "partial_success": partial,
    })

    return result


def main():
    """CLI entry point for demo script usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Execute age-based governance transition")
    parser.add_argument("--pod-name", required=True, help="Pod name (e.g. ayoub)")
    parser.add_argument("--date-of-birth", required=True, help="ISO-8601 date (YYYY-MM-DD)")
    parser.add_argument("--min-age", type=int, default=16, help="Minimum age for transition (default: 16)")
    parser.add_argument("--dry-run", action="store_true", help="Check eligibility without executing transition")
    args = parser.parse_args()

    try:
        eligible = check_transition_eligibility(args.pod_name, args.date_of_birth, args.min_age)
    except ValueError as e:
        print(json.dumps({"status": "error", "pod": args.pod_name, "message": str(e)}))
        sys.exit(1)

    if not eligible:
        result = {
            "status": "ineligible",
            "pod": args.pod_name,
            "message": f"Pod owner is below the minimum age threshold ({args.min_age} years)",
        }
        print(json.dumps(result))
        sys.exit(1)

    if args.dry_run:
        try:
            guardians = get_guardian_webids(args.pod_name)
        except RuntimeError as e:
            print(json.dumps({"status": "error", "pod": args.pod_name, "message": str(e)}))
            sys.exit(1)
        result = {
            "status": "eligible",
            "pod": args.pod_name,
            "guardian_webids": guardians,
            "message": "Dry run: eligible for transition. Use without --dry-run to execute.",
        }
        print(json.dumps(result))
        sys.exit(0)

    css_base_url = os.environ.get("CSS_CONNECT_URL", os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000"))
    owner_webid = f"{css_base_url.rstrip('/')}/{args.pod_name}/profile/card#me"
    try:
        guardian_webids = get_guardian_webids(args.pod_name)
    except RuntimeError as e:
        print(json.dumps({"status": "error", "pod": args.pod_name, "message": str(e)}))
        sys.exit(1)

    transition = execute_transition(args.pod_name, owner_webid, guardian_webids)

    result = {
        "status": "ok" if transition.success else "error",
        "pod": transition.pod_name,
        "owner_webid": transition.owner_webid,
        "revoked_count": transition.revoked_count,
        "revoked_identities": transition.revoked_identities,
        "partial_success": transition.partial_success,
        "failed_revokes": transition.failed_revokes,
        "timestamp": transition.timestamp,
    }
    print(json.dumps(result))
    sys.exit(0 if transition.success else 1)


if __name__ == "__main__":
    main()
