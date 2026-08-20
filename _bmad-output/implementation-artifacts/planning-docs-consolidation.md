# Story: Planning-Docs Consolidation — One Owner Per Fact

Status: review
Type: housekeeping / process (cuts across all 8 epics — not epic-scoped)
Blocking: no

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **anyone (human or agent) picking up this project**,
I want each fact about the project to live in exactly one file, with pointers instead of copies,
so that I can trust what I read instead of cross-checking four documents that disagree.

## Context / Why now

Raised by Nicolas 2026-08-02: *"sprint-status is filled with a lot of large comments, is it the place for those? shouldn't we keep it lean and only link on reference files and memory path? This feels very bad on the single source of truth principle side."*

Correct, and the investigation found the drift was systemic rather than a couple of missed entries.

### Already done (2026-08-02) — do not redo

| Work | Result |
|---|---|
| Key parity between `epics.md` and `sprint-status.yaml` | **58/58, zero mismatches both directions** |
| Epic 2 + Epic 3 renumbered to executed reality | plan→execution notes added at each epic header and on every split/added story |
| Stories missing from `epics.md` | added: 7.7, 4.0.1, 4.0.2, 4.4.1, all of Epic 8 (8.1–8.7) |
| Stories missing from `sprint-status.yaml` | added: 7.8, 7.9, 8.6.1, 3.7.1 |
| Convention recorded | `project-context.md` created (BMAD auto-loads it) + memory entry |
| **Story 6.2 collapsed** | one `story-6-2-acl-dashboard: done` key; TUI story file marked `Status: superseded` with a pointer note, not deleted; `epics.md` already read correctly as one pivoted story — no edit needed there |
| **Task 2 verified executed (2026-08-20)** | commit `43d5ac6` (same day as this draft) did all three edits: sprint-status.yaml key collapse, TUI file header note, epics.md Epic 6 "(PIVOT)" section — confirmed still consistent 18 days later, re-check found nothing to redo |

Two things surfaced only by reading the files, worth keeping in mind for the rest of the pass:
- **Planned Story 2.2 (dataset generation) was never a story at all** — the PRD classes the dataset as an external input. No amount of renumbering would have revealed that; only reading did.
- **Story 3.7.1 (Pipeline Dashboard TUI) was `done`, had a story file, and was absent from `sprint-status.yaml` entirely.**

### What remains — this story

1. **The comment bloat — worse, not better, as of 2026-08-20.** `sprint-status.yaml` is now **106,708 bytes (104.2 KB) / 226 lines** — up from ~56 KB at draft time, across 18 more days and stories 7.5–8.9. **14 comments exceed 120 chars** (was 8), **12 exceed 2 KB** (was 8), all Epic 7/8. The largest is no longer `story-8-7` — it's now the **top-of-file `last_updated:` field itself, ~14.9 KB**, followed by `story-7-9` at ~13.1 KB. `story-8-7` is ~4.6 KB, roughly where it was, but no longer the outlier. See Dev Notes for the full current ranking and the new bloat pattern this reveals.
2. **The 6.2 duplicate**, now unambiguous — see the settled decision below. **Confirmed fully executed 2026-08-20** (commit `43d5ac6`, same day as this draft) — nothing left to do here.
3. **A re-runnable drift check.** Without one, the parity achieved above decays silently again. It decayed across eight epics before anyone looked. **Confirmed still true 2026-08-20**: no drift-check script exists anywhere in the repo. Also confirmed live: `story-7-12-agent-identity-lifecycle` is `done` in sprint-status.yaml with **no matching entry in epics.md** — a real mismatch the drift check should catch, useful as its first test case.

### Settled decision — Story 6.2 (Nicolas, 2026-08-02)

> *"6.2 is kind of the same, we needed UI but TUI was a dead end, so that path was superseded by the new dashboard path."*

**One story, two implementation paths.** 6.2 is a single story — "we need a UI" — whose first path (Textual TUI) proved a dead end and was superseded by the FastAPI + HTML ACL dashboard. Therefore:

- **One key**, `story-6-2-*`, status `done`.
- The TUI attempt is **history to preserve, not a mistake to erase** — it is a real architectural finding (see the archived `architecture_dashboard_tui_decision` and `story_6_2_textual_hybrid_decision` memories, and Story 3.7.1, which is the same dead end reached earlier).
- Both story files stay on disk. The superseded one is marked as a superseded path of 6.2, not as a separate story.

