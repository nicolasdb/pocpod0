"""Tests for the SPARQL Query Skill handler (Story 3.1).

Tests:
  Unit (no containers required):
    1. _agent_id_from_webid: extracts short ID from WebID URI
    2. _extract_pod_uris: normalises parameters to pod root URIs
    3. run_skill: ACL denied returns structured denial (mocked CSS)
    4. run_skill: template error returns error response (mocked CSS)
    5. run_skill: success path returns results + provenance (mocked CSS + Oxigraph)
    6. run_skill: ACL skipped when no CSS URIs in params
    7. Logging: denied event uses level=WARN and event=sparql.query.denied
    8. Logging: success event uses level=INFO and event=sparql.query.executed
    9. Logging: error event uses level=ERROR and event=sparql.query.error

  Integration (requires running Docker services; skipped if not available):
    10. All 5 templates execute against real Oxigraph (AC2)
    11. ACL granted path: claire queries ayoub pod (AC2)
    12. ACL denied path: troll denied access to ayoub pod (AC3)
    13. Structured logging emitted on each execution (AC4)

Run from repo root with venv active:
    pytest agents/skills/sparql-query/tests/test_handler.py -v

For integration tests only:
    pytest agents/skills/sparql-query/tests/test_handler.py -v -m integration
"""

import json
import os
import sys
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

# ---------------------------------------------------------------------------
# Path setup: handler.py and parameterize.py are one level up
# ---------------------------------------------------------------------------
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR))

import handler  # noqa: E402 — must come after sys.path manipulation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CSS_BASE = "http://localhost:3000"
OXIGRAPH_BASE = "http://localhost:7878"

CLAIRE_WEBID = f"{CSS_BASE}/claire/profile/card#me"
TROLL_WEBID = f"{CSS_BASE}/troll-adversary/profile/card#me"
AYOUB_POD = f"{CSS_BASE}/ayoub/"

MOCK_BINDINGS = [
    {
        "activity": {"type": "uri", "value": f"{CSS_BASE}/ayoub/learning/course/abc.ttl"},
        "result": {"type": "literal", "value": "pass"},
        "date": {"type": "literal", "value": "2026-01-01"},
        "g": {"type": "uri", "value": f"{CSS_BASE}/ayoub/learning/course/abc.ttl"},
    }
]


def _mock_css_allowed() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _mock_css_denied() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 403
    return resp


