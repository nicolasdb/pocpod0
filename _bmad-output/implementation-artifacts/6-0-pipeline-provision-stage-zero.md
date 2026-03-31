# Story 6.0: Pipeline Provision as Stage 0

Status: ready-for-dev

## Story

As a **demo facilitator** (Nicolas),
I want `run_pipeline.py` to provision pods and seed community data as Stage 0 before all other stages,
so that a full demo reset is a single command (`compose down -v && compose up -d && run_pipeline.py`) with no manual steps.

## Acceptance Criteria

1. **AC1: Stage 0 provisions all pods**
   - **Given** CSS is running after a `compose down -v && compose up -d`
   - **When** `run_pipeline.py` executes
   - **Then** Stage 0 runs first, calling `provision_pods.py` to create all pods from `pod-config.yaml`
   - **And** access-log ACLs are configured for all pods (via `provision_access_log_acl`)
   - **And** JSONL events `stage.start` and `stage.done` are emitted to `data/pipeline-run.jsonl`

2. **AC2: Stage 0 seeds community pod with dietary aggregate**
   - **Given** `school-community` pod exists (created by provision step)
   - **When** Stage 0 completes provisioning
   - **Then** `camp-dietary-aggregate.ttl` content is written to `http://localhost:3000/school-community/camp/dietary-aggregate-2026` via CSS HTTP PUT
   - **And** the resource is valid Turtle and readable via CSS GET with appropriate WebID
   - **And** a `stage.done` JSONL event includes elapsed time

3. **AC3: Full reset produces working demo state**
   - **Given** `podman compose down -v` followed by `podman compose up -d`
   - **When** `python pipeline/run_pipeline.py` completes all stages (0 through 5)
   - **Then** Isabelle can query the community pod's dietary aggregate (`camp-aggregate.rq` template)
   - **And** the food service ephemeral consent scenario (Story 5.6) works end-to-end
   - **And** no manual seed data steps are required

4. **AC4: Stage 0 is idempotent**
   - **Given** pods already exist (e.g., running pipeline a second time without `--wipe`)
   - **When** Stage 0 runs
   - **Then** existing pods are not duplicated (CSS returns 409 for existing pods, tolerated)
   - **And** seed data is overwritten via PUT (idempotent by HTTP semantics)
   - **And** no errors are raised

5. **AC5: Stage labels updated**
   - **Given** the STAGES list now has 6 stages
   - **When** displayed to the user
   - **Then** labels show `[0/6]` through `[6/6]` (not `[1/5]` through `[5/5]`)

## Tasks / Subtasks

- [ ] Task 1: Create `provision_stage.py` module (AC: 1, 2, 4)
  - [ ] 1.1: New module `pipeline/src/pocpod0_pipeline/provision_stage.py` — callable as `python -m pocpod0_pipeline.provision_stage`
  - [ ] 1.2: Call `PodProvisioner.provision_all()` with error handling (non-zero exit on failure)
  - [ ] 1.3: Seed `school-community` pod — HTTP PUT `camp-dietary-aggregate.ttl` to `/school-community/camp/dietary-aggregate-2026` with `Content-Type: text/turtle` and provisioner WebID auth
  - [ ] 1.4: Handle CSS LDP container auto-creation — PUT to `/school-community/camp/dietary-aggregate-2026` will auto-create `/school-community/camp/` container if CSS is configured to do so; if not, create it first
  - [ ] 1.5: Exit 0 on success, non-zero on failure
- [ ] Task 2: Wire Stage 0 into `run_pipeline.py` (AC: 1, 5)
  - [ ] 2.1: Insert new stage at position 0 in `STAGES` list: `{"name": "provision", "label": "[0/6] Provision pods + seed data", "cmd": [sys.executable, "-m", "pocpod0_pipeline.provision_stage"]}`
  - [ ] 2.2: Update all existing stage labels from `[1/5]`..`[5/5]` to `[1/6]`..`[5/6]`
  - [ ] 2.3: Stage 0 uses the same `run_stage()` framework — JSONL events are automatic
- [ ] Task 3: Wire `--wipe` flag to also wipe community pod seed data (AC: 4)
  - [ ] 3.1: The existing `wipe_css_pods()` already recursively deletes `learning/` containers — verify it also covers `camp/` container in `school-community`, or extend to cover community pod seed paths
- [ ] Task 4: Tests (AC: 1-5)
  - [ ] 4.1: Unit test for `provision_stage.py` — mock `PodProvisioner` and CSS PUT, verify calls and exit codes
  - [ ] 4.2: Verify STAGES list has 6 entries with correct labels
  - [ ] 4.3: Verify stage 0 is first in execution order

## Dev Notes

### Architecture Compliance

- **JSONL events:** Stage 0 MUST emit events via `run_stage()` — which calls `_emit("stage.start", ...)` and `_emit("stage.done", ...)` automatically. No custom JSONL code needed in the stage module itself.
- **Module pattern:** All existing stages are invocable as `python -m pocpod0_pipeline.<module>`. Stage 0 must follow the same pattern. See `generate_troll_load`, `generate_scenarios`, `ingest`, `load_graph`, `embed` for reference.
- **Error handling:** `run_stage()` (line 267) checks `result.returncode != 0` and calls `sys.exit()`. The new module must exit non-zero on failure.

