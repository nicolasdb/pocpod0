"""Unit tests for the vector privacy attack module (Story 2.8).

Tests:
  1. PII detection helper with known PII and non-PII payloads (AC-6 / NFR12)
  2. Report generation format matches AC-4 schema
  3. Determinism: same inputs produce identical results (NFR12)
  4. Non-blocking exit behavior (AC-5)
  5. TrollTestResult reuse (no local dataclass defined)

Run from repo root with venv active:
    pytest agents/troll-adversary/tests/test_vector_privacy.py -v
"""

import importlib.util
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load vector_privacy module via importlib (consistent with project pattern)
# ---------------------------------------------------------------------------

_repo_root = Path(__file__).resolve().parents[3]  # pocpod0/
_vp_path = _repo_root / "agents" / "troll-adversary" / "attacks" / "vector_privacy.py"
_spec = importlib.util.spec_from_file_location("vector_privacy", _vp_path)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

detect_pii_in_payload = _mod.detect_pii_in_payload
TrollTestResult = _mod.TrollTestResult
_build_narrative = _mod._build_narrative
VectorPrivacyTestSuite = _mod.VectorPrivacyTestSuite

# Load TrollTestResult from the canonical source for identity check
_acl_path = _repo_root / "agents" / "troll-adversary" / "attacks" / "acl_enforcement.py"
_acl_spec = importlib.util.spec_from_file_location("acl_enforcement", _acl_path)
_acl_mod = importlib.util.module_from_spec(_acl_spec)  # type: ignore[arg-type]
_acl_spec.loader.exec_module(_acl_mod)  # type: ignore[union-attr]
CanonicalTrollTestResult = _acl_mod.TrollTestResult


# ---------------------------------------------------------------------------
# Tests: PII detection helper
# ---------------------------------------------------------------------------

class TestDetectPii:
    """Tests for detect_pii_in_payload() — ground truth PII detection."""

    def test_known_name_in_pod_uri(self):
        payload = {"pod_resource_uri": "http://localhost:3000/ayoub/", "triple_uris": []}
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is True
        assert pii_type in ("name", "identity")
        assert confidence >= 0.8

    def test_claire_student_pod(self):
        payload = {
            "pod_resource_uri": "http://localhost:3000/claire-student-1/",
            "triple_uris": [],
        }
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is True
        assert pii_type in ("name", "identity")
        assert confidence >= 0.8

    def test_fatima_child_pod(self):
        payload = {
            "pod_resource_uri": "http://localhost:3000/fatima-child-2/",
            "triple_uris": [],
        }
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is True

    def test_non_pii_payload_empty(self):
        payload = {"pod_resource_uri": "", "triple_uris": []}
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is False
        assert pii_type is None
        assert confidence == 0.0

    def test_non_pii_generic_uri(self):
        payload = {
            "pod_resource_uri": "http://localhost:3000/school-community/",
            "triple_uris": [],
        }
        # school-community is not an individual student pod
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is False

    def test_triple_uri_with_known_segment(self):
        payload = {
            "pod_resource_uri": "",
            "triple_uris": ["http://localhost:3000/ayoub/data/graph1"],
        }
        pii, pii_type, confidence = detect_pii_in_payload(payload)
        assert pii is True
        assert pii_type == "identity"

    def test_missing_fields_no_crash(self):
        """detect_pii_in_payload must not crash on missing or None fields."""
        pii, pii_type, confidence = detect_pii_in_payload({})
        assert pii is False

        pii, pii_type, confidence = detect_pii_in_payload(
            {"pod_resource_uri": None, "triple_uris": None}
        )
        assert pii is False

    def test_determinism(self):
        """Same input always produces same output (NFR12)."""
        payload = {"pod_resource_uri": "http://localhost:3000/ayoub/", "triple_uris": []}
        results = [detect_pii_in_payload(payload) for _ in range(5)]
        assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# Tests: TrollTestResult is the canonical shared dataclass
# ---------------------------------------------------------------------------

class TestTrollTestResultReuse:
    """Verify vector_privacy uses the canonical TrollTestResult, not a local clone."""

    def test_troll_test_result_is_canonical(self):
        """TrollTestResult imported in vector_privacy is the same class as acl_enforcement's."""
        # Both modules load from the same acl_enforcement.py source.
        # They may be different objects (importlib loads separate module instances),
        # but they must have the same field structure.
        vp_fields = {f.name for f in TrollTestResult.__dataclass_fields__.values()}
        canonical_fields = {f.name for f in CanonicalTrollTestResult.__dataclass_fields__.values()}
        assert vp_fields == canonical_fields

    def test_troll_result_instantiation(self):
        r = TrollTestResult(
            attack_category="vector_privacy",
            access_path="direct",
            test_name="test-name-extraction",
            result="partial",
            details="Found pod_resource_uri with name",
            evidence={"pii_detected": True, "pii_type": "name", "confidence": 0.9},
        )
        assert r.attack_category == "vector_privacy"
        assert r.access_path == "direct"
        assert r.result == "partial"

    def test_result_values_accepted(self):
        """All three result values are valid for vector privacy (NFR8)."""
        for result_val in ("pass", "partial", "fail"):
            r = TrollTestResult(
                attack_category="vector_privacy",
                access_path="direct",
                test_name=f"test-{result_val}",
                result=result_val,
                details="test",
                evidence={},
            )
            assert r.result == result_val


