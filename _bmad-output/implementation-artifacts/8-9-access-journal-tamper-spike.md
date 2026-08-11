# Story 8.9: Access Journal — Tamper-Evidence Spike

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a pod owner whose `access-log/` receives read receipts from other people's agents,
I want to know whether those agents can also **rewrite** that log — and, if they can, whether Append-only is even reachable given how receipts are written today,
so that the journal is either a trustworthy record or honestly described as something less, and never quietly assumed to be the former.

## Context — read this before planning any work

**This is a spike, not a feature.** Timebox: one working session. The deliverable is a decision plus evidence, not a subsystem. The detection half of the original Story 8.9 (anomaly signals, operator alerting, identity-level rate limiting) was moved to `post-poc-backlog.md` on 2026-08-11 and is **out of scope** — do not build it. Per-slug attribution moved to Story 7.9 and is also **out of scope here**.

**The framing in `epics.md` is out of date and this story supersedes it.** The epic entry calls the tamper question "a hypothesis, not a confirmed defect." Story 8.6 already answered it. See Invalidated Assumptions below — the answer is known, and the genuinely open question is a different one.

## Acceptance Criteria

1. **The current effective grant on `access-log/` is confirmed live, with evidence, not inherited from a prior story's notes.** Using the AGENT credential, an overwrite (`PUT`) against an existing `receipts.jsonl` is attempted and the HTTP status recorded; a read (`GET`) is attempted and the status recorded. The raw `.acl` governing `access-log/` is fetched and included verbatim in the story's Dev Agent Record.

2. **The `access-log/` container's ACL provenance is established:** whether it carries its own `.acl` or inherits `acl:default` from pod root, and — if inherited — what the parent actually grants. Recorded as a URL plus the Turtle that was read, not as a summary.

3. **The "can it be Append-only?" question is answered against the real write path, not in principle.** The answer must account for `podClient.appendFile` being a **read-then-overwrite**, not a protocol-level append (see Dev Notes). A written verdict states, for each of the three candidate paths below, whether it works, and on what evidence.

4. **At least one candidate Append-only path is tested live against the pod**, not reasoned about on paper. A negative result is a valid outcome and is recorded as such — the AC is that a real request was made and its status recorded, not that Append-only was achieved.

5. **A decision is recorded and applied**, chosen from: (a) migrate receipts to an Append-only-compatible write path and tighten the grant; (b) keep RW and state it honestly everywhere the system's guarantees are described; (c) a hybrid. The decision names its own cost and what it does not solve.

6. **Every user-facing document that describes this property matches the decision.** `docs/team-onboarding.md` and `mcp-connector/SKILL.md` currently promise Append-only "once 7.6/7.8 lands" — both of those stories were deferred to post-PoC on 2026-08-11, so that forward reference is now a promise against work that is not scheduled. It must be corrected regardless of which decision is taken.

7. **Story 8.7's honest-boundaries section states the outcome as verified**, replacing any assumed or forward-looking language about the journal's tamper properties.

8. **No regression in receipt writing.** After any change, a cross-pod read still produces a receipt entry in the subject's `access-log/`, verified by reading the log back — the same evidence standard Story 8.6 used (byte-length growth plus content re-read, not assumption).

## Tasks / Subtasks

- [ ] **Task 1 — Establish ground truth live (AC: 1, 2)**
  - [ ] 1.1 Write `mcp-connector/scripts/probe-access-log-acl.js`, modelled on `scripts/verify-isolation.js` (same shape: argv inputs, explicit failure messages, non-zero exit on error). It must take the target pod root as an argument, never hardcode `hyperscope_ndb`.
  - [ ] 1.2 Authenticate with `getAgentSession()` from `src/auth.js` — the AGENT credential, never an owner credential. This is the whole point: the probe must ask "what can the *agent* do", and an owner session would answer a different question.
  - [ ] 1.3 `GET` `<podRoot>access-log/receipts.jsonl` — record status.
  - [ ] 1.4 `PUT` the file's own content back to itself unchanged — record status. **Read the existing content first and write exactly those bytes back.** A 200/205 proves Write; a 403 proves Write is absent. Writing anything else risks destroying a real journal, and this pod holds real receipts.
  - [ ] 1.5 `GET` `<podRoot>access-log/.acl` and `<podRoot>.acl` — record both statuses and both bodies verbatim. If `access-log/.acl` 404s, the container inherits and the pod-root `acl:default` is the governing rule.
  - [ ] 1.6 Paste raw statuses and Turtle into the Dev Agent Record. No paraphrasing.

