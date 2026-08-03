# Story 7.9: Backoffice-Minted Connector Credentials

Status: needs-redraft

> **REDRAFT REQUIRED 2026-08-03** — `sprint-change-proposal-2026-08-03.md`, approved by Nicolas.
> **Blocked on Story 7.10. Do not implement as written.**
>
> Trigger: Nicolas never uses the 7.4 credentials UI. He signs *out* of the backoffice,
> re-authorizes, and clicks CSS's stock "Edit account" link instead — because the unlock
> gate charges a password for the wrong thing (tokens, not pods).
>
> **What changes in the redraft:**
> 1. **Drop the account-gate scope entirely.** It moves to Story 7.10, which removes the
>    gate outright: CSS's account cookie and the `CSS-Account-Token` are the *same value*
>    (`ResolveLoginHandler.js:35-36`) and the backoffice is same-origin, so the browser
>    already holds it. No password re-entry anywhere in this flow.
> 2. **Add a hard dependency on 7.10** for both the account session and pod creation. As
>    drafted, this story automates 8.7 walkthrough steps (d)–(f) while (b)–(c) still force
>    the user out of the product — a button in the middle of a broken flow.
> 3. **Simplify AC9.** The account-token delegation still exists (the mint must stay
>    server-side to keep `clientSecret` out of the browser), but the person no longer
>    re-types a password to create it.
>
> **Everything else below stands** — the atomic-write/fail-fast analysis (AC4/AC5), the
> orphan-credential revoke path (Task 2.7), the nginx routing decision, and the SQLite
> deferral all survive the redraft unchanged.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a person onboarding to the connector**,
I want to click one button in the backoffice and receive my ready-to-paste MCP connector URL,
so that I do not have to mint credentials by hand, copy a secret out of a one-time dialog, and message an operator to edit a secrets file on a server I cannot see.

## Context / Why now

Story 8.7 documented the manual path honestly: mint AGENT client-credentials in the backoffice → hand the operator `clientId`/`clientSecret`/`webId`/`label` → operator edits `identities.json` and runs `npm run slug` → the person pastes the assembled URL into Claude. That path works, and 8.6.1 removed its worst step (no restart needed anymore). It still puts a human operator in the middle of every single onboarding and asks a newcomer to handle a raw client secret in a browser.

This story collapses steps (d)–(f) of the 8.7 walkthrough into one button.

**The blocker named in the epic sketch is already gone.** The sketch says "connector sessions are boot-time singletons, so a new identity needs either a reload path or an accepted restart." Story 8.6.1 (landed 2026-08-02) added lazy login on cache miss: a slug written to `identities.json` is picked up on its first request, no restart, already-connected identities uninterrupted. **Do not build a reload path. Do not add a restart step.** Write the entry correctly and the existing `resolveIdentity` does the rest.

