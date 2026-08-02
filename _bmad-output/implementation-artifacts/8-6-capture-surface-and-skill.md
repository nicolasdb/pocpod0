# Story 8.6: Capture Surface — Append-First Tools, Destructive Ceremony, and the Capture Skill

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **someone thinking out loud in a Claude conversation**,
I want to say "save this to my pod" and have it land in the right container, appended rather than clobbered, with real ceremony before anything is destroyed,
so that my pod becomes the place my thinking accumulates — instead of the artifact → download → re-import shuffle, which only ever goes one way and never lets the agent read back what I already know.

## Context / Why now

Epic 8 has been building **half a plugin**. A Claude plugin is an MCP server **and** a skill. 8.1–8.5 built, deployed, hardened and live-verified the MCP half. The skill half does not exist: `mcp-connector/SKILL.md` is a *developer* document ("here's `auth.js`, run onboarding like this") for someone building with the toolkit. Nothing tells Claude, in a conversation, **when** to capture, **where** it goes, or **what shape** it takes. Without that, every capture is improvised by whoever is chatting.

The tool surface has a matching gap, and it is not the one it looks like.

**The obvious gap** — no delete tool. `podClient.deleteResource` exists (`podClient.js:62`, exported line 89) but has **zero callers**: never wired into `mcp-server.js`. Epic 8's own `/shared` cleanups were done by one-off Node scripts importing `podClient` directly, and by raw `session.fetch(url, {method:'DELETE'})` — the library path, never the chat path. Epic 7's two-tap delete is `backoffice/pod-api.js`, a different codebase (browser app) sharing only the CSS instance. So: deletion has been proven three ways and is available from a chat in exactly none of them. The workaround — rename to `RM-*` and sweep later in the backoffice — doesn't dodge the problem: rename in Solid is copy+delete, and someone still empties the trash.

**The real gap** — `solid_write_resource` is a blind PUT. No read-before-write, no report of what it's replacing, and **no `destructiveHint` annotation** (only the three permission-writing tools carry one, `mcp-server.js:290` and siblings). Today an agent that mis-targets a URL destroys a file's contents with *less* ceremony than granting a stranger read access. That inconsistency is a bigger live risk than the missing delete, and adding delete without fixing it would be plugging the smaller hole.

For a capture workflow the right primitive is **append**, not overwrite. Epic 8's own action-log convention already does read-then-append by hand in every story since 8.2 — that pattern deserves to be a tool rather than a per-story ritual.

Scope boundary:
- **8.5 (before this):** first third-party-client evidence — the connector driven from claude.ai, negative test, four deferred items closed. Pure verification, no new tools.
- **8.6 (this):** complete the capture surface (append / ceremonial write / delete) and write the skill that uses it.
- **8.7 (after this):** team onboarding page — the first *other* person, as OWNER of their own pod.

Do not add a second identity here. Do not write 8.7's onboarding prose here.

## Design intent (settled with Nicolas — implement, don't re-litigate)

The connector's purpose is a **capture path**: externalize insight from a chat into the user's own pod, and — the part artifact-download can never do — let the agent **read it back** and build on it. Everything below follows from that:

| Principle | Consequence |
|---|---|
| Capture is additive | `solid_append_resource` is the default write path; overwrite is the exception, not the norm |
| Destruction is uniformly ceremonial | Overwrite, delete and permission change all get the same treatment — today only permission changes do |
| Confirm against reality, not a URL string | A confirmation that shows only a path is theatre; it must show **what is about to be lost** |
| Agent's blast radius stays small | Still no `acl:Control` in the data pod, still no self-granting (brief §4.1/§4.3) — unchanged |

## Verified state (probed 2026-08-01 — do not re-derive)

