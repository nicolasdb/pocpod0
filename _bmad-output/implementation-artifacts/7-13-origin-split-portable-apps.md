# Story 7.13: Origin Split — Backoffice & Valisette Off pod.nicolasdb.eu

Status: ready-for-dev

## Story

As a pod owner running two Solid apps (backoffice, Valisette) on my own server, I want each app on its own subdomain instead of sharing `pod.nicolasdb.eu` with the CSS provider, so the apps stop fighting over browser-global session state and `pod.nicolasdb.eu` can be a plain Solid provider any client can trust.

## Context — read this before planning any work

**This story fixes a live, user-confirmed bug, not a hypothetical.** Commit `6432771` (2026-08-26) added Valisette at `/valisette/`, served by CSS alongside backoffice at `/`, both on `pod.nicolasdb.eu`. Its own commit message flags: "KNOWN ISSUE (not yet resolved): the SSO bounce between backoffice and Valisette still recurs in some flow." Nicolas reproduced it directly: signing out of Valisette restored backoffice's access — i.e. logging into one app was silently ending the other's session.

### Root cause, verified against library source (not the docs — the actual npm dist)

Fetched `@inrupt/solid-client-authn-browser@2.3.0`, `@inrupt/oidc-client-ext@2.3.0` from the npm registry this session and read the bundled `dist/index.mjs`/`index.es.js` directly (esm.sh is what the browser actually loads, per `pod-api.js:51`, `?bundle` flag). Three mechanisms, **all keyed by browser origin, none by app**:

1. **`clearOidcPersistentStorage()`** (`oidc-client-ext/dist/index.es.js:379`) — regex-deletes every `localStorage` key matching `^oidc\..+$` or `^solidClientAuthenticationUser:.+$`. Called from `ClientAuthentication.login()` (`solid-client-authn-browser/dist/index.mjs:76`, via `SessionInfoManager.clear()`) **at the start of every login, before it does anything else.** `sessionId` gives zero protection — the wipe is a regex over all keys on the origin, not scoped to any one session's keys. **Logging into Valisette silently deletes backoffice's stored tokens, and vice versa.** This is the mechanism the current fix doesn't touch.

2. **`solidClientAuthn:currentSession`** (`dist/index.mjs:1071`) — one pointer per origin, set on `EVENTS.LOGIN` (`:1305`). `handleIncomingRedirect({restorePreviousSession:true})` reads this pointer and calls `silentlyAuthenticate(storedSessionId, ...)` (`:1264-1269`) using **whatever id is stored there**, ignoring which `Session` instance is asking. `silentlyAuthenticate` (`:1094`) then redirects to `storedSessionInfo.redirectUrl` — the *other* app's URL. Story 7.1's `Solid.namedSession`/`Solid.canRestore` guard (`backoffice/pod-api.js:1165-1179`, mirrored in `valisette/valisette.js:217-225`) is the correct, working mitigation for **this one mechanism only** — it makes `restorePreviousSession` conditional on the pointer already matching the app's own session id.

3. **`solidClientAuthn:currentUrl`** (`dist/index.mjs:1072`) — same one-per-origin pattern, used to restore post-redirect scroll position. Minor, same root cause.

**None of this is a config knob.** It's how the library manages storage, by design, for the single-app-per-origin case Inrupt built it for. The only fix that removes all three at once — because browser storage (`localStorage`) is scoped by origin, not by path — is putting backoffice and Valisette on different origins.

### Why not patch around it instead

