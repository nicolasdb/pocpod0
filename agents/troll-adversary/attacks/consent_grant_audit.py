"""Troll audit module: consent grant verification.

Answers "why does X have access?" by dereferencing the consent grant RDF resource
in the pod — no CSS ACL query required, no human intermediary.

The consent grant URI is self-describing: it carries purpose, scope, excluded fields,
and the full grant contract. This is the BP-1 (bidirectional accountability) audit path.

Isolation notes:
  - CSS operations hit localhost:3000
  - From within distrobox: use distrobox-host-exec for podman exec CSS curl commands
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add pipeline/src to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "pipeline" / "src"))

from pocpod0_pipeline.consent_grant import list_consent_grants, get_consent_grant


@dataclass
class AuditResult:
    found: bool
    pod_name: str = ""
    grantee_webid: str = ""
    grant_uri: str = ""
    grant_id: str = ""
    purpose: str = ""
    scope: str = ""
    excluded: str = ""
    consequence_of_refusal: str = ""
    granted_at: str = ""
    revoked_at: str = ""
    expires_at: str = ""
    message: str = ""


def audit_consent_grant(pod_name: str, grantee_webid: str) -> AuditResult:
    """Audit who has access and why — answers "why does X have access?".

    Fetches all consent grants for the pod and finds the one matching the grantee.
    Does NOT query CSS ACLs — the consent grant RDF resource is the authoritative source.

    Args:
        pod_name: Pod name to audit (e.g. "ayoub").
        grantee_webid: Full WebID URI of the grantee (e.g. "http://localhost:3000/isabelle/profile/card#me").

    Returns:
        AuditResult with found=True and full grant details, or found=False with message.
    """
    grants = list_consent_grants(pod_name)

    for grant in grants:
        if grant.get("requestedBy", "").rstrip("/") == grantee_webid.rstrip("/"):
            return AuditResult(
                found=True,
                pod_name=pod_name,
                grantee_webid=grantee_webid,
                grant_uri=grant.get("grant_uri", ""),
                grant_id=grant.get("grant_id", ""),
                purpose=grant.get("purpose", ""),
                scope=grant.get("scope", ""),
                excluded=grant.get("excluded", ""),
                consequence_of_refusal=grant.get("consequenceOfRefusal", ""),
                granted_at=grant.get("grantedAt", ""),
                revoked_at=grant.get("revokedAt", ""),
                expires_at=grant.get("expiresAt", ""),
            )

    return AuditResult(
        found=False,
        pod_name=pod_name,
        grantee_webid=grantee_webid,
        message=f"No active consent grant found for <{grantee_webid}> in pod '{pod_name}'",
    )


def format_audit_answer(audit_result: AuditResult) -> str:
    """Return a human-readable paragraph suitable for TUI or troll report display.

    Troll philosophy: failures are first-class citizens. If no grant is found,
    the answer explains why that is suspicious (access without consent grant = policy violation).
    """
    if not audit_result.found:
        return (
            f"No consent grant found for <{audit_result.grantee_webid}> in pod '{audit_result.pod_name}'. "
            f"If this grantee has ACL access without a corresponding consent grant resource, "
            f"that is a policy violation — access was granted without recording the purpose, "
            f"scope, or consequence of refusal. Ayoub cannot inspect or revoke what he cannot see."
        )

    revocation_note = ""
    if audit_result.revoked_at:
        revocation_note = (
            f" NOTE: This grant was REVOKED on {audit_result.revoked_at}. "
            f"The grantee should no longer have ACL access. "
            f"If they still do, that is a tombstone/ACL inconsistency."
        )

    return (
        f"<{audit_result.grantee_webid}> has access to pod '{audit_result.pod_name}' "
        f"under consent grant <{audit_result.grant_uri}>.\n"
        f"  Grant ID:   {audit_result.grant_id}\n"
        f"  Granted at: {audit_result.granted_at}\n"
        f"  Expires at: {audit_result.expires_at}\n"
        f"  Purpose:    {audit_result.purpose}\n"
        f"  Scope:      {audit_result.scope}\n"
        f"  Excluded:   {audit_result.excluded}\n"
        f"  If refused: {audit_result.consequence_of_refusal}"
        f"{revocation_note}"
    )


def run_audit(pod_name: str, grantee_webid: str) -> dict:
    """Run audit and return structured JSON result (for troll report and TUI)."""
    result = audit_consent_grant(pod_name, grantee_webid)
    answer = format_audit_answer(result)
    output = {
        "audit_type": "consent_grant_audit",
        "pod": pod_name,
        "grantee": grantee_webid,
        "found": result.found,
        "answer": answer,
    }
    if result.found:
        output.update({
            "grant_id": result.grant_id,
            "grant_uri": result.grant_uri,
            "purpose": result.purpose,
            "scope": result.scope,
            "excluded": result.excluded,
            "granted_at": result.granted_at,
            "revoked_at": result.revoked_at,
            "expires_at": result.expires_at,
        })
    print(json.dumps(output))
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Consent grant audit — why does X have access?")
    parser.add_argument("--pod", required=True, help="Pod name to audit (e.g. ayoub)")
    parser.add_argument("--grantee", required=True, help="Grantee WebID URI")
    args = parser.parse_args()
    run_audit(args.pod, args.grantee)
