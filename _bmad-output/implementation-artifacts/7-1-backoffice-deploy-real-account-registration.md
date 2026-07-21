# Story 7.1: Backoffice Deploy & Real Account Registration

Status: ready-for-dev

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

- [ ] Task 1: Import mockup into repo (AC: #1, #2)
  - [ ] 1.1 Copy `index.html`, `pod-api.js`, `support.js` from `backoffice/` (already imported into repo root at this path) — confirm these are the files to deploy, no rewrite needed
  - [ ] 1.2 Add a custom CSS component config importing `css:config/http/static/default.json` pattern and adding a `StaticAssetHandler` entry mapping `/` → `backoffice/index.html`, plus `/pod-api.js` and `/support.js` — wire into `infra/css/config.json` `@graph` (same file already customized for `debug-auth-header.json`, see Story 4.4.1 precedent)
  - [ ] 1.3 Mount `backoffice/` read-only into the CSS container via `docker-compose.yml` volumes (pattern: `- ./infra/css/config.json:/config.json:ro` already exists at docker-compose.yml:9 — add `- ./backoffice:/backoffice:ro`)
  - [ ] 1.4 Verify `/` returns backoffice HTML and CSS's own LDP root (pod listing, account API, OIDC) is unaffected at other paths — check locally before VPS push
- [ ] Task 2: Inrupt library strategy decision (AC: #7)
  - [ ] 2.1 Decide: keep esm.sh runtime `import(...)` (bundle's current approach, zero build step) vs. `npm i` + bundle locally. Recommendation: keep esm.sh for POC — no build tooling exists in this repo, bundling adds a new toolchain for marginal offline benefit
  - [ ] 2.2 Keep pinned versions in `pod-api.js`: `@inrupt/solid-client-authn-browser@2.3.0`, `@inrupt/solid-client@2.1.0` — do NOT upgrade to npm latest (5.0.0 / 3.0.0, major version bumps, out of scope for this story)
- [ ] Task 3: Wire real account/pod provisioning (AC: #3)
  - [ ] 3.1 In `pod-api.js`, replace the demo-backend "Create my pod" call with real CSS `.account/` API calls: `GET /.account/` (discover `controls`) → `POST controls.account.account` (empty POST, get `css-account` cookie / `CSS-Account-Token`) → `POST controls.password.create {email, password}` → `POST controls.account.pod {name}` (per CSS v7 JSON API, verified against docs 2026-07-21)
  - [ ] 3.2 Map onboarding's existing passphrase field to CSS `password` field (bundle already invites a multi-word passphrase with a strength hint — reuse as password value, no UI change per AC7)
  - [ ] 3.3 On successful provisioning, hand off to `login()` (existing real Inrupt flow) so the new user lands authenticated
  - [ ] 3.4 Preserve `RealBackend`/`DemoBackend` interface split described in HANDOFF.md — new account creation becomes part of `RealBackend`, demo pod remains available for the "I'm new to this... explore first" path if kept
- [ ] Task 4: Fallback path if Task 3 slips (AC: #6)
  - [ ] 4.1 If timeboxed out, wire "Create my pod" to link to CSS's own registration page instead, returning to "I already have a pod" afterward
  - [ ] 4.2 Record in story Completion Notes which path (real API wiring vs. link-out fallback) actually shipped
- [ ] Task 5: E2E verification on VPS (AC: #5)
  - [ ] 5.1 Push via `make vps-push/build/deploy` (established Story 4.0.2 pattern)
  - [ ] 5.2 Full live walkthrough: new account+pod, login, file CRUD, sharing grant/revoke, WAC panel — using a throwaway account, delete after (same discipline as Story 4.4.1 Task 4)
  - [ ] 5.3 Confirm public `Authorization: WebID` header-stripping (Story 4.4.1 security fix, `04-pocpod0.conf`) still applies — backoffice must authenticate via real OIDC only, never rely on the debug-auth-header path

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

### Debug Log References

### Completion Notes List

### File List
