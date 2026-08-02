# Story: Planning-Docs Consolidation — One Owner Per Fact

Status: ready-for-dev
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

Two things surfaced only by reading the files, worth keeping in mind for the rest of the pass:
- **Planned Story 2.2 (dataset generation) was never a story at all** — the PRD classes the dataset as an external input. No amount of renumbering would have revealed that; only reading did.
- **Story 3.7.1 (Pipeline Dashboard TUI) was `done`, had a story file, and was absent from `sprint-status.yaml` entirely.**

### What remains — this story

1. **The comment bloat.** `sprint-status.yaml` is **~56 KB** with a single **8.9 KB** line. Eight entries exceed 2 KB, all Epic 7/8.
2. **The 6.2 duplicate**, now unambiguous — see the settled decision below.
3. **A re-runnable drift check.** Without one, the parity achieved above decays silently again. It decayed across eight epics before anyone looked.

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

2. **The drift check distinguishes sub-numbered stories from real duplicates.** `3.7`/`3.7.1`, `4.0`/`4.0.1`/`4.0.2`, `4.4`/`4.4.1`, `8.6`/`8.6.1` are legitimate; only genuinely colliding numbers are reported. A check that cries wolf gets ignored.

3. ~~Story 6.2 resolves to one key~~ **Done 2026-08-02**, out of scope for this story now — see the table above.

4. **No comment in `sprint-status.yaml` exceeds 120 characters**, and every trimmed entry follows the form:
   `key: status  # <date>: <one-line summary> → see <path>`

5. **Nothing is lost in the trim.** Before shortening any comment, verify its content exists in the story file (or progress report, or memory) and **append what is missing there first**. This is a migration, not a deletion — some findings exist *only* in those comments.

6. **`sprint-status.yaml` ends under 8 KB** (from ~56 KB) while still carrying every key and status.

7. **The BMAD workflows that consume `sprint-status.yaml` still work** — the file parses, and next-backlog-story selection still resolves correctly. **A lean file that breaks story selection is a worse outcome than a fat one.**

8. **The drift check passes** at the end of this story, and its output is recorded as the evidence.

9. **`epic-8-action-log.md` and the progress reports are untouched** by the trim — they are the intended home for narrative and are working as designed.

## Tasks / Subtasks

- [ ] **Task 1 — Build the drift check first (AC: 1, 2)**
  - [ ] 1.1 Report key mismatches both directions, real duplicate story numbers, comments >120 chars, file size.
  - [ ] 1.2 Handle sub-numbered stories correctly (AC2) — the naive regex reports four false positives.
  - [ ] 1.3 Run it **before** any edit and keep the baseline output; it is the evidence the pass did something.
  - [ ] 1.4 One command, runnable by a human. Document it in `project-context.md` next to the convention.
  - [ ] 1.5 **Build this before touching anything else** — otherwise the rest of the work is judged by eye.

- [ ] **Task 2 — Resolve Story 6.2 (AC: 3)**
  - [ ] 2.1 Collapse to a single `story-6-2-*` key, status `done`.
  - [ ] 2.2 Mark the TUI story file as a superseded *path* of 6.2 — a header note, not a deletion.
  - [ ] 2.3 Confirm `epics.md`'s Story 6.2 entry reflects one story with two paths, so the epic doc matches.
  - [ ] 2.4 Preserve the pivot as a finding: Textual/TUI was reached twice (3.7.1 and 6.2) and abandoned twice. That pattern is worth being legible to a future reader.

- [ ] **Task 3 — Migrate the mega-comments (AC: 4, 5, 6)**
  - [ ] 3.1 For each entry over 120 chars, read the comment **and** the story file. List what the comment says that the story file does not.
  - [ ] 3.2 Append the gaps to the story file's Completion Notes / Change Log — or the epic progress report, whichever is the right owner — **before** trimming anything.
  - [ ] 3.3 Replace the comment with `# <date>: <one-line summary> → see <path>`.
  - [ ] 3.4 One epic at a time, commit per epic, so a mistake is reviewable rather than a 56 KB diff.
  - [ ] 3.5 **Start with Epic 8** — largest entries, most recently written, so the content is still fresh enough to judge what is redundant.
  - [ ] 3.6 Include the 4.4 KB `story-8-7` entry written on 2026-08-02. It is the newest offender and the same rule applies to it.

- [ ] **Task 4 — Verify (AC: 7, 8, 9)**
  - [ ] 4.1 Drift check passes; record the output.
  - [ ] 4.2 Spot-check three trimmed entries against their story files to confirm nothing was lost.
  - [ ] 4.3 Confirm `sprint-status.yaml` still parses and next-backlog-story selection still resolves.
  - [ ] 4.4 Confirm `epic-8-action-log.md` and the progress reports are unmodified.

## Dev Notes

### Why the comments got there — understand before removing

`sprint-status.yaml` is the one file every BMAD workflow reads start-to-finish, so it became the place to leave anything the next session must not miss. That instinct was **right about the need and wrong about the location**. If this pass removes the context without relocating it, the same pressure refills the file within a few stories. Task 3.2's *append-before-trimming* ordering is the entire safety mechanism.

### This is a migration, not a cleanup

The mega-comments contain real findings: live-verified results, review findings that were rejected and why, corrected scope decisions, traps discovered on the VPS. Some may exist *only* there. Deleting first and checking later loses project history that cost real sessions to produce.

### Don't over-automate the trim

A regex truncating comments at 120 chars satisfies AC4 and violates AC5. **The reading is the work; the trimming is trivial.**

### Sequencing

Non-blocking. Best run **between** stories, not mid-story, since it rewrites the file dev workflows read to pick up work.

### Traps

- **Sub-numbered stories are not duplicates** — `3.7.1`, `4.0.1`, `4.0.2`, `4.4.1`, `8.6.1` are real stories. A naive duplicate check reports all of them (AC2).
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
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml] — the ~56 KB file, the 8.9 KB line, the two 6.2 keys
- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 2 and Epic 3 plan→execution reconciliation notes
- [Source: _bmad-output/implementation-artifacts/epic-8-progress-report.md] — the intended home for evidence narrative
- Memory: `feedback_single_source_of_truth`, `architecture_dashboard_tui_decision` (archived), `story_6_2_textual_hybrid_decision` (archived)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-02 | Drafted after Nicolas flagged large narrative comments in `sprint-status.yaml` and missing keys in both directions. Investigation found the drift systemic — 9+ stories, all of Epic 8, a duplicate story number, and two distinct root causes (renumbering divergence; sprint-status used as the cross-session context dump). |
| 2026-08-02 | **Rescoped after the same-session keys pass.** Parity (58/58) and the Epic 2/3 renumbering are complete, so their ACs were removed. Story 6.2 resolved by Nicolas as one story with a superseded TUI path — recorded as settled, no longer an open question. Remaining scope: the drift check, the 6.2 collapse, and the comment migration. |