| Fact | Value |
|---|---|
| Registered tools (7) | `solid_read_resource`, `solid_write_resource`, `solid_list_container`, `solid_get_permissions`, `solid_grant_access`, `solid_revoke_access`, `solid_set_public_access` |
| `destructiveHint: true` today | Only on `solid_grant_access`, `solid_revoke_access`, `solid_set_public_access` |
| `deleteResource` | `podClient.js:62`, exported line 89, **zero callers** anywhere in the repo |
| Known `deleteResource` bug (8.1) | 404s when given a container URL with a trailing slash — worked around live with raw `session.fetch(url, {method:'DELETE'})` |
| Known `deleteResource` gap (8.1 review, in `deferred-work.md`) | Silently no-ops on containers, no API-level guard |
| Existing skill file | `mcp-connector/SKILL.md` — 40 lines, developer-facing toolkit doc, **not** a capture skill |
| Append precedent | Epic 8 action log, `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` — read-then-write append, done by hand every story since 8.2 |
| Verification target container | `https://pod.nicolasdb.eu/hyperscope_ndb/shared/` (already granted by Nicolas as OWNER — this story mints no grants) |
| Public endpoint | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` |

## Acceptance Criteria

1. **`solid_append_resource` exists** and is the documented default for capture. Read-then-append; creates the resource if absent; **never** silently replaces existing content. Concurrent-append behaviour is stated honestly in the tool description (last-writer-wins on a lost-update race — no ETag/If-Match today, same limitation Story 7.3 recorded for the backoffice).
2. **Append is proven non-destructive**: appending twice to a resource that already has content yields original + both additions, verified by byte-length growth and content re-read — not by assuming.
3. **`solid_write_resource` carries ceremony.** `destructiveHint: true`, and when the target already exists the tool reports what is about to be replaced (at minimum: existing byte size and first line / content-type) so a human confirms against reality rather than a URL. Writing to a *new* resource stays unceremonious — creation destroys nothing.
4. **`solid_delete_resource` exists**, `destructiveHint: true`, and handles the two known traps honestly: the container trailing-slash 404 (8.1) and the container silent no-op (`deferred-work.md`). Deleting a container either works correctly or **fails loudly** with an actionable message — it never reports success having done nothing.
5. **Ceremony is verified in a real client, not asserted.** From claude.ai: an overwrite of an existing file and a delete each produce an explicit confirmation before the tool fires. If the client does **not** prompt, record it as a finding (same honest treatment 8.5 gives the permission tools) — the guarantee then rests on hints alone and 8.7's onboarding must say so.
6. **Capture skill exists** as a user-facing skill (not the developer toolkit doc), covering: when to offer capture, which container, naming convention, what frontmatter/metadata a captured note carries, append-vs-new-resource decision, and how to read back and extend an existing note. `SKILL.md`'s developer content is preserved (moved or clearly separated), not overwritten.
7. **Round trip proven from a chat**: capture something from a live conversation into `shared/`, then in a *later* conversation have the agent find it, read it, and append to it. That round trip is the thing artifact→download→import cannot do and is this story's central claim.
8. **Journal covers the new tools**: append, ceremonial write and delete all appear with correct `ok`/`denied`/`error` outcomes attributed by label, and greps clean of slug and secret terms.
9. **No regression**: `scripts/verify-http.js` passes against the live public URL (updated for the new tool count), the container is healthy at 1 identity, and 8.5's negative test still fails cleanly with its pinned wording.
10. **Epic 8 convention**: dated "Story 8.6" section **appended** to `epic-8-action-log.md` (read-then-write, verified by byte-length growth), Story 8.6 proof-table section added to `epic-8-progress-report.md`, and `deferred-work.md`'s `deleteResource` container no-op item struck as closed.
11. **Read receipts (added 2026-08-02, FR42 / architecture.md BP-1)**: when the connector reads a resource it does **not** own, it appends a receipt entry — timestamp, reader label/WebID, resource URL, outcome — into the **data subject's own** `access-log/` container, using an `acl:Append`-only grant (never `acl:Write`). Evidence lands where the audited party cannot retract it. The honest limit is stated in the skill and the tool description: this is a **voluntary accountability convention**, not enforcement — CSS surfaces no per-resource read log to owners, so a reader that simply declines to write receipts leaves no trace by this mechanism. Proven live: read a resource in a granted container, then have the *subject* read back their own access log showing that access.

## Tasks / Subtasks

- [ ] **Task 1 — `solid_append_resource` (AC: 1, 2)**
  - [ ] 1.1 Add an append path. Reuse `podClient.readFile`/`writeFile` rather than writing a new HTTP path; if a helper belongs in `podClient.js`, put it there so the library consumers (Hermes, per brief §1) get it too.
  - [ ] 1.2 Absent resource → create. Existing resource → original + addition, never a replace.
  - [ ] 1.3 Register as an MCP tool via `safeHandler(toolName, label, resourceKey, fn)` — same wrapper as every other tool, so journalling and error mapping come for free.
  - [ ] 1.4 State the lost-update race in the tool description. Do not build optimistic concurrency here (Story 7.3 already scoped that as a cross-API design problem).
  - [ ] 1.5 Prove AC2 live: two appends to a resource with pre-existing content, byte-length growth + content re-read.

- [ ] **Task 2 — Ceremony on `solid_write_resource` (AC: 3)**
  - [ ] 2.1 Add `annotations: { destructiveHint: true, ... }`, matching the shape already used on the permission tools.
  - [ ] 2.2 Probe the target before writing. If it exists, surface existing size + first line / content-type in what the tool reports, so the confirmation shows what is about to be lost.
  - [ ] 2.3 New-resource writes stay light — creation destroys nothing, and ceremony that fires on everything gets clicked through.
  - [ ] 2.4 A failed existence probe must not silently become "assume new". Fail toward caution.

- [ ] **Task 3 — `solid_delete_resource` (AC: 4)**
  - [ ] 3.1 Wire `podClient.deleteResource` in as an MCP tool with `destructiveHint: true`, via `safeHandler`.
  - [ ] 3.2 Handle the container trailing-slash 404 (8.1's live finding) rather than rediscovering it.
  - [ ] 3.3 Close the silent container no-op: either delete correctly or fail loudly with an actionable message. A success report for a no-op is the failure mode this AC exists to prevent.
  - [ ] 3.4 Recursive container delete is **out of scope** — say so in the tool description. Story 7.7 owns owner-driven recursive deletion with ceremony; do not build a second implementation here.

- [ ] **Task 4 — The capture skill (AC: 6)**
  - [ ] 4.1 Decide the split: `SKILL.md`'s current developer content moves (e.g. to `references/` or a clearly-marked section) — it stays available, it does not get overwritten.
  - [ ] 4.2 Write the user-facing capture skill: when to offer capture, target container, naming convention, frontmatter/metadata on a captured note, append-vs-new decision, read-back-and-extend flow.
  - [ ] 4.3 Ground it in the tools that actually exist after Tasks 1–3 — no aspirational capabilities. Name the destructive ones and say the human confirms.
  - [ ] 4.4 Keep it short enough to be loaded into a chat without eating the context it's supposed to help capture.

- [ ] **Task 5 — Live verification from claude.ai (AC: 5, 7)**
  - [ ] 5.1 Reuse 8.5's method and its traps (the dev sandbox gets 403 from the allowlist; on-host requests hairpin — see 8.4 Task 8). Do not re-derive.
  - [ ] 5.2 Capture something real from a conversation into `shared/` using the skill.
  - [ ] 5.3 **New conversation**: have the agent find that note, read it, and append to it. This is AC7 — the round trip, and the story's central claim.
  - [ ] 5.4 Ceremony test: overwrite an existing file, and delete a throwaway file. Record whether the client actually prompted each time.
  - [ ] 5.5 Capture transcript/screenshot evidence.

- [ ] **Task 5b — Read receipts (AC: 11)**
  - [ ] 5b.1 Reuse Epic 5's `receipt.py` (BP-1) **shape**, not its code — that module is Python and lives in the pipeline; this is a Node connector. Match the semantics and field names so receipts across the two systems are the same artifact, and reuse `_safe_uri()`'s lesson (Turtle injection) if emitting RDF.
  - [ ] 5b.2 Emit a receipt when reading a resource whose owner is not this identity. Determining "not mine" cheaply: compare the resource URL's pod root against the identity's own `webId` pod root — do not add a network round trip per read.
  - [ ] 5b.3 Write receipts into the **data subject's own** `access-log/` container (BP-1's path), **not** the reader's pod. Rationale settled 2026-08-02: a receipt held by the party being audited can be quietly deleted by them — evidence must land where it cannot be retracted.
  - [ ] 5b.4 The grant this needs is **`acl:Append`, never `acl:Write`**, scoped to `access-log/` alone. Append lets a reader add an entry without reading others' entries and without modifying or deleting anything — that is precisely why the single-writer invariant survives (see architecture.md BP-6: nobody *overwrites* your pod but you; an append-only mailbox is a deliberate, narrow, revocable exception). **Verify live that CSS actually enforces Append-without-Read on this container** — if an Append grant leaks read access, that is a finding to record, not to work around.
  - [ ] 5b.5 Append-only write path, via Task 1's `solid_append_resource` — a receipt log that can be clobbered is not a receipt log.
  - [ ] 5b.6 Receipt-write failure must not silently swallow the read, nor abort it. Log the failure to the audit journal (`journal.js`) and report it — a read that happened without a receipt is exactly the case the subject needs to know about.
  - [ ] 5b.7 State the voluntary/non-enforcement limit in the skill and tool description. Do not imply the pod server logs reads; it does not.
  - [ ] 5b.8 Prove live: read a resource in the granted container from claude.ai, then have the **subject** read back their own `access-log/` showing that access recorded.

- [ ] **Task 6 — Journal + regression (AC: 8, 9)**
  - [ ] 6.1 Journal shows append / write / delete with correct outcomes, attributed by label.
  - [ ] 6.2 `grep` for slug and every secret term → 0 hits.
  - [ ] 6.3 Update `scripts/verify-http.js` for the new tool count and re-run against the live public URL.
  - [ ] 6.4 Re-confirm 8.5's negative test still fails cleanly with its pinned wording (Task 3's new error paths must not have loosened the classification).

- [ ] **Task 7 — Close the loop (AC: 10)**
  - [ ] 7.1 Append a dated "Story 8.6" section to `epic-8-action-log.md` (read-then-write, verify by byte-length growth). **Use `solid_append_resource` for this** — the tool this story adds, doing the job the convention has done by hand since 8.2. That is the convention's own dogfood test.
  - [ ] 7.2 Add a "Story 8.6" proof-table section to `epic-8-progress-report.md`.
  - [ ] 7.3 Strike the `deleteResource` container no-op item from `deferred-work.md`.

## Dev Notes

### Why append, and not "just be careful with write"

Every capture that overwrites is a chance to lose something that was never backed up — pods have no versioning (brief §7 defers it explicitly, and flags it as a real gap versus Git+Obsidian *before pods hold anything irreplaceable*). Until versioning exists, **append is the safety mechanism**. Design the skill so the additive path is the path of least resistance, not the one you have to remember to choose.

### Ceremony that works vs. ceremony that gets clicked through

A confirmation showing only a URL trains people to approve reflexively. Showing "this replaces 4.2 KB starting `## Meeting notes 2026-07-…`" is a confirmation someone can actually be wrong about and notice. That is the whole point of Task 2.2 — and the reason creation stays unceremonious in 2.3.

