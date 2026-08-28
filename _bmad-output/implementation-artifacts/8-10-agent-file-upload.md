# Story 8.10: Agent File Upload — Ticketed Out-of-Band Transfer

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent that has just produced a real file on disk — a screen capture, an audio message, a session transcript dumped as JSON or TOML by a local script —
I want to push those bytes into the pod without re-emitting their content as a tool argument,
so that capture stops being priced per byte of model output and stops being capped by a JSON-RPC body limit.

## Context — the problem this closes

Today the connector's only write path is `content:` as a JSON string on `solid_write_resource` / `solid_append_resource`. For a file that **already exists on disk**, that forces an absurd round trip: read the file into context, re-emit it byte-for-byte as a tool argument, and have the connector write it back out. A 50KB file is ~15k output tokens, truncation-prone, and it crosses two independent ceilings:

| Ceiling | Where | Effect |
|---|---|---|
| Model output tokens | agent must re-emit file as an argument | ~15k tokens per 50KB, truncation risk |
| `express.json()` 100kb + nginx `client_max_body_size 100k` | `mcp-server.js:936`, `11-solid-mcp.conf` | hard reject above ~100kb of escaped JSON |

Slicing into smaller files does not help — it multiplies the cost, because each chunk is read-into-context, emitted, and (for append) read-then-overwritten pod-side.

**This is not a gap in our code.** Verified against the MCP specification (2026-07-28) via Context7:

- `tools/call` params are JSON. There is no byte channel in a tool argument.
- `roots/list` returns **URIs only** — `{"uri": "file:///home/user/projects/myproject"}`. It tells a server which paths it may operate on; it transfers nothing. A *remote* server handed `file:///tmp/x.jpg` can do nothing with it.
- `resources/*` flows server → client. Wrong direction.

MCP has **no client→server bulk-transfer primitive**. Any solution is necessarily out-of-band. This story adopts one.

## Decision — path A, ticketed

Chosen from a seven-option survey (party-mode session, 2026-08-28). **Decision in-band, bytes out-of-band:**

```
1. agent calls MCP tool
     solid_prepare_upload(targetUrl, contentType, bytes)
   -> connector probes targetUrl, reports what exists (ceremony happens HERE)
   -> returns { uploadUrl, expiresIn: 300, curl: "<ready-to-run command>" }

2. agent runs the returned command (it has a shell; the file is already on disk)
     curl --data-binary @/tmp/screencap.jpg <uploadUrl>

3. connector buffers, verifies length, PUTs to CSS as the agent identity
   -> journal entry, no receipt (this is a write to one's own pod)
```

Why ticketed rather than `curl -T file https://host/upload/<slug>?target=...`:

- **The slug must not leave the JSON-RPC channel.** It is the bearer credential for `/mcp/:slug`. In a curl invocation it lands in shell history and in `ps` output for the duration of the transfer. Story 8.4 deliberately set `access_log off` on the proxy location to keep that string out of nginx logs; leaking it into `~/.bash_history` is the same regression by another route.
- **The ticket restores Story 8.6's ceremony.** The existence probe and the "this replaces N bytes starting `...`" warning happen inside the tool call at step 1, where the model can surface it to the human before any byte moves. A bare `curl -T` would be a blind PUT with less ceremony than granting a stranger read access — exactly the defect 8.6 Task 2 fixed for `solid_write_resource`.

**Prior art:** Nicolas reports the same ticket-handoff shape in use elsewhere for moving generated `.stl` files out of a Claude conversation. The pattern is not novel; that is a point in its favour.

### Rejected alternatives (do not re-litigate without new information)

| | Path | Why not |
|---|---|---|
| B | Client holds its own CSS credential, PUTs direct | Moves a credential off the VPS. Re-opens **SEC-4**, whose risk acceptance is justified entirely by "SSH-key-only, sole key holder, own data." |
| C | `solid_fetch_to_pod(sourceUrl, targetUrl)` — connector pulls | Installs an SSRF primitive on a host adjacent to CSS, Oxigraph and Qdrant. Viable later **only** with a scheme+host allowlist and no redirect-following. |
| D | Generic upload ticket redeemable by a browser | This story *is* D's mechanism, scoped to the agent case. Browser redemption is a later extension, not now. |
| E | Chunked append via tool args | The waste this story exists to remove. Explicitly **not** built (see AC10). |
| F | Human downloads, uploads via backoffice | Already exists (`pod-api.js:142`, Story 7.3). Remains the claude.ai answer. |
| G | Local stdio MCP sidecar reading local paths | Nicest ergonomics, but same credential-off-VPS problem as B. |

### Scope boundary — claude.ai gets nothing from this

