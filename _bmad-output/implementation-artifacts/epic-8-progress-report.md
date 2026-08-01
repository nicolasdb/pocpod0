# Epic 8 — Solid MCP Connector: Progress Report

Living record of Epic 8 progress with pointers to durable, checkable proof on the
live pod (`pod.nicolasdb.eu`) — not just transcripts. Updated per story as they close.

## Convention (binding for 8.2 onward)

- **`https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md`** is a running log.
  Each story that does live pod work **appends** a dated section to it (read existing
  content first, write back existing + new section) — never overwrite/replace it.
- **This progress-report.md** gets a new "Story 8.x" section per story on close,
  same table format as 8.1's: a proof/checkable-artifact table, bugs found+fixed,
  scope notes. Keep 8.1's section as-is; add below it, don't restructure past sections.
- Any intentional live-pod leftover (proof file, etc.) gets a row in that story's
  table here, and a line in the story file's own AC7-equivalent note — same pattern
  as 8.1's post-review addendum above.

## Story 8.1 — WAC Manager Live Verification & Hardening

**Status:** review (2026-07-30)
**Full narrative:** `8-1-wac-hardening-verification.md` (Dev Agent Record has per-AC detail)

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Proof file | `https://pod.nicolasdb.eu/hyperscope_ndb/shared/story-8-1-proof.txt` | AGENT (`nicolas_claude`) wrote this live, via client-credentials token, into Nicolas-granted container (AC1). Left in place intentionally — not cleaned up. |
| Action log | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` | Ongoing log of AGENT-authenticated actions against the pod, written by AGENT into its own workspace. Append to this on future sessions rather than replacing it. |
| ACL on `hyperscope_ndb/shared/` | account UI / direct `.acl` GET | Confirms `nicolas_claude` still has only `Read, Append, Write` — never `Control` — unchanged by any of this story's grant attempts (both of which CSS rejected). |
| Code diff | `git diff` on `mcp-connector/src/podClient.js` + `wacManager.js` | The two bugs found+fixed: string-content write crash, and 403-vs-friendly-error normalization. |

### Bugs found and fixed (live, not theoretical)

1. **`podClient.js writeFile()`** — a plain string content argument crashed before any network call (Inrupt's Node `File`-detection polyfill can't handle a raw string). Fixed: coerce to `Buffer`.
2. **`wacManager.js grantAccess()` / `setPublicAccess()`** — an agent without `acl:Control` got a raw Inrupt 403 stack trace instead of the documented `"...does not have Control access..."` message. Fixed: `_saveAclOrThrowControlError` normalizes it.

### Scope notes (not bugs, just how CSS actually behaves)

- **AC2** (WAC-read on the data-pod container) is a **verified negative**: CSS requires `acl:Control` just to *read* a resource's `.acl`, not only read/write on the resource — so `listAgentsWithAccess`/`getAgentAccess` correctly return `null` for AGENT there. This is proof the two-token model holds, not a gap to close.
- **AC3** used `setPublicAccess` + an anonymous out-of-app fetch instead of a named second-agent grant, because no second Solid WebID exists in this environment. Allowed under AC5's own wording; noted rather than silently substituted.

## Story 8.2 — MCP Server: stdio -> Streamable HTTP Transport

**Status:** review (2026-07-31)
**Full narrative:** `8-2-http-transport.md` (Dev Agent Record has per-AC detail)

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Action log entry | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (Story 8.2 section, appended 2026-07-31) | Live MCP client (`initialize` -> `tools/list` -> `tools/call solid_list_container`) ran successfully over the new HTTP transport against `hyperscope_ndb/shared/`, using AGENT's existing read access from 8.1. |
| Code diff | `git diff` on `mcp-connector/src/mcp-server.js`, `src/auth.js`, `package.json` | `StdioServerTransport` replaced by `StreamableHTTPServerTransport` behind `createMcpExpressApp()`; `.env` loading made path-explicit (no longer cwd-dependent); `express` declared as a direct dependency. |
| Verification script | `mcp-connector/scripts/verify-http.js` | Committed, re-runnable real-client check (not a one-off) — this is what 8.5 should reuse rather than rebuilding. |
| README | `mcp-connector/README.md` | HTTP invocation, PORT/HOST config, local-verification command documented; stdio instructions removed. |

No data-pod writes in this story beyond the read-only `solid_list_container` call above — transport-only change, per the story's own scope boundary. `wacManager.js`/`podClient.js` were not touched.

### Decisions recorded

- **Session model: stateless, per-request transport+server** (`sessionIdGenerator: undefined`), not stateful. Rationale: 8.3 gives each person their own endpoint bound to their own token, so per-request construction is the shape that story wants anyway; a stateless server also survives restart without clients holding dead session IDs. The Solid session itself stays a boot-time singleton (`keepAlive: true`) regardless — different lifetime from the per-request MCP transport/server.
- `GET`/`DELETE /mcp` return `405` (no SSE stream/session to serve in stateless mode).
- `GET /healthz` added, unauthenticated, deliberately omits the WebID.

### Bugs/gaps found and fixed (this story)

1. **`auth.js` `.env` loading** — bare `dotenv.config()` resolved relative to `process.cwd()`, which is `/` in this sandbox (and would be wrong for `npm run mcp` invoked from elsewhere too). Fixed: path-explicit `dotenv.config({ path: path.join(__dirname, "..", ".env") })`.
2. **`express` as transitive-only dependency** — resolved at runtime purely by hoisting from `@modelcontextprotocol/sdk`'s own dependency. Declared explicitly in `package.json` (AC7).

### Scope notes

- Permission-writing tools (`solid_grant_access`, `solid_revoke_access`, `solid_set_public_access`) were **not** exercised against the data pod in this story's verification — 8.1 already proved their Control-access enforcement live, and re-running that adds no new information (story's own Task 5.2 instruction).
- Audit journal, rate limiting, TLS/nginx/systemd, and per-person routing are explicitly deferred to 8.3/8.4, per the story's scope boundary — not implemented here.

## Story 8.3 — Per-Person MCP Endpoints

**Status:** review (2026-07-31)
**Full narrative:** `8-3-per-person-endpoints.md` (Dev Agent Record has per-AC detail)

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Action log entry | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (Story 8.3 section, appended 2026-07-31) | Boot, routing, and isolation all live-verified; throwaway account provisioned and its credentials revoked afterward. |
| Code diff | `git diff` on `mcp-connector/src/mcp-server.js`, new `src/identityRegistry.js`, `scripts/gen-slug.js`, `scripts/verify-isolation.js` | Bare `/mcp` replaced by `POST /mcp/:slug`; N-identity boot with fail-fast; identity registry load/validation. |
| Config template | `mcp-connector/identities.example.json` | Shape of the gitignored `identities.json` — placeholders only, no real values ever committed. |
| Isolation script | `mcp-connector/scripts/verify-isolation.js` | Committed, re-runnable proof that identity A is denied on identity B's private resource, with 8.2's actionable error text — not asserted, run live during this story. |
| README | `mcp-connector/README.md` | Per-person URL scheme, add/remove/rotate procedure, URL-secrecy trade-off, verification commands, explicit "public exposure is 8.4" note. |

### Decisions recorded

- **Bare `/mcp` removed, not kept as a configured identity.** Keeping it running alongside per-person routes would be exactly the undocumented shared-identity endpoint AC1 forbids. Anyone wanting the old single-identity shape configures it as one `identities.json` entry.
- **`identities.json` is a separate gitignored artifact from `.env`.** `.env` still holds nothing but the OIDC issuer (and, only transiently, OWNER credentials for onboarding). Identities never touch `.env`.
- **Slugs are validated, not just generated safely.** `identityRegistry.js` rejects non-URL-safe or too-short slugs and duplicate top-level JSON keys (which `JSON.parse` would otherwise silently drop) at load time, naming the offending entry's *label* only.
- **Defensive webId check added beyond the story's literal ask:** after each identity logs in, the server confirms `session.info.webId` matches the configured `webId` and fails fast (naming the label) on mismatch — catches a stale/typo'd config entry before it causes confusing tool errors downstream.

### Bugs/gaps found (this story)

- None in the touched code. One environmental gotcha reconfirmed: this sandbox's `dotenv` treats an unescaped `#` as a comment start even mid-value with no preceding space, silently truncating `AGENT_WEBID`'s `#me` fragment when re-parsed outside the normal `auth.js` load path. Not a product bug — `auth.js`'s own load path is unaffected — but worth knowing if you ever re-parse `.env` by hand for a script.

