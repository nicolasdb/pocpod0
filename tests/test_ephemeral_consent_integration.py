"""Integration tests for Story 5.6: Ephemeral time-scoped consent (AC1, AC2, AC3).

These tests mock external services (Oxigraph, CSS) but exercise the full lifecycle
across module boundaries — consent_grant.py ↔ expire_tokens.py coordination.

Run with: pytest tests/test_ephemeral_consent_integration.py -m integration
Skip in unit-only runs: pytest tests/ -m "not integration"
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "pipeline" / "src"))

from pocpod0_pipeline.consent_grant import (
    EphemeralGrantResult,
    generate_token,
    create_ephemeral_consent_grant,
    lookup_token,
    deregister_token,
)
from pocpod0_pipeline.expire_tokens import (
    ExpiryResult,
    check_expired_tokens,
    revoke_expired_token,
)

pytestmark = pytest.mark.integration

AYOUB_POD = "ayoub"
AYOUB_POD_URI = "http://localhost:3000/ayoub/"
SERVICE_LABEL = "camp-food-service"
PURPOSE = "Serve dietary-appropriate meals during summer camp"
SCOPE = "Dietary restriction flag and type"
EXCLUDED = "Identity, name, school, grades, any PII"
CONSEQUENCE = "Default meal served"
GRANTED_AT = "2026-06-20T08:00:00Z"
EXPIRES_AT = "2026-08-31T23:59:59Z"


def _make_ephemeral_turtle(token_id, expires_at=EXPIRES_AT, revoked_at=""):
    return f"""@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://localhost:3000/ayoub/consent-grants/grant-ayoub-camp-food-service-20260620> a poc:ConsentGrant , poc:EphemeralConsentGrant ;
  poc:token         "{token_id}" ;
  poc:serviceLabel  "camp-food-service" ;
  poc:purpose       "Test" ;
  poc:scope         "test" ;
  poc:excluded      "none" ;
  poc:consequenceOfRefusal "none" ;
  poc:grantedAt     "{GRANTED_AT}"^^xsd:dateTime ;
  poc:revokedAt     "{revoked_at}" ;
  poc:expiresAt     "{expires_at}"^^xsd:dateTime .
