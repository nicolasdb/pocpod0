#!/usr/bin/env node
/**
 * probe-append-only.js
 *
 * Story 8.9 Tasks 2 and 3 (AC3, AC4): is an Append-only receipt journal
 * actually reachable against this CSS instance — not in principle, live?
 *
 * Story 8.6 recorded Append-only as "could not be realized" and attributed it
 * to the Epic 7 backoffice offering no such toggle. That is a statement about a
 * UI, not about the protocol, and `wacManager.grantAccess()` has accepted
 * `append: true` all along. This script settles it by writing an Append-only
 * ACL programmatically and then behaving like the constrained party.
 *
 * WHY IT RUNS IN THE AGENT'S OWN POD: authoring an ACL needs `acl:Control`,
 * which the agent deliberately does NOT have on a data pod (Story 8.1 AC4
 * proved the 403, and that guarantee must not be weakened to make this story
 * easier). The agent DOES hold Control over its own pod, so the scratch
 * container lives there and the Append-only grant is aimed at a *different*
 * identity — the public agent class, fetched unauthenticated. Same substitution
 * Story 8.1 used when no second WebID was available. The real `access-log/` is
 * never touched.
 *
 * What it proves, in order:
 *   Task 3.1  grantAccess/setPublicAccess can author acl:Append at all — the
 *             .acl is read back and printed verbatim, so the Turtle is evidence.
 *   Path A    POST a new resource into an Append-only container  -> expect 201
 *             PUT over an existing resource                      -> expect 403
 *             GET an existing resource                           -> expect 403
 *             i.e. a journal of many small resources, unrewritable by its writer.
 *   Path B    N3 PATCH (insert-only) against an RDF resource with acl:Append.
 *             DELETE-bearing PATCH against the same                -> expect 403
 *
 * Everything it creates, it deletes. Usage:
 *   node scripts/probe-append-only.js [--keep]
 */

const { getAgentSession } = require("../src/auth");
const wac = require("../src/wacManager");

const KEEP = process.argv.includes("--keep");
const AGENT_WEBID = process.env.AGENT_WEBID;

const line = (s = "") => console.log(s);
const rule = () => line("-".repeat(72));

const results = [];
/** @param expected a value, an array of acceptable values, or null to record without asserting. */
function record(label, expected, actual, note = "") {
  const accepted = expected === null ? null : Array.isArray(expected) ? expected : [expected];
  const ok = accepted === null || accepted.includes(actual);
  results.push({ label, expected: accepted, actual, ok });
  line(`  ${ok ? "PASS" : "FAIL"}  ${label}`);
  line(
    `        expected ${accepted === null ? "(recorded, not asserted)" : accepted.join(" or ")}, got ${actual}${note ? ` — ${note}` : ""}`
  );
}

// CSS answers an UNAUTHENTICATED denial with 401 (an invitation to log in),
// not 403 — verified live on 2026-08-11. Both are denials; which one comes back
// is a function of whether credentials were presented, not of the mode. This
// probe's constrained party is anonymous by construction (see header), so the
// denial it sees is 401. An authenticated identity holding the same
// Append-only grant would see 403.
const DENIED = [401, 403];
// CSS returns 205 Reset Content on a successful write, not 200.
const WROTE = [200, 201, 204, 205];

/** Unauthenticated fetch — this is the Append-only-constrained party. */
async function anon(method, url, opts = {}) {
  const res = await fetch(url, { method, ...opts });
  const text = await res.text().catch(() => "");
  return { status: res.status, location: res.headers.get("location"), text };
}

