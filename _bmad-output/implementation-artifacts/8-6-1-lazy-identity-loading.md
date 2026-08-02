# Story 8.6.1: Lazy Identity Loading — Onboard Without a Restart

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **the operator of the MCP connector**,
I want a newly-configured person to start working without restarting the service,
so that onboarding a teammate is not gated on a service restart that interrupts everyone already using it.

## Context / Why now

Story 8.7 walks a **real second person** through onboarding while Nicolas stays quiet. Under today's code that walkthrough contains a step reading "now the operator restarts the container" — which is both a bad experience and a genuine interruption for every other connected identity.

The cause is narrow and specific. `bootIdentities()` is **the only place in the codebase where a Solid session is ever created**:

```js
for (const [slug, id] of configured) {
  session = await getAgentSession({...});   // ← the only birth site
  identities.set(slug, { session, label, webId, clientId, clientSecret });
}
```

`identities` is then a fixed in-memory `Map`, and routing is a single lookup — `identities.get(req.params.slug)`. A slug added to `identities.json` after boot is simply not in the Map, so it 404s exactly like a guessed slug.

**This is not a storage problem.** Moving the identity map to SQLite or anywhere else changes nothing about the restart, because boot is still the only place sessions are created. (Story 7.9 owns the storage change, for a different reason: letting the backoffice write an entry without racing the connector reading it.)

**And the eagerness was deliberate.** Story 8.3 AC3, verbatim in the code comment:

> *if ANY identity fails to log in, the whole process refuses to start — a half-authenticated server that silently serves 3 of 4 people is worse than one that refuses to start.*

That property is worth keeping. This story does not trade it away — it keeps eager boot for the configured roster **and** adds a lazy path for identities that appear afterwards.

Scope boundary:
- **8.6 (before this):** capture tools + skill + receipts.
- **8.6.1 (this):** session lifecycle only. ~30 lines and a live test.
- **8.7 (after this):** the onboarding page, walked by a real second person — with no restart step in it.
- **7.9 (later):** backoffice-minted credentials + SQLite store. Different problem.

Do not change the storage backend here. Do not build minting UI here.

## Verified state (read from source 2026-08-02 — do not re-derive)

| Fact | Value |
|---|---|
| Session creation site | `bootIdentities()` in `src/mcp-server.js` — the only one |
| Identity map | in-memory `Map<slug, {session, label, webId, clientId, clientSecret}>` |
| Routing | `identities.get(req.params.slug)`; miss → `unknownSlugLimiter` then generic 404 |
| Boot policy | any failed login → `console.error` + `process.exit(1)` (8.3 AC3) |
| WebID cross-check at boot | `session.info.webId !== id.webId` → fatal, catches a stale/typo'd `webId` |
| Config source | `loadIdentities()` from `identities.json`; chmod-600 enforced, duplicate-`webId` refused, slug entropy floor 22 |
| Session keep-alive | `keepAlive: true`, process-lifetime |
| Re-auth path (8.5 Task 4) | one-shot re-login on 401, mutates `identity.session` in place so all holders see it |
| `/healthz` | `identities.size > 0 && every(session.info.isLoggedIn)`; aggregate boolean only, never a count or WebID |
| Miss-path uniformity (8.3 AC4) | unknown slug, bare `/mcp`, `/mcp/` all return the *same* generic 404 — response shape must not become a slug oracle |

## Acceptance Criteria

1. **A person added to `identities.json` after boot works on their next request**, with no restart and no interruption to identities already serving. Proven live, not asserted.

2. **8.3 AC3's fail-fast is preserved for the configured roster.** A broken credential present in `identities.json` at boot still refuses process start. The lazy path is strictly additive — it must not turn an existing startup failure into a silent partial service.

3. **The lazy path re-reads the identity source on a cache miss only**, never on the hot path of a known slug. A valid request must not pay a file read.

4. **A lazy login failure returns the same generic 404 as an unknown slug.** No new error shape, no timing or status-code difference that distinguishes "slug exists but its credentials are bad" from "slug does not exist" — that distinction is a slug oracle and 8.3 AC4 built the uniform miss path deliberately.

5. **All of `loadIdentities()`'s guards still apply to a lazily-loaded identity**: chmod-600 refusal, slug entropy floor, duplicate-`webId` rejection, and the boot-time `session.info.webId` cross-check. A lazily-added identity must not be able to enter through a weaker door than a boot-time one.

