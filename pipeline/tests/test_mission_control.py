"""Tests for mission_control.py — consent propagation visualizer.

Tests cover:
- Task 2: Pod state calculation
- Task 3: Cluster aggregate calculation
- Task 4: Regional aggregate calculation
- Task 5: Civic aggregate calculation
- Task 6: Keyframe detection
- Task 13: Event parsing
- Task 14: Integration tests
"""

import json
import pytest
from datetime import datetime
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pocpod0_pipeline.mission_control import (
    ConsentEvent,
    PodState,
    PodStateEnum,
    ClusterAggregate,
    RegionalAggregate,
    CivicAggregate,
    parse_consent_event,
    calculate_pod_state,
    calculate_cluster_aggregate,
    calculate_regional_aggregate,
    calculate_civic_aggregate,
    should_fire_keyframe_stop1,
    should_fire_keyframe_stop2,
    should_fire_keyframe_stop3,
    should_fire_keyframe_stop4,
    CLUSTER_MAPPING,
    REGION_MAPPING,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def sample_events():
    """Sample consent events for testing."""
    return [
        ConsentEvent(
            timestamp="2026-03-31T14:00:00Z",
            event_type="consent.grant",
            pod="ayoub-pod",
            grantee_webid="isabelle-webid",
            scope="STEM_PROGRESS",
        ),
        ConsentEvent(
            timestamp="2026-03-31T14:15:00Z",
            event_type="consent.grant",
            pod="sofia-pod",
            grantee_webid="isabelle-webid",
            scope="STEM_PROGRESS",
        ),
        ConsentEvent(
            timestamp="2026-03-31T14:30:00Z",
            event_type="consent.revoke",
            pod="karim-pod",
        ),
    ]


# =========================================================================
# Task 13: Event Parsing Tests
# =========================================================================

class TestEventParsing:
    """Unit tests for JSON parsing (Task 13)."""

    def test_parse_valid_consent_grant_event(self):
        """Parse valid consent.grant event."""
        line = json.dumps({
            "timestamp": "2026-03-31T14:00:00Z",
            "event_type": "consent.grant",
            "pod": "ayoub-pod",
            "grantee_webid": "isabelle-webid",
            "scope": "STEM_PROGRESS",
        })
        event = parse_consent_event(line)

        assert event is not None
        assert event.event_type == "consent.grant"
        assert event.pod == "ayoub-pod"
        assert event.timestamp == "2026-03-31T14:00:00Z"

    def test_parse_valid_consent_revoke_event(self):
        """Parse valid consent.revoke event."""
        line = json.dumps({
            "timestamp": "2026-03-31T14:30:00Z",
            "event_type": "consent.revoke",
            "pod": "karim-pod",
        })
        event = parse_consent_event(line)

        assert event is not None
        assert event.event_type == "consent.revoke"
        assert event.pod == "karim-pod"

    def test_parse_malformed_json(self):
        """Handle malformed JSON gracefully (Task 13.3)."""
        line = "not valid json"
        event = parse_consent_event(line)

        assert event is None

    def test_parse_empty_line(self):
        """Handle empty lines gracefully."""
        line = ""
        event = parse_consent_event(line)

        assert event is None

    def test_parse_missing_fields(self):
        """Handle missing fields gracefully (Task 13.4)."""
        line = json.dumps({
            "timestamp": "2026-03-31T14:00:00Z",
            "event_type": "consent.grant",
            # pod is missing
        })
        event = parse_consent_event(line)

        assert event is not None
        assert event.pod is None

    def test_parse_acl_grant_event(self):
        """Parse ACL grant event."""
        line = json.dumps({
            "timestamp": "2026-03-31T14:00:00Z",
            "event_type": "acl.grant",
            "pod": "ayoub-pod",
        })
        event = parse_consent_event(line)

        assert event is not None
        assert event.event_type == "acl.grant"

    def test_parse_governance_transition_event(self):
        """Parse acl.governance.transition event."""
        line = json.dumps({
            "timestamp": "2026-03-31T14:45:00Z",
            "event_type": "acl.governance.transition",
            "pod": "mehdi-pod",
        })
        event = parse_consent_event(line)

        assert event is not None
        assert event.event_type == "acl.governance.transition"


# =========================================================================
# Task 2: Pod State Calculation Tests
# =========================================================================

class TestPodStateCalculation:
    """Unit tests for pod state calculation (Task 2)."""

    def test_pod_active_after_grant(self, sample_events):
        """Pod is active after consent.grant (Task 2.2)."""
        state = calculate_pod_state("ayoub-pod", sample_events)

        assert state.current_state == PodStateEnum.ACTIVE
        assert state.pod_id == "ayoub-pod"

    def test_pod_revoked_after_revoke(self, sample_events):
        """Pod is revoked after consent.revoke (Task 2.2)."""
        state = calculate_pod_state("karim-pod", sample_events)

        assert state.current_state == PodStateEnum.REVOKED

    def test_pod_revoked_after_expired(self):
        """Pod is revoked after consent.expired."""
        events = [
            ConsentEvent(
                timestamp="2026-03-31T14:00:00Z",
                event_type="consent.grant",
                pod="sofia-pod",
            ),
            ConsentEvent(
                timestamp="2026-03-31T15:00:00Z",
                event_type="consent.expired",
                pod="sofia-pod",
            ),
        ]
        state = calculate_pod_state("sofia-pod", events)

        assert state.current_state == PodStateEnum.REVOKED

    def test_pod_transitioning_after_governance_change(self):
        """Pod is transitioning after acl.governance.transition."""
        events = [
            ConsentEvent(
                timestamp="2026-03-31T14:00:00Z",
                event_type="consent.grant",
                pod="mehdi-pod",
            ),
            ConsentEvent(
                timestamp="2026-03-31T14:45:00Z",
                event_type="acl.governance.transition",
                pod="mehdi-pod",
            ),
        ]
        state = calculate_pod_state("mehdi-pod", events)

        assert state.current_state == PodStateEnum.TRANSITIONING

    def test_pod_anomaly_when_unknown(self):
        """Pod is anomaly when no events exist (Task 2.2)."""
        state = calculate_pod_state("unknown-pod", [])

        assert state.current_state == PodStateEnum.ANOMALY

    def test_pod_event_count(self):
        """Pod tracks number of events."""
        events = [
            ConsentEvent(timestamp="2026-03-31T14:00:00Z", event_type="consent.grant", pod="sofia-pod"),
            ConsentEvent(timestamp="2026-03-31T14:30:00Z", event_type="consent.revoke", pod="sofia-pod"),
        ]
        state = calculate_pod_state("sofia-pod", events)

        assert state.event_count == 2


# =========================================================================
# Task 3: Cluster Aggregate Calculation Tests
# =========================================================================

class TestClusterAggregateCalculation:
    """Unit tests for cluster aggregate calculation (Task 3)."""

    def test_cluster_aggregate_counts_active_pods(self):
        """Cluster aggregate counts active pods (Task 3.2)."""
        pod_states = {
            "ayoub-pod": PodState("ayoub-pod", PodStateEnum.ACTIVE),
            "sofia-pod": PodState("sofia-pod", PodStateEnum.ACTIVE),
            "karim-pod": PodState("karim-pod", PodStateEnum.REVOKED),
            "fatima-pod": PodState("fatima-pod", PodStateEnum.ACTIVE),
        }

        # Fill with anomaly for other pods in cluster
        for pod in CLUSTER_MAPPING["school-nl-1"]:
            if pod not in pod_states:
                pod_states[pod] = PodState(pod, PodStateEnum.ANOMALY)

        agg = calculate_cluster_aggregate("school-nl-1", pod_states)

        assert agg.active_pods == 3
        assert agg.revoked_pods == 1
        assert agg.cluster_id == "school-nl-1"

    def test_cluster_aggregate_recalculation_on_state_change(self):
        """Cluster aggregate recalculates when pod state changes (Task 3.3)."""
        # Initial state: all pods active
        pod_states_1 = {pod: PodState(pod, PodStateEnum.ACTIVE) for pod in CLUSTER_MAPPING["school-nl-1"]}
        agg_1 = calculate_cluster_aggregate("school-nl-1", pod_states_1)

        # State change: one pod revoked
        pod_states_2 = {pod: PodState(pod, PodStateEnum.ACTIVE) for pod in CLUSTER_MAPPING["school-nl-1"]}
        pod_states_2["karim-pod"] = PodState("karim-pod", PodStateEnum.REVOKED)
        agg_2 = calculate_cluster_aggregate("school-nl-1", pod_states_2)

        assert agg_1.active_pods > agg_2.active_pods
        assert agg_2.revoked_pods == 1

    def test_cluster_aggregate_returns_metadata(self):
        """Cluster aggregate includes cluster name and last_updated (Task 3.2)."""
        pod_states = {pod: PodState(pod, PodStateEnum.ACTIVE) for pod in CLUSTER_MAPPING["school-nl-1"]}

        agg = calculate_cluster_aggregate("school-nl-1", pod_states)

        assert agg.cluster_name is not None
        assert agg.last_updated is not None
        assert isinstance(agg.last_updated, str)


# =========================================================================
# Task 4: Regional Aggregate Calculation Tests
# =========================================================================

class TestRegionalAggregateCalculation:
    """Unit tests for regional aggregate calculation (Task 4)."""

    def test_regional_aggregate_sums_clusters(self):
        """Regional aggregate sums cluster counts (Task 4.1)."""
        cluster_aggs = {
            "school-nl-1": ClusterAggregate(
                cluster_id="school-nl-1",
                cluster_name="School NL",
                pods=[],
                active_pods=8,
                total_pods=8,
            ),
            "school-fr-1": ClusterAggregate(
                cluster_id="school-fr-1",
                cluster_name="School FR",
                pods=[],
                active_pods=6,
                total_pods=8,
            ),
        }

        agg = calculate_regional_aggregate("nl-region", {"school-nl-1": cluster_aggs["school-nl-1"]})

        assert agg.total_pods == 8
        assert agg.active_pods == 8

    def test_regional_publication_ready_threshold(self):
        """Regional aggregate checks publication threshold (Task 4.2)."""
        # With enough pods for publication (>= 10)
        cluster_aggs_good = {
            "school-nl-1": ClusterAggregate(
                cluster_id="school-nl-1",
                cluster_name="School NL",
                pods=[],
                active_pods=10,
                total_pods=10,
            ),
        }

        agg_good = calculate_regional_aggregate("nl-region", cluster_aggs_good)
        assert agg_good.publication_ready is True

        # With insufficient pods for publication (< 10)
        cluster_aggs_bad = {
            "school-nl-1": ClusterAggregate(
                cluster_id="school-nl-1",
                cluster_name="School NL",
                pods=[],
                active_pods=5,
                total_pods=8,
            ),
        }

        agg_bad = calculate_regional_aggregate("nl-region", cluster_aggs_bad)
        assert agg_bad.publication_ready is False


# =========================================================================
# Task 5: Civic Aggregate Calculation Tests
# =========================================================================

class TestCivicAggregateCalculation:
    """Unit tests for civic aggregate calculation (Task 5)."""

    def test_civic_aggregate_privacy_boundary_respected(self):
        """Civic aggregate validates privacy boundary (Task 5.2)."""
        regional_agg = RegionalAggregate(
            region_id="nl-region",
            region_name="Brussels NL",
            clusters=["school-nl-1"],
            total_pods=8,
            active_pods=8,
            publication_ready=True,
        )

        # All pods active = privacy respected
        pod_states = {pod: PodState(pod, PodStateEnum.ACTIVE) for pod in CLUSTER_MAPPING["school-nl-1"]}

        agg = calculate_civic_aggregate(regional_agg, pod_states)

        assert agg.privacy_boundary_respected is True

    def test_civic_aggregate_privacy_boundary_violated(self):
        """Civic aggregate detects privacy violations (Task 5.3)."""
        regional_agg = RegionalAggregate(
            region_id="nl-region",
            region_name="Brussels NL",
            clusters=["school-nl-1"],
            total_pods=8,
            active_pods=7,  # One pod revoked
            publication_ready=True,
        )

        # One pod revoked = check privacy boundary
        pod_states = {pod: PodState(pod, PodStateEnum.ACTIVE) for pod in CLUSTER_MAPPING["school-nl-1"]}
        pod_states["karim-pod"] = PodState("karim-pod", PodStateEnum.REVOKED)

        agg = calculate_civic_aggregate(regional_agg, pod_states)

        # Privacy boundary should detect the revoked pod
        assert agg.privacy_boundary_respected is False


# =========================================================================
# Task 6: Keyframe Detection Tests
# =========================================================================

class TestKeyframeDetection:
    """Unit tests for keyframe detection (Task 6)."""

    def test_keyframe_fires_on_consent_grant(self):
        """Keyframe fires on consent.grant event (Task 6.1)."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:00:00Z",
            event_type="consent.grant",
            pod="ayoub-pod",
        )

        assert should_fire_keyframe_stop1(event) is True

    def test_keyframe_fires_on_consent_revoke(self):
        """Keyframe fires on consent.revoke event."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:30:00Z",
            event_type="consent.revoke",
            pod="karim-pod",
        )

        assert should_fire_keyframe_stop1(event) is True

    def test_keyframe_fires_on_acl_grant(self):
        """Keyframe fires on acl.grant event."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:00:00Z",
            event_type="acl.grant",
            pod="mehdi-pod",
        )

        assert should_fire_keyframe_stop1(event) is True

    def test_keyframe_fires_on_governance_transition(self):
        """Keyframe fires on acl.governance.transition event."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:45:00Z",
            event_type="acl.governance.transition",
            pod="mehdi-pod",
        )

        assert should_fire_keyframe_stop1(event) is True

    def test_keyframe_stop2_fires_on_aggregate_change(self):
        """Keyframe STOP 2 fires when cluster active_pods count changes (Task 6.2)."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:30:00Z",
            event_type="consent.revoke",
            pod="karim-pod",
        )

        previous_agg = ClusterAggregate(
            cluster_id="school-nl-1",
            cluster_name="School NL",
            pods=[],
            active_pods=8,
            total_pods=8,
        )
        current_agg = ClusterAggregate(
            cluster_id="school-nl-1",
            cluster_name="School NL",
            pods=[],
            active_pods=7,  # count changed after revoke
            total_pods=8,
        )

        assert should_fire_keyframe_stop2(event, previous_agg, current_agg) is True

    def test_keyframe_stop2_no_fire_when_unchanged(self):
        """Keyframe STOP 2 does NOT fire when cluster count is unchanged."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:30:00Z",
            event_type="acl.grant",
            pod="karim-pod",
        )
        agg = ClusterAggregate("school-nl-1", "School NL", [], active_pods=8, total_pods=8)
        assert should_fire_keyframe_stop2(event, agg, agg) is False

    def test_keyframe_stop4_fires_on_civic_locked(self):
        """Keyframe STOP 4 fires on civic.aggregate.locked event (Task 6.4)."""
        event = ConsentEvent(
            timestamp="2026-03-31T16:00:00Z",
            event_type="civic.aggregate.locked",
        )

        assert should_fire_keyframe_stop4(event) is True

    def test_keyframe_stop4_fires_on_threshold_breach(self):
        """Keyframe STOP 4 fires on civic.threshold.breach event."""
        event = ConsentEvent(
            timestamp="2026-03-31T16:15:00Z",
            event_type="civic.threshold.breach",
        )

        assert should_fire_keyframe_stop4(event) is True


