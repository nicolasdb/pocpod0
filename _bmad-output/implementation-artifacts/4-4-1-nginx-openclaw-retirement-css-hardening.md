# Story 4.4.1: Nginx-Gateway Consolidation, OpenClaw Retirement Kickoff, CSS Public Hardening

Status: in-progress

## Story

As a **project lead** (Nicolas),
I want the VPS nginx routing consolidated onto the shared `nginx-gateway` container, OpenClaw's local dependencies removed from the pocpod0 stack, and CSS safely reachable at a real public subdomain,
So that the VPS stops carrying dead/duplicate infrastructure, teammates can register real Solid pods on `pod.nicolasdb.eu` for multi-user ACL testing, and the pod stack isn't exposed to identity-spoofing over the public internet.

## Context

This story was **not planned** — it emerged from a working session that started as a "let's review the last couple months" conversation and surfaced three separate issues:

1. OpenClaw (Discord agent layer) should be retired from the project.
2. Portainer was reachable only via a Cloudflare tunnel (an artifact of early VPS setup, before nginx+certbot was understood) — Nicolas wanted it moved to the shared nginx-gateway with proper HTTPS instead.
3. Deeper work on Solid pod lifecycle (create, explore, ACLs, app integration) requires CSS to actually be live and correctly routed on the VPS.

Point 3 is what actually got worked this session. Points 1 and 2 surfaced a bigger structural finding: **the VPS already runs a shared `nginx-gateway` container** (`/home/nicolas/hetzner-gateway`) that fronts multiple unrelated projects (smartflow, mapsofmaking, timetracker) with real Let's Encrypt certs via `conf.d/*.conf` per service. pocpod0 was NOT using this — it had captured its own local `nginx` container (`infra/nginx/nginx.conf`) doing purely CSS content-negotiation proxying, port-published on 8080/8443, never fronted by TLS. Meanwhile `pod.nicolasdb.eu` (a real subdomain, DNS already pointed at the VPS) was wired in `nginx-gateway`'s conf.d to OpenClaw, not CSS.

**This is the course-correction trigger**: pocpod0's own `docker-compose.yml` nginx service was redundant with infrastructure that already existed and should have been used from the start. Epic 4/6 work built VPS deploy tooling (`make vps-push/build/deploy`) without folding pocpod0 into the shared gateway pattern the VPS had already standardized on for other projects. Where exactly this should have been caught (Story 4.0.2 VPS deploy? A dedicated infra story?) is not yet decided — flagging for `bmad-correct-course` rather than deciding unilaterally here.

## What actually happened this session

**1. VPS live-state audit** (not from memory — re-verified against running containers):
- pocpod0 stack (CSS, oxigraph, qdrant, openclaw-gateway, local nginx) was fully stopped, 3 months idle.
- `nginx-gateway` container already handles TLS termination + Let's Encrypt for 5+ other projects on this VPS.
- Cloudflare tunnel (`tunel` container) only routes `portainer.nicolasdb.eu` and `grafana.nicolasdb.eu` — unrelated to pocpod0, but flagged by Nicolas as a separate cleanup (not yet started).
- `04-pocpod0.conf` in nginx-gateway existed, pointed at OpenClaw (`openclaw-gateway:18789`), domain `pod.nicolasdb.eu`.

**2. CSS repointed onto the shared gateway** (done, verified live):
- Rewrote `nginx-gateway/conf.d/04-pocpod0.conf`: same domain (`pod.nicolasdb.eu`), backend swapped to `community-solid-server:3000`. Ported over the Solid/LDP-specific header passthrough (`Link`, `WAC-Allow`, `Accept-Patch/Post/Put`, `Vary`, `Accept-Control-Expose-Headers`, etc.) and Accept-header content-negotiation forwarding from the old local `infra/nginx/nginx.conf`, which had a real, tested purpose (`tests/integration/test-nginx-content-negotiation.sh`) — this was almost deleted outright before that was caught.
- `community-solid-server` added to the shared `gateway` Docker network in `docker-compose.yml` so nginx-gateway can resolve it by container name.
- Local `nginx` service block removed from `docker-compose.yml`; `infra/nginx/` directory deleted; `scripts/setup.sh` no longer creates `infra/nginx/ssl`; `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT` removed from `.env.example`.
- CSS `--baseUrl` was hardcoded to `http://localhost:3000/` in the compose command — fixed to read `${CSS_BASE_URL}` so it's correct on VPS. `CSS_BASE_URL`, `CSS_IDENTIFIER_URL`, `CSS_IDENTIFIER_HOST` pinned to `pod.nicolasdb.eu` in `infra/vps/.env.vps` (auto-applied on every `make vps-push`).
- Pushed and brought up on VPS: `community-solid-server`, `oxigraph`, `qdrant` running; `openclaw-gateway` and old `nginx` left stopped as orphan containers (not deleted — OpenClaw retirement itself is still an open, separate decision).

