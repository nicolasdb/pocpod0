# Story 7.4: Apps & Credentials — Connect External Apps to Your Pod

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **pod owner**,
I want to see which apps and agents currently have access to my pod, and to mint, name, and revoke machine credentials that let an external app (a Discord bot, a Matrix bridge, a script) read or write on my behalf,
so that I can safely wire automated tools into my pod and cut any of them off the moment I want to — without hand-crafting OIDC flows or exposing my password.

## Context / Why now

The live audit (throwaway-audit-0723, 2026-07-23 — see `deferred-work.md` and memory `css_acl_portability_audit`) proved the full Client Credentials path works on our CSS `v0.5` and, crucially, that credentials are **revocable over HTTP**:

- Mint: `POST /.account/account/{id}/client-credentials/` body `{name, webId}` → `{id, secret, resource}` (secret shown **once**).
- Use: `POST /.oidc/token` with HTTP Basic `id:secret` (url-encoded) + a DPoP proof, body `grant_type=client_credentials&scope=webid` → `access_token`; then requests carry `Authorization: DPoP <token>` + per-request DPoP proof.
- List: `GET /.account/account/{id}/client-credentials/` → `{clientCredentials: { name_uuid: resourceUrl, ... }}`.
- Revoke: `DELETE {resourceUrl}` → 200. **Live-confirmed.**
- Gotcha: account `logout` invalidates the CSS-Account-Token immediately — revoke before logout, or re-login.

This is the enabling story for the Discord/Matrix bot bridges (Epic 4 territory) and answers Nicolas's own question ("credential token is some sort of API key, right?" — yes). It also gives the "People & apps" screen a real *outbound* half: not just who can see my space, but which credentials I've issued.

**Security note (WAC limitation, honest framing):** CSS default is WAC, which cannot restrict a credential to a *specific app's* data — a credential bound to your WebID can act with whatever access that WebID has. ACP (the future CSS default) is what would scope per-app. Until then, treat every issued credential as "acts as me" and lean on: least-privilege ACLs on the target resources, clear naming, and easy revocation. This must be surfaced to the user in plain language, not hidden.

## Acceptance Criteria

1. **List issued credentials:** the backoffice shows all client-credentials currently issued for the owner's account (name + when, from `GET .../client-credentials/`), including a clear empty state.
2. **Mint a credential:** the owner can create a named credential (name + target WebID, defaulting to their own) via `POST .../client-credentials/`; the resulting **secret is displayed exactly once** with a copy affordance and an explicit "you won't see this again — store it now" warning. Never persisted in app state or logged.
3. **Revoke a credential:** the owner can revoke any listed credential (`DELETE {resourceUrl}` → success), and it disappears from the list; a subsequent token request with that credential fails (`invalid_client`). Revoke asks for confirmation.
4. **Connection recipe:** for a freshly minted credential, the UI shows a copy-pasteable, plain-language "how to connect" snippet (token endpoint, grant type, scope, and that DPoP is required) — enough for a bot author to authenticate. No secret is baked into a stored/exported artifact.
5. **Outbound half of "People & apps":** the People & apps surface distinguishes *agents who can see my space* (inbound access, WAC grants) from *credentials I have issued* (outbound machine access), so the two concepts aren't conflated.
6. **Honest security framing:** the UI states, in plain language, that an issued credential acts with the owner's identity/access (WAC per-app limitation) and that the safe controls are least-privilege ACLs + revocation. No overclaiming of per-app sandboxing we don't have.
7. **Secret hygiene:** the secret is only ever held transiently in the DOM for display/copy, never written to `localStorage`/app state/logs; closing the reveal clears it.
8. **WCAG 2.1 AA** on all new controls; **no regression** to existing account/login/People-&-apps behavior.

## Tasks / Subtasks

