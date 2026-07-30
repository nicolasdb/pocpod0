# Story 8.2: MCP Server — stdio → Streamable HTTP Transport

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a team member on Claude Pro**,
I want the Solid MCP connector to serve over HTTP instead of stdio,
so that Claude.ai can reach it from Anthropic's infrastructure at a public URL — the only transport that works, since claude.ai's code sandbox cannot reach `pod.nicolasdb.eu` at all.

## Context / Why now

`src/mcp-server.js` currently uses `StdioServerTransport`, which only works for a locally-spawned process. Brief §1 verified empirically that claude.ai's sandbox network is allowlisted to package registries only (`curl https://pod.nicolasdb.eu/` → `403 host_not_allowed`), so a Skill running code in-chat can never reach the pod. A remote MCP connector inverts the direction — **Claude calls the server** from Anthropic's infra to a public URL — which is why HTTP transport is the gate for everything downstream in Epic 8.

Story 8.1 landed the correctness floor: `wacManager.js`/`podClient.js` are live-verified against the real pod, two real bugs found and fixed, and the two-token security property confirmed live (AGENT gets a clean documented error, not a 403 stack, when it tries to escalate on a data pod). **This story changes transport only.** It must not touch `wacManager.js`/`podClient.js` logic — those are now verified code, and re-verification is Story 8.5's job, not this one's.

Scope boundary against the next two stories, so this one doesn't creep:
- **8.2 (this):** one endpoint, one identity, HTTP transport works locally. Still `.env`-driven single AGENT token.
- **8.3:** per-person endpoint paths (`/mcp/<random-slug>`), each bound to a different AGENT token.
- **8.4:** VPS deploy — nginx/TLS on a subdomain, systemd, rate limiting, Anthropic IP allowlist.

Do not build 8.3's multi-tenant routing or 8.4's rate limiting here. Build the single-endpoint HTTP server such that 8.3 can add routing without a rewrite (see Task 3).

## Acceptance Criteria

