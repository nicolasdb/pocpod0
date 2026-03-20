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