- [ ] **Task 2 — Answer whether Append-only is reachable (AC: 3, 4)**
  - [ ] 2.1 Confirm by reading `src/podClient.js:73-90` that `appendFile` performs `getFile` then `overwriteFile` — i.e. it needs **Read + Write**, and would break under an Append-only grant. State this explicitly in the verdict; it is the crux.
  - [ ] 2.2 Evaluate **Path A — POST-per-receipt.** Instead of appending to one `receipts.jsonl`, `POST` each receipt as a new resource into `access-log/`. WAC `acl:Append` on a *container* is expected to permit creating new resources. Test it: grant the agent append-only on a scratch container, `POST` a resource, confirm 201; then attempt `PUT` over an existing one and confirm 403. Cost to weigh: the journal becomes many small resources instead of one file, which changes how the subject reads it.
  - [ ] 2.3 Evaluate **Path B — RDF receipts + N3 Patch.** `acl:Append` on an RDF resource permits insert-only `PATCH`. `receipts.jsonl` is `text/plain`, so this requires the receipt format to become RDF. Cost to weigh: changes the artifact shape and diverges from Epic 5's `receipt.py` JSONL convention that `src/receipt.js:10-13` deliberately mirrors.
  - [ ] 2.4 Evaluate **Path C — keep RW, describe it honestly.** Zero code cost, full honesty cost. This is a legitimate outcome, not a failure.
  - [ ] 2.5 Test at least one of A or B live against a **scratch container**, never against the real `access-log/`.

- [ ] **Task 3 — Confirm who can even author an Append-only ACL (AC: 3)**
  - [ ] 3.1 Story 8.6 recorded that Append-only "could not be realized" because the Epic 7 backoffice offers only RO/RW/only-me/public-read. That was true of the **backoffice UI** and is not the whole picture: `src/wacManager.js` `grantAccess()` takes `{read, write, append, control}` and already supports `append: true` (`wacManager.js:92`, and `append` appears in the mode set at `:75`). Verify this end-to-end on the scratch container.
  - [ ] 3.2 Note the constraint honestly: `grantAccess` needs `acl:Control`, so the **pod owner** runs it, not the agent — Story 8.1 AC4 proved the agent gets 403 doing this, and that guarantee must not be weakened to make this story easier.
  - [ ] 3.3 If Append-only is reachable programmatically but not through the backoffice, say so plainly. It changes the deferral of 7.6/7.11b from "blocks Append-only" to "makes it a scripted step rather than a UI step."

- [ ] **Task 4 — Decide and apply (AC: 5, 8)**
  - [ ] 4.1 Record the decision with its rationale and its cost.
  - [ ] 4.2 If A or B is chosen: implement it in `src/receipt.js` (and `src/podClient.js` if a new primitive is needed), then tighten the real `access-log/` grant.
  - [ ] 4.3 Regression-verify: perform a cross-pod read, then read the log back and confirm the new entry — byte-growth plus content re-read.
  - [ ] 4.4 If C is chosen: no code change, and Task 5 carries the whole outcome.

- [ ] **Task 5 — Make every document match reality (AC: 6, 7)**
  - [ ] 5.1 `docs/team-onboarding.md` lines ~26, ~97, ~128 — remove or correct the "once true Append-only / once 7.6-7.8 lands" forward references. Those stories are deferred; a promise against unscheduled work misleads the reader this page exists to be honest with.
  - [ ] 5.2 `mcp-connector/SKILL.md` (~line 91) — align the receipt description with the decision.
  - [ ] 5.3 `src/receipt.js` header comment (lines 1-19) — it currently describes the design intent; make it describe the shipped behaviour, with the intent noted as such if they still differ.
  - [ ] 5.4 `epics.md` Story 8.9 — replace the "hypothesis, not a confirmed defect" bullet with the verified outcome.
  - [ ] 5.5 `epics.md` Story 8.7 — its honest-boundaries bullet already requires stating this "as verified or as assumed, per Story 8.9's spike result". Supply the result.
  - [ ] 5.6 Append a dated Story 8.9 section to the live pod action log and to `epic-8-progress-report.md`, per the Epic 8 convention (binding since 8.2).

