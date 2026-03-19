# Story 2.1: OSLO Vocabulary Schema Contract

Status: done

## Story

As a **developer**,
I want a documented vocabulary schema mapping xAPI concepts to OSLO education classes,
so that the ingestion pipeline and agent query layer share a common semantic contract (the Phase 2-to-3 bridge).

## Acceptance Criteria

**AC1: Schema files exist with correct mappings**
Given the OSLO education vocabularies (data.vlaanderen.be) and xAPI statement structure
When the schema contract is defined
Then Turtle files exist in `data/schemas/` mapping xAPI Actor, Verb, Object, Result, Context to OSLO education classes
And the following files are created:
- `oslo-education.ttl` — Education domain mapping (courses, assessments, learning activities)
- `oslo-person.ttl` — Person domain mapping (students, teachers, parents, administrators)
- `xapi-to-oslo.ttl` — xAPI-to-OSLO mapping rules (how each xAPI component maps)
- `pocpod0-vocab.ttl` — Project-specific extensions (custom classes/properties not in OSLO)

**AC2: Namespace prefixes follow conventions**
Given the schema contract files
When a developer or agent reads them
Then namespace prefixes follow OSLO conventions:
- `oslo-educ:` — OSLO education vocabulary (prefix for `https://data.vlaanderen.be/ns/onderwijs#`)
- `oslo-person:` — OSLO person vocabulary (prefix for `https://data.vlaanderen.be/ns/persoon#`)
- `xapi:` — xAPI vocabulary namespace
- `pocpod0:` — Project-specific namespace for custom classes
And the mapping is sufficient to convert any xAPI statement in the synthetic dataset to OSLO-mapped RDF

**AC3: Schema validates in Oxigraph**
Given the schema contract
When loaded into Oxigraph
Then the schema validates without errors
And SPARQL queries using OSLO classes return correct results

## Tasks / Subtasks

### Task 1: Research OSLO education vocabulary (AC1, AC2)
- [x] Review OSLO education vocabulary at `https://data.vlaanderen.be/ns/onderwijs`
- [x] Review OSLO person vocabulary at `https://data.vlaanderen.be/ns/persoon`
- [x] Identify the specific OSLO classes that map to xAPI Actor, Verb, Object, Result, Context
- [x] Document the mapping decisions (which OSLO class for each xAPI concept)

### Task 2: Create `oslo-education.ttl` (AC1, AC2)
- [x] Define namespace prefixes: `oslo-educ:`, `xapi:`, `pocpod0:`, standard prefixes (`rdf:`, `rdfs:`, `owl:`, `skos:`)
- [x] Map xAPI Verb to OSLO education activity types (e.g., `xapi:attempted` -> `oslo-educ:Evaluatie`)
- [x] Map xAPI Object to OSLO education resources (courses, assessments, learning materials)
- [x] Map xAPI Result to OSLO evaluation/result classes
- [x] Map xAPI Context to OSLO education context (school, class group, program)
- [x] Include `rdfs:label` and `rdfs:comment` on all classes and properties for discoverability

### Task 3: Create `oslo-person.ttl` (AC1, AC2)
- [x] Map xAPI Actor to OSLO person classes (student, teacher, parent, administrator, regional advisor)
- [x] Define role-based person subtypes relevant to the 5 personas
- [x] Map xAPI Agent properties (name, mbox, account) to OSLO person properties
- [x] Include all 5 persona roles: student (Ayoub), tutor (Claire), parent (Fatima), admin (Marc), regional (Isabelle)

### Task 4: Create `xapi-to-oslo.ttl` (AC1, AC2)
- [x] Define mapping rules as RDF triples (e.g., using `owl:equivalentClass`, `rdfs:subClassOf`, or custom mapping predicates)
- [x] Map the complete xAPI statement structure:
  - `xapi:actor` -> `oslo-person:` classes
  - `xapi:verb` -> `oslo-educ:` activity types
  - `xapi:object` -> `oslo-educ:` learning resources
  - `xapi:result` -> `oslo-educ:` evaluation results
  - `xapi:context` -> `oslo-educ:` institutional context
- [x] Ensure mapping preserves all xAPI data (lossless: original xAPI fields must be recoverable)
- [x] Include provenance predicates (`prov:wasDerivedFrom`) in the mapping schema

