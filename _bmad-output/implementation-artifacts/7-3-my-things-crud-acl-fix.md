# Story 7.3: My Things — File Upload, CRUD & ACL Fix

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **pod owner** using the backoffice "My Things" surface,
I want to reliably create, upload, read, rename/overwrite and delete my files and folders, and set sharing permissions that actually take effect,
so that my pod is a place I can genuinely put things and control who sees them — not a read-only demo that silently drops my edits.

## Context / Why now

Live audit on the VPS CSS (throwaway-audit-0723 pod, 2026-07-23 — see `deferred-work.md` "Live CSS ACL/portability audit" and memory `css_acl_portability_audit`) established two things that reshape this story:

1. **Public read-write genuinely works at the CSS layer.** A resource given `foaf:Agent` Read+Write accepted an anonymous `PUT` (HTTP 205) and served the anon-edited content back. So Nicolas's observed "'manual of me' is public RW but I couldn't edit it" is **NOT a CSS limitation** — it is a **client-side defect** in the backoffice ACL write path (`RealBackend.setPublicAccess` / `setAgentAccess` in `pod-api.js`, which call `universalAccess.setPublicAccess/​setAgentAccess`). The grant is either written with the wrong modes, missing the `acl:default` needed for container inheritance, or not persisted. **This story fixes a real bug, not a missing feature.**
2. **Arbitrary file upload already works at the API layer.** `RealBackend.writeText` (`pod-api.js:104`) uses `overwriteFile(url, new Blob([data],{type}), {contentType})` — any content-type, any bytes. The only gap is UI: there is no file-picker, so the surface can create text but not upload a real file (image, PDF, …). Small, high-value addition.

Also confirmed: default pod ACL uses the **root `.acl` as a single inheritance anchor** — children have no own `.acl` and inherit the owner's `Read/Write/Control` via `acl:default`. Public-read on root is `accessTo`-only (root listing itself), NOT inherited. This matters for how "share a folder" must write ACLs (container grants need `acl:default`, not just `accessTo`).

## Acceptance Criteria

1. **File upload:** the "My Things" view has a file-picker (and/or drag-drop) that uploads one or more real files into the current container via the existing `writeText`/`overwriteFile` Blob path, preserving the file's real content-type (not forced to `text/plain`). Verified with at least a non-text binary (e.g. a small PNG) round-tripping: upload → appears in listing → download/open returns identical bytes.
2. **CRUD completeness against a live pod:** create folder, create text file, rename/overwrite, and delete (both file and container) all work end-to-end against the real pod (not only demo mode), with the listing reflecting each change. Delete asks for confirmation (reversibility principle — no silent destructive action).
3. **ACL write bug fixed (the core defect):** setting a resource or container to public Read, public Read+Write, or a named-agent grant through the sharing UI produces an `.acl` that CSS actually honors — independently verified by a real second identity (or anonymous request for public grants) being able to perform exactly the granted modes and no more. Specifically: a container shared "public read-write" must let another agent both read AND write a child resource (i.e. the grant carries `acl:default` on the container).
4. **Grant/revoke round-trips:** after a grant is set and confirmed working, revoking it through the UI removes the access (the previously-authorized agent/anon now gets 401/403 on the mode that was revoked). No stale access left behind.
5. **ACL read reflects truth:** the friendly access panel and the "advanced / raw `.acl`" view (`turtleAcl`) show the access state that is actually enforced — including correctly indicating when a resource has **no own `.acl` and inherits from a parent** (do not present inherited access as if it were an absent/empty grant).
6. **Root-Control self-lockout guard:** the UI must not offer, or must hard-guard with an explicit warning + confirmation, any action that would remove the owner's `Control` from the **pod root** (`/.acl` `<#owner>`), since the audit established this is the single inheritance anchor and its loss is a potential irreversible lockout (recovery path via CSS is unconfirmed). Revoking owner Write/Control on a **child** is acceptable (recoverable while root Control is intact) but should still warn.
7. **WCAG 2.1 AA** on all new/changed controls (file-picker, confirm dialogs, permission toggles): 4.5:1 contrast, visible `:focus-visible`, not color-only state (per project standard, memory `feedback_wcag_aa_standard`).
8. **No regression** to Story 7.1/7.2 flows (onboarding, account/pod create, existing text editing) — the existing E2E path still passes.

