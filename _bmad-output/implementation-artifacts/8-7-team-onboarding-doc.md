# Story 8.7: Team Onboarding — Your Pod, Your Agent, Your Grants

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a teammate who has been told "you should put your notes in a pod"**,
I want a short page that explains what I actually own, walks me from zero to a working connector in my Claude app, and tells me honestly what the system does and does not guarantee,
so that I can start capturing into my own pod without needing Nicolas on a call — and without mistaking a convention for an enforcement.

## Context / Why now

Epic 8 has run at **one identity** (Nicolas) since 8.2, deliberately — no orphan CSS accounts, no multi-person complexity while the connector was still being proven. 8.5 verified the connector live from claude.ai. 8.6 completes the capture surface and writes the capture skill. 8.7 is where a **second real person** walks the path, and the artifact is the page that lets them.

Two things make this more than a checklist.

**First, the model has to be legible before the steps make sense.** A person who thinks the pod is "a folder Nicolas gave me" will misunderstand every subsequent step — especially why they, not Nicolas, hold the OWNER credential, and why their agent is a separate identity they grant into rather than a login. The conceptual frame settled 2026-08-02 (architecture.md BP-6) is short enough to fit on the same page as the steps, and without it the steps are cargo cult.

**Second, this story inherits an honesty obligation.** 8.5 and 8.6 both test what claude.ai *actually does* with `destructiveHint` annotations rather than assuming. 8.6 adds read receipts that are a voluntary convention, not enforcement. 8.7 is where those findings meet a human who will make decisions based on them. Overstating any of it here is worse than not shipping the page.

Scope boundary:
- **8.6 (before this):** append/ceremony/delete tools + the capture skill + read receipts. Code.
- **8.7 (this):** the human-facing onboarding page, walked end-to-end by a real second person. Prose + one live proof.
- **7.9 (after this):** backoffice-minted credentials, which collapses steps 4–6 of this page into a button.
- **7.8 (after this):** roles-and-grants UI, which is what makes the model manageable past a handful of people.

Do not build the backoffice minting flow here. Do not build a roles UI here.

## Design decisions settled before drafting (2026-08-02 — implement, don't re-litigate)

Walked as a concrete multi-layer scenario (student → course → school → region) rather than argued abstractly. Full record in architecture.md BP-6 and the amended BP-1/BP-2.

