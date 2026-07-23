# Story 7.5: Export & Backup — Download Your Pod

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **pod owner**,
I want to download the contents of my pod as a single archive (and understand how I'd put it back or move it elsewhere),
so that Solid's promise of portability and data ownership is real for me — I can hold my own backup and I am not locked to this provider.

## Context / Why now

Nicolas asked directly how one "packs a pod, downloads it, and unpacks it back here or on another provider" — the interoperability/portability claim at the heart of Solid. The audit established the honest state of the art (memory `css_acl_portability_audit`):

- **There is no standard pod-archive format and no CSS export/import endpoint.** Portability today is done by **crawling LDP**: recursively `GET` every container (follow `ldp:contains`) and resource, save each with its content-type (and optionally its `.acl`), then restore by `PUT`-ing them back. `solid-file-client` (`getFolderTree`/`copyFolder`) is the community tool for exactly this.
- **The hard part is identity rebinding:** moving to another provider changes the WebID, which breaks every `.acl` `acl:agent`/`acl:default` URI that referenced the old WebID. A faithful *move* needs ACL rewriting; a *backup* of your own data doesn't.
- **Server-level backup already exists** for the operator: CSS's file backend is plain files on disk, and we already run `make vps-backup` (nightly volume tar). That is the operator's disaster-recovery backup. This story is the **owner-facing** export — a user downloading *their* data, which the volume tar does not provide per-user.

Scope decision: this story delivers the **read/export half** (download my pod as an archive) as the high-value, low-risk first step. Full cross-provider *import/restore* (with WebID/ACL rebinding) is called out as a follow-on, not built here, because the rebinding problem deserves its own design.

## Acceptance Criteria

1. **One-click export:** from the backoffice, the owner can export their pod (or a chosen subtree) and receive a single downloadable archive (e.g. a `.zip`) built client-side by crawling the pod over authenticated LDP.
2. **Faithful content + structure:** the archive preserves the container/resource tree and each resource's bytes and content-type (so a PNG comes back a PNG, Turtle comes back Turtle). Round-trip check: at least one binary and one RDF resource export and re-open identically.
3. **Access metadata captured (not silently dropped):** each resource/container's effective access (its `.acl` where one exists, or a note that it inherits) is included in the archive as sidecar metadata, so a future restore/move has what it needs — even though automated re-application is out of scope here. Inherited-vs-explicit is distinguished (consistent with 7.3 AC5).
4. **Honest portability explainer:** the export UI states plainly what the archive is and isn't — "this is your data; moving it to another provider will need your permissions re-applied because your identity address (WebID) changes there." No overclaiming of turnkey cross-provider migration.
5. **Graceful, resumable-ish crawl:** the crawl degrades gracefully on a resource it can't read (permission/timeout) — it records the skip and continues, and the final archive includes a manifest of what succeeded/failed (per `feedback_graceful_failure_design`). A large pod doesn't hang the UI silently.
6. **Scope safety:** export only walks resources the owner's session is authorized to read; it never attempts to exfiltrate outside the owner's pod. No secret material (e.g. client-credential secrets, which aren't pod resources anyway) is included.
7. **WCAG 2.1 AA** on export controls/progress; **no regression** to existing surfaces.

## Tasks / Subtasks

- [ ] Task 1: LDP crawl (AC: #1, #2, #5, #6)
  - [ ] 1.1 Implement an authenticated recursive crawl in `RealBackend`: start at pod root (or chosen container), read `ldp:contains`, recurse containers, fetch each resource with its content-type. Reuse `list`/`readText`/`getFile`.
  - [ ] 1.2 Decide the crawl tool: use pinned `@inrupt/solid-client` primitives directly, or evaluate `solid-file-client` — pick based on bundle size / pinned-version compatibility; document the choice.
  - [ ] 1.3 Handle binaries (fetch as Blob/ArrayBuffer, not text) so non-text bytes survive.
  - [ ] 1.4 Graceful skip + manifest of successes/failures.
- [ ] Task 2: Archive assembly + download (AC: #1, #2, #3)
  - [ ] 2.1 Build a `.zip` client-side (a small, self-hostable zip lib consistent with the no-CORS/self-contained deploy posture — no unvetted CDN) mirroring the pod tree; store each resource with its bytes.
  - [ ] 2.2 Include per-resource sidecar access metadata (the `.acl` or an "inherits from parent" note) and a top-level manifest (tree + content-types + crawl result).
  - [ ] 2.3 Trigger a browser download of the assembled archive.
- [ ] Task 3: Portability explainer + a11y (AC: #4, #7)
  - [ ] 3.1 Plain-language panel: what the archive contains, that it's the user's data to keep, and the WebID/ACL rebinding caveat for cross-provider moves.
  - [ ] 3.2 Progress UI (Zeigarnik/goal-gradient — show crawl progress), contrast/focus-visible/keyboard.
- [ ] Task 4: Regression + scope check (AC: #6, #7)
  - [ ] 4.1 Confirm crawl stays within the owner's pod and only reads authorized resources.
  - [ ] 4.2 Regression pass on My Things / People & apps.

## Dev Notes

- **Export first, import later — deliberate.** The download/backup is genuinely useful on its own and carries no destructive risk. Cross-provider *restore* needs WebID/ACL rebinding (rewriting `acl:agent`/`acl:default` to the new identity) and provider-account bootstrapping — a separate story once someone actually needs to move.
- **Operator backup ≠ owner export.** `make vps-backup` (volume tar) is disaster recovery for the whole server; it doesn't give an individual owner *their* portable copy. This story fills that gap. Don't conflate them in the UI.
- **Crawl semantics:** follow `ldp:contains`; containers end in `/`. The audit's root listing (Turtle with `ldp:contains <profile/>, <README>`) is the shape to walk. Binaries must be fetched as Blob, not text, or they corrupt.
- **Self-contained deploy:** the backoffice is served same-origin from CSS with a strict posture — any zip library must be bundled/self-hosted, not pulled from an external CDN at runtime (consistent with 7.1's esm.sh/self-host decision; revisit that decision for a zip lib specifically).
- **Portability is a headline Solid claim** — treat the honesty of AC4 as a feature, not a disclaimer to bury. Under-promising here builds the trust the whole product is about.
- **Design principles:** progressive disclosure (simple "Download my pod" up front, the rebinding caveat one layer down), graceful failure (partial-crawl manifest), reversibility (export is read-only/non-destructive by nature).

### Testing Requirements

- No automated test harness in `backoffice/` — verify manually, same discipline as 7.1–7.4.
  - AC2: mandatory manual round-trip on both a binary (PNG) and an RDF (Turtle) resource — export, re-open the archive, byte-compare.
  - AC5: manually induce a failure (e.g. a resource the session can't read) mid-crawl and confirm the manifest records the skip and the crawl continues rather than hanging/erroring out.
  - AC6: manually confirm the crawl only ever requests URLs under the owner's pod root (no traversal outside via absolute links in resource content).
  - AC7: manually re-run My Things / People & apps flows to confirm no regression.

### Invalidated Assumptions

- **Assumption:** "Solid pods are portable, so there's an export/import button / standard archive." → **Reality:** no standard pod archive, no CSS export endpoint; portability = LDP crawl + re-PUT, and cross-provider moves break `.acl` agent URIs (WebID changes). Portability is a *capability you build*, not a given.
- **Assumption:** "the nightly volume backup already covers the owner." → **Reality:** that's operator-level whole-server DR, not a per-owner portable copy; different need.

### Project Structure Notes

- Changes land in `backoffice/index.html` (export control, progress, portability explainer) and `backoffice/pod-api.js` (`RealBackend` crawl + archive assembly; demo-mode stub). Possibly a small self-hosted zip lib added under `backoffice/`. No `infra/css/` change expected (unless a new static asset needs serving, mirroring 7.1's `StaticAssetHandler` additions).
- Keep pinned Inrupt versions.

### References

- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Live CSS ACL/portability audit (2026-07-23)] — portability reality (LDP crawl, WebID-rebind problem, volume-tar vs owner export)
- Memory: `css_acl_portability_audit` — portability section; `infra_vps_deploy` — existing `make vps-backup`
- [Source: backoffice/pod-api.js] — `list`/`readText`/`getFile` primitives to build the crawl on
- Memory: `feedback_graceful_failure_design`, `feedback_wcag_aa_standard`, `project_pilot_bridge`
- solid-file-client (community LDP crawl/copy tool) — evaluate for Task 1.2

## Dev Agent Record

### Context Reference

### Agent Model Used

### Completion Notes List

### File List

## Change Log

| Date       | Change |
|------------|--------|
| 2026-07-23 | Drafted from live audit. Owner-facing pod export via LDP crawl → downloadable archive with access-metadata sidecars + honest portability explainer. Cross-provider import/restore (WebID/ACL rebinding) explicitly deferred to a follow-on. |