Scope boundary:
- **8.7 (done, docs):** the manual path, written for a human.
- **7.9 (this):** one-button minting. The 8.7 page's steps (d)–(f) get rewritten to point at the button.
- **7.8 (separate):** roles-and-grants UI. Not here.
- Granting the agent access to containers stays **manual and owner-driven** (8.5's corrected scope). This story mints an identity; it does not grant it anything.

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| **The backoffice has no server side** | It is 4 static files (`index.html`, `pod-api.js`, `support.js`, `tokens.css`) bind-mounted read-only into the CSS container and served by CSS's `StaticAssetHandler` | `docker-compose.yml:11`, `infra/css/config.json:94-119` |
| Backoffice public URL | `https://pod.nicolasdb.eu/` (root of the CSS vhost) | Story 7.1 |
| Connector public URL | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` | 8.4/8.5 live |
| **Connector vhost is IP-allowlisted** | `allow 160.79.104.0/21` (Anthropic outbound), `127.0.0.1`, `172.16.0.0/12`, the host's own two public IPs, then `deny all`. **A teammate's browser gets 403.** | `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf:113-145` |
| nginx repo | `hetzner-gateway`, **separate repo**, own `make vps-deploy`. Not `pocpod0/infra/` | `infra_vps_structure` memory |
| TLS cert | Multi-SAN, **not wildcard** — covers exactly `claw, n8n, nicolasdb.eu, pgadmin, pod, portainer, smartflow`. A new subdomain needs a cert expansion shared with 5 production sites | `infra_vps_structure` memory |
| Account-token reality | Client-credential minting needs a `CSS-Account-Token` from `POST /.account/login/password/` (email+password) — **not** the OIDC/WebID session. The `controls.account.clientCredentials` URL only appears on the *authed* `/.account/` index, and only when that GET carries **no** `content-type` header | 7.4, live-verified |
| Mint response | `POST` to the clientCredentials control returns `{ id, secret, resource }`. **`secret` is returned exactly once and is never re-fetchable** | 7.4, live-verified |
| Existing client methods | `accountLogin`, `listClientCredentials`, `createClientCredential(name, webId)`, `revokeClientCredential(resourceUrl)` | `backoffice/pod-api.js:409-489` |
| Slug generation | `crypto.randomBytes(16).toString("base64url")` = 22 chars | `mcp-connector/scripts/gen-slug.js` |
| Identity map shape | `slug → { label, webId, clientId, clientSecret }` | `identities.example.json` |
| Identity map location | `mcp-connector/identities.json` — gitignored, **server-authored on the VPS**, excluded from `make vps-push`'s rsync, must be owned by uid 1000, **chmod 600 enforced at boot** | 8.4, `identityRegistry.js` |
| **Boot is fail-fast** | If ANY configured identity fails to log in, `bootIdentities()` calls `process.exit(1)` — the whole connector refuses to start | `mcp-server.js:658-670` |
| Lazy load | `resolveIdentity()` re-reads `identities.json` on a cache miss, logs the identity in, caches it. Negative results cached 30 s. Concurrent first-requests de-duplicated via `inFlightLogins` | `mcp-server.js:710-770` (8.6.1) |
| Registry guards already built | slug URL-safe + ≥22 chars, all 4 fields present and non-empty, duplicate `webId` refused, duplicate `clientId` refused, duplicate JSON text keys refused, over-permissive file mode refused | `identityRegistry.js` |
| Pod-name uniqueness | Global across the instance, not per-account — a duplicate pod name is refused `409 Conflict` | CSS `TemplatedPodGenerator.generate`, verified 2026-08-03 |
| Connector runtime | Node + Express 5, `express-rate-limit` 8.x already a dependency | `mcp-connector/package.json` |

## Design decisions settled before drafting (implement, don't re-litigate)

| Decision | Rationale |
|---|---|
| **The endpoint lives in `mcp-connector`, not a new service** | It is the only process that can safely write `identities.json` (same container, same uid, same file) and the only one whose lazy loader must pick the write up. A second service writing another service's secrets file across a volume is a worse design with more moving parts. |
| **Exposed at `https://pod.nicolasdb.eu/onboard/`, proxied to `mcp-connector:3939`** | Cheapest correct answer. Browser-reachable (the connector vhost's allowlist would 403 a teammate). **Same origin as the backoffice, so no CORS.** No cert expansion — `pod.` is already on the multi-SAN cert; a new subdomain would drag 5 production sites through a cert change. |
| **`/mcp/<slug>` stays allowlisted, untouched** | Only the new `/onboard/` path becomes browser-reachable, and it lives on a *different vhost*. The connector's own vhost keeps `deny all`. Do not relax `11-solid-mcp.conf`. |
| **Browser sends the account token; the server does the minting** | The only way to satisfy "secrets never flow through the browser". The person's browser signs in to the CSS account API (existing `accountLogin`), then hands that short-lived account token to `/onboard/mint`. The `clientSecret` is created server-side, written to `identities.json`, and **never serialized into any response**. |
| **Storage stays JSON. No SQLite in this story.** | The epic sketch proposed JSON → SQLite here. `identityRegistry.js` already carries validated guards that are specific to the JSON-text representation (duplicate-key detection cannot be done post-`JSON.parse`). Rewriting the store would discard tested security guards to solve a scale problem that does not exist at N=3. Revisit when the file, not the roadmap, hurts. **Never Supabase** — it would put every AGENT `clientSecret` on third-party infra. |
| **This story mints an identity; it does not grant it access** | Granting is an owner-driven manual act on the owner's own data (8.5's corrected scope). The button ends at "here is your connector URL". |

