# Story 7.14: Onboard CORS Fix (descoped from token-auth/provider-agnostic pods)

Status: done

## Story

As a pod owner, I want `/onboard/*` (agent-identity minting, connector grants) to keep working from the backoffice UI after Story 7.13's origin split, so those features don't silently 401 the moment backoffice moves to its own subdomain.

## Descope decision (2026-08-26)

This story was originally drafted with a much larger scope: replace the `css-account` cookie with a portable `Authorization: CSS-Account-Token` header across all 13 call sites in `backoffice/pod-api.js`, plus provider-agnostic issuer input and account-console feature-detection for non-CSS providers. Discussed with Nicolas before starting implementation:

- **The premise was wrong.** The cookie is `SameSite=Lax`, which is *site*-scoped (eTLD+1), not *origin*-scoped. `backoffice.nicolasdb.eu` and `pod.nicolasdb.eu` share the registrable domain `nicolasdb.eu` — same-site, cross-origin. `SameSite=Lax` permits same-site cross-origin subrequests. The cookie already survives Story 7.13's move; there is no live regression on the `RealBackend` account-API paths (client credentials, pod list/create, agent-identity link) that a token rewrite would fix.
- **Nicolas's actual constraint:** the existing OIDC/WebID-picker popup is the only mechanism he has to sign out and switch between WebIDs linked to one account. A token rewrite implied either abandoning that (bad) or bolting on a second, parallel email+password login form just to capture a `controls.password.login` response body (since the OIDC flow redirects through CSS's own hosted login page — our JS never sees that response). Concluded not worth the UX regression for a prototyping-stage app where multi-provider portability is explicitly "nice to have, not now."
- **The one real, live-breaking bug**: `mcp-connector/src/onboardRouter.js` had zero CORS handling and doc comments assuming same-origin. Confirmed live pre-fix: cross-origin probe from `Origin: https://backoffice.nicolasdb.eu` → `401`, zero `access-control-*` headers (a CORS block, not an auth failure) — this genuinely breaks post-7.13 regardless of the cookie/token question, because the browser won't let JS read the response without an explicit CORS grant.

Full token-auth/provider-agnostic-pods scope is preserved below (unchanged) as a reference for a future story if multi-provider support becomes a real requirement — **do not treat it as current scope**.

## Acceptance Criteria (current, descoped scope)

1. `/onboard/mint`, `/onboard/grants`, `/onboard/revoke` respond with correct `Access-Control-Allow-Origin`/`Access-Control-Allow-Credentials` headers for `https://backoffice.nicolasdb.eu`, and `OPTIONS` preflights return `204` with the right `Access-Control-Allow-*` headers.
2. Cookie-based auth is unchanged — no client-side (`backoffice/pod-api.js`) changes, no new login UI. The existing WebID-popup/OIDC flow keeps working exactly as today, sign-out/WebID-switch included.
3. nginx's `04-pocpod0.conf` `/onboard/` block is confirmed to pass `Origin`, `Cookie`, and `OPTIONS` through untouched (no interference with the new CORS layer).
4. No regression: existing backoffice flows against `pod.nicolasdb.eu`/`backoffice.nicolasdb.eu` — login, file CRUD, client-credential mint/list/revoke, agent identity lifecycle, pod create/delete, connector mint/grants/revoke — all continue to work.

## Tasks / Subtasks

- [x] **Task 1 — CORS middleware in `onboardRouter.js` (AC1, AC2)**
  - [x] 1.1 Add hand-rolled CORS middleware (no new dependency — `cors` npm package not present in `mcp-connector/package.json`, avoided per no-new-deps-without-approval): explicit origin allowlist via `ONBOARD_CORS_ORIGINS` env var (default `https://backoffice.nicolasdb.eu`), `Access-Control-Allow-Credentials: true`, `Vary: Origin`, `OPTIONS` short-circuited to `204` with `Access-Control-Allow-Methods`/`Access-Control-Allow-Headers`.
  - [x] 1.2 Update the router's header comment (was: "same-origin, no CORS") to reflect Story 7.13's origin split and this fix.
  - [x] 1.3 No change needed to `getCookie()`/cookie-forwarding — cookie already arrives cross-origin-same-site; only the response needed a CORS grant.

