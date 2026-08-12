# Story 7.9: Backoffice-Minted Connector Credentials

Status: ready-for-review — deployed, Task 7 live click-through completed end-to-end by Nicolas (mint → claude.ai → read/list confirmed). One commit (`7a121f6`, container-read error fix) built and tested but NOT yet deployed.

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a person onboarding to the connector**,
I want to click one button in the backoffice and receive my ready-to-paste MCP connector URL — and to see, on that same screen, every grant that exists in my name and be able to kill any of them,
so that I never have to hand-mint a credential, never have to message an operator to edit a secrets file on a server I cannot see, and never hold a key I have no way to take back.

## Context — read this before planning any work

**This story is the one that removes the operator from onboarding.** That is its entire value and its entire scope discipline. It sits at position 1 on the revised critical path to "a second person onboards alone" (`sprint-change-proposal-2026-08-11.md#8`, revised sequence: 8.9 → **7.9** → 8.7 Task 4+ → 7.11a → 7.5). Anything that does not shorten a newcomer's first hour belongs somewhere else, and this story names where.

Three things changed since the 2026-08-03 draft, and all three shrink or sharpen it:

1. **Story 7.10 shipped (2026-08-03, done).** It deleted the "Unlock app management" email/password gate outright and it built pod creation in the backoffice. Both were prerequisites this story used to be missing. The account session now rides the `css-account` cookie with `credentials: 'include'` — **no password re-entry anywhere in this flow.** The old draft's whole account-gate scope is gone; do not rebuild any part of it.
2. **Story 8.9 shipped (2026-08-11, live-verified).** The `access-log/` journal is now `acl:Append`-only and receipts are POSTed one resource per read, each carrying a **reserved `underGrant` field that is `null` today** (`mcp-connector/src/receipt.js:99`). 8.9 also handed this story two things: per-slug attribution (moved here explicitly, `8-9-access-journal-tamper-spike.md:15`) and the finding that a use's link to its justification **cannot be reconstructed after the fact** — timestamp correlation is a guess.
3. **The consent-loop proposal landed today (2026-08-11).** It identifies exactly one time-sensitive item, and it is inside this story: the grant table must reserve `grantUri` plus the justification fields **now**, because 7.9 is the story that creates that table.

### Why the reserved fields are not optional and not scope creep

The grant-table shape specified in `epics.md:372` is:

```
slug -> { credentialRef, webId, containers[], createdAt, expiresAt, lastUsedAt, revoked }
```

Every field there is **credential bookkeeping** — which key, which containers, is it still live, when was it last used. All of it answers *what is technically permitted*. **None of it records what it was for.** No purpose, no exclusions, no consequence-of-refusal, no requester distinct from the credential holder (`sprint-change-proposal-2026-08-11-consent-loop.md:75`).

The argument for adding those fields in this story is a **migration-window argument, not a feature argument**:

> Adding a purpose/justification dimension to a table being designed now is a field list. Adding it to a table already in production, already minted against, with live credentials in it, is a migration. The window is open and it closes when 7.9 ships. (`sprint-change-proposal-2026-08-11-consent-loop.md:77`)

This is the same reasoning Story 8.9 used for `underGrant`, and the two are two ends of one wire: `grantUri` is the value that will eventually populate `underGrant` in every receipt. Neither end is useful alone, and neither can be retrofitted onto records already written.

**Scope fence — read this twice.** This story:

- **DOES** add `grantUri` and the nullable `purpose` / `scope` / `excluded` / `consequenceOfRefusal` fields to the grant record, using the `poc:ConsentGrant` names that already shipped in Story 5.5.
- **DOES NOT** build consent-request intake.
- **DOES NOT** mint `poc:ConsentGrant` RDF resources.
- **DOES NOT** add an approval step to onboarding. The preemptive-grant path stays the default; review-before-access is explicitly *not* introduced here, because "every access needs a human decision" would turn the second person's first experience into waiting on the first person (`sprint-change-proposal-2026-08-11-consent-loop.md:98`).
- **DOES NOT** populate `underGrant` in receipts. It stays `null` until the connector actually mints grant resources.

Those four belong to the **next story, not yet drafted**, listed as items 3 and 4 of the consent-loop proposal (`sprint-change-proposal-2026-08-11-consent-loop.md:111-114`). If during implementation you find yourself designing a request form, an approval queue, or a Turtle template — stop, you have left this story.

### Scope boundary against neighbouring stories

- **8.7 (done, docs):** the manual path, written for a human. This story rewrites its steps (d)–(f) into the button.
- **7.10 (done):** account session + pod creation. Consume it; do not touch it.
- **8.9 (done):** the journal and its Append-only grant. This story adds *attribution* to it, nothing else. The detection half (anomaly signals, alerting, identity-level rate limiting) is in `post-poc-backlog.md` and stays there.
- **7.11b (deferred post-PoC):** roles as grant bundles, collective-account view, receipt surfacing.
- **7.6 (deferred post-PoC):** file-manager hardening.
- **Granting the agent access to containers stays manual and owner-driven** (8.5's corrected scope). This story mints an identity and *records* which containers a grant covers; it does not perform the WAC grant.
- **Consolidation of receipts** (weekly fold into triples/SQLite/one document) is consent-loop item 5, "later, cheap once the above exists". Not here.

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| **The backoffice has no server side** | 4 static files (`index.html`, `pod-api.js`, `support.js`, `tokens.css`) bind-mounted read-only into the CSS container, served by CSS's `StaticAssetHandler` | `docker-compose.yml:11`, `infra/css/config.json:94-119` |
| **The account cookie IS the account token** | `css-account`, set `Path=/; SameSite=Lax`, deliberately **not** `HttpOnly`, TTL 14 days refreshed on use. `CSS-Account-Token` maps to the same metadata term — cookie and header are interchangeable | `ResolveLoginHandler.js:35-36`, `CookieMetadataWriter.js:39-42`, `BaseCookieStore.js`; memory `css_account_pod_lifecycle_facts` |
| **The unlock gate is gone** | Story 7.10 deleted `accountLogin(email,password)` and the "Unlock app management" prompt. `RealBackend._accountControls()` resolves controls lazily from the cookie via `credentials: 'include'`, caches them, and degrades to an honest sign-in prompt on 401 | `7-10-account-and-pod-lifecycle.md`; memory `story_7_10_pod_lifecycle_patterns` |
| **The `content-type` trap is still live** | The authed `GET /.account/` must carry **no** `content-type` header or CSS content-negotiates a controls-less body and `controls.account.clientCredentials` comes back `undefined` | 7.4 live finding, re-confirmed for 7.10 |
| Mint response | `POST` to the clientCredentials control returns `{ id, secret, resource }`. **`secret` is returned exactly once and is never re-fetchable** | 7.4, live-verified |
| Existing client methods | `listClientCredentials`, `createClientCredential(name, webId)`, `revokeClientCredential(resourceUrl)`, `createPod`, `listPods` | `backoffice/pod-api.js` |
| **Pod ownership is per-WebID, not per-account** | `createPod()` must pass `settings: { webId }` or CSS mints a brand-new WebID and the pod becomes unmanageable from the original session | memory `architecture_pod_webid_ownership`; `CreatePodHandler.js` / `BasePodCreator.js` |
| Backoffice public URL | `https://pod.nicolasdb.eu/` (root of the CSS vhost) | Story 7.1 |
| Connector public URL | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` | 8.4/8.5 live |
| **Connector vhost is IP-allowlisted** | `allow 160.79.104.0/21` (Anthropic outbound), `127.0.0.1`, `172.16.0.0/12`, the host's own two public IPs, then `deny all`. **A teammate's browser gets 403.** | `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf:113-145` |
| nginx repo | `hetzner-gateway`, **separate repo**, own `make vps-deploy` | memory `infra_vps_structure` |
| TLS cert | Multi-SAN, **not wildcard**. A new subdomain needs a cert expansion shared with 5 production sites | memory `infra_vps_structure` |
| Slug generation | `crypto.randomBytes(16).toString("base64url")` = 22 chars; `MIN_SLUG_LENGTH = 22` | `mcp-connector/scripts/gen-slug.js`, `identityRegistry.js:32` |
| Identity map shape **today** | `slug → { label, webId, clientId, clientSecret }` | `identities.example.json` |
| Identity map location | `mcp-connector/identities.json` — gitignored, **server-authored on the VPS**, excluded from `make vps-push`'s rsync, owned by uid 1000, **chmod 600 enforced at boot** | 8.4, `identityRegistry.js` |
| **Boot is fail-fast** | If ANY configured identity fails to log in, `bootIdentities()` calls `process.exit(1)` — the whole connector refuses to start | `mcp-server.js:658-670` |
| Lazy load | `resolveIdentity()` re-reads `identities.json` on cache miss, logs in, caches. Negative results cached 30 s. Concurrent first-requests de-duplicated via `inFlightLogins` | `mcp-server.js:710-770` (8.6.1) |
| Registry guards already built | slug URL-safe + ≥22 chars, all 4 fields present and non-empty, duplicate `webId` refused, duplicate `clientId` refused, duplicate JSON text keys refused, over-permissive file mode refused | `identityRegistry.js:42,96,120,197` |
| **Receipts are Append-only and one-resource-per-read** | `receipt.js` POSTs one JSON receipt per read; the agent is denied listing, read-back, overwrite and delete of its own receipts (403 on all four, live-verified) | 8.9 Dev Agent Record |
| **`underGrant` is reserved and `null`** | Explicitly `null` rather than omitted, so a later reader can distinguish "no grant recorded" from "predates the field" | `mcp-connector/src/receipt.js:38,99` |
| CSS denial codes | **401 to an *unauthenticated* denial, 403 to an *authenticated* one.** The code reflects whether credentials were presented, not the mode | 8.9 live-verified |
| CSS write success code | **205 Reset Content**, not 200 | 8.9 live-verified |
| Reading `.acl` needs `acl:Control` | A 403 on `GET .acl` is **not** evidence about the grant. `WAC-Allow: user="..."` on any GET is CSS's own statement of the effective grant | 8.9 live-verified |
| `poc:ConsentGrant` vocabulary (shipped) | `requestedBy`, `purpose`, `scope`, `excluded`, `consequenceOfRefusal`, `grantedAt`, `revokedAt` (tombstone, empty string until revoked), `expiresAt` | `5-5-consent-grant-as-rdf-resource.md:17-24`, `architecture.md:383` |
| Pod-name uniqueness | Global across the instance, not per-account — a duplicate is refused `409 Conflict` | `TemplatedPodGenerator.generate`, verified 2026-08-03 |
| Connector runtime | Node + Express 5, `express-rate-limit` 8.x already a dependency | `mcp-connector/package.json` |
| **The "Requests" tab is fabricated** | `S.requests` is hardcoded seed data (`backoffice/index.html:807`), rendered at `:672-694`, badged in the sidebar at `:1525` and on the home screen at `:1682-1686`. Never persisted, no intake. Known since Story 7.2 | `sprint-change-proposal-2026-08-11-consent-loop.md:59` |

## Design decisions settled before drafting (implement, don't re-litigate)

| Decision | Rationale |
|---|---|
| **The endpoint lives in `mcp-connector`, not a new service** | It is the only process that can safely write `identities.json` (same container, same uid, same file) and the only one whose lazy loader must pick the write up. A second service writing another service's secrets file across a volume is a worse design with more moving parts. |
| **Exposed at `https://pod.nicolasdb.eu/onboard/`, proxied to `mcp-connector:3939`** | Browser-reachable (the connector vhost's allowlist would 403 a teammate). **Same origin as the backoffice**, so no CORS *and* the `css-account` cookie is sent automatically. No cert expansion — `pod.` is already on the multi-SAN cert. |
| **`/mcp/<slug>` stays allowlisted, untouched** | Only the new `/onboard/` path becomes browser-reachable, and it lives on a *different vhost*. Do not relax `11-solid-mcp.conf`. |
| **The browser forwards its account cookie; the server does the minting** | The only way to satisfy "secrets never flow through the browser". Same-origin `fetch(..., {credentials:'include'})` carries `css-account` to `/onboard/`; the connector uses it as a `CSS-Account-Token` for exactly the mint sequence. The `clientSecret` is created server-side, written to `identities.json`, and **never serialized into any response**. **No password is ever re-typed** — that was the 2026-08-03 finding that killed the old draft. |
| **Storage stays JSON. No SQLite in this story.** | `identityRegistry.js`'s duplicate-key detection operates on raw JSON *text* and cannot be reproduced post-`JSON.parse`. Rewriting the store would discard tested security guards to solve a scale problem that does not exist at N=3. Revisit when the file, not the roadmap, hurts. **Never Supabase** — it would put every AGENT `clientSecret` on third-party infra. |
| **Revocation is a tombstone, not a deletion** | `revoked` is set and the row is kept, mirroring `poc:revokedAt`'s tombstone pattern (`5-5-consent-grant-as-rdf-resource.md:137-139`). A deleted row destroys the record that the grant ever existed, which is precisely what the journal is supposed to be able to explain. |
| **`expiresAt` defaults to `null` = never expires** | Expiry is opt-in in this story. It ships *with* its UX or it does not ship at all — see AC10/AC11. |
| **This story mints and revokes; it does not grant container access** | Granting is an owner-driven manual act on the owner's own data (8.5's corrected scope). `containers[]` **records** the intended scope; it does not apply it. Say so in the UI or the field becomes a lie. |

