# Story 7.6: My Things — File-Manager Hardening (learn from solid-file-manager)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **pod owner** managing a real, growing pod through the backoffice "My Things" surface,
I want file operations to be as robust and fluid as a dedicated Solid file manager — moving things between folders, handling large/many files without freezing or silent data loss, and recovering gracefully when an op fails —
so that My Things feels like a trustworthy place to keep real work, not a fragile demo that loses a file on a name collision or hangs on a big folder.

## Context / Why now

Story 7.3 built the CRUD + ACL + upload spine and, through live browser testing on a real messy pod (`hyperscope_ndb`, populated partly by the third-party `focus.noeldemartin.com` todo app), surfaced a class of robustness gaps that are real but out of 7.3's scope. During that review the question arose: are we reinventing a file manager? The community reference is **[solid-contrib/solid-file-manager](https://github.com/solid-contrib/solid-file-manager)** (and the underlying `solid-file-client`).

Decision (with Nicolas, 2026-07-23): **do NOT adopt solid-file-manager wholesale** — it lacks the two things that are the whole point of our surface: an **ACL/permissions UI** and **inline file editing**, and it's a standalone app, not a drop-in library. Adopting it would mean discarding our differentiators (onboarding, ACL truth-telling, reversibility/double-tap delete, WCAG, inline edit) and rebuilding them on someone else's architecture. Instead, **treat it as a reference and respectfully "steal" the specific robustness patterns we lack**, keeping our own surface and its differentiators.

What we keep (do NOT regress): inline editor, ACL/sharing drawer with inheritance truth-telling, two-tap delete, per-file overwrite/creation collision guards, WCAG. What solid-file-manager does better and we should learn from: **move/copy across folders**, **bulk/multi-select operations**, **transfer progress for large or many files**, and **robust copy/move edge-case handling** (name collisions, deep trees, mixed binary/text).

This story is explicitly a **hardening/UX pass on top of 7.3**, not a rewrite. Bundle discipline holds: no wholesale new framework, keep pinned Inrupt lib versions unless a concrete gap forces an addition (documented if so).

## Acceptance Criteria

1. **Move across folders:** the owner can move a file or folder into a different container (not just rename in place). Move preserves bytes, content-type, and any explicit `.acl` (same guarantees as 7.3 rename), recurses for folders, and confirms before overwriting a same-named item at the destination (no silent data loss). Live round-trip verified: a binary moved between two folders is byte-identical and the source is gone.
2. **Bulk selection + bulk ops:** the file list supports selecting multiple items and performing delete (and at least move) on the selection as one action, with a single confirmation summarizing the count/impact (reuse the reversibility bar; bulk delete of N still gives a clear "delete N things?" confirm). One item failing does not abort or silently drop the rest (`feedback_graceful_failure_design`) — per-item outcome is reported.
3. **Transfer progress:** upload, move, and bulk operations on many/large files show real per-item progress and a running summary, and never leave the UI frozen or ambiguous about whether it's working. Big folders don't block interaction silently.
4. **Robust large-folder listing:** opening a folder with many entries (hundreds+) stays responsive — ACL fetches are already parallelized (7.3); this story confirms the parallel fetch scales, adds batching/throttling if needed to avoid hammering the server, and shows a loading state that reflects progress rather than an indefinite spinner.
5. **Graceful op failure, everywhere:** every multi-step op (move, bulk, big upload) degrades gracefully on a partial failure — it reports what succeeded and what didn't with a plain-language reason, leaves the pod in a consistent state (no half-moved item that's been deleted from source but never written to destination), and never claims success it didn't achieve (`feedback_troll_report_philosophy`, `feedback_graceful_failure_design`).
6. **Reference audit captured:** a short written comparison of solid-file-manager / solid-file-client patterns we evaluated — what we adopted, what we deliberately didn't, and why — lives in the story's Dev Notes (so the "don't re-adopt this later" reasoning is durable). No code is copied verbatim without attribution; patterns are re-implemented in our idiom.
7. **No regression + WCAG 2.1 AA:** all 7.3 flows (create/upload/rename/overwrite/delete, ACL drawer, inline edit, two-tap delete, inheritance display) still pass; new controls (multi-select, move target picker, progress) meet 4.5:1 contrast, visible `:focus-visible`, keyboard-operable, not color-only state.

## Tasks / Subtasks

