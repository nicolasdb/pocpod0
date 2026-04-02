"""Tests for mission_control.py — Operations Control Room.

Covers:
  - Event parsing (parse_consent_event)
  - Pod state calculation (calculate_pod_state, build_pod_states)
  - Cascade impact computation (compute_cascade_impact)
  - Troll result aggregation (aggregate_troll_results, TrollCategoryResult)
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pocpod0_pipeline.mission_control import (
    ConsentEvent,
    PodState,
    PodStateEnum,
    TrollCategoryResult,
    POD_SLUGS,
    parse_consent_event,
    calculate_pod_state,
    build_pod_states,
    compute_cascade_impact,
    aggregate_troll_results,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def seeded_events():
    """Simulates post-seed state: 6 pods consented, ayoub has no events."""
    seeded = [p for p in POD_SLUGS if p != "ayoub"]
    return [
        ConsentEvent(
            timestamp="2026-04-01T10:00:00Z",
            event_type="consent.grant",
            pod=pod,
            grantee_webid="https://school.example.org/profile#school",
            scope="school-enrollment",
        )
        for pod in seeded
    ]


# =========================================================================
# Event Parsing
# =========================================================================

class TestEventParsing:
    def test_parse_valid_consent_grant(self):
        line = json.dumps({
            "timestamp": "2026-04-01T10:00:00Z",
            "event_type": "consent.grant",
            "pod": "ayoub",
            "grantee_webid": "https://school.example.org/profile#school",
            "scope": "school-enrollment",
        })
        ev = parse_consent_event(line)
        assert ev is not None
        assert ev.event_type == "consent.grant"
        assert ev.pod == "ayoub"

    def test_parse_valid_consent_revoke(self):
        line = json.dumps({
            "timestamp": "2026-04-01T11:00:00Z",
            "event_type": "consent.revoke",
            "pod": "claire",
        })
        ev = parse_consent_event(line)
        assert ev is not None
        assert ev.event_type == "consent.revoke"
        assert ev.pod == "claire"

    def test_parse_acl_governance_transition(self):
        line = json.dumps({
            "timestamp": "2026-04-01T12:00:00Z",
            "event_type": "acl.governance.transition",
            "pod": "fatima-child-1",
        })
        ev = parse_consent_event(line)
        assert ev is not None
        assert ev.event_type == "acl.governance.transition"

    def test_parse_malformed_json_returns_none(self):
        assert parse_consent_event("not valid json") is None

    def test_parse_empty_line_returns_none(self):
        assert parse_consent_event("") is None

    def test_parse_missing_pod_field(self):
        line = json.dumps({"timestamp": "2026-04-01T10:00:00Z", "event_type": "consent.grant"})
        ev = parse_consent_event(line)
        assert ev is not None
        assert ev.pod is None


# =========================================================================
# Pod State Calculation
# =========================================================================

class TestPodStateCalculation:
    def test_active_after_grant(self):
        events = [ConsentEvent("2026-04-01T10:00:00Z", "consent.grant", pod="ayoub")]
        state = calculate_pod_state("ayoub", events)
        assert state.current_state == PodStateEnum.ACTIVE

    def test_active_after_acl_grant(self):
        events = [ConsentEvent("2026-04-01T10:00:00Z", "acl.grant", pod="claire")]
        state = calculate_pod_state("claire", events)
        assert state.current_state == PodStateEnum.ACTIVE

    def test_revoked_after_revoke(self):
        events = [
            ConsentEvent("2026-04-01T10:00:00Z", "consent.grant", pod="ayoub"),
            ConsentEvent("2026-04-01T11:00:00Z", "consent.revoke", pod="ayoub"),
        ]
        state = calculate_pod_state("ayoub", events)
        assert state.current_state == PodStateEnum.REVOKED

    def test_revoked_after_expired(self):
        events = [
            ConsentEvent("2026-04-01T10:00:00Z", "consent.grant", pod="claire"),
            ConsentEvent("2026-04-01T12:00:00Z", "consent.expired", pod="claire"),
        ]
        state = calculate_pod_state("claire", events)
        assert state.current_state == PodStateEnum.REVOKED

    def test_transitioning_after_governance_change(self):
        events = [
            ConsentEvent("2026-04-01T10:00:00Z", "consent.grant", pod="fatima-child-1"),
            ConsentEvent("2026-04-01T14:00:00Z", "acl.governance.transition", pod="fatima-child-1"),
        ]
        state = calculate_pod_state("fatima-child-1", events)
        assert state.current_state == PodStateEnum.TRANSITIONING

    def test_no_consent_when_no_events(self):
        """Pod with no events is NO_CONSENT (not ANOMALY)."""
        state = calculate_pod_state("ayoub", [])
        assert state.current_state == PodStateEnum.NO_CONSENT
        assert state.event_count == 0

    def test_event_count_tracked(self):
        events = [
            ConsentEvent("2026-04-01T10:00:00Z", "consent.grant", pod="claire"),
            ConsentEvent("2026-04-01T11:00:00Z", "consent.revoke", pod="claire"),
        ]
        state = calculate_pod_state("claire", events)
        assert state.event_count == 2

    def test_events_sorted_by_timestamp(self):
        """State determined by latest event even when events are out of order."""
        events = [
            ConsentEvent("2026-04-01T11:00:00Z", "consent.grant", pod="ayoub"),
            ConsentEvent("2026-04-01T10:00:00Z", "consent.revoke", pod="ayoub"),  # earlier
        ]
        state = calculate_pod_state("ayoub", events)
        # Grant is latest (11:00) → active
        assert state.current_state == PodStateEnum.ACTIVE


# =========================================================================
# Build Pod States
# =========================================================================

class TestBuildPodStates:
    def test_all_pods_present_after_seed(self, seeded_events):
        """After seed, all 8 pods have a state."""
        states = build_pod_states(seeded_events)
        assert set(states.keys()) == set(POD_SLUGS)

    def test_ayoub_no_consent_after_seed(self, seeded_events):
        """Ayoub has no events in seed → NO_CONSENT."""
        states = build_pod_states(seeded_events)
        assert states["ayoub"].current_state == PodStateEnum.NO_CONSENT

    def test_seeded_pods_active(self, seeded_events):
        """All non-ayoub pods are ACTIVE after seed."""
        states = build_pod_states(seeded_events)
        for pod in POD_SLUGS:
            if pod != "ayoub":
                assert states[pod].current_state == PodStateEnum.ACTIVE, f"{pod} should be ACTIVE"

    def test_empty_events_all_no_consent(self):
        """With no events, all pods are NO_CONSENT."""
        states = build_pod_states([])
        assert all(s.current_state == PodStateEnum.NO_CONSENT for s in states.values())


# =========================================================================
# Cascade Impact
# =========================================================================

class TestCascadeImpact:
    def _all_active_except(self, *excluded: str) -> dict[str, PodState]:
        states = {}
        for pod in POD_SLUGS:
            if pod in excluded:
                states[pod] = PodState(pod, PodStateEnum.NO_CONSENT)
            else:
                states[pod] = PodState(pod, PodStateEnum.ACTIVE)
        return states

    def test_unknown_pod_returns_message(self):
        states = self._all_active_except()
        result = compute_cascade_impact("nonexistent", states)
        # Pod not in POD_SLUGS → descriptive "no pod" message
        assert "No pod selected" in result or "click" in result.lower()

    def test_ayoub_cascade_shows_no_dependents(self):
        states = self._all_active_except("ayoub")
        result = compute_cascade_impact("ayoub", states)
        # ayoub has no downstream dependents in CASCADE_MAP
        assert "ayoub" in result
        assert "school" in result.lower() or "threshold" in result.lower()

    def test_fatima_cascade_includes_children(self):
        """Fatima controls fatima-child-1 and fatima-child-2."""
        states = self._all_active_except()
        result = compute_cascade_impact("fatima", states)
        assert "fatima-child-1" in result or "fatima-child-2" in result

    def test_threshold_met_when_enough_active(self):
        states = self._all_active_except()  # 8 active
        result = compute_cascade_impact("ayoub", states)
        # Even if ayoub revokes, 7 remain ≥ _MIN_PODS_FOR_PUBLICATION (6)
        assert "MET" in result

    def test_threshold_not_met_when_too_few(self):
        # Only 6 pods active; fatima controls 2 children → after revoke: 3 remain
        states = {
            "ayoub": PodState("ayoub", PodStateEnum.NO_CONSENT),
            "claire": PodState("claire", PodStateEnum.NO_CONSENT),
            "claire-student-1": PodState("claire-student-1", PodStateEnum.NO_CONSENT),
            "claire-student-2": PodState("claire-student-2", PodStateEnum.NO_CONSENT),
            "fatima": PodState("fatima", PodStateEnum.ACTIVE),
            "fatima-child-1": PodState("fatima-child-1", PodStateEnum.ACTIVE),
            "fatima-child-2": PodState("fatima-child-2", PodStateEnum.ACTIVE),
            "school-community": PodState("school-community", PodStateEnum.ACTIVE),
        }
        result = compute_cascade_impact("fatima", states)
        # fatima revokes → removes herself + 2 children → 1 active left → NOT MET
        assert "NOT MET" in result


# =========================================================================
# Troll Result Aggregation
# =========================================================================

class TestTrollResultAggregation:
    def _make_probe_done(self, category: str, result: str) -> str:
        return json.dumps({
            "event_type": "troll.probe.done",
            "category": category,
            "test_name": f"{category}-001",
            "result": result,
        })

    def _make_category_done(self, category: str, passed: int, partial: int, failed: int) -> str:
        return json.dumps({
            "event_type": "troll.category.done",
            "category": category,
            "passed": passed,
            "partial": partial,
            "failed": failed,
        })

    def test_empty_lines_returns_empty(self):
        result = aggregate_troll_results([])
        assert result == {}

    def test_probe_done_counts_pass(self):
        lines = [self._make_probe_done("access-control", "pass")]
        result = aggregate_troll_results(lines)
        assert "access-control" in result
        assert result["access-control"].passed == 1
        assert result["access-control"].failed == 0

    def test_probe_done_counts_fail(self):
        lines = [
            self._make_probe_done("access-control", "pass"),
            self._make_probe_done("access-control", "fail"),
        ]
        result = aggregate_troll_results(lines)
        r = result["access-control"]
        assert r.passed == 1
        assert r.failed == 1

    def test_category_done_takes_precedence_over_probes(self):
        """troll.category.done summary overrides probe aggregation."""
        lines = [
            self._make_probe_done("access-control", "pass"),
            self._make_category_done("access-control", passed=10, partial=2, failed=0),
        ]
        result = aggregate_troll_results(lines)
        r = result["access-control"]
        # Should use summary values, not probe count
        assert r.passed == 10
        assert r.partial == 2

    def test_multiple_categories(self):
        lines = [
            self._make_probe_done("access-control", "pass"),
            self._make_probe_done("query-safety", "fail"),
        ]
        result = aggregate_troll_results(lines)
        assert "access-control" in result
        assert "query-safety" in result

    def test_severity_green_when_all_pass(self):
        r = TrollCategoryResult(category="x", passed=5, partial=0, failed=0)
        assert r.severity == "green"

    def test_severity_yellow_when_partial(self):
        r = TrollCategoryResult(category="x", passed=4, partial=1, failed=0)
        assert r.severity == "yellow"

    def test_severity_red_when_any_fail(self):
        r = TrollCategoryResult(category="x", passed=3, partial=0, failed=2)
        assert r.severity == "red"

    def test_severity_unknown_when_empty(self):
        r = TrollCategoryResult(category="x", passed=0, partial=0, failed=0)
        assert r.severity == "unknown"

    def test_malformed_json_skipped(self):
        lines = ["not json", self._make_probe_done("access-control", "pass")]
        result = aggregate_troll_results(lines)
        assert result["access-control"].passed == 1

    def test_real_troll_run_format(self):
        """Parse the actual troll-run.jsonl format from Story 6.1."""
        lines = [
            json.dumps({
                "event_type": "troll.category.done",
                "timestamp": "2026-03-29T11:32:10.887272Z",
                "category": "deletion_timing",
                "passed": 0,
                "partial": 0,
                "failed": 5,
            })
        ]
        result = aggregate_troll_results(lines)
        assert "deletion_timing" in result
        r = result["deletion_timing"]
        assert r.failed == 5
        assert r.severity == "red"
