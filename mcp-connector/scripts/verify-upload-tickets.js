#!/usr/bin/env node
/**
 * verify-upload-tickets.js
 *
 * Story 8.10 AC10: live proof for the six adversarial cases the ticketed
 * upload path must refuse. Same convention as verify-http.js/verify-mint-
 * gate.js — a committed script driven against a real running server, not a
 * unit-test-framework mock (no test framework exists in mcp-connector/,
 * 8.2/8.3/8.4 precedent).
 *
 * Usage:
 *   node scripts/verify-upload-tickets.js <mcpUrl> [targetUrl]
 *
 * <mcpUrl> is the full /mcp/<slug> URL (same argument verify-http.js takes).
 * The upload base is derived from it by stripping the /mcp/<slug> suffix.
 * [targetUrl] defaults to a file under the AGENT identity's existing
 * shared/ grant (Story 8.1) so the "already exists" branch of
 * solid_prepare_upload can be exercised too.
 *
 * Connect via 127.0.0.1 for a local run (DNS-rebinding protection), or the
 * public https://solid-mcp.nicolasdb.eu/mcp/<slug> URL for the live check —
 * same rule verify-http.js documents.
 *
 * The expiry case waits out the real 300s TTL (uploadTickets.js has no env
 * override — the TTL is a fixed security property, not a knob). Override
 * VERIFY_EXPIRY_WAIT_MS only to point at a locally patched, shorter-TTL
 * build; do not shorten it against the real server.
 */

const crypto = require("crypto");
const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StreamableHTTPClientTransport } = require("@modelcontextprotocol/sdk/client/streamableHttp.js");

const MCP_URL = process.argv[2] || "http://127.0.0.1:3939/mcp";
const TARGET_URL =
  process.argv[3] ||
  process.env.VERIFY_UPLOAD_TARGET_URL ||
  "https://pod.nicolasdb.eu/hyperscope_ndb/shared/8-10-verify-upload.txt";
const UPLOAD_BASE = MCP_URL.replace(/\/mcp\/[^/]+\/?$/, "");
const EXPIRY_WAIT_MS = Number(process.env.VERIFY_EXPIRY_WAIT_MS || 305 * 1000);

let failures = 0;

