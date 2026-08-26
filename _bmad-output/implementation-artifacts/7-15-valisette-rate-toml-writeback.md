---
title: 'Valisette — TOML Write-Back for Rate Compatibility'
type: 'feature'
created: '2026-08-26'
status: 'done'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Valisette (the gist swipe-triage app) built its own aggregate
`triage-YYYY-MM-DD.toml` into a separate `triage/` folder every 30s. The Rate
pipeline (9h, ingests into Oxigraph at `pocpod0:7878`) now expects the grouped
TOML the cleanup pass writes into `capture/gists/` to be the single buffer
between swipe and ingestion — Valisette must patch each gist's `validation`
field in that same file, in place, and touch nothing else.

**Approach:** Read the source file fresh on every swipe, string-patch the one
`validation = "..."` line for that gist (never parse-and-rebuild — the file
carries fields Valisette doesn't own, `ingested` above all), PUT it back with
`If-Match`. Widen the deck to every `pending` gist across all non-ingested
files in the folder, newest file first, so a backlog never gates or silently
drops gists.

## Boundaries & Constraints

**Always:**
- Every write re-reads the file immediately before patching — never hold a
  file string across swipes (a Rate run landing mid-session would otherwise
  be clobbered, erasing `ingested = true`).
- A failed or interrupted write leaves `validation = "pending"` on the pod
  (fail-to-pending) — the gist returns to the deck, never silently dropped.
- Only the matched gist's `validation` line changes; every other line
  (comments, field order, pipeline-added fields) survives byte-identical.
- Deck order is newest file first; a multi-day backlog sinks below tonight's
  gists rather than gating them.

**Ask First:** N/A — settled in party-mode review (see epics.md 7.15 entry).

**Never:**
- No `triage/` output folder, no rebuilt aggregate file, no parse→rebuild
  writer.
- No flags (`revisit`/`priority`) or comment field — nothing in the Rate
  contract has anywhere for them to land.
- No local mirror of decisions in `localStorage` — the pod file is the single
  source of truth.
- Rate-side changes (reading the TOML, the `ingested` stamp, Oxigraph
  insertion) are out of scope.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal swipe | gist `pending` in today's file | `validation` patched to voted value, file re-read+PUT with `If-Match` | N/A |
| Concurrent write (Rate or another client) | ETag stale on PUT | 412 → re-read once, re-patch, retry | Second 412 or `ingested` now true → batch-closed state |
| Network drops mid-swipe | write throws | gist re-inserted into deck at current position; pod still `pending` | status strip shows failure, not silence |
| Undo | last swipe has a `history` entry | re-patches file back to `pending` (or prior value); gate is "last swipe exists", not "unsaved" | write failure on undo shown, history not lost |
| Multi-day backlog | 2+ non-ingested files | all `pending` gists loaded, newest file's gists first; older-day cards show full date | N/A |
| All files ingested / no `.toml` present | scan finds nothing | distinct empty-state copy per cause (no files / none pending / read error) | N/A |
| Batch closed mid-session | file's `ingested` flips true between swipes | write throws `batch-closed`; remaining gists in that file are dropped from further attempts this session | status strip: "batch closed by the rate — the rest rolls over" |

</frozen-after-approval>

## Code Map

- `valisette/valisette.js` -- full rewrite of the write path, deck-loading, swipe/undo, and rendering
- `valisette/index.html` -- setup screen output-folder UI removed; deck flag tray/comment removed; third overlay added
- `valisette/valisette.css` -- tray/flag/comment/output rules removed; `#anagnorisis-overlay` styling added

## Tasks & Acceptance

**Execution:**
- [x] `valisette/valisette.js` -- replace `buildTOML`/`flushSave` with `patchValidationLine` + `writeValidation` (GET→patch→PUT, `If-Match`, 412 retry) -- string-level patch is the only way to guarantee unrelated fields survive
- [x] `valisette/valisette.js` -- `collectPendingFiles`/`scanSource`/`loadGists` -- deck spans all non-ingested files, newest first, each gist tagged with its `sourceUrl`
- [x] `valisette/valisette.js` -- `onUp`/`commit` -- swipe-up commits `anagnorisis` directly; remove flag tray state machine
- [x] `valisette/valisette.js` -- `undo` -- re-gate on `history.length`, re-patch file back to prior value
- [x] `valisette/valisette.js` -- drop `saveSessionToLocalStorage`/`restoreSessionFromLocalStorage`; keep only source-folder + recents persistence
- [x] `valisette/valisette.js` -- demo mode patches an in-memory TOML string through the same code path (no parallel demo logic)
- [x] `valisette/index.html`, `valisette/valisette.css` -- remove output-folder UI, flag tray, comment field; add anagnorisis overlay

**Acceptance Criteria:**
- Given a two-gist source TOML with a `raw` block containing the word "validation" in prose, when one gist is swiped, then only that gist's `validation` line changes and every other byte (including `ingested`) is unchanged.
- Given a swipe with the network offline, when the write fails, then the gist reappears in the deck and the pod-side file still reads `validation = "pending"`.
- Given two non-ingested files from different days, when the deck loads, then today's gists appear before yesterday's, and yesterday's cards show their date.
- Given a swipe followed immediately by undo, when both complete, then the pod file reads `validation = "pending"` for that gist again.

## Spec Change Log

(none — filed after implementation, no review loopbacks)

## Design Notes

Full design discussion (undo-gate bug, clobber risk, backlog-ordering
trade-off, empty-state honesty) happened in a party-mode session with Sally
(UX) and Winston (architect) before implementation; see conversation history
2026-08-26. Key call reversed mid-review: deck order was planned oldest-first
("drains chronologically") and changed to **newest-first** on user pushback —
a multi-day backlog must never gate tonight's fresh gists; staleness sinking
to the bottom is itself the safety valve for a future "drop after n days"
policy, since anything that ages out was already the least-attended.

## Verification

**Manual checks (no CLI build/test step in this app):**
- `node --check` on `valisette.js` for syntax.
- Live: two-gist fixture in `capture/gists/`, swipe one each way, `curl` the
  file — exactly the two `validation` values changed.
- Live: devtools offline, swipe, confirm gist returns to deck and pod file
  unchanged.
- Live: edit the file server-side mid-session, swipe, confirm `If-Match` 412
  path recovers instead of clobbering.
- Live: swipe, undo, `curl` — field back to `pending`.

