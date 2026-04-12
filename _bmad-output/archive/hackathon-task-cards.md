# pocpod0 Hackathon — Task Cards

_Each task is self-contained and shippable in ~3 hours. Pick one._

---

## Task A: Claire — Cross-Context Insight Discovery
**Story:** 3.3 | **Priority:** [must-ship] | **Difficulty:** Medium

### The Scenario
Claire is a secondary school teacher in Brussels with 120 students. Three students are failing math — but she can't see what happens outside her classroom. One attends tutoring, another does Khan Academy self-study, a third transferred mid-year. Claire needs to see the full picture.

### What You Build
1. **Agent config** (`agents/claire-teacher/agent.yaml`) — Claire's persona, ACL role (tutor), persona prompt
2. **SPARQL templates** — `student-progress.rq` and `cross-context-query.rq` in `agents/skills/sparql-query/templates/`
3. **Hybrid query demo** — Claire calls both SPARQL skill + Qdrant skill, merges results

### Acceptance Criteria
- [ ] Claire's agent queries "Which students are struggling with quadratic equations across all learning contexts?"
- [ ] Graph-only results return structured facts (grades, attendance, activities)
- [ ] Hybrid results add semantic insight (e.g., "tutoring notes show student grasps concept through geometric visualization")
- [ ] Results show side-by-side comparison (graph-only vs. hybrid)
- [ ] Provenance displayed: which triples, from which Pod resources
- [ ] Claire cannot see data from pods outside her ACL scope

### Files You Touch
```
agents/claire-teacher/agent.yaml          # CREATE
agents/skills/sparql-query/templates/     # ADD .rq files
```

### Reference
- Pod data: `ayoub`, `claire-student-1`, `claire-student-2` pods
- OSLO schema: `data/schemas/oslo-education.ttl`
- Existing skill: `agents/skills/sparql-query/skill.yaml` (read to understand interface)

---

## Task B: Fatima — Unified Parental View
**Story:** 3.4 | **Priority:** [target] | **Difficulty:** Medium

### The Scenario
Fatima has two children — one in a Flemish school, one in a French-speaking school. She juggles two platforms, gets report cards twice a year, and has no idea what the robotics workshop is actually teaching her kids. She wants one view, both children, all contexts.

### What You Build
1. **Agent config** (`agents/fatima-parent/agent.yaml`) — Fatima's persona, ACL role (parent), persona prompt
2. **SPARQL template** — `parental-view.rq` in `agents/skills/sparql-query/templates/`
3. **Multi-pod query** — Fatima queries both children's pods in a single request

