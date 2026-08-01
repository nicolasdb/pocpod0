# Story 8.5: Live Verification from claude.ai

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a HyperScope team member on Claude Pro**,
I want to add the deployed connector in claude.ai and, from a real conversation, list / read / write / inspect permissions on exactly the pod containers my WebID is granted — and nothing more,
so that the mission brief's Definition of Done is *met or disproven by a real MCP client*, instead of by our own verification scripts talking to our own server.

## Context / Why now

8.1–8.4 are `done`. The connector is live at `https://solid-mcp.nicolasdb.eu/mcp/<slug>` behind TLS, an Anthropic-IP allowlist, rate limiting, and a JSONL audit journal. Every layer is proven — **by `scripts/verify-http.js` and `scripts/verify-isolation.js`, which we wrote, against a server we wrote.** No third-party MCP client has ever spoken to it. That is the gap this story closes.

Two things make 8.5 more than a demo:

1. **The connector has never faced a real MCP client.** `solid_read_resource`/`write`/`list`/`get_permissions` and the two-token boundary have only ever been exercised by our own scripts.
2. **8.7 onboards real people.** Four deferred items are cheap operator-error guards today and become live incidents at N > 1. Nicolas's call: fold all four in now, before anyone else is depending on the service.

### Correction made during planning — do not repeat this mistake

An earlier draft of this story had Task 2 run `npm run onboard` / `onboard:apply` locally with **Nicolas's OWNER credentials**, on the theory that this was the only way to exercise brief T6 steps 1–3. Nicolas caught this: **that is backwards.** Each team member is their own OWNER on their own pod. Granting the AGENT access is a manual, human, one-time WAC act each person performs on their own data — never a script Claude Code runs centrally holding someone else's OWNER secret. `hyperscope_ndb/shared/` (the container 8.1–8.4 already use) was granted by Nicolas by hand, exactly as intended; automating that step here — even for "just this once, locally" — would be Claude Code touching a credential it has no business touching, and would model the wrong pattern for 8.7's onboarding.

**Consequence for this story:** `onboarding.js` and `whoami.js` are **not executed with OWNER credentials in 8.5.** `onboarding.js`'s role in this story is corrected reference material for 8.7 (each person runs — or adapts — it themselves against their own pod, with their own OWNER token, which never leaves their machine). `whoami.js` **is** run in 8.5, but only as an AGENT-side self-audit (no OWNER involved) against grants that already exist.

Scope boundary:
- **8.4 (done):** deployment and safe exposure.
- **8.5 (this):** drive it from claude.ai end-to-end including the negative test; AGENT-only self-audit via `whoami.js`; correct `GRANTS`/`PROBES` as reference material; close the four deferred items.
- **8.6:** the capture surface — append-first tools, destructive ceremony, and the capture skill.
- **8.7:** the human onboarding page — where a real teammate is OWNER of their own pod, runs (or adapts) `onboarding.js` themselves, and is the first *other* identity.

Do not write 8.7's onboarding prose here. Do not add the append/delete tools here — that is 8.6. Do not add a second identity here. Do not run `onboarding.js` in apply mode (or dry-run mode) with anyone's OWNER credentials as part of this story.

## Decisions taken at planning (do not re-litigate)

| Decision | Rationale |
|---|---|
| **claude.ai-side verification + AGENT-only self-audit**, not OWNER-run onboarding | OWNER-granting is each person's own manual act on their own pod (see correction above) — 8.5 verifies against grants that already exist, it doesn't mint new ones on someone else's behalf |
| **Stay at one identity** (Nicolas / `nicolas_claude`) | Keeps the failure surface small and adds **zero** new orphan CSS accounts. A real teammate walks the OWNER path in 8.7 |
| **Fold all four deferred items** (8.1 ×1, 8.2 ×2, 8.3 ×1) | "Mostly cheap, and next story we onboard people — better now than later" (Nicolas) |

## Verified state (probed 2026-08-01 — do not re-derive)

