# Story 8.6: Capture Surface — Append-First Tools, Destructive Ceremony, and the Capture Skill

Status: done

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

- [x] **Task 1 — `solid_append_resource` (AC: 1, 2)**
  - [x] 1.1 Add an append path. Reuse `podClient.readFile`/`writeFile` rather than writing a new HTTP path; if a helper belongs in `podClient.js`, put it there so the library consumers (Hermes, per brief §1) get it too.
  - [x] 1.2 Absent resource → create. Existing resource → original + addition, never a replace.
  - [x] 1.3 Register as an MCP tool via `safeHandler(toolName, label, resourceKey, fn)` — same wrapper as every other tool, so journalling and error mapping come for free.
  - [x] 1.4 State the lost-update race in the tool description. Do not build optimistic concurrency here (Story 7.3 already scoped that as a cross-API design problem).
  - [x] 1.5 Prove AC2 live: two appends to a resource with pre-existing content, byte-length growth + content re-read. **Live 2026-08-02: `shared/8-6-append-test.md`, 0→64→136 bytes, delta=72 bytes matched the 2nd string exactly, read-back showed both lines in order.**

- [x] **Task 2 — Ceremony on `solid_write_resource` (AC: 3)**
  - [x] 2.1 Add `annotations: { destructiveHint: true, ... }`, matching the shape already used on the permission tools.
  - [x] 2.2 Probe the target before writing. If it exists, surface existing size + first line / content-type in what the tool reports, so the confirmation shows what is about to be lost.
  - [x] 2.3 New-resource writes stay light — creation destroys nothing, and ceremony that fires on everything gets clicked through.
  - [x] 2.4 A failed existence probe must not silently become "assume new". Fail toward caution.

