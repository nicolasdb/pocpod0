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
  deleteFile,
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
  return overwriteFile(url, content, { contentType, fetch: session.fetch });
}

/** Delete any resource (file or RDF document). Does not recursively delete containers. */
async function deleteResource(url, session) {
  return deleteFile(url, { fetch: session.fetch });
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
  deleteResource,
  createContainer,
  listContainer,
  checkIsContainer,
};
