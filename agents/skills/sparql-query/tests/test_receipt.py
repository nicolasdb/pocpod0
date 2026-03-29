"""Tests for agents/skills/sparql-query/receipt.py.

Unit tests (no live CSS required):
  - build_receipt_turtle: all fields, denied case, multiple named graphs
  - _make_timestamp_slug: colon replacement, milliseconds, edge cases
  - write_access_receipt: returns False on HTTP error without raising

Integration tests (live CSS required) are gated by pytest mark `integration`
and skipped by default. Run with: pytest -m integration
"""

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: ensure receipt module is importable from test directory
# ---------------------------------------------------------------------------

_SKILL_DIR = Path(__file__).parent.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

import receipt  # noqa: E402 — local import after path setup

# Re-register the module so @patch can find it by canonical name
sys.modules["receipt"] = receipt


# ---------------------------------------------------------------------------
# Unit tests — build_receipt_turtle
# ---------------------------------------------------------------------------


class TestBuildReceiptTurtle(unittest.TestCase):
    """Test receipt Turtle document generation."""

    def _build(self, **kwargs):
        defaults = dict(
            agent_webid="http://localhost:3000/claire/profile/card#me",
            query_type="student-progress",
            pod_uri="http://localhost:3000/ayoub/",
            consent_grant_uri="http://localhost:3000/ayoub/.acl",
            result_shape="student-progress: 5 activity record(s), summarized",
            named_graphs=["http://localhost:3000/ayoub/learning/course1.ttl"],
            timestamp="2026-03-25T14:32:17.432Z",
            timestamp_slug="2026-03-25T14-32-17-432Z",
        )
        defaults.update(kwargs)
        return receipt.build_receipt_turtle(**defaults)

    def test_is_valid_turtle_structure(self):
        ttl = self._build()
        self.assertIn("@prefix xsd:", ttl)
        self.assertIn("@prefix poc:", ttl)
        self.assertIn("@prefix dcterms:", ttl)
        self.assertIn("a poc:AccessReceipt", ttl)

    def test_all_required_fields_present(self):
        ttl = self._build()
        self.assertIn("poc:queriedBy", ttl)
        self.assertIn("poc:accessedAt", ttl)
        self.assertIn("poc:queryType", ttl)
        self.assertIn("poc:resultShape", ttl)
        self.assertIn("poc:consentGrant", ttl)
        self.assertIn("poc:namedGraphsContributed", ttl)
        self.assertIn("dcterms:created", ttl)

    def test_receipt_uri_uses_urn_scheme(self):
        ttl = self._build(timestamp_slug="2026-03-25T14-32-17-432Z")
        self.assertIn("<urn:receipt:2026-03-25T14-32-17-432Z>", ttl)

    def test_denied_query_has_access_denied_flag(self):
        ttl = self._build(consent_grant_uri=None)
        self.assertIn('poc:accessDenied "true"^^xsd:boolean', ttl)
        self.assertNotIn("poc:consentGrant", ttl)

    def test_denied_query_no_consent_grant_uri(self):
        ttl = self._build(consent_grant_uri=None)
        self.assertNotIn("poc:consentGrant", ttl)

    def test_multiple_named_graphs_turtle_list(self):
        graphs = [
            "http://localhost:3000/ayoub/learning/a.ttl",
            "http://localhost:3000/ayoub/learning/b.ttl",
        ]
        ttl = self._build(named_graphs=graphs)
        # Proper RDF list: both URIs inside one set of parentheses
        self.assertIn("<http://localhost:3000/ayoub/learning/a.ttl>", ttl)
        self.assertIn("<http://localhost:3000/ayoub/learning/b.ttl>", ttl)
        self.assertIn("poc:namedGraphsContributed (", ttl)

    def test_empty_named_graphs_produces_empty_list(self):
        ttl = self._build(named_graphs=[])
        self.assertIn("poc:namedGraphsContributed () ;", ttl)

    def test_no_raw_data_in_receipt(self):
        # result_shape must only contain metadata description
        ttl = self._build(result_shape="5 activity records, summarized")
        # The turtle doc should not contain any SPARQL result row content
        self.assertNotIn("scaledScore", ttl)
        self.assertNotIn("bindings", ttl)

    def test_agent_webid_in_output(self):
        ttl = self._build(agent_webid="http://localhost:3000/claire/profile/card#me")
        self.assertIn("<http://localhost:3000/claire/profile/card#me>", ttl)

    def test_consent_grant_uri_in_output(self):
        ttl = self._build(consent_grant_uri="http://localhost:3000/ayoub/.acl")
        self.assertIn("<http://localhost:3000/ayoub/.acl>", ttl)

    def test_timestamp_in_output(self):
        ttl = self._build(timestamp="2026-03-25T14:32:17.432Z")
        self.assertIn("2026-03-25T14:32:17.432Z", ttl)


