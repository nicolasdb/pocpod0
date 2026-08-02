# Project Context — pocpod0

Rules that apply across all work in this repo. BMAD workflows load this file when present.

## Single source of truth — one owner per fact

Each fact lives in exactly one file. Everywhere else points to it.

| File | Owns | Must never hold |
|---|---|---|
| `_bmad-output/planning-artifacts/epics.md` | intent — what & why, one entry per story that **actually exists** | status, execution detail, findings |
| `_bmad-output/implementation-artifacts/{story}.md` | the truth for one story — context, ACs, tasks, dev notes, completion notes | — |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | **state only**: `key: status` + a ≤120-char pointer | narrative, findings, evidence, decisions |
| `_bmad-output/implementation-artifacts/epic-N-progress-report.md` | proof/evidence narrative per epic | intent |
| `_bmad-output/planning-artifacts/architecture.md` | cross-cutting model, principles (BP-*) | per-story execution detail |
| `_bmad-output/planning-artifacts/prd.md` | requirements (FR*/NFR), user journeys | implementation detail |
| `~/.claude/projects/.../memory/` | cross-session lessons and decisions | anything the repo already records |

**Rule: nothing appears in two places except as a pointer.**

### sprint-status.yaml is a state file, not a handoff document

It is the one file every workflow reads start-to-finish, which makes it tempting as a place to leave notes for the next session. Resist it. Context belongs in the story file; lessons belong in memory; evidence belongs in the progress report. Entry format:

```yaml
  story-8-5-live-verification: done  # 2026-08-01: all ACs met live → see 8-5-live-verification.md
```

### When a story is split, renumbered, or inserted mid-execution

**Write back to `epics.md` in the same session.** This is the single largest source of drift in this project: epics.md carried the original plan numbering while execution split and inserted stories, and the two diverged silently across eight epics before anyone checked.

### When a cross-cutting model lands mid-story

Sweep `architecture.md` principles, `prd.md` journeys + FRs, and the `epics.md` epic header before drafting further. Expect to find prior principles that now disagree — reconcile them explicitly with a dated amendment note rather than overwriting. The disagreement usually contains an argument worth keeping.

## Evidence conventions

- **Live evidence beats argument** (Epic 8). An AC met by a real client beats one met by our own script talking to our own server.
- **Failure states are first-class.** A documented "the client did not prompt" result is a finding, not a failure to hide.
- **Verify third-party behaviour before framing it as a defect** — docs or a live test, not assumption.
- Epic 8 appends a dated section to the pod-hosted action log per story (read-then-append, verified by byte-length growth).

## Accessibility

WCAG 2.1 AA for all user-facing surfaces: 4.5:1 contrast, `focus-visible`, never colour alone as an indicator.
