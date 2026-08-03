# Story 7.7: Delete My Pod — Owner-Driven Removal with Ceremony

Status: merged-into-7-10

> **SUPERSEDED 2026-08-03** — merged into **Story 7.10: Account & Pod Lifecycle**
> (`sprint-change-proposal-2026-08-03.md`, approved by Nicolas).
>
> Create-pod and delete-pod are the same reversibility problem inverted: same
> `RealBackend` methods, same screen, same ceremony design language. Splitting them
> split one design conversation across two review cycles.
>
> **No scope was dropped.** Everything below carries into 7.10 — the recursive-delete
> ceremony, the "confirmation shows what is about to be destroyed, not just a name"
> requirement, and the no-HTTP-delete-path / orphan-accumulation context.
>
> This file is kept as the source of that detail when 7.10 is drafted. **Do not
> implement it directly.**

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As **a pod owner**,
I want to delete a pod I created — with enough friction that I cannot do it by accident,
so that the stuff I make while testing or exploring is mine to remove, instead of accumulating forever on the server.

## Context / Why now

This gap keeps surfacing and keeps being deferred. It has now been hit by four separate stories:

- **7.1** — 17 orphan CSS accounts found on the VPS; no cleanup path existed, logged to `deferred-work.md`.
- **7.3 / 7.4** — throwaway test accounts created for live verification; credentials revocable, account shells not.
- **7.6** — still documents "the throwaway account itself can't be HTTP-deleted (known CSS limitation)".
- **8.3** — needs a throwaway identity to prove endpoint isolation, and will leave another shell behind.

A live inventory on 2026-07-31 found **29 account records**, up from the 17 recorded in 7.1 — Story 7.1's own e2e runs added ~12. The gap is not static; it widens every time we verify something against the live server. Nicolas raised it directly: *"I'm testing multiple pods, and I should be able to delete stuff I create, with caution of course."*

**Sovereignty framing, not just housekeeping.** This project's whole thesis is that people control their own data. A pod you can create but never delete is a contradiction of that thesis, and "delete my data" is the most basic sovereignty operation there is. That makes this a product feature, not a maintenance chore.

**The ceremony matters as much as the delete.** Story 7.3 established two-tap delete for files and a root-`Control` self-lockout guard, and Story 7.1's security incident showed how fast an unguarded destructive call becomes irreversible (a malformed request silently claimed the site root; no backup existed). Deleting a whole pod is the most destructive action the backoffice can offer — it earns proportionally more friction than a file delete, not the same amount.

## Acceptance Criteria

1. **Owner can delete their own pod's contents** from the backoffice: an authenticated recursive delete of every resource in the pod, with the owner's own session — no admin credential, no server-side privilege.
2. **Ceremony proportional to the blast radius:** deletion requires an explicit, non-accidental confirmation that is *stronger* than 7.3's two-tap file delete — the owner must type the pod name (or equivalent deliberate act), see an exact count of what will be destroyed, and be told plainly that it is irreversible. A misclick, a double-tap, or a stray Enter must not be able to trigger it.
3. **Honest about what actually gets removed:** the UI must state clearly what deletion does and does not do. Pod *contents* are removed over HTTP; the **CSS account shell and its record cannot be deleted over HTTP** (`DELETE /.account/account/{id}/` → 404, `DELETE .../pod/{id}/` → 400 on account API v0.5 — re-verified 2026-07-31). Do not imply a completeness the implementation cannot deliver. Silent partial deletion presented as full deletion is worse than an honest limitation.
4. **Graceful partial failure:** if some resources fail to delete (permission, in-use, network), the operation reports exactly which ones and leaves the pod in a describable state — never a silent half-delete claiming success. Follow 7.3's per-item failure discipline and `feedback_graceful_failure_design` (error states determine trust).
5. **Self-lockout guard preserved:** deletion must not strip the root `.acl` in a way that leaves the owner unable to act on what remains. 7.3's root-`Control` guard applies here — the root `.acl` is the single inheritance anchor and losing `Control` on it is a potential irreversible lockout.
6. **Backup prompt before destruction:** the owner is offered the Story 7.5 export path *before* confirming, so "download your pod, then delete it" is one coherent flow rather than two unrelated features. If 7.5 has not shipped when this is built, link to `make vps-backup` guidance instead and note the dependency.
7. **Operator-side full removal documented (not necessarily built):** since the account shell survives, document the operator procedure for genuine full removal — a script running inside the CSS container using its own `AccountStore` cascade — and decide explicitly whether to build it now or defer. Record the decision either way.
8. **WCAG 2.1 AA** (4.5:1 contrast, focus-visible, no color-only signalling) — same bar as every Epic 7 story. Destructive confirmation must be reachable and comprehensible by keyboard and screen reader.
9. **Verified live against a throwaway pod**, not only in the demo backend: create a throwaway account + pod, populate it, delete it through the real UI path, and confirm the contents are actually gone with an independent authenticated request. Reuse 7.3's DPoP verification harness rather than writing a new one.

