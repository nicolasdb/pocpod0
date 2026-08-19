# Story 7.12: Agent Identity Lifecycle

Status: drafted — not yet ready-for-dev. **Live evidence this is blocking, not speculative:** see Context, "The Alex proof case."

## Story

As **a pod owner setting up more than one AI agent**,
I want to create a named WebID for each agent inside a pod I already own, without creating a throwaway pod for each one,
so that every agent has its own revocable identity and its own attributable trail, and my account stops accumulating pods I cannot delete.

## Context — read this before planning any work

**This story closes the gap that makes throwaway pods accumulate.** Pod creation is currently the *only* path in either UI that mints a WebID. So every time Nicolas wanted a second agent identity he created a pod, and CSS has no pod deletion — the pods are still there (`nicolas/`, `agent/`, `test-xpod/`), unremovable through any HTTP surface.

### The Alex proof case (2026-08-19)

Not a hypothesis — this already happened. Nicolas informally guided Alex (an off-script attempt ahead of Story 8.7's controlled Task 4 run, since Alex already had his own pod and was familiar with the system) through onboarding a connector. **Alex minted straight off his own pod's root WebID** rather than a dedicated agent identity — there was nothing in the current flow to route him otherwise. The result: his connector now carries full authority over his entire pod, not a scoped grant, and the mistake is expensive to notice because the connector *works* — it just works with far more power than intended.

This is exactly AC1's failure mode with a name attached. **A pod owner who already has a pod will default to minting off their own root WebID unless the flow makes "create an agent identity first" the obvious, faster path** — not a side door they'd have to already know to look for. Design the create-identity action to appear *before* the mint action is reachable for someone who owns the target pod, not as a peer option next to it.

Open, logged in Story 8.7's Task 4.0: whether to remediate Alex's connector (revoke + re-mint against a proper agent identity) now or after this story ships.

The fix is not a cleanup tool. It is removing the reason the mess is created.

### The model, verified live 2026-08-19 (do not re-derive)

CSS keeps **three** objects and **two independent** registrations. Conflating them is what produced the wrong mental model:

| Link | Grants | Existing UI |
|---|---|---|
| WebID → **Account** (`webIdLink`) | can authenticate as it; **gates credential minting** | CSS stock "Link WebID" |
| WebID → **Pod** (`owner`) | full Control over **all** resources in that pod | CSS stock "Pod settings → Add owner" |

A WebID's *location* (which pod hosts its profile document) is unrelated to which pods it controls. **WebID : Pod is n:1, not 1:1.** One pod can host many WebID documents.

Live proof, from the account record on the VPS: `test-xpod`'s `pod.<id>.owner` still names `test-xpod/profile/card#me`, while that WebID is absent from `webIdLink` — the link was deleted, the owner record survived. Independent, as claimed.

See memory `css_webid_pod_cardinality` for the full evidence, including the exact handler source.

### What CSS actually enforces

- `LinkWebIdHandler.js` — resolves a WebID to its **storage/pod**; if `accountId === pod.accountId`, it links with **no ownership challenge**. The check is per-pod, not per-document, so any number of WebID docs under a pod you created link freely.
- `CreateClientCredentialsHandler.js` — `if (!await this.webIdStore.isLinked(webId, accountId)) throw`. **The webIdLink is the mint gate.**
- `@solid/access-token-verifier` — the resource server **dereferences the WebID anonymously** and requires `<webid> solid:oidcIssuer <iss>`. **A WebID document that is not publicly readable cannot authenticate.** Non-negotiable, and the single easiest thing to get wrong here.

### Scope fence

This story:

- **DOES** create a WebID: write the profile document, set its public-read ACL, link it to the account.
- **DOES** list and unlink agent identities.
- **DOES NOT** build pod deletion. CSS has no `DeletePodHandler`; the disk path is a sudo operation with a three-place edit and a stopped server (memory `css_webid_pod_cardinality`). If it is ever wanted it is an operator runbook, not a UI. **Do not put a delete-pod button in the backoffice.**
- **DOES NOT** add "Add owner" to the backoffice. Owner is full Control over every resource in the pod — the opposite of what a scoped agent should hold. It stays a CSS-stock expert operation.
- **DOES NOT** change the mint flow's UX (Story 7.9 owns it). It only makes a new WebID *available* to that flow.
- **DOES NOT** perform WAC grants on data pods. Granting stays owner-driven and manual (8.5's corrected scope), same boundary 7.9 respects.

## Verified state (do not re-derive)

| Fact | Value | Source |
|---|---|---|
| WebID : Pod cardinality | **n:1** — many WebIDs per pod | `LinkWebIdHandler.js`, live 2026-08-19 |
| Linking a WebID under an owned pod | **No ownership challenge** — `isCreator` short-circuits `ownershipValidator` | `LinkWebIdHandler.js` |
| Credential-mint gate | `webIdStore.isLinked(webId, accountId)` — **not** pod ownership | `CreateClientCredentialsHandler.js` |
| WebID doc must be public-readable | RS dereferences anonymously (bare `node-fetch`) for `solid:oidcIssuer`; else `WebidDereferencingError` | `@solid/access-token-verifier/dist/algorithm/retrieveWebidTrustedOidcIssuers.js` |
| Minimum WebID doc | `<webid> solid:oidcIssuer <ISSUER>; a foaf:Person.` | `templates/pod/base/profile/card$.ttl.hbs` |
| Stock profile ACL | public `foaf:Agent` Read on the card, owner RWC | `templates/pod/wac/profile/card.acl.hbs` |
| Link endpoint | `POST controls.account.webId` `{webId}` → `{resource, webId, oidcIssuer}` | account API v0.5 |
| Unlink endpoint | `DELETE <webIdLink resourceUrl>` | account API v0.5 |
| Pod deletion | **No `DeletePodHandler` exists.** `dist/identity/interaction/pod/` has Create + UpdateOwner only | live container |
| Deleting a webIdLink | Does **not** delete the profile doc; pod stays. Re-linking restores control | `test-xpod/profile/card` → 200 |
| Our mint's ownership check | `accountControlsWebId()` prefix-matches pod baseUrls — **looser than CSS's real rule** | `mcp-connector/src/onboardRouter.js` |
| ACL writer | `_writeAcl` targets `./` + basename for files, `./` only for containers (fixed in 7.3) | `backoffice/pod-api.js` |
| Filenames with spaces break ACL Turtle | Known open defect — agent names must be slug-safe | `deferred-work.md` (2026-08-13) |

## Acceptance Criteria

1. **One action creates a usable agent identity.** From the backoffice, a signed-in person names an agent, picks a pod they own, and gets back a WebID that is immediately mintable — profile document written, public-read ACL set, linked to the account, all in one action. No CSS-stock page, no hand-written Turtle.

2. **The profile document is correct and minimal.** It contains exactly `solid:oidcIssuer <ISSUER>` and `a foaf:Person`, plus `foaf:name` for the agent label, mirroring `card$.ttl.hbs`. The issuer is read from configuration, never hardcoded per-environment.

3. **The profile document is publicly readable, and this is verified, not assumed.** After writing, the flow performs an **anonymous** (credential-free) GET of the WebID document and asserts it returns 200 and parses with the `solid:oidcIssuer` triple present. **This is the failure mode that produces an opaque authentication error hours later, on a surface we do not own** — catch it at creation. If the check fails, the identity is not reported as ready and the UI says which step failed.

4. **Agent names are constrained to slug-safe characters** before they reach a URL or an ACL. No spaces, no `/ \ < > " '`, no control characters — `deferred-work.md` (2026-08-13) records that a filename with spaces makes `_writeAcl` emit Turtle that is invalid per the `IRIREF` grammar. Reject with a legible message rather than sanitizing silently, so the name the person typed is the name they get.

5. **The identity is linked to the account, and the link is what the UI reports.** `POST controls.account.webId`. Because CSS gates *credential minting* on `isLinked` and not on pod ownership, an unlinked WebID would pass our own mint check and then fail inside CSS with a generic 400 — so the link must be confirmed before the identity is presented as usable.

6. **Partial failure never leaves a half-made identity presented as whole.** The flow is write-doc → write-ACL → verify-public → link, and each step can fail. On failure at any step, the UI names the step and the identity is listed as **incomplete**, not as ready. Best-effort cleanup of the written document on a link failure, logged loudly on double-failure (Story 7.9 AC2.8's precedent).

7. **Agent identities are listed with their real state.** For each: name, WebID, host pod, linked-or-not, and whether a connector grant currently exists against it (join on 7.9's grant table by `webId`). A WebID with no grant reads as "no connector" — not as an error, and not as an empty space.

8. **Unlinking is available and honest about what it does and does not do.** Unlinking revokes the ability to authenticate as that WebID and blocks new credential minting. It does **not** delete the profile document, does **not** remove WAC grants already written on other pods, and does **not** invalidate an already-issued token (memory `css_revocation_model`: CSS never introspects, ~1h TTL). The UI says this in the same breath. **Where a live connector grant exists for that WebID, revoke the grant first** — 7.9's revoke is the instant layer because it removes WAC; unlinking alone is not a revocation.

9. **Existing pod-bound WebIDs are shown alongside, not hidden.** The four WebIDs already linked (`hyperscope_ndb`, `nicolas_claude`, `nicolas`, `agent`) must appear in the same list as newly created agent identities, clearly marked as pod-root identities. A list that shows only what this story created would misrepresent what can reach the pods.

10. **The mint gate is corrected to match CSS.** `accountControlsWebId()` currently prefix-matches owned pod baseUrls; CSS's actual rule is `isLinked`. Switch to the account's `webIdLinks` list — same authed `/.account/` fetch the endpoint already makes, strictly more correct, less code. A WebID this story creates must pass; a WebID merely sitting under an owned pod but unlinked must not.

11. **Orphan recovery is documented and reachable.** Deleting a link strands a pod, and the recovery is to re-link the WebID whose document still exists. This must appear in `docs/team-onboarding.md`'s honest-limits section, because the person who hits it will otherwise conclude the pod is lost.

12. **The pod-deletion boundary is stated, not silently omitted.** CSS cannot delete a pod. `docs/team-onboarding.md` says so plainly, alongside the reason this story exists — that agent identities no longer require a pod each. No UI affordance implies otherwise. **No delete-pod button.**

13. **WCAG 2.1 AA.** 4.5:1 contrast, `focus-visible` on every new control, no colour-only state (linked/unlinked/incomplete carry text). Same standard as 7.3/7.4/7.10.

14. **Secrets stay out of everything.** This flow handles no `clientSecret`, and must not start. The account cookie is read per-request, never logged, never persisted (7.9 AC17's posture). Note for whoever probes the account store: `.internal/accounts/data/<accountId>$.json` holds **every client-credential secret in plaintext** (SEC-4, risk-accepted) — prefer field-selective reads over `cat` when debugging.

15. **No regression.** 7.9's mint/list/revoke still work end-to-end; the four existing linked WebIDs still authenticate; `verify-http.js` passes; `/healthz` unchanged.

## Tasks / Subtasks

- [ ] **Task 1 — Identity creation in `pod-api.js` (AC: 1, 2, 3, 4, 6)**
  - [ ] 1.1 `RealBackend.createAgentIdentity(podBaseUrl, agentName)`: validate the name (AC4), compose the WebID as `<podBaseUrl>agents/<name>#me`, write the profile doc, write the public-read ACL, verify anonymously, then link.
  - [ ] 1.2 Reuse the existing `_writeAcl` path rather than hand-rolling Turtle — 7.3 fixed a real bug there (`accessTo` targets `./` + basename for files). Do not introduce a second ACL writer.
  - [ ] 1.3 The anonymous verification GET must genuinely omit credentials — a same-origin `fetch` with `credentials: 'omit'`, not the authed helper. A check that passes only because it was authenticated proves nothing (AC3).
  - [ ] 1.4 Step-labelled errors so AC6's UI can name the failing step.
  - [ ] 1.5 `DemoBackend` stub matching the same contract, throwing on the same error shapes (7.9's review found the demo/real divergence worth avoiding).

- [ ] **Task 2 — Link management (AC: 5, 7, 8, 9)**
  - [ ] 2.1 `listWebIdLinks()` from `controls.account.webId`; join against 7.9's `GET /onboard/grants` by `webId` for AC7's connector column.
  - [ ] 2.2 `unlinkWebId(resourceUrl)` — `DELETE` the link resource.
  - [ ] 2.3 Mark pod-root identities distinctly from agent identities (AC9). Heuristic: the WebID sits at `<pod>/profile/card#me`. State it as a heuristic in a comment; it is presentation only, nothing authorizes on it.

- [ ] **Task 3 — Backoffice UI (AC: 1, 7, 8, 12, 13)**
  - [ ] 3.1 "Agent identities" section on the People & apps screen, gated on the same `credsUnlocked`/`credsSignedOut` state as 7.9's connector section.
  - [ ] 3.2 Create form: agent name + pod picker (pods the account owns). Inline validation for AC4.
  - [ ] 3.3 List per AC7, with the incomplete state from AC6 visually distinct and actionable (retry the failed step).
  - [ ] 3.4 Unlink with the arm/confirm-within-4s idiom (7.9's grants list), plus AC8's honest copy. Where a live grant exists, the confirm step says revoke-the-connector-first and links to it.
  - [ ] 3.5 AC12's boundary text where a person would look for a delete-pod button.
  - [ ] 3.6 Cache-buster bump on `pod-api.js`.

- [ ] **Task 4 — Correct the mint gate (AC: 10, 15)**
  - [ ] 4.1 Replace `accountControlsWebId()`'s prefix match with a `webIdLinks` membership test in `mcp-connector/src/onboardRouter.js`.
  - [ ] 4.2 Keep `isUnderPod()` for the `/grants` and `/revoke` ownership filters — those scope *rows to a viewer* and are a different question from *may this WebID be minted against*. Do not collapse the two.
  - [ ] 4.3 Test: a WebID created by this story mints; an unlinked WebID under an owned pod is refused **before** anything is written.

- [ ] **Task 5 — Docs (AC: 11, 12)**
  - [ ] 5.1 `docs/team-onboarding.md`: agent identities no longer need a pod each; orphan recovery via re-linking; CSS cannot delete a pod. Every existing honest-limits bullet stays.
  - [ ] 5.2 `mcp-connector/README.md`: the corrected mint gate, and that a WebID must be linked *and* publicly dereferenceable.

- [ ] **Task 6 — Live verification (AC: 3, 5, 15)**
  - [ ] 6.1 Create `hermes-manny` under `nicolas_claude` through the real UI. Confirm anonymous GET of the WebID doc returns 200 with the issuer triple.
  - [ ] 6.2 Mint a connector against it; confirm it authenticates on first request with no restart (7.9 AC15's lazy path).
  - [ ] 6.3 Confirm two live connectors on **one pod** produce distinguishable `grantId`s in the access journal — the attribution this whole approach exists for.
  - [ ] 6.4 Unlink; confirm new mints refused, and confirm the ~1h token window behaves as `css_revocation_model` predicts (authenticates, denied by WAC) rather than as a bug.
  - [ ] 6.5 Confirm the four pre-existing WebIDs still authenticate (AC15).

## Dev Notes

### The one thing most likely to go wrong

**A WebID document that is not publicly readable.** The resource server dereferences it with a bare `node-fetch` and no credentials, purely to read `solid:oidcIssuer`. If that GET 401s, authentication fails with `WebidDereferencingError` — and the failure surfaces at *token use*, inside claude.ai or Hermes, long after creation, with an error we cannot style or explain.

This is why AC3 demands an anonymous verification at creation time rather than trusting the ACL write. It is the same class of failure 7.9's expiry discussion identified: a cliff on a surface we do not own.

### Why not "Add owner"

CSS's Pod settings page has an "Add owner" field that attaches a WebID to a pod, and it looks like exactly what this story wants. It is not. The page states it plainly: *"All these WebIDs have full control access over all resources in the pod."* Owner is Control over everything, permanently, with no scoping. An agent should hold narrow WAC on specific containers instead.

Add owner stays a CSS-stock expert operation. Do not surface it.

### Why pod deletion is out of scope, in one paragraph

`dist/identity/interaction/pod/` contains `CreatePodHandler`, `UpdateOwnerHandler` and `PodIdRoute`. There is no delete handler; the account API cannot remove a pod at all. Disk-level removal *does* work but is not `rm -r` alone — the pod stays registered in `payload.pod.<podId>` inside `.internal/accounts/data/<accountId>$.json` and in `.internal/accounts/index/pod/baseUrl/<urlencoded>$.json`, so a folder-only delete leaves a pod that still lists and whose globally-unique name stays reserved (409 on re-create). All three live under `/var/lib/docker/volumes/pocpod0_css-data/_data/`, `root`-owned, sudo required, and CSS must be **stopped** first because `.internal/locks/` is live. That is an operator runbook with a backup step, not a button. This story removes the *reason* pods accumulate instead.

### Reuse — do not re-derive

- ACL writing: `_writeAcl` in `backoffice/pod-api.js` (7.3-corrected).
- One-time-secret / arm-confirm idioms: 7.4 and 7.9's sections in `backoffice/index.html`.
- Grant listing: 7.9's `GET /onboard/grants`, already returns `webId` per row.
- Cookie-session pattern: 7.10's `_accountControls()`, `credentials: 'include'`, no password re-entry.

### Invalidated assumptions

- **"Every agent needs its own pod."** False. Held until 2026-08-19; it is what produced `nicolas/`, `agent/`, `test-xpod/`.
- **"WebID:Pod is 1:1."** False. n:1.
- **"CSS can delete a pod if you find the right endpoint."** False — no handler exists.
- **"An orphaned pod is lost."** False — the profile doc survives an unlink; re-linking restores control.

## References

- Memory `css_webid_pod_cardinality` — full evidence, handler source, disk-deletion mechanics
- Memory `css_account_pod_lifecycle_facts` — account cookie, `allowRoot:false`, templates
- Memory `architecture_pod_webid_ownership` — per-WebID ownership, `settings.webId`
- Memory `css_revocation_model` — no introspection, ~1h TTL, WAC is the instant layer
- Story 7.9 — mint/grants/revoke, the flow this feeds
- `deferred-work.md` 2026-08-13 — filenames-with-spaces ACL defect (AC4's basis)

## Change Log

| Date | Change |
|---|---|
| 2026-08-19 | Drafted from the live CSS cardinality investigation |
