# Story 8.1: WAC Manager — Live Verification & Hardening

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the **MCP connector's runtime (AGENT identity)**,
I want `wacManager.js`'s grant/revoke/read functions to be proven correct against the real `pod.nicolasdb.eu` CSS instance — not just offline unit assertions,
so that the connector never silently writes an ineffective `.acl` (a grant that looks successful but CSS doesn't actually honor), which is exactly the failure class Story 7.3 found in the backoffice.

## Context / Why now

`MISSION_BRIEF_solid-mcp-connector.md` (Quest B handoff, 2026-07-30) ships a Node.js MCP toolkit (`mcp-connector/`, unzipped from `solid-pod-agent.zip`) including `src/wacManager.js`. Its own header comment already rejects `@inrupt/solid-client`'s auto-detecting `universalAccess` API in favor of WAC-specific low-level calls (`createAcl`, `setAgentResourceAccess`, `setAgentDefaultAccess`, `saveAclFor`) — correctly citing that the universal API is unreliable against WAC servers. Its inline comments also already document three of the exact pitfalls independently discovered in Story 7.3/backoffice work: orphaned ACLs (no owner `control:true` in a fresh ACL write), `getAgentAccessAll` requiring the resource-with-ACL rather than an extracted ACL dataset, and `createAclFromFallbackAcl` already returning a full ACL dataset (don't re-wrap it). So this is **not** the same starting point as pre-fix `backoffice/pod-api.js`, which called `universalAccess` directly.

However: **7/7 assertions in the brief are offline-only** — `wacManager.js` has never made a real network call. Story 7.3's experience is the reason this matters: its pre-fix code also looked reasonable on read, and the actual defect (missing `acl:default` on container grants, so a "public RW" folder let anon `GET` the container but not `PUT` a child) only surfaced under live, out-of-app verification (`_bmad-output/implementation-artifacts/7-3-my-things-crud-acl-fix.md`, Task 1). Reading Inrupt's WAC-specific functions correctly is not proof they emit the same Turtle CSS's WAC implementation expects in every case (container `acl:default` coverage, `accessTo` targeting a container vs. a specific child resource, CSS's occasional extra `create` mode surfacing as an unexpected 403 — see brief §6, pitfalls 5 and 6).

This story is the gate before any of 8.2-8.6: verify first, harden only where verification finds a real gap, and only fall back to porting Story 7.3's hand-rolled `.acl` Turtle writer (`backoffice/pod-api.js`, `_writeAcl()` ~line 241-338) if Inrupt's own writer reproduces a bug live.

## Acceptance Criteria

1. **Grant round-trips live, container scope included:** using real OWNER and AGENT credentials against `pod.nicolasdb.eu`, `grantAccess(containerUrl, agentWebId, {read:true,write:true}, session, {scope:'both'})` produces an `.acl` that a real out-of-app request obeys — specifically, the agent can `PUT` a *child* resource of the container it was granted access to, not just `GET` the container listing (this is precisely the bug Story 7.3 found; `scope:'both'` is supposed to prevent it by writing both `acl:accessTo` and `acl:default`).
2. **Revoke round-trips live:** after a grant, `revokeAccess` removes exactly that agent's access; a subsequent out-of-app request from that agent's identity on the previously-granted mode fails (401/403). Other agents'/public's existing grants on the same resource are untouched (additive/non-destructive write, per the same standard Story 7.3 verified).
3. **No orphaned ACL:** creating a fresh ACL (resource with no existing `.acl` or fallback) always leaves the OWNER webId with `control:true` in the saved dataset — verified by re-reading the ACL after write and confirming the owner's authorization block, not just trusting the write didn't throw.
4. **`listAgentsWithAccess` / `getAgentAccess` read the true state:** for a resource with a container-level `default` grant and no resource-level ACL of its own, these functions correctly report the effective (inherited) access rather than reporting "no access" — mirrors Story 7.3 AC5's inheritance truth-telling requirement.
5. **Verification method matches Story 7.3's, not a weaker one:** every claim above is checked with an independent, out-of-app HTTP request (anonymous `fetch` for public grants, a second real WebID session for agent grants) — an in-app "the call didn't throw" or "AGENT's own re-read looks right" check is insufficient, since the whole point is catching a case where the app's own view of its write diverges from what CSS actually enforces.
6. **Decision recorded:** if all of AC1-4 pass live with the Inrupt WAC-specific calls as-is, this story closes with `wacManager.js` unchanged plus this verification recorded (no speculative rewrite). If any reproduce a Story-7.3-class bug, port the relevant piece of `backoffice/pod-api.js`'s hand-rolled `.acl` Turtle read/write into `wacManager.js`, and re-run AC1-4 against the fix.
7. **Cleanup:** any throwaway grants/resources created during verification are revoked/removed afterward (same discipline as Story 7.3/7.4 — no orphaned test grants left on `pod.nicolasdb.eu`).

## Tasks / Subtasks