def _mock_oxigraph_results(bindings: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": {"bindings": bindings}}
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Unit tests — no containers required
# ---------------------------------------------------------------------------


class TestAgentIdFromWebid:
    def test_standard_webid(self):
        assert handler._agent_id_from_webid(f"{CSS_BASE}/claire/profile/card#me") == "claire"

    def test_hyphenated_agent(self):
        assert handler._agent_id_from_webid(f"{CSS_BASE}/troll-adversary/profile/card#me") == "troll-adversary"

    def test_empty_string(self):
        assert handler._agent_id_from_webid("") == "unknown"


class TestExtractPodUris:
    def test_profile_card_normalised_to_pod_root(self):
        params = {"student_uri": f"{CSS_BASE}/ayoub/profile/card#me"}
        result = handler._extract_pod_uris(params)
        assert result == [f"{CSS_BASE}/ayoub/"]

    def test_document_uri_extracts_pod_root(self):
        params = {"context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl"}
        result = handler._extract_pod_uris(params)
        assert result == [f"{CSS_BASE}/ayoub/"]

    def test_pod_root_kept_as_is(self):
        params = {"pod_uri": f"{CSS_BASE}/ayoub/"}
        result = handler._extract_pod_uris(params)
        assert result == [f"{CSS_BASE}/ayoub/"]

    def test_non_css_uri_ignored(self):
        params = {"x": "http://example.com/other"}
        assert handler._extract_pod_uris(params) == []

    def test_deduplication(self):
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        result = handler._extract_pod_uris(params)
        assert result == [f"{CSS_BASE}/ayoub/"]

    def test_multiple_pods(self):
        params = {
            "child1": f"{CSS_BASE}/fatima-child-1/profile/card#me",
            "child2": f"{CSS_BASE}/fatima-child-2/profile/card#me",
        }
        result = handler._extract_pod_uris(params)
        assert len(result) == 2
        assert f"{CSS_BASE}/fatima-child-1/" in result
        assert f"{CSS_BASE}/fatima-child-2/" in result


class TestRunSkillAclDenied:
    def test_acl_denied_returns_denial_response(self):
        params = {"student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
                  "context_uri": f"{CSS_BASE}/ayoub/"}
        with patch("handler.requests.head", return_value=_mock_css_denied()):
            result = handler.run_skill("student-progress", TROLL_WEBID, "student", params)
        assert result["status"] == "denied"
        assert "troll-adversary" in result["agent"]
        assert AYOUB_POD in result["requested_resources"]
        assert "403" in result["reason"]

    def test_acl_denied_includes_reason(self):
        params = {"pod_uri": AYOUB_POD}
        with patch("handler.requests.head", return_value=_mock_css_denied()):
            result = handler.run_skill("cross-context-query", TROLL_WEBID, "student",
                                       params | {"agent_role": "student"})
        assert result["status"] == "denied"
        assert "reason" in result


class TestRunSkillSuccess:
    def test_success_returns_summary(self):
        """Success path returns 'summary' dict (not raw 'results' — Story 3.4 token-bloat fix)."""
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post", return_value=_mock_oxigraph_results(MOCK_BINDINGS)):
            result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "success"
        assert result["result_count"] == 1
        assert "summary" in result
        assert "results" not in result  # raw bindings never returned

    def test_provenance_reduced_to_pod_root(self):
        """Provenance is collapsed to pod root URI, not individual document URIs."""
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post", return_value=_mock_oxigraph_results(MOCK_BINDINGS)):
            result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "success"
        # Provenance is pod root, not individual graph URI
        assert f"{CSS_BASE}/ayoub/" in result["provenance"]
        assert f"{CSS_BASE}/ayoub/learning/course/abc.ttl" not in result["provenance"]

    def test_no_css_uris_skips_acl(self):
        """When no CSS URIs in params, ACL check is skipped (acl_status=skipped)."""
        params = {"program_uri": "http://example.com/program",
                  "community_uri": "http://example.com/community"}
        with patch("handler.requests.post", return_value=_mock_oxigraph_results([])):
            result = handler.run_skill("aggregate-anonymized", CLAIRE_WEBID, "regional", params)
        assert result["status"] == "success"
        assert result["result_count"] == 0


class TestRunSkillErrors:
    def test_personal_template_without_pod_uris_returns_error(self):
        """P-1: personal templates must not skip ACL check (SEC-2)."""
        params = {"student_uri": "http://example.com/not-a-css-pod"}
        result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "error"
        assert "SEC-2" in result["error"] or "pod URI" in result["error"]

    def test_invalid_webid_returns_error(self):
        """P-5: invalid WebID must be rejected before header construction."""
        params = {"student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
                  "context_uri": f"{CSS_BASE}/ayoub/"}
        result = handler.run_skill("student-progress", "not-a-uri\ninjection", "tutor", params)
        assert result["status"] == "error"

    def test_invalid_template_returns_error(self):
        with patch("handler.requests.head", return_value=_mock_css_allowed()):
            result = handler.run_skill("nonexistent-template", CLAIRE_WEBID, "tutor",
                                       {"student_uri": AYOUB_POD, "context_uri": AYOUB_POD})
        assert result["status"] == "error"
        assert "error" in result

    def test_oxigraph_connection_error_returns_error(self):
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   side_effect=requests.RequestException("connection refused")):
            result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "error"
        assert "connection" in result["error"].lower()


# ---------------------------------------------------------------------------
# Parental view tests (Story 3.5)
# ---------------------------------------------------------------------------

FATIMA_WEBID = f"{CSS_BASE}/fatima/profile/card#me"
CHILD1_POD = f"{CSS_BASE}/fatima-child-1/"
CHILD2_POD = f"{CSS_BASE}/fatima-child-2/"

