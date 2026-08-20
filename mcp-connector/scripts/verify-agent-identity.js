#!/usr/bin/env node
/**
 * verify-agent-identity.js
 *
 * Story 7.12. Offline, no network, no live pod — drives RealBackend's
 * createAgentIdentity() against a fake CSS to prove the ownership-challenge
 * path actually works, because that path is the ONE this deployment always
 * takes (config/identity/pod/static.json => one root storage => isCreator is
 * always false => TokenOwnershipValidator always runs).
 *
 * Run: node scripts/verify-agent-identity.js
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const POD_API = path.join(__dirname, "../../backoffice/pod-api.js");
const ISSUER = "https://pod.nicolasdb.eu/";
const POD = "https://pod.nicolasdb.eu/nicolas_claude/";
const WEBID = POD + "agents/smoke#me";
const PROFILE = POD + "agents/smoke";
const TOKEN = "d8af2474-a315-4cb1-a124-4ba2e123f94d";

/**
 * Load pod-api.js as an ES module without a browser. It imports the Inrupt
 * libs from esm.sh at call time only (inside loadLibs), so evaluating the
 * module body is safe offline; we construct RealBackend directly via a tiny
 * shim rather than going through Solid.realClient().
 */
// The module-level `fetch` pod-api.js sees. Late-bound through this holder so a
// test can swap the mock AFTER the module has been evaluated — binding the
// sandbox to globalThis.fetch by value would freeze in the real one.
const anonFetch = { fn: null };

async function loadRealBackendClass() {
  const src = fs.readFileSync(POD_API, "utf-8");
  // Strip the export keywords so this can be evaluated as a plain script and
  // the classes captured off the sandbox global.
  const script = src
    .replace(/^export\s+(const|function|class)\s/gm, "$1 ")
    .replace(/^export\s+\{[^}]*\};?$/gm, "")
    + "\n;globalThis.__RealBackend = RealBackend;";
  const sandbox = {
    console, URL, Blob, setTimeout, clearTimeout,
    fetch: (...args) => anonFetch.fn(...args),
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  new vm.Script(script, { filename: "pod-api.js" }).runInContext(sandbox);
  return sandbox.__RealBackend;
}

function makeBackend(RealBackend, world) {
  // Authed fetch (session) — writes to the fake pod.
  const authedFetch = async (url, opts = {}) => {
    const method = (opts.method || "GET").toUpperCase();
    if (method === "PUT") {
      world.docs[url] = opts.body;
      world.putLog.push(url);
      return { ok: true, status: 205, text: async () => "" };
    }
    if (method === "GET") {
      const body = world.docs[url];
      return body === undefined
        ? { ok: false, status: 404, text: async () => "" }
        : { ok: true, status: 200, text: async () => body };
    }
    return { ok: true, status: 205, text: async () => "" };
  };

  const session = { fetch: authedFetch, info: { webId: POD + "profile/card#me" } };
  const backend = new RealBackend({ sc: {} }, session);

  // Account-API controls, pre-resolved so _accountControls() short-circuits.
  backend._controls = { account: { webId: "https://pod.nicolasdb.eu/.account/account/acct/webid/" } };

  // Unauthenticated/global fetch: the anonymous verify GET, and the link POSTs.
  anonFetch.fn = async (url, opts = {}) => {
    const u = String(url);
    const method = (opts.method || "GET").toUpperCase();

    if (method === "POST" && u.includes("/webid/")) {
      world.linkAttempts.push(world.docs[PROFILE]);
      const doc = world.docs[PROFILE] || "";
      const proven = doc.includes(`oidcIssuerRegistrationToken "${TOKEN}"`);
      if (!proven) {
        return {
          ok: false, status: 400,
          clone() { return this; },
          json: async () => ({
            message: `Verification token not found. Please add the RDF triple <${WEBID}> `
              + `<http://www.w3.org/ns/solid/terms#oidcIssuerRegistrationToken> "${TOKEN}". `
              + `to the WebID document at ${PROFILE} to prove it belongs to you.`,
          }),
        };
      }
      return {
        ok: true, status: 200,
        json: async () => ({ resource: "https://pod.nicolasdb.eu/.account/account/acct/webid/xyz/", webId: WEBID, oidcIssuer: ISSUER }),
      };
    }

    // Anonymous verify-public GET — only succeeds if a public-read .acl exists.
    if (method === "GET") {
      if (!world.acls[u]) return { ok: false, status: 401, text: async () => "" };
      const body = world.docs[u];
      return body === undefined
        ? { ok: false, status: 404, text: async () => "" }
        : { ok: true, status: 200, text: async () => body };
    }
    return { ok: false, status: 405 };
  };

  // Record ACL writes rather than re-testing _writeAcl (7.3 owns that).
  backend._writeAcl = async (url, grant) => {
    assert.strictEqual(grant.public.read, true, "profile ACL must grant public read");
    world.acls[url] = grant;
    return true;
  };
  backend._cleanupOrphanDoc = async (url) => { world.deleted.push(url); delete world.docs[url]; };
  return backend;
}

