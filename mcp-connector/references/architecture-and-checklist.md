# Architecture & checklist

## 1. Identity model: one account, one pod per identity

**The chosen setup** (confirmed working on `pod.nicolasdb.eu`): a single CSS
account owns several pods, each of which comes with its own WebID:

| Pod | WebID | Role |
|---|---|---|
| `hyperscope_ndb/` | `.../hyperscope_ndb/profile/card#me` | the data (owner) |
| `nicolas_claude/` | `.../nicolas_claude/profile/card#me` | the agent |
| `nicolas/` | `.../nicolas/profile/card#me` | personal |

This is a good model, and better than the separate-account approach in
practical terms: one account page to manage and revoke everything from, no
second email/password to look after, and — the part that matters — **the
isolation you actually care about is at the WebID level, not the account
level**.

Why the same-account sharing is not a security problem: a client-credentials
token authenticates at the *resource* layer as one specific WebID, and gets
exactly what WAC grants that WebID. The *account management* API
(`/.account/`, where new tokens are minted) authenticates separately, with
the account's email/password and a `CSS-Account-Token`. So holding the
agent's `id`/`secret` does **not** let the holder reach the account API,
enumerate the other pods, or mint a token for `hyperscope_ndb`. A leaked
agent secret buys the attacker the agent's granted access and nothing more —
the same blast radius as a separate account would have given.

The one genuine consequence of "each pod comes with its own WebID": CSS gives
that WebID **full control over its own pod** at creation. So the agent has
`acl:Control` on `nicolas_claude/` by construction — it can restructure or
even publish *its own* pod. That's fine (it's the agent's workspace, and a
good place for its audit log and cached state), but it means the accurate
statement is "the agent can only do what I granted it *outside its own pod*."
Don't put anything in `nicolas_claude/` you'd be unhappy for the agent to
change.

### The two-token model

Because of how WAC works, this is not optional:

- **OWNER token** — tied to `hyperscope_ndb`. Used *only* by
  `src/onboarding.js`, run by hand, to create the grants. Then it goes back in
  the password manager. **Never deployed with the agent.**
- **AGENT token** — tied to `nicolas_claude`. What the running agent holds.

The agent cannot grant itself access to `hyperscope_ndb`, because only a WebID
that already holds `acl:Control` on a container may edit that container's ACL.
So the bootstrap must be performed by the owner identity. That constraint is
the security property — don't engineer around it by giving the agent Control.

### Cross-pod WAC works exactly as normal

Two WebIDs on the same server and same account are still just two WebIDs to
WAC — granting `nicolas_claude` access to a container in `hyperscope_ndb` is
identical to granting a WebID from a completely different provider. Nothing
special is needed. Two practical notes:

- To let the agent write *into* a container it needs `write` (or `append` for
  add-only) on the **container**, plus `read` to list it.
- Use `scope: 'both'` when granting on a container, so the grant covers the
  container *and* its children (WAC `acl:default` inheritance). `scope:
  'resource'` alone would let the agent list the folder but not touch what's
  inside it.

## 2. WAC vs ACP — check which one the Pod actually uses

Solid supports two access-control systems: **WAC** (what you asked about —
`.acl` resources with `acl:Authorization` statements) and the newer **ACP**
(Access Control Policies, used by some hosted providers like Inrupt
PodSpaces). They have different APIs. `wacManager.js` in this toolkit uses
the WAC-specific functions from `@inrupt/solid-client`, which are the
mature, well-tested path.

There's also a "universal access" API (`@inrupt/solid-client/universal`)
that's supposed to auto-detect and handle both — but as of 2026 it has open
bugs specifically against WAC servers when a resource doesn't have an `.acl`
yet (throws instead of initialising one). If you're self-hosting **Community
Solid Server**, you're on WAC by default and `wacManager.js` will work as
written. If a Pod turns out to use ACP, you'll need the ACP-specific API
(`docs.inrupt.com/guides/access-control-policies`) instead — check the
`Link: rel="acl"` header on a resource, or just ask the provider.

