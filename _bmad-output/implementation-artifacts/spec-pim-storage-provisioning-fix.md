---
title: 'Restore pim:storage auto-provisioning on pod creation'
type: 'bugfix'
created: '2026-08-29'
status: 'done'
context: []
baseline_commit: '49cd39b1ec6db5695d90e9b7967524da2f68238c'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** CSS's stock `create-pod.html.ejs` (v7) has a "Link to this storage from my WebID" checkbox that sends `settings.linkStorage: true`, which is what makes the server write a `pim:storage` triple into the new WebID profile. pocpod0's restyled override of that template (Story 7.2, commit `66af50b`, live since `7c2b0a1`) dropped the checkbox and its JS entirely while claiming "JS stays identical to stock" — so every pod created via the normal internal-WebID flow since then gets no `pim:storage` triple, breaking any app (e.g. solid-sport-tracker) that discovers the pod root the standard way.

**Approach:** Restore the checkbox markup + its form-submission JS into `infra/css/templates/identity/account/create-pod.html.ejs`, keeping the existing friendlier copy. Also fix a pre-existing (upstream) id mismatch in that JS (`linkStorageCheckbox` referenced but never defined — the real id is `linkStorage`) so the visibility-toggle handler doesn't throw when switching to "external WebID". Deploy to the VPS and live-verify with a real pod-creation round trip.

## Boundaries & Constraints

**Always:** Keep the checkbox checked by default (matches stock CSS behavior — internal-WebID pods get `pim:storage` unless the user unchecks it). Preserve all existing element ids/names the JS/e2e flow depends on (`mainForm`, `internalWebIdOn`, `name`, `webId`) except the one being fixed. Keep the friendlier copy text from Story 7.2 (pod/WebID glosses) — do not revert to stock's plainer wording.

**Ask First:** N/A — this is a scoped restoration of known-missing behavior, no open design decisions.