### Key Files to Touch

| File | Action |
|------|--------|
| `pipeline/src/pocpod0_pipeline/provision_stage.py` | **CREATE** — Stage 0 entry point module |
| `pipeline/run_pipeline.py` | **EDIT** — Add stage 0 to `STAGES`, update labels |
| `pipeline/tests/test_provision_stage.py` | **CREATE** — Unit tests |

### Key Files to Reference (READ ONLY)

| File | What to Extract |
|------|-----------------|
| `pipeline/run_pipeline.py:54-81` | `STAGES` list structure — match this format exactly |
| `pipeline/run_pipeline.py:267-282` | `run_stage()` — understand how stages are executed |
| `pipeline/run_pipeline.py:46-51` | `_emit()` — JSONL event format (stage module does NOT call this directly) |
| `pipeline/run_pipeline.py:192-232` | `wipe_css_pods()` — understand what `--wipe` already cleans |
| `pipeline/src/pocpod0_pipeline/provision_pods.py:42-50` | `PodProvisioner.__init__()` — constructor signature |
| `pipeline/src/pocpod0_pipeline/provision_pods.py:169` | `provision_all()` — returns `Dict` with `{created, failed, acl_applied, acl_failed}` |
| `pipeline/src/pocpod0_pipeline/provision_pods.py:653` | `provision_access_log_acl()` — called inside `provision_all()`, no separate call needed |
| `pipeline/src/pocpod0_pipeline/provision_pods.py:764-796` | `main()` — reference for CSS_BASE_URL resolution and config_path derivation |
| `data/seeds/camp-dietary-aggregate.ttl` | Exact seed content to PUT to community pod |
| `infra/css/pods/pod-config.yaml` | Pod definitions used by `PodProvisioner` |

### CSS HTTP PUT for Seed Data

```python
# PUT Turtle resource to CSS pod
# CSS accepts PUT with Authorization: WebID header
# Content-Type: text/turtle
# URL: {css_base_url}/school-community/camp/dietary-aggregate-2026

headers = {
    "Authorization": f"WebID {css_base_url}/provisioner/profile/card#me",
    "Content-Type": "text/turtle",
}
seed_path = project_root / "data" / "seeds" / "camp-dietary-aggregate.ttl"
resp = requests.put(url, headers=headers, data=seed_path.read_text())
# Accept 201 (created) or 205 (updated) — CSS returns 205 on overwrite
```

### Wipe Considerations

The existing `wipe_css_pods()` in `run_pipeline.py` deletes `/{slug}/learning/` containers for all pods. The `school-community` pod seed goes to `/school-community/camp/`, which is NOT cleaned by the current wipe. Two options:
1. **Extend `wipe_css_pods()`** to also delete `/{slug}/camp/` — safe since Stage 0 will re-seed it
2. **Rely on `compose down -v`** as the primary full-reset mechanism (already documented as the demo reset strategy)

Recommend Option 2 for PoC simplicity — `--wipe` is a partial cleanup tool, `compose down -v` is the full reset. Document this distinction.

### Invalidated Assumptions

| Assumption | Status | Correction |
|---|---|---|
| `agent.yaml` is the agent config format | INVALIDATED (Epic 3.3) | Agents use `SOUL.md` / `AGENTS.md` / `IDENTITY.md` workspace — no YAML config |
| `provision_pods.py` seeds community data | INVALIDATED (Epic 5 retro) | `provision_pods.py` only creates pods + applies ACLs. Community data seeding is a separate step (this story) |
| `--wipe` flag provides full reset | PARTIAL | `--wipe` cleans learning/ containers + Oxigraph + Qdrant. Does NOT delete community pod seed data. Full reset = `compose down -v` |

### Environment

- **Distrobox note:** `distrobox-host-exec podman compose` for container commands from within distrobox
- **CSS health:** Wait for CSS healthcheck before running provision (compose `depends_on` handles this for services, but pipeline script runs outside containers)
- **CSS base URL:** Default `http://localhost:3000` when running outside Docker network

### Previous Story Intelligence (Story 5.6)

- `httpx` and `requests` coexist in the codebase — `provision_pods.py` uses `requests`, `run_pipeline.py` uses `httpx`. For the new module, use `requests` (consistent with `provision_pods.py` which it wraps).
- `_safe_uri()` pattern from Story 5.4 — not needed here (no user-supplied URIs in seed data).
- `sys.modules` registration after `importlib.exec_module()` — only relevant if the new module uses importlib patterns (unlikely for this story).

### Project Structure Notes

- New module `provision_stage.py` goes in `pipeline/src/pocpod0_pipeline/` alongside existing pipeline modules
- Test file goes in `pipeline/tests/test_provision_stage.py`
- No new dependencies required — `requests` already in pipeline dependencies

### References

- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-03-30.md#Pipeline Gap] — Story 6.0 origin and rationale
- [Source: _bmad-output/planning-artifacts/architecture.md#INFRA-5] — JSONL event format spec
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 6] — Epic 6 overview and narrative context
- [Source: pipeline/run_pipeline.py:54-81] — STAGES list to modify
- [Source: pipeline/src/pocpod0_pipeline/provision_pods.py:764-796] — `main()` pattern to reuse

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