MOCK_PARENTAL_BINDINGS_CHILD1 = [
    {
        "g": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/learning/course/abc.ttl"},
        "actor": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/profile/card#me"},
        "verb": {"type": "uri", "value": "http://adlnet.gov/expapi/verbs/attended"},
        "object": {"type": "uri", "value": "https://poc-pod0.edu/vocab/activity-robotics-workshop"},
    },
    {
        "g": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/learning/course/def.ttl"},
        "actor": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/profile/card#me"},
        "verb": {"type": "uri", "value": "http://adlnet.gov/expapi/verbs/completed"},
        "object": {"type": "uri", "value": "https://poc-pod0.edu/vocab/activity-course-mathematics-nl"},
        "scaledScore": {"type": "literal", "value": "0.55"},
        "success": {"type": "literal", "value": "true"},
    },
]

MOCK_PARENTAL_BINDINGS_CHILD2 = [
    {
        "g": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-2/learning/course/ghi.ttl"},
        "actor": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-2/profile/card#me"},
        "verb": {"type": "uri", "value": "http://adlnet.gov/expapi/verbs/attended"},
        "object": {"type": "uri", "value": "https://poc-pod0.edu/vocab/activity-robotics-workshop"},
    },
]

MOCK_PARENTAL_BINDINGS = MOCK_PARENTAL_BINDINGS_CHILD1 + MOCK_PARENTAL_BINDINGS_CHILD2


class TestParentalView:
    """Story 3.5: Fatima's unified parental view."""

    def _parental_params(self) -> dict:
        return {
            "child_pod_1": CHILD1_POD,
            "child_pod_2": CHILD2_POD,
            "agent_id": "fatima-parent",
        }

    def test_both_pod_uris_extracted_from_params(self):
        """ACL check fires on both child pods."""
        params = self._parental_params()
        pod_uris = handler._extract_pod_uris(params)
        assert CHILD1_POD in pod_uris
        assert CHILD2_POD in pod_uris
        assert len(pod_uris) == 2

    def test_parental_view_success_returns_children_summaries(self):
        """AC1/AC2: success returns per-child summaries."""
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(MOCK_PARENTAL_BINDINGS)):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "success"
        assert "summary" in result
        assert "children" in result["summary"]
        assert len(result["summary"]["children"]) == 2

    def test_parental_view_threshold_signal_detected(self):
        """AC1: score < 0.6 but success=True is flagged per child."""
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(MOCK_PARENTAL_BINDINGS)):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "success"
        child1 = next(
            c for c in result["summary"]["children"]
            if CHILD1_POD in c["pod_uri"]
        )
        assert "below_60_marked_success" in child1
        assert child1["below_60_marked_success"][0]["score"] == 0.55

    def test_parental_view_attended_no_outcome_detected(self):
        """AC1: attended-only sessions (no score) are counted as gaps."""
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(MOCK_PARENTAL_BINDINGS)):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "success"
        # Both children have attended robotics workshop with no score
        for child in result["summary"]["children"]:
            assert child.get("attended_no_outcome_count", 0) >= 1

    def test_parental_view_attendance_discrepancy_detected(self):
        """AC2: different session counts for same activity are flagged."""
        # Child-1 has 2 attended robotics rows, child-2 has 1
        bindings_extra = MOCK_PARENTAL_BINDINGS_CHILD1 + [
            {
                "g": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/learning/course/xyz.ttl"},
                "actor": {"type": "uri", "value": f"{CSS_BASE}/fatima-child-1/profile/card#me"},
                "verb": {"type": "uri", "value": "http://adlnet.gov/expapi/verbs/attended"},
                "object": {"type": "uri", "value": "https://poc-pod0.edu/vocab/activity-robotics-workshop"},
            }
        ] + MOCK_PARENTAL_BINDINGS_CHILD2
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(bindings_extra)):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "success"
        gaps = result["summary"].get("gaps", [])
        discrepancy = [g for g in gaps if g["type"] == "attendance_discrepancy"]
        assert discrepancy, "Expected attendance discrepancy gap to be reported"
        assert "activity-robotics-workshop" in discrepancy[0]["activity"]

    def test_parental_view_acl_denied_fatima_cannot_access_ayoub(self):
        """AC3: fatima's agent is denied access to ayoub's pod."""
        params = {
            "child_pod_1": CHILD1_POD,
            "child_pod_2": AYOUB_POD,  # unauthorized
            "agent_id": "fatima-parent",
        }
        with patch("handler.requests.head", return_value=_mock_css_denied()):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "denied"
        assert "403" in result["reason"]

    def test_parental_view_denial_logged_as_warn(self):
        """AC5: denial produces WARN log with sparql.query.denied event."""
        buf = StringIO()
        params = {
            "child_pod_1": CHILD1_POD,
            "child_pod_2": AYOUB_POD,
            "agent_id": "fatima-parent",
        }
        with patch("handler.requests.head", return_value=_mock_css_denied()), \
             patch("sys.stdout", buf):
            handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        logs = [json.loads(l) for l in buf.getvalue().strip().splitlines() if l]
        denied = [l for l in logs if l.get("event") == "sparql.query.denied"]
        assert denied
        assert denied[0]["level"] == "WARN"
        assert denied[0]["agent"] == "fatima-parent"

    def test_parental_view_success_logged_with_agent_fatima(self):
        """AC5: successful query produces INFO log with agent=fatima."""
        buf = StringIO()
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(MOCK_PARENTAL_BINDINGS)), \
             patch("sys.stdout", buf):
            handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        logs = [json.loads(l) for l in buf.getvalue().strip().splitlines() if l]
        executed = [l for l in logs if l.get("event") == "sparql.query.executed"]
        assert executed
        assert executed[0]["agent"] == "fatima-parent"
        assert executed[0]["level"] == "INFO"
        assert "result_count" in executed[0]

    def test_parental_view_provenance_covers_both_children(self):
        """AC2: provenance includes both child pod roots."""
        params = self._parental_params()
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   return_value=_mock_oxigraph_results(MOCK_PARENTAL_BINDINGS)):
            result = handler.run_skill("parental-view", FATIMA_WEBID, "parental", params)
        assert result["status"] == "success"
        assert CHILD1_POD in result["provenance"]
        assert CHILD2_POD in result["provenance"]


