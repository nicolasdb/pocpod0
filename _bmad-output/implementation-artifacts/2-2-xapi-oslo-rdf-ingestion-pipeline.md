# Story 2.2: xAPI-OSLO RDF Ingestion Pipeline

Status: ready-for-dev

## Story

As a **developer**,
I want a pipeline that generates synthetic xAPI statements and converts them to OSLO-mapped RDF triples stored as Turtle resources in learner Pods,
so that the three-layer data architecture has realistic learning data flowing through a lossless transformation pipeline.

## Acceptance Criteria

**AC1: Synthetic xAPI dataset generated**
Given the 5 learner personas (Ayoub, Claire's 2 students, Fatima's 2 children)
When the dataset generation script executes
Then ~10K xAPI statements are produced in `data/synthetic/`
And statements cover: course activities, assessments, tutoring sessions, self-study, extracurricular (robotics workshop), cross-institutional contexts

**AC2: Dataset covers all 5 persona scenarios**
Given the generated dataset
When analyzed for scenario coverage
Then data supports:
- Claire's cross-context query (struggling student with hidden tutoring progress)
- Fatima's multi-child unified view (two children, two schools, NL+FR)
- Marc's transfer scenario (student transferring NL->FR)
- Isabelle's aggregate policy query (STEM program impact across communities)
- Ayoub's full learning history for governance/deletion scenarios

**AC3: Dataset is valid xAPI**
Given the dataset
When validated against xAPI specification
Then all statements are valid xAPI JSON

**AC4: Pipeline converts xAPI to OSLO-mapped RDF**
Given the synthetic xAPI dataset and the OSLO schema contract (from story 2-1)
When the ingestion pipeline (`pipeline/src/pocpod0_pipeline/ingest.py`) processes the dataset
Then each xAPI statement is converted to OSLO-mapped RDF triples using the schema contract
And the resulting Turtle resources are stored in the appropriate learner Pod via CSS

**AC5: Pipeline uses log+continue error handling**
Given a pipeline run processing ~10K statements
When individual statements fail conversion
Then the failure is logged (structured JSON to stdout) and the pipeline continues
And a summary reports total processed, succeeded, and failed counts

**AC6: Conversion is lossless**
Given the pipeline has completed
When I inspect the Pod resources
Then each learner Pod contains Turtle resources representing their learning activities
And the conversion is lossless — original xAPI data is preserved within the RDF representation (enabling FR10 round-trip recovery)

## Tasks / Subtasks

### Task 1: Set up Python package structure (AC4)
- [ ] Create `pipeline/pyproject.toml` with project metadata, dependencies, and entry points
- [ ] Dependencies: `rdflib`, `requests`, `httpx` (for async CSS/Oxigraph access), `pydantic` (for xAPI validation)
- [ ] Build tool: use `uv` or `pip` compatible configuration
- [ ] Create `pipeline/src/pocpod0_pipeline/__init__.py`
- [ ] Create `pipeline/src/pocpod0_pipeline/utils.py` — shared utilities: structured JSON logging setup, config loading
- [ ] Set up virtual environment activation (always activate venv for Python commands)

### Task 2: Build synthetic xAPI dataset generator (AC1, AC2, AC3)
- [ ] Create `pipeline/src/pocpod0_pipeline/generate_dataset.py`
- [ ] Define the 5 personas and their learning contexts:
  - **Ayoub:** Full K-12 history — math courses, science labs, Khan Academy self-study, robotics workshop, assessments across NL school
  - **Claire-student-1:** Struggling in math at school, thriving in gemeente tutoring (geometric visualization approach), moderate self-study
  - **Claire-student-2:** Average student, some tutoring, standard course progression
  - **Fatima-child-1:** NL school, language arts + STEM activities, robotics workshop participant
  - **Fatima-child-2:** FR school, similar subjects, different activity providers
- [ ] Generate ~10K xAPI statements distributed across personas:
  - Course activities (attended, completed, progressed)
  - Assessments (scored, passed, failed) — ensure Claire-student-1 fails school math tests but excels in tutoring
  - Tutoring sessions (gemeente-funded, private)
  - Self-study (Khan Academy, online resources)
  - Extracurricular (robotics workshop with applied math exercises)
  - Cross-institutional contexts (NL and FR schools, community programs)
- [ ] Include timestamps spanning a realistic school semester (September-January)
- [ ] Output as JSON files in `data/synthetic/` — one file per persona or one consolidated file with clear persona separation
- [ ] Validate all generated statements against xAPI spec (actor + verb + object mandatory, valid verb IRIs)