- [ ] Task 1: Set up live credentials (AC: prerequisite)
  - [ ] 1.1 Obtain/confirm OWNER (`hyperscope_ndb`) and AGENT (`nicolas_claude`) client-credentials tokens per the brief's two-token model (§4.1) — OWNER used only for this verification pass, never committed or deployed.
  - [ ] 1.2 Confirm `src/auth.js` login works against real `pod.nicolasdb.eu` for both identities (this is also first-ever network use of `auth.js` — if it fails, that's this story's finding too, not just `wacManager.js`'s).
- [ ] Task 2: Container-scope grant/revoke verification (AC: #1, #2, #5)
  - [ ] 2.1 Reproduce Story 7.3's exact test shape: grant AGENT `{read:true,write:true}` on a throwaway container with `scope:'both'`, then attempt an anonymous or second-identity `PUT` to a child resource — must succeed.
  - [ ] 2.2 Revoke, re-attempt the same child `PUT` — must now fail.
  - [ ] 2.3 Grant a second, unrelated agent on the same container — confirm the first agent's revoked state and the new agent's granted state don't interfere (additive-write check).
- [ ] Task 3: Orphan-ACL and read-accuracy verification (AC: #3, #4)
  - [ ] 3.1 Trigger the fresh-ACL-creation path (`createAcl`) on a resource with no existing ACL/fallback; re-`GET` the raw `.acl` and confirm owner `control:true` is present.
  - [ ] 3.2 Verify `listAgentsWithAccess`/`getAgentAccess` against a resource relying on container-level `default` inheritance (no own ACL) — must report the inherited access, not empty.
- [ ] Task 4: Decision + (conditional) hardening (AC: #6)
  - [ ] 4.1 If Tasks 2-3 all pass clean: record the verification result in this story's Dev Notes, no code change to `wacManager.js`.
  - [ ] 4.2 If any bug reproduces: port the corresponding logic from `backoffice/pod-api.js`'s `_writeAcl()`/`getAccess()` (direct Turtle read/write) into `wacManager.js`, re-run the failing AC, and note the port explicitly (what changed and why) rather than silently replacing working code.
- [ ] Task 5: Cleanup (AC: #7)
  - [ ] 5.1 Revoke all test grants and delete any throwaway resources/containers created for this verification.

## Dev Notes

- **Reuse target:** `backoffice/pod-api.js` — `_writeAcl()` (~line 241-338, direct `.acl` Turtle emission: `acl:accessTo` on the target itself, `acl:default` on containers, owner block always included) and `getAccess()` (Turtle parser that distinguishes own vs. inherited ACL). Port the *pattern*, not a copy-paste: the MCP server runs `@inrupt/solid-client-authn-node` client-credentials sessions server-side, not a browser DPoP session, so the `fetch` wiring differs even though the Turtle logic transfers directly.
- **Verification harness:** reuse Story 7.3's zero-dependency Node `webcrypto` DPoP client-credentials pattern (no npm deps) for the independent out-of-app checks in AC5, rather than building a new one.
- **Non-negotiables carried from the brief (do not relax for convenience):** AGENT must never hold `acl:Control` on a data pod; grants scoped to containers only, never pod root; OWNER credentials never touch this story's code paths beyond the one-time onboarding/verification session.
- **Source:** `_bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md` §3 (confirmed/unconfirmed table), §6 (known pitfalls 1-6), Annex (Inrupt universal-access API warning).

## Change Log

| Date | Change |
|---|---|
| 2026-07-30 | Story drafted from Epic 8 (sprint change proposal 2026-07-30), ready-for-dev. |
| 2026-07-30 | Pre-verification static fixes to `mcp-connector/src/mcp-server.js` (checked against current MCP TypeScript SDK v1.29.0 docs via Context7, no live pod needed): (1) all six `inputSchema` values were wrapped in `z.object({...})` — the documented v1.x shape is a raw Zod shape (`{ field: z.type() }`), not a `ZodObject`; unwrapped. (2) `solid_grant_access` exposed an `asDefault` boolean that was passed as `{ asDefault }` to `wacManager.grantAccess`, which reads `options.scope` — `asDefault` was silently ignored, so every grant through the tool defaulted to `scope:'resource'` and could never produce a working container share (brief §6 pitfall 5). Replaced with a `scope: 'resource'|'default'|'both'` param actually wired through. (3) Added `annotations: {readOnlyHint:false, destructiveHint:true, idempotentHint:true}` to `solid_grant_access`/`solid_revoke_access` per brief §4.4 (documented as a hint only, not an enforced gate — spec text: "clients should never make tool use decisions based on ToolAnnotations from untrusted servers"). (4) `setPublicAccess` was implemented in `wacManager.js` but never exposed as an MCP tool at all; added `solid_set_public_access` with the same destructive annotation, matching the three tools the brief names as requiring human confirmation. These are wiring/interface bugs caught by re-reading the code against the brief's own DoD and current SDK docs — orthogonal to this story's live-verification ACs (AC1-7), which target `wacManager.js`'s WAC correctness, not the tool-registration layer.