class TestLogging:
    """Verify log structure emitted to stdout."""

    def _capture_logs(self, *args, **kwargs) -> list[dict]:
        """Run run_skill and capture all JSON log lines.

        run_skill() only prints log entries (not the final result — that's printed
        by main()). So all printed lines are log entries.
        """
        buf = StringIO()
        with patch("sys.stdout", buf):
            handler.run_skill(*args, **kwargs)
        lines = [l for l in buf.getvalue().strip().splitlines() if l]
        return [json.loads(l) for l in lines]

    def test_denied_event_emitted(self):
        params = {"student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
                  "context_uri": f"{CSS_BASE}/ayoub/"}
        with patch("handler.requests.head", return_value=_mock_css_denied()):
            logs = self._capture_logs("student-progress", TROLL_WEBID, "student", params)
        events = [l["event"] for l in logs]
        assert "sparql.query.denied" in events
        denied = next(l for l in logs if l["event"] == "sparql.query.denied")
        assert denied["level"] == "WARN"
        assert denied["service"] == "sparql-query-skill"
        # P-4: acl_check must not appear in denial log (only "passed"/"skipped" are valid)
        assert "acl_check" not in denied.get("details", {})

    def test_success_event_emitted(self):
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post", return_value=_mock_oxigraph_results(MOCK_BINDINGS)):
            logs = self._capture_logs("student-progress", CLAIRE_WEBID, "tutor", params)
        events = [l["event"] for l in logs]
        assert "sparql.query.executed" in events
        executed = next(l for l in logs if l["event"] == "sparql.query.executed")
        assert executed["level"] == "INFO"
        # P-3: result_count is a top-level field in the log entry (AC4 schema)
        assert "result_count" in executed
        assert "result_count" not in executed["details"]
        assert "oxigraph_latency_ms" in executed["details"]
        assert "acl_check" in executed["details"]

    def test_error_event_emitted(self):
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/learning/course/abc.ttl",
        }
        with patch("handler.requests.head", return_value=_mock_css_allowed()), \
             patch("handler.requests.post",
                   side_effect=requests.RequestException("fail")):
            logs = self._capture_logs("student-progress", CLAIRE_WEBID, "tutor", params)
        events = [l["event"] for l in logs]
        assert "sparql.query.error" in events
        error = next(l for l in logs if l["event"] == "sparql.query.error")
        assert error["level"] == "ERROR"


