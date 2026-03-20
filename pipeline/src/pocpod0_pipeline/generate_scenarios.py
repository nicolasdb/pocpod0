"""Narrative-rich scenario xAPI dataset generator.

Generates ~300-500 xAPI statements for 5 learner personas covering all demo journeys.
Uses pocpod0-xapi-profile.jsonld as vocabulary/persona reference.

Output: data/synthetic/scenarios/{persona}.json + scenarios-consolidated.json
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from pocpod0_pipeline.utils import log_event, schemas_dir, synthetic_dir


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADL = "http://adlnet.gov/expapi/verbs/"
POCPOD0 = "https://poc-pod0.edu/vocab/"
ACT = "http://adlnet.gov/expapi/activities/"

VERBS = {
    "attempted":  {"id": f"{ADL}attempted",  "display": {"en-US": "attempted"}},
    "completed":  {"id": f"{ADL}completed",  "display": {"en-US": "completed"}},
    "passed":     {"id": f"{ADL}passed",     "display": {"en-US": "passed"}},
    "failed":     {"id": f"{ADL}failed",     "display": {"en-US": "failed"}},
    "scored":     {"id": f"{ADL}scored",     "display": {"en-US": "scored"}},
    "attended":   {"id": f"{ADL}attended",   "display": {"en-US": "attended"}},
    "progressed": {"id": f"{ADL}progressed", "display": {"en-US": "progressed"}},
    "mastered":   {"id": f"{POCPOD0}verb-mastered",      "display": {"en-US": "mastered"}},
    "struggled":  {"id": f"{POCPOD0}verb-struggled-with","display": {"en-US": "struggled with"}},
    "sought-help":{"id": f"{POCPOD0}verb-sought-help",  "display": {"en-US": "sought help for"}},
    "demonstrated":{"id":f"{POCPOD0}verb-demonstrated",  "display": {"en-US": "demonstrated"}},
}

# Semester window: September – January
SEMESTER_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
SEMESTER_END   = datetime(2026, 1, 31, tzinfo=timezone.utc)
SEMESTER_DAYS  = (SEMESTER_END - SEMESTER_START).days


def _rand_ts(
    start: datetime = SEMESTER_START,
    end: datetime = SEMESTER_END,
    hour_min: int = 8,
    hour_max: int = 18,
) -> str:
    day_offset = random.randint(0, (end - start).days)
    hour = random.randint(hour_min, hour_max)
    minute = random.choice([0, 15, 30, 45])
    ts = start + timedelta(days=day_offset, hours=hour, minutes=minute)
    return ts.isoformat().replace("+00:00", "Z")


def _stmt(
    actor_webid: str,
    actor_name: str,
    verb_key: str,
    obj_id: str,
    obj_name: str,
    obj_type: str,
    result: Dict = None,
    context_extensions: Dict = None,
    timestamp: str = None,
    pod_name: str = None,
) -> Dict[str, Any]:
    stmt: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "actor": {
            "objectType": "Agent",
            "account": {"homePage": "http://localhost:3000", "name": actor_webid},
            "name": actor_name,
        },
        "verb": VERBS[verb_key],
        "object": {
            "objectType": "Activity",
            "id": obj_id,
            "definition": {
                "name": {"en-US": obj_name},
                "type": obj_type,
            },
        },
        "timestamp": timestamp or _rand_ts(),
    }
    if result:
        stmt["result"] = result
    ctx: Dict[str, Any] = {"platform": "pocpod0"}
    if context_extensions:
        ctx["extensions"] = context_extensions
    stmt["context"] = ctx
    if pod_name:
        stmt["_pocpod0_pod"] = pod_name  # internal routing hint, stripped before validation
    return stmt


def _school_math_fail(actor_webid: str, actor_name: str, pod: str, week: int) -> List[Dict]:
    """School math assessments: struggling student fails."""
    day = week * 7 + random.randint(0, 4)
    ts = (SEMESTER_START + timedelta(days=day, hours=random.randint(8, 12))).isoformat().replace("+00:00", "Z")
    score = round(random.uniform(0.35, 0.55), 2)
    return [
        _stmt(actor_webid, actor_name, "attempted",
              f"{POCPOD0}activity-math-assessment-fractions",
              "Mathematics Assessment: Fractions",
              f"{ACT}assessment",
              result={"score": {"scaled": score}, "success": False, "completion": False},
              context_extensions={f"{POCPOD0}ext-emotional-state": "frustrated",
                                  f"{POCPOD0}ext-visibility": "school-context"},
              timestamp=ts, pod_name=pod),
        _stmt(actor_webid, actor_name, "failed",
              f"{POCPOD0}activity-math-assessment-fractions",
              "Mathematics Assessment: Fractions",
              f"{ACT}assessment",
              result={"score": {"scaled": round(random.uniform(0.35, 0.50), 2)}, "success": False},
              context_extensions={f"{POCPOD0}ext-visibility": "school-context"},
              timestamp=(SEMESTER_START + timedelta(days=day + 1, hours=9)).isoformat().replace("+00:00", "Z"),
              pod_name=pod),
    ]


def _tutoring_mastery(actor_webid: str, actor_name: str, pod: str, week: int) -> List[Dict]:
    """Gemeente tutoring: hidden-to-school mastery events."""
    day = week * 7 + 2  # Wednesday
    ts_attend = (SEMESTER_START + timedelta(days=day, hours=16, minutes=30)).isoformat().replace("+00:00", "Z")
    ts_master = (SEMESTER_START + timedelta(days=day, hours=17, minutes=30)).isoformat().replace("+00:00", "Z")
    return [
        _stmt(actor_webid, actor_name, "attended",
              f"{POCPOD0}activity-gemeente-tutoring",
              "Municipality-Funded Tutoring Session",
              f"{POCPOD0}activity-gemeente-tutoring",
              context_extensions={f"{POCPOD0}ext-visibility": "hidden-to-school-teachers",
                                  f"{POCPOD0}ext-funding": "gemeente-stem-program"},
              timestamp=ts_attend, pod_name=pod),
        _stmt(actor_webid, actor_name, "mastered",
              f"{POCPOD0}activity-gemeente-tutoring",
              "Geometric Visualization: Fractions Mastery",
              f"{POCPOD0}activity-gemeente-tutoring",
              result={"score": {"scaled": round(random.uniform(0.82, 0.96), 2)}, "success": True},
              context_extensions={f"{POCPOD0}ext-emotional-state": "confident",
                                  f"{POCPOD0}ext-visibility": "hidden-to-school-teachers"},
              timestamp=ts_master, pod_name=pod),
    ]


# ---------------------------------------------------------------------------
# Persona generators
# ---------------------------------------------------------------------------

def gen_ayoub() -> List[Dict]:
    """Ayoub: complete K-12 history — governance/transfer/deletion demo."""
    pod = "ayoub"
    webid = f"http://localhost:3000/{pod}/profile/card#me"
    name = "Ayoub"
    stmts: List[Dict] = []

    subjects = ["mathematics", "sciences", "dutch-language", "history", "geography", "physical-education"]
    for week in range(0, 22, 1):
        for subj in random.sample(subjects, k=random.randint(2, 4)):
            verb = random.choice(["attempted", "completed", "progressed", "scored"])
            score = round(random.uniform(0.55, 0.90), 2)
            day = week * 7 + random.randint(0, 4)
            ts = (SEMESTER_START + timedelta(days=day, hours=random.randint(8, 16))).isoformat().replace("+00:00", "Z")
            stmts.append(_stmt(
                webid, name, verb,
                f"{POCPOD0}activity-course-{subj}",
                f"Course: {subj.replace('-', ' ').title()}",
                f"{ACT}course",
                result={"score": {"scaled": score}, "success": score >= 0.5},
                timestamp=ts, pod_name=pod,
            ))

    # Robotics workshop (weekly Wednesday)
    for week in range(0, 18):
        day = week * 7 + 2
        ts = (SEMESTER_START + timedelta(days=day, hours=17)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "attended",
            f"{POCPOD0}activity-robotics-workshop",
            "Robotics Workshop (STEM)",
            f"{POCPOD0}activity-robotics-workshop",
            context_extensions={f"{POCPOD0}ext-language-context": "mixed-nl-fr-en"},
            timestamp=ts, pod_name=pod,
        ))
        if week % 3 == 0:
            stmts.append(_stmt(
                webid, name, "demonstrated",
                f"{POCPOD0}activity-robotics-workshop",
                "Applied Math: Robotics Challenge",
                f"{POCPOD0}activity-robotics-workshop",
                result={"score": {"scaled": round(random.uniform(0.70, 0.95), 2)}, "success": True},
                timestamp=(SEMESTER_START + timedelta(days=day, hours=18)).isoformat().replace("+00:00", "Z"),
                pod_name=pod,
            ))

    # Khan Academy self-study
    for week in range(0, 20, 1):
        day = week * 7 + random.randint(0, 6)
        ts = (SEMESTER_START + timedelta(days=day, hours=20, minutes=30)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "progressed",
            f"{POCPOD0}activity-khan-academy-session",
            "Khan Academy Self-Study",
            f"{ACT}lesson",
            timestamp=ts, pod_name=pod,
        ))

    # Transfer event (FR -> NL school, mid-semester)
    transfer_day = 60
    stmts.append(_stmt(
        webid, name, "completed",
        f"{POCPOD0}activity-school-transfer-nl",
        "School Transfer: FR to NL institution",
        f"{POCPOD0}activity-school-transfer",
        context_extensions={f"{POCPOD0}ext-transfer-from": "pocpod0:inst-ecole-liege-francophone",
                             f"{POCPOD0}ext-transfer-to": "pocpod0:inst-nl-school-brussels-1",
                             f"{POCPOD0}ext-consent-type": "parental-opt-in"},
        timestamp=(SEMESTER_START + timedelta(days=transfer_day, hours=9)).isoformat().replace("+00:00", "Z"),
        pod_name=pod,
    ))

    return stmts


def gen_claire_student_1() -> List[Dict]:
    """Alex (Lucas in story): struggling at school, excelling in gemeente tutoring."""
    pod = "claire-student-1"
    webid = f"http://localhost:3000/{pod}/profile/card#me"
    name = "Alex"
    stmts: List[Dict] = []

    # 6 weeks of school math failure + tutoring mastery (the cross-context pattern)
    for week in range(1, 7):
        stmts.extend(_school_math_fail(webid, name, pod, week))
        stmts.extend(_tutoring_mastery(webid, name, pod, week))

    # Khan Academy remediation (evening self-study)
    for week in range(1, 7):
        day = week * 7 + random.randint(4, 6)
        ts = (SEMESTER_START + timedelta(days=day, hours=20, minutes=random.choice([0, 30]))).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "progressed",
            f"{POCPOD0}activity-khan-academy-session",
            "Khan Academy: Fraction Remediation",
            f"{ACT}lesson",
            context_extensions={f"{POCPOD0}ext-help-seeking-behavior": "video-replay"},
            timestamp=ts, pod_name=pod,
        ))

    # Help-seeking at school (showing awareness)
    for week in range(2, 5):
        day = week * 7 + 3
        ts = (SEMESTER_START + timedelta(days=day, hours=13)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "sought-help",
            f"{POCPOD0}activity-math-assessment-fractions",
            "Mathematics: Fractions",
            f"{ACT}assessment",
            context_extensions={f"{POCPOD0}ext-help-seeking-behavior": "teacher-asked",
                                 f"{POCPOD0}ext-visibility": "school-context"},
            timestamp=ts, pod_name=pod,
        ))

    return stmts


def gen_claire_student_2() -> List[Dict]:
    """Jordan (Emma in story): average student, standard progression."""
    pod = "claire-student-2"
    webid = f"http://localhost:3000/{pod}/profile/card#me"
    name = "Jordan"
    stmts: List[Dict] = []

    subjects = ["mathematics", "dutch-language", "sciences", "arts", "history", "music"]
    for week in range(0, 18, 1):
        for subj in random.sample(subjects, k=random.randint(2, 3)):
            score = round(random.uniform(0.55, 0.78), 2)
            day = week * 7 + random.randint(0, 4)
            ts = (SEMESTER_START + timedelta(days=day, hours=random.randint(8, 15))).isoformat().replace("+00:00", "Z")
            verb = random.choice(["attempted", "completed", "scored"])
            stmts.append(_stmt(
                webid, name, verb,
                f"{POCPOD0}activity-course-{subj}",
                f"Course: {subj.replace('-', ' ').title()}",
                f"{ACT}course",
                result={"score": {"scaled": score}, "success": score >= 0.5},
                timestamp=ts, pod_name=pod,
            ))

    # Some tutoring (moderate)
    for week in range(3, 9, 2):
        day = week * 7 + 2
        ts = (SEMESTER_START + timedelta(days=day, hours=16, minutes=30)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "attended",
            f"{POCPOD0}activity-gemeente-tutoring",
            "Municipality-Funded Tutoring Session",
            f"{POCPOD0}activity-gemeente-tutoring",
            context_extensions={f"{POCPOD0}ext-visibility": "hidden-to-school-teachers"},
            timestamp=ts, pod_name=pod,
        ))

    # Some Khan Academy
    for week in range(0, 16, 3):
        day = week * 7 + random.randint(4, 6)
        ts = (SEMESTER_START + timedelta(days=day, hours=21)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "progressed",
            f"{POCPOD0}activity-khan-academy-session",
            "Khan Academy Self-Study",
            f"{ACT}lesson",
            timestamp=ts, pod_name=pod,
        ))

    return stmts


def gen_fatima_child_nl() -> List[Dict]:
    """Sam (Youssef in story): NL school, language arts + STEM, robotics workshop."""
    pod = "fatima-child-1"
    webid = f"http://localhost:3000/{pod}/profile/card#me"
    name = "Sam"
    stmts: List[Dict] = []

    subjects = ["nl-language-arts", "mathematics", "science", "music"]
    for week in range(0, 18, 1):
        for subj in random.sample(subjects, k=random.randint(1, 3)):
            score = round(random.uniform(0.60, 0.88), 2)
            day = week * 7 + random.randint(0, 4)
            ts = (SEMESTER_START + timedelta(days=day, hours=random.randint(8, 13))).isoformat().replace("+00:00", "Z")
            verb = random.choice(["attended", "completed", "scored"])
            stmts.append(_stmt(
                webid, name, verb,
                f"{POCPOD0}activity-course-{subj}-nl",
                f"NL School Course: {subj.replace('-', ' ').title()}",
                f"{ACT}course",
                result={"score": {"scaled": score}, "success": score >= 0.5},
                context_extensions={f"{POCPOD0}ext-language-context": "NL"},
                timestamp=ts, pod_name=pod,
            ))

    # Robotics (shared with sibling on Wednesdays)
    for week in range(0, 18):
        day = week * 7 + 2
        ts = (SEMESTER_START + timedelta(days=day, hours=17)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "attended",
            f"{POCPOD0}activity-robotics-workshop",
            "Robotics Workshop (STEM)",
            f"{POCPOD0}activity-robotics-workshop",
            context_extensions={f"{POCPOD0}ext-language-context": "mixed-nl-fr-en",
                                 f"{POCPOD0}ext-sibling-present": "true"},
            timestamp=ts, pod_name=pod,
        ))

    return stmts


def gen_fatima_child_fr() -> List[Dict]:
    """Léa (Nour in story): FR school, similar subjects, different providers."""
    pod = "fatima-child-2"
    webid = f"http://localhost:3000/{pod}/profile/card#me"
    name = "Léa"
    stmts: List[Dict] = []

    subjects = ["fr-language-arts", "mathematics", "sciences-naturelles", "art-plastique"]
    for week in range(0, 18, 1):
        for subj in random.sample(subjects, k=random.randint(1, 3)):
            score = round(random.uniform(0.58, 0.85), 2)
            day = week * 7 + random.randint(0, 4)
            ts = (SEMESTER_START + timedelta(days=day, hours=random.randint(8, 14))).isoformat().replace("+00:00", "Z")
            verb = random.choice(["attended", "completed", "scored"])
            stmts.append(_stmt(
                webid, name, verb,
                f"{POCPOD0}activity-course-{subj}-fr",
                f"FR School Course: {subj.replace('-', ' ').title()}",
                f"{ACT}course",
                result={"score": {"scaled": score}, "success": score >= 0.5},
                context_extensions={f"{POCPOD0}ext-language-context": "FR"},
                timestamp=ts, pod_name=pod,
            ))

    # Robotics (shared sibling session on Wednesdays)
    for week in range(0, 16):
        day = week * 7 + 2
        ts = (SEMESTER_START + timedelta(days=day, hours=17, minutes=10)).isoformat().replace("+00:00", "Z")
        stmts.append(_stmt(
            webid, name, "attended",
            f"{POCPOD0}activity-robotics-workshop",
            "Robotics Workshop (STEM)",
            f"{POCPOD0}activity-robotics-workshop",
            context_extensions={f"{POCPOD0}ext-language-context": "mixed-nl-fr-en",
                                 f"{POCPOD0}ext-sibling-present": "true"},
            timestamp=ts, pod_name=pod,
        ))

    return stmts


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_xapi(stmt: Dict) -> bool:
    """Minimal xAPI validation: actor + verb + object mandatory."""
    actor = stmt.get("actor", {})
    verb = stmt.get("verb", {})
    obj = stmt.get("object", {})
    return (
        bool(actor.get("account") or actor.get("mbox") or actor.get("openid") or actor.get("name"))
        and bool(verb.get("id"))
        and bool(obj.get("id"))
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GENERATORS = {
    "ayoub": gen_ayoub,
    "claire-student-1": gen_claire_student_1,
    "claire-student-2": gen_claire_student_2,
    "fatima-child-1": gen_fatima_child_nl,
    "fatima-child-2": gen_fatima_child_fr,
}


def generate_all(output_dir: Path) -> List[Dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_stmts: List[Dict] = []

    for persona, gen_fn in GENERATORS.items():
        stmts = gen_fn()
        invalid = [s for s in stmts if not validate_xapi(s)]
        if invalid:
            log_event("generate.validation.warning", "WARN",
                      {"persona": persona, "invalid_count": len(invalid)})

        per_file = output_dir / f"{persona}.json"
        with open(per_file, "w", encoding="utf-8") as f:
            json.dump(stmts, f, indent=2, ensure_ascii=False)

        log_event("generate.persona.complete", "INFO",
                  {"persona": persona, "count": len(stmts), "file": str(per_file)})
        all_stmts.extend(stmts)

    consolidated = output_dir / "scenarios-consolidated.json"
    with open(consolidated, "w", encoding="utf-8") as f:
        json.dump(all_stmts, f, indent=2, ensure_ascii=False)

    log_event("generate.scenarios.complete", "INFO",
              {"total": len(all_stmts), "file": str(consolidated)})
    return all_stmts


def main() -> None:
    random.seed(42)
    out = synthetic_dir() / "scenarios"
    stmts = generate_all(out)
    print(f"Generated {len(stmts)} scenario statements → {out}")


if __name__ == "__main__":
    main()
