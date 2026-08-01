/**
 * wacManager.js
 *
 * Read and modify Web Access Control (WAC) permissions on a Solid resource.
 *
 * IMPORTANT — WAC vs ACP: this module uses the WAC-specific API, which is
 * the mature/reliable path (@inrupt's newer "universal access" API that
 * auto-detects WAC/ACP has known bugs against WAC servers as of 2026 — see
 * references/architecture-and-checklist.md). Community Solid Server uses
 * WAC by default, so this is the right module for pod.nicolasdb.eu.
 *
 * Access modes are objects like:
 *   { read: true, write: false, append: false, control: false }
 *
 * SCOPE matters a lot for containers:
 *   'resource' — applies to that URL only (default).
 *   'default'  — applies to the container's children that have no ACL of
 *                their own (WAC inheritance).
 *   'both'     — the usual intent for "give the agent access to this folder
 *                and everything in it", done in a single ACL write.
 */

const {
  getSolidDatasetWithAcl,
  hasResourceAcl,
  hasFallbackAcl,
  hasAccessibleAcl,
  createAcl,
  createAclFromFallbackAcl,
  getResourceAcl,
  getAgentAccessAll,
  getAgentResourceAccess,
  setAgentResourceAccess,
  setAgentDefaultAccess,
  setPublicResourceAccess,
  setPublicDefaultAccess,
  saveAclFor,
} = require("@inrupt/solid-client");

/**
 * Fetches the resource together with its ACL, and returns a usable
 * (possibly newly-initialised) ACL dataset to modify.
 *
 * Throws if the calling agent lacks acl:Control here — which is correct:
 * an agent must not be able to grant itself rights it doesn't already hold.
 */
async function _getEditableAcl(resourceUrl, session) {
  const datasetWithAcl = await getSolidDatasetWithAcl(resourceUrl, {
    fetch: session.fetch,
  });

  let resourceAcl;
  if (!hasResourceAcl(datasetWithAcl)) {
    if (!hasAccessibleAcl(datasetWithAcl)) {
      const err = new Error(
        `${session.info.webId} does not have Control access to ${resourceUrl}, ` +
          "so it cannot change permissions here. This grant must be made by " +
          "the pod owner's WebID (see src/onboarding.js)."
      );
      // Story 8.5 Task 5: attach the real status so downstream consumers
      // classify by status code, not by matching "Control" in the text.
      err.statusCode = 403;
      throw err;
    }
    if (!hasFallbackAcl(datasetWithAcl)) {
      // No resource ACL and no readable fallback: initialise a fresh one.
      // Saving an ACL with nobody holding control:true permanently orphans
      // this resource — nobody, including the pod owner, could ever change
      // its permissions again. Always include the acting session's own
      // WebID with control:true in the same batch that creates a new ACL,
      // regardless of what the caller's own modes requested.
      resourceAcl = setAgentResourceAccess(createAcl(datasetWithAcl), session.info.webId, {
        read: true,
        write: true,
        append: true,
        control: true,
      });
    } else {
      resourceAcl = createAclFromFallbackAcl(datasetWithAcl);
    }
  } else {
    resourceAcl = getResourceAcl(datasetWithAcl);
  }

  return { datasetWithAcl, resourceAcl };
}

/**
 * Grant/adjust access for a specific agent (WebID) on a resource.
 * @param {string} resourceUrl
 * @param {string} agentWebId
 * @param {{read?:boolean, write?:boolean, append?:boolean, control?:boolean}} modes
 * @param {import('@inrupt/solid-client-authn-node').Session} session
 * @param {{scope?: 'resource'|'default'|'both'}} [options]
 */
async function grantAccess(resourceUrl, agentWebId, modes, session, options = {}) {
  const scope = options.scope || "resource";
  if (!["resource", "default", "both"].includes(scope)) {
    throw new Error(`Invalid scope "${scope}" — expected 'resource', 'default', or 'both'.`);
  }
  const { datasetWithAcl, resourceAcl } = await _getEditableAcl(resourceUrl, session);

  let updatedAcl = resourceAcl;
  if (scope === "resource" || scope === "both") {
    updatedAcl = setAgentResourceAccess(updatedAcl, agentWebId, modes);
  }
  if (scope === "default" || scope === "both") {
    updatedAcl = setAgentDefaultAccess(updatedAcl, agentWebId, modes);
  }

  return _saveAclOrThrowControlError(resourceUrl, datasetWithAcl, updatedAcl, session);
}

/**
 * `_getEditableAcl`'s hasAccessibleAcl/hasFallbackAcl checks are a heuristic
 * based on whether the ACL resource is discoverable, NOT whether this agent
 * actually has acl:Control there — CSS only tells the truth on the real PUT.
 * Story 8.1 AC4 (live verification) found that an agent with read/write but
 * no Control on a data-pod container passes those checks, builds a fresh ACL
 * Turtle client-side, and only 403s on saveAclFor — surfacing a raw Inrupt
 * "Storing the Resource ... failed: [403]" stack instead of the documented
 * "does not have Control access" message. Normalize that here.
 */
/**
 * Inrupt's FetchError doesn't reliably expose a `statusCode`/`status`
 * property, but it does embed the real HTTP status in its message (e.g.
 * "Storing the Resource at [...] failed: [403] ..." or "... failed: [501]
 * ..."). Extract it and attach it as `.statusCode` so every caller up the
 * chain — including mcp-server.js's toToolErrorResult (Story 8.5 Task 5)
 * — can classify by status code first instead of substring-matching
 * `err.message` for "control" / "501", which breaks silently the moment
 * the message wording changes upstream.
 */
