# Sprint Change Proposal — Epic 7 Resequence & Story Merge

**Date:** 2026-08-03
**Author:** Bob (SM), from a party-mode review with Winston (Architect), Sally (UX), Amelia (Dev), Quinn (QA), Paige (Tech Writer)
**Trigger:** Story 7.9 review — user reported never using the shipped credentials UI
**Scope classification:** **Moderate** (backlog reorganization, no PRD/FR change)

---

## Section 1 — Issue Summary

Story 7.9 (`ready-for-dev`) was brought up for review. Nicolas opened by describing how he *actually* creates pods and credentials in practice:

> "we did design a 'people & apps' page with a section about credential where I need to re-enter my email+password but to be frank, I never use it because it only manage token credentials not pods. So the easiest path I found is to signout from the 'backoffice' app, then back to re-authorize the app to access my pod page, and click 'edit account'."

**The most motivated user of this product routes around the feature we built for him.** That is the triggering evidence — not a bug report, a usage pattern.

Investigation during the review produced four findings, three of them verified against source rather than assumed.

### Finding 1 — The "unlock app management" gate is unnecessary friction (VERIFIED)

CSS `ResolveLoginHandler.js:35-36`:

```js
// Putting it in the metadata, so it can be converted into an HTTP response header.
// Putting it in the response JSON so users can also use it in an Authorization header.
json.authorization = await this.cookieStore.generate(accountId);
```

The `CSS-Account-Token` and the account cookie are **the same value**, emitted through two transports. `CookieParser.js` reads it back off the `Cookie` header. The backoffice is served from `pod.nicolasdb.eu` root — **same origin as CSS** — so the browser already holds that cookie.

Story 7.4's email+password gate asks the user to re-authenticate in order to obtain a token the browser already has.

Nicolas's "Edit account" path is therefore **not unsafe and not an exploit** — it is stock CSS navigation riding the session he already established. It is, however, undocumented, requires signing *out* to reach, and was found by accident. Safe-from-CSS ≠ discoverable-from-our-app.

### Finding 2 — There is no path to create a pod from the backoffice (GAP)

Nicolas's whole workaround exists because our app cannot create a pod. Story 7.9's "one button" mints credentials for an agent WebID the person must have created by **leaving the product**. 7.9 as drafted automates the middle of a journey whose beginning is unowned.

Story 8.7's walkthrough steps (b)/(c) have no home in any story.

### Finding 3 — The pod-root ACL is real, public, and invisible in the UI (VERIFIED)

CSS ships this at every pod creation (`templates/pod/wac/.acl.hbs`):

```turtle
<#public>
    acl:agentClass foaf:Agent;
    acl:accessTo <./>;          # the container ITSELF
    acl:mode acl:Read.          # no acl:default

<#owner>
    acl:agent <{{webId}}>;
    acl:accessTo <./>;
    acl:default <./>;           # children inherit THIS
    acl:mode acl:Read, acl:Write, acl:Control.
```

Two consequences:

- **The backoffice footer "🔒 New things start private" is CORRECT.** Public has `accessTo` but no `acl:default`, so it never propagates to children. Only the owner rule carries `default`. This was expected to be a lie and is not.
- **The pod root container is publicly listable, and "My things" has no row for it.** Anyone can list the top level of a pod and read the names of everything in it. This is the "top pod permission" the user cannot find — it exists, it is real, and the UI does not admit it.

Additionally, `pod-api.js:253` returns `{ agents: [], public: emptyModes(), inherited: true }` when no standalone `.acl` exists. The badge "Inherits from parent" is accurate but **the app never resolves what the parent grants** — it shrugs upward and leaves the user's obvious next question unanswered.

### Finding 4 — `profile/card` is deletable through an ordinary delete button (RISK)

Raised by Nicolas: *"I could misunderstand what card#me importance is and delete this file manually, thus break the pod main mechanic."*

Confirmed. CSS's own template comment: *"The WebID profile is readable by the public. This is required for discovery and verification, e.g. when checking identity providers."*

`profile/card` **is** the WebID document. Deleting it breaks OIDC login, and every `.acl` naming that WebID points at a URL that 404s. There is no versioning and no undo. Today "My things" renders `profile` as an ordinary folder with the same 🗑 affordance as a throwaway note.

This also explains a prior open question: Story 8.5's isolation probe saw `LIST` succeed where denial was expected, because public read was genuinely present via these template ACLs. The scope was not too wide — the probe measured the wrong thing, which is why the WRITE probe was added. **The test result stands.**

### Supporting structural evidence (graphify)

The existing knowledge graph was queried to confirm coupling rather than assert it:

