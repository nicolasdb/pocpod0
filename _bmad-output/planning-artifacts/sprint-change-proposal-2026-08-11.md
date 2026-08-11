# Sprint Change Proposal — Security Brief Course Correction

**Date:** 2026-08-11
**Author:** Scrum Master (Bob) with Nicolas
**Trigger document:** `security-hardening-brief-2026-08-09.md` (hosted on the pod at `hyperscope_ndb/shared/`, revision appended 2026-08-11)
**Scope classification:** **Moderate** — backlog reorganisation, no replan
**MVP impact:** **None**
**Status:** Approved by Nicolas, 2026-08-11

---

## 1. Issue Summary

### What triggered this

Not a new requirement and not a failure. A **live verification pass** run between 2026-07-30 and 2026-08-11 against source code and the live host — deliberately not against memory — went back to a security brief written on 2026-08-09 and checked its open questions.

Four questions closed. One closed with a **negative answer that is a real finding**. And one premise that Epic 8's roadmap rested on turned out to be false in a direction nobody had considered.

The brief is unusual as a change trigger in that it corrects *itself*: §§11–17 were appended as a revision that explicitly does not erase the earlier reasoning, keeping §§1–10 as the record of what was known at the time. This proposal follows the same convention — superseded decisions are marked superseded, not deleted.

### The three things that move the plan

**A. Credential-at-rest — new finding, previously unowned.**

CSS client-credentials secrets sit in plaintext, on an unencrypted disk. Two independent layers, neither mitigating the other, both verified in source on the live host:

- **Application:** `BaseClientCredentialsStore.js` declares its storage schema as `secret: 'string'`. No hash field, no digest, no bcrypt/argon2 import. `create()` generates `randomBytes(64).toString('hex')` and passes it to `storage.create(...)` verbatim.
- **Disk:** `lsblk` shows plain ext4 on `sda1`; `cryptsetup status` shows no mapped device — no LUKS.

Anyone with host/root access, or a volume snapshot, reads live client-credential secrets directly. No cracking, no cryptographic work.

Two things make this bigger than it first appears. It is **not a pocpod0 defect** — the plaintext store is the upstream OIDC library's convention, inherited by CSS, so this is a decision about a dependency's behaviour rather than a bug fix. And it is **not a property of the slug scheme**: any CSS client-credentials secret inherits it, including the server-side DPoP-bound token that an OAuth 2.1 migration would hold. Migrating to OAuth does not close it. It moves the same plaintext secret behind a better front door.

**B. The OAuth migration premise is void for the claude.ai path.**

Epic 8 adopted the URL-slug believing Anthropic's connector surface blocked OAuth. That diagnosis was half wrong, and the correction cuts against us rather than for us.

Claude's remote connectors *do* support OAuth 2.1 at the product level — DCR (RFC 7591), Client ID Metadata Documents, PKCE `S256`, RFC 9728 discovery. But **those fields are not exposed on this account.** Verified absent (`8-4-vps-deploy-hardening.md:315`), and the connector was accepted by claude.ai with no OAuth configuration whatsoever (`8-5-live-verification.md:141,143`).

So the §10 question the brief itself posed — "does the MCP server run its own authorization server, or delegate to CSS?" — is not answered. It is **dissolved**. It presupposed a design choice, and there is currently no surface to attach either option to. That is closed at *unavailable*, not at *undecided*.

**C. The access journal is a receipt file, not yet a control.**

Story 8.6 shipped the honest half: `receipt.js` appends JSONL to the data subject's `access-log/receipts.jsonl` via `acl:Append`, correctly located per BP-1. The brief's §4.4 asks for the rest — per-identity attribution, rate limiting, anomaly detection, operator alerting, and append-only *outside the agent's own write scope*, on the principle that a journal the agent can rewrite is not a journal.

### Evidence quality

