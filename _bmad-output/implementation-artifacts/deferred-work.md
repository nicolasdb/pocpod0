# Deferred Work

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

## Side Quest: OpenClaw gateway bind / WebUI + CLI pairing (2026-04-14)

- **Issue:** With `OPENCLAW_GATEWAY_BIND=lan` (OpenClaw-recommended Docker value), the browser WebUI at `http://localhost:18789` reaches the gateway but shows "disconnected — pairing required"; the CLI inside the container cannot connect via `ws://127.0.0.1:18789` (loopback not bound), so `openclaw devices approve` has no working path to clear the pairing. Exec approvals from Discord also depend on the WebUI/TUI approval loop in the absence of a confirmed native Discord execApprovals registration.
- **Regression vs. Epic 3:** Stories 3.3–3.8 did not hit this. The Story 4.0 seed-on-boot refactor changed the entrypoint and bind semantics; something in that transition invalidated the previously working state. Diff Story 3.3 compose/entrypoint against current to isolate the delta.
- **Tried (all dead-ends):** `bind=all` (invalid value, crash-loop), `bind=auto` (loopback-only, host port unreachable), `bind=lan` (current — WebUI reachable but CLI pairing stuck). Current state is equivalent to Story 4.0 RI-2.
- **Next steps for the side quest:**
  1. Diff Story 3.3 openclaw config/compose vs. current to find the behavior delta.
  2. Investigate `bind=custom` with an explicit listen address covering both loopback and eth0 (per OpenClaw gateway config reference).
  3. Alternative: have `openclaw-cli` connect via the container's eth0 interface instead of `127.0.0.1` so CLI works under `bind=lan`.
  4. Validate whether `channels.discord.execApprovals` actually registers a native approvals client once pairing is unblocked.
- **Workaround for now:** Accept as carried RI-2. Discord chat + agent heartbeats work; WebUI control and CLI pairing remain broken. Observe via `podman logs openclaw-gateway`.