- `backoffice/pod-api.js` is a bridge node into Stories 7.1, 7.3 **and** 7.5
- `RealBackend` (29 edges) and `DemoBackend` (22 edges) are both god nodes
- `_writeAcl() --semantically_similar_to--> _saveAclOrThrowControlError` — the graph independently flagged **two ACL writers**, one in `backoffice/pod-api.js`, one in `mcp-connector/src/wacManager.js`
- Story 7.5 already `references` Story 7.7

7.8 and 7.9 have no graph nodes: 7.8 was never drafted, 7.9 is hours old. The graph is stale on both by construction, not by omission.

**Conclusion:** the merge axis is not the feature, it is the file. Five remaining Epic 7 stories all edit `RealBackend` + `DemoBackend` + one screen in `index.html`. Five separate dev/review cycles would re-review the same code five times.

---

## Section 2 — Impact Analysis

### Epic impact

**Epic 7 only.** No FR changes, no PRD scope change, no architecture-principle change. Epic 8 is unaffected — 8.7 gains a doc update once 7.9 lands (already anticipated in 7.9 AC12).

### Story impact

| Story | Status before | Impact |
|---|---|---|
| 7.5 Export & Backup | ready-for-dev | **Re-sequenced last** — its access-metadata sidecars consume the effective-access resolver |
| 7.6 File-manager hardening | ready-for-dev | **Unchanged** — genuinely independent |
| 7.7 Delete My Pod | ready-for-dev | **Merged into new 7.10** |
| 7.8 Roles & Grants | backlog | **Merged into new 7.11** |
| 7.9 Connector credentials | ready-for-dev | **Shrinks** — gate removal extracted to 7.10; needs redraft |
| **7.10 Account & Pod Lifecycle** | — | **NEW** |
| **7.11 Effective Access & Roles** | — | **NEW** |

Net: 5 open stories → 5 open stories, but two previously-unowned primitives now have owners, and two review cycles are eliminated.

### Artifact conflicts

- `epics.md` — Epic 7 story list: rewrite 7.5/7.7/7.8/7.9, add 7.10/7.11
- `sprint-status.yaml` — status changes + two new keys
- `_bmad-output/implementation-artifacts/7-9-backoffice-minted-credentials.md` — redraft (gate removal out, dependency on 7.10 in)
- `7-7-delete-my-pod.md` — superseded, content folds into 7.10
- `docs/team-onboarding.md` — steps (b)–(f) collapse once 7.10 + 7.9 land (deferred until then)
- **No** PRD, architecture, or UX-spec changes

### Technical impact

- No new dependencies, no new services, no infrastructure change
- One nginx `location` block still required by 7.9 (`hetzner-gateway`, separate repo)
- `pod-api.js` `accountLogin()` + the unlock-gate UI get **deleted**, not modified — a net code reduction

---

## Section 3 — Recommended Approach

**Direct Adjustment** — modify and add stories within the existing plan. No rollback, no MVP change.

Rollback was considered and rejected: 7.4's credential minting is correct and live-verified; only its *gate* is redundant. Nothing shipped needs reverting.

**Rationale for merging rather than inserting:**

1. **Shared file surface.** All five stories edit the same two classes in one file. Separate cycles re-review identical code.
2. **Blind-primitive risk.** Building the effective-access resolver (7.11) without the UI that consumes it means shipping an unproven abstraction. Same for the pod-root ACL row without pod creation.
3. **Ceremony symmetry.** Create-pod and delete-pod are the same problem inverted, and the pod-root ACL row is where "what am I about to destroy" is *shown*. Splitting them splits one design conversation across two reviews.

**Effort:** roughly neutral in total dev time, **−2 adversarial review cycles**.

**Risk:** 7.10 is larger than any single story it replaces. Mitigation — it is internally sequenced (gate → create → root-ACL row → guardrails → delete), and each sub-piece is independently demonstrable.

**Timeline:** 7.9 is unblocked sooner in practice, because it stops waiting on primitives nobody had scheduled.

---

## Section 4 — Detailed Change Proposals

### 4.1 — `epics.md` — Story 7.5 (re-sequence note only)

**OLD** (final bullet):
```
- WCAG 2.1 AA
```

**NEW:**
```
- WCAG 2.1 AA
- **Sequencing (2026-08-03): runs LAST in Epic 7.** The per-resource access-metadata sidecars depend on Story 7.11's effective-access resolver. Shipping before it would emit `inherited` for most resources — technically true, operationally useless, and permanently baked into an archive users keep.
```

**Rationale:** An export is the artifact people retain. A misleading manifest is worse than a late one.

---

### 4.2 — `epics.md` — Story 7.7 → merged

