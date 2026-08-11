# Sprint Change Proposal — Receipts Are Half a Loop: Consent as Request-and-Review

**Date:** 2026-08-11
**Author:** Developer (Amelia) with Nicolas
**Trigger:** Story 8.9 execution — a reframing Nicolas raised mid-spike, which the story did not anticipate and which is larger than the spike
**Scope classification:** **Moderate** — reframes an already-planned story (7.9), retires a stub, adds no epic
**MVP impact:** **None today** — nothing proposed here blocks the current critical path to "a second person onboards alone"
**Status:** Proposed, awaiting decision

---

## 1. Issue Summary

### What triggered this

Story 8.9 asked a narrow question — can the agent that writes read-receipts also rewrite them? — and answered it: yes it could, now it cannot, verified live. Path A shipped.

Mid-spike, asked whether RDF receipts bought anything over JSON, Nicolas reframed the question rather than answering it:

> The intent is to be able to understand, question the request and audit further uses of my data, being able to revoke anytime if I disagree. This audit aims to inform any decision on permission.
>
> Instead of me granting you access to something just in case, it would be people requesting access with critical justifications. Each request should answer who, what, why and what if not granted.

That is not a storage-format question. It says the receipt is **not a log** — it is the audit half of a loop whose other half does not exist:

```
  request (who / what / why / what-if-refused)
        |
        v
  you review, scope it, decide  ----->  grant
        ^                                 |
        |                                 v
   revoke decision  <-----  audit  <-----  receipts
```

Today pocpod0 ships the bottom-right arc and nothing else. Receipts accumulate, correctly located and now tamper-evident — and there is no artifact they refer back to, so no receipt can answer the question the reframing cares about: *"was this use consistent with what was asked for?"*

### Why it surfaced now and not earlier

Because 8.9 forced the question "what is a receipt *for*". While the journal was rewritable, the answer didn't matter much. Having made it trustworthy, the natural next question is what it is trustworthy *about* — and the honest answer is: that a read happened, and nothing else.

### What already exists — more than expected

This is not a greenfield proposal. **Story 5.5 already shipped the vocabulary**, and it answers Nicolas's four questions almost exactly:

| Nicolas's question | `poc:ConsentGrant` predicate (Story 5.5, shipped) |
|---|---|
| Who is asking? | `poc:requestedBy` |
| Why? | `poc:purpose` |
| What will they see? | `poc:scope` — and `poc:excluded`, what they will **not** see |
| What if I say no? | `poc:consequenceOfRefusal` |
| Can I take it back? | `poc:revokedAt` (tombstone), `poc:expiresAt` |

`architecture.md:383` and the Anagnorisis trust-architecture doc both carry it. `create_consent_grant(...)` exists and works.

**But it lives only in the pipeline.** It is Python, it serves the Epic 1–6 simulation, and the two systems people actually touch know nothing about it:

- The **MCP connector** grants are raw WAC ACLs. No grant URI, no purpose, no exclusions, nothing for a receipt to point at. Story 8.9 reserved an `underGrant` field in every receipt for exactly this — currently `null`.
- The **backoffice** "Requests" tab is a **hardcoded UI stub** (`backoffice/index.html:555`): fake seed data, never persisted, no intake. Known since Story 7.2 and logged then as "a separate feature, not a 7.2 bug." It has been showing a promise it cannot keep ever since.

So the gap is not "build a consent model." It is **the model exists in the wrong process, and the UI that would collect requests is a lie.**

---

## 2. Impact Analysis

### On Story 7.9 (next on the critical path)

7.9 is the story that removes the operator from onboarding. Its scope already includes a grant table:

```
slug -> { credentialRef, webId, containers[], createdAt, expiresAt, lastUsedAt, revoked }
```

That shape is **credential bookkeeping**: which key, which containers, is it still live. Every field answers *what is technically permitted*. None answers *what it was permitted for* — no purpose, no exclusions, no consequence-of-refusal, no requester distinct from the credential holder.

This is the load-bearing observation of this proposal. **7.9 is about to build the grant table.** Adding a purpose/scope/justification dimension to a table being designed now is a design decision. Adding it to a table already in production, already minted against, is a migration. The window is open and closes when 7.9 ships.

The proposal is **not** to expand 7.9 into a consent-request system — that would blow the one story whose entire value is shortening the critical path. It is narrower: **7.9's grant table carries a `grantUri` and reserves the justification fields, even if nothing populates them yet.** Same reasoning Story 8.9 used for `underGrant`: the link between a use and its justification cannot be reconstructed later, and timestamp correlation is a guess.

### On the "Requests" tab