- [ ] Task 1: Reference audit (AC: #6) — **do this first, it scopes the rest**
  - [ ] 1.1 Read solid-file-manager + solid-file-client source for their move/copy, bulk-op, and progress implementations. Note concrete patterns (e.g. `copyFolder`/`getFolderTree`, collision strategy, how they surface progress).
  - [ ] 1.2 Write the "adopted / rejected / why" comparison into Dev Notes. Confirm the licence permits pattern reuse and record attribution.
  - [ ] 1.3 Decide: pinned `@inrupt/solid-client` primitives only, or add a vetted helper — justify against bundle/pinned-version discipline.
- [ ] Task 2: Move across folders (AC: #1)
  - [ ] 2.1 Generalize 7.3's `rename` (which is copy-to-new + delete-old in the same parent) into a `move(oldUrl, newParentUrl)` that targets a different container; preserve bytes/content-type/explicit-ACL, recurse for folders.
  - [ ] 2.2 **Consistency safety:** write-then-verify-then-delete ordering so a failed copy never deletes the source (no data loss on partial move). Collision confirm at destination.
  - [ ] 2.3 UI: a move affordance (target-folder picker) that is keyboard-operable; live round-trip test a binary across folders.
- [ ] Task 3: Bulk selection + bulk ops (AC: #2, #5)
  - [ ] 3.1 Multi-select in the file list (checkbox/selection state), with a bulk action bar.
  - [ ] 3.2 Bulk delete + bulk move over the selection, per-item graceful failure, single count-aware confirmation.
- [ ] Task 4: Progress + large-folder robustness (AC: #3, #4)
  - [ ] 4.1 Per-item + summary progress for upload/move/bulk (reuse/extend the `uploadStatus` pattern into a general progress surface).
  - [ ] 4.2 Confirm parallel ACL fetch scales on a large folder; add batching/throttle if it hammers the server; progress-reflecting loading state.
- [ ] Task 5: No-regression + a11y (AC: #7)
  - [ ] 5.1 Re-run all 7.3 flows; confirm inline edit, ACL drawer, two-tap delete, collision guards intact.
  - [ ] 5.2 Contrast/focus-visible/keyboard on multi-select, move picker, progress; not color-only.

## Dev Notes

- **This builds directly on 7.3's `pod-api.js` primitives.** `rename` already does copy(bytes+content-type+explicit-ACL)-then-delete and recurses; `move` is the same with a different destination parent. `remove` already recurses non-empty containers. `getAccess`/`_writeAcl` handle explicit-vs-inherited. Don't re-solve these — extend them.
- **Consistency ordering is the safety-critical bit.** A move that deletes the source before confirming the destination write succeeded can lose data. Copy → verify (re-GET) → only then delete source. Mirror the "no success we didn't achieve" discipline.
- **solid-file-manager is a REFERENCE, not a dependency.** Re-implement patterns in our idiom; keep our ACL UI + inline edit + two-tap delete, which it lacks. Record the audit so this decision isn't re-litigated.
- **Bundle discipline:** pinned `@inrupt/solid-client-authn-browser@2.3.0` / `solid-client@2.1.0`, loaded via `esm.sh?bundle`. `solid-file-client` may be evaluated but adding it must clear the bundle/pinned-version bar (Task 1.3).
- **Verification discipline (same as 7.1/7.2/7.3):** no automated harness in `backoffice/`; verify via live-pod round-trips. 7.3 established a working out-of-app verification harness — a zero-dependency Node DPoP client-credentials session (webcrypto, no npm) that drives the real `RealBackend` methods against `pod.nicolasdb.eu` and checks results with independent anonymous/authed requests. Reuse that harness for move/bulk verification. Always revoke test client-credentials after; the throwaway account itself can't be HTTP-deleted (known CSS limitation, `deferred-work.md`).
- **Design principles unchanged:** cognitive ergonomics (Miller ≤4, Hick one primary action), progressive disclosure, reversibility (confirm/undo, two-tap delete) — `backoffice/HANDOFF.md`.

### Invalidated Assumptions

- **Assumption:** "we should adopt solid-file-manager to avoid reinventing a file manager." → **Reality:** it lacks the ACL/permissions UI and inline editing that are the core of this surface, and is a standalone app not a library; adopting it costs more (rebuild differentiators on foreign arch) than maintaining our thin wrapper over `solid-client`. It's a reference to learn from, not a base to build on.
- **Assumption:** "7.3's rename covers moving things." → **Reality:** 7.3 rename is deliberately same-parent only; cross-folder move (and bulk) is this story.

### Project Structure Notes

- Changes land in `backoffice/pod-api.js` (`move`, generalized from `rename`; possibly batched ACL fetch) and `backoffice/index.html` (multi-select, move target picker, general progress surface). No `infra/css/` change expected.
- Keep the pinned Inrupt lib versions unless Task 1.3 justifies an addition.
- Cache-bust: bump the `pod-api.js?v=` query on any `pod-api.js` change (7.3 shipped through `v=7-3-7`).

### References

- https://github.com/solid-contrib/solid-file-manager — reference implementation for move/copy, bulk ops, transfer progress
- solid-file-client (`getFolderTree`, `copyFolder`) — underlying LDP crawl/copy primitives
- [Source: backoffice/pod-api.js] — 7.3 `RealBackend`: `rename`, `remove` (recursive), `getAccess`/`_writeAcl`, `uploadFile`
- [Source: _bmad-output/implementation-artifacts/7-3-my-things-crud-acl-fix.md] — CRUD/ACL/upload spine this hardens
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — file-manager hardening backlog note (2026-07-23)
- Memory: `feedback_graceful_failure_design`, `feedback_troll_report_philosophy`, `feedback_wcag_aa_standard`, `css_acl_portability_audit`

## Dev Agent Record

### Context Reference

### Agent Model Used

### Completion Notes List

### File List

## Change Log

| Date       | Change |
|------------|--------|
| 2026-07-23 | Drafted from 7.3 live-testing findings + the solid-file-manager "reference not dependency" decision. Scope = cross-folder move, bulk ops, transfer progress, large-folder robustness, graceful partial-failure — hardening on top of 7.3, keeping our ACL UI + inline edit + two-tap delete differentiators. |