6. **The miss path cannot be turned into a login-attempt amplifier.** A guessed slug must not cause a file read plus an outbound OIDC login per request. Bound it — the tighter `unknownSlugLimiter` still applies, and a failed lazy load is negatively cached (or otherwise rate-bounded) so repeated guesses do not hammer CSS.

7. **`/healthz` stays honest and stays quiet.** It reflects lazily-added identities once they exist, still reports an aggregate boolean only, and still never leaks a count, WebID, or per-identity breakdown.

8. **Concurrent first-requests for the same new slug do not produce two logins.** Two simultaneous requests either share one in-flight login or one waits — never two sessions for one identity.

9. **The journal attributes a lazily-loaded identity correctly** by label, from its very first call, and greps clean of slug and secret terms.

10. **No regression**: `scripts/verify-http.js` passes against the live public URL, unknown-slug 404 and both rate-limit budgets behave as before, and 8.5's negative test still fails cleanly with its pinned wording.

11. **Story 8.7's walkthrough contains no restart step.** Confirm by reading it — this story exists to remove that line.

## Tasks / Subtasks

- [ ] **Task 1 — Lazy resolution on cache miss (AC: 1, 3, 5)**
  - [ ] 1.1 Extract a `resolveIdentity(slug)` used by the route: return the cached entry if present; otherwise re-read via `loadIdentities()`, and if the slug is now configured, log it in and cache it.
  - [ ] 1.2 Reuse `getAgentSession({..., keepAlive: true})` and the **same** `session.info.webId` cross-check `bootIdentities()` does. Factor the per-identity login into one function both paths call — two copies will drift.
  - [ ] 1.3 Known slugs must not touch the filesystem. The re-read happens only on a miss.
  - [ ] 1.4 Cache the resulting entry in the same `Map`, with the same shape (including `clientId`/`clientSecret`, which 8.5's re-auth-on-401 depends on).

- [ ] **Task 2 — Keep fail-fast (AC: 2)**
  - [ ] 2.1 Leave `bootIdentities()`'s eager loop and its `process.exit(1)` untouched.
  - [ ] 2.2 State in a comment why both policies coexist, so a future reader doesn't "simplify" the eager path away and silently reintroduce partial service.

- [ ] **Task 3 — Miss-path safety (AC: 4, 6)**
  - [ ] 3.1 A lazy login failure falls through to the existing `notFound` handler. Same body, same status. Do not add a distinguishing message.
  - [ ] 3.2 Negatively cache (short TTL) or otherwise bound failed lazy loads so a slug-guessing loop cannot drive one file read + one CSS login per guess. **This AC is the security-relevant one** — without it this story makes the guessing surface more expensive for us than for the guesser.
  - [ ] 3.3 Keep `unknownSlugLimiter` in front of the miss path, unchanged.
  - [ ] 3.4 Never log the attempted slug — it is the credential being guessed (8.3 AC7).

- [ ] **Task 4 — Concurrency (AC: 8)**
  - [ ] 4.1 De-duplicate in-flight logins per slug (a promise map is sufficient; there is no cluster mode here — single process).
  - [ ] 4.2 Ensure a rejected in-flight login clears its entry, so one failure does not permanently poison that slug until restart.

- [ ] **Task 5 — Verification (AC: 1, 7, 9, 10, 11)**
  - [ ] 5.1 Live: add an identity to a running container, call its endpoint, confirm it works with no restart and that an already-connected identity is uninterrupted.
  - [ ] 5.2 Confirm `/healthz` reflects it, still aggregate-only.
  - [ ] 5.3 Confirm journal attribution by label from the first call; grep for slugs and secret terms → 0 hits.
  - [ ] 5.4 Re-run `scripts/verify-http.js`; re-confirm unknown-slug 404, both rate-limit budgets, and 8.5's pinned negative-test wording.
  - [ ] 5.5 Confirm boot still refuses to start with a deliberately broken credential in `identities.json` — AC2 is easy to believe and easy to have broken.
  - [ ] 5.6 Remove the restart step from Story 8.7's walkthrough.

## Dev Notes

### Why this is small but not trivial

The change is a handful of lines. The care is in **not weakening three deliberate properties** that earlier stories argued for explicitly: 8.3 AC3's fail-fast boot, 8.3 AC4's uniform miss path, and 8.3 AC7's never-log-the-slug. Each is easy to erode by accident here — a helpful error message on the miss path is a slug oracle, and a "simplified" boot loop is silent partial service.

### The amplification trap

Naive lazy loading turns every guessed slug into a file read **and an outbound OIDC login attempt against CSS**. That is strictly worse than today, where a guess is a Map miss. Task 3.2 is not optional polish — without it this story hands a guesser a cheap way to generate load against the identity provider. Bound it before shipping.

### What this story is not

Not a storage change (Story 7.9). Not credential minting (7.9). Not a fix for `identities.json` holding plaintext secrets under file-mode protection alone — that is a real, separate question and stays open.

### Traps

- **The dev sandbox cannot reach the public URL** — allowlist excludes roaming addresses; curl returns `403`. On-host requests hairpin (8.4 Task 8's method). **A 403 from your laptop is not a broken deploy.**
- **`identities.json` is chmod-600-enforced at boot** — a re-read at runtime hits the same check. Writing the file with a looser mode will start failing lazy loads, not just startup.
- **403 ≠ expired session** (8.5 Task 4): the one-shot re-auth is 401-only. Do not entangle it with this story's login path.
- **Every VPS deploy is confirmed with Nicolas first** (8.4 precedent).

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Identity load + all validation guards | `loadIdentities()`, `src/identityRegistry.js` |
| Per-identity login + WebID cross-check | the body of `bootIdentities()` — factor it, don't copy it |
| Session creation | `getAgentSession()`, `src/auth.js` |
| Re-auth on 401 | `reauthIdentity()` — already mutates `identity.session` in place |
| Uniform miss response | `notFound` + `unknownSlugLimiter`, `src/mcp-server.js` |
| Live regression | `scripts/verify-http.js` |

### Invalidated Assumptions

- **Assumption:** adding a teammate requires a restart because the identity map is a static JSON file → **Reality:** the file is incidental. The restart exists because `bootIdentities()` is the only site that creates a Solid session. Changing the storage backend alone would not remove it.
- **Assumption:** moving identities to SQLite/Supabase solves the onboarding friction → **Reality:** it solves a *different* problem (concurrent writes from the backoffice — Story 7.9). Supabase is additionally ruled out: it would put every teammate's AGENT `clientSecret` on third-party infrastructure, which is not a defensible position for this project.
- **Assumption:** eager all-or-nothing boot is incidental strictness → **Reality:** it is 8.3 AC3, argued explicitly — a server silently serving 3 of 4 people is worse than one that refuses to start. Preserve it.

### Project Structure Notes

Changes confined to `mcp-connector/src/mcp-server.js` (identity resolution + route), possibly a small export from `src/identityRegistry.js`. No storage change, no schema, no new dependency. No changes to `backoffice/`, `pipeline/`, or `infra/`. nginx lives in the separate `hetzner-gateway` repo and is untouched.

### Testing approach

No test framework in `mcp-connector/` and this story does not add one (8.2–8.6 precedent). Evidence: `node --check`, the live add-without-restart demonstration, a deliberate broken-credential boot test for AC2, and the `verify-http.js` regression run. **Live evidence beats argument** — Epic 8 convention.

### References

- [Source: _bmad-output/implementation-artifacts/8-3-per-person-endpoints.md] — AC3 fail-fast boot, AC4 uniform miss path, AC6 slug entropy, AC7 never log the slug
- [Source: _bmad-output/implementation-artifacts/8-5-live-verification.md] — Task 4 re-auth-on-401 (401 only, never 403); Task 6 identity-registry guards
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md] — hairpin verification method, rate-limit design, deploy confirmation practice
- [Source: _bmad-output/implementation-artifacts/8-7-team-onboarding-doc.md] — the walkthrough whose restart step this story removes
- [Source: mcp-connector/src/mcp-server.js] — `bootIdentities()`, route handler, `/healthz`, limiters
- [Source: mcp-connector/src/identityRegistry.js] — `loadIdentities()` and its guards

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-02 | Drafted and inserted between 8.6 and 8.7. Origin: Nicolas asked whether slug management could be externalised (Supabase/SQLite) and said the slug mechanism was still foggy. Reading the source showed the fog was two conflated problems — slug→identity *lookup* (a storage question) and identity→*session* creation (the restart). The restart is caused entirely by the second, so no storage change fixes it. Supabase ruled out (AGENT secrets on third-party infra); SQLite deferred to 7.9 where the concurrent-write problem actually appears. |
