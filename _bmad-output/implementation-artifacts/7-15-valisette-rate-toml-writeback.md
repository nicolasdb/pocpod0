---
title: 'Valisette — TOML Write-Back for Rate Compatibility'
type: 'feature'
created: '2026-08-26'
status: 'review'
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

**Approach:** Read the source file fresh on every swipe, string-patch the
`validation` line for that gist (never parse-and-rebuild — the file carries
fields Valisette doesn't own), PUT it back with `If-Match`. Widen the deck to
every `pending` gist across all non-ingested files in the folder, newest file
first, so a backlog never gates or silently drops gists.

## Boundaries & Constraints

**Always:**
- Every write re-reads the file immediately before patching — never hold a
  file string across swipes (a Rate run landing mid-session would otherwise
  be clobbered).
- A failed or interrupted write leaves `validation = "pending"` on the pod
  (fail-to-pending) — the gist returns to the deck, never silently dropped.
- Only the matched gist's `validation`, `note`, and `triage_flags` lines
  change; every other field survives byte-identical, including the
  pipeline's own `tags`.
- Deck order is newest file first; a multi-day backlog sinks below tonight's
  gists rather than gating them.

**Ask First:** N/A — settled in party-mode review (see epics.md 7.15 entry),
plus three follow-up decisions taken live during dogfooding (see Dev Notes).

**Never:**
- No `triage/` output folder, no rebuilt aggregate file, no parse→rebuild
  writer.
- No local mirror of decisions in `localStorage` — the pod file is the single
  source of truth.
- No reuse of the pipeline's `tags` field for UI state — it holds topical
  keywords (`["cron","timezone"]`), unrelated meaning.
- Rate-side changes (reading the TOML, the `ingested` stamp, Oxigraph
  insertion) are out of scope.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal swipe | gist `pending` in today's file | `validation` (+ `note`/`triage_flags` if set) patched, file re-read+PUT with `If-Match` | N/A |
| Concurrent write (Rate or another client) | ETag stale on PUT | 412 → re-read once, re-patch, retry | Second 412 or `ingested` now true → batch-closed state |
| Network drops mid-swipe | write throws | gist re-inserted into deck at current position; pod still `pending` | status strip shows failure, not silence |
| Undo | last swipe has a `history` entry | re-patches file back to prior `validation`/`note`/`triage_flags`; gate is "last swipe exists", not "unsaved" | write failure on undo shown, history not lost |
| Multi-day backlog | 2+ non-ingested files | all `pending` gists loaded, newest file's gists first; older-day cards show full date | N/A |
| All files ingested / no `.toml` present | scan finds nothing | distinct empty-state copy per cause (no files / none pending / read error) | back button on deck header returns to setup |
| Batch closed mid-session | file's `ingested` flips true between swipes | write throws `batch-closed`; remaining gists in that file are dropped from further attempts this session | status strip: "batch closed by the rate — the rest rolls over" |
| Single-line `raw = """text"""` | real pipeline output writes raw on one line | parsed and patched correctly | N/A — see Dev Notes, this was a live bug |
| Raw containing the word `validation` | prose text inside a `raw` block | never mistaken for the `validation` field | N/A |

</frozen-after-approval>

## Code Map

- `valisette/valisette.js` -- full rewrite of the write path, deck-loading, swipe/undo, flag tray, and rendering
- `valisette/index.html` -- setup screen output-folder UI removed; deck header gained a back button; flag tray + comment restored
- `valisette/valisette.css` -- output/recents rules removed; flag-tray/comment/back-button styling; counter-text contrast fix

## Tasks & Acceptance

**Execution:**
- [x] `valisette/valisette.js` -- `patchGistFields(text, id, validation, note, flags)` -- single string-level pass patches/inserts `validation`, `note`, `triage_flags`; everything else byte-identical
- [x] `valisette/valisette.js` -- `collectPendingFiles`/`scanSource`/`loadGists` -- deck spans all non-ingested files, newest first, each gist tagged with its `sourceUrl`
- [x] `valisette/valisette.js` -- swipe left/right commit `validated`/`rejected` directly; drag-up reopens a flag tray (anagnorisis/follow-up/priority, multi-select, non-exclusive)
- [x] `valisette/valisette.js` -- `undo` -- re-gates on `history.length`, re-patches file back to prior `validation`/`note`/`triage_flags`, restores tray/comment for editing
- [x] `valisette/valisette.js` -- drop `saveSessionToLocalStorage`/`restoreSessionFromLocalStorage` and the recents chip row; keep only source-folder persistence
- [x] `valisette/valisette.js` -- demo mode patches an in-memory TOML string through the same code path, skips folder selection entirely (no pod behind it)
- [x] `valisette/index.html`, `valisette/valisette.css` -- remove output-folder UI + recents; flag tray + comment restored; deck-header back button added

**Acceptance Criteria:**
- Given a real pipeline-authored TOML (single-line `raw`, `tags`, `source`, `status`, `confidence`, `routing` fields present), when one gist is swiped, then only that gist's `validation` (and `note`/`triage_flags` if set) changes and every other byte is unchanged.
- Given a swipe with the network offline, when the write fails, then the gist reappears in the deck and the pod-side file still reads `validation = "pending"`.
- Given two non-ingested files from different days, when the deck loads, then today's gists appear before yesterday's, and yesterday's cards show their date.
- Given a swipe followed immediately by undo, when both complete, then the pod file reads `validation = "pending"` for that gist again.
- Given the deck reaches "nothing pending" or any other state, when the user wants to leave, then a back button on the deck header returns to setup.

## Spec Change Log

- **2026-08-26, live dogfooding:** anagnorisis reverted from a 3rd validation
  outcome back to a flag (see Dev Notes #4) — needs practice before locking a
  schema around it as an outcome. `revisit`/`priority` flags restored
  alongside it, contra the original "Never: no flags" line — superseded, see
  Boundaries above.
- **2026-08-26:** comment field restored, now written as `note` — contra the
  original "no comment field" line — superseded.

## Design Notes

Full pre-implementation design discussion (undo-gate bug, clobber risk,
backlog-ordering trade-off, empty-state honesty) happened in a party-mode
session with Sally (UX) and Winston (architect); see conversation history
2026-08-26. Key call reversed mid-review: deck order was planned oldest-first
("drains chronologically") and changed to **newest-first** on user pushback —
a multi-day backlog must never gate tonight's fresh gists; staleness sinking
to the bottom is itself the safety valve for a future "drop after n days"
policy, since anything that ages out was already the least-attended.

## Dev Notes — live bugs found & fixed during dogfooding

Everything below surfaced only against the real pod / real pipeline file,
after the initial implementation passed on synthetic fixtures.

1. **Demo `sourcePath` leaked into a real login.** `bootDemo()` → `loadGists()`
   → `saveSetupToLocalStorage()` persisted the `demo:///...` path into
   `valisette:setup`; a subsequent real WebID login read it back and tried to
   list `demo://` as a pod container ("couldn't read that folder"). Fixed by
   skipping the save in demo mode and ignoring any already-stored `demo:`
   value on restore.
2. **Real TOML raw blocks are single-line** (`raw = """text"""`, open+close on
   the same line), not the multi-line form the parser assumed. The parser
   only recognized a raw block as closed if the line was *exactly* `"""` —
   any other single-line raw left it "inside raw" for the rest of the file,
   silently swallowing every `[[gist]]` boundary after the first one. Every
   gist past the first failed to patch ("gist is no longer in that file").
   Fixed in both `parseGistTOML` and the patcher: a raw line closes on the
   same line whenever it *ends* in `"""`.
3. **Failed-write retry duplicated the gist.** `commit()` never removes a
   gist from `state.gists` (only advances the pointer); the failure handler
   re-inserted it anyway, so the deck total grew by one on every failed
   retry (observed 17, then 23, on a 7-gist file — compounded by bug #2's
   near-constant failures). Fixed by moving the pointer back to the gist's
   existing array index instead of re-inserting.
4. **Anagnorisis reverted from a 3rd validation outcome to a flag.** Initial
   design made `validation` 3-way (`pending`/`validated`/`rejected`/
   `anagnorisis`), swipe-up committing it directly. User feedback: needs
   validating from practice before locking that into the schema, and the
   original tray/flags UX (anagnorisis + follow-up + priority, multi-select,
   non-exclusive) worked better. Reverted; flags now live in a new
   `triage_flags` field, written only when non-empty, deliberately not the
   pipeline's own `tags`.
5. **Comment field restored**, now written as a `note` field on the gist
   (only when non-empty) — the original plan had dropped it since the Rate
   contract had nowhere for it to land; extended the contract instead.
6. **Deck screen had no way out.** The close button only exists on
   screen-done, reached by finishing the whole stack — landing on "nothing
   pending" straight from setup (or abandoning mid-deck) left no affordance
   back to setup. Added a "‹" back button to the deck header.
7. **Counter contrast.** `#counter-text` used `--text-tertiary`, visibly
   darker than `#session-date`'s `--text-secondary` on the same header row.
   Matched.

## Known schema gap — needs a decision before this ships for real use

The handoff spec says the session header (`[gist_session]`) carries
`ingested = false`, flipped to `true` by the Rate once done with a file.
**The live file (`capture/gists/2026-08-21.toml`, written by the cleanup
pass) has no `ingested` key at all** — confirmed by reading it directly on
the VPS. Valisette's `isIngested()` defaults to `false` when the key is
absent, so today it degrades safely (never treats a file as closed when it
shouldn't) — but that's incidental, not a contract. Either the cleanup pass
needs to start writing `ingested`, or Valisette needs a different signal for
"this batch is closed." Blocks trusting the "batch closed mid-session" path
in practice.

## TOML Schema

### Input — what Valisette expects to find in `capture/gists/*.toml`

```toml
[gist_session]
version_schema = "v1"
# ...other pipeline-authored session fields, read-only to Valisette
# ingested = false        ← spec assumes this; NOT present in the live file today (see gap above)

[[gist]]
id = "gist-20260821-001"            # required — patch target key
timestamp = 1787291737               # untouched
type = "decision"                    # untouched — decision | apprentissage | protocole
titre = "..."                        # untouched
validation = "pending"               # required — must exist for the patcher to find its anchor line
raw = """single line or multi-line""" # untouched — both forms parse correctly
source = "session:manny/..."         # untouched
raw_type = "decision"                # untouched
status = "provisoire"                # untouched
confidence = 0.85                    # untouched
moment = "2026-08-21 08:20 CEST"     # read by Valisette (display + date/backlog logic)
tags = ["cron", "timezone"]          # untouched — PIPELINE topic tags, never written by Valisette
routing = "automate"                 # untouched
# note = "..."                       # optional — present if a prior Valisette session added one
# triage_flags = ["anagnorisis"]     # optional — present if a prior Valisette session added one
```

Only two fields are load-bearing for Valisette to function: `id` (patch
target) and `validation` (must exist, any value — used to filter to
`pending` and as the patch anchor line). Every other field is passed through
untouched and re-emitted byte-identical.

### Output — what a swipe changes

A swipe patches, on the one matched `[[gist]]` block, in place, preserving
line order and every other field:

| Field | When written | Values |
|---|---|---|
| `validation` | always | `"pending"` → `"validated"` \| `"rejected"` |
| `note` | only if the comment box was non-empty | free text, TOML-escaped |
| `triage_flags` | only if at least one flag was toggled | array of `"anagnorisis"` \| `"followup"` \| `"priority"` |

`anagnorisis` is **not** a `validation` value in the current implementation
(see Dev Note #4) — it is one of three `triage_flags`, independent of
validated/rejected. Undo reverses all three fields back to their pre-swipe
values on the same gist.

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
- Confirmed live by Nicolas 2026-08-26 against `capture/gists/2026-08-21.toml`
  on the VPS pod, after bugs #1–#3 above were found and fixed in the same
  session.