# =========================================================================
# Task 14: Integration Tests
# =========================================================================

class TestIntegration:
    """Integration tests for full scenarios (Task 14)."""

    def test_full_scenario_claire_request_to_revoke_impact(self):
        """Full scenario: Claire request → Karim revoke → cluster impact (Task 14.3)."""
        # Scenario: Claire makes request, Ayoub grants, then Karim revokes
        events = [
            # Ayoub grants consent for STEM_PROGRESS
            ConsentEvent(
                timestamp="2026-03-31T14:00:00Z",
                event_type="consent.grant",
                pod="ayoub-pod",
                scope="STEM_PROGRESS",
            ),
            # Sofia grants
            ConsentEvent(
                timestamp="2026-03-31T14:05:00Z",
                event_type="consent.grant",
                pod="sofia-pod",
                scope="STEM_PROGRESS",
            ),
            # ... more grants ...
        ]

        # Initialize 16 pods to active
        for pod in CLUSTER_MAPPING["school-nl-1"][:6]:
            events.append(ConsentEvent(
                timestamp=f"2026-03-31T14:0{len(events)}:00Z",
                event_type="consent.grant",
                pod=pod,
            ))

        # Calculate initial cluster state
        pod_states_1 = {pod: calculate_pod_state(pod, events) for pod in CLUSTER_MAPPING["school-nl-1"]}
        cluster_1 = calculate_cluster_aggregate("school-nl-1", pod_states_1)

        # Karim revokes
        events.append(ConsentEvent(
            timestamp="2026-03-31T14:30:00Z",
            event_type="consent.revoke",
            pod="karim-pod",
        ))

        # Recalculate cluster state
        pod_states_2 = {pod: calculate_pod_state(pod, events) for pod in CLUSTER_MAPPING["school-nl-1"]}
        cluster_2 = calculate_cluster_aggregate("school-nl-1", pod_states_2)

        # Verify impact: cluster count decreased
        assert cluster_2.active_pods < cluster_1.active_pods

    def test_privacy_boundary_on_civic_publication(self):
        """Integration: Verify privacy boundary on civic publication (Task 14.3)."""
        # Create consent history with revoked pods
        events = [
            ConsentEvent(timestamp="2026-03-31T14:00:00Z", event_type="consent.grant", pod="ayoub-pod"),
            ConsentEvent(timestamp="2026-03-31T14:05:00Z", event_type="consent.grant", pod="sofia-pod"),
            ConsentEvent(timestamp="2026-03-31T14:30:00Z", event_type="consent.revoke", pod="karim-pod"),
        ]

        # Fill remaining pods with active state
        for pod in CLUSTER_MAPPING["school-nl-1"][3:]:
            events.append(ConsentEvent(timestamp="2026-03-31T14:00:00Z", event_type="consent.grant", pod=pod))

        # Calculate states
        pod_states = {pod: calculate_pod_state(pod, events) for pod in CLUSTER_MAPPING["school-nl-1"]}
        cluster_aggs = {"school-nl-1": calculate_cluster_aggregate("school-nl-1", pod_states)}
        regional_agg = calculate_regional_aggregate("nl-region", cluster_aggs)
        civic_agg = calculate_civic_aggregate(regional_agg, pod_states)

        # Verify privacy boundary is correctly checked
        # With one revoked pod, privacy boundary should be violated
        assert civic_agg.privacy_boundary_respected is False

    def test_scenario_with_expired_tokens(self):
        """Integration: Handle expired consent tokens (Task 14.5)."""
        events = [
            ConsentEvent(
                timestamp="2026-03-31T14:00:00Z",
                event_type="consent.grant",
                pod="ayoub-pod",
            ),
            ConsentEvent(
                timestamp="2026-03-31T15:00:00Z",
                event_type="consent.expired",
                pod="ayoub-pod",
            ),
        ]

        state = calculate_pod_state("ayoub-pod", events)

        # Expired = revoked
        assert state.current_state == PodStateEnum.REVOKED

    def test_missing_pod_context_alert(self):
        """Integration: Handle missing pod context in events (Task 14.5)."""
        # Event missing pod field
        event = ConsentEvent(
            timestamp="2026-03-31T14:00:00Z",
            event_type="consent.grant",
            pod=None,  # Missing
        )

        # Should not crash, handle gracefully
        pod_states = {"unknown-pod": calculate_pod_state("unknown-pod", [event])}
        assert pod_states["unknown-pod"].current_state == PodStateEnum.ANOMALY


