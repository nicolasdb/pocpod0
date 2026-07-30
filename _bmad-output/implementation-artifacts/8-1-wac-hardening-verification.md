# Story 8.1: WAC Manager — Live Verification & Hardening

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the **MCP connector's runtime (AGENT identity)**,
I want `wacManager.js`'s grant/revoke/read functions to be proven correct against the real `pod.nicolasdb.eu` CSS instance, using only the AGENT credential — never the OWNER credential,
so that the connector never silently writes an ineffective `.acl` (a grant that looks successful but CSS doesn't actually honor, the failure class Story 7.3 found in the backoffice), **and** the dev/verification environment never has to hold the one credential capable of granting itself arbitrary access.

## Context / Why now

`MISSION_BRIEF_solid-mcp-connector.md` (Quest B handoff, 2026-07-30) ships a Node.js MCP toolkit (`mcp-connector/`, unzipped from `solid-pod-agent.zip`) including `src/wacManager.js`. Its own header comment already rejects `@inrupt/solid-client`'s auto-detecting `universalAccess` API in favor of WAC-specific low-level calls (`createAcl`, `setAgentResourceAccess`, `setAgentDefaultAccess`, `saveAclFor`) — correctly citing that the universal API is unreliable against WAC servers. Its inline comments also already document three of the exact pitfalls independently discovered in Story 7.3/backoffice work: orphaned ACLs (no owner `control:true` in a fresh ACL write), `getAgentAccessAll` requiring the resource-with-ACL rather than an extracted ACL dataset, and `createAclFromFallbackAcl` already returning a full ACL dataset (don't re-wrap it). So this is **not** the same starting point as pre-fix `backoffice/pod-api.js`, which called `universalAccess` directly.

However: **7/7 assertions in the brief are offline-only** — `wacManager.js` has never made a real network call.

**Correction from the original draft of this story (2026-07-30):** the first version of this story assumed OWNER credentials would be available in this dev/verification environment (Task 1.1: "obtain OWNER and AGENT tokens"). Nicolas flagged this correctly — it re-creates exactly the risk the two-token model (brief §4.1) exists to prevent. The fix isn't a workaround, it's recognizing what the security property actually implies for *this* story's scope:

- **AGENT can never legitimately call `grantAccess`/`revokeAccess`/`setPublicAccess`/fresh-ACL-creation on a data pod container**, because `_getEditableAcl` requires `acl:Control`, and AGENT never holds Control on a data pod (brief §4.3 — this is enforced by `wacManager.js` itself: `_getEditableAcl` throws `"...does not have Control access..."` when it's missing). So AC1-3 of the original draft (grant/revoke round-trip, orphan-ACL check) **cannot be meaningfully verified by AGENT against a data pod** — attempting to would either require handing AGENT `acl:Control` (violates §4.3) or require OWNER credentials in this environment (violates what Nicolas is asking for now). Neither is acceptable.
- What CAN be verified with AGENT-only credentials:
  - **Read/write pod content** (`podClient.js`) and **read WAC state** (`listAgentsWithAccess`/`getAgentAccess`) on whatever containers Nicolas has *already granted* AGENT access to via WAC, using his own identity, outside this session/environment (backoffice UI or direct `.acl` edit — his call, not this story's concern).
  - **Grant/revoke/fresh-ACL-creation**, live, against **AGENT's own workspace pod** (`nicolas_claude/`), where AGENT holds `acl:Control` by CSS construction at pod creation (brief §4.3 note) — no OWNER token needed, this is AGENT managing its own space.
  - **The negative case**: AGENT attempting `grantAccess`/`revokeAccess` on a data-pod container it does *not* control must fail with the documented error, not a confusing stack trace — this is a first-class verification target now, not an afterthought, because it's the live proof that the two-token model actually holds under real network conditions and not just in code review.

This story is the gate before any of 8.2-8.6: verify first, harden only where verification finds a real gap, and only fall back to porting Story 7.3's hand-rolled `.acl` Turtle writer (`backoffice/pod-api.js`, `_writeAcl()` ~line 241-338) if Inrupt's own writer reproduces a bug live — scoped to whichever of AGENT's-own-pod or read-only-on-granted-containers actually exercises the affected code path.

## Prerequisite (Nicolas, outside this story/session)

Confirmed 2026-07-30 (account screenshots): single CSS account on `pod.nicolasdb.eu` with three pods —
- **OWNER/data pod:** `https://pod.nicolasdb.eu/hyperscope_ndb/` — WebID `https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me` — this story's target, real test data already lives here, Nicolas confirms it's safe to use.
- **AGENT/workspace pod:** `https://pod.nicolasdb.eu/nicolas_claude/` — WebID `https://pod.nicolasdb.eu/nicolas_claude/profile/card#me` — used for Task 3's grant/revoke/orphan-ACL checks (AGENT holds Control here by construction).
- `https://pod.nicolasdb.eu/nicolas/` — unrelated to this story.

Before Task 2/3 can run, Nicolas grants AGENT (`nicolas_claude`) read+write on **at least one container inside `hyperscope_ndb/`** via WAC himself (backoffice sharing UI or direct `.acl` edit), using `scope:'both'` semantics. He then shares:
- an AGENT client-credentials token, minted for the `nicolas_claude` WebID (`.env`, gitignored, never committed) — the account screen (`/.account/account/.../client-credentials/`) lets him pick which of his three WebIDs a token is bound to; pick `nicolas_claude`, not `hyperscope_ndb`, and
- the URL of the container granted inside `hyperscope_ndb/`, so the story's read/write checks have a real target.

OWNER credentials (a token bound to the `hyperscope_ndb` WebID) are not requested, not needed, and must not be entered into this environment at any point in this story.

## Acceptance Criteria

1. **Content read/write on a Nicolas-granted container:** using only the AGENT credential, `podClient.js` reads and writes a resource inside the container Nicolas pre-granted, and the write is independently confirmed (re-`GET` shows the new content) — proves the connector's basic CRUD path works against the real pod at all, since it's never made a network call before.
2. **WAC read reflects true state on a Nicolas-granted container:** `listAgentsWithAccess`/`getAgentAccess` on that container (and, if it has children with no ACL of their own, on a child too) correctly report AGENT's actual granted access, including inherited (`default`-scope) access rather than reporting "no access" for a resource that only has a container-level grant — mirrors Story 7.3 AC5's inheritance truth-telling requirement.
3. **Grant/revoke/orphan-ACL round-trip on AGENT's own workspace pod:** against `nicolas_claude/` (or a throwaway subcontainer inside it), `grantAccess(...,{scope:'both'})` → independent out-of-app request (anonymous or second-WebID `fetch`) confirms the grant is honored on a *child* resource, not just the container listing (the exact bug Story 7.3 found) → `revokeAccess` → the same request now fails. A fresh-ACL-creation path (resource with no existing ACL/fallback inside the workspace pod) always leaves AGENT's own `control:true` intact after the write (no self-orphaning).
4. **Negative case — the security property holds live, not just in code:** AGENT calling `grantAccess`/`revokeAccess`/`setPublicAccess` on the data-pod container from AC1/2 (where it has read/write but not Control) fails with `_getEditableAcl`'s documented error message, not a stack trace or a silent no-op — proves live that AGENT genuinely cannot escalate its own access on a data pod.
5. **Verification method matches Story 7.3's, not a weaker one:** every claim above is checked with an independent, out-of-app HTTP request (anonymous `fetch` for public grants, a second real WebID session for agent grants) where applicable — an in-app "the call didn't throw" or "AGENT's own re-read looks right" check is insufficient, since the whole point is catching a case where the app's own view of its write diverges from what CSS actually enforces.
6. **Decision recorded:** if AC1-4 all pass clean with the Inrupt WAC-specific calls as-is, this story closes with `wacManager.js`/`podClient.js` unchanged plus this verification recorded (no speculative rewrite). If any reproduce a Story-7.3-class bug, port the relevant piece of `backoffice/pod-api.js`'s hand-rolled `.acl` Turtle read/write into `wacManager.js`, and re-run the failing AC against the fix.
7. **Cleanup:** any throwaway grants/resources created inside AGENT's own workspace pod during verification are revoked/removed afterward (same discipline as Story 7.3/7.4 — no orphaned test grants left on `pod.nicolasdb.eu`). Nothing is written or removed in the data-pod container beyond what AC1's round-trip test needed.

## Tasks / Subtasks

- [ ] Task 1: Set up live credentials (AC: prerequisite)
  - [ ] 1.1 Receive AGENT (`nicolas_claude`, WebID `https://pod.nicolasdb.eu/nicolas_claude/profile/card#me`) client-credentials token from Nicolas, and the URL(s) of the container(s) he's pre-granted inside `https://pod.nicolasdb.eu/hyperscope_ndb/` via WAC. **Do not request or accept a token bound to the `hyperscope_ndb` WebID (OWNER) in this environment.**
  - [ ] 1.2 Confirm `src/auth.js` login works against real `pod.nicolasdb.eu` for the AGENT identity (this is also first-ever network use of `auth.js` — if it fails, that's this story's finding too, not just `wacManager.js`'s).
- [ ] Task 2: Content + WAC-read verification on the Nicolas-granted container (AC: #1, #2)
  - [ ] 2.1 Read an existing resource, write a new/updated one, re-`GET` to confirm.
  - [ ] 2.2 Verify `listAgentsWithAccess`/`getAgentAccess` report AGENT's true granted access, including inherited access on a child resource with no ACL of its own if one exists.
- [ ] Task 3: Grant/revoke/orphan-ACL verification on AGENT's own workspace pod (AC: #3, #5)
  - [ ] 3.1 In `https://pod.nicolasdb.eu/nicolas_claude/` (or a throwaway subcontainer), grant a second test identity `{read:true,write:true}` with `scope:'both'`; independently confirm (out-of-app request) it can `PUT` a child resource, not just list the container.
  - [ ] 3.2 Revoke; re-confirm the same request now fails.
  - [ ] 3.3 Trigger fresh-ACL-creation (`createAcl`) on a resource in the workspace pod with no existing ACL/fallback; re-`GET` the raw `.acl` and confirm AGENT's own `control:true` is present (no self-orphaning).
- [ ] Task 4: Negative-permission verification on the data-pod container (AC: #4)
  - [ ] 4.1 From the AGENT session, call `grantAccess` (or `setPublicAccess`) on the Nicolas-granted data-pod container from Task 2 (where AGENT has read/write but not Control) — confirm it fails with `_getEditableAcl`'s documented error, not an unhandled exception.
- [ ] Task 5: Decision + (conditional) hardening (AC: #6)
  - [ ] 5.1 If Tasks 2-4 all pass clean: record the verification result in this story's Dev Notes, no code change to `wacManager.js`/`podClient.js`.
  - [ ] 5.2 If any bug reproduces: port the corresponding logic from `backoffice/pod-api.js`'s `_writeAcl()`/`getAccess()` (direct Turtle read/write) into `wacManager.js`, re-run the failing AC, and note the port explicitly (what changed and why) rather than silently replacing working code.
- [ ] Task 6: Cleanup (AC: #7)
  - [ ] 6.1 Revoke all test grants and delete any throwaway resources/containers created inside AGENT's own workspace pod. Confirm the data-pod container from Task 2 is left exactly as Nicolas granted it (no residual writes beyond AC1's content round-trip, no permission changes — Task 4's grant attempt must have failed, so nothing to undo there).

## Dev Notes

- **Reuse target:** `backoffice/pod-api.js` — `_writeAcl()` (~line 241-338, direct `.acl` Turtle emission: `acl:accessTo` on the target itself, `acl:default` on containers, owner block always included) and `getAccess()` (Turtle parser that distinguishes own vs. inherited ACL). Port the *pattern*, not a copy-paste: the MCP server runs `@inrupt/solid-client-authn-node` client-credentials sessions server-side, not a browser DPoP session, so the `fetch` wiring differs even though the Turtle logic transfers directly.
- **Verification harness:** reuse Story 7.3's zero-dependency Node `webcrypto` DPoP client-credentials pattern (no npm deps) for the independent out-of-app checks, rather than building a new one.
- **Non-negotiables carried from the brief (do not relax for convenience):** AGENT must never hold `acl:Control` on a data pod — this story treats that as something to *prove live* (AC4), not just trust from reading the code; grants scoped to containers only, never pod root; **OWNER credentials never enter this environment for this story, full stop** — onboarding (the one place OWNER is used) is Nicolas's own action, out of band, not something this story or its dev/verification tooling performs.
- **Source:** `_bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md` §3 (confirmed/unconfirmed table), §4.1 (two-token model), §4.3 (agent scope), §6 (known pitfalls 1-6), Annex (Inrupt universal-access API warning).

## Change Log

| Date | Change |
|---|---|
| 2026-07-30 | Story drafted from Epic 8 (sprint change proposal 2026-07-30), ready-for-dev. |
| 2026-07-30 | Nicolas: won't share OWNER token — will grant AGENT access to specific folders himself via WAC, only AGENT token gets shared. Story rewritten: AC1-7 restructured so OWNER credentials never enter this environment. Grant/revoke/orphan-ACL checks moved to AGENT's own workspace pod (where it holds Control by construction); content/WAC-read checks target whatever container(s) Nicolas pre-grants; added an explicit negative-permission AC proving live that AGENT cannot escalate on a data pod it doesn't control. Onboarding (OWNER-only) confirmed as Nicolas's own out-of-band action, not part of this story. |
| 2026-07-30 | Pre-verification static fixes to `mcp-connector/src/mcp-server.js` (checked against current MCP TypeScript SDK v1.29.0 docs via Context7, no live pod needed): (1) all six `inputSchema` values were wrapped in `z.object({...})` — the documented v1.x shape is a raw Zod shape (`{ field: z.type() }`), not a `ZodObject`; unwrapped. (2) `solid_grant_access` exposed an `asDefault` boolean that was passed as `{ asDefault }` to `wacManager.grantAccess`, which reads `options.scope` — `asDefault` was silently ignored, so every grant through the tool defaulted to `scope:'resource'` and could never produce a working container share (brief §6 pitfall 5). Replaced with a `scope: 'resource'|'default'|'both'` param actually wired through. (3) Added `annotations: {readOnlyHint:false, destructiveHint:true, idempotentHint:true}` to `solid_grant_access`/`solid_revoke_access` per brief §4.4 (documented as a hint only, not an enforced gate — spec text: "clients should never make tool use decisions based on ToolAnnotations from untrusted servers"). (4) `setPublicAccess` was implemented in `wacManager.js` but never exposed as an MCP tool at all; added `solid_set_public_access` with the same destructive annotation, matching the three tools the brief names as requiring human confirmation. These are wiring/interface bugs caught by re-reading the code against the brief's own DoD and current SDK docs — orthogonal to this story's live-verification ACs (AC1-7), which target `wacManager.js`'s WAC correctness, not the tool-registration layer.
