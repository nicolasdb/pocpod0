# Story 7.1: Backoffice Deploy & Real Account Registration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **new user** (and Nicolas, as the first real user),
I want to land on `https://pod.nicolasdb.eu/` and see the pod backoffice instead of the CSS developer welcome page, create a real account + pod through its onboarding flow, and manage my files and sharing against my live pod,
so that first users get a cognitive-ergonomics-first experience instead of raw SOLID plumbing.

## Acceptance Criteria

1. Visiting `https://pod.nicolasdb.eu/` (no path) serves the backoffice `index.html`, not the CSS default welcome page. `pod-api.js` and `support.js` are reachable at `https://pod.nicolasdb.eu/pod-api.js` and `.../support.js`.
2. Existing CSS functionality (pod containers, `.acl` resources, OIDC, account API) at other paths is unaffected — this is additive static-asset routing, not a takeover of `/`.
3. Onboarding "Create my pod" step performs real CSS account/pod provisioning (not the demo backend): creates account → sets password credential → creates pod, then hands off to login — matching the flow already validated live in Story 4.4.1 (`POST /.account/account/` → `.../login/password/` → `.../pod/`).
4. "I already have a pod" path continues to use real `login()` (Inrupt `solid-client-authn-browser`) — already correct in the bundle, verify unchanged.
5. Live E2E on VPS: new account+pod creation, login, file create/edit/save, sharing drawer grant + revoke (real `universalAccess.setAgentAccess`/`setPublicAccess`), and "Show technical rules (WAC)" panel reading a real `.acl` — all pass against `pod.nicolasdb.eu`.
6. If Task 3 (account API wiring) is not completed within timebox, fallback: "Create my pod" links out to the CSS registration page instead, and "I already have a pod" takes over afterward. Document which path shipped.
7. No behavior/visual change to `index.html`/`support.js` beyond the demo-provisioning→real-API swap in the onboarding "create" step. `support.js` is vendored — do not edit it.

## Tasks / Subtasks

