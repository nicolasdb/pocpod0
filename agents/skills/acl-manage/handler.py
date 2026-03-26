"""ACL Management Skill handler for OpenClaw agents.

CLI invocation pattern (used by OpenClaw exec tool):
    python handler.py --action ACTION \
                      --pod-name POD_NAME \
                      [--identity WEBID] \
                      [--role ROLE_LABEL] \
                      [--access-level read|read/write|control]

Actions:
    grant       Grant a WebID access to the pod
    revoke      Revoke a WebID's access from the pod
    view        View current ACL state (read-only)
    transition  Age-based sovereignty transition (revoke all guardians)

Output:
    Structured JSON log lines to stderr; final result JSON to stdout.
    Exit code 0 on ok, 1 on denied or error.

Environment variables:
    CSS_CONNECT_URL       TCP endpoint for CSS (default: http://localhost:3000)
    CSS_IDENTIFIER_URL    Identifier-space base URL (default: same as CSS_CONNECT_URL)
    AGENT_POD_OWNERSHIP   Comma-separated pod names this agent owns (required for mutations)
    AGENT_ID              Agent identifier for denied-event logging (optional)

Security:
    SEC-OWN: Ownership check happens BEFORE any ACL mutation.
    view action is permitted regardless of ownership scope.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Compute project root: handler.py is at {root}/agents/skills/acl-manage/handler.py
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent  # agents/skills/acl-manage -> root

# Add pipeline src to path so we can import provision_pods
_PIPELINE_SRC = _PROJECT_ROOT / "pipeline" / "src"
if str(_PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_SRC))

from pocpod0_pipeline.provision_pods import PodProvisioner


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_provisioner() -> PodProvisioner:
    css_url = os.environ.get("CSS_CONNECT_URL", os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000"))
    config_path = _PROJECT_ROOT / "infra" / "css" / "pods" / "pod-config.yaml"
    return PodProvisioner(css_url, str(config_path))


def _get_owned_pods() -> list[str]:
    raw = os.environ.get("AGENT_POD_OWNERSHIP", "")
    if not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _get_agent_id() -> str:
    return os.environ.get("AGENT_ID", "unknown-agent")


def _append_consent_event(event: dict) -> None:
    """Append one JSONL line to data/consent-events.jsonl. Never raises."""
    jsonl_path = _PROJECT_ROOT / "data" / "consent-events.jsonl"
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        print(json.dumps({"level": "WARN", "event": "consent_event_write_failed", "error": str(e)}), file=sys.stderr)


def _emit_denied(action: str, pod_name: str, identity: str | None, reason: str) -> dict:
    agent_id = _get_agent_id()
    event = {
        "event_type": "acl.denied",
        "timestamp": _now_iso(),
        "pod": pod_name,
        "agent_id": agent_id,
        "action": action,
        "reason": reason,
    }
    if identity:
        event["identity"] = identity
    _append_consent_event(event)
    return {
        "status": "denied",
        "action": action,
        "pod": pod_name,
        "identity": identity,
        "event_type": "acl.denied",
        "message": reason,
    }


def _check_ownership(action: str, pod_name: str, identity: str | None) -> dict | None:
    """Return denied result dict if not authorized, else None."""
    if action == "view":
        return None  # view is always permitted
    owned = _get_owned_pods()
    if not owned:
        agent_id = _get_agent_id()
        reason = f"Authorization denied: agent {agent_id} does not own pod {pod_name}"
        return _emit_denied(action, pod_name, identity, reason)
    if pod_name not in owned:
        agent_id = _get_agent_id()
        reason = f"Authorization denied: agent {agent_id} does not own pod {pod_name}"
        return _emit_denied(action, pod_name, identity, reason)
    return None


def action_grant(provisioner: PodProvisioner, pod_name: str, identity: str, role: str, access_level: str) -> dict:
    denial = _check_ownership("grant", pod_name, identity)
    if denial:
        return denial

    try:
        success, message = provisioner.grant_acl_access(pod_name, identity, role, access_level)
    except Exception as e:
        return {"status": "error", "action": "grant", "pod": pod_name, "message": f"CSS error: {e}"}

    if not success:
        return {"status": "error", "action": "grant", "pod": pod_name, "message": message}

    event = {
        "event_type": "acl.grant",
        "timestamp": _now_iso(),
        "pod": pod_name,
        "identity": identity,
        "action": "grant",
        "role": role,
        "access_level": access_level,
    }
    _append_consent_event(event)
    return {
        "status": "ok",
        "action": "grant",
        "pod": pod_name,
        "identity": identity,
        "event_type": "acl.grant",
        "message": message,
    }


def action_revoke(provisioner: PodProvisioner, pod_name: str, identity: str) -> dict:
    denial = _check_ownership("revoke", pod_name, identity)
    if denial:
        return denial

    try:
        success, message = provisioner.revoke_acl_access(pod_name, identity)
    except Exception as e:
        return {"status": "error", "action": "revoke", "pod": pod_name, "message": f"CSS error: {e}"}

    if not success:
        return {"status": "error", "action": "revoke", "pod": pod_name, "message": message}

    event = {
        "event_type": "acl.revoke",
        "timestamp": _now_iso(),
        "pod": pod_name,
        "identity": identity,
        "action": "revoke",
    }
    _append_consent_event(event)
    return {
        "status": "ok",
        "action": "revoke",
        "pod": pod_name,
        "identity": identity,
        "event_type": "acl.revoke",
        "message": message,
    }


def action_view(provisioner: PodProvisioner, pod_name: str) -> dict:
    # view never requires ownership check
    try:
        success, result = provisioner.view_acl_state(pod_name, output_format="human")
    except Exception as e:
        return {"status": "error", "action": "view", "pod": pod_name, "message": f"CSS error: {e}"}

    if not success:
        error_msg = result.get("error", "unknown error") if isinstance(result, dict) else str(result)
        return {"status": "error", "action": "view", "pod": pod_name, "message": error_msg}

    grants = result.get("acl_grants", [])
    event = {
        "event_type": "acl.view",
        "timestamp": _now_iso(),
        "pod": pod_name,
        "action": "view",
        "grant_count": len(grants),
    }
    _append_consent_event(event)
    return {
        "status": "ok",
        "action": "view",
        "pod": pod_name,
        "event_type": "acl.view",
        "acl_grants": grants,
        "message": f"ACL state for {pod_name}: {len(grants)} grant(s)",
    }


def action_transition(provisioner: PodProvisioner, pod_name: str) -> dict:
    denial = _check_ownership("transition", pod_name, None)
    if denial:
        return denial

    # Identify owner WebID and guardian WebIDs from current ACL
    # Use same priority as _get_provisioner: CSS_CONNECT_URL first
    css_base_url = os.environ.get("CSS_CONNECT_URL", os.environ.get("CSS_IDENTIFIER_URL", "http://localhost:3000"))
    owner_webid = f"{css_base_url.rstrip('/')}/{pod_name}/profile/card#me"

    try:
        success, result = provisioner.view_acl_state(pod_name, output_format="human")
    except Exception as e:
        return {"status": "error", "action": "transition", "pod": pod_name, "message": f"CSS error reading ACL: {e}"}

    if not success:
        error_msg = result.get("error", "ACL read failed") if isinstance(result, dict) else str(result)
        return {"status": "error", "action": "transition", "pod": pod_name, "message": error_msg}

    grants = result.get("acl_grants", [])
    guardian_webids = []
    for g in grants:
        webid = g.get("agent_webid")
        if not webid:
            print(json.dumps({"level": "WARN", "event": "acl_grant_missing_webid", "pod": pod_name, "grant": g}), file=sys.stderr)
            continue
        if webid != owner_webid:
            guardian_webids.append(webid)

    revoked = []
    errors = []
    for webid in guardian_webids:
        try:
            ok, msg = provisioner.revoke_acl_access(pod_name, webid)
            if ok:
                revoked.append(webid)
            else:
                errors.append({"webid": webid, "error": msg})
        except Exception as e:
            errors.append({"webid": webid, "error": str(e)})

    partial = len(errors) > 0
    event = {
        "event_type": "acl.governance.transition",
        "timestamp": _now_iso(),
        "pod": pod_name,
        "from_role": "shared_governance",
        "to_role": "sole_owner",
        "revoked_identities": revoked,
    }
    if partial:
        event["partial_failure"] = errors
    _append_consent_event(event)

    status = "ok" if not partial else "partial"
    msg = f"Transition complete: {len(revoked)} guardian(s) revoked"
    if partial:
        msg += f"; {len(errors)} revoke(s) failed (see partial_failure)"
    return {
        "status": status,
        "action": "transition",
        "pod": pod_name,
        "event_type": "acl.governance.transition",
        "revoked_identities": revoked,
        "partial_failure": errors if partial else [],
        "message": msg,
    }


def main():
    parser = argparse.ArgumentParser(description="ACL management skill handler")
    parser.add_argument("--action", required=True, choices=["grant", "revoke", "view", "transition"])
    parser.add_argument("--pod-name", required=True)
    parser.add_argument("--identity", default=None)
    parser.add_argument("--role", default=None)
    parser.add_argument("--access-level", default="read")
    args = parser.parse_args()

    # Validate required args per action
    if args.action == "grant":
        if not args.identity:
            print(json.dumps({"status": "error", "action": "grant", "message": "--identity required for grant"}))
            sys.exit(1)
        if not args.role:
            print(json.dumps({"status": "error", "action": "grant", "message": "--role required for grant"}))
            sys.exit(1)
    elif args.action == "revoke":
        if not args.identity:
            print(json.dumps({"status": "error", "action": "revoke", "message": "--identity required for revoke"}))
            sys.exit(1)

    try:
        provisioner = _get_provisioner()
    except Exception as e:
        print(json.dumps({"status": "error", "action": args.action, "message": f"Failed to initialize provisioner: {e}"}))
        sys.exit(1)

    if args.action == "grant":
        result = action_grant(provisioner, args.pod_name, args.identity, args.role, args.access_level)
    elif args.action == "revoke":
        result = action_revoke(provisioner, args.pod_name, args.identity)
    elif args.action == "view":
        result = action_view(provisioner, args.pod_name)
    elif args.action == "transition":
        result = action_transition(provisioner, args.pod_name)

    print(json.dumps(result))
    sys.exit(0 if result["status"] in ("ok", "partial") else 1)


if __name__ == "__main__":
    main()
