# Post-POC Backlog

Ideas captured during the POC that are worth pursuing after the current scope closes.

---

## Idea: Medical Silos Domain Variant

**Captured:** 2026-03-20
**Status:** backlog

### Concept

Apply the same pod sovereignty + data silo architecture to a healthcare domain instead of education. The structural problem is identical — fragmented siloed data across providers, no unified view, strict access rules — but the domain makes GDPR stakes and consent friction much more visceral.

### Stakeholder map (mirrors education personas)

| Healthcare | Education analog |
|---|---|
| Patient (child) | Learner |
| Physician (GP) | Teacher |
| Kinésithérapeute | Tutoring provider |
| Logopède | Extracurricular provider |
| Dentist | Another school |
| Health insurance | Policy/aggregate role (Isabelle) |
| Divorced parents | Split custody = split consent authority |

### Why this is interesting

- **Divorced parents** = perfect analog to NL/FR school split (Fatima's scenario). Each parent has partial consent authority. The pod sovereignty model must handle: which parent can grant access to which provider? Can the child's GP see data from the kine without parent B's consent?
- **Health insurance** aggregate queries = Isabelle's policy role but with GDPR Article 9 (special category data) — much harder access rules, much stronger demo of why the architecture matters.
- **Cross-silo hidden data**: child struggling at school but kine records show motor development issue — same cross-context insight problem as Claire/Alex, but with real privacy stakes.
- **Deletion cascade**: right-to-erasure request from patient = Ayoub's governance scenario, but healthcare retention rules add conflict (you can't always delete medical records).

### Reuse from POC

- Pod provisioning, ACL, CSS auth patterns: 100% reusable
- OSLO vocabulary: replace with HL7 FHIR or a Belgian health ontology
- xAPI → replace with FHIR resources or HL7 messages
- Ingestion pipeline, Oxigraph, Qdrant: reusable with schema swap
- All agent journeys (cross-context, aggregate, transfer, governance) map 1:1

### Notes

- Belgium has a strong eHealth platform context (eHealthBox, Vitalink, RSW) — real institutional silos to reference
- Could be a compelling follow-up grant application or demo for a health-sector audience
- Same codebase, different vocabulary schema contract (Story 2.1 equivalent = define FHIR/OSLO health schema contract)

---

## Improvement: Live progress indicator for long-running pipeline jobs

**Captured:** 2026-03-20
**Status:** backlog
**Target story:** 6.2 Mission Control Dashboard

### Problem

The embed pipeline (and load_graph) buffers all work before writing to the data store, making mid-run progress invisible. Specifically:

- `embed.py` generates all embeddings first, then batch-upserts to Qdrant at the end — Qdrant point count stays at 0 throughout the entire embedding phase
- `load_graph.py` loads resources one by one into Oxigraph — queryable mid-run but no counter surface
- Both are long-running black boxes from the dashboard's perspective

### Required change in embed.py

Move the `batch_upsert_points()` call inside the embedding loop — upsert each batch immediately after it's embedded, rather than buffering all vectors:

```python
# Current (buffered — dashboard-unfriendly):
for i in range(0, len(texts), batch_size):
    vectors = embedder.generate_embeddings(texts[i:i+batch_size])
    all_vectors.extend(vectors)
upserted = writer.batch_upsert_points(chunks, all_vectors)

# Target (streaming — live Qdrant counter):
for i in range(0, len(chunks), batch_size):
    batch_chunks = chunks[i:i+batch_size]
    vectors = embedder.generate_embeddings([c["text"] for c in batch_chunks])
    writer.batch_upsert_points(batch_chunks, vectors)
    # Dashboard can now poll: GET /collections/pocpod0_embeddings → points_count
```

### Dashboard probe

```bash
curl -s http://localhost:6333/collections/pocpod0_embeddings \
  | jq '.result.points_count'
# Returns live count during run; compare to total chunks_extracted from pipeline start log
```

### Notes

- Total chunks extracted is logged at pipeline start (`embed.extract` event) — dashboard can use that as the denominator
- Same pattern applies to load_graph: Oxigraph triple count is already queryable mid-run via SPARQL COUNT — just needs surfacing in the dashboard
- Matches the mission control UX note: "pipeline jobs are long-running black boxes; needs live progress indicators"