## Dev Notes

### The finding that reframes this story

`podClient.appendFile()` (`src/podClient.js:73-90`) is a **read-then-overwrite**, not a protocol append:

```js
const file = await getFile(url, { fetch: session.fetch });   // needs Read
...
await overwriteFile(url, Buffer.from(combined, "utf-8"), ...); // needs Write
```

`src/receipt.js:60` calls exactly this. So the receipt write path structurally requires **Read + Write** on `access-log/receipts.jsonl`. An `acl:Append`-only grant would not tighten the journal — it would stop receipts working entirely.

This is why the story is not "fix the grant." Changing the grant without changing the write path breaks Story 8.6's shipped behaviour. The two must move together or not at all.

### What Story 8.6 already established (do not re-derive)

- The `access-log/` grant given live is **RW, not Append-only** — recorded as a deliberate, documented deviation from design intent, not a defect (`8-6-capture-surface-and-skill.md:109`, `:212`, `:219`).
- The reason recorded at the time: the Epic 7 backoffice exposes only RO / RW / "only me" / "public read", with no Append-only toggle and no reset-to-inherit. Attributed to "Story 7.6/7.8 scope."
- **Append-only in isolation has never been verified against CSS.** What is proven is that RW enforces correctly — a superset. So even the positive claim is untested at the mode this story cares about.
- CSS does **not** auto-create a missing parent container on first `PUT` into it; `access-log/` had to be created by hand by the owner (`:213`). Relevant if the spike creates a scratch container.
- Grant readiness was proven by a permission-error *transition*: `403` (no grant) → `404` (grant in place, resource absent). Reuse this technique — it distinguishes "not allowed" from "not there," which a bare 404 does not.

### Why the deferral of 7.6 / 7.11b matters here

On 2026-08-11 Story 7.6 was deferred to post-PoC and Story 7.8 (now 7.11b) was likewise deferred. Story 8.6's honest note and `docs/team-onboarding.md` both point at those stories as the thing that would deliver Append-only. **That forward reference is now stale in a way that misleads**: the page tells a newcomer their journal will become tamper-evident "once 7.6/7.8 lands," and neither is scheduled. AC6 exists because of this. Correcting it is required whichever technical decision is taken.

Task 3 may also change the deferral's meaning: if `wacManager.grantAccess({append: true})` works, Append-only was never actually blocked on the backoffice UI — only its *self-service* form was.

### Architecture constraints that must not be weakened

- **BP-1 (bidirectional accountability):** receipts land in the **data subject's** pod, never the reader's. `receipt.js:24-28` (`podRootOf`) implements this and `prd.md` FR42 was corrected on 2026-08-11 to match. Do not "simplify" by moving receipts to the reader's pod — that inversion was explicitly reversed in Story 8.6 (`:256`) because the audited party would then hold their own audit trail.
- **BP-6 (single-writer pods):** the append-only mailbox is a *deliberate narrow exception* to "nobody writes your pod but you." Any Path-A/B design must keep it narrow — an exception scoped to `access-log/`, not a general write grant.
- **The agent never self-grants.** Story 8.1 AC4 proved `grantAccess` on a foreign pod root returns 403 for the agent. Task 3 runs grants as the **owner**. If a proposed design needs the agent to widen its own access, the design is wrong.
- **SEC-4 (`architecture.md`):** credential-at-rest risk is accepted for the PoC. Nothing in this story changes that, and the honest-boundaries text in Task 5 should not imply that a tamper-evident journal compensates for it.

### Honest limit that survives every outcome

Receipts are a **voluntary convention**, not enforcement. CSS surfaces no server-side per-resource read log, so a reader that simply declines to write receipts leaves no trace by this mechanism. This is already stated in `receipt.js:15-18`, `SKILL.md`, and the tool description. Making the journal tamper-evident does **not** make it complete, and no document updated in Task 5 may blur that line.