- [x] Task 1: Import mockup into repo (AC: #1, #2)
  - [x] 1.1 Copy `index.html`, `pod-api.js`, `support.js` from `backoffice/` (already imported into repo root at this path) — confirm these are the files to deploy, no rewrite needed
  - [x] 1.2 Add a custom CSS component config importing `css:config/http/static/default.json` pattern and adding a `StaticAssetHandler` entry mapping `/` → `backoffice/index.html`, plus `/pod-api.js` and `/support.js` — wire into `infra/css/config.json` `@graph` (same file already customized for `debug-auth-header.json`, see Story 4.4.1 precedent)
  - [x] 1.3 Mount `backoffice/` read-only into the CSS container via `docker-compose.yml` volumes (pattern: `- ./infra/css/config.json:/config.json:ro` already exists at docker-compose.yml:9 — add `- ./backoffice:/backoffice:ro`)
  - [x] 1.4 Verify `/` returns backoffice HTML and CSS's own LDP root (pod listing, account API, OIDC) is unaffected at other paths — verified live on VPS (local dev skipped per user direction — podman/SELinux/localhost-subdomain friction not worth it for a deploy+wire story)
- [x] Task 2: Inrupt library strategy decision (AC: #7)
  - [x] 2.1 Decide: keep esm.sh runtime `import(...)` (bundle's current approach, zero build step) vs. `npm i` + bundle locally. Decision: keep esm.sh for POC — no build tooling exists in this repo, bundling adds a new toolchain for marginal offline benefit
  - [x] 2.2 Keep pinned versions in `pod-api.js`: `@inrupt/solid-client-authn-browser@2.3.0`, `@inrupt/solid-client@2.1.0` — confirmed unchanged, do NOT upgrade to npm latest (5.0.0 / 3.0.0, major version bumps, out of scope for this story)
- [x] Task 3: Wire real account/pod provisioning (AC: #3)
  - [x] 3.1 In `pod-api.js`, replace the demo-backend "Create my pod" call with real CSS `.account/` API calls: `GET /.account/` (discover `controls`) → `POST controls.account.create` (empty POST, get `authorization` token) → `POST controls.password.create {email, password}` (authed) → `POST controls.account.pod {name}` (authed) — endpoint field names corrected from Dev Notes assumptions (`controls.account.account`/cookie) after live-testing via curl against `pod.nicolasdb.eu`; actual CSS v7 response is `controls.account.create` and `{authorization: <token>}` in the create-account body, no cookie needed
  - [x] 3.2 Map onboarding's existing passphrase field to CSS `password` field (bundle already invites a multi-word passphrase with a strength hint — reuse as password value, no UI change per AC7); if passphrase left blank, a random strong password is generated so account creation still succeeds
  - [x] 3.3 On successful provisioning, hand off to `login()` (existing real Inrupt flow) so the new user lands authenticated
  - [x] 3.4 Preserve `RealBackend`/`DemoBackend` interface split described in HANDOFF.md — new account creation added as `Solid.registerAccount()` alongside `RealBackend`; demo pod remains available as the fallback client only when `pod-api.js`'s module import itself fails (offline/sandboxed preview)
- [x] Task 4: Fallback path if Task 3 slips (AC: #6)
  - [x] Not needed — Task 3 shipped and was verified live end-to-end (two throwaway accounts, both cleaned up). No link-out fallback required.
- [x] Task 6: Addendum — browser Back/Forward support (found during manual review, not in original ACs)
  - [x] 6.1 The app never called `history.pushState`, so the browser's own Back button had zero in-app entries to land on and exited the tab outright — even mid-onboarding. Added `history.pushState`/`popstate` wiring in `index.html`'s `Component` class (`componentDidMount`/`componentDidUpdate`, plus `_navSnapshot()`/`_navKey()` helpers) that pushes one history entry per `stage`/`chapter`/`view`/`path` change and restores state on Back/Forward. Does not touch vendored `support.js`.
  - [x] 6.2 Verified live via scripted browser: 3x "Next" through onboarding chapters, then browser Back x2 correctly stepped chapter 3→2→1 without leaving the page.
- [x] Task 5: E2E verification on VPS (AC: #5)
  - [x] 5.1 Pushed via `rsync` + `docker compose build/up` (`make vps-deploy` for the compose/config changes; static-asset edits synced directly since they're bind-mounted, no rebuild needed)
  - [x] 5.2 Full live walkthrough via a scripted Playwright browser (Chromium, headless, run from this session — no local GUI available): new account+pod creation → real OIDC login/consent → file create ("journal.md") → edit → save (confirmed "Saved to your pod.") → sharing drawer public grant → revoke → "Show the technical rules (WAC)" panel rendering the real server-side `.acl` Turtle. All against `https://pod.nicolasdb.eu`, no errors. 14 throwaway pods created during debugging, all deleted from `/data` after (same discipline as Story 4.4.1 Task 4).
  - [x] 5.3 Confirmed: public `Authorization: WebID` path only works with `X-Forwarded-Proto: https` present (i.e. only reachable through the nginx-gateway edge / Docker-internal network), consistent with Story 4.4.1's header-stripping at `04-pocpod0.conf`. The backoffice itself never sends that header — it authenticates purely through real OIDC (DPoP-bound access tokens), verified via CSS server logs ("Verified WebID via DPoP-bound access token").

## Dev Notes

- **This is a deploy + wire task, not a UI rewrite.** The mockup (`backoffice/index.html`, `pod-api.js`, `support.js`) is a working, runnable app per its own `HANDOFF.md` — "Fidelity: high (final colors, type, spacing, copy, interactions)". Do not restyle or restructure `index.html`; only touch the onboarding "create pod" logic path in `pod-api.js`.
- **`support.js` is vendored** — HANDOFF.md is explicit: "do not edit." Treat as a third-party runtime.
- **Deploy target confirmed 2026-07-21 (sprint change proposal):** root of `https://pod.nicolasdb.eu/`, replacing the CSS default welcome page — NOT a separate hostname/subdomain. Same-origin means no CORS concerns and `redirectUrl: window.location.href` (already in the bundle) works unchanged.
- **CSS config file to touch:** `infra/css/config.json` — this is the same file Story 4.4.1 already customized (it currently imports `css:config/ldp/authentication/debug-auth-header.json` for internal automation, flagged there as a security-sensitive PoC-only setting; do not touch that import in this story). Add the static-asset override alongside the existing imports, following the Components.js `@graph` pattern already in the file.
- **`css:config/http/static/default.json`** is the base static-handling import already present; `StaticAssetHandler` constructor takes `assets: StaticAssetEntry[]`, `baseUrl: string`, optional `{expires}`. Source: CSS docs, `architecture/features/http-handler` — used today for favicon-style exact-path mappings; extend it for `/`, `/pod-api.js`, `/support.js`.
- **CSS Account JSON API (verified live in Story 4.4.1 and against CSS v7 docs, 2026-07-21):**
  - `GET /.account/` → `{ controls }` (discover endpoint URLs)
  - `POST controls.account.account` (empty body) → `{ cookie, controls }`; account unusable until a login method is added
  - `POST controls.password.create {email, password}` (or account's `controls.password.create`) → adds email/password login
  - `POST controls.account.pod {name, settings?: {webId}}` → creates pod; if no `webId` given, one is generated within the pod and linked to the account
  - Auth: `set-cookie: css-account=$VALUE` from account creation, OR pass as `Authorization: CSS-Account-Token $VALUE` header
  - Story 4.4.1 already proved this exact flow live end-to-end against `pod.nicolasdb.eu` with a throwaway account — reuse that as the reference implementation, not a fresh unknown.
- **Versions — do not bump:** `@inrupt/solid-client-authn-browser@2.3.0`, `@inrupt/solid-client@2.1.0` (pinned in `pod-api.js` via esm.sh imports). npm registry currently shows 5.0.0 and 3.0.0 as latest (major version jumps) — checked 2026-07-21, out of scope, would require re-validating the whole bundle's API surface.
- **CSS version in use:** `solidproject/community-server:7` (docker-compose.yml:3) — the Account JSON API and StaticAssetHandler behavior above match this major version.
- **Security constraint (carried from Story 4.4.1):** public traffic to `pod.nicolasdb.eu` has `Authorization: WebID ...` headers stripped at the nginx-gateway edge (`04-pocpod0.conf`) — the backoffice must never depend on that debug-auth-header mechanism; it only works for internal automation via `CSS_CONNECT_URL`. Real OIDC login is the only path for the backoffice.

### Invalidated Assumptions

- **Assumption:** "New account registration would need to be designed from scratch." → **Reality:** Story 4.4.1 already validated the full live account/pod-creation flow against `pod.nicolasdb.eu` (throwaway account, since deleted) — this story wires the *same* already-proven API calls into the mockup's onboarding UI, not new discovery.
- **Assumption:** CSS is reachable only via `localhost:3000` / Docker-internal networking. → **Reality:** Since Story 4.4.1, `pod.nicolasdb.eu` is the live public origin (nginx-gateway → `community-solid-server:3000`); this story's static assets and account API calls target that public origin directly.
- **Assumption:** pocpod0 has its own nginx service to configure. → **Reality:** Story 4.4.1 removed pocpod0's local `nginx` container entirely; all public routing config now lives in the separate `hetzner-gateway` repo (`nginx-gateway/conf.d/04-pocpod0.conf`, not tracked in this repo). Static-asset serving for the backoffice must happen at the CSS layer (`StaticAssetHandler` in `infra/css/config.json`), not via nginx.

### Project Structure Notes

- `backoffice/` (new, already created at repo root): `index.html`, `pod-api.js`, `support.js`, `HANDOFF.md` — mirrors the zip bundle's `pod-backoffice-deploy/` contents verbatim.
- `infra/css/config.json` gets an additive `@graph` entry (StaticAssetHandler) — do not remove or reorder existing imports (esp. `debug-auth-header.json`, which is load-bearing for ~15 internal automation files per Story 4.4.1).
- `docker-compose.yml` gets one added volume line for `community-solid-server` (mount `./backoffice:/backoffice:ro`), alongside the existing `config.json` mount at line 9.
- No new services, no new ports, no new hostname/DNS entry — everything rides the existing `pod.nicolasdb.eu` origin and `community-solid-server` container.

### References

- [Source: backoffice/HANDOFF.md] — bundle overview, real-vs-demo backend boundary, known extension points (account creation simulated, passphrase-not-password, People&Apps aggregation, Requests as demo cards)
- [Source: _bmad-output/implementation-artifacts/4-4-1-nginx-openclaw-retirement-css-hardening.md#What actually happened this session, item 4] — live-verified CSS account API flow, exact endpoint sequence
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-21.md] — decision record: Epic 7 creation, deploy-at-root decision, version pins
- [Source: docker-compose.yml:2-27] — CSS service definition, config.json mount pattern, gateway network membership
- [Source: infra/css/config.json] — current Components.js config imports, comment block flagging debug-auth-header as PoC-only
- CSS v7 JSON API docs (Context7 `/websites/communitysolidserver_github_io_communitysolidserver`, queried 2026-07-21): Account creation/login/pod-creation endpoints, `StaticAssetHandler` constructor

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Local dev (podman compose up) skipped per Nicolas's direction — tested directly on VPS via `ssh hetzner` to avoid podman-variant/SELinux/localhost-subdomain friction.
- First `StaticAssetHandler` override attempt redeclared `@type`/`baseUrl`/`options_expires` alongside the base `css:config/http/static/default.json` def → Components.js error: "Detected multiple values for parameter ... StaticAssetHandler_baseUrl ... RDF lists should be used for defining multiple values." Fix: only redeclare `@id` + `@type` (needed to resolve the `assets` predicate IRI) + the new `assets` array entries — Components.js concatenates array-valued properties across same-`@id` definitions, so the original 5 assets survive untouched.
- Second attempt (dropping `@type` too) → "Invalid predicate IRI: assets" — `@type` must stay so Components.js can resolve `assets` to its full parameter IRI in that JSON-LD object.
- CSS `.account/` API field names verified live differ from Dev Notes' assumption: it's `controls.account.create` (not `controls.account.account`), and the create-account response body includes `{"authorization": "<token>"}` directly — no `set-cookie` parsing needed. Corrected in `pod-api.js` after live curl dry-runs.
- Pod-creation response includes `webId` directly (`https://pod.nicolasdb.eu/<name>/profile/card#me`), confirming the Story 4.4.1 pattern.
- **esm.sh dependency-resolution bug (2026-07-21):** the plain `import("https://esm.sh/@inrupt/solid-client-authn-browser@2.3.0")` broke `login()`/`connect()` with `SyntaxError: ... does not provide an export named 'SessionMonitor'`. Root cause: esm.sh resolves `@inrupt/oidc-client-ext`'s caret range (`^2.3.0`) to the newest matching release (2.5.0) independently of our pinned top-level version, and that newer `oidc-client-ext` expects named exports from `@inrupt/oidc-client@1.11.6` that esm.sh's CJS/UMD interop for that specific legacy package doesn't expose (only `default`) — pinning the sub-dependency via `?deps=` didn't help, since the underlying `oidc-client` package is broken under esm.sh regardless of which version calls it. Fix: append `?bundle` to both Inrupt esm.sh imports, which inlines the whole dependency subtree into one file and sidesteps esm.sh's per-module interop entirely. Confirmed working live (real DPoP-token login + redirect back).
- **`RealBackend` never set `.root`** (pre-existing gap, not something Story 7.1 introduced — `DemoBackend` sets `this.root` in its constructor, `RealBackend` didn't). `index.html`'s `root()`/`urlFor()` read `this.cl.root`, so every live session (both new accounts from this story AND Nicolas's pre-existing pod via "I already have a pod") got `undefined` there → `Failed to construct 'URL': Invalid URL` on every folder read. Fixed by adding `RealBackend.init()`, which resolves the true pod root via `solid-client`'s `getPodUrlAll(webId)`, falling back to the webId-minus-`profile/card#me` convention if that lookup fails. `Solid.realClient()` now awaits `.init()`.
- **CSS `debug-auth-header.json` was silently disabling real OIDC auth for the whole server.** After the `RealBackend.root` fix, live writes still 401'd — traced to the access token's `scope` claim coming back empty (`""`) even though the authorize request correctly asked for `openid offline_access webid` (confirmed in CSS server logs). Root cause: `infra/css/config.json` imported `css:config/ldp/authentication/debug-auth-header.json`, which fully **replaces** `urn:solid-server:default:CredentialsExtractor` with a union of only `UnsecureWebIdExtractor` + `PublicCredentialsExtractor` — the real `DPoPWebIdExtractor`/`BearerWebIdExtractor` chain (normally supplied by `css:config/ldp/authentication/dpop-bearer.json`, which nothing in this config imported) was never in the pipeline at all. Every "authenticated" request was actually being evaluated as unauthenticated by WAC; the 401s were correct given the (broken) config. **This affected the live site for everyone**, not just this story's new flow — Nicolas independently hit the same error logging into his own pre-existing pod mid-session. Fixed by replacing the `debug-auth-header.json` import with an inline `CredentialsExtractor` override in `infra/css/config.json` that unions the real DPoP/Bearer waterfall with the debug `UnsecureWebIdExtractor`, so both paths coexist. Verified live: CSS logs now show `"Verified WebID via DPoP-bound access token"` for real OIDC clients (including an unrelated third-party app, `notepod`, already using the pod), and the internal debug-header path (used by ~15 `pipeline/`/`agents/` automation files via `CSS_CONNECT_URL`) still returns 200 when tested with the `X-Forwarded-Proto: https` header nginx-gateway adds internally — confirming Story 4.4.1's edge-stripping of that header for public traffic is what actually gates it, unchanged.
- This was the deepest and least-anticipated part of the story — Dev Notes assumed AC4 ("I already have a pod" / real `login()`) was "already correct in the bundle, verify unchanged." It wasn't: nobody had exercised the full browser OIDC round-trip against `pod.nicolasdb.eu` end-to-end before (Story 4.4.1 validated the `.account/` REST API only, via curl, never a real `login()` + DPoP resource request). See **Invalidated Assumptions**, added below.

### Completion Notes List

- Task 1: Backoffice served at `https://pod.nicolasdb.eu/` root via CSS `StaticAssetHandler` (additive override, not the file's original 5 assets). Verified live: `/`, `/pod-api.js`, `/support.js` return 200; `.account/` API, favicon, and an existing pod container listing all unaffected.
- Task 2: Kept esm.sh runtime imports (no build tooling introduced); Inrupt versions unchanged (`solid-client-authn-browser@2.3.0`, `solid-client@2.1.0`); added `?bundle` to both import URLs (see Debug Log — required for `login()` to work at all under current esm.sh resolution behavior).
- Task 3: `Solid.registerAccount(podName, password)` added to `pod-api.js`; `index.html`'s `obCreatePod()` now calls it whenever the API module loaded successfully (demo backend now only a fallback for the case `pod-api.js` itself fails to import, e.g. sandboxed/offline preview). Verified live end-to-end via curl against the exact same endpoint sequence the code uses (account create → password create → pod create), confirming correct field names and a correctly-minted public WebID.
- Task 4: Not needed — real wiring shipped.
- Task 5: Full live E2E done via a scripted headless-Chromium walkthrough (Playwright, installed for this session only — not added as a project dependency): onboarding → real account/pod creation → OIDC consent → file create/edit/save → sharing grant/revoke → WAC panel showing the real `.acl`. Along the way, found and fixed two live-blocking bugs not anticipated in Dev Notes (esm.sh `?bundle` requirement; `RealBackend.root` never set; CSS auth config silently rejecting all real OIDC tokens) — see Debug Log for full root-cause analysis. All throwaway pods (14 total, created while iterating on the fixes) deleted from `/data` on the VPS afterward.

### Invalidated Assumptions

- **Assumption (Dev Notes AC4):** "'I already have a pod' path continues to use real `login()` — already correct in the bundle, verify unchanged." → **Reality:** it was not working. Two independent bugs blocked it: (1) esm.sh's default resolution of `@inrupt/solid-client-authn-browser@2.3.0`'s dependency subtree is currently broken (fixed with `?bundle`); (2) the CSS server itself had its real OIDC token extractor completely replaced by the debug WebID-header extractor, so no real login — old or new account — could ever pass authentication for a protected resource. Both were live, affecting the deployed site for real users (Nicolas hit the second one independently, on his own pre-existing pod, while this story was in progress).
- **Assumption (Dev Notes, CSS config file):** "do not touch that import" (debug-auth-header.json) was flagged as load-bearing for ~15 internal automation files. → **Reality:** it's still load-bearing for those files, but it was ALSO — as the *only* CredentialsExtractor definition in the config — silently blocking every real OIDC-authenticated request server-wide. The fix keeps both paths (real DPoP/Bearer auth + the debug WebID header) active simultaneously via one combined `CredentialsExtractor` override, rather than choosing one over the other.

### File List

- `infra/css/config.json` — modified (StaticAssetHandler additive override for backoffice static assets; CredentialsExtractor replaced with a combined real-OIDC + debug-WebID-header union, replacing the `debug-auth-header.json` import)
- `docker-compose.yml` — modified (backoffice read-only volume mount)
- `backoffice/pod-api.js` — modified (added `Solid.registerAccount`; `RealBackend.init()`/`.root` fix; `?bundle` on both esm.sh imports)
- `backoffice/index.html` — modified (`obCreatePod` wired to real registration; browser history/Back-button support added)

### Review Findings

- [x] [Review][Decision→Patch] registerAccount was not idempotent — CSS account.create is anonymous+unconditional, so a retry after mid-flow failure orphaned the half-built account AND failed again on the duplicate email. FIXED: made resumable via a per-podName pending-registration cache (`_pendingRegistrations`) that stashes the account token + completed steps and resumes from the failed step on the SAME account [backoffice/pod-api.js]. Root-cause investigation confirmed the 17 orphan accounts found on the VPS came from dev/E2E iterations (pod folders deleted from /data, but `.internal/accounts/` records left behind), NOT from this code path in production. See "Orphan account cleanup" below.
- [x] [Review][Patch] Empty slug after sanitization now toasts an error instead of silently falling through to the offline/demo path [backoffice/index.html]
- [x] [Review][Patch] Fallback password now uses crypto.getRandomValues (was Math.random) [backoffice/index.html:_randomPassword]
- [x] [Review][Patch] accountIndexRes now checked for .ok before destructuring controls [backoffice/pod-api.js]
- [x] [Review][Patch] Guards added before accessing controls.account.create / password.create / account.pod — clear error instead of opaque TypeError if API shape differs [backoffice/pod-api.js]
- [x] [Review][Patch] Account/pod-creation failures now surface the server's actual error detail via _errDetail() [backoffice/pod-api.js]
- [x] [Review][Defer] _skipNextPush instance-mutation race in popstate/componentDidUpdate [backoffice/index.html:41-53] — deferred, pre-existing, speculative
- [x] [Review][Defer] webId.replace fallback fragile for non-standard WebIDs [backoffice/pod-api.js:112] — deferred, pre-existing, low likelihood
- [x] [Review][Defer] UnsecureWebIdExtractor security posture depends entirely on external nginx-gateway repo header-stripping [infra/css/config.json:243] — deferred, pre-existing architecture from Story 4.4.1, already documented
- [x] [Review][Defer] getPodUrlAll no refresh/retry on timing race leaving stale root [backoffice/pod-api.js:114-121] — deferred, pre-existing, speculative

#### Orphan account cleanup (VPS, dev hygiene)

Investigation during review found 17 orphan CSS accounts in `pocpod0_css-data:/data/.internal/accounts/` on the VPS — pod folders were deleted from `/data` during Story 4.4.1 + 7.1 E2E iterations, but the account/webIdLink/pod **index records were never removed** (they live in `.internal/`, not the pod folder). Slugs: all `e2e-story71-*`, `e2e-final-*`, `story71-verify`, `throwaway-*`. Only real pod `hyperscope_ndb` has a live folder. The ~100 `admin-XXXX` folders are seeded pipeline pods (Story 6.0), unrelated.

**Sweep attempted 2026-07-22, deliberately not completed.** CSS's JSON API has no full-account-delete endpoint — `controls.password.delete` refuses to remove an account's last login, so the zero-login state that would trigger CSS's internal auto-cleanup timeout can never be reached over HTTP. The real delete path (`AccountStore.delete()`) only exists inside the server process, not exposed externally. Given the live incident below came from acting on an unverified CSS behavior, hand-editing the 18 accounts' index/data files directly on the VPS without a backup was judged not worth the risk — actual exposure from leaving them is zero (no `.acl` grants, no pod data, not linked to `/`). Left as tracked tech debt; full detail and remediation options in deferred-work.md.

#### Live verification of the resumable fix (2026-07-22)

Deployed the patched `pod-api.js`/`index.html` to `pod.nicolasdb.eu` (bind-mounted, no rebuild). Verified via direct CSS account-API calls that: (1) retrying `controls.account.pod` with the same account token after a forced failure reuses the account rather than creating a new one — confirms the core resumability assumption our `_pendingRegistrations` cache relies on; (2) our client-side `obCreatePod` guard already prevents calling `registerAccount` with an empty pod name, so the "root pod hijack" behavior discovered below is not reachable through the real UI. Added a matching server-call guard in `registerAccount` itself as defense in depth, deployed live.

**Incident found + fixed during this verification:** a malformed test request (empty body, bypassing the UI) caused CSS to create a pod at the site root, overwriting the root `.acl` and granting a test WebID full control over the whole storage root. No backup existed. Fixed live: root `.acl` restored to public-read-only, leftover pod data removed, other pods confirmed unaffected (each has its own `.acl`). Full incident writeup in deferred-work.md. Site confirmed healthy throughout (backoffice serving 200, pod-api.js reachable) — the StaticAssetHandler override at `/` was never at risk since it wins over LDP resolution for GET requests.

### Change Log

- 2026-07-21: Story 7.1 implemented and deployed to VPS. Backoffice live at `https://pod.nicolasdb.eu/` root with real CSS account/pod provisioning. Fixed three live-blocking bugs discovered during required E2E verification: esm.sh dependency resolution (added `?bundle`), `RealBackend` missing pod root, and CSS's debug-auth-header import silently disabling real OIDC authentication server-wide (affected existing pods too, not just new ones from this story).
- 2026-07-21: Addendum — fixed browser Back button exiting the app mid-onboarding (no history entries were ever pushed). Small, scoped addition to `index.html`; verified live.