Every claim above is verified in primary source. Where the brief asserted something this proposal could check independently, it was checked against the repository before being written down — including three items that turned out **not** to need work (§3 below). One item in the brief's framing is carried forward as a **hypothesis to verify**, not a finding: see Story 8.9's lead item.

---

## 2. Impact Analysis

### Epic impact

| Epic | Status | Impact |
|---|---|---|
| **Epic 8 — Solid MCP Connector** | in-progress | **Scope amended + 2 stories added.** Its auth premise changes meaning: hardening is the real posture, not scaffolding |
| **Epic 7 — Pod Owner Experience** | in-progress | **Story 7.9 redraft brief amended.** Order (7.10 → 7.9 → 7.11 → 7.6 → 7.5) unchanged |
| **Epics 1–6** | done / parked | No impact. SEC-1 is superseded rather than rewritten precisely because they were built under it |

**No resequencing.** Both new stories are hardening on surfaces that already work. Neither blocks Story 8.7 (parked on the availability of a real second person) nor any Epic 7 story.

### Story impact

- **New — Story 8.8: Credential-at-Rest Hardening.** Owns finding A. Must close a compatibility unknown before implementing.
- **New — Story 8.9: Access Journal as a Real Control.** Owns finding C.
- **Amended — Story 7.9** (`needs-redraft`, unchanged status). Its redraft brief gains the grant-table shape and the revocation-UI requirement.
- **Unchanged — Story 8.7** stays `in-progress`, still parked on a real second person.

### Artifact conflicts

| Artifact | Conflict | Resolution |
|---|---|---|
| `architecture.md` SEC-1 | "No User Authentication in PoC" — false since Epic 7 | **Superseded**, current three-path model documented |
| `architecture.md` | No home for the credential-at-rest gap | **SEC-4 added** |
| `epics.md` Epic 8 header | Implies a migration path that does not exist | **Auth posture block added** |
| `prd.md` FR42 | Said the receipt lands in the reader's **own** pod | **Corrected** to the data subject's pod |
| `epics.md` Story 7.9 | Grant record specified as a bare pair | **Grant-table shape + revocation UI added** |
| `sprint-status.yaml` | No entries for the new work | **2 entries + `last_updated` rationale** |
| `post-poc-backlog.md` | Self-hosted OAuth path had nowhere to live | **Entry added** |

The **FR42 conflict was found during this analysis and is not from the brief.** It matters more than a stale-doc nit: it inverted the principle. A receipt held by the party being audited can be quietly deleted by them, which is exactly why BP-1 places it in the subject's pod under `acl:Append`. The PRD was describing the failure mode as if it were the design.

### Technical impact

- **Code:** none in this proposal. All changes are planning artifacts.
- **Infrastructure:** Story 8.8 may reach the host (LUKS) or the CSS dependency (fork/patch) — that choice is the story's first task, not a foregone conclusion.
- **Deployment:** unchanged.

---

## 3. Verified Closed — No Work Proposed

Recorded because *not* opening a story is also a decision, and the next reader deserves to know these were checked rather than skipped.

| Brief item | Finding | Evidence |
|---|---|---|
| §3 "convert the slug to an opaque key" | **Already true.** 22-char base64url = 128 bits, above the W3C TAG 120-bit floor | `gen-slug.js:14` — `crypto.randomBytes(16).toString("base64url")`, CSPRNG, no predictable derivation |
| §4.3 slug in proxy logs | **Closed by Story 8.4.** Server-scope `access_log off`, live-probed, 0 hits | `11-solid-mcp.conf:44,76,150` |
| §4.3 `Referrer-Policy` / HSTS | **Present.** Brief asks for `no-referrer`; current is `strict-origin-when-cross-origin`, which already withholds the path cross-origin — and this vhost serves JSON to a non-browser client, so no `Referer` is generated at all | `11-solid-mcp.conf:92-93` |
| §4.2 container scoping | **Confirmed.** Agent grant sits on a leaf `shared/.acl`, not pod root | Brief §15, live |
| §4.1 non-owner agent WebID | **Confirmed with a scope correction.** `nicolas_claude` holds Control on its own workspace pod (normal, unavoidable — `OwnerPermissionReader`), never on data pods | Story 8.1 AC4 — `grantAccess` on `hyperscope_ndb/` returns 403 |
| §7 CSS version ambiguity | **Resolved.** CSS 7.1.9 → `.account/` API, not 6.x `/idp/credentials/` | `/community-server/package.json` on host |

