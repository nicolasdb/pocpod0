# Story 2.2: xAPI-OSLO RDF Ingestion Pipeline

Status: done

## Story

As a **developer**,
I want a pipeline that generates synthetic xAPI statements and converts them to OSLO-mapped RDF triples stored as Turtle resources in learner Pods,
so that the three-layer data architecture has realistic learning data flowing through a lossless transformation pipeline.

**Primary goal:** Prove we can ingest raw data into a pod, generate RDF triples and vector embeddings from it, and enforce strict permission access rules across stakeholder types. Troll stress-tests this — key deliverable.
**Secondary goal:** Prove we can import data as currently formatted in schools (xAPI).

## Acceptance Criteria

**AC1: Scenario xAPI dataset generated (~300-500 statements)**
Given the 5 learner personas (Ayoub, Lucas, Emma, Youssef, Nour)
When the scenario generator script executes
Then ~300-500 narrative-rich xAPI statements are produced in `data/synthetic/scenarios/`
And statements cover: course activities, assessments, tutoring sessions, self-study, extracurricular (robotics workshop), cross-institutional contexts
And the generator uses `data/schemas/pocpod0-xapi-profile.jsonld` as its vocabulary/persona reference

**AC2: Scenario dataset covers all 5 persona scenarios**
Given the generated scenario dataset
When analyzed for scenario coverage
Then data supports:
- Claire's cross-context query (Alex/Lucas — struggling student with hidden tutoring progress)
- Fatima's multi-child unified view (Youssef + Nour, two schools, NL+FR)
- Marc's transfer scenario (student transferring NL->FR)
- Isabelle's aggregate policy query (STEM program impact across communities)
- Ayoub's full learning history for governance/deletion scenarios

**AC3: All generated datasets are valid xAPI**
Given both the scenario dataset and the Troll load dataset
When validated against xAPI specification
Then all statements are valid xAPI JSON

**AC4: Troll load generator produces configurable-volume stress data**
Given a target volume parameter (default 5K, configurable up to 50K)
When the Troll load generator script executes
Then N minimal valid xAPI statements are produced in `data/synthetic/troll-load/`
And statements have diverse randomized WebIDs spanning multiple permission tiers (student, teacher, parent, admin, unauthorized)
And statements are structurally valid but not narratively coherent — simulating a raw school LRS dump

**AC5: Pipeline converts xAPI to OSLO-mapped RDF**
Given the synthetic xAPI datasets and the OSLO schema contract (from story 2-1)
When the ingestion pipeline (`pipeline/src/pocpod0_pipeline/ingest.py`) processes the datasets
Then each xAPI statement is converted to OSLO-mapped RDF triples using the schema contract
And the resulting Turtle resources are stored in the appropriate learner Pod via CSS

**AC6: Pipeline uses log+continue error handling**
Given a pipeline run processing statements
When individual statements fail conversion
Then the failure is logged (structured JSON to stdout) and the pipeline continues
And a summary reports total processed, succeeded, and failed counts

**AC7: Conversion is lossless**
Given the pipeline has completed
When I inspect the Pod resources
Then each learner Pod contains Turtle resources representing their learning activities
And the conversion is lossless — original xAPI data is preserved within the RDF representation (enabling FR10 round-trip recovery)

## Tasks / Subtasks

### Task 1: Set up Python package structure (AC4)
- [x] Create `pipeline/pyproject.toml` with project metadata, dependencies, and entry points
- [x] Dependencies: `rdflib`, `requests`, `httpx` (for async CSS/Oxigraph access), `pydantic` (for xAPI validation)
- [x] Build tool: use `uv` or `pip` compatible configuration
- [x] Create `pipeline/src/pocpod0_pipeline/__init__.py`
- [x] Create `pipeline/src/pocpod0_pipeline/utils.py` — shared utilities: structured JSON logging setup, config loading
- [x] Set up virtual environment activation (always activate venv for Python commands)

