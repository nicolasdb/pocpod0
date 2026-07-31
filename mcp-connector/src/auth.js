/**
 * auth.js
 *
 * Authenticates as the AGENT's own WebID using a Solid client-credentials
 * token (id + secret), which is how Community Solid Server (CSS) — and most
 * self-hosted Solid Pods — let a script/bot log in without a browser.
 *
 * How to get an id/secret (CSS):
 *   1. Create a separate account for the agent (don't reuse a human account).
 *   2. Go to <your-css-instance>/.account/, log in, open "Client credentials",
 *      give it a name, pick the agent's WebID, and generate a token.
 *   3. Store the returned `secret` immediately — the server never shows it again.
 * See references/architecture-and-checklist.md for the full walkthrough,
 * including how to do this programmatically instead of via the UI.
 *
 * IMPORTANT: id/secret let the holder act fully as that WebID. Treat them
 * like a password: never commit them, never log them, load from env only.
 */

const path = require("path");
const { Session } = require("@inrupt/solid-client-authn-node");
// Path-explicit so it doesn't depend on process.cwd() — bare dotenv.config()
// resolves .env relative to cwd, which silently finds nothing when this
// module is required from another directory (e.g. `npm run mcp` invoked
// elsewhere, or this sandbox where cwd is `/`).
require("dotenv").config({ path: path.join(__dirname, "..", ".env") });

/**
 * @param {object} [opts]
 * @param {string} [opts.clientId]     defaults to process.env.SOLID_CLIENT_ID
 * @param {string} [opts.clientSecret] defaults to process.env.SOLID_CLIENT_SECRET
 * @param {string} [opts.oidcIssuer]   defaults to process.env.SOLID_OIDC_ISSUER
 * @param {boolean} [opts.keepAlive]   auto-refresh in the background (default true).
 *   Set to false for short-lived invocations (e.g. a cron job or serverless
 *   call) where you'll log in fresh each run instead of holding a long-lived
 *   process.
 * @returns {Promise<import('@inrupt/solid-client-authn-node').Session>}
 */
async function getAgentSession(opts = {}) {
  const clientId = opts.clientId || process.env.SOLID_CLIENT_ID;
  const clientSecret = opts.clientSecret || process.env.SOLID_CLIENT_SECRET;
  const oidcIssuer = opts.oidcIssuer || process.env.SOLID_OIDC_ISSUER;
  const keepAlive = opts.keepAlive !== undefined ? opts.keepAlive : true;

  if (!clientId || !clientSecret || !oidcIssuer) {
    throw new Error(
      "Missing SOLID_CLIENT_ID / SOLID_CLIENT_SECRET / SOLID_OIDC_ISSUER. " +
        "Copy .env.example to .env and fill these in."
    );
  }

  const session = new Session({ keepAlive });

  await session.login({ clientId, clientSecret, oidcIssuer });

  if (!session.info.isLoggedIn) {
    throw new Error(
      "Solid login did not succeed — check the client id/secret/issuer, " +
        "and that the token hasn't been deleted from the account page."
    );
  }

  // Handy to log once at startup so you can confirm which identity is active.
  // eslint-disable-next-line no-console
  console.log(`[solid-pod-agent] authenticated as ${session.info.webId}`);

  return session;
}

/** Always call this when a script/process is done, to clean up. */
async function closeSession(session) {
  if (session) await session.logout();
}

module.exports = { getAgentSession, closeSession };
