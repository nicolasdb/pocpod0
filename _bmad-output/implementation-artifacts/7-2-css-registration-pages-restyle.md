# Story 7.2: CSS Registration Pages Restyle

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **new user** landing on any CSS-served page outside the backoffice shell (registration, login, OIDC consent),
I want the same visual language and cognitive care as the backoffice,
so that no part of the sign-up journey drops back into raw, developer-grade SOLID UI and breaks trust or comprehension.

## Acceptance Criteria

1. CSS's default account/login/pod-creation HTML views and the OIDC consent/interaction screen render with backoffice design tokens (colors, fonts, spacing, radii) instead of CSS's stock styling.
2. Copy on these pages is reviewed for plain-language tone consistent with the backoffice onboarding (no raw jargon like "WebID", "pod", "OIDC" without a plain-language gloss, matching the bundle's "no-jargon onboarding storyline" principle).
3. Each screen keeps to the bundle's cognitive-ergonomics rules: Miller's Law (≤4 chunks per step), Hick's Law (one primary action per screen).
4. Functional behavior of every restyled flow is unchanged: account create, password/credential set, pod create, OIDC consent grant — all still complete successfully end-to-end.
5. WCAG 2.1 AA: 4.5:1 contrast minimum, visible focus states on all interactive elements (buttons, links, form fields).
6. Client consent screen shows `clientName: "Pod Backoffice"` (already set via Dynamic Client Registration in the bundle) — verify it displays correctly once page is restyled, not just left as a TODO.

## Tasks / Subtasks

- [ ] Task 1: Locate CSS's template/view customization mechanism (AC: #1)
  - [ ] 1.1 Identify which CSS components render the registration/login/pod/consent HTML (CSS v7, config imported via `css:config/identity/...json` chain already present in `infra/css/config.json` — `identity/handler/default.json`, `identity/oidc/default.json`, `identity/pod/static.json`, `identity/email/default.json`)
  - [ ] 1.2 Determine override mechanism: CSS supports HTML template asset overrides (Handlebars-based views bundled with `@solid/community-server`) — confirm exact template file paths and the Components.js config needed to point at custom templates vs. relying on `StaticAssetHandler` (used in Story 7.1 for the backoffice root) for CSS-specific dependency
  - [ ] 1.3 If direct template override proves too invasive for POC timebox, fallback: minimal CSS injection via a static stylesheet asset mapped over the existing template's class hooks (lower risk, less complete — document tradeoff)
- [ ] Task 2: Apply backoffice design tokens (AC: #1, #3, #5)
  - [ ] 2.1 Reuse exact tokens from `backoffice/index.html`/HANDOFF.md: bg `#f6f4ef`, panel `#fbfaf7`, text `#26241f`, muted `#8a8474`/`#b3ac9a`, line `#e7e2d6`, hover `#efece3`, accent (sage) `#3d6b52`, accentSoft `#eef3ef`, warn `#b5722a`/`#faf3e6`, code bg `#f0ede4`
  - [ ] 2.2 Fonts: Lexend (UI), Atkinson Hyperlegible (accessibility toggle), JetBrains Mono (WebIDs/codes) — load same font sources as backoffice for visual continuity
  - [ ] 2.3 Radii 8–16px, pill buttons 99px — match backoffice component shapes
  - [ ] 2.4 One primary action per screen (Hick's Law) — check each CSS default screen (register, login, pod-create, consent) for competing CTAs and simplify
  - [ ] 2.5 Verify 4.5:1 contrast on all text/background pairs post-restyle; verify `:focus-visible` styling present on every interactive element (per project's WCAG 2.1 AA standard)
- [ ] Task 3: Copy review (AC: #2)
  - [ ] 3.1 Audit existing CSS default copy on each screen for raw technical jargon
  - [ ] 3.2 Rewrite using the same plain-language register as the backoffice onboarding chapters (`intro → box → webid → keys → checkpoint → create → folders → file → share → recap`) — reuse those chapters' phrasing patterns where equivalent concepts appear (e.g. WebID explained once, simply)
- [ ] Task 4: Functional regression check (AC: #4, #6)
  - [ ] 4.1 Full flow test: account create → password set → pod create → login → OIDC consent grant, on restyled pages, end-to-end
  - [ ] 4.2 Confirm consent screen displays `clientName: "Pod Backoffice"` correctly (bundle already sends this via Dynamic Client Registration — no client pre-registration needed per HANDOFF.md)
  - [ ] 4.3 Re-run Story 7.1's throwaway-account E2E check (or equivalent) against the now-restyled pages to confirm no regression from the visual changes

## Dev Notes

- **Depends on Story 7.1 for design-token source of truth** — do not invent new tokens; the backoffice mockup is the canonical design system for this whole user-facing surface. Pull exact values from `backoffice/index.html`/HANDOFF.md, not memory or approximation.
- **Scope boundary:** this story restyles CSS's own server-rendered account/OIDC pages. It does NOT touch `backoffice/index.html` (that's Story 7.1's surface) and does NOT change CSS's underlying account/OIDC logic — visual/copy layer only, functionality must be provably unchanged (AC4).
- **CSS version:** `solidproject/community-server:7` (docker-compose.yml:3). Template override mechanisms are version-specific — confirm against this exact major version, not assumed from older CSS docs.
- **Design principles (same as backoffice, HANDOFF.md):** cognitive ergonomics + Laws of UX — Miller's Law (≤4 chunks/step), Hick's Law (one primary action), progressive disclosure, Zeigarnik/Goal-Gradient (visible phase progress), Peak-End (recap finale), reversibility (undo toasts) — apply whichever are relevant to a registration/consent flow (Miller's + Hick's most directly; multi-step progress framing if the account→pod flow spans multiple screens).
- **Existing project standard:** WCAG 2.1 AA is an established project requirement (4.5:1 contrast, focus-visible) — this is not new scope invented for this story, it's the project's baseline bar for all user-facing surfaces.
- **Risk flag:** CSS template customization depth is unconfirmed at story-creation time (Task 1.2/1.3 fork). If full Handlebars template override is not feasible within timebox, the documented fallback (stylesheet-only override) is an acceptable, lower-fidelity completion — record which path shipped in Completion Notes, same discipline as Story 7.1's Task 4 fallback pattern.

### Invalidated Assumptions

- **Assumption:** CSS default registration UI is out of reach for customization (config-only server). → **Reality:** CSS v7's identity/pod/account handling is composed via configurable, replaceable components (`css:config/identity/...json` imports already present in `infra/css/config.json`) — the same Components.js pattern already used in this repo (Story 4.4.1's `debug-auth-header.json`, this epic's Story 7.1 `StaticAssetHandler` addition) extends to template/view overrides; this is config work, not a CSS server fork.

### Project Structure Notes

- Changes land in `infra/css/config.json` (additive `@graph`/import entries, same file touched in Stories 4.4.1 and 7.1 — do not disturb existing imports) and a new small assets/template directory if template override is chosen (e.g. `infra/css/templates/` or `infra/css/views/`, to be named at implementation time based on what CSS's override mechanism actually expects).
- No changes to `backoffice/` in this story.

### References

- [Source: backoffice/HANDOFF.md#Design tokens] — full token list, fonts, radii, theme names (daylight/paper/ink)
- [Source: backoffice/HANDOFF.md#Screens / views] — Gate/Onboarding copy patterns and chapter structure to mirror in restyled CSS copy
- [Source: infra/css/config.json] — current identity-related config imports (`identity/handler/default.json`, `identity/oidc/default.json`, `identity/pod/static.json`, `identity/email/default.json`, `identity/ownership/token.json`)
- [Source: _bmad-output/implementation-artifacts/7-1-backoffice-deploy-real-account-registration.md] — sibling story, shared design-token source, deploy pattern precedent
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-21.md] — decision record for Epic 7
- Memory: `feedback_wcag_aa_standard` — WCAG 2.1 AA is this project's established accessibility bar (4.5:1 contrast, focus-visible; color-only indicators fail)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
