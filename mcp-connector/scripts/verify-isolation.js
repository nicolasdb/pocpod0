#!/usr/bin/env node
/**
 * verify-isolation.js
 *
 * Story 8.3 AC5: proves isolation live, not asserted. With two distinct
 * identities configured (A and B), a tools/call on A's endpoint must reach
 * A's resources and be DENIED on a resource only B can read — with 8.2's
 * actionable error text, not a stack trace.
 *
 * Requires identities.json to have exactly the two slugs passed as argv,
 * and the server already running (npm run mcp).
 *
 * Usage: node scripts/verify-isolation.js <slugA> <slugB> <privateResourceUrl>
 */

const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StreamableHTTPClientTransport } = require("@modelcontextprotocol/sdk/client/streamableHttp.js");

const [slugA, slugB, privateUrl] = process.argv.slice(2);
if (!slugA || !slugB || !privateUrl) {
  console.error("Usage: node scripts/verify-isolation.js <slugA> <slugB> <privateResourceUrl>");
  process.exit(1);
}

const BASE = process.env.MCP_BASE_URL || "http://127.0.0.1:3939";

async function connect(slug) {
  const transport = new StreamableHTTPClientTransport(new URL(`${BASE}/mcp/${slug}`));
  const client = new Client({ name: "verify-isolation", version: "0.1.0" });
  await client.connect(transport);
  return client;
}

async function main() {
  const clientB = await connect(slugB);
  console.log("[B] writing private resource as B ...");
  const writeRes = await clientB.callTool({
    name: "solid_write_resource",
    arguments: { url: privateUrl, content: "only B should read this", contentType: "text/plain" },
  });
  if (writeRes.isError) throw new Error(`B failed to write its own resource: ${writeRes.content[0].text}`);

  console.log("[B] reading own resource ...");
  const readB = await clientB.callTool({ name: "solid_read_resource", arguments: { url: privateUrl } });
  if (readB.isError) throw new Error(`B should be able to read its own resource: ${readB.content[0].text}`);
  console.log("[B] read own resource: OK");
  await clientB.close();

  const clientA = await connect(slugA);
  console.log("[A] attempting to read B's private resource (must be DENIED) ...");
  const readA = await clientA.callTool({ name: "solid_read_resource", arguments: { url: privateUrl } });
  if (!readA.isError) {
    throw new Error("ISOLATION FAILURE: identity A read identity B's private resource!");
  }
  console.log(`[A] correctly denied — error text: "${readA.content[0].text}"`);

  console.log("[A] confirming A still reaches its own resources ...");
  const ownRead = await clientA.callTool({
    name: "solid_list_container",
    arguments: { containerUrl: process.env.VERIFY_CONTAINER_URL || "https://pod.nicolasdb.eu/hyperscope_ndb/shared/" },
  });
  if (ownRead.isError) throw new Error(`A should still reach its own resources: ${ownRead.content[0].text}`);
  console.log("[A] own-resource access: OK");
  await clientA.close();

  console.log("[verify-isolation] ALL CHECKS PASSED");
}

main().catch((err) => {
  console.error("[verify-isolation] FAILED:", err.message);
  process.exit(1);
});
