"""Consent Grant module — create, revoke, list, and audit consent grants as RDF resources.

Consent grants are written as Turtle resources to a pod's /consent-grants/ container
on CSS. They carry the full consent contract (purpose, scope, excluded data, etc.)
and implement the tombstone revocation pattern (poc:revokedAt populated on revocation,
never deleted).

Architecture:
  - Pipeline-internal layer: imports grant/revoke ACL functions directly from provision_pods.py
  - CSS HTTP PUT/GET: authenticated with provisioner WebID (debug-auth-header mode)
  - JSONL events: appended to data/consent-events.jsonl (telemetry — never blocks governance)
  - Turtle template: infra/css/pods/consent-grant.ttl.j2 (Jinja2)

Isolation notes:
  - CSS operations hit localhost:3000
  - From within distrobox: use distrobox-host-exec for podman exec CSS curl commands
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from jinja2 import Environment, FileSystemLoader
from rdflib import Graph

from pocpod0_pipeline.utils import log_event, repo_root

# ─── paths ───────────────────────────────────────────────────────────────────

_ROOT = repo_root()
_TEMPLATE_DIR = _ROOT / "infra" / "css" / "pods"
_TEMPLATE_NAME = "consent-grant.ttl.j2"
_CONSENT_EVENTS_PATH = _ROOT / "data" / "consent-events.jsonl"
_CSS_BASE_URL = os.environ.get("CSS_BASE_URL", "http://localhost:3000")
_PROVISIONER_WEBID = f"{_CSS_BASE_URL}/provisioner/profile/card#me"


# ─── data classes ─────────────────────────────────────────────────────────────

@dataclass
class ConsentGrantResult:
    grant_id: str
    grant_uri: str
    pod_name: str
    grantee_webid: str
    granted_at: str
    status: str  # "ok" | "error"
    error_message: str = ""


@dataclass
class RevokeGrantResult:
    grant_id: str
    pod_name: str
    grantee_webid: str
    revoked_at: str
    status: str  # "ok" | "error"
    error_message: str = ""


# ─── helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _provisioner_headers(content_type: str = "text/turtle") -> dict:
    return {
        "Authorization": f"WebID {_PROVISIONER_WEBID}",
        "Content-Type": content_type,
    }


def _grantee_slug(grantee_webid: str) -> str:
    """Extract a filesystem-safe slug from a grantee WebID."""
    # e.g. http://localhost:3000/isabelle/profile/card#me -> isabelle
    match = re.search(r'/([^/#]+)/profile/card', grantee_webid)
    if match:
        return match.group(1).lower()
    # fallback: last path segment before # or ?
    slug = re.sub(r'[^a-z0-9\-]', '-', grantee_webid.lower().split('#')[0].split('/')[-1])
    return slug or "grantee"


def _date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _safe_literal(value: str) -> str:
    """Escape a string value for safe embedding in a Turtle string literal.

    Prevents Turtle injection: escapes backslash and double-quote characters.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _emit_consent_event(event: dict) -> None:
    """Append one JSONL line to data/consent-events.jsonl. Never raises."""
    try:
        _CONSENT_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONSENT_EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        print(
            json.dumps({"level": "WARN", "event": "consent_event_write_failed", "error": str(e)}),
            file=sys.stderr,
        )


def _render_turtle(
    grant_uri: str,
    grantee_webid: str,
    purpose: str,
    scope: str,
    excluded: str,
    consequence_of_refusal: str,
    granted_at: str,
    expires_at: str,
) -> str:
    """Render the Jinja2 Turtle template and validate it parses with rdflib."""
    # P-2: reject grantee_webid containing > which would break the IRI in the template
    if ">" in grantee_webid or "<" in grantee_webid:
        raise ValueError(f"grantee_webid contains invalid IRI characters: {grantee_webid!r}")
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=False)
    template = env.get_template(_TEMPLATE_NAME)
    turtle_str = template.render(
        grant_uri=grant_uri,
        grantee_webid=grantee_webid,
        # P-1: escape string literals to prevent Turtle injection
        purpose=_safe_literal(purpose),
        scope=_safe_literal(scope),
        excluded=_safe_literal(excluded),
        consequence_of_refusal=_safe_literal(consequence_of_refusal),
        granted_at=granted_at,
        expires_at=expires_at,
    )
    # Validate: rdflib parse (empty string for poc:revokedAt is valid Turtle)
    g = Graph()
    g.parse(data=turtle_str, format="turtle")
    return turtle_str


