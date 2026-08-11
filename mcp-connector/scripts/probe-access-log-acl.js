#!/usr/bin/env node
/**
 * probe-access-log-acl.js
 *
 * Story 8.9 Task 1 (AC1, AC2): establishes, live and with raw evidence, what
 * the AGENT credential can actually do to a pod's `access-log/` — the container
 * that holds read receipts about the pod owner. The question this answers is
 * "can the party being audited rewrite its own audit trail", so it MUST run as
 * the agent (getAgentSession), never as the owner: an owner session would
 * answer a different question and answer it "yes" trivially.
 *
 * What it records, verbatim, with no paraphrasing:
 *   - GET  <podRoot>access-log/                  status + WAC-Allow header
 *   - GET  <podRoot>access-log/receipts.jsonl    status + WAC-Allow header
 *   - PUT  <podRoot>access-log/receipts.jsonl    status — the file's OWN bytes,
 *          read back unchanged. 200/205 proves Write; 403 proves Write absent.
 *          This pod holds real receipts: writing anything else would destroy a
 *          real journal, which is why the body is a byte-for-byte round trip
 *          and the probe aborts if the GET did not succeed.
 *   - GET  <podRoot>access-log/.acl              status + body (own ACL?)
 *   - GET  <podRoot>.acl                         status + body (inherited acl:default?)
 *
 * A 404 on access-log/.acl means the container carries no ACL of its own and
 * is governed by the pod root's acl:default — that is the AC2 provenance
 * question, and both bodies are printed so the answer is read off the Turtle
 * rather than assumed.
 *
 * Read-only apart from the identical-bytes PUT. Never hardcodes a pod.
 *
 * Usage: node scripts/probe-access-log-acl.js <podRootUrl> [--no-write-probe]
 *   e.g. node scripts/probe-access-log-acl.js https://pod.nicolasdb.eu/hyperscope_ndb/
 */

const { getAgentSession } = require("../src/auth");

const args = process.argv.slice(2);
const podRoot = args.find((a) => !a.startsWith("--"));
const skipWriteProbe = args.includes("--no-write-probe");

if (!podRoot) {
  console.error("Usage: node scripts/probe-access-log-acl.js <podRootUrl> [--no-write-probe]");
  console.error("  <podRootUrl> must be a pod root, e.g. https://pod.example.org/alice/");
  process.exit(1);
}
if (!/^https?:\/\/.+\/$/.test(podRoot)) {
  console.error(`[probe] "${podRoot}" is not a pod root URL — it must be absolute and end with "/".`);
  process.exit(1);
}

const line = (s = "") => console.log(s);
const rule = () => line("-".repeat(72));

/** Print a request's raw evidence: status, selected headers, body if asked. */
async function probe(session, method, url, { body, headers = {}, showBody = false } = {}) {
  let res;
  try {
    res = await session.fetch(url, { method, body, headers });
  } catch (err) {
    line(`${method} ${url}`);
    line(`  NETWORK ERROR: ${err && err.message}`);
    return null;
  }
  line(`${method} ${url}`);
  line(`  status:    ${res.status} ${res.statusText}`);
  const wac = res.headers.get("wac-allow");
  if (wac) line(`  WAC-Allow: ${wac}`);
  const ct = res.headers.get("content-type");
  if (ct) line(`  Content-Type: ${ct}`);
  const text = await res.text();
  if (showBody) {
    line("  body (verbatim):");
    if (text.length === 0) line("    <empty>");
    else text.split("\n").forEach((l) => line(`    ${l}`));
  } else {
    line(`  body bytes: ${Buffer.byteLength(text, "utf-8")}`);
  }
  line();
  return { status: res.status, contentType: ct, wac, text };
}

async function main() {
  const accessLog = `${podRoot}access-log/`;
  const receipts = `${accessLog}receipts.jsonl`;

  const session = await getAgentSession({ keepAlive: false });
  if (!session.info.isLoggedIn) throw new Error("Agent session is not logged in — check .env credentials.");

  line("=== Story 8.9 Task 1 — access-log/ ground truth (AGENT credential) ===");
  line(`agent WebID: ${session.info.webId}`);
  line(`pod root:    ${podRoot}`);
  line(`timestamp:   ${new Date().toISOString()}`);
  rule();

  line("--- 1.3  Read the container and the journal ---");
  await probe(session, "GET", accessLog);
  const got = await probe(session, "GET", receipts);

  line("--- 1.4  Overwrite probe: the file's OWN bytes, unchanged ---");
  if (skipWriteProbe) {
    line("  SKIPPED (--no-write-probe)\n");
  } else if (!got || got.status !== 200) {
    // Without a successful read there are no original bytes to write back, and
    // writing anything else could destroy a real journal. Refuse rather than
    // improvise a body.
    line(`  SKIPPED — the GET returned ${got ? got.status : "no response"}, so the original`);
    line("  bytes are unknown. Refusing to PUT a body that is not a byte-for-byte");
    line("  round trip of what is already there.\n");
  } else {
    line(`  writing back ${Buffer.byteLength(got.text, "utf-8")} bytes, identical to what was read`);
    await probe(session, "PUT", receipts, {
      body: Buffer.from(got.text, "utf-8"),
      headers: { "content-type": got.contentType || "text/plain" },
    });
    const after = await probe(session, "GET", receipts);
    if (after && after.status === 200) {
      const same = after.text === got.text;
      line(`  round-trip integrity: content ${same ? "IDENTICAL — journal intact" : "CHANGED — INVESTIGATE"}`);
      if (!same) process.exitCode = 1;
      line();
    }
  }

  line("--- 1.5  ACL provenance: own .acl, or inherited from pod root? ---");
  const own = await probe(session, "GET", `${accessLog}.acl`, { showBody: true });
  await probe(session, "GET", `${podRoot}.acl`, { showBody: true });

  rule();
  line("Reading the result:");
  line("  * WAC-Allow user=... on the GETs is CSS's own statement of the effective grant.");
  line("  * PUT 200/205 => Write is held (the journal is rewritable by its own writer).");
  line("    PUT 403     => Write is absent.");
  line(
    `  * access-log/.acl ${own ? own.status : "?"} => ${
      own && own.status === 404
        ? "no ACL of its own; the pod-root acl:default governs."
        : own && own.status === 403
          ? "an ACL may exist but the agent lacks acl:Control to read it (expected for a non-owner)."
          : "see body above."
    }`
  );
  line("  * A 403 reading .acl is NOT evidence of the grant — CSS requires Control to read ACLs.");

  await session.logout().catch(() => {});
}

main().catch((err) => {
  console.error(`[probe] FAILED: ${err && err.message}`);
  process.exit(1);
});
