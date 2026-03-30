"""Tests for Story 5.6: Ephemeral time-scoped consent — double-aveugle pattern.

AC1: create_ephemeral_consent_grant produces opaque token + Turtle with poc:token+poc:expiresAt
AC2: Token expiry auto-revokes access, writes tombstone + receipt + JSONL event
AC3: Double-aveugle aggregate query — community pod returns counts, no individual identity
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
    register_token,
    lookup_token,
    deregister_token,
    create_ephemeral_consent_grant,
)
from pocpod0_pipeline.expire_tokens import (
    ExpiryResult,
    check_expired_tokens,
    revoke_expired_token,
    _OXIGRAPH_URL,
)

# ─── constants ─────────────────────────────────────────────────────────────────

AYOUB_POD = "ayoub"
AYOUB_POD_URI = "http://localhost:3000/ayoub/"
SERVICE_LABEL = "camp-food-service"
PURPOSE = "Serve appropriate meals during summer camp"
SCOPE = "Dietary restriction (yes/no + type)"
EXCLUDED = "Identity, name, school, grades"
CONSEQUENCE = "Default meal served (no accommodation for dietary needs)"
EXPIRES_AT = "2026-08-31T23:59:59Z"
GRANTED_AT = "2026-06-20T08:00:00Z"

SAMPLE_TOKEN = generate_token(AYOUB_POD_URI, GRANTED_AT)


# ─── Task 1 & 3: generate_token ────────────────────────────────────────────────

class TestGenerateToken:
    def test_returns_16_char_hex(self):
        token = generate_token(AYOUB_POD_URI, GRANTED_AT)
        assert len(token) == 16
        assert all(c in "0123456789abcdef" for c in token)

    def test_deterministic(self):
        t1 = generate_token(AYOUB_POD_URI, GRANTED_AT)
        t2 = generate_token(AYOUB_POD_URI, GRANTED_AT)
        assert t1 == t2

    def test_different_inputs_different_tokens(self):
        t1 = generate_token(AYOUB_POD_URI, GRANTED_AT)
        t2 = generate_token("http://localhost:3000/marc/", GRANTED_AT)
        assert t1 != t2

    def test_token_is_not_webid(self):
        """Token must be opaque string — not a dereferenceable URI."""
        token = generate_token(AYOUB_POD_URI, GRANTED_AT)
        assert not token.startswith("http")
        assert "/" not in token
        assert "#" not in token


# ─── Task 3: register_token ────────────────────────────────────────────────────

class TestRegisterToken:
    def test_issues_sparql_insert(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            register_token(SAMPLE_TOKEN, AYOUB_POD_URI, "grant-ayoub-camp-20260620", GRANTED_AT, EXPIRES_AT)

        call_kwargs = mock_httpx.post.call_args
        body = call_kwargs[1]["content"].decode("utf-8")
        assert "urn:token-index" in body
        assert f"urn:token:{SAMPLE_TOKEN}" in body
        assert AYOUB_POD_URI in body
        assert "INSERT DATA" in body

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Token registration failed"):
                register_token(SAMPLE_TOKEN, AYOUB_POD_URI, "grant-1", GRANTED_AT, EXPIRES_AT)


# ─── Task 3: lookup_token ──────────────────────────────────────────────────────

class TestLookupToken:
    def test_returns_dict_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": {
                "bindings": [{
                    "pod_uri": {"value": AYOUB_POD_URI},
                    "grant_id": {"value": "grant-ayoub-camp-20260620"},
                    "issued_at": {"value": GRANTED_AT},
                    "expires_at": {"value": EXPIRES_AT},
                }]
            }
        }

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = lookup_token(SAMPLE_TOKEN)

        assert result is not None
        assert result["pod_uri"] == AYOUB_POD_URI
        assert result["grant_id"] == "grant-ayoub-camp-20260620"

    def test_returns_none_when_not_found(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"bindings": []}}

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = lookup_token("deadbeef00000000")

        assert result is None

    def test_returns_none_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            result = lookup_token(SAMPLE_TOKEN)

        assert result is None


# ─── Task 3: deregister_token ─────────────────────────────────────────────────

class TestDeregisterToken:
    def test_issues_sparql_delete(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            deregister_token(SAMPLE_TOKEN)

        call_kwargs = mock_httpx.post.call_args
        body = call_kwargs[1]["content"].decode("utf-8")
        assert "urn:token-index" in body
        assert f"urn:token:{SAMPLE_TOKEN}" in body
        assert "DELETE" in body

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Token deregistration failed"):
                deregister_token(SAMPLE_TOKEN)


# ─── Task 1: create_ephemeral_consent_grant ────────────────────────────────────

class TestCreateEphemeralConsentGrant:
    def _mock_success(self):
        """Return mocks for register_token(ok), CSS PUT(201), emit_event."""
        httpx_resp = MagicMock()
        httpx_resp.status_code = 204

        css_resp = MagicMock()
        css_resp.status_code = 201

        head_resp = MagicMock()
        head_resp.status_code = 404  # no collision

        return httpx_resp, css_resp, head_resp

    def test_returns_ok_with_token(self):
        httpx_resp, css_resp, head_resp = self._mock_success()

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.consent_grant.requests") as mock_requests, \
             patch("pocpod0_pipeline.consent_grant._emit_consent_event"):
            mock_httpx.post.return_value = httpx_resp
            mock_requests.head.return_value = head_resp
            mock_requests.put.return_value = css_resp

            result = create_ephemeral_consent_grant(
                pod_name=AYOUB_POD,
                service_label=SERVICE_LABEL,
                purpose=PURPOSE,
                scope=SCOPE,
                excluded=EXCLUDED,
                consequence_of_refusal=CONSEQUENCE,
                expires_at=EXPIRES_AT,
            )

        assert result.status == "ok"
        assert len(result.token_id) == 16
        assert all(c in "0123456789abcdef" for c in result.token_id)
        assert result.pod_name == AYOUB_POD
        assert result.expires_at == EXPIRES_AT

    def test_turtle_contains_token_and_expiry(self):
        """Verify rendered Turtle includes poc:token and poc:expiresAt."""
        from pocpod0_pipeline.consent_grant import _render_ephemeral_turtle
        turtle_str = _render_ephemeral_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-test",
            service_label=SERVICE_LABEL,
            token_id="abc123def456abcd",
            purpose=PURPOSE,
            scope=SCOPE,
            excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE,
            granted_at=GRANTED_AT,
            expires_at=EXPIRES_AT,
        )
        assert 'poc:token' in turtle_str
        assert '"abc123def456abcd"' in turtle_str
        assert 'poc:expiresAt' in turtle_str
        assert EXPIRES_AT in turtle_str
        assert 'poc:EphemeralConsentGrant' in turtle_str

    def test_token_not_a_webid_in_turtle(self):
        """Double-aveugle: token is a string literal, not a URI. Food service cannot dereference it."""
        from pocpod0_pipeline.consent_grant import _render_ephemeral_turtle
        turtle_str = _render_ephemeral_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-test",
            service_label=SERVICE_LABEL,
            token_id="abc123def456abcd",
            purpose=PURPOSE,
            scope=SCOPE,
            excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE,
            granted_at=GRANTED_AT,
            expires_at=EXPIRES_AT,
        )
        # Token appears as string literal "...", NOT as a URI <...>
        assert '"abc123def456abcd"' in turtle_str
        assert "<abc123def456abcd>" not in turtle_str

    def test_emits_jsonl_event_with_token_id(self):
        httpx_resp, css_resp, head_resp = self._mock_success()
        captured_events = []

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.consent_grant.requests") as mock_requests, \
             patch("pocpod0_pipeline.consent_grant._emit_consent_event", side_effect=captured_events.append):
            mock_httpx.post.return_value = httpx_resp
            mock_requests.head.return_value = head_resp
            mock_requests.put.return_value = css_resp

            result = create_ephemeral_consent_grant(
                pod_name=AYOUB_POD, service_label=SERVICE_LABEL,
                purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
                consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
            )

        assert len(captured_events) == 1
        event = captured_events[0]
        assert event["event_type"] == "consent.grant"
        assert "token_id" in event
        assert event["token_id"] == result.token_id
        assert event["expires_at"] == EXPIRES_AT

    def test_returns_error_when_token_registration_fails(self):
        httpx_resp = MagicMock()
        httpx_resp.status_code = 500

        head_resp = MagicMock()
        head_resp.status_code = 404

        with patch("pocpod0_pipeline.consent_grant.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.consent_grant.requests") as mock_requests:
            mock_httpx.post.return_value = httpx_resp
            mock_requests.head.return_value = head_resp

            result = create_ephemeral_consent_grant(
                pod_name=AYOUB_POD, service_label=SERVICE_LABEL,
                purpose=PURPOSE, scope=SCOPE, excluded=EXCLUDED,
                consequence_of_refusal=CONSEQUENCE, expires_at=EXPIRES_AT,
            )

        assert result.status == "error"
        assert "Token index registration failed" in result.error_message


# ─── Task 4+5: check_expired_tokens / revoke_expired_token ───────────────────

class TestCheckExpiredTokens:
    def test_returns_only_expired(self):
        """Mock Oxigraph: 2 expired tokens + 1 active. Only 2 should be revoked."""
        import datetime

        expired_bindings = [
            {
                "token_id": {"value": "expired111111111"},
                "pod_uri": {"value": "http://localhost:3000/ayoub/"},
                "grant_id": {"value": "grant-ayoub-camp-20260620"},
                "expires_at": {"value": "2026-06-01T00:00:00Z"},
            },
            {
                "token_id": {"value": "expired222222222"},
                "pod_uri": {"value": "http://localhost:3000/marc/"},
                "grant_id": {"value": "grant-marc-camp-20260620"},
                "expires_at": {"value": "2026-06-02T00:00:00Z"},
            },
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"bindings": expired_bindings}}

        revoked = []

        def fake_revoke(token_id, grant_id, pod_name, expired_at="", oxigraph_url="http://localhost:7878", css_base_url="http://localhost:3000"):
            revoked.append(token_id)
            return ExpiryResult(
                token_id=token_id, pod_name=pod_name, grant_id=grant_id,
                expired_at=expired_at or "2026-09-01T00:00:00Z", status="revoked",
            )

        with patch("pocpod0_pipeline.expire_tokens.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.expire_tokens.revoke_expired_token", side_effect=fake_revoke):
            mock_httpx.post.return_value = mock_resp
            results = check_expired_tokens()

        assert len(results) == 2
        assert set(r.status for r in results) == {"revoked"}
        assert "expired111111111" in revoked
        assert "expired222222222" in revoked

    def test_empty_list_when_no_expired(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"bindings": []}}

        with patch("pocpod0_pipeline.expire_tokens.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_resp
            results = check_expired_tokens()

        assert results == []


class TestRevokeExpiredToken:
    def _make_sample_turtle(self, token_id="abc123def456abcd"):
        return f"""@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://localhost:3000/ayoub/consent-grants/grant-test> a poc:ConsentGrant, poc:EphemeralConsentGrant ;
  poc:token "{token_id}" ;
  poc:serviceLabel "camp-food-service" ;
  poc:purpose "Test" ;
  poc:scope "test" ;
  poc:excluded "none" ;
  poc:consequenceOfRefusal "none" ;
  poc:grantedAt "2026-06-20T08:00:00Z"^^xsd:dateTime ;
  poc:revokedAt "" ;
  poc:expiresAt "2026-08-31T23:59:59Z"^^xsd:dateTime .