## Acceptance Criteria

1. **One button, one result.** A signed-in person clicks a single action in the backoffice and receives their MCP connector URL (`https://solid-mcp.nicolasdb.eu/mcp/<slug>`) plus their own pod root URL, displayed together, without leaving the page, without re-typing a password, and without an operator being involved at any point.

2. **The `clientSecret` never reaches the browser.** Verified by inspection of every response body the endpoint can return, on success and on **every** error path. A grep of all response payloads for the secret returns zero hits.

3. **The connector URL is revealed once**, reusing Story 7.4's one-time-secret UX (copy affordance, explicit "this will not be shown again", cleared from client state on navigation). The slug **is** a bearer credential and the UI says so in the same breath it hands it over, matching `docs/team-onboarding.md`'s wording.

4. **The grant record carries the full specified shape, including the reserved justification fields.** Each entry is:

   ```
   slug -> {
     label, webId, clientId, clientSecret,      // existing, unchanged — boot still needs these
     grantId,                                    // non-secret stable identifier, safe to publish
     grantUri,                                   // null today; the future poc:ConsentGrant URI
     credentialRef,                              // the CSS credential resource URL — required to revoke
     containers: [],                             // recorded intended scope; NOT applied by this story
     createdAt, expiresAt, lastUsedAt, revoked,  // epics.md:372 bookkeeping
     purpose, scope, excluded, consequenceOfRefusal   // RESERVED, nullable, all null today
   }
   ```

   The four justification fields and `grantUri` are **written as explicit `null`, never omitted** — the same convention `receipt.js` uses for `underGrant`, so a later reader can distinguish "nothing recorded" from "predates the field". Their names mirror the `poc:ConsentGrant` predicates exactly (`purpose`, `scope`, `excluded`, `consequenceOfRefusal`) so that porting the vocabulary later is a rename of nothing. **Nothing in this story populates them, and nothing in this story reads them.** A test asserts they are present and null on a freshly minted grant.

5. **Backward compatibility with existing entries is proven.** Entries already in the live `identities.json` carry only the original four fields. The registry must load them without error and treat every new field as absent-means-null. A test loads a pre-7.9-shaped file and asserts a clean boot. **This is the whole point of doing it now**: adding these fields must be a field list, not a migration.

6. **The written entry is validated before it is persisted, using the same rules that govern boot.** The endpoint must refuse to write an entry that `loadIdentities()` would reject — duplicate `webId`, duplicate `clientId`, missing required field, weak or malformed slug. Validation runs against the **merged prospective file**, not the new entry in isolation. **This is the story's highest-severity requirement:** `bootIdentities()` is fail-fast (`process.exit(1)`), so one bad written entry bricks the connector for *every* user at the next restart, and the failure surfaces later, disconnected from the mint that caused it.

7. **Revoked entries are excluded from boot and from active resolution, but retained in the file.** A revoked grant's CSS credential no longer exists, so a login attempt against it **fails** — and under AC6's fail-fast boot that would take the whole connector down. Therefore: `bootIdentities()` and `resolveIdentity()` must both skip `revoked` entries, and the duplicate-`webId` / duplicate-`clientId` checks must **ignore revoked rows** so that a person who revokes can mint again for the same WebID. A test covers exactly this sequence: mint → revoke → restart (boots clean) → mint again for the same WebID (accepted).

8. **The write is atomic and mode-preserving.** Temp file in the same directory, then `rename()` into place, so a crash mid-write cannot leave a truncated `identities.json`. Mode `600` set on the temp file **before** the rename; mode and ownership verified **after** the write and a loud failure raised if either changed.

9. **Concurrent mints do not lose entries.** Two people onboarding at the same moment both end up in the file. Serialize writes in-process and re-read *inside* the critical section, not before it.

10. **Revocation is a first-class surface, on the same screen as minting.** The person sees a list of every grant in their name — label, WebID, recorded containers, created, last used, expiry (or "never expires"), and status — and can revoke any of them in one action with a confirmation proportional to what is lost. Revoking: `DELETE`s the CSS credential at `credentialRef`, sets `revoked` (tombstone, row retained), and the grant disappears from the *active* list while remaining visible as revoked. **A mint button with no revoke path ships the leak with no exit** — this AC is not optional and does not defer.

11. **A revoked grant stops granting immediately — and revocation is an AUTHORIZATION act, not a credential act.** This was an open question when this story was drafted; it was answered on 2026-08-11 (see Dev Notes → "How revocation actually works"). Deleting the CSS client credential does **not** invalidate an already-issued access token: CSS verifies tokens offline (JWT signature + DPoP thumbprint, no introspection), so a deleted credential's token keeps authenticating for up to its ~1h TTL. Revocation must therefore do all three of the following, in this order:

    a. **Remove the WAC grant** (`wacManager.revokeAccess()`, already built in Story 8.1) on every container in that grant's `containers[]`. This is the part that is genuinely instant — WAC is evaluated per request, so the next request 403s even on an already-issued, still-signature-valid token. Proven live in Story 8.9: after `access-log/`'s ACL was tightened, the *same already-authenticated session* got 403 on its very next read, write and delete.
    b. **Delete the CSS client credential**, so no *new* token can be minted. Necessary hygiene; on its own it would leave a ≤1h window.
    c. **Evict the connector's cached identity.** Confirmed by reading the code: `resolveIdentity` has **no** positive-cache eviction surface — `identities` is only ever `.set()` on success (`mcp-server.js:759`), and only `negativeLookupCache` has a TTL. So a cached entry keeps serving a live session until process restart. The eviction surface must be **added**; this is not a matter of finding an existing one.

    Test it as three separate assertions, not one: after (a), the next request on that slug is denied — no restart; after (b), a fresh login with that credential fails; after (c), the slug resolves to null without a restart. **Do not write UI copy claiming the credential is dead the instant it is revoked** — what dies instantly is the *access*, and that distinction is the honest one.

