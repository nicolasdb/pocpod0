/**
 * journal.js
 *
 * Story 8.4 AC7: append-only JSONL audit journal of every tool invocation.
 * Lives on the named `mcp-audit` Docker volume (docker-compose.yml), not a
 * bind-mount under the repo path — `make vps-push`'s `rsync --delete-after`
 * would otherwise eat it, same root cause as AC9's identities.json fix.
 *
 * Never write the slug, client id, client secret, or bearer token — only
 * the identity's `label` (set at boot, see mcp-server.js bootIdentities) and
 * the tool's target resource URL are logged, matching the AC7 rule Story
 * 8.3 established for the 404 path and applying it to a file whose whole
 * purpose is to be kept.
 */

const fs = require("fs");
const path = require("path");

const JOURNAL_PATH = process.env.AUDIT_LOG_PATH || "/app/audit/journal.jsonl";

// Bound: one active file up to this size, one rotated backup kept alongside
// it (rename, not delete-then-recreate, so a crash mid-rotation can't drop
// the file entirely). Total worst case is 2x this number — an unbounded
// audit file on a disk that's already tight is the same failure class AC3
// exists to close for nginx logs.
//
// Validated rather than a bare Number(...): a malformed value silently
// becomes NaN, and `size >= NaN` is always false — that would disable
// rotation entirely instead of failing loudly at boot.
function parseMaxBytes(raw) {
  if (raw === undefined || raw === "") return 10 * 1024 * 1024; // 10 MiB
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`Invalid AUDIT_LOG_MAX_BYTES "${raw}" — must be a positive integer.`);
  }
  return value;
}

const MAX_BYTES = parseMaxBytes(process.env.AUDIT_LOG_MAX_BYTES);

function rotateIfNeeded() {
  let size = 0;
  try {
    size = fs.statSync(JOURNAL_PATH).size;
  } catch (err) {
    if (err.code !== "ENOENT") throw err;
    return;
  }
  if (size >= MAX_BYTES) {
    fs.renameSync(JOURNAL_PATH, `${JOURNAL_PATH}.1`);
  }
}

/**
 * @param {object} entry
 * @param {string} entry.label - identity label, never the slug.
 * @param {string} entry.tool - MCP tool name.
 * @param {string} [entry.resource] - target resource URL, if the tool has one.
 * @param {"ok"|"denied"|"error"} entry.outcome
 */
function appendAuditEntry({ label, tool, resource, outcome }) {
  try {
    fs.mkdirSync(path.dirname(JOURNAL_PATH), { recursive: true });
    rotateIfNeeded();
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      label,
      tool,
      resource: resource || null,
      outcome,
    });
    fs.appendFileSync(JOURNAL_PATH, line + "\n");
  } catch (err) {
    // The journal is best-effort observability, not a request-blocking
    // concern — a full disk or permissions problem here must not turn into
    // a 500 for the caller. Surface it on stderr so it isn't silent.
    // eslint-disable-next-line no-console
    console.error("[solid-pod-agent mcp-server] audit journal write failed:", err.message);
  }
}

module.exports = { appendAuditEntry, JOURNAL_PATH, MAX_BYTES };
