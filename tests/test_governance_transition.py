"""Tests for Story 5.1: governance_transition.py and acl-manage handler.

AC1: Age-based governance transition executes
AC2: Post-transition state verifiable (JSONL event emitted)
AC3: Former guardian denied modification
AC4: Agent-callable acl-manage skill
AC5: Ownership scope enforcement
"""

import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add pipeline/src to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "agents" / "skills" / "acl-manage"))

from pocpod0_pipeline.governance_transition import (
    TransitionResult,
    check_transition_eligibility,
    execute_transition,
    get_guardian_webids,
)


# ─── check_transition_eligibility ────────────────────────────────────────────

class TestCheckTransitionEligibility:
    def test_age_below_threshold_returns_false(self):
        # 14 years old, threshold 16
        dob = (date.today().replace(year=date.today().year - 14)).isoformat()
        assert check_transition_eligibility("ayoub", dob, 16) is False

    def test_age_at_threshold_returns_true(self):
        # Exactly 16 today
        dob = date.today().replace(year=date.today().year - 16)
        assert check_transition_eligibility("ayoub", dob.isoformat(), 16) is True

    def test_age_above_threshold_returns_true(self):
        # 18 years old, threshold 16
        dob = (date.today().replace(year=date.today().year - 18)).isoformat()
        assert check_transition_eligibility("ayoub", dob, 16) is True

    def test_birthday_not_yet_reached_this_year_is_still_below(self):
        # Born exactly 16 years ago but one day in the future (birthday tomorrow)
        future_birthday = date.today() + timedelta(days=1)
        dob = future_birthday.replace(year=future_birthday.year - 16)
        assert check_transition_eligibility("ayoub", dob.isoformat(), 16) is False

    def test_custom_min_age(self):
        dob = (date.today().replace(year=date.today().year - 18)).isoformat()
        assert check_transition_eligibility("ayoub", dob, 18) is True
        assert check_transition_eligibility("ayoub", dob, 19) is False


# ─── execute_transition ───────────────────────────────────────────────────────

