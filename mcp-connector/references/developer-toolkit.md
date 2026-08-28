# Solid Pod Agent Toolkit — developer reference

Gives an AI agent three capabilities on a Solid Pod: **authenticate** as its own bot identity, **read/write/append/delete** resources, and **read/grant/revoke WAC permissions**. Built for HyperScope's Git+Obsidian → Pods migration, for use either as a Claude skill or lifted into another agent harness (e.g. a Hermes-based agent) running on a VPS.

This is the *developer* document — how the toolkit is built and wired. For the user-facing skill that tells Claude when/where/how to capture into a pod during a conversation, see `../SKILL.md`.

## Core design decision: the agent has its own WebID

Don't authenticate the agent *as* the user. Give the agent its **own WebID** and grant it scoped WAC access to specific containers.

On Community Solid Server, one account can own several pods, each of which comes with its own WebID — so the agent's identity is just another pod on the same account (`nicolas_claude/` alongside `hyperscope_ndb/`). Isolation lives at the WebID level: a client-credentials token gets exactly what WAC grants that WebID, and cannot reach the account API to escalate.

**Two tokens, different jobs:**
- **OWNER token** (`hyperscope_ndb`) — used only by `src/onboarding.js`, run by hand, to create the grants. Never deployed with the agent.
- **AGENT token** (`nicolas_claude`) — what the running agent holds.

The agent cannot grant itself access to the owner's pod: only a WebID already holding `acl:Control` may edit a container's ACL. That constraint is the security property. See `references/architecture-and-checklist.md` §1.

## Files

- `src/auth.js` — creates an authenticated `session` from a client-credentials id/secret (CSS-style). All other modules take this `session` as a parameter.
- `src/podClient.js` — CRUD: `readFile`, `writeFile`, `appendFile`, `readDataset`, `saveDataset`, `listContainer`, `createContainer`, `deleteResource`, `confirmGone`.
- `src/wacManager.js` — `grantAccess`, `revokeAccess`, `setPublicAccess`, `listAgentsWithAccess`, `getAgentAccess`. Use `scope: 'both'` on containers so grants cover the container *and* its children.
- `src/receipt.js` — read receipts (Story 8.6 AC11 / FR42, reshaped by Story 8.9): when the agent reads a resource it doesn't own, POST an entry as its own resource into the *subject's* `access-log/` container. One resource per receipt, because that is what an `acl:Append` grant permits — `appendFile` is a read-then-overwrite and needs Write, which an append-only journal must withhold from its own writer. Voluntary accountability convention, not enforcement — CSS surfaces no per-resource read log to owners.
- `src/onboarding.js` — one-time bootstrap: run as OWNER to grant the agent its scoped access. Dry-run by default, `--apply` to write.
- `src/whoami.js` — run as AGENT to verify its real effective access, including that it's correctly *denied* where it should be.
- `src/mcp-server.js` — exposes all of the above as MCP tools over Streamable HTTP, so *any* MCP-capable agent (Claude, a Hermes harness with an MCP client, etc.) can call them without custom glue code. Ten tools as of Story 8.10: `solid_read_resource`, `solid_write_resource`, `solid_append_resource`, `solid_delete_resource`, `solid_list_container`, `solid_get_permissions`, `solid_grant_access`, `solid_revoke_access`, `solid_set_public_access`, `solid_prepare_upload`. Also mounts `POST /upload/:token` (Story 8.10, outside `/mcp`) — the ticket-redemption route `solid_prepare_upload` hands a URL for.
- `src/uploadTickets.js` — Story 8.10: in-memory ticket store backing the out-of-band upload path. MCP tool args are JSON with no byte channel and no client→server bulk-transfer primitive (verified against the MCP spec), so a file already on disk moves via a one-time ticket instead of being re-emitted as a tool argument: `solid_prepare_upload` issues a token bound to `{targetUrl, identity, contentType, bytes}`, TTL 300s, single-use (atomic delete-then-use), CSPRNG token (same generator class as `scripts/gen-slug.js`). No persistence — a restart drops in-flight tickets, acceptable at a 5-minute window.
- `references/architecture-and-checklist.md` — the "stuff you haven't thought of yet": identity model, security checklist, ACP vs WAC, notifications, versioning, multi-user (Singelijn) scaling.

## Workflow

1. **Generate credentials** for the agent's WebID (via the Pod provider's account page or API — see reference doc). Put `id`, `secret`, and `oidcIssuer` in `.env` (copy `.env.example`).
2. **Authenticate**: `const session = await getAgentSession();` from `src/auth.js`.
3. **Read/write/append**: use `podClient.js` functions, passing `session.fetch` where required. Prefer `appendFile` over `writeFile` when the goal is adding to something, not replacing it — `writeFile` is a blind overwrite.
4. **Inspect/manage permissions**: use `wacManager.js`. Before the agent *writes* a permission change (as opposed to just reporting current permissions), surface the proposed change to the human and get explicit confirmation — granting `acl:Control` or broad access is high-stakes and shouldn't happen silently.
5. **If wiring into a non-Claude harness** (e.g. Hermes): either import `src/*.js` directly as functions, or run `src/mcp-server.js` and connect to it as an MCP server if the harness speaks MCP.

Read `references/architecture-and-checklist.md` before deploying this for real Pod data — it covers things that are easy to miss (ACP vs WAC detection, DPoP/session lifecycle for long-running processes, rate limits, backups, notifications instead of polling, and how this should scale across Singelijn's multiple student Pods).
