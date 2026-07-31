# solid-pod-agent

Connects an AI agent to a Solid Pod: authenticate as the agent's own WebID,
read/write resources, and manage WAC (Web Access Control) permissions.

See `SKILL.md` for the overview and `references/architecture-and-checklist.md`
for the design rationale and things worth deciding before this touches real
Pod data (identity model, WAC vs ACP, backups, notifications, multi-user
scaling, etc.) — read that before deploying.

## Setup

```bash
npm install
cp .env.example .env
# then fill in SOLID_OIDC_ISSUER / SOLID_CLIENT_ID / SOLID_CLIENT_SECRET
```

Getting the client id/secret (Community Solid Server):
1. Create a dedicated account for the agent (its own WebID, not a human's).
2. Go to `<your-css-instance>/.account/`, log in, open **Client credentials**.
3. Name the token, pick the agent's WebID, generate. Copy the `secret` now —
   the server won't show it again.

Then have the Pod owner (Nicolas, or a Singelijn student) grant that WebID
scoped WAC access on the containers the agent should touch.

## Use directly (Node)

```js
const { getAgentSession, closeSession } = require("./src/auth");
const podClient = require("./src/podClient");
const wacManager = require("./src/wacManager");

const session = await getAgentSession();
const notes = await podClient.listContainer("https://pod.example/notes/", session);
await podClient.writeFile("https://pod.example/notes/today.md", "# ...", "text/markdown", session);
const access = await wacManager.listAgentsWithAccess("https://pod.example/notes/", session);
await closeSession(session);
```

Try it end-to-end with `npm run example` (edit `TARGET_CONTAINER` in
`src/example-usage.js` first).

## Use as an MCP server (Streamable HTTP)

```bash
npm run mcp
```

Starts an HTTP server (default `http://127.0.0.1:3939/mcp`) exposing
`solid_read_resource`, `solid_write_resource`, `solid_list_container`,
`solid_get_permissions`, `solid_grant_access`, `solid_revoke_access`, and
`solid_set_public_access` as MCP tools over `StreamableHTTPServerTransport`.
This replaces the earlier stdio transport: stdio only works for a
locally-spawned process, and Claude.ai's remote-connector infra needs to
reach the server at a public URL instead (claude.ai's own code sandbox
cannot reach a Pod directly — `403 host_not_allowed`).

Config via env vars:
- `PORT` — default `3939`. Rejected at startup if not an integer in 1–65535.
- `HOST` — default `127.0.0.1`. Binding `0.0.0.0` (needed behind nginx in a
  VPS deploy) disables the SDK's automatic DNS-rebinding protection for
  localhost — set `ALLOWED_HOSTS` to restore it.
- `ALLOWED_HOSTS` — comma-separated `Host` header allowlist, passed straight
  to the SDK. Unset by default (fine on loopback, where protection is
  automatic). Required when `HOST` is `0.0.0.0`; the VPS deploy story sets
  its value.

The server is stateless: each POST `/mcp` gets its own transport/server
pair, so there's no session ID and no SSE stream. `GET`/`DELETE /mcp` return
`405` accordingly. `GET /healthz` returns `{"ok":true}` for health checks
(deliberately no WebID in the response — this endpoint is unauthenticated).

The Solid login happens once at process startup (`keepAlive: true`) and is
reused for every request — not re-done per call.

Local verification (a real MCP client handshake, not just curl):

```bash
npm run mcp &
node scripts/verify-http.js http://127.0.0.1:3939/mcp
```

This runs `initialize` → `tools/list` → one read-only `tools/call`
(`solid_list_container`) against the running server using the SDK's own
`Client` + `StreamableHTTPClientTransport`. Connect via `127.0.0.1`, not
`localhost` or a LAN IP — the DNS-rebinding protection rejects a mismatched
`Host` header otherwise.

**Public exposure (TLS, nginx, systemd, rate limiting, Anthropic IP
allowlist) is a separate VPS-deploy story — do not point this straight at
the internet off the back of local verification alone.**

## Deploying on a VPS

- Keep `.env` out of git (`.gitignore` it) and restrict its permissions
  (`chmod 600 .env`).
- Production HTTP exposure (nginx/TLS, systemd unit, rate limiting, IP
  allowlisting) is handled in a dedicated deploy story, not covered here.

## Installing as a Claude skill

This folder follows the Claude Skill format (`SKILL.md` + `src/` + `references/`).
If you want Claude itself to have this available in future HyperScope
sessions, it can be saved as a skill directly from here.