**Never:** Do not touch any other identity template (`main.html.ejs`, `consent.html.ejs`) or backend CSS config (`infra/css/config.json`) — the backend already passes `settings.linkStorage` through untouched (verified: CSS's `CreatePodHandler` yup schema does not strip unknown `settings` keys). Do not write a migration/backfill script for existing broken profiles — out of scope per explicit user decision, handled manually later.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Internal WebID, checkbox left checked (default) | POST to pod-create with `internalWebId=on`, `linkStorage=on` | New WebID profile includes `pim:storage <podRoot>` | N/A |
| Internal WebID, checkbox unchecked | POST with `internalWebId=on`, no `linkStorage` | New WebID profile has no `pim:storage` triple (explicit opt-out) | N/A |
| External WebID selected | POST with `internalWebId=''`, `webId=<uri>` | `settings.webId` sent, `linkStorage` never sent regardless of checkbox state (radio toggle forces it) | N/A |
| Toggle radio internal→external→internal in the UI | User clicks external, then back to internal | No uncaught JS exception; checkbox visibility and checked-state react correctly | Previously threw `TypeError` on `linkStorageCheckbox.checked` (undefined ref) |

</frozen-after-approval>

## Code Map

- `infra/css/templates/identity/account/create-pod.html.ejs` -- bind-mounted override of CSS's stock pod-creation form; missing the linkStorage checkbox + JS, root cause of the bug
- `docker-compose.yml` -- already bind-mounts this file into the CSS container (no change needed, just confirms deploy path)
- Makefile (`make vps-push` / `make vps-build` / `make vps-deploy`) -- deploy path to push the fix live to pod.nicolasdb.eu

## Tasks & Acceptance

**Execution:**
- [x] `infra/css/templates/identity/account/create-pod.html.ejs` -- restore the `linkStorageForm` checkbox block (checked by default) inside the internal-WebID radio option, restore the `else if (formData.get('linkStorage') === 'on') json.settings = { linkStorage: true }` branch, restore `updateLinkStorageVisibility()` + its change-event wiring -- this is the only mechanism that gets `pim:storage` written
- [x] same file -- fix `getElements('mainForm', 'internalWebIdOn', 'linkStorageCheckbox')` to request `'linkStorage'` (the actual element id) instead of the nonexistent `'linkStorageCheckbox'`, and update the destructured variable name/references accordingly -- prevents the latent TypeError on radio toggle
- [x] Deploy: run `make vps-push && make vps-build` + `docker compose up -d` (per `infra_vps_deploy` conventions) to push the fixed template live
- [x] (discovered during live-verify) VPS's `community-solid-server` image was created 2026-03-03 and its baked-in `card$.ttl.hbs` has no `{{#if linkStorage}}` clause at all -- `linkStorage` feature didn't exist in CSS yet at that build. `docker compose pull community-solid-server` on the VPS + `docker compose up -d` to recreate the container on a current `:7` image, then re-verify
- [x] Live-verify: created throwaway pod `verifypimstorage2` via the real API flow (internal WebID, `linkStorage:true`) -- `profile/card` confirmed contains `pim:storage <https://pod.nicolasdb.eu/verifypimstorage2/>`; account logged out (no HTTP delete path exists, per known CSS gap -- left orphaned same as prior throwaway/orphan accounts)

**Acceptance Criteria:**
- Given the deployed create-pod form with internal WebID selected and the checkbox left at its default checked state, when a pod is created, then the returned WebID profile document contains a `pim:storage <podRoot>` triple.
- Given the same form with the checkbox manually unchecked, when a pod is created, then no `pim:storage` triple is added (opt-out still works).
- Given the form loaded in a browser, when the user toggles the WebID radio from internal to external and back, then no uncaught JS exception occurs and the checkbox is visible/checked again.

## Spec Change Log

- 2026-08-29 (implementation, not a review loopback): live-verify against the deployed template fix alone still produced no `pim:storage` triple. Root cause traced further: VPS's `community-solid-server` container was running an image pulled once on 2026-03-03 and never refreshed (`docker-compose.yml` pins the moving tag `:7`, but no `vps-*` Makefile target ever runs `docker compose pull` on the VPS). That image's own baked-in `card$.ttl.hbs` had no `{{#if linkStorage}}` clause at all -- the feature didn't exist in CSS yet at that build. User approved (via AskUserQuestion) pulling a fresh `:7` image and recreating the container as part of this task's scope. Done; live-verified working. KEEP: the frontend checkbox/JS fix was still correct and necessary, just not sufficient on its own -- both fixes are required together.
- Follow-up not in this task's scope: no `vps-pull` Makefile target exists to refresh third-party images (community-server, oxigraph, qdrant) on the VPS -- worth its own story so this class of staleness doesn't recur.

## Design Notes

Reference for the exact restored block (from stock CSS v7 image `solidproject/community-server:7`, confirmed via `podman run --rm --entrypoint cat ... create-pod.html.ejs`):

```html
<ol id="linkStorageForm">
  <li class="checkbox">
    <label>
      <input type="checkbox" id="linkStorage" name="linkStorage" checked>
      Link to this storage from my WebID.
      <p class="checkbox-explanation">This adds a <code>pim:storage</code> triple to the WebID document...</p>
    </label>
  </li>
</ol>
```
JS: `const { mainForm, internalWebIdOn, linkStorage } = getElements('mainForm', 'internalWebIdOn', 'linkStorage');` then use `linkStorage.checked = false` in place of the old `linkStorageCheckbox` reference.

## Verification

**Commands:**
- `podman run --rm --entrypoint cat docker.io/solidproject/community-server:7 /community-server/templates/identity/account/create-pod.html.ejs` -- expected: reference copy of stock checkbox/JS block to diff against the restored file
- `make vps-deploy` (or equivalent per `infra_vps_deploy.md`) -- expected: CSS container restarts cleanly, no errors in logs

**Manual checks (if no CLI):**
- `curl -s https://pod.nicolasdb.eu/<throwaway-pod>/profile/card` after a fresh pod creation -- expect `pim:storage` triple present
- Browser DevTools console during radio toggle -- expect no uncaught errors

## Suggested Review Order

**Submission logic (wires the checkbox to the server request)**

- The line that actually gets `pim:storage` written -- explicit opt-in sent only for internal-WebID pods.
  [`create-pod.html.ejs:104`](../../infra/css/templates/identity/account/create-pod.html.ejs#L104)

- Element refs fixed: was destructuring a nonexistent `linkStorageCheckbox` id, now matches the real `linkStorage` checkbox.
  [`create-pod.html.ejs:75`](../../infra/css/templates/identity/account/create-pod.html.ejs#L75)

**Visibility toggle (keeps checkbox in sync with WebID radio choice)**

- Hides/unchecks the storage-link checkbox when external WebID is chosen, since `linkStorage` is meaningless there.
  [`create-pod.html.ejs:85`](../../infra/css/templates/identity/account/create-pod.html.ejs#L85)

- Wired to the radio's `change` event so toggling `internalWebId` re-syncs the checkbox.
  [`create-pod.html.ejs:93`](../../infra/css/templates/identity/account/create-pod.html.ejs#L93)

**Markup (restored form control)**

- The checkbox itself, checked by default -- matches stock CSS's default opt-in behavior.
  [`create-pod.html.ejs:20`](../../infra/css/templates/identity/account/create-pod.html.ejs#L20)