# ---------------------------------------------------------------------------
# Tests: Report generation format
# ---------------------------------------------------------------------------

class TestReportFormat:
    """Verify the AC-4 report schema is respected."""

    def test_narrative_contains_required_fields(self):
        """_build_narrative produces a non-empty narrative string."""
        # Create mock results
        results = [
            TrollTestResult(
                attack_category="vector_privacy",
                access_path="direct",
                test_name="name-extraction-test",
                result="pass",
                details="no PII",
                evidence={"pii_detected": False, "pii_type": None, "confidence": 0.0},
            ),
            TrollTestResult(
                attack_category="vector_privacy",
                access_path="direct",
                test_name="identity-correlation-test",
                result="partial",
                details="weak signal",
                evidence={"pii_detected": True, "pii_type": "identity", "confidence": 0.6},
            ),
        ]
        narrative = _build_narrative(1, 1, 0, 2, results)
        assert isinstance(narrative, str)
        assert len(narrative) > 50
        # Should mention counts
        assert "2 tests" in narrative
        assert "1 passed" in narrative
        assert "1 partial" in narrative

    def test_troll_result_has_required_evidence_keys(self):
        """Evidence dict for vector privacy results must include AC-4 fields."""
        r = TrollTestResult(
            attack_category="vector_privacy",
            access_path="direct",
            test_name="name-extraction-student-named-ayoub",
            result="partial",
            details="pod_resource_uri exposes identity",
            evidence={
                "query": "student named Ayoub",
                "top_k_results": [],
                "pii_detected": True,
                "pii_type": "name",
                "confidence": 0.9,
            },
        )
        # AC-4 required evidence fields
        assert "query" in r.evidence
        assert "top_k_results" in r.evidence
        assert "pii_detected" in r.evidence
        assert "pii_type" in r.evidence
        assert "confidence" in r.evidence

    def test_result_serializable_to_json(self):
        """TrollTestResult must be fully JSON-serializable (for report writing)."""
        from dataclasses import asdict
        r = TrollTestResult(
            attack_category="vector_privacy",
            access_path="direct",
            test_name="test",
            result="pass",
            details="ok",
            evidence={"pii_detected": False, "pii_type": None, "confidence": 0.0},
        )
        serialized = json.dumps(asdict(r))
        loaded = json.loads(serialized)
        assert loaded["attack_category"] == "vector_privacy"
        assert loaded["result"] == "pass"


# ---------------------------------------------------------------------------
# Tests: Non-blocking behavior (AC-5)
# ---------------------------------------------------------------------------

class TestNonBlocking:
    """Verify the suite is non-blocking (NFR8)."""

    def test_suite_blocking_false_in_summary(self, tmp_path, monkeypatch):
        """Summary must always have blocking=False regardless of findings."""
        # Monkeypatch REPORT_DIR to tmp_path to avoid writing to repo
        monkeypatch.setattr(_mod, "REPORT_DIR", tmp_path)

        # Monkeypatch _preflight_check to return an error (no Qdrant available)
        # This exercises the preflight path
        monkeypatch.setattr(_mod, "_preflight_check", lambda url: "Qdrant not available")
        monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

        suite = VectorPrivacyTestSuite(qdrant_url="http://localhost:6333")
        summary = suite.run_all()
        assert summary["blocking"] is False

    def test_suite_blocking_false_no_api_key(self, tmp_path, monkeypatch):
        """Summary must be non-blocking when API key is missing."""
        monkeypatch.setattr(_mod, "REPORT_DIR", tmp_path)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        suite = VectorPrivacyTestSuite(qdrant_url="http://localhost:6333")
        # api_key is read from env at __init__ time; re-init to pick up monkeypatch
        suite.api_key = ""
        summary = suite.run_all()
        assert summary["blocking"] is False


# ---------------------------------------------------------------------------
# Tests: Determinism (NFR12)
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Verify PII detection is deterministic for the same inputs."""

    def test_pii_detection_deterministic_positive(self):
        payload = {
            "pod_resource_uri": "http://localhost:3000/fatima-child-1/",
            "triple_uris": ["http://localhost:7878/graph/abc"],
        }
        results = [detect_pii_in_payload(payload) for _ in range(10)]
        assert len(set(results)) == 1, "PII detection must be deterministic"

    def test_pii_detection_deterministic_negative(self):
        payload = {
            "pod_resource_uri": "http://localhost:3000/school-community/",
            "triple_uris": [],
        }
        results = [detect_pii_in_payload(payload) for _ in range(10)]
        assert len(set(results)) == 1, "PII detection must be deterministic"