- [x] **Task 2 — nginx pass-through confirmation (AC3)**
  - [x] 2.1 Read `hetzner-gateway/nginx/conf.d/04-pocpod0.conf`'s `/onboard/` location block: no header stripping applies to it (the `Authorization: WebID` strip is scoped to the catch-all `location /` serving CSS, not `/onboard/`), all proxy headers pass through unmodified, `OPTIONS` is not special-cased/blocked.
  - [x] 2.2 Updated the block's stale comment (claimed same-origin/no-CORS) to reflect the new CORS layer living in `onboardRouter.js` itself.

- [x] **Task 3 — Deploy + live verification (AC1, AC4)**
  - [x] 3.1 Rebuilt/redeployed `mcp-connector` on the VPS (`docker compose build mcp-connector && docker compose up -d mcp-connector`), reloaded nginx-gateway for the comment-only config change.
  - [x] 3.2 Live cross-origin preflight: `OPTIONS /onboard/grants` with `Origin: https://backoffice.nicolasdb.eu` → `204` with `access-control-allow-origin: https://backoffice.nicolasdb.eu`, `access-control-allow-credentials: true`, `access-control-allow-methods`, `access-control-allow-headers`. Real `GET /onboard/grants` (no cookie, curl) → `401 {"error":"Not signed in."}` **with** CORS headers present — proves the auth check runs and is reachable from JS now, was previously CORS-blocked before any auth check ran.
  - [x] 3.3 Live browser test by Nicolas found a SECOND bug this fix exposed (CORS wasn't the whole story): `mintConnector`/`listGrants`/`revokeGrant` in `backoffice/pod-api.js` fetched relative `"/onboard/..."` paths — pre-7.13 that resolved same-origin against `pod.nicolasdb.eu` for free; post-split from `backoffice.nicolasdb.eu` it resolved against backoffice's OWN origin instead and 404'd there (screenshot: "Could not list connector grants (HTTP 404)"). Fixed by making all three calls absolute (`new URL("/onboard/...", ISSUER)`), redeployed, cache-buster bumped (`index.html` `?v=7-14-1`), confirmed live by Nicolas: "connector are back. confirmed."

## Dev Agent Record

**Descope discussion (2026-08-26):** See "Descope decision" section above — full detail of why the token-header rewrite was dropped, captured inline in the story rather than only in chat, per Nicolas's steer during kickoff.

**Task 1 implementation notes:** `mcp-connector/src/onboardRouter.js` — added CORS middleware right after `express.json()`, before the rate limiter, so a rejected-origin request still hits the rate limiter (no bypass). Used a plain allowlist check against `req.headers.origin` rather than the `cors` npm package, since `mcp-connector/package.json` doesn't currently depend on it and this is a 15-line need. `ONBOARD_CORS_ORIGINS` env var (comma-separated) lets Nicolas add dev origins (e.g. a local port) without a code change; defaults to just the production backoffice origin, never `*` (this router mints credentials, per the original story's own reasoning — preserved even though the token-rewrite scope around it was dropped).