### Acceptance Criteria
- [ ] Fatima's agent queries a unified view of both children
- [ ] Results combine data across NL and FR school contexts seamlessly via structured RDF
- [ ] Each child's progress is distinguishable within the unified view
- [ ] Provenance shows which Pod resources contributed
- [ ] Fatima cannot see data from pods outside her ACL scope (only her children's pods)

### Files You Touch
```
agents/fatima-parent/agent.yaml           # CREATE
agents/skills/sparql-query/templates/     # ADD parental-view.rq
```

### Reference
- Pod data: `fatima-child-1`, `fatima-child-2` pods
- ACL config: `infra/css/pods/fatima-child-*/` (read-only reference)

---

## Task C: Isabelle — Evidence-Based Policy
**Story:** 3.5 | **Priority:** [target] | **Difficulty:** Medium-Hard

### The Scenario
Isabelle is a regional education policy advisor in Brussels. Budget season: she needs to justify funding for after-school STEM programs. She currently receives PDF narratives with self-reported numbers. She needs aggregate, anonymized, cross-community evidence of program impact. This query is currently unanswerable by anyone in Belgium.

### What You Build
1. **Agent config** (`agents/isabelle-policy/agent.yaml`) — Isabelle's persona, ACL role (regional), persona prompt
2. **SPARQL template** — `aggregate-anonymized.rq` in `agents/skills/sparql-query/templates/`
3. **Anonymization enforcement** — Query returns aggregate data only, no individual student records

### Acceptance Criteria
- [ ] Isabelle's agent queries "What is the measurable impact of funded STEM programs on participating students?"
- [ ] Results return aggregate data across both NL and FR communities
- [ ] No individual student data exposed — results are anonymized at aggregate level
- [ ] Provenance shows: "derived from N triples across M student pods, all with active regional-access consent grants"
- [ ] Isabelle cannot query individual student records — aggregate-only access enforced

### Files You Touch
```
agents/isabelle-policy/agent.yaml         # CREATE
agents/skills/sparql-query/templates/     # ADD aggregate-anonymized.rq
```

### Reference
- ACL role: `regional` — aggregate read access across all pods
- Anonymization: handle in SPARQL (GROUP BY, COUNT, AVG — no individual identifiers in SELECT)

---

## Task D: Troll Hardening — Cross-Inference Attacks
**Story:** 3.6 | **Priority:** [must-ship] | **Difficulty:** Hard

### The Scenario
The troll agent tries to trick role agents into revealing data they shouldn't have access to. Can Claire be prompted to leak Isabelle's policy data? Can Fatima's agent be tricked into exposing data from children that aren't hers? This is adversarial creativity — your job is to find the cracks.

### What You Build
1. **Attack scripts** (`agents/troll-adversary/attacks/cross-inference.py`) — NL prompt attacks through the agent layer
2. **Attack diversity** — Try multiple strategies: direct questions, social engineering prompts, context manipulation, role confusion
3. **Structured logging** — Each probe logged with category, access path, result

### Acceptance Criteria
- [ ] Minimum 5 distinct cross-inference attack probes written
- [ ] Each probe targets a different agent (Claire, Fatima, Isabelle) with a different strategy
- [ ] Each probe logged as structured JSON: `{ "attack_category": "cross_inference", "access_path": "through_agent", "agent_tested": "...", "test_name": "...", "result": "pass|partial|fail", "details": "..." }`
- [ ] Results are flagged as probabilistic/non-deterministic (LLM-dependent)
- [ ] Partial/fail results documented honestly with risk assessment

### Files You Touch
```
agents/troll-adversary/attacks/cross-inference.py   # CREATE/EXTEND
```

### Reference
- Existing troll attacks: `agents/troll-adversary/attacks/` (ACL, injection, vector scripts for pattern reference)
- Troll report format: `agents/troll-adversary/report/template.md`

### Bonus Challenges
- Can you make an agent leak data from another agent's conversation?
- Can you construct a prompt that makes the SPARQL skill return results outside the agent's ACL scope?
- Can you extract individual student identifiers through Isabelle's aggregate-only access?

---

## Task E: Additional SPARQL Templates & Query Hardening
**Priority:** Bonus | **Difficulty:** Variable

### For Participants Who Finish Early or Want a Different Angle

Pick from:
1. **Transfer profile query** — Write `transfer-profile.rq` for Marc's transfer scenario (Story 4.1 prep)
2. **Edge-case SPARQL queries** — Queries that test the OSLO schema boundaries (missing data, cross-language, malformed URIs)
3. **Query performance profiling** — Run the existing queries at scale, identify slow patterns, suggest index optimizations for Oxigraph
4. **Additional troll attacks** — Extend `sparql-injection.py` or `vector-privacy.py` with new attack vectors

---

## How to Test Your Work

```bash
# Verify services are running
docker-compose ps

# Test a SPARQL query directly
curl -X POST http://localhost:7878/query \
  -H "Content-Type: application/sparql-query" \
  -d "SELECT * WHERE { ?s ?p ?o } LIMIT 10"

# Test Qdrant
curl http://localhost:6333/collections

# Run your agent (via OpenClaw)
# [instructions will be provided at the event based on OpenClaw CLI]
```

## Logging Format (Use This)

```json
{
  "timestamp": "ISO-8601",
  "service": "agent|troll",
  "level": "INFO|WARN|ERROR",
  "event": "query.executed|attack.probe|agent.response",
  "agent": "claire-teacher|troll-adversary|...",
  "duration_ms": 123,
  "details": {}
}
```