### Task 2a: Build scenario xAPI dataset generator (AC1, AC2, AC3)
- [x] Create `pipeline/src/pocpod0_pipeline/generate_scenarios.py`
- [x] Load persona definitions and vocabulary from `data/schemas/pocpod0-xapi-profile.jsonld`
- [x] Define the 5 personas and their learning contexts:
  - **Ayoub:** Full K-12 history — math courses, science labs, Khan Academy self-study, robotics workshop, assessments across NL school
  - **Lucas (Claire's student):** Struggling in math at school, thriving in gemeente tutoring (geometric visualization approach), moderate self-study
  - **Emma (Claire's student):** Average student, some tutoring, standard course progression
  - **Youssef (Fatima's child):** NL school, language arts + STEM activities, robotics workshop participant
  - **Nour (Fatima's child):** FR school, similar subjects, different activity providers
- [x] Generate ~300-500 narrative-rich xAPI statements distributed across personas:
  - Course activities (attended, completed, progressed)
  - Assessments (scored, passed, failed) — ensure Lucas fails school math tests but excels in tutoring
  - Tutoring sessions (gemeente-funded, with visibility: hidden-to-school markers)
  - Self-study (Khan Academy, online resources)
  - Extracurricular (robotics workshop with applied math exercises)
  - Cross-institutional contexts (NL and FR schools, community programs)
- [x] Include timestamps spanning a realistic school semester (September-January)
- [x] Output as JSON files in `data/synthetic/scenarios/` — one file per persona + one consolidated file
- [x] Validate all generated statements against xAPI spec (actor + verb + object mandatory, valid verb IRIs)
- [x] Use verbs and activity types from the jsonld profile (pocpod0:verb-mastered, pocpod0:verb-struggled-with, etc.)

### Task 2b: Build Troll load generator (AC4, AC3)
- [x] Create `pipeline/src/pocpod0_pipeline/generate_troll_load.py`
- [x] Accept `--count` parameter (default: 5000, max: 50000)
- [x] Generate N minimal valid xAPI statements with:
  - Randomized actor WebIDs spanning permission tiers: student (60%), teacher (15%), parent (10%), admin (10%), unauthorized/unknown (5%)
  - Diverse verb usage from standard ADL verbs (attended, completed, scored, attempted, etc.)
  - Randomized activity IDs across realistic school resource patterns
  - Timestamps spread across the same semester window (September-January)
  - Varying levels of completeness: some with result/score, some without, some with context extensions, some minimal
- [x] Output to `data/synthetic/troll-load/` as a single consolidated JSON file
- [x] Include a summary manifest: `troll-load-manifest.json` with WebID distribution, verb distribution, and volume stats
- [x] Validate all generated statements are structurally valid xAPI

### Task 3: Build xAPI-to-OSLO RDF converter (AC4, AC6)
- [x] Create `pipeline/src/pocpod0_pipeline/oslo_mapper.py` — OSLO vocabulary mapping logic
- [x] Load schema contract from `data/schemas/` (the 4 Turtle files from story 2-1)
- [x] Implement conversion for each xAPI component:
  - `actor` -> OSLO person classes with role metadata
  - `verb` -> OSLO education activity types
  - `object` -> OSLO education resources (course, assessment, activity)
  - `result` -> OSLO evaluation results with scores
  - `context` -> OSLO institutional context with community language tags
- [x] **Lossless conversion strategy:** Embed original xAPI JSON as a literal within the RDF representation (e.g., `pocpod0:originalXapi` property containing the serialized JSON string) so that round-trip recovery (FR10) is possible
- [x] Generate unique URIs for each converted resource (e.g., `pocpod0:statement/{uuid}`)
- [x] Add `prov:wasDerivedFrom` triple pointing to the Pod resource URI where the Turtle will be stored

### Task 4: Build ingestion pipeline — CSS Pod storage (AC4, AC5)
- [x] Create `pipeline/src/pocpod0_pipeline/ingest.py` — main ingestion orchestrator
- [x] Implement pipeline flow:
  1. Read synthetic xAPI statements from `data/synthetic/`
  2. For each statement, call `oslo_mapper.py` to convert to OSLO-mapped RDF
  3. Serialize as Turtle
  4. Store in the appropriate learner Pod via CSS HTTP API (PUT to `http://css:3000/{pod-name}/{resource-path}`)
- [x] Implement log+continue error handling:
  - Wrap each statement processing in try/except
  - Log failures as structured JSON: `{"level": "ERROR", "event": "ingest.statement.failed", "details": {"statement_id": "...", "error": "..."}}`
  - Continue processing remaining statements
- [x] Emit summary at end: `{"event": "ingest.run.complete", "details": {"total": N, "succeeded": M, "failed": K}}`
- [x] Pod resource path convention: `{pod-name}/learning/{activity-type}/{statement-uuid}.ttl`

### Task 5: Create pipeline entry point script (AC4)
- [x] Create CLI entry point in `pipeline/src/pocpod0_pipeline/ingest.py` (or `__main__.py`)
- [x] Support command-line arguments: `--input-dir` (default: `data/synthetic/`), `--css-base-url` (default from env: `CSS_BASE_URL`)
- [x] Create or update `scripts/run-pipeline.sh` to activate venv and run the pipeline

### Task 6: Write tests (AC1-AC7)
- [x] Create `tests/pipeline/test_generate_scenarios.py`:
  - Test: scenario dataset generates 300-500 statements
  - Test: all 5 personas have statements
  - Test: scenario coverage — Lucas has both failing school scores AND positive tutoring data
  - Test: all statements are valid xAPI JSON (actor + verb + object present)
  - Test: jsonld profile vocabulary is used (pocpod0 verbs/activities appear)
  - Test: tutoring statements have visibility markers
- [x] Create `tests/pipeline/test_generate_troll_load.py`:
  - Test: default run generates 5000 statements
  - Test: custom --count parameter respected
  - Test: WebID distribution roughly matches target percentages (student 60%, teacher 15%, etc.)
  - Test: all statements are structurally valid xAPI
  - Test: manifest file generated with correct distribution stats
- [x] Create `tests/pipeline/test_ingest.py`:
  - Test: single xAPI statement converts to valid Turtle
  - Test: lossless conversion — original xAPI recoverable from Turtle
  - Test: log+continue — pipeline survives malformed input
  - Test: summary counts are accurate
- [x] Create `tests/pipeline/test_oslo_mapper.py`:
  - Test: each xAPI component maps to correct OSLO class
  - Test: namespace prefixes are correct
  - Test: provenance triple (`prov:wasDerivedFrom`) is present

## Dev Notes

> **Handoff from Story 2.1:** See `_bmad-output/implementation-artifacts/2-1-oslo-vocabulary-schema-contract.md` — Handoff Notes section for gotchas and recommendations.
> Key: use schema files in `data/schemas/`; use `pocpod0:originalXapiJson` + `pocpod0:originalXapiStatementId` for lossless preservation; Oxigraph `POST /store` creates named graphs — always query with `GRAPH ?g { }`.

### Architecture Context
- **Three-Layer Data Model:** This story populates Layer 1 (Pod/CSS). Stories 2-3 and 2-4 populate Layer 2 (Oxigraph).
- **Data flow:** xAPI JSON -> oslo_mapper.py -> Turtle -> CSS Pod (PUT via HTTP) -> Later: load_graph.py reads from Pods and loads into Oxigraph
- **Lossless requirement is critical:** FR10 (round-trip xAPI recovery) depends on the original xAPI being preserved. The recommended approach is to store the original xAPI JSON as a literal property within the RDF graph (e.g., `pocpod0:originalXapi`). This is the simplest path to lossless round-trip.

### Technical Constraints
- **Python 3.12+** — use modern Python features
- **Package management:** `uv` or `pip` — configure in `pipeline/pyproject.toml`
- **Always activate venv** for Python commands
- **CSS base URL:** `http://localhost:3000` (or `http://css:3000` within Docker network)
- **CSS API:** HTTP PUT to store resources, HTTP GET to retrieve — standard Solid/LDP protocol
- **CSS Auth (CRITICAL):** ALL CSS requests (PUT, GET, DELETE) MUST include `Authorization: WebID http://localhost:3000/{agent}/profile/card#me` header. `X-Ms-User` does NOT work and is silently ignored by CSS 7. CSS must be configured with `debug-auth-header.json` (UnsecureWebIdExtractor). The provisioner WebID is `http://localhost:3000/provisioner/profile/card#me`. Without this header, all CSS operations return 401.
- **CSS success codes:** Accept `[200, 201, 205]` — CSS returns HTTP 205 (Reset Content) for successful ACL PUT updates
- **Structured JSON logging to stdout** — docker-compose captures it
- **Error handling:** log+continue — never halt the pipeline for one bad statement
- **Python naming:** `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- **File naming:** lowercase, hyphen-separated for non-Python files

### Synthetic Dataset Design Notes

**Two-generator architecture (agreed in party mode review):**
- **Scenario generator** (`generate_scenarios.py`): ~300-500 narrative-rich statements. Uses `data/schemas/pocpod0-xapi-profile.jsonld` as vocabulary/persona reference. Designed for demo quality — each persona has a coherent story arc.
- **Troll load generator** (`generate_troll_load.py`): Configurable volume (5K-50K). Minimal valid xAPI with diverse WebIDs across permission tiers. Designed for permission stress testing. Not narratively coherent — simulates raw school LRS dump.

The scenario dataset must be carefully designed to support all 5 demo journeys. Key data points:

**Claire's scenario (cross-context insight):**
- Alex (implemented as `claire-student-1`; referred to as "Lucas" in story text — both names used) fails math assessments at school (score 0.35–0.55)
- Same student excels in gemeente-funded tutoring (geometric visualization approach, score 0.82–0.96)
- Same student has Khan Academy self-study activity
- The hybrid query (SPARQL + vector) must be able to surface the tutoring insight that graph-only misses

**Fatima's scenario (multi-child view):**
- Youssef attends NL school — language arts strong, STEM activities, robotics
- Nour attends FR school — similar subjects, different providers
- Both children have extracurricular activities

**Marc's scenario (transfer):**
- One student has a complete NL school history
- Transfer event to FR school — data must support showing the complete profile to the receiving school

**Isabelle's scenario (aggregate policy):**
- Multiple students in STEM programs (robotics workshop)
- Data must support aggregate queries showing measurable impact on school performance
- Cross-community (NL + FR) data points

**Ayoub's scenario (full history + governance):**
- Complete learning history across all contexts
- Data rich enough to demonstrate deletion cascade (specific resources can be targeted)

### xAPI Verb IRIs (Common Ones to Include)
- `http://adlnet.gov/expapi/verbs/attempted`
- `http://adlnet.gov/expapi/verbs/completed`
- `http://adlnet.gov/expapi/verbs/passed`
- `http://adlnet.gov/expapi/verbs/failed`
- `http://adlnet.gov/expapi/verbs/scored`
- `http://adlnet.gov/expapi/verbs/attended`
- `http://adlnet.gov/expapi/verbs/progressed`

### Isolation Notes
- Use `distrobox-host-exec` for accessing podman containers from within distrobox
- CSS container must be running and healthy before pipeline can store resources
- Pipeline runs as a script, not a long-running service

### Project Structure Notes

Files to create:
- `pipeline/pyproject.toml`
- `pipeline/src/pocpod0_pipeline/__init__.py`
- `pipeline/src/pocpod0_pipeline/ingest.py`
- `pipeline/src/pocpod0_pipeline/oslo_mapper.py`
- `pipeline/src/pocpod0_pipeline/generate_scenarios.py`
- `pipeline/src/pocpod0_pipeline/generate_troll_load.py`
- `pipeline/src/pocpod0_pipeline/utils.py`
- `tests/pipeline/test_generate_scenarios.py`
- `tests/pipeline/test_generate_troll_load.py`
- `tests/pipeline/test_ingest.py`
- `tests/pipeline/test_oslo_mapper.py`
- `tests/pipeline/conftest.py` (if not existing)

Directories to create (if not existing):
- `pipeline/src/pocpod0_pipeline/`
- `data/synthetic/scenarios/`
- `data/synthetic/troll-load/`
- `tests/pipeline/`

Files to modify:
- `scripts/run-pipeline.sh` (create or update)

### Dependencies on Other Stories
- **Depends on Story 2-1:** OSLO schema contract must exist in `data/schemas/` before the pipeline can use it
- **Depended on by Story 2-3:** Graph loader reads Turtle from Pods (stored by this pipeline)
- **Depended on by Story 2-4:** Round-trip recovery tests need pipeline output

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` — Story 2.2 (Synthetic xAPI Dataset, line ~349-373) + Story 2.3 (xAPI-OSLO RDF Ingestion Pipeline, line ~374-396)
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` — Decision DA-1 (Three-Layer Data Model), DA-2 (Provenance & Traceability), DA-3 (OSLO Vocabulary Schema Contract), Error Handling patterns, Project Structure
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR8 (lossless ingestion), User Journeys (all 5 persona scenarios), Technical Success criteria
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — story-2-2-xapi-oslo-rdf-ingestion-pipeline

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References
- `repo_root()` in `utils.py` initially used `parents[4]` (too many levels); corrected to `parents[3]`
- Scenario total count (250) needed tuning of week-range parameters to reach 303 (AC1 requires 300-500)

### Completion Notes List
- **Task 1:** Updated `pyproject.toml` with `rdflib`, `httpx`, `pydantic` deps + CLI entry points. Created `utils.py` with structured JSON logging, CSS auth headers (Authorization: WebID), and path helpers.
- **Task 2a:** `generate_scenarios.py` generates 303 narrative-rich statements for 5 personas (seed=42). Alex (claire-student-1) has cross-context pattern: fails school math (0.35–0.55) + masters gemeente tutoring (0.82–0.96) + hidden-to-school-teachers markers + Khan Academy self-study. Ayoub has transfer event. Fatima children share robotics workshop on Wednesdays with sibling-present extension.
- **Task 2b:** `generate_troll_load.py` generates default 5K statements (max 50K via --count). WebID tier distribution matches spec: student 60%, teacher 15%, parent 10%, admin 10%, unauthorized 5%. Manifest JSON written with distribution stats.
- **Task 3:** `oslo_mapper.py` converts xAPI → OSLO RDF: actor→`oslo:Person`, object→`oslo:PublicService`, result→`oslo:Participation`. Lossless via `pocpod0:originalXapiJson` literal (original JSON) + `pocpod0:originalXapiStatementId`. `prov:wasDerivedFrom` points to CSS Pod resource URI.
- **Task 4:** `ingest.py` orchestrates load → convert → PUT to CSS. Uses `Authorization: WebID {PROVISIONER_WEBID}` for all CSS requests. Accepts CSS success codes 200/201/204/205. log+continue with structured JSON. Summary: `{"event":"ingest.run.complete","details":{"total":N,"succeeded":M,"failed":K}}`.
- **Task 5:** `scripts/run-pipeline.sh` activates venv, runs generate_scenarios, generate_troll_load, then ingest. Supports --dry-run, --count, --input-dir flags.
- **Task 6:** 47 tests pass (15 oslo_mapper, 8 troll, 19 scenarios, 9 ingest). All ACs validated. 0 regressions.

### File List
- `pipeline/pyproject.toml` (modified — added rdflib/httpx/pydantic deps + entry points)
- `pipeline/src/pocpod0_pipeline/utils.py` (created)
- `pipeline/src/pocpod0_pipeline/generate_scenarios.py` (created)
- `pipeline/src/pocpod0_pipeline/generate_troll_load.py` (created)
- `pipeline/src/pocpod0_pipeline/oslo_mapper.py` (created)
- `pipeline/src/pocpod0_pipeline/ingest.py` (created)
- `pipeline/tests/test_generate_scenarios.py` (created)
- `pipeline/tests/test_generate_troll_load.py` (created)
- `pipeline/tests/test_oslo_mapper.py` (created)
- `pipeline/tests/test_ingest.py` (created)
- `scripts/run-pipeline.sh` (created)
- `data/synthetic/scenarios/ayoub.json` (generated — 110 statements)
- `data/synthetic/scenarios/claire-student-1.json` (generated — 33 statements)
- `data/synthetic/scenarios/claire-student-2.json` (generated — 51 statements)
- `data/synthetic/scenarios/fatima-child-1.json` (generated — 54 statements)
- `data/synthetic/scenarios/fatima-child-2.json` (generated — 55 statements)
- `data/synthetic/scenarios/scenarios-consolidated.json` (generated — 303 statements)
- `data/synthetic/troll-load/troll-load.json` (generated — 5000 statements)
- `data/synthetic/troll-load/troll-load-manifest.json` (generated)

## Handoff Notes

### What Worked
- Scenario generator (303 statements, seed=42) produces narrative-rich, demo-quality data covering all 5 persona journeys with cross-context patterns intact
- CSS auth pattern: `Authorization: WebID {provisioner_webid}` with success codes [200,201,204,205]
- Lossless strategy: `pocpod0:originalXapiJson` + `pocpod0:originalXapiStatementId` as RDF literals — simple and effective for FR10 round-trip
- Pod resource path convention: `{pod}/learning/{activity-type}/{uuid}.ttl`

### What Didn't Work
- `repo_root()` using `parents[4]` — one level too deep; correct is `parents[3]` (pipeline/src/pocpod0_pipeline/ → pipeline/ → pocpod0/)

### Gotchas
- **Troll load is NOT ingested into Pods.** Troll statements use synthetic WebIDs (e.g., `student-042`) that have no provisioned Pod. The ingest pipeline defaults to `data/synthetic/scenarios/` only. Troll load is stress data for permission/ACL validation in Story 2.7 — it is not Pod data.
- **Dataset size: the pipeline outputs 303 scenario statements, NOT 10K.** The xAPI profile (`pocpod0:volumeTargets.totalStatements: 10000`) is aspirational and irrelevant for POC. Do not assume 10K input when sizing Oxigraph load, test data, or performance expectations.
- Troll load (5K, in `data/synthetic/troll-load/`) is separate from scenarios and has no pod routing hint — it will need explicit mapping logic if ingested
- The OSLO ontology mapping is a POC approximation: actor→`oslo:Person`, object→`oslo:PublicService`, result→`oslo:Participation`. These are reasonable but not formally validated against OSLO spec — treat as working hypothesis

### Recommendations for Next Story (2.3 — Oxigraph Setup)
- **Expect ~303 Turtle files from scenario ingestion** (one per statement), not thousands
- Read Turtle from CSS Pods via HTTP GET with `Authorization: WebID` header
- Graph named by Pod resource URI — use `NAMED GRAPH` pattern in SPARQL queries
- `prov:wasDerivedFrom` triple in each graph points back to the CSS Pod source URL

### Corrections to Shared Understanding
- The 10K volume target in `pocpod0-xapi-profile.jsonld` (`pocpod0:volumeTargets`) is **not a POC requirement** — it was over-engineered. POC operates with 303 scenario statements. Any story referencing 10K input should be corrected before dev starts.
- OSLO/xAPI alignment is fog-of-war: the mapping is iteratively refined, not fully specified upfront. Story 2.3 and beyond should expect refinement, not a stable contract.

## Change Log

- 2026-03-20: Story 2.2 implemented — xAPI-OSLO RDF ingestion pipeline. New Python package modules: utils, generate_scenarios, generate_troll_load, oslo_mapper, ingest. 303 narrative scenario statements + 5K troll load statements generated. 47 unit tests all passing. scripts/run-pipeline.sh orchestrates full pipeline execution.
