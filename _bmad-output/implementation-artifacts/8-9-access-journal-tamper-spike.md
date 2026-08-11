# Story 8.9: Access Journal — Tamper-Evidence Spike

Status: review

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

- [x] **Task 1 — Establish ground truth live (AC: 1, 2)**
  - [x] 1.1 Write `mcp-connector/scripts/probe-access-log-acl.js`, modelled on `scripts/verify-isolation.js` (same shape: argv inputs, explicit failure messages, non-zero exit on error). It must take the target pod root as an argument, never hardcode `hyperscope_ndb`.
  - [x] 1.2 Authenticate with `getAgentSession()` from `src/auth.js` — the AGENT credential, never an owner credential. This is the whole point: the probe must ask "what can the *agent* do", and an owner session would answer a different question.
  - [x] 1.3 `GET` `<podRoot>access-log/receipts.jsonl` — record status.
  - [x] 1.4 `PUT` the file's own content back to itself unchanged — record status. **Read the existing content first and write exactly those bytes back.** A 200/205 proves Write; a 403 proves Write is absent. Writing anything else risks destroying a real journal, and this pod holds real receipts.
  - [x] 1.5 `GET` `<podRoot>access-log/.acl` and `<podRoot>.acl` — record both statuses and both bodies verbatim. If `access-log/.acl` 404s, the container inherits and the pod-root `acl:default` is the governing rule.
  - [x] 1.6 Paste raw statuses and Turtle into the Dev Agent Record. No paraphrasing.

- [x] **Task 2 — Answer whether Append-only is reachable (AC: 3, 4)**
  - [x] 2.1 Confirm by reading `src/podClient.js:73-90` that `appendFile` performs `getFile` then `overwriteFile` — i.e. it needs **Read + Write**, and would break under an Append-only grant. State this explicitly in the verdict; it is the crux.
  - [x] 2.2 Evaluate **Path A — POST-per-receipt.** Instead of appending to one `receipts.jsonl`, `POST` each receipt as a new resource into `access-log/`. WAC `acl:Append` on a *container* is expected to permit creating new resources. Test it: grant the agent append-only on a scratch container, `POST` a resource, confirm 201; then attempt `PUT` over an existing one and confirm 403. Cost to weigh: the journal becomes many small resources instead of one file, which changes how the subject reads it.
  - [x] 2.3 Evaluate **Path B — RDF receipts + N3 Patch.** `acl:Append` on an RDF resource permits insert-only `PATCH`. `receipts.jsonl` is `text/plain`, so this requires the receipt format to become RDF. Cost to weigh: changes the artifact shape and diverges from Epic 5's `receipt.py` JSONL convention that `src/receipt.js:10-13` deliberately mirrors.
  - [x] 2.4 Evaluate **Path C — keep RW, describe it honestly.** Zero code cost, full honesty cost. This is a legitimate outcome, not a failure.
  - [x] 2.5 Test at least one of A or B live against a **scratch container**, never against the real `access-log/`.

- [x] **Task 3 — Confirm who can even author an Append-only ACL (AC: 3)**
  - [x] 3.1 Story 8.6 recorded that Append-only "could not be realized" because the Epic 7 backoffice offers only RO/RW/only-me/public-read. That was true of the **backoffice UI** and is not the whole picture: `src/wacManager.js` `grantAccess()` takes `{read, write, append, control}` and already supports `append: true` (`wacManager.js:92`, and `append` appears in the mode set at `:75`). Verify this end-to-end on the scratch container.
  - [x] 3.2 Note the constraint honestly: `grantAccess` needs `acl:Control`, so the **pod owner** runs it, not the agent — Story 8.1 AC4 proved the agent gets 403 doing this, and that guarantee must not be weakened to make this story easier.
  - [x] 3.3 If Append-only is reachable programmatically but not through the backoffice, say so plainly. It changes the deferral of 7.6/7.11b from "blocks Append-only" to "makes it a scripted step rather than a UI step."

