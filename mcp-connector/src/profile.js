/**
 * profile.js
 *
 * solid_whoami: which WebID this connector carries, and what its profile says
 * about it. Before this, the only way for a model to learn its own identity
 * was to probe paths and infer it from what answered (live 2026-10-01: three
 * connectors told apart by access tests alone). A skill that must decide
 * "am I the collective's agent or a member's?" needs it as its first step.
 *
 * Pure on purpose: it resolves no collective and no role — that is the
 * caller's work, from config.ttl. It writes nothing, and the profile is read
 * with the session's own fetch rather than through solid_read_resource, so no
 * read receipt is written: an agent reading its own profile is not a read of
 * someone else's pod.
 *
 * `webId` comes from the identity, which loginIdentity() cross-checked against
 * session.info.webId at login: it is the authenticated identity, not a value
 * read from the profile. The profile only adds what it declares; an
 * unreadable profile leaves those null and does not fail the call.
 */

const N3 = require("n3");

const P = {
  storage: "http://www.w3.org/ns/pim/space#storage",
  oidcIssuer: "http://www.w3.org/ns/solid/terms#oidcIssuer",
  name: "http://xmlns.com/foaf/0.1/name",
};

/** What the profile document says about `webId`, from its Turtle. */
function describeProfile(turtle, webId) {
  const docUrl = webId.split("#")[0];
  const quads = new N3.Parser({ baseIRI: docUrl }).parse(turtle);
  const first = (predicate) => {
    const q = quads.find((q) => q.subject.value === webId && q.predicate.value === predicate);
    return q ? q.object.value : null;
  };
  return { storage: first(P.storage), oidcIssuer: first(P.oidcIssuer), name: first(P.name) };
}

/** The tool's result: always `webId`; the rest when the profile is readable. */
async function whoami(identity) {
  const webId = identity.webId;
  const result = { webId, storage: null, oidcIssuer: null, name: null, profileReadable: false };
  const res = await identity.session.fetch(webId.split("#")[0], { headers: { Accept: "text/turtle" } });
  if (res.status === 401) {
    // safeHandler re-authenticates once on a 401: an expired session, not a
    // profile that refuses this identity.
    const err = new Error(`GET ${webId} failed: [401]`);
    err.statusCode = 401;
    throw err;
  }
  if (!res.ok) return result;
  try {
    return { webId, ...describeProfile(await res.text(), webId), profileReadable: true };
  } catch {
    return result;
  }
}

module.exports = { describeProfile, whoami };
