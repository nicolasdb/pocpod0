# Deferred Work

## Deferred from: code review of story-7.4 (2026-07-23)

- Hardcoded `ISSUER`/token-endpoint (`pod.nicolasdb.eu`) in `pod-api.js` — fine for single-tenant VPS today, revisit if backoffice ever targets multiple pod deployments.
- `safeFileName` misses DEL (`\x7f`), bidi/RTL-override, and zero-width chars — pre-existing hardening gap, out of 7.4's scope, worth a pass alongside 7.6 hardening.
- Credential name-strip regex (`id.replace(/_[0-9a-f-]{36}$/i, "")`) assumes CSS's `_<uuid>` id-suffix shape; breaks if CSS changes format or an app name coincidentally matches the pattern.
- `DemoBackend.createClientCredential` id format (`name_demo-xxxxxxxx`) diverges from the real CSS id shape, so the demo path never exercises the real name-display stripping logic.
- `getAccess()` sets an `error` flag only on the `loadFolder` load path; `refreshAccess`/rename's ACL-carry `getAccess` calls don't, so a transient ACL-fetch failure can show misleadingly clean "private" state in some UI spots and "unknown" in others.
- AC1 ("name + when") — issuance timestamp isn't shown because CSS's `client-credentials/` list endpoint doesn't return one; not implementable without an upstream CSS change.
- `countDescendants`/`confirmDelete` arm-count race under rapid arm/disarm clicks on the delete button — cosmetic, low likelihood.
- `_refuseIfUnknownAcl` blocks all editing on any resource with a non-foaf `agentClass`/`agentGroup`/`origin` ACL block, with no in-UI path forward besides raw Turtle edit — pre-existing documented TODO, revisit once group-sharing UI lands.


## File-manager hardening — deferred from Story 7.3 to new Story 7.6 (2026-07-23)

Story 7.3 live-testing on a real messy pod (`hyperscope_ndb`, partly populated by the third-party `focus.noeldemartin.com` todo app) surfaced robustness gaps beyond 7.3's CRUD/ACL/upload scope. Captured as **Story 7.6 (drafted, ready-for-dev)** rather than scope-creeping 7.3:

- **Cross-folder move** — 7.3 `rename` is same-parent only; moving between folders (copy-verify-delete ordering so a partial move never loses data) is 7.6.
- **Bulk multi-select** delete/move with count-aware confirm + per-item graceful failure.
- **Transfer progress** for many/large files; large-folder listing responsiveness (batch/throttle the already-parallel ACL fetch).
- **Decision (with Nicolas):** do NOT adopt `solid-contrib/solid-file-manager` wholesale — it lacks our ACL/permissions UI, inline edit, and two-tap delete (our differentiators) and is a standalone app, not a library. Use it + `solid-file-client` as a **reference** to re-implement move/copy/bulk/progress patterns in our idiom. Audit "adopted/rejected/why" is a 7.6 deliverable so this isn't re-litigated.

7.3 itself shipped through `pod-api.js?v=7-3-7` with all data-loss paths guarded (new-file/new-folder/rename/upload collisions all refuse or confirm; editor-rename warns on unsaved changes).

## Deferred from: code review of 6-1-troll-comprehensive-run-and-report (2026-03-31)

- Bare imports in `run_comprehensive.py:27-31` are fragile if the module is ever imported from outside the attacks/ directory. Works correctly as a script. Consider adding `sys.path` guard if module reuse is needed.

## Deferred from: code review of 6-2-mission-control-dashboard-implementation (2026-03-31)

- **W1: `publication_ready` ignores TRANSITIONING pods** — design decision; transitioning ≠ revoked, threshold check intentionally uses only active count. Reconsider if transitioning pods cause unexpected "NOT READY" signals in demo.
- **W2: Partial write on last JSONL line** — `json.loads` will fail on incomplete last line mid-write; event silently skipped. Acceptable for PoC where writers complete quickly. Production fix: read only complete lines (check for `\n` suffix).

## Deferred from: code review of 6-3-funder-intervention-points (2026-04-04)