A same-origin fix exists (give each app a custom `IStorage` — `Session` accepts `{secureStorage, insecureStorage}`, interface is just `get/set/delete`, see `Session.d.ts:10,14` — prefixed keys would dodge mechanism #1's regex). It was considered and rejected for this story: it fights library internals that could change in a minor version, it doesn't fix #2/#3 (those keys are hardcoded, unprefixable), and it doesn't serve the stated product goal — two independently hostable Solid apps. Origin split does all of that in one move and is the documented, unsurprising way to run multiple Solid apps.

### Secondary finding: current asset caching makes deploys undebuggable

Confirmed live (`curl -I https://pod.nicolasdb.eu/pod-api.js`, `/valisette/`, this session): every backoffice/Valisette asset gets `cache-control: max-age=86400` with **no `ETag`, no `Last-Modified`**. CSS's `StaticAssetHandler` sets this from `config/http/static/default.json`'s shared `options_expires` (same `@id` as the app-asset blocks, so it's inherited, not set per-app). A browser that loaded a stale copy has no way to know it's stale for 24h. Confirmed also: `valisette/valisette.js:18` imports `/pod-api.js` with **no cache-buster** (`import { Solid } from "/pod-api.js"`), while `backoffice/index.html:990` uses `?v=7-12-3` — so Valisette in particular could be running yesterday's `pod-api.js` in some browsers right now. This story's nginx move is also the fix: static files served from disk get real `ETag`/`Last-Modified` for free, and the deploy step can set short/no caching deliberately instead of inheriting CSS's blanket 24h.

### Secondary finding: root container unmasking risk

`infra/css/config.json`'s backoffice block currently maps `relativeUrl: "/"` → `/backoffice/index.html` (see block right before the Valisette one, `@id: urn:solid-server:default:StaticAssetHandler`). CSS's `StaticAssetHandler.expandFolderAssets()` only auto-expands **root folder** mappings (`filePath.endsWith('/') && relativeUrl === '/'`) — the backoffice mapping is a single file, not a folder, so it doesn't trigger that path, but it does **mask** whatever CSS itself would otherwise serve at `/` (its own root storage container, `pod/static.json` = one root storage — memory `css_static_pods_ownership_challenge`). Removing this mapping (this story's Task 3) makes that root container directly reachable again at `https://pod.nicolasdb.eu/`. There was a prior incident here: memory `css_orphan_acl_lockout` — a resource `.acl` with `accessTo <./>` 403s everyone including the owner, no HTTP recovery, disk-only fix, swept clean 2026-08-13. **Verify the root container's current `.acl` is sane before removing the mapping, not after.**

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| `clearOidcPersistentStorage()` wipes all `oidc.*`/`solidClientAuthenticationUser:*` keys, unscoped, on every login | Confirmed, npm dist source | `oidc-client-ext@2.3.0/dist/index.es.js:379-401` |
| `solidClientAuthn:currentSession`/`currentUrl` are one-per-origin globals | Confirmed, npm dist source | `solid-client-authn-browser@2.3.0/dist/index.mjs:1071-1072` |
| Existing `namedSession`/`canRestore` guard fixes mechanism #2 only | Confirmed by code read + live repro (sign-out of Valisette restored backoffice) | `backoffice/pod-api.js:1165-1201`, `valisette/valisette.js:217-257` |
| Both apps served from `pod.nicolasdb.eu` via CSS `StaticAssetHandler` | Confirmed | `infra/css/config.json` (two `StaticAssetHandler` blocks, same `@id`), `docker-compose.yml` bind-mounts |
| Static assets: `max-age=86400`, no ETag, no Last-Modified | Confirmed live | `curl -I https://pod.nicolasdb.eu/pod-api.js`, `/valisette/valisette.js` (2026-08-26) |
| `/valisette` (no trailing slash) → 401, falls through to LDP, not a redirect | Confirmed live | `curl -I https://pod.nicolasdb.eu/valisette` (2026-08-26) |
| Valisette's `pod-api.js` import has no cache-buster; backoffice's does | Confirmed | `valisette/valisette.js:18` vs `backoffice/index.html:990` |
| `Authorization: WebID` header is stripped at the nginx edge, public traffic only | Confirmed, prior story | `4-4-1-nginx-openclaw-retirement-css-hardening.md`, `04-pocpod0.conf` (hetzner-gateway repo, not this repo) |
| CSS root storage = single anchor for the whole pod file tree | Confirmed, prior investigation | memory `css_static_pods_ownership_challenge` |
| Orphaned-ACL lockout on root has no HTTP recovery path | Confirmed, prior incident, remediated | memory `css_orphan_acl_lockout` |
| nginx vhosts for `pod.nicolasdb.eu` live in a **separate repo** (`hetzner-gateway`), not this one | Confirmed | `docker-compose.yml:80-83` comments, `08-2-http-transport.md` pattern for `mcp-connector`'s vhost |
| Certbot / DNS are also outside this repo | Stated by Nicolas | this session |

## Scope fence

**This story DOES:**
- Move backoffice and Valisette to their own subdomains, served as static files by nginx directly from disk (not through CSS).
- Remove both `StaticAssetHandler` app-asset blocks from `infra/css/config.json`.
- Verify the root container's ACL before that removal ships.
- Replicate the `Authorization: WebID` public-edge-stripping rule on the two new vhosts (that rule currently only exists on `pod.nicolasdb.eu`'s vhost).
- Drop the now-redundant `namedSession`/`canRestore` guard from `pod-api.js` and `valisette.js` (mechanism #2 can't fire across origins; the guard becomes dead code once #1/#2/#3 are all moot).
- Add deploy targets (rsync + reload) for the two new static roots.

**This story DOES NOT:**
- Touch the cookie-vs-header auth question, or the `ISSUER` hardcode, or `/onboard/`'s CORS gap. That's Story 7.14, and it's sequenced *after* this one — 7.14 needs backoffice already cross-origin from `pod.nicolasdb.eu` to even reproduce what it's fixing.
- Provision DNS records or certbot certs. Out of this repo (`hetzner-gateway`), but this story's nginx/deploy work is **blocked on** those existing — call this out explicitly as a pre-req, don't silently assume it.
- Add a Client Identifier Document or issuer discovery (mentioned in the session's investigation as a longer-term portability improvement) — not needed to fix the bounce, deliberately left for a later story if wanted.

## Acceptance Criteria

1. **`backoffice.nicolasdb.eu` and `valisette.nicolasdb.eu` each serve their app as static files from disk**, via nginx, not via CSS's `StaticAssetHandler`. `pod.nicolasdb.eu/` no longer serves the backoffice at its root, and `pod.nicolasdb.eu/valisette/` no longer serves Valisette.

2. **The SSO bounce is gone.** Live test: log into `backoffice.nicolasdb.eu`, then log into `valisette.nicolasdb.eu` in the same browser without logging out first — both sessions remain independently valid afterward (reload each, still logged in as expected). This is the acceptance test that matters; everything else is infrastructure to get here.

3. **`Authorization: WebID <uri>` is stripped at the nginx edge on both new vhosts**, matching the existing rule on `pod.nicolasdb.eu` (story 4.4.1). Public traffic to either new vhost cannot spoof this header; confirm with the same live test pattern 4.4.1 used (spoofed header → the app's own auth behavior, not an impersonated identity).

4. **Root container ACL is verified sane before the `/` mapping is removed from `infra/css/config.json`.** Fetch and read the current `.acl` (or absence of one, meaning default inheritance) on `pod.nicolasdb.eu`'s root; confirm it does not grant unintended public access and is not an orphaned lockout state (memory `css_orphan_acl_lockout`). Record what was found in the Dev Agent Record before proceeding with the removal.

5. **After removal, `pod.nicolasdb.eu/` serves CSS's own behavior** (whatever the root storage container naturally returns — a directory listing per WAC, or a 401/403 per ACL, not a 500 or an orphaned-lockout state). Confirm live.

6. **Static assets get real cache validation.** nginx serves `backoffice.nicolasdb.eu`/`valisette.nicolasdb.eu` files with either a short `max-age` (e.g. 5 minutes) or `ETag`/`Last-Modified`-based validation — not CSS's current unconditional 24h opaque cache. A file changed and redeployed must be visible to a client within the chosen window without a hard-refresh workaround.

7. **`namedSession`/`canRestore` are removed from `backoffice/pod-api.js` and `valisette/valisette.js`**, replaced with a plain per-app `Session` (stable `sessionId` kept — no reason to lose that — but the conditional-restore guard and its long explanatory comments go, since the race they guard against no longer exists once storage is origin-scoped). `restorePreviousSession: true` unconditionally is safe again.

8. **Deploy path exists for both new static roots** — Makefile target(s) or equivalent, following the existing `make vps-push/build/deploy` pattern (memory `infra_vps_deploy`), so this isn't a manual one-off.

9. **No regression.** Backoffice login (`/.account/`, cookie-based — untouched by this story), Valisette's real-pod gist listing, and every existing `pod.nicolasdb.eu` LDP path continue to work exactly as before, from their new hosts.

## Tasks / Subtasks

- [ ] **Task 1 — Pre-req: DNS + certs (AC: none directly; blocks Task 2-4)**
  - [ ] 1.1 Confirm with Nicolas (or hetzner-gateway repo) that A records for `backoffice.nicolasdb.eu` and `valisette.nicolasdb.eu` exist and point at the VPS.
  - [ ] 1.2 Confirm certbot has issued/expanded certs to cover both new names (this repo does not own certbot config — coordinate, don't assume).

- [ ] **Task 2 — Root container ACL verification (AC: 4, 5)**
  - [ ] 2.1 GET `https://pod.nicolasdb.eu/.acl` (or the resolved root ACL per WAC inheritance) with an authenticated request as the pod owner; read and record its contents.
  - [ ] 2.2 Confirm it is not the orphaned-lockout shape from memory `css_orphan_acl_lockout` (`accessTo <./>` on a resource `.acl` that 403s the owner too).
  - [ ] 2.3 Document the finding in Dev Agent Record before Task 3 removes the masking mapping.

- [ ] **Task 3 — nginx vhosts + static serving (AC: 1, 3, 6)**
  - [ ] 3.1 Write nginx server blocks for `backoffice.nicolasdb.eu` and `valisette.nicolasdb.eu` in the hetzner-gateway repo (out-of-repo change, coordinate), serving each app's directory from disk (`root /srv/backoffice;` / `root /srv/valisette;`, `try_files $uri $uri/ =404;` — these are single-page-ish static apps, no SPA fallback needed per current `index.html` structure, confirm against actual routing before assuming otherwise).
  - [ ] 3.2 Set cache headers per AC6 — either nginx's own `etag on;`/`if_modified_since` (default, just don't override with a long `expires`) or an explicit short `expires 5m;`.
  - [ ] 3.3 Add the `Authorization: WebID` stripping `map` block from `04-pocpod0.conf` (story 4.4.1) to both new server blocks.
  - [ ] 3.4 Live-verify: fetch each app's `index.html`, confirm 200 + correct headers; spoof `Authorization: WebID <uri>` on each and confirm it's stripped before reaching any backend.

- [ ] **Task 4 — Remove CSS-served copies (AC: 1, 5)**
  - [ ] 4.1 Remove the backoffice `StaticAssetHandler` block (`relativeUrl: "/"` mapping and siblings) from `infra/css/config.json`.
  - [ ] 4.2 Remove the Valisette `StaticAssetHandler` block from `infra/css/config.json`.
  - [ ] 4.3 Remove the corresponding bind-mounts from `docker-compose.yml` (`./backoffice:/backoffice:ro`, `./valisette:/valisette:ro`) — CSS no longer needs read access to either directory.
  - [ ] 4.4 Restart CSS, confirm `pod.nicolasdb.eu/` and `/valisette/` no longer serve the old apps and instead reflect the root container's real state (per AC5).

- [ ] **Task 5 — Deploy plumbing (AC: 8)**
  - [ ] 5.1 Add Makefile target(s) (or extend existing `vps-*` targets, memory `infra_vps_deploy`) to rsync `backoffice/` → `/srv/backoffice` and `valisette/` → `/srv/valisette` on the VPS.
  - [ ] 5.2 Confirm the deploy path doesn't accidentally sync `.git` or dev-only files (mirror whatever exclusion pattern the existing `vps-push` target already uses).

- [ ] **Task 6 — Client code cleanup (AC: 2, 7, 9)**
  - [ ] 6.1 In `backoffice/pod-api.js`: replace `Solid.namedSession`/`_backofficeSession`/`canRestore` machinery with a plain `new libs.authn.Session({}, BACKOFFICE_SESSION_ID)` and unconditional `restorePreviousSession: true`. Remove the now-inaccurate long comment block explaining the cross-app race (or replace it with a one-line note that the race no longer applies post-origin-split, for the next person's benefit).
  - [ ] 6.2 In `valisette/valisette.js`: same simplification — drop the `canRestore` check in `initSolid()`, keep `SESSION_ID = "valisette"` for stability across reloads, restore unconditionally.
  - [ ] 6.3 Update the code comments referencing `Solid.namedSession`/`canRestore` in both files (`valisette.js:6-10,212-216`) since the mechanism they describe is being removed, not just no longer needed.
  - [ ] 6.4 Live-verify AC2: log into backoffice, then Valisette without logging out, confirm both stay logged in after reload.

- [ ] **Task 7 — Full regression pass (AC: 9)**
  - [ ] 7.1 Backoffice: login, file browse/CRUD/upload/ACL, client-credential mint/list/revoke, agent identity list (7.12) — all from `backoffice.nicolasdb.eu`.
  - [ ] 7.2 Valisette: login, gist container listing, swipe-triage flow, autosave — from `valisette.nicolasdb.eu`.
  - [ ] 7.3 `pod.nicolasdb.eu`: confirm LDP/WAC/OIDC endpoints unaffected — this is the acceptance bar for "pod.nicolasdb.eu is a plain Solid provider now."

## Dev Agent Record

_(To be filled during implementation: root ACL finding from Task 2, any deviations, live verification results.)_

## File List

_(To be filled during implementation.)_
