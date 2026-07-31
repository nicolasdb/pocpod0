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

## Epic 8 — remaining stories

- 8.3 Per-person endpoints — backlog
- 8.4 VPS deploy hardening — backlog
- 8.5 Live verification — backlog (depends on 8.1, now unblocked)
- 8.6 Team onboarding doc — backlog