- [ ] Task 1: Account-session plumbing for the credentials API (AC: #1, #2, #3)
  - [ ] 1.1 Establish the authenticated account context the credentials endpoints need (CSS-Account-Token from the owner's existing login session) and resolve the account-scoped controls (`controls.account.clientCredentials`) the same way 7.1's registration flow resolves controls.
  - [ ] 1.2 Add `RealBackend` methods: `listClientCredentials()`, `createClientCredential(name, webId)`, `revokeClientCredential(resourceUrl)` — thin wrappers over the confirmed endpoints.
  - [ ] 1.3 Handle the logout/token-invalidation gotcha: do not eagerly log out the account session while the credentials view is open; re-auth gracefully if the token has expired.
- [ ] Task 2: Credentials UI (AC: #1, #2, #3, #4, #7)
  - [ ] 2.1 List view (name, resource, revoke button) with empty state, under an "Apps & credentials" section of People & apps.
  - [ ] 2.2 Mint flow: name + WebID (default self) → create → **one-time secret reveal** with copy + "store it now" warning; clear on close.
  - [ ] 2.3 Revoke flow with confirmation; refresh list; (optional) verify by attempting a token request and showing it now fails.
  - [ ] 2.4 "How to connect" recipe panel for the minted credential (endpoint/grant/scope/DPoP note), copy-pasteable, secret-free.
- [ ] Task 3: People & apps inbound/outbound split (AC: #5, #6)
  - [ ] 3.1 Reframe the existing People & apps screen so inbound access grants and outbound issued credentials are visually distinct sections.
  - [ ] 3.2 Add the plain-language WAC-limitation note (acts-as-me + revoke/ACL are the real controls).
- [ ] Task 4: Security hardening + a11y + regression (AC: #7, #8)
  - [ ] 4.1 Audit that the secret never touches persistent storage or logs; transient DOM only.
  - [ ] 4.2 Contrast/focus-visible/keyboard on all new controls.
  - [ ] 4.3 Regression pass on account/login/People-&-apps.

## Dev Notes

- **Flow is proven end-to-end** (mint → token → authed request → revoke → token now fails) via the audit's manual DPoP script. A browser implementation can lean on the pinned `@inrupt/solid-client-authn-browser` for the DPoP/token mechanics if it exposes a client-credentials path; otherwise the raw `/.oidc/token` + DPoP flow is documented and small. Confirm which the pinned version (authn-browser 2.3.0) supports before choosing.
- **Secret is shown once by CSS design** — there is no re-fetch. The whole UX must respect that (copy-first, warn hard, never store).
- **DPoP is mandatory** for CSS client-credentials tokens — the connection recipe must say so, or a bot author using plain Bearer will fail.
- **Revocation is the primary safety control** given WAC's per-app blindness. Make revoke fast, obvious, and confirmed.
- **Ties to Epic 4:** this is the mechanism a Discord/Matrix bridge uses to write into a pod unattended. Keep the recipe generic (not Discord-specific) so it serves any bridge.
- **CSS version pinning:** docs note the credential API "currently still requires email+password on some paths" as a temporary upstream state — verify against our deployed `v0.5` behavior, don't assume a newer/older shape.
- **Design principles:** one primary action per screen, progressive disclosure (recipe behind a "connect an app" affordance), reversibility (revoke) — same bar as 7.1–7.3.

### Testing Requirements

- No automated test harness in `backoffice/` — verify manually, same discipline as 7.1/7.2/7.3.
  - AC2/AC3: live round-trip is mandatory — mint a real credential, use it to fetch an `access_token` via `/.oidc/token` (Basic + DPoP), confirm an authed request succeeds, then revoke and confirm the same request now fails (`invalid_client`/401). Don't accept "UI shows revoked" as proof.
  - AC7 (secret hygiene): manually inspect `localStorage`/app state/console after a mint+close cycle to confirm the secret isn't retained.
  - AC8: manually re-run the existing account/login/People-&-apps flow before calling the story done.
  - DPoP proof generation (ES256 via node `crypto`, `ath` = b64url(sha256(token))) was hand-rolled during the audit script; if `@inrupt/solid-client-authn-browser` 2.3.0 doesn't expose a client-credentials helper, the dev agent may need to port that logic into the browser (WebCrypto SubtleCrypto, not node `crypto`) — flag this explicitly if it comes up, it's the trickiest part of the story.

### Invalidated Assumptions

- **Assumption (from 7.1 era):** "there's no HTTP way to remove things from a CSS account." → **Reality (live-verified):** client-credentials ARE HTTP-deletable (`DELETE {resourceUrl}` → 200). (Accounts/pods still are not — that's a separate ops problem, see 7.5/ops.)
- **Assumption:** "a credential can be scoped to a single app." → **Reality:** under WAC it acts with the owner's full WebID access; per-app scoping needs ACP, which is not the CSS default yet. Frame honestly.

### Project Structure Notes

- Changes land in `backoffice/index.html` (Apps & credentials UI within People & apps) and `backoffice/pod-api.js` (`RealBackend` credential methods; demo-mode stubs so offline preview shows the UI with fake data). No `infra/css/` change expected.
- Reuse 7.1's account-controls resolution pattern; keep pinned Inrupt versions.

### References

- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Live CSS ACL/portability audit (2026-07-23)] — confirmed mint/list/token/revoke flow + the logout gotcha
- Memory: `css_acl_portability_audit` — exact endpoints, DPoP token shape, revoke confirmation
- [Source: https://communitysolidserver.github.io/CommunitySolidServer/latest/usage/client-credentials/] — upstream client-credentials doc (verify against deployed v0.5)
- [Source: https://communitysolidserver.github.io/CommunitySolidServer/latest/usage/authorization-methods/] — WAC vs ACP; why per-app scoping needs ACP
- [Source: backoffice/pod-api.js] — `registerAccount`/controls-resolution pattern to mirror (`:328`)
- Memory: `feedback_wcag_aa_standard`, `story_7_1_backoffice_deploy_patterns`
- Relates to: `project_two_products_vision`, Epic 4 Discord/Matrix bridge work (memory `story_4_0_openclaw_discord_patterns`)

## Dev Agent Record

### Context Reference

### Agent Model Used

### Completion Notes List

### File List

## Change Log

| Date       | Change |
|------------|--------|
| 2026-07-23 | Drafted from live audit. Client-credentials mint/list/revoke (all confirmed working incl. HTTP revoke), one-time-secret UX, connection recipe for bot bridges, People-&-apps inbound/outbound split, honest WAC per-app-limitation framing. |