- [x] **Task 4 — Decide and apply (AC: 5, 8)**
  - [x] 4.1 Record the decision with its rationale and its cost.
  - [x] 4.2 If A or B is chosen: implement it in `src/receipt.js` (and `src/podClient.js` if a new primitive is needed), then tighten the real `access-log/` grant.
  - [x] 4.3 Regression-verify: perform a cross-pod read, then read the log back and confirm the new entry — byte-growth plus content re-read.
  - [x] 4.4 If C is chosen: no code change, and Task 5 carries the whole outcome. — **N/A: Path A was chosen.** Task 5 ran anyway, since AC6's doc correction was required whatever the decision.

- [x] **Task 5 — Make every document match reality (AC: 6, 7)**
  - [x] 5.1 `docs/team-onboarding.md` lines ~26, ~97, ~128 — remove or correct the "once true Append-only / once 7.6-7.8 lands" forward references. Those stories are deferred; a promise against unscheduled work misleads the reader this page exists to be honest with.
  - [x] 5.2 `mcp-connector/SKILL.md` (~line 91) — align the receipt description with the decision.
  - [x] 5.3 `src/receipt.js` header comment (lines 1-19) — it currently describes the design intent; make it describe the shipped behaviour, with the intent noted as such if they still differ.
  - [x] 5.4 `epics.md` Story 8.9 — replace the "hypothesis, not a confirmed defect" bullet with the verified outcome.
  - [x] 5.5 `epics.md` Story 8.7 — its honest-boundaries bullet already requires stating this "as verified or as assumed, per Story 8.9's spike result". Supply the result.
  - [x] 5.6 Append a dated Story 8.9 section to the live pod action log and to `epic-8-progress-report.md`, per the Epic 8 convention (binding since 8.2).

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

claude-opus-5 (Claude Code, bmad-dev-story workflow)

### Debug Log References

