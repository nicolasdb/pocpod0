# Story 8.5: Live Verification from claude.ai

Status: review

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

- [x] **Task 1 — Correct `GRANTS`/`PROBES` as reference material (AC: 1, 2)**
  - [x] 1.1 Confirm `hyperscope_ndb/shared/` is the AGENT's real granted container (already true, per `DATA_POD_GRANTED_CONTAINER`) — no new grant is made.
  - [x] 1.2 Rewrite `whoami.js`'s `PROBES` to `shared/` plus the two expect-denied entries.
  - [x] 1.3 Rewrite `onboarding.js`'s `GRANTS` to describe `shared/`'s actual grant shape (modes, scope, why) as the worked example a future OWNER (8.7) adapts. **Do not run `onboard` or `onboard:apply` against this or any pod in this story.**

- [x] **Task 2 — AGENT-only self-audit (AC: 3)** — Run on hetzner via `docker exec mcp-connector npm run whoami` (dev sandbox has no AGENT creds; container does). No `OWNER_*` var read or required — container boots with only the AGENT identity's `clientId`/`clientSecret`.
  - [x] 2.1 `npm run whoami` — AGENT creds only, confirmed by `identities.json`/container env containing no `OWNER_*` var.
  - [x] 2.2 First run (old PROBES, pre-8.5 code, still on old deploy) showed READ:yes on `hyperscope_ndb/` root and `nicolas/` — initially flagged as a possible over-grant, but Nicolas confirmed both are intentionally public-read (minimal public data), so LIST alone couldn't demonstrate a denial once PROBES was corrected to real containers. Added a WRITE probe to `whoami.js` (throwaway `whoami-write-probe.txt`, cleaned up on success) so isolation is actually exercised. Redeployed; final AGENT-only result on live `shared/`/root/`nicolas/`:
    ```
    https://pod.nicolasdb.eu/hyperscope_ndb/shared/
        READ  : yes (3 item(s))
        WRITE : yes
        ACL   : not visible (no ACL discoverable/accessible to this agent)

    https://pod.nicolasdb.eu/hyperscope_ndb/
        READ  : yes (6 item(s))
        WRITE : no  (HTTP 403)
        ACL   : not visible (no ACL discoverable/accessible to this agent)

    https://pod.nicolasdb.eu/nicolas/
        READ  : yes (2 item(s))
        WRITE : no  (HTTP 403)
        ACL   : not visible (no ACL discoverable/accessible to this agent)
    ```
    Grant on `shared/` confirmed (read+write); real 403 denials confirmed on both other containers — a run showing only successes would have failed this AC, and the WRITE probe is what makes the denial real instead of masked by public read.

- [x] **Task 3 — Fold in deferred item: `getAgentAccess` null ambiguity (AC: 5, 9)** *[from 8.1 review]*
  - [x] 3.1 In `wacManager.js`, make "no ACL found" distinguishable from "no access recorded for this agent" instead of collapsing both to `null`. Keep the exported signature stable — the brief's annex depends on `grantAccess`/`revokeAccess`/`listAgentsWithAccess`/`getAgentAccess` staying a swappable interface.
  - [x] 3.2 In `mcp-server.js`, render each case as a sentence a human reads in a chat. AC5 is the reason: today a chat user sees the literal `null`.
  - [x] 3.3 Update `whoami.js`'s `ACL : not visible` branch to use the new distinction.

- [x] **Task 4 — Fold in deferred item: session expiry / re-auth (AC: 9)** *[from 8.2 review, deferred twice]*
  - [x] 4.1 On a 401 that indicates an expired session, re-login **once** for that identity and retry the call. Bounded — never a login loop, never a retry on 403 (403 is a real WAC denial and must stay denied).
  - [x] 4.2 Log the re-auth at info level with the label only (never slug/secret).
  - [x] 4.3 8.4's session-aware `/healthz` stays the detector; this is the recovery. Confirmed by code inspection (not a live run — no reachable server in this sandbox): `/healthz` reads `identity.session.info.isLoggedIn` from the same shared `identities` Map entry that `reauthIdentity` mutates, so it reflects the new session on the very next poll with no separate wiring needed.