## 3. Session lifecycle for a long-running agent

`Session` from `@inrupt/solid-client-authn-node` refreshes its access token
automatically in the background (`keepAlive: true`, the default) — fine for
a persistent process (e.g. the MCP server, or a daemon on your VPS). If the
agent instead runs as a short cron job or serverless call, pass
`keepAlive: false` and just log in fresh each invocation; don't try to
persist the DPoP keypair across processes.

## 4. Confirm before the agent writes permission changes

`grantAccess` / `revokeAccess` / `setPublicAccess` are one function call away
from over-sharing a container. Treat these the way you'd treat any
send/modify/delete action: the agent should propose the change ("grant
`agent-x` read+write on `/notes/`?") and get human confirmation before
calling it — especially anywhere near `acl:Control` or public access. This
toolkit doesn't build in a confirmation gate itself since that belongs in
whatever harness calls it (Claude already does this by convention; wire the
same expectation into a Hermes-based agent).

## 5. Rate limits, quotas, and error handling

Self-hosted CSS on a modest VPS has no built-in rate limiting by default,
but the VPS itself does (disk I/O, memory). If Singelijn scales to many
students' Pods on the same instance, watch disk quota per Pod and general
server load. Wrap every Pod call in try/catch — a 403 (no permission), 404
(resource/container doesn't exist yet), or 409 (conflict) are all routine,
not exceptional, and the agent should handle them gracefully rather than
crashing.

## 6. Don't poll — subscribe to notifications

If the agent needs to react to changes in a Pod (e.g. new student notes
appearing) rather than just being invoked on demand, CSS implements the
**Solid Notifications protocol** (WebSockets/WebSub) so you can subscribe to
a container and get pushed updates instead of polling on a timer. Relevant
once the agent moves from "assist on request" to "watch and react."
See: `communitysolidserver.github.io/CommunitySolidServer/7.x/usage/notifications/`.

## 7. Pods don't version — plan backups separately

Unlike Git, a Solid Pod resource is simply overwritten on `PUT`; there's no
built-in history. During the Git+Obsidian → Pods migration this is a real
gap versus what you have now. Options: periodic export/snapshot of key
containers into the existing Git repo, or a lightweight audit log resource
the agent appends to before overwriting anything important. Worth deciding
before Pods hold anything you'd regret losing.

## 8. Audit trail (ties to "walking the talk")

Since HyperScope's own principle is that tools must prove themselves
internally first, consider having the agent log every read/write/permission
change it makes (to a dedicated Pod container, or locally) — both so you can
verify the agent behaves as intended, and so this becomes the reference
implementation of transparency you'd want Singelijn (and later partners) to
adopt too.

## 9. Multi-user scaling (Singelijn)

The pod-per-identity pattern extends cleanly: each student account owns their
own pod/WebID, and grants `nicolas_claude` (or a per-school agent WebID)
scoped access on specific containers. Revoking one student is one ACL edit on
their pod and touches nobody else.

The decision to revisit later: **one agent WebID across all student pods**
(simple, one credential to rotate, but one leaked secret exposes every
container granted to it) vs **an agent WebID per student** (stronger isolation,
more provisioning and rotation to automate). Start with the former while
Singelijn is a living lab; the switch point is when the agent holds access to
enough student data that a single secret becomes an unacceptable concentration.


## 10. Where "Hermes harness" fits in

This toolkit is deliberately harness-agnostic: `src/*.js` are plain
functions you can import directly, and `src/mcp-server.js` exposes the same
functions as MCP tools for any MCP-capable agent to call without custom
glue. If the Hermes-based agent you're deploying speaks MCP (or you add an
MCP client to it), point it at `node src/mcp-server.js` and it gets read,
write, list, and WAC management as callable tools immediately. If it uses a
different tool-calling convention, the functions in `podClient.js` and
`wacManager.js` are the pieces to wrap.
