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

## Story 8.5 — Live Verification from claude.ai

**Status:** review-ready — all tasks (1–9) done, all 11 ACs met with live evidence.
**Full narrative:** `8-5-live-verification.md` (Dev Agent Record has per-task detail)

Code changes were built in a dev sandbox (no AGENT credentials, no network path to the live endpoint) and validated via `node --check` + an 18-case identity-registry unit-check. Task 7 (adding the connector in claude.ai, driving a real conversation) was run live by Nicolas — the whole point of this story is proof from a client the team didn't write, so this step could not and was not automated. Tasks 2, 8, and 9.1 (AGENT self-audit, journal read, live regression, action-log append) all required either AGENT credentials or the live session Task 7 produced, and were completed afterward via `docker exec` on hetzner.

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Code diff | `git diff` on `mcp-connector/src/wacManager.js`, `mcp-server.js`, `identityRegistry.js`, `whoami.js`, `onboarding.js`, `scripts/verify-http.js` | The four folded-in deferred items (8.1's `getAgentAccess` null ambiguity, 8.2's session-expiry + error-classification gaps, 8.3's identity-registry operator guards) plus corrected `PROBES`/`GRANTS` reference material. |
| Identity-registry unit-check | ephemeral script, not committed (8.2/8.3/8.4 precedent) | 18/18 cases pass: 13 original 8.3 cases + 5 new (duplicate webId, duplicate clientId, over-permissive mode ×2, restrictive mode still loads). Full output in the story's Dev Agent Record. |
| `deferred-work.md` | strikethrough + **CLOSED** notes on the four items | Traceable closure, not silent deletion of history. |
| claude.ai transcripts | `_bmad-output/test-artifacts/Claude-Testing hypercampus connector with Solid pod.md` (one consolidated export) + connector-setup screenshot | AC4–AC7 evidence — a real, independent MCP client exercising every tool. |
| Live journal | `/app/audit/journal.jsonl` on hetzner (`docker exec mcp-connector`) | AC8 — all three outcome classes (`ok`/`denied`/`error`), attributed by label, 0 grep hits for the slug/secrets. |
| `verify-http.js` live re-run | via `docker exec mcp-connector node scripts/verify-http.js <live URL>` | AC10 — ALL CHECKS PASSED, including the new Task 5.2 pinned negative-test wording assertion. |
| `epic-8-action-log.md` on the pod | `nicolas_claude`'s pod, Story 8.5 section | AC11 — appended live, byte-length growth (7995→9810) and prefix preservation both verified, not assumed. |

### Live findings from Task 7 (evidence, not just checkmarks)

- **`solid_get_permissions`** rendered a human sentence ("...requires Control access... read/write only") every time — never the literal string `null` (AC5).
- **Negative test**: write into `tasks/` (ungranted) failed with the exact pinned wording ("Access denied — this agent lacks the required WAC permission on that resource."), verbatim match, no drift (AC6).
- **Approval test**: `solid_grant_access` triggered *two* confirmation layers — a text pause from Claude itself, and claude.ai's own native approval UI — before the call ran. The client genuinely gates on `destructiveHint`, a stronger result than the "no prompt is a legitimate outcome" fallback the story allowed for (AC7). The call then 403'd correctly (agent has no Control anywhere, by design) — no grant was ever created, nothing to revert.
- **Resource-precise isolation**: `office-vault.md` inside the granted `shared/` container came back denied via its own resource-level ACL override, while every sibling resource succeeded — WAC enforcement is finer-grained than the container grant alone.
- **Write→read propagation, live-measured**: 335ms write, first read back byte-exact 1ms later, 5/5 consecutive reads matched. No connector- or CSS-side caching/delay exists. A real client-side stale-cache issue was found on Nicolas's own editor (not the connector) — ruled in by direct measurement, not assumed.

### Decisions recorded

- `wacManager.getAgentAccess()`'s return shape changed from a bare value to `{ aclVisible, access }` — a deliberate, documented break in shape (not in exported function signature/params) so "ACL not visible at all" and "ACL visible, zero grants" are structurally distinguishable rather than both reading as falsy.
- `buildMcpServer()`/`safeHandler()` now take the whole `identity` object rather than a destructured `session`/`label`, so a mid-request re-auth's new session is picked up by tool handlers without a stale closure — necessary plumbing for Task 4's bounded 401 retry, not scope creep.
- Task 6's file-mode guard is enforced (refuses to load), not advisory (README `chmod 600` text) — same posture upgrade already applied to slug entropy in 8.3.

## Story 8.6 — Capture Surface: Append-First Tools, Destructive Ceremony, and the Capture Skill

**Status:** in-progress (2026-08-02) — Tasks 1–6, 5b all complete and live-verified; Task 7 (this section) closing the loop.
**Full narrative:** `8-6-capture-surface-and-skill.md` (Dev Agent Record has per-task detail)

Code built and `node --check`-verified in this session, then deployed live to the VPS (two rebuild+redeploy cycles, both confirmed with Nicolas — one for the initial tool set, one for two bugs found mid-live-verification), and exercised from a real claude.ai conversation by Nicolas (full transcript in `test-artifacts/`).

### What you can check yourself, right now

| Check | Where | What it proves |
|---|---|---|
| Action log entry | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (Story 8.6 section, appended via `solid_append_resource` — the tool this story adds, dogfooding the convention) | Live proof the append tool works for the exact job the epic-8 convention has done by hand since 8.2. |
| Code diff | `git diff` on `mcp-connector/src/podClient.js`, `mcp-server.js`, new `src/receipt.js` | `appendFile`/`confirmGone` added; `deleteResource` switched from inrupt's `deleteFile` to raw `fetch` DELETE (fixes 8.1's trailing-slash 404 at the root); `solid_write_resource` gained `destructiveHint`+existence-probe ceremony; two new tools registered; read-receipt side effect wired into `solid_read_resource`. |
| Skill split | `mcp-connector/SKILL.md` (now the user-facing capture skill) + `references/developer-toolkit.md` (former `SKILL.md` content, preserved) | Epic 8 now ships the *skill* half of a Claude plugin, not just the MCP half. |
| `verify-http.js` live re-run | `docker exec mcp-connector node scripts/verify-http.js <live URL>` | 9 tools listed (was 7), `solid_list_container` OK, 8.5's negative test wording unchanged — no regression. |
| claude.ai transcript | `_bmad-output/test-artifacts/Claude-Validating hyperCampus connector Task 5 steps.md` | AC2, AC5, AC7 live evidence, plus the two bugs found and fixed mid-session. |
| Live proof note | `https://pod.nicolasdb.eu/hyperscope_ndb/shared/story-8-6-task5-validation-report.md` | Nicolas's own session captured a written validation report onto the pod via the capture tools — a second, independent dogfood of the capture path. |
| Live journal | `/app/audit/journal.jsonl` on hetzner | `solid_append_resource`, `solid_delete_resource`, `solid_write_resource`, `read_receipt` all present with correct `ok`/`denied`/`error` outcomes, attributed by label. |