### Invalidated Assumptions

- **Assumption:** `epics.md` Story 8.9 — "whether the grant cascades Write is unknown; this framing is a hypothesis, not a confirmed defect." → **Reality:** Story 8.6 confirmed live on 2026-08-02 that the grant is RW. The journal *is* currently rewritable by the agent that writes to it. This was known, documented, and disclosed to users — not an unexamined assumption. The genuinely open question is narrower and harder: **can it be Append-only at all**, given the read-then-overwrite write path?
- **Assumption:** the fix is a grant correction. → **Reality:** a grant correction alone breaks receipts, because `appendFile` needs Read + Write. Grant and write path must change together.
- **Assumption (Story 8.6, `:212`):** Append-only is blocked because the backoffice UI offers no such toggle. → **Reality (to verify in Task 3):** `wacManager.grantAccess()` accepts `append: true` programmatically. The backoffice gap blocks the *self-service* path, not the capability. Do not treat the UI gap as a protocol limitation.
- **Assumption:** "7.6/7.8 will deliver this." → **Reality:** both were deferred to post-PoC on 2026-08-11 (`post-poc-backlog.md`). Any document promising Append-only on their arrival is now misleading.
- **Assumption (brief §15, carried into the SCP):** container scoping was verified. → **Reality:** §15 verified `shared/`. `access-log/` is a *different* container at pod root and was never covered. Task 1.5 covers it properly.

### Project Structure Notes

- New probe script → `mcp-connector/scripts/probe-access-log-acl.js`, alongside `verify-isolation.js` and `verify-http.js`. Add an npm script only if it takes no required arguments; these verify scripts are invoked directly with argv today, and that pattern should hold.
- Receipt logic stays in `src/receipt.js`; any new write primitive belongs in `src/podClient.js` next to `appendFile`, not inlined into `receipt.js` — `podClient` is the shared library surface (Hermes consumes it too, per `appendFile`'s own note at `:64-66`).
- Credentials come from `mcp-connector/.env` via `auth.js`'s path-explicit `dotenv.config()` (`auth.js:26`) — it does **not** resolve relative to `cwd`. Run scripts from anywhere, but do not add a bare `dotenv.config()`.
- Live target is `https://pod.nicolasdb.eu`. There is no staging pod. Task 1.4's write-back-identical-bytes rule and Task 2.5's scratch-container rule exist because of this — the journal being probed holds real receipts.

### Testing Requirements

- **Live evidence over unit tests.** This is a spike against a real server's authorization behaviour; a mock proves nothing about CSS's WAC evaluation. Epic 8's standard throughout has been live verification with raw statuses recorded (see 8.1–8.6).
- Record HTTP status codes verbatim. The `403 → 404` transition technique from 8.6 is the reliable way to distinguish "denied" from "absent."
- Regression check for AC8 uses Story 8.6's evidence standard: byte-length growth **plus** content re-read. Not "the call returned 200."
- Node `node --check` on any new script before running it against the live pod, per Epic 8 practice.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 8.9] — story scope after the 2026-08-11 split
- [Source: `_bmad-output/planning-artifacts/architecture.md#Decision SEC-4] — credential-at-rest risk acceptance
- [Source: `_bmad-output/planning-artifacts/prd.md#FR42] — receipt location, corrected 2026-08-11
- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-11.md#8] — party-mode addendum, why this story runs first
- [Source: `_bmad-output/implementation-artifacts/8-6-capture-surface-and-skill.md:109,212,213,219,256] — the RW deviation, the container-creation finding, the BP-1 reversal
- [Source: `mcp-connector/src/podClient.js:73-90] — `appendFile` read-then-overwrite
- [Source: `mcp-connector/src/receipt.js:50-61] — receipt write path
- [Source: `mcp-connector/src/wacManager.js:75,92] — `append` mode support in `grantAccess`
- [Source: `mcp-connector/scripts/verify-isolation.js] — probe script shape to follow
- [Source: `docs/team-onboarding.md:26,97,128] — stale forward references to 7.6/7.8

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
