#!/usr/bin/env node
/**
 * onboarding.js — the one-time bootstrap step.
 *
 * THE TWO-TOKEN MODEL (important):
 *
 *   OWNER token  — tied to the pod owner's WebID (e.g. hyperscope_ndb).
 *                  Holds Control over the data. Used ONLY by this script,
 *                  run by a human, to grant the agent its access. Then it
 *                  goes back in the password manager. The agent never sees it.
 *
 *   AGENT token  — tied to the agent's WebID (e.g. nicolas_claude).
 *                  This is what the running agent holds. It can only do what
 *                  the grants below allow.
 *
 * Why it has to work this way: the agent cannot grant itself access to the
 * owner's pod. Only a WebID that already holds acl:Control on a container can
 * change that container's ACL. So the bootstrap is necessarily done by the
 * owner identity, not the agent identity. That's the security property, not
 * an inconvenience.
 *
 * Run:  node src/onboarding.js            (dry run — shows what it would do)
 *       node src/onboarding.js --apply    (actually writes the ACLs)
 */

const { getAgentSession, closeSession } = require("./auth");
const wacManager = require("./wacManager");

// ---------------------------------------------------------------------------
// CONFIGURE: what the agent is allowed to touch, and with which modes.
// Start deliberately narrow. Add containers as you find you need them —
// that friction is the point.
// ---------------------------------------------------------------------------
const AGENT_WEBID =
  process.env.AGENT_WEBID || "https://pod.nicolasdb.eu/nicolas_claude/profile/card#me";

const GRANTS = [
  {
    container: "https://pod.nicolasdb.eu/hyperscope_ndb/notes/",
    modes: { read: true, append: true, write: true, control: false },
    scope: "both", // the container itself + everything inside it
    why: "agent reads and writes HyperScope notes",
  },
  {
    container: "https://pod.nicolasdb.eu/hyperscope_ndb/inbox/",
    modes: { read: true, append: true, write: false, control: false },
    scope: "both",
    why: "agent can drop new items in, but not overwrite existing ones",
  },
  // Deliberately NOT granted by default:
  //   - control: true anywhere in the owner's pod
  //   - anything at the pod root (https://pod.nicolasdb.eu/hyperscope_ndb/)
];

const APPLY = process.argv.includes("--apply");

async function main() {
  // NOTE: this authenticates with the OWNER credentials, not the agent's.
  const session = await getAgentSession({
    clientId: process.env.OWNER_CLIENT_ID,
    clientSecret: process.env.OWNER_CLIENT_SECRET,
    oidcIssuer: process.env.SOLID_OIDC_ISSUER,
    keepAlive: false,
  });

  if (!process.env.OWNER_CLIENT_ID) {
    throw new Error(
      "OWNER_CLIENT_ID / OWNER_CLIENT_SECRET not set. This script must run as " +
        "the pod OWNER's WebID, not the agent's. See .env.example."
    );
  }

  console.log(`\nActing as owner: ${session.info.webId}`);
  console.log(`Granting to agent: ${AGENT_WEBID}`);
  console.log(APPLY ? "\nMODE: APPLY (writing ACLs)\n" : "\nMODE: DRY RUN (nothing written)\n");

  try {
    for (const grant of GRANTS) {
      const modeList = Object.entries(grant.modes)
        .filter(([, v]) => v)
        .map(([k]) => k)
        .join(", ");
      console.log(`- ${grant.container}`);
      console.log(`    modes: ${modeList || "(none)"}  scope: ${grant.scope}`);
      console.log(`    why:   ${grant.why}`);

      if (!APPLY) {
        console.log("    -> skipped (dry run)\n");
        continue;
      }

      await wacManager.grantAccess(
        grant.container,
        AGENT_WEBID,
        grant.modes,
        session,
        { scope: grant.scope }
      );
      console.log("    -> granted");

      // Verify by reading the ACL back, rather than trusting the write.
      const effective = await wacManager.getAgentAccess(
        grant.container,
        AGENT_WEBID,
        session
      );
      console.log(`    -> verified: ${JSON.stringify(effective)}\n`);
    }

    console.log("Done.");
    if (!APPLY) {
      console.log("Re-run with --apply to write these ACLs for real.\n");
    } else {
      console.log(
        "Next: run `npm run whoami` using the AGENT credentials to confirm " +
          "the agent sees exactly this access and nothing more.\n"
      );
    }
  } finally {
    await closeSession(session);
  }
}

main().catch((err) => {
  console.error("\nOnboarding failed:", err.message);
  process.exit(1);
});
