# Anagnorisis: Isabelle, Trust Architecture & Civic Data Sovereignty

**Captured:** 2026-03-24
**Context:** Party-mode deep dive on Story 3.6 (Isabelle — Evidence-Based Policy)
**Status:** Design principles + strategic findings — feeds Story 3.6 implementation, Epic 5 backlog, and grant strategy

---

> **IMPLEMENTATION STATUS — 2026-04-12**
>
> | Section | Status |
> |---------|--------|
> | §3 Bidirectional accountability (access receipts) | ✅ Implemented — Story 5.4 (`receipt.py`, BP-1) |
> | §4 Trust circle boundary / consent-as-RDF | ✅ Implemented — Story 5.1 (`acl-manage` skill, JSONL consent events) |
> | §4 Ephemeral double-aveugle tokens | ✅ Implemented — Story 5.6 (`generate_token`, Oxigraph token index, BP-5) |
> | §5 Tombstone revocation (temporal signal) | ✅ Implemented — Story 5.2 (deletion cascade, PRIV-1 fix) |
> | §7 Data audit findings (Story 3.6) | ✅ Resolved — Story 3.6 done, vocabulary mismatch fixed |
> | §8 Open decisions (data path A/B/C) | ✅ Resolved — Story 3.6 implementation chose path C (hybrid) |
> | §9 New stories → "Access Receipt Written to Pod" | ✅ Implemented — Story 5.4 |
> | §9 New stories → "Consent Grant as RDF Resource" | ✅ Implemented — Story 5.1 |
> | §9 Post-PoC: Immutable Aggregate via IPFS+IPLD | 📋 In post-poc-backlog.md |
> | §1 Isabelle's institutional reality | 🟢 Still live — demo narrative |
> | §2 EU pull / regulatory alignment | 🟢 Still live — funding pitch |
> | §6 5-star Linked Data evolution path | 🟢 Still live — pilot roadmap |
> | §10 Funding strategy + consortium | 🟢 Still live — see project_funding_strategy.md |
> | §11 The Inversion (demo pitch core) | 🟢 Still live — core funder narrative |

---

---

## 1. Isabelle's Institutional Reality (Validated)

### Who she is

Regional education policy advisor for Brussels-Capital Region. She funds cross-community extracurricular programs (robotics workshops, STEM initiatives, tutoring) that serve students from both NL (Vlaamse Gemeenschap) and FR (Fédération Wallonie-Bruxelles) school systems.

### The structural paradox

- **Education is a community competence**, not a regional one. Brussels-Capital has no jurisdiction over schools.
- **Isabelle signs the checks** but cannot access the data those checks buy. Her leverage is contractual (grant conventions with *rapportage* obligations), not jurisdictional.
- The leverage produces **paper, not data**. Program coordinators submit Word/PDF narrative reports with self-reported participant counts. The coordinator's livelihood depends on the grant renewal Isabelle decides.
- Neither community (VGC, COCOF) has obligation to share student outcome data with a regional entity. GDPR is invoked as the blocker, but the real firewall is **political**: sharing data is perceived as jurisdictional encroachment.

### The Kafka machine (structural, not incompetent)

> "The rules are working as intended — they just produce absurd outcomes for someone in Isabelle's position."

The parliament asks for "measurable impact." Programs submit headcounts. Isabelle writes reports from headcounts. Parliament approves renewal. Nobody knows if anyone learned anything. Isabelle knows this is theater but cannot break the loop because:

1. Filing a formal data-sharing request with both communities takes ~18 months + a bilateral agreement that doesn't exist.
2. Commissioning external evaluations costs as much as the program and takes 2 years.
3. Not renewing a program that serves vulnerable kids because she has no data is politically impossible.

### The pain point (emotional core)

> "I'm making decisions about children's lives with my eyes closed, and I've been told that's fine."

Isabelle's demo moment is not being impressed by numbers. It's being **relieved** — seeing aggregate impact data for the first time after years of epistemic blindness.

---