### Bugs found and fixed (live, not theoretical)

1. **`toToolErrorResult`'s 409 branch discarded specific error messages.** Any 409 (both current producers are `solid_delete_resource`'s own guards) got overwritten with a generic "Conflict" string — live-observed when the non-empty-container refusal lost its actionable "delete the contents first" text. Fixed: 409 now passes `err.message` through.
2. **Read-receipt writes had no path to the existing 401-retry.** `safeHandler` already gives every tool call a one-shot reauth-and-retry on a stale session (Story 8.5 Task 4), but the receipt-write call sat inside its own try/catch (added so a receipt failure can never abort the read itself) — which caught 401s *before* they could reach that retry logic. A receipt attempted against a stale long-running session therefore failed permanently instead of self-healing. Root-caused via direct server-side reproduction (`docker exec`, fresh login against the identical grant succeeded instantly), disproving the claude.ai agent's own incorrect on-the-spot conclusion that receipt-writing "wasn't implemented" — the journal showed the attempt firing on every single cross-pod read from the very first one, well before any grant existed. Fixed: receipt write now gets the same one-shot reauth retry as every other tool call.

### Decisions / findings recorded

- **`access-log/` grant is RW, not Append-only** — Epic 7's backoffice UI has no Append-only option or reset-to-inherit today (only RO/RW/"only me"/"public read"), so 5b.4's "Append-only, never Write" design intent can't be realized through current tooling. Scoped to Story 7.6/7.8; skill/onboarding language corrected to say RW-today rather than imply Append-only already works end to end.
- **CSS does not auto-create a missing parent container.** Nicolas had to create `access-log/` by hand before a grant on it meant anything — an 8.7 onboarding-sequence item.
- **AC7's round trip has a caveat.** The new-conversation test had the pod root URL available via project instructions, so it wasn't discovering the pod root cold — only locating a specific file within a known container by description. A fully cold variant (WebID-profile pod-root discovery) is a stricter test not exercised here.
- **Pre-existing `/healthz` staleness, unrelated to this story's changes**, found during pre-deploy health check: `session.info.isLoggedIn` goes stale between real tool calls, self-healing only reactively. Assessed low-risk (nothing in `docker-compose.yml` restarts on it) and deferred — see `deferred-work.md`.

