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
 * story 8-2-http-transport.md, "Concurrency trap"). Story 8.3: N Solid
 * sessions (one per configured identity, see identityRegistry.js) are
 * boot-time singletons reused across every request to their slug — logging
 * in per request would be a real regression (latency + needless token churn
 * against CSS).
 *
 * Routing: POST /mcp/<slug> looks up the matching identity's session and
 * builds a fresh per-request server bound to it (buildMcpServer(identity)).
 * Unknown slugs get a generic 404 (AC4) — see identities.example.json for
 * the config shape and identityRegistry.js for load/validation.
 *
 * Run: node src/mcp-server.js  (reads PORT/HOST from env, defaults below)
 */

const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StreamableHTTPServerTransport } = require("@modelcontextprotocol/sdk/server/streamableHttp.js");
const { createMcpExpressApp } = require("@modelcontextprotocol/sdk/server/express.js");
const rateLimit = require("express-rate-limit");
const { z } = require("zod");

const { getAgentSession } = require("./auth");
const { loadIdentities } = require("./identityRegistry");
const podClient = require("./podClient");
const wacManager = require("./wacManager");
const { appendAuditEntry } = require("./journal");

const PORT = parsePort(process.env.PORT);
const HOST = process.env.HOST || "127.0.0.1";

// Comma-separated Host header allowlist. Only meaningful when HOST is not a
// loopback address: createMcpExpressApp auto-enables DNS-rebinding protection
// for 127.0.0.1/localhost/::1 and silently disables it for anything else, so
// binding 0.0.0.0 behind nginx (story 8.4) needs this set explicitly.
const ALLOWED_HOSTS = process.env.ALLOWED_HOSTS
  ? process.env.ALLOWED_HOSTS.split(",").map((h) => h.trim()).filter(Boolean)
  : undefined;

// Story 8.4 AC4. Two buckets, because the two paths are abused differently:
// a valid slug is a known caller doing too much work, an unknown slug is
// someone guessing at a 22-char secret. The guessing path gets the tighter
// budget — it has no legitimate high-volume use at all.
const RATE_LIMIT_WINDOW_MS = 60 * 1000;
const RATE_LIMIT_MAX = parsePositiveInt("RATE_LIMIT_MAX", process.env.RATE_LIMIT_MAX, 120);
const RATE_LIMIT_MAX_UNKNOWN = parsePositiveInt(
  "RATE_LIMIT_MAX_UNKNOWN",
  process.env.RATE_LIMIT_MAX_UNKNOWN,
  10
);

// AC4.4 (body-size cap) — resolved, no code needed here. 8.2 flagged
// solid_write_resource's `content` as an unbounded z.string(), but the body
// never actually was unbounded: createMcpExpressApp() registers
// express.json() itself, with express's default 100kb limit, before any of
// our middleware. Adding a second parser here would be dead code — the
// first one registered wins, so a later, larger limit cannot raise the cap.
// 100kb is the real effective ceiling; nginx's client_max_body_size is set
// to match so oversized bodies are refused at the edge instead of being
// streamed into Node first. Raising it means passing an explicit
// { limit } through the SDK, which its current API does not expose.
const MAX_BODY_BYTES = "100kb"; // effective, imposed by the SDK — informational

// AC4.4: a hung upstream (CSS not answering) otherwise holds a
// transport+server pair open forever. Slightly under nginx's
// proxy_read_timeout 60s so this side gives the tidier JSON-RPC error
// rather than nginx's opaque 504.
const REQUEST_TIMEOUT_MS = parsePositiveInt(
  "REQUEST_TIMEOUT_MS",
  process.env.REQUEST_TIMEOUT_MS,
  55000
);

/**
 * Rate-limit responses must use the same generic shape as the 404 path
 * (AC4/8.3): a 429 that looked different per-slug would confirm which
 * slugs exist. Never log the slug — it is the credential being guessed.
 */
function rateLimitHandler(req, res) {
  res.status(429).json({
    jsonrpc: "2.0",
    error: { code: -32000, message: "Too many requests." },
    id: null,
  });
}