### Task 5: Create `pocpod0-vocab.ttl` (AC1, AC2)
- [x] Define project-specific classes not covered by OSLO (e.g., `pocpod0:TutoringSession`, `pocpod0:SelfStudyActivity`, `pocpod0:RoboticsWorkshop`)
- [x] Define project-specific properties (e.g., `pocpod0:deletedAt` for soft-delete, `pocpod0:communityLanguage` for NL/FR)
- [x] Define provenance-related properties if not fully covered by PROV-O
- [x] Ensure all custom classes/properties have `rdfs:label`, `rdfs:comment`, and proper domain/range

### Task 6: Validate schema in Oxigraph (AC3)
- [x] Start Oxigraph container (`oxigraph/oxigraph:0.5.6`, port 7878)
- [x] Load all 4 Turtle files into Oxigraph via SPARQL endpoint (HTTP POST)
- [x] Run validation SPARQL queries:
  - Query all classes: `SELECT ?class WHERE { ?class a owl:Class . }`
  - Query all mappings: `SELECT ?xapi ?oslo WHERE { ?xapi owl:equivalentClass ?oslo . }`
  - Query by namespace: `SELECT ?s ?p ?o WHERE { ?s ?p ?o . FILTER(STRSTARTS(STR(?s), "https://data.vlaanderen.be/")) }`
- [x] Verify no parse errors, no missing references
- [x] Write at least 3 sample SPARQL queries that agents would use, using `?camelCase` variable naming:
  - `?studentName`, `?learningContext`, `?assessmentResult`, `?activityType`

### Task 7: Create unit tests (AC3)
- [x] Create `tests/pipeline/test_oslo_schema.py`
- [x] Test: all 4 Turtle files parse without errors (use `rdflib`)
- [x] Test: required namespace prefixes are defined
- [x] Test: all xAPI components have at least one OSLO mapping
- [x] Test: all custom `pocpod0:` classes have `rdfs:label`

## Dev Notes

### Architecture Context
- **Three-Layer Data Model:** Pod (CSS source of truth) -> Graph (Oxigraph queryable index) -> Vector (Qdrant semantic index)
- This schema contract is the **Phase 2-to-3 bridge**: agents in Phase 3 query OSLO classes, NOT xAPI fields directly
- The schema must support lossless conversion: original xAPI data preserved within RDF representation so FR10 (round-trip recovery) is achievable

### Technical Constraints
- **Oxigraph version:** 0.5.6 (image: `oxigraph/oxigraph:0.5.6`, port 7878)
- **RDF serialization:** Turtle (`.ttl`) as primary format
- **SPARQL variables:** Always `?camelCase` (e.g., `?studentName`, `?learningContext`)
- **Namespace prefixes:** `oslo-educ:`, `oslo-person:`, `xapi:`, `pocpod0:`
- **File naming:** lowercase, hyphen-separated: `oslo-education.ttl`, `oslo-person.ttl`, `xapi-to-oslo.ttl`, `pocpod0-vocab.ttl`
- **Python naming:** `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- **Provenance:** Every Oxigraph triple will include `prov:wasDerivedFrom <pod-resource-uri>` — schema must include PROV-O namespace

### OSLO Vocabulary References
- OSLO Education: `https://data.vlaanderen.be/ns/onderwijs`
- OSLO Person: `https://data.vlaanderen.be/ns/persoon`
- OSLO is the Flemish government open data standard — alignment with Athumi infrastructure is a strategic requirement

### xAPI Structure to Map
An xAPI statement has these top-level components:
```json
{
  "actor": { "name": "...", "mbox": "...", "account": {...} },
  "verb": { "id": "http://adlnet.gov/expapi/verbs/...", "display": {...} },
  "object": { "id": "...", "definition": { "type": "...", "name": {...} } },
  "result": { "score": {...}, "success": true/false, "completion": true/false },
  "context": { "contextActivities": {...}, "extensions": {...} },
  "timestamp": "ISO-8601"
}
```

### 5 Persona Scenarios the Schema Must Support
1. **Claire (teacher):** Cross-context student queries — school + tutoring + self-study activities
2. **Fatima (parent):** Multi-child view — two children, two schools (NL + FR), extracurricular
3. **Marc (admin):** Transfer scenario — student moving NL->FR school, full profile query
4. **Isabelle (regional):** Aggregate anonymized queries — STEM program impact across communities
5. **Ayoub (student):** Full learning history — courses, assessments, tutoring, robotics workshop, governance/deletion

