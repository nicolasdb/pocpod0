#!/usr/bin/env python3
"""Seed consent events for Mission Control demo.

Writes consent.grant events for all pods except ayoub to data/consent-events.jsonl.
After seeding:
  - 6 pods → green (consented)
  - ayoub → "no consent" (no events)
  - Dashboard starts in meaningful state for demo

Usage (from repo root, venv active):
    python scripts/seed-consent-events.py [--reset]

--reset  Truncates consent-events.jsonl before seeding (clean slate).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
CONSENT_FILE = DATA_DIR / "consent-events.jsonl"

# Pods that receive pre-consent (school enrollment baseline).
# ayoub is intentionally excluded — his consent is the live demo act.
SEEDED_PODS = [
    "claire",
    "claire-student-1",
    "claire-student-2",
    "fatima",
    "fatima-child-1",
    "fatima-child-2",
    "school-community",
]

SCOPE = "school-enrollment"
GRANTEE_WEBID = "https://school.example.org/profile#school"


def seed(reset: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if reset:
        CONSENT_FILE.write_text("")
        print(f"[seed] Truncated {CONSENT_FILE}")

    seed_ts = datetime.now(timezone.utc).isoformat()
    events_written = 0

    with CONSENT_FILE.open("a") as f:
        for pod in SEEDED_PODS:
            event = {
                "timestamp": seed_ts,
                "event_type": "consent.grant",
                "pod": pod,
                "grantee_webid": GRANTEE_WEBID,
                "scope": SCOPE,
                "source": "seed",
            }
            f.write(json.dumps(event) + "\n")
            events_written += 1
            print(f"[seed] {pod} → consent.grant ({SCOPE})")

    print(f"\n[seed] Done. {events_written} events written to {CONSENT_FILE}")
    print("[seed] Dashboard will show:")
    print(f"  {events_written} pods → active (green)")
    print("  ayoub → no consent (red)")
    print("  Total: 8 pods")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate consent-events.jsonl before seeding",
    )
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