| Fact | Value |
|---|---|
| Public endpoint | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` (slug is a bearer secret, out of git) |
| Issuer | `https://pod.nicolasdb.eu/` |
| AGENT WebID | `https://pod.nicolasdb.eu/nicolas_claude/profile/card#me` |
| OWNER WebID | `https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me` — **not used by this story** (see correction above); belongs to Nicolas alone and is exercised by Nicolas by hand, outside any script run in this story |
| Real granted container | `https://pod.nicolasdb.eu/hyperscope_ndb/shared/` (`DATA_POD_GRANTED_CONTAINER`) — already granted by Nicolas as OWNER, already used by 8.1/8.2/8.4. This story's verification target |
| Placeholder containers still in code | `hyperscope_ndb/notes/`, `hyperscope_ndb/inbox/` — in `onboarding.js:37` `GRANTS` and `whoami.js:18` `PROBES`. Brief's own admitted guesses, never granted, never confirmed to exist |
| Registered tools (7) | `solid_read_resource`, `solid_write_resource`, `solid_list_container`, `solid_get_permissions`, `solid_grant_access`, `solid_revoke_access`, `solid_set_public_access` |
| Destructive annotation | The three permission-writing tools already carry `annotations: { destructiveHint: true, ... }` (`mcp-server.js:290` and siblings) — 8.5 verifies the client *honours* it, does not add it |
| Action log | `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` — append, never overwrite |

## Acceptance Criteria

