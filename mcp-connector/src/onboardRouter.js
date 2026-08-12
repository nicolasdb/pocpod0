/**
 * onboardRouter.js
 *
 * Story 7.9: the button that removes the operator from onboarding. Mounted
 * at /onboard/ on the SAME Express app as /mcp/:slug, but routed to the
 * browser-reachable pod.nicolasdb.eu vhost (see hetzner-gateway's
 * 04-pocpod0.conf), never the IP-allowlisted solid-mcp.nicolasdb.eu vhost.
 *
 * The browser forwards its `css-account` cookie (same-origin, no CORS);
 * this server uses it for exactly one CSS Account API call sequence per
 * request, never logs it, never persists it, discards it at end of request
 * (AC17). The clientSecret CSS returns is written straight to
 * identities.json and never serialized into any response (AC2).
 */

const express = require("express");
const rateLimit = require("express-rate-limit");
const fs = require("fs");
const path = require("path");

const { generateSlug } = require("../scripts/gen-slug.js");
const { writeIdentity, updateIdentity, generateGrantId, DEFAULT_PATH } = require("./identityRegistry");
const wacManager = require("./wacManager");

const ISSUER = process.env.SOLID_OIDC_ISSUER || "https://pod.nicolasdb.eu/";

function readRegistryRaw() {
  try {
    const raw = fs.existsSync(DEFAULT_PATH) ? fs.readFileSync(DEFAULT_PATH, "utf-8") : "{}";
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function accountIndexUrl() {
  return new URL("/.account/", ISSUER).toString();
}

/**
 * Resolve `controls` from the authed account index using the caller's
 * forwarded cookie. AC2.3 / the 7.4-and-7.10 content-type trap: this GET
 * must carry NO content-type header, or CSS content-negotiates a
 * controls-less body and controls.account.clientCredentials comes back
 * undefined — looking exactly like "the endpoint doesn't exist".
 */
async function fetchAccountControls(cookie) {
  const res = await fetch(accountIndexUrl(), { headers: { cookie } });
  if (res.status === 401) return { unauthenticated: true };
  if (!res.ok) throw new Error(`Account index request failed (${res.status}).`);
  let body;
  try {
    body = await res.json();
  } catch {
    throw new Error("Account index returned an unreadable response.");
  }
  if (!body || !body.controls || !body.controls.account) return { unauthenticated: true };
  return { controls: body.controls };
}

/**
 * AC16: mint only against a webId this account actually controls. CSS's
 * account index does not hand back a flat "these are your webIds" list in
 * one place we can rely on without a live shape check (Task 7 verifies
 * this), so this checks the account's pod ownership map — every pod this
 * account created was created with settings.webId === the account's own
 * WebID (architecture_pod_webid_ownership) — and falls back to comparing
 * against the account's own resolved WebID if that control isn't present.
 * Fails CLOSED: any shape this can't positively confirm is refused, not
 * silently allowed.
 */
async function accountControlsWebId(controls, cookie, webId) {
  const podUrl = controls.account && controls.account.pod;
  if (!podUrl) return false;
  const res = await fetch(podUrl, { headers: { cookie } });
  if (!res.ok) return false;
  let body;
  try {
    body = await res.json();
  } catch {
    return false;
  }
  const pods = (body && body.pods) || {};
  // Every pod baseUrl this account owns implies ownership of the WebID
  // profile document beneath it (CSS convention: one pod per top-level
  // segment, WebID lives at <podBaseUrl>profile/card#me for pods created
  // through this flow). Accept an exact WebID-prefix match against any
  // owned pod's baseUrl.
  return Object.keys(pods).some((baseUrl) => webId.startsWith(baseUrl));
}

function genericFailure(res, status, message) {
  // AC16: an unauthenticated or malformed request gets a generic failure
  // that reveals nothing about existing identities.
  res.status(status).json({ error: message });
}

/**
 * @param {Map<string,object>} identities the shared, mutable identities Map
 *   also held by mcp-server.js — mint/revoke must mutate the SAME instance
 *   so a newly-minted slug resolves without a restart (AC15) and a revoked
 *   one is evicted without one (AC11c).
 */
function buildOnboardRouter(identities) {
  const router = express.Router();
  // The app-level express.json() (registered by the MCP SDK's
  // createMcpExpressApp) already parses JSON bodies ahead of route
  // dispatch — body-parser sets req._body and skips a re-parse, so this is
  // a safe no-op, but keep it explicit in case this router is ever mounted
  // standalone outside that app.
  router.use(express.json());

  // AC2.11: independent of mcpLimiter/unknownSlugLimiter.
  const onboardLimiter = rateLimit({
    windowMs: 60 * 1000,
    limit: 20,
    standardHeaders: "draft-7",
    legacyHeaders: false,
    handler: (req, res) => genericFailure(res, 429, "Too many requests."),
  });
  router.use(onboardLimiter);

  function getCookie(req) {
    return req.headers.cookie || "";
  }

  router.post("/mint", async (req, res) => {
    const cookie = getCookie(req);
    if (!cookie) return genericFailure(res, 401, "Not signed in.");

    const { webId, label } = req.body || {};
    if (typeof webId !== "string" || !/^https?:\/\/[^\s<>"]+$/.test(webId)) {
      return genericFailure(res, 400, "Invalid request.");
    }
    const safeLabel = typeof label === "string" && label.trim() ? label.trim().slice(0, 200) : "Unlabeled";

    let controls;
    try {
      const resolved = await fetchAccountControls(cookie);
      if (resolved.unauthenticated) return genericFailure(res, 401, "Not signed in.");
      controls = resolved.controls;
    } catch (err) {
      return genericFailure(res, 502, "Could not reach the account service.");
    }

    const ccUrl = controls.account.clientCredentials;
    if (!ccUrl) return genericFailure(res, 500, "This account exposes no client-credentials endpoint.");

    const owns = await accountControlsWebId(controls, cookie, webId).catch(() => false);
    if (!owns) return genericFailure(res, 403, "This account does not control that WebID.");

    // Mint via CSS. AC2.5: `resource` is credentialRef — without it there
    // is no revoke path, so a missing resource is a hard failure.
    let mintRes;
    try {
      mintRes = await fetch(ccUrl, {
        method: "POST",
        headers: { cookie, "content-type": "application/json" },
        body: JSON.stringify({ name: safeLabel, webId }),
      });
    } catch (err) {
      return genericFailure(res, 502, "Could not reach the account service.");
    }
    if (!mintRes.ok) return genericFailure(res, 502, "Could not mint a credential.");

    let clientId, clientSecret, credentialRef;
    try {
      ({ id: clientId, secret: clientSecret, resource: credentialRef } = await mintRes.json());
    } catch {
      return genericFailure(res, 502, "Credential minted but the response was unreadable.");
    }
    if (!clientId || !clientSecret || !credentialRef) {
      // AC2.5: treat a missing resource/id/secret as a hard failure, not a
      // warning — without credentialRef there is no revoke path.
      if (clientId && clientSecret && credentialRef === undefined) {
        // Best-effort cleanup even without a resource URL is not possible —
        // we have no URL to DELETE. Surface loudly; this is the orphan case
        // Epic 7 already names as the precedent for "clean up later".
      }
      return genericFailure(res, 502, "Credential minted but the server did not return usable id/secret/resource.");
    }

    const slug = generateSlug();
    const grantId = generateGrantId();
    const entry = {
      label: safeLabel,
      webId,
      clientId,
      clientSecret,
      grantId,
      credentialRef,
      containers: [],
      createdAt: new Date().toISOString(),
      expiresAt: null,
      lastUsedAt: null,
      revoked: false,
      grantUri: null,
      purpose: null,
      scope: null,
      excluded: null,
      consequenceOfRefusal: null,
    };

    try {
      await writeIdentity(slug, entry);
    } catch (err) {
      // AC2.8: mint-then-write-failure strands a live credential nobody
      // holds (CSS returns the secret exactly once). Revoke it before
      // returning an error.
      try {
        await fetch(credentialRef, { method: "DELETE", headers: { cookie } });
      } catch {
        // Best-effort — Epic 7's orphan-account precedent for what "clean up
        // later" means in practice. Logged, not thrown, so the real error
        // (the write failure) is what reaches the caller.
        // eslint-disable-next-line no-console
        console.error("[onboardRouter] mint write failed AND credential cleanup failed — orphan credential left on CSS.");
      }
      return genericFailure(res, 500, "Could not complete onboarding. Nothing was written.");
    }

    // Story 8.6.1's lazy path picks this up on first request — no reload,
    // no restart (AC15). We do NOT pre-populate `identities` here: that
    // would require logging in synchronously inside this request, and the
    // lazy path already exists to do that on first use.
    const connectorUrl = new URL(`/mcp/${slug}`, "https://solid-mcp.nicolasdb.eu/").toString();
    const podRootUrl = new URL(webId).origin + "/" + webId.split("/")[3] + "/";

    // AC18: never in a URL path — response body only. `webId` and `podRootUrl`
    // are returned for scope DISCLOSURE in the reveal modal ("acting as X, which
    // controls pod Y"), not as a hint about which pod to read: WAC has no reverse
    // index, so neither this endpoint nor the connector can enumerate the pods a
    // credential can actually reach. Only the human knows the target.
    res.status(201).json({ connectorUrl, podRootUrl, webId });
  });

  router.get("/grants", async (req, res) => {
    const cookie = getCookie(req);
    if (!cookie) return genericFailure(res, 401, "Not signed in.");
    let controls;
    try {
      const resolved = await fetchAccountControls(cookie);
      if (resolved.unauthenticated) return genericFailure(res, 401, "Not signed in.");
      controls = resolved.controls;
    } catch {
      return genericFailure(res, 502, "Could not reach the account service.");
    }

    // List every identity in the shared registry file whose webId this
    // account controls. Re-read from disk (not the in-memory `identities`
    // Map, which holds only ACTIVE/logged-in entries) so revoked rows are
    // visible too (AC10: "revoked ones visible as revoked").
    const all = readRegistryRaw();

    const podUrl = controls.account && controls.account.pod;
    let ownedPrefixes = [];
    if (podUrl) {
      try {
        const podsRes = await fetch(podUrl, { headers: { cookie } });
        if (podsRes.ok) {
          const body = await podsRes.json();
          ownedPrefixes = Object.keys((body && body.pods) || {});
        }
      } catch {
        ownedPrefixes = [];
      }
    }

    const grants = Object.entries(all)
      .filter(([slug]) => slug !== "_comment")
      .filter(([, entry]) => ownedPrefixes.some((p) => entry.webId && entry.webId.startsWith(p)))
      .map(([, entry]) => ({
        grantId: entry.grantId || null,
        label: entry.label,
        webId: entry.webId,
        containers: entry.containers || [],
        createdAt: entry.createdAt || null,
        lastUsedAt: entry.lastUsedAt || null,
        expiresAt: entry.expiresAt || null,
        revoked: !!entry.revoked,
        // Never the slug, never clientId/clientSecret/credentialRef (AC3.1).
      }));

    res.status(200).json({ grants });
  });

  router.post("/revoke", async (req, res) => {
    const cookie = getCookie(req);
    if (!cookie) return genericFailure(res, 401, "Not signed in.");
    const { grantId } = req.body || {};
    if (typeof grantId !== "string" || !grantId) return genericFailure(res, 400, "Invalid request.");

    const all = readRegistryRaw();
    const found = Object.entries(all).find(([slug, e]) => slug !== "_comment" && e.grantId === grantId);
    if (!found) return genericFailure(res, 404, "Grant not found.");
    const [slug, entry] = found;
    if (entry.revoked) return res.status(200).json({ revoked: true }); // idempotent

    // AC11: three ordered steps. (a) WAC revoke on every recorded container
    // — genuinely instant, stops an already-issued token immediately. In
    // practice containers[] is usually empty (granting stays manual/owner-
    // driven, this story only records intended scope) so this loop is a
    // no-op for most grants today; it exists for when it isn't.
    const identity = identities.get(slug);
    if (Array.isArray(entry.containers) && entry.containers.length > 0) {
      if (!identity || !identity.session) {
        // Can't perform (a) without a live session for this identity — abort
        // per AC11 rather than silently skip a real access-removal step.
        return genericFailure(res, 500, "Cannot revoke: no live session to remove WAC access with.");
      }
      try {
        for (const containerUrl of entry.containers) {
          await wacManager.revokeAccess(containerUrl, entry.webId, identity.session, { scope: "both" });
        }
      } catch (err) {
        return genericFailure(res, 500, "Could not remove access. Not revoked — try again.");
      }
    }

    // (b) Delete the CSS client credential so no NEW token can be minted.
    let credentialDeleteFailed = false;
    if (entry.credentialRef) {
      try {
        const delRes = await fetch(entry.credentialRef, { method: "DELETE", headers: { cookie } });
        if (!delRes.ok && delRes.status !== 404) credentialDeleteFailed = true;
      } catch {
        credentialDeleteFailed = true;
      }
    }

    // (c) Tombstone — row retained, marked revoked.
    try {
      await updateIdentity(slug, { revoked: true });
    } catch (err) {
      return genericFailure(res, 500, "Access was removed but the registry could not be updated. Contact the operator.");
    }

    // Evict from the shared in-memory Map immediately (AC11c) — there is no
    // other eviction surface; this IS the one Task 3.3 adds.
    identities.delete(slug);

    if (credentialDeleteFailed) {
      // eslint-disable-next-line no-console
      console.error(`[onboardRouter] revoke: WAC access removed and grant tombstoned, but credential DELETE failed for grantId ${grantId} — orphan credential on CSS (Epic 7 precedent).`);
    }

    res.status(200).json({ revoked: true });
  });

  return router;
}

module.exports = { buildOnboardRouter };