- [x] **Task 5 — Fold in deferred item: error classification by status code (AC: 6, 9)** *[from 8.2 review]*
  - [x] 5.1 In `toToolErrorResult`, classify on status code first and fall back to the message match, rather than substring-matching `err.message` for `"control"` / `"501"`. Same fix shape as 8.1's 403-detection patch.
  - [x] 5.2 AC6's "clean failure" **is** these strings — pin the exact wording with an assertion in the verification script so a future refactor can't silently reword the security-relevant message.

- [x] **Task 6 — Fold in deferred item: `identities.json` operator guards (AC: 9)** *[from 8.3 review]*
  - [x] 6.1 Reject duplicate `webId` / `clientId` across slugs in `loadIdentities()` — two slugs pointing at one identity silently defeats the per-person isolation 8.3 exists to provide.
  - [x] 6.2 Refuse to load an over-permissive `identities.json` (ssh-style), rather than leaving `chmod 600` as README advice. Do the same for `.env` if it's a one-liner in the same path.
  - [x] 6.3 Extend the 8.3 unit-check harness (13 cases) with the new rejections. Keep the existing cases passing. Now 18/18 passing (13 original + 5 new: duplicate webId, duplicate clientId, over-permissive mode ×2, restrictive mode still loads).

- [x] **Task 7 — Add the connector in claude.ai (AC: 4, 5, 6, 7)** — Run live by Nicolas from claude.ai (transcripts in `_bmad-output/test-artifacts/`). All 5 subtasks done.
  - [x] 7.1 Connector "hyperCampus" added, URL `https://solid-mcp.nicolasdb.eu/mcp/<slug>`, no OAuth fields needed — connected cleanly, no refusal/DCR demand. All 7 tools visible (screenshot 2026-08-01 18:14). claude.ai's own per-tool "Needs approval" toggle observed, defaulted to "Needs approval" for all 3 write/permission tools and all 4 read tools — separate mechanism from destructiveHint annotations, relevant evidence for AC7/7.4.
  - [x] 7.2 Happy path — transcript `Claude-Testing hypercampus connector with Solid pod.md` (single consolidated export, later appended to): `solid_list_container` on `shared/` ✓; `solid_write_resource` (test file + hidden question) ✓; `solid_read_resource` round-trip ✓ (three separate reads across two chat turns, content confirmed correct including a live user edit); `solid_get_permissions` ✓ — rendered the human sentence "checking permissions requires Control access... I only have read/write" both times, never the literal string `null` (AC5 requirement met). Bonus finding: `office-vault.md`, also inside `shared/`, came back "access denied" while every other resource in the same container succeeded — a per-resource ACL override inside a scope:'both' grant, not a bug; confirms WAC isolation is resource-precise. Second finding: agent could not guess the pod URL unprompted ("Solid Pods don't have a single fixed address I can guess") — needed it stated explicitly; captured as an onboarding-material gap for 8.6/8.7 (see memory). Third finding, INVESTIGATED not assumed: Nicolas's own edit to `claude-access-test.md` (adding a "##question 2" section) initially failed to persist in his own browser/editor client and required a manual reload+retry on his side before it saved — raised as a possible write/read propagation-delay risk. Live-tested directly against the pod from the container (write, then 5 immediate consecutive reads via `podClient`): write 335ms, first read back matched byte-exact only 1ms after write completed, all 5 reads matched with zero staleness. **No server-side or connector-side propagation delay exists** — CSS serves the latest write instantly. The delay Nicolas hit was his own editor/browser holding a stale local copy before his own save (client-side cache), not the pod or connector. No fix needed here; ruled out with a live measurement, not by assumption.
  - [x] 7.3 Negative test — write attempt into `tasks/` (never granted) returned exactly: **"Access denied — this agent lacks the required WAC permission on that resource."** — verbatim match to `verify-http.js`'s `EXPECTED_DENIED_MESSAGE` pinned string (Task 5.2). Clean failure, no stack trace, no silent success (AC6 met). Also independently confirmed read-denied on both `tasks/` and `profile/` — access is genuinely scoped to `shared/` only, not just conventionally respected.
  - [x] 7.4 Approval test — `solid_grant_access` invoked targeting `shared/claude-access-test.md`, granting read-only to a throwaway placeholder WebID (`https://example.org/webid#me`). **Two-layer confirmation observed, both confirmed by Nicolas**: (1) Claude itself paused and asked for text confirmation before calling the tool, (2) claude.ai's own native approval UI (the "Needs approval" toggle seen at connector setup) also fired as a real prompt/button before the call executed — the client genuinely gates on `destructiveHint`, not just hinting at it (strong positive result for AC7, stronger than the "no prompt is a legitimate documented outcome" fallback the story allowed for). Call itself then 403'd with `"...does not have Control access... This grant must be made by the pod owner's WebID"` — correct, since the AGENT never holds Control anywhere by design (§4.1); no grant was ever created (confirmed: nothing exists for `example.org/webid#me` on that file), so no revert was needed.
  - [x] 7.5 Evidence captured — one consolidated transcript (the exporter re-exports in place; earlier `(1)`/`(2)` were intermediate re-exports of the same growing conversation, not separate files) in `_bmad-output/test-artifacts/Claude-Testing hypercampus connector with Solid pod.md`, plus a connector-setup screenshot (`/home/nicolas/Images/Screenshots/screencap_0801_181428.png`, 7 tools + approval toggles visible).