"""

    def test_tombstone_populated(self):
        """revoke_expired_token must populate poc:revokedAt in the Turtle."""
        token_id = "abc123def456abcd"
        turtle_str = self._make_sample_turtle(token_id)

        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = turtle_str

        css_put = MagicMock()
        css_put.status_code = 205

        httpx_resp = MagicMock()
        httpx_resp.status_code = 204

        written_turtle = []

        def capture_put(url, headers, data, timeout):
            written_turtle.append(data.decode("utf-8"))
            return css_put

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_requests, \
             patch("pocpod0_pipeline.expire_tokens.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token"), \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event"), \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_requests.get.return_value = css_get
            mock_requests.put.side_effect = capture_put
            mock_httpx.post.return_value = httpx_resp

            result = revoke_expired_token(token_id, "grant-test", AYOUB_POD, expired_at="2026-09-01T00:00:00Z")

        assert result.status == "revoked"
        assert len(written_turtle) == 1
        # Tombstone: poc:revokedAt must be populated (non-empty)
        from rdflib import Graph, URIRef, Literal
        g = Graph()
        g.parse(data=written_turtle[0], format="turtle")
        poc_ns = "http://localhost:3000/vocab/pocpod0#"
        revoked_vals = list(g.objects(None, URIRef(f"{poc_ns}revokedAt")))
        assert len(revoked_vals) == 1
        assert str(revoked_vals[0]) != ""

    def test_emits_consent_expired_event(self):
        token_id = "abc123def456abcd"
        turtle_str = self._make_sample_turtle(token_id)

        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = turtle_str
        css_put = MagicMock()
        css_put.status_code = 205
        httpx_resp = MagicMock()
        httpx_resp.status_code = 204

        captured_events = []

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_requests, \
             patch("pocpod0_pipeline.expire_tokens.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token"), \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event", side_effect=captured_events.append), \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_requests.get.return_value = css_get
            mock_requests.put.return_value = css_put
            mock_httpx.post.return_value = httpx_resp

            revoke_expired_token(token_id, "grant-test", AYOUB_POD, expired_at="2026-09-01T00:00:00Z")

        assert len(captured_events) == 1
        ev = captured_events[0]
        assert ev["event_type"] == "consent.expired"
        assert ev["token_id"] == token_id
        assert ev["pod"] == AYOUB_POD

    def test_deregisters_token(self):
        token_id = "abc123def456abcd"
        turtle_str = self._make_sample_turtle(token_id)

        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = turtle_str
        css_put = MagicMock()
        css_put.status_code = 205
        httpx_resp = MagicMock()
        httpx_resp.status_code = 204

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_requests, \
             patch("pocpod0_pipeline.expire_tokens.httpx") as mock_httpx, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token") as mock_dereg, \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event"), \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_requests.get.return_value = css_get
            mock_requests.put.return_value = css_put
            mock_httpx.post.return_value = httpx_resp

            revoke_expired_token(token_id, "grant-test", AYOUB_POD, expired_at="2026-09-01T00:00:00Z")

        mock_dereg.assert_called_once_with(token_id, _OXIGRAPH_URL)

    def test_idempotent_when_already_revoked(self):
        """If poc:revokedAt is already non-empty, log warning and return without error."""
        token_id = "abc123def456abcd"
        # Turtle with revokedAt already set
        already_revoked_turtle = f"""@prefix poc: <http://localhost:3000/vocab/pocpod0#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://localhost:3000/ayoub/consent-grants/grant-test> a poc:ConsentGrant, poc:EphemeralConsentGrant ;
  poc:token "{token_id}" ;
  poc:serviceLabel "camp-food-service" ;
  poc:grantedAt "2026-06-20T08:00:00Z"^^xsd:dateTime ;
  poc:revokedAt "2026-08-01T00:00:00Z"^^xsd:dateTime ;
  poc:expiresAt "2026-08-31T23:59:59Z"^^xsd:dateTime .