function ok(label) {
  console.log(`[verify-upload-tickets] OK — ${label}`);
}
function fail(label, detail) {
  failures += 1;
  console.error(`[verify-upload-tickets] FAIL — ${label}${detail ? `: ${detail}` : ""}`);
}
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Real `curl --data-binary` always sends a Content-Type (defaults to
// application/x-www-form-urlencoded unless overridden — AC5 is exactly
// that the server ignores it and uses the ticket's declared type instead).
// Node's bare fetch() sends none at all, which express.raw({type:"*/*"})
// then refuses to parse (type-is has nothing to match against) — a client
// gap, not a server one. Every POST in this script goes through here so it
// mirrors what a real curl invocation actually sends.
function postUpload(url, body) {
  return fetch(url, {
    method: "POST",
    body,
    headers: { "content-type": "application/octet-stream" },
  });
}

async function prepareUpload(client, body, overwrite = false) {
  const bytes = Buffer.byteLength(body, "utf-8");
  const result = await client.callTool({
    name: "solid_prepare_upload",
    arguments: { targetUrl: TARGET_URL, contentType: "text/plain", bytes, overwrite },
  });
  const text = result.content && result.content[0] && result.content[0].text;
  const match = text && text.match(/curl --data-binary @<path-to-file> (\S+)/);
  if (!match) {
    throw new Error(`solid_prepare_upload did not return a ticket (overwrite:${overwrite}): ${text}`);
  }
  return { uploadUrl: match[1], bytes, text };
}

async function main() {
  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL));
  const client = new Client({ name: "verify-upload-tickets", version: "0.1.0" });
  console.log(`[verify-upload-tickets] connecting to ${MCP_URL} ...`);
  await client.connect(transport);
  console.log(`[verify-upload-tickets] upload base resolved to ${UPLOAD_BASE}`);

  // --- Baseline: a correct ticket + correct redemption actually works,
  // and existence-probe/overwrite ceremony fires (AC3) --------------------
  const body1 = `verify-upload-tickets baseline ${new Date().toISOString()}\n`;
  const first = await prepareUpload(client, body1);
  const putRes = await postUpload(first.uploadUrl, Buffer.from(body1, "utf-8"));
  if (putRes.ok) ok("baseline upload succeeded");
  else fail("baseline upload", `expected 2xx, got ${putRes.status}`);

  const secondPrepareNoOverwrite = await client.callTool({
    name: "solid_prepare_upload",
    arguments: { targetUrl: TARGET_URL, contentType: "text/plain", bytes: 1 },
  });
  const noOverwriteText = secondPrepareNoOverwrite.content[0].text;
  if (noOverwriteText.includes("already exists") && !noOverwriteText.includes("curl")) {
    ok("existence probe refuses a ticket without overwrite:true (AC3)");
  } else {
    fail("existence probe / overwrite gate", noOverwriteText);
  }

  // --- Case 1: replayed ticket after successful redemption ---------------
  const replayRes = await postUpload(first.uploadUrl, Buffer.from(body1, "utf-8"));
  if (replayRes.status === 404) ok("ticket replay after redemption refused (404)");
  else fail("ticket replay", `expected 404, got ${replayRes.status}`);

  // --- Case 2: unknown/guessed token, same generic shape -----------------
  const guessedToken = crypto.randomBytes(16).toString("base64url");
  const guessRes = await postUpload(`${UPLOAD_BASE}/upload/${guessedToken}`, Buffer.from("guess"));
  const guessBody = await guessRes.json().catch(() => null);
  const replayBody = await replayRes.json().catch(() => null);
  if (guessRes.status === 404 && guessBody && replayBody && guessBody.error === replayBody.error) {
    ok("unknown token: same generic 404 shape as a replayed one (no existence oracle)");
  } else {
    fail("unknown-token generic shape", `guess=${guessRes.status} ${JSON.stringify(guessBody)}, replay=${JSON.stringify(replayBody)}`);
  }

  // --- Case 3: declared bytes != actual body length -----------------------
  const body3 = "twelve bytes";
  const ticket3 = await prepareUpload(client, body3, true);
  const mismatchRes = await postUpload(ticket3.uploadUrl, Buffer.from(body3 + "extra", "utf-8"));
  if (mismatchRes.status === 400) ok("length mismatch refused (400), nothing written");
  else fail("length mismatch", `expected 400, got ${mismatchRes.status}`);
  // Confirm the pod is unchanged: re-reading must still show the baseline
  // body from the first (successful) upload, not the mismatched attempt.
  const readAfterMismatch = await client.callTool({ name: "solid_read_resource", arguments: { url: TARGET_URL } });
  const readText = readAfterMismatch.content && readAfterMismatch.content[0] && readAfterMismatch.content[0].text;
  if (readText === body1) ok("pod byte-identical after refused length-mismatch upload");
  else fail("pod mutated by a refused upload", `expected baseline body, got: ${readText}`);
  // The rejected ticket was also consumed by this attempt (redeem-then-
  // verify is the only order that closes the two-attempt race) — confirm
  // it cannot be retried with a correct body either.
  const retryAfterMismatch = await postUpload(ticket3.uploadUrl, Buffer.from(body3, "utf-8"));
  if (retryAfterMismatch.status === 404) ok("ticket consumed by its first (even if rejected) redemption attempt");
  else fail("ticket reuse after a rejected redemption", `expected 404, got ${retryAfterMismatch.status}`);

  // --- Case 4: body larger than the cap -----------------------------------
  // UPLOAD_MAX_BYTES defaults to 25MiB in mcp-server.js; override
  // VERIFY_UPLOAD_CAP_BYTES to match a smaller cap the target server was
  // started with, so this case doesn't require generating 25MB+ over the
  // wire on every run.
  const capBytes = Number(process.env.VERIFY_UPLOAD_CAP_BYTES || 25 * 1024 * 1024);
  const oversizedTicket = await prepareUpload(client, "placeholder", true);
  const oversizedBody = Buffer.alloc(capBytes + 1, 0x61);
  const oversizedRes = await postUpload(oversizedTicket.uploadUrl, oversizedBody);
  if (oversizedRes.status === 413 || oversizedRes.status === 400) {
    ok(`oversized body (${capBytes + 1} bytes) refused at app level (${oversizedRes.status})`);
  } else {
    fail("oversized body", `expected 413/400, got ${oversizedRes.status}`);
  }

  // --- Case: ticket cannot be redirected to a different target -----------
  // The route takes no target parameter at all — POST /upload/:token always
  // writes to the URL bound into the ticket at issue time (mcp-server.js's
  // handler reads ticket.targetUrl, never anything from the request). Prove
  // a client-supplied override is inert rather than assuming it from the
  // code shape: attach a spoofed target as a query string and confirm the
  // write still lands at TARGET_URL, not the spoofed one.
  const body4 = "target binding proof";
  const ticket4 = await prepareUpload(client, body4, true);
  const spoofedTargetUrl = TARGET_URL.replace(/[^/]+$/, "8-10-verify-upload-SPOOFED.txt");
  const spoofedUrl = `${ticket4.uploadUrl}?target=${encodeURIComponent(spoofedTargetUrl)}`;
  const spoofRes = await postUpload(spoofedUrl, Buffer.from(body4, "utf-8"));
  if (spoofRes.ok) {
    const spoofRead = await client.callTool({ name: "solid_read_resource", arguments: { url: TARGET_URL } });
    const spoofReadText = spoofRead.content && spoofRead.content[0] && spoofRead.content[0].text;
    if (spoofReadText === body4) ok("query-string target override ignored — write bound to the ticket's original target (AC2)");
    else fail("target binding", `write did not land at TARGET_URL: ${spoofReadText}`);
  } else {
    fail("target binding upload", `expected 2xx, got ${spoofRes.status}`);
  }

  // --- Case 5: expired ticket ----------------------------------------------
  console.log(`[verify-upload-tickets] waiting ${Math.round(EXPIRY_WAIT_MS / 1000)}s for a ticket to expire (AC10) ...`);
  const expiringTicket = await prepareUpload(client, "will expire", true);
  await sleep(EXPIRY_WAIT_MS);
  const expiredRes = await postUpload(expiringTicket.uploadUrl, Buffer.from("will expire", "utf-8"));
  if (expiredRes.status === 404) ok("expired ticket refused (404)");
  else fail("expired ticket", `expected 404, got ${expiredRes.status}`);

  await client.close();

  console.log(
    failures === 0
      ? "[verify-upload-tickets] ALL CHECKS PASSED"
      : `[verify-upload-tickets] ${failures} CHECK(S) FAILED`
  );
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error("[verify-upload-tickets] FAILED:", err.message);
  process.exit(1);
});