1. **Streamable HTTP transport replaces stdio:** `src/mcp-server.js` (or its successor) serves MCP over `StreamableHTTPServerTransport` on a configurable port/host, and `npm run mcp` starts it. `StdioServerTransport` is no longer the server's transport.
2. **All 7 existing tools still work over HTTP, unchanged in behavior:** `solid_read_resource`, `solid_write_resource`, `solid_list_container`, `solid_get_permissions`, `solid_grant_access`, `solid_revoke_access`, `solid_set_public_access` are all reachable and produce the same results as before. Their `inputSchema` shapes, `scope` wiring, and the destructive `annotations` on the three permission-writing tools (brief §4.4) are carried over verbatim — do not redesign the tool layer in this story.
3. **Verified with a real MCP client, not just a curl:** an actual MCP client handshake (`initialize` → `tools/list` → at least one `tools/call`) completes against the running HTTP server. A raw `curl` that returns *some* JSON is insufficient — the point is protocol-level compatibility, the same "don't trust it until an independent client confirms it" discipline Stories 7.3/8.1 used.
4. **Session model chosen deliberately and documented:** stateless (`sessionIdGenerator: undefined`) vs stateful (`() => randomUUID()`) is an explicit decision recorded in Dev Notes with its reason, not a copy-paste default. Whichever is chosen, concurrent requests must not interleave state incorrectly (see Dev Notes "Concurrency trap").
5. **The Solid session is created once, not per request:** `getAgentSession()` runs at startup with `keepAlive: true` and is reused for the process lifetime. A login per HTTP request would be a real regression (latency + needless token churn against CSS). If the Solid login fails at boot, the process exits with a clear error rather than serving a broken endpoint. **Prerequisite:** `.env` must actually load — `auth.js:21` calls bare `require("dotenv").config()`, which resolves `.env` relative to `process.cwd()`, so `npm run mcp` from another directory (or this sandbox, where `cwd` is `/`) silently finds no credentials and trips AC5's fail-fast for the wrong reason. Fix it path-explicitly (see Task 1.4).
6. **Routine Solid errors degrade gracefully, not as stack traces:** a tool call that hits 401/403/404/409 from CSS returns an MCP error result with an actionable message (e.g. "no write access to that container"), not a leaked stack trace. Brief §5 T5 names these as routine cases, and 8.1's `_saveAclOrThrowControlError` already established the pattern for 403 — extend that discipline to the tool-response layer. **Two non-HTTP failure modes 8.1 proved are the normal case, not edge cases — both must be handled or `solid_get_permissions` ships broken:**
   - `listAgentsWithAccess`/`getAgentAccess` **return `null`, they do not throw**, whenever AGENT lacks `acl:Control` on the target — which is every data-pod container. Surface this as "reading permissions requires Control access on this resource; this agent has read/write only", not as an empty/valid-looking result.
   - `getAgentAccess` **501s on non-RDF files** (CSS can't content-negotiate `text/plain` → `text/turtle` on the resource fetch). Surface as "permissions can only be read for RDF resources or containers."
7. **`express` declared as a direct dependency:** it currently resolves only as a transitive dep of `@modelcontextprotocol/sdk`. Add it to `mcp-connector/package.json` explicitly — relying on a hoisted transitive dep silently breaks on the next SDK bump.
8. **No credential or secret reaches the logs:** startup may log the authenticated WebID (already does), but never the client id/secret, and request logging must not dump `Authorization` headers or full request bodies containing tokens.
9. **README updated:** the "Use as an MCP server" section documents the HTTP invocation, port/host config, and the local-verification command from AC3 — replacing the stdio instructions.

## Tasks / Subtasks

- [ ] Task 1: Swap the transport (AC: #1, #5, #7)
  - [ ] 1.1 Add `express` to `package.json` dependencies (pin the major already in the lock: `^5.2.1`). Keep `@modelcontextprotocol/sdk` on the **1.x** line — do not bump to 2.x (brief §5 T1; 1.x is production-supported for months after v2 and the `registerTool` API changes across the major).
  - [ ] 1.2 Replace `StdioServerTransport` with `StreamableHTTPServerTransport` from `@modelcontextprotocol/sdk/server/streamableHttp.js`. Read `PORT`/`HOST` from env with sane defaults (`127.0.0.1` while local — see Task 4 on why the default matters).
  - [ ] 1.3 Keep the single boot-time `getAgentSession()` (`keepAlive: true`). Fail fast with a clear message if login fails.
  - [ ] 1.4 Make `.env` loading path-explicit so it doesn't depend on `cwd`: either `dotenv.config({ path: path.join(__dirname, "..", ".env") })` in `auth.js`, or `--env-file` in the `mcp` script. **`auth.js` may be edited for this** — the "do not touch" rule below covers `wacManager.js`/`podClient.js` only. Keep the change to config loading; don't restructure the login flow.
- [ ] Task 2: Wire Express and choose the session model (AC: #1, #4)
  - [ ] 2.1 Use `createMcpExpressApp()` from `@modelcontextprotocol/sdk/server/express.js` rather than hand-rolling an Express app — it ships DNS-rebinding protection (see Dev Notes). Note it returns a **bare Express app** with that middleware applied and mounts no routes: you still register `app.post("/mcp", ...)` yourself, confirm whether JSON body-parsing is applied, and pass the parsed body through as `transport.handleRequest(req, res, req.body)`.
  - [ ] 2.2 Decide stateless vs stateful, implement it, and record the decision + reason in Dev Notes. Read the "Concurrency trap" note first — this is the one place a wrong choice produces a bug that only shows up under two simultaneous clients.
  - [ ] 2.3 If stateless: return **405** with a JSON-RPC error for `GET`/`DELETE /mcp` (no SSE stream or session teardown exists to serve), and close the per-request transport on `res.on("close")` so transports don't leak per request.
  - [ ] 2.4 Add a plain `GET /healthz` returning `{ok:true}` — 8.4 needs it for systemd/nginx health checks and it eases AC3 verification. **Do not include the WebID** unless the listener is bound to loopback: this endpoint is unauthenticated and goes public in 8.4, and the agent's WebID is not something to hand out anonymously.
- [ ] Task 3: Keep 8.3's per-person routing cheap (AC: #1)
  - [ ] 3.1 Structure the server so the "build a server instance for identity X" step is a function taking a session, not module-level global wiring. 8.3 then adds a path→token map and calls it per identity; no rewrite. **Do not** implement multi-identity routing itself in this story.
- [ ] Task 4: Error handling and log hygiene (AC: #6, #8)
  - [ ] 4.1 Wrap each tool handler so a thrown Solid/Inrupt error becomes an MCP error result with a human-actionable message, mapping 401/403/404/409 explicitly. Reuse 8.1's documented-error wording where it already exists (`wacManager.js`'s Control-access message) rather than inventing a second phrasing.
  - [ ] 4.2 Confirm no secret, `Authorization` header, or token appears in any log line, including error paths.
- [ ] Task 5: Verify with a real MCP client (AC: #3)
  - [ ] 5.1 Run the server locally, connect an actual MCP client, complete `initialize` → `tools/list` → one read-only `tools/call` (`solid_list_container` or `solid_read_resource` against `hyperscope_ndb/shared/`, where AGENT already has read access from 8.1). Use the SDK's own client — already installed, no new dep: `Client` from `@modelcontextprotocol/sdk/client/index.js` + `StreamableHTTPClientTransport` from `@modelcontextprotocol/sdk/client/streamableHttp.js`. Commit the script as `mcp-connector/scripts/verify-http.js` so 8.5 can re-run it instead of rebuilding it.
    - **Connect via `http://127.0.0.1:<port>/mcp`, not `localhost` or a LAN IP** — with `createMcpExpressApp()` defaults, DNS-rebinding protection rejects a mismatched `Host` header, which looks like a protocol failure and will otherwise burn an hour.
  - [ ] 5.2 Record the transcript/result in Dev Notes. **Do not** exercise the permission-writing tools against the data pod here — 8.1 already proved they correctly fail, and repeating it adds live-pod noise for no new information.
- [ ] Task 6: Docs + Epic 8 convention (AC: #9)
  - [ ] 6.1 Update `mcp-connector/README.md`: HTTP invocation, `PORT`/`HOST`, local verification command. Note that public exposure (TLS, nginx, rate limiting, IP allowlist) is Story 8.4, so nobody deploys this straight to the internet off the back of this story.
  - [ ] 6.2 Per the Epic 8 convention (binding from 8.2 onward, see `epic-8-progress-report.md`): **append** a dated section to `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (read existing content first, write back existing + new — never overwrite), and add a "Story 8.2" section to `epic-8-progress-report.md` with its proof table. If this story does no live pod writes beyond AC3's read, say exactly that in the table rather than padding it.

## Dev Notes

### Verified API surface (checked against the installed SDK, not from memory)

`@modelcontextprotocol/sdk` **1.30.0** is what's in `node_modules`/lock. Both of these exist in the 1.x line — no v2 bump needed:

- `@modelcontextprotocol/sdk/server/streamableHttp.js` → exports **`StreamableHTTPServerTransport`**
  - Constructor options: `sessionIdGenerator`, `onsessioninitialized`, `onsessionclosed`, `enableJsonResponse`, `eventStore`, `allowedHosts`, `allowedOrigins`, `enableDnsRebindingProtection`, `retryInterval`, `keepAliveMs`
  - `handleRequest(req, res, parsedBody?)` — Node `IncomingMessage`/`ServerResponse`; accepts a pre-parsed body, so `express.json()` upstream is fine
- `@modelcontextprotocol/sdk/server/express.js` → exports **`createMcpExpressApp({ host?, allowedHosts? })`**
  - DNS-rebinding protection is auto-enabled **only** when host is `127.0.0.1` / `localhost` / `::1`. Binding `0.0.0.0` silently turns it off — behind nginx on the VPS (8.4) you must pass `allowedHosts` explicitly. Worth wiring the option now even though 8.4 sets its value.

### Concurrency trap — read before doing Task 2.2

The SDK's own examples do this **two different ways**, and copying the wrong one is the likely bug in this story:

- One shared transport + one shared server, `sessionIdGenerator: () => randomUUID()` (stateful).
- A **new** transport + server per request, `sessionIdGenerator: undefined` (stateless).

A single *shared* transport in *stateless* mode is the combination to avoid — it has no session to disambiguate concurrent clients. If you go stateless, build the transport and server per request; the cost is re-registering 7 tool definitions per call, which is trivial. **The Solid session must still be the boot-time singleton either way** (AC5) — per-request MCP server, process-lifetime Solid session. Those are different objects with different lifetimes; don't collapse them.

Recommendation: **stateless + per-request transport/server.** Rationale: 8.3 gives each person their own endpoint path bound to their own token, so per-request construction is the shape that story wants anyway; and a stateless server survives restart without clients holding dead session IDs. Record the actual choice in Dev Notes per AC4 either way.

### Do not touch

`wacManager.js` and `podClient.js` are live-verified as of 8.1 (commits `a3d1064`, `59465a7`). This story is transport-only. If a bug surfaces in them during AC3 verification, note it — don't silently fix it inside a transport story, and don't re-run 8.1's verification suite here. (`auth.js` is editable, but only for the `.env` path fix in Task 1.4.)

### Explicitly deferred — do not build here

- **Audit journal** (brief §5 T5: log every read/write/permission change with identity, resource, timestamp) — belongs with the VPS deploy hardening in 8.4. Its absence in this story is intentional, not an oversight.
- **Rate limiting** (T5), **TLS/nginx/systemd** (T4), **Anthropic IP allowlist** (T4) — all 8.4.
- **Per-person endpoints / multi-identity routing** (T3) — 8.3. Task 3.1 only makes room for it.

### Invalidated Assumptions

- **Assumption:** T2 (per-request identity via connector "Request headers") is available, so the server can be multi-tenant without secret URLs. → **Reality:** verified absent 2026-07-30 on this Claude Pro account — *Add custom connector* exposes only `Name`, `Remote MCP server URL`, and OAuth client id/secret. **T3 (per-person endpoint paths) is the retained path, not a fallback.** Do not design 8.2 around header-injected identity.
- **Assumption:** the brief's "convert to `StreamableHTTPServerTransport` behind Express (or equivalent)" means hand-rolling the Express wiring. → **Reality:** SDK 1.30.0 ships `createMcpExpressApp()` with DNS-rebinding protection built in. Use it; hand-rolling loses that protection silently.
- **Assumption:** `express` is already a project dependency because it resolves at runtime. → **Reality:** it's only a transitive dep of `@modelcontextprotocol/sdk` (which depends on `express@^5.2.1`). It works today purely by hoisting. Declare it (AC7).
- **Assumption:** `wacManager.js`'s `_getEditableAcl` Control check is what stops an agent escalating on a data pod. → **Reality:** 8.1 found `hasAccessibleAcl`/`hasFallbackAcl` are *discoverability* heuristics, not Control checks — the real enforcement is CSS's 403 on the `saveAclFor` PUT, normalized by `_saveAclOrThrowControlError`. Relevant here only so AC6's error mapping doesn't "helpfully" swallow that 403.
- **Assumption:** `npm run mcp` output/logging is unobserved plumbing. → **Reality:** stdio transport used stdout as the protocol channel; over HTTP, stdout is free for logging again. Logging that would have corrupted the stdio protocol is now safe — but AC8's secret-hygiene rule applies to it.

### Environment quirk (carried from 8.1, will otherwise be rediscovered)

This dev sandbox's Bash `$PWD` is not honored by the `node` process — `process.cwd()` reports `/` regardless of a preceding `cd`. Invoke scripts with absolute paths and `node --env-file=<abs>/.env <abs>/script.js`. Not a project bug; noted so it doesn't burn time again.

### Project Structure Notes

- All work in `mcp-connector/` (new-ish top-level dir, no shared runtime with `backoffice/` or `pipeline/`). No changes to `infra/` in this story — the systemd unit and nginx vhost are 8.4.
- CommonJS (`require`), matching every existing file in `src/`. Don't introduce ESM here.
- Existing scripts in `package.json`: `mcp`, `onboard`, `onboard:apply`, `whoami`, `example`. Keep `npm run mcp` as the entry point (AC1) so README/docs elsewhere stay true.
- `.env` is gitignored and holds AGENT credentials only. **OWNER credentials must not enter this environment** (brief §4.1) — this story needs no OWNER access at all.

### References

- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#5-tâches] — T1 (stdio→HTTP, keep SDK 1.x), T2 (header auth unavailable), T3 (per-person endpoints), T4 (VPS deploy), T5 (hardening/rate limiting/error handling)
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#4-contraintes-darchitecture] — §4.1 two-token model, §4.3 agent scope, §4.4 human confirmation on permission writes
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#1-contexte] — sandbox network allowlist proof (`403 host_not_allowed`), why a connector and not a Skill
- [Source: _bmad-output/implementation-artifacts/8-1-wac-hardening-verification.md] — live-verified state of `wacManager.js`/`podClient.js`, the two fixed bugs, `_saveAclOrThrowControlError` error wording, `process.cwd()` sandbox quirk
- [Source: _bmad-output/implementation-artifacts/epic-8-progress-report.md#convention-binding-for-82-onward] — append-only action log + per-story progress table
- [Source: mcp-connector/references/architecture-and-checklist.md#3-session-lifecycle-for-a-long-running-agent] — `keepAlive: true` for a persistent process; §5 routine 403/404/409 handling
- [Source: mcp-connector/src/mcp-server.js] — the 7 registered tools, their schemas and destructive annotations, to be carried over unchanged

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