# =========================================================================
# Edge Case Tests
# =========================================================================

class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_empty_events_list(self):
        """Handle empty events list."""
        state = calculate_pod_state("ayoub-pod", [])
        assert state.current_state == PodStateEnum.ANOMALY

    def test_events_out_of_order(self):
        """Handle events that arrive out of chronological order in the list.

        grant has timestamp 14:30 (later) but appears first in the list.
        revoke has timestamp 14:00 (earlier) and appears second.
        After sorting by timestamp, grant is last → ACTIVE.
        """
        events = [
            ConsentEvent(timestamp="2026-03-31T14:30:00Z", event_type="consent.grant", pod="ayoub-pod"),
            ConsentEvent(timestamp="2026-03-31T14:00:00Z", event_type="consent.revoke", pod="ayoub-pod"),
        ]

        # Should sort by timestamp and use last event (grant@14:30)
        state = calculate_pod_state("ayoub-pod", events)
        assert state.current_state == PodStateEnum.ACTIVE  # grant is last by timestamp

    def test_cluster_with_no_pods(self):
        """Handle cluster with no pods."""
        pod_states = {}
        agg = calculate_cluster_aggregate("school-nl-1", pod_states)

        assert agg.active_pods == 0
        assert agg.revoked_pods == 0

    def test_unknown_event_type(self):
        """Handle unknown event type."""
        event = ConsentEvent(
            timestamp="2026-03-31T14:00:00Z",
            event_type="unknown.event.type",
            pod="ayoub-pod",
        )

        # Should not fire keyframe on unknown event
        assert should_fire_keyframe_stop1(event) is False
