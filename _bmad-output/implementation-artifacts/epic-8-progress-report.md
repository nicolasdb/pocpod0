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

## Epic 8 — remaining stories

- 8.2 HTTP transport — backlog
- 8.3 Per-person endpoints — backlog
- 8.4 VPS deploy hardening — backlog
- 8.5 Live verification — backlog (depends on 8.1, now unblocked)
- 8.6 Team onboarding doc — backlog