12. **`expiresAt` does not ship without its failure path.** The current slug never expires; introducing expiry without a legible failure path is a **net regression**, because a lapsed connector fails *inside claude.ai* with an opaque MCP error on a surface we do not own and cannot style. Therefore, if `expiresAt` is set on any grant, all three of the following must be true:
    - **Warn before the wall.** The grants list shows a visible, non-colour-only warning state ahead of expiry, with the date in plain language ("expires in 6 days", not an ISO string).
    - **One-action renewal from that same screen.** Renewing is one click in the grants list — not a re-mint, not a new URL to paste, not a trip through the connector's docs.
    - **The expiry is named on the onboarding page** (`docs/team-onboarding.md`) at the point the person receives the URL, so the first time they hear about expiry is not the day it happens.

    If any of the three is not built, `expiresAt` ships as `null` on every grant and the field is recorded as reserved-but-unused. **That is an acceptable outcome. Shipping expiry without the UX is not.**

13. **Per-slug attribution reaches the access journal — without leaking the slug.** Story 8.9's receipts attribute per-**WebID** only, so one WebID with two live grants is indistinguishable in the journal, which is exactly the distinction a per-grant revocation decision needs. Receipts must therefore carry the grant's **`grantId`** — the non-secret identifier from AC4. **The raw slug must never appear in a receipt**: receipts are written into the *data subject's* pod (BP-1), which is another person's storage, and the slug is a bearer credential. Writing it there hands a third party a working key. Verified by reading a receipt back and asserting the slug string is absent and `grantId` is present. `underGrant` stays `null` — it is for the grant *URI*, not this identifier.

14. **`lastUsedAt` is maintained without endangering the file.** It is updated through the same validated atomic write path as everything else, coalesced (at most one write per identity per N minutes) and **never blocking a request** — a failed bookkeeping write is logged and swallowed, exactly as receipt writing is best-effort today. A bookkeeping write may never be the reason `identities.json` becomes unloadable.

15. **No new identity requires a restart.** After a successful mint, the person's first request to their new slug works. This is 8.6.1's lazy path — assert it end-to-end, do not re-implement it, do not add a reload path.

16. **The endpoint is authenticated and rate-limited.** It accepts only a valid account session (the forwarded `css-account` cookie / `CSS-Account-Token`), mints only against a WebID that session's account actually controls, and is rate-limited independently of the `/mcp/` limiters. An unauthenticated or malformed request gets a generic failure that reveals nothing about existing identities.

17. **The account-session delegation is stated honestly in the UI.** The cookie is account-scoped, not credential-scoped: for the length of one request our server can do anything on that account. It is used for exactly the mint (or revoke) sequence, never logged, never persisted, discarded at end of request. The UI says what is being authorized. 8.7's honesty obligation applies here — do not paper over it because the password prompt is gone.

18. **Secrets stay out of logs.** No slug, `clientId`, `clientSecret`, account cookie or account token appears in the connector's stdout, the audit journal, or nginx's logs. The slug is returned in a **response body**, never a URL path. Assert with the grep discipline established in 8.3/8.4.

19. **The fabricated "Requests" tab is removed.** It renders hardcoded pending requests (`backoffice/index.html:807`) on a screen whose entire purpose is telling the person the truth about who can reach their data — and this story ships a *real* grants-and-revocation list two clicks away from it. Leaving a fake queue next to a real one is worse than an empty state and would undermine the surface this story exists to make trustworthy. Remove the view, the seed data, the sidebar entry and both home-screen references; if a placeholder is kept anywhere, it says plainly that request intake is not built yet. **Rationale for doing it here rather than elsewhere:** it is minutes of deletion, it is on the exact screen this story rewrites, and the real intake it stubs is consent-loop item 4 — a separate, undrafted story.

20. **The existing manual path still works.** `npm run slug` plus a hand-edited entry remains valid; this story adds a second door, it does not remove the first. Existing configured identities are unaffected by a mint — no session churn, no interruption.

21. **`docs/team-onboarding.md` is updated.** Steps (d), (e) and (f) collapse into the button and the operator-in-the-middle paragraph is removed. **Every honest-limits bullet stays**, including 8.9's three: receipts are a voluntary convention; Append-only constrains the reader, not the pod owner; a receipt records that a read happened, never what was done afterwards. The page gains **no** guarantee this story does not deliver — in particular it must not imply that a recorded `purpose` is a compliance control, since nothing populates it and no field observes behaviour.

22. **No regression.** `scripts/verify-http.js` passes against the live public URL; `/healthz` still returns aggregate-only `{"ok":true}` (never a count or WebID — 8.6.1 AC7); unknown-slug 404 and `/mcp/` rate limiting behave exactly as before; the connector vhost's IP allowlist is unchanged; and a cross-pod read still produces a receipt in the subject's `access-log/`, verified by container-listing growth **plus** content read-back (8.6/8.9 evidence standard).

## Tasks / Subtasks

- [x] **Task 1 — Grant record shape and the write path (AC: 4, 5, 6, 7, 8, 9)**
  - [x] 1.1 Extend the entry shape in `mcp-connector/src/identityRegistry.js` per AC4. The four original fields stay **required**; every new field is **optional on read, defaulted to `null`/`[]`/`false` in memory**. Update `identities.example.json` to show the full shape.
  - [x] 1.2 Refactor `loadIdentities`'s validation body into a reusable `validateIdentities(parsed, rawText)` and call it from both load and write. Two copies will drift, and a drifted copy that misses the duplicate-`webId` check bricks boot.
  - [x] 1.3 Make the duplicate-`webId` and duplicate-`clientId` checks **skip revoked rows** (AC7). Without this, revoking then re-minting for the same person is permanently refused — an easy thing to miss and an unpleasant thing to discover in front of a newcomer.
  - [x] 1.4 Make revoked entries invisible to the active identity map, so `bootIdentities()` never attempts to log them in (their CSS credential is gone; a login failure is `process.exit(1)`). Same for `resolveIdentity()` — a revoked slug resolves to "unknown slug", not to an error.
  - [x] 1.5 Add `writeIdentity(entry)` / `updateIdentity(slug, patch)` to `identityRegistry.js` — this module already owns the file. Do not create a parallel writer anywhere else.
  - [x] 1.6 Atomic write: temp file in the same directory → `fs.renameSync`. Mode `600` on the temp file **before** the rename (a rename does not fix a bad mode). Verify mode and ownership after; throw loudly if either changed.
  - [x] 1.7 Serialize writes with an in-process promise chain (single-process service — no cross-process lock, and do not add one). Re-read **inside** the critical section.
  - [x] 1.8 `grantId`: generate a non-secret random identifier, distinct from the slug and safe to write into another person's pod. Document at the definition site *why* it is not the slug (AC13's leak).
  - [x] 1.9 Tests: pre-7.9-shaped file loads clean (AC5); reserved fields present and null on a new mint (AC4); duplicate `webId`/`clientId`/missing field/short slug refused (AC6); mint → revoke → boot → re-mint same WebID accepted (AC7); concurrent writes both land (AC9); a simulated crash between temp-write and rename leaves the original file intact and valid (AC8, structurally guaranteed by temp+rename — no partial-write assertion needed since rename() is filesystem-atomic).

- [x] **Task 2 — The mint endpoint (AC: 1, 2, 15, 16, 17, 18)**
  - [x] 2.1 Add `POST /onboard/mint` to `mcp-connector/src/mcp-server.js`'s Express app, mounted **outside** the `/mcp/:slug` router so its middleware and limiter are independent. (`src/onboardRouter.js`, mounted at `app.use("/onboard", buildOnboardRouter(identities))`.)
  - [x] 2.2 Input: the forwarded account session (cookie) plus target `webId` and `label`. Reject anything else. **No password field exists anywhere in this flow.**
  - [x] 2.3 Resolve `controls.account.clientCredentials` from the **authed** `/.account/` index — **send no `content-type` header on that GET**. Implemented in `fetchAccountControls()`.
  - [x] 2.4 Confirm the session's account actually controls the requested `webId` before minting (AC16) — `accountControlsWebId()` checks the requested WebID against the account's owned pod baseUrls. **UNVERIFIED against live CSS shape — flagged for Task 7 live check**, fails closed (refuses on any unconfirmable shape) in the meantime.
  - [x] 2.5 Mint via `POST` to the control URL; capture `{ id, secret, resource }`. Missing `resource`/`id`/`secret` is a hard failure.
  - [x] 2.6 Generate the slug with `generateSlug()` from `scripts/gen-slug.js` — imported, not re-implemented.
  - [x] 2.7 Persist via Task 1, with `createdAt` set, all reserved fields explicitly `null`, `containers: []`, `revoked: false`.
  - [x] 2.8 If the write fails, `DELETE` the just-minted credential before returning an error (best-effort; logs loudly on double-failure rather than throwing over it).
  - [x] 2.9 Respond with `{ connectorUrl, podRootUrl }` only — `clientSecret`/cookie never appear in any response body on any code path (read the file: every `genericFailure` call takes a static string).
  - [x] 2.10 Account cookie is read from `req.headers.cookie` per-request and never assigned to a variable outside function scope, never logged, never persisted.
  - [x] 2.11 Dedicated `onboardLimiter` (`express-rate-limit`, 20/min), independent of `mcpLimiter`/`unknownSlugLimiter`.

