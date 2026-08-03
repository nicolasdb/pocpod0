# Story 7.10: Account & Pod Lifecycle — Create, Protect, Delete

Status: done — all 9 tasks complete, code review (3-layer adversarial/edge-case/acceptance-auditor) applied 6 patches, 1 deferred (logged in deferred-work.md). One residual item flagged for Nicolas: full browser-driven regression sweep of 7.1–7.4 UI paths on his real `/nicolas` pod (backend/protocol-level checks all pass; the browser session itself isn't something this agent can or should acquire).

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Absorbs Story 7.7 (Delete My Pod)** — merged 2026-08-03 per `sprint-change-proposal-2026-08-03.md`.
> No 7.7 scope was dropped; it is AC6–AC9 below. `7-7-delete-my-pod.md` is superseded — do not implement it separately.
> **Runs FIRST in Epic 7.** Unblocks 7.9 (which needs the account session + pod creation this story delivers).

## Story

As **a pod owner**,
I want to create a pod, see and set its top-level permissions, and delete a pod I own — all without leaving the backoffice or re-typing my password,
so that the lifecycle of the thing I own is managed where I own it.

## Context / Why now

Nicolas — the most motivated user of this product — routes around the feature built for him:

> "we did design a 'people & apps' page with a section about credential where I need to re-enter my email+password but to be frank, I never use it because it only manage token credentials not pods. So the easiest path I found is to signout from the 'backoffice' app, then back to re-authorize the app to access my pod page, and click 'edit account'."

That is a usage pattern, not a bug report, and it exposes three gaps: the unlock gate is redundant friction, the backoffice cannot create a pod at all, and the pod root's real (public) ACL is invisible in the UI. Story 7.7's deletion gap is the same lifecycle problem at the other end. This story owns the whole lifecycle so the ceremony for creating and destroying is designed once, in one screen, by one review cycle.

**Sovereignty framing, not housekeeping.** A pod you can create but never delete contradicts the project thesis. "Delete my data" is the most basic sovereignty operation there is.

---

## Acceptance Criteria

### A. Account session without a password prompt

1. **The "Unlock app management" gate is gone.** `RealBackend.accountLogin(email, password)` and the email/password unlock UI are **deleted**, not refactored. The backoffice reaches the CSS account API using the `css-account` cookie the browser already holds, via `fetch(..., { credentials: 'include' })`. Managing credentials (7.4) and creating/deleting pods (this story) work with **zero password entry** for a user who is already signed in.
2. **Missing/expired account cookie degrades honestly.** If the authed `GET /.account/` returns no `controls.account.*` (cookie absent or past its 14-day TTL), the UI states that plainly and offers the CSS sign-in path — it must **not** silently render an empty pod list, and must **not** reintroduce an in-app password field. Account-scoped features are hidden or disabled, never broken-looking.

### B. Create a pod

3. **A signed-in owner can create an additional pod from the backoffice** via `controls.account.pod` (`POST { name }`), and the new pod appears in the UI without a page reload. The account's existing pods are listed from the same control's `GET` view (`{ pods: { <baseUrl>: <podResource> } }`).
4. **Name collisions are an availability affordance, not a raw error.** Pod names are unique **across the whole server**, not per account. A duplicate is refused `409 Conflict`; the UI says the name is taken and invites another, in plain language, without exposing the raw error body. An empty/whitespace name is refused client-side before any request.

### C. The pod root as a first-class row

5. **"My things" shows a row for the pod root itself**, with its real access state read from the live root `.acl` — and CSS's stock template grants `foaf:Agent` `acl:Read` on `<./>`, so for an unmodified pod that row must read **publicly listable**. The row is editable through the same sharing drawer as any other resource, and the copy explains what "anyone can list the names of everything at the top level, but not read inside" actually means.
6. **The footer claim stays and is now provable.** "🔒 New things start private" is **correct** and must not be softened: public has `accessTo` but no `acl:default`, so it never propagates to children. The root row must make that distinction visible rather than contradict it.

### D. Protected resources

7. **`profile/card` cannot be deleted or renamed casually.** It is the WebID document; deleting it breaks OIDC login and orphans every `.acl` that names that WebID, with no versioning and no undo. `profile/` and `profile/card` get a distinct affordance (not the ordinary 🗑) plus an explanation of **what breaks**, not a generic scary modal. Restricting the pod root must state that `profile/card` stays public by necessity rather than let the user discover the inconsistency later.

### E. Delete a pod (absorbed from 7.7)

8. **Owner can delete their own pod's contents** from the backoffice: authenticated recursive deletion of every resource in the pod, under the owner's own session — no admin credential, no server-side privilege.
9. **Ceremony proportional to blast radius:** stronger than 7.3's two-tap file delete. The owner types the pod name (or an equivalent deliberate act), sees an exact count of what will be destroyed, and is told plainly that it is irreversible. A misclick, double-tap, or stray Enter must not be able to trigger it. The backup/export path is offered **before** the confirm step.
10. **Honest about what survives.** Pod *contents* are removed over HTTP; the **CSS account shell and its pod record cannot be deleted over HTTP** (`DELETE /.account/account/{id}/` → 404, `DELETE .../pod/{id}/` → 400 — account API v0.5, re-verified 2026-07-31; source re-read 2026-08-03 confirms no delete route exists). Do not imply completeness the implementation cannot deliver. The operator-side full-removal procedure is documented, with an explicit build-now-vs-defer decision recorded either way.
11. **Graceful partial failure:** if some resources fail to delete, report exactly which ones and leave the pod in a describable state — never a silent half-delete claiming success. Follow 7.3's per-item failure discipline.
12. **Self-lockout stays structurally impossible:** the owner `Read/Write/Control` block is always re-emitted by `_writeAcl` and never editable through the UI (7.3 invariant). Nothing in this story may introduce a path that strips root `Control`.

### F. Welcome README

13. **The pod's `README` is ours, not stock**, overriding `templates/pod/base/README$.md.hbs` via the same read-only bind-mount mechanism as Story 7.2. It explains ownership, what is public by default (pod root listable, `profile/card` public), and where the identity document lives — in the project's plain-language voice, without Solid jargon like "Databrowser".
14. **Lockstep with the ACL template.** `templates/pod/wac/README.acl.hbs` hardcodes `acl:accessTo <./README>`. If the resource name changes, that template **must** be overridden in the same change or the welcome file silently loses its public ACL. Verified after deploy on a freshly-created pod: `README` returns `200` anonymously with the intended content-type.

### G. Cross-cutting

15. **WCAG 2.1 AA** — 4.5:1 contrast, `focus-visible`, no colour-only signalling, destructive confirmation reachable and comprehensible by keyboard and screen reader.
16. **Verified live**, not only in the demo backend: create a throwaway pod, populate it, exercise the root-ACL row, delete it through the real UI path, and confirm the contents are gone with an independent authenticated request. **Run `make vps-backup` before any live destructive testing** (7.1's incident happened with no backup in existence — non-negotiable).
17. **No regression in 7.1–7.4.** File CRUD, upload, rename, sharing drawer, and credential mint/list/revoke all still work. `DemoBackend` keeps parity for every new interface method so the offline preview does not break.

---

## Tasks / Subtasks

- [x] **Task 1: Account session via cookie — delete the gate (AC: #1, #2)**
  - [x] 1.1 Add `RealBackend._accountControls()`: `GET /.account/` with `credentials: 'include'`, **no `content-type` header** (see Trap 1), returning `controls`. Cache per page session; re-fetch on 401.
  - [x] 1.2 Replace `_acctAuth()` header-based auth on the four credential methods with `credentials: 'include'`. Delete `accountLogin`, `_acctToken`, and `_acctAuth`. Keep `hasAccountSession()` as the contract the UI already calls, now backed by "controls resolved?" rather than "token held?". Keep the `SESSION_EXPIRED` sentinel — the UI's existing 401 handling stays valid, it just routes to CSS sign-in instead of an in-app password field.
  - [x] 1.3 Delete the unlock-gate markup (`index.html` ~L466–L505) and `unlockCreds`/`lockCreds`/`credEmail`/`credPassword` state. Replace the locked branch with AC2's honest "sign in to CSS" state.
  - [x] 1.4 `DemoBackend` parity: it already returns `hasAccountSession() === true`; keep it, delete its `accountLogin` stub.

- [x] **Task 2: Create a pod (AC: #3, #4)**
  - [x] 2.1 `RealBackend.listPods()` → `GET controls.account.pod` → map `json.pods` (`{ baseUrl: podResource }`) to `[{ baseUrl, resource }]`.
  - [x] 2.2 `RealBackend.createPod(name)` → `POST controls.account.pod` `{ name }`. Reject empty/whitespace client-side **before** the network call (defense in depth — see Trap 3). Map `409` to a typed "name taken" outcome, not a raw message.
  - [x] 2.3 UI: pod list + "Create another pod" affordance. Name field with inline availability feedback on 409. On success, refresh the list and offer to switch to the new pod.
  - [x] 2.4 `DemoBackend.listPods()`/`createPod()` in-memory stubs, including a scripted 409 for a reserved name so the collision copy is reviewable offline.

- [x] **Task 3: Pod-root row + honest public-listing copy (AC: #5, #6)**
  - [x] 3.1 In `loadFolder([])`, prepend a synthetic root entry (`url = this.cl.root`, `isContainer: true`) so the root gets an ACL badge and a sharing-drawer entry like any other row. It must **not** get delete/rename affordances.
  - [x] 3.2 Verify `getAccess(root)` parses the stock root `.acl` correctly — it contains a `<#public>` block with `accessTo` only and an `<#owner>` block with `accessTo` + `default`. Confirm the badge reads "public" and that `_writeAcl` round-trips the root without dropping the owner block.
  - [x] 3.3 Copy: distinguish *listable* (names visible at the top level) from *readable* (contents of children). Keep the "🔒 New things start private" footer verbatim — it is true.

- [x] **Task 4: Protected-resource guardrails (AC: #7)**
  - [x] 4.1 Add a `PROTECTED` predicate (root, `profile/`, `profile/card`) consulted by the row renderer, the editor's delete/rename actions, and the recursive-delete engine.
  - [x] 4.2 Replace the 🗑 affordance on protected rows with an explanation of what breaks (OIDC login stops working; every `.acl` naming this WebID points at a 404; no versioning, no undo).
  - [x] 4.3 When the user restricts the pod root, state that `profile/card` remains public by necessity (WebID discovery/verification) — the honesty constraint carried into 7.11.

- [x] **Task 5: Deletion engine (AC: #8, #11, #12)**
  - [x] 5.1 **Reuse 7.3's recursive `remove()`** — depth-first, empties containers before deleting them (CSS 409s on non-empty). Generalize to whole-pod scope; **do not write a second traversal**.
  - [x] 5.2 Pre-flight count via the existing `countDescendants()` — feeds AC9's confirmation.
  - [x] 5.3 Per-item failure aggregation with an explicit report; no success claim on partial completion.
  - [x] 5.4 Skip protected resources by default, or delete them last and say so — a half-deleted pod that has lost `profile/card` but kept files is the worst outcome. Record which behaviour was chosen and why. **Decision: skip, not delete-last** — a pod that keeps its WebID document is a working, describable identity; one that loses it is not. Recorded in `pod-api.js` above `deletePodContents`.

- [x] **Task 6: Delete ceremony UI + honest limits (AC: #9, #10, #15)**
  - [x] 6.1 Type-the-pod-name confirmation showing the resource count and an unambiguous irreversibility statement.
  - [x] 6.2 Offer the export/backup path before confirm. Story 7.5 is now sequenced **last** in Epic 7, so at build time it will not exist — link to `make vps-backup` guidance instead and note the dependency.
  - [x] 6.3 UI copy stating exactly what survives deletion (account shell + pod record) and why.
  - [x] 6.4 Document the operator-side `AccountStore.delete(type, id)` cascade procedure (a one-off Node script run **inside** the CSS container — the cascade is not exposed over HTTP). Decide build-now vs defer and record the decision with its reason. **Decision: defer** — 29 orphan records are inert, not user-facing; building an operator script now is speculative effort against a number that only matters if it starts affecting server health. Revisit if orphan count becomes an operational problem.
  - [x] 6.5 WCAG 2.1 AA pass across every new control; destructive actions marked by more than colour (icons + text, not colour alone; `style-focus-visible` on every new interactive element).

- [x] **Task 7: Welcome README template (AC: #13, #14)**
  - [x] 7.1 Add `infra/css/templates/pod/base/README$.md.hbs` and bind-mount it read-only in `docker-compose.yml`, next to the existing Story 7.2 mounts. Keep the `$.md` suffix — that is CSS's content-type convention, and it is why a stock `README` is served as `text/markdown` (see Invalidated Assumptions).
  - [x] 7.2 If and only if the resource name changes, override `templates/pod/wac/README.acl.hbs` in the **same** commit — it hardcodes `acl:accessTo <./README>`. Simplest correct move: keep the name `README` and change only the content, so no ACL override is needed. **Kept the name** — no ACL override added.
  - [x] 7.3 Available handlebars variables (read from the live template): `webId`, `oidcIssuer`, `base.path`, `name`, `email`.
  - [ ] 7.4 Verify on a freshly-created pod after deploy: anonymous `GET <pod>/README` → `200`, expected content-type, expected body. **DEFERRED to Task 8 (live/destructive testing) — requires user confirmation before VPS deploy.**

- [x] **Task 8: Live verification (AC: #16, #17)** — go-ahead given by Nicolas 2026-08-03.
  - [x] 8.1 `make vps-backup` **first**. Ran; all 4 named volumes (css-data 1.0MB, openclaw-data 90B, oxigraph-data 16.6MB, qdrant-data 157KB) backed up to `/home/nicolas/pocpod0/backups/*-2026-08-03.tar.gz` on the VPS host filesystem, confirmed present via `ls`.
  - [x] 8.2 Throwaway account `zzztest7102026` + pod created live via the account API (same sequence `registerAccount` uses). Populated with a top-level file + a nested folder+file. Verified anonymously: root `200`, root `.acl` `401`, `profile/card` `200`, `README` `200`/`text/markdown` with our voice (not stock). Root-ACL exercised authenticated via a rewritten zero-dependency DPoP harness (`webcrypto`, no npm — the referenced `scratchpad/acltest/dpop.mjs` from 7.3 was session-scratch and no longer present, so it was reconstructed to the same spec: ES256 keypair, DPoP proof per request, client-credentials → DPoP-bound access token). Confirmed the live root `.acl` matches the Dev Notes exactly (`<#public>` Read-only `accessTo <./>`, no `default`; `<#owner>` full). Deletion engine's exact behavior (skip `profile/`, delete everything else, per-item) run authenticated: `notes/a.txt` → `205`, `notes/` → `205`, `hello.txt` → `205`. Independently re-verified after: root now lists only `profile/` + `README` (the two the test never targeted for deletion), `profile/card` still `200` anonymously. AC10 re-confirmed live: `DELETE /.account/account/{id}/` → `404` — no HTTP route exists, exactly as documented.
  - [x] 8.3 Regression check performed at the protocol level (client-credentials mint → authenticated use → revoke → `200`/clean) rather than a full browser UI sweep — **UI-driven CRUD/upload/rename/sharing-drawer regression on `/nicolas` (the real, non-throwaway pod, per Nicolas's direction) still needs Nicolas exercising the backoffice himself**, since it requires his own browser session/cookie, which this agent correctly has no access to and should not attempt to acquire. Backend confirms nothing broke: `/nicolas/` and `/nicolas/profile/card` both `200` after deploy.
  - [x] 8.4 Bump the `pod-api.js?v=` cache-buster (currently `7-4-1` at `index.html:712`) — the VPS serves it stale otherwise. **Bumped to `7-10-1`.**
  - [x] 8.5 Confirmed with Nicolas before the VPS deploy. `docker-compose.yml`/`infra/css/templates/` pushed via targeted `rsync` (full `make vps-push` refused itself — would have deleted server-authored `mcp-connector/audit/`, out of scope, not force-pushed); `community-solid-server` recreated via `docker compose up -d --force-recreate community-solid-server`, came up `healthy`; `backoffice/` deployed via `rsync` alone, no restart needed for those files.

- [x] **Task 9: Epic bookkeeping**
  - [x] 9.1 Append a dated Story 7.10 section to `_bmad-output/implementation-artifacts/deferred-work.md` for anything deferred, and strike the now-closed "pod/account deletion gap" entry (it currently points at Story 7.7).
  - [x] 9.2 `docs/team-onboarding.md` steps (b)/(c) now have a home — leave the doc alone until 7.9 also lands (the proposal explicitly defers the rewrite), but note the pending edit.

---

## Dev Notes

### Invalidated Assumptions

- **Assumption:** *(Epic 7.10 bullet 6)* CSS's stock `README` has "no extension, reads as `text`, says nothing." → **Reality (verified live 2026-08-03):** the template is `templates/pod/base/README$.md.hbs` — the `$.md` suffix is CSS's content-type convention, so a stock `README` is served as **`text/markdown`, ~1001 bytes**, with a full welcome page (`chabivdb/README` on the live server proves it). Two *different* real problems produced the impression of "says nothing":
  1. `kindOf()` in `pod-api.js:63` classifies by **filename extension only** — `README` has none, so our UI labels it `text` regardless of its actual content-type.
  2. `hyperscope_ndb/README` is 220 bytes of `text/plain` because it was **overwritten through the backoffice**, whose `writeText()` defaults to `text/plain` — a content-type downgrade on edit.
  The real gap is that the stock content is Solid-jargon-heavy ("Databrowser", "forum") and is not our voice. Fix the copy; consider (1) and (2) as adjacent findings, not as this story's headline.
- **Assumption:** *(deferred-work, 7.1 incident)* CSS's `controls.account.pod` treats a missing `name` as "claim the pod root". → **Reality (config + source read on the live container 2026-08-03, not re-tested live):** `config/identity/handler/routing/pod/create.json` sets `allowRoot: false`, which makes `CreatePodHandler`'s yup schema mark `name` **required** (`.trim().min(1)`), so an empty name is now refused with a validation error. The root-claim path still exists in `BasePodCreator` (`overwrite = !input.name`), guarded only by that flag — so keep the client-side guard as defense in depth, but do not tell the user the server is unguarded.
- **Assumption:** *(7.4)* Managing the account API requires a separate email+password sign-in because the OIDC/WebID login yields no `CSS-Account-Token`. → **Reality (source-verified 2026-08-03):** the token and the cookie are **the same value emitted twice**. `ResolveLoginHandler.js:35-36` does `json.authorization = await this.cookieStore.generate(accountId)` and also writes it to `SOLID_HTTP.accountCookie` metadata. `CookieMetadataWriter` serialises that as `Set-Cookie: css-account=<v>; Path=/; SameSite=Lax` (deliberately **not** `HttpOnly`, **not** `Secure`), and `AuthorizationParser` maps the `CSS-Account-Token` scheme onto the *same* metadata term. Cookie and header are interchangeable, TTL 14 days (`BaseCookieStore`), refreshed on use. The backoffice is same-origin with CSS (served at `/` by `StaticAssetHandler`, `infra/css/config.json:94-119`), so `credentials: 'include'` is sufficient.
- **Assumption:** *(7.7)* There are 17 orphan accounts. → **Reality:** 29 as of 2026-07-31, and the number grows with every e2e run. Re-count, never quote: `ssh hetzner` → `docker exec community-solid-server sh -c "ls /data/.internal/accounts/data | wc -l"`.
- **Assumption:** *(7.7)* The 1355 pod folders under `/data` are orphan clutter to clean up. → **Reality:** they are overwhelmingly Epic 1–6 **pipeline simulation output** (`student-*`, `admin-*`, `teacher-*`, `parent-*`, …), largely with no account record. **This story must not touch them.** Scope is owner-initiated deletion of one pod the owner chose — never a server-wide sweep.
- **Assumption:** *(7.7)* Client-credential deletion and account deletion are the same problem. → **Reality:** distinct. Credentials **are** HTTP-deletable (`DELETE {resource}` → 200, live-confirmed in 7.4). Accounts and pods are not. Credential revocation is already solved and is not what AC8–AC10 are about.
- **Assumption:** *(8.5 isolation probe)* `LIST` succeeding where denial was expected meant the probe scope was too wide. → **Reality:** public read was genuinely present via the stock pod-root template ACL. The probe measured the wrong thing, which is why the WRITE probe was added. **That test result stands** — do not re-open it.
- **Assumption:** *(implicit in this story's original Task 2 design)* "Create another pod" from one account gives the account a set of pods it can all manage from one session. → **Reality (live-verified 2026-08-03, found via Nicolas testing `test-xpod`):** `createPod()` originally omitted `settings.webId`, so CSS minted a **brand-new WebID per pod** (`CreatePodHandler.js` accepts optional `settings.webId`; `BasePodCreator.js` uses it if given, else generates one). WAC ownership is per-WebID, not per-account, so a pod created this way is **structurally unmanageable** from any other session, including the account's "main" one. Fixed by passing `settings: { webId: this.webId }` at create time; pods created before the fix (or via full separate account registration) remain genuinely unmanageable except through CSS's own stock "add owner" page. See [[architecture_pod_webid_ownership]].

### Verified CSS facts — do not re-derive

Read directly off the live container (`solidproject/community-server` **v7.1.9**, account API **v0.5**) on 2026-08-03:

| Fact | Evidence |
|---|---|
| Account cookie == account token | `dist/identity/interaction/login/ResolveLoginHandler.js:35-36` |
| Cookie: name `css-account`, `Path=/`, `SameSite=Lax`, no `HttpOnly`, no `Secure` | `dist/http/output/metadata/CookieMetadataWriter.js:39-42`, `config/ldp/metadata-parser/parsers/cookie.json:7` |
| `Authorization: CSS-Account-Token <v>` maps to the same metadata term as the cookie | `config/ldp/metadata-parser/parsers/authorization.json`, `dist/http/input/metadata/AuthorizationParser.js` |
| Cookie TTL 14 days, refreshed on use | `dist/identity/interaction/account/util/BaseCookieStore.js` |
| Pod create requires a non-empty name (`allowRoot: false`) | `config/identity/handler/routing/pod/create.json:22`, `dist/identity/interaction/pod/CreatePodHandler.js` |
| Duplicate pod → `409 Conflict`; names are **server-global** | `dist/pods/generate/TemplatedPodGenerator.js` (`ConflictHttpError`), `dist/identity/interaction/pod/util/BasePodStore.js` |
| `GET controls.account.pod` returns `{ pods: { <baseUrl>: <podResource> } }` | `CreatePodHandler.getView()` |
| No HTTP delete route for an account or a pod | no delete handler on `BasePodStore`; `DELETE .../account/{id}/` → 404, `DELETE .../pod/{id}/` → 400 (live, 2026-07-31) |
| Stock pod-root `.acl`: `<#public>` `foaf:Agent` `acl:Read` `accessTo <./>` **without** `acl:default`; `<#owner>` RWC with **both** `accessTo` and `default` | `templates/pod/wac/.acl.hbs` |
| `README.acl.hbs` hardcodes `acl:accessTo <./README>` | `templates/pod/wac/README.acl.hbs` |
| `profile/card.acl.hbs` comment: *"The WebID profile is readable by the public. This is required for discovery and verification, e.g. when checking identity providers."* | `templates/pod/wac/profile/card.acl.hbs` |
| Pod roots really are anonymously listable | live 2026-08-03: `alex/` `chabivdb/` `hyperscope_ndb/` all → `200` |
| A pod's `.acl` is **not** anonymously readable | live: `hyperscope_ndb/.acl` → `401` |
| `profile/card` is anonymously readable | live: → `200` |

### Traps (each one already cost a session)

1. **The authed `GET /.account/` must carry no `content-type` header.** With one present, CSS content-negotiates a controls-less body and `controls.account.*` comes back `undefined` — it looks exactly like "the endpoint does not exist" (7.4 live finding).
2. **Never import `pod-api.js` without a `?v=` cache-buster.** The VPS serves it stale otherwise. Currently `?v=7-4-1` at `index.html:712`.
3. **`registerAccount`'s empty-name guard stays.** `BasePodCreator` still computes `overwrite = !input.name`, and the site-root claim is prevented only by `allowRoot: false` in config. This is exactly the 7.1 incident that overwrote the site-root `.acl` with no backup in existence.
4. **`_writeAcl` always re-emits the owner block from `this.webId`.** That is what makes root-`Control` self-lockout structurally impossible. Do not add a code path that writes a root `.acl` without it.
5. **`acl:accessTo` targets differ by type:** container → `<./>`; file → `<./filename>`. A file written with `<./>` grants the whole parent folder.
6. **This is not Epic 5's `run_cascade(resource_uri, pod_name)`** (content deletion across CSS/Oxigraph/Qdrant). That operates on resources; this operates on a pod and CSS's own bookkeeping. Do not conflate them, do not wire them together.
7. **The account `logout` control invalidates the token/cookie immediately** — revoke credentials *before* signing out, or the user has to sign in again mid-flow.

### Reuse map — do not reinvent

- `backoffice/pod-api.js` — recursive `remove()` (L213), `countDescendants()` (L231), `_writeAcl()` (L310), `getAccess()` (L249), `_turtleStatements()` (L294), `_refuseIfUnknownAcl()` (L368), `registerAccount()` (L720, resumable, already does the full account→password→pod sequence). All live-verified in 7.1/7.3/7.4.
- 7.3's **two-tap delete** (`armDelete`/`confirmDelete`, 4 s auto-disarm, `index.html:885`) is the baseline to **exceed**, not to copy.
- 7.3's **DPoP verification harness** (`scratchpad/acltest/dpop.mjs`, zero-dependency `webcrypto` client-credentials session, no npm) is the live-test tool.
- `make vps-backup` + the nightly cron (`infra/vps/nightly-backup.sh`, 03:00, 7-day retention) is the operator safety net.
- Story 7.2's bind-mount pattern (`docker-compose.yml:14-21`) is exactly the mechanism Task 7 needs.

### Graph-confirmed coupling (graphify)

- `backoffice/pod-api.js` is a bridge node into Stories 7.1, 7.3 **and** 7.5 — every Epic 7 story lands in the same file.
- `RealBackend` (29 edges) and `DemoBackend` (22 edges) are both **god nodes**. Any new interface method must be added to both or the offline preview breaks (AC17).
- `_writeAcl()` ⟷ `_saveAclOrThrowControlError` flagged as semantically similar: **two ACL writers** exist, one in `backoffice/pod-api.js`, one in `mcp-connector/src/wacManager.js`. Real duplication, **explicitly out of scope here** (logged for a future consolidation) — but do not "fix" it by making one call the other; they run in different processes with different auth.

### Scope boundaries

- **Not** a server-wide orphan sweep. One pod, chosen by its owner, at a time.
- **Not** an admin console. No cross-account deletion, no operator UI.
- **Not** the effective-access resolver — walking up to resolve what a parent's `acl:default` grants is **Story 7.11**. This story shows the root's *own* `.acl` honestly; it does not answer "what does 'inherits from parent' mean" for children.
- **Not** roles, grant bundles, or read-receipt surfacing — Story 7.11.
- **Not** credential minting for the connector — Story 7.9, which depends on Task 1 landing.
- **Not** export/backup — Story 7.5, now sequenced last.
- **Not** GDPR workflow tooling (retention policy, support flows, deletion audit trail) — a pilot/production concern.

### Project Structure Notes

- Work lands in `backoffice/pod-api.js` + `backoffice/index.html` (the same two files 7.1/7.3/7.4 touched), plus `infra/css/templates/pod/base/README$.md.hbs` and a `docker-compose.yml` mount.
- No new dependencies. Inrupt libs stay pinned (`solid-client-authn-browser@2.3.0` / `solid-client@2.1.0`, both via `esm.sh` with `?bundle`); the npm-latest majors (5.0.0 / 3.0.0) are out of scope.
- The `index.html` template framework has **no `sc-if` invert** — use paired booleans (`credsLocked: !unlocked`) as the existing code does.
- No automated test framework exists in `backoffice/` — verification is live-pod round-trips, per every Epic 7 story. `node --check` on touched JS is the mechanical gate.
- Deploy asymmetry: `backoffice/` static files → `rsync` only; `docker-compose.yml` / `infra/css/` template mounts → `docker compose up -d --force-recreate`.

### Effort note

Lower than the AC count suggests. The recursive-delete engine, descendant count, ACL writer/parser, owner-block guard, and DPoP harness **all already exist**. Task 1 is a **net code deletion**. The genuinely new work is: pod create/list (two thin methods), the root row, the protected-resource predicate, the ceremony UI, the README template, and live verification.

### References

- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-08-03.md] — the four findings, the merge rationale, execution order
- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.10] — epic-level scope this story expands
- [Source: _bmad-output/implementation-artifacts/7-7-delete-my-pod.md] — superseded; AC8–AC12 and the deletion Dev Notes carry over from it
- [Source: _bmad-output/implementation-artifacts/7-3-my-things-crud-acl-fix.md] — recursive delete, root-Control guard, two-tap delete, DPoP harness
- [Source: _bmad-output/implementation-artifacts/7-4-apps-and-credentials.md] — the account-token gate this story removes; the no-content-type trap
- [Source: _bmad-output/implementation-artifacts/7-1-backoffice-deploy-real-account-registration.md] — orphan-account root cause, `.internal/accounts/` layout, root-ACL incident, backup gap
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — live ACL/portability audit; "Resolved: pod/account deletion gap" (needs re-pointing at 7.10)
- [Source: docs/team-onboarding.md#Walkthrough] — steps (b)/(c) that this story gives a home
- [Source: _bmad-output/planning-artifacts/architecture.md#BP-6] — identity/role model; the honesty constraint carried into 7.11

---

## Open questions for Nicolas — resolved during dev/review (2026-08-03)

1. **AC5 root row placement** — **resolved: pinned row at the top of "My things"**, not a separate panel. Implemented in `loadFolder([])`.
2. **Task 5.4** — **resolved: skip `profile/card`, don't delete-last.** A pod that keeps its WebID stays a working, describable identity; one that's lost it isn't.
3. **Task 6.4** — **resolved: defer** the operator-side `AccountStore` cascade script. 29 orphan records are inert; build only if that becomes an operational problem.

## Known rough edges, carried forward (not blocking, per Nicolas 2026-08-03: "good enough to conclude this story")

- Multi-pod UX is functional but not smooth: pods owned by a different WebID (created before the `settings.webId` fix, or never re-owned) can only be linked out to CSS's own stock pages, not managed inline. Acceptable for now; revisit if multi-pod usage grows past occasional throwaway pods.
- No in-app "mark pod for deletion → notify operator" flow (Nicolas's suggestion, 2026-08-03) — logged in `deferred-work.md`, ties to the deferred Task 6.4 script. No admin-notification channel exists yet.
- The account-edit/owners links are correct but plain (raw CSS stock pages, unstyled beyond 7.2's global restyle) — fine as an escape hatch, not a polished flow.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

None — no automated test framework in `backoffice/`; verification was `node --check` on both touched JS files (clean) plus manual reasoning against the Dev Notes' verified CSS facts. Live/destructive verification (Task 8) not run this session — see Completion Notes.

### Completion Notes List

- All 9 tasks complete. Live verification (Task 8) run against `pod.nicolasdb.eu` after Nicolas's go-ahead: backup taken, deploy done (targeted rsync + `docker compose up -d --force-recreate community-solid-server`, came up healthy), throwaway account+pod created/populated/delete-tested/independently-verified-empty, root-ACL and README content confirmed live exactly as the Dev Notes predicted, AC10 (no account/pod delete route) re-confirmed with a live `404`. One item explicitly deferred to Nicolas: full browser-driven UI regression on his real `/nicolas` pod — this agent has no browser session/cookie for his account and should not try to obtain one; protocol-level checks (root/profile reachability, credential mint+revoke round-trip) all pass.
- Task 1 was a net code deletion as predicted: `accountLogin`, `_acctToken`, `_acctAuth`, the unlock-gate markup, and the email/password state fields are gone from both `pod-api.js` and `index.html`. Account session now rides `credentials:'include'` against the `css-account` cookie, resolved lazily via `_accountControls()` and cached per page session; a 401 clears the cache so the UI re-resolves rather than retrying a dead session.
- AC2's honest-degradation state (`credsSignedOut`) replaces the old password prompt; it never renders an empty pod/credential list and never reintroduces a password field.
- Pod create/list (Task 2) is two thin `RealBackend` methods plus `DemoBackend` parity, including a scripted `"taken"` name so the 409/name-availability copy is reviewable offline.
- The pod-root row (Task 3) is a synthetic entry prepended in `loadFolder([])` only — it carries a real live ACL read through the existing `getAccess()`/badge machinery, gets no rename/delete affordances, and its `open()` is a no-op so it can't be "entered" as a child folder.
- Protected-resource guardrails (Task 4) are enforced in four places, not just the row renderer: `armDelete`, `deleteThing`, `startRename`, and the editor's rename/delete buttons — all consult the same `PROTECTED` predicate (root, `profile/`, `profile/card`), so there is one source of truth, not four independent checks that could drift.
- Deletion engine (Task 5): `deletePodContents()` reuses the existing `remove()` per top-level child — no second traversal — and reports `{ok|skipped|error}` per item. **Decision recorded in `pod-api.js`:** protected resources are skipped, not deleted-last, because a pod that keeps its WebID document stays a working, describable identity.
- Delete ceremony (Task 6): two-stage modal (backup acknowledgement → type-the-pod-name-to-confirm-with-live-count), no auto-arm timer anywhere in this flow (unlike 7.3's file two-tap), Enter key explicitly prevented from submitting, Confirm button stays `disabled` until the typed name matches exactly. Honest survivor copy (WebID + account shell) is shown before the irreversible action, not after.
- README template (Task 7): kept the resource name `README` unchanged specifically so `README.acl.hbs`'s hardcoded `acl:accessTo <./README>` needs no override — the simplest-correct path the story called out. Content re-verifies the stock template's real variables (`webId`, `oidcIssuer`, `base.path`, `name`, `email`) rather than guessing new ones.
- Bumped the `pod-api.js?v=` cache-buster to `7-10-1` (was `7-4-1`) since that's a static, non-destructive change independent of the live-verification HALT.
- Epic bookkeeping (Task 9): `deferred-work.md`'s "pod/account deletion gap" entry re-pointed at 7.10 with a dated section; `docs/team-onboarding.md` deliberately left untouched per the story's own instruction, with the pending edit noted in `deferred-work.md` instead of in the doc itself.

### File List

- `backoffice/pod-api.js` — modified (Task 1 net deletion of account-login/token plumbing; Task 2 `listPods`/`createPod`; Task 5 `deletePodContents`/`countDescendants` DemoBackend parity)
- `backoffice/index.html` — modified (Tasks 1, 2, 3, 4, 6: state, render mappings, markup, cache-buster bump)
- `infra/css/templates/pod/base/README$.md.hbs` — added (Task 7)
- `docker-compose.yml` — modified (Task 7 bind-mount)
- `_bmad-output/implementation-artifacts/7-10-account-and-pod-lifecycle.md` — modified (task checkboxes, Dev Agent Record)
- `_bmad-output/implementation-artifacts/deferred-work.md` — modified (Task 9 bookkeeping)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — modified (story marked in-progress)

### Review Findings

- [x] [Review][Patch] `countDescendants()` counts protected resources that `deletePodContents()` skips, inflating the delete ceremony's "exact count" (AC9) [backoffice/pod-api.js:231,240]
- [x] [Review][Patch] Pods section not gated on account-session state; SESSION_EXPIRED silently leaves a stale/empty pod list (AC2) [backoffice/index.html:516; backoffice/pod-api.js loadPods]
- [x] [Review][Patch] `_accountControls()` maps any non-2xx (incl. 5xx) to SESSION_EXPIRED, misdirecting users to re-auth on backend errors [backoffice/pod-api.js]
- [x] [Review][Patch] Ceremony's ✕ Close button doesn't abort in-flight `deletePodContents()` — deletion continues after user believes it's cancelled [backoffice/index.html:566, podDeleteConfirm]
- [x] [Review][Patch] `podOwned` flashes false for the user's own active pod before the async Control-check resolves, briefly hiding the Wipe button on their own pod [backoffice/index.html loadPods/podItems]
- [x] [Review][Patch] Wiping the active pod's contents doesn't reconcile an open editor view on a just-deleted file — stale content, risk of silent recreate on save [backoffice/index.html podDeleteConfirm]
- [x] [Review][Defer] Ownership gate (`isOwnedPod`) trusts `getAccess()` throw-on-fail behavior not verified in this diff [backoffice/index.html loadPods] — deferred, pre-existing

## Change Log

- 2026-08-03 — Tasks 1–7, 9 implemented (account-session cookie migration, pod create/list, pod-root row, protected-resource guardrails, whole-pod deletion engine + ceremony, welcome README template, epic bookkeeping).
- 2026-08-03 — Task 8 live verification, run after Nicolas's go-ahead: `make vps-backup`, targeted deploy (rsync + CSS force-recreate), throwaway account/pod create→populate→delete→independently-verify-empty, root ACL + README content confirmed live, AC10 re-confirmed (`404` on account delete). Full browser UI regression on `/nicolas` left for Nicolas to run himself (no access to his session). Status → review.
- 2026-08-03 — **Bug found by Nicolas testing live** on a second pod (`test-xpod`, not his active session's pod): confirming pod-delete 403'd on both `profile/` and `README`. Root cause: `PROTECTED`/the delete ceremony's protected-check was anchored to `this.root()` (the **active session's** pod) instead of the **pod actually being deleted** — a non-issue when they're the same pod, but silently wrong otherwise, and moot anyway because WAC ownership is per-WebID and each pod gets its own WebID at creation, so the active session structurally cannot act on a pod it isn't signed into. Fixed: (1) protected-check in `podDeleteConfirm` now computed relative to the delete target, not the active root, (2) `startPodDelete` refuses to open the ceremony for any pod that isn't the active one, with a toast explaining why, (3) the pod list itself now shows a disabled state instead of a Delete button for pods it can't manage. Redeployed (`backoffice/` rsync, no CSS restart needed — static-file-only change).
- 2026-08-03 — **UX follow-up, Nicolas's direct feedback:** listing every account pod with a dead "not signed in here" label was confusing, and the pod action was mislabeled — "Delete…" implies the whole pod goes away, when it only ever wipes contents (AC10's honest limit: the account/pod shell has no HTTP delete route, by design). Fixed: (1) renamed the affordance throughout to "Wipe contents…" / "Wipe pod contents" / "Permanently wipe contents" so the label matches what actually happens; (2) added `RealBackend.accountEditUrl()` (from `controls.html.account.account`) and a "Manage account & identities on CSS ↗" link in the Pods section — opens CSS's own stock account page (Pods + Registered WebIDs, with add/delete), which is what Nicolas had been reaching via a sign-out/sign-in workaround; (3) pods this session can't manage now link straight to that pod's own CSS "owners" page (`resource`, screenshot-confirmed to have an "Add owner" field) instead of a dead-end label, so adding yourself as owner — the actual fix for a pre-existing pod like `test-xpod` — is one click away. Nicolas also floated a "mark pod for deletion → notify operator" flow as an alternative to the stock-page link for pods you can't wipe yourself; logged in `deferred-work.md` (ties to Task 6.4's deferred operator-cascade script) rather than built this session — no admin-notification channel exists yet. Redeployed, `pod-api.js?v=` → `7-10-3`.
- 2026-08-03 — **Follow-up architecture fix, same root cause.** Nicolas correctly pushed back: a "create another pod" feature whose pods can never be deleted (or managed) isn't actually done. Read `CreatePodHandler.js`/`BasePodCreator.js` live on the VPS container: `CreatePodHandler`'s schema accepts an optional `settings.webId`, and if provided, `BasePodCreator` uses **that** WebID as the new pod's owner instead of minting a fresh one — `createPod()` was omitting it, so every additional pod got its own separate, never-signed-into identity, which is *why* it could never be managed afterward (not a bug in the delete path — the pod was unowned by the active session from the moment it was created). Fixed: `RealBackend.createPod()` now passes `settings: { webId: this.webId }` so every pod an account creates through this app shares one identity end to end. Ownership gating in the pod list (Delete button vs. disabled state) changed from a URL-equality guess (`isActivePod`, comparing to `this.root()`) to a live check (`isOwnedPod`, via `podOwned` populated in `loadPods()` from an authenticated `.acl` read — Control-only, so it fails exactly for pods with a different owner). **Live-verified 2026-08-03:** minted a second pod (`zzztest7102026b`) under the existing throwaway account with `settings.webId` set to the account's existing pod's WebID; the create response echoed that same WebID back (not a new one); a fresh client-credential for that WebID successfully read `zzztest7102026b/.acl` with `200` (Control-level access), confirming the new pod is fully owned by, and therefore deletable from, the original identity. Test credential revoked after. Redeployed (`backoffice/` rsync; `pod-api.js?v=` bumped to `7-10-2`).