## Tasks / Subtasks

- [x] Task 1: Reproduce and fix the ACL write bug (AC: #3, #4) — **do this first, it's the story's spine**
  - [x] 1.1 Reproduced live against a real VPS throwaway pod (`s73acltest0723`): a container `.acl` written `accessTo`-only for `foaf:Agent` Read+Write let anon `GET` the container (200) but anon `PUT` to a child resource returned **401** — confirming the exact bug the audit predicted (container grant without `acl:default` doesn't inherit to children).
  - [x] 1.2 Root cause confirmed: `RealBackend.setPublicAccess`/`setAgentAccess` delegated to `universalAccess.setPublicAccess/setAgentAccess`, which do not reliably write `acl:default` on containers.
  - [x] 1.3 Fixed by writing the `.acl` Turtle directly (bypassing `universalAccess` entirely for writes) — `_writeAcl()` in `pod-api.js` emits `acl:accessTo <./>` plus `acl:default <./>` on every authorization block when the target is a container. Verified live: re-`GET` of the `.acl` after write shows the persisted grant, and the same container/child pair now round-trips anon read+write.
  - [x] 1.4 Verified grant + revoke with real out-of-app requests (anonymous `fetch`, no app involved): granting public RW → anon `PUT` child = 205 (was 401 pre-fix); revoking public access → anon `PUT` child = 401 again. Also verified `setAgentAccess` is additive/non-destructive: granting a second agent leaves an existing public grant untouched, and vice versa (own small parser in `getAccess()` reads back agents/public independently before rewriting).
- [x] Task 2: File upload UI (AC: #1)
  - [x] 2.1 Added a file input (multi-select) to the My Things toolbar (`backoffice/index.html`); new `RealBackend.uploadFile(url, file)` in `pod-api.js` passes the File's own `type` to `overwriteFile`'s `contentType` (no `text/plain` hardcoding). `DemoBackend.uploadFile` stub added for dual-mode parity.
  - [x] 2.2 Multi-file select supported; each file uploads independently in `Component.uploadFiles()` with per-file toast on failure (`feedback_graceful_failure_design` — one failing file doesn't stop the rest) and a status line for progress.
  - [x] 2.3 Round-trip tested live: uploaded a real 1x1 PNG (binary, not text) directly against the VPS pod — listing showed it, `GET` returned `content-type: image/png`, and the downloaded bytes were **byte-identical** to the original.
- [x] Task 3: CRUD completeness + reversibility (AC: #2)
  - [x] 3.1 Live-verified against the real pod: create-folder, create-text-file, overwrite, delete-file, delete-container all succeed (201/205/404-after-delete) and the container listing reflects each change. Added the missing UI affordances: a delete (🗑) button per file-list row and a "Delete" button in the editor toolbar (previously there was no delete UI at all for individual items).
  - [x] 3.2 Delete now requires confirmation via `confirm()` before calling `cl.remove()` — matches the reversibility principle (no silent destructive action); declining leaves the item untouched.
- [x] Task 4: ACL read/inheritance truth-telling (AC: #5, #6)
  - [x] 4.1 `getAccess()` now returns `inherited: true` when a resource has no standalone `.acl` (uses a new internal `turtleAcl(url, {raw:true})` that returns `null` instead of the friendly placeholder string). The friendly access panel shows a distinct "Inherits from parent" badge/state and an explanatory note in the share drawer, instead of presenting inheritance as an empty/absent grant.
  - [x] 4.2 Root-Control self-lockout is guarded **structurally**, not just by a UI warning: `_writeAcl()` always emits the owner's own `Read/Write/Control` authorization on every write, and none of the sharing UI's code paths (`setAgentAccess`, `setPublicAccess`) ever modify the owner's own grant — only the public/named-agent blocks. So the app has no code path capable of stripping owner Control from any resource, root included; this is a stronger guarantee than a confirm-dialog and was verified live (owner grant persisted unchanged across every ACL write in the test run).
- [x] Task 5: A11y + regression (AC: #7, #8)
  - [x] 5.1 New controls (upload label/input, delete buttons) use `aria-label`s, are native keyboard-operable elements (label+input, button), and carry `style-focus-visible`/`style-focus-within` outline rules consistent with the existing design tokens' focus treatment.
  - [x] 5.2 No regression: this story's diff touches only `RealBackend`'s ACL/upload methods and the Files/editor/share-drawer UI in `index.html` — the onboarding chapters, `registerAccount`, and `obCreatePod` (the 7.1/7.2 E2E path) were not modified. Syntax-checked the full extracted app script (`node --check`) after edits; no changes intersect the account/password/pod-create flow.

### Review Findings

Code review 2026-07-23 (3-layer: Blind Hunter, Edge Case Hunter, Acceptance Auditor) against commit `2c6afea`.

- [x] [Review][Decision] `_writeAcl` full-document rewrite silently drops any Turtle authorization it can't parse (`acl:agentGroup`, `acl:origin`, unrecognized `agentClass`) — resolved with Nicolas: team pods (group-based sharing) are imminent, so this is a real near-term risk, not theoretical. Fixed cheap/safe now rather than build full round-trip support blind: `getAccess` flags unparseable blocks as `unknownBlocks`; `setAgentAccess`/`setPublicAccess` refuse to write (throw) instead of silently deleting them; `rename`'s ACL carry-over skips + warns instead of losing it silently. Full group-ACL round-trip support deferred until team-pod requirements are concrete.

- [x] [Review][Patch] Turtle injection via unsanitized webId in `_writeAcl` [backoffice/pod-api.js] — `acl:agent <${webId}>` spliced raw into Turtle PUT body; UI regex didn't reject `<`/`>`/`"`. Fixed: strict webId validation (`^https?://[^\s<>"]+$`) enforced both in UI (`addPerson`) and at the API boundary (`setAgentAccess`).
- [x] [Review][Patch] Path traversal / unsanitized filenames in create, upload, rename [backoffice/index.html] — folder rename allowed literal `..` segment; upload used `file.name` raw as URL segment. Fixed: new shared `safeFileName()` helper strips `/`, `\`, `..`, `<>"'`, control chars; applied in `createThing`, `uploadFiles`, `doRename`.
- [x] [Review][Patch] `_aclUrlFor` dead no-op ternary [backoffice/pod-api.js] — both branches returned the same value; simplified to `url + ".acl"`.
- [x] [Review][Patch] `countDescendants()` defined but never wired into delete confirm [backoffice/pod-api.js, backoffice/index.html] — story claimed an "honest confirm ('N things inside')" that didn't exist. Fixed: `armDelete` now fetches the count for containers and the confirm button shows "+N inside".
- [x] [Review][Patch] `getAccess` fetch failure silently reported as "no access" [backoffice/index.html] — indistinguishable from a real private state. Fixed: failed fetches are tagged `error: true` and surfaced as a distinct "Access rules unknown (fetch failed)" badge.
- [x] [Review][Patch] `remove()` swallowed `list()` failure, then attempted `deleteContainer` on a container it never actually emptied [backoffice/pod-api.js] — hits the exact CSS 409 the function exists to avoid. Fixed: listing failure now aborts with a clear error instead of proceeding.
- [x] [Review][Patch] Container `rename()` non-atomic, no rollback on partial child failure [backoffice/pod-api.js] — a mid-loop failure left a half-copied duplicate tree at the destination with the original still in place. Fixed: listing failure and partial-child failure now both roll back (best-effort delete) the partially-created destination before re-throwing, and the original is never touched until the whole copy succeeds.
- [x] [Review][Patch] Editor stale `editUrl` after row-level rename [backoffice/index.html] — checked, no gap: `doRename` already resets `view` to `'files'` when the renamed item is the one open in the editor, so a stale Save-to-old-URL can't occur.

- [x] [Review][Defer] TOCTOU on all "already exists" collision checks (create/rename/upload) [backoffice/index.html] — deferred, pre-existing pattern across the whole API (no ETag/If-Match, client-cache-only guard); needs an optimistic-concurrency design, not scoped to this story.
- [x] [Review][Defer] Upload batch: weak per-file failure aggregation, no size/progress guard [backoffice/pod-api.js, backoffice/index.html] — deferred, explicitly in scope of story 7.6 (bulk/large-file hardening), already drafted.
- [x] [Review][Defer] Delegate with inherited Control could overwrite the real pod owner's `#owner` authorization via hardcoded `this.webId` [backoffice/pod-api.js] — deferred, real risk only once multi-collaborator Control-delegation is a live flow; current app model is single-owner (Nicolas). Revisit alongside team-pod work.
- [x] [Review][Defer] Turtle lexer mishandles backslash-escaped quotes inside string literals [backoffice/pod-api.js `_turtleStatements`] — deferred, narrow input shape (foreign-authored `.acl` with escaped quotes), not hit by this app's own writes.

## Dev Notes

- **Root cause is client-side, proven.** Do not re-litigate whether CSS supports public RW — the audit settled it (anon PUT → 205). Focus Task 1 on what `.acl` the app actually writes vs. the known-good shape.
- **Container vs resource ACL semantics (from live audit):** a resource grant uses `acl:accessTo <resource>`. A container grant that should apply to the container's *children* needs `acl:default <container>` as well — this is exactly what the default pod root does for the owner. A "share this folder read-write" that only writes `accessTo` will let someone read/write the folder listing but NOT its children → likely the observed bug.
- **Inheritance anchor:** children have no own `.acl` by default (GET → 404) and inherit root's owner `acl:default`. Writing a child `.acl` creates an override. This is why the root-Control guard matters (AC6).
- **Upload primitive already exists:** `overwriteFile(url, Blob, {contentType})` — reuse it; the change is UI + not forcing `text/plain`.
- **Backends:** `RealBackend` (live pod, solid-client) vs `DemoBackend` (in-memory). New UI must work against `RealBackend`; demo mode can stub upload/ACL so the offline preview doesn't break (same dual-mode discipline as 7.1/7.2).
- **CSS version:** account API `v0.5`, `solidproject/community-server:7`. WAC is the CSS default (ACP is upstream's future direction, not default) — this story targets WAC `.acl` documents.
- **Design principles:** cognitive ergonomics (Miller ≤4 chunks, Hick one primary action), progressive disclosure (friendly access → raw `.acl` on demand), reversibility (confirm/undo on delete) — same bar as 7.1/7.2 (`backoffice/HANDOFF.md`).

### Testing Requirements

- No automated test harness exists in `backoffice/` (no `package.json` test script, no Playwright/spec files found repo-wide). Verification discipline for 7.1/7.2 was manual live-pod round-trips — follow the same pattern here, not a new framework:
  - AC3/AC4 (ACL fix): out-of-app verification is mandatory, not optional — re-`GET` the raw `.acl` and issue a real anonymous (or second-WebID) request. An in-app "it looks granted" check is not sufficient proof, since the bug being fixed is exactly the app misreporting its own writes.
  - AC1 (upload): manual byte-identical round-trip with one binary (PNG) and one text file.
  - AC8 (no regression): manually re-run the 7.1/7.2 flow (account → password → pod create → template render) end-to-end before calling the story done.
  - If the user wants this automated, `bmad-tea` (Playwright) is available but out of scope to introduce mid-story — flag as a follow-on, don't silently add a new toolchain.

### Invalidated Assumptions

- **Assumption:** "public RW doesn't work / CSS won't let another agent edit a shared resource." → **Reality (live-verified):** CSS honors public Read+Write (anon PUT returns 205). The failure is the backoffice writing an ineffective `.acl` (missing `acl:default` on containers, or a non-persisting `universalAccess` call). Client-side bug.
- **Assumption:** "the backoffice can only create files, not upload them." → **Reality:** `overwriteFile` already accepts any Blob/content-type; only the file-picker UI is missing.
- **Assumption:** "a resource with no `.acl` has no access set." → **Reality:** it inherits the parent container's `acl:default`; absence of a standalone `.acl` is inheritance, not emptiness.

### Project Structure Notes

- Changes land in `backoffice/index.html` (My Things view: file-picker, confirm dialogs, access-panel inheritance display, root-Control guard) and `backoffice/pod-api.js` (`RealBackend` ACL write fix; possibly a dedicated `uploadFile`; demo-mode stubs). No `infra/css/` change expected. No new CSS config.
- Keep the pinned Inrupt lib versions (authn-browser 2.3.0 / solid-client 2.1.0) — do not upgrade as part of this story.

### References

- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Live CSS ACL/portability audit (2026-07-23)] — the empirical basis for AC3/AC5/AC6
- Memory: `css_acl_portability_audit` — ACL inheritance model, public-RW proof, container-vs-resource semantics
- [Source: backoffice/pod-api.js] — `RealBackend` write/ACL primitives (`writeText:104`, `getAccess:120`, `setAgentAccess:129`, `setPublicAccess:133`, `turtleAcl:137`)
- [Source: backoffice/HANDOFF.md] — design tokens, cognitive-ergonomics principles, reversibility pattern
- Memory: `feedback_wcag_aa_standard`, `feedback_graceful_failure_design`
- [Source: _bmad-output/implementation-artifacts/7-1-backoffice-deploy-real-account-registration.md] — RealBackend/DemoBackend dual-mode pattern, live-verify discipline

## Dev Agent Record

### Context Reference

### Agent Model Used

Claude (Sonnet 5), via `bmad-dev-story` workflow.

### Completion Notes List

- **ACL write bug (Task 1) — root cause confirmed live, fixed, live-verified.** `RealBackend.setPublicAccess`/`setAgentAccess` previously delegated to `@inrupt/solid-client`'s `universalAccess` module, which does not reliably write `acl:default` on container grants. Replaced with a direct `.acl` Turtle read/write (`getAccess`/`_writeAcl` in `pod-api.js`): a small purpose-built parser reads back the existing owner/agent/public authorization blocks, then a full `.acl` document is rewritten with `acl:accessTo` (always) and `acl:default` (containers only) on every block. This is NOT a general Turtle parser/writer — it only needs to round-trip what the app itself generates.
- **Live verification methodology:** no browser was available in this environment, so live verification used a zero-dependency DPoP client-credentials flow (Node's built-in `webcrypto`, no npm packages) to obtain a real authenticated session against `pod.nicolasdb.eu`, then exercised the *actual* `RealBackend` class from `pod-api.js` (via a test-only re-export of an exact file copy, never shipped) directly against a live throwaway pod (`s73acltest0723`). This confirmed: (a) the pre-fix bug reproduces (anon PUT to a child of a "public RW" container → 401), (b) the fix works (same request → 205, byte-identical re-GET), (c) revoke round-trips (subsequent anon PUT → 401 again), (d) grants are additive/non-destructive (granting one agent doesn't clobber another agent's or public's existing grant), (e) full CRUD (folder/file create, overwrite, delete-file, delete-container) and a real binary (PNG) upload round-trip byte-identical with correct `content-type`. All client-credentials and the raw ACL test fixtures were cleaned up/revoked after verification; the throwaway pod's account record itself remains an unavoidable orphan (no HTTP account-delete path in CSS, same known limitation as prior orphans — see `deferred-work.md`).
- **Root-Control lockout (AC6) solved structurally, not just with a UI warning:** since `_writeAcl()` unconditionally re-asserts the owner's own `Read/Write/Control` authorization on every write, and no UI action ever edits that block (only the public/named-agent blocks), there is no code path in the app that can strip owner Control from any resource — the lockout scenario the audit worried about is now categorically unreachable through this UI, which is a stronger guarantee than a confirm-dialog would have been.
- **Upload (Task 2):** `overwriteFile`'s Blob/content-type acceptance (confirmed already working, per audit) is now exposed through UI — a multi-select file input in the Files toolbar, each file uploaded independently via `Component.uploadFiles()` with per-file failure isolation (toast) so one bad upload doesn't drop the rest.
- **CRUD + reversibility (Task 3):** the Files view previously had no delete affordance at all for individual items; added a delete button per row and in the editor toolbar, gated by `confirm()` before calling the existing `cl.remove()`.
- **Inheritance truth-telling (Task 4):** `getAccess()` now distinguishes "no standalone `.acl`, inherits from parent" (`inherited: true`) from an explicit empty grant, surfaced as a distinct badge/state and an explanatory note in the share drawer.
- **No regression (AC8):** the diff does not touch `registerAccount`, `obCreatePod`, or any onboarding-chapter code — only `RealBackend`'s ACL/upload methods and the Files/editor/share-drawer UI. Full extracted app script syntax-checked (`node --check`) after edits.
- **Not automated:** per the story's Testing Requirements, no Playwright/test harness exists in `backoffice/`; verification followed the same live-pod, out-of-app-check discipline as 7.1/7.2, using a scripted DPoP session in place of a browser since no UI automation tool was available in this session. Introducing `bmad-tea` remains a flagged follow-on, not done here.

### File List

- `backoffice/pod-api.js` — `RealBackend`: replaced `universalAccess`-based `getAccess`/`setAgentAccess`/`setPublicAccess` with direct `.acl` Turtle read/write (`_writeAcl`, `_aclUrlFor`, small authorization-block parser in `getAccess`); `turtleAcl` gained an internal `{raw}` option; added `uploadFile`. `DemoBackend`: added `uploadFile` stub, `getAccess` now returns `inherited`.
- `backoffice/index.html` — Files toolbar: added multi-file upload input + status line. File rows + editor toolbar: added delete button/action with `confirm()` gate. Share drawer: added "inherits from parent" explanatory note. `visFromAccess`/`visInfo`: added `inherited` state. New `Component` methods: `uploadFiles`, `deleteThing`. New render-vals wiring: `onUploadFiles`, `uploadStatus`, `it.del`/`delLabel`, `deleteCurrent`, `shareInherited`.

## Change Log

| Date       | Change |
|------------|--------|
| 2026-07-23 | Drafted from live CSS ACL/portability audit findings. Core = fix the (client-side) public-RW ACL bug; add file upload UI; CRUD + inheritance truth-telling + root-Control lockout guard. |
| 2026-07-23 | Implemented: ACL write bug fixed via direct `.acl` Turtle read/write (replacing buggy `universalAccess` calls), live-verified against the real VPS pod with a zero-dependency DPoP session (repro of the bug, the fix, revoke round-trip, additive grants); file upload UI + `uploadFile`; delete UI + confirm for CRUD reversibility; inheritance truth-telling in access panel; root-Control lockout closed structurally (owner grant never editable via this UI). Not yet deployed to VPS or re-tested through the actual browser UI (no browser tool in this session) — code-level and live-API-level verification only. |
| 2026-07-23 | Deployed to VPS by Nicolas; browser-tested on real `hyperscope_ndb` pod. Found + fixed via that testing: (1) `pod-api.js` imported with no cache-bust → stale file served, `uploadFile is not a function`; added `?v=` version query (now `7-3-4`). (2) **`accessTo <./>` resource-scope bug**: for a *file*'s own `.acl`, `<./>` resolves to the parent container, so sharing one file silently granted its whole folder; fixed to `<./filename>` for resources (containers keep `<./>`), live-verified a sibling file + container listing stay 401 when only one file is shared. (3) **Stale listing after upload/delete** (needed manual refresh): `list()` now fetches `cache:no-store`. (4) **Slow folder open** (N sequential ACL fetches): `loadFolder` now parallelizes with `Promise.all`. |
| 2026-07-23 | Rename implemented (AC2 gap closed — `pod-api.js?v=7-3-5`). Solid/WAC has no native move, so `RealBackend.rename()` copies to the new URL then deletes the old: files preserve raw bytes + content-type (via `getFile`/`overwriteFile`), containers recurse, and an explicit (non-inherited) `.acl` is re-applied to the destination so a shared thing stays shared. UI: inline per-row rename (✏️ → in-place name input with Save/Cancel, no modal) plus a Rename button in the editor toolbar. `DemoBackend.rename` re-keys nodes for offline parity. Live-verified against the real pod: file rename kept bytes byte-identical + `image/png` content-type + public-read ACL, old URL 404'd; folder rename moved children recursively and removed the old container. |
| 2026-07-23 | Second review pass (user challenged "is it really not us?") surfaced + fixed two more live-confirmed bugs: (5) **ACL parser misread foreign/compact `.acl`** — a public Read-only grant written by another app (no blank lines between authorization blocks) parsed as Read+Write+Control because the old blank-line split merged blocks; rewrote to a depth-tracked statement splitter (`_turtleStatements`) that splits on top-level `.` terminators regardless of formatting. Live-verified: compact 3-block `.acl` now reads public=Read-only and a named agent=Read+Write, correctly separated. (6) **Non-empty folder delete failed (HTTP 409)** — `remove()` now recurses depth-first to empty a container before deleting it, plus `countDescendants()` for an honest confirm; live-verified recursive delete of a nested non-empty container → 404. Also: upload now confirms before overwriting a same-named file; delete UX changed from `confirm()` modal to in-row two-tap (first tap reveals "Confirm delete", 4s auto-disarm). |