**Residual, accepted, not storied:** the slug still appears in `solid-mcp_error.log` on upstream-resolution failure. This is nginx's own error format, not configurable away. Mitigated by file permissions (640 `root:adm`), matching the existing logrotate policy.

---

## 4. Recommended Approach

**Selected: Direct Adjustment.**

| Option | Verdict | Reason |
|---|---|---|
| **Direct Adjustment** | **Selected** | Every finding is additive. Effort Medium, risk Low |
| Rollback | Not viable | Nothing to revert — no shipped work is wrong, only under-scoped or under-documented |
| PRD / MVP review | Not needed | MVP is unaffected. The demo surface works and is not weakened by any finding |

**Rationale.** The findings do not contradict what was built; they describe conditions around it that were assumed rather than checked. The one genuine finding (A) is a property of a dependency and its host, not of our design. The one invalidated premise (B) changes how existing work should be *valued* — hardening is permanent, not interim — rather than requiring it to be redone.

**Effort:** Story 8.8 Medium (dominated by the compatibility unknown, not by implementation). Story 8.9 Medium. Artifact edits done as part of this proposal.

**Risk of not acting:** rising, but not acute. The finding's exposure requires host or snapshot access, and the VPS holds no third-party production data today. It sharpens the moment a second person's credentials live there — which Story 8.7 is explicitly waiting to make happen.

**Timeline:** no PoC delay. Both stories sit in `backlog` behind the current Epic 7 order.

---

## 5. Detailed Change Proposals

All eight edits below are **applied**.

### 5.1 `architecture.md` — SEC-1 superseded

Replaced "Decision SEC-1: No User Authentication in PoC" with "Decision SEC-1: Authentication — Superseded 2026-08-11", documenting the three real authentication paths (human → CSS via Solid-OIDC; agent → CSS via client-credentials + DPoP; MCP client → connector via capability URL), the WAC authorization model, and the verified structural non-owner guarantee.

*Rationale:* as written, SEC-1 told a future reader this system has no authentication to attack. It has three paths, one of which is a bearer token in a URL. Superseded rather than rewritten, so Epics 1–6 still read coherently against the decision they were built under.

### 5.2 `architecture.md` — SEC-4 added

New decision recording the credential-at-rest gap: both layers, both verifications, the scope note that it outlives the slug design, and the explicitly undecided choice of which layer to fix.

*Rationale:* recorded as a decision rather than a deferred-work line because it is a standing property that every future credential inherits. In `deferred-work.md` it would be invisible to whoever designs the next auth surface.

### 5.3 `epics.md` — Epic 8 auth posture block

Added after the Positioning line: the corrected OAuth diagnosis, the indefinite-slug consequence, the two-way target split, the re-evaluation trigger, the open `acp:client` question, and the note that SEC-4 is not solved by OAuth.

### 5.4 `epics.md` — Story 8.8 added

Full story stub. Leads with the finding and both verifications; states plainly it is not a pocpod0 defect; makes the compatibility unknown a gate before implementation; requires the layer decision to be recorded in SEC-4 (with "accept the risk" a valid outcome); states the honest boundary that at-rest protection is not protection from a live compromised host.

### 5.5 `epics.md` — Story 8.9 added

Full story stub covering attribution, anomaly alerting, identity-level rate limiting, and append-only-outside-agent-scope.