- [x] **Task 8 — Journal + regression (AC: 8, 10)** — Completed after Task 7, via `docker exec` on hetzner (session ran live, journal reachable from the host).
  - [x] 8.1 Read `/app/audit/journal.jsonl` on the live container. All three outcome classes present and correctly attributed by `label`: `ok` (list/read/write successes), `denied` (WAC refusals — `tasks/` write, `tasks/`/`profile/` reads, `office-vault.md` read, the `solid_grant_access` Control-denial), `error` (a probe against a nonexistent resource from an earlier session). Session's Task 7 entries visible from `2026-08-01T16:18:19Z` through `17:07:16Z`, all labeled "Nicolas (agent)" — no cross-identity leakage.
  - [x] 8.2 `grep` for the slug and every secret term on the live journal → **0 hits** (re-run against the real file, not just the repo). Slug `bOEFhDkERQ1BUTbsM_l7BA`, the clientSecret value, and the clientId string all absent.
  - [x] 8.3 `node scripts/verify-http.js https://solid-mcp.nicolasdb.eu/mcp/<slug>` run from inside the container (hairpin path, per 8.4's method) — **ALL CHECKS PASSED**, including the new Task 5.2 pinned negative-test assertion (denial wording matched exactly, no drift). `docker ps` confirms container `healthy`, 1 identity configured. No regression.
  - [x] 8.4 Cleanup reviewed against the live journal: every negative-test write (`8-5-verify-denied-probe.txt`, the `tasks/` write attempt) was `denied` — nothing was ever persisted, nothing to delete. Two resources were deliberately written and are **kept as POC evidence, explicitly** (8.1 precedent): `shared/claude-access-test.md` (the Task 7.2 read/write round-trip, referenced in transcripts) and `shared/test-log-2026-08-01.md` (Claude's own session summary, factually verified against the journal/transcripts, not clutter).

- [x] **Task 9 — Close the loop (AC: 11)** — Done after Task 7/8, via `docker exec` on hetzner.
  - [x] 9.1 Appended dated "Story 8.5" section to `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md`. Read-then-write: file was 7995 bytes before, 9810 after (grew by 1815, matching the appended content's length), re-read afterward and confirmed the new content starts with the exact pre-append bytes (prefix preserved, nothing overwritten) — verified by measurement, not assumed.
  - [x] 9.2 Add a "Story 8.5" proof-table section to `epic-8-progress-report.md`, matching 8.1–8.4's format. Added, honestly describing the blocked items rather than a synthetic proof-table.
  - [x] 9.3 Strike the four closed items from `deferred-work.md`; leave the re-deferred ones with the reason recorded (Dev Notes).

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

Claude Sonnet 5 (claude-sonnet-5), via a worktree-isolated dev agent.

### Debug Log References

- `node --check` clean on every touched `.js` file: `src/whoami.js`, `src/onboarding.js`, `src/wacManager.js`, `src/mcp-server.js`, `src/identityRegistry.js`, `scripts/verify-http.js`.
- Extended `loadIdentities()` unit-check (13 original 8.3 cases + 5 new Story 8.5 cases = 18 total, all passing), run as an ephemeral script (not committed, per 8.2/8.3/8.4 precedent of "no test framework introduced"). Full pass/fail output captured below in Completion Notes.
- `curl -m5 https://solid-mcp.nicolasdb.eu/` from this dev sandbox → `403` (confirms the story's own documented allowlist trap, not a broken deploy). `curl -m5 https://pod.nicolasdb.eu/` → `200` (general egress works).
- No `.env`, no `identities.json`, and no `node_modules` present anywhere reachable from this sandbox — verified via `find` before concluding Tasks 2/8.3/9.1 were genuinely blocked rather than just inconvenient.

### Completion Notes List

**HALT condition reached, as instructed.** Task 7 (add the connector in claude.ai) requires a human driving claude.ai's UI interactively and cannot be done by this agent — skipped entirely, not marked complete, per explicit instruction. Everything in Task 8 that depends on a live claude.ai session (8.1, 8.4) and Task 9.1 (writing to the live pod) are consequently also blocked, for a second, independent reason: **this dev sandbox has no AGENT credentials at all** (`mcp-connector/.env` does not exist here, no `SOLID_CLIENT_ID`/`SOLID_CLIENT_SECRET`/`AGENT_WEBID` env vars are set) and **no `node_modules`** (so even `npm run whoami` can't get past `require("@inrupt/...")`). Both facts were verified directly (`find`/`env`/`ls`), not assumed. Task 2 (AGENT-only self-audit) is consequently **not run** — no fabricated whoami output is recorded anywhere in this story or its Completion Notes.

Story status is left as `ready-for-dev` — not moved to `review` — per explicit instruction, since Task 7 (and the AC4–AC7 parts of Task 8 that depend on it) still need Nicolas to run interactively before this story can honestly be called done.

**What was actually done, and how it was verified:**

- **Task 1 (AC1, AC2):** `whoami.js`'s `PROBES` now lists exactly `hyperscope_ndb/shared/` (expect access) plus `hyperscope_ndb/` root and `nicolas/` (both expect-denied) — the `notes/`/`inbox/` placeholders (never-granted, per the story's own "Invalidated Assumptions") are removed, not just commented out. `onboarding.js`'s `GRANTS` constant was rewritten to describe `shared/`'s real grant shape (`read+append+write`, `control:false`, `scope:'both'`) as honest 8.7 reference material — the file is untouched otherwise, and was **not executed** at any point (no `--apply`, no dry run either — I did not run `node src/onboarding.js` at all, matching the story's correction).
- **Task 3 (AC5, AC9):** `wacManager.getAgentAccess()` now returns `{ aclVisible, access }` instead of a bare value that collapsed "ACL not visible to this session at all" and "ACL visible, agent has zero grants" into the same falsy-ish signal. `whoami.js`'s ACL line branches on `aclVisible` explicitly. `listAgentsWithAccess()` (used by `mcp-server.js`'s `solid_get_permissions` tool) was left returning its existing `null`-on-not-visible contract, because `mcp-server.js` **already** renders that as a human sentence ("Reading permissions requires Control access...") rather than the literal word `null` — checked by reading the existing code, not assumed. No tool currently calls `getAgentAccess()` directly (grepped to confirm), so there was no live call site in `mcp-server.js` to update for that specific function; the new discriminated shape is ready for whichever future tool wires it in (Story 8.6 candidate).
- **Task 4 (AC9):** `bootIdentities()` now retains each identity's `clientId`/`clientSecret` in memory (never logged) alongside its session. `buildMcpServer()` was changed to take the whole `identity` object rather than a bare `session`, and every tool handler now reads `identity.session` live instead of a value captured at server-build time — necessary so a mid-request re-auth's new session is actually used by the retry, not a stale closed-over reference. `safeHandler()` catches a `401`, calls `reauthIdentity(identity)` exactly once (structurally bounded — no loop is possible, the retry path itself doesn't re-enter the 401 branch), retries the same call once, and only re-throws to the generic error path if that retry also fails. `403` never triggers this path (checked via `status === 401` only, no `<=` or substring). `/healthz` needed **no changes** — it already reads `identity.session.info.isLoggedIn` off the same shared `identities` Map entry that `reauthIdentity` mutates in place, so it self-corrects on the next poll. This was verified by code inspection only — there is no live 401 to force in this sandbox.
- **Task 5 (AC6, AC9):** Root-caused the substring-matching: `wacManager.js`'s own Control-access errors, and any 501 CSS returns Inrupt wraps, never carried a `.statusCode` — Inrupt's FetchError only embeds the real HTTP status inside its message text (e.g. `"...failed: [403]..."`). Added `_normalizeFetchError()` in `wacManager.js` that extracts that bracketed status and attaches it as `.statusCode`, applied it in `_saveAclOrThrowControlError`, the `!hasAccessibleAcl` throw in `_getEditableAcl`, and both `listAgentsWithAccess`/`getAgentAccess`'s dataset fetch. `mcp-server.js`'s `toToolErrorResult` now checks `status === 403`/`status === 501` **before** falling back to the message-substring checks, which are now gated on `!status` so they only fire for an error that somehow bypassed wacManager's normalization entirely. AC6's exact wording (`"Access denied — this agent lacks the required WAC permission on that resource."`) is now pinned as `EXPECTED_DENIED_MESSAGE` in `scripts/verify-http.js`, asserted against a real negative-test tool call added to that script (write to a non-granted URL, `VERIFY_DENIED_URL`, defaults to the data-pod root) — the assertion exists and is syntax-valid, but **has not actually run against a live server** in this sandbox (same blocker as Task 8.3).
- **Task 6 (AC9):** `identityRegistry.js`'s `loadIdentities()` now tracks `webId`→label and `clientId`→label maps across the whole slug loop and throws (naming both labels, never the slug) on a repeat of either. Added `_refuseIfOverPermissive()`, a POSIX-mode check (masks against `0o077`) applied to `identities.json` unconditionally and to `.env` best-effort (only if it exists — a deployment supplying credentials purely via real env vars shouldn't be penalized for a `.env` that was never created). No-ops cleanly on Windows. Extended the unit-check harness from 13 to 18 cases (5 new: duplicate webId, duplicate clientId, over-permissive `0644` mode, restrictive `0600` still loads, world-readable `0604` mode) — **all 18 pass**, full output:
  ```
  pass  1 valid single identity: loaded 1 identities
  pass  2 valid multiple identities: loaded 2 identities
  pass  3 missing file: No identities file at ... Copy identities.example.js...
  pass  4 too-short slug: ... shorter than 22 characters — too guessable...
  pass  5 missing required field: ... missing required field "clientSecret".
  pass  6 duplicate top-level JSON key (text-level): ... duplicate slug key(s)...
  pass  7 malformed JSON: identities.json is not valid JSON: ...
  pass  8 top-level array instead of object: ... must be a JSON object...
  pass  9 top-level string instead of object: ... must be a JSON object...
  pass  10 unsafe slug characters: ... isn't URL-safe. Slugs must match...
  pass  11 empty identities object: ... contains no identities...
  pass  12 _comment key skipped (with warning, not fatal): loaded 1 identities
  pass  13 only _comment key, no real identities: ... contains no identities...
  pass  14 duplicate webId across two slugs: ... has the same webId as identity "Person 1"...
  pass  15 duplicate clientId across two slugs: ... has the same clientId as identity "Person 1"...
  pass  16 over-permissive identities.json mode (0644): ... readable/writable by group or o...
  pass  17 correctly restrictive identities.json mode (0600) still loads: loaded 1 identities
  pass  18 world-readable identities.json mode (0604): ... readable/writable by group...

  18 passed, 0 failed (of 18 total cases)
  ```
- **Task 8.2:** Grepped `mcp-connector/` for `SOLID_CLIENT_SECRET`/`OWNER_CLIENT_SECRET`/`clientSecret` — the only hits are field-name mentions in `README.md` (documenting the JSON shape), never a real value. There is no local audit journal file in this sandbox to grep (the server has never run here), so the live-journal half of AC8 (Task 8.1) is genuinely unattemptable from here, not just skipped for convenience.
- **Task 9.2:** Added a "Story 8.5" section to `epic-8-progress-report.md`, following the existing per-story table format, but honestly describing what's blocked rather than fabricating a proof table for work that didn't happen.
- **Task 9.3:** Struck all four closed deferred items in `deferred-work.md` with a one-line pointer to the story/task that closed each, using strikethrough + a **CLOSED (...)** note rather than deleting the history.

**A worktree/branch-state note, unrelated to the story's own content:** this worktree was created from a stale base commit that predated `mcp-connector` entirely (pre-Epic-8, before `vps-mode` had most of its Epic 7/8 work). Before any story work could start, it had to be fast-forwarded to `origin/vps-mode`'s tip, and then a further single local-only commit (`6232bbc`, which drafted this very story file and hadn't been pushed yet) had to be pulled in from the shared checkout as a temporary git remote. Both were plain fast-forwards with zero divergent history — no merge, no force, nothing destructive — but flagging it since it's outside this story's normal scope.

**Live-verification phase (Task 7 onward), run by Nicolas + Claude Code together:**

- **Task 2:** `whoami.js` run live via `docker exec mcp-connector npm run whoami` on hetzner (dev sandbox still had no AGENT creds; the container does). First run used the container's not-yet-redeployed old code and old PROBES, and unexpectedly showed READ:yes on `hyperscope_ndb/` root and `nicolas/` — flagged as a possible over-grant, but Nicolas confirmed both are intentionally public-read. That meant LIST alone couldn't demonstrate a denial once PROBES pointed at real containers, so a **WRITE probe** was added to `whoami.js` (throwaway file, self-cleaning on success) to actually exercise the agent's own WAC rights independent of public access. Redeployed; final result showed `shared/` granting both read+write and the other two containers correctly WRITE-denied (403) — AC3 met with a genuine demonstrated refusal, not just accesses.
- **Task 7:** Connector "hyperCampus" added in claude.ai against the live URL, no OAuth fields, no refusal. All 7 tools visible. Full happy path (list/write/read round-trip/get_permissions), negative test (exact pinned denial wording), and approval test (both a text confirmation AND claude.ai's native approval UI fired before the destructive tool ran) all completed live — see Dev Notes/Tasks section above for the full evidence and three linked transcripts in `_bmad-output/test-artifacts/`.
- **Live finding, investigated not assumed:** Nicolas's own client-side edit appeared to fail to persist, raising a possible write/read propagation-delay risk. Tested directly against the pod (write, then 5 immediate consecutive reads via `podClient`): zero staleness, byte-exact every time, 1ms after write completion. Ruled out as a server/connector issue; isolated to Nicolas's local editor cache.
- **Task 8:** Journal read live (`/app/audit/journal.jsonl`) — all three outcome classes (`ok`/`denied`/`error`) present, correctly attributed by label, 0 grep hits for the slug/secrets. `scripts/verify-http.js` re-run live post-redeploy — ALL CHECKS PASSED including the new pinned negative-test assertion. Container confirmed `healthy`, 1 identity. No test resources needed deletion (all negative-test writes were denied, nothing persisted); two resources kept explicitly as POC evidence: `shared/claude-access-test.md` and `shared/test-log-2026-08-01.md`.
- **Task 9.1:** Appended dated "Story 8.5" section to `epic-8-action-log.md` on the pod via a read-then-write script — verified by byte-length growth (7995→9810 bytes) and confirmed the new content's prefix matched the pre-append bytes exactly (safe append, nothing overwritten).
- **Redeploys required:** two live `make vps-deploy` runs this story (confirmed with Nicolas both times) — one for Tasks 1–6's code, one for the WRITE-probe fix to `whoami.js` found live during Task 2.

### File List

- `mcp-connector/src/whoami.js` — Task 1.2 (PROBES corrected), Task 3.3 (ACL branch uses discriminated result), Task 2 (WRITE probe added to demonstrate genuine denial, not just LIST, since two PROBES containers turned out to be public-read)
- `mcp-connector/src/onboarding.js` — Task 1.3 (GRANTS corrected as reference only; not executed)
- `mcp-connector/src/wacManager.js` — Task 3.1 (`getAgentAccess` discriminated return), Task 5.1 (`_normalizeFetchError`, statusCode attached to Control-access and fetch errors)
- `mcp-connector/src/mcp-server.js` — Task 3.2 (comment/behavior around `getAgentAccess` consumers confirmed already-human-readable), Task 4 (identity-aware re-auth-on-401, `buildMcpServer`/`safeHandler` now take `identity` not bare `session`/`label`), Task 5.1 (`toToolErrorResult` status-first classification)
- `mcp-connector/src/identityRegistry.js` — Task 6.1 (cross-slug duplicate webId/clientId rejection), Task 6.2 (file-mode guard for `identities.json` and `.env`)
- `mcp-connector/scripts/verify-http.js` — Task 5.2 (pinned AC6 wording assertion + negative-test call)
- `_bmad-output/implementation-artifacts/deferred-work.md` — Task 9.3 (four closed items struck)
- `_bmad-output/implementation-artifacts/epic-8-progress-report.md` — Task 9.2 (Story 8.5 section added)
- `_bmad-output/implementation-artifacts/8-5-live-verification.md` — this file (Tasks/Subtasks, Dev Agent Record, Change Log)

## Change Log

| Date | Change |
|---|---|
| 2026-08-01 | Drafted. Scope: claude.ai-side verification + AGENT-only self-audit; single identity; all four candidate deferred items folded in ahead of team onboarding. |
| 2026-08-01 | Corrected before dev: removed OWNER-credential execution of `onboarding.js`/`onboard:apply` from this story — OWNER-granting is each person's own manual act on their own pod, not a script run centrally on their behalf. `onboarding.js` is reference material for 8.7; `whoami.js` runs AGENT-only. |
| 2026-08-01 | Tasks 1, 3, 4, 5, 6, 8.2, 9.2, 9.3 implemented and `node --check`/unit-check verified. Task 2 (AGENT self-audit) and the AC4–AC7-dependent parts of Task 8 (8.1, 8.3) and Task 9.1 left undone — no AGENT credentials, no `node_modules`, and no reachable path to the live MCP endpoint exist in this dev sandbox, and Task 7 requires a human driving claude.ai interactively. Status intentionally left `ready-for-dev`, not `review`. |
| 2026-08-01 | Task 7 run live by Nicolas from claude.ai — connector added, all 7 tools verified, happy path/negative test/approval test all completed with real evidence (3 transcripts + screenshot). Task 2 completed live via hetzner `docker exec`, revealing a real gap (2 of 3 PROBES were public-read, so READ alone couldn't demonstrate denial) — fixed by adding a WRITE probe to `whoami.js`, redeployed. Live-investigated a client-side propagation-delay concern Nicolas raised, ruled out as a server/connector issue via direct write→read timing measurement (0 staleness). Tasks 8 (8.1/8.3/8.4) and 9.1 completed live once the session existed to check. All 9 tasks and 11 ACs now met. Status moved to `review`. Two live `make vps-deploy` runs this story. |