## Epic 8 — remaining stories

- 8.6 Capture surface — **in-progress**, Task 7 (this update) closing the loop
- 8.6.1 Lazy identity loading — backlog
- 8.7 Team onboarding doc — ready-for-dev
- 7.6/7.8 Backoffice grant-scope UI (Append-only, inherit-reset) — flagged by 8.6, not yet drafted as scoped subtasks
- 7.7 Delete pod with ceremony — drafted, closes the no-HTTP-delete gap noted above

---

## Story 8.9 — Access Journal Tamper-Evidence Spike (2026-08-11)

A timeboxed spike, not a feature: one question, answered with live evidence, then applied.

**Question:** can the agent that writes read-receipts into a pod's `access-log/` also rewrite them — and if so, is Append-only even reachable, given the receipt write path?

### What was already believed, and what was actually true

Story 8.6 recorded the grant as RW and attributed the absence of Append-only to the Epic 7 backoffice offering no such toggle. Both halves needed checking, and one was wrong.

| Belief | Verified outcome |
|---|---|
| The `access-log/` grant might cascade Write from pod root | **No cascade.** `access-log/` carries its **own** `.acl`; pod root grants the agent nothing. The RW was an explicit leaf grant. |
| The journal is rewritable by its own writer | **Confirmed.** `PUT` of the file's own bytes → **205**, file mtime moved. Not a theoretical hole. |
| Append-only is blocked by the backoffice UI gap | **Wrong.** `wacManager.grantAccess({append:true})` authored a clean Append-only ACL end-to-end. The gap blocks *self-service*, not the capability — which downgrades the 7.6/7.11b deferral from "blocks Append-only" to "makes it a scripted step, not a UI step." |
| Path A diverges from Epic 5's JSONL convention | **Backwards.** Epic 5's `receipt.py:271` already writes one Turtle resource per receipt. Path A *converges* with it. |

### Evidence

| Check | Where | What it proves |
|---|---|---|
| `scripts/probe-access-log-acl.js` | Live, AGENT credential, `hyperscope_ndb/` | AC1/AC2 ground truth: `WAC-Allow: user="append read write"`, `PUT` → 205, `.acl` 403 to the agent (Control required). Governing Turtle read host-side and recorded verbatim in the story file. |
| `scripts/probe-append-only.js` | Live, scratch container in the agent's **own** pod | 8/8. Path A: `POST` → 201, `PUT`/`GET`/`DELETE` on an existing child denied. Path B: insert-only N3 `PATCH` → 205, `deletes`-bearing PATCH denied. Append-only is real and CSS evaluates it per-mode. |
| `scripts/verify-receipt-appendonly.js` | Live, real `access-log/`, before **and** after tightening | AC8 to Story 8.6's standard. Before: receipt POST 201, container listing grew, receipt read back and parsed. After: POST still 201, and the agent is **denied** listing, read-back, overwrite and delete of its own receipt — 403 on all four. |

The scratch container lived in the agent's own pod precisely so the agent's **lack** of Control on a data pod (Story 8.1 AC4) was never weakened to make the spike easier.

### Decision — Path A, with its cost stated

POST one resource per receipt; tighten the grant to `acl:Append`.

Chosen because **format is the reversible part and the tamper property is not**. A weekly consolidation job can fold JSON receipts into triples, SQLite, or one rolled-up file later. What no later job can recover is a receipt written while its writer held Write — that entry is untrustworthy forever — or a receipt's link to the grant it was made under, which timestamp correlation can only guess at.