### Task 3: Build xAPI-to-OSLO RDF converter (AC4, AC6)
- [ ] Create `pipeline/src/pocpod0_pipeline/oslo_mapper.py` — OSLO vocabulary mapping logic
- [ ] Load schema contract from `data/schemas/` (the 4 Turtle files from story 2-1)
- [ ] Implement conversion for each xAPI component:
  - `actor` -> OSLO person classes with role metadata
  - `verb` -> OSLO education activity types
  - `object` -> OSLO education resources (course, assessment, activity)
  - `result` -> OSLO evaluation results with scores
  - `context` -> OSLO institutional context with community language tags
- [ ] **Lossless conversion strategy:** Embed original xAPI JSON as a literal within the RDF representation (e.g., `pocpod0:originalXapi` property containing the serialized JSON string) so that round-trip recovery (FR10) is possible
- [ ] Generate unique URIs for each converted resource (e.g., `pocpod0:statement/{uuid}`)
- [ ] Add `prov:wasDerivedFrom` triple pointing to the Pod resource URI where the Turtle will be stored

### Task 4: Build ingestion pipeline — CSS Pod storage (AC4, AC5)
- [ ] Create `pipeline/src/pocpod0_pipeline/ingest.py` — main ingestion orchestrator
- [ ] Implement pipeline flow:
  1. Read synthetic xAPI statements from `data/synthetic/`
  2. For each statement, call `oslo_mapper.py` to convert to OSLO-mapped RDF
  3. Serialize as Turtle
  4. Store in the appropriate learner Pod via CSS HTTP API (PUT to `http://css:3000/{pod-name}/{resource-path}`)
- [ ] Implement log+continue error handling:
  - Wrap each statement processing in try/except
  - Log failures as structured JSON: `{"level": "ERROR", "event": "ingest.statement.failed", "details": {"statement_id": "...", "error": "..."}}`
  - Continue processing remaining statements
- [ ] Emit summary at end: `{"event": "ingest.run.complete", "details": {"total": N, "succeeded": M, "failed": K}}`
- [ ] Pod resource path convention: `{pod-name}/learning/{activity-type}/{statement-uuid}.ttl`

### Task 5: Create pipeline entry point script (AC4)
- [ ] Create CLI entry point in `pipeline/src/pocpod0_pipeline/ingest.py` (or `__main__.py`)
- [ ] Support command-line arguments: `--input-dir` (default: `data/synthetic/`), `--css-base-url` (default from env: `CSS_BASE_URL`)
- [ ] Create or update `scripts/run-pipeline.sh` to activate venv and run the pipeline

### Task 6: Write tests (AC1-AC6)
- [ ] Create `tests/pipeline/test_generate_dataset.py`:
  - Test: dataset generates correct number of statements (~10K)
  - Test: all 5 personas have statements
  - Test: scenario coverage — Claire's struggling student has both failing school scores and positive tutoring data
  - Test: all statements are valid xAPI JSON
- [ ] Create `tests/pipeline/test_ingest.py`:
  - Test: single xAPI statement converts to valid Turtle
  - Test: lossless conversion — original xAPI recoverable from Turtle
  - Test: log+continue — pipeline survives malformed input
  - Test: summary counts are accurate
- [ ] Create `tests/pipeline/test_oslo_mapper.py`:
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

The dataset must be carefully designed to support all 5 demo journeys. Key data points:

**Claire's scenario (cross-context insight):**
- Claire-student-1 (Ayoub is also this student in the demo) fails math assessments at school
- Same student excels in gemeente-funded tutoring (geometric visualization approach)
- Same student has Khan Academy self-study activity
- The hybrid query (SPARQL + vector) must be able to surface the tutoring insight that graph-only misses

**Fatima's scenario (multi-child view):**
- Fatima-child-1 attends NL school — language arts strong, STEM activities, robotics
- Fatima-child-2 attends FR school — similar subjects, different providers
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
- `pipeline/src/pocpod0_pipeline/generate_dataset.py`
- `pipeline/src/pocpod0_pipeline/utils.py`
- `tests/pipeline/test_generate_dataset.py`
- `tests/pipeline/test_ingest.py`
- `tests/pipeline/test_oslo_mapper.py`
- `tests/pipeline/conftest.py` (if not existing)

Directories to create (if not existing):
- `pipeline/src/pocpod0_pipeline/`
- `data/synthetic/`
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
### Debug Log References
### Completion Notes List
### File List