claude.ai has no shell, so it cannot execute step 2. Upload is a **shell-capable-clients-only** capability: Claude Code, Hermes, cron scripts. For claude.ai the answer stays path F — download the artifact, upload it from the backoffice. This must be stated plainly in `SKILL.md` rather than left for a user to discover by failure.

## Acceptance Criteria

1. **`solid_prepare_upload` tool exists** taking `targetUrl` (pod URL), `contentType`, and `bytes` (declared size). It returns `uploadUrl`, `expiresIn`, and a ready-to-run `curl` command string. Registered alongside the existing nine tools in `buildMcpServer()`.

2. **Ticket properties, all four enforced:** opaque (CSPRNG, ≥22 chars, same generator class as `scripts/gen-slug.js`), **single-use** (redeemed or expired, never both-usable), **TTL 300s**, and **bound at issue time to both the target URL and the issuing identity**. A ticket cannot be redirected to a different target or redeemed as a different identity.

3. **Existence probe at ticket time.** `solid_prepare_upload` probes `targetUrl` before issuing. If the resource exists, the tool response states the byte count and first line of what would be lost (same shape as `solid_write_resource`'s Task 2.2/2.4 report, codepoint-sliced via `Array.from`, not `.slice`). A ticket for an existing resource is issued **only** when the call passes `overwrite: true`. A failed probe fails toward caution — never silently treated as "new".

4. **`POST /upload/:token` route** mounted **outside** `/mcp`, with its own raw-body parser, its own size cap and its own rate-limit bucket — the isolation shape Story 7.9 established for `/onboard` (`mcp-server.js:1011`). It must not parse JSON, so the 100kb `express.json` ceiling never applies to it.

5. **Content-type comes from the ticket, never from the upload request.** curl defaults to `application/x-www-form-urlencoded` and a client can assert anything; the type declared at step 1 is authoritative.

6. **Buffer, verify, then PUT — never stream through.** Received length is compared against the ticket's declared `bytes`; a mismatch is rejected and **nothing is written to the pod**. Rationale: pods have no versioning, so a client dying at 60% must not leave a truncated `screencap.jpg` at the real URL. A rejected upload leaves the pod byte-identical to before.

7. **nginx `client_max_body_size` is raised only inside `location /upload/`** in `11-solid-mcp.conf`, never at server level. Raising it at server level would silently unwind the 100k cap protecting `/mcp` and regress Story 8.4 AC4.4. App-level cap and nginx cap must agree (proposed: 25M — record the number actually chosen and why).

8. **Journal entries for both events** (`upload_prepared`, `upload_completed`) via `journal.js`, carrying identity `label` and target URL only. Never the token, never the slug — `journal.js`'s existing rule. **No receipt**: `receipt.js` implements BP-1 read receipts for reading *someone else's* data; this is a write to one's own pod.

9. **Live end-to-end proof** from a real shell-capable client against the deployed VPS endpoint: a file **larger than 100kb** (so it demonstrably could not have gone through the JSON-RPC path) lands in the pod with correct bytes and correct content-type. Verify by reading it back and comparing a checksum against the source. Per the Epic 8 convention, append a dated section to `https://pod.nicolasdb.eu/nicolas_claude/epic-8-action-log.md` (read-then-append, never overwrite) and add a Story 8.10 section to `epic-8-progress-report.md`.

10. **Adversarial cases proven, not assumed** — each must be demonstrated live or by script under `mcp-connector/scripts/`:
    - expired ticket → refused
    - ticket replayed after successful redemption → refused
    - ticket redeemed against a *different* target URL than issued for → refused
    - body larger than the cap → refused at nginx, not streamed into Node
    - declared `bytes` ≠ actual body length → refused, pod unchanged
    - unknown/guessed token → generic failure, no information about whether tokens exist (same discipline as the `/mcp/:slug` 404 path, AC4/8.3)

11. **`SKILL.md` documents the two-step flow** and states the claude.ai boundary explicitly (no shell → path F, download and upload from the backoffice). `references/developer-toolkit.md` gains the new module entry. The tool count "Nine tools are available" in `SKILL.md` is updated.

12. **Chunked-append is NOT built.** Out of scope by decision, not by omission.

## Tasks / Subtasks

- [ ] **Task 1 — Ticket store** (AC: 2)
  - [ ] 1.1 New module `src/uploadTickets.js`: in-memory `Map`, TTL 300s, single-use, bound `{targetUrl, identityLabel, contentType, bytes, issuedAt}`. Restart drops in-flight tickets — acceptable at a 5-minute window; say so in the header comment.
  - [ ] 1.2 Token generation reusing the CSPRNG approach in `scripts/gen-slug.js` (22 chars). Do not invent a second scheme.
  - [ ] 1.3 Sweep expired entries on access; do not leave an unbounded Map (same bounded-growth discipline as `journal.js`'s rotation).
  - [ ] 1.4 Redemption is atomic: delete-then-use, so two concurrent redemptions cannot both succeed.

- [ ] **Task 2 — `solid_prepare_upload` tool** (AC: 1, 3, 5)
  - [ ] 2.1 Register in `buildMcpServer()` via `safeHandler(...)`, matching the existing nine registrations' shape.
  - [ ] 2.2 Existence probe reusing `solid_write_resource`'s `_probe404` logic — **do not duplicate it**, extract or call it.
  - [ ] 2.3 Gate on `overwrite: true` for an existing target; report bytes + first line otherwise.
  - [ ] 2.4 Return `uploadUrl`, `expiresIn`, and a literal `curl --data-binary @<path> <uploadUrl>` string the agent can run unmodified.
  - [ ] 2.5 `annotations`: this call itself writes nothing — `readOnlyHint: false` (it mutates ticket state) but **not** `destructiveHint`; the destructive moment is redemption.

- [ ] **Task 3 — `POST /upload/:token` route** (AC: 4, 5, 6, 8)
  - [ ] 3.1 Mount outside `/mcp`, after the `/onboard` mount in `main()`. Own `express.raw({ type: '*/*', limit: <cap> })`.
  - [ ] 3.2 Own `rateLimit` bucket — **not** `mcpLimiter`. Uploads are low-count/high-bytes; sharing a 120/min bucket describes neither traffic shape. Generic 429 via the existing `rateLimitHandler` discipline.
  - [ ] 3.3 Redeem ticket → resolve identity → `podClient.writeFile(targetUrl, buffer, ticket.contentType, identity.session)`.
  - [ ] 3.4 Length check against `ticket.bytes` **before** any pod write.
  - [ ] 3.5 Unknown/expired token returns the same generic shape as the `/mcp/:slug` 404 path. Never log the attempted token.
  - [ ] 3.6 Journal `upload_prepared` (Task 2) and `upload_completed` (here) — label + target URL only.

- [ ] **Task 4 — nginx** (AC: 7)
  - [ ] 4.1 `location /upload/ { client_max_body_size <cap>; }` in `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf`. Server-level stays 100k.
  - [ ] 4.2 Keep `access_log off` on this location too — the URL path carries a redeemable credential.
  - [ ] 4.3 Check `proxy_read_timeout`/`proxy_send_timeout` (currently 60s) are adequate for the cap over a slow link; raise for this location only if not. Note that the app's `REQUEST_TIMEOUT_MS` (55s) sits just under it and applies to this route as well — reconcile explicitly rather than discovering it live.

- [ ] **Task 5 — Adversarial verification** (AC: 10)
  - [ ] 5.1 `scripts/verify-upload-tickets.js` covering all six cases in AC10, following the existing `verify-*.js` conventions.
  - [ ] 5.2 Confirm the pod is byte-identical after every refused case.

- [ ] **Task 6 — Live proof + docs** (AC: 9, 11)
  - [ ] 6.1 Deploy (`make vps-push` / `vps-build` / `vps-deploy`), then push a >100kb real file end-to-end from a shell-capable client; checksum round-trip.
  - [ ] 6.2 Append dated section to the live `epic-8-action-log.md` (read-then-append).
  - [ ] 6.3 Story 8.10 section in `epic-8-progress-report.md` — proof table, bugs found+fixed, scope notes.
  - [ ] 6.4 `SKILL.md`: two-step flow, tool count, **claude.ai boundary stated plainly**.
  - [ ] 6.5 `references/developer-toolkit.md`: `uploadTickets.js` entry.
  - [ ] 6.6 `epics.md`: record Story 8.10 outcome under the Epic 8 story list.

## Dev Notes

### Traps that have already cost this codebase time

- **Do not add a second `express.json()` to raise the cap.** Story 8.4 tried it: `createMcpExpressApp()` registers `express.json()` (default 100kb) ahead of user middleware, and Express uses the **first** parser registered, so a later larger limit is dead code. This story does not need it anyway — `/upload/` uses `express.raw`, a different route with its own parser. Marked "Do not 'fix' this again" in `8-4-vps-deploy-hardening.md:403`.
- **`podClient.writeFile()` coerces strings to Buffer** because Inrupt's Node `File`-detection polyfill crashes on a raw string (Story 8.1, found live on first real write). Passing an `express.raw` Buffer straight through is the supported path — do not stringify it first.
- **`ALLOWED_HOSTS` / DNS-rebinding.** The SDK's Host check is app-level and applies to every route including `/upload/`. `solid-mcp.nicolasdb.eu` is already allowlisted (`docker-compose.yml:93`). Story 7.9 lost live time to exactly this when `/onboard` was reached via a hostname that wasn't listed — every request 403'd "Invalid Host" before reaching the router.
- **`trust proxy: 1`, not `true`.** Already set. Rate limiting on the new bucket depends on it. `true` would trust the whole forged XFF chain and let every caller pick their own bucket.
- **Static-asset caching does not apply here** (no backoffice change), but if any backoffice surface is touched later, `?v=` bumping is mandatory — CSS serves it `max-age=86400` with no ETag.

### Source tree — files to touch

**New**
- `mcp-connector/src/uploadTickets.js`
- `mcp-connector/scripts/verify-upload-tickets.js`

**Modified**
- `mcp-connector/src/mcp-server.js` — tool registration (~line 690, after the permission tools), route mount (~line 1011, after `/onboard`)
- `mcp-connector/SKILL.md` — flow, tool count, claude.ai boundary
- `mcp-connector/references/developer-toolkit.md`
- `hetzner-gateway/nginx/conf.d/11-solid-mcp.conf` — **VPS-side, not in this repo**
- `_bmad-output/implementation-artifacts/epic-8-progress-report.md`
- `_bmad-output/planning-artifacts/epics.md`

**Reused, do not reimplement**
- `podClient.writeFile()` — the pod write
- `journal.js` `append()` — audit entries
- `scripts/gen-slug.js` — CSPRNG token generation
- `safeHandler()` in `mcp-server.js` — tool error normalization
- `_probe404()` in `mcp-server.js` — existence probe

### Invalidated Assumptions

- **Assumption:** `8-4-vps-deploy-hardening.md` — "raising the cap needs an explicit `{ limit }` through the SDK, which its current API does not expose." → **Reality:** `createMcpExpressApp()` is a *convenience wrapper*. The SDK's documented Express integration is to build your own app, register your own `express.json({ limit })`, and call `transport.handleRequest(req, res, req.body)`. The 100kb ceiling is inherited, not imposed. **This story does not act on that** — it routes around the JSON parser entirely — but the recorded claim is wrong and should not be relied on by a future story.
- **Assumption (implied by Story 7.3's upload work):** the backoffice already has upload, so agent upload is a small extension. → **Reality:** `pod-api.js:142 uploadFile()` is **browser → CSS direct**, using the human's own session and a `File` object from `<input type=file>`. The connector is not in that path and neither is any cap. Reusable as a *pattern* (content-type from `file.type`, per-file failure isolation, overwrite confirmation at `index.html:1163`) — not as a code path.
- **Assumption:** an MCP tool could take a local file path. → **Reality:** the connector is a *remote* HTTP server. `roots/list` transfers URIs, not bytes. A path argument is meaningless server-side. Only a stdio/local server (rejected path G) could honour one.

### Project Structure Notes

- The `/upload/` route is a **third** independent surface on this app, alongside `/mcp/:slug` (JSON-RPC, slug auth) and `/onboard` (cookie auth, CORS-restricted). Keep the three auth models genuinely separate — Story 7.9's comment at `mcp-server.js:1007` is the precedent and the reason.
- Credential posture is unchanged: the VPS still holds every CSS credential and no client gains one. That is what keeps **SEC-4**'s risk acceptance intact, and it is the reason paths B and G were rejected. **If a future story moves a credential onto a client machine, SEC-4 must be re-opened, not quietly widened.**
- No receipt is written (AC8). Confirm against **BP-1** before changing that: receipts exist so that reading someone else's data leaves a trace in *their* pod. Uploading to your own pod has no data subject other than yourself.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 8: Solid MCP Connector] — non-negotiables, auth posture, slug as load-bearing
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision SEC-4] — credential-at-rest risk acceptance and its trigger
- [Source: _bmad-output/planning-artifacts/architecture.md#Principle BP-1] — receipts land with the data subject
- [Source: _bmad-output/planning-artifacts/architecture.md#Principle BP-6] — single-writer pods; append-only mailbox is the one exception
- [Source: _bmad-output/implementation-artifacts/8-4-vps-deploy-hardening.md:166-167,294,403] — body cap, nginx reconciliation, the dead-code trap
- [Source: _bmad-output/implementation-artifacts/8-6-capture-surface-and-skill.md] — destructive ceremony, existence probe, append-first
- [Source: _bmad-output/implementation-artifacts/8-9-access-journal-tamper-spike.md] — `postResource`, append-only journal, live-verification discipline
- [Source: mcp-connector/src/mcp-server.js:55-90,936,1007-1011] — ALLOWED_HOSTS, body cap comment, router isolation precedent
- [Source: mcp-connector/src/podClient.js:44-58] — `writeFile` Buffer coercion
- [Source: backoffice/pod-api.js:140-148] — browser-direct upload, pattern reference only
- [Source: MCP specification 2026-07-28, `client/roots.mdx`, `server/tools.mdx` via Context7] — roots return URIs not bytes; tool args are JSON

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