**3. Security issue found and fixed** (not planned, discovered while validating):
- CSS is configured with `css:config/ldp/authentication/debug-auth-header.json` — trusts a raw `Authorization: WebID <uri>` header with zero verification. This exists because ~15 files across `pipeline/`, `agents/skills/`, and `agents/troll-adversary/` depend on it for automation (confirmed via grep).
- That auth mode was silently exposed to the public internet the moment `pod.nicolasdb.eu` went live on the shared gateway — anyone could impersonate any WebID with a single header, no login required. Confirmed exploitable with a live curl test (200 OK, `WAC-Allow` reflecting owner-level access for a spoofed identity).
- Fix chosen: **not** swapping CSS's auth config (would break all 15 dependent files, since internal automation has no real OIDC client). Instead, added an nginx `map` in `04-pocpod0.conf` that strips any `Authorization` header matching `^WebID ` before proxying to CSS — public-only mitigation. Internal automation is unaffected because it already talks to CSS via `CSS_CONNECT_URL` (`community-solid-server:3000` on the Docker-internal network), bypassing the public gateway entirely.
- Verified live: public path with spoofed header → `401`. Internal path (from within the `gateway` Docker network) with the same header → CSS still evaluates it (hit a stale-data 500 unrelated to auth, see below) — confirms the strip is edge-only.

**4. End-to-end validation** (throwaway account, since deleted):
- Full CSS account API flow tested live over `https://pod.nicolasdb.eu`: `POST /.account/account/` → `POST .../login/password/` → `POST .../pod/` → correct public WebID minted (`https://pod.nicolasdb.eu/throwaway-test/profile/card#me`), profile card fetched and confirmed correct Turtle with `solid:oidcIssuer` pointing at the real domain.
- Throwaway pod data removed after test (`.internal/` index leftovers harmless, will be wiped in the planned data recreate below).

## Known follow-ups / not done in this session

- **Existing pod data is stale and orphaned.** `css-data` volume holds ~1300 synthetic pipeline pods (Story 6.0 `camp-dietary-aggregate.ttl` fixtures) plus named demo pods (`ayoub`, `claire`, `fatima`, `school-community`, etc.) — all with WebIDs and `.acl` files baked to the old `http://localhost:3000` identifier space. These are now permanently orphaned (Solid WebIDs are not migratable in place; confirmed via a live 500 "outside configured identifier space" error). Decision (Nicolas, this session): **recreate, don't restore** — wipe `css-data` and re-run `scripts/setup.sh` / pipeline provision when next needed. Not yet executed.
- **OpenClaw retirement not executed.** `agents/` (Discord persona configs, Epic 4 work), `infra/openclaw/` (Dockerfile, entrypoint), and the `openclaw-gateway` service definition itself still exist in the repo and on the VPS (stopped, not deleted). This is the bigger, separate decision flagged in the original ask — scope (whole Discord-agent feature vs. just infra) still needs Nicolas's explicit confirmation before touching.
- **Cloudflare tunnel / Portainer HTTPS migration not started.** Still routes only `portainer.nicolasdb.eu` and `grafana.nicolasdb.eu`; Nicolas wants Portainer moved to an `nginx-gateway` conf.d entry (same pattern as `01-smartbe.conf`) and the tunnel entry removed. Agreed in conversation, no files touched yet.
- **Pod lifecycle deep-dive not started.** The original third ask — create/explore/upload files/manage ACLs/integrate a pod into a custom app — is still ahead. This session only got CSS safely reachable as a prerequisite.
- Nicolas has not yet created his own real pod (was about to, when this documentation request interrupted).

## Suggested sprint-status placement

