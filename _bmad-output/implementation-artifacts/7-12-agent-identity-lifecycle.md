# Story 7.12: Agent Identity Lifecycle

Status: in-progress — Tasks 1-5 implemented and deployed to VPS; Task 6's browser/human-hands steps still open (see Dev Agent Record).

## Story

As **a pod owner setting up more than one AI agent**,
I want to create a named WebID for each agent inside a pod I already own, without creating a throwaway pod for each one,
so that every agent has its own revocable identity and its own attributable trail, and my account stops accumulating pods I cannot delete.

## Context — read this before planning any work

**This story closes the gap that makes throwaway pods accumulate.** Pod creation is currently the *only* path in either UI that mints a WebID. So every time Nicolas wanted a second agent identity he created a pod, and CSS has no pod deletion — the pods are still there (`nicolas/`, `agent/`, `test-xpod/`), unremovable through any HTTP surface.

### The Alex proof case (2026-08-19)

Not a hypothesis — this already happened. Nicolas informally guided Alex (an off-script attempt ahead of Story 8.7's controlled Task 4 run, since Alex already had his own pod and was familiar with the system) through onboarding a connector. **Alex minted straight off his own pod's root WebID** rather than a dedicated agent identity — there was nothing in the current flow to route him otherwise. The result: his connector now carries full authority over his entire pod, not a scoped grant, and the mistake is expensive to notice because the connector *works* — it just works with far more power than intended.

This is exactly AC1's failure mode with a name attached. **A pod owner who already has a pod will default to minting off their own root WebID unless the flow makes "create an agent identity first" the obvious, faster path** — not a side door they'd have to already know to look for. Design the create-identity action to appear *before* the mint action is reachable for someone who owns the target pod, not as a peer option next to it.

**Not our call to fix.** Alex's pod, Alex's connector, Alex's decision — nobody but Alex acts on it. The obligation this story carries is to make the frontend legible enough that he (or anyone in his position) can see the difference between "minted off my root WebID" and "minted off a scoped agent identity" and choose for himself, including choosing to leave it as-is. AC7's grant list already shows which WebID a connector was minted against — worth confirming in this story that it's legible enough for a non-operator to read that distinction unassisted.

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
| ~~Linking a WebID under an owned pod~~ | ~~**No ownership challenge** — `isCreator` short-circuits `ownershipValidator`~~ **FALSE ON THIS DEPLOYMENT** — see below | `LinkWebIdHandler.js` |
| Linking a WebID (corrected, live 2026-08-19) | **Ownership challenge ALWAYS fires.** `infra/css/config.json` uses `config/identity/pod/static.json` + `storage/location/root.json` = ONE root storage, so `getStorageIdentifier(webId)` resolves every WebID to the ROOT pod, owned by account `80f4a781…`, not ours (`0ce7c46b…`) → `isCreator` false → `TokenOwnershipValidator` runs. Answered automatically: CSS's 400 carries the required proof triple, we republish the doc with it, retry, strip it back out. | live failure + `TokenOwnershipValidator.js` |
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

- [x] **Task 1 — Identity creation in `pod-api.js` (AC: 1, 2, 3, 4, 6)**
  - [x] 1.1 `RealBackend.createAgentIdentity(podBaseUrl, agentName)`: validate the name (AC4), compose the WebID as `<podBaseUrl>agents/<name>#me`, write the profile doc, write the public-read ACL, verify anonymously, then link.
  - [x] 1.2 Reuse the existing `_writeAcl` path rather than hand-rolling Turtle — 7.3 fixed a real bug there (`accessTo` targets `./` + basename for files). Do not introduce a second ACL writer.
  - [x] 1.3 The anonymous verification GET must genuinely omit credentials — a same-origin `fetch` with `credentials: 'omit'`, not the authed helper. A check that passes only because it was authenticated proves nothing (AC3).
  - [x] 1.4 Step-labelled errors so AC6's UI can name the failing step.
  - [x] 1.5 `DemoBackend` stub matching the same contract, throwing on the same error shapes (7.9's review found the demo/real divergence worth avoiding).

- [x] **Task 2 — Link management (AC: 5, 7, 8, 9)**
  - [x] 2.1 `listWebIdLinks()` from `controls.account.webId`; join against 7.9's `GET /onboard/grants` by `webId` for AC7's connector column.
  - [x] 2.2 `unlinkWebId(resourceUrl)` — `DELETE` the link resource.
  - [x] 2.3 Mark pod-root identities distinctly from agent identities (AC9). Heuristic: the WebID sits at `<pod>/profile/card#me`. State it as a heuristic in a comment; it is presentation only, nothing authorizes on it.

- [x] **Task 3 — Backoffice UI (AC: 1, 7, 8, 12, 13)**
  - [x] 3.1 "Agent identities" section on the People & apps screen, gated on the same `credsUnlocked`/`credsSignedOut` state as 7.9's connector section.
  - [x] 3.2 Create form: agent name + pod picker (pods the account owns). Inline validation for AC4.
  - [x] 3.3 List per AC7, with the incomplete state from AC6 visually distinct and actionable (retry the failed step).
  - [x] 3.4 Unlink with the arm/confirm-within-4s idiom (7.9's grants list), plus AC8's honest copy. Where a live grant exists, the confirm step says revoke-the-connector-first and links to it.
  - [x] 3.5 AC12's boundary text where a person would look for a delete-pod button.
  - [x] 3.6 Cache-buster bump on `pod-api.js`.

- [x] **Task 4 — Correct the mint gate (AC: 10, 15)**
  - [x] 4.1 Replace `accountControlsWebId()`'s prefix match with a `webIdLinks` membership test in `mcp-connector/src/onboardRouter.js`.
  - [x] 4.2 Keep `isUnderPod()` for the `/grants` and `/revoke` ownership filters — those scope *rows to a viewer* and are a different question from *may this WebID be minted against*. Do not collapse the two.
  - [x] 4.3 Test: a WebID created by this story mints; an unlinked WebID under an owned pod is refused **before** anything is written.

- [x] **Task 5 — Docs (AC: 11, 12)**
  - [x] 5.1 `docs/team-onboarding.md`: agent identities no longer need a pod each; orphan recovery via re-linking; CSS cannot delete a pod. Every existing honest-limits bullet stays.
  - [x] 5.2 `mcp-connector/README.md`: the corrected mint gate, and that a WebID must be linked *and* publicly dereferenceable.

- [ ] **Task 6 — Live verification (AC: 3, 5, 15)** — deployed to VPS 2026-08-19; boot regression (6.5, partial) and endpoint reachability confirmed from this session. The browser/human-hands sub-steps below need Nicolas's own account session (no browser tool and no account password available to this session) — see Dev Agent Record for exactly what's confirmed vs. still open.
  - [x] 6.1 **DONE 2026-08-19.** Nicolas created `agent-smithwhite` (not `hermes-manny` — name differs, substance identical) under `nicolas_claude` through the real UI, in ONE action, with the ownership challenge answered automatically. Verified from outside the browser with credential-free `curl`: anonymous GET of `https://pod.nicolasdb.eu/nicolas_claude/agents/agent-smithwhite` returns **200 `text/turtle`** carrying `solid:oidcIssuer <https://pod.nicolasdb.eu/>` — the exact path `@solid/access-token-verifier` takes, so this WebID can authenticate (AC3). The ownership-proof token was correctly stripped after linking, leaving the minimal profile (AC2). Scoping confirmed minimal: `agents/` container is **not** anonymously listable (401, so agent names aren't enumerable) and `<doc>.acl` requires Control (401) — public read is granted on the one document that needs it and nothing else. UI shows it as an agent identity (🤖) distinct from the four pod-root identities (🗄️), each with its real WebID (AC7, AC9).
  - [x] 6.2 **DONE 2026-08-20.** Nicolas minted a connector against `agent-smithwhite` via the new identity picker (mint dialog defaulted to it, no sign-out needed). Live-confirmed working.
  - [x] 6.3 **DONE 2026-08-20, task premise corrected.** As originally worded this assumed one WebID can carry two live connectors ("mint twice against the same agent WebID," per the pre-correction team-onboarding.md). That premise is FALSE: `identityRegistry.js`'s one-webId-one-slug guard is deliberate architecture — one connector per identity, by design — confirmed by Nicolas ("we did discuss about that feature. No more than ONE connector per webID"). Live-tested: minting a second connector against `agent-smithwhite` was correctly REFUSED. `team-onboarding.md` corrected to match (create a new agent identity per connector, which this story made cheap) — commit `cf9e8c4`. The distinguishable-attribution goal is met at the WEBID level, not by two connectors sharing one: each agent identity IS its own attributable trail, one connector each.
  - [ ] 6.4 **Deferred by Nicolas, not blocking.** Unlink `agent-smithwhite`; confirm new mints refused, and confirm the ~10min token window (corrected from ~1h, see `css_acp_spike_results`) behaves as `css_revocation_model` predicts (authenticates, denied) rather than as a bug. Run whenever that identity is actually being retired — no need to burn a live connector just to close this checkbox. Nicolas separately flagged, correctly, that unlink is currently NOT blocked while a connector is active (advisory copy only) — logged as its own deferred-work item, not a 6.4 blocker.
  - [x] 6.5 Confirm the four pre-existing WebIDs still authenticate (AC15) — partial: `nicolas_claude` and `claude-alex` confirmed authenticating cleanly in the post-deploy boot log (both configured identities logged in with no error). The other two (`nicolas`, `agent`) aren't in mcp-connector's `identities.json` (they're not connector identities) and would need a direct OIDC-login check by Nicolas.

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
- **"Linking a WebID inside a pod your account created skips the ownership challenge."** FALSE on this deployment, and it was this story's load-bearing premise. `pod/static.json` gives ONE root storage, so `isCreator` is always false and `TokenOwnershipValidator` always fires. Found only by deploying and watching it fail on a real click — the handler source alone (read without checking the configured storage strategy) supported the wrong conclusion. See memory `css_static_pods_ownership_challenge`.

## References

- Memory `css_webid_pod_cardinality` — full evidence, handler source, disk-deletion mechanics
- Memory `css_account_pod_lifecycle_facts` — account cookie, `allowRoot:false`, templates
- Memory `architecture_pod_webid_ownership` — per-WebID ownership, `settings.webId`
- Memory `css_revocation_model` — no introspection, ~1h TTL, WAC is the instant layer
- Story 7.9 — mint/grants/revoke, the flow this feeds
- `deferred-work.md` 2026-08-13 — filenames-with-spaces ACL defect (AC4's basis)

## Dev Agent Record

### Debug Log

- **BUG FOUND AND FIXED LIVE (2026-08-19, post-deploy):** the initial
  `listWebIdLinks()`/`accountControlsWebId()` implementation guessed
  `controls.account.webId`'s GET shape as `{ webIdLinks: { <resourceUrl>:
  {webId} } }` — key/value backwards. Nicolas caught it from the deployed UI
  (screenshot: the "Agent identities" list showed link-resource paths like
  `.../account/.../webid/45d6bd89-.../` where a real WebID should be). Read
  `LinkWebIdHandler.js` directly off the running `community-solid-server`
  container (`ssh hetzner`, `docker exec community-solid-server cat
  /community-server/dist/identity/interaction/webid/LinkWebIdHandler.js`) —
  its `getView()` builds `webIdLinks[webId] = resourcePath`, confirming the
  real shape is `{ webIdLinks: { <webId>: <resourceUrl> } }`, the reverse of
  what was implemented. Fixed in both `pod-api.js`'s `listWebIdLinks()` and
  `onboardRouter.js`'s `accountControlsWebId()`, `verify-mint-gate.js`'s
  fixture corrected to match, all offline checks re-run, re-deployed. POST's
  response shape (`{resource, webId, oidcIssuer}`) and DELETE's contract were
  unaffected — `UnlinkWebIdHandler.js` was also read live and confirms DELETE
  on the resource path is correct as implemented.
- **SECOND LIVE FAILURE, same root habit (2026-08-19).** Nicolas ran the flow
  for real (`agent_smith_white` under `nicolas_claude`) and it dead-ended with
  CSS's raw ownership-challenge error dumped into the row. Three distinct
  defects behind one screenshot:
  1. **The webIdLinks fix never reached the browser** — `pod-api.js` was edited
     without bumping `?v=7-12-1`, so the browser served the cached old module.
     The list kept showing resource paths even though the corrected file was on
     the server. Cache-buster bump is not optional bookkeeping; it is the only
     thing that makes a `pod-api.js` change real. Now `?v=7-12-3`.
  2. **This story's load-bearing premise was false** (see Invalidated
     assumptions): `pod/static.json` = one root storage ⇒ `isCreator` always
     false ⇒ `TokenOwnershipValidator` always fires. Fixed properly rather than
     papered over: `_linkWebIdWithOwnershipProof()` parses the token out of
     CSS's 400, republishes the WebID document with the proof triple (the app
     owns that document — it just wrote it), retries the link, then strips the
     triple. One click, per AC1. Proven by
     `mcp-connector/scripts/verify-agent-identity.js` (offline, mocked CSS):
     asserts two link attempts, proof present on the second, token absent
     afterwards, no retry-loop on a non-token failure, cleanup on failure.
  3. **UX failure, called out as such by Nicolas.** Incomplete rows dumped
     CSS's full multi-line error verbatim. Now: one short sentence naming the
     step and what it means, raw detail moved to `title=` for debugging, plus a
     Dismiss action so a dead row can be cleared.
- This is the second time in this story a guessed wire shape needed a live
  correction post-deploy rather than pre-deploy — worth remembering:
  `docker exec <container> cat <path>` against the running CSS container was
  available the whole time and would have caught this before deploy, not
  after. Use it first next time a CSS account-API shape is uncertain, rather
  than reasoning from sibling-endpoint analogy.
- Deployed to the VPS (`make vps-deploy`, 2026-08-19) — mcp-connector rebuilt and
  restarted cleanly; boot log shows both configured identities (`nicolas_claude`,
  `claude-alex`) authenticating with no error, and `/onboard/grants` reachable
  through `pod.nicolasdb.eu` (401 unauthenticated, as expected with no cookie).
  This confirms Task 4's corrected mint gate didn't break the existing boot path,
  but does **not** exercise the new `createAgentIdentity`/`listWebIdLinks`/
  `unlinkWebId` code paths, which only run from an authenticated browser session.
- Task 6.1-6.4 need a live browser session signed in as the pod owner
  (`nicolas_claude`'s account) to click through the new "Agent identities" UI —
  no browser tool and no account password were available to this session, so
  these remain **open**, for Nicolas to run by hand against
  `https://pod.nicolasdb.eu/`. Everything they'd exercise (the create/list/unlink
  code, the corrected mint gate, the docs) is written, deployed, and passes
  offline checks (syntax, tag-balance, `verify-mint-gate.js`) — what's unverified
  is specifically the live wire contract for `controls.account.webId` and the
  end-to-end browser flow.

### Completion Notes

- Task 1: `RealBackend.createAgentIdentity()` in `backoffice/pod-api.js` — four
  step-labelled stages (write-doc → write-acl → verify-public → link), reuses
  `_writeAcl` (no second ACL writer), anonymous `credentials:'omit'` verification
  fetch, best-effort orphan-doc cleanup with loud double-failure logging.
  `DemoBackend` parity added with a `_demoFailStep` hook for exercising the
  incomplete-state UI offline.
- Task 2: `listWebIdLinks()`/`unlinkWebId()` added to both backends; AC9's
  pod-root-vs-agent marking is a presentation-only heuristic (`/profile/card#me`
  suffix), documented as such in the code.
- Task 3: new "Agent identities" section in `backoffice/index.html`'s People &
  apps screen — same `credsUnlocked`/`credsSignedOut` gating, arm/confirm-4s
  unlink idiom (mirrors 7.9's grant revoke), a client-side-tracked
  `agentIncomplete` list so a failed create is shown as an incomplete row with
  retry (AC6) rather than a dead-end toast, AC12's no-delete-pod boundary text,
  cache-buster bumped to `?v=7-12-1`.
- Task 4: `accountControlsWebId()` in `mcp-connector/src/onboardRouter.js`
  rewritten to check `controls.account.webId` link membership instead of pod
  ownership prefix-matching. `isUnderPod()`/`fetchOwnedPodPrefixes()` untouched
  (still used by `/grants`/`/revoke`, a different question per Task 4.2).
  Verified offline against a mocked `fetch` in
  `mcp-connector/scripts/verify-mint-gate.js` (Task 4.3's two cases + a
  fails-closed case) — all pass.
- Task 5: `docs/team-onboarding.md` step (c) rewritten to create an agent
  identity inside the existing data pod rather than a second pod; two new
  honest-limits bullets (no pod deletion exists; unlinking doesn't lose the pod).
  `mcp-connector/README.md` documents the corrected mint gate and the
  linked-AND-public-dereferenceable requirement.
- Task 6: deploy done, boot/endpoint regression checks done from this session
  (see Debug Log). The remaining sub-steps require a live browser session as
  the pod owner and are left for Nicolas — story Status is `in-progress`, not
  `review`, until those close (per this workflow's own completion gate: all
  tasks must be `[x]` before moving to review).

## File List

- `backoffice/pod-api.js` — `createAgentIdentity`, `listWebIdLinks`,
  `unlinkWebId` (RealBackend + DemoBackend), `slugifyAgentName` helper
- `backoffice/index.html` — "Agent identities" section, state, methods, view
  derivation; cache-buster bump
- `mcp-connector/src/onboardRouter.js` — `accountControlsWebId()` rewritten;
  exported for testing
- `mcp-connector/scripts/verify-mint-gate.js` — new, Task 4.3's offline test
- `mcp-connector/scripts/verify-agent-identity.js` — new, offline test of
  `createAgentIdentity`'s ownership-challenge path, failure cleanup, and slug rejection
- `mcp-connector/README.md` — mint-gate + dereferenceability documentation
- `docs/team-onboarding.md` — step (c) rewritten; two new honest-limits bullets
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status flipped to
  ready-for-dev then in-progress

## Change Log

| Date | Change |
|---|---|
| 2026-08-19 | Drafted from the live CSS cardinality investigation |
| 2026-08-19 | Marked ready-for-dev by Nicolas; Tasks 1-5 implemented, deployed to VPS, boot/endpoint regression confirmed. Task 6's browser/human-hands live steps left open — no browser tool or account password available to this session. Status: in-progress. |
| 2026-08-19 | **Scope extended by Nicolas** (crosses this story's "does not change the mint flow's UX" fence, decided deliberately): mint dialog now has an IDENTITY PICKER. Source-verified why this is safe and correct — `CreateClientCredentialsHandler.handle()` gates on `isLinked(webId, accountId)`, i.e. ACCOUNT-scoped, so the OIDC-signed-in WebID is irrelevant and any linked identity is mintable from the current session. Previously the mint bound to `state.webId` (whoever you signed in as), which is precisely the Alex footgun: the copy told you to sign in again as the agent rather than letting you just choose. Picker defaults to a dedicated agent identity when one exists, states each option's blast radius on the option itself (pod-root = "full control of &lt;pod&gt;", agent = "reaches only what you grant it"), and the summary sentence below updates with the choice. Also recorded: CSS's stock account page claims registered WebIDs "have full control access to the pods registered for this account" — **false on this deployment**, verified against every pod's root `.acl` (each names only its own pod-root WebID; `agent-smithwhite#me` appears in none). |
| 2026-08-20 | Task 6.2/6.3 done live. 6.2: connector minted against `agent-smithwhite` via the new identity picker. 6.3: task's original premise was wrong (assumed multiple connectors per WebID) — corrected after Nicolas confirmed one-connector-per-WebID is deliberate architecture; `team-onboarding.md`'s contradicting claim fixed (commit `cf9e8c4`). Two gaps found live and logged to deferred-work rather than fixed inline: the mint-refusal error is unhelpfully generic (cleanup already correct, message isn't), and unlink is not blocked while a connector is active (advisory copy only, not a guard — Nicolas's own observation). 6.4 deferred by Nicolas (not blocking) — runs when `agent-smithwhite` is actually retired. Also corrected: revocation/token-TTL copy changed from "~1h" to "~10 minutes" across index.html and team-onboarding.md, matching the measured client_credentials TTL (`css_acp_spike_results`). Status remains in-progress (6.4 open, so not all tasks are [x] yet — no move to review). |
| 2026-08-19 | Task 6.1 PASSES live after the fixes: `agent-smithwhite` created in one action under `nicolas_claude`, anonymous GET 200 with the issuer triple, proof token stripped, container not enumerable. AC1/2/3/5/7/9 confirmed live. 6.2-6.4 (connector mint against it, dual-grant attribution, unlink behaviour) still open. |
| 2026-08-19 | Nicolas ran it live; it failed. Three fixes: cache-buster bump (the earlier webIdLinks fix was never being served), automatic handling of CSS's ownership challenge (this story's "no challenge" premise was false under `pod/static.json` — corrected in Verified state + Invalidated assumptions), and legible incomplete-row copy replacing a raw CSS error dump. New offline test `verify-agent-identity.js` covers the challenge path. Redeployed. |