class TestExecuteTransition:
    def _make_provisioner(self, revoke_returns=None):
        mock = MagicMock()
        if revoke_returns is None:
            mock.revoke_acl_access.return_value = (True, "Revoked")
        else:
            mock.revoke_acl_access.side_effect = revoke_returns
        return mock

    def test_revoke_called_once_per_guardian(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CSS_CONNECT_URL", "http://localhost:3000")
        # Point JSONL to tmp_path
        jsonl_path = tmp_path / "consent-events.jsonl"
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path.touch()

        mock_provisioner = self._make_provisioner()
        guardian_webids = [
            "http://localhost:3000/guardian1/profile/card#me",
            "http://localhost:3000/guardian2/profile/card#me",
        ]

        with patch("pocpod0_pipeline.governance_transition._get_provisioner", return_value=mock_provisioner):
            result = execute_transition("ayoub", "http://localhost:3000/ayoub/profile/card#me", guardian_webids)

        assert mock_provisioner.revoke_acl_access.call_count == 2
        mock_provisioner.revoke_acl_access.assert_any_call("ayoub", guardian_webids[0])
        mock_provisioner.revoke_acl_access.assert_any_call("ayoub", guardian_webids[1])
        assert result.revoked_count == 2
        assert result.success is True

    def test_jsonl_event_emitted_on_transition(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        mock_provisioner = self._make_provisioner()
        guardian_webids = ["http://localhost:3000/guardian/profile/card#me"]

        with patch("pocpod0_pipeline.governance_transition._get_provisioner", return_value=mock_provisioner):
            execute_transition("ayoub", "http://localhost:3000/ayoub/profile/card#me", guardian_webids)

        events = [json.loads(line) for line in jsonl_path.read_text().strip().splitlines()]
        assert len(events) == 1
        assert events[0]["event_type"] == "acl.governance.transition"
        assert events[0]["pod"] == "ayoub"
        assert events[0]["from_role"] == "shared_governance"
        assert events[0]["to_role"] == "sole_owner"
        assert guardian_webids[0] in events[0]["revoked_identities"]

    def test_partial_failure_logs_error_and_continues(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        guardian_webids = [
            "http://localhost:3000/guardian1/profile/card#me",
            "http://localhost:3000/guardian2/profile/card#me",
        ]

        # First revoke raises exception, second succeeds
        mock_provisioner = self._make_provisioner(
            revoke_returns=[Exception("CSS timeout"), (True, "Revoked")]
        )

        with patch("pocpod0_pipeline.governance_transition._get_provisioner", return_value=mock_provisioner):
            result = execute_transition("ayoub", "http://localhost:3000/ayoub/profile/card#me", guardian_webids)

        assert result.partial_success is True
        assert result.revoked_count == 1
        assert len(result.failed_revokes) == 1
        assert result.failed_revokes[0]["webid"] == guardian_webids[0]
        # Both revokes were attempted — did not abort after first failure
        assert mock_provisioner.revoke_acl_access.call_count == 2

    def test_no_guardians_is_successful_transition(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        mock_provisioner = self._make_provisioner()

        with patch("pocpod0_pipeline.governance_transition._get_provisioner", return_value=mock_provisioner):
            result = execute_transition("ayoub", "http://localhost:3000/ayoub/profile/card#me", [])

        assert result.success is True
        assert result.revoked_count == 0
        mock_provisioner.revoke_acl_access.assert_not_called()


# ─── acl-manage handler ownership scope ──────────────────────────────────────

class TestAclManageOwnershipScope:
    """Tests for handler.py ownership enforcement (AC5)."""

    def _import_handler(self):
        """Import handler module fresh each time."""
        import importlib
        import handler as h
        importlib.reload(h)
        return h

    def test_agent_owning_pod_is_allowed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "ayoub")
        monkeypatch.setenv("AGENT_ID", "ayoub-student")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        mock_provisioner.revoke_acl_access.return_value = (True, "Revoked")

        result = h.action_revoke(mock_provisioner, "ayoub", "http://localhost:3000/guardian/profile/card#me")
        assert result["status"] == "ok"

    def test_agent_not_owning_pod_is_denied(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "claire")
        monkeypatch.setenv("AGENT_ID", "claire-teacher")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        result = h.action_revoke(mock_provisioner, "ayoub", "http://localhost:3000/guardian/profile/card#me")

        assert result["status"] == "denied"
        assert "claire-teacher" in result["message"]
        assert "ayoub" in result["message"]
        mock_provisioner.revoke_acl_access.assert_not_called()

    def test_denied_message_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "other-pod")
        monkeypatch.setenv("AGENT_ID", "claire-teacher")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        result = h.action_grant(
            mock_provisioner, "ayoub",
            "http://localhost:3000/claire/profile/card#me",
            "teacher", "read"
        )

        assert result["status"] == "denied"
        assert "Authorization denied" in result["message"]

    def test_empty_ownership_env_denies_all(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "")
        monkeypatch.setenv("AGENT_ID", "some-agent")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        result = h.action_grant(mock_provisioner, "ayoub", "http://x/p", "role", "read")
        assert result["status"] == "denied"
        assert "Authorization denied" in result["message"]
        assert "some-agent" in result["message"]

    def test_view_is_permitted_without_ownership(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        (tmp_path / "data" / "consent-events.jsonl").touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        mock_provisioner.view_acl_state.return_value = (True, {"acl_grants": []})

        result = h.action_view(mock_provisioner, "ayoub")
        assert result["status"] == "ok"


# ─── JSONL event format ───────────────────────────────────────────────────────

class TestJsonlEventFormat:
    ALLOWED_EVENT_TYPES = {
        "acl.grant",
        "acl.revoke",
        "acl.view",
        "acl.governance.transition",
        "acl.denied",
    }

    def _collect_events(self, jsonl_path: Path) -> list[dict]:
        lines = jsonl_path.read_text().strip().splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def test_every_event_is_json_parseable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "ayoub")
        monkeypatch.setattr(
            "pocpod0_pipeline.governance_transition._PROJECT_ROOT", tmp_path
        )
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        mock_provisioner.grant_acl_access.return_value = (True, "Granted")
        mock_provisioner.revoke_acl_access.return_value = (True, "Revoked")
        mock_provisioner.view_acl_state.return_value = (True, {"acl_grants": []})

        h.action_grant(mock_provisioner, "ayoub", "http://x/p", "role", "read")
        h.action_revoke(mock_provisioner, "ayoub", "http://x/p")
        h.action_view(mock_provisioner, "ayoub")

        events = self._collect_events(jsonl_path)
        assert len(events) == 3
        for event in events:
            assert isinstance(event, dict)

    def test_event_type_is_in_allowed_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "ayoub")
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        mock_provisioner.grant_acl_access.return_value = (True, "Granted")
        h.action_grant(mock_provisioner, "ayoub", "http://x/p", "role", "read")

        events = self._collect_events(jsonl_path)
        for event in events:
            assert event["event_type"] in self.ALLOWED_EVENT_TYPES

    def test_timestamp_is_iso8601(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "ayoub")
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        mock_provisioner.view_acl_state.return_value = (True, {"acl_grants": []})
        h.action_view(mock_provisioner, "ayoub")

        events = self._collect_events(jsonl_path)
        for event in events:
            ts = event.get("timestamp", "")
            # Must be parseable as ISO-8601
            from datetime import datetime
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            assert parsed is not None

    def test_denied_event_emitted_on_ownership_violation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_POD_OWNERSHIP", "other")
        monkeypatch.setenv("AGENT_ID", "claire-teacher")
        (tmp_path / "data").mkdir(exist_ok=True)
        jsonl_path = tmp_path / "data" / "consent-events.jsonl"
        jsonl_path.touch()

        import handler as h
        monkeypatch.setattr("handler._PROJECT_ROOT", tmp_path)

        mock_provisioner = MagicMock()
        h.action_grant(mock_provisioner, "ayoub", "http://x/p", "role", "read")

        events = self._collect_events(jsonl_path)
        assert len(events) == 1
        assert events[0]["event_type"] == "acl.denied"
        assert events[0]["pod"] == "ayoub"
