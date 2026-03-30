"""Tests for Story 5.5: consent_grant.py and consent_grant_audit.py.

AC1: Consent grant resource created with full contract
AC2: Troll can answer "why does Isabelle have access?"
AC3: Revocation applies tombstone and removes ACL
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "agents" / "troll-adversary" / "attacks"))

from pocpod0_pipeline.consent_grant import (
    ConsentGrantResult,
    RevokeGrantResult,
    generate_grant_id,
    _grantee_slug,
    _render_turtle,
    _turtle_set_revoked_at,
    _parse_grant_turtle,
    inject_revocation_filter,
    get_revoked_pods,
)

# ─── constants ────────────────────────────────────────────────────────────────

AYOUB_POD = "ayoub"
ISABELLE_WEBID = "http://localhost:3000/isabelle/profile/card#me"
GRANTED_AT = "2026-03-25T10:00:00Z"
EXPIRES_AT = "2027-03-25T00:00:00Z"
PURPOSE = "Justify funding renewal for robotics program"
SCOPE = "Aggregate participant count, avg session attendance"
EXCLUDED = "Individual names, scores, school identifiers"
CONSEQUENCE = "Data excluded from aggregate"


# ─── generate_grant_id ────────────────────────────────────────────────────────

class TestGenerateGrantId:
    def test_standard_format(self):
        grant_id = generate_grant_id(AYOUB_POD, ISABELLE_WEBID, GRANTED_AT)
        assert grant_id == "grant-ayoub-isabelle-20260325"

    def test_filesystem_safe_chars(self):
        grant_id = generate_grant_id(AYOUB_POD, ISABELLE_WEBID, GRANTED_AT)
        assert " " not in grant_id
        assert "/" not in grant_id
        assert "#" not in grant_id

    def test_grantee_slug_extraction(self):
        slug = _grantee_slug(ISABELLE_WEBID)
        assert slug == "isabelle"

    def test_grantee_slug_fallback(self):
        slug = _grantee_slug("http://example.com/unknown")
        assert len(slug) > 0
        assert " " not in slug


# ─── Turtle template rendering ────────────────────────────────────────────────

class TestTurtleTemplate:
    def _render(self, granted_at=GRANTED_AT, expires_at=EXPIRES_AT):
        return _render_turtle(
            grant_uri=f"http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE,
            scope=SCOPE,
            excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE,
            granted_at=granted_at,
            expires_at=expires_at,
        )

    def test_renders_without_error(self):
        turtle = self._render()
        assert len(turtle) > 0

    def test_parses_cleanly_with_rdflib(self):
        from rdflib import Graph
        turtle = self._render()
        g = Graph()
        g.parse(data=turtle, format="turtle")
        assert len(g) > 0

    def test_revokedat_is_empty_string_initially(self):
        turtle = self._render()
        assert 'poc:revokedAt     ""' in turtle or 'poc:revokedAt ""' in turtle or 'revokedAt' in turtle
        # Confirm via rdflib parse
        from rdflib import Graph, URIRef, Literal
        g = Graph()
        g.parse(data=turtle, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        revoked_vals = list(g.objects(None, URIRef(f"{poc_ns}revokedAt")))
        assert len(revoked_vals) == 1
        assert str(revoked_vals[0]) == ""

    def test_all_required_fields_present(self):
        from rdflib import Graph, URIRef
        turtle = self._render()
        g = Graph()
        g.parse(data=turtle, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        for field in ["requestedBy", "purpose", "scope", "excluded",
                      "consequenceOfRefusal", "grantedAt", "revokedAt", "expiresAt"]:
            vals = list(g.objects(None, URIRef(f"{poc_ns}{field}")))
            assert len(vals) == 1, f"Missing field: {field}"

    def test_consent_grant_type_declared(self):
        from rdflib import Graph, URIRef
        from rdflib.namespace import RDF
        turtle = self._render()
        g = Graph()
        g.parse(data=turtle, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        subjects = list(g.subjects(RDF.type, URIRef(f"{poc_ns}ConsentGrant")))
        assert len(subjects) == 1


# ─── _turtle_set_revoked_at ───────────────────────────────────────────────────

class TestTombstoneUpdate:
    def test_sets_revoked_at(self):
        turtle = _render_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, granted_at=GRANTED_AT, expires_at=EXPIRES_AT,
        )
        revoked_at = "2026-04-01T12:00:00Z"
        updated = _turtle_set_revoked_at(turtle, revoked_at)

        from rdflib import Graph, URIRef, Literal
        g = Graph()
        g.parse(data=updated, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        vals = list(g.objects(None, URIRef(f"{poc_ns}revokedAt")))
        assert len(vals) == 1
        assert str(vals[0]) == revoked_at

    def test_empty_string_no_longer_present(self):
        turtle = _render_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, granted_at=GRANTED_AT, expires_at=EXPIRES_AT,
        )
        updated = _turtle_set_revoked_at(turtle, "2026-04-01T12:00:00Z")
        from rdflib import Graph, URIRef, Literal
        g = Graph()
        g.parse(data=updated, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        empty_triples = list(g.triples((None, URIRef(f"{poc_ns}revokedAt"), Literal(""))))
        assert len(empty_triples) == 0


# ─── create_consent_grant ─────────────────────────────────────────────────────

class TestCreateConsentGrant:
    def _mock_provisioner(self, grant_ok=True):
        prov = MagicMock()
        prov.grant_acl_access.return_value = (grant_ok, "ok" if grant_ok else "error")
        return prov

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.head")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_create_success(self, mock_emit, mock_head, mock_put, mock_provisioner):
        mock_head.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(status_code=201)
        mock_provisioner.return_value = self._mock_provisioner(grant_ok=True)

        from pocpod0_pipeline.consent_grant import create_consent_grant
        result = create_consent_grant(
            pod_name=AYOUB_POD, grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
        )

        assert result.status == "ok"
        assert result.grant_id.startswith("grant-ayoub-isabelle-")
        assert result.grantee_webid == ISABELLE_WEBID
        assert result.pod_name == AYOUB_POD
        assert result.grant_uri.startswith("http://localhost:3000/ayoub/consent-grants/")

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.head")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_create_emits_jsonl_event(self, mock_emit, mock_head, mock_put, mock_provisioner):
        mock_head.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(status_code=201)
        mock_provisioner.return_value = self._mock_provisioner(grant_ok=True)

        from pocpod0_pipeline.consent_grant import create_consent_grant
        create_consent_grant(
            pod_name=AYOUB_POD, grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
        )

        mock_emit.assert_called_once()
        event = mock_emit.call_args[0][0]
        assert event["event_type"] == "consent.grant"
        assert event["pod"] == AYOUB_POD
        assert event["grantee"] == ISABELLE_WEBID
        assert event["purpose"] == PURPOSE
        assert "T" in event["timestamp"] and "Z" in event["timestamp"]  # ISO-8601 UTC

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.delete")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.head")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_create_css_put_failure_returns_error(self, mock_emit, mock_head, mock_put, mock_delete, mock_provisioner):
        mock_head.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(status_code=500)
        mock_provisioner.return_value = self._mock_provisioner()

        from pocpod0_pipeline.consent_grant import create_consent_grant
        result = create_consent_grant(
            pod_name=AYOUB_POD, grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
        )

        assert result.status == "error"
        assert "CSS PUT failed" in result.error_message
        mock_provisioner.return_value.grant_acl_access.assert_not_called()

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.delete")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.head")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_create_acl_failure_rolls_back_turtle(self, mock_emit, mock_head, mock_put, mock_delete, mock_provisioner):
        mock_head.return_value = MagicMock(status_code=404)
        mock_put.return_value = MagicMock(status_code=201)
        mock_provisioner.return_value = self._mock_provisioner(grant_ok=False)
        mock_delete.return_value = MagicMock(status_code=200)

        from pocpod0_pipeline.consent_grant import create_consent_grant
        result = create_consent_grant(
            pod_name=AYOUB_POD, grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
        )

        assert result.status == "error"
        mock_delete.assert_called_once()  # rollback triggered


# ─── revoke_consent_grant ─────────────────────────────────────────────────────

class TestRevokeConsentGrant:
    def _sample_turtle(self):
        return _render_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, granted_at=GRANTED_AT, expires_at=EXPIRES_AT,
        )

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.get")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_revoke_success(self, mock_emit, mock_get, mock_put, mock_provisioner):
        mock_get.return_value = MagicMock(status_code=200, text=self._sample_turtle())
        mock_put.return_value = MagicMock(status_code=200)
        prov = MagicMock()
        prov.revoke_acl_access.return_value = (True, "ok")
        mock_provisioner.return_value = prov

        from pocpod0_pipeline.consent_grant import revoke_consent_grant
        result = revoke_consent_grant(AYOUB_POD, "grant-ayoub-isabelle-20260325")

        assert result.status == "ok"
        assert result.revoked_at != ""
        assert "T" in result.revoked_at and "Z" in result.revoked_at

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.get")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_revoke_populates_revokedat_in_turtle(self, mock_emit, mock_get, mock_put, mock_provisioner):
        mock_get.return_value = MagicMock(status_code=200, text=self._sample_turtle())
        mock_put.return_value = MagicMock(status_code=200)
        prov = MagicMock()
        prov.revoke_acl_access.return_value = (True, "ok")
        mock_provisioner.return_value = prov

        from pocpod0_pipeline.consent_grant import revoke_consent_grant
        result = revoke_consent_grant(AYOUB_POD, "grant-ayoub-isabelle-20260325")

        # Verify PUT was called with non-empty revokedAt in the body
        put_body = mock_put.call_args[1]["data"].decode("utf-8")
        from rdflib import Graph, URIRef
        g = Graph()
        g.parse(data=put_body, format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        revoked_vals = list(g.objects(None, URIRef(f"{poc_ns}revokedAt")))
        assert len(revoked_vals) == 1
        assert str(revoked_vals[0]) != ""

    @patch("pocpod0_pipeline.consent_grant._get_pod_acl_provisioner")
    @patch("pocpod0_pipeline.consent_grant.requests.put")
    @patch("pocpod0_pipeline.consent_grant.requests.get")
    @patch("pocpod0_pipeline.consent_grant._emit_consent_event")
    def test_revoke_emits_jsonl_event(self, mock_emit, mock_get, mock_put, mock_provisioner):
        mock_get.return_value = MagicMock(status_code=200, text=self._sample_turtle())
        mock_put.return_value = MagicMock(status_code=200)
        prov = MagicMock()
        prov.revoke_acl_access.return_value = (True, "ok")
        mock_provisioner.return_value = prov

        from pocpod0_pipeline.consent_grant import revoke_consent_grant
        revoke_consent_grant(AYOUB_POD, "grant-ayoub-isabelle-20260325")

        mock_emit.assert_called_once()
        event = mock_emit.call_args[0][0]
        assert event["event_type"] == "consent.revoke"
        assert event["pod"] == AYOUB_POD

    @patch("pocpod0_pipeline.consent_grant.requests.get")
    def test_revoke_css_get_failure_returns_error(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)

        from pocpod0_pipeline.consent_grant import revoke_consent_grant
        result = revoke_consent_grant(AYOUB_POD, "grant-ayoub-isabelle-20260325")

        assert result.status == "error"
        assert "CSS GET failed" in result.error_message


# ─── get_consent_grant ────────────────────────────────────────────────────────

class TestGetConsentGrant:
    def _sample_turtle(self):
        return _render_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            grantee_webid=ISABELLE_WEBID,
            purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE, granted_at=GRANTED_AT, expires_at=EXPIRES_AT,
        )

    @patch("pocpod0_pipeline.consent_grant.requests.get")
    def test_returns_parsed_fields(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text=self._sample_turtle())

        from pocpod0_pipeline.consent_grant import get_consent_grant
        result = get_consent_grant(AYOUB_POD, "grant-ayoub-isabelle-20260325")

        assert result["purpose"] == PURPOSE
        assert result["scope"] == SCOPE
        assert result["excluded"] == EXCLUDED
        assert result["grantedAt"] == GRANTED_AT
        assert result["revokedAt"] == ""

    @patch("pocpod0_pipeline.consent_grant.requests.get")
    def test_returns_empty_dict_on_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)

        from pocpod0_pipeline.consent_grant import get_consent_grant
        result = get_consent_grant(AYOUB_POD, "nonexistent-grant")

        assert result == {}


# ─── list_consent_grants ──────────────────────────────────────────────────────

class TestListConsentGrants:
    def _container_turtle(self, grant_ids):
        base = "http://localhost:3000/ayoub/consent-grants/"
        lines = [
            "@prefix ldp: <http://www.w3.org/ns/ldp#> .",
            f"<{base}> ldp:contains",
        ]
        entries = [f"  <{base}{gid}.ttl>" for gid in grant_ids]
        lines.append(" ,\n".join(entries) + " .")
        return "\n".join(lines)

    @patch("pocpod0_pipeline.consent_grant.get_consent_grant")
    @patch("pocpod0_pipeline.consent_grant.requests.get")
    def test_returns_list_of_summaries(self, mock_get, mock_get_grant):
        container_ttl = self._container_turtle(["grant-ayoub-isabelle-20260325"])
        mock_get.return_value = MagicMock(status_code=200, text=container_ttl)
        mock_get_grant.return_value = {
            "purpose": PURPOSE, "scope": SCOPE, "revokedAt": "",
            "grant_uri": "http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
        }

        from pocpod0_pipeline.consent_grant import list_consent_grants
        results = list_consent_grants(AYOUB_POD)

        assert len(results) == 1
        assert results[0]["purpose"] == PURPOSE

    @patch("pocpod0_pipeline.consent_grant.requests.get")
    def test_returns_empty_list_on_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)

        from pocpod0_pipeline.consent_grant import list_consent_grants
        results = list_consent_grants(AYOUB_POD)

        assert results == []


# ─── SPARQL revocation filter injection ───────────────────────────────────────

class TestInjectRevocationFilter:
    def _sample_query(self):
        return (
            "SELECT ?x WHERE {\n"
            "  GRAPH ?attendGraph { ?x a <http://example.org/Thing> . }\n"
            "}"
        )

    def test_no_revocations_returns_unchanged(self):
        query = self._sample_query()
        result = inject_revocation_filter(query, [])
        assert result == query

    def test_one_revoked_pod_injects_filter(self):
        query = self._sample_query()
        result = inject_revocation_filter(query, ["http://localhost:3000/ayoub/"])
        assert "FILTER(?attendGraph NOT IN" in result
        assert "ayoub" in result

    def test_multiple_revoked_pods(self):
        query = self._sample_query()
        result = inject_revocation_filter(
            query, ["http://localhost:3000/ayoub/", "http://localhost:3000/marc/"]
        )
        assert "ayoub" in result
        assert "marc" in result

    def test_filter_before_closing_brace(self):
        query = self._sample_query()
        result = inject_revocation_filter(query, ["http://localhost:3000/ayoub/"])
        assert result.rstrip().endswith("}")

    def test_get_revoked_pods_returns_revoked(self):
        with patch("pocpod0_pipeline.consent_grant.list_consent_grants") as mock_list:
            mock_list.return_value = [{"revokedAt": "2026-04-01T12:00:00Z", "purpose": PURPOSE}]
            revoked = get_revoked_pods(["ayoub"])
            assert any("ayoub" in uri for uri in revoked)
            assert all(uri.startswith("http") for uri in revoked)

    def test_get_revoked_pods_skips_active(self):
        with patch("pocpod0_pipeline.consent_grant.list_consent_grants") as mock_list:
            mock_list.return_value = [{"revokedAt": "", "purpose": PURPOSE}]
            revoked = get_revoked_pods(["ayoub"])
            assert revoked == []


# ─── JSONL event emission ─────────────────────────────────────────────────────

class TestJsonlEventEmission:
    def test_grant_event_schema(self):
        from pocpod0_pipeline.consent_grant import _emit_consent_event
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        with patch("pocpod0_pipeline.consent_grant._CONSENT_EVENTS_PATH", path):
            _emit_consent_event({
                "event_type": "consent.grant",
                "timestamp": GRANTED_AT,
                "pod": AYOUB_POD,
                "grant_id": "grant-ayoub-isabelle-20260325",
                "grantee": ISABELLE_WEBID,
                "purpose": PURPOSE,
            })

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "consent.grant"
        assert event["pod"] == AYOUB_POD
        assert event["grantee"] == ISABELLE_WEBID
        assert event["timestamp"] == GRANTED_AT

        path.unlink()

    def test_revoke_event_schema(self):
        from pocpod0_pipeline.consent_grant import _emit_consent_event
        with tempfile.NamedTemporaryFile(mode="r", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        with patch("pocpod0_pipeline.consent_grant._CONSENT_EVENTS_PATH", path):
            _emit_consent_event({
                "event_type": "consent.revoke",
                "timestamp": "2026-04-01T12:00:00Z",
                "pod": AYOUB_POD,
                "grant_id": "grant-ayoub-isabelle-20260325",
                "grantee": ISABELLE_WEBID,
            })

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "consent.revoke"
        assert "purpose" not in event  # revoke event has no purpose field

        path.unlink()


# ─── Troll audit ──────────────────────────────────────────────────────────────

class TestAuditConsentGrant:
    def _sample_grant(self):
        return {
            "requestedBy": ISABELLE_WEBID,
            "purpose": PURPOSE,
            "scope": SCOPE,
            "excluded": EXCLUDED,
            "consequenceOfRefusal": CONSEQUENCE,
            "grantedAt": GRANTED_AT,
            "revokedAt": "",
            "expiresAt": EXPIRES_AT,
            "grant_uri": "http://localhost:3000/ayoub/consent-grants/grant-ayoub-isabelle-20260325",
            "grant_id": "grant-ayoub-isabelle-20260325",
        }

    @patch("consent_grant_audit.list_consent_grants")
    def test_found_returns_full_details(self, mock_list):
        mock_list.return_value = [self._sample_grant()]

        from consent_grant_audit import audit_consent_grant
        result = audit_consent_grant(AYOUB_POD, ISABELLE_WEBID)

        assert result.found is True
        assert result.purpose == PURPOSE
        assert result.scope == SCOPE
        assert result.excluded == EXCLUDED
        assert result.grant_uri != ""

    @patch("consent_grant_audit.list_consent_grants")
    def test_not_found_returns_message(self, mock_list):
        mock_list.return_value = []

        from consent_grant_audit import audit_consent_grant
        result = audit_consent_grant(AYOUB_POD, ISABELLE_WEBID)

        assert result.found is False
        assert "No active consent grant found" in result.message

    @patch("consent_grant_audit.list_consent_grants")
    def test_format_answer_contains_required_fields(self, mock_list):
        mock_list.return_value = [self._sample_grant()]

        from consent_grant_audit import audit_consent_grant, format_audit_answer
        result = audit_consent_grant(AYOUB_POD, ISABELLE_WEBID)
        answer = format_audit_answer(result)

        assert PURPOSE in answer
        assert SCOPE in answer
        assert EXCLUDED in answer

    @patch("consent_grant_audit.list_consent_grants")
    def test_format_answer_not_found_explains_policy_violation(self, mock_list):
        mock_list.return_value = []

        from consent_grant_audit import audit_consent_grant, format_audit_answer
        result = audit_consent_grant(AYOUB_POD, ISABELLE_WEBID)
        answer = format_audit_answer(result)

        assert "policy violation" in answer.lower() or "No consent grant" in answer

    @patch("consent_grant_audit.list_consent_grants")
    def test_format_answer_revoked_includes_note(self, mock_list):
        grant = self._sample_grant()
        grant["revokedAt"] = "2026-04-01T12:00:00Z"
        mock_list.return_value = [grant]

        from consent_grant_audit import audit_consent_grant, format_audit_answer
        result = audit_consent_grant(AYOUB_POD, ISABELLE_WEBID)
        answer = format_audit_answer(result)

        assert "REVOKED" in answer or "revoked" in answer.lower()