It should not survive this proposal in its current form. A stub that renders fake pending requests, on a page whose purpose is showing you who has access to your data, is worse than an empty state. Either it becomes real, or it is removed and replaced with an honest "not built yet."

Removing it is minutes. Recommended regardless of what else is decided here.

### On Epic 5's work

None. The pipeline keeps its own `create_consent_grant`. If the connector adopts the same vocabulary, the two converge for free — which is exactly what happened to receipt *shape* in Story 8.9, where `receipt.js` turned out to be the outlier against `receipt.py`'s one-resource-per-receipt convention. Worth checking for the same pattern before designing anything new here.

### On the honest-limits story

The consent loop **does not** fix the two limits Story 8.9 recorded, and any UI built on it must not imply otherwise:

- Receipts remain a **voluntary convention.** CSS surfaces no server-side read log. A reader that declines to write a receipt leaves no trace — a request-and-review flow makes the cooperative path richer, not enforced.
- A receipt records that a read **happened**, never what was done with the data afterwards. A purpose field records what someone *said* they would do. Neither observes what they did. **A consent loop that presents purpose as if it were compliance would be a downgrade in honesty from what ships today.**

There is also a real UX hazard: request-and-review adds an approval step to a system whose current selling point is that a newcomer can onboard alone. If every access needs a human decision, the second person's first experience becomes waiting on the first person. Any design must keep the preemptive-grant path available and make review the exception.

---

## 3. Recommended Path Forward

**Direct adjustment — no rollback, nothing to revert.** Everything proposed is additive, and the one deletion (the stub tab) removes a false promise.

### Now, inside Story 7.9 — small, and the window closes

1. **Grant table carries `grantUri`** plus reserved `purpose` / `scope` / `excluded` / `consequenceOfRefusal`, nullable. Cost: a few fields. Benefit: every grant minted from now on can be pointed at a justification, and every receipt written under it can name it.
2. **Delete or honestly empty the "Requests" tab.** It currently shows fabricated data.

### Next — a story of its own, not yet drafted

3. **`poc:ConsentGrant` in the connector.** Port the vocabulary from `create_consent_grant`, mint a grant resource at a dereferenceable URI alongside the WAC ACL, populate `underGrant` in receipts. This is where the loop actually closes: "show me every use of my data under this grant, next to what they promised to exclude" becomes answerable.
4. **Request intake.** The real one: a requester states who/what/why/what-if-refused; the owner reviews, narrows the scope (the requester usually has no idea which file they need), and approves or declines. Note the asymmetry Nicolas identified — the requester describes an *interest*, the owner translates it into a *scope*.

### Later — cheap once the above exists

5. **Consolidation job.** Nicolas's own suggestion: fold accumulated receipts weekly into whatever shape queries best — triples in the graph, SQLite, or one rolled-up document — and retire the individual resources. This is also the reason Story 8.9 chose JSON over RDF at write time: format is the reversible part.

### Explicitly not proposed

- Not an epic. Items 3–5 are one story each, and the sequencing above is deliberate.
- Not a change to the current MVP critical path. Item 1 is a field list inside a story already in flight; item 2 is a deletion.
- Not the detection half of the original 8.9 (anomaly signals, alerting, rate limiting). That stays in `post-poc-backlog.md`, and this proposal does not reopen it.

---

## 4. Decision Needed

1. **Approve item 1** — 7.9's grant table reserves the justification fields and a `grantUri`? *(Recommended: yes. It is the only time-sensitive item here.)*
2. **Approve item 2** — remove the fake "Requests" tab? *(Recommended: yes, independent of everything else.)*
3. **Items 3–5** — draft as stories now, or park until a second person's real data is on the system? *(No recommendation. It depends on whether the consent loop is a PoC demonstrator or post-PoC product, which is Nicolas's call, not a technical one.)*

---

## 5. References

- `_bmad-output/implementation-artifacts/8-9-access-journal-tamper-spike.md` — the spike this came out of; live evidence for the tamper property and its limits
- `_bmad-output/implementation-artifacts/5-5-consent-grant-as-rdf-resource.md` — `poc:ConsentGrant`, shipped, with all four question-predicates
- `_bmad-output/planning-artifacts/architecture.md:383` — the grant shape in the architecture doc
- `_bmad-output/planning-artifacts/anagnorisis-isabelle-trust-architecture.md:139` — "Consent as Architecture": the boolean ACL flag as a dereferenceable contract
- `backoffice/index.html:555` — the hardcoded "Requests" stub, flagged in Story 7.2
- `mcp-connector/src/receipt.js` — the reserved `underGrant` field and the three honest limits
