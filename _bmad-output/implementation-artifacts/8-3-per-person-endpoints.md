# Story 8.3: Per-Person MCP Endpoints

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a team member with my own Solid pod**,
I want my own MCP endpoint URL bound to my own AGENT token,
so that when I add the connector in Claude.ai it acts as *me* — reaching my pod and not my colleagues' — without the server holding one shared identity for everybody.

## Context / Why now

Story 8.2 made the connector serve MCP over Streamable HTTP with **one endpoint and one identity** (`/mcp`, a single `.env`-driven AGENT token). That is the shape that unblocks Claude.ai reaching the pod at all, but it cannot serve a team: every person adding the connector would act as `nicolas_claude`.

The brief's T2 (per-request identity from connector-injected request headers) was **verified absent** on this Claude Pro account on 2026-07-30 — *Add custom connector* exposes only `Name`, `Remote MCP server URL`, and OAuth client id/secret. So **T3 — one endpoint path per person — is the retained path for the MVP, not a fallback** (brief §5 T3).

8.2 deliberately left the door open for exactly this: `buildMcpServer(session)` is already a plain function of a session rather than module-level wiring, precisely so 8.3 could add routing without a rewrite. This story spends that affordance.

**The honest security trade-off, to be documented, not glossed:** with per-person URLs, part of the protection is the *secrecy of the URL* on top of the WAC token. That means long, random, unguessable slugs — never a person's first name, never committed to the repo, never pasted into a shared channel — plus a cheap rotation path when one leaks (brief §5 T3 says this explicitly).

Scope boundary against neighbouring stories:
- **8.3 (this):** path→identity routing, N identities loaded from non-versioned config, unknown-slug behavior, isolation proven live.
- **8.4:** VPS deploy — nginx/TLS on a dedicated subdomain, systemd, rate limiting, Anthropic IP allowlist, audit journal.
- **8.6:** team onboarding doc — how a real colleague gets their pod, agent account, token and URL.

Do not build 8.4's rate limiting or audit journal here.

## Acceptance Criteria

1. **Path-routed identities:** the server serves `POST /mcp/<slug>` where each `<slug>` maps to its own AGENT identity. The single-identity `POST /mcp` from 8.2 either becomes one configured identity or is removed — decide explicitly and record it in Dev Notes; do not leave an undocumented shared-identity endpoint serving alongside the per-person ones, because that is precisely the thing this story exists to eliminate.
2. **Identities loaded from non-versioned config:** slug → `{clientId, clientSecret, webId, label}` comes from a gitignored file or env, never from a committed file. The repo must contain only an `.example` template with placeholder values. Adding a person is a config edit plus a restart — no code change.
3. **One Solid session per identity, created at boot, not per request:** every configured identity logs in once at startup with `keepAlive: true` and is reused for the process lifetime — 8.2's AC5 rule, now N times. Startup logs each authenticated WebID (already safe per 8.2's AC8) and never the secrets. If **any** configured identity fails to log in, the process exits with a clear message naming *which* slug failed — a half-authenticated server that silently serves 3 of 4 people is worse than one that refuses to start.
4. **Unknown or malformed slug returns 404 and reveals nothing:** a wrong slug must not disclose whether that slug exists, how many identities are configured, or any WebID. A generic 404 JSON-RPC error body. Do not log the full attempted slug at info level (it may be a near-miss of a real secret URL — logging it copies the secret into the log file).
5. **Isolation proven live, not asserted:** with two distinct identities configured, a `tools/call` on identity A's endpoint reaches A's resources and is **denied** on a resource only B can read. The denial must surface as 8.2's actionable error text, not a stack trace. This is the story's real claim — routing that "works" without an isolation test proves nothing.
6. **Slug rotation is a documented, cheap operation:** changing a person's slug is a config edit + restart, and the README states the leak-response procedure. Slugs are generated with a CSPRNG (`crypto.randomBytes`), not `Math.random()`, and are long enough to be unguessable (≥ 22 chars of URL-safe entropy). Ship a tiny generator (`npm run slug` or equivalent) so nobody hand-invents a weak one.
7. **No secret or slug reaches the logs or the repo:** extends 8.2's AC8. Startup may log WebIDs and *labels*, never slugs, client ids or secrets — a slug in a log is a credential in a log. Verify by grepping a real boot log, including a forced-failure path.
8. **8.2's guarantees survive:** all 7 tools still work over each per-person endpoint with unchanged behavior and annotations; stateless per-request transport+server is retained; `GET`/`DELETE` on an MCP path still return 405; `GET /healthz` still returns `{ok:true}` with no WebID and no identity count.
9. **README updated:** per-person URL scheme, how to add/remove/rotate a person, the URL-secrecy trade-off stated plainly, and the local verification command. Public exposure remains Story 8.4 — say so.