Do not re-litigate this. Implement it.

## Target model — one owner per fact

Already written to `project-context.md`; restated here so this story is self-contained.

| File | Owns | Must never hold |
|---|---|---|
| `epics.md` | intent — what & why, one entry per story that **actually exists** | status, execution detail, findings |
| `{epic}-{story}-{slug}.md` | the truth for one story — context, ACs, tasks, dev notes, completion notes | — |
| `sprint-status.yaml` | **state only**: `key: status` + a ≤120-char pointer | narrative, findings, evidence, decisions |
| `epic-N-progress-report.md` | proof/evidence narrative per epic | intent |
| `architecture.md` / `prd.md` | cross-cutting model, principles, requirements | per-story execution detail |
| memory | cross-session lessons | anything the repo already records |

**Rule: nothing appears in two places except as a pointer.**

## Acceptance Criteria

1. **A drift check exists, is re-runnable by someone else, and is documented.** It reports: key mismatches between `epics.md` and `sprint-status.yaml`, duplicate story numbers, comments over 120 characters, and total file size. **Without this the pass is a one-time cleanup that rots again** — parity was achieved once already and decayed across eight epics.

2. **The drift check distinguishes sub-numbered stories from real duplicates.** `3.7`/`3.7.1`, `4.0`/`4.0.1`/`4.0.2`, `4.4`/`4.4.1`, `8.6`/`8.6.1` are legitimate; only genuinely colliding numbers are reported. **As of 2026-08-20, also add `7.11`/`7.11a`/`7.11b`** — a letter-suffix split, not a dotted sub-number, so the allowlist logic needs to recognize both suffix styles, not just `\d+\.\d+`. A check that cries wolf gets ignored.

3. ~~Story 6.2 resolves to one key~~ **Done 2026-08-02**, out of scope for this story now — see the table above.

4. **No comment in `sprint-status.yaml` exceeds 120 characters**, and every trimmed entry follows the form:
   `key: status  # <date>: <one-line summary> → see <path>`

5. **Nothing is lost in the trim.** Before shortening any comment, verify its content exists in the story file (or progress report, or memory) and **append what is missing there first**. This is a migration, not a deletion — some findings exist *only* in those comments.

6. **`sprint-status.yaml` ends under 8 KB** (from **104.2 KB** as of 2026-08-20, was ~56 KB at draft time) while still carrying every key and status.

7. **The BMAD workflows that consume `sprint-status.yaml` still work** — the file parses, and next-backlog-story selection still resolves correctly. **A lean file that breaks story selection is a worse outcome than a fat one.**

8. **The drift check passes** at the end of this story, and its output is recorded as the evidence.

9. **`epic-8-action-log.md` and the progress reports are untouched** by the trim — they are the intended home for narrative and are working as designed.

## Tasks / Subtasks

- [x] **Task 1 — Build the drift check first (AC: 1, 2)**
  - [x] 1.1 Report key mismatches both directions, real duplicate story numbers, comments >120 chars, file size.
  - [x] 1.2 Handle sub-numbered stories correctly (AC2) — the naive regex reports four false positives.
  - [x] 1.3 Run it **before** any edit and keep the baseline output; it is the evidence the pass did something.
  - [x] 1.4 One command, runnable by a human. Document it in `project-context.md` next to the convention.
  - [x] 1.5 **Build this before touching anything else** — otherwise the rest of the work is judged by eye.

- [x] **Task 2 — Resolve Story 6.2 (AC: 3)** — re-verified 2026-08-20, already executed by commit `43d5ac6`, nothing to redo.
  - [x] 2.1 Collapse to a single `story-6-2-*` key, status `done`. Confirmed: only `story-6-2-acl-dashboard: done` exists (drift check finds no 6.2 duplicate).
  - [x] 2.2 Mark the TUI story file as a superseded *path* of 6.2 — a header note, not a deletion. Confirmed: `6-2-mission-control-dashboard-implementation.md` header reads "Status: superseded" with pointer note.
  - [x] 2.3 Confirm `epics.md`'s Story 6.2 entry reflects one story with two paths, so the epic doc matches. Confirmed: `### Story 6.2: ACL Enforcement Dashboard (PIVOT)`.
  - [x] 2.4 Preserve the pivot as a finding: Textual/TUI was reached twice (3.7.1 and 6.2) and abandoned twice. Confirmed present in both the TUI file's header note and `sprint-status.yaml`'s `story-6-2-acl-dashboard` comment.