| Decision | Consequence for this page |
|---|---|
| **Nobody overwrites your pod but your own AGENT** | The page leads with this. Everything else is a grant you hold on someone else's pod. |
| One deliberate exception: **append-only mailboxes** (`acl:Append` ≠ `acl:Write`) | Explain it where read receipts are explained, not as a footnote — it is why the receipt log works. |
| **Three identity classes** — personal agent / collective service agent / role-assigned control | Name all three so the model is legible; the walkthrough covers **personal only**. |
| **Roles are named grant bundles**, not identities | Mentioned as the model; the UI for it is Story 7.8, so say "today this is manual". |
| **Anonymization at the ownership boundary**, not as a query filter | One paragraph — it is the reason a collective can serve a region without exposing anyone. |
| **What scales is grants, not credentials** | The answer to "can't we just share one agent login?" — which will be asked. Answer it on the page. |
| Connector = **first line of conscious input** | Frame the whole page this way. This is deliberate capture, not ambient collection. |
| Slug minting stays **manual** for now | Document today's real path honestly; note 7.9 is coming so the page won't need a rewrite. |

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| Public connector endpoint | `https://solid-mcp.nicolasdb.eu/mcp/<slug>` | 8.4/8.5 live |
| Slug generation | `npm run slug` → `scripts/gen-slug.js`, 16 CSPRNG bytes base64url = 22 chars | 8.3 AC6 |
| Identity map | `mcp-connector/identities.json`, gitignored, **chmod 600 enforced at boot** (refuses group/other-readable) | `identityRegistry.js`, 8.5 Task 6.2 |
| Identity map shape | `slug → { label, webId, clientId, clientSecret }` | `identities.example.json` |
| Uniqueness guard | Two slugs pointing at the same `webId` are **refused at boot** | 8.5 Task 6.1 |
| Sessions | Boot-time singletons for the configured roster; a slug added after boot is now lazily logged in on its first request — **no restart needed** (8.6.1, landed 2026-08-02) | `mcp-server.js` |
| claude.ai connector dialog | **No request-headers field** (verified 2026-07-30) — this is the entire reason the slug exists | brief T2 |
| Approval prompts on `destructiveHint` | claude.ai fired **two** layers live (Claude's own text pause + native approval UI) before a destructive call | 8.5 Task 7 |
| Pod URL discoverability | Claude **cannot guess** a pod root URL; asked cold before any tool call worked | 8.5 live finding |
| Credential minting UI | Story 7.4 shipped mint/list/revoke client-credentials with one-time secret reveal | 7.4 |
| Write→read propagation | 335 ms write, byte-exact read back 1 ms later, 0 staleness over 5 reads | 8.5 |
| ACL precision | Resource-level `.acl` overrides a container grant — a granted container can still contain denied resources | 8.5 live |
| Per-resource read log from CSS | **Does not exist.** 8.4's journal covers the connector's own actions only | verified 2026-08-02 |
| Missing parent container | **CSS does not auto-create one.** Granting access to `access-log/` 404s until the container exists — it had to be hand-created before the grant worked | 8.6 session finding, 2026-08-02 |
| Backoffice grant granularity | **No Append-only option.** Only RO / RW / only-me / public-read exist — any new person's `access-log/` grant is **RW**, not Append-only, until 7.6/7.8 land | 8.6 session finding, 2026-08-02 |

## Acceptance Criteria

1. **The page leads with the model, not the steps.** A reader who stops after the first screen can correctly state: they are OWNER of their own account; their agent is a separate identity they grant into; nobody overwrites their pod but their own agent; everything else is a grant they can audit and revoke. Under 400 words for this section.

2. **The three identity classes are named** (personal agent / collective service agent / role-assigned control) with one line each on who holds the credential and what it does. The walkthrough that follows is explicitly scoped to the **personal** case.

3. **"Why can't we all share one agent login?" is answered on the page**, because it will be asked. The answer is concrete — shared secret = skeleton key across everyone's granted data, no per-human write attribution, full rotation whenever one person leaves — and states the alternative: *what scales is grants, not credentials.*

4. **The walkthrough is complete and literally followable by someone who has never seen the system**, covering, in order: (a) create a CSS account at `pod.nicolasdb.eu` — you are OWNER; (b) create your data pod; (c) create your agent pod (its own WebID on the same account); (d) mint AGENT client-credentials via the backoffice (Story 7.4's flow, one-time secret); (e) hand the operator your `clientId`/`clientSecret`/`webId`/label for an `identities.json` entry + `npm run slug` — the connector picks it up on your first request, no restart needed (8.6.1); (f) add the connector in Claude using the assembled URL; (g) **create the `access-log/` container yourself before granting it** — CSS does not auto-create a missing parent container, so a grant against a container that does not yet exist 404s; (h) grant your own agent access to your chosen containers, by hand, as OWNER, naming `access-log/` explicitly as **RW today** (the backoffice has no Append-only option — that lands with 7.6/7.8), not the stronger Append-only guarantee the receipt design assumes. **Your OWNER credential never leaves your machine and is never given to the operator.**

5. **The page states the reader's own pod root URL prominently**, and tells them to state it to Claude on first use. This closes 8.5's live finding — Claude cannot guess a pod root and will otherwise ask cold before any tool call works.

6. **Day-to-day usage is covered in brief** (AC-scoped: pointer plus concrete first actions, not a duplicate of 8.6's skill): capture something, read it back in a later conversation, extend it. The read-back round trip is named as the thing that distinguishes this from artifact→download→import.

7. **Honest limits are stated plainly, not buried.** At minimum: (a) destructive-action confirmations are MCP *hints* — record what claude.ai actually did (8.5: two layers fired), and say the guarantee rests on the client honouring them; (b) read receipts are a **voluntary convention** — CSS surfaces no per-resource read log, so a reader that declines to write receipts leaves no trace; (c) there is **no pod versioning** — append is the safety mechanism, overwrite can lose data permanently; (d) the slug **is** a credential — anyone holding that URL is you, to the connector; (e) **your `access-log/` grant is RW today, not Append-only** — the backoffice doesn't offer the stronger option yet (7.6/7.8), so say "RW today, Append-only once that lands," never imply the tighter guarantee already holds.

8. **A real second person completes the walkthrough end-to-end**, following only the page, with Nicolas available but not narrating. Every point where they get stuck, guess, or have to ask is recorded and fixed in the page. This is the story's central claim: **the page works, verified by someone using it, not by its author reading it.**

9. **The second identity is live and isolated**: the new person's identity appears in the running connector, they can capture into their own pod from claude.ai, and `whoami.js` (or an equivalent self-audit) confirms their agent is **denied** where it should be — including denied on Nicolas's containers. Isolation demonstrated by a refusal, not only by an access.

10. **The uniqueness guard is exercised for real, not asserted.** With two identities configured, confirm the boot-time refusal of a duplicate `webId` across slugs still fires (8.5 Task 6.1 was unit-checked at N=1; this is the first configuration where it protects something real).

11. **No regression at N=2**: `scripts/verify-http.js` passes against the live public URL, `/healthz` reports **2** identities healthy, the audit journal attributes actions to the correct label per person, and greps clean of every slug and secret term. Rate-limiting and unknown-slug 404 behaviour unchanged.

12. **Epic 8 convention**: dated "Story 8.7" section **appended** to `epic-8-action-log.md` using `solid_append_resource` (verified by byte-length growth), and a Story 8.7 proof-table section added to `epic-8-progress-report.md`.

## Tasks / Subtasks

- [ ] **Task 1 — Write the conceptual frame (AC: 1, 2, 3)**
  - [ ] 1.1 Lead with the invariant in plain language. Not "single-writer semantics" — something a teacher or a parent reads once and retains.
  - [ ] 1.2 Name the three identity classes, one line each. Scope the walkthrough to personal explicitly, so nobody wonders where the collective steps went.
  - [ ] 1.3 Answer the shared-login question head-on. Give the concrete failure (skeleton key, no attribution, rotate-on-departure), then the alternative.
  - [ ] 1.4 One paragraph on collectives: a school/team/family account, Control held by a role, roles as grant bundles. Enough that the model is legible; not a setup guide.
  - [ ] 1.5 One paragraph on the ownership boundary for aggregates — why a collective can answer a region without exposing anyone (PRD Journey 4, amended).
  - [ ] 1.6 Keep it under 400 words. If it needs more, the frame is wrong, not the budget.

- [ ] **Task 2 — Write the walkthrough (AC: 4, 5)**
  - [ ] 2.1 Steps (a)–(g) as literal, followable instructions with real URLs — no placeholders a reader has to resolve.
  - [ ] 2.2 Make the **OWNER boundary explicit at the moment it matters**: you mint your own credentials, you grant your own access, your OWNER credential never leaves your machine and the operator never sees it. This is 8.5's corrected-scope lesson stated to a human.
  - [ ] 2.3 Be honest about the operator-in-the-middle step (e): what you hand over, what you do not, that it takes effect on your next request with no restart (8.6.1), and that Story 7.9 will make this a button.
  - [ ] 2.4 State the pod root URL prominently and tell the reader to give it to Claude on first use.
  - [ ] 2.5 Say plainly that the slug is a credential — treat the connector URL like a password.
  - [ ] 2.6 Suggest which containers to grant first, and why starting narrow is the right default.
  - [ ] 2.7 Add the hand-create-the-container step before the `access-log/` grant — CSS 404s a grant against a non-existent container, and this bit the author during 8.6.
  - [ ] 2.8 Word the `access-log/` grant step as **RW**, not Append-only, and say why (backoffice gap, closes with 7.6/7.8) — do not let the walkthrough imply a guarantee the current UI can't produce.

- [ ] **Task 3 — Day-to-day usage + honest limits (AC: 6, 7)**
  - [ ] 3.1 Concrete first actions: capture a note, find it in a later conversation, extend it. Point at 8.6's capture skill rather than restating it.
  - [ ] 3.2 Write the limits section: hints-not-guarantees (with 8.5's actual result), receipts-are-voluntary, no-versioning, slug-is-a-credential, RW-not-Append-only-yet.
  - [ ] 3.3 Frame limits as *how to work with the system*, not as disclaimers — a person who knows append is the safe path behaves differently from one who has been warned about overwrites.

- [ ] **Task 4 — Onboard the second person for real (AC: 8, 9)**
  - [ ] 4.1 Pick the person and confirm with Nicolas before creating anything. **This creates a real CSS account** — Epic 7 already accumulated orphan accounts and there is still no HTTP delete path for accounts or pods.
  - [ ] 4.2 They follow the page. Nicolas available for genuine blockers, **not** narrating. Silence is the measurement.
  - [ ] 4.3 Record every stumble, guess, and question verbatim as it happens — not reconstructed afterward.
  - [ ] 4.4 Fix the page from those notes. The fixes are the deliverable; the draft was a hypothesis.
  - [ ] 4.5 Their capture from claude.ai into their own pod, working.
  - [ ] 4.6 Self-audit their agent: granted where intended, **denied** on Nicolas's containers. Record the refusal — AC9 needs a denial, not just an access. (8.5 Task 2 learned this the hard way: public-read resources made LIST alone useless as evidence, and a WRITE probe had to be added.)

- [ ] **Task 5 — N=2 verification (AC: 10, 11)**
  - [ ] 5.1 Exercise the duplicate-`webId` guard against the real two-identity config; confirm the boot refusal fires and its message is actionable.
  - [ ] 5.2 `verify-http.js` against the live public URL; `/healthz` reports 2 identities healthy.
  - [ ] 5.3 Journal attributes actions to the correct label per person — the first configuration where mis-attribution is even possible.
  - [ ] 5.4 Grep the journal for both slugs and every secret term → 0 hits.
  - [ ] 5.5 Confirm unknown-slug 404 and rate-limiting unchanged (both were built to be indistinguishable per-slug; N=2 is the first chance to check they still are).

- [ ] **Task 6 — Close the loop (AC: 12)**
  - [ ] 6.1 Append a dated "Story 8.7" section to `epic-8-action-log.md` via `solid_append_resource`; verify byte-length growth.
  - [ ] 6.2 Add a "Story 8.7" proof-table section to `epic-8-progress-report.md`.
  - [ ] 6.3 Record the onboarding-friction notes from 4.3 somewhere durable — they are the input to Story 7.9's UI.

## Dev Notes

### Where the page lives

Decide and state it: repo docs vs. served from the backoffice vs. a pod resource. Serving it from the backoffice has an argument — the person is already there minting credentials in step (d) — but it is not required by any AC. **A pod-hosted onboarding page is a nice dogfood and a bad single point of failure**: if the reader cannot reach the pod, the page explaining how to reach the pod is also unreachable. Repo docs (per Story 8.4's Divio structure) is the safe default.

### The 400-word budget is a real constraint

Every prior instinct in this project has been to explain thoroughly — and this document's audience is someone who has not opted into the architecture yet. The frame earns its place by being retained, not by being complete. Everything that does not fit belongs in architecture.md BP-6, which is linked, not inlined.

### What "verified by the reader" means

AC8 is the story's spine. A page reviewed by its author reads as obvious to its author. The measurement is a person following it while Nicolas stays quiet. **Every intervention Nicolas makes is a defect in the page**, and should be logged as one — that reframe is the whole point of Task 4.2's "available, not narrating".

### Traps

- **The dev sandbox cannot reach the public URL** — the allowlist excludes roaming addresses; curl returns `403`. On-host requests hairpin through the VPS's own allowlisted IP (8.4 Task 8's method). **A 403 from your laptop is not a broken deploy.**
- **A new identity no longer needs a container restart** — 8.6.1 (landed 2026-08-02) added lazy login on cache miss. A new identity works on its first request after the operator saves `identities.json`; already-connected identities are uninterrupted. Do not write a restart step into this page.
- **CSS does not auto-create a missing parent container.** `access-log/` had to be hand-created before its grant worked — put the create-container step before the grant step, not after a failed grant teaches the reader the hard way.
- **The backoffice has no Append-only grant option.** Only RO/RW/only-me/public-read exist, so any `access-log/` grant minted through it is RW. Say "RW today, Append-only once 7.6/7.8 lands" — do not imply the stronger guarantee the receipt design assumes.
- **`identities.json` is chmod-600-enforced at boot.** A file written with looser permissions makes the container refuse to start. Set the mode when writing the entry, not after.
- **Real CSS accounts cannot be deleted over HTTP.** Confirm the person before creating. Epic 7's orphan accounts are the precedent.
- **OWNER credentials never leave the new person's machine**, and the operator never asks for them. This is 8.5's corrected scope, and the page is where it becomes a human-facing promise rather than an internal note.
- **Denial evidence needs a write probe.** Public-read resources make a successful LIST prove nothing about isolation — 8.5 Task 2's live bug.
- **Every VPS deploy is confirmed with Nicolas first** (8.4 precedent).
- **Do not overstate the approval prompts.** 8.5 saw two layers fire on claude.ai. That is a property of that client's current behaviour, not a guarantee of the protocol. Say both parts.

### Reuse — do not re-derive

| Need | Existing thing |
|---|---|
| Slug generation | `npm run slug` → `scripts/gen-slug.js` |
| Identity entry shape + validation rules | `identities.example.json`, `identityRegistry.js` |
| Credential minting UI + one-time secret UX | Story 7.4's backoffice flow |
| Agent self-audit incl. denial probes | `src/whoami.js` (WRITE probe added in 8.5) |
| Live end-to-end regression | `scripts/verify-http.js` |
| Grant reference (adapt, do not execute centrally) | `src/onboarding.js`'s `GRANTS` constant |
| Doc structure | Story 8.4's Divio-structured docs |
| Capture usage guidance | 8.6's capture skill — link, don't restate |

### Explicitly deferred — do not build here

Backoffice-minted credentials and the reload path for new identities (Story 7.9). Roles-and-grants UI (Story 7.8). Collective-account setup walkthrough. A collective service agent. Server-side access logging. Pod versioning (brief §7). OAuth/DCR, ACP migration, notifications (brief §7). Anything 8.5/8.6 re-deferred stays deferred unless it blocks a task here.

### Invalidated Assumptions

- **Assumption:** the coordination question is "shared butler WebID vs per-person agents" → **Reality:** it was a false dichotomy. Both exist and do different jobs — a *personal* agent (one human, capture) and a *collective service* agent (nobody holds it, runs as cron). The shared-credential-for-multiple-humans option is the only one ruled out. See architecture.md BP-6.
- **Assumption:** a collective agent reading personal pods destroys write attribution → **Reality:** it does not, because a collective agent never writes into a personal pod. Under BP-6 the invariant removes the ambiguity rather than mitigating it. Read attribution was never in question — the log pairs reader identity with resource owner.
- **Assumption (architecture.md BP-1, 2026-03-24):** receipts are written into the data subject's pod → **Reality:** confirmed and kept, but the mechanism is now specified as `acl:Append`-only on `access-log/`, never `acl:Write`. A receipt in the reader's own pod was drafted and rejected on 2026-08-02: it leaves the audited party holding the audit trail.
- **Assumption (architecture.md BP-2):** aggregate anonymization is `GROUP BY` in a query the consumer runs → **Reality:** the primary boundary is *ownership* — the consuming agent is never granted the personal data. `GROUP BY` is defense-in-depth inside the collective's own boundary. PRD Journey 4 amended 2026-08-02.
- **Assumption:** the slug is an implementation detail → **Reality:** it is the bearer credential, wearing a path costume, and exists solely because claude.ai's connector dialog has no request-headers field. Anyone holding the URL is that identity. The page must say so.
- **Assumption:** Hermes will need slugs too → **Reality:** it will not — same docker network, no untrusted client, no missing-header problem. It should reuse the slug mechanism anyway, because the alternative is a second auth code path to build and secure for one internal caller.
- **Assumption:** revocation is a sufficient control on its own → **Reality:** revocation without visibility is theoretical. A person who cannot see that a read happened has no trigger to revoke. That gap is what 8.6's receipts (FR42) exist to close, and this page must not imply the pod server provides it.

### Project Structure Notes

Primary artifact is documentation, most likely under `docs/` following 8.4's Divio structure. Config change: one new entry in `mcp-connector/identities.json` (gitignored, chmod 600) — no restart, per 8.6.1. Possible small edit to `mcp-connector/SKILL.md` or 8.6's capture skill if the live walkthrough exposes a gap. No changes to `backoffice/`, `pipeline/`, or `infra/`. nginx lives in the separate `hetzner-gateway` repo and is untouched.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Principle-BP-6-Single-Writer-Pods-Role-Based-Collective-Access] — the model this page teaches; the page links here rather than inlining it
- [Source: _bmad-output/planning-artifacts/architecture.md#Principle-BP-1-Bidirectional-Accountability] — receipt location + `acl:Append` mechanism, amended 2026-08-02
- [Source: _bmad-output/planning-artifacts/architecture.md#Principle-BP-2-Trustless-Anonymization-Structural-Not-Policy] — ownership boundary primary, `GROUP BY` secondary, amended 2026-08-02
- [Source: _bmad-output/planning-artifacts/prd.md#Journey-4-Isabelle-Evidence-Based-Policy] — amended anonymization boundary; FR42 read receipts
- [Source: _bmad-output/planning-artifacts/MISSION_BRIEF_solid-mcp-connector.md] — §4.1 two-token model, §4.3 agent scope, §7 out-of-scope (versioning, OAuth/DCR, ACP)
- [Source: _bmad-output/implementation-artifacts/8-5-live-verification.md] — claude.ai method, allowlist/hairpin trap, OWNER-boundary correction, double approval-prompt result, pod-URL-not-guessable finding, whoami WRITE-probe lesson, uniqueness guard
- [Source: _bmad-output/implementation-artifacts/8-6-capture-surface-and-skill.md] — capture skill and read receipts this page points at
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md] — Divio doc structure, hairpin verification, deploy confirmation practice
- [Source: _bmad-output/implementation-artifacts/7-4-apps-and-credentials.md] — credential minting flow the walkthrough's step (d) uses
- [Source: mcp-connector/src/identityRegistry.js] — identity map validation: slug entropy floor, chmod 600 refusal, duplicate-webId guard

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change |
|---|---|
| 2026-08-01 | Renumbered from 8.6 when the capture-surface story was inserted ahead of it. |
| 2026-08-02 | Drafted after a design session that resolved the deferred coordination/identity question. Nicolas reframed the connector as the "first line of conscious input" and traced a concrete school scenario (student → course → school → region), which produced architecture.md BP-6 (single-writer invariant, three identity classes, roles as grant bundles), amended BP-1 (receipt mechanism) and BP-2 (ownership boundary over query filter), amended PRD Journey 4 + FR19, added FR42, added Task 5b to Story 8.6, and drafted Stories 7.8 and 7.9. Scope confirmed with Nicolas: conceptual frame included, walkthrough personal-only, slug minting documented as manual with 7.9 noted. |
| 2026-08-02 | Amended from 8.6 session handoff: added missing-parent-container gap (CSS doesn't auto-create `access-log/`, must be hand-created before the grant works) as an explicit walkthrough step (AC4 step g, Task 2.7) rather than a step the reader discovers via a failed grant; added the Append-only-vs-RW gap (backoffice has no Append-only option today) as an honest-limits bullet (AC7e) and walkthrough wording rule (Task 2.8, 3.2) so the page says "RW today, Append-only once 7.6/7.8 lands" rather than implying the stronger guarantee. Pod-root-URL discoverability (AC5) was already present, unchanged. Noted 8.6.1 (lazy identity loading) as a sequencing dependency to check before finalizing the restart wording in step (e). |