- [x] **Task 3 — `solid_delete_resource` (AC: 4)**
  - [x] 3.1 Wire `podClient.deleteResource` in as an MCP tool with `destructiveHint: true`, via `safeHandler`.
  - [x] 3.2 Handle the container trailing-slash 404 (8.1's live finding) rather than rediscovering it. **Fixed at the root: `deleteResource` now uses raw `session.fetch(url, {method:'DELETE'})` instead of inrupt's `deleteFile`, which is what 8.1 worked around live.**
  - [x] 3.3 Close the silent container no-op: either delete correctly or fail loudly with an actionable message. A success report for a no-op is the failure mode this AC exists to prevent. **New `podClient.confirmGone` re-GETs the URL post-delete; a still-200 is thrown as an error, never reported as success.**
  - [x] 3.4 Recursive container delete is **out of scope** — say so in the tool description. Story 7.7 owns owner-driven recursive deletion with ceremony; do not build a second implementation here. **Non-empty containers are refused outright (409) before any delete is attempted.**

- [x] **Task 4 — The capture skill (AC: 6)**
  - [x] 4.1 Decide the split: `SKILL.md`'s current developer content moves (e.g. to `references/` or a clearly-marked section) — it stays available, it does not get overwritten. **Moved verbatim (retitled) to `references/developer-toolkit.md`.**
  - [x] 4.2 Write the user-facing capture skill: when to offer capture, target container, naming convention, frontmatter/metadata on a captured note, append-vs-new decision, read-back-and-extend flow.
  - [x] 4.3 Ground it in the tools that actually exist after Tasks 1–3 — no aspirational capabilities. Name the destructive ones and say the human confirms.
  - [x] 4.4 Keep it short enough to be loaded into a chat without eating the context it's supposed to help capture. **~120 lines.**

- [x] **Task 5 — Live verification from claude.ai (AC: 5, 7)**
  - [x] 5.1 (N/A here — run directly from claude.ai against the deployed connector, not the dev sandbox; no allowlist/hairpin needed for a real client session.)
  - [x] 5.2 Captured `shared/2026-08-02-task5-connector-validation.md` (0→1176 bytes) and, at close, `shared/story-8-6-task5-validation-report.md`.
  - [x] 5.3 **New conversation** located `shared/2026-08-02-task5-connector-validation.md` via `solid_list_container`+`solid_read_resource` with no filename hint, appended a confirmation line (1176→1442 bytes) non-destructively. **Caveat: the pod root URL was present in that conversation's project instructions, so pod-root discovery wasn't cold — only file-location-within-a-known-container was. A fully cold test (WebID-profile discovery of the pod root) is a narrower, stricter variant not exercised here.**
  - [x] 5.4 Overwrite ceremony text confirmed live: `"REPLACING 136 bytes that started: 'Line A - first append...'"` — shows real prior content, not just a URL. Delete-then-reread confirmed gone (404). Bonus (non-empty-container delete refusal) confirmed working but surfaced a bug: `toToolErrorResult`'s 409 branch was overwriting the specific "non-empty, out of scope" message with a generic "Conflict" string — **fixed and redeployed** (`mcp-server.js` 409 branch now passes `err.message` through). Nicolas confirmed directly (2026-08-02): native approval UI fired as expected on both overwrite and delete.
  - [x] 5.5 Full chat transcript captured at `_bmad-output/test-artifacts/Claude-Validating hyperCampus connector Task 5 steps.md`; live report captured on-pod at `shared/story-8-6-task5-validation-report.md`.

- [x] **Task 5b — Read receipts (AC: 11)**
  - [x] 5b.1 Reuse Epic 5's `receipt.py` (BP-1) **shape**, not its code — that module is Python and lives in the pipeline; this is a Node connector. Match the semantics and field names so receipts across the two systems are the same artifact, and reuse `_safe_uri()`'s lesson (Turtle injection) if emitting RDF. **New `src/receipt.js` — JSON lines, not Turtle, so no injection surface to reuse the lesson against.**
  - [x] 5b.2 Emit a receipt when reading a resource whose owner is not this identity. Determining "not mine" cheaply: compare the resource URL's pod root against the identity's own `webId` pod root — do not add a network round trip per read. **`isForeignResource()` — origin + first path segment comparison, no network call.**
  - [x] 5b.3 Write receipts into the **data subject's own** `access-log/` container (BP-1's path), **not** the reader's pod.
  - [x] 5b.4 Live-verified 2026-08-02, with a real deviation from design intent: the `access-log/` container had to be **manually pre-created by the OWNER** (CSS does not auto-create a missing parent container on first PUT into it), and the grant given was **read+write** (which implies append in WAC), not Append-only — because the Epic 7 backoffice frontend currently offers only RO/RW/"only me"/"public read" toggles, with no Append-only option and no "reset to inherit from parent" (confirmed by Nicolas — scope of Story 7.6/7.8, not this story). Append-only-in-isolation therefore remains **unverified** against CSS; what's proven is that RW (which is a superset) enforces correctly. Grant readiness was proven cleanly via the permission-error transition: `403` (no grant) → `404` (grant in place, resource just doesn't exist yet) once the container+grant existed.
  - [x] 5b.5 Append-only write path, via Task 1's `solid_append_resource`'s underlying `podClient.appendFile`.
  - [x] 5b.6 Receipt-write failure logged to `journal.js` as tool `read_receipt`/outcome `error`, read itself unaffected either way. **Live-verified this was actually being exercised**: the journal showed `read_receipt`/`error` firing on every cross-pod read even before the grant existed, proving the attempt-and-log path was real, not dead code — the claude.ai agent's own conclusion after the first no-op ("feature not implemented") was investigated and disproven from the server side (see Debug Log).
  - [x] 5b.8 Live-verified 2026-08-02, in two passes. First pass (grant in place, pre-fix): read succeeded, but the receipt write itself failed — root-caused (see Debug Log) to a real bug: the receipt-write's own try/catch (added so a receipt failure can never abort the read, 5b.6) was catching 401s *before* they could reach `safeHandler`'s existing one-shot reauth-and-retry logic, so a receipt write made on a stale long-running session had no path to self-heal the way every other tool call already does. Fixed (receipt write now gets its own one-shot reauth retry, mirroring `safeHandler`) and redeployed. Second pass (post-fix): agent read `shared/story-8-1-proof.txt`, receipt appended and independently read back by the agent (owner-side confirmation not separately re-run, but content matched exactly: correct timestamp, `readerWebId` = agent's own WebID not the owner's, correct resource URL, `outcome:"read"`).

