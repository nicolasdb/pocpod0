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
      throw new Error(
        `${session.info.webId} does not have Control access to ${resourceUrl}, ` +
          "so it cannot change permissions here. This grant must be made by " +
          "the pod owner's WebID (see src/onboarding.js)."
      );
    }
    if (!hasFallbackAcl(datasetWithAcl)) {
      // No resource ACL and no readable fallback: initialise a fresh one.
      // WARNING: saving an ACL with nobody holding control:true permanently
      // orphans this resource — nobody, including the pod owner, could ever
      // change its permissions again. Always include the owner with
      // control:true in the same batch that creates a new ACL.
      resourceAcl = createAcl(datasetWithAcl);
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
  const { datasetWithAcl, resourceAcl } = await _getEditableAcl(resourceUrl, session);

  let updatedAcl = resourceAcl;
  if (scope === "resource" || scope === "both") {
    updatedAcl = setAgentResourceAccess(updatedAcl, agentWebId, modes);
  }
  if (scope === "default" || scope === "both") {
    updatedAcl = setAgentDefaultAccess(updatedAcl, agentWebId, modes);
  }

  return saveAclFor(datasetWithAcl, updatedAcl, { fetch: session.fetch });
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
  const { datasetWithAcl, resourceAcl } = await _getEditableAcl(resourceUrl, session);

  let updatedAcl = resourceAcl;
  if (scope === "resource" || scope === "both") {
    updatedAcl = setPublicResourceAccess(updatedAcl, modes);
  }
  if (scope === "default" || scope === "both") {
    updatedAcl = setPublicDefaultAccess(updatedAcl, modes);
  }

  return saveAclFor(datasetWithAcl, updatedAcl, { fetch: session.fetch });
}

/**
 * Read-only: which agents have explicit access to this resource.
 * Returns e.g. { "https://pod.example/x/profile/card#me": { read: true, ... } }
 */
async function listAgentsWithAccess(resourceUrl, session) {
  const datasetWithAcl = await getSolidDatasetWithAcl(resourceUrl, {
    fetch: session.fetch,
  });
  // NOTE: getAgentAccessAll takes the resource-WITH-ACL, not an extracted ACL
  // dataset — it does the resource-acl / fallback-acl branching internally.
  // (Passing getResourceAcl(...) here throws: an ACL dataset has no internal_acl.)
  return getAgentAccessAll(datasetWithAcl);
}

/**
 * Read-only: what access does ONE specific agent have here? Useful for the
 * agent to check its own effective rights before attempting a write, so it
 * can report "I don't have write access to that folder" instead of 403ing.
 */
async function getAgentAccess(resourceUrl, agentWebId, session) {
  const datasetWithAcl = await getSolidDatasetWithAcl(resourceUrl, {
    fetch: session.fetch,
  });
  // getResourceAcl takes the resource; createAclFromFallbackAcl ALREADY
  // returns an ACL dataset — don't call getResourceAcl on its output.
  const acl = hasResourceAcl(datasetWithAcl)
    ? getResourceAcl(datasetWithAcl)
    : hasFallbackAcl(datasetWithAcl)
      ? createAclFromFallbackAcl(datasetWithAcl)
      : null;
  if (!acl) return null;
  // getAgentResourceAccess(aclDataset, agent) — takes the ACL dataset.
  return getAgentResourceAccess(acl, agentWebId);
}

module.exports = {
  grantAccess,
  revokeAccess,
  setPublicAccess,
  listAgentsWithAccess,
  getAgentAccess,
};
