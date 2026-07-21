# Handoff: Pod Backoffice (SOLID) — deploy & extend

## Overview
A privacy-first backoffice for a SOLID pod: sign in, manage files (create / edit / browse
any text-based format), and control access (WAC/ACL) in plain language — with a scaffolded,
no-jargon onboarding storyline for brand-new, non-technical users. Built against a
**Community Solid Server (CSS)** instance at `https://pod.nicolasdb.eu/`.

Design principles: cognitive ergonomics + Laws of UX — Miller's Law (≤4 chunks per step),
Hick's Law (one primary action), progressive disclosure (friendly ACL by default, raw WAC on
demand), Zeigarnik/Goal-Gradient (visible phase progress), Peak-End (recap finale),
reversibility everywhere (undo toasts).

## About these files
Unlike a typical design handoff, **this bundle is a working, runnable static app** — not just a
visual reference. It is three files that run directly in a browser:

| File | Role |
|------|------|
| `index.html` | The whole app. Authored as a "Design Component" — plain HTML + an inline logic class, no build step. |
| `pod-api.js`  | The pod layer. One interface, two backends: **RealBackend** (live CSS via Inrupt libs) and **DemoBackend** (in-memory pod for offline exploration). |
| `support.js`  | The Design-Component runtime that renders `index.html`. Vendored — do not edit. |

You can deploy it as-is, **or** treat it as a high-fidelity reference and re-implement in a
framework. If re-implementing, keep `pod-api.js` almost verbatim — it is real, framework-agnostic
SOLID code — and rebuild only the view layer.

Fidelity: **high** (final colors, type, spacing, copy, interactions).

## Deploy beside your CSS instance

The app is static; serve the three files together from any HTTPS origin (or `localhost`).
SOLID-OIDC requires a secure context — `https://` anywhere, or `http://localhost` for dev.

**Same VPS as CSS (recommended for your setup):**
1. Copy the folder to the VPS, e.g. `/var/www/pod-backoffice/`.
2. Serve it on its own hostname over TLS, e.g. `https://app.nicolasdb.eu/`, via your existing
   reverse proxy (nginx/Caddy). Example Caddy block:
   ```
   app.nicolasdb.eu {
       root * /var/www/pod-backoffice
       file_server
   }
   ```
3. Open `https://app.nicolasdb.eu/` → "I already have a pod" → authenticates against
   `https://pod.nicolasdb.eu/` and returns to the app.

**Local dev:** `cd pod-backoffice-deploy && npx serve` (or `python3 -m http.server 3000`).

**No app pre-registration needed.** CSS supports Dynamic Client Registration; the code sets
`redirectUrl: window.location.href`, so the app self-registers and returns to wherever it's served.
`clientName` is `"Pod Backoffice"` (shown on the consent screen). Set a stable Client Identifier
Document later if you want a fixed client name/logo on that screen.

**Network dependency:** `pod-api.js` imports the Inrupt libraries from `esm.sh` at runtime
(`@inrupt/solid-client-authn-browser@2.3.0`, `@inrupt/solid-client@2.1.0`). For an air-gapped or
fully self-hosted deploy, `npm i` those, bundle them, and change the two `import(...)` URLs in
`pod-api.js` to your local paths.

## Real vs demo boundary
- On load, `Solid.init()` runs `handleIncomingRedirect({restorePreviousSession:true})`.
  Logged in → **live** mode, loads the user's real root container. Otherwise → the gate.
- "I'm new to this" → onboarding on the **demo** pod (a "Demo pod" badge shows in live app chrome
  when demo is active), so the flow is fully explorable without a session.
- Every file/ACL action calls the **same interface** — only the backend differs. Live writes are
  real `overwriteFile` / `createContainerAt` / `universalAccess.setAgentAccess` / `setPublicAccess`
  calls, and real `.acl` fetches for the "Show technical rules (WAC)" panel.

## Known extension points (intentional gaps)
1. **New-account creation is simulated.** CSS account/pod registration is a *separate* flow from
   OIDC login (the IDP account API), so the onboarding "Create my pod" step (name + optional
   passphrase) provisions against the demo backend only. To make it real, either (a) link users to
   the CSS registration page first, then the "I already have a pod" path takes over, or (b) call the
   CSS `.account/` controls API to register + create pod + set the passphrase, then log in. For a
   seamless in-backoffice onboarding you'll customize the CSS registration UI/templates on the
   server itself.
2. **Passphrase, not password.** The create step invites a multi-word passphrase (optional) with a
   live strength hint. Wire this to whatever credential the CSS account API expects.
3. **People & apps** aggregates agents from the ACLs of resources the app has *visited* (there is no
   global "who can see everything" index in SOLID). For a complete view, crawl the pod or maintain
   an index resource.
4. **Requests** are modelled as demo cards. For production, back them with an inbox container
   (LDN notifications) or the Inrupt Access Requests flow; "Allow" already performs a real
   `setAgentAccess` grant when a live session exists.

## Screens / views
- **Gate** — two choices only (Hick): "I'm new to this" (onboarding) · "I already have a pod"
  (live `login()`). Offline note explains the preview/real-URL distinction.
- **Onboarding** (10 chapters, 3 phases: Understand → Set up → Ready):
  `intro → box → webid → keys → checkpoint → create → folders → file → share → recap`.
  Concept chapters carry ≤4 chunks each; the share chapter reveals the resulting WAC only *after*
  a deliberate choice (decision→consequence). Recap restates the 4-part mental model (Peak-End).
- **App shell** — sidebar (Home / My things / People & apps / Requests) + breadcrumb header.
- **My things** — container listing with per-row access badge; new file / new folder.
- **Editor** — split view: monospace edit pane + live pane (Markdown render for `.md`, syntax
  highlight + line numbers for `.json`/`.toml`/code/text). JSON validity hint. Save writes to pod.
- **Sharing drawer** — friendly visibility (Only me / Anyone with the link) + add person by WebID
  (read or read+edit) + "Show the technical rules (WAC)" progressive disclosure showing the raw
  `.acl` turtle. All backed by `universalAccess`.

## Design tokens (daylight theme; also `paper`, `ink`)
- bg `#f6f4ef` · panel `#fbfaf7` · text `#26241f` · muted `#8a8474` / `#b3ac9a`
- line `#e7e2d6` · hover `#efece3` · accent (sage) `#3d6b52` · accentSoft `#eef3ef`
- warn `#b5722a` · warnBg `#faf3e6` · code bg `#f0ede4`
- Fonts: **Lexend** (UI), **Atkinson Hyperlegible** (accessibility toggle), **JetBrains Mono**
  (WebIDs, code, filenames). Radii 8–16px; pill buttons 99px.
- Themes and the readable-font toggle are exposed as component props (`theme`, `readableFont`).

## Files
- `index.html` — the app (template + logic).
- `pod-api.js` — SOLID/demo backends. **The real SOLID code lives here.**
- `support.js` — DC runtime (vendored).