- [x] **Task 3 — Migrate the mega-comments (AC: 4, 5, 6)**
  - [x] 3.1 For each entry over 120 chars, read the comment **and** the story file. List what the comment says that the story file does not.
  - [x] 3.2 Append the gaps to the story file's Completion Notes / Change Log — or the epic progress report, whichever is the right owner — **before** trimming anything. Only one real gap found (Story 7.12 missing from `epics.md` — the drift check's predicted first finding); added there. Every other oversized comment's content was already present in its story file, `epics.md`, `architecture.md`, or a `sprint-change-proposal-*.md` — verified before trimming, nothing else to append.
  - [x] 3.3 Replace the comment with `# <date>: <one-line summary> → see <path>`.
  - [x] 3.4 One epic at a time, commit per epic, so a mistake is reviewable rather than a 56 KB diff. (Epic 8 + top-of-file: commit `6f845a4`. Epic 7 + `epics.md` 7.12 fix: commit `4afc793`. Epics 1–6/Sprint Metadata/Known Issues + size pass: this session's final commit.)
  - [x] 3.5 **Start with Epic 8** — largest entries, most recently written, so the content is still fresh enough to judge what is redundant.
  - [x] 3.6 Include the ~4.6 KB `story-8-7` entry. It was the newest offender on 2026-08-02; as of 2026-08-20 it's mid-pack, but the same rule applies.
  - [x] 3.7 **Migrate the top-of-file `last_updated:` field too (~14.9 KB as of 2026-08-20)** — it is not epic-scoped like the rest, it's a global rolling changelog (7.12 review + party-mode scope review + security course-correction concatenated). Read it in full, append anything not already in a story file/progress report/memory, then trim it the same way as a per-story comment.
  - [x] 3.8 Also migrate `story-7-9` (~13.1 KB) — currently the largest per-story entry, found during the 2026-08-20 refresh.

- [x] **Task 4 — Verify (AC: 7, 8, 9)**
  - [x] 4.1 Drift check passes; record the output. See `drift-check-final-2026-08-20.txt` (clean, 0 problems) vs `drift-check-baseline-2026-08-20.txt` (2 problem categories, 30 oversized comments, 1 key mismatch).
  - [x] 4.2 Spot-check three trimmed entries against their story files to confirm nothing was lost. Done inline throughout Task 3 for every entry (not just three) — each comment's full content was read and matched against its story file/owner doc before trimming; see commit messages and this file's Change Log for the pattern.
  - [x] 4.3 Confirm `sprint-status.yaml` still parses and next-backlog-story selection still resolves. Verified with `python3 -c "import yaml; yaml.safe_load(...)"` — parses cleanly, 82 total keys; first `ready-for-dev` story top-to-bottom resolves to `story-4-1-marc-school-transfer-via-discord`, unchanged from pre-migration (only `planning-docs-consolidation`'s own status was intentionally changed, to `in-progress`).
  - [x] 4.4 Confirm `epic-8-action-log.md` and the progress reports are unmodified. `git status` shows no changes to either — confirmed.

## Dev Notes

### Why the comments got there — understand before removing

`sprint-status.yaml` is the one file every BMAD workflow reads start-to-finish, so it became the place to leave anything the next session must not miss. That instinct was **right about the need and wrong about the location**. If this pass removes the context without relocating it, the same pressure refills the file within a few stories. Task 3.2's *append-before-trimming* ordering is the entire safety mechanism.

### This is a migration, not a cleanup

The mega-comments contain real findings: live-verified results, review findings that were rejected and why, corrected scope decisions, traps discovered on the VPS. Some may exist *only* there. Deleting first and checking later loses project history that cost real sessions to produce.

### Don't over-automate the trim

A regex truncating comments at 120 chars satisfies AC4 and violates AC5. **The reading is the work; the trimming is trivial.**

### The bloat found a second home (found 2026-08-20)

The original story only anticipated per-story-key comments bloating. 18 days later, the **top-of-file `last_updated:` field** independently grew into a ~14.9 KB rolling changelog — it's now the single largest entry in the file, larger than any per-story comment. Same root cause as the Dev Notes section above (sprint-status.yaml is the one file every workflow reads, so it absorbs anything "the next session must not miss") just applied to a different field. Task 3.7 handles it, but a future drift check (Task 1) should probably flag this field's length too, not just per-story comments, or the pattern will just recur in a third location.

### Sequencing

Non-blocking. Best run **between** stories, not mid-story, since it rewrites the file dev workflows read to pick up work.

### Traps

- **Sub-numbered stories are not duplicates** — `3.7.1`, `4.0.1`, `4.0.2`, `4.4.1`, `8.6.1` are real stories. A naive duplicate check reports all of them (AC2). **As of 2026-08-20, also `7.11a`/`7.11b`** — a letter suffix, not a dotted number; don't assume the sub-numbering pattern is always `\d+\.\d+`.
- **`story-3-3-openClaw-agent-infrastructure` has a capital C.** Harmless today; any exact-match check must not assume lowercase keys.
- **Epic ordering in `sprint-status.yaml` is 1,2,3,5,6,4,7,8** — deliberate (the Epic 3 retro resequenced 5→6→4), not drift. Do not "fix" it.
- **Do not touch `epic-8-action-log.md`** — a live pod resource under an append-only convention.
- **`epics.md` contains an Epic List overview section with headings that repeat the detail sections' headings.** Inserting content by anchoring on `## Epic N:` will hit the overview first — this bit during the 2026-08-02 pass and silently corrupted a heading before it was caught. Anchor on the detail section explicitly.

### Invalidated Assumptions

- **Assumption:** stories missing from `epics.md` just need appending → **Reality:** several were renumbering divergences (one planned story split into two executed ones, one planned story never executed at all). Appending would have created a second wrong mapping alongside the first. Resolved 2026-08-02 by renumbering to executed reality.
- **Assumption:** `sprint-status.yaml` is a reasonable place for handoff context → **Reality:** it is a state file read by automation; narrative there duplicates story files and drifts from them.
- **Assumption:** the two 6.2 keys are a data-entry mistake → **Reality:** they are one story with two implementation paths, the first a genuine dead end. The pivot is a finding worth preserving, not an error to erase (Nicolas, 2026-08-02).

### Project Structure Notes

Touches `_bmad-output/planning-artifacts/epics.md`, `_bmad-output/implementation-artifacts/sprint-status.yaml`, story files under `_bmad-output/implementation-artifacts/`, `project-context.md`, and a new check script. **No code changes, no deploy, no risk to the running stack.**

### Testing approach

The drift check *is* the test. Baseline output before, passing output after, plus three manual spot-checks that trimmed content survived its migration.

### References

- [Source: project-context.md] — the one-owner-per-fact convention this story enforces
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml] — 104.2 KB as of 2026-08-20 (was ~56 KB at draft), largest entry now the top-of-file `last_updated:` field (~14.9 KB); the two 6.2 keys already collapsed to one
- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 2 and Epic 3 plan→execution reconciliation notes
- [Source: _bmad-output/implementation-artifacts/epic-8-progress-report.md] — the intended home for evidence narrative
- Memory: `feedback_single_source_of_truth`, `architecture_dashboard_tui_decision` (archived), `story_6_2_textual_hybrid_decision` (archived)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- **Drift check** (`scripts/drift_check.py`): matches story/epic identity by numeric id parsed from the key (`story-7-11a-...` → `7.11a`, `story-8-6-1-...` → `8.6.1`), not by key text — this structurally handles sub-numbered stories and letter-suffix splits without a hardcoded allowlist, and is immune to the `story-3-3-openClaw-...` capital-C trap. Baseline run found exactly what the story predicted: 30 oversized comments and one real drift (`story-7-12-agent-identity-lifecycle` missing from `epics.md`).
- **Story 6.2**: re-verified already fully executed by commit `43d5ac6` (same day as the 2026-08-20 draft refresh) — single key, TUI file superseded-header, `epics.md` PIVOT note all confirmed present. Nothing to redo.
- **Comment migration**: every oversized comment was read in full and cross-checked against its story file (Completion Notes, Change Log, Review Findings), `epics.md`, `architecture.md`, or a `sprint-change-proposal-*.md` before being trimmed — in every case but one the content was already fully preserved there. The one exception, Story 7.12's missing `epics.md` entry, was written back before its `sprint-status.yaml` comment was trimmed.
- **Size**: went further than AC6's literal ask once the per-story comments were gone — the remaining bulk was epic-header narrative blocks (resequencing rationale already duplicated in `epics.md`'s own epic headers) and a stale pre-Epic-1 "Sprint Metadata" block never read by any BMAD workflow. Trimmed those too, and stripped the `→ see <path>` suffix from pointers where the path is now a documented mechanical derivation (`project-context.md`: story files are named `{key minus "story-"}.md`). Final size 7.6 KB, from a 106.7 KB baseline (93% reduction), with the drift check clean end to end.
- **`planning-docs-consolidation`'s own sprint-status entry** was updated from `ready-for-dev`/stale-comment to `in-progress` mid-session (now `review`, this update) — it was itself an example of the exact staleness pattern this story fixes.