**Its lead item is framed as a hypothesis on purpose.** The brief's §15 verified leaf-container scoping on `shared/`, but `access-log/` sits at pod root and was never covered by that check. Whether the agent's grant there cascades `Write` is **unknown**, so the story instructs: verify, then write the AC. Shipping it as a stated defect would have been the kind of unverified framing this project has been burned by before.

### 5.6 `epics.md` — Story 7.9 redraft input

Two bullets added: the grant-table shape `slug → { credentialRef, webId, containers[], createdAt, expiresAt, lastUsedAt, revoked }`, explicitly flagged as *not* throwaway work since it is the shape an OAuth grant store needs; and the revocation UI as the open question the redraft must answer — a mint button with no revoke path ships the leak with no exit.

### 5.7 `prd.md` — FR42 corrected

"its **own** pod" → "the **data subject's** pod ... `acl:Append` and never `acl:Write`", with an inline note explaining what the old wording contradicted and why the inversion mattered.

### 5.8 `post-poc-backlog.md` — self-hosted OAuth entry

Records the available-now half of the OAuth target: RFC 9728 PRM, PKCE, RFC 8707 audience validation, no token passthrough, server-side-only DPoP token, and the cheap header-second-factor subset. Notes it is out of PoC scope **by choice, not by constraint** — which is precisely what distinguishes it from the claude.ai half.

### 5.9 `sprint-status.yaml`

Two `backlog` entries with full context inline, and a `last_updated: 2026-08-11` rationale following this file's existing convention of carrying the reasoning in the status file itself.

*Validation note:* the file was checked structurally — 78 story/epic lines well-formed, both new keys resolving to `backlog`, all prose confined after `#`. A full YAML parse was not run: PyYAML is not installed in this environment and this repo has no venv.

---

## 6. Implementation Handoff

**Scope: Moderate** → Product Owner / Scrum Master.

| Recipient | Responsibility |
|---|---|
| **SM (Bob)** | Draft Story 8.8 and 8.9 when they reach the top of the backlog. Both carry a verify-first gate — neither should be drafted as if its central technical question is settled |
| **SM (Bob)** | Redraft Story 7.9 after 7.10 (already `needs-redraft`), now folding in the grant table and revocation UI |
| **Architect (Winston)** | Owns SEC-4. It stays open until Story 8.8 records a decision — including an explicit decision to accept the risk |
| **Dev (Amelia)** | No action. No code changes in this proposal |

### Success criteria

1. SEC-4 no longer reads "not yet closed" — resolved *or* explicitly risk-accepted with a rationale.
2. The `access-log/` grant is verified as Append-without-Write, or corrected to be.
3. Story 7.9's redraft ships a revocation path alongside the mint button.
4. No planning document still claims an OAuth migration path for claude.ai that does not exist.

### Watch item, not scheduled

Anthropic exposing connector OAuth fields on this account. It is the single trigger that reopens §7 for claude.ai, and nothing on our side advances it.

---

## 7. Open Items Carried Forward

| Item | Owner | Note |
|---|---|---|
| Does CSS's `AcpReader` actually evaluate `acp:client` matchers? | Unowned | CSS's own `access-token-verifier` lists client-id application as future work. Testable on a toy policy. **No design may lean on it until tested** |
| Revocation UI shape | Story 7.9 redraft | Was an open unknown in the brief; now has an owner |
| Is an app-side hash/KDF compatible with CSS's client-credentials flow? | Story 8.8 | Gates the layer decision. May require an upstream fork/patch |
| Slug in `solid-mcp_error.log` on upstream failure | Accepted | nginx's own error format; perms-mitigated |

---

## 8. Addendum — Party-Mode Scope Review _(same day, 2026-08-11)_

**Trigger:** Nicolas reviewed this proposal against the MVP's actual priority — the newcomer journey and easy onboarding, no dead-end solutions, Pareto. Participants: PM, UX, Architect, Test Architect, SM.

### The finding about this proposal