This doesn't fit cleanly as a Story 4.1 prerequisite or a numbered Epic 4 story — it's unplanned infra remediation triggered by discovering pocpod0 wasn't using VPS-standard shared infrastructure. Recording it as `story-4-4-1` (infra side-quest, same numbering pattern as `4-0-1`/`4-0-2`) pending a proper `bmad-correct-course` pass to decide whether OpenClaw retirement + Portainer/tunnel migration become their own stories under Epic 4 or a new small epic ("Epic 4.5: VPS Infra Consolidation").

## Tasks / Subtasks

- [x] **Task 1: VPS live-state audit** — containers, cloudflared config, nginx-gateway conf.d inventory, DNS check for `pod.nicolasdb.eu`.
- [x] **Task 2: Repoint CSS onto shared nginx-gateway**
  - [x] 2.1: Preserve Solid-header passthrough + content-negotiation logic from local nginx before deleting it (caught via test-script trace, not assumed).
  - [x] 2.2: Rewrite `04-pocpod0.conf`, add CSS to `gateway` network, remove local `nginx` service + `infra/nginx/`.
  - [x] 2.3: Fix hardcoded `--baseUrl`, pin `CSS_BASE_URL`/`CSS_IDENTIFIER_URL`/`CSS_IDENTIFIER_HOST` in `infra/vps/.env.vps`.
  - [x] 2.4: Push, bring up CSS/oxigraph/qdrant on VPS, reload nginx-gateway, verify live (headers, content negotiation, direct vs. gateway identifier-space behavior).
- [x] **Task 3: Security review before public exposure**
  - [x] 3.1: Identify debug-auth-header risk, map internal dependents (grep across pipeline/skills/troll-adversary).
  - [x] 3.2: Confirm internal automation uses `CSS_CONNECT_URL` (bypasses public gateway) — safe to mitigate at the edge only.
  - [x] 3.3: Implement + verify header-stripping fix in `04-pocpod0.conf`, confirm public vs. internal behavior diverges correctly.
- [x] **Task 4: End-to-end account/pod creation validation** — live throwaway signup + pod creation over public domain, verified correct public WebID, cleaned up after.
- [ ] **Task 5: Data recreate** — wipe `css-data`, reseed under new base URL. Not started.
- [ ] **Task 6: OpenClaw retirement scope decision** — pending Nicolas confirmation on blast radius (infra-only vs. whole Discord-agent feature).
- [ ] **Task 7: Portainer → nginx-gateway migration, tunnel removal** — agreed in conversation, not started.
- [ ] **Task 8: Pod lifecycle deep-dive** (original ask #3) — create/explore/upload/ACL/app-integration walkthrough. Not started.

## Files Changed

- `docker-compose.yml` — removed `nginx` and `openclaw-gateway` services; `community-solid-server` joined `gateway` network; `--baseUrl` now uses `${CSS_BASE_URL}`.
- `infra/nginx/` — deleted (nginx.conf, SPIKE-DECISION.md, ssl/).
- `scripts/setup.sh` — removed `infra/nginx/ssl` directory creation.
- `.env.example` — removed `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT`.
- `infra/vps/.env.vps` — added `CSS_BASE_URL`, `CSS_IDENTIFIER_URL`, `CSS_IDENTIFIER_HOST` overrides.
- (VPS-side, not in git) `hetzner-gateway/nginx/conf.d/04-pocpod0.conf` — rewritten to front CSS instead of OpenClaw, added Solid-header passthrough and public-only `Authorization: WebID` stripping.

## Notes for course-correction

Flagging explicitly per Nicolas's framing ("our session is even the trigger for a course correction, yet I don't know yet where"): the structural gap is that **VPS infrastructure conventions (shared nginx-gateway, no local per-project nginx/TLS) existed before Story 4.0.2 but weren't referenced or enforced when pocpod0 was deployed.** Recommend a `bmad-correct-course` pass to decide:
1. Does Epic 4 need an explicit "VPS infra conformance" story/checklist for future services?
2. Where do OpenClaw retirement and Portainer/tunnel migration land — Epic 4 stories, or a new small epic?
3. Should `infra/vps/README.md` (Story 4.0.2 AC7) be updated now to document the shared-gateway pattern so it's not rediscovered again?
