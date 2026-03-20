"""Troll load generator.

Generates configurable-volume minimal valid xAPI statements with diverse randomized
WebIDs spanning multiple permission tiers. Simulates a raw school LRS dump.

Output: data/synthetic/troll-load/troll-load.json + troll-load-manifest.json
"""

import argparse
import json
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from pocpod0_pipeline.utils import log_event, synthetic_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADL = "http://adlnet.gov/expapi/verbs/"

ADL_VERBS = [
    {"id": f"{ADL}attended",   "display": {"en-US": "attended"}},
    {"id": f"{ADL}completed",  "display": {"en-US": "completed"}},
    {"id": f"{ADL}passed",     "display": {"en-US": "passed"}},
    {"id": f"{ADL}failed",     "display": {"en-US": "failed"}},
    {"id": f"{ADL}scored",     "display": {"en-US": "scored"}},
    {"id": f"{ADL}attempted",  "display": {"en-US": "attempted"}},
    {"id": f"{ADL}progressed", "display": {"en-US": "progressed"}},
]

ACT_TYPES = [
    "http://adlnet.gov/expapi/activities/course",
    "http://adlnet.gov/expapi/activities/assessment",
    "http://adlnet.gov/expapi/activities/lesson",
    "http://adlnet.gov/expapi/activities/module",
]

RESOURCE_PATTERNS = [
    "https://school-nl.edu/courses/{subject}/{id}",
    "https://school-fr.edu/activités/{subject}/{id}",
    "https://gemeente.brussels/tutoring/{id}",
    "https://lrs.ocl.org/activities/{subject}-{id}",
    "https://khanacademy.org/nl/{subject}",
    "https://openclipart.org/activities/{id}",
]

SUBJECTS = [
    "mathematics", "sciences", "dutch-language", "french-language",
    "history", "geography", "arts", "physical-education", "music",
    "informatics", "biology", "chemistry", "physics",
]

SEMESTER_START = datetime(2025, 9, 1, tzinfo=timezone.utc)
SEMESTER_END   = datetime(2026, 1, 31, tzinfo=timezone.utc)

# Permission tier distribution (must sum to 1.0)
TIER_DISTRIBUTION: List[Tuple[str, float]] = [
    ("student",      0.60),
    ("teacher",      0.15),
    ("parent",       0.10),
    ("admin",        0.10),
    ("unauthorized", 0.05),
]

POD_POOLS = {
    "student":      ["ayoub", "claire-student-1", "claire-student-2",
                     "fatima-child-1", "fatima-child-2",
                     "student-{:04d}"],
    "teacher":      ["claire", "teacher-{:04d}"],
    "parent":       ["fatima", "parent-{:04d}"],
    "admin":        ["admin-{:04d}"],
    "unauthorized": ["unknown-{:04d}", "external-{:04d}"],
}


def _pick_webid(tier: str, rng: random.Random) -> str:
    templates = POD_POOLS[tier]
    tmpl = rng.choice(templates)
    if "{" in tmpl:
        return f"http://localhost:3000/{tmpl.format(rng.randint(1, 500))}/profile/card#me"
    return f"http://localhost:3000/{tmpl}/profile/card#me"


def _rand_ts(rng: random.Random) -> str:
    day = rng.randint(0, (SEMESTER_END - SEMESTER_START).days)
    hour = rng.randint(7, 20)
    minute = rng.choice([0, 15, 30, 45])
    ts = SEMESTER_START + timedelta(days=day, hours=hour, minutes=minute)
    return ts.isoformat().replace("+00:00", "Z")


def _pick_activity(rng: random.Random) -> Tuple[str, str]:
    pattern = rng.choice(RESOURCE_PATTERNS)
    subj = rng.choice(SUBJECTS)
    act_id = pattern.format(subject=subj, id=str(uuid.uuid4())[:8])
    return act_id, subj


def _gen_statement(tier: str, rng: random.Random) -> Dict:
    webid = _pick_webid(tier, rng)
    verb = rng.choice(ADL_VERBS)
    act_id, subj = _pick_activity(rng)
    act_type = rng.choice(ACT_TYPES)

    stmt: Dict = {
        "id": str(uuid.uuid4()),
        "actor": {
            "objectType": "Agent",
            "account": {"homePage": "http://localhost:3000", "name": webid},
        },
        "verb": verb,
        "object": {
            "objectType": "Activity",
            "id": act_id,
            "definition": {
                "name": {"en-US": subj.replace("-", " ").title()},
                "type": act_type,
            },
        },
        "timestamp": _rand_ts(rng),
    }

    # Some statements have result/score (~40%)
    if rng.random() < 0.40:
        stmt["result"] = {
            "score": {"scaled": round(rng.uniform(0.0, 1.0), 2)},
            "success": rng.choice([True, False]),
            "completion": rng.choice([True, False]),
        }

    # Some with context extensions (~25%)
    if rng.random() < 0.25:
        stmt["context"] = {
            "extensions": {
                "https://poc-pod0.edu/vocab/ext-language-context": rng.choice(["NL", "FR", "EN"]),
            }
        }

    return stmt


def _weighted_tier(rng: random.Random) -> str:
    roll = rng.random()
    cumulative = 0.0
    for tier, weight in TIER_DISTRIBUTION:
        cumulative += weight
        if roll < cumulative:
            return tier
    return TIER_DISTRIBUTION[-1][0]


def generate_troll_load(count: int, output_dir: Path, seed: int = 0) -> Path:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    statements: List[Dict] = []
    tier_counter: Counter = Counter()

    for _ in range(count):
        tier = _weighted_tier(rng)
        tier_counter[tier] += 1
        statements.append(_gen_statement(tier, rng))

    # Validate all statements
    invalid = [s for s in statements if not (
        s.get("actor") and s.get("verb", {}).get("id") and s.get("object", {}).get("id")
    )]
    if invalid:
        log_event("generate.troll.validation.warning", "WARN",
                  {"invalid_count": len(invalid)})

    out_file = output_dir / "troll-load.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(statements, f, indent=2, ensure_ascii=False)

    # Manifest
    verb_counter: Counter = Counter(
        s["verb"]["id"].split("/")[-1] for s in statements
    )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_statements": count,
        "webid_tier_distribution": {
            tier: {
                "count": tier_counter[tier],
                "pct": round(tier_counter[tier] / count * 100, 1),
            }
            for tier, _ in TIER_DISTRIBUTION
        },
        "verb_distribution": {v: c for v, c in verb_counter.most_common()},
        "invalid_count": len(invalid),
    }
    manifest_file = output_dir / "troll-load-manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log_event("generate.troll.complete", "INFO",
              {"count": count, "file": str(out_file), "manifest": str(manifest_file)})
    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Troll load xAPI statements")
    parser.add_argument("--count", type=int, default=5000,
                        help="Number of statements to generate (default 5000, max 50000)")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    args = parser.parse_args()

    count = min(max(1, args.count), 50_000)
    out = synthetic_dir() / "troll-load"
    generate_troll_load(count, out, seed=args.seed)
    print(f"Generated {count} troll statements → {out}")


if __name__ == "__main__":
    main()