# ---------------------------------------------------------------------------
# Integration tests — require running Docker services
# ---------------------------------------------------------------------------


def _services_available() -> bool:
    """Check if Oxigraph and CSS are reachable."""
    try:
        r = requests.get(f"{OXIGRAPH_BASE}/", timeout=2)
        if r.status_code not in (200, 404):
            return False
        r2 = requests.head(f"{CSS_BASE}/", timeout=2)
        # CSS at localhost:3000 may return 401 or 404 — both mean it's running
        return r2.status_code < 500
    except requests.RequestException:
        return False


INTEGRATION = pytest.mark.skipif(
    not _services_available(),
    reason="Docker services (Oxigraph, CSS) not available",
)


def _get_first_document_uri(pod_name: str) -> str | None:
    """Query Oxigraph for the first named graph document in a pod."""
    query = f"""
    SELECT ?g WHERE {{
      GRAPH ?g {{ ?s ?p ?o }}
      FILTER(STRSTARTS(STR(?g), "{CSS_BASE}/{pod_name}/"))
    }} LIMIT 1
    """
    try:
        resp = requests.post(
            f"{OXIGRAPH_BASE}/query",
            data=query.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
            timeout=10,
        )
        bindings = resp.json().get("results", {}).get("bindings", [])
        return bindings[0]["g"]["value"] if bindings else None
    except Exception:
        return None