### Scope notes

- Task 4.1's throwaway account (`story83throwaway1785486779`) was provisioned via the full CSS HTTP flow (account create -> password login register -> pod create -> client-credentials mint), live-confirmed end-to-end. Its client-credentials were revoked at the end of the isolation test; the **account shell** itself cannot be removed over HTTP (CSS exposes no account/pod delete) — tracked as Story 7.7's job, not this one's.
- Rate limiting, TLS/nginx/systemd, and the Anthropic IP allowlist remain out of scope here, per the story's own boundary — 8.4's job.

## Story 8.4 — VPS Deploy & Hardening

**Status:** review (2026-08-01)
**Full narrative:** `8-4-vps-deploy-hardening.md` (Dev Agent Record has per-AC detail)

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Action log entry | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (Story 8.4 section, appended 2026-08-01) | Full deploy/hardening narrative, live-verified end to end. |
| Live endpoint | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` | TLS + rate limiting + IP allowlist + audit journal all live in production, not local-only. |
| nginx vhost | `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf` (separate repo) | Subdomain, TLS, `access_log off`, allowlist — not in `pocpod0/infra/`. |
| Code diff | `mcp-connector/src/journal.js` (new), `entrypoint.sh` (new), `Dockerfile`, `src/mcp-server.js` | Audit journal + `safeHandler` outcome classification; root→node privilege-drop via `gosu`. |
| README | `mcp-connector/README.md` — "Deploying on a VPS" | Restructured 2026-08-01 into Divio quadrants (Reference / How-to / Explanation) rather than one mixed section. |

### Bugs found and fixed (live, not theoretical)

1. **`mcp-audit` named volume created root-owned by Docker** — silently EACCES'd every audit-journal write from the non-root `node` container user. Fixed durably via `entrypoint.sh` + `gosu` (chowns as root, drops to `node`, self-heals every boot) rather than a one-off `chown`.
2. **`access_log off` on the proxy `location` block was insufficient** — a resolver-failure request (upstream not yet running) still leaked the slug into the **global** `access.log`. Fixed by moving `access_log off` to server scope on both server blocks; re-probed clean (0 hits).
3. **AC5's allowlist and AC6's internal reuse path collided** — `ALLOWED_HOSTS` set to the public hostname only made every internal call from `gateway` fail with a genuine `403 Invalid Host` (the SDK's DNS-rebinding check, not a routing fault). Fixed by listing both hostnames, public first (the compose healthcheck reads element 0).
4. **`make vps-push`'s `rsync --delete-after` had no guard** — would silently delete server-authored files (`identities.json`, and an unrelated pre-existing gap, `backups/nightly-backup.log`) on the next unrelated push. Fixed with a dry-run-then-refuse guard (ported from `hetzner-gateway`'s own fix for the identical problem), requiring `FORCE=1` to override.

### Decisions recorded

- **Docker compose service, not systemd** (brief T4 deviation) — no host Node toolchain on the VPS, every other service is already a container, consistent with `architecture.md`'s own INFRA-2.
- **`/healthz` is session-aware** (closing a gap 8.2 and 8.3 both deferred): aggregate boolean over every configured identity's `session.info.isLoggedIn`, 200 iff all alive — no per-identity/WebID/count ever exposed, by construction (`.every()`).
- **No roaming admin IP allowlisted**, by Nicolas's choice (2026-07-31) — ssh-based administration instead, removing a credential-shaped fact that would need re-checking on every ISP IP change.
- **README restructured along the Divio documentation system** (tutorial/how-to/reference/explanation, never mixed in one doc) rather than appending more mixed-shape prose to the existing "Deploying on a VPS" section.

### Scope notes

- Task 8's throwaway account (`mcp84iso`) was provisioned for the deferred AC5 cross-identity re-verification, live-confirmed over the **public URL**. Credentials revoked afterward (DELETE 200, re-GET 404 confirmed); the account/pod shell remains a permanent orphan pending Story 7.7. Improvement over 8.3: this throwaway's password was retained outside the repo, so a future story can reuse it instead of minting orphan #3.
- The Epic 8 action-log/progress-report convention itself is a changelog/audit trail, not one of the four Divio quadrants — kept separate from the README restructure rather than forced into it.

## Epic 8 — remaining stories

- 8.5 Live verification — backlog (depends on 8.1, now unblocked)
- 8.6 Team onboarding doc — backlog
- 7.7 Delete pod with ceremony — drafted, closes the no-HTTP-delete gap noted above
