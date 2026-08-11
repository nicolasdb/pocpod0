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
 * ONE RESOURCE PER RECEIPT (Story 8.9, decided 2026-08-11). Until then this
 * module appended lines to a single `access-log/receipts.jsonl` via
 * `podClient.appendFile`, which is a read-then-overwrite and therefore needed
 * Read + Write on the journal. That meant the agent writing the audit trail
 * could also rewrite it — verified live on 2026-08-11, a PUT of the file's own
 * bytes returned 205. A journal its own writer can rewrite is not a journal.
 *
 * POSTing each receipt as its own resource is the write that an `acl:Append`
 * grant permits: verified live, POST -> 201 while PUT/GET/DELETE against an
 * existing entry are all denied. The agent can add entries and cannot touch
 * the ones already written. This also matches what Epic 5's `receipt.py`
 * already does (one Turtle resource per receipt), so the two systems now agree
 * on shape as well as on field names.
 *
 * Honest limits — all three must survive any rewrite of this file:
 *  1. VOLUNTARY convention, not enforcement. CSS surfaces no per-resource read
 *     log to owners, so a reader that simply declines to write receipts leaves
 *     no trace by this mechanism. Append-only makes the cooperative path
 *     trustworthy; it does not make the record complete.
 *  2. Append-only stops the READER tampering. It does not stop the pod owner
 *     editing receipts about themselves — they hold acl:Control over their own
 *     pod. That follows from BP-1 (evidence lands with the data subject) and
 *     is the price of putting it there.
 *  3. `underGrant` is reserved and currently null: this connector's grants are
 *     raw WAC ACLs with no `poc:ConsentGrant` URI to point at (that vocabulary
 *     shipped in Story 5.5, in the pipeline, not here). The field is written
 *     anyway because a receipt's link to the grant it was made under cannot be
 *     reconstructed after the fact — timestamp correlation is a guess. See the
 *     Story 8.9 change proposal for the consent-request loop that fills it.
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
 * Throws on a malformed resourceUrl/readerWebId rather than silently
 * defaulting to "not foreign" — a misconfigured identity (empty/malformed
 * webId) must not silently and permanently disable receipts with no trace.
 * The read itself is never gated on this: callers log the failure and let
 * the read proceed regardless (receipts are a side effect, not a gate).
 */
function isForeignResource(resourceUrl, readerWebId) {
  return podRootOf(resourceUrl) !== podRootOf(readerWebId);
}

/**
 * Slug hint for a receipt: sortable-by-name, collision-resistant, and safe as
 * a URL path segment. The server may ignore or alter it, so it is only a hint —
 * the authoritative URL is whatever the POST returns.
 */
function receiptSlug(ts) {
  const stamp = ts.replace(/[:.]/g, "-");
  const rand = Math.random().toString(36).slice(2, 8);
  return `${stamp}-${rand}.json`;
}

/**
 * Write a read receipt into the subject's own access-log/ container, as its
 * own resource. Requires the reader's session to hold acl:Append on that
 * container (this module mints no grants — that is a human, out-of-band act,
 * the same boundary as every other grant in this story).
 *
 * @returns {Promise<{url: string, status: number}>} the created receipt's URL
 */
async function writeReadReceipt({ resourceUrl, readerLabel, readerWebId, outcome, underGrant }, session) {
  const accessLogUrl = `${podRootOf(resourceUrl)}access-log/`;
  const ts = new Date().toISOString();
  const body = JSON.stringify(
    {
      ts,
      reader: readerLabel,
      readerWebId,
      resource: resourceUrl,
      outcome,
      // Reserved — see honest limit 3 in this file's header. Explicitly null
      // rather than omitted, so a later reader can tell "no grant was recorded"
      // apart from "this receipt predates the field".
      underGrant: underGrant || null,
    },
    null,
    2
  );
  return podClient.postResource(accessLogUrl, body, "application/json", session, {
    slug: receiptSlug(ts),
  });
}

module.exports = { podRootOf, isForeignResource, writeReadReceipt, receiptSlug };