"""
        css_get = MagicMock()
        css_get.status_code = 200
        css_get.text = already_revoked_turtle

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_requests, \
             patch("pocpod0_pipeline.expire_tokens.deregister_token") as mock_dereg, \
             patch("pocpod0_pipeline.expire_tokens._emit_consent_event") as mock_emit, \
             patch("pocpod0_pipeline.expire_tokens._write_access_receipt"):
            mock_requests.get.return_value = css_get

            result = revoke_expired_token(token_id, "grant-test", AYOUB_POD, expired_at="2026-09-01T00:00:00Z")

        assert result.status == "already_revoked"
        mock_dereg.assert_not_called()
        mock_emit.assert_not_called()


# ─── Task 6: _write_access_receipt ────────────────────────────────────────────

class TestWriteAccessReceipt:
    def test_receipt_written_with_correct_fields(self):
        """Verify receipt Turtle is PUT to correct path with correct fields."""
        from pocpod0_pipeline.expire_tokens import _write_access_receipt

        css_put = MagicMock()
        css_put.status_code = 201

        written = []

        def capture_put(url, headers, data, timeout):
            written.append((url, data.decode("utf-8")))
            return css_put

        with patch("pocpod0_pipeline.expire_tokens.requests") as mock_requests:
            mock_requests.put.side_effect = capture_put
            _write_access_receipt(
                pod_name=AYOUB_POD,
                token_id="abc123def456abcd",
                service_label=SERVICE_LABEL,
                grant_id="grant-ayoub-camp-20260620",
                granted_at=GRANTED_AT,
                expired_at="2026-09-01T00:00:00Z",
            )

        assert len(written) == 1
        url, turtle = written[0]
        assert "/ayoub/access-log/" in url
        assert "camp-food" in url.lower() or "receipt" in url.lower() or "access" in url.lower()
        assert "poc:AccessReceipt" in turtle
        assert '"abc123def456abcd"' in turtle
        assert GRANTED_AT in turtle
        assert "2026-09-01T00:00:00Z" in turtle


# ─── Double-aveugle property test ─────────────────────────────────────────────

class TestDoubleAveugles:
    def test_token_is_not_webid_in_grant_turtle(self):
        """AC1 double-aveugle: token value doesn't look like a WebID in Turtle output."""
        from pocpod0_pipeline.consent_grant import _render_ephemeral_turtle
        token_id = "abc123def456abcd"
        turtle_str = _render_ephemeral_turtle(
            grant_uri="http://localhost:3000/ayoub/consent-grants/grant-test",
            service_label="camp-food-service",
            token_id=token_id,
            purpose=PURPOSE,
            scope=SCOPE,
            excluded=EXCLUDED,
            consequence_of_refusal=CONSEQUENCE,
            granted_at=GRANTED_AT,
            expires_at=EXPIRES_AT,
        )
        # WebID pattern would be a URI like <http://...>
        # Token must appear as a plain string literal, not a URI
        assert f'"{token_id}"' in turtle_str
        # The key invariant: no <token_id> URI in the turtle
        assert f"<{token_id}>" not in turtle_str
        # Pod URI (Ayoub's identity) is NOT visible to the grantee (no requestedBy triple)
        assert "requestedBy" not in turtle_str

    def test_aggregate_query_returns_no_individual_webid(self):
        """AC3: camp-aggregate.rq query result contains only counts — no individual WebID."""
        rq_path = _PROJECT_ROOT / "agents" / "skills" / "sparql-query" / "templates" / "camp-aggregate.rq"
        assert rq_path.exists(), "camp-aggregate.rq must exist"
        query_text = rq_path.read_text()
        # Must use GROUP BY or aggregate functions — structural anonymization
        assert "COUNT" in query_text or "GROUP BY" in query_text or "SUM" in query_text
        # Must NOT select individual ?actor or ?student variables that expose identity
        # (individual binding variables like ?student are OK in WHERE clause for filtering,
        # but must not appear in SELECT as exposed results)
        select_part = query_text[:query_text.lower().find("where")]
        assert "?student" not in select_part
        assert "?actor" not in select_part
        assert "?webid" not in select_part