## Acceptance Criteria

1. **One button, one result.** A signed-in person clicks a single action in the backoffice and receives their MCP connector URL (`https://solid-mcp.nicolasdb.eu/mcp/<slug>`) plus their own pod root URL, displayed together, without leaving the page and without an operator being involved at any point.

2. **The `clientSecret` never reaches the browser.** Verified by inspection of every response body the endpoint can return, on both success and every error path. The mint happens server-side; the secret goes from the CSS response straight into `identities.json` and nowhere else. A grep of the response payloads for the secret returns zero hits.

3. **The connector URL is revealed once**, reusing Story 7.4's one-time-secret UX (copy affordance, explicit "this will not be shown again", cleared from client state on navigation). The slug **is** a credential — the UI must say so in the same breath it hands it over, matching `docs/team-onboarding.md`'s wording.

4. **The written entry is validated before it is persisted, using the same rules that govern boot.** The endpoint must refuse to write an entry that `loadIdentities()` would reject — specifically a duplicate `webId`, a duplicate `clientId`, a missing field, or a weak/malformed slug. **This is the story's highest-severity requirement:** `bootIdentities()` is fail-fast (`process.exit(1)` on any bad identity), so a single bad written entry bricks the connector for *every* user at the next restart. Validation runs against the merged prospective file, not just the new entry in isolation.

5. **The write is atomic and mode-preserving.** Write to a temp file in the same directory and `rename()` into place, so a crash mid-write cannot leave a truncated or empty `identities.json` (which would fail-fast the whole connector on next boot). The resulting file is mode `600` and owned by the same uid as before — verify after the write, do not assume `rename` preserved it.

6. **Concurrent mints do not lose entries.** Two people onboarding at the same moment must both end up in the file. A naive read-modify-write races and silently drops one. Serialize writes within the process, and re-read immediately before merging.

7. **No new identity requires a restart.** After a successful mint, the person's first request to their new slug works. This is 8.6.1's lazy path — assert it end-to-end, do not re-implement it.

8. **The endpoint is authenticated and rate-limited.** It accepts only a valid `CSS-Account-Token`, mints only against a WebID the token's own account controls, and is rate-limited independently of the `/mcp/` limiter. An unauthenticated or malformed request gets a generic failure that reveals nothing about existing identities.

9. **The account token is treated as the delegation it is.** It is used for the mint call and discarded: never logged, never written to disk, never held past the request. The UI states plainly what the person is authorizing when they hand it over — this is a real trust boundary, and 8.7's honesty obligation applies here too.

10. **Secrets stay out of logs.** No slug, `clientId`, `clientSecret`, or account token appears in the connector's stdout, the audit journal, or nginx's logs. The slug is returned in a **response body**, not a URL path, so nginx access logging is not a leak vector here — but assert the journal and stdout are clean, per 8.3/8.4's established grep discipline.

11. **The existing manual path still works.** `npm run slug` + a hand-edited entry remains valid; this story adds a second door, it does not remove the first. Existing configured identities are unaffected by a mint — no session churn, no interruption.

12. **`docs/team-onboarding.md` is updated.** Steps (d), (e) and (f) collapse into the button. Step (e)'s operator-in-the-middle paragraph is removed. **Keep the honest-limits section intact** — the slug is still a credential, and the `access-log/` grant is still RW-not-Append-only. The page must not gain a guarantee this story does not deliver.

13. **No regression**: `scripts/verify-http.js` passes against the live public URL, `/healthz` still returns its aggregate-only `{"ok":true}` (never a count or WebID — 8.6.1 AC7), unknown-slug 404 and `/mcp/` rate-limiting behave exactly as before, and the connector vhost's IP allowlist is unchanged.

## Tasks / Subtasks