function _normalizeFetchError(err) {
  if (!err || err.statusCode || err.status) return err;
  const messageStatus = String(err && err.message).match(/\[(\d{3})\]/)?.[1];
  if (messageStatus) {
    err.statusCode = Number(messageStatus);
  }
  return err;
}

async function _saveAclOrThrowControlError(resourceUrl, datasetWithAcl, updatedAcl, session) {
  try {
    return await saveAclFor(datasetWithAcl, updatedAcl, { fetch: session.fetch });
  } catch (e) {
    const normalized = _normalizeFetchError(e);
    if (normalized.statusCode === 403) {
      const controlError = new Error(
        `${session.info.webId} does not have Control access to ${resourceUrl}, ` +
          "so it cannot change permissions here. This grant must be made by " +
          "the pod owner's WebID (see src/onboarding.js)."
      );
      // Carry the real status forward (Story 8.5 Task 5) so
      // toToolErrorResult classifies this by status code, not by matching
      // the word "Control" in the message text.
      controlError.statusCode = 403;
      throw controlError;
    }
    throw normalized;
  }
}

/** Revoke all access for an agent (sets every mode false, resource + default). */
async function revokeAccess(resourceUrl, agentWebId, session, options = {}) {
  return grantAccess(
    resourceUrl,
    agentWebId,
    { read: false, write: false, append: false, control: false },
    session,
    { scope: options.scope || "both" }
  );
}

/** Set (or remove) public access — anyone, logged in or not. Use sparingly. */
async function setPublicAccess(resourceUrl, modes, session, options = {}) {
  const scope = options.scope || "resource";
  if (!["resource", "default", "both"].includes(scope)) {
    throw new Error(`Invalid scope "${scope}" — expected 'resource', 'default', or 'both'.`);
  }
  const { datasetWithAcl, resourceAcl } = await _getEditableAcl(resourceUrl, session);

  let updatedAcl = resourceAcl;
  if (scope === "resource" || scope === "both") {
    updatedAcl = setPublicResourceAccess(updatedAcl, modes);
  }
  if (scope === "default" || scope === "both") {
    updatedAcl = setPublicDefaultAccess(updatedAcl, modes);
  }

  return _saveAclOrThrowControlError(resourceUrl, datasetWithAcl, updatedAcl, session);
}

/**
 * Read-only: which agents have explicit access to this resource.
 * Returns e.g. { "https://pod.example/x/profile/card#me": { read: true, ... } }
 */
async function listAgentsWithAccess(resourceUrl, session) {
  let datasetWithAcl;
  try {
    datasetWithAcl = await getSolidDatasetWithAcl(resourceUrl, { fetch: session.fetch });
  } catch (err) {
    throw _normalizeFetchError(err);
  }
  // NOTE: getAgentAccessAll takes the resource-WITH-ACL, not an extracted ACL
  // dataset — it does the resource-acl / fallback-acl branching internally.
  // (Passing getResourceAcl(...) here throws: an ACL dataset has no internal_acl.)
  // Returns null when no ACL is accessible to this session — callers (e.g.
  // mcp-server.js's solid_get_permissions) already branch on that.
  return getAgentAccessAll(datasetWithAcl);
}

/**
 * Read-only: what access does ONE specific agent have here? Useful for the
 * agent to check its own effective rights before attempting a write, so it
 * can report "I don't have write access to that folder" instead of 403ing.
 *
 * Story 8.5 Task 3: returns a discriminated result instead of a bare
 * `null`/object, so "no ACL is visible to this session at all" (this agent
 * lacks Control, or the resource has neither its own ACL nor a readable
 * fallback) is distinguishable from "the ACL is visible, and this specific
 * agent simply has no grants recorded in it" (a legitimate all-false
 * Access). Collapsing both to `null` made onboarding.js/whoami.js print the
 * literal string "null" to a human instead of an actionable state.
 *
 * @returns {Promise<{aclVisible: boolean, access: object|null}>}
 *   aclVisible=false  -> access is always null; no ACL could be read here.
 *   aclVisible=true   -> access is the Access object for agentWebId
 *                        (all-false modes if this agent has no explicit rule).
 */
async function getAgentAccess(resourceUrl, agentWebId, session) {
  let datasetWithAcl;
  try {
    datasetWithAcl = await getSolidDatasetWithAcl(resourceUrl, { fetch: session.fetch });
  } catch (err) {
    throw _normalizeFetchError(err);
  }
  // getResourceAcl takes the resource; createAclFromFallbackAcl ALREADY
  // returns an ACL dataset — don't call getResourceAcl on its output.
  const acl = hasResourceAcl(datasetWithAcl)
    ? getResourceAcl(datasetWithAcl)
    : hasFallbackAcl(datasetWithAcl)
      ? createAclFromFallbackAcl(datasetWithAcl)
      : null;
  if (!acl) return { aclVisible: false, access: null };
  // getAgentResourceAccess(aclDataset, agent) — takes the ACL dataset.
  return { aclVisible: true, access: getAgentResourceAccess(acl, agentWebId) };
}

module.exports = {
  grantAccess,
  revokeAccess,
  setPublicAccess,
  listAgentsWithAccess,
  getAgentAccess,
};
