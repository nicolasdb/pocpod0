#!/usr/bin/env node
/**
 * mcp-server.js
 *
 * Exposes the Pod toolkit as MCP tools over Streamable HTTP, so Claude.ai's
 * remote-connector infra (or any MCP-capable HTTP client) can reach it at a
 * public URL. claude.ai's code sandbox cannot reach pod.nicolasdb.eu at all
 * (403 host_not_allowed), so a remote connector — Claude calling this server
 * from Anthropic's infra — is the only viable direction; stdio only works
 * for a locally-spawned process.
 *
 * NOTE ON VERSIONS: MCP shipped a v2 SDK around the 2026-07-28 spec release.
 * This file targets the v1.x API (server.registerTool), which stays
 * supported for production use for a while after v2 ships. package.json
 * pins the SDK to the 1.x line for that reason — check the current MCP
 * TypeScript SDK docs before bumping it, since the API does change across
 * major versions.
 *
 * Session model: stateless, per-request transport+server (see Dev Notes in
 * story 8-2-http-transport.md, "Concurrency trap"). The Solid session is a
 * boot-time singleton reused across every request — logging in per request
 * would be a real regression (latency + needless token churn against CSS).
 *
 * Run: node src/mcp-server.js  (reads PORT/HOST from env, defaults below)
 */

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StreamableHTTPServerTransport } = require("@modelcontextprotocol/sdk/server/streamableHttp.js");
const { createMcpExpressApp } = require("@modelcontextprotocol/sdk/server/express.js");
const { z } = require("zod");

const { getAgentSession } = require("./auth");
const podClient = require("./podClient");
const wacManager = require("./wacManager");

const PORT = parsePort(process.env.PORT);
const HOST = process.env.HOST || "127.0.0.1";

// Comma-separated Host header allowlist. Only meaningful when HOST is not a
// loopback address: createMcpExpressApp auto-enables DNS-rebinding protection
// for 127.0.0.1/localhost/::1 and silently disables it for anything else, so
// binding 0.0.0.0 behind nginx (story 8.4) needs this set explicitly.
const ALLOWED_HOSTS = process.env.ALLOWED_HOSTS
  ? process.env.ALLOWED_HOSTS.split(",").map((h) => h.trim()).filter(Boolean)
  : undefined;