- **W1: consent-events.jsonl emission untested** — AC1 requires this as observable outcome but it's a subprocess side effect that can't be exercised through mocked subprocess. Architectural limitation of subprocess-based skills.
- **W2: Popen handle discarded (zombie processes)** — repeated troll runs accumulate zombie processes. Acceptable for PoC demo with bounded runs. Production fix: store handle and wait asynchronously, or use `asyncio.create_subprocess_exec`.
- **W3: Concurrent full+category JSONL race** — `write_text("")` truncation races with in-flight `open("a")` write if both run simultaneously. Single-operator demo makes this unlikely.
- **W4: HANDLER_PATH/TROLL_PATH break in non-standard pip install** — `Path(__file__).parent×4` layout assumption fails outside editable dev install. Not relevant for demo.
- **W5: No polling timeout for failed subprocess** — if `data/` mkdir fails (or any crash before `troll.run.done`), polling runs forever and the Run button stays disabled until page reload. Acceptable for PoC.
- **W3: `extra=data` aliasing in `parse_consent_event`** — `extra` field holds same dict object as source `data`. Read-only in PoC. Production fix: `extra={k: v for k, v in data.items() if k not in known_fields}`.
- **W4: `_poll_jsonl_task` not cancelled on unmount** — Textual cancels async tasks on exit. Not a concern for demo use.
- **D3: Troll events display ([ATTACKS] tab)** — `troll_events` polled and stored but not rendered. Deferred to Story 6.3 (Funder Intervention Points) where troll summary is contextually relevant to funder audience.
- `DEFAULT_POD_URI` and `DEFAULT_RESOURCE_URI` hardcoded to `http://localhost:3000/ayoub/` regardless of `CSS_BASE_URL` env var. Acceptable for PoC; fix before pilot.
- `blocking_pass` logic ignores `partial` results in blocking categories (ACL, SPARQL). A category with 100% partial results returns `blocking_pass=True`. Intentional per spec ("fails"); revisit if partial = inconclusive is a concern for pilot.

## Deferred from: code review of 4-0-discord-seed-on-boot-infrastructure (2026-04-13)

- **D1: `DISCORD_ALLOW_FROM` unset → literal string in DM allowlist** — `"allowFrom": ["${DISCORD_ALLOW_FROM}"]` with unset var silently rejects all DMs. OpenClaw framework limitation; no startup validation hook. Acceptable for PoC (single user, variable is documented in .env.example).
- **D2: Volume rename openclaw-data → openclaw-data-default breaks existing deployments** — existing volumes silently lost on `docker-compose up`. PoC only; no production deployments. Document before any multi-operator setup.
- **D3: Skill files not updated between factory resets** — `if [ ! -d "${SKILLS_TARGET}" ]` guard means skill bug fixes don't apply until `down -v`. By-design PoC tradeoff; factory reset is documented mechanism. Add checksum-based sync before pilot.
- **D4: Troll heartbeat config-validated only, not runtime-observed** — 30m interval not witnessed firing. Config structure identical to Claire's working heartbeat. Accept for PoC; validate by observation before pilot demo.

## Side Quest: OpenClaw gateway bind / WebUI + CLI pairing — RESOLVED (2026-04-15)

