---
name: solid-pod-agent
description: Toolkit for connecting an AI agent (Claude, a Hermes-based harness, or any other agent runtime) to a SOLID Pod — authenticating as a bot/agent identity via client-credentials tokens, reading and writing Pod resources (RDF datasets and files), and inspecting/granting/revoking Web Access Control (WAC) permissions. Use this whenever the task involves HyperScope's Pod migration, connecting an agent to a Solid Pod, generating or using Solid client-credentials tokens, or managing acl:Read/Write/Append/Control permissions on Pod resources.
---

# Solid Pod Agent Toolkit

Gives an AI agent three capabilities on a Solid Pod: **authenticate** as its own bot identity, **read/write** resources, and **read/grant/revoke WAC permissions**. Built for HyperScope's Git+Obsidian → Pods migration, for use either as a Claude skill or lifted into another agent harness (e.g. a Hermes-based agent) running on a VPS.

## Core design decision: the agent has its own WebID

Don't authenticate the agent *as* the user. Give the agent its **own WebID** and grant it scoped WAC access to specific containers.

On Community Solid Server, one account can own several pods, each of which comes with its own WebID — so the agent's identity is just another pod on the same account (`nicolas_claude/` alongside `hyperscope_ndb/`). Isolation lives at the WebID level: a client-credentials token gets exactly what WAC grants that WebID, and cannot reach the account API to escalate.

**Two tokens, different jobs:**
- **OWNER token** (`hyperscope_ndb`) — used only by `src/onboarding.js`, run by hand, to create the grants. Never deployed with the agent.
- **AGENT token** (`nicolas_claude`) — what the running agent holds.

The agent cannot grant itself access to the owner's pod: only a WebID already holding `acl:Control` may edit a container's ACL. That constraint is the security property. See `references/architecture-and-checklist.md` §1.

## Files

- `src/auth.js` — creates an authenticated `session` from a client-credentials id/secret (CSS-style). All other modules take this `session` as a parameter.
- `src/podClient.js` — CRUD: `readFile`, `writeFile`, `readDataset`, `saveDataset`, `listContainer`, `createContainer`, `deleteResource`.
- `src/wacManager.js` — `grantAccess`, `revokeAccess`, `setPublicAccess`, `listAgentsWithAccess`, `getAgentAccess`. Use `scope: 'both'` on containers so grants cover the container *and* its children.
- `src/onboarding.js` — one-time bootstrap: run as OWNER to grant the agent its scoped access. Dry-run by default, `--apply` to write.
- `src/whoami.js` — run as AGENT to verify its real effective access, including that it's correctly *denied* where it should be.
- `src/mcp-server.js` — optional: exposes all of the above as MCP tools over stdio, so *any* MCP-capable agent (Claude, a Hermes harness with an MCP client, etc.) can call them without custom glue code.
- `references/architecture-and-checklist.md` — the "stuff you haven't thought of yet": identity model, security checklist, ACP vs WAC, notifications, versioning, multi-user (Singelijn) scaling.

## Workflow

1. **Generate credentials** for the agent's WebID (via the Pod provider's account page or API — see reference doc). Put `id`, `secret`, and `oidcIssuer` in `.env` (copy `.env.example`).
2. **Authenticate**: `const session = await getAgentSession();` from `src/auth.js`.
3. **Read/write**: use `podClient.js` functions, passing `session.fetch` where required.
4. **Inspect/manage permissions**: use `wacManager.js`. Before the agent *writes* a permission change (as opposed to just reporting current permissions), surface the proposed change to the human and get explicit confirmation — granting `acl:Control` or broad access is high-stakes and shouldn't happen silently.
5. **If wiring into a non-Claude harness** (e.g. Hermes): either import `src/*.js` directly as functions, or run `src/mcp-server.js` and connect to it as an MCP server if the harness speaks MCP.

Read `references/architecture-and-checklist.md` before deploying this for real Pod data — it covers things that are easy to miss (ACP vs WAC detection, DPoP/session lifecycle for long-running processes, rate limits, backups, notifications instead of polling, and how this should scale across Singelijn's multiple student Pods).