- [ ] **Task 1 — Identity-store write path (AC: 4, 5, 6)**
  - [ ] 1.1 Add a `writeIdentity(entry)` function to `mcp-connector/src/identityRegistry.js` — the module that already owns reading and validating this file. Do not create a parallel writer elsewhere.
  - [ ] 1.2 Re-read the current file, merge the prospective entry, and run the **existing** validation over the merged result. Refactor `loadIdentities`'s validation body into a reusable `validateIdentities(parsed)` rather than duplicating the rules — two copies will drift, and a drifted copy that misses the duplicate-`webId` check bricks boot.
  - [ ] 1.3 Atomic write: temp file in the same directory → `fs.renameSync`. Set mode `600` explicitly on the temp file **before** the rename (a rename does not fix a bad mode).
  - [ ] 1.4 Verify mode and ownership after the write; throw loudly if either changed. `entrypoint.sh` runs the process as `node`/uid 1000 — a file the process cannot re-read is a self-inflicted outage.
  - [ ] 1.5 Serialize writes with an in-process promise chain (single-process service — no cross-process lock needed, and do not add one). Re-read inside the critical section, not before it.
  - [ ] 1.6 Unit-check: duplicate `webId` refused, duplicate `clientId` refused, missing field refused, short slug refused, concurrent writes both land, and a simulated crash between temp-write and rename leaves the original file intact and valid.

- [ ] **Task 2 — The mint endpoint (AC: 1, 2, 8, 9, 10)**
  - [ ] 2.1 Add `POST /onboard/mint` to `mcp-connector/src/mcp-server.js`'s Express app, mounted **outside** the `/mcp/:slug` router so its middleware and limiter are independent.
  - [ ] 2.2 Input: the person's `CSS-Account-Token` and the target agent `webId` + `label`. Reject anything else.
  - [ ] 2.3 Resolve `controls.account.clientCredentials` from the **authed** `/.account/` index — **send no `content-type` header on that GET** or CSS content-negotiates a controls-less body back (7.4's key live finding; this is the single most likely thing to silently break).
  - [ ] 2.4 Confirm the token's account actually controls the requested `webId` before minting — do not mint a credential for a WebID the caller does not own.
  - [ ] 2.5 Mint via `POST` to the control URL; capture `{ id, secret, resource }`.
  - [ ] 2.6 Generate the slug with `scripts/gen-slug.js`'s `generateSlug()` — import it, do not re-implement `randomBytes`.
  - [ ] 2.7 Persist via Task 1's `writeIdentity`. **If the write fails, revoke the just-minted credential** (`DELETE` its `resource`) before returning an error — otherwise every failed attempt leaves a live orphan credential on the person's account, which is exactly the Epic 7 orphan-accumulation pattern in a new place.
  - [ ] 2.8 Respond with `{ connectorUrl, podRootUrl }` only. Assert by test that `clientSecret` and the account token appear in no response body on any path, including error paths.
  - [ ] 2.9 Discard the account token at end of request. Never log it, the slug, or the secret. Add the new terms to the existing secret-grep discipline.
  - [ ] 2.10 Dedicated `express-rate-limit` instance for `/onboard/`, independent of `mcpLimiter` and `unknownSlugLimiter`.

- [ ] **Task 3 — Backoffice UI (AC: 1, 3, 9)**
  - [ ] 3.1 Add the one-button flow to `backoffice/index.html`, inside the existing People & apps screen next to 7.4's credential UI. Reuse the existing "Unlock app management" account-sign-in gate — do not build a second sign-in.
  - [ ] 3.2 Add a `RealBackend.mintConnector(webId, label)` method to `backoffice/pod-api.js` that POSTs to `/onboard/mint` with the account token. Same-origin, so no CORS handling is needed — if you find yourself adding CORS headers, the routing is wrong.
  - [ ] 3.3 Add a `DemoBackend` stub so the offline/demo preview renders the UI with fake data, matching 7.4's pattern.
  - [ ] 3.4 One-time reveal of the connector URL: copy affordance, "this will not be shown again", cleared on `nav()` away — mirror `mintedSecret`'s existing handling exactly.
  - [ ] 3.5 Show the person's pod root URL alongside it, with the instruction to state it to Claude on first use (8.5's live finding — the agent cannot guess it).
  - [ ] 3.6 State plainly that the URL is a credential, and what handing over the account token authorizes.
  - [ ] 3.7 WCAG 2.1 AA: 4.5:1 contrast, `focus-visible` on every new control, no color-only status. Match the existing app patterns.
  - [ ] 3.8 Bump `pod-api.js`'s cache-buster query string — the file is bind-mounted and browser-cached.