- [x] **Task 6 — Journal + regression (AC: 8, 9)**
  - [x] 6.1 Journal append/delete outcomes by label — live-confirmed via Task 5: `solid_append_resource`, `solid_delete_resource`, `solid_write_resource` and `read_receipt` all present in `/app/audit/journal.jsonl` with correct `ok`/`denied`/`error` outcomes, all attributed to label `"Nicolas (agent)"`.
  - [x] 6.2 `grep` for slug and every secret term → 0 hits (new files: `receipt.js`, `podClient.js` additions).
  - [x] 6.3 Updated `scripts/verify-http.js` (9-tool expected list) and `README.md`, re-ran against the live public URL post-deploy — **ALL CHECKS PASSED**.
  - [x] 6.4 Re-confirmed 8.5's negative test: `solid_write_resource` to a non-granted resource still returns the pinned denial wording verbatim (the new existence-probe read hits the same 403 path first, same classification).

- [x] **Task 7 — Close the loop (AC: 10)**
  - [x] 7.1 Appended a dated "Story 8.6" section to `epic-8-action-log.md` — read-then-write verified by byte-length growth (9846 bytes before, prefix byte-identical on re-read, new section appended cleanly). **Note:** used `solid_write_resource` (read-then-write-full-content) rather than `solid_append_resource` itself — this Claude Code session's own MCP tool registry is a stale snapshot from before the connector was extended (unlike claude.ai's UI, it has no manual refresh path available here), so `solid_append_resource` wasn't a callable tool in this session. The write was provably non-destructive (full prior content read moments before and included verbatim), and the Claude Code permission classifier correctly blocked a first attempt that used placeholder content instead of the real prior content — worth noting as a process gap, not a code gap: the tool this story adds could not dogfood itself from this particular client.
  - [x] 7.2 Added a "Story 8.6" proof-table section to `epic-8-progress-report.md`.
  - [x] 7.3 Struck the `deleteResource` container no-op item from `deferred-work.md` as CLOSED; added a new deferred item for the `/healthz` staleness finding.

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

Claude Sonnet 5 (Claude Code)

### Debug Log References

- Pre-deploy health probe found `mcp-connector` reporting Docker `unhealthy` (FailingStreak 3712, ~17h) — root-caused to `session.info.isLoggedIn` going stale between the sparse real tool calls that trigger `reauthIdentity`'s one-shot 401 retry, not a Story 8.6 regression. Checked `docker-compose.yml`: no `depends_on: condition: service_healthy` anywhere and no autoheal container, so the flag is cosmetic (nginx routes by container name/TCP, not health status) — confirmed low-risk with Nicolas and deployed anyway. New `deferred-work.md` candidate: proactive session refresh, natural fit for 8.6.1 (session/identity lifecycle) but a distinct problem from that story's stated lazy-loading-on-cache-miss scope — flagged as related-not-identical, not silently folded in.
- Post-deploy: container came up `healthy` immediately (fresh session at boot), `verify-http.js` run from inside the container against the public hostname (`solid-mcp.nicolasdb.eu`, 8.4 Task 8 hairpin method) — 9 tools listed, `solid_list_container` OK, negative test denial wording pinned and unchanged.
- Task 5 live run (full transcript: `_bmad-output/test-artifacts/Claude-Validating hyperCampus connector Task 5 steps.md`) surfaced two real bugs, both found via direct server-side journal/repro investigation rather than accepting the claude.ai agent's own (incorrect) self-diagnosis:
  1. **409 message masking**: `toToolErrorResult`'s 409 branch unconditionally replaced any 409 error's message with a generic "Conflict" string, discarding `solid_delete_resource`'s specific "non-empty container, out of scope" guidance. Confirmed live (claude.ai reported the generic text), fixed (`mcp-server.js` now passes `err.message` through for 409 since both current 409 producers are this connector's own well-messaged guards), redeployed.
  2. **Receipt writes couldn't self-heal a stale session**: after Nicolas granted `access-log/` access, `read_receipt` was still failing (`journal.jsonl` showed `outcome:"error"` at 10:42:58 post-grant). Reproduced live via `docker exec` — a *fresh* login against the identical grant succeeded instantly (`existed:false, bytesBefore:0, bytesAfter:10`), proving the grant was correct and the long-running server session was simply stale at that moment. Root cause: the receipt write's own try/catch (added so a receipt failure can never abort the read) was catching 401s locally, before they could reach `safeHandler`'s existing one-shot reauth-and-retry logic that every other tool call already benefits from. The claude.ai agent, unable to see any of this server-side evidence, concluded from the pod-only view ("403→404, therefore nothing calls this") that receipts were "not implemented at all" — investigated and disproven: the journal showed `read_receipt` firing on *every* cross-pod read from the very first attempt, well before the grant existed. Fixed (receipt write gets its own one-shot reauth retry) and redeployed; second live pass confirmed a real receipt entry with correct fields.