def _turtle_set_revoked_at(turtle_str: str, revoked_at: str) -> str:
    """Parse Turtle, replace empty poc:revokedAt with timestamp, re-serialize."""
    from rdflib import Literal, URIRef
    from rdflib.namespace import XSD

    g = Graph()
    g.parse(data=turtle_str, format="turtle")

    poc_ns = "http://localhost:3000/vocab/pocpod0#"
    revoked_at_pred = URIRef(f"{poc_ns}revokedAt")

    # Find subject with poc:revokedAt = ""
    subjects = list(g.subjects(revoked_at_pred, Literal("")))
    if not subjects:
        raise ValueError("poc:revokedAt empty string triple not found in Turtle")

    for subj in subjects:
        g.remove((subj, revoked_at_pred, Literal("")))
        g.add((subj, revoked_at_pred, Literal(revoked_at)))

    return g.serialize(format="turtle")


def _get_pod_acl_provisioner():
    """Return a PodProvisioner configured from environment."""
    from pocpod0_pipeline.provision_pods import PodProvisioner

    css_url = os.environ.get("CSS_CONNECT_URL", _CSS_BASE_URL)
    config_path = _ROOT / "infra" / "css" / "pods" / "pod-config.yaml"
    return PodProvisioner(css_url, str(config_path))


# ─── public API ───────────────────────────────────────────────────────────────

def generate_grant_id(pod_name: str, grantee_webid: str, timestamp: str) -> str:
    """Return a unique, filesystem-safe grant ID slug.

    Format: grant-{pod_name}-{grantee_slug}-{date}
    If a collision would occur (same day, same grantee), callers use
    _resolve_grant_id_collision to find a free suffix.
    """
    slug = _grantee_slug(grantee_webid)
    date_tag = timestamp[:10].replace("-", "")  # YYYYMMDD from ISO-8601
    return f"grant-{pod_name}-{slug}-{date_tag}"


def _resolve_grant_id_no_collision(pod_name: str, base_grant_id: str, max_attempts: int = 9) -> Optional[str]:
    """Check CSS for existence of grant resources; return the first free grant_id.

    Returns None if all attempts are exhausted (should be treated as error).
    """
    # Check base ID first
    grant_uri = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/{base_grant_id}.ttl"
    headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}
    try:
        resp = requests.head(grant_uri, headers=headers, timeout=5)
        if resp.status_code == 404:
            return base_grant_id
    except requests.RequestException:
        return base_grant_id  # assume free if CSS unreachable

    for i in range(2, max_attempts + 1):
        candidate = f"{base_grant_id}-{i}"
        uri = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/{candidate}.ttl"
        try:
            resp = requests.head(uri, headers=headers, timeout=5)
            if resp.status_code == 404:
                return candidate
        except requests.RequestException:
            return candidate
    return None


