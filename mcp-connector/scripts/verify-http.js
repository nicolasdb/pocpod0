#!/usr/bin/env node
/**
 * verify-http.js
 *
 * Story 8.2 AC3: a real MCP client handshake against the running HTTP
 * server — initialize -> tools/list -> one read-only tools/call. A raw curl
 * that returns some JSON is insufficient; this uses the SDK's own client so
 * protocol-level compatibility is actually confirmed. Kept as a committed
 * script (not thrown away) so Story 8.5 can re-run it instead of rebuilding it.
 *
 * Usage: node scripts/verify-http.js [http://127.0.0.1:3939/mcp]
 *
 * Connect via 127.0.0.1, not localhost or a LAN IP — createMcpExpressApp's
 * default DNS-rebinding protection rejects a mismatched Host header, which
 * looks like a protocol failure otherwise.
 */

const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StreamableHTTPClientTransport } = require("@modelcontextprotocol/sdk/client/streamableHttp.js");

const SERVER_URL = process.argv[2] || "http://127.0.0.1:3939/mcp";

// Read-only container AGENT already has access to as of Story 8.1.
const LIST_CONTAINER_URL = process.env.VERIFY_CONTAINER_URL || "https://pod.nicolasdb.eu/hyperscope_ndb/shared/";

// Story 8.5 AC6/Task 5.2: a container the AGENT is NOT granted on, to prove
// the negative path fails cleanly. Defaults to the data-pod root, which
// whoami.js's PROBES also expects-denied for the same reason.
const DENIED_WRITE_URL =
  process.env.VERIFY_DENIED_URL || "https://pod.nicolasdb.eu/hyperscope_ndb/8-5-verify-denied-probe.txt";

// Pinned verbatim from mcp-server.js's toToolErrorResult 403 fallback
// branch. AC6's "clean failure" IS this exact string — asserting it here
// means a future refactor that rewords wacManager/mcp-server's error text
// fails this script loudly instead of silently drifting the
// security-relevant, user-facing wording.
const EXPECTED_DENIED_MESSAGE =
  "Access denied — this agent lacks the required WAC permission on that resource.";

async function main() {
  const transport = new StreamableHTTPClientTransport(new URL(SERVER_URL));
  const client = new Client({ name: "verify-http-script", version: "0.1.0" });

  console.log(`[verify-http] connecting to ${SERVER_URL} ...`);
  await client.connect(transport);
  console.log("[verify-http] initialize: OK");

  const tools = await client.listTools();
  console.log(`[verify-http] tools/list: OK — ${tools.tools.length} tools:`);
  for (const t of tools.tools) console.log(`  - ${t.name}`);

  const expected = [
    "solid_read_resource",
    "solid_write_resource",
    "solid_list_container",
    "solid_get_permissions",
    "solid_grant_access",
    "solid_revoke_access",
    "solid_set_public_access",
  ];
  const names = tools.tools.map((t) => t.name);
  const missing = expected.filter((name) => !names.includes(name));
  if (missing.length > 0) {
    throw new Error(`Missing expected tools: ${missing.join(", ")}`);
  }

  console.log(`[verify-http] tools/call solid_list_container(${LIST_CONTAINER_URL}) ...`);
  const result = await client.callTool({
    name: "solid_list_container",
    arguments: { containerUrl: LIST_CONTAINER_URL },
  });
  console.log("[verify-http] tools/call: OK");
  console.log(JSON.stringify(result, null, 2));

  console.log(`[verify-http] negative test: solid_write_resource to a non-granted resource (${DENIED_WRITE_URL}) ...`);
  const deniedResult = await client.callTool({
    name: "solid_write_resource",
    arguments: { url: DENIED_WRITE_URL, content: "should never be written (verify-http negative test)", contentType: "text/plain" },
  });
  if (!deniedResult.isError) {
    throw new Error(
      `Negative test FAILED: expected a clean denial (isError:true) for ${DENIED_WRITE_URL}, ` +
        `got: ${JSON.stringify(deniedResult)}`
    );
  }
  const deniedText = deniedResult.content && deniedResult.content[0] && deniedResult.content[0].text;
  if (deniedText !== EXPECTED_DENIED_MESSAGE) {
    throw new Error(
      `Negative test wording drifted (AC6). Expected exactly:\n  "${EXPECTED_DENIED_MESSAGE}"\ngot:\n  "${deniedText}"`
    );
  }
  console.log("[verify-http] negative test: OK — clean denial, wording pinned");

  await client.close();
  console.log("[verify-http] ALL CHECKS PASSED");
}

main().catch((err) => {
  console.error("[verify-http] FAILED:", err.message);
  process.exit(1);
});