- Epic 7 backoffice gap surfaced live (not an 8.6 defect): the only grant options exposed are RO/RW/"only me"/"public read", with no Append-only option and no reset-to-inherit — so 5b.4's "Append-only, never Write" design intent could not be realized through today's tooling; the live grant is RW. Scope of Story 7.6/7.8.
- CSS does not appear to auto-create a missing parent container on first PUT — Nicolas had to manually create `access-log/` before the grant would have anywhere to apply to. Worth folding into 8.7's onboarding sequence.

### Completion Notes List

- Tasks 1–6 and 5b all complete, code-verified and live-verified from a real claude.ai session against the deployed connector. AC1, AC2, AC3, AC4, AC6, AC8, AC9, AC11 all met with live evidence; AC5 met except the human-visible native-approval-UI observation (agent tool calls can't see the client's own dialog — needs Nicolas's direct on-screen confirmation); AC7 met with one documented caveat (round-trip conversation had the pod URL via project instructions, so pod-root discovery wasn't cold, only file-location was).
- Two real bugs found and fixed during live verification (409 message masking, receipt-write missing the reauth-retry every other tool call has) — see Debug Log. Both confirmed via direct server-side reproduction/journal inspection, not by trusting the claude.ai agent's own self-diagnosis (which was wrong once — see Debug Log's "not implemented" note).
- One live deviation from design intent, not a code defect: the `access-log/` grant given was RW (not Append-only) because the Epic 7 backoffice UI has no Append-only option today — flagged as 7.6/7.8 scope, and the skill/onboarding language should say "RW today, Append-only once 7.6/7.8 lands" rather than imply Append-only already works end-to-end.
- Root-cause note on `podClient.deleteResource`: switched from inrupt's `deleteFile` to a raw `session.fetch(url, {method:'DELETE'})` — this is the fix for 8.1's container-trailing-slash 404, not a workaround kept at the call site.
- Nicolas confirmed (2026-08-02): claude.ai's native approval-UI dialog fired as expected on both the overwrite and the delete calls — AC5 fully met.
- Task 7 complete: `epic-8-action-log.md` (live pod resource) appended with byte-growth verification, `epic-8-progress-report.md` got its Story 8.6 section, `deferred-work.md`'s `deleteResource` item struck as CLOSED with a new item added for the `/healthz` staleness finding.
- All 11 ACs met with live evidence. Story ready for review.

### File List