## Tasks / Subtasks

- [x] Task 1: Identity registry (AC: #2, #6)
  - [x] 1.1 Define the config shape: a gitignored `identities.json` (or `IDENTITIES_*` env) mapping `slug → {clientId, clientSecret, webId, label}`. Commit `identities.example.json` with obvious placeholders only. Add the real file to `.gitignore` **before** creating it — an accidental commit of this file is a full credential leak for every team member at once.
  - [x] 1.2 Load and validate at boot: reject duplicate slugs, missing fields, and slugs that are too short or not URL-safe. Fail with a message naming the offending slug's *label*, not the slug.
  - [x] 1.3 Add a slug generator script using `crypto.randomBytes` → URL-safe base64/base58, ≥ 22 chars. Wire it as an npm script.
- [x] Task 2: Boot N sessions (AC: #3, #7)
  - [x] 2.1 At startup, `getAgentSession({ clientId, clientSecret, oidcIssuer, keepAlive: true })` per identity. `auth.js` **already accepts these as opts** (`auth.js:39-43`) — no change needed there; do not refactor it.
  - [x] 2.2 Build a `slug → { session, label, webId }` map. Fail fast naming the failing identity's label if any login fails.
  - [x] 2.3 Confirm the boot log shows one WebID line per identity and contains no slug/secret.
- [x] Task 3: Route by slug (AC: #1, #4, #8)
  - [x] 3.1 Replace the fixed `app.post("/mcp", ...)` with a slug-parameterised route. Look the slug up in the map; on miss return a generic 404 JSON-RPC error. Keep the per-request transport + `buildMcpServer(session)` construction exactly as 8.2 left it — pass the *matched identity's* session.
  - [x] 3.2 Keep `GET`/`DELETE` on MCP paths at 405 and `/healthz` unchanged and identity-free.
  - [x] 3.3 Decide the fate of bare `/mcp` (AC1) and record the decision + reason in Dev Notes.
- [x] Task 4: Prove isolation live (AC: #5)
  - [x] 4.1 Provision a **throwaway** second identity rather than borrowing a colleague's: create a throwaway CSS account + pod, mint client credentials for it, and configure it as the second slug. See Dev Notes for why a throwaway and not `alex`/`chabivdb`, and for the exact credential-mint flow (already live-confirmed, do not re-derive it).
  - [x] 4.2 Extend `scripts/verify-http.js` (or add a sibling) to drive **both** endpoints: each reaches its own resource, and identity B is denied on a resource only A can read, with the documented error text. Commit it so 8.5 can re-run it.
  - [x] 4.3 Clean up: revoke the throwaway's client credentials when done. Note honestly in the story that the throwaway *account shell* cannot be removed over HTTP (see Dev Notes) — that gap is Story 7.7's job, not this one's.
- [x] Task 5: Docs + Epic 8 convention (AC: #9)
  - [x] 5.1 README: URL scheme, add/remove/rotate a person, the URL-secrecy trade-off in plain words, verification command, and an explicit "public exposure is 8.4" note.
  - [x] 5.2 Per the Epic 8 convention (binding since 8.2): **append** a dated section to `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (read existing, write existing + new — never overwrite) and add a "Story 8.3" section with its proof table to `epic-8-progress-report.md`.

## Dev Notes

### Invalidated Assumptions

- **Assumption:** T2 (per-request identity via connector-injected request headers) may be available, making secret URLs unnecessary. → **Reality:** verified absent 2026-07-30 on this Claude Pro account. **T3 is the retained path, not a fallback.** Revisit only if Anthropic's changelog adds the field.
- **Assumption (from Story 8.1 AC3):** "no second Solid WebID exists in this environment." → **Reality: false as of 2026-07-31.** A live inventory found real human accounts `chabivdb` (Xavier) and `alex` (with an issued `obsidian_*` credential) alongside `nicolas`, `nicolas_claude` and `hyperscope_ndb`. Multi-identity work is no longer blocked on inventing an identity. **But do not test isolation against a colleague's real pod** — technical access is not consent, and a failed isolation test means touching someone's real data. Use a throwaway (Task 4.1).
- **Assumption:** the VPS has ~17 orphan CSS accounts. → **Reality:** 29 account records as of 2026-07-31; Story 7.1's own e2e runs added ~12 more. The gap grew rather than closing. Relevant here only as a reason to keep this story's throwaway footprint to exactly one account and to revoke its credentials.
- **Assumption:** the 1355 pod folders on the server are orphan clutter. → **Reality:** they are overwhelmingly Epic 1–6 pipeline simulation output (`student-*`, `admin-*`, `teacher-*`, `parent-*`, `unknown-*`, `external-*`), mostly with no account record at all. Do not "clean" them and do not conflate the pod-folder count with the account count.
- **Assumption:** the Story 7.1 root-ACL incident may still be live. → **Reality:** remediated. One account record still lists `baseUrl` as the site root, but `/data/.acl` contains only the minimal `<#public>` `acl:Read` reconstruction — no stray Control. Inert bookkeeping, not a risk to this story.
- **Assumption:** SDK examples showing `@modelcontextprotocol/node` / `@modelcontextprotocol/express` packages apply here. → **Reality:** those are **v2** package names. This project is pinned to SDK **1.x** and uses `createMcpExpressApp` from `@modelcontextprotocol/sdk/server/express.js`. Do not copy v2 import paths from current docs; the 1.x API in 8.2's `mcp-server.js` is the reference.

### Verified API surface

- `auth.js:39-43` — `getAgentSession(opts)` already reads `opts.clientId` / `opts.clientSecret` / `opts.oidcIssuer` with env fallbacks, and `opts.keepAlive`. **This is the multi-identity hook and it already exists.** Call it N times with explicit opts. Do not restructure `auth.js`.
- `mcp-server.js` (post-8.2) — `buildMcpServer(session)` returns a fresh `McpServer` with all 7 tools registered, taking the session as its only input. This is the per-identity factory; it needs no change.
- Express 5 route params work normally on the app returned by `createMcpExpressApp()` — it is a bare Express app with DNS-rebinding middleware applied and no routes mounted. `app.post("/mcp/:slug", ...)` is fine.
- **Client-credentials mint flow (live-confirmed 2026-07-23, do not re-derive):** account login `POST /.account/login/password/` `{email,password}` → `{authorization}` (the CSS-Account-Token). The `controls.account.clientCredentials` URL appears only on the **authenticated** `GET /.account/` index, and that GET must carry **no `content-type` header** or CSS content-negotiates away the controls. Then `POST {ccUrl}` `{name, webId}` → `{id, secret, resource}` with the secret shown **once**. Revoke with `DELETE {resource}` → 200.

### Decision: fate of bare `/mcp` (Task 3.3)

**Removed, not kept as a configured identity.** `mcp-server.js` no longer has
a `POST /mcp` route at all — only `POST /mcp/:slug`. Keeping bare `/mcp`
alive (even pointed at one identity) alongside the per-person routes would
be exactly the undocumented shared-identity endpoint AC1 says not to leave
running. Anyone who wants the old single-identity shape back configures it
as one entry in `identities.json` and uses that entry's slug.

### Do not touch

`wacManager.js` and `podClient.js` remain live-verified from 8.1 and untouched through 8.2. This story is routing + identity wiring only. `auth.js` needs no change at all (its opts already support this). If a bug surfaces in the WAC layer during Task 4's isolation test, **note it — do not silently fix it inside a routing story.**

### Why a throwaway and not a real colleague's pod

`alex` and `chabivdb` are real people with real data. An isolation test's *success* condition is a denial, which means the failure mode is unauthorised access to a colleague's pod. Technical access is not consent. Provision one throwaway account for the test and revoke its credentials afterwards.

Be honest in the story record about the residue: CSS exposes **no HTTP account/pod delete** (`DELETE /.account/account/{id}/` → 404, `DELETE .../pod/{id}/` → 400; only client-credentials are deletable). So the throwaway *account shell* will persist. That is a known, tracked gap — **Story 7.7 (delete pod with ceremony) is being drafted to close it** — not something to hide or to solve here.

### Explicitly deferred — do not build here

- **Rate limiting, TLS/nginx/systemd, Anthropic IP allowlist, audit journal** — all Story 8.4.
- **OAuth-based per-user auth** — would remove the secret-URL trade-off entirely, but depends on connector features not available today (T2). Out of scope.
- **A UI for managing identities** — config file + restart is the MVP. No admin surface.

### Environment quirks (carried forward — these will otherwise burn time again)

- This dev sandbox's `node` does **not** inherit `process.cwd()` from Bash `cd`, **and does not inherit shell-set environment variables** (confirmed during 8.2's review: `PORT=x node ...` had no effect). Invoke with absolute paths and `--env-file=<abs>/.env`. Test env-var-dependent logic by unit-checking the parsing function directly rather than through the process.
- With `createMcpExpressApp()` defaults, connect to `http://127.0.0.1:<port>/...` — **not** `localhost` or a LAN IP. DNS-rebinding protection rejects a mismatched `Host` header and it looks like a protocol failure.
- Live server state is checkable via `ssh hetzner` → `docker exec community-solid-server ...` (data at `/data`, accounts at `/data/.internal/accounts/data`).

### Testing approach (there is no test framework here — do not add one)

`mcp-connector/` has **no** test runner, linter or CI, and neither 8.1 nor 8.2 added one. The established validation pattern for this package is:
1. `node --check` on every touched file (syntax gate),
2. unit-check pure functions by requiring/evaluating them directly (8.2's review did this for `parsePort` because shell env vars don't reach `node` in this sandbox),
3. a committed live-verification script driven by the SDK's own MCP client (`scripts/verify-http.js`) as the real acceptance evidence.

Extend that script for this story (Task 4.2) rather than introducing Jest/Vitest/Mocha. A new test framework is scope creep and would be the only one in the package.

### Secret-handling specifics

- `chmod 600` the identities file, same rule as `.env` (brief §5 T5).
- `mcp-connector/.gitignore` currently contains only `node_modules/` and `.env`. **Add the identities filename to it in the same commit that introduces the file** — ideally before the file exists locally.
- Forward-looking risk for 8.4: slugs live in the URL **path**, so nginx/systemd access logs will capture them by default. That turns a routine access log into a credential store. Flag it in the story record so 8.4 configures log filtering deliberately; do not build the nginx config here.

### Project Structure Notes

- All work in `mcp-connector/`. CommonJS (`require`) — every file in `src/` uses it; do not introduce ESM.
- Keep `npm run mcp` as the entry point so existing docs stay true.
- `ALLOWED_HOSTS`, `PORT` (validated via `parsePort`) and `HOST` env vars already exist from 8.2's review — reuse, don't reinvent.
- `.env` holds the single AGENT credential today; the new identities file is a **separate** gitignored artifact. **OWNER credentials must never enter this environment** (brief §4.1).

### References

- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#5-tâches] — T3 (per-person endpoints, retained path), T2 (header auth verified unavailable), T4/T5 (deferred to 8.4)
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#4-contraintes-darchitecture] — §4.1 two-token model, §4.2 no shared-account pod hosting, §4.3 agent scope, §4.4 human confirmation on permission writes
- [Source: _bmad-output/implementation-artifacts/8-2-http-transport.md] — HTTP transport, stateless per-request model, `buildMcpServer(session)` factoring, error mapping, `parsePort`/`ALLOWED_HOSTS`, and the Review Findings section's live-verification discipline
- [Source: _bmad-output/implementation-artifacts/8-1-wac-hardening-verification.md] — live-verified `wacManager.js`/`podClient.js`, documented Control-access error wording
- [Source: mcp-connector/src/auth.js#39-43] — `getAgentSession(opts)` multi-identity hook
- [Source: _bmad-output/implementation-artifacts/epic-8-progress-report.md#convention-binding-for-82-onward] — append-only action log + per-story proof table

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- Live boot test with a single real identity (AGENT/nicolas_claude under a generated slug): confirmed authenticated-WebID log line, no slug/secret in logs, unknown-slug 404, GET-on-real-slug 405, `/healthz` unauthenticated, and `scripts/verify-http.js` passing all 7 tools against `/mcp/<slug>`.
- Live two-identity boot + `scripts/verify-isolation.js` run: identity B wrote+read its own private resource; identity A denied on that resource with the documented error text (`"Access denied — this agent lacks the required WAC permission on that resource."`); identity A still reached its own known-good container afterward.
- Throwaway CSS account/pod provisioned live via the full HTTP flow (`POST /.account/account/` → password-login register → pod create → client-credentials mint), then the credentials revoked at the end (`DELETE` on the credentials resource → 200, confirmed gone via 404 on re-GET).
- Full session narrative and proof table: `epic-8-progress-report.md` (Story 8.3 section) and the appended dated entry on `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md`.

### Completion Notes List

- All 9 ACs satisfied and live-verified (not just asserted): path-routed identities, gitignored config with committed `.example` template, N sessions booted at boot with fail-fast naming the failing label, unknown-slug 404 leaking nothing, isolation proven live between a real identity and a provisioned throwaway, CSPRNG slug generator wired as `npm run slug`, all 7 tools + 8.2 guarantees (405s, `/healthz`) retained, and README updated.
- Bare `/mcp` was removed rather than kept as one configured identity — decision and reasoning recorded in Dev Notes ("Decision: fate of bare `/mcp`").
- Added one check beyond the literal task list: after each identity logs in, the server verifies `session.info.webId` matches the configured `webId` and fails fast (naming the label) on mismatch — this caught a real bug during testing (see below) and is worth having permanently, since a stale/typo'd config entry would otherwise surface as a confusing downstream tool error instead of a clear boot failure.
- Environment quirk reconfirmed and worth flagging for future stories: this sandbox's `dotenv` treats an unescaped `#` mid-value as a comment start even with no preceding space, so any ad hoc re-parsing of `.env` (outside `auth.js`'s own load path, which is unaffected) can silently truncate `AGENT_WEBID`'s `#me` fragment. Caught by the webId-mismatch check above during manual test-fixture setup — not a product bug, `auth.js` itself was never affected.
- Throwaway account `story83throwaway1785486779`'s account/pod shell persists (CSS has no HTTP delete for account or pod) — consistent with the story's own Dev Notes and tracked under Story 7.7, not fixed here.
- No test framework was introduced, per the story's own Dev Notes guidance; validation was `node --check` on every touched file, direct unit-checks of `identityRegistry.js`'s validation logic (valid config, too-short slug, missing field, duplicate top-level key), and the two committed live-verification scripts (`verify-http.js`, new `verify-isolation.js`).

### File List

- `mcp-connector/src/identityRegistry.js` (new) — load/validate `identities.json`
- `mcp-connector/identities.example.json` (new) — committed placeholder template
- `mcp-connector/scripts/gen-slug.js` (new) — CSPRNG slug generator, wired as `npm run slug`
- `mcp-connector/scripts/verify-isolation.js` (new) — committed live isolation-proof script
- `mcp-connector/src/mcp-server.js` (modified) — N-identity boot, `/mcp/:slug` routing, bare `/mcp` removed, webId-mismatch fail-fast
- `mcp-connector/package.json` (modified) — added `slug` npm script
- `mcp-connector/.gitignore` (modified) — added `identities.json`, `.throwaway-identity.json`
- `mcp-connector/README.md` (modified) — per-person endpoint docs, add/remove/rotate procedure, isolation-verification command
- `_bmad-output/implementation-artifacts/epic-8-progress-report.md` (modified) — Story 8.3 section
- `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (live pod resource, appended) — Story 8.3 dated entry

## Change Log

- 2026-07-31 — Story 8.3 implemented and live-verified: per-person `/mcp/<slug>` routing, N-identity boot with fail-fast, gitignored identity config, CSPRNG slug generator, live isolation proof against a provisioned-and-cleaned-up throwaway identity, README updated, Epic 8 action log + progress report appended.