- **Cost:** the journal is many small resources, so reading it means listing a container rather than reading one file.
- **Side effect, deliberate:** the agent loses **Read** on `access-log/`. It can no longer see other readers' entries — a privacy gain that forecloses any future design needing the agent to read receipts back.
- **Does not solve:** (1) still a voluntary convention — CSS surfaces no server-side read log, so a reader that writes no receipt leaves no trace; Append-only makes the cooperative path trustworthy without making the record complete. (2) It constrains the **reader**, not the pod owner, who holds Control over their own `access-log/` — inherent to BP-1, and the price of putting evidence where the audited party cannot retract it. (3) A receipt records that a read happened, never what was done with the data afterwards.

### Applied

- `podClient.postResource()` — the write an `acl:Append` grant actually permits. `appendFile` is a read-then-overwrite and cannot be used under such a grant; both now coexist, with the constraint documented at both call sites.
- `receipt.js` — POSTs one JSON receipt per read, and reserves an `underGrant` field (explicitly `null` today, so "no grant recorded" is distinguishable from "predates the field").
- Live `access-log/` grant tightened to `acl:Append` only. Previous ACL preserved at `.acl.bak-8-9`; the pre-existing `receipts.jsonl` left in place as history.

### Reframing surfaced during the spike — carried to a change proposal

Nicolas's framing, which the story did not anticipate: **receipts exist to inform a permission decision.** They are the audit half of a consent loop — request → review → grant → audit → revoke — not a standalone log. The interesting UX inversion is that access is *requested with justification* (who, what, why, what if refused) and reviewed, rather than granted preemptively.

`poc:ConsentGrant` already ships exactly that vocabulary (Story 5.5: `requestedBy`, `purpose`, `scope`, `excluded`, `consequenceOfRefusal`, `revokedAt` tombstone, `expiresAt`) — but only in the pipeline. The connector knows nothing of it, and request intake does not exist: the backoffice "Requests" tab is a hardcoded stub, known since 7.2. This reframes Story 7.9, which owns the grant table.

Deliberately **not** built here — it is larger than a spike and larger than a backlog line. A sprint change proposal follows.

### Documentation corrected (AC6, AC7)

`docs/team-onboarding.md` and `mcp-connector/SKILL.md` promised Append-only "once 7.6/7.8 lands"; both stories were deferred post-PoC on 2026-08-11, making that a promise against unscheduled work on the one page whose purpose is honesty. Both now describe shipped behaviour with both limits attached. `epics.md` Story 8.7's honest-boundaries bullet now states the property as **verified**, not assumed.

### Deployed and verified in production

`make vps-deploy` refused on Story 8.4's guard (`deleting mcp-connector/audit/`). Investigated rather than forced: the live journal is in the `mcp-audit` named volume and the host path is an empty leftover, so forcing would have been harmless — but the path was excluded in the Makefile anyway, because a guard that cries wolf on a known-safe path every deploy is one that gets `FORCE`d reflexively, and the next thing it refuses might be `identities.json`.

Post-deploy, a real `tools/call solid_read_resource` on a foreign resource through the deployed endpoint: read OK (1196 chars), receipt `2026-08-11T16-35-31-868Z-aonuvr.json` created in `access-log/` under the Append-only grant, and **no** `read_receipt` error in the connector's own journal — which is how a receipt failure surfaces. AC8 now holds against production, not only against the library.

**Incidental, logged not fixed:** `scripts/verify-http.js` defaults to `http://127.0.0.1:3939/mcp` and its docstring instructs exactly that, but Story 8.4's `ALLOWED_HOSTS` now rejects it (`Invalid Host: 127.0.0.1`). In-container the working URL is `http://mcp-connector:3939/…`. A stale runbook whose failure mode looks like a protocol error.

## Story 8.10 — Agent File Upload: Ticketed Out-of-Band Transfer (2026-08-28)

### Problem

The connector's only write path was `content:` as a JSON string on `solid_write_resource`/`solid_append_resource`. For a file **already on disk**, that meant reading it into context and re-emitting it byte-for-byte as a tool argument — ~15k output tokens per 50KB, truncation-prone, and capped hard by `express.json()`'s 100kb default plus nginx's matching `client_max_body_size`. Verified against the MCP spec (2026-07-28, via Context7) that this is not a gap in our code: `tools/call` params are JSON with no byte channel, `roots/list` returns URIs only (no transfer), and `resources/*` flows server→client, the wrong direction. MCP has no client→server bulk-transfer primitive.