## 2. The EU Pull — Working For Us

### Regulatory alignment

The **EU Data Governance Act** (in force since Sept 2023) and the **European Education Area** initiative push toward exactly what this system demonstrates:

- Federated data access with consent-based disclosure
- Cross-border/cross-entity aggregation
- Provenance trails and data intermediary frameworks
- "Data altruism organization" — a legal form designed for this use case

Isabelle's frustration is Kafka **today**, but EU policy direction **tomorrow**. The system we're building is the infrastructure the DGA assumes exists but nobody has built for education yet.

### Strategic implication

The EU pull creates a wedge: institutions (communities) push **against** data sharing, but the EU pulls **toward** it. This means:

- **First-wave funders** should be entities aligned with the EU pull (Fondation Roi Baudouin, Erasmus+, Interreg, Athumi)
- **Second-wave funders** are the institutions themselves — sell them the benefit of *protected* data sharing that preserves their sovereignty
- The PoC positions itself as **compliance-forward**, not as a Brussels workaround

---

## 3. Design Principle: Bidirectional Accountability

### The principle

> **"Every data flow that serves an institution must generate a readable receipt for the person whose data flowed."**

This is the anti-bossware guarantee. Tracking works in both directions:

- Isabelle sees aggregate impact → Ayoub sees a receipt of what Isabelle saw
- The troll audits both simultaneously
- Trust is not hope-based — it's **verifiable** (trustless)

### Trustless = mathematical, not reputational

- The `GROUP BY` in the SPARQL aggregate is **structural anonymization** — individual retrieval is impossible by query construction, not by policy promise
- Ayoub doesn't need to trust that Isabelle only sees counts. The math makes it so.
- But Ayoub currently has no way to see this proof. **That's the gap to fill.**

### GDPR as architecture (not compliance theater)

- Consent revocation = ACL grant removal → SPARQL filter automatically excludes → no admin action
- This is GDPR Article 7(3) (right to withdraw) implemented as architectural primitive
- "The math erased him. That's trustless."

---

## 4. The Trust Circle Boundary

### Concept

A **visual, auditable boundary** that the data subject themselves drew (via consent), showing exactly where their data becomes anonymous.

**Ayoub's view:**
> "Your robotics workshop attendance was part of an aggregate query by Isabelle (Brussels-Capital Policy Advisor) on March 15. She received: 32 students attended, 4 sessions. She did NOT receive: your name, your school, your score. Here is the exact boundary where your data was anonymized →"

### Properties

- **Inside the circle** = personal data, full detail, Ayoub's sovereign space
- **Outside the circle** = a number in a pile, structurally de-identified by GROUP BY
- The boundary is **drawn by Ayoub** (consent grant), not by the institution
- The boundary is **mathematically enforced** (SPARQL structure), not policy-enforced
- The boundary is **auditable** by the troll at any time

### The consent grant as RDF resource (John's 4 questions)

Every access request carries answers to:

1. **Who** is asking? (agent WebID + role)
2. **What** will they see? (and what they will NOT see)
3. **Why** are they asking? (purpose, linked to grant convention or mandate)
4. **What happens if you say no?** (consequence of refusal)

```turtle
<consent-grant-uri> a poc:ConsentGrant ;
  poc:requestedBy <isabelle-webid> ;
  poc:purpose "Justify funding renewal for robotics program to Brussels-Capital parliament" ;
  poc:scope "Aggregate participant count, avg session attendance, community distribution" ;
  poc:excluded "Individual names, scores, school identifiers, addresses" ;
  poc:consequenceOfRefusal "Your data excluded from aggregate; funding decision made on remaining N-1" ;
  poc:grantedAt "2026-03-24T..."^^xsd:dateTime ;
  poc:revokedAt ""^^xsd:dateTime ;     # tombstone — filled on revocation
  poc:expiresAt "2026-09-01T..."^^xsd:dateTime .
```

The troll can dereference `poc:purpose` to answer Ayoub's "why does Isabelle have my data?"

