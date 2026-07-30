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

## Use as an MCP server (for Hermes or any MCP-capable harness)

```bash
npm run mcp
```

Exposes `solid_read_resource`, `solid_write_resource`, `solid_list_container`,
`solid_get_permissions`, `solid_grant_access`, `solid_revoke_access` as MCP
tools over stdio. Point your agent harness's MCP client at this process.

## Deploying on a VPS

- Run as a systemd service (or alongside the Hermes harness process) so
  `keepAlive` session refresh works continuously; use `keepAlive: false` in
  `auth.js` if you're instead invoking this as a short-lived job.
- Keep `.env` out of git (`.gitignore` it) and restrict its permissions
  (`chmod 600 .env`).
- If the VPS also hosts the Community Solid Server instance itself, this
  package can run as a separate process alongside it — no special
  networking needed beyond reaching its own `SOLID_OIDC_ISSUER` URL.

## Installing as a Claude skill

This folder follows the Claude Skill format (`SKILL.md` + `src/` + `references/`).
If you want Claude itself to have this available in future HyperScope
sessions, it can be saved as a skill directly from here.