Note the honest limit, and say it in 8.7: MCP annotations are **hints**. The spec is explicit that clients must not gate purely on them. AC5 tests what claude.ai actually does; a "no prompt" result is a legitimate documented finding, not something to hide or work around. **Update from 8.5's live run:** claude.ai did NOT take the "no prompt" path — invoking `solid_grant_access` (already `destructiveHint: true`) triggered *two* confirmation layers, a text pause from Claude itself AND claude.ai's own native approval UI/button, both before the call executed. So the "no prompt is acceptable" framing is a documented fallback, not the expected case — 8.6's new `destructiveHint`-annotated tools (delete, and the overwrite-detecting write) should expect the same double-gate on this client, and Task 2.2's "showing what's about to be lost" ceremony sits *underneath* that native prompt, not instead of it.

### Notes from 8.5's live claude.ai run (carried forward, not yet acted on here)

- **Pod URL isn't discoverable by the agent.** In 8.5's first live exchange, Claude had no way to guess the pod root URL ("Solid Pods don't have a single fixed address I can guess") and had to ask cold before any tool call worked. The capture skill's first-launch behavior (or a fixed system note wired into `SKILL.md`) should state the person's own pod root URL up front so this doesn't repeat per conversation.
- **Write→read propagation is instant, live-measured.** Direct write-then-5x-immediate-read test against the pod: 335ms write, first read back byte-exact 1ms later, zero staleness across all 5 reads. No connector/CSS-side caching exists — so `solid_append_resource`'s read-then-write doesn't need any defensive delay/retry for propagation lag. The one real risk found was **client-side** caching on a human's own editor (stale local copy before their own save) — worth a line in the capture skill's guidance if humans are expected to co-edit files the agent also touches, but it's not something the connector/append tool itself needs to guard against.
- **ACL is resource-precise, not just container-blunt.** `office-vault.md` inside the granted `shared/` container came back access-denied via its own resource-level ACL override, while every sibling resource in the same container succeeded. `solid_append_resource` and `solid_delete_resource` must both handle "container is granted, but this specific resource inside it is not" as a normal, expected denial path — not something to special-case as a bug.