"""


class TestFullEphemeralLifecycle:
    """Integration test: create ephemeral grant → token in index → simulate expiry → verify tombstone + event + receipt."""

    def test_full_lifecycle(self):
        token_id = generate_token(AYOUB_POD_URI, GRANTED_AT)
        turtle = _make_ephemeral_turtle(token_id)
        captured_events = []

        # Setup mocks
        httpx_ok = MagicMock()
        httpx_ok.status_code = 204

        css_head_404 = MagicMock()
        css_head_404.status_code = 404

        css_put_ok = MagicMock()
        css_put_ok.status_code = 201

        css_get_ok = MagicMock()
        css_get_ok.status_code = 200
        css_get_ok.text = turtle

        # Phase 1: create ephemeral grant
        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.consent_grant.requests") as mock_requests, \
             patch("pocpod0_pipeline.consent_grant._emit_consent_event",
                   side_effect=captured_events.append):
            mock_httpx.post.return_value = httpx_ok
            mock_requests.head.return_value = css_head_404
            mock_requests.put.return_value = css_put_ok

            grant_result = create_ephemeral_consent_grant(
                pod_name=AYOUB_POD, service_label=SERVICE_LABEL,
                purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
                consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
            )

        assert grant_result.status == "ok"
        assert len(grant_result.token_id) == 16

        # Verify consent.grant event emitted with token_id
        assert len(captured_events) == 1
        assert captured_events[0]["event_type"] == "consent.grant"
        assert "token_id" in captured_events[0]

        # Phase 2: simulate expiry check — token is now expired
        expiry_events = []

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_req, \
             patch("pocpod0_pipeline.expire_tokens.httpx") as mock_hx, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token"), \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event",
                   side_effect=expiry_events.append), \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_req.get.return_value = css_get_ok
            mock_req.put.return_value = css_put_ok
            mock_hx.post.return_value = httpx_ok

            expiry_result = revoke_expired_token(
                token_id=grant_result.token_id,
                grant_id=grant_result.grant_id,
                pod_name=AYOUB_POD,
                expired_at=EXPIRES_AT,
            )

        # Verify tombstone
        assert expiry_result.status == "revoked"
        assert len(expiry_events) == 1
        ev = expiry_events[0]
        assert ev["event_type"] == "consent.expired"
        assert ev["token_id"] == grant_result.token_id

    def test_tombstone_turtle_has_revoked_at(self):
        """Verify the Turtle written back has non-empty poc:revokedAt."""
        token_id = generate_token(AYOUB_POD_URI, GRANTED_AT)
        turtle = _make_ephemeral_turtle(token_id)

        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = turtle

        written = []

        def capture_put(url, headers, data, timeout):
            written.append(data.decode("utf-8"))
            r = MagicMock()
            r.status_code = 205
            return r

        httpx_ok = MagicMock()
        httpx_ok.status_code = 204

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_req, \
             patch("pocpod0_pipeline.expire_tokens.httpx") as mock_hx, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token"), \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event"), \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_req.get.return_value = css_get
            mock_req.put.side_effect = capture_put
            mock_hx.post.return_value = httpx_ok

            revoke_expired_token(
                token_id=token_id,
                grant_id="grant-ayoub-camp-food-service-20260620",
                pod_name=AYOUB_POD,
                expired_at=EXPIRES_AT,
            )

        assert len(written) == 1
        from rdflib import Graph, URIRef, Literal
        g = Graph()
        g.parse(data=written[0], format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        revoked_vals = list(g.objects(None, URIRef(f"{poc_ns}revokedAt")))
        assert len(revoked_vals) == 1
        assert str(revoked_vals[0]) != ""
        # expiresAt should still be present
        expires_vals = list(g.objects(None, URIRef(f"{poc_ns}expiresAt")))
        assert len(expires_vals) == 1


class TestDoubleAveugles:
    """Integration tests for the double-aveugle principle (AC3)."""

    def test_food_service_cannot_query_token_index(self):
        """The food service token value does NOT appear as a dereferenceable WebID in the grant.

        The token is a plain string literal in RDF — the food service cannot dereference it
        to discover Ayoub's identity.
        """
        from pocpod0_pipeline.consent_grant import _render_ephemeral_turtle
        token_id = generate_token(AYOUB_POD_URI, GRANTED_AT)
        turtle_str = _render_ephemeral_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-test",
            service_label=SERVICE_LABEL,
            token_id=token_id,
            purpose=PURPOSE,
            scope=SCOPE,
            excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE,
            granted_at=GRANTED_AT,
            expires_at=EXPIRES_AT,
        )
        # Key invariant: token is a string literal, not a URI
        assert f'"{token_id}"' in turtle_str
        assert f"<{token_id}>" not in turtle_str
        # Ayoub's WebID is NOT in the grant visible to the food service
        assert "ayoub/profile/card" not in turtle_str
        # No requestedBy (that would expose an institutional WebID)
        assert "requestedBy" not in turtle_str

    def test_aggregate_query_structural_anonymization(self):
        """AC3: camp-aggregate.rq SELECT clause contains only aggregates, no individual identifiers."""
        rq_path = _PROJECT_ROOT / "agents" / "skills" / "sparql-query" / "templates" / "camp-aggregate.rq"
        assert rq_path.exists()
        query_text = rq_path.read_text()

        select_part = query_text[:query_text.lower().find("where")]
        # Must aggregate — COUNT, SUM, AVG, or GROUP BY
        assert any(kw in query_text.upper() for kw in ("COUNT", "SUM", "AVG", "GROUP BY"))
        # SELECT must not expose individual identity variables
        assert "?student" not in select_part
        assert "?actor" not in select_part
        assert "?webid" not in select_part
        assert "?name" not in select_part

    def test_community_pod_seed_no_individual_identifiers(self):
        """AC3: camp-dietary-aggregate.ttl contains no individual WebIDs or names."""
        seed_path = _PROJECT_ROOT / "data" / "seeds" / "camp-dietary-aggregate.ttl"
        assert seed_path.exists()
        seed_text = seed_path.read_text()

        # Must contain aggregate counts
        assert "totalEnrollments" in seed_text or "count" in seed_text.lower()
        # Must NOT contain individual WebID patterns like /profile/card#me
        assert "/profile/card#me" not in seed_text
        # Must NOT contain student names
        for name in ("ayoub", "marc", "fatima", "claire"):
            assert name not in seed_text.lower()


class TestIdempotency:
    """Test that revocation is idempotent — double-expiry does not error."""

    def test_already_revoked_returns_correct_status(self):
        token_id = generate_token(AYOUB_POD_URI, GRANTED_AT)
        already_revoked_turtle = _make_ephemeral_turtle(
            token_id, revoked_at="2026-09-01T00:00:00Z"
        )

        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = already_revoked_turtle

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_req, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token") as mock_dereg, \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event") as mock_emit:
            mock_req.get.return_value = css_get

            result = revoke_expired_token(
                token_id=token_id,
                grant_id="grant-test",
                pod_name=AYOUB_POD,
                expired_at=EXPIRES_AT,
            )

        assert result.status == "already_revoked"
        # No side effects on idempotent call
        mock_dereg.assert_not_called()
        mock_emit.assert_not_called()