---

## 5. Temporal Signal — Liquid Democracy in the Pipes

### Tombstone approach (agreed for PoC)

When Ayoub revokes `regional-access` consent:
- His named graphs get flagged `consent-revoked` (not deleted — preserves historical provenance)
- Next aggregate query: SPARQL filter excludes him → count drops from 32 to 31
- No admin action. The math adjusts.
- Historical aggregates remain immutable — they record what was true *at the time*

### The civic signal

If consent revocations spike suddenly in one territory, the aggregate pipeline goes dry. Isabelle sees the trend: participation dropping without program changes. **That's a signal of distrust** — not a data quality problem.

This is **liquid democracy at the data layer**: continuous preference expression through data sovereignty choices. Not voting. Not consultation. A 16-year-old changing his mind, and the system reflecting it instantly.

### Immutable aggregate publication

Once data crosses the trust circle boundary outward and is anonymized:
- It becomes a **public good**, not personal data
- Should be published as **immutable, content-addressed, append-only** records
- Protocol: **IPFS + IPLD** (preferred — RDF-compatible via JSON-LD, Merkle DAG integrity, content-addressable, cryptographic verification of triples)
- Nobody can retroactively inflate the participant count in the Word document, because the Word document is replaced by a hash

---

## 6. 5-Star Linked Data Evolution Path

### PoC (now): simulated URIs in isolation

- Named graph URIs are `http://localhost:3000/ayoub/...` — local, not dereferenceable
- ACL checks are HEAD requests against local CSS
- Consent is a boolean ACL flag, no metadata

### Pilot (next): real URIs on real domains

- Pod URIs become dereferenceable on Eduvik or partner domains
- ACL inheritance chain is **walkable by any RDF client**: GET pod URI → ACL doc → agent WebID → role → consent scope
- Consent grant becomes a dereferenceable RDF resource (the 4-question template above)
- External auditors can verify the consent chain independently — 5-star trust
- IPLD makes RDF content-addressable with cryptographic verification of triples

### Bridge: IPLD + Solid compatibility

IPLD is designed for structured data using Merkle DAGs — inherently compatible with RDF's graph model. The convergence:
- IPLD supports JSON-LD (key RDF serialization) → semantic data stored and traversed with integrity
- Solid provides data ownership + interoperability via Linked Data
- IPLD provides immutable, verifiable storage for RDF graphs
- Together: decentralized pods with cryptographically verified, content-addressed aggregate publications

---

## 7. Data Audit Findings — Story 3.6 Implementation

### What exists in Oxigraph (actual state)

| What | Status |
|---|---|
| Vocabulary | `poc-pod0.edu/vocab/*` — NOT oslo-educ |
| Robotics attendance | 58 records (ayoub, fatima-child-1, fatima-child-2) |
| Scores on robotics | **None** — all `attended`, no `scaledScore` |
| `ext-language-context` NL/FR | Exists on many records, NOT on robotics records |
| `ext-funding: gemeente-stem-program` | Predicate exists, **0 records** carry this value |
| `ext-consent-type` | Only value is `parental-opt-in` (no `regional-access`) |
| Cross-community pods | Yes — school-nl.edu, school-fr.edu, gemeente.brussels sources |

### What the aggregate-anonymized.rq template expects vs. reality

| Template uses | Actual data uses |
|---|---|
| `oslo-educ:programma` | `poc-pod0:object` (URI-based, not program entity) |
| `oslo-educ:betreft` | `poc-pod0:verb` + `poc-pod0:object` |
| `oslo-educ:score` | `poc-pod0:scaledScore` |
| `$community_uri` (single graph) | Multiple named graphs per pod (one per resource) |
| GROUP BY with AVG(score) | No scores exist for robotics → AVG returns NULL |

### The "before" data as narrative asset

The missing scores ARE Isabelle's present reality. The PoC data already demonstrates what she has today: headcounts only. The "measurable impact" is the aspirational state the system enables. Implementation decision on data path pending (see §8).