# ---------------------------------------------------------------------------
# Unit tests — _make_timestamp_slug
# ---------------------------------------------------------------------------


class TestMakeTimestampSlug(unittest.TestCase):
    """Test timestamp → URL-safe slug conversion."""

    def test_colons_replaced(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.432Z")
        self.assertNotIn(":", slug)

    def test_milliseconds_preserved(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.432Z")
        self.assertEqual(slug, "2026-03-25T14-32-17-432Z")

    def test_no_milliseconds_pads_to_three(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17Z")
        self.assertTrue(slug.endswith("000Z"), f"Expected '000Z' suffix, got: {slug}")

    def test_no_special_characters(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.432Z")
        import re
        self.assertRegex(slug, r'^[A-Za-z0-9\-]+Z$')

    def test_date_hyphens_preserved(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.432Z")
        self.assertTrue(slug.startswith("2026-03-25T"))

    def test_single_digit_milliseconds_pads(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.4Z")
        # frac "4" → "400"
        self.assertIn("-400Z", slug)

    def test_six_digit_milliseconds_truncated(self):
        slug = receipt._make_timestamp_slug("2026-03-25T14:32:17.432123Z")
        # Only first 3 fractional digits kept
        self.assertIn("-432Z", slug)


# ---------------------------------------------------------------------------
# Unit tests — write_access_receipt (mocked HTTP)
# ---------------------------------------------------------------------------


class TestWriteAccessReceipt(unittest.TestCase):
    """Test write_access_receipt error handling and non-blocking contract."""

    def _call(self, **kwargs):
        defaults = dict(
            agent_webid="http://localhost:3000/claire/profile/card#me",
            query_type="student-progress",
            pod_uri="http://localhost:3000/ayoub/",
            consent_grant_uri="http://localhost:3000/ayoub/.acl",
            result_shape="5 records summarized",
            named_graphs=["http://localhost:3000/ayoub/learning/a.ttl"],
            timestamp="2026-03-25T14:32:17.432Z",
        )
        defaults.update(kwargs)
        return receipt.write_access_receipt(**defaults)

    def test_returns_false_on_http_error_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call()
        self.assertFalse(result)

    def test_returns_false_on_http_403(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call()
        self.assertFalse(result)

    def test_returns_false_on_connection_error_without_raising(self):
        import requests as req
        with patch("receipt.requests.put", side_effect=req.RequestException("timeout")):
            result = self._call()
        self.assertFalse(result)

    def test_returns_true_on_201(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = ""
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call()
        self.assertTrue(result)

    def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call()
        self.assertTrue(result)

    def test_returns_true_on_204(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call()
        self.assertTrue(result)

    def test_never_raises_on_unexpected_exception(self):
        """write_access_receipt must never raise — it always returns bool."""
        with patch("receipt.build_receipt_turtle", side_effect=RuntimeError("boom")):
            try:
                result = self._call()
            except Exception as exc:
                self.fail(f"write_access_receipt raised unexpectedly: {exc}")
        self.assertFalse(result)

    def test_denied_query_none_consent_grant(self):
        """consent_grant_uri=None (denied query) should still write successfully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.text = ""
        with patch("receipt.requests.put", return_value=mock_resp):
            result = self._call(consent_grant_uri=None, result_shape="access denied")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