## Tasks / Subtasks

- [ ] Task 1: Confirm the real deletion surface (AC: #1, #3)
  - [ ] 1.1 Re-verify against live CSS v0.5 what an owner can actually delete over HTTP: recursive resource delete, container delete, root container behavior. Record the true limits **before** designing the UI, so the copy matches reality.
  - [ ] 1.2 Confirm the account/pod delete endpoints are still absent (they were on 2026-07-31). If CSS has since gained them, that changes this story's shape — re-scope rather than proceeding on a stale assumption.
- [ ] Task 2: Deletion engine (AC: #1, #4, #5)
  - [ ] 2.1 **Reuse 7.3's recursive delete** in `backoffice/pod-api.js` — it already handles depth-tracked traversal and per-item failure. Generalize it to a whole-pod scope; do not write a second traversal.
  - [ ] 2.2 Preserve the root-`Control` self-lockout guard; add a pre-flight count of resources to be destroyed (feeds AC2's confirmation).
  - [ ] 2.3 Per-item failure aggregation with an explicit report; no success claim on partial completion.
- [ ] Task 3: Ceremony UI (AC: #2, #6, #8)
  - [ ] 3.1 Confirmation requiring a deliberate act (type the pod name), showing the resource count and an unambiguous irreversibility statement.
  - [ ] 3.2 Offer the export/backup path before the confirm step (AC6).
  - [ ] 3.3 WCAG 2.1 AA pass; destructive action clearly marked by more than color.
- [ ] Task 4: Honest limits + operator path (AC: #3, #7)
  - [ ] 4.1 UI copy stating exactly what survives deletion and why.
  - [ ] 4.2 Document the operator-side `AccountStore` cascade procedure; decide build-now vs defer and record the decision with its reason.
- [ ] Task 5: Live verification (AC: #9)
  - [ ] 5.1 Throwaway account + pod, populated, deleted through the real path, independently confirmed empty. Reuse 7.3's DPoP harness.
  - [ ] 5.2 **Run `make vps-backup` before any live destructive testing** — 7.1's incident happened with no backup in existence. Non-negotiable.

## Dev Notes

### Invalidated Assumptions

- **Assumption:** there are 17 orphan accounts. → **Reality:** 29 account records as of 2026-07-31. The number grows with each e2e run; re-count with `ssh hetzner` → `docker exec community-solid-server sh -c "ls /data/.internal/accounts/data | wc -l"` rather than quoting any figure.
- **Assumption:** the 1355 pod folders under `/data` are orphan clutter to clean up. → **Reality:** they are overwhelmingly Epic 1–6 **pipeline simulation output** (`student-*` 323, `admin-*` 308, `teacher-*` 273, `parent-*` 191, `unknown-*` 119, `external-*` 119), largely with no account record. **This story must not touch them.** Its scope is owner-initiated deletion of a pod the owner chose, not a server-wide sweep.
- **Assumption:** the Story 7.1 root-ACL incident may still be live. → **Reality:** remediated — `/data/.acl` holds only the minimal `<#public>` `acl:Read` reconstruction. One account record still lists the site root as its `baseUrl`, but it carries no grant. Inert.
- **Assumption:** client-credentials deletion is the same problem as account deletion. → **Reality:** distinct. Credentials **are** HTTP-deletable (`DELETE {resource}` → 200, live-confirmed 7.4); accounts are not. Revoking credentials is already solved and is not what this story is about.

### Reuse map — do not reinvent

- `backoffice/pod-api.js` — recursive delete, hand-rolled `.acl` Turtle writer, depth-tracked parser, DPoP session handling. All from 7.3, all live-verified.
- 7.3's **two-tap delete** pattern is the baseline to *exceed*, not to copy — pod deletion needs stronger friction than file deletion.
- 7.3's **DPoP verification harness** (zero-dependency Node client-credentials session using webcrypto, no npm) is the live-test tool. Reuse it.
- Story 7.5's export flow is the backup half of AC6.
- `make vps-backup` + the installed nightly cron (`infra/vps/nightly-backup.sh`, 03:00 daily, 7-day retention) is the operator safety net.

### CSS facts that constrain this story (live-confirmed, do not re-derive)

- Account API version **0.5**; container `community-solid-server`, data at `/data`, accounts at `/data/.internal/accounts/data/` (one JSON per account holding password + pod + webIdLink + clientCredentials together, with separate index files pointing back).
- **No HTTP account/pod delete.** CSS's `controls.password.delete` deliberately refuses to remove an account's last login, specifically to prevent reaching the auto-cleanup-eligible zero-login state. Full removal requires CSS's internal `AccountStore.delete(type, id)` cascade, which is not exposed over HTTP.
- Empty `name` on pod create claims the **site root** — the 7.1 footgun. Any code path here that constructs pod URLs must pass an explicit slug and reject an empty one.
- This is **not** the same tool as Epic 5's `run_cascade(resource_uri, pod_name)`, which deletes a specific resource's content + ACL + triples + vectors across CSS/Oxigraph/Qdrant (GDPR content deletion). That operates on resources; this operates on a pod and CSS's own account bookkeeping. Do not conflate them, and do not wire this into `run_cascade`.

### Scope boundaries

- **Not** a server-wide orphan sweep. One pod, chosen by its owner, at a time.
- **Not** an admin console. No cross-account deletion, no operator UI.
- **Not** GDPR-workflow tooling (support flows, retention policy, audit trail of deletions) — that is a pilot/production concern.
- Cross-provider migration/rebinding remains Story 7.5's territory.

### Effort note

Lower than it looks: the recursive-delete engine, ACL guard, per-item failure reporting and DPoP test harness **all already exist** from 7.3. The genuinely new work is the ceremony UI, the pre-flight count, the honest-limits copy, and the live throwaway verification. The one real unknown is Task 1.1 — exactly how CSS behaves deleting a pod's root container — which is why it is sequenced first.

### Project Structure Notes

- Work lands in `backoffice/` (`pod-api.js`, `index.html`) — the same two files 7.3/7.4 touched. Bump the `pod-api.js` cache-buster on change.
- No new dependencies. Inrupt libs stay pinned (`authn-browser 2.3.0` / `solid-client 2.1.0`); the npm-latest majors are out of scope.
- Backoffice files are bind-mounted on the VPS — static-asset-only changes deploy via `rsync`, no rebuild. `config.json` changes need `docker compose up -d --force-recreate`.
- No automated test framework exists in `backoffice/` — verification is live-pod round-trips, per every Epic 7 story.

### References

- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — the recurring deletion gap, logged since 7.1
- [Source: _bmad-output/implementation-artifacts/7-3-my-things-crud-acl-fix.md] — recursive delete, root-Control guard, two-tap delete, DPoP harness
- [Source: _bmad-output/implementation-artifacts/7-4-apps-and-credentials.md] — credential revoke (solved; distinct from account delete)
- [Source: _bmad-output/implementation-artifacts/7-1-backoffice-deploy-real-account-registration.md] — orphan-account root cause, `.internal/accounts/` layout, root-ACL incident, backup gap
- [Source: _bmad-output/implementation-artifacts/7-5-export-backup-portability.md] — export flow feeding AC6

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