**OLD:** `### Story 7.7: Delete My Pod` (full section, 4 bullets)

**NEW:**
```
### Story 7.7: Delete My Pod _(MERGED into Story 7.10 — 2026-08-03)_
Superseded. Scope moved wholesale into **Story 7.10: Account & Pod Lifecycle**, where create-pod and delete-pod are designed as one reversibility problem rather than two. No scope was dropped in the merge; the recursive-delete ceremony, the "show what is destroyed, not just a name" requirement, and the no-HTTP-delete-path context all carry over.
```

**Rationale:** Create and delete share the same screen, the same `RealBackend` methods, and the same ceremony design language.

---

### 4.3 — `epics.md` — Story 7.8 → merged

**OLD:** `### Story 7.8: Roles & Grants — Permission UI Beyond Raw WebIDs _(DRAFT — added 2026-08-02)_` (full section)

**NEW:**
```
### Story 7.8: Roles & Grants — Permission UI _(MERGED into Story 7.11 — 2026-08-03)_
Superseded. Scope moved wholesale into **Story 7.11: Effective Access & Roles**, which pairs the roles UI with the effective-access resolver it silently depended on. No scope was dropped: role-as-grant-bundle, the single-writer invariant made visible, the collective-account Control view, and FR42 read-receipt surfacing all carry over.
```

**Rationale:** 7.8 assumed a resolver that does not exist. Pairing them means the resolver is proven by the UI that consumes it.

---

### 4.4 — `epics.md` — Story 7.9 (rewrite)

**OLD** (bullets 2 and 5):
```
- Server-side endpoint mints AGENT client-credentials against the CSS account API using the person's **own** authenticated session, writes the `identities.json` entry, and returns the assembled connector URL **once** (reuse Story 7.4's one-time-secret UX)
...
- **Blocker to resolve:** connector sessions are boot-time singletons (`mcp-server.js`), so a new identity needs either a reload path (re-read `identities.json` + authenticate the new identity) or an accepted "restart on new teammate"
```

**NEW:**
```
- Server-side endpoint mints AGENT client-credentials against the CSS account API using the person's **own** authenticated session, writes the `identities.json` entry, and returns the assembled connector URL **once** (reuse Story 7.4's one-time-secret UX)
- **Depends on Story 7.10** for the account session (no password re-entry) and for pod creation — without 7.10 this button automates the middle of a journey that still forces the user out of the product
...
- ~~Blocker: boot-time singletons~~ **RESOLVED by Story 8.6.1** (2026-08-02): lazy login on cache miss means a new identity works on its first request. **Do not build a reload path; do not add a restart step.**
```

**Rationale:** One stated blocker is already resolved; two unstated ones are real and now owned by 7.10.

---

### 4.5 — `epics.md` — NEW Story 7.10

```
### Story 7.10: Account & Pod Lifecycle — Create, Protect, Delete _(ADDED 2026-08-03 — absorbs 7.7)_
As a pod owner, I can create a pod, see and set its top-level permissions, and delete it — all without leaving the backoffice or re-typing my password — so that the lifecycle of the thing I own is managed where I own it.
- **Kill the unlock gate.** VERIFIED: CSS's account cookie and the `CSS-Account-Token` are the same value (`ResolveLoginHandler.js:35-36`), and the backoffice is same-origin with CSS — the browser already holds it. Remove `accountLogin(email,password)` and the "Unlock app management" prompt; read the authed `/.account/` index with `credentials: 'include'`. Net code deletion. **Trap: that GET must carry no `content-type` header** or CSS content-negotiates a controls-less body (7.4's live finding).
- **Create a pod from the backoffice** via `controls.account.pod`. Pod names collide **globally across the instance**, not per-account — a duplicate is refused `409 Conflict` (verified in `TemplatedPodGenerator.generate`, 2026-08-03). Surface that as a name-availability affordance, not a raw error.
- **Show the pod-root ACL as a real row.** CSS's pod template grants `foaf:Agent` `acl:Read` on `<./>` with no `acl:default` — the pod root is publicly *listable* while its children are not. Today no UI row exists for it. Make it visible, explain it, make it editable.
- **Protected-resource guardrails.** `profile/card` is the WebID document; deleting it breaks OIDC login and orphans every `.acl` that names that WebID, with no versioning and no undo. It currently carries the same delete affordance as a throwaway note. Distinct treatment + an explanation of what breaks — not a scary modal.
- **Delete a pod** (absorbed from 7.7): owner-driven recursive deletion, ceremony proportional to what is lost, confirmation shows what is about to be destroyed rather than just a name. Closes the orphan-accumulation gap — CSS exposes no HTTP delete path for accounts or pods.
- **Welcoming README template.** Override CSS's stock `README` (no extension, reads as `text`, says nothing) with a `README.md` that explains ownership, what is public by default, and where the identity document lives. **Lockstep requirement:** `README.acl.hbs` hardcodes `acl:accessTo <./README>` — rename without overriding it in the same change and the welcome file loses its public ACL. Same bind-mount mechanism as Story 7.2.
- WCAG 2.1 AA
```

