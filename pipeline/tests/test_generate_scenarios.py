"""Tests for generate_scenarios.py — AC1, AC2, AC3."""

import json
import random
import tempfile
from pathlib import Path

import pytest

from pocpod0_pipeline.generate_scenarios import (
    GENERATORS,
    gen_ayoub,
    gen_claire_student_1,
    gen_claire_student_2,
    gen_fatima_child_nl,
    gen_fatima_child_fr,
    generate_all,
    validate_xapi,
)

POCPOD0 = "https://poc-pod0.edu/vocab/"


@pytest.fixture(scope="module")
def all_statements():
    random.seed(42)
    with tempfile.TemporaryDirectory() as tmp:
        stmts = generate_all(Path(tmp))
    return stmts


@pytest.fixture(scope="module")
def persona_statements():
    random.seed(42)
    return {
        "ayoub":            gen_ayoub(),
        "claire-student-1": gen_claire_student_1(),
        "claire-student-2": gen_claire_student_2(),
        "fatima-child-1":   gen_fatima_child_nl(),
        "fatima-child-2":   gen_fatima_child_fr(),
    }


# ---------------------------------------------------------------------------
# AC1: Scenario dataset generates 300-500 statements
# ---------------------------------------------------------------------------

def test_total_statement_count_in_range(all_statements):
    total = len(all_statements)
    assert 300 <= total <= 500, f"Expected 300-500 statements, got {total}"


# ---------------------------------------------------------------------------
# AC2: All 5 personas have statements
# ---------------------------------------------------------------------------

def test_all_five_personas_present(persona_statements):
    for persona, stmts in persona_statements.items():
        assert len(stmts) > 0, f"No statements for persona {persona}"


def test_each_persona_has_minimum_statements(persona_statements):
    for persona, stmts in persona_statements.items():
        assert len(stmts) >= 10, f"Too few statements for persona {persona}: {len(stmts)}"


# ---------------------------------------------------------------------------
# AC2: Lucas (claire-student-1) has cross-context data — fails school, excels in tutoring
# ---------------------------------------------------------------------------

def test_claire_student_1_has_school_failures(persona_statements):
    stmts = persona_statements["claire-student-1"]
    failing_school = [
        s for s in stmts
        if s.get("verb", {}).get("id", "").endswith("failed")
        and "school-context" in str(s.get("context", {}))
    ]
    assert len(failing_school) >= 1, "Alex should have at least one school math failure"


def test_claire_student_1_has_tutoring_mastery(persona_statements):
    stmts = persona_statements["claire-student-1"]
    mastered = [
        s for s in stmts
        if s.get("verb", {}).get("id") == f"{POCPOD0}verb-mastered"
    ]
    assert len(mastered) >= 1, "Alex should have gemeente tutoring mastery events"


def test_claire_student_1_tutoring_hidden_to_school(persona_statements):
    stmts = persona_statements["claire-student-1"]
    hidden = [
        s for s in stmts
        if "hidden-to-school-teachers" in str(s.get("context", {}))
    ]
    assert len(hidden) >= 1, "Tutoring statements should have hidden-to-school visibility marker"


def test_claire_student_1_has_self_study(persona_statements):
    stmts = persona_statements["claire-student-1"]
    khan = [
        s for s in stmts
        if "khan-academy" in s.get("object", {}).get("id", "").lower()
    ]
    assert len(khan) >= 1, "Alex should have Khan Academy self-study statements"


# ---------------------------------------------------------------------------
# AC2: Fatima children share robotics workshop
# ---------------------------------------------------------------------------

def test_fatima_children_both_attend_robotics(persona_statements):
    robotics_uri = f"{POCPOD0}activity-robotics-workshop"
    for persona in ("fatima-child-1", "fatima-child-2"):
        stmts = persona_statements[persona]
        robotics = [s for s in stmts if s.get("object", {}).get("id") == robotics_uri]
        assert len(robotics) >= 1, f"{persona} should have robotics workshop statements"


# ---------------------------------------------------------------------------
# AC2: Ayoub has transfer event
# ---------------------------------------------------------------------------

def test_ayoub_has_transfer_event(persona_statements):
    stmts = persona_statements["ayoub"]
    transfer = [
        s for s in stmts
        if "transfer" in s.get("object", {}).get("id", "").lower()
    ]
    assert len(transfer) >= 1, "Ayoub should have a school transfer event"


# ---------------------------------------------------------------------------
# AC3: All generated statements are valid xAPI
# ---------------------------------------------------------------------------

def test_all_statements_valid_xapi(all_statements):
    invalid = [s for s in all_statements if not validate_xapi(s)]
    assert len(invalid) == 0, f"{len(invalid)} invalid xAPI statements found"


def test_all_statements_have_timestamp(all_statements):
    missing = [s for s in all_statements if not s.get("timestamp")]
    assert len(missing) == 0, f"{len(missing)} statements missing timestamp"


# ---------------------------------------------------------------------------
# AC1: jsonld profile vocabulary is used (pocpod0 verbs/activities appear)
# ---------------------------------------------------------------------------

def test_pocpod0_verbs_appear(all_statements):
    pocpod0_verbs = [
        s for s in all_statements
        if s.get("verb", {}).get("id", "").startswith(POCPOD0)
    ]
    assert len(pocpod0_verbs) >= 1, "Should use pocpod0 vocabulary verbs"


def test_pocpod0_activities_appear(all_statements):
    pocpod0_acts = [
        s for s in all_statements
        if s.get("object", {}).get("id", "").startswith(POCPOD0)
    ]
    assert len(pocpod0_acts) >= 1, "Should use pocpod0 activity IRIs"


# ---------------------------------------------------------------------------
# Consolidated file written
# ---------------------------------------------------------------------------

def test_consolidated_file_written():
    random.seed(42)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        stmts = generate_all(out)
        consolidated = out / "scenarios-consolidated.json"
        assert consolidated.exists()
        with open(consolidated) as f:
            data = json.load(f)
        assert len(data) == len(stmts)


def test_per_persona_files_written():
    random.seed(42)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        generate_all(out)
        for persona in GENERATORS:
            f = out / f"{persona}.json"
            assert f.exists(), f"Missing persona file: {f.name}"
