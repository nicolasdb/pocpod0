#!/usr/bin/env node
/**
 * verify-version-metadata.js
 *
 * ADR 006 (publication by pull): the collective's agent needs a change key
 * per file. Offline check, no pod: feeds podClient a container listing in the
 * shape CSS 7 serves and a file response carrying an ETag, and asserts the
 * key survives. A server that omits the fields must yield null ("unknown"),
 * never a value that would read as "unchanged".
 *
 * Usage: node scripts/verify-version-metadata.js
 */

const assert = require("node:assert/strict");
const podClient = require("../src/podClient");

const BASE = "https://pod.example/alice/out/";
const CONTAINER_TTL = `
@prefix dc: <http://purl.org/dc/terms/>.
@prefix ldp: <http://www.w3.org/ns/ldp#>.
@prefix posix: <http://www.w3.org/ns/posix/stat#>.
@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.
<> a ldp:Container, ldp:BasicContainer, ldp:Resource;
   ldp:contains <note.md>, <sub/>, <bare.md>.
<note.md> a ldp:Resource;
   dc:modified "2026-09-24T12:00:00.000Z"^^xsd:dateTime;
   posix:mtime 1790251200;
   posix:size 1234.
<sub/> a ldp:Container, ldp:BasicContainer, ldp:Resource;
   dc:modified "2026-09-20T08:00:00.000Z"^^xsd:dateTime.
<bare.md> a ldp:Resource.
`;

function fakeSession(routes) {
  return {
    fetch: async (url, init = {}) => {
      const r = routes[url];
      if (!r) return new Response("not found", { status: 404, statusText: "Not Found" });
      const res = new Response(r.body, { status: r.status || 200, headers: r.headers });
      // A constructed Response has url "", and solid-client resolves the
      // listing's relative IRIs against it; a real fetch sets it.
      Object.defineProperty(res, "url", { value: url });
      return res;
    },
  };
}

(async () => {
  const session = fakeSession({
    [BASE]: { body: CONTAINER_TTL, headers: { "content-type": "text/turtle" } },
    [BASE + "note.md"]: {
      body: "# Note\n\nsecond line\n",
      headers: { etag: '"abc123"', "last-modified": "Thu, 24 Sep 2026 12:00:00 GMT", "content-type": "text/markdown" },
    },
    [BASE + "secret.md"]: { body: "", status: 403 },
  });

  const entries = await podClient.listContainerDetailed(BASE, session);
  const byUrl = Object.fromEntries(entries.map((e) => [e.url, e]));
  assert.equal(entries.length, 3);
  assert.deepEqual(byUrl[BASE + "note.md"], {
    url: BASE + "note.md", isContainer: false, modified: "2026-09-24T12:00:00.000Z", size: 1234,
  });
  assert.equal(byUrl[BASE + "sub/"].isContainer, true);
  assert.equal(byUrl[BASE + "sub/"].size, null);
  assert.equal(byUrl[BASE + "bare.md"].modified, null, "missing modified must be null, not guessed");
  assert.equal(byUrl[BASE + "bare.md"].size, null);
  console.log("list: modified/size parsed, absent fields are null");

  const file = await podClient.readFileWithVersion(BASE + "note.md", session);
  assert.equal(file.text, "# Note\n\nsecond line\n", "text must be byte-for-byte, no metadata glued on");
  assert.equal(file.etag, '"abc123"');
  assert.equal(file.contentType, "text/markdown");
  console.log("read: text intact, etag and content-type returned");

  await assert.rejects(podClient.readFileWithVersion(BASE + "secret.md", session), (err) => {
    assert.equal(err.statusCode, 403, "statusCode must be set so safeHandler journals a denial");
    assert.match(err.message, /\[403\]/);
    return true;
  });
  console.log("read: 403 surfaces with statusCode for safeHandler");

  console.log("ALL CHECKS PASSED");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