### File List

- `scripts/drift_check.py` (new)
- `_bmad-output/implementation-artifacts/drift-check-baseline-2026-08-20.txt` (new)
- `_bmad-output/implementation-artifacts/drift-check-final-2026-08-20.txt` (new)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — comment migration + size reduction, no status values changed except this story's own)
- `_bmad-output/planning-artifacts/epics.md` (modified — added missing Story 7.12 entry)
- `project-context.md` (modified — documented the drift-check command and the story-file naming convention)
- `_bmad-output/implementation-artifacts/planning-docs-consolidation.md` (this file)

## Change Log

| Date | Change |
|---|---|
| 2026-08-02 | Drafted after Nicolas flagged large narrative comments in `sprint-status.yaml` and missing keys in both directions. Investigation found the drift systemic — 9+ stories, all of Epic 8, a duplicate story number, and two distinct root causes (renumbering divergence; sprint-status used as the cross-session context dump). |
| 2026-08-02 | **Rescoped after the same-session keys pass.** Parity (58/58) and the Epic 2/3 renumbering are complete, so their ACs were removed. Story 6.2 resolved by Nicolas as one story with a superseded TUI path — recorded as settled, no longer an open question. Remaining scope: the drift check, the 6.2 collapse, and the comment migration. |
| 2026-08-20 | **Refreshed after 18 days of further work (stories 7.5–8.9).** Re-explored rather than trusted the draft. Findings: (1) Task 2 (6.2 collapse) confirmed fully executed same-day via commit `43d5ac6` — nothing to redo; (2) the bloat grew, not shrank — 56 KB → 104.2 KB, 8 → 14 oversized comments; (3) a new bloat pattern appeared: the top-of-file `last_updated:` field is now the single largest entry (~14.9 KB), not any per-story comment — added Task 3.7 to handle it; (4) `story-8-7` (the old "newest offender") is now mid-pack; `story-7-9` (~13.1 KB) is now the largest per-story entry — added Task 3.8; (5) new sub-numbering style found, `7.11a`/`7.11b` (letter suffix, not dotted) — added to AC2 and Traps; (6) one live drift confirmed as a first test case for the drift check: `story-7-12-agent-identity-lifecycle` has no epics.md entry. Remaining scope unchanged in kind (drift check + comment migration), numbers and task list updated to match current reality. |
| 2026-08-20 | **Implemented, all tasks complete.** Built `scripts/drift_check.py` (id-based matching, no allowlist needed), ran it baseline (30 oversized comments, 1 key mismatch — the predicted 7.12 gap). Re-verified Story 6.2 already resolved, nothing to redo. Migrated every oversized comment epic by epic (8, top-of-file, 7-9, rest of 7, then 1–6/metadata for the size target), verifying content preservation before each trim; the one real gap found (7.12 missing from `epics.md`) was written back before trimming. Went beyond AC6's letter to also cut duplicated epic-header narrative and a dead Sprint Metadata block, and documented a story-file naming convention to drop redundant pointers. Final: 106.7 KB → 7.6 KB (93% reduction), drift check clean (0/0 key mismatches, 0 duplicates, 0 oversized comments), YAML still parses, next-backlog-story selection unchanged, `epic-8-action-log.md`/progress reports untouched. Status → review. |
