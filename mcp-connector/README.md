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
`solid_read_resource`, `solid_write_resource`, `solid_append_resource`,
`solid_delete_resource`, `solid_list_container`, `solid_get_permissions`,
`solid_grant_access`, `solid_revoke_access`, and `solid_set_public_access`
as MCP tools over `StreamableHTTPServerTransport`.
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

Split below by [Divio](https://docs.divio.com/documentation-system/) quadrant:
**Reference** (facts to look up), **How-to** (steps for a known task), and
**Explanation** (why it's built this way). Don't mix them back together when
editing — a fact and its rationale can live in different sections and link
to each other instead.

### Reference

Env vars (`mcp-connector/.env`, never committed):

| Var | Default | Notes |
|---|---|---|
| `PORT` | `3939` | Rejected at startup if not an integer in 1–65535. |
| `HOST` | `127.0.0.1` | `0.0.0.0` in the VPS container; disables the SDK's automatic DNS-rebinding protection. |
| `ALLOWED_HOSTS` | unset | Required once `HOST=0.0.0.0`. Live value: `solid-mcp.nicolasdb.eu,mcp-connector:3939,mcp-connector` — public hostname **first**, the compose healthcheck reads element 0. |
| `AUDIT_LOG_PATH` | `/app/audit/journal.jsonl` | Inside the container, on the `mcp-audit` named volume. |
| `AUDIT_LOG_MAX_BYTES` | `10485760` (10 MiB) | Active file rotates to a single `.1` backup past this size. |

File/volume/path facts:
- `identities.json` — server-authored on the VPS (excluded from `make
  vps-push`'s rsync, never round-trips through the repo), one entry per
  person (`clientId`, `clientSecret`, `webId`, `label`), must be owned by
  uid 1000.
- `mcp-audit` — named Docker volume, not a bind-mount (a bind-mount under
  the repo path would be deleted by `rsync --delete-after`). Journal line
  shape: `{ts, label, tool, resource, outcome}` — never a slug, client id,
  secret, or token.
- nginx vhost: `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf` — **separate
  repo**, not `pocpod0/infra/` (which has no nginx content at all). TLS on
  `solid-mcp.nicolasdb.eu`, `access_log off`, `limit_req`, IP allowlist.
- Allowlist: Anthropic outbound `160.79.104.0/21` (not the `/23` inbound
  range), `127.0.0.1`, `172.16.0.0/12` (Docker bridge), this host's own
  public IP. Everything else: `deny all` → 403.

### How-to

**Deploy a code change:**
```bash
make vps-push      # pocpod0 repo: syncs mcp-connector/, guards identities.json + node_modules
make vps-deploy    # rebuilds + restarts mcp-connector via docker compose
```
nginx/TLS changes are a **separate** repo and deploy: `hetzner-gateway`'s
own `make vps-deploy` (rsync + `nginx -t` + restart).

**Add / rotate / remove a person:** see "Per-person endpoints" above —
mint client credentials against their own Solid account, generate a slug
(`npm run slug`), edit `identities.json` on the VPS directly (it's
server-authored, not pushed from a checkout), restart.

**Connect an on-host client (Hermes, or any MCP client on the same
Docker daemon) — use the internal path, not the public URL:**
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

### Explanation

- **Docker compose, not systemd.** The brief assumed a systemd unit; the
  VPS has no host `node`/`npm`, every other service on the box is already a
  container, and nginx already routes to containers by name over the
  `gateway` network. A systemd unit would mean installing and maintaining a
  host Node toolchain for one process — decided against with Nicolas
  2026-07-31, recorded as a deliberate brief deviation.
- **The IP allowlist is nginx-level, not a UFW firewall rule.** UFW opens
  443 for the whole host, shared with `pod.nicolasdb.eu` and four other
  vhosts — restricting it there would take all of them down. Per-`server`-
  block in nginx is the only layer that can restrict just this vhost.
- **The internal path bypasses nginx entirely, on purpose.** Hermes and any
  other on-host container reach `mcp-connector:3939` directly over the
  `gateway` Docker network — no TLS termination, no allowlist entry needed
  per client, and critically, **no slug ever reaches an access log**,
  since nginx is never in the request path. This is why AC6 required
  proving the internal path live, not just asserting the network exists.
- **`entrypoint.sh` + `gosu`, not a one-off `chown`.** Docker creates a
  fresh named volume root-owned by default, which EACCES's every audit-
  journal write from the non-root `node` user the container runs as. A
  manual `chown` fixes it once; `entrypoint.sh` (`chown -R node:node
  /app/audit` as root, then `exec gosu node "$@"`) fixes it on *every* boot,
  so the volume self-heals after any future recreate instead of silently
  breaking again.

## Installing as a Claude skill

This folder follows the Claude Skill format (`SKILL.md` + `src/` + `references/`).
If you want Claude itself to have this available in future HyperScope
sessions, it can be saved as a skill directly from here.