1. **`PROBES` reflects reality.** `whoami.js`'s `PROBES` list is corrected to real containers: `hyperscope_ndb/shared/` (expect access) plus at least two expect-denied entries (`hyperscope_ndb/` root, `nicolas/`). Placeholder `notes/`/`inbox/` entries are removed or clearly marked as unused reference.
2. **`GRANTS` corrected as reference, not executed.** `onboarding.js`'s `GRANTS` constant is corrected to describe a real, sensible pattern (e.g. `shared/`) so it's honest material for 8.7 to adapt — **without being run in this story.**
3. **AGENT self-audit shows refusals, not just accesses.** `npm run whoami` (AGENT creds only, no OWNER credential touched or present) prints the expected grant on `shared/` **and** the expected denials (data-pod root, another person's pod). A run showing only successes fails this AC.
4. **Connector added in claude.ai** (Settings → Connectors → custom) against the live URL, and all 7 tools are visible in a real conversation.
5. **Happy path from the conversation:** list `shared/`, write a resource, read it back, inspect its WAC permissions — all four succeed, and `solid_get_permissions` renders a human-readable answer (never the literal string `null`).
6. **Negative test** (brief DoD point 5): ask Claude to write into a container the AGENT has no grant on → fails **cleanly** with the documented actionable message (e.g. no write access to this container), not a stack trace, not a silent success.
7. **Human approval is real, not annotated.** Invoking one permission-writing tool (`solid_grant_access` on a harmless target within Nicolas's own already-OWNER-controlled pod, then revert) produces an explicit approval prompt in the client. If the client does **not** prompt, record that as a finding — the brief's §4.4 guarantee then rests on hints alone and must be stated honestly in 8.7.
8. **Journal corroborates independently.** The audit journal shows the whole session attributed by label, with `ok` / `denied` / `error` outcomes distinguishable, and greps clean for the slug and every secret term.
9. **Four deferred items closed**, each with its own evidence (table under Tasks).
10. **No regression:** `scripts/verify-http.js` passes against the live public URL after the code changes, and the container is healthy at 1 identity.
11. **Epic 8 convention:** dated "Story 8.5" section **appended** to `epic-8-action-log.md` on the pod (read-then-write, verified by byte-length growth), and a Story 8.5 proof-table section added to `epic-8-progress-report.md`.

## Tasks / Subtasks

- [ ] **Task 1 — Correct `GRANTS`/`PROBES` as reference material (AC: 1, 2)**
  - [ ] 1.1 Confirm `hyperscope_ndb/shared/` is the AGENT's real granted container (already true, per `DATA_POD_GRANTED_CONTAINER`) — no new grant is made.
  - [ ] 1.2 Rewrite `whoami.js`'s `PROBES` to `shared/` plus the two expect-denied entries.
  - [ ] 1.3 Rewrite `onboarding.js`'s `GRANTS` to describe `shared/`'s actual grant shape (modes, scope, why) as the worked example a future OWNER (8.7) adapts. **Do not run `onboard` or `onboard:apply` against this or any pod in this story.**

- [ ] **Task 2 — AGENT-only self-audit (AC: 3)**
  - [ ] 2.1 `npm run whoami` using only `SOLID_CLIENT_ID`/`SOLID_CLIENT_SECRET`/`AGENT_WEBID` (AGENT creds) — confirm no `OWNER_*` env var is read or required by this run.
  - [ ] 2.2 Record accesses **and** denials verbatim in Completion Notes.

- [ ] **Task 3 — Fold in deferred item: `getAgentAccess` null ambiguity (AC: 5, 9)** *[from 8.1 review]*
  - [ ] 3.1 In `wacManager.js`, make "no ACL found" distinguishable from "no access recorded for this agent" instead of collapsing both to `null`. Keep the exported signature stable — the brief's annex depends on `grantAccess`/`revokeAccess`/`listAgentsWithAccess`/`getAgentAccess` staying a swappable interface.
  - [ ] 3.2 In `mcp-server.js`, render each case as a sentence a human reads in a chat. AC5 is the reason: today a chat user sees the literal `null`.
  - [ ] 3.3 Update `whoami.js`'s `ACL : not visible` branch to use the new distinction.

- [ ] **Task 4 — Fold in deferred item: session expiry / re-auth (AC: 9)** *[from 8.2 review, deferred twice]*
  - [ ] 4.1 On a 401 that indicates an expired session, re-login **once** for that identity and retry the call. Bounded — never a login loop, never a retry on 403 (403 is a real WAC denial and must stay denied).
  - [ ] 4.2 Log the re-auth at info level with the label only (never slug/secret).
  - [ ] 4.3 8.4's session-aware `/healthz` stays the detector; this is the recovery. Confirm `/healthz` still reports correctly after a forced re-auth.

- [ ] **Task 5 — Fold in deferred item: error classification by status code (AC: 6, 9)** *[from 8.2 review]*
  - [ ] 5.1 In `toToolErrorResult`, classify on status code first and fall back to the message match, rather than substring-matching `err.message` for `"control"` / `"501"`. Same fix shape as 8.1's 403-detection patch.
  - [ ] 5.2 AC6's "clean failure" **is** these strings — pin the exact wording with an assertion in the verification script so a future refactor can't silently reword the security-relevant message.

- [ ] **Task 6 — Fold in deferred item: `identities.json` operator guards (AC: 9)** *[from 8.3 review]*
  - [ ] 6.1 Reject duplicate `webId` / `clientId` across slugs in `loadIdentities()` — two slugs pointing at one identity silently defeats the per-person isolation 8.3 exists to provide.
  - [ ] 6.2 Refuse to load an over-permissive `identities.json` (ssh-style), rather than leaving `chmod 600` as README advice. Do the same for `.env` if it's a one-liner in the same path.
  - [ ] 6.3 Extend the 8.3 unit-check harness (13 cases) with the new rejections. Keep the existing cases passing.

- [ ] **Task 7 — Add the connector in claude.ai (AC: 4, 5, 6, 7)**
  - [ ] 7.1 Add custom connector with the full slug URL. **If Claude refuses an unauthenticated remote MCP server or demands OAuth/DCR — stop and raise it.** See Dev Notes; that is an architecture finding, not a bug to code around inside this story.
  - [ ] 7.2 Happy path: list `shared/`, write a resource, read it back, `solid_get_permissions` on it.
  - [ ] 7.3 Negative test: ask for a write into a non-granted container. Capture the exact user-visible text.
  - [ ] 7.4 Approval test: invoke one permission-writing tool on a harmless target already within Nicolas's own pod; record whether the client actually prompted; revert the grant.
  - [ ] 7.5 Capture evidence (transcript excerpts / screenshots) — this story's whole value is that the proof comes from outside our own code.

- [ ] **Task 8 — Journal + regression (AC: 8, 10)**
  - [ ] 8.1 Read the journal for the session: all three outcome classes present, attributed by label.
  - [ ] 8.2 `grep` for the slug and every secret term → 0 hits.
  - [ ] 8.3 Re-run `node scripts/verify-http.js` against the live public URL. Confirm container healthy at 1 identity.
  - [ ] 8.4 Clean up test resources written during Task 7, except anything deliberately kept as POC evidence — and if kept, say so explicitly (8.1's precedent).

- [ ] **Task 9 — Close the loop (AC: 11)**
  - [ ] 9.1 Append a dated "Story 8.5" section to `epic-8-action-log.md` (read-then-write, verify by byte-length growth — do not assume).
  - [ ] 9.2 Add a "Story 8.5" proof-table section to `epic-8-progress-report.md`, matching 8.1–8.4's format.
  - [ ] 9.3 Strike the four closed items from `deferred-work.md`; leave the re-deferred ones with the reason recorded (Dev Notes).

## Dev Notes

### The one thing that can invalidate this story

claude.ai's *Add custom connector* dialog exposes `Name`, `Remote MCP server URL`, and under Advanced: `OAuth Client ID` / `OAuth Client Secret`. **There is no "Request headers" field** — verified in session 2026-07-30 (brief T2), which is precisely why T3's secret-slug-in-URL is the retained path and not a fallback. So the whole URL, slug included, goes in the URL field.

If Claude rejects an unauthenticated remote MCP server, or forces an OAuth / dynamic-client-registration flow, **that is a genuine architecture finding.** Stop, record it, raise it with Nicolas. Do not bolt an OAuth server onto the connector inside this story.

### Who holds which credential, and why this story doesn't touch OWNER

Each person is the OWNER of their own pod. Granting the AGENT access is a manual act the OWNER performs on their own data — a script Claude Code runs with someone's OWNER secret defeats the reason the two-token model exists (§4.1: the OWNER token, if it ever reaches an agent or an automated flow, lets that agent grant itself anything). `hyperscope_ndb/shared/` is already granted, done correctly, by hand, before this story. Nothing in 8.5 mints a new grant or touches `OWNER_CLIENT_ID`/`OWNER_CLIENT_SECRET`. If verification surfaces a genuine need for an additional grant, that grant is made by Nicolas, manually, outside this story's automation — not scripted into a task.

### Traps

- **The dev sandbox cannot reach the public URL.** The allowlist (Anthropic's outbound `160.79.104.0/21` + operator) excludes roaming addresses — your curl gets `403`. On-host requests to the public hostname hairpin through the VPS's own allowlisted IP; that's 8.4 Task 8's method, reuse it. Anthropic's own infrastructure is allowlisted, so claude.ai works even when your terminal doesn't. **A 403 from your laptop is not a broken deploy.**
- **Orphan ACL is unrecoverable** (§6 pitfall 4) — relevant if Task 7.4's revert ever needs a fresh `.acl` write; always keep owner `control: true` in the same save.
- **`scope: 'resource'` alone on a container** lets the agent list the folder but not touch its contents (§6 pitfall 5). Always `'both'`.
- **403 ≠ expired session.** Task 4's retry must never fire on a 403 — that's a real WAC denial and AC6 depends on it staying denied.
- **`podClient.deleteResource()` 404s on container URLs** (8.1 note) — if Task 8.4 cleanup needs a container removed, use a raw `session.fetch(url, {method:'DELETE'})`.
- **Every VPS deploy is confirmed with Nicolas first** (8.4 precedent, three deploys that story).

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Tool wrapper + journal + outcome classification | `safeHandler(toolName, label, resourceKey, fn)`, `mcp-server.js` |
| Error → MCP result mapping | `toToolErrorResult`, `mcp-server.js` (Task 5 modifies this, doesn't replace it) |
| Identity validation | `loadIdentities()`, `identityRegistry.js` (Task 6 extends it) |
| Audit append + rotation | `journal.js` |
| Live end-to-end regression | `scripts/verify-http.js` |
| Pod read/write for the action log | `podClient.js` + `auth.js` under the AGENT session (8.2/8.4's method) |
| Isolation harness (**not needed here** — single identity) | `scripts/verify-isolation.js` |

### Explicitly deferred — do not build here

Re-defer with the reason, keep in `deferred-work.md`: journal rotation non-atomicity and `entrypoint.sh`'s unconditional chown (8.4 — operational, off this story's path); timing-unsafe `Map.get` on slugs, WebID URI normalization, `SOLID_OIDC_ISSUER` validation, sequential boot without timeout, and fail-fast single-point-of-failure (8.3 — the last two only bite at N > 1 and belong with 8.7's onboarding); `deleteResource` container no-op (8.1 — Story 7.7's territory). Also out of scope: a second identity, OWNER-run `onboarding.js` execution (belongs to each person, in 8.7); new append/delete tools and the capture skill (Story 8.6), OAuth/DCR, ACP migration, notifications, pod versioning (brief §7).

### Invalidated Assumptions

- **Assumption (from this story's own earlier draft):** exercising `onboarding.js` requires this story to run it with Nicolas's OWNER credentials → **Reality:** OWNER-granting is each individual's own manual act on their own pod; a central script run with someone's OWNER secret is the exact anti-pattern §4.1 exists to prevent. Corrected before implementation — see "Correction made during planning" above.
- **Assumption:** `hyperscope_ndb/notes/` and `hyperscope_ndb/inbox/` are the agent's containers → **Reality:** they are the brief's own admitted guesses, never granted. The one container actually granted and exercised by 8.1/8.2/8.4 is `hyperscope_ndb/shared/`.
- **Assumption:** T2 request-header auth might be available by now → **Reality:** absent on this Pro account as of 2026-07-30; T3's secret slug is the retained design, not a stopgap.
- **Assumption:** verification scripts passing means the DoD is met → **Reality:** every check so far is our code talking to our code. AC4–AC7 are the first third-party-client evidence in Epic 8.
- **Assumption:** the destructive-tool approval guarantee is delivered by the annotation → **Reality:** MCP annotations are hints; the spec says clients must not gate purely on them. AC7 tests the client's actual behaviour, and a "no prompt" result is a legitimate outcome to document, not a failure to hide.
- **Assumption:** `/healthz` covers session death → **Reality:** 8.4 made it *detect*; nothing recovers. That's Task 4.

### Testing approach

There is no test framework in `mcp-connector/` and this story does not add one (8.2/8.3/8.4 precedent). Evidence is: `node --check` on every touched file, direct unit-checks of `loadIdentities()` (extend 8.3's 13-case harness), the live `verify-http.js` run, the AGENT-only `whoami` run, and the claude.ai transcript. **Live evidence beats argument** — this is the Epic 8 convention.

### Rollback / blast radius

No new ACL grants are made by this story (see correction above) — Task 7.4's approval test operates on a target already inside Nicolas's own OWNER-controlled pod and is reverted immediately. Everything else is either read-only, local code, or a resource written into the agent's own workspace pod.

### Project Structure Notes

All code changes are inside `mcp-connector/src/` (`wacManager.js`, `mcp-server.js`, `identityRegistry.js`, `auth.js`, `onboarding.js` GRANTS-only, `whoami.js`) plus `scripts/`. No changes to `backoffice/`, `pipeline/`, or `infra/`. nginx-side config is in the separate `hetzner-gateway` repo and is **not** touched by this story.

### References

- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#2-definition-de-done] — the five DoD points AC4–AC6 map to
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#4-contraintes-darchitecture] — §4.1 two-token model (why OWNER stays untouched by this story), §4.3 agent scope, §4.4 human confirmation
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#6-pièges-connus] — pitfalls 4 (orphan ACL) and 5 (`scope: 'both'`)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred-from-code-review-of-story-8.2] — session expiry, error-substring classification
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred-from-code-review-of-story-8.3] — cross-slug uniqueness, file-mode check
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred-from-code-review-of-story-8-1-wac-hardening-verification] — `getAgentAccess` null ambiguity
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md] — allowlist/hairpin verification method, deploy confirmation practice
- [Source: mcp-connector/README.md#Deploying-on-a-VPS] — live env values, `ALLOWED_HOSTS` ordering

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-01 | Drafted. Scope: claude.ai-side verification + AGENT-only self-audit; single identity; all four candidate deferred items folded in ahead of team onboarding. |
| 2026-08-01 | Corrected before dev: removed OWNER-credential execution of `onboarding.js`/`onboard:apply` from this story — OWNER-granting is each person's own manual act on their own pod, not a script run centrally on their behalf. `onboarding.js` is reference material for 8.7; `whoami.js` runs AGENT-only. |
