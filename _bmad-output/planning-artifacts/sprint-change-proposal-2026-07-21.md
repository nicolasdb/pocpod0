# Sprint Change Proposal — 2026-07-21

**Trigger:** Pivot request from Nicolas. Park Epic 4 (capstone) temporarily; prioritize real-user CSS experience: account onboarding, pod creation, and a pod content/ACL management backoffice.

## 1. Issue Summary

The POC stack is now live on the VPS with CSS served at `https://pod.nicolasdb.eu/` (Story 4.4.1). First real users are imminent, but the CSS default account-registration UX is developer-grade and there is no user-facing surface to manage pod content or ACLs. Nicolas produced a high-fidelity, **runnable** mockup ("SOLID Pod Management Interface.zip", built with Claude design): a 3-file static app (`index.html`, `pod-api.js`, `support.js`) with real Inrupt SOLID code (SOLID-OIDC login, file CRUD, `universalAccess` ACL management, WAC progressive disclosure) plus a demo backend and a 10-chapter no-jargon onboarding flow.

Remaining gaps (per the bundle's HANDOFF.md):
1. New-account creation is simulated — must wire to the CSS `.account/` controls API (register + create pod + credential), or link out to CSS registration.
2. The CSS default registration page must be restyled to match the backoffice design language (cognitive-ergonomics care: Miller/Hick, progressive disclosure, Lexend/Atkinson Hyperlegible, sage accent `#3d6b52`).

## 2. Impact Analysis

- **Epic impact:** No existing epic covers pod-owner self-service UX. Epic 4 is parked (status stays `in-progress`; Story 4.1 remains `ready-for-dev` for when it resumes). New **Epic 7: Pod Owner Experience** created.
- **Story impact:** Two new stories (7.1, 7.2). Story 4.3 (Nicolas onboarding proof) becomes a natural consumer of this work — link, don't merge.
- **Artifact conflicts:** None. PRD/architecture untouched (static app beside CSS, existing nginx-gateway pattern from 4.4.1). epics.md and sprint-status.yaml get additive entries.
- **Technical impact:** Backoffice served same-origin at `https://pod.nicolasdb.eu/` root via CSS `StaticAssetHandler`, replacing default welcome page (HTTPS already in place via nginx-gateway; Dynamic Client Registration means no pre-registration; no CORS). CSS config change for custom registration templates (7.2). Inrupt libs currently loaded from esm.sh — self-hosting/bundling is a 7.1 decision point.
- **Overlap watch:** Existing ACL dashboard (Story 6.2, funder/observer view) vs backoffice sharing drawer (pod-owner view) — different audiences, keep both; note in Epic 7 preamble.

## 3. Recommended Approach

**Direct Adjustment** — additive mini-epic, no rollback, no MVP change.

- Effort: 7.1 small-to-medium (deploy trivial; `.account/` API wiring is the meat). 7.2 small-to-medium (CSS template override mechanics + styling).
- Risk: low. Both stories touch only new surfaces; worst case falls back to link-out registration (HANDOFF option a).
- Timeline: Epic 4 resumes after Epic 7 (and after open 4.4.1 remainder).

## 4. Detailed Change Proposals

### 4a. epics.md — Epic List section, append after Epic 6 entry

```
### Epic 7: Pod Owner Experience _(ADDED 2026-07-21 — sprint change: Epic 4 parked, first-user UX prioritized)_
Real users can create an account and pod on our CSS instance and manage their pod content and ACLs through a cognitive-ergonomics-first backoffice — the first user-facing product surface of the stack.
**Origin:** High-fidelity runnable mockup (SOLID Pod Management Interface, Claude design). Design principles: Miller's Law (≤4 chunks), Hick's Law (one primary action), progressive disclosure (friendly ACL → raw WAC on demand), reversibility.
**Relationship:** Prerequisite-sibling of Story 4.3 (Nicolas onboarding proof). ACL dashboard (6.2) = observer view; backoffice sharing = owner view — both kept.
**Dashboard backlog:** none (this IS a user surface)

### Story 7.1: Backoffice Deploy & Real Account Registration
As a new user, I can reach the pod backoffice on its own hostname, create a real CSS account + pod from the onboarding flow, and manage my files and sharing against my live pod.
- Import mockup bundle into repo (new `backoffice/` dir); serve at `https://pod.nicolasdb.eu/` root via CSS `StaticAssetHandler` config (`/` → index.html, `/pod-api.js`, `/support.js`), replacing the default CSS welcome page. Same-origin: no CORS, `redirectUrl: window.location.href` works unchanged. Decision 2026-07-21: no dedicated hostname.
- Wire onboarding "Create my pod" to CSS `.account/` controls API: create account, set credential (passphrase), create pod, then login handoff
- Decide + implement Inrupt lib strategy (esm.sh runtime import vs bundled self-host). Keep pinned versions (authn-browser 2.3.0 / solid-client 2.1.0); npm latest are 5.0.0 / 3.0.0 major bumps — upgrade is out of scope
- Registration flow (verified against CSS v7 docs 2026-07-21): `GET /.account/` for controls → `POST /.account/account` (cookie) → `POST controls.password.create {email,password}` → `POST controls.account.pod {name}`; auth via `Authorization: CSS-Account-Token $VALUE`. No HTML rewrite — mockup deploys as-is, only demo-provisioning call swapped
- Verify live mode E2E on VPS: login, file CRUD, sharing drawer grants/revokes, WAC panel reads real .acl
- Fallback (timebox): link-out to CSS registration page, "I already have a pod" path takes over

### Story 7.2: CSS Registration Pages Restyle
As a new user landing on the CSS-served registration/login/consent pages, I experience the same visual language and cognitive care as the backoffice.
- Override CSS registration/login/consent templates (CSS template customization mechanism)
- Apply backoffice tokens: daylight theme, Lexend / Atkinson Hyperlegible / JetBrains Mono, sage accent, ≤4 chunks per step, one primary action per screen
- Keep flows functional: account create, pod provisioning, OIDC consent (client name "Pod Backoffice")
- WCAG 2.1 AA (4.5:1 contrast, focus-visible)
```

### 4b. sprint-status.yaml — development_status, append after epic-4 block

```yaml
  # Epic 7: Pod Owner Experience (ADDED 2026-07-21 — sprint change proposal 2026-07-21)
  # Epic 4 PARKED at this date: 4.1 stays ready-for-dev, resume after Epic 7.
  # Origin: runnable mockup bundle "SOLID Pod Management Interface.zip" (see backoffice/ + its HANDOFF.md).
  epic-7: backlog
  story-7-1-backoffice-deploy-real-account-registration: backlog
  story-7-2-css-registration-pages-restyle: backlog
  epic-7-retrospective: optional
```

Also: `last_updated: 2026-07-21` comment extended with Epic 7 addition + Epic 4 park.

### 4c. Repo — import mockup

Unzip bundle into `backoffice/` (tracked), keep `HANDOFF.md` beside it. Delete or keep zip at Nicolas's preference. (Executed as first task of Story 7.1.)

## 5. Implementation Handoff

- **Scope:** Minor-to-Moderate (backlog addition + resequencing note; no replan).
- **Route:** SM (`bmad-create-story` for 7.1 when ready) → dev team.
- **Success criteria:** New user completes account+pod creation via backoffice on VPS; registration pages visually consistent; Story 4.3 unblocked to reuse this surface.