@INTEGRATION
class TestIntegration:
    """Integration tests against real Docker services."""

    def test_student_progress_template_executes(self):
        """AC2: student-progress template runs against real Oxigraph."""
        doc_uri = _get_first_document_uri("ayoub")
        if not doc_uri:
            pytest.skip("No Oxigraph data for ayoub pod")
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": doc_uri,
        }
        result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "success"
        assert "summary" in result
        assert "provenance" in result

    def test_cross_context_query_template_executes(self):
        """AC2: cross-context-query template runs against real Oxigraph."""
        doc_uri = _get_first_document_uri("ayoub")
        if not doc_uri:
            pytest.skip("No Oxigraph data for ayoub pod")
        params = {
            "agent_role": "tutor",
            "pod_uri": doc_uri,
        }
        result = handler.run_skill("cross-context-query", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "success"

    def test_aggregate_anonymized_template_executes(self):
        """AC2: aggregate-anonymized template runs against real Oxigraph."""
        doc_uri = _get_first_document_uri("school-community")
        params = {
            "program_uri": "http://example.com/stem-program",
            "community_uri": doc_uri or "http://localhost:3000/school-community/",
        }
        # Aggregate query doesn't target personal pods — no ACL check needed
        # Use provisioner-equivalent agent that has school-community access
        result = handler.run_skill("aggregate-anonymized", CLAIRE_WEBID, "tutor", params)
        # Success even with 0 results (template executed, ACL skipped for non-CSS program URI)
        assert result["status"] in ("success", "denied"), f"Unexpected: {result}"
        # If denied (school-community ACL), that's a valid result for this test
        if result["status"] == "success":
            assert "summary" in result

    def test_parental_view_template_executes(self):
        """AC1/AC2: parental-view queries both children's pods with fatima's WebID."""
        fatima_webid = f"{CSS_BASE}/fatima/profile/card#me"
        params = {
            "child_pod_1": f"{CSS_BASE}/fatima-child-1/",
            "child_pod_2": f"{CSS_BASE}/fatima-child-2/",
        }
        result = handler.run_skill("parental-view", fatima_webid, "parental", params)
        assert result["status"] == "success"
        assert "summary" in result
        assert "children" in result["summary"]
        assert len(result["summary"]["children"]) == 2

    def test_parental_view_gap_detection_real_data(self):
        """AC1: gap detection runs on real Oxigraph data (attended without scores)."""
        fatima_webid = f"{CSS_BASE}/fatima/profile/card#me"
        params = {
            "child_pod_1": f"{CSS_BASE}/fatima-child-1/",
            "child_pod_2": f"{CSS_BASE}/fatima-child-2/",
        }
        result = handler.run_skill("parental-view", fatima_webid, "parental", params)
        assert result["status"] == "success"
        # With real data: robotics workshop sessions are attended-only
        # At least one child should have attended_no_outcome_count > 0
        children = result["summary"]["children"]
        any_gap = any(c.get("attended_no_outcome_count", 0) > 0 for c in children)
        assert any_gap, f"Expected robotics workshop gap; children: {children}"

    def test_parental_view_acl_denied_fatima_cannot_access_ayoub(self):
        """AC3: fatima is denied access to ayoub's pod."""
        fatima_webid = f"{CSS_BASE}/fatima/profile/card#me"
        params = {
            "child_pod_1": f"{CSS_BASE}/fatima-child-1/",
            "child_pod_2": f"{CSS_BASE}/ayoub/",  # unauthorized
        }
        result = handler.run_skill("parental-view", fatima_webid, "parental", params)
        assert result["status"] == "denied", f"Expected denial, got: {result}"

    def test_transfer_profile_template_executes(self):
        """AC2: transfer-profile template runs against real Oxigraph."""
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
        }
        result = handler.run_skill("transfer-profile", CLAIRE_WEBID, "tutor", params)
        assert result["status"] == "success"

    def test_acl_granted_claire_accesses_ayoub(self):
        """AC2: claire (tutor) has CSS ACL access to ayoub pod."""
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/",
        }
        # Use a real Oxigraph query but we only need the ACL part to work
        doc_uri = _get_first_document_uri("ayoub")
        if doc_uri:
            params["context_uri"] = doc_uri
        result = handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        # Must not be denied
        assert result["status"] != "denied", f"ACL should allow claire: {result}"

    def test_acl_denied_troll_cannot_access_ayoub(self):
        """AC3: troll is denied access to ayoub pod."""
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": f"{CSS_BASE}/ayoub/",
        }
        result = handler.run_skill("student-progress", TROLL_WEBID, "student", params)
        assert result["status"] == "denied", f"Troll should be denied, got: {result}"
        assert "requested_resources" in result
        assert AYOUB_POD in result["requested_resources"]

    def test_structured_logging_on_success(self, capsys):
        """AC4: structured log emitted with required fields on success."""
        doc_uri = _get_first_document_uri("ayoub")
        if not doc_uri:
            pytest.skip("No Oxigraph data")
        params = {
            "student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
            "context_uri": doc_uri,
        }
        handler.run_skill("student-progress", CLAIRE_WEBID, "tutor", params)
        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().splitlines() if l]
        # run_skill() only prints log entries (result is printed by main())
        log_lines = [json.loads(l) for l in lines]
        executed = [l for l in log_lines if l.get("event") == "sparql.query.executed"]
        assert executed, "Expected sparql.query.executed log entry"
        log = executed[0]
        assert "timestamp" in log
        assert "duration_ms" in log
        assert "result_count" in log  # P-3: top-level per AC4 schema
        assert log["details"]["acl_check"] == "passed"
        assert "oxigraph_latency_ms" in log["details"]

    def test_structured_logging_on_denial(self, capsys):
        """AC4: structured log emitted with WARN level on denial."""
        params = {"student_uri": f"{CSS_BASE}/ayoub/profile/card#me",
                  "context_uri": f"{CSS_BASE}/ayoub/"}
        handler.run_skill("student-progress", TROLL_WEBID, "student", params)
        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().splitlines() if l]
        log_lines = [json.loads(l) for l in lines]
        denied = [l for l in log_lines if l.get("event") == "sparql.query.denied"]
        assert denied, "Expected sparql.query.denied log entry"
        assert denied[0]["level"] == "WARN"
