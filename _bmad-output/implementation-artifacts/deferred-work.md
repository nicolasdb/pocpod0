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