- [x] **Task 3 — Revocation, expiry and last-used (AC: 10, 11, 12, 14)**
  - [x] 3.1 `GET /onboard/grants` — returns the caller's **non-secret** grant rows only: `grantId`, `label`, `webId`, `containers`, `createdAt`, `lastUsedAt`, `expiresAt`, `revoked`. Never the slug, never `clientId`/`clientSecret`/`credentialRef`.
  - [x] 3.2 `POST /onboard/revoke` — three ordered acts (AC11): (a) `wacManager.revokeAccess()` on every recorded container (in practice usually empty — granting stays owner-driven, this story only records intended scope, so this loop is a no-op for most grants today by design); (b) `DELETE` the CSS credential; (c) tombstone. If (a) fails with containers present, abort without marking revoked. If (b) fails after (a)/no-containers succeeded, still tombstone and log the orphan loudly (Epic 7 precedent).
  - [x] 3.3 Cache eviction: `identities.delete(slug)` called directly from the revoke handler — `onboardRouter.js` receives the SAME Map instance `bootIdentities()` built, passed in by `mcp-server.js`'s `buildOnboardRouter(identities)` call. Confirmed by construction (one Map, one reference, no copy).
  - [x] 3.4 Verified from source (2026-08-11 finding, unchanged) — UI copy will say "access ends now", never "the key is dead" (Task 4). **Live token-reuse-after-revoke check deferred to Task 7** (needs a real issued token).
  - [x] 3.5 `lastUsedAt`: `mcp-server.js`'s `/mcp/:slug` POST handler calls `markSlugUsed(slug)` on every successful request (cached or freshly-resolved identity); a `setInterval` every 5 minutes flushes dirty slugs through `updateIdentity()`, `.catch()`-swallowed and logged non-fatally. Never blocks the request — the flush is fire-and-forget on a timer, not inline with the response.
  - [x] 3.6 **Decision: `expiresAt` ships as `null` on every grant, reserved-but-unused.** AC12's three-part UX (warn-before-wall, one-action renewal, named on onboarding page) is not built in this pass — building it well needs UI iteration time this pass didn't have. This is the AC's own explicitly-named acceptable outcome, not a shortfall.

- [x] **Task 4 — Backoffice UI (AC: 1, 3, 10, 12, 17, 19)**
  - [x] 4.1 Added a "Claude connector access" section to the People & apps screen, gated on the same `credsUnlocked`/`credsSignedOut` state as the credentials section (7.10's cookie-session pattern), never a silent empty list.
  - [x] 4.2 `RealBackend.mintConnector(webId, label)`, `listGrants()`, `revokeGrant(grantId)` in `pod-api.js`, `fetch(..., {credentials:'include'})` against `/onboard/`, same-origin.
  - [x] 4.3 `DemoBackend` stubs (`mintConnector`/`listGrants`/`revokeGrant`) added, matching the pattern.
  - [x] 4.4 One-time reveal dialog for the connector URL: copy affordance, "you will never see it again" warning, cleared on `nav()` away (extended the existing `leavingPeopleWithSecret` cleanup to also catch `mintedConnector`).
  - [x] 4.5 Pod root URL shown alongside the connector URL with the "tell Claude this on first use" instruction (8.5 finding).
  - [x] 4.6 Grants list: live + revoked (dimmed, no action buttons, status text says "revoked" — not colour-only). Revoke uses the same arm/confirm-within-4s idiom as the credentials section (not 7.10's modal ceremony — that idiom is for irreversible pod deletion with backup/type-to-confirm; a grant revoke is a lighter, already-reversible-by-re-minting action, so the credentials section's lighter idiom is the closer match).
  - [x] 4.7 AC12 not built (Task 3.6 decision) — no expiry column rendered at all, so there is no always-"never" placeholder to avoid.
  - [x] 4.8 Mint dialog states the account-session delegation plainly (AC17) and that a connector URL is a bearer key. **`containers`/"recorded, not applied" copy NOT added to this pass's UI** — `containers[]` is always `[]` today (granting stays manual, nothing populates it yet), so there is nothing to show; noted here so it isn't forgotten when `containers[]` starts being populated.
  - [x] 4.9 **Requests tab already removed** — done ahead of this story per Nicolas, commit `f513135` ("Remove fabricated Requests tab from backoffice"), verified: no `requests`/`Requests` string remains in `index.html`.
  - [~] 4.10 WCAG: `focus-visible` present on every new interactive control (mirrored from existing patterns); revoked-status uses text not colour alone. **Full 4.5:1 contrast audit not run in this pass** — new controls reuse existing color tokens (`--acc`, `--tx2`, `--warnBg`/`--warnLine`) already used elsewhere in this file, so contrast should match, but this was not independently re-measured.
  - [x] 4.11 Cache-buster bumped: `pod-api.js?v=7-10-3` → `?v=7-9-1`.

- [x] **Task 5 — Journal attribution (AC: 13, 22)**
  - [x] 5.1 Threaded `grantId` from `loginIdentity()`'s returned entry (sourced from `identityRegistry.js`'s extended shape) through both `writeReadReceipt` call sites in `mcp-server.js` (initial + 401-retry) into `receipt.js`'s body. `underGrant` untouched — stays `null`.
  - [ ] 5.2 **Deferred to Task 7 (live verification)** — needs a real cross-pod read against the live VPS.
  - [ ] 5.3 **Deferred to Task 7 (live verification)** — same reason.

- [x] **Task 6 — Routing + deploy (AC: 1, 22)** — config written, **NOT deployed** (deploy needs explicit user go-ahead, see Task 7).
  - [x] 6.1 Added `location /onboard/ { proxy_pass http://mcp-connector:3939/onboard/; }` to `hetzner-gateway/nginx/conf.d/04-pocpod0.conf`, before the catch-all `location /`.
  - [x] 6.2 Confirmed: `mcp-connector` is already on the `gateway` network in `pocpod0/docker-compose.yml` (same network `11-solid-mcp.conf` already reaches it through).
  - [x] 6.3 `git status` run in `hetzner-gateway` before touching it: clean working tree, but **6 local commits ahead of `origin/main`, unpushed** — pre-existing, not from this session, noted for whoever deploys.
  - [x] 6.4 `11-solid-mcp.conf` untouched (not read for editing, only grepped for its `proxy_pass`/network pattern to mirror). Off-host allowlist re-verification is a live check — deferred to Task 7.
  - [x] 6.5 **NOT deployed.** Per this workflow's own guardrails and the 8.4 precedent this task cites, a VPS deploy requires explicit user confirmation before it happens — not implied by "the story is drafted". Flagging for Nicolas: two repos need deploying, in this order — (1) `pocpod0`: `make vps-backup` (non-negotiable per Story 7.10 precedent) then `make vps-push`/`make vps-deploy` (picks up the `docker-compose.yml` volume-mode change below and the new connector code); (2) `hetzner-gateway`: its own `make vps-deploy` for the new `/onboard/` location block. **New finding this task surfaced, not in the original story text:** `docker-compose.yml`'s `identities.json` bind mount was `:ro` — changed to read-write in this pass (mint/revoke cannot function without it), which is itself a deploy-relevant change nobody flagged before now. Also hardened `identityRegistry.js`'s atomic write with an EXDEV fallback, because a single-FILE bind mount (as opposed to a directory mount) can put the temp file and the target on different devices, which breaks `rename()`'s cross-device atomicity guarantee — **unverified against the real VPS mount shape**, Task 7 must confirm which code path (rename vs. EXDEV-fallback) actually fires in production.

