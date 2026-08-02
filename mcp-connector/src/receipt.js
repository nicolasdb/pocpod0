/**
 * receipt.js
 *
 * Story 8.6 AC11 / FR42: read receipts. When this connector reads a
 * resource it does not own, it appends an entry to the DATA SUBJECT's own
 * `access-log/` container — never the reader's own pod (see architecture.md
 * BP-1: a receipt held by the party being audited can be quietly deleted by
 * them; evidence must land where it cannot be retracted).
 *
 * Shape matches Epic 5's `receipt.py` (BP-1) semantics — timestamp, reader,
 * resource, outcome — not its code (that module is Python, lives in the
 * pipeline). This is a Node connector; only the field names and intent are
 * shared so receipts from both systems read as the same kind of artifact.
 *
 * Honest limit (state this in the skill and tool description too): this is
 * a VOLUNTARY accountability convention, not enforcement. CSS surfaces no
 * per-resource read log to owners — a reader that simply declines to write
 * receipts leaves no trace by this mechanism.
 */

const podClient = require("./podClient");

/** Pod root = origin + first path segment (the CSS convention: one pod per top-level segment). */
function podRootOf(url) {
  const u = new URL(url);
  const first = u.pathname.split("/").filter(Boolean)[0];
  return first ? `${u.origin}/${first}/` : `${u.origin}/`;
}

/**
 * Cheap "not mine" check: compare pod roots, no network round trip per read.
 * A malformed URL is treated as non-foreign — the read itself will fail or
 * succeed on its own merits; receipts are a side effect, not a gate.
 */
function isForeignResource(resourceUrl, readerWebId) {
  try {
    return podRootOf(resourceUrl) !== podRootOf(readerWebId);
  } catch {
    return false;
  }
}

/**
 * Append a read receipt into the subject's own access-log/ container.
 * Requires the reader's session to already hold an acl:Append grant there
 * (this module mints no grants — that is a human, out-of-band act, same
 * boundary as every other grant in this story).
 *
 * @returns {Promise<{existed: boolean, bytesBefore: number, bytesAfter: number}>}
 */
async function writeReadReceipt({ resourceUrl, readerLabel, readerWebId, outcome }, session) {
  const accessLogUrl = `${podRootOf(resourceUrl)}access-log/receipts.jsonl`;
  const line =
    JSON.stringify({
      ts: new Date().toISOString(),
      reader: readerLabel,
      readerWebId,
      resource: resourceUrl,
      outcome,
    }) + "\n";
  return podClient.appendFile(accessLogUrl, line, "text/plain", session);
}

module.exports = { podRootOf, isForeignResource, writeReadReceipt };