All evidence below is live against `https://pod.nicolasdb.eu` on 2026-08-11. There is no staging pod; every probe was written to be non-destructive on the real journal (identical-bytes write-back, scratch container in the agent's own pod).

#### Task 1 — ground truth, AGENT credential (`scripts/probe-access-log-acl.js`)

Raw statuses, verbatim:

```
agent WebID: https://pod.nicolasdb.eu/nicolas_claude/profile/card#me
pod root:    https://pod.nicolasdb.eu/hyperscope_ndb/
timestamp:   2026-08-11T14:01:35.987Z

GET https://pod.nicolasdb.eu/hyperscope_ndb/access-log/
  status:    200 OK
  WAC-Allow: user="append read write"
  Content-Type: text/turtle

GET https://pod.nicolasdb.eu/hyperscope_ndb/access-log/receipts.jsonl
  status:    200 OK
  WAC-Allow: user="append read write"
  Content-Type: text/plain
  body bytes: 1177

PUT https://pod.nicolasdb.eu/hyperscope_ndb/access-log/receipts.jsonl   (1177 bytes, identical to what was read)
  status:    205 Reset Content

GET https://pod.nicolasdb.eu/hyperscope_ndb/access-log/receipts.jsonl
  status:    200 OK
  body bytes: 1177
  round-trip integrity: content IDENTICAL — journal intact

GET https://pod.nicolasdb.eu/hyperscope_ndb/access-log/.acl
  status:    403 Forbidden
  body: {"name":"ForbiddenHttpError","message":"","statusCode":403,"errorCode":"H403","details":{}}

GET https://pod.nicolasdb.eu/hyperscope_ndb/.acl
  status:    403 Forbidden
  body: {"name":"ForbiddenHttpError","message":"","statusCode":403,"errorCode":"H403","details":{}}
```

**AC1 answered.** `WAC-Allow: user="append read write"` is CSS's own statement of the effective grant, and the `PUT` → **205** confirms it is not merely advertised: the file's mtime moved to `2026-08-11 14:01:37` (checked on the server's file backend). The journal was genuinely rewritable by the party it audits. Content was written back byte-for-byte, so nothing was lost.

**The 403s on `.acl` are not evidence of the grant** — CSS requires `acl:Control` to read an ACL, and the agent correctly does not have it (consistent with Story 8.1 AC4). AC2 requires the actual Turtle, so it was read from the server's file backend instead:

`/data/hyperscope_ndb/access-log/.acl` (before this story changed it; preserved at `.acl.bak-8-9`):

```turtle
@prefix acl: <http://www.w3.org/ns/auth/acl#>.
@prefix foaf: <http://xmlns.com/foaf/0.1/>.

<#owner>
    a acl:Authorization;
    acl:agent <https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me>;
    acl:accessTo <./>;
    acl:default <./>;
    acl:mode acl:Read, acl:Write, acl:Control.

<#grant0>
    a acl:Authorization;
    acl:agent <https://pod.nicolasdb.eu/nicolas_claude/profile/card#me>;
    acl:accessTo <./>;
    acl:default <./>;
    acl:mode acl:Read, acl:Append, acl:Write.
```

`/data/hyperscope_ndb/.acl` (pod root, unchanged by this story):

```turtle
# Root ACL resource for the agent account
@prefix acl: <http://www.w3.org/ns/auth/acl#>.
@prefix foaf: <http://xmlns.com/foaf/0.1/>.

# The homepage is readable by the public
<#public>
    a acl:Authorization;
    acl:agentClass foaf:Agent;
    acl:accessTo <./>;
    acl:mode acl:Read.

# The owner has full access to every resource in their pod.
# Other agents have no access rights,
# unless specifically authorized in other .acl resources.
<#owner>
    a acl:Authorization;
    acl:agent <https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me>;
    acl:accessTo <./>;
    acl:default <./>;
    acl:mode
        acl:Read, acl:Write, acl:Control.
```

**AC2 answered — and it corrects a premise the story was drafted on.** `access-log/` carries its **own** `.acl`. It does **not** inherit, and pod root grants the agent **nothing**. So the RW was an explicit, deliberate leaf grant, not a cascade from root. The sprint-status worry that "the grant cascades Write" is a verified negative.

#### Task 2 + 3 — is Append-only reachable? (`scripts/probe-append-only.js`)

Run against a scratch container in the agent's **own** pod (`nicolas_claude/scratch-8-9-append/`), created and torn down by the script. It runs there deliberately: authoring an ACL needs `acl:Control`, which the agent must **not** have on a data pod (Story 8.1 AC4) — that guarantee was not weakened to make this story easier. The Append-only grant therefore targets a *different* identity, the public agent class, fetched unauthenticated. Same substitution Story 8.1 used when no second WebID was available.

`wacManager.setPublicAccess({append:true}, scope:'both')` and `grantAccess(<owner WebID>, {append:true}, scope:'both')` both returned without error, and the saved ACL reads back (`GET .acl` → 200) with `acl:Append` and **no** Read/Write/Control on any non-owner rule:

```turtle
<#9b270ea3-…> a <…acl#Authorization>;
    <…acl#mode> <…acl#Append>;
    <…acl#accessTo> <https://pod.nicolasdb.eu/nicolas_claude/scratch-8-9-append/>;
    <…acl#agentClass> <http://xmlns.com/foaf/0.1/Agent>.
<#4050b17b-…> a <…acl#Authorization>;
    <…acl#mode> <…acl#Append>;
    <…acl#default> <https://pod.nicolasdb.eu/nicolas_claude/scratch-8-9-append/>;
    <…acl#agentClass> <http://xmlns.com/foaf/0.1/Agent>.
```

Behaviour under that grant — **8/8**:

| Probe | Expected | Actual |
|---|---|---|
| `acl:Append` present in the authored ACL | true | true |
| no Write/Read/Control leaked into non-owner rules | 0 | 0 |
| **Path A** — `POST` a new resource into the container | 201 | **201** |
| **Path A** — `PUT` over an existing resource (tamper) | denied | **401** |
| **Path A** — `GET` an existing resource (Append implies no Read) | denied | **401** |
| **Path A** — `DELETE` an existing resource | denied | **401** |
| **Path B** — insert-only N3 `PATCH` on an RDF resource | success | **205** |
| **Path B** — `PATCH` carrying `deletes` (tamper) | denied | **401** |

**AC3 and AC4 answered: both Path A and Path B work.** The decisive detail is the *asymmetry within one identity* — the same anonymous party got **205** on an insert-only PATCH and was refused on a deleting PATCH against the same resource. That rules out "everything unauthenticated is just blocked" and proves CSS evaluates modes per-operation.

Two probe-authoring corrections worth recording, since both would mislead a future reader of these scripts:

- **CSS answers an *unauthenticated* denial with 401, not 403.** Both are denials; which one comes back depends on whether credentials were presented, not on the mode. Confirmed by the Task 4 re-run below, where an *authenticated* identity under the same Append-only grant got **403** on all four operations.
- **CSS returns 205 on a successful write**, not 200. The first run's "failures" were the assertions being wrong, not the server.

**Task 3 conclusion:** Append-only was never blocked by the protocol. `wacManager.grantAccess()` has accepted `append:true` all along. Story 8.6's attribution to "7.6/7.8 scope" described a **UI** gap. That changes the meaning of the 7.6/7.11b deferral from "blocks Append-only" to "makes it a scripted step rather than a UI step" — recorded in `epics.md` and in `team-onboarding.md`, which now tells the reader plainly that this one step is not self-service.

#### Task 4 — regression, before and after (`scripts/verify-receipt-appendonly.js`)

Evidence standard is Story 8.6's — container listing growth **plus** content read-back — not "the call returned 201".

**Before tightening** (agent still RW), target `hyperscope_ndb/shared/claude-access-test.md` — 7/7:

```
PASS  target is a foreign resource (a receipt is owed at all)
PASS  cross-pod READ succeeded — 1196 chars
PASS  receipt POST accepted — status 201, url …/access-log/2026-08-11T14-33-40-314Z-0gk3x2.json
PASS  container listing grew — 573 -> 876 bytes
PASS  new receipt appears in the container listing
PASS  receipt reads back — status 200
PASS  receipt is valid JSON with the expected fields
  {
    "ts": "2026-08-11T14:33:40.314Z",
    "reader": "verify-8-9",
    "readerWebId": "https://pod.nicolasdb.eu/nicolas_claude/profile/card#me",
    "resource": "https://pod.nicolasdb.eu/hyperscope_ndb/shared/claude-access-test.md",
    "outcome": "read",
    "underGrant": null
  }
```

**After tightening** the real `access-log/` to `acl:Append` only — 7/7:

```
GET …/access-log/ (before) -> 403
PASS  cross-pod READ succeeded — 1196 chars
PASS  receipt POST accepted — status 201, url …/access-log/2026-08-11T14-34-42-766Z-96rmxu.json
GET …/access-log/ (after)  -> 403
PASS  container listing DENIED (agent no longer holds Read) — status 403
PASS  reading back its own receipt DENIED — status 403
PASS  overwriting its own receipt DENIED (the tamper attempt) — status 403
PASS  deleting its own receipt DENIED — status 403
```

**AC8 satisfied.** Confirmed independently on the server's file backend — both receipts present, and the pre-existing journal untouched at its original 1177 bytes:

```
-rw-r--r--  1499  Aug 11 14:34  .acl
-rw-r--r--   491  Aug 11 14:33  .acl.bak-8-9
-rw-r--r--   269  Aug 11 14:33  2026-08-11T14-33-40-314Z-0gk3x2.json
-rw-r--r--   269  Aug 11 14:34  2026-08-11T14-34-42-766Z-96rmxu.json
-rw-r--r--  1177  Aug 11 14:01  receipts.jsonl$.txt
```

The two `verify-8-9` receipts were left in place. They record reads that genuinely happened; deleting them to tidy up would be exactly the rewriting-of-history this story exists to prevent.

### Completion Notes List

**Decision (AC5): Path A — POST-per-receipt, with the grant tightened to `acl:Append`.**

Rationale, and it is not the one the story anticipated. The story framed the choice as JSON-vs-RDF and warned that Path A "diverges from Epic 5's `receipt.py` JSONL convention". That is backwards: `receipt.py:271` already writes **one Turtle resource per receipt** into `access-log/{timestamp_slug}.ttl`. Path A *converges* the two systems on shape; the single-file JSONL in `receipt.js` was the outlier.

The real axis, surfaced by Nicolas during the spike: **format is reversible and the tamper property is not.** A consolidation job can later fold JSON receipts into triples, SQLite, or one rolled-up file. What no later job can recover is (a) a receipt written while its writer held Write — untrustworthy forever — or (b) a receipt's link to the grant it was made under, which timestamp correlation can only guess at. So the decision was made on what must be captured at write time, and Path B's RDF-ness was set aside as something the consolidation step can add for free.

**Its cost, stated:** the journal becomes many small resources, so reading it means listing a container rather than reading one file. The agent also loses **Read** on `access-log/` — a privacy gain (it can no longer see other readers' entries) that forecloses any future design needing the agent to read receipts back.

**What it does not solve** — three limits, all carried into every document updated in Task 5:

1. Still a **voluntary convention**. CSS surfaces no server-side per-resource read log, so a reader that simply declines to write receipts leaves no trace. Append-only makes the cooperative path trustworthy; it does not make the record complete.
2. It constrains the **reader, not the pod owner**, who holds `acl:Control` over their own `access-log/` and can edit it. That follows from BP-1 — evidence must land where the audited party cannot retract it — and is the price of putting it in the subject's pod.
3. A receipt records that a read **happened**, never what was done with the data afterwards.

**Applied:** `podClient.postResource()` added (the write an Append-only grant permits; `appendFile` is kept for non-journal use with the constraint documented at both sites). `receipt.js` POSTs one JSON receipt per read and reserves an `underGrant` field — explicitly `null` rather than omitted, so a later reader can distinguish "no grant recorded" from "predates the field". The live `access-log/` grant is now `acl:Append` only, previous ACL preserved at `.acl.bak-8-9`, and the pre-existing `receipts.jsonl` left in place as history.

**Invalidated assumptions, confirmed or corrected:**

- ✅ *"The fix is a grant correction"* — correct that it is not. `appendFile` needs Read+Write; the grant and the write path moved together.
- ✅ *"Append-only is blocked by the backoffice UI"* — corrected. Blocked the self-service path only; `grantAccess({append:true})` works.
- ✅ *"Container scoping was never verified for `access-log/`"* — now verified, and it produced a **new** finding: `access-log/` has its own leaf `.acl` and pod root grants the agent nothing, so no Write ever cascaded.
- ❌ *"Path A diverges from Epic 5's JSONL convention"* — **wrong, and inverted.** Epic 5 already does Path A.

**Testing note (deliberate, per the story's Testing Requirements):** no unit tests were added. `mcp-connector` has no test harness (`npm test` is the stock "no test specified" stub), and a mock cannot prove anything about CSS's WAC evaluation — which is the entire subject of this story. Evidence is live HTTP status codes recorded verbatim, matching Epic 8's standard since 8.1. `node --check` passed on every new and modified file. The three probe scripts are re-runnable and are the regression suite for this behaviour.

**Scope held.** The detection half (anomaly signals, alerting, identity-level rate limiting) stayed in `post-poc-backlog.md`; per-slug attribution stayed with Story 7.9. Neither was built.

**Out-of-scope reframing, carried to a sprint change proposal (Nicolas, 2026-08-11).** Receipts exist to inform a *permission decision* — they are the audit half of a consent loop (request → review → grant → audit → revoke), not a standalone log. The UX inversion: access is requested with justification (who, what, why, what if refused) and reviewed, rather than granted preemptively. `poc:ConsentGrant` already ships that vocabulary (Story 5.5) but only in the pipeline; the connector knows nothing of it, and request intake does not exist — the backoffice "Requests" tab is a hardcoded stub, known since 7.2. This reframes Story 7.9, which owns the grant table, so it needs a real decision rather than a backlog line. The `underGrant` field reserved above is the one piece of it that had to be captured now.

**Deployed and verified end-to-end (2026-08-11, 16:35 UTC).** `make vps-deploy` initially refused on the Story 8.4 guard — `deleting mcp-connector/audit/`. Investigated rather than forced: the live audit journal is in the `mcp-audit` **named volume**, and the host path is an empty leftover, so `FORCE=1` would have been harmless this time. Excluded it in the Makefile anyway — a guard that cries wolf on a known-safe path every deploy is one that gets `FORCE`d reflexively, and the next refusal might be `identities.json`.

After deploy, a real `tools/call solid_read_resource` against the deployed endpoint (not the library directly) on a foreign resource:

```
cross-pod read isError: false | chars: 1196
access-log/2026-08-11T16-35-31-868Z-aonuvr.json   274 bytes   (new receipt)
audit journal: {"ts":"2026-08-11T16:35:31.976Z","label":"Nicolas (agent)","tool":"solid_read_resource","resource":"…/shared/claude-access-test.md","outcome":"ok"}
```

The receipt landed under the tightened grant, through the deployed code, via the real MCP path. No `read_receipt` error entry in the connector's own journal — which is exactly how a receipt failure would surface. AC8 closed against production, not just against the library.

**Incidental finding, not fixed here:** `scripts/verify-http.js` defaults to `http://127.0.0.1:3939/mcp` and its docstring instructs "connect via 127.0.0.1, not localhost or a LAN IP". That advice is now stale — Story 8.4 set `ALLOWED_HOSTS=solid-mcp.nicolasdb.eu,mcp-connector:3939,mcp-connector`, so `127.0.0.1` is rejected with `Invalid Host` and the script cannot run as documented. Reaching it in-container needs `http://mcp-connector:3939/…`. A stale runbook that fails looking like a protocol error — logged for a follow-up, out of scope for this spike.

### File List

**New**
- `mcp-connector/scripts/probe-access-log-acl.js` — Task 1 ground-truth probe (AC1, AC2)
- `mcp-connector/scripts/probe-append-only.js` — Tasks 2+3 feasibility probe (AC3, AC4)
- `mcp-connector/scripts/verify-receipt-appendonly.js` — Task 4.3 regression, before/after (AC8)

**Modified**
- `mcp-connector/src/podClient.js` — added `postResource()`, exported it
- `mcp-connector/src/receipt.js` — POST-per-receipt, `underGrant` reserved, header rewritten to describe shipped behaviour and the three limits (Task 5.3)
- `mcp-connector/SKILL.md` — receipt section rewritten (Task 5.2, AC6)
- `mcp-connector/references/developer-toolkit.md` — `receipt.js` entry updated
- `docs/team-onboarding.md` — stale "once 7.6/7.8 lands" references removed; Append-only described as live, with the not-self-service caveat and the owner-can-still-edit limit (Task 5.1, AC6)
- `_bmad-output/planning-artifacts/epics.md` — Story 8.9 outcome recorded; Story 8.7 honest-boundaries bullet now states the property as verified (Tasks 5.4, 5.5, AC7)
- `_bmad-output/implementation-artifacts/epic-8-progress-report.md` — Story 8.9 section appended (Task 5.6)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions
- `_bmad-output/implementation-artifacts/8-9-access-journal-tamper-spike.md` — this record

**Changed live (not in git)**
- `hyperscope_ndb/access-log/.acl` on `pod.nicolasdb.eu` — tightened to `acl:Append` for the agent; previous version preserved as `.acl.bak-8-9`
- `nicolas_claude/epic-8-action-log.md` — Story 8.9 section appended (Task 5.6, Epic 8 convention)

### Change Log

| Date | Change |
|---|---|
| 2026-08-11 | Task 1: probed `access-log/` live with the AGENT credential. Confirmed Write is held (`PUT` → 205, mtime moved) and that the container carries its **own** `.acl` — pod root grants the agent nothing, so no Write cascaded. |
| 2026-08-11 | Tasks 2+3: verified live that Append-only is reachable — Path A (POST → 201, PUT/GET/DELETE denied) and Path B (insert-only PATCH → 205, deleting PATCH denied), 8/8. Confirmed `wacManager.grantAccess({append:true})` authors it end-to-end; the Epic 7 backoffice gap blocked self-service only. |
| 2026-08-11 | Task 4: decided Path A. Added `podClient.postResource()`; `receipt.js` now POSTs one JSON receipt per read with a reserved `underGrant` field; tightened the live `access-log/` grant to `acl:Append`. Regression 7/7 before and after — the agent is now denied listing, read-back, overwrite and delete of its own receipt. |
| 2026-08-11 | Task 5: corrected `team-onboarding.md`, `SKILL.md`, `developer-toolkit.md`, `receipt.js`'s header and `epics.md` (8.9 outcome + 8.7 honest-boundaries as verified). Appended the Story 8.9 section to the live pod action log and to `epic-8-progress-report.md`. |
| 2026-08-11 | Deployed to VPS and verified end-to-end: cross-pod read through the deployed MCP endpoint produced a receipt under the Append-only grant, with no receipt-failure entry in the connector's journal. Makefile gained a `mcp-connector/audit/` rsync exclude so the 8.4 deploy guard stops firing on a known-safe path. |
