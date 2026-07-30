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
const PROBES = [
  "https://pod.nicolasdb.eu/nicolas_claude/",
  "https://pod.nicolasdb.eu/hyperscope_ndb/notes/",
  "https://pod.nicolasdb.eu/hyperscope_ndb/inbox/",
  "https://pod.nicolasdb.eu/hyperscope_ndb/", // expect: denied
  "https://pod.nicolasdb.eu/nicolas/", // expect: denied
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

      // What does the ACL say, if the agent can even see it?
      try {
        const access = await wacManager.getAgentAccess(url, session.info.webId, session);
        console.log(`    ACL   : ${access ? JSON.stringify(access) : "not visible"}`);
      } catch (err) {
        console.log(`    ACL   : not readable (${err.statusCode || err.message})`);
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
