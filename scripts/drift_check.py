#!/usr/bin/env python3
"""Planning-docs drift check: epics.md <-> sprint-status.yaml.

Reports, without editing anything:
  - keys present in sprint-status.yaml but missing from epics.md (and vice versa)
  - real duplicate story numbers (sub-numbered stories like 4.0.1, 7.11a are NOT duplicates)
  - comments in sprint-status.yaml over 120 chars
  - sprint-status.yaml file size

Story/epic identity is compared by NUMBER (e.g. "7.11a", "8.6.1"), not by key
text or slug, so a capitalized slug (story-3-3-openClaw-...) or a sub-numbered
story (4.0 vs 4.0.1 vs 4.0.2) is handled correctly without an explicit allowlist.

Usage (from repo root, venv active):
    python scripts/drift_check.py

Exit code 0 if no key mismatches, no real duplicates, and no oversized
comments; 1 otherwise. File-size is reported but does not affect exit code
(AC6 has its own threshold check, not this script's job).
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EPICS_MD = REPO_ROOT / "_bmad-output/planning-artifacts/epics.md"
SPRINT_STATUS = REPO_ROOT / "_bmad-output/implementation-artifacts/sprint-status.yaml"

COMMENT_MAX_LEN = 120

STORY_KEY_RE = re.compile(r"^story-(\d+)-(\d+[a-z]?)(?:-(\d+))?-")
EPIC_KEY_RE = re.compile(r"^epic-(\d+)$")
STORY_HEADER_RE = re.compile(r"^###\s+Story\s+(\d+\.\d+[a-z]?(?:\.\d+)?)\s*:")
EPIC_HEADER_RE = re.compile(r"^###?\s+Epic\s+(\d+)\s*:")


def story_id_from_key(key: str) -> str | None:
    m = STORY_KEY_RE.match(key)
    if not m:
        return None
    epic, story, sub = m.groups()
    story_id = f"{epic}.{story}"
    if sub:
        story_id += f".{sub}"
    return story_id


def parse_epics_md(text: str):
    story_ids = set()
    epic_ids = set()
    for line in text.splitlines():
        m = STORY_HEADER_RE.match(line)
        if m:
            story_ids.add(m.group(1))
            continue
        m = EPIC_HEADER_RE.match(line)
        if m:
            epic_ids.add(m.group(1))
    return story_ids, epic_ids


def parse_sprint_status(text: str):
    """Return (story_ids, story_keys_by_id, epic_ids, oversized_comments)."""
    story_keys_by_id = defaultdict(list)
    epic_ids = set()
    oversized_comments = []

    in_dev_status = False
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.rstrip() == "development_status:":
            in_dev_status = True

        # Comment length check applies to the whole file (line 4's
        # top-of-file last_updated comment is the largest offender).
        hash_idx = raw.find("#")
        if hash_idx != -1:
            comment = raw[hash_idx:]
            if len(comment) > COMMENT_MAX_LEN:
                oversized_comments.append((lineno, len(comment), raw[:60].strip()))

        if not in_dev_status:
            continue

        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # top-level entries under development_status are indented exactly 2 spaces
        if not raw.startswith("  ") or raw.startswith("   "):
            continue

        key_part = stripped.split(":", 1)[0].strip()
        if not key_part or " " in key_part:
            continue

        m = EPIC_KEY_RE.match(key_part)
        if m:
            epic_ids.add(m.group(1))
            continue

        story_id = story_id_from_key(key_part)
        if story_id:
            story_keys_by_id[story_id].append(key_part)

    story_ids = set(story_keys_by_id.keys())
    return story_ids, story_keys_by_id, epic_ids, oversized_comments


def main() -> int:
    epics_text = EPICS_MD.read_text()
    sprint_text = SPRINT_STATUS.read_text()

    epics_story_ids, epics_epic_ids = parse_epics_md(epics_text)
    sprint_story_ids, story_keys_by_id, sprint_epic_ids, oversized_comments = parse_sprint_status(sprint_text)

    missing_in_epics = sorted(sprint_story_ids - epics_story_ids, key=_sort_key)
    missing_in_sprint = sorted(epics_story_ids - sprint_story_ids, key=_sort_key)
    epic_missing_in_epics = sorted(sprint_epic_ids - epics_epic_ids, key=int)
    epic_missing_in_sprint = sorted(epics_epic_ids - sprint_epic_ids, key=int)

    real_duplicates = {sid: keys for sid, keys in story_keys_by_id.items() if len(keys) > 1}

    size = SPRINT_STATUS.stat().st_size

    problems = 0

    print("=== Planning-docs drift check ===")
    print(f"epics.md:            {EPICS_MD.relative_to(REPO_ROOT)}")
    print(f"sprint-status.yaml:  {SPRINT_STATUS.relative_to(REPO_ROOT)}")
    print()

    print(f"sprint-status.yaml size: {size:,} bytes ({size / 1024:.1f} KB)")
    print()

    print(f"Story keys — sprint-status.yaml: {len(sprint_story_ids)}, epics.md: {len(epics_story_ids)}")
    if missing_in_epics:
        problems += 1
        print(f"  ❌ in sprint-status.yaml but missing from epics.md ({len(missing_in_epics)}):")
        for sid in missing_in_epics:
            print(f"       {sid}  ({', '.join(story_keys_by_id[sid])})")
    else:
        print("  ✅ every sprint-status.yaml story id has an epics.md entry")

    if missing_in_sprint:
        problems += 1
        print(f"  ❌ in epics.md but missing from sprint-status.yaml ({len(missing_in_sprint)}):")
        for sid in missing_in_sprint:
            print(f"       {sid}")
    else:
        print("  ✅ every epics.md story id has a sprint-status.yaml entry")
    print()

    print(f"Epic keys — sprint-status.yaml: {len(sprint_epic_ids)}, epics.md: {len(epics_epic_ids)}")
    if epic_missing_in_epics:
        problems += 1
        print(f"  ❌ epic keys in sprint-status.yaml missing from epics.md: {epic_missing_in_epics}")
    if epic_missing_in_sprint:
        problems += 1
        print(f"  ❌ epic keys in epics.md missing from sprint-status.yaml: {epic_missing_in_sprint}")
    if not epic_missing_in_epics and not epic_missing_in_sprint:
        print("  ✅ epic keys match both directions")
    print()

    print(f"Duplicate story numbers (excluding legitimate sub-numbered stories): {len(real_duplicates)}")
    if real_duplicates:
        problems += 1
        for sid, keys in sorted(real_duplicates.items(), key=lambda kv: _sort_key(kv[0])):
            print(f"  ❌ {sid}: {keys}")
    else:
        print("  ✅ none")
    print()

    print(f"Comments over {COMMENT_MAX_LEN} chars: {len(oversized_comments)}")
    if oversized_comments:
        problems += 1
        for lineno, length, preview in sorted(oversized_comments, key=lambda t: -t[1]):
            print(f"  ❌ line {lineno}: {length} chars — {preview}...")
    else:
        print("  ✅ none")
    print()

    if problems:
        print(f"RESULT: {problems} problem categor{'y' if problems == 1 else 'ies'} found.")
    else:
        print("RESULT: clean.")

    return 1 if problems else 0


def _sort_key(story_id: str):
    parts = re.split(r"[.]", story_id)
    key = []
    for p in parts:
        m = re.match(r"(\d+)([a-z]?)", p)
        key.append((int(m.group(1)), m.group(2)))
    return key


if __name__ == "__main__":
    sys.exit(main())
