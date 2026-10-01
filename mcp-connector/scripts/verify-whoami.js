#!/usr/bin/env node
/**
 * verify-whoami.js
 *
 * solid_whoami, two ways:
 *
 * 1. Offline, always: describeProfile() against fixed Turtle — a profile with
 *    everything, one with nothing, and one whose triples are about another
 *    subject (a profile document can describe more than its owner; only the
 *    WebID's own triples count).
 *
 * 2. Live, when given a server URL: initialize -> tools/call solid_whoami over
 *    the SDK client (same as verify-http.js), asserting the expected WebID.
 *
 * Usage:
 *   node scripts/verify-whoami.js
 *   node scripts/verify-whoami.js http://127.0.0.1:3939/mcp/<slug> <expected-webid>
 *
 * Checking "no receipt" stays manual: list the owner's access-log/ before and
 * after a live call; the tool never goes through writeReadReceipt.
 */

const assert = require("node:assert/strict");
const { describeProfile } = require("../src/profile");

const WEBID = "https://pod.example/collective/agents/agent#me";

function offline() {
  const full = `
    @prefix foaf: <http://xmlns.com/foaf/0.1/> .
    @prefix solid: <http://www.w3.org/ns/solid/terms#> .
    @prefix pim: <http://www.w3.org/ns/pim/space#> .
    <#me> foaf:name "Agent" ; solid:oidcIssuer <https://pod.example/> ; pim:storage </collective/> .
    <#other> foaf:name "Someone else" .`;
  assert.deepEqual(describeProfile(full, WEBID), {
    storage: "https://pod.example/collective/",
    oidcIssuer: "https://pod.example/",
    name: "Agent",
  });

  assert.deepEqual(describeProfile("<#me> a <http://xmlns.com/foaf/0.1/Agent> .", WEBID), {
    storage: null,
    oidcIssuer: null,
    name: null,
  });

  const aboutOthers = `<#other> <http://xmlns.com/foaf/0.1/name> "Not me" .`;
  assert.equal(describeProfile(aboutOthers, WEBID).name, null);
  console.log("offline: ok");
}

async function live(serverUrl, expected) {
  const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
  const { StreamableHTTPClientTransport } = require("@modelcontextprotocol/sdk/client/streamableHttp.js");
  const client = new Client({ name: "verify-whoami", version: "0.1.0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(serverUrl)));
  try {
    const { tools } = await client.listTools();
    assert.ok(tools.some((t) => t.name === "solid_whoami"), "solid_whoami is not listed");
    const result = await client.callTool({ name: "solid_whoami", arguments: {} });
    assert.ok(!result.isError, `solid_whoami failed: ${result.content?.[0]?.text}`);
    const me = JSON.parse(result.content[0].text);
    console.log(me);
    if (expected) assert.equal(me.webId, expected);
    console.log("live: ok");
  } finally {
    await client.close();
  }
}

(async () => {
  offline();
  if (process.argv[2]) await live(process.argv[2], process.argv[3]);
})().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