- **Original issue (2026-04-14):** WebUI unreachable under `podman compose up`. Root cause hypothesized as podman-compose#967 (bridge instead of pasta, iptables failure in rootless podman).
- **Resolution (Story 4.0.1, 2026-04-15):** Investigation found the premise was wrong:
  1. System uses **Docker Compose v2.39.4** (not podman-compose) — podman-compose#967 doesn't apply.
  2. Podman auto-rebased to **v5.8.1** via Kinoite rebase — rootless bridge port forwarding works correctly.
  3. Earlier "connection reset" was a timing issue (curl fired before gateway's ~40s Node.js startup completed).
  4. WebUI is now accessible at `http://localhost:18789` (HTTP 200). No code changes required.
- **Remaining known issue (RI-2 from Story 4.0):** CLI pairing (`openclaw devices list/approve`) still fails with WebSocket handshake timeout. Pre-existing; not caused by network mode. Workaround: use Discord for agent interaction; observe via `podman logs openclaw-gateway`.
- **Story 4.0.2 (VPS deploy):** Still valid as a strategic goal (pilot-bridge path) but is no longer needed as an emergency unblock for local Epic 4 development.

## Post-Story 4.0.2 deferred items (2026-04-16)

- **Pipeline progress tab in FastAPI ACL dashboard:** Drop the Textual TUI (`--with-dashboard` flag). Add a `/pipeline` tab to the existing FastAPI dashboard (`pocpod0-acl-dashboard`) with live log streaming via SSE from `pipeline-run.jsonl`. Gives real-time ingestion progress without a second terminal or TUI dependency. Candidate for a story in the Epic 4 / post-PoC backlog.

## Deferred from: code review of story-7.1 (2026-07-22)

- _skipNextPush instance-mutation race in popstate/componentDidUpdate [backoffice/index.html:41-53] — speculative, no concrete repro found.
- webId.replace(/profile\/card#me$/,"") fallback fragile for non-standard WebIDs [backoffice/pod-api.js:112] — low likelihood, CSS webIds consistently match this pattern today.
- UnsecureWebIdExtractor security posture depends entirely on external nginx-gateway repo header-stripping [infra/css/config.json:243] — pre-existing architecture decision from Story 4.4.1, already flagged in config comments.
- getPodUrlAll no refresh/retry if timing race leaves stale root [backoffice/pod-api.js:114-121] — speculative, no concrete repro found.

## Deferred from: code review of story-7.2 (2026-07-23)

- Passphrase/password field is `type="text"` (unmasked), now elevated to a mandatory secret by AC8 [backoffice/index.html] — pre-existing since Story 7.1, worth revisiting given the field is no longer optional.
- Google Fonts `@import` on auth/consent pages (privacy leak — Google sees every login-page load; also a single point of failure) [infra/css/main.css] — mirrors existing backoffice pattern from Story 7.1, not new to this story.
- `main div:has(> #client_logo) { display: block; }` (the consent client-logo gap fix) has no fallback for browsers without `:has()` support (Safari <15.4, Firefox <121) — degrades to the original cosmetic phantom-gap bug, not a functional break [infra/css/main.css].
- AC6 "Pod Backoffice" clientName display claimed verified in Completion Notes, but no direct screenshot/evidence of that specific string rendering was captured — only the surrounding layout fix (grid vs float) was screenshot-verified. Low-risk; spot-check manually before pilot.

## Live CSS ACL/portability audit (2026-07-23, throwaway-audit-0723 pod)

Spun up a throwaway pod on live VPS CSS (v0.5 account API) to kill stale assumptions before writing Epic 7 stories. Findings:

- **Default pod ACL template (confirmed live):** root `.acl` grants `<#public>` only `acl:Read` on `<./>` with **`accessTo` only (no `acl:default`)** — so public-read applies to the root container listing *itself*, not inherited by children. Owner `<#owner>` gets `Read/Write/Control` with **both `accessTo` and `acl:default`** → inherited by every child.
- **Inheritance model (confirmed):** fresh child containers (`profile/`) have **no own `.acl`** (GET → 404); they inherit root's owner grant via `acl:default`. So the pod-root `.acl` is the single anchor. Self-revoking Write on a *child* writes a child `.acl` override and is recoverable as long as **root Control is intact**. (Did NOT live-test stripping root Control — treat as potentially irreversible.)
- **Public RW works at CSS layer (confirmed):** created `/manual`, wrote a `.acl` granting `foaf:Agent` Read+Write → anon GET 200, anon PUT **205 (success)**, re-read showed anon-edited content. → Nicolas's "manual of me: public RW but couldn't edit" is **NOT a CSS limitation**; it points to a **backoffice bug** — likely `universalAccess.setPublicAccess` not writing the grant as expected (wrong modes, or `accessTo` without `acl:default`, or app not persisting). Story 7.3 ACL work = client-side bug, not server feature.
- **Client-credentials flow (confirmed working, v0.5):** `POST /.account/account/{id}/client-credentials/` `{name, webId}` → `{id, secret}`; token via `POST /.oidc/token` grant_type=client_credentials + DPoP. Credentials **ARE deletable over HTTP** (`DELETE .../client-credentials/{id}/` → 200/205). This is the 7.4 bot-connect + revoke backend.
- **Account/pod deletion still NOT exposed over HTTP (re-verified, unchanged from 7.1):** `DELETE /.account/account/{id}/` → 404, `DELETE .../pod/{id}/` → 400. Only credentials are HTTP-deletable. Confirms orphan-cleanup still needs in-container Node/`AccountStore` approach.
- **Gotcha:** account `logout` invalidates the CSS-Account-Token immediately; revoke credentials BEFORE logout, or re-login with password to continue.

**Cleanup state of throwaway-audit-0723:** `/manual`+`.acl` deleted, all client-credentials revoked (`clientCredentials: {}`), no live exposure. The account + empty pod (default `profile/`+README, public-read root) **remain as orphan #19** — cannot be HTTP-deleted, same as the others below. Sweep with them.

## Orphan CSS account cleanup — VPS (from code review of story-7.1, 2026-07-22)

- 18 orphan CSS account records in `pocpod0_css-data:/data/.internal/accounts/` on the VPS (17 original from Story 4.4.1/7.1 E2E dev iterations + 1 from a code-review verification test, see incident note below). Pod folders/data removed from /data but account/webIdLink/pod index records remain in `.internal/`. Slugs: e2e-story71-*, e2e-final-*, story71-verify, throwaway-*, review-resume-test-17598.
- **Sweep attempted 2026-07-22, deliberately not completed.** Investigated CSS's storage layer: each account is a single JSON file (`data/<accountId>$.json`) holding password/pod/webIdLink/clientCredentials together, cross-referenced by separate index files (`index/owner/`, `index/pod/`, `index/pod/baseUrl/`, `index/webIdLink/`, etc). CSS has an internal cascade-delete (`AccountStore.delete(type, id)`, removes an object and all objects that reference it) but it is **not exposed over HTTP** — the JSON API only offers `controls.password.delete`, which itself refuses to remove an account's last login (`checkAccount` guard), so a zero-login state (and the auto-cleanup timeout that follows it) can never be reached through the API. There is no `DELETE /.account/account/{id}`.
- Given the same session's live incident (see below) came from acting on an unverified CSS API assumption, hand-editing `.internal/accounts/` index+data files across 18 live records to force the cascade manually was judged too risky without a backup and was **not done**. Actual risk of leaving them is assessed as zero — no real pod data, no `.acl` grants, not linked to `/` (that grant was already removed). They are dead rows, not a live exposure.
- Real fix path: either (a) a one-off Node script run inside the CSS container using its own `AccountStore` module directly (uses the real cascade-delete, safest option, needs someone with container shell access + reading the CSS source to construct it correctly), or (b) upgrade/patch to a CSS version that exposes account deletion over HTTP, if one exists upstream. Also: fix E2E test scripts to clean up via a full account-teardown path, not just the pod folder, so this doesn't recur.

### Incident during code review verification (2026-07-22)

While live-testing the resumable `registerAccount` fix, a curl call to `controls.account.pod` with an intentionally malformed body (`{}`, no `name` — meant to force a retry-path failure) was **not rejected by CSS**. It created a pod at the **site root** (`https://pod.nicolasdb.eu/`), overwriting the root `.acl` to grant a throwaway test WebID full `Read/Write/Control` over the entire storage root. No `css-data` backup existed. Fixed immediately: root `.acl` restored to public-read-only (best-effort reconstruction, not a byte-for-byte backup restore — no original was available). The account's password login was deleted where possible; CSS refused deletion since it was the account's only login, so the credential itself still exists but the security exposure (root access grant) is closed. The leftover pod's disk data was removed via `rm -rf` (same pattern as the story's own throwaway-pod cleanup). Other pods (`ayoub`, `claire`, etc.) were unaffected — each has its own `.acl` overriding root's default inheritance, confirmed live.

**Root cause / lesson:** CSS's `controls.account.pod` treats a missing `name` as "claim the pod root" rather than rejecting the request — undocumented, surprising behavior. Our app's client-side code already guards against this (`obCreatePod` never calls `registerAccount` with an empty slug), so this is **not reachable through the real UI** — it only occurred because a manual curl test bypassed that client-side guard. Still, worth a defense-in-depth note: `registerAccount` in `pod-api.js` could reject an empty `podName` before hitting the network as an extra guard, and CSS deployments handling untrusted direct API traffic should treat this root-claim behavior as a known footgun.

## Deferred from: code review of story-7.3 (2026-07-23)

- TOCTOU on all "already exists" collision checks (create/rename/upload) [backoffice/index.html] — client-cache-only guard, no ETag/If-Match. Needs an optimistic-concurrency design across the whole API, not scoped to this story.
- Upload batch: weak per-file failure aggregation, no size/progress guard for large files [backoffice/pod-api.js, backoffice/index.html] — explicitly in scope of story 7.6 (bulk/large-file hardening), already drafted.
- Delegate with inherited Control could overwrite the real pod owner's `#owner` authorization via hardcoded `this.webId` in `_writeAcl` [backoffice/pod-api.js] — real risk only once multi-collaborator Control-delegation is a live flow; current app model is single-owner (Nicolas). Revisit alongside team-pod work.
- Turtle lexer (`_turtleStatements`) mishandles backslash-escaped quotes inside string literals [backoffice/pod-api.js] — narrow input shape (foreign-authored `.acl` with escaped quotes), not hit by this app's own writes.