**Task 2 implementation notes:** No code change needed — confirmed by reading the actual nginx config on the VPS (`ssh hetzner`) that the `/onboard/` location block is a clean pass-through (no `Authorization` stripping, which only applies to the CSS catch-all `location /`; no method restrictions). Only the stale explanatory comment (which asserted same-origin/no-CORS, now false post-7.13) needed updating, done directly on the VPS since `hetzner-gateway` is a separate out-of-repo repo (same pattern as Story 7.13's nginx work).

## File List

- `mcp-connector/src/onboardRouter.js` — CORS middleware added, header comment updated (repo + VPS)
- `backoffice/pod-api.js` — `mintConnector`/`listGrants`/`revokeGrant` fetch calls made absolute against `ISSUER` (repo + VPS `/srv/backoffice`)
- `backoffice/index.html` — cache-buster bumped `?v=7-12-3` → `?v=7-14-1` (repo + VPS `/srv/backoffice`)
- `/home/nicolas/hetzner-gateway/nginx/conf.d/04-pocpod0.conf` — comment updated only, no functional change (out-of-repo, VPS-side)

## Change Log

- 2026-08-26: Story descoped from full token-auth/provider-agnostic-pods rewrite to a targeted CORS fix for `/onboard/*`, after kickoff discussion established the cookie already survives Story 7.13's same-site subdomain split and a token rewrite would force an unwanted second login form. Full original scope preserved in this file for future reference.
- 2026-08-26: Live browser test surfaced a second, independent bug the CORS fix uncovered — relative `/onboard/*` fetch paths in `pod-api.js` broke post-origin-split. Fixed, deployed, live-confirmed by Nicolas. Story closed.

---

## Original scope (preserved for reference — NOT current scope)

_The sections below are the original story draft, kept verbatim for anyone picking up multi-provider portability later. None of this is being implemented in this story's current pass._

### Story (original)

As a pod owner, I want the backoffice to authenticate with a portable `Authorization` header instead of a same-site cookie, and to manage a pod on any Solid provider (not just this CSS instance), so the app is genuinely hostable anywhere and genuinely Solid-spec-compliant where the underlying operation actually is.

### Context — read this before planning any work

**Depends on 7.13.** Story 7.13 moves backoffice to `backoffice.nicolasdb.eu`, cross-*origin* from `pod.nicolasdb.eu` but same-*site* (both under `nicolasdb.eu`). The cookie survives that move — this story's findings are about what still doesn't work even after 7.13, and what was never provider-agnostic to begin with. Do this story second; some of its acceptance tests (the `/onboard/` CORS gap, specifically) are only reproducible once backoffice is actually cross-origin.

This story bundles two independent fixes found together while investigating the same file (`backoffice/pod-api.js`) for the same root cause session. They don't depend on each other and could ship as separate PRs if that's preferred — call this out to Nicolas at kickoff if he'd rather split them.

#### Fix (a): cookie → `Authorization: CSS-Account-Token` header

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

**Open question surfaced during kickoff (2026-08-26), unresolved in the original draft:** the account token can only be captured client-side by calling `controls.password.login` directly via `fetch`. The daily-use login path is pure OIDC redirect through CSS's own hosted page (`session.login()`), which our JS never sees the response body of — the `css-account` cookie gets set by that page directly. Implementing fix (a) as written would require adding a second, parallel email+password login form purely to capture that token, which conflicts with Nicolas's requirement that the existing WebID-picker/OIDC popup remain the single sign-in/switch-WebID mechanism. Not resolved in this draft — would need its own design pass if revisited.

#### `/onboard/*` needs the same treatment, or it silently breaks post-7.13

`mcp-connector/src/onboardRouter.js` (header comment, line 9): *"The browser forwards its `css-account` cookie (same-origin, no CORS)."* Confirmed live this session: cross-origin probe (`Origin: https://backoffice.nicolasdb.eu`) against `/onboard/grants` → `401`, **zero `access-control-*` response headers** — no CORS middleware exists on this router at all. Once Story 7.13 puts backoffice on its own subdomain, every `/onboard/*` call from the backoffice UI (agent identity minting, connector grants — Stories 7.9/7.12) breaks outright, not gracefully.

**This part shipped — see current scope above.** Fix used cookie-forwarding as-is (already works same-site) plus CORS middleware, not a token-header rewrite.

#### Fix (b): the account-console vs. pod-manager split

Backoffice is two features sharing one file. They have opposite portability:

| Half | Spec status | Confirmed portable today? |
|---|---|---|
| File browse/CRUD/upload/ACL edit (`RealBackend.list/readText/writeText/_writeAcl` etc.) | Plain LDP + WAC, standard Solid | **Already portable** — see below |
| `/.account/*` register, pod create/delete, WebID link, client-credential mint | CSS-proprietary JSON API, no spec exists | **Not portable, and never can be** — no equivalent API on other providers |

**Correction to carry forward: pod-root derivation is already provider-agnostic.** `RealBackend.init()` (`pod-api.js:112-120`) calls `this.sc.getPodUrlAll(this.webId, {fetch: this.fetch})` — this is `@inrupt/solid-client` reading `pim:storage` triples off the user's own WebID profile document, which is exactly the spec-correct, provider-agnostic way to find someone's pod root. It is **not** hardcoded to CSS's URL-segment convention. Don't re-derive or "fix" this — it's already right.

**The actual gap is narrower: nothing ever offers a non-default issuer.** `Solid.connect()` (`pod-api.js:1196-1203`) takes an optional `oidcIssuer` parameter and already falls back to `ISSUER` (`"https://pod.nicolasdb.eu/"`) only when none is given — the plumbing for a custom issuer exists. But **every call site in `backoffice/index.html`** (`connectLive`, the walkthrough's "Connect" button, `Solid.connect()` at lines 1289, 1637, 1681) calls it with **zero arguments**. There is no UI for a user to type or discover a different provider — the login button can only ever start a flow against `pod.nicolasdb.eu`. That's the entire portability gap for the pod-manager half: add issuer input/discovery to the UI, and the manager half genuinely works against any Solid pod today, unmodified.

**The account-console half cannot be made portable — it should instead announce its own boundary.** No spec exists for pod/account lifecycle across providers (ESS has a different admin surface, NSS/solidcommunity.net has none at all). The correct behavior when connected to a non-CSS pod (or when `/.account/` is unreachable) is to detect that and **hide** the register/create-pod/credential-mint controls, not attempt and fail against them. This makes the Solid-vs-our-server boundary visible in the UI, which is arguably a better product than hiding it.

**Status: not implemented.** Nicolas confirmed at kickoff (2026-08-26) that multi-provider portability is "nice to have, not a priority right now" for this prototyping-stage app. Deferred to a future story if/when it becomes a real requirement.

### Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| CSS accepts `Authorization: CSS-Account-Token <value>` as a full equivalent of the `css-account` cookie | Confirmed, Context7 (live query, matches current docs) | `communitysolidserver.github.io/.../usage/account/json-api`, `usage/client-credentials` |
| Login response already returns this token, unused by our code | Confirmed | CSS `ResolveLoginHandler.js` (`json.authorization = ...`); `backoffice/pod-api.js` never reads response body's `authorization` field |
| Token path works cross-origin, cross-site, today, no CSS-side change | Confirmed live | `curl -H "Authorization: CSS-Account-Token bogus" -H "Origin: https://backoffice.nicolasdb.eu" https://pod.nicolasdb.eu/.account/` → 200 + CORS headers |
| `AuthorizationParser` mapping `CSS-Account-Token` → account cookie value is CSS stock config, not ours | Confirmed | `config/ldp/metadata-parser/parsers/authorization.json` (CSS npm package source) |
| Cookie is `SameSite=Lax`, hardcoded, not configurable | Confirmed | CSS `CookieMetadataWriter.ts` (upstream source) |
| `SameSite=Lax` is site-scoped, not origin-scoped — cookie already survives Story 7.13's same-site subdomain split | Confirmed, reasoned through at 7.14 kickoff (2026-08-26) | WHATWG/MDN SameSite semantics — this is why the token rewrite turned out unnecessary |
| `/onboard/*` reads `Cookie` header only, no CORS middleware | Confirmed, and FIXED this story | `mcp-connector/src/onboardRouter.js:9` (comment), live cross-origin probe → 401, no `access-control-*` |
| nginx's `Authorization: WebID` strip rule only matches that literal scheme, and only on the CSS catch-all block, not `/onboard/` | Confirmed, prior story + re-verified 2026-08-26 | `4-4-1-nginx-openclaw-retirement-css-hardening.md`, `04-pocpod0.conf` |
| `RealBackend.root` derivation already uses `pim:storage` via `getPodUrlAll`, already provider-agnostic | Confirmed | `backoffice/pod-api.js:112-120` |
| Every UI call site defaults `Solid.connect()` to `ISSUER` with no override offered | Confirmed | `backoffice/index.html:1289,1637,1681` — all zero-arg calls |
| `Solid.connect(oidcIssuer, clientName)` already accepts an override param | Confirmed | `backoffice/pod-api.js:1196-1203` |
| `RealBackend`'s account-console methods (`_ccUrl`, `_controls`, pod create/delete, credential mint) all fetch `ISSUER`-relative `/.account/*` paths, correctly — these ARE meant to stay pinned to our own CSS instance | Confirmed | `pod-api.js:441-830` region |
| No CSS-equivalent account/pod-lifecycle API exists on other Solid implementations | Domain knowledge, stated as a hard constraint, not independently re-verified per-provider this session | — |

### Original scope fence, ACs, Tasks

_(Omitted here — see git history / this file's prior version for the full original 11-AC, 7-task draft if reviving this work. Not reproduced twice to keep this file from ballooning back to its pre-descope size.)_
