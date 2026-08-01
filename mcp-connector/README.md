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

The server is stateless: each POST `/mcp/<slug>` gets its own transport/server
pair, so there's no session ID and no SSE stream. `GET`/`DELETE /mcp/<slug>`
return `405` accordingly. `GET /healthz` returns `{"ok":true}` for health
checks (deliberately no WebID and no identity count — this endpoint is
unauthenticated).

### Per-person endpoints (Story 8.3)

Claude.ai's *Add custom connector* only exposes a URL and OAuth client
id/secret — no way for it to inject per-request identity headers (verified
absent 2026-07-30). So each team member gets **their own URL path** bound to
their own AGENT credential: `POST /mcp/<slug>`, where `<slug>` is a long,
random, unguessable string — never a person's name, never committed, never
pasted into a shared channel.

**The honest trade-off:** part of the protection here is the *secrecy of the
URL* on top of the WAC token. Anyone who obtains a slug can act as that
person until it's rotated. That is why slugs are CSPRNG-generated
(`crypto.randomBytes`, ≥22 URL-safe chars — see `npm run slug`), why the
identities file is gitignored, and why an unknown/malformed slug gets a
generic 404 that reveals nothing (no hint whether it's a near-miss, how many
identities exist, or any WebID).

**Bare `/mcp` (Story 8.2's single shared endpoint) has been removed.** It
would have kept exactly the shared-identity shape this story exists to
eliminate. If you want the old single-identity behavior, configure it as one
entry in `identities.json`.

Config lives in `identities.json` (gitignored) next to `package.json`, keyed
by slug:

```bash
cp identities.example.json identities.json
chmod 600 identities.json
npm run slug   # generate a slug for each person
# then edit identities.json — one entry per person
```

Each entry needs `clientId`, `clientSecret`, `webId`, and `label` (see
"Getting the client id/secret" above — do this once per person, against
*their own* Solid account, never a shared one). All identities log in once
at boot with `keepAlive: true`; if **any** fails, the whole process refuses
to start and names the failing identity's *label* (never its slug or secret)
in the error.

**Adding, removing, or rotating a person** is a config edit + restart:
- *Add*: mint a client-credentials token for their WebID, generate a slug
  (`npm run slug`), add an entry, restart.
- *Remove*: delete their entry, restart.
- *Rotate (a slug leaked)*: generate a new slug, move the same
  `clientId`/`clientSecret`/`webId`/`label` under it, delete the old entry,
  restart, and tell the person their connector URL changed.

Startup logs one line per identity with the authenticated WebID — never a
slug, client id, or secret. Grep a boot log to confirm this yourself,
including on a forced-failure path (e.g. a deliberately wrong secret).

The Solid login for every configured identity happens once at process
startup (`keepAlive: true`) and is reused for every request to that
identity's slug — not re-done per call.

Local verification (a real MCP client handshake, not just curl):

```bash
npm run mcp &
node scripts/verify-http.js http://127.0.0.1:3939/mcp/<a-configured-slug>
```

This runs `initialize` → `tools/list` → one read-only `tools/call`
(`solid_list_container`) against the running server using the SDK's own
`Client` + `StreamableHTTPClientTransport`. Connect via `127.0.0.1`, not
`localhost` or a LAN IP — the DNS-rebinding protection rejects a mismatched
`Host` header otherwise.

To prove isolation between two identities (not just assert it), configure
two slugs and run:

```bash
node scripts/verify-isolation.js <slugA> <slugB> <a-resource-url-only-B-can-read>
```

This has A read its own resources, has B write+read a private resource, then
confirms A is **denied** on that same resource with 8.2's actionable error
text (not a stack trace) while still reaching its own resources fine.

**Public exposure (TLS, nginx, systemd, rate limiting, Anthropic IP
allowlist, audit journal) is a separate VPS-deploy story (8.4) — do not
point this straight at the internet off the back of local verification
alone.** Note for that story: slugs live in the URL path, so nginx/systemd
access logs will capture them by default — that turns a routine access log
into a credential store, so 8.4 needs deliberate log filtering.

## Deploying on a VPS

- Keep `.env` out of git (`.gitignore` it) and restrict its permissions
  (`chmod 600 .env`). Same for `identities.json`, which holds one set of
  client credentials per person.
- `identities.json` is **server-authored**: it is excluded from `make
  vps-push`'s rsync, so it is written directly on the VPS and never
  round-trips through the repo. It must be owned by uid 1000 (`chown
  1000:1000`) — the container runs as the non-root `node` user and a
  root-owned `600` file gives it `EACCES` on boot.
- Public exposure lives in the `hetzner-gateway` repo
  (`nginx/conf.d/11-solid-mcp.conf`): TLS on `solid-mcp.nicolasdb.eu`,
  `access_log off` (the slug in the URL path is a bearer credential),
  `limit_req`, and an IP allowlist restricted to Anthropic's outbound range
  plus this host. Everything else gets a 403.
- **Audit journal** (`src/journal.js`): append-only JSONL at
  `/app/audit/journal.jsonl` inside the container, one line per tool call
  (`ts`, `label`, `tool`, `resource`, `outcome` — never the slug, client id,
  secret or token). Backed by the `mcp-audit` named Docker volume, not a
  bind-mount under the repo path (`rsync --delete-after` would delete it).
  Bounded at 10 MiB active + one rotated `.1` backup (`AUDIT_LOG_MAX_BYTES`
  env var to override). **Docker creates a fresh named volume root-owned**,
  which EACCES's every write from the non-root `node` user the container
  runs as — `entrypoint.sh` fixes this on every boot (`chown -R node:node
  /app/audit` as root, then drops to `node` via `gosu` before exec'ing the
  app), so it self-heals rather than needing a manual chown after a volume
  is recreated.

### Connecting another client on the same host (Hermes, or any MCP client)

On-host clients should **not** go through the public URL. Add the
`gateway` network to the client's compose service and point it at the
internal address:

```yaml
services:
  hermes:
    networks: [default, gateway]

networks:
  gateway:
    external: true
```

```
http://mcp-connector:3939/mcp/<slug>
```

This is preferred over `https://solid-mcp.nicolasdb.eu/mcp/<slug>` for
anything running on this host, because it skips TLS termination and the
nginx hop entirely, is not subject to the IP allowlist (which would
otherwise have to grow an entry per client), and — most importantly —
**puts no slug into any access log**, since nginx is never involved.

One catch: the MCP SDK's DNS-rebinding protection validates the `Host`
header, so the internal hostname has to be listed too. `MCP_ALLOWED_HOSTS`
is therefore `solid-mcp.nicolasdb.eu,mcp-connector:3939,mcp-connector`.
Keep the public hostname **first** — the compose healthcheck reads
`ALLOWED_HOSTS.split(',')[0]`. Without the internal entries the handshake
fails with `Invalid Host: mcp-connector`, not with a connection error,
which is easy to misread as a routing problem.

## Installing as a Claude skill

This folder follows the Claude Skill format (`SKILL.md` + `src/` + `references/`).
If you want Claude itself to have this available in future HyperScope
sessions, it can be saved as a skill directly from here.