async function main() {
  const RealBackend = await loadRealBackendClass();
  let passed = 0;

  // The ownership-challenge path: first link 400s asking for a proof triple,
  // the flow adds it, retries, and strips it back out. One user action.
  {
    const world = { docs: {}, acls: {}, deleted: [], putLog: [], linkAttempts: [] };
    const backend = makeBackend(RealBackend, world);
    const out = await backend.createAgentIdentity(POD, "smoke");

    assert.strictEqual(out.webId, WEBID);
    assert.strictEqual(world.linkAttempts.length, 2, "should link twice: challenge then proof");
    assert.ok(!world.linkAttempts[0].includes("RegistrationToken"), "1st attempt carries no token");
    assert.ok(world.linkAttempts[1].includes(`oidcIssuerRegistrationToken "${TOKEN}"`), "2nd attempt carries the proof triple");
    assert.ok(!world.docs[PROFILE].includes("RegistrationToken"), "token stripped from the published doc afterwards");
    assert.ok(world.docs[PROFILE].includes(`solid:oidcIssuer <${ISSUER}>`), "issuer triple survives");
    assert.deepStrictEqual(world.deleted, [], "nothing cleaned up on the success path");
    console.log("PASS: ownership challenge answered automatically, token stripped after");
    passed++;
  }

  // A non-token link failure must NOT loop — it cleans up and reports the step.
  {
    const world = { docs: {}, acls: {}, deleted: [], putLog: [], linkAttempts: [] };
    const backend = makeBackend(RealBackend, world);
    const realFetch = anonFetch.fn;
    anonFetch.fn = async (url, opts = {}) => {
      const u = String(url);
      if ((opts.method || "GET").toUpperCase() === "POST" && u.includes("/webid/")) {
        world.linkAttempts.push(1);
        return { ok: false, status: 400, clone() { return this; }, json: async () => ({ message: "is already registered to this account." }) };
      }
      return realFetch(url, opts);
    };
    await assert.rejects(
      () => backend.createAgentIdentity(POD, "smoke"),
      (e) => /^link: /.test(e.message) && /already registered/.test(e.message),
      "should surface a step-labelled link error"
    );
    assert.strictEqual(world.linkAttempts.length, 1, "must not retry a non-token failure");
    assert.deepStrictEqual(world.deleted, [PROFILE], "orphan doc cleaned up");
    console.log("PASS: a non-token link failure is step-labelled, not retried, and cleaned up");
    passed++;
  }

  // Slug validation rejects rather than silently sanitizing (AC4).
  {
    const world = { docs: {}, acls: {}, deleted: [], putLog: [], linkAttempts: [] };
    const backend = makeBackend(RealBackend, world);
    await assert.rejects(() => backend.createAgentIdentity(POD, "bad name"), /letters, numbers/);
    assert.deepStrictEqual(world.putLog, [], "nothing written for an invalid name");
    console.log("PASS: an invalid agent name is rejected before anything is written");
    passed++;
  }

  console.log(`\n${passed} passed.`);
}

main().catch((e) => { console.error("FAIL", e); process.exit(1); });