function parsePort(raw) {
  if (!raw) return 3939;
  const port = Number(raw);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Invalid PORT "${raw}" — must be an integer between 1 and 65535.`);
  }
  return port;
}

/**
 * A malformed numeric env var (e.g. RATE_LIMIT_MAX="abc") must fail loudly at
 * boot, not silently become NaN — a NaN limit/timeout/bound compares false
 * against everything downstream (e.g. journal.js's rotation-size check),
 * which quietly disables the thing it was meant to configure.
 */
function parsePositiveInt(name, raw, fallback) {
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`Invalid ${name} "${raw}" — must be a positive integer.`);
  }
  return value;
}

/**
 * Map a routine Solid/CSS error to a human-actionable MCP error result
 * instead of leaking a stack trace. Reuses 8.1's documented wording for the
 * Control-access case (wacManager.js's _saveAclOrThrowControlError) rather
 * than inventing new phrasing.
 *
 * Story 8.5 Task 5: classify by HTTP status code FIRST. wacManager.js now
 * normalizes every Solid/Inrupt error it throws (or lets through) to carry
 * an explicit `.statusCode` — extracted from the bracketed status in
 * Inrupt's FetchError message when Inrupt itself doesn't expose one (see
 * wacManager.js `_normalizeFetchError`) — so by the time an error reaches
 * here, status should almost always be present. The message-substring
 * checks below are now a genuine fallback for the rare error that reaches
 * this function without ever having passed through wacManager's
 * normalization (e.g. a future call path added without it), not the
 * primary classification path. A future refactor that reword's wacManager's
 * error text can no longer silently reclassify these as generic errors,
 * because the status code — not the wording — is what's matched first.
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
  } else if (status === 501) {
    message = "Permissions can only be read for RDF resources or containers.";
  } else if (!status && err && err.message && err.message.toLowerCase().includes("control")) {
    // Fallback only: no status code was attached at all. wacManager's own
    // throw paths now always set statusCode=403 for Control-access denials
    // (Story 8.5 Task 5), so reaching this branch means some other code
    // path threw a Control-related error without going through
    // wacManager's normalization.
    message = "Reading permissions requires Control access on this resource; this agent has read/write only.";
  } else if (
    !status &&
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

/**
 * Wrap a tool handler so thrown Solid/Inrupt errors become MCP error results,
 * and so every invocation is recorded in the AC7 audit journal — timestamp,
 * identity label, tool name, target resource, outcome. Never the slug,
 * client id, secret or token: those never reach this function, only
 * `identity.label` (resolved once at boot) and the tool's own args do.
 *
 * Story 8.5 Task 4: on a 401 (session appears dead), re-authenticate this
 * identity exactly once and retry the same call. Never retries on 403 —
 * that is a real WAC denial (AC6 depends on it staying denied), not an
 * expired-session condition. `fn` must read the session via `identity`
 * (not a value captured at server-build time) so the retry actually uses
 * the freshly re-authenticated session — see buildMcpServer below, where
 * every tool implementation closes over `identity.session`, not `session`.
 *
 * @param {string} toolName
 * @param {{session: object, label: string, clientId: string, clientSecret: string}} identity
 * @param {string|undefined} resourceKey - name of the arg holding the
 *   target resource URL (varies per tool: url/containerUrl/resourceUrl).
 * @param {Function} fn - the actual tool implementation.
 */
function safeHandler(toolName, identity, resourceKey, fn) {
  const label = identity.label;
  return async (args, ...rest) => {
    const resource = resourceKey ? args[resourceKey] : undefined;
    try {
      let result;
      try {
        result = await fn(args, ...rest);
      } catch (err) {
        const status = err && (err.statusCode || err.status || (err.response && err.response.status));
        if (status === 401) {
          // Bounded to exactly one retry: reauthIdentity is called once
          // here, and this catch block is not itself re-entered for the
          // retry's own errors — a second failure (401 again, or anything
          // else) falls straight through to the outer catch below.
          await reauthIdentity(identity);
          result = await fn(args, ...rest);
        } else {
          throw err;
        }
      }
      // solid_get_permissions returns { isError: true } without throwing
      // when Control access is missing — that's a denial, not a crash.
      appendAuditEntry({ label, tool: toolName, resource, outcome: result && result.isError ? "denied" : "ok" });
      return result;
    } catch (err) {
      const status = err && (err.statusCode || err.status || (err.response && err.response.status));
      appendAuditEntry({ label, tool: toolName, resource, outcome: status === 403 ? "denied" : "error" });
      return toToolErrorResult(err);
    }
  };
}

/**
 * Build a fresh McpServer instance wired to the given identity. Takes the
 * whole `identity` object (not a bare `session`) so every tool
 * implementation reads `identity.session` live at call time — required for
 * Task 4's retry-after-reauth to actually use the new session instead of a
 * stale one captured when this function ran. Kept as a function of
 * `identity` — not module-level global wiring — so Story 8.3 can call this
 * per identity/token without a rewrite.
 */
function buildMcpServer(identity) {
  const server = new McpServer({ name: "solid-pod-agent", version: "0.1.0" });

  server.registerTool(
    "solid_read_resource",
    {
      description:
        "Read a Solid Pod resource. Returns text content. Works for RDF " +
        "documents (Turtle/JSON-LD) and text-based files.",
      inputSchema: { url: z.string().url() },
    },
    safeHandler("solid_read_resource", identity, "url", async ({ url }) => {
      const file = await podClient.readFile(url, identity.session);
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
    safeHandler("solid_write_resource", identity, "url", async ({ url, content, contentType }) => {
      await podClient.writeFile(url, content, contentType, identity.session);
      return { content: [{ type: "text", text: `Wrote ${url}` }] };
    })
  );

  server.registerTool(
    "solid_list_container",
    {
      description: "List the resources directly inside a Pod container (folder URL).",
      inputSchema: { containerUrl: z.string().url() },
    },
    safeHandler("solid_list_container", identity, "containerUrl", async ({ containerUrl }) => {
      const urls = await podClient.listContainer(containerUrl, identity.session);
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
    safeHandler("solid_get_permissions", identity, "resourceUrl", async ({ resourceUrl }) => {
      const access = await wacManager.listAgentsWithAccess(resourceUrl, identity.session);
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
    safeHandler("solid_grant_access", identity, "resourceUrl", async ({ resourceUrl, agentWebId, read, write, append, control, scope }) => {
      await wacManager.grantAccess(
        resourceUrl,
        agentWebId,
        { read, write, append, control },
        identity.session,
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
    safeHandler("solid_revoke_access", identity, "resourceUrl", async ({ resourceUrl, agentWebId }) => {
      await wacManager.revokeAccess(resourceUrl, agentWebId, identity.session);
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
    safeHandler("solid_set_public_access", identity, "resourceUrl", async ({ resourceUrl, read, write, append, control, scope }) => {
      await wacManager.setPublicAccess(resourceUrl, { read, write, append, control }, identity.session, {
        scope,
      });
      return {
        content: [{ type: "text", text: `Updated public access on ${resourceUrl}` }],
      };
    })
  );

  return server;
}

/**
 * Boot every configured identity's Solid session, once, at startup.
 * Story 8.3 AC3: N identities, each logged in with keepAlive:true and
 * reused for the process lifetime. AC3: if ANY identity fails to log in,
 * the whole process refuses to start — a half-authenticated server that
 * silently serves 3 of 4 people is worse than one that refuses to start.
 *
 * @returns {Promise<Map<string, {session: object, label: string, webId: string}>>}
 */
async function bootIdentities() {
  const configured = loadIdentities();
  const identities = new Map();

  for (const [slug, id] of configured) {
    let session;
    try {
      session = await getAgentSession({
        clientId: id.clientId,
        clientSecret: id.clientSecret,
        oidcIssuer: process.env.SOLID_OIDC_ISSUER,
        keepAlive: true,
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(
        `[solid-pod-agent mcp-server] fatal: Solid login failed for identity "${id.label}":`,
        err.message
      );
      process.exit(1);
    }

    if (session.info.webId !== id.webId) {
      // Defensive: catches a stale/typo'd webId in identities.json before it
      // causes confusing tool errors later.
      // eslint-disable-next-line no-console
      console.error(
        `[solid-pod-agent mcp-server] fatal: identity "${id.label}" logged in as ` +
          `${session.info.webId}, not the configured webId. Fix identities.json.`
      );
      process.exit(1);
    }

    // auth.js already logs "authenticated as <webId>" per login. That alone
    // can't be correlated to a person when N identities boot, so name the
    // label here too — label and WebID are both safe to log (AC7); the slug,
    // client id and secret are not.
    // eslint-disable-next-line no-console
    console.log(
      `[solid-pod-agent mcp-server] identity "${id.label}" ready as ${session.info.webId}`
    );

    // clientId/clientSecret are kept in-memory only, never logged, so Task
    // 4's one-shot re-auth-on-401 can re-login this identity later without
    // re-reading identities.json. They already lived in `id` (from
    // loadIdentities()) for the duration of this loop; the only change is
    // holding onto them past boot.
    identities.set(slug, {
      session,
      label: id.label,
      webId: session.info.webId,
      clientId: id.clientId,
      clientSecret: id.clientSecret,
    });
  }

  return identities;
}

/**
 * Story 8.5 Task 4: on a 401 that indicates the process-lifetime Solid
 * session has died (token revoked/expired despite `keepAlive`), re-login
 * once for that identity and mutate `identity.session` in place so every
 * holder of the shared `identities` Map — including /healthz and the next
 * request's freshly-built tool server — immediately sees the new session.
 * Bounded to exactly one attempt by construction: this function is only
 * ever called once per failed call, from inside safeHandler's single retry
 * branch (see below) — there is no loop here or in the caller.
 */
async function reauthIdentity(identity) {
  // eslint-disable-next-line no-console
  console.log(
    `[solid-pod-agent mcp-server] session for identity "${identity.label}" looks expired (401) — re-authenticating once`
  );
  const session = await getAgentSession({
    clientId: identity.clientId,
    clientSecret: identity.clientSecret,
    oidcIssuer: process.env.SOLID_OIDC_ISSUER,
    keepAlive: true,
  });
  identity.session = session;
  return session;
}

async function main() {
  const identities = await bootIdentities();

  const app = createMcpExpressApp({ host: HOST, allowedHosts: ALLOWED_HOSTS });

  // AC4.2: exactly one proxy hop (nginx-gateway) sits in front of this, so
  // trust exactly one. `true` would trust the whole X-Forwarded-For chain,
  // which a caller can forge — every attacker would then get to pick their
  // own rate-limit bucket, and the limiter below would be decorative.
  app.set("trust proxy", 1);

  // AC4.4: bound how long a single request may occupy a transport+server
  // pair. Fires only if nothing has been sent yet.
  app.use((req, res, next) => {
    res.setTimeout(REQUEST_TIMEOUT_MS, () => {
      if (!res.headersSent) {
        res.status(504).json({
          jsonrpc: "2.0",
          error: { code: -32001, message: "Request timed out." },
          id: null,
        });
      }
    });
    next();
  });

  // Stateless mode: a fresh transport + server per request. There is no
  // session to disambiguate concurrent clients in stateless mode, so a
  // single shared transport would let concurrent requests interleave state
  // incorrectly — see Dev Notes "Concurrency trap". The cost (re-registering
  // 7 tool definitions per call) is trivial. Story 8.3: the slug in the path
  // picks which identity's already-authenticated session backs this request.
  // AC4: reveal nothing about whether a slug exists, how many identities are
  // configured, or any WebID. Do not log the attempted slug — it may be a
  // near-miss of a real secret URL, and logging it would copy that secret
  // into the log file.
  const notFound = (req, res) => {
    // eslint-disable-next-line no-console
    console.warn("[solid-pod-agent mcp-server] rejected request to unknown MCP slug");
    res.status(404).json({
      jsonrpc: "2.0",
      error: { code: -32601, message: "Not found." },
      id: null,
    });
  };

  // AC4.3. Two independent stores, both keyed on client IP (via `trust
  // proxy: 1` above, so this is the real caller and not the nginx
  // container). Separate stores matter: if unknown-slug guesses shared the
  // valid-traffic bucket, a guessing attacker could exhaust a legitimate
  // user's budget and lock them out.
  const mcpLimiter = rateLimit({
    windowMs: RATE_LIMIT_WINDOW_MS,
    limit: RATE_LIMIT_MAX,
    standardHeaders: "draft-7",
    legacyHeaders: false,
    handler: rateLimitHandler,
  });

  // Tighter, because guessing a 22-char slug is the only reason to hit this
  // path repeatedly — there is no legitimate high-volume use of a wrong URL.
  // No standardHeaders here: this limiter guards the guessing path, and
  // RateLimit-Policy/RateLimit would hand a slug-guesser exact remaining-quota
  // telemetry to pace their guesses just under the threshold.
  const unknownSlugLimiter = rateLimit({
    windowMs: RATE_LIMIT_WINDOW_MS,
    limit: RATE_LIMIT_MAX_UNKNOWN,
    standardHeaders: false,
    legacyHeaders: false,
    handler: rateLimitHandler,
  });

  app.use("/mcp", mcpLimiter);

  app.post("/mcp/:slug", async (req, res) => {
    const identity = identities.get(req.params.slug);

    if (!identity) {
      // Run the tighter limiter only once we know the slug is unknown, so
      // valid callers never consume the guessing budget.
      unknownSlugLimiter(req, res, () => notFound(req, res));
      return;
    }

    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    const server = buildMcpServer(identity);

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
  // Route through the tighter limiter first: GET/DELETE on an unknown slug is
  // the same guessing surface as POST, and without this it ran at the loose
  // 120/min budget regardless of slug validity.
  app.get("/mcp/:slug", (req, res) => {
    if (!identities.has(req.params.slug)) {
      unknownSlugLimiter(req, res, () => notSupported(req, res));
      return;
    }
    notSupported(req, res);
  });
  app.delete("/mcp/:slug", (req, res) => {
    if (!identities.has(req.params.slug)) {
      unknownSlugLimiter(req, res, () => notSupported(req, res));
      return;
    }
    notSupported(req, res);
  });

  // A request to bare /mcp (8.2's removed endpoint) or /mcp/ with an empty
  // slug segment matches no :slug route, so without this it would fall
  // through to Express's default HTML 404 — a different response shape than
  // the unknown-slug path, which is itself a signal. AC4 says every miss on
  // this surface reveals nothing, so give them all the same generic body.
  // These are miss paths too, so they get the tighter budget for the same
  // reason the unknown-slug path does.
  app.all("/mcp", (req, res) => unknownSlugLimiter(req, res, () => notFound(req, res)));
  app.all("/mcp/", (req, res) => unknownSlugLimiter(req, res, () => notFound(req, res)));

  // Unauthenticated health check for the Docker/nginx checks. Story 8.4 AC8:
  // 8.2 shipped a static {ok:true} and both 8.2 and 8.3's reviews deferred
  // the decision here — a compose healthcheck backed by a static value
  // reports healthy even when every Solid session has died. Decided:
  // session-aware, using the same `session.info.isLoggedIn` auth.js already
  // checks right after login. Aggregate boolean only — never a per-identity
  // breakdown, WebID, or identity count. This endpoint is public as of 8.4,
  // and none of those is something to hand out anonymously; "some session
  // is dead" is operationally useful, "which one" is not something an
  // unauthenticated caller needs. `isLoggedIn` reflects the SDK's own
  // client-side state (flips false on an expired/revoked token it has
  // noticed, not necessarily the instant CSS invalidates it) — a
  // best-effort liveness signal, not a live round-trip to CSS on every poll
  // (that would turn a 15s healthcheck into 15s-interval load against CSS
  // for a value that mostly doesn't change).
  // Deliberately NOT rate-limited and deliberately outside /mcp: the Docker
  // healthcheck polls it every 15s, and a limiter here would eventually mark
  // a perfectly healthy container unhealthy and restart it.
  app.get("/healthz", (req, res) => {
    let allSessionsAlive;
    try {
      // No identities configured is not healthy — .every() on an empty map
      // vacuously returns true, which would hide the exact failure this AC
      // exists to catch (e.g. identities.json missing or unreadable).
      allSessionsAlive =
        identities.size > 0 &&
        [...identities.values()].every((identity) => identity.session.info.isLoggedIn);
    } catch (err) {
      // Any unexpected shape (session field missing, SDK throw) means we
      // can't confirm liveness — treat as unhealthy rather than 500ing.
      // eslint-disable-next-line no-console
      console.error("[solid-pod-agent mcp-server] /healthz check failed:", err.message);
      allSessionsAlive = false;
    }
    res.status(allSessionsAlive ? 200 : 503).json({ ok: allSessionsAlive });
  });

  app.listen(PORT, HOST, () => {
    // eslint-disable-next-line no-console
    console.log(
      `[solid-pod-agent mcp-server] listening on http://${HOST}:${PORT}/mcp/<slug> ` +
        `(${identities.size} ${identities.size === 1 ? "identity" : "identities"} configured)`
    );
  });
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[solid-pod-agent mcp-server] fatal:", err.message);
  process.exit(1);
});