def create_consent_grant(
    pod_name: str,
    grantee_webid: str,
    purpose: str,
    scope: str,
    excluded: str,
    consequence_of_refusal: str,
    expires_at: str,
) -> ConsentGrantResult:
    """Create a consent grant RDF resource in the pod and grant ACL access.

    Steps:
      1. Generate grant ID; resolve collision
      2. Render and validate Turtle template
      3. HTTP PUT to CSS pod (atomic with ACL grant)
      4. Grant ACL access via provision_pods.py
      5. Emit JSONL event
    """
    granted_at = _now_iso()
    base_id = generate_grant_id(pod_name, grantee_webid, granted_at)
    grant_id = _resolve_grant_id_no_collision(pod_name, base_id)
    if grant_id is None:
        msg = f"Grant ID collision: could not allocate unique ID after 9 attempts for {base_id}"
        log_event("consent.grant.error", "ERROR", {"pod": pod_name, "grantee": grantee_webid, "error": msg})
        return ConsentGrantResult(
            grant_id=base_id, grant_uri="", pod_name=pod_name,
            grantee_webid=grantee_webid, granted_at=granted_at, status="error", error_message=msg,
        )

    grant_uri = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/{grant_id}"
    grant_resource_url = f"{grant_uri}.ttl"

    # Step 2: render + validate Turtle
    try:
        turtle_str = _render_turtle(
            grant_uri=grant_uri,
            grantee_webid=grantee_webid,
            purpose=purpose,
            scope=scope,
            excluded=excluded,
            consequence_of_refusal=consequence_of_refusal,
            granted_at=granted_at,
            expires_at=expires_at,
        )
    except Exception as e:
        msg = f"Turtle render/parse failed: {e}"
        log_event("consent.grant.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
        return ConsentGrantResult(
            grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
            grantee_webid=grantee_webid, granted_at=granted_at, status="error", error_message=msg,
        )

    # Step 3: HTTP PUT to CSS — must succeed before ACL grant
    try:
        headers = _provisioner_headers("text/turtle")
        resp = requests.put(grant_resource_url, headers=headers, data=turtle_str.encode("utf-8"), timeout=10)
        if resp.status_code not in (200, 201, 205):
            msg = f"CSS PUT failed: HTTP {resp.status_code}"
            log_event("consent.grant.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "url": grant_resource_url, "error": msg})
            return ConsentGrantResult(
                grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
                grantee_webid=grantee_webid, granted_at=granted_at, status="error", error_message=msg,
            )
    except requests.RequestException as e:
        msg = f"CSS PUT exception: {e}"
        log_event("consent.grant.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
        return ConsentGrantResult(
            grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
            grantee_webid=grantee_webid, granted_at=granted_at, status="error", error_message=msg,
        )

    # Step 4: grant ACL access — if this fails, attempt to roll back Turtle write
    try:
        provisioner = _get_pod_acl_provisioner()
        acl_ok, acl_msg = provisioner.grant_acl_access(pod_name, grantee_webid, "institutional-grantee", "read")
        if not acl_ok:
            # Roll back: delete the Turtle resource
            try:
                del_headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}
                del_resp = requests.delete(grant_resource_url, headers=del_headers, timeout=10)
                if del_resp.status_code not in (200, 204):
                    log_event("consent.grant.rollback_failed", "ERROR",
                              {"pod": pod_name, "grant_id": grant_id, "url": grant_resource_url,
                               "http_status": del_resp.status_code})
            except Exception as del_exc:
                log_event("consent.grant.rollback_failed", "ERROR",
                          {"pod": pod_name, "grant_id": grant_id, "url": grant_resource_url,
                           "error": str(del_exc)})
            log_event(
                "consent.grant.inconsistency", "ERROR",
                {"pod": pod_name, "grant_id": grant_id, "event": "acl_grant_failed_after_turtle_write", "acl_error": acl_msg},
            )
            return ConsentGrantResult(
                grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
                grantee_webid=grantee_webid, granted_at=granted_at, status="error",
                error_message=f"ACL grant failed (Turtle rolled back): {acl_msg}",
            )
    except Exception as e:
        log_event("consent.grant.inconsistency", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": str(e)})
        return ConsentGrantResult(
            grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
            grantee_webid=grantee_webid, granted_at=granted_at, status="error",
            error_message=f"ACL provisioner exception: {e}",
        )

    # Step 5: emit JSONL consent event (telemetry — never blocks)
    _emit_consent_event({
        "event_type": "consent.grant",
        "timestamp": granted_at,
        "pod": pod_name,
        "grant_id": grant_id,
        "grantee": grantee_webid,
        "purpose": purpose,
    })

    log_event("consent.grant", "INFO", {"pod": pod_name, "grant_id": grant_id, "grantee": grantee_webid, "status": "ok"})
    return ConsentGrantResult(
        grant_id=grant_id, grant_uri=grant_uri, pod_name=pod_name,
        grantee_webid=grantee_webid, granted_at=granted_at, status="ok",
    )


def revoke_consent_grant(pod_name: str, grant_id: str) -> RevokeGrantResult:
    """Revoke a consent grant by applying the tombstone pattern and removing ACL.

    Steps:
      1. Fetch existing Turtle from CSS
      2. Parse + update poc:revokedAt
      3. HTTP PUT updated Turtle back
      4. Revoke ACL access via provision_pods.py
      5. Emit JSONL event
    """
    revoked_at = _now_iso()
    grant_resource_url = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/{grant_id}.ttl"
    headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}

    # Step 1: fetch existing Turtle
    try:
        resp = requests.get(grant_resource_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            msg = f"CSS GET failed: HTTP {resp.status_code}"
            log_event("consent.revoke.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
            return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid="", revoked_at="", status="error", error_message=msg)
        turtle_str = resp.text
    except requests.RequestException as e:
        msg = f"CSS GET exception: {e}"
        log_event("consent.revoke.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
        return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid="", revoked_at="", status="error", error_message=msg)

    # Step 2: parse + extract grantee + update poc:revokedAt
    try:
        from rdflib import URIRef
        g = Graph()
        g.parse(data=turtle_str, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        requested_by_pred = URIRef(f"{poc_ns}requestedBy")
        grantee_webid = str(next(iter(g.objects(None, requested_by_pred)), ""))
        if not grantee_webid:
            raise ValueError("poc:requestedBy not found in grant Turtle — cannot revoke ACL")
        updated_turtle = _turtle_set_revoked_at(turtle_str, revoked_at)
    except Exception as e:
        msg = f"Turtle parse failed: {e}"
        log_event("consent.revoke.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
        return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid="", revoked_at="", status="error", error_message=msg)

    # Step 3: PUT updated Turtle back
    try:
        put_headers = _provisioner_headers("text/turtle")
        resp = requests.put(grant_resource_url, headers=put_headers, data=updated_turtle.encode("utf-8"), timeout=10)
        if resp.status_code not in (200, 201, 205):
            msg = f"CSS PUT (tombstone) failed: HTTP {resp.status_code}"
            log_event("consent.revoke.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
            return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid=grantee_webid, revoked_at="", status="error", error_message=msg)
    except requests.RequestException as e:
        msg = f"CSS PUT (tombstone) exception: {e}"
        log_event("consent.revoke.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": msg})
        return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid=grantee_webid, revoked_at="", status="error", error_message=msg)

    # Step 4: revoke ACL
    try:
        provisioner = _get_pod_acl_provisioner()
        acl_ok, acl_msg = provisioner.revoke_acl_access(pod_name, grantee_webid)
        if not acl_ok:
            log_event("consent.revoke.inconsistency", "ERROR",
                      {"pod": pod_name, "grant_id": grant_id, "event": "acl_revoke_failed", "acl_error": acl_msg})
            # Do NOT fail the revocation — tombstone is written; ACL inconsistency is logged
    except Exception as e:
        log_event("consent.revoke.inconsistency", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": str(e)})

    # Step 5: emit JSONL event
    _emit_consent_event({
        "event_type": "consent.revoke",
        "timestamp": revoked_at,
        "pod": pod_name,
        "grant_id": grant_id,
        "grantee": grantee_webid,
    })

    log_event("consent.revoke", "INFO", {"pod": pod_name, "grant_id": grant_id, "grantee": grantee_webid, "status": "ok"})
    return RevokeGrantResult(grant_id=grant_id, pod_name=pod_name, grantee_webid=grantee_webid, revoked_at=revoked_at, status="ok")


def get_consent_grant(pod_name: str, grant_id: str) -> dict:
    """Fetch and parse a consent grant Turtle resource; return dict of poc: fields.

    Returns empty dict on error (caller should check for empty/missing keys).
    """
    grant_resource_url = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/{grant_id}.ttl"
    headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}"}
    try:
        resp = requests.get(grant_resource_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            log_event("consent.get.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "http_status": resp.status_code})
            return {}
        return _parse_grant_turtle(resp.text)
    except Exception as e:
        log_event("consent.get.error", "ERROR", {"pod": pod_name, "grant_id": grant_id, "error": str(e)})
        return {}


def _parse_grant_turtle(turtle_str: str) -> dict:
    """Parse a consent grant Turtle resource into a plain dict."""
    from rdflib import URIRef, Literal
    poc_ns = "http://localhost:3000/vocab/pocpod0#"
    g = Graph()
    g.parse(data=turtle_str, format="turtle")
    result = {}
    predicates = [
        "requestedBy", "purpose", "scope", "excluded", "consequenceOfRefusal",
        "grantedAt", "revokedAt", "expiresAt",
    ]
    for pred_name in predicates:
        pred = URIRef(f"{poc_ns}{pred_name}")
        val = next(iter(g.objects(None, pred)), None)
        if val is not None:
            # Normalize xsd:dateTime: rdflib emits +00:00 but we want Z suffix
            result[pred_name] = str(val).replace("+00:00", "Z")
    # Grant URI: subject of the ConsentGrant
    grant_type = URIRef(f"{poc_ns}ConsentGrant")
    from rdflib.namespace import RDF
    subj = next(iter(g.subjects(RDF.type, grant_type)), None)
    if subj:
        result["grant_uri"] = str(subj)
    return result


def list_consent_grants(pod_name: str) -> list:
    """List all consent grant summaries for a pod.

    Fetches the /consent-grants/ container from CSS and parses each .ttl resource.
    Returns list of dicts; empty list on error or no grants.
    """
    container_url = f"{_CSS_BASE_URL}/{pod_name}/consent-grants/"
    headers = {"Authorization": f"WebID {_PROVISIONER_WEBID}", "Accept": "text/turtle"}
    try:
        resp = requests.get(container_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            log_event("consent.list.error", "ERROR", {"pod": pod_name, "http_status": resp.status_code})
            return []
        # Parse the container Turtle to find contained .ttl resources
        from rdflib import URIRef
        g = Graph()
        g.parse(data=resp.text, format="turtle")
        contains_pred = URIRef("http://www.w3.org/ns/ldp#contains")
        grant_urls = [str(obj) for obj in g.objects(None, contains_pred) if str(obj).endswith(".ttl")]
        if not grant_urls:
            # Fallback: find any URIs under the container
            base = container_url.rstrip("/")
            grant_urls = [str(obj) for obj in g.objects() if str(obj).startswith(base) and str(obj).endswith(".ttl")]
    except Exception as e:
        log_event("consent.list.error", "ERROR", {"pod": pod_name, "error": str(e)})
        return []

    results = []
    for url in grant_urls:
        grant_id = url.rstrip("/").split("/")[-1].removesuffix(".ttl")
        grant_data = get_consent_grant(pod_name, grant_id)
        if grant_data:
            grant_data["grant_id"] = grant_id
            results.append(grant_data)
    return results


def inject_revocation_filter(query: str, revoked_pod_uris: list) -> str:
    """Inject a SPARQL FILTER clause excluding revoked pod graphs into a query.

    Called AFTER parameterize_query() (post-parameterization, not user-supplied input).
    Inserts FILTER(?attendGraph NOT IN (<uri1>, <uri2>)) before the last closing brace.

    If revoked_pod_uris is empty, returns the query unchanged.

    Args:
        query: Fully parameterized SPARQL query string.
        revoked_pod_uris: List of pod base URIs (e.g. ["http://localhost:3000/ayoub/"]).

    Returns:
        Query string with revocation filter injected, or original query if no revocations.
    """
    if not revoked_pod_uris:
        return query
    # Build FILTER: FILTER(?attendGraph NOT IN (<uri1>, <uri2>))
    uri_list = ", ".join(f"<{uri.rstrip('/')}/>".replace("//", "/") for uri in revoked_pod_uris)
    filter_clause = f"  FILTER(?attendGraph NOT IN ({uri_list}))\n"
    # Insert before the last closing brace of the WHERE block
    last_brace = query.rfind("}")
    if last_brace == -1:
        return query  # malformed query — don't modify
    return query[:last_brace] + filter_clause + query[last_brace:]


def get_revoked_pods(known_pod_names: list) -> list:
    """Return list of pod base URIs whose consent has been revoked.

    For each pod in known_pod_names, fetches grants and checks for non-empty poc:revokedAt.
    Returns full pod base URIs (e.g. "http://localhost:3000/ayoub/") — compatible with
    inject_revocation_filter() which embeds them directly into SPARQL FILTER clauses.
    """
    revoked = []
    for pod_name in known_pod_names:
        grants = list_consent_grants(pod_name)
        for g in grants:
            if g.get("revokedAt", "") != "":
                pod_uri = f"{_CSS_BASE_URL}/{pod_name}/"
                revoked.append(pod_uri)
                break
    return revoked
