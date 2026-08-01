#!/usr/bin/env node
/**
 * whoami.js — run as the AGENT, to confirm what it can actually reach.
 *
 * This is the "walking the talk" check: don't assume the grants worked,
 * verify from the agent's own perspective. Run it after onboarding, and
 * again any time you change ACLs.
 *
 * Run: npm run whoami
 */

const { getAgentSession, closeSession } = require("./auth");
const podClient = require("./podClient");
const wacManager = require("./wacManager");

// Containers to probe. Include ones you expect to FAIL — confirming the
// agent is correctly locked out matters as much as confirming access.
//
// Story 8.5 correction: the earlier list included `hyperscope_ndb/notes/`
// and `hyperscope_ndb/inbox/` as if they were real granted containers.
// They never were — they were this brief's own admitted guesses, never
// granted by the OWNER, never confirmed to exist. The one container that
// is actually granted and already exercised by 8.1/8.2/8.4 is
// `hyperscope_ndb/shared/` (DATA_POD_GRANTED_CONTAINER). PROBES now
// reflects reality: one expect-access entry, two expect-denied entries.
const PROBES = [
  "https://pod.nicolasdb.eu/hyperscope_ndb/shared/", // expect: access (real grant)
  "https://pod.nicolasdb.eu/hyperscope_ndb/", // expect: denied (pod root, not granted)
  "https://pod.nicolasdb.eu/nicolas/", // expect: denied (a different person's pod)
];

async function main() {
  const session = await getAgentSession({ keepAlive: false });
  console.log(`\nAgent identity: ${session.info.webId}\n`);

  try {
    for (const url of PROBES) {
      process.stdout.write(`${url}\n`);

      // Can it list?
      try {
        const contents = await podClient.listContainer(url, session);
        console.log(`    READ  : yes (${contents.length} item(s))`);
      } catch (err) {
        const code = err.statusCode || err.status || "?";
        console.log(`    READ  : no  (HTTP ${code})`);
      }

      // Can it write? LIST alone can't prove a denial when a container is
      // publicly readable (as hyperscope_ndb/ root and nicolas/ both are) —
      // READ would show "yes" there regardless of the agent's own grant.
      // WRITE isolates the agent's actual WAC rights instead of public
      // access. Probe a throwaway resource name and clean up on success so
      // this check is idempotent and never litters a real pod.
      const probeUrl = `${url}whoami-write-probe.txt`;
      try {
        await podClient.writeFile(probeUrl, "whoami.js write probe — safe to delete", "text/plain", session);
        console.log(`    WRITE : yes`);
        try {
          await session.fetch(probeUrl, { method: "DELETE" });
        } catch {
          // best-effort cleanup; a leftover probe file is a minor mess, not a failure
        }
      } catch (err) {
        const code = err.statusCode || err.status || "?";
        console.log(`    WRITE : no  (HTTP ${code})`);
      }

      // What does the ACL say, if the agent can even see it? getAgentAccess
      // now returns a discriminated { aclVisible, access } shape (Story 8.5
      // Task 3) so "no ACL visible to this agent at all" is printed
      // differently from "ACL visible, agent has zero access recorded in
      // it" — collapsing both to a bare `null` used to print the same
      // unhelpful "not visible" text for two different situations.
      try {
        const { aclVisible, access } = await wacManager.getAgentAccess(url, session.info.webId, session);
        console.log(
          `    ACL   : ${aclVisible ? JSON.stringify(access) : "not visible (no ACL discoverable/accessible to this agent)"}`
        );
      } catch (err) {
        console.log(`    ACL   : not readable (${err?.statusCode || err?.message || String(err)})`);
      }
      console.log("");
    }
  } finally {
    await closeSession(session);
  }
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