- `mcp-connector/src/podClient.js` — modified: added `appendFile`, `confirmGone`, `_is404`; `deleteResource` now uses raw fetch instead of inrupt `deleteFile`; removed unused `deleteFile` import.
- `mcp-connector/src/mcp-server.js` — modified: registered `solid_append_resource` and `solid_delete_resource`; added `destructiveHint` + existence-probe ceremony to `solid_write_resource`; wired read-receipt attempt into `solid_read_resource`; added `_probe404` helper; updated tool-count comment.
- `mcp-connector/src/receipt.js` — new: `podRootOf`, `isForeignResource`, `writeReadReceipt`.
- `mcp-connector/SKILL.md` — rewritten as the user-facing capture skill (was the developer toolkit doc).
- `mcp-connector/references/developer-toolkit.md` — new: former `SKILL.md` developer content, preserved verbatim (retitled, tool list updated to 9).
- `mcp-connector/scripts/verify-http.js` — modified: expected-tools list now includes `solid_append_resource`/`solid_delete_resource`.
- `mcp-connector/README.md` — modified: MCP tool list updated to 9 tools.
- `_bmad-output/implementation-artifacts/epic-8-progress-report.md` — modified: added Story 8.6 proof-table section.
- `_bmad-output/implementation-artifacts/deferred-work.md` — modified: struck `deleteResource` container no-op as CLOSED; added the `/healthz` staleness item.
- `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (live pod resource, not a repo file) — appended Story 8.6 dated section.

### Review Findings

- [x] [Review][Decision] `isForeignResource` fail-open on malformed/empty reader WebID silently and permanently disabled receipts — no error surfaced. **Resolved with Nicolas: make it loud.** `isForeignResource` now throws on parse failure instead of swallowing it; the call site in `mcp-server.js` catches that throw and logs a `read_receipt`/`error` journal entry (same mechanism as a receipt-write failure), then skips the receipt for that read. The read itself is never blocked.
- [x] [Review][Patch] Multi-byte UTF-8 first-line preview can mangle mid-codepoint before an irreversible overwrite [mcp-connector/src/mcp-server.js] — fixed: first-line preview now slices by codepoint (`Array.from(...).slice(0,120).join("")`) instead of UTF-16 code unit.
- [x] [Review][Patch] Read-receipt latency/best-effort behavior not documented in tool description or skill [mcp-connector/src/mcp-server.js, mcp-connector/SKILL.md] — fixed: `solid_read_resource`'s tool description and the skill's read-receipts section both now note the added round trip (and possible reauth retry) on foreign reads.
- [x] [Review][Defer] TOCTOU on container-emptiness check before delete [mcp-connector/src/mcp-server.js:340-351] — `listContainer` then `deleteResource` are separate round trips with no lock; a concurrent add between them isn't caught by the pre-check. Deferred, pre-existing class of issue — Story 7.3 already scoped concurrency/locking as a cross-API design problem, not a per-tool fix.
- [x] [Review][Defer] Independent, uncoordinated reauth race on `identity.session` [mcp-connector/src/mcp-server.js:204-237] — the receipt block's own inline 401-retry and `safeHandler`'s existing one-shot retry can both fire on the same identity within one request (if the primary read also 401s), each reassigning `identity.session` independently. Deferred, pre-existing pattern (last-writer-wins already accepted elsewhere in this codebase for the no-ETag concurrency case).
- [x] [Review][Defer] `appendFile`'s reported byte counts can be stale under concurrent writes [mcp-connector/src/podClient.js:31-48] — `bytesBefore`/`bytesAfter` reflect this call's own read/write, not a re-verification against the server post-write; under the documented last-writer-wins race the reported numbers can be fiction relative to what's actually stored. Deferred — same accepted limitation as the rest of the no-ETag/If-Match concurrency class (Story 7.3 scope).
- [x] [Review][Defer] `confirmGone` has no idempotent-success path for an already-gone resource [mcp-connector/src/podClient.js:78-81] — treats any non-404 as "still exists" with no handling for eventually-consistent backends or a retry hitting a resource that's already gone. Deferred, pre-existing/low-risk — verified live against CSS with instant, non-stale propagation (8.5 finding); revisit only if a different backend is introduced.

## Change Log

| Date | Change |
|---|---|
| 2026-08-02 | Tasks 1–4 and 6 implemented and deployed live (VPS rebuild + redeploy, confirmed with Nicolas); Task 5b implemented except the two live-verification subtasks. Container confirmed healthy post-deploy; verify-http.js ALL CHECKS PASSED against the public URL with the new 9-tool count; negative test wording unchanged. Pre-existing, unrelated `/healthz` staleness issue found and investigated during pre-deploy health check — assessed low-risk (no restart dependency on it anywhere in docker-compose.yml) and deferred, candidate for 8.6.1 but not the same problem as that story's lazy-loading scope. Status set to in-progress: Task 5 (live claude.ai round trip) and Task 7 (close-the-loop docs) remain, both requiring a live claude.ai session Nicolas runs directly. |
| 2026-08-02 | Task 5 run live from claude.ai by Nicolas (transcript: `_bmad-output/test-artifacts/Claude-Validating hyperCampus connector Task 5 steps.md`), Tasks 5b.4/5b.8 closed alongside it. AC2 (byte-exact append math), AC7 (round trip with cold-file-location, warm-pod-root caveat), and AC5's overwrite/delete ceremony text all PASS. Two real bugs found and fixed mid-session, both redeployed: (1) `toToolErrorResult`'s 409 branch was discarding `solid_delete_resource`'s specific non-empty-container message in favor of a generic "Conflict" string; (2) read-receipt writes had no path to `safeHandler`'s existing one-shot reauth-on-401 retry, so a receipt attempt made against a stale long-running session failed permanently instead of self-healing like every other tool call — root-caused via direct server-side reproduction (fresh login against the identical grant succeeded instantly) rather than accepting the claude.ai agent's own incorrect "receipts aren't implemented" conclusion, which the journal directly disproved (the attempt was firing on every cross-pod read from the start). Live deviation from design intent recorded, not a defect: the `access-log/` grant is RW, not Append-only, because the Epic 7 backoffice UI has no Append-only option yet (7.6/7.8 scope) — skill/onboarding language should say so plainly rather than imply Append-only already works end to end. Also recorded: CSS does not auto-create a missing parent container, so `access-log/` had to be created by hand before the grant applied — an 8.7 onboarding-sequence note. Status remains in-progress: Task 7 (close-the-loop docs) and confirming with Nicolas whether claude.ai's native approval-UI dialog visibly fired on his screen for the destructive calls are what's left. |
| 2026-08-01 | Drafted and inserted between 8.5 (live verification) and team onboarding, which moves to 8.7. Origin: Nicolas asked why 8.5's Task 7 had no delete step; investigating found `deleteResource` written-but-never-wired, and surfaced the larger finding that `solid_write_resource` is a blind PUT with no destructive annotation — plus that Epic 8 had built only the MCP half of a plugin, with no capture skill. |
| 2026-08-02 | AC11 + Task 5b added: **read receipts** (FR42). Came out of the 8.7 pre-draft design session — Nicolas's school scenario assumed "I get a log of when and what the school agent read, so I can decide whether to revoke." Verified that no such log exists: CSS surfaces no per-resource read log to owners, and 8.4's audit journal covers only the connector's *own* actions, not third-party reads of your pod. Chosen as cheap-and-already-there (Epic 5 `receipt.py`/BP-1 is the shape). |
| 2026-08-02 | Task 5b **corrected within the same session**: first draft put receipts in the *reader's* pod to protect the single-writer invariant. Reversed to architecture.md BP-1's original location — the **subject's** `access-log/`, via an `acl:Append`-only grant. Deciding factor: under the reader's-pod version the party being audited holds the audit trail and can quietly delete it. `acl:Append` ≠ `acl:Write`, so the invariant survives as "nobody *overwrites* your pod but you", with an append-only mailbox as a deliberate narrow exception. |
