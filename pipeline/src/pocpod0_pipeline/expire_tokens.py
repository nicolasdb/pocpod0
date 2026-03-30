"""Expiry check script — pipeline step for ephemeral consent token auto-revocation (BP-5).

Implements AC2 of Story 5.6: checks Oxigraph <urn:token-index> for tokens whose
poc:expiresAt has passed, then for each expired token:
  1. Fetches the grant Turtle from the pod
  2. Populates poc:revokedAt (tombstone — same pattern as Story 5.5 / BP-4)
  3. PUTs the updated Turtle back to the pod
  4. Deregisters the token from <urn:token-index>
  5. Writes an access log receipt to the pod's /access-log/ container
  6. Emits a consent.expired JSONL event to data/consent-events.jsonl

This script is NOT a daemon — it runs once and exits. In production it would be
a scheduled job (cron/Kubernetes CronJob). For the PoC demo it is triggered manually.

Demo sequence:
  1. python pipeline/src/pocpod0_pipeline/consent_grant.py create-ephemeral ...
  2. (mock date past expires_at)
  3. python pipeline/src/pocpod0_pipeline/expire_tokens.py

Isolation notes:
  - Oxigraph SPARQL endpoints: http://localhost:7878/query and /update
  - CSS pod HTTP: http://localhost:3000/{pod}/...
  - From within distrobox: use distrobox-host-exec if containerized
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import requests
from jinja2 import Environment, FileSystemLoader
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import XSD

# Resolve to repo root: pipeline/src/pocpod0_pipeline/expire_tokens.py → 5 parents up
_PROJECT_ROOT = Path(__file__).resolve()
for _ in range(5):
    _PROJECT_ROOT = _PROJECT_ROOT.parent

from pocpod0_pipeline.utils import log_event, repo_root
from pocpod0_pipeline.consent_grant import (
    deregister_token,
    _emit_consent_event,
    _turtle_set_revoked_at,
    _provisioner_headers,
    _PROVISIONER_WEBID,
)

_ROOT = repo_root()
_TEMPLATE_DIR = _ROOT / "infra" / "css" / "pods"
_ACCESS_RECEIPT_TEMPLATE = "access-receipt.ttl.j2"
_CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
_OXIGRAPH_URL = os.environ.get("OXIGRAPH_URL", "http://localhost:7878")


# ─── data classes ─────────────────────────────────────────────────────────────

@dataclass
class ExpiryResult:
    token_id: str
    pod_name: str
    grant_id: str
    expired_at: str
    status: str  # "revoked" | "already_revoked" | "error"
    error_message: str = ""


# ─── helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pod_name_from_uri(pod_uri: str) -> str:
    """Extract pod_name from pod URI, e.g. 'http://localhost:3000/ayoub/' → 'ayoub'."""
    return pod_uri.rstrip("/").split("/")[-1]


def _write_access_receipt(
    pod_name: str,
    token_id: str,
    service_label: str,
    grant_id: str,
    granted_at: str,
    expired_at: str,
    css_base_url: str = _CSS_BASE_URL,
) -> None:
    """Write Turtle access log receipt to /access-log/ in the pod.

    Failure is non-fatal: logs error to stderr but does NOT fail the revocation.
    The receipt is telemetry; the revocation is the critical operation.
    """
    try:
        date_tag = expired_at[:10].replace("-", "")
        receipt_filename = f"camp-food-{date_tag}.ttl"
        receipt_uri = f"{css_base_url}/{pod_name}/access-log/{receipt_filename}"
        receipt_url = receipt_uri

        # Check if receipt already exists (append-style: add suffix if collision)
        head_headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}
        head_resp = requests.head(receipt_url, headers=head_headers, timeout=5)
        if head_resp.status_code != 404:
            for i in range(2, 10):
                receipt_filename = f"camp-food-{date_tag}-{i}.ttl"
                receipt_uri = f"{css_base_url}/{pod_name}/access-log/{receipt_filename}"
                receipt_url = receipt_uri
                head_resp = requests.head(receipt_url, headers=head_headers, timeout=5)
                if head_resp.status_code == 404:
                    break

        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)
        template = env.get_template(_ACCESS_RECEIPT_TEMPLATE)
        turtle_str = template.render(
            receipt_uri=receipt_uri,
            token_id=token_id,
            service_label=service_label,
            grant_id=grant_id,
            granted_at=granted_at,
            expired_at=expired_at,
        )

        put_headers = {
            "Authorization": f"WebID {_PROVISIONER_WEBID}",
            "Content-Type": "text/turtle",
        }
        resp = requests.put(receipt_url, headers=put_headers, data=turtle_str.encode("utf-8"), timeout=10)
        if resp.status_code not in (200, 201, 205):
            print(
                json.dumps({"level": "WARN", "event": "access_receipt_write_failed",
                            "pod": pod_name, "http_status": resp.status_code}),
                file=sys.stderr,
            )
    except Exception as exc:
        print(
            json.dumps({"level": "ERROR", "event": "access_receipt_exception",
                        "pod": pod_name, "error": str(exc)}),
            file=sys.stderr,
        )


def _extract_grant_fields(turtle_str: str) -> dict:
    """Parse ephemeral grant Turtle and return poc: field dict."""
    poc_ns = "http://localhost:3000/vocab/pocpod0#"
    g = Graph()
    g.parse(data=turtle_str, format="turtle")
    result = {}
    for pred_name in ("token", "serviceLabel", "grantedAt", "revokedAt", "expiresAt"):
        val = next(iter(g.objects(None, URIRef(f"{poc_ns}{pred_name}"))), None)
        if val is not None:
            result[pred_name] = str(val).replace("+00:00", "Z")
    return result


# ─── public API ───────────────────────────────────────────────────────────────

def check_expired_tokens(
    oxigraph_url: str = _OXIGRAPH_URL,
    css_base_url: str = _CSS_BASE_URL,
) -> list[ExpiryResult]:
    """Query Oxigraph <urn:token-index> for all tokens with poc:expiresAt <= NOW().

    Returns list of ExpiryResult — empty list if none expired (not an error).
    """
    now = _now_iso()
    query = (
        "PREFIX poc: <http://localhost:3000/vocab/pocpod0#>\n"
        "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"
        "SELECT ?token_id ?pod_uri ?grant_id ?expires_at WHERE {\n"
        "  GRAPH <urn:token-index> {\n"
        "    ?token_uri poc:tokenFor ?pod_uri ;\n"
        "               poc:grantId ?grant_id ;\n"
        "               poc:expiresAt ?expires_at .\n"
        f'    FILTER(?expires_at <= "{now}"^^xsd:dateTime)\n'
        "    BIND(STRAFTER(STR(?token_uri), \"urn:token:\") AS ?token_id)\n"
        "  }\n"
        "}"
    )
    resp = httpx.post(
        f"{oxigraph_url.rstrip('/')}/query",
        content=query.encode("utf-8"),
        headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        timeout=30,
    )
    if resp.status_code != 200:
        log_event("expire_tokens.query_failed", "ERROR",
                  {"http_status": resp.status_code, "body": resp.text[:200]})
        return []

    bindings = resp.json().get("results", {}).get("bindings", [])
    if not bindings:
        return []

    results = []
    for b in bindings:
        token_id = b["token_id"]["value"]
        pod_uri = b["pod_uri"]["value"]
        grant_id = b["grant_id"]["value"]
        expires_at = b["expires_at"]["value"]
        pod_name = _pod_name_from_uri(pod_uri)

        result = revoke_expired_token(
            token_id=token_id,
            grant_id=grant_id,
            pod_name=pod_name,
            expired_at=expires_at,
            oxigraph_url=oxigraph_url,
            css_base_url=css_base_url,
        )
        results.append(result)

    return results


def revoke_expired_token(
    token_id: str,
    grant_id: str,
    pod_name: str,
    expired_at: str,
    oxigraph_url: str = _OXIGRAPH_URL,
    css_base_url: str = _CSS_BASE_URL,
) -> ExpiryResult:
    """Revoke an expired ephemeral token: tombstone Turtle, deregister, emit event, write receipt.

    Idempotent: if poc:revokedAt is already non-empty, logs warning and returns 'already_revoked'.
    Receipt write failure is non-fatal — revocation proceeds regardless.
    """
    grant_resource_url = f"{css_base_url}/{pod_name}/consent-grants/{grant_id}.ttl"
    auth_headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}

    # Step 1: fetch existing Turtle
    try:
        resp = requests.get(grant_resource_url, headers=auth_headers, timeout=10)
        if resp.status_code != 200:
            msg = f"CSS GET failed: HTTP {resp.status_code}"
            log_event("expire_tokens.revoke_error", "ERROR",
                      {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": msg})
            return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                                expired_at=expired_at, status="error", error_message=msg)
        turtle_str = resp.text
    except requests.RequestException as e:
        msg = f"CSS GET exception: {e}"
        log_event("expire_tokens.revoke_error", "ERROR",
                  {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": msg})
        return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                            expired_at=expired_at, status="error", error_message=msg)

    # Step 2: parse fields + check idempotency
    try:
        fields = _extract_grant_fields(turtle_str)
        current_revoked = fields.get("revokedAt", "")
        service_label = fields.get("serviceLabel", "unknown-service")
        granted_at = fields.get("grantedAt", "")

        if current_revoked and current_revoked != "":
            log_event("expire_tokens.already_revoked", "WARN",
                      {"pod": pod_name, "grant_id": grant_id, "token_id": token_id})
            return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                                expired_at=expired_at, status="already_revoked")

        updated_turtle = _turtle_set_revoked_at(turtle_str, expired_at)
    except Exception as e:
        msg = f"Turtle parse/update failed: {e}"
        log_event("expire_tokens.revoke_error", "ERROR",
                  {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": msg})
        return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                            expired_at=expired_at, status="error", error_message=msg)

    # Step 3: PUT updated Turtle (tombstone)
    try:
        put_headers = {
            "Authorization": f"WebID {_PROVISIONER_WEBID}",
            "Content-Type": "text/turtle",
        }
        resp = requests.put(grant_resource_url, headers=put_headers,
                            data=updated_turtle.encode("utf-8"), timeout=10)
        if resp.status_code not in (200, 201, 205):
            msg = f"CSS PUT (tombstone) failed: HTTP {resp.status_code}"
            log_event("expire_tokens.revoke_error", "ERROR",
                      {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": msg})
            return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                                expired_at=expired_at, status="error", error_message=msg)
    except requests.RequestException as e:
        msg = f"CSS PUT exception: {e}"
        log_event("expire_tokens.revoke_error", "ERROR",
                  {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": msg})
        return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                            expired_at=expired_at, status="error", error_message=msg)

    # Step 4: deregister token from index
    try:
        deregister_token(token_id, oxigraph_url)
    except Exception as e:
        log_event("expire_tokens.deregister_failed", "ERROR",
                  {"pod": pod_name, "grant_id": grant_id, "token_id": token_id, "error": str(e)})
        # Do not fail revocation — tombstone is written; index cleanup failure is logged

    # Step 5: write access log receipt (non-fatal on failure)
    _write_access_receipt(
        pod_name=pod_name,
        token_id=token_id,
        service_label=service_label,
        grant_id=grant_id,
        granted_at=granted_at,
        expired_at=expired_at,
        css_base_url=css_base_url,
    )

    # Step 6: emit consent.expired JSONL event
    _emit_consent_event({
        "event_type": "consent.expired",
        "timestamp": _now_iso(),
        "token_id": token_id,
        "pod": pod_name,
        "grant_id": grant_id,
        "expired_at": expired_at,
    })

    print(json.dumps({
        "level": "INFO", "event": "consent.expired",
        "pod": pod_name, "grant_id": grant_id, "token_id": token_id, "expired_at": expired_at,
    }))
    log_event("consent.expired", "INFO", {
        "pod": pod_name, "grant_id": grant_id, "token_id": token_id,
        "expired_at": expired_at, "status": "revoked",
    })

    return ExpiryResult(token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                        expired_at=expired_at, status="revoked")


# ─── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    results = check_expired_tokens()
    if not results:
        print(json.dumps({"level": "INFO", "event": "expire_tokens.no_expired", "count": 0}))
        sys.exit(0)

    for r in results:
        print(json.dumps({
            "level": "INFO" if r.status == "revoked" else "WARN",
            "event": f"expire_tokens.{r.status}",
            "token_id": r.token_id,
            "pod": r.pod_name,
            "grant_id": r.grant_id,
            "expired_at": r.expired_at,
            "error": r.error_message,
        }))

    errors = [r for r in results if r.status == "error"]
    sys.exit(1 if errors else 0)