- [ ] **Task 4 — Routing + deploy (AC: 1, 13)**
  - [ ] 4.1 Add `location /onboard/ { proxy_pass http://mcp-connector:3939/onboard/; }` to `hetzner-gateway/nginx/conf.d/04-pocpod0.conf`, **before** the catch-all `location /`. **Separate repo, separate deploy.**
  - [ ] 4.2 Confirm `mcp-connector` is on the `gateway` Docker network so nginx can resolve it by container name.
  - [ ] 4.3 **Run `git status` in `hetzner-gateway` before deploying** — its `make vps-deploy` uses `rsync --delete-after`, so an unrelated uncommitted deletion silently removes a live vhost. Standing rule from `infra_vps_structure`.
  - [ ] 4.4 Leave `11-solid-mcp.conf` untouched. Re-verify its allowlist still returns 403 from off-host after deploying.
  - [ ] 4.5 **Confirm with Nicolas before any VPS deploy** (8.4 precedent). Two repos deploy here — say which, and in what order.

- [ ] **Task 5 — Live verification (AC: 7, 11, 13)**
  - [ ] 5.1 Mint an identity through the real button in a real browser against the live VPS.
  - [ ] 5.2 Confirm the new slug works **on its first request with no restart** (8.6.1's lazy path) — this is the AC7 proof.
  - [ ] 5.3 Confirm already-connected identities were uninterrupted across the mint.
  - [ ] 5.4 Attempt a duplicate-`webId` mint and confirm it is refused **before** anything is written; then confirm `identities.json` is byte-identical to before the attempt and the connector still boots.
  - [ ] 5.5 `verify-http.js` against the live public URL; `/healthz` still `{"ok":true}` aggregate-only.
  - [ ] 5.6 Grep the journal, container stdout, and nginx logs for every slug, secret, and token term → 0 hits.
  - [ ] 5.7 Confirm unknown-slug 404 and `/mcp/` rate-limiting unchanged.
  - [ ] 5.8 Confirm the failed-write path revokes its minted credential (force a write failure, then list credentials and confirm no orphan).

- [ ] **Task 6 — Docs + Epic convention (AC: 12)**
  - [ ] 6.1 Rewrite `docs/team-onboarding.md` steps (d)/(e)/(f) as the single button. Remove the operator-in-the-middle paragraph. Keep every honest-limits bullet.
  - [ ] 6.2 Update `mcp-connector/README.md`'s "Adding, removing, or rotating a person" section — the manual path stays documented (AC11), with the button as the primary route.
  - [ ] 6.3 Append a dated "Story 7.9" section to `epic-8-action-log.md` via `solid_append_resource`; verify byte-length growth.

## Dev Notes

### The one thing most likely to go wrong

`bootIdentities()` calls `process.exit(1)` if **any** identity fails to log in. That design is correct (8.3 AC3: a half-authenticated server that silently serves 3 of 4 people is worse than one that refuses to start) — but it means **this story's write path can brick the entire connector for everyone**. A duplicate `webId`, a truncated file from a non-atomic write, or a mode change that makes the file unreadable all turn into "the connector will not start" at the next restart, and the failure surfaces *later*, disconnected from the mint that caused it.

Tasks 1.2–1.4 exist entirely for this. Validate the merged file, write atomically, verify the mode afterwards.

### Where the server side comes from

There isn't one yet. The backoffice is four static files served by CSS's `StaticAssetHandler` — there is no backoffice process, no API, nothing to add a route to. The endpoint goes in `mcp-connector` (already Node + Express 5, already owns `identities.json`) and is exposed through the `pod.nicolasdb.eu` vhost so a browser can reach it on the same origin as the backoffice.

Do not add the route to the `solid-mcp.nicolasdb.eu` vhost. Its allowlist exists to keep everything except Anthropic's outbound range away from the connector, and a teammate's laptop is exactly what it 403s.

### The account-token trade

"Secrets never flow through the browser" and "the browser is where the person signs in" pull against each other. The resolution: the browser gets an account token (email+password, existing `accountLogin`), and hands *that* to our server, which does the minting. The `clientSecret` is created and consumed entirely server-side.

Be honest in the UI about what that token authorizes — it is account-scoped, not credential-scoped, so for the length of one request our server can do anything on that account. Mitigations are: used for exactly the mint sequence, never logged, never persisted, discarded at end of request. This is the same class of honesty obligation 8.7 carries; do not paper over it.

### Traps

- **The `content-type` trap.** The authed `GET /.account/` must carry **no** `content-type` header, or CSS content-negotiates a controls-less body and `controls.account.clientCredentials` comes back `undefined`. This cost real time in 7.4. It will look like "the endpoint doesn't exist".
- **The dev sandbox cannot reach the public URL** — the allowlist excludes roaming addresses; curl returns `403`. On-host requests hairpin through the VPS's own allowlisted IP. **A 403 from your laptop is not a broken deploy.**
- **Two repos deploy here.** App code: `pocpod0`, `make vps-push` + `make vps-deploy`. nginx: `hetzner-gateway`, its own `make vps-deploy`. Run `git status` in `hetzner-gateway` first — `rsync --delete-after` will remove a live vhost that is merely missing locally.
- **`identities.json` is server-authored and excluded from `vps-push`'s rsync.** It never round-trips through the repo. Do not add it to the sync, and do not test the write path by pushing a file.
- **Mint-then-fail leaves an orphan credential.** CSS mints on `POST` and the secret is unrecoverable afterwards, so a failed `identities.json` write strands a live credential nobody holds. Revoke on failure (Task 2.7). Epic 7's orphan accounts are the precedent for what "we'll clean it up later" actually means — there is still no HTTP delete path for accounts or pods.
- **Do not re-implement slug generation.** `generateSlug()` exists and its output length is what `identityRegistry.js`'s `MIN_SLUG_LENGTH` was written against. A hand-rolled generator that emits 21 chars gets refused at boot.
- **Do not build a reload path.** 8.6.1 already did it. Adding a second mechanism creates two ways for an identity to enter the cache, which is how the boot-vs-lazy strictness distinction gets accidentally collapsed.
- **`/healthz` must never leak a count.** 8.6.1 AC7. It returns `{"ok":true}` and nothing else, no matter how many identities exist.

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Read/validate the identity map | `mcp-connector/src/identityRegistry.js` — extend it, don't fork it |
| Slug generation | `generateSlug()` in `mcp-connector/scripts/gen-slug.js` |
| Account sign-in + credential mint/list/revoke | `backoffice/pod-api.js:409-489` (`accountLogin`, `createClientCredential`, `revokeClientCredential`) |
| One-time-secret reveal UX | 7.4's `mintedSecret` flow in `backoffice/index.html` |
| Demo-mode stubs | `DemoBackend` in `backoffice/pod-api.js` |
| Rate limiting | `express-rate-limit`, already a dependency and already configured twice in `mcp-server.js` |
| Lazy identity pickup | `resolveIdentity()` in `mcp-server.js` (8.6.1) — consume it, don't touch it |
| Live regression harness | `mcp-connector/scripts/verify-http.js` |
| Human-facing wording for slug-is-a-credential | `docs/team-onboarding.md` |

### Explicitly deferred — do not build here

JSON → SQLite migration (revisit when the file hurts; **never Supabase**). Roles-and-grants UI (7.8). Append-only grant support (7.6/7.8). Automated container grants — granting stays owner-driven and manual (8.5's corrected scope). Self-service slug rotation. Credential expiry/renewal. Collective/service-agent onboarding. OAuth/DCR, ACP migration (brief §7).

### Invalidated Assumptions

- **Assumption (epic sketch, 2026-08-02):** "connector sessions are boot-time singletons, so a new identity needs either a reload path or an accepted restart" → **Reality:** resolved by Story 8.6.1 (2026-08-02). `resolveIdentity()` lazily logs in on cache miss; a new entry works on its first request. **No reload path, no restart step.**
- **Assumption (epic sketch):** "store moves JSON → SQLite here" → **Reality:** deliberately deferred. `identityRegistry.js`'s duplicate-key detection operates on raw JSON text and cannot be reproduced post-parse; a store rewrite would discard tested guards to solve a scale problem that does not exist at N=3.
- **Assumption:** the backoffice can host a server-side endpoint → **Reality:** the backoffice has **no server side at all**. Four static files served by CSS's `StaticAssetHandler`. The endpoint has to live in `mcp-connector` and be routed to.
- **Assumption:** the endpoint can live on the connector's existing public hostname → **Reality:** `solid-mcp.nicolasdb.eu` is IP-allowlisted to Anthropic's outbound range plus the host itself. A person's browser gets `403`. It must be reachable via `pod.nicolasdb.eu`.
- **Assumption (7.4-era):** the OIDC/WebID session that signs a person into the backoffice can manage credentials → **Reality:** it cannot. The account API needs a separate `CSS-Account-Token` from an email+password login, and the control URL only appears on the authed index fetched without a `content-type` header.
- **Assumption:** a partial failure is recoverable by retrying → **Reality:** CSS returns the `clientSecret` exactly once. A mint that succeeds followed by a write that fails produces an unrecoverable orphan credential unless it is explicitly revoked.

### Project Structure Notes

- `mcp-connector/src/identityRegistry.js` — add `writeIdentity` + extract `validateIdentities`.
- `mcp-connector/src/mcp-server.js` — add the `/onboard/mint` route + its own limiter.
- `backoffice/index.html`, `backoffice/pod-api.js` — UI + client method + demo stub. Bind-mounted; a plain `rsync` deploys them, no rebuild.
- `hetzner-gateway/nginx/conf.d/04-pocpod0.conf` — **separate repo** — one new `location /onboard/` block.
- `docs/team-onboarding.md`, `mcp-connector/README.md` — doc updates.
- No changes to `pipeline/`, `infra/css/`, or `11-solid-mcp.conf`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-7.9-Backoffice-Minted-Connector-Credentials] — original sketch (blocker since resolved; SQLite deferred here)
- [Source: _bmad-output/implementation-artifacts/7-4-apps-and-credentials.md] — account-token reality, `content-type` trap, one-time-secret UX, mint/revoke flow
- [Source: _bmad-output/implementation-artifacts/8-6-1-lazy-identity-loading.md] — lazy load, negative cache, `/healthz` aggregate-only rule
- [Source: _bmad-output/implementation-artifacts/8-5-live-verification.md] — OWNER-boundary correction, pod-URL-not-guessable finding, allowlist/hairpin trap
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md] — identities.json ownership/exclusion, journal grep discipline, deploy confirmation practice
- [Source: mcp-connector/src/identityRegistry.js] — validation rules the write path must satisfy
- [Source: mcp-connector/src/mcp-server.js] — `bootIdentities` fail-fast, `resolveIdentity` lazy path, limiter patterns
- [Source: backoffice/pod-api.js] — `accountLogin`/`createClientCredential`/`revokeClientCredential`
- [Source: hetzner-gateway/nginx/conf.d/11-solid-mcp.conf] — the allowlist that rules out the connector vhost
- [Source: docs/team-onboarding.md] — the page this story rewrites
- Memory: `story_7_1_backoffice_deploy_patterns`, `story_7_4_credentials_patterns`, `infra_vps_structure`, `infra_vps_deploy`, `story_8_4_deploy_hardening_patterns`, `feedback_wcag_aa_standard`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-03 | Drafted. Blocker named in the epic sketch (boot-time singletons) confirmed already resolved by 8.6.1 — reload path removed from scope. Two architectural findings recorded that the sketch did not anticipate: the backoffice has no server side (static files under CSS's StaticAssetHandler), and the connector's own vhost is IP-allowlisted against browsers — jointly determining that the endpoint lives in `mcp-connector` and is routed via `pod.nicolasdb.eu/onboard/`. SQLite migration deferred with rationale. Mint-then-write-failure orphan-credential path identified and given an explicit revoke step. |
