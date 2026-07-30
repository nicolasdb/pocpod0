#!/usr/bin/env node
/**
 * mcp-server.js
 *
 * Exposes the Pod toolkit as MCP tools over stdio, so any MCP-capable agent
 * (Claude, or a Hermes-style harness with an MCP client) can call it without
 * custom glue code — just point the harness at this process as an MCP server.
 *
 * NOTE ON VERSIONS: MCP shipped a v2 SDK around the 2026-07-28 spec release.
 * This file targets the v1.x API (server.registerTool), which stays
 * supported for production use for a while after v2 ships. package.json
 * pins the SDK to the 1.x line for that reason — check the current MCP
 * TypeScript SDK docs before bumping it, since the API does change across
 * major versions.
 *
 * Run: node src/mcp-server.js
 */

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod");

const { getAgentSession } = require("./auth");
const podClient = require("./podClient");
const wacManager = require("./wacManager");

async function main() {
  // One shared, kept-alive session for the lifetime of this process.
  const session = await getAgentSession();

  const server = new McpServer({ name: "solid-pod-agent", version: "0.1.0" });

  server.registerTool(
    "solid_read_resource",
    {
      description:
        "Read a Solid Pod resource. Returns text content. Works for RDF " +
        "documents (Turtle/JSON-LD) and text-based files.",
      inputSchema: { url: z.string().url() },
    },
    async ({ url }) => {
      const file = await podClient.readFile(url, session);
      const text = await file.text();
      return { content: [{ type: "text", text }] };
    }
  );

  server.registerTool(
    "solid_write_resource",
    {
      description: "Write/overwrite a resource at a given Pod URL.",
      inputSchema: {
        url: z.string().url(),
        content: z.string(),
        contentType: z.string().default("text/turtle"),
      },
    },
    async ({ url, content, contentType }) => {
      await podClient.writeFile(url, content, contentType, session);
      return { content: [{ type: "text", text: `Wrote ${url}` }] };
    }
  );

  server.registerTool(
    "solid_list_container",
    {
      description: "List the resources directly inside a Pod container (folder URL).",
      inputSchema: { containerUrl: z.string().url() },
    },
    async ({ containerUrl }) => {
      const urls = await podClient.listContainer(containerUrl, session);
      return { content: [{ type: "text", text: JSON.stringify(urls, null, 2) }] };
    }
  );

  server.registerTool(
    "solid_get_permissions",
    {
      description:
        "List which agents (WebIDs) currently have explicit WAC access to a resource, and what modes.",
      inputSchema: { resourceUrl: z.string().url() },
    },
    async ({ resourceUrl }) => {
      const access = await wacManager.listAgentsWithAccess(resourceUrl, session);
      return { content: [{ type: "text", text: JSON.stringify(access, null, 2) }] };
    }
  );

  server.registerTool(
    "solid_grant_access",
    {
      description:
        "Grant WAC access modes (read/write/append/control) to a specific WebID on a resource. " +
        "For a container, use scope 'both' so the grant covers both the container itself and " +
        "its children (scope 'resource' alone lets the agent list the folder but not touch " +
        "what's inside it). High-stakes — the calling agent should confirm this with the human " +
        "before invoking it.",
      inputSchema: {
        resourceUrl: z.string().url(),
        agentWebId: z.string().url(),
        read: z.boolean().default(false),
        write: z.boolean().default(false),
        append: z.boolean().default(false),
        control: z.boolean().default(false),
        scope: z.enum(["resource", "default", "both"]).default("resource"),
      },
      // Hints only (spec: clients should never gate purely on these), but this
      // is the documented way to ask a client to require explicit approval —
      // brief §4.4 mandates it for anything that changes who-sees-what.
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    },
    async ({ resourceUrl, agentWebId, read, write, append, control, scope }) => {
      await wacManager.grantAccess(
        resourceUrl,
        agentWebId,
        { read, write, append, control },
        session,
        { scope }
      );
      return {
        content: [
          { type: "text", text: `Updated access for ${agentWebId} on ${resourceUrl}` },
        ],
      };
    }
  );

  server.registerTool(
    "solid_revoke_access",
    {
      description: "Revoke all WAC access for a specific WebID on a resource.",
      inputSchema: {
        resourceUrl: z.string().url(),
        agentWebId: z.string().url(),
      },
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    },
    async ({ resourceUrl, agentWebId }) => {
      await wacManager.revokeAccess(resourceUrl, agentWebId, session);
      return {
        content: [{ type: "text", text: `Revoked access for ${agentWebId} on ${resourceUrl}` }],
      };
    }
  );

  server.registerTool(
    "solid_set_public_access",
    {
      description:
        "Set (or remove) PUBLIC access to a resource — anyone, logged in or not. Use sparingly. " +
        "For a container, use scope 'both' (see solid_grant_access). High-stakes — the calling " +
        "agent should confirm this with the human before invoking it.",
      inputSchema: {
        resourceUrl: z.string().url(),
        read: z.boolean().default(false),
        write: z.boolean().default(false),
        append: z.boolean().default(false),
        control: z.boolean().default(false),
        scope: z.enum(["resource", "default", "both"]).default("resource"),
      },
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    },
    async ({ resourceUrl, read, write, append, control, scope }) => {
      await wacManager.setPublicAccess(resourceUrl, { read, write, append, control }, session, {
        scope,
      });
      return {
        content: [{ type: "text", text: `Updated public access on ${resourceUrl}` }],
      };
    }
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[solid-pod-agent mcp-server] fatal:", err);
  process.exit(1);
});
