# Story 7.14: Backoffice Auth — Token Header + Provider-Agnostic Pod Management

Status: ready-for-dev — **depends on Story 7.13 shipping first** (origin split).

## Story

As a pod owner, I want the backoffice to authenticate with a portable `Authorization` header instead of a same-site cookie, and to manage a pod on any Solid provider (not just this CSS instance), so the app is genuinely hostable anywhere and genuinely Solid-spec-compliant where the underlying operation actually is.

## Context — read this before planning any work

**Depends on 7.13.** Story 7.13 moves backoffice to `backoffice.nicolasdb.eu`, cross-*origin* from `pod.nicolasdb.eu` but same-*site* (both under `nicolasdb.eu`). The cookie survives that move — this story's findings are about what still doesn't work even after 7.13, and what was never provider-agnostic to begin with. Do this story second; some of its acceptance tests (the `/onboard/` CORS gap, specifically) are only reproducible once backoffice is actually cross-origin.

This story bundles two independent fixes found together while investigating the same file (`backoffice/pod-api.js`) for the same root cause session. They don't depend on each other and could ship as separate PRs if that's preferred — call this out to Nicolas at kickoff if he'd rather split them.

### Fix (a): cookie → `Authorization: CSS-Account-Token` header

**Why the cookie is a domain-binding constraint at all.** `backoffice/pod-api.js` has 13 `fetch(..., {credentials:'include'})` call sites (lines `457, 487, 507, 523, 536, 562, 634, 715, 765, 789, 807, 816, 825` — confirmed via `grep -n "credentials.*include" backoffice/pod-api.js`; re-run before starting, this will drift). CSS's `CookieMetadataWriter.ts` (upstream source, current `main` branch, read this session) sets the `css-account` cookie with `sameSite: 'lax'`, hardcoded, not configurable via `infra/css/config.json`. `SameSite=Lax` is a **site**-scoped rule (eTLD+1), not origin-scoped — that's *why* 7.13's subdomain split doesn't break it. But it hard-caps how far backoffice can ever move: never off `nicolasdb.eu` entirely (a different registrable domain, e.g. GitHub Pages, a user's own domain) without CSS emitting `SameSite=None; Secure`, which it doesn't and isn't ours to change upstream.

**Confirmed via Context7 (CSS docs, queried live this session, matches current `main` and the deployed 7.1.9):**

> Upon successful login, the API issues a `set-cookie` header in the format `css-account=$VALUE`... Alternatively, the `$VALUE` can be included in an `Authorization` header as `CSS-Account-Token $VALUE`.

Confirmed live against the deployed instance too: `Authorization: CSS-Account-Token <bogus>` against `/.account/` from a **foreign Origin, no cookie at all** → `HTTP/2 200` with `access-control-allow-origin` echoing the foreign origin. Preflight `OPTIONS` with `Access-Control-Request-Headers: authorization` → `204` with `access-control-allow-headers: authorization,content-type`. **CSS already accepts and CORS-clears this path today, cross-origin, cross-site, no server change needed on the CSS side.** This is purely a `backoffice/pod-api.js` client-side change.

**The `AuthorizationParser` wiring is stock, not something this repo added:**
```json
// CSS's own config/ldp/metadata-parser/parsers/authorization.json
"AuthorizationParser:_authMap_key": "CSS-Account-Token",
"AuthorizationParser:_authMap_value": "...http:accountCookie"
```
And `ResolveLoginHandler.js` (CSS source): `json.authorization = await this.cookieStore.generate(accountId)` — the login response already returns this value today; `backoffice/pod-api.js` just never reads or stores it, relying on the browser's cookie jar implicitly instead.

**Does not conflict with the nginx `Authorization: WebID` stripping rule (story 4.4.1).** That rule strips headers matching `^WebID ` specifically; `CSS-Account-Token` and `Bearer`/`DPoP` (already used for the pod's own resource fetches) are untouched. Confirm this explicitly during implementation rather than assuming — a broad strip rule would be a silent, hard-to-diagnose breakage.

### `/onboard/*` needs the same treatment, or it silently breaks post-7.13

`mcp-connector/src/onboardRouter.js` (header comment, line 9): *"The browser forwards its `css-account` cookie (same-origin, no CORS)."* Confirmed live this session: cross-origin probe (`Origin: https://backoffice.nicolasdb.eu`) against `/onboard/grants` → `401`, **zero `access-control-*` response headers** — no CORS middleware exists on this router at all. Once Story 7.13 puts backoffice on its own subdomain, every `/onboard/*` call from the backoffice UI (agent identity minting, connector grants — Stories 7.9/7.12) breaks outright, not gracefully.

Fix: `onboardRouter.js`'s `getCookie(req)` (line ~155) currently does `req.headers.cookie || ""` and forwards it as a `Cookie:` header to CSS. Since CSS accepts `Authorization: CSS-Account-Token` on the *exact same* endpoints it accepts the cookie on, the simplest fix is symmetric: read `Authorization` from the incoming request and forward it as `Authorization` to CSS directly — no cookie reconstruction needed. Add standard CORS middleware (allow the backoffice's origin, credentials or authorization header, per how strict Nicolas wants this — a `cors` npm package with an explicit origin allowlist, not `*`, since this router can mint credentials).

### Fix (b): the account-console vs. pod-manager split

Backoffice is two features sharing one file. They have opposite portability:

| Half | Spec status | Confirmed portable today? |
|---|---|---|
| File browse/CRUD/upload/ACL edit (`RealBackend.list/readText/writeText/_writeAcl` etc.) | Plain LDP + WAC, standard Solid | **Already portable** — see below |
| `/.account/*` register, pod create/delete, WebID link, client-credential mint | CSS-proprietary JSON API, no spec exists | **Not portable, and never can be** — no equivalent API on other providers |

**Correction to carry forward: pod-root derivation is already provider-agnostic.** `RealBackend.init()` (`pod-api.js:112-120`) calls `this.sc.getPodUrlAll(this.webId, {fetch: this.fetch})` — this is `@inrupt/solid-client` reading `pim:storage` triples off the user's own WebID profile document, which is exactly the spec-correct, provider-agnostic way to find someone's pod root. It is **not** hardcoded to CSS's URL-segment convention. Don't re-derive or "fix" this — it's already right.

**The actual gap is narrower: nothing ever offers a non-default issuer.** `Solid.connect()` (`pod-api.js:1196-1203`) takes an optional `oidcIssuer` parameter and already falls back to `ISSUER` (`"https://pod.nicolasdb.eu/"`) only when none is given — the plumbing for a custom issuer exists. But **every call site in `backoffice/index.html`** (`connectLive`, the walkthrough's "Connect" button, `Solid.connect()` at lines 1289, 1637, 1681) calls it with **zero arguments**. There is no UI for a user to type or discover a different provider — the login button can only ever start a flow against `pod.nicolasdb.eu`. That's the entire portability gap for the pod-manager half: add issuer input/discovery to the UI, and the manager half genuinely works against any Solid pod today, unmodified.

**The account-console half cannot be made portable — it should instead announce its own boundary.** No spec exists for pod/account lifecycle across providers (ESS has a different admin surface, NSS/solidcommunity.net has none at all). The correct behavior when connected to a non-CSS pod (or when `/.account/` is unreachable) is to detect that and **hide** the register/create-pod/credential-mint controls, not attempt and fail against them. This makes the Solid-vs-our-server boundary visible in the UI, which is arguably a better product than hiding it.

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| CSS accepts `Authorization: CSS-Account-Token <value>` as a full equivalent of the `css-account` cookie | Confirmed, Context7 (live query, matches current docs) | `communitysolidserver.github.io/.../usage/account/json-api`, `usage/client-credentials` |
| Login response already returns this token, unused by our code | Confirmed | CSS `ResolveLoginHandler.js` (`json.authorization = ...`); `backoffice/pod-api.js` never reads response body's `authorization` field |
| Token path works cross-origin, cross-site, today, no CSS-side change | Confirmed live | `curl -H "Authorization: CSS-Account-Token bogus" -H "Origin: https://backoffice.nicolasdb.eu" https://pod.nicolasdb.eu/.account/` → 200 + CORS headers |
| `AuthorizationParser` mapping `CSS-Account-Token` → account cookie value is CSS stock config, not ours | Confirmed | `config/ldp/metadata-parser/parsers/authorization.json` (CSS npm package source) |
| Cookie is `SameSite=Lax`, hardcoded, not configurable | Confirmed | CSS `CookieMetadataWriter.ts` (upstream source) |
| `/onboard/*` reads `Cookie` header only, no CORS middleware | Confirmed | `mcp-connector/src/onboardRouter.js:9` (comment), live cross-origin probe → 401, no `access-control-*` |
| nginx's `Authorization: WebID` strip rule only matches that literal scheme | Confirmed, prior story | `4-4-1-nginx-openclaw-retirement-css-hardening.md` |
| `RealBackend.root` derivation already uses `pim:storage` via `getPodUrlAll`, already provider-agnostic | Confirmed | `backoffice/pod-api.js:112-120` |
| Every UI call site defaults `Solid.connect()` to `ISSUER` with no override offered | Confirmed | `backoffice/index.html:1289,1637,1681` — all zero-arg calls |
| `Solid.connect(oidcIssuer, clientName)` already accepts an override param | Confirmed | `backoffice/pod-api.js:1196-1203` |
| `RealBackend`'s account-console methods (`_ccUrl`, `_controls`, pod create/delete, credential mint) all fetch `ISSUER`-relative `/.account/*` paths, correctly — these ARE meant to stay pinned to our own CSS instance | Confirmed | `pod-api.js:441-830` region |
| No CSS-equivalent account/pod-lifecycle API exists on other Solid implementations | Domain knowledge, stated as a hard constraint, not independently re-verified per-provider this session | — |

## Scope fence

**This story DOES:**
- Replace all 13 `credentials:'include'` call sites in `backoffice/pod-api.js` with `Authorization: CSS-Account-Token <token>`, storing the token from the login response in the backoffice's own storage (not relying on the cookie jar).
- Add CORS + `Authorization`-header forwarding to `mcp-connector/src/onboardRouter.js`.
- Add an issuer input (or WebID-first discovery) to the backoffice login UI, wiring it through to `Solid.connect(oidcIssuer)`'s existing parameter.
- Add detection for "connected pod is not this CSS instance / `/.account/` unreachable" and hide account-console controls accordingly.

**This story DOES NOT:**
- Change `RealBackend.root`/`init()` pod-root derivation — already correct, do not touch.
- Add a Client Identifier Document or drop Dynamic Client Registration — real portability improvement, genuinely useful (avoids per-login DCR against providers that support it, works against providers that refuse DCR like NSS/ESS), but independent of this story's bug fixes. Flag as a good next story if Nicolas wants it; don't scope-creep it in here.
- Touch Valisette's auth — Valisette never used the cookie (it's WebID/DPoP-only against the connected pod already, no account-console features), so it's unaffected by fix (a). It already takes `state.provider` as a real issuer input (`valisette.js:242-248` `doLogin()`), so it doesn't have fix (b)'s gap either — it's already closer to the target shape than backoffice.
- Rework `/.account/` calls that are correctly meant to always target our CSS instance (registration, pod creation, credential minting for the operator's own pod). Fix (b) only concerns the pod-*manager* half.

## Acceptance Criteria

1. **Login returns and stores a portable token.** After `POST controls.password.login` succeeds, `backoffice/pod-api.js` reads the response body's `authorization` field and stores it (e.g. `sessionStorage`, scoped to the backoffice's own origin) instead of relying on the `css-account` cookie implicitly set by the browser.

2. **All 13 `credentials:'include'` call sites are replaced** with `headers: { authorization: \`CSS-Account-Token ${token}\` }` (or equivalent), reading the stored token from AC1. Enumerate every site via `grep -n "credentials.*include" backoffice/pod-api.js` before starting — do not rely on this story's line-number list, which will drift.

3. **Cross-site login works.** Live test: with backoffice served from a domain that is NOT `nicolasdb.eu` (a local dev port is sufficient for this test — doesn't need to be a real second domain), log in, confirm the full authenticated flow (file browse, at minimum) works. This is the acceptance bar that actually proves the domain-binding constraint is gone, not just that 7.13's same-site move still works.

4. **`logout()` invalidates the token server-side**, not just clears local storage — call `controls.account.logout` (already in the API surface per CSS docs) with the token, then discard it locally.

5. **`/onboard/*` accepts the same `Authorization: CSS-Account-Token` header, forwarded to CSS**, and has CORS middleware allowing the backoffice's actual origin (explicit allowlist, not `*`, since this router mints credentials) with `Authorization` in `Access-Control-Allow-Headers`. Live-verify: cross-origin OPTIONS preflight and the real POST both succeed from `backoffice.nicolasdb.eu` (post-7.13) against the connector-minting and agent-identity-listing endpoints (Stories 7.9, 7.12's UI features).

6. **The nginx `Authorization: WebID` strip does not collide.** Confirm live (spoofed `Authorization: WebID <uri>` still stripped; a real `Authorization: CSS-Account-Token <token>` request passes through untouched) on both `pod.nicolasdb.eu` and the two 7.13 vhosts.

7. **Backoffice login UI accepts an issuer.** At minimum, a text field for a WebID or issuer URL that flows into `Solid.connect(oidcIssuer)`; WebID-first discovery (fetch the WebID, read `solid:oidcIssuer`) is preferred if time allows but a plain issuer-URL field satisfies this AC. The existing "Connect" button's zero-arg call becomes the default-to-`pod.nicolasdb.eu` *option*, not the only path.

8. **File-manager operations work end-to-end against a pod on a different Solid server.** Live test against any second CSS instance (a fresh local `docker-compose` instance is sufficient, doesn't need to be a different implementation) reachable at a different issuer: connect, list, upload, edit ACL. Confirms `getPodUrlAll`'s `pim:storage` derivation genuinely works cross-provider, not just cross-`nicolasdb.eu`-subdomain.

9. **Account-console controls detect and hide themselves against a non-CSS-or-unreachable provider.** When `/.account/` 404s, times out, or the response doesn't match CSS's expected shape, the UI does not show register/create-pod/mint-credential controls, and does not throw an unhandled error — it degrades to file-manager-only, with a plain statement of why (not a silent disappearance).

10. **WCAG 2.1 AA** on any new UI (issuer field, degraded-mode messaging) — 4.5:1 contrast, `focus-visible`, no color-only state, matching the standard already applied in 7.3/7.4/7.10/7.12.

11. **No regression.** Existing backoffice flows against `pod.nicolasdb.eu` (the common case — Nicolas's own daily use) continue to work exactly as before: login, file CRUD, client-credential mint/list/revoke (7.4/7.9), agent identity lifecycle (7.12), pod create/delete (7.10).

## Tasks / Subtasks

- [ ] **Task 1 — Token storage + all call sites (AC: 1, 2, 4)**
  - [ ] 1.1 On successful login, extract `authorization` from the response body; store in `sessionStorage` (matches the ephemeral, per-tab nature of the existing cookie-backed session — don't upgrade to `localStorage` without discussing persistence implications with Nicolas first).
  - [ ] 1.2 `grep -n "credentials.*include" backoffice/pod-api.js`, replace every site with the `Authorization: CSS-Account-Token` header, reading the stored token.
  - [ ] 1.3 `logout()`: call `controls.account.logout` with the token (per CSS docs, an authed empty POST), then clear stored token regardless of the call's success/failure (don't leave a dead token sitting in storage on a network error).
  - [ ] 1.4 Handle the "no token stored" case (never logged in, or storage was cleared) as the existing "not signed in" 401 path already does — don't introduce a new error shape.

- [ ] **Task 2 — `/onboard/*` header + CORS (AC: 5, 6)**
  - [ ] 2.1 In `onboardRouter.js`, add a helper reading `req.headers.authorization` (matching CSS's `CSS-Account-Token` scheme check), forward it as `Authorization` on the outbound `fetch` calls to CSS's `/.account/*` — replacing `getCookie`'s `Cookie:` forwarding, or supporting both during a transition if Nicolas wants zero-downtime rollout (decide and document the choice).
  - [ ] 2.2 Add CORS middleware (the `cors` npm package or hand-rolled equivalent) scoped to this router's mount point, with an explicit origin allowlist including `backoffice.nicolasdb.eu` (and any dev origins Nicolas wants for testing) — not `*`.
  - [ ] 2.3 Live-verify preflight + real request from a cross-origin test client against at least one mutating endpoint (agent identity mint or connector grant).

- [ ] **Task 3 — nginx collision check (AC: 6)**
  - [ ] 3.1 Confirm live, on all three vhosts (`pod.nicolasdb.eu` + the two from 7.13), that `Authorization: WebID <uri>` is stripped and `Authorization: CSS-Account-Token <token>` passes through unmodified. This can run in parallel with 7.13's own nginx work if timing allows — flag the dependency either way.

- [ ] **Task 4 — Issuer input in login UI (AC: 3, 7)**
  - [ ] 4.1 Add an issuer/WebID field to the login UI in `backoffice/index.html`'s connect flow, wired to `Solid.connect(oidcIssuer)`'s existing parameter (`pod-api.js:1196`).
  - [ ] 4.2 If implementing WebID-first discovery (preferred, not required for AC7): fetch the WebID doc, parse `solid:oidcIssuer`, prefill/auto-use it.
  - [ ] 4.3 Keep the current zero-arg "Connect" path as the default/quick option for the common case (Nicolas's own pod) — this is additive, not a replacement UI flow.

- [ ] **Task 5 — Account-console detection + hide (AC: 9)**
  - [ ] 5.1 On connect, probe `/.account/` against whatever issuer is now in play (from Task 4); on failure or unexpected shape, set a flag the UI reads to suppress register/create-pod/mint-credential controls.
  - [ ] 5.2 Add a plain-language message explaining the degraded mode (not a silent disappearance) — matches this story's stated design goal of making the Solid-vs-our-server boundary visible.
  - [ ] 5.3 Confirm file-manager controls (list/CRUD/upload/ACL) remain fully available in this degraded mode — the whole point is that half still works.

- [ ] **Task 6 — Cross-provider live test (AC: 8)**
  - [ ] 6.1 Stand up a second CSS instance (fresh local `docker-compose`, different port/issuer) or use an existing second instance if one is available.
  - [ ] 6.2 Connect backoffice to it via Task 4's issuer field, run the full file-manager flow (list/upload/edit/ACL), confirm no CSS-instance-specific assumption breaks.

- [ ] **Task 7 — Full regression pass (AC: 11)**
  - [ ] 7.1 Against `pod.nicolasdb.eu` (post-7.13, from `backoffice.nicolasdb.eu`): login, file CRUD, client-credential mint/list/revoke, agent identity lifecycle, pod create/delete.
  - [ ] 7.2 Confirm `verify-http.js` (or whatever the existing smoke-test script is, per 7.12's precedent) still passes.

## Dev Agent Record

_(To be filled during implementation: token storage mechanism chosen, whether cookie-forwarding was kept in parallel during transition, cross-provider test instance details.)_

## File List

_(To be filled during implementation.)_