### Traps

- **The dev sandbox cannot reach the public URL** — the allowlist (Anthropic's outbound `160.79.104.0/21` + operator) excludes roaming addresses; your curl gets `403`. On-host requests hairpin through the VPS's own allowlisted IP (8.4 Task 8's method). **A 403 from your laptop is not a broken deploy.**
- **`deleteResource` 404s on container URLs with a trailing slash** (8.1, live) — known, do not rediscover.
- **A no-op reported as success is worse than an error.** That is exactly the container-delete gap Task 3.3 closes.
- **403 ≠ expired session** — 8.5's Task 4 added bounded re-auth on 401 only. New tools must not retry a 403; that's a real WAC denial.
- **This story mints no ACL grants.** `shared/` is already granted by Nicolas, by hand, as OWNER. OWNER credentials are not touched — same boundary 8.5 corrected for (see its "Correction made during planning").
- **Every VPS deploy is confirmed with Nicolas first** (8.4 precedent).

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Tool wrapper + journal + outcome classification | `safeHandler(toolName, label, resourceKey, fn)`, `mcp-server.js` |
| Error → MCP result mapping (status-code-first after 8.5) | `toToolErrorResult`, `mcp-server.js` |
| Read/write primitives | `podClient.js` — `readFile`, `writeFile`, `deleteResource` (already written, needs wiring not rewriting) |
| Destructive annotation shape | `solid_grant_access`'s `annotations` block, `mcp-server.js:290` |
| Append pattern | The read-then-write the action-log convention has used by hand since Story 8.2 |
| Audit append + rotation | `journal.js` |
| Live end-to-end regression | `scripts/verify-http.js` |
| Recursive container delete (**do not duplicate**) | Story 7.7's scope, `backoffice/` |

### Explicitly deferred — do not build here

Optimistic concurrency / ETag / If-Match on append (Story 7.3 scoped this as a cross-API design problem, not a per-tool fix). Recursive container delete (Story 7.7). Pod versioning / undo (brief §7 — a distinct mission, and the real answer to overwrite risk long-term). A second identity, OAuth/DCR, ACP migration, notifications (brief §7). Everything 8.5 re-deferred stays re-deferred unless it blocks a task here.

### Invalidated Assumptions

- **Assumption:** Epic 8 is building a Claude plugin → **Reality:** it has been building the MCP half only. A plugin is MCP **+** skill, and `SKILL.md` is a developer toolkit doc, not a capture skill. That half starts here.
- **Assumption:** deletion isn't available because nobody implemented it → **Reality:** `deleteResource` has been implemented and exported since the toolkit handoff; it was simply never registered as an MCP tool. Epic 8's own cleanups used it directly as a library, which is why the gap stayed invisible.
- **Assumption:** the destructive-action gap is the missing delete tool → **Reality:** `solid_write_resource` is a blind PUT with no annotation — a bigger live risk. Adding delete without fixing overwrite plugs the smaller hole.
- **Assumption:** Epic 7's two-tap delete covers this → **Reality:** that's `backoffice/pod-api.js`, a browser app sharing only the CSS instance. No code path in common with the connector.
- **Assumption:** capture is a write problem → **Reality:** the differentiator versus artifact→download→import is **read-back**. AC7's round trip, not the write, is the claim worth proving.

### Testing approach

No test framework in `mcp-connector/`, and this story does not add one (8.2–8.5 precedent). Evidence: `node --check` on every touched file, the live `verify-http.js` run, the AC2 append proof (byte growth + re-read), and the claude.ai transcript for AC5/AC7. **Live evidence beats argument** — Epic 8 convention.

### Rollback / blast radius

New tools only widen what a chat can do to `shared/` — a container already granted, already used as Epic 8's verification target, holding no irreplaceable data. The delete tool is the one genuinely new destructive capability; test it on a throwaway file created for the purpose, never on the action log or a proof artifact. Task 7.1 writes to the action log via append specifically because append cannot clobber it.

### Project Structure Notes

Changes inside `mcp-connector/`: `src/mcp-server.js` (3 tool registrations + annotations), `src/podClient.js` (append helper if it belongs there), `SKILL.md` + possibly `references/` (skill split), `scripts/verify-http.js` (tool count). No changes to `backoffice/`, `pipeline/`, or `infra/`. nginx config lives in the separate `hetzner-gateway` repo and is untouched.

### References

- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#4-contraintes-darchitecture] — §4.3 agent scope, §4.4 human confirmation before permission writes (the ceremony precedent this story generalizes)
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md#7-hors-scope] — versioning/backup deferred, and the warning to address it before pods hold anything irreplaceable
- [Source: _bmad-output/implementation-artifacts/8-1-wac-hardening-verification.md] — `deleteResource` container trailing-slash 404, raw-fetch workaround, action-log convention origin
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred-from-code-review-of-story-8-1-wac-hardening-verification] — `deleteResource` silent container no-op (closed by AC4)
- [Source: _bmad-output/implementation-artifacts/8-5-live-verification.md] — claude.ai verification method, allowlist/hairpin trap, pinned negative-test wording, OWNER boundary correction, live approval-prompt result (both text + native UI fired), write→read propagation measurement (0 staleness), resource-level ACL override finding — see "Notes from 8.5's live claude.ai run" above
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md] — on-host hairpin verification method, deploy confirmation practice
- [Source: mcp-connector/SKILL.md] — current developer-facing content to preserve, not overwrite

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-01 | Drafted and inserted between 8.5 (live verification) and team onboarding, which moves to 8.7. Origin: Nicolas asked why 8.5's Task 7 had no delete step; investigating found `deleteResource` written-but-never-wired, and surfaced the larger finding that `solid_write_resource` is a blind PUT with no destructive annotation — plus that Epic 8 had built only the MCP half of a plugin, with no capture skill. |
| 2026-08-02 | AC11 + Task 5b added: **read receipts** (FR42). Came out of the 8.7 pre-draft design session — Nicolas's school scenario assumed "I get a log of when and what the school agent read, so I can decide whether to revoke." Verified that no such log exists: CSS surfaces no per-resource read log to owners, and 8.4's audit journal covers only the connector's *own* actions, not third-party reads of your pod. Chosen as cheap-and-already-there (Epic 5 `receipt.py`/BP-1 is the shape). |
| 2026-08-02 | Task 5b **corrected within the same session**: first draft put receipts in the *reader's* pod to protect the single-writer invariant. Reversed to architecture.md BP-1's original location — the **subject's** `access-log/`, via an `acl:Append`-only grant. Deciding factor: under the reader's-pod version the party being audited holds the audit trail and can quietly delete it. `acl:Append` ≠ `acl:Write`, so the invariant survives as "nobody *overwrites* your pod but you", with an append-only mailbox as a deliberate narrow exception. |
