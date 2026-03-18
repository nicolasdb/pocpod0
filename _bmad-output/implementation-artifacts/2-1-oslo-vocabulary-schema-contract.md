# Story 2.1: OSLO Vocabulary Schema Contract

Status: ready-for-dev

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
- [ ] Review OSLO education vocabulary at `https://data.vlaanderen.be/ns/onderwijs`
- [ ] Review OSLO person vocabulary at `https://data.vlaanderen.be/ns/persoon`
- [ ] Identify the specific OSLO classes that map to xAPI Actor, Verb, Object, Result, Context
- [ ] Document the mapping decisions (which OSLO class for each xAPI concept)

### Task 2: Create `oslo-education.ttl` (AC1, AC2)
- [ ] Define namespace prefixes: `oslo-educ:`, `xapi:`, `pocpod0:`, standard prefixes (`rdf:`, `rdfs:`, `owl:`, `skos:`)
- [ ] Map xAPI Verb to OSLO education activity types (e.g., `xapi:attempted` -> `oslo-educ:Evaluatie`)
- [ ] Map xAPI Object to OSLO education resources (courses, assessments, learning materials)
- [ ] Map xAPI Result to OSLO evaluation/result classes
- [ ] Map xAPI Context to OSLO education context (school, class group, program)
- [ ] Include `rdfs:label` and `rdfs:comment` on all classes and properties for discoverability

### Task 3: Create `oslo-person.ttl` (AC1, AC2)
- [ ] Map xAPI Actor to OSLO person classes (student, teacher, parent, administrator, regional advisor)
- [ ] Define role-based person subtypes relevant to the 5 personas
- [ ] Map xAPI Agent properties (name, mbox, account) to OSLO person properties
- [ ] Include all 5 persona roles: student (Ayoub), tutor (Claire), parent (Fatima), admin (Marc), regional (Isabelle)

### Task 4: Create `xapi-to-oslo.ttl` (AC1, AC2)
- [ ] Define mapping rules as RDF triples (e.g., using `owl:equivalentClass`, `rdfs:subClassOf`, or custom mapping predicates)
- [ ] Map the complete xAPI statement structure:
  - `xapi:actor` -> `oslo-person:` classes
  - `xapi:verb` -> `oslo-educ:` activity types
  - `xapi:object` -> `oslo-educ:` learning resources
  - `xapi:result` -> `oslo-educ:` evaluation results
  - `xapi:context` -> `oslo-educ:` institutional context
- [ ] Ensure mapping preserves all xAPI data (lossless: original xAPI fields must be recoverable)
- [ ] Include provenance predicates (`prov:wasDerivedFrom`) in the mapping schema

### Task 5: Create `pocpod0-vocab.ttl` (AC1, AC2)
- [ ] Define project-specific classes not covered by OSLO (e.g., `pocpod0:TutoringSession`, `pocpod0:SelfStudyActivity`, `pocpod0:RoboticsWorkshop`)
- [ ] Define project-specific properties (e.g., `pocpod0:deletedAt` for soft-delete, `pocpod0:communityLanguage` for NL/FR)
- [ ] Define provenance-related properties if not fully covered by PROV-O
- [ ] Ensure all custom classes/properties have `rdfs:label`, `rdfs:comment`, and proper domain/range

### Task 6: Validate schema in Oxigraph (AC3)
- [ ] Start Oxigraph container (`oxigraph/oxigraph:0.5.6`, port 7878)
- [ ] Load all 4 Turtle files into Oxigraph via SPARQL endpoint (HTTP POST)
- [ ] Run validation SPARQL queries:
  - Query all classes: `SELECT ?class WHERE { ?class a owl:Class . }`
  - Query all mappings: `SELECT ?xapi ?oslo WHERE { ?xapi owl:equivalentClass ?oslo . }`
  - Query by namespace: `SELECT ?s ?p ?o WHERE { ?s ?p ?o . FILTER(STRSTARTS(STR(?s), "https://data.vlaanderen.be/")) }`
- [ ] Verify no parse errors, no missing references
- [ ] Write at least 3 sample SPARQL queries that agents would use, using `?camelCase` variable naming:
  - `?studentName`, `?learningContext`, `?assessmentResult`, `?activityType`

### Task 7: Create unit tests (AC3)
- [ ] Create `tests/pipeline/test_oslo_schema.py`
- [ ] Test: all 4 Turtle files parse without errors (use `rdflib`)
- [ ] Test: required namespace prefixes are defined
- [ ] Test: all xAPI components have at least one OSLO mapping
- [ ] Test: all custom `pocpod0:` classes have `rdfs:label`

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
### Debug Log References
### Completion Notes List
### File List