### Isolation Notes
- Use `distrobox-host-exec` for accessing podman containers from within distrobox
- Oxigraph SPARQL endpoint accessible at `http://localhost:7878/query` (GET/POST) and `http://localhost:7878/store` (POST for data loading)

### Project Structure Notes

Files to create:
- `data/schemas/oslo-education.ttl`
- `data/schemas/oslo-person.ttl`
- `data/schemas/xapi-to-oslo.ttl`
- `data/schemas/pocpod0-vocab.ttl`
- `tests/pipeline/test_oslo_schema.py`
- `tests/pipeline/conftest.py` (if not already existing)

Directories to create (if not existing):
- `data/schemas/`
- `tests/pipeline/`

### References

- Epics doc: `_bmad-output/planning-artifacts/epics.md` — Story 2.1 acceptance criteria (line ~327-348)
- Architecture doc: `_bmad-output/planning-artifacts/architecture.md` — Decision DA-3 (OSLO Vocabulary Schema Contract), naming patterns, RDF/SPARQL naming conventions
- PRD: `_bmad-output/planning-artifacts/prd.md` — FR13, Technical Constraints (Committed Standards)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — story-2-1-oslo-vocabulary-schema-contract

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log References
- Oxigraph POST /store creates per-request named graphs (not default graph); SPARQL queries must use `GRAPH ?g { }` pattern. Validated with 467 triples across 4 named graphs.

### Completion Notes List
- AC1: All 4 Turtle files created in `data/schemas/` with correct mappings
- AC2: Namespace prefixes `oslo-educ:`, `oslo-person:`, `xapi:`, `pocpod0:` defined in all relevant files; all classes/properties have `rdfs:label` and `rdfs:comment`
- AC2: Mapping decisions — xAPI Actor → `oslo-person:GeregistreerdPersoon` (role subtypes via `pocpod0:*Actor` classes); xAPI Verb → `oslo-educ:Leeractiviteit` subtypes; xAPI Object → `oslo-educ:Leermiddel` and subclasses; xAPI Result → `oslo-educ:EvaluatieResultaat`; xAPI Context → `oslo-educ:OnderwijsInstelling`
- AC3: All 4 files loaded into Oxigraph (HTTP 201, 467 triples); 3 validation SPARQL queries return correct results (37 classes, 9 equivalentClass mappings, OSLO namespace triples)
- AC3: 23 unit tests all pass; tests cover parse, namespace prefixes, xAPI mappings, pocpod0 class labels
- Lossless round-trip: `pocpod0:originalXapiJson` and `pocpod0:originalXapiStatementId` properties preserve original xAPI for FR10 recovery
- 3 sample SPARQL queries with `?camelCase` variables documented in `xapi-to-oslo.ttl`

### File List
- `data/schemas/oslo-education.ttl` (created)
- `data/schemas/oslo-person.ttl` (created)
- `data/schemas/xapi-to-oslo.ttl` (created)
- `data/schemas/pocpod0-vocab.ttl` (created)
- `tests/pipeline/test_oslo_schema.py` (created)
- `tests/pipeline/conftest.py` (created)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (updated: in-progress → review)

## Change Log
- 2026-03-19: Story 2.1 implemented — OSLO vocabulary schema contract created (4 Turtle files, 467 triples, 23 tests passing)

## Handoff Notes

### What Worked
- OSLO class names mapped cleanly to xAPI components with no ambiguity
- rdflib parsed all 4 Turtle files cleanly on first attempt; 23 tests green immediately
- Oxigraph accepted all files via HTTP POST with no errors

### What Didn't Work
- Nothing significant failed

### Gotchas
- **Oxigraph named graphs:** `POST /store` creates one named graph per request (not the default graph). SPARQL queries must use `GRAPH ?g { }` pattern — plain `WHERE { ?s ?p ?o }` returns 0 results. This will affect every story that queries Oxigraph.

### Recommendations for Next Stories
- **2.2 (xAPI Ingestion — can run in parallel):** Import the 4 schema files in `data/schemas/` — don't redefine namespaces. Use `pocpod0:originalXapiJson` and `pocpod0:originalXapiStatementId` for lossless xAPI preservation.
- **2.3 (Oxigraph Storage — merge point for 2.1 + 2.2):** This story depends on both 2.1 schema contract AND 2.2 ingestion output. Start 2.3 only after both are done. The named graph pattern from this story applies directly — each Pod resource should be loaded into its own named graph for isolation.

### Corrections to Shared Understanding
- None — story matched expectations
