#!/usr/bin/env node
/**
 * verify-mint-gate.js
 *
 * Story 7.12 Task 4.3. Offline, no network, no live pod — mocks global.fetch
 * to exercise accountControlsWebId()'s corrected logic: it must gate on
 * whether the account has LINKED a webId (controls.account.webId), not on
 * whether the webId merely sits under a pod the account owns. Run:
 *   node scripts/verify-mint-gate.js
 *
 * Fixture shape confirmed live against CSS's actual LinkWebIdHandler.js
 * (getView(), read off the running container, 2026-08-19): the key is the
 * webId, the value is the resource URL — `{ webIdLinks: { <webId>: <res> } }`.
 */

const assert = require("assert");
const { accountControlsWebId } = require("../src/onboardRouter.js");

function fakeFetch(linkedWebIds) {
  return async (url) => ({
    ok: true,
    json: async () => ({
      webIdLinks: Object.fromEntries(
        linkedWebIds.map((webId, i) => [webId, `https://pod.example.org/.account/webid/${i}/`])
      ),
    }),
  });
}

async function main() {
  let passed = 0;
  const controls = { account: { webId: "https://pod.example.org/.account/webid/" } };

  // A WebID this account has actually linked (e.g. created via Story 7.12's
  // createAgentIdentity flow) must pass the gate.
  {
    global.fetch = fakeFetch(["https://pod.example.org/alice/agents/bot#me"]);
    const owns = await accountControlsWebId(controls, "cookie", "https://pod.example.org/alice/agents/bot#me");
    assert.strictEqual(owns, true);
    console.log("PASS: a linked webId passes the mint gate");
    passed++;
  }

  // A WebID sitting under an owned pod but NEVER linked must be refused
  // BEFORE any CSS mint call is attempted — this is the exact false-positive
  // AC10 calls out (the old prefix-match gate would have allowed this).
  {
    global.fetch = fakeFetch(["https://pod.example.org/alice/agents/bot#me"]);
    const owns = await accountControlsWebId(controls, "cookie", "https://pod.example.org/alice/agents/unlinked#me");
    assert.strictEqual(owns, false);
    console.log("PASS: an unlinked webId under an owned pod is refused");
    passed++;
  }

  // No account.webId control at all -> fails closed.
  {
    global.fetch = fakeFetch([]);
    const owns = await accountControlsWebId({ account: {} }, "cookie", "https://pod.example.org/alice/agents/bot#me");
    assert.strictEqual(owns, false);
    console.log("PASS: missing controls.account.webId fails closed");
    passed++;
  }

  console.log(`\n${passed} passed.`);
}

main().catch((e) => {
  console.error("FAIL", e);
  process.exit(1);
});
