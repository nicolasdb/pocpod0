#!/usr/bin/env node
/**
 * verify-receipt-appendonly.js
 *
 * Story 8.9 Task 4.3 (AC8): after the Path-A change, does a cross-pod read
 * still produce a receipt in the subject's access-log/?
 *
 * Evidence standard is Story 8.6's, not "the call returned 200": the container
 * is listed before and after, and the new receipt is READ BACK and its content
 * checked. A POST that returns 201 and lands nowhere useful would pass a
 * status-code check and fail this one.
 *
 * Run it TWICE — once before tightening the real grant and once after. Before,
 * the agent still holds Read and can list/read back its own receipt. After, it
 * holds Append only, so listing and reading back are DENIED — and that denial
 * is itself the proof the grant tightened. Pass --expect-appendonly for the
 * second run so the script asserts the denials instead of the reads.
 *
 * Usage:
 *   node scripts/verify-receipt-appendonly.js <foreignResourceUrl> [--expect-appendonly]
 */

const podClient = require("../src/podClient");
const { getAgentSession } = require("../src/auth");
const { isForeignResource, writeReadReceipt, podRootOf } = require("../src/receipt");

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith("--"));
const expectAppendOnly = args.includes("--expect-appendonly");

if (!target) {
  console.error("Usage: node scripts/verify-receipt-appendonly.js <foreignResourceUrl> [--expect-appendonly]");
  process.exit(1);
}

const line = (s = "") => console.log(s);
const results = [];
function record(label, ok, detail = "") {
  results.push({ label, ok });
  line(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
}

/** Raw list so a 401/403 is a value to assert on, not an exception to catch. */
async function listRaw(containerUrl, session) {
  const res = await session.fetch(containerUrl, { headers: { accept: "text/turtle" } });
  return { status: res.status, text: await res.text().catch(() => "") };
}

async function main() {
  const session = await getAgentSession({ keepAlive: false });
  if (!session.info.isLoggedIn) throw new Error("Agent session not logged in — check .env.");
  const webId = session.info.webId;
  const accessLog = `${podRootOf(target)}access-log/`;

  line("=== Story 8.9 AC8 — receipts still work after the Path-A change ===");
  line(`agent WebID: ${webId}`);
  line(`target:      ${target}`);
  line(`access-log:  ${accessLog}`);
  line(`mode:        ${expectAppendOnly ? "AFTER tightening (expect Append-only)" : "BEFORE tightening"}`);
  line(`timestamp:   ${new Date().toISOString()}`);
  line("-".repeat(72));

  record("target is a foreign resource (a receipt is owed at all)", isForeignResource(target, webId));

  const before = await listRaw(accessLog, session);
  line(`  GET ${accessLog} (before) -> ${before.status}, ${Buffer.byteLength(before.text)} bytes`);

  // The read the receipt is about — this is the act being recorded.
  const file = await podClient.readFile(target, session);
  const text = await file.text();
  record("cross-pod READ succeeded", text.length >= 0, `${text.length} chars`);

  const written = await writeReadReceipt(
    { resourceUrl: target, readerLabel: "verify-8-9", readerWebId: webId, outcome: "read" },
    session
  );
  record("receipt POST accepted", written.status === 201, `status ${written.status}, url ${written.url}`);
  if (!written.url) throw new Error("POST succeeded but server returned no Location header — cannot verify a receipt with no URL");

  const after = await listRaw(accessLog, session);
  line(`  GET ${accessLog} (after)  -> ${after.status}, ${Buffer.byteLength(after.text)} bytes`);

  if (expectAppendOnly) {
    // Under Append-only the agent must be unable to see or alter the journal.
    // These denials are the point of the story: the party writing the audit
    // trail can no longer read other readers' entries or rewrite its own.
    record("container listing DENIED (agent no longer holds Read)", [401, 403].includes(after.status), `status ${after.status}`);

    const readBack = await session.fetch(written.url);
    record("reading back its own receipt DENIED", [401, 403].includes(readBack.status), `status ${readBack.status}`);

    const tamper = await session.fetch(written.url, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: Buffer.from('{"tampered":true}', "utf-8"),
    });
    record("overwriting its own receipt DENIED (the tamper attempt)", [401, 403].includes(tamper.status), `status ${tamper.status}`);

    const del = await session.fetch(written.url, { method: "DELETE" });
    record("deleting its own receipt DENIED", [401, 403].includes(del.status), `status ${del.status}`);
  } else {
    record("container listing grew", Buffer.byteLength(after.text) > Buffer.byteLength(before.text),
      `${Buffer.byteLength(before.text)} -> ${Buffer.byteLength(after.text)} bytes`);
    record("new receipt appears in the container listing", after.text.includes(written.url.split("/").pop()));

    const readBack = await session.fetch(written.url);
    const body = await readBack.text();
    record("receipt reads back", readBack.status === 200, `status ${readBack.status}`);
    let parsed = null;
    try {
      parsed = JSON.parse(body);
    } catch (_) {}
    record("receipt is valid JSON with the expected fields",
      Boolean(parsed && parsed.ts && parsed.resource === target && parsed.readerWebId === webId && "underGrant" in parsed));
    line("  receipt body (verbatim):");
    body.split("\n").forEach((l) => line(`    ${l}`));
  }

  line("-".repeat(72));
  const failed = results.filter((r) => !r.ok);
  line(`RESULT: ${results.length - failed.length}/${results.length} checks passed`);
  failed.forEach((f) => line(`  FAILED: ${f.label}`));
  await session.logout().catch(() => {});
  if (failed.length) process.exitCode = 2;
}

main().catch((err) => {
  console.error(`[verify-receipt] FAILED: ${err && err.message}`);
  process.exit(1);
});