### Decision — Path A, ticketed (party-mode session survey of seven options)

`solid_prepare_upload(targetUrl, contentType, bytes)` probes the target (existence ceremony happens here, same as `solid_write_resource`), issues an opaque single-use ticket, and returns a ready-to-run `curl --data-binary @<path> <uploadUrl>` string. The agent runs it itself — the bytes never re-enter the JSON-RPC channel. Rejected: client-held CSS credential (reopens SEC-4), connector-pulls-by-URL (SSRF primitive), bare `curl -T` without a ticket (puts the slug in shell history/`ps`, undoes Story 8.4's `access_log off`).

### Built

- `src/uploadTickets.js` — in-memory `Map`, TTL 300s, CSPRNG token (same generator class as `scripts/gen-slug.js`), atomic delete-then-use redemption, bound to `{targetUrl, identity, contentType, bytes}` at issue time.
- `solid_prepare_upload` tool (10th tool) — existence probe reusing `_probe404`, `overwrite: true` gate, ticket issuance.
- `POST /upload/:token` — a **third** independent auth surface (`/mcp/:slug`, `/onboard`, now `/upload/:token`), own `express.raw` parser (never touches the 100kb `express.json` ceiling), own rate-limit bucket, own request timeout (290s, scoped off the `/mcp` path's 55s one — a bare `app.use()` for the old timeout previously applied globally and would have killed any real upload). Buffers, verifies declared `bytes` against actual length **before** any pod write, then PUTs. Content-type comes from the ticket, never the request.
- nginx `location /upload/` (VPS-side `11-solid-mcp.conf`, not in this repo) — `client_max_body_size 25m`, `access_log off` (token in the path), 300s timeouts. Deliberately **public** (no `allow`/`deny`) — unlike `location /`'s Anthropic-only allowlist, an upload comes from a shell-capable client's own machine, not Anthropic's infra; the single-use TTL-bound token is the credential, same posture as `/onboard`.
- `scripts/verify-upload-tickets.js` — all AC10 adversarial cases as a committed live-verification script.

### Live proof (2026-08-28, deployed VPS)

| Case | Result |
|---|---|
| Baseline upload + existence-probe/overwrite ceremony | OK |
| Ticket replayed after redemption | 404 |
| Unknown/guessed token | 404, identical body to a replay (no oracle) |
| Declared `bytes` ≠ actual body length | 400, pod byte-identical after, ticket consumed |
| Body larger than cap (26,214,401 bytes) | 413, refused at app level |
| Query-string target override on redemption | ignored — route has no target parameter, write bound to ticket's original `targetUrl` |
| Expired ticket (real 300s TTL, waited live) | 404 |
| >100kb real file end-to-end | 150,000-byte JPEG-content file uploaded via `curl`-equivalent POST; read back via a raw authenticated fetch (not `solid_read_resource`, which is lossy for binary) — SHA-256 `b69282220b2be0e225ea228b8af910f31bf66adac69ae38fb57bee1f02acfcdd` matched source exactly; content-type `image/jpeg` confirmed served from the ticket, not the request |

Journal (`journal.jsonl`) carries `upload_prepared`-equivalent (`solid_prepare_upload`, via the existing `safeHandler` convention) and `upload_completed` entries, label + target URL only — grepped clean of the token/slug.

### Bug found and fixed during live verification

Debugging a false "0 bytes received" failure led first to suspecting the server; root cause was the throwaway debug HTTP client (Node's bare `fetch()`) sending no `Content-Type` header, which `express.raw({type:"*/*"})` then refuses to parse (nothing for `type-is` to match). Real `curl --data-binary` always sends a default `Content-Type`, so the shipped server was correct as written — `scripts/verify-upload-tickets.js` was fixed to send an explicit header on every POST so it actually exercises what a real client sends, rather than a client bug masquerading as a server one.

### Scope confirmed out

claude.ai has no shell and cannot run the returned `curl` command — stated plainly in `SKILL.md`; the answer there stays download-and-upload-from-backoffice. Chunked-append via tool args was not built (AC12) — this story exists to remove exactly that pattern.

### Test resources

`shared/8-10-verify-upload*.txt` created and deleted during adversarial verification. `shared/8-10-proof-file.jpg` (150,000 bytes, random content) kept as live POC evidence of the >100kb path, per Epic 8 convention.