---

### 4.6 — `epics.md` — NEW Story 7.11

```
### Story 7.11: Effective Access & Roles _(ADDED 2026-08-03 — absorbs 7.8)_
As a pod owner, I can see what access actually applies to a resource — not just that it "inherits from parent" — and manage that access as named roles rather than raw WebID rows.
- **Effective-access resolver.** `pod-api.js:253` returns `inherited: true` with empty agents/public when no standalone `.acl` exists, and nothing ever walks upward to resolve what the parent's `acl:default` actually grants. Build that walk once. Consumed here, by Story 7.5's export sidecars, and by the badge fix below.
- **Finish the sentence the badge starts.** "Inherits from parent" is accurate but unanswerable — it must state what the parent grants, or link to the row that does.
- Role = named grant bundle (absorbed from 7.8): define once (containers + modes), assign/unassign personal-agent WebIDs, revoke an assignment without touching the underlying identity
- Surface the **single-writer invariant** visibly: "my pod, my agent writes" vs "someone else's pod, I hold a grant" are different mental objects that currently render identically
- Collective-account view: which role holds `acl:Control`, who is assigned, how succession reassigns it
- Read receipts (FR42, built in Story 8.6) surfaced to the data subject — what makes revocation an informed decision rather than a theoretical right
- **Honesty constraint:** never offer an "only me" control at pod scope that the protocol will not honour. `profile/card` stays public by necessity (WebID discovery). If a user restricts the pod root, tell them why that one resource remains public rather than letting them find the inconsistency later.
- **Sequencing:** depends on 8.6 (receipts) and 8.7 (model documented). Runs before Story 7.5.
- WCAG 2.1 AA
```

---

### 4.7 — `sprint-status.yaml`

```
story-7-5-export-backup-portability:   ready-for-dev → ready-for-dev  (re-sequenced last)
story-7-6-file-manager-hardening:      ready-for-dev → unchanged
story-7-7-delete-my-pod:               ready-for-dev → merged-into-7-10
story-7-8-roles-and-grants-ui:         backlog       → merged-into-7-11
story-7-9-backoffice-minted-credentials: ready-for-dev → needs-redraft
story-7-10-account-and-pod-lifecycle:  (new)         → backlog
story-7-11-effective-access-and-roles: (new)         → backlog
```

---

## Section 5 — Implementation Handoff

**Scope: Moderate** — backlog reorganization, no fundamental replan.

### Execution order

1. **7.10 — Account & Pod Lifecycle** (`create-story`, then dev) — unblocks everything
2. **7.9 — Connector credentials** (redraft first, then dev) — now genuinely small
3. **7.11 — Effective Access & Roles** (`create-story`, then dev)
4. **7.6 — File-manager hardening** (already `ready-for-dev`, independent)
5. **7.5 — Export & Backup** (already `ready-for-dev`, must follow 7.11)

### Handoff

| Recipient | Responsibility |
|---|---|
| SM (`create-story`) | Draft 7.10 and 7.11 with full context |
| SM (`create-story` / manual) | Redraft 7.9 — remove gate scope, add 7.10 dependency, mark the 8.6.1 assumption invalidated |
| Dev (`dev-story`) | Implement in the order above |
| Nicolas | Confirm before any VPS deploy (8.4 precedent) — note two repos deploy here |

### Success criteria

- A person creates an account, a pod, an agent pod, mints connector credentials, and connects Claude **without leaving the backoffice and without re-typing a password**
- The pod-root ACL is visible and editable; `profile/card` cannot be deleted casually
- "Inherits from parent" states what is inherited
- Story 8.7's walkthrough shrinks to match, honest-limits section intact
- No regression in 7.1–7.4 behaviour; `verify-http.js` and `/healthz` unchanged

### Open items deliberately NOT resolved here

- `_writeAcl()` / `_saveAclOrThrowControlError` duplication across `backoffice/` and `mcp-connector/` — flagged by graphify, real, but a refactor with no user-facing story. Logged for a future consolidation.
- Cross-provider import/restore (WebID/ACL rebinding) — remains deferred per 7.5.
- `docs/team-onboarding.md` rewrite — deferred until 7.10 + 7.9 are live, so the page describes what exists.

---

## Approval

- [ ] Nicolas approves this proposal for implementation