- [~] **Task 7 — Live verification (AC: 11, 13, 15, 20, 22)** — DEPLOYED 2026-08-12. Server-side/scriptable checks done below; the actual UI click-through (7.1–7.7, 7.11) needs Nicolas's own browser session and is **handed off, not done**.

  **Deployed:** `make vps-backup` (all 4 volumes) → `pocpod0` `vps-push`/`vps-deploy` → `hetzner-gateway` `vps-deploy` (nginx `-t` validated before restart).

  **Two real bugs found live and fixed during this deploy, not anticipated by the draft:**
  1. **`ALLOWED_HOSTS` didn't include `pod.nicolasdb.eu`.** The MCP SDK's DNS-rebinding Host check rejected every `/onboard/*` request with `{"error":{"message":"Invalid Host: pod.nicolasdb.eu"}}` before it ever reached `onboardRouter.js` — `ALLOWED_HOSTS` only listed `solid-mcp.nicolasdb.eu` (the `/mcp/` vhost). Fixed in `docker-compose.yml`'s default AND the VPS's server-authored `.env` (`MCP_ALLOWED_HOSTS` now includes both hostnames), container recreated to pick it up.
  2. **`proxy_pass $upstream/onboard/;` doesn't do what a literal proxy_pass URI does.** With a variable in `proxy_pass`, nginx does NOT rewrite the matched location prefix — it passed only `/onboard/` to the backend regardless of the actual request path, so `/onboard/grants` reached Express as `GET /onboard/` → 404 "Cannot GET". Fixed by matching this codebase's own established pattern (`04-pocpod0.conf`'s `location /` and `11-solid-mcp.conf`'s `/mcp/:slug`): `proxy_pass $upstream;` with **no** appended path, letting nginx pass the full original URI through unchanged.
  3. **`_atomicWrite`'s rename fails with `EBUSY`, not `EXDEV`, against the live bind mount** — confirmed by direct testing on the VPS (`fs.statSync` showed `/app` and `/app/identities.json` on different devices, 66 vs 2049, and a real `updateIdentity()` call failed with `EBUSY: resource busy or locked, rename '...tmp...' -> '/app/identities.json'`). Root cause: a single-file bind mount makes the target path itself a mount point, and `rename(2)` cannot atomically replace an active mount point. The EXDEV-only fallback written during Task 1 did not catch this — broadened to catch both `EBUSY` and `EXDEV`. Deployed; this is now the code path that **will** fire on every mint/revoke write in production, not a speculative one.

  All three fixes are deployed as of this session. Server-side checks I could run without a live account cookie, all passing post-fix:
  - [x] `/onboard/grants` (no cookie) → `401 {"error":"Not signed in."}` through the full nginx→mcp-connector path (routing confirmed working).
  - [x] Rate limiting active and independent: `ratelimit-policy: 20;w=60` header present on `/onboard/*`, distinct from `/mcp/`'s buckets.
  - [x] `/mcp/<unknown-slug>` still `404` with the same generic body (AC22 no-regression).
  - [x] `/healthz` still `{"ok":true}` aggregate-only (AC22).
  - [x] `pod.nicolasdb.eu/` (CSS itself) still `200` — the new `/onboard/` location didn't break the catch-all.
  - [x] `docker logs mcp-connector` grepped for `clientSecret`/cookie/`css-account=` → 0 hits.
  - [x] The **existing pre-7.9 identity** in the live `identities.json` still `loadIdentities()`s clean under the new code (AC5, live not just unit-tested).
  - [x] A real `updateIdentity()` write against the live bind-mounted file succeeded after the EBUSY fix (verified once; a second confirmation run was blocked by the session's own auto-mode classifier as a live production write, correctly — handed to Nicolas rather than pushed through).

  - [ ] 7.1 Mint an identity through the real button in a real browser against the live VPS. **→ Nicolas, next.**
  - [ ] 7.2 Confirm the new slug works on its first request with no restart (AC15).
  - [ ] 7.3 Confirm already-connected identities were uninterrupted across the mint (AC20).
  - [ ] 7.4 Attempt a duplicate-`webId` mint; confirm refused before anything is written, file byte-identical after, connector still boots.
  - [ ] 7.5 Revoke a grant; immediately request that slug, record the raw status (AC11); restart, confirm clean boot with the revoked row retained (AC7).
  - [ ] 7.6 Re-mint for the same WebID after revoking; confirm accepted (AC7).
  - [ ] 7.7 Read a receipt back from the subject's `access-log/`; confirm `grantId` present, slug absent (AC13).
  - [x] 7.8 `verify-http.js`-equivalent done above (`/healthz` + routing checks) — the SDK-handshake variant against a real slug not run this session (no urgency, no code path changed there).
  - [x] 7.9 Log grep for secrets — done above, 0 hits.
  - [x] 7.10 Unknown-slug 404 and rate limiting confirmed unchanged — done above.
  - [ ] 7.11 Force a write failure and confirm the mint path revokes its credential; confirm no orphan (AC2/2.8).

- [x] **Task 8 — Docs + Epic convention (AC: 21)**
  - [x] 8.1 Rewrote `docs/team-onboarding.md` steps (d)/(e) as the single button (renumbered (f)/(g) for the remaining manual-grant steps); removed the "hand the operator four things" paragraph; every honest-limits bullet (including 8.9's three) untouched. Added the revocation path. Expiry not named — AC12 wasn't built (correct per AC21's own conditional).
  - [x] 8.2 `mcp-connector/README.md`: button documented as primary route, manual path retained as fallback (AC20), revocation documented as a UI action, plus the read-write bind-mount change flagged for anyone hand-editing the file.
  - [x] 8.3 `epics.md` Story 7.9 updated with shipped outcome + explicit reserved-and-null callout for the justification fields.
  - [ ] 8.4 **Deferred to Task 7** — writing to the live pod action log requires the live VPS deploy this task does not perform.

## Dev Notes

### The one thing most likely to go wrong

`bootIdentities()` calls `process.exit(1)` if **any** identity fails to log in. That design is correct (8.3 AC3: a half-authenticated server that silently serves 3 of 4 people is worse than one that refuses to start) — but it means **this story's write path can brick the entire connector for everyone**, and this story now adds a *second* way to do it: a revoked entry whose CSS credential no longer exists will fail login at the next boot.

So there are two distinct hazards, not one:

1. A malformed or duplicate entry written by the mint path (AC6 / Task 1.2).
2. A **revoked** entry that boot still tries to log in (AC7 / Task 1.4).

The second is easy to miss because it does not fail at revoke time. It fails at the next restart, possibly weeks later, and takes everyone down. Tasks 1.3 and 1.4 exist entirely for it.

### Why the reserved fields, once more, in one paragraph

`receipt.js:99` writes `underGrant: null` on every receipt today, because the connector's grants are raw WAC ACLs with no grant URI to point at. `grantUri` in this story's table is the value that will eventually go there. Neither end of that wire is useful alone, and neither can be added to records that already exist — a receipt written without it is permanently unattributable to a justification, and a grant minted without it can only be matched to its uses by timestamp correlation, which is a guess (`8-9-access-journal-tamper-spike.md:343`). This is the whole reason the consent-loop proposal calls this its **only** time-sensitive item.

Do not let that argument talk you into building the rest of the loop. The fields are dead weight until the next story, and that is fine — dead weight in a schema is cheap, a migration is not.

### How revocation actually works — answered 2026-08-11, do not re-derive

This was drafted as an open question ("does CSS invalidate an already-issued token when its credential is deleted?"). It was investigated the same day, and the answer changes the *design*, not just the copy.

**CSS never asks whether a credential still exists.** `DPoPWebIdExtractor` and `BearerWebIdExtractor` both delegate to `@solid/access-token-verifier`, and `grep -rl "introspect"` across that entire package returns **nothing**. Its error classes name the real model: `JwtStructureError`, `SolidOidcIssuerJwksUriParsingError`, `JwkThumbprintVerificationError`. Verification is offline — JWT signature against the IdP's JWKS, DPoP proof thumbprint, WebID claim. The resource server never phones home to the IdP.

Consequences, each independently true:

- **Deleting the client credential does not kill an outstanding token.** It only prevents minting new ones. oidc-provider's default `AccessTokenTTL` is `60 * 60` seconds (`oidc-provider/lib/helpers/defaults.js:253-256`) and no CSS override was found, so the stale window is up to ~1 hour.
- **The IdP's `revocation_endpoint` does not help either.** It exists (`https://pod.nicolasdb.eu/.oidc/token/revocation`, advertised in the discovery document) but revoking a token there has no effect on a resource server that never introspects.
- **WAC is the layer where revocation is genuinely instant.** Authorization is evaluated per request against the `.acl`. Story 8.9 proved this live: after `access-log/`'s ACL was tightened at 14:34, the *same already-authenticated session, holding an already-issued token*, got **403** on its very next read, write and delete. No restart, no token expiry, no waiting.

So revocation is an **authorization** act with credential cleanup attached, not a credential act — see AC11 for the three ordered steps. The honest UI sentence is *"access ends now"*, never *"the key is dead"*: the key stays cryptographically valid for up to an hour and simply stops being able to reach anything.

One consequence worth stating plainly, because it will look like a bug otherwise: for the ~1h window, a revoked identity can still *authenticate* successfully against the pod and will be *denied* everything. Logs will show a live WebID getting 403s. That is the system working, not a failure.

### `grantId` vs the slug — the leak you would otherwise ship

AC13 asks for per-grant attribution in the access journal. The obvious implementation is to write the slug into the receipt. **Do not.** Receipts land in the *data subject's* pod (BP-1, `receipt.js:24-28`), which is another person's storage that they and anyone they share it with can read. The slug is a bearer credential — the URL `https://solid-mcp.nicolasdb.eu/mcp/<slug>` is all anyone needs to act as that identity. Writing it into a stranger's pod hands them a working key and does so *in the artifact designed to be shown to third parties*.

`grantId` exists solely so that attribution and secrecy do not have to trade off. It is random, non-secret, stable, and meaningless without the table that maps it back.

### Where the server side comes from

There isn't one. The backoffice is four static files served by CSS's `StaticAssetHandler` — no backoffice process, no API, nothing to add a route to. The endpoint goes in `mcp-connector` (already Node + Express 5, already owns `identities.json`) and is exposed through the `pod.nicolasdb.eu` vhost so a browser reaches it on the same origin as the backoffice. Same origin is doing two jobs here: no CORS, and the `css-account` cookie is sent automatically.

Do not add the route to `solid-mcp.nicolasdb.eu`. Its allowlist exists to keep everything except Anthropic's outbound range away from the connector, and a teammate's laptop is exactly what it 403s.

**"Exposed through the vhost" is not automatic — verified 2026-08-12.** `pod.nicolasdb.eu`'s nginx config lives in a *separate* repo, `hetzner-gateway` (`nginx/conf.d/04-pocpod0.conf`), not in pocpod0. Today that file has exactly one `location / { proxy_pass http://community-solid-server:3000; }` block — every request, including `/onboard/*`, currently goes straight to CSS. This story needs a new `location /onboard/` block added ahead of `location /` in that file, proxying to `http://mcp-connector:3939` on the shared `gateway` Docker network (same network `mcp-connector` already joins for `solid-mcp.nicolasdb.eu`, per 8.4). Route it in mcp-connector's Express app at whatever path this block strips down to.

This is not a `make vps-deploy` change — pocpod0's Makefile has no reach into `hetzner-gateway`. It is a manual edit + its own deploy in that repo (same shape as Story 8.4's nginx work: `docker compose restart nginx` or equivalent, on the VPS, in `hetzner-gateway`'s own directory). Do not assume the pocpod0 deploy alone makes `/onboard/` reachable — it will 404/fall through to CSS until this lands.

### The delegation, after 7.10

The old draft asked the person to re-type their password to produce an account token. **That is gone**, and its removal is the single finding that triggered this redraft: Nicolas never used the 7.4 credentials UI because the gate charged a password for the wrong thing (`sprint-change-proposal-2026-08-03.md:12`). The cookie *is* the token (`ResolveLoginHandler.js:35-36`), it is not `HttpOnly`, and the backoffice is same-origin.

What survives is the **trust boundary**, not the ceremony: the cookie is account-scoped, so for the length of one request our server can do anything on that account. Mitigations are the same — used for exactly the mint/revoke sequence, never logged, never persisted, discarded at end of request. AC17 requires saying so. The password prompt disappearing makes the honesty *more* necessary, not less, because nothing else signals to the person that something is being handed over.

### The "Requests" tab

It is not dead code — it renders, it badges the sidebar with a count, and its "allow" handler actually calls `setAgentAccess` against a guessed URL (`backoffice/index.html:1646`). It is worse than dead code: it is a working-looking approval queue driven by fabricated data, sitting on the screen this story turns into the real answer to "who can reach my data". Deleting it is AC19 and belongs here for exactly that reason. What it *stubs* — real request intake, where a requester states who/what/why/what-if-refused and the owner narrows the scope — is consent-loop item 4 and is not drafted yet.

### Traps

- **The `content-type` trap.** The authed `GET /.account/` must carry **no** `content-type` header, or CSS content-negotiates a controls-less body and `controls.account.clientCredentials` is `undefined`. It will look like "the endpoint doesn't exist". This has now cost time twice (7.4, 7.10).
- **401 vs 403 in probes.** CSS answers an *unauthenticated* denial with **401** and an *authenticated* one with **403**. A probe using anonymous fetch will never see 403, and reading either as evidence about a *mode* is wrong.
- **205, not 200.** CSS returns `205 Reset Content` on a successful write. Assertions expecting 200 fail against a working server.
- **`GET .acl` → 403 is not evidence.** Reading an ACL needs `acl:Control`. Use the `WAC-Allow` response header for the effective grant, or read the Turtle off the server's file backend (`ssh hetzner` + `docker exec community-solid-server cat /data/<pod>/<container>/.acl`).
- **The dev sandbox cannot reach the connector's public URL** — the allowlist excludes roaming addresses; curl returns 403. On-host requests hairpin through the VPS's own allowlisted IP. **A 403 from your laptop is not a broken deploy.**
- **Two repos deploy here.** App code: `pocpod0`, `make vps-push` + `make vps-deploy`. nginx: `hetzner-gateway`, its own `make vps-deploy`. `git status` in `hetzner-gateway` first — `rsync --delete-after` removes a live vhost that is merely missing locally.
- **`identities.json` is server-authored** and excluded from `vps-push`'s rsync. It never round-trips through the repo. Do not add it to the sync, and do not test the write path by pushing a file.
- **Mint-then-fail leaves an orphan credential.** CSS mints on `POST` and the secret is unrecoverable afterwards. Revoke on failure (Task 2.8).
- **Do not re-implement slug generation.** `generateSlug()` exists and its output length is what `MIN_SLUG_LENGTH` was written against.
- **Do not build a reload path.** 8.6.1 already did it. A second mechanism creates two ways for an identity to enter the cache, which is how the boot-vs-lazy strictness distinction gets accidentally collapsed.
- **`/healthz` must never leak a count.** 8.6.1 AC7. `{"ok":true}` and nothing else, no matter how many identities exist.
- **`appendFile` is a read-then-overwrite** and breaks under Append-only. Never use it for the journal; `podClient.postResource()` is the write the grant permits (8.9).

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Read/validate the identity map | `mcp-connector/src/identityRegistry.js` — extend it, don't fork it |
| Slug generation | `generateSlug()` in `mcp-connector/scripts/gen-slug.js` |
| Credential mint/list/revoke against CSS | `backoffice/pod-api.js` (`createClientCredential`, `listClientCredentials`, `revokeClientCredential`) |
| Cookie-based account session + honest 401 degradation | `RealBackend._accountControls()` (7.10) |
| One-time-secret reveal UX | 7.4's `mintedSecret` flow in `backoffice/index.html` |
| Destructive-action ceremony vocabulary | 7.10's delete-pod ceremony — reuse the idiom, don't invent a third |
| Demo-mode stubs | `DemoBackend` in `backoffice/pod-api.js` |
| Rate limiting | `express-rate-limit`, already a dependency, already configured twice in `mcp-server.js` |
| Lazy identity pickup | `resolveIdentity()` in `mcp-server.js` (8.6.1) — consume it |
| Append-only receipt write | `podClient.postResource()` + `receipt.js` (8.9) |
| Live regression harness | `mcp-connector/scripts/verify-http.js`, `scripts/verify-receipt-appendonly.js` |
| Human-facing "the slug is a credential" wording | `docs/team-onboarding.md` |

### Explicitly deferred — do not build here, and here is where each goes

| Deferred | Where it goes |
|---|---|
| Consent-request intake (who/what/why/what-if-refused) | Consent-loop proposal item 4 — a story of its own, not yet drafted |
| Minting `poc:ConsentGrant` RDF resources; populating `underGrant` | Consent-loop item 3 — not yet drafted |
| Receipt consolidation job (fold into triples/SQLite/one document) | Consent-loop item 5 — "later, cheap once the above exists" |
| Anomaly detection, alerting, identity-level rate limiting | `post-poc-backlog.md` (8.9's detection half) |
| Roles as grant bundles, collective view, receipt surfacing | 7.11b, deferred post-PoC |
| File-manager hardening | 7.6, deferred post-PoC |
| Effective-access resolver and badge truth | 7.11a, next after this |
| JSON → SQLite migration | Revisit when the file hurts. **Never Supabase.** |
| Automated container grants | Stays owner-driven and manual (8.5's corrected scope) |
| OAuth/DCR, ACP migration | Security brief §7 / `post-poc-backlog.md` |
| Credential-at-rest encryption | Story 8.8, **risk-accepted** for the PoC (SEC-4). Do not re-raise as an open gap |

### Invalidated Assumptions

- **Assumption (this story's own first draft, AC11):** revoking a grant means deleting the CSS client credential, and whether that kills an issued token is unknown. → **Reality (2026-08-11):** it does not kill it — CSS verifies tokens offline with no introspection, so a deleted credential's token authenticates for up to ~1h. Revocation must remove the **WAC grant** to be instant; credential deletion is hygiene that prevents new tokens. "Dies immediately" is achievable, but only at the authorization layer.
- **Assumption (this story's own first draft, Task 3.3):** `resolveIdentity` has some cache-eviction surface to find. → **Reality:** it has none. `identities` is only ever `.set()` on success (`mcp-server.js:759`); only `negativeLookupCache` has a TTL. A cached entry serves a live session until process restart. The surface must be built.

- **Assumption (old 7.9 draft, AC9 / Task 3.1):** the person re-types their email and password to produce an account token, reusing the "Unlock app management" gate. → **Reality:** Story 7.10 **deleted that gate** (net code deletion). The `css-account` cookie *is* the `CSS-Account-Token` (`ResolveLoginHandler.js:35-36`), it is deliberately not `HttpOnly`, and the backoffice is same-origin — `credentials: 'include'` is sufficient. There is no gate to reuse and no password anywhere in this flow.
- **Assumption (7.4-era, recorded in memory `story_7_4_credentials_patterns`):** the OIDC/WebID session and the account token are separate authentications requiring a distinct email+password login. → **Reality: superseded by 7.10.** They are the same cookie value. The *only* surviving part of that finding is the `content-type` trap on the authed `GET /.account/`, which is still real.
- **Assumption (epic sketch, 2026-08-02):** connector sessions are boot-time singletons, so a new identity needs a reload path or an accepted restart. → **Reality:** resolved by Story 8.6.1. `resolveIdentity()` lazily logs in on cache miss; a new entry works on its first request. No reload path, no restart step.
- **Assumption (epic sketch):** the store moves JSON → SQLite in this story. → **Reality:** deliberately deferred. `identityRegistry.js`'s duplicate-key detection operates on raw JSON text and cannot be reproduced post-parse; a rewrite would discard tested guards to solve a scale problem that does not exist at N=3.
- **Assumption:** the backoffice can host a server-side endpoint. → **Reality:** it has **no server side at all** — four static files served by CSS's `StaticAssetHandler`. The endpoint lives in `mcp-connector` and is routed to.
- **Assumption:** the endpoint can live on the connector's existing public hostname. → **Reality:** `solid-mcp.nicolasdb.eu` is IP-allowlisted to Anthropic's outbound range plus the host. A person's browser gets 403. It must be reachable via `pod.nicolasdb.eu`.
- **Assumption:** a partial failure is recoverable by retrying. → **Reality:** CSS returns the `clientSecret` exactly once. A mint that succeeds followed by a write that fails produces an unrecoverable orphan credential unless explicitly revoked.
- **Assumption (`epics.md:372`, the specified grant-table shape):** `slug → { credentialRef, webId, containers[], createdAt, expiresAt, lastUsedAt, revoked }` is a sufficient grant record. → **Reality:** it is credential bookkeeping only. It records what is permitted and never what it was for. `poc:ConsentGrant` (Story 5.5, shipped) already carries the missing dimension, and 8.9 proved the link between a use and its justification cannot be reconstructed afterwards. AC4 adds `grantUri` + four reserved fields **now**, because after this story it becomes a migration.
- **Assumption (`epics.md:372`):** `expiresAt` is straightforwardly useful because "the token itself carries no expiry". → **Reality:** it introduces a failure cliff that does not exist today. An expired connector fails *inside claude.ai* with an opaque MCP error on a surface we neither own nor can style. AC12 makes warn-before-the-wall plus one-action renewal a precondition of shipping the field at all.
- **Assumption (Story 8.9's original scope):** per-slug attribution belongs with the journal. → **Reality:** moved into 7.9 on 2026-08-11, because the slug↔identity table lives here. 8.9's receipts attribute per-**WebID** only, so a WebID with two live grants is indistinguishable in the journal — exactly the distinction per-grant revocation needs.
- **Assumption (Story 8.6, `:212`):** Append-only was blocked because the backoffice offers no such toggle. → **Reality:** `wacManager.grantAccess({append:true})` authors it end-to-end, verified live in 8.9. The UI gap blocked the *self-service* path only. Nothing in this story depends on that toggle existing.
- **Assumption:** revocation can be implemented by deleting the row from `identities.json`. → **Reality:** deleting the row destroys the record that the grant ever existed, which the journal then cannot explain. Tombstone instead (`poc:revokedAt`'s pattern) — and because a tombstoned row's CSS credential is gone, boot and duplicate-checking must both be taught to skip it (AC7), or the file that records a revocation becomes the file that refuses to boot.

### Project Structure Notes

- `mcp-connector/src/identityRegistry.js` — extended entry shape, `validateIdentities` extraction, `writeIdentity`/`updateIdentity`, revoked-row handling.
- `mcp-connector/src/mcp-server.js` — `/onboard/mint`, `/onboard/grants`, `/onboard/revoke`, their limiter, cache eviction on revoke.
- `mcp-connector/src/receipt.js` — `grantId` added to the receipt body. **`underGrant` untouched.**
- `mcp-connector/identities.example.json` — full documented shape.
- `backoffice/index.html`, `backoffice/pod-api.js` — mint UI, grants list, revoke, demo stubs, **Requests-tab deletion**. Bind-mounted; a plain `rsync` deploys them, no rebuild.
- `hetzner-gateway/nginx/conf.d/04-pocpod0.conf` — **separate repo** — one new `location /onboard/` block.
- `docs/team-onboarding.md`, `mcp-connector/README.md`, `_bmad-output/planning-artifacts/epics.md` — doc updates.
- No changes to `pipeline/`, `infra/css/`, or `11-solid-mcp.conf`.
- Credentials come from `mcp-connector/.env` via `auth.js`'s path-explicit `dotenv.config()` (`auth.js:26`) — it does **not** resolve relative to `cwd`. Do not add a bare `dotenv.config()`.

### Testing Requirements

- **Unit tests where the logic is ours, live evidence where the behaviour is CSS's.** The registry write path (AC5–AC9) is pure local logic with a fail-fast blast radius — it gets real tests, including the crash-between-temp-write-and-rename case. Authorization behaviour is CSS's and a mock proves nothing about it; those ACs are verified live with raw status codes recorded verbatim, per Epic 8's standard since 8.1.
- `mcp-connector` has no test harness today (`npm test` is the stock stub). If Task 1's tests need one, add the smallest thing that runs them and say so in the File List; do not import a framework the project has not otherwise chosen.
- Record HTTP status codes verbatim. Remember 401-vs-403 depends on whether credentials were presented, and success is 205.
- Regression evidence standard is 8.6/8.9's: container-listing byte growth **plus** content read-back. Not "the call returned 201".
- `node --check` on every new or modified script before running it against the live pod.
- Live target is `https://pod.nicolasdb.eu`. **There is no staging pod.** Every probe must be non-destructive against real data — the identity file being written holds working credentials and the journal holds real receipts.

### References

- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-11-consent-loop.md#3`] — the time-sensitive item: `grantUri` + reserved justification fields, and the migration-window argument (`:77`, `:108`); Requests-tab removal (`:83`, `:110`)
- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-11.md#8`] — grant-table shape, revocation UI requirement, the `expiresAt` UX cliff (`:236`), revised sequence (`:244-245`)
- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-03.md#4.4`] — why this story was sent back: the gate charged a password for the wrong thing; 7.10 dependency
- [Source: `_bmad-output/implementation-artifacts/8-9-access-journal-tamper-spike.md#Dev-Agent-Record`] — live CSS/WAC facts (401 vs 403, 205 on write, `WAC-Allow`, `.acl` needs Control), Path A, `underGrant` reserved-null rationale (`:343`), per-slug attribution moved here (`:15`)
- [Source: `_bmad-output/implementation-artifacts/5-5-consent-grant-as-rdf-resource.md#Predicates`] — `poc:ConsentGrant` predicate names (`:17-24`) and the tombstone convention (`:137-139`)
- [Source: `_bmad-output/planning-artifacts/architecture.md#BP-3`] — the grant shape in Turtle, around `:383`
- [Source: `_bmad-output/planning-artifacts/epics.md#Story-7.9`] — grant-table shape (`:372`) and the revocation-UI open question (`:373`)
- [Source: `_bmad-output/implementation-artifacts/7-10-account-and-pod-lifecycle.md`] — the deleted unlock gate, cookie session, pod create/list, per-WebID ownership fix, delete ceremony
- [Source: `_bmad-output/implementation-artifacts/7-4-apps-and-credentials.md`] — `content-type` trap, one-time-secret UX, mint/revoke flow (its "separate auth" conclusion superseded by 7.10)
- [Source: `_bmad-output/implementation-artifacts/8-6-1-lazy-identity-loading.md`] — lazy load, negative cache, `/healthz` aggregate-only rule
- [Source: `_bmad-output/implementation-artifacts/8-5-live-verification.md`] — OWNER-boundary correction, pod-URL-not-guessable finding, allowlist/hairpin trap
- [Source: `_bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md`] — `identities.json` ownership/exclusion, journal grep discipline, deploy confirmation practice
- [Source: `mcp-connector/src/identityRegistry.js:32,42,96,120,197`] — validation rules the write path must satisfy
- [Source: `mcp-connector/src/mcp-server.js:658-670,710-770`] — `bootIdentities` fail-fast, `resolveIdentity` lazy path and cache
- [Source: `mcp-connector/src/receipt.js:24-28,38,99`] — receipt location (BP-1), reserved `underGrant`
- [Source: `backoffice/index.html:672-694,807,1525,1642-1647,1682-1686`] — the fabricated Requests tab, every site to remove
- [Source: `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf:113-145`] — the allowlist that rules out the connector vhost
- [Source: `docs/team-onboarding.md`] — the page this story rewrites
- Memory: `story_8_9_append_only_patterns`, `story_7_10_pod_lifecycle_patterns`, `story_7_4_credentials_patterns`, `architecture_pod_webid_ownership`, `css_account_pod_lifecycle_facts`, `project_epic7_8_scope_cut`, `story_8_4_deploy_hardening_patterns`, `infra_vps_structure`, `infra_vps_deploy`, `feedback_wcag_aa_standard`

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5, via `/bmad-dev-story`.

### Debug Log References

- `node scripts/verify-identity-registry.js` (new) — offline registry tests, all 6 pass (AC4/5/6/7/8/9).
- `node --check` clean on `src/onboardRouter.js`, `src/mcp-server.js`, `src/identityRegistry.js`, `src/receipt.js`.
- Loaded `onboardRouter.js` + all touched `src/` modules via `require()` to confirm the module graph resolves.

### Completion Notes List

- Tasks 1–6, 8 code-complete and self-consistent; Task 7 (live VPS verification) and the live-only sub-items of Tasks 5/8 (5.2/5.3, 8.4) are **explicitly not done** — they require a real VPS deploy, which this session did not perform per the standing rule to confirm destructive/deploy actions with the user first.
- **Found and fixed a bug in my own first draft**, not in pre-existing code: `identityRegistry.js`'s `writeChain` promise chain broke permanently after any single rejected write (`.then()` on a rejected promise with no handler just re-throws forever) — every subsequent mint/revoke would have silently no-op'd and replayed the first failure's error. Caught by the AC7 test failing with a stale error message; fixed by keeping `writeChain` itself always-resolving while returning the real per-call outcome to the caller.
- **Two deploy-relevant gaps surfaced that the story draft didn't anticipate:** `docker-compose.yml`'s `identities.json` bind mount was `:ro` (changed to read-write — mint/revoke cannot function otherwise), and the atomic write needed an `EXDEV` fallback because a single-FILE bind mount can put the temp file and the target on different devices. Neither is verified against the real VPS mount shape yet.
- **AC16 (mint only against a WebID the account controls) is implemented but unverified against live CSS shape** — `accountControlsWebId()` in `onboardRouter.js` infers ownership from the account's pod baseUrl list rather than a confirmed flat WebID-ownership endpoint, fails closed on any unconfirmable shape. Flag for Task 7.
- AC12 (`expiresAt` UX) and AC14's original design intent are handled per Task 3.5/3.6's decisions above — `lastUsedAt` IS implemented (coalesced background flush), `expiresAt` ships `null` everywhere (the AC's own named acceptable outcome).
- Requests tab (AC19) was already removed in a prior pass (commit `f513135`, ahead of this story per Nicolas) — verified, not re-done.
- **Post-deploy, six live findings total** (three at deploy, three in real use) — see Change Log. The pattern worth carrying forward: every one came from live use, none from local tests, and the two most expensive were *misleading error messages* rather than broken behaviour. Local tests always left at least one active identity, so the all-revoked deadlock was structurally invisible to them.
- **Known gap, not fixed:** legacy pre-7.9 identities carry `grantId: null` and cannot be revoked through `/onboard/revoke`, which looks up by `grantId` and rejects a non-string with a 400. Hit live on the hand-made "Nicolas (agent)" entry; Nicolas chose a manual out-of-band revoke over a backfill fix. A `grantId` backfill on load would close it for any remaining legacy rows.
- **Verified, contrary to the draft's assumption:** all four of Nicolas's WebIDs have real pods (`root:200 card:200` for each), so a pod-less agent WebID — floated as the clean least-privilege answer — is not what exists here. It isn't needed either: a WebID owning only its own agent pod already confines the blast radius, which is the design working as intended.
- **AC16 ownership check now live-confirmed working** (it was flagged unverified above): mint succeeded against Nicolas's own WebIDs and the flow has been exercised repeatedly through the real UI.

### File List

- `mcp-connector/src/identityRegistry.js` — extended shape, `validateIdentities`, `writeIdentity`/`updateIdentity`, atomic write + EBUSY/EXDEV fallback (widened post-deploy: live testing hit EBUSY, not EXDEV), `generateGrantId`.
- `mcp-connector/src/onboardRouter.js` — new. `/onboard/mint`, `/onboard/grants`, `/onboard/revoke`.
- `mcp-connector/src/mcp-server.js` — mounts `onboardRouter`, threads `grantId` into `loginIdentity`/receipts, adds `markSlugUsed`/coalesced `lastUsedAt` flush.
- `mcp-connector/src/receipt.js` — `grantId` field on receipts.
- `mcp-connector/identities.example.json` — full extended shape documented.
- `mcp-connector/scripts/verify-identity-registry.js` — new, offline registry test script.
- `mcp-connector/README.md` — "Adding/removing/rotating a person" section rewritten.
- `docker-compose.yml` — `identities.json` mount `:ro` → read-write; `ALLOWED_HOSTS` default gains `pod.nicolasdb.eu` (found live: `/onboard/*` was 403ing on the SDK's DNS-rebinding check).
- `backoffice/pod-api.js` — `RealBackend`/`DemoBackend` `mintConnector`/`listGrants`/`revokeGrant`.
- `backoffice/index.html` — Claude connector access section, mint/reveal dialogs, grants list, state/methods, cache-buster bump. Post-deploy: scope-disclosure line added to both the mint dialog and the reveal modal; "Your pod root" field and its copy button removed (misleading — named the agent's own pod, not the target).
- `docs/team-onboarding.md` — steps (d)/(e) rewritten as the button, renumbered (f)/(g), revocation path added.
- `hetzner-gateway/nginx/conf.d/04-pocpod0.conf` — new `/onboard/` location block, **deployed**; `proxy_pass` fixed live (variable + appended path doesn't rewrite the URI the way a literal proxy_pass URI does — matched the codebase's established no-appended-path pattern instead).
- VPS server-authored `.env` — `MCP_ALLOWED_HOSTS` gains `pod.nicolasdb.eu` (not tracked in the repo, edited directly over SSH like `identities.json`).
- `_bmad-output/planning-artifacts/epics.md` — Story 7.9 shipped-outcome note.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `story-7-9…` → `in-progress`.

## Change Log

| Date | Change |
|---|---|
| 2026-08-12 (live use) | **Task 7 live click-through completed by Nicolas end-to-end**: mint → claude.ai connector setup → public file read → `shared/` listing → root listing, all working against a properly-scoped agent identity. Three further findings, none caught by local tests, all from real use: (4) **all-revoked boot deadlock** — `loadIdentities()` threw when every entry was revoked, `bootIdentities()` treats that as fatal, and `/onboard/mint` (the only way to create a replacement) is served by the *same* process, so revoking the last identity was unrecoverable without out-of-band file surgery. The guard was correct pre-7.9, when an empty file meant misconfiguration; it became wrong the moment revocation was a product feature. Removed; empty active map is now a legitimate return value; `/healthz` no longer requires `identities.size > 0`; regression test added. (5) **`identities.json` ownership** — a write performed via `docker exec` (which defaults to root) left the file `root:root`, and the app drops to uid 1000 via `gosu node`, so the next boot hit `EACCES` and crash-looped. Fixed with `chown 1000:1000` + `--force-recreate`; a testing artifact rather than a code defect, but the failure mode is real for any manual write. (6) **`solid_read_resource` on a container reported a false permission denial** — see the separate entry below. Also confirmed by live probe: `/healthz` returning 403 from a developer laptop is Story 8.4's AC5 IP allowlist working correctly, not a regression. |
| 2026-08-12 (scope disclosure) | **Owner-privilege footgun found by Nicolas in live use, and addressed in the UI.** He minted a connector while signed in as the WebID of the pod holding his *data* rather than his agent WebID. The result works perfectly and warns nobody, while holding Read/Write/**Control** over that entire pod via the root ACL's `acl:default` — the exact blast radius the agent-pod design exists to prevent. Root cause is not architectural: minting binds to the signed-in WebID, which is correct; the dialog simply never said what that choice costs. Established during the discussion and worth recording: **a CSS client credential carries the full authority of its WebID and cannot be scoped** — Solid-OIDC defines no scope parameter and CSS v7 implements none — so a per-grant rights picker in the mint modal would be theatre, and worse, would read as a guarantee. WAC on the target is the only real boundary. The UI therefore *discloses* instead: the mint dialog now names the pod the connector will control before confirming, and the reveal modal restates it. Also **removed the "Your pod root" field** from the reveal modal — derived from the minting WebID, it named the *agent's* own pod rather than the target, and WAC has no reverse index, so no endpoint can enumerate where a credential may go. Only the human knows the target; `team-onboarding.md` now says to put it in the project instructions or prompt. |
| 2026-08-12 (container read) | **Pre-existing defect surfaced by 7.9's identity change, fixed.** `solid_read_resource` calls Inrupt's `getFile()`, which CSS answers with a bare `403 Forbidden` when the URL is a container — even where the agent demonstrably has Read. `toToolErrorResult` then mapped it to "Access denied — this agent lacks the required WAC permission", sending the reader off auditing ACLs, re-minting credentials and doubting the WebID, none of which were wrong. Live-proved with the same session, same URL: raw `session.fetch()` → `200 text/turtle`, `getFile()` → `403`. Masked until now because the connector previously ran as the pod owner; moving to a correctly-scoped agent identity is what exposed it. A Solid container URL always ends in `/`, so the case is decidable before any request — `solid_read_resource` now refuses with a 400 naming `solid_list_container`, and the tool description says so up front. Changes no identity's reach, only which request is made and what it says when it can't. **Also a data point for AC11's failure-mode story: the two worst time sinks today were both misleading error text, not broken authorization.** |
| 2026-08-12 (deploy) | **Deployed to VPS** (`vps-backup` → `pocpod0` deploy → `hetzner-gateway` deploy) with Nicolas's go-ahead. Found and fixed **three live bugs** none of the local testing caught: (1) `ALLOWED_HOSTS` missing `pod.nicolasdb.eu`, so `/onboard/*` 403'd on the SDK's DNS-rebinding check before reaching the router at all; (2) `proxy_pass $upstream/onboard/;` (variable + appended path) doesn't rewrite the URI the way a literal proxy_pass does — nginx passed only `/onboard/` regardless of the real path, fixed to match the codebase's own no-appended-path pattern; (3) `_atomicWrite`'s rename failed with `EBUSY` (not the anticipated `EXDEV`) against the live single-file bind mount — a bind-mounted file IS a mount point, and rename cannot replace one — fallback widened to catch both. All three redeployed and confirmed working server-side. Live click-through (mint/revoke via the actual UI, AC7.1–7.7/7.11) handed to Nicolas — needs his account session, which this session correctly would not substitute for. |
| 2026-08-12 | **Tasks 1–6, 8 implemented.** Task 7 (live VPS verification) deliberately not run at this point — needed Nicolas's go-ahead per the deploy-confirmation rule (see the entry above for what happened once it was given). See Dev Agent Record for the bug caught in review (writeChain permanent-break) and two deploy-relevant gaps found mid-implementation (read-only volume mount, EXDEV on single-file bind mount — later found to actually be EBUSY, see above). |
| 2026-08-03 | Drafted. Blocker named in the epic sketch (boot-time singletons) confirmed already resolved by 8.6.1. Two architectural findings: the backoffice has no server side, and the connector's own vhost is IP-allowlisted against browsers — jointly determining that the endpoint lives in `mcp-connector` and is routed via `pod.nicolasdb.eu/onboard/`. SQLite deferred. Mint-then-write-failure orphan-credential path identified. |
| 2026-08-03 | Marked `needs-redraft` (sprint-change-proposal-2026-08-03). Nicolas never used the 7.4 credentials UI — the unlock gate charged a password for the wrong thing. Account-gate scope moved to Story 7.10. |
| 2026-08-11 | **Redrafted after 7.10 and 8.9 shipped.** Account-gate scope removed entirely (7.10 deleted the gate; the cookie *is* the account token — no password anywhere). Grant-table shape from `epics.md:372` adopted **and extended**: AC4 adds `grantUri` plus reserved-nullable `purpose`/`scope`/`excluded`/`consequenceOfRefusal` mirroring `poc:ConsentGrant`, on the migration-window argument from the consent-loop proposal — with an explicit fence that no intake, no grant resources and no approval step are in scope. Revocation UI promoted to a first-class AC (AC10) with cache eviction (AC11), and revocation designed as a tombstone — which surfaced a new fail-fast hazard: a revoked row whose credential is gone would kill boot, so AC7 requires boot/resolution/duplicate-checking to skip revoked rows. `expiresAt` gated behind warn-before-the-wall + one-action renewal + naming it on the onboarding page, with "ship it as null" declared an acceptable outcome (AC12). Per-slug attribution absorbed from 8.9 as `grantId` — explicitly **not** the slug, which is a bearer credential and must never be written into another person's pod (AC13). Fabricated "Requests" tab removal accepted into this story with rationale (AC19). Every deferred item now names where it goes. |
| 2026-08-11 | **Both open questions closed by investigation, not deferred to the developer.** (1) CSS does not invalidate an issued token when its credential is deleted — `@solid/access-token-verifier` has no introspection path, verification is offline JWT+DPoP, oidc-provider's default TTL is 1h, and the IdP's `revocation_endpoint` is irrelevant to a resource server that never introspects. Revocation therefore redesigned as an **authorization** act: WAC revoke (instant, proven live in 8.9) + credential delete (blocks new tokens) + cache eviction, in that order — AC11 and Task 3.2 rewritten. (2) `resolveIdentity` has **no** positive-cache eviction surface; it must be built, not found — Task 3.3 rewritten so nobody spends time searching. Re-mint-after-revoke confirmed already covered by AC7 + Task 1.3 (duplicate-`webId` checks skip revoked rows, tombstone retained). |
| 2026-08-12 | **`/onboard/` routing verified as not automatic.** Checked `hetzner-gateway/nginx/conf.d/04-pocpod0.conf` directly: today it has one `location /` forwarding everything to CSS, no route to `mcp-connector`. This story requires a manual `location /onboard/` block in that separate repo, proxying to `http://mcp-connector:3939` on the shared `gateway` network, plus its own deploy there — not covered by pocpod0's `make vps-deploy`. Documented under "Where the server side comes from" so the dev agent doesn't assume same-origin routing already exists. |