async function main() {
  const session = await getAgentSession({ keepAlive: false });
  if (!session.info.isLoggedIn) throw new Error("Agent session not logged in — check .env.");
  const webId = session.info.webId;
  const podRoot = `${new URL(webId).origin}/${new URL(webId).pathname.split("/").filter(Boolean)[0]}/`;
  const scratch = `${podRoot}scratch-8-9-append/`;

  line("=== Story 8.9 Tasks 2+3 — is Append-only reachable? (live) ===");
  line(`agent WebID:  ${webId}`);
  line(`scratch:      ${scratch}   (agent's OWN pod — never the data pod)`);
  line(`timestamp:    ${new Date().toISOString()}`);
  rule();

  // --- Setup: container + one pre-existing resource, created as owner-of-self.
  // CSS does not auto-create a missing parent container (Story 8.6 :213), so
  // the container is created explicitly before anything is put inside it.
  line("--- setup ---");
  let res = await session.fetch(scratch, {
    method: "PUT",
    headers: { link: '<http://www.w3.org/ns/ldp#BasicContainer>; rel="type"', "content-type": "text/turtle" },
  });
  line(`  PUT  ${scratch} -> ${res.status} (container)`);

  const existing = `${scratch}existing.txt`;
  res = await session.fetch(existing, {
    method: "PUT",
    headers: { "content-type": "text/plain" },
    body: Buffer.from("seed line\n", "utf-8"),
  });
  line(`  PUT  ${existing} -> ${res.status} (pre-existing resource)`);

  const rdfDoc = `${scratch}journal.ttl`;
  res = await session.fetch(rdfDoc, {
    method: "PUT",
    headers: { "content-type": "text/turtle" },
    body: Buffer.from('<#e0> <http://example.org/note> "seed" .\n', "utf-8"),
  });
  line(`  PUT  ${rdfDoc} -> ${res.status} (RDF resource, for Path B)`);
  line();

  // --- Task 3.1: can an Append-only ACL be authored programmatically at all?
  line("--- Task 3.1  author an Append-only grant via wacManager ---");
  // scope 'both': acl:accessTo governs the container itself (so POST into it is
  // allowed) and acl:default governs the resources inside it (so an existing
  // entry cannot be rewritten). Append-only on the container alone would leave
  // children unaddressed and inheriting nothing.
  await wac.setPublicAccess(
    scratch,
    { read: false, write: false, append: true, control: false },
    session,
    { scope: "both" }
  );
  line("  setPublicAccess({append:true}, scope:'both') returned without error");

  if (AGENT_WEBID) {
    // Also exercise the named-WebID path (grantAccess), since that is what a
    // real access-log/ grant would use — the public class is only this probe's
    // stand-in for a second identity.
    await wac.grantAccess(
      scratch,
      "https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me",
      { read: false, write: false, append: true, control: false },
      session,
      { scope: "both" }
    );
    line("  grantAccess(<owner WebID>, {append:true}, scope:'both') returned without error");
  }

  const aclRes = await session.fetch(`${scratch}.acl`, { headers: { accept: "text/turtle" } });
  const aclBody = await aclRes.text();
  line(`  GET  ${scratch}.acl -> ${aclRes.status}`);
  line("  .acl body (verbatim — this is the evidence acl:Append was written):");
  aclBody.split("\n").forEach((l) => line(`    ${l}`));
  // The saved Turtle uses full URIs, not the acl: prefix — match on the URI.
  const ACL_NS = "http://www.w3.org/ns/auth/acl#";
  const hasMode = (m) => new RegExp(`<${ACL_NS}${m}>`).test(aclBody);
  record("acl:Append present in the authored ACL", true, hasMode("Append"));
  // Scoped to the non-owner rules: the owner's own rule legitimately carries
  // Read/Write/Control, so a bare document-wide search would prove nothing.
  const nonOwnerRules = aclBody
    .split(/\n(?=<)/)
    .filter((r) => !r.includes("/nicolas_claude/profile/card#me"));
  const leaked = nonOwnerRules.filter((r) => new RegExp(`<${ACL_NS}(Write|Read|Control)>`).test(r));
  record("no Write/Read/Control leaked into the non-owner rules", 0, leaked.length, leaked.join(" | ").slice(0, 200));
  line();

  // --- Path A: POST-per-receipt into an Append-only container.
  line("--- Path A  POST-per-receipt into an Append-only container (unauthenticated) ---");
  const post = await anon("POST", scratch, {
    headers: { "content-type": "text/plain", slug: "receipt-probe" },
    body: "{\"ts\":\"probe\"}\n",
  });
  record("POST a NEW resource into the container", [201], post.status, post.location ? `Location: ${post.location}` : "");

  const put = await anon("PUT", existing, {
    headers: { "content-type": "text/plain" },
    body: "REWRITTEN BY THE AUDITED PARTY\n",
  });
  record("PUT over an EXISTING resource (the tamper attempt) is DENIED", DENIED, put.status);

  const get = await anon("GET", existing);
  record("GET an existing resource is DENIED (Append implies no Read)", DENIED, get.status);

  const del = await anon("DELETE", existing);
  record("DELETE an existing resource is DENIED", DENIED, del.status);
  line();

  // --- Path B: N3 Patch against an RDF resource.
  line("--- Path B  insert-only N3 PATCH on an RDF resource (unauthenticated) ---");
  const insertPatch = `@prefix solid: <http://www.w3.org/ns/solid/terms#>.
_:rename a solid:InsertDeletePatch;
  solid:inserts { <#e1> <http://example.org/note> "appended by patch" . }.`;
  const patchIns = await anon("PATCH", rdfDoc, {
    headers: { "content-type": "text/n3" },
    body: insertPatch,
  });
  record("PATCH inserts-only on an RDF resource SUCCEEDS", WROTE, patchIns.status, WROTE.includes(patchIns.status) ? "" : patchIns.text.slice(0, 160));

  const deletePatch = `@prefix solid: <http://www.w3.org/ns/solid/terms#>.
_:rename a solid:InsertDeletePatch;
  solid:deletes { <#e0> <http://example.org/note> "seed" . }.`;
  const patchDel = await anon("PATCH", rdfDoc, {
    headers: { "content-type": "text/n3" },
    body: deletePatch,
  });
  record("PATCH deletes (the tamper attempt) is DENIED", DENIED, patchDel.status);
  line();

  // --- Teardown.
  if (KEEP) {
    line(`--- teardown SKIPPED (--keep): ${scratch} still exists ---`);
  } else {
    line("--- teardown ---");
    const posted = post.location ? new URL(post.location, scratch).href : null;
    for (const url of [posted, existing, rdfDoc, `${scratch}.acl`, scratch].filter(Boolean)) {
      const r = await session.fetch(url, { method: "DELETE" });
      line(`  DELETE ${url} -> ${r.status}`);
    }
  }

  rule();
  const failed = results.filter((r) => !r.ok);
  line(`RESULT: ${results.length - failed.length}/${results.length} expectations met`);
  failed.forEach((f) => line(`  UNMET: ${f.label} (expected ${f.expected}, got ${f.actual})`));
  await session.logout().catch(() => {});
  if (failed.length) process.exitCode = 2;
}

main().catch((err) => {
  console.error(`[probe-append-only] FAILED: ${err && err.message}`);
  process.exit(1);
});