---

## 8. Open Decisions for Story 3.6 Implementation

### Data path options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Fix the data** | Add ext-funding, ext-language-context to robotics records + add pre/post score fixtures | Honest demo of full capability | Touches ingest pipeline |
| **B: Redesign query** | Use what exists — attendance aggregation only | Fast, no pipeline changes | Weaker "measurable impact" demo |
| **C: Hybrid** | Fix vocabulary mismatch in template + add minimal score fixtures to 2-3 pods | Best demo value, scope-limited | Some synthetic data needed |

**Decision pending** — Nicolas to choose path.

---

## 9. New Stories Identified

### Epic 5 — New story: "Access Receipt Written to Pod"

Every query execution generates a turtle receipt stored at the data subject's pod:
- Location: `/ayoub/access-log/[timestamp].ttl`
- Contains: who queried, when, what shape of data was returned, which consent grant authorized it
- Troll indexes this for audit queries
- Ayoub owns the receipt — it's in his pod, not in a platform log

### Epic 5 — New story: "Consent Grant as RDF Resource"

The boolean ACL flag evolves into a dereferenceable URI carrying the 4-question consent contract (who, what, why, consequence-of-refusal). The troll can answer "why does X have access to my data?" by dereferencing the consent grant.

### Post-PoC backlog: "Immutable Aggregate Publication via IPFS+IPLD"

Aggregated, anonymized results published as content-addressed, append-only RDF on IPFS. Historical integrity guaranteed by Merkle DAG. No retroactive editing of aggregate records.

---

## 10. Funding Strategy — Consortium & Timeline

### The consortium

| Entity | Role |
|---|---|
| **Syntonie** (head) | Theory, values, neurodiversity lens |
| **OpenFab** (hand) | Making, prototyping, hardware/Arduino |
| **Politype** (heart, being born) | Digital democracy prototyping, game-based governance |
| **Firo Facilitation** | Process expertise, facilitation methodology |
| **DémocratieXXL** | Scale, democratic legitimacy, civic relationships |

PocPod0 is the **infrastructure layer** underneath Politype. The civic tech framing bridges data sovereignty → participatory democracy → game-based governance.

### Timeline

| When | Target | Ask |
|---|---|---|
| **Q2 2026** | Fondation Roi Baudouin | Civic tech + social cohesion. Small, fast, builds Belgian credibility |
| **Q3-Q4 2026** | Athumi + Eduvik | Paid pilot — Flemish data utility mandate + education partner |
| **2027 H1** | KA210 Erasmus+ (YOUTH) | Neurodiversity + citizen sensing + plurality. October 2026 call |
| **2027 H2** | Interreg NWE/Europe | Cross-border scale. Backed by FRB + Athumi + KA210 results |
| **2028** | EU DGA registration | Data altruism organization — the institutional endgame form |

### Key framing

> "We're building the infrastructure the EU Data Governance Act assumes exists but nobody has built for education yet."

For Wave 1 (funders aligned with EU pull): sell the vision.
For Wave 2 (institutions): sell the benefit — protected data sharing that preserves their sovereignty, not a land-grab.

---

## 11. The Inversion (Demo Pitch Core)

We started with: "Isabelle can't get data because of institutional complexity."

We arrived at: **a system where a 16-year-old in Molenbeek has more legible control over his civic data footprint than most governments have over their own citizens' data.**

That inversion is the pitch. Not the technology. Not the compliance. The inversion.

- Ayoub can ask "who has my data and why?" → machine-readable, human-legible answer
- Isabelle can ask "did this program work?" → evidence she can show to parliament
- The troll audits both simultaneously
- The tombstone ensures historical integrity
- The aggregates are immutable public goods
- If Ayoub withdraws consent, the aggregate adjusts instantly — no admin, no ticket, no 18-month bilateral agreement

**This is what participatory digital democracy infrastructure looks like at the data layer.** Not a voting app. Not a consultation platform. The layer *beneath* all of those that makes them trustworthy.