Sections 1–7 are technically sound and **product-blind**. They added two security stories, amended one, and corrected a PRD line. The newcomer journey — the only thing gating the pilot narrative — received nothing. The correction below does not retract any analysis above; it re-prioritises what gets built from it.

### Decisions

**SEC-4 → risk accepted, not deferred-open.** Nicolas's input closed it: VPS access is SSH-key only, he holds the sole key, no password auth and no other key holder, and the only data at risk today is his own. Remediation is disproportionate now — LUKS on a running root filesystem is a rebuild-and-migrate, and the app-side alternative may need an upstream fork whose feasibility is itself unknown. `architecture.md` SEC-4 now records a dated acceptance with a rationale instead of an open gap, which also reads better to an external reviewer than an unresolved item with no owner. **Trigger:** the first non-Nicolas person's real data on the VPS. Story 8.8 becomes the pre-pilot gate that owns it.

**Story 8.9 → split.** The tamper-evidence question (is the agent's grant on `access-log/` genuinely Append-without-Write?) is minutes of work and closes a possible real hole, so it stays and **runs first** — before Story 7.9 rewrites the same grant model. Per-slug attribution moved into Story 7.9, where the slug↔identity table already lives. Detection, alerting and identity-level rate limiting moved to `post-poc-backlog.md`: at roughly ten journal entries per week across two users, every entry is an outlier and every alert is noise, which trains the operator to ignore the channel before it carries a real signal.

**Story 7.11 → split.** 7.11a (effective-access resolver, badge truth, single-writer invariant, `profile/card` honesty constraint) stays in scope — Story 7.5 depends on the resolver and the badge currently tells users something unanswerable. 7.11b (roles as grant bundles, collective-account view, receipt surfacing) defers: no PoC journey has two people sharing a pod, so the UI would ship untested against its own use case and the receipts view would render empty. The model is settled in BP-6; only its surface is deferred.

**Story 7.6 → deferred on its own premise.** It opens "as a pod owner with a real, growing pod" and nobody has one. Story 7.3's spine already covers create, upload, read, overwrite, delete and rename.

### New finding, not from the security brief

**Story 7.9's `expiresAt` creates a UX cliff that does not exist today.** The current slug never expires. Introducing expiry without a legible failure path is a net regression: a lapsed connector stops answering inside claude.ai with an opaque MCP error, on a surface we do not own and cannot style. The person cannot read it, cannot self-serve, and what she remembers is that the pod thing broke. Story 7.9 now requires warn-before-the-wall in the grants list, one-action renewal from that same screen, and the expiry named on the onboarding page. **Do not ship `expiresAt` without it.**

**Story 8.7's honest-boundaries section must state SEC-4.** The page tells a second person what the system does and does not guarantee. A known plaintext-credential exposure cannot be omitted from it — naming limits before a user finds them is the project's stated ethic, and an accepted risk is still a risk the reader is entitled to know about.

### Revised sequence

| # | Story | Rationale |
|---|---|---|
| 0 | **8.9** — `access-log/` tamper spike | Minutes. Same grant model 7.9 rewrites |
| 1 | **7.9** — redraft + build (+ attribution, + expiry UX) | Removes the operator from onboarding |
| 2 | **8.7** Task 4+ — real second person walks the page | Validates step 1. Needs a human |
| 3 | **7.11a** — resolver + badge | Unblocks 7.5, fixes a UX untruth |
| 4 | **7.5** — export | Portability is a founding claim |

**Deferred:** 7.11b, 7.6, 8.9's detection half. **Risk-accepted:** 8.8.

**Net effect:** the critical path to *"a second person onboards alone"* goes from five stories to **two stories plus a spike**.

*Validation note (unchanged from §5.9):* `sprint-status.yaml` was re-checked structurally after these edits — 80 story/epic keys, none malformed, all five new or changed keys resolving to their intended values, all prose confined after `#`. A full YAML parse still was not run: PyYAML is not installed here and this repo has no venv.