function parsePort(raw) {
  if (!raw) return 3939;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Invalid PORT "${raw}" — must be an integer between 1 and 65535.`);
  }
  return port;
}

/**
 * Map a routine Solid/CSS error to a human-actionable MCP error result
 * instead of leaking a stack trace. Reuses 8.1's documented wording for the
 * Control-access case (wacManager.js's _saveAclOrThrowControlError) rather
 * than inventing new phrasing.
 */
function toToolErrorResult(err) {
  const status = err && (err.statusCode || err.status || (err.response && err.response.status));
  let message;

  if (status === 401) {
    message = "Not authenticated — the agent's Solid session is not logged in.";
  } else if (status === 403) {
    message = err.message && err.message.includes("Control")
      ? err.message
      : "Access denied — this agent lacks the required WAC permission on that resource.";
  } else if (status === 404) {
    message = "Resource not found at that URL.";
  } else if (status === 409) {
    message = "Conflict — the request could not be completed in the resource's current state.";
  } else if (err && err.message && err.message.toLowerCase().includes("control")) {
    // listAgentsWithAccess/getAgentAccess return null (not throw) without Control,
    // but wacManager surfaces a documented Error in some call paths too.
    message = "Reading permissions requires Control access on this resource; this agent has read/write only.";
  } else if (
    err &&
    err.message &&
    (err.message.includes("501") || err.message.toLowerCase().includes("not implemented"))
  ) {
    message = "Permissions can only be read for RDF resources or containers.";
  } else {
    message = err && err.message ? err.message : "Unexpected error.";
  }

  return { content: [{ type: "text", text: message }], isError: true };
}

/** Wrap a tool handler so thrown Solid/Inrupt errors become MCP error results. */
function safeHandler(fn) {
  return async (...args) => {
    try {
      return await fn(...args);
    } catch (err) {
      return toToolErrorResult(err);
    }
  };
}

/**
 * Build a fresh McpServer instance wired to the given (already-authenticated)
 * Solid session. Kept as a function of `session` — not module-level global
 * wiring — so Story 8.3 can call this per identity/token without a rewrite.
 */
function buildMcpServer(session) {
  const server = new McpServer({ name: "solid-pod-agent", version: "0.1.0" });

  server.registerTool(
    "solid_read_resource",
    {
      description:
        "Read a Solid Pod resource. Returns text content. Works for RDF " +
        "documents (Turtle/JSON-LD) and text-based files.",
      inputSchema: { url: z.string().url() },
    },
    safeHandler(async ({ url }) => {
      const file = await podClient.readFile(url, session);
      const text = await file.text();
      return { content: [{ type: "text", text }] };
    })
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
    safeHandler(async ({ url, content, contentType }) => {
      await podClient.writeFile(url, content, contentType, session);
      return { content: [{ type: "text", text: `Wrote ${url}` }] };
    })
  );

  server.registerTool(
    "solid_list_container",
    {
      description: "List the resources directly inside a Pod container (folder URL).",
      inputSchema: { containerUrl: z.string().url() },
    },
    safeHandler(async ({ containerUrl }) => {
      const urls = await podClient.listContainer(containerUrl, session);
      return { content: [{ type: "text", text: JSON.stringify(urls, null, 2) }] };
    })
  );

  server.registerTool(
    "solid_get_permissions",
    {
      description:
        "List which agents (WebIDs) currently have explicit WAC access to a resource, and what modes.",
      inputSchema: { resourceUrl: z.string().url() },
    },
    safeHandler(async ({ resourceUrl }) => {
      const access = await wacManager.listAgentsWithAccess(resourceUrl, session);
      if (access === null) {
        return {
          content: [
            {
              type: "text",
              text: "Reading permissions requires Control access on this resource; this agent has read/write only.",
            },
          ],
          isError: true,
        };
      }
      return { content: [{ type: "text", text: JSON.stringify(access, null, 2) }] };
    })
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
    safeHandler(async ({ resourceUrl, agentWebId, read, write, append, control, scope }) => {
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
    })
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
    safeHandler(async ({ resourceUrl, agentWebId }) => {
      await wacManager.revokeAccess(resourceUrl, agentWebId, session);
      return {
        content: [{ type: "text", text: `Revoked access for ${agentWebId} on ${resourceUrl}` }],
      };
    })
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
    safeHandler(async ({ resourceUrl, read, write, append, control, scope }) => {
      await wacManager.setPublicAccess(resourceUrl, { read, write, append, control }, session, {
        scope,
      });
      return {
        content: [{ type: "text", text: `Updated public access on ${resourceUrl}` }],
      };
    })
  );

  return server;
}

async function main() {
  // One shared, kept-alive session for the lifetime of this process.
  // AC5: fail fast with a clear error if login fails, rather than serving a
  // broken endpoint.
  let session;
  try {
    session = await getAgentSession();
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[solid-pod-agent mcp-server] fatal: Solid login failed:", err.message);
    process.exit(1);
  }

  const app = createMcpExpressApp({ host: HOST, allowedHosts: ALLOWED_HOSTS });

  // Stateless mode: a fresh transport + server per request. There is no
  // session to disambiguate concurrent clients in stateless mode, so a
  // single shared transport would let concurrent requests interleave state
  // incorrectly — see Dev Notes "Concurrency trap". The cost (re-registering
  // 7 tool definitions per call) is trivial. This also happens to be the
  // shape Story 8.3 wants anyway: each person's endpoint constructs its own
  // per-request server bound to their own token.
  app.post("/mcp", async (req, res) => {
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    const server = buildMcpServer(session);

    res.on("close", () => {
      transport.close();
      server.close();
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[solid-pod-agent mcp-server] request handling error:", err.message);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: { code: -32603, message: "Internal server error" },
          id: null,
        });
      }
    }
  });

  // Stateless mode has no SSE stream or session to tear down, so GET/DELETE
  // are not meaningful requests here.
  const notSupported = (req, res) => {
    res.status(405).json({
      jsonrpc: "2.0",
      error: { code: -32000, message: "Method not allowed. This server is stateless." },
      id: null,
    });
  };
  app.get("/mcp", notSupported);
  app.delete("/mcp", notSupported);

  // Unauthenticated health check for 8.4's systemd/nginx checks. Deliberately
  // does not include the WebID — this endpoint goes public in 8.4, and the
  // agent's WebID is not something to hand out anonymously.
  app.get("/healthz", (req, res) => {
    res.json({ ok: true });
  });

  app.listen(PORT, HOST, () => {
    // eslint-disable-next-line no-console
    console.log(`[solid-pod-agent mcp-server] listening on http://${HOST}:${PORT}/mcp`);
  });
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[solid-pod-agent mcp-server] fatal:", err.message);
  process.exit(1);
});
