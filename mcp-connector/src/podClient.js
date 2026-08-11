/**
 * podClient.js
 *
 * Read/write operations against a Solid Pod. Every function takes an
 * authenticated `session` (from auth.js) and uses `session.fetch` so
 * requests carry the agent's DPoP-bound access token.
 *
 * Two kinds of resources:
 *  - RDF datasets (Turtle, JSON-LD, etc.) — use readDataset/saveDataset.
 *  - Arbitrary files (images, PDFs, plain text blobs) — use readFile/writeFile.
 *  - Containers (folders) — use listContainer/createContainer.
 */

const {
  getSolidDataset,
  saveSolidDatasetAt,
  createSolidDataset,
  getFile,
  overwriteFile,
  createContainerAt,
  getContainedResourceUrlAll,
  isContainer,
} = require("@inrupt/solid-client");

/** Read an RDF resource as a SolidDataset (for use with getThing/setThing etc). */
async function readDataset(url, session) {
  return getSolidDataset(url, { fetch: session.fetch });
}

/** Save a SolidDataset back to the Pod (creates it if it doesn't exist yet). */
async function saveDataset(url, dataset, session) {
  return saveSolidDatasetAt(url, dataset, { fetch: session.fetch });
}

/** Start a brand-new empty dataset, e.g. before adding Things to it. */
function newDataset() {
  return createSolidDataset();
}

/** Read a non-RDF file. Returns a Blob (Node: a Buffer-like Blob polyfill). */
async function readFile(url, session) {
  return getFile(url, { fetch: session.fetch });
}

/**
 * Write/overwrite a non-RDF file.
 * @param {string|Buffer|Blob} content
 * @param {string} contentType e.g. 'text/markdown', 'application/pdf'
 */
async function writeFile(url, content, contentType, session) {
  // @inrupt/solid-client's Node polyfill for File/Blob does `'name' in input`
  // to detect a File-like object; a raw string satisfies neither branch and
  // throws "Cannot use 'in' operator to search for 'name' in <string>" before
  // any network call. Story 8.1 AC1 (live verification) hit this on first
  // real write — coerce plain strings to Buffer, which the polyfill accepts.
  const body = typeof content === "string" ? Buffer.from(content, "utf-8") : content;
  return overwriteFile(url, body, { contentType, fetch: session.fetch });
}

/**
 * Append to a non-RDF file: read-then-write, original content preserved,
 * addition placed after it. Absent resource -> created with just `content`.
 * Story 8.6 Task 1: the read-then-write the epic-8 action-log convention has
 * done by hand since Story 8.2, now a reusable primitive (so library
 * consumers like Hermes get it too, not just the MCP tool).
 *
 * No optimistic concurrency (ETag/If-Match) — Story 7.3 already scoped that
 * as a cross-API design problem, not a per-tool fix. Concurrent appends to
 * the same resource are a lost-update race: last writer wins.
 *
 * @returns {Promise<{existed: boolean, bytesBefore: number, bytesAfter: number}>}
 */
async function appendFile(url, content, contentType, session) {
  let existing = "";
  let existed = false;
  try {
    const file = await getFile(url, { fetch: session.fetch });
    existing = await file.text();
    existed = true;
  } catch (err) {
    if (!_is404(err)) throw err;
  }
  const combined = existing + content;
  await overwriteFile(url, Buffer.from(combined, "utf-8"), { contentType, fetch: session.fetch });
  return {
    existed,
    bytesBefore: Buffer.byteLength(existing, "utf-8"),
    bytesAfter: Buffer.byteLength(combined, "utf-8"),
  };
}

/**
 * Create a NEW resource inside a container, letting the server assign the URL.
 * Story 8.9: this is the write primitive that an `acl:Append`-only grant
 * actually permits. `appendFile` above cannot be used under such a grant — it
 * is a read-then-overwrite, so it needs Read + Write, and Write is exactly what
 * an append-only journal must withhold from its own writer.
 *
 * Verified live 2026-08-11 against CSS 7.x with a container carrying only
 * `acl:Append` (accessTo + default): POST -> 201, while PUT/GET/DELETE against
 * an existing child are all denied. That asymmetry is the whole point — the
 * writer can add entries and cannot alter the ones already there.
 *
 * `slug` is a HINT. The server may ignore it or disambiguate a collision, so
 * the authoritative URL is the returned one, never one the caller composed.
 *
 * @param {string} containerUrl must end with '/'
 * @param {string|Buffer} content
 * @param {string} contentType
 * @param {import('@inrupt/solid-client-authn-node').Session} session
 * @param {{slug?: string}} [options]
 * @returns {Promise<{url: string, status: number}>}
 */
async function postResource(containerUrl, content, contentType, session, options = {}) {
  if (!containerUrl.endsWith("/")) {
    throw new Error(`postResource expects a container URL ending in "/", got "${containerUrl}"`);
  }
  const headers = { "content-type": contentType };
  if (options.slug) headers.slug = options.slug;

  const res = await session.fetch(containerUrl, {
    method: "POST",
    headers,
    body: typeof content === "string" ? Buffer.from(content, "utf-8") : content,
  });

  if (!res.ok) {
    const err = new Error(`POST ${containerUrl} failed [${res.status}]: ${await res.text().catch(() => "")}`);
    err.statusCode = res.status;
    throw err;
  }

  const location = res.headers.get("location");
  return {
    // A 201 without Location would leave the caller unable to name what it
    // just created; surface that rather than silently returning undefined.
    url: location ? new URL(location, containerUrl).href : null,
    status: res.status,
  };
}

function _is404(err) {
  const status = err && (err.statusCode || err.status || (err.response && err.response.status));
  if (status) return status === 404;
  return Boolean(err && err.message && err.message.includes("[404]"));
}

/**
 * Delete any resource (file or RDF document). Does not recursively delete
 * containers — callers must ensure a container is empty first.
 *
 * Story 8.1 (live): inrupt's `deleteFile` 404s against a container URL that
 * ends in '/', even when the container exists — a library quirk, not a real
 * 404 from CSS. Raw `session.fetch` with an explicit DELETE avoids it, which
 * is exactly the workaround 8.1 used live; this makes it the permanent path
 * instead of a per-story rediscovery.
 */
async function deleteResource(url, session) {
  const res = await session.fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const err = new Error(`DELETE ${url} failed: [${res.status}] ${res.statusText || ""}`.trim());
    err.statusCode = res.status;
    throw err;
  }
  return res;
}

/** True if a GET against `url` now 404s — used to confirm a delete actually happened. */
async function confirmGone(url, session) {
  const res = await session.fetch(url, { method: "GET" });
  return res.status === 404;
}

/** Create a container (folder). URL must end in '/'. */
async function createContainer(url, session) {
  return createContainerAt(url, { fetch: session.fetch });
}

/** List the URLs of resources directly inside a container. */
async function listContainer(containerUrl, session) {
  const dataset = await getSolidDataset(containerUrl, { fetch: session.fetch });
  return getContainedResourceUrlAll(dataset);
}

/** Check whether a URL points to a container. */
async function checkIsContainer(url, session) {
  const dataset = await getSolidDataset(url, { fetch: session.fetch });
  return isContainer(dataset);
}

module.exports = {
  readDataset,
  saveDataset,
  newDataset,
  readFile,
  writeFile,
  appendFile,
  postResource,
  deleteResource,
  confirmGone,
  createContainer,
  listContainer,
  checkIsContainer,
};
