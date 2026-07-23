// pod-api.js — one interface, two backends.
//   RealBackend  → live Community Solid Server via the Inrupt libraries
//   DemoBackend  → in-memory pod so the whole experience is explorable
//                  even when an OIDC redirect can't complete (e.g. in a preview)
//
// The app never talks to the libraries directly — it holds a `client` with:
//   list(url) · readText(url) · writeText(url,text,type) · makeFolder(url)
//   remove(url) · getAccess(url) · setAgentAccess(url,webId,modes)
//   setPublicAccess(url,modes) · turtleAcl(url)
//
// Loaded once, from esm.sh. At a proper URL the real path just works.

const ISSUER = "https://pod.nicolasdb.eu/";
const CLIENT_NAME = "Pod Backoffice";
// CSS token endpoint a bot uses to exchange a client credential for a DPoP access
// token. Surfaced in the "how to connect" recipe (Story 7.4).
export const TOKEN_ENDPOINT = new URL("/.oidc/token", ISSUER).href;

let _libs = null;

// In-progress account registrations, keyed by podName, so a retry after a
// mid-flow failure resumes on the same CSS account instead of orphaning it
// (see Solid.registerAccount). Lives for the page session only.
const _pendingRegistrations = {};

// Best-effort human-readable detail from a failed CSS JSON-API response.
async function _errDetail(res) {
  try {
    const body = await res.clone().json();
    if (body && (body.message || body.name)) return body.message || body.name;
  } catch (e) { /* non-JSON body */ }
  return `HTTP ${res.status}`;
}

async function loadLibs() {
  if (_libs) return _libs;
  // `?bundle` forces esm.sh to inline the whole dependency subtree into one file.
  // Required as of 2026-07-21: without it, esm.sh's default per-module resolution
  // pulls a newer @inrupt/oidc-client-ext against the pinned old @inrupt/oidc-client,
  // and that UMD package only exposes a `default` export under esm.sh's CJS-interop,
  // breaking named imports (`SessionMonitor`/`UserManager`) deep in the OIDC chain.
  const [authn, sc] = await Promise.all([
    import("https://esm.sh/@inrupt/solid-client-authn-browser@2.3.0?bundle"),
    import("https://esm.sh/@inrupt/solid-client@2.1.0?bundle"),
  ]);
  _libs = { authn, sc };
  return _libs;
}

// ---------- shape helpers shared by both backends ----------
export const MODES = ["read", "append", "write", "control"];
export function emptyModes() {
  return { read: false, append: false, write: false, control: false };
}
function baseName(url) {
  const u = url.replace(/\/$/, "");
  return decodeURIComponent(u.slice(u.lastIndexOf("/") + 1)) || "/";
}
function extOf(name) {
  const m = /\.([a-z0-9]+)$/i.exec(name);
  return m ? m[1].toLowerCase() : "";
}
export function kindOf(name, isContainer) {
  if (isContainer) return "folder";
  const e = extOf(name);
  if (["json"].includes(e)) return "json";
  if (["md", "markdown"].includes(e)) return "md";
  if (["toml", "yaml", "yml", "ini", "cfg"].includes(e)) return "config";
  if (["js", "ts", "py", "css", "html", "sh", "rb", "go", "rs"].includes(e)) return "code";
  if (["txt", "log", ""].includes(e)) return "text";
  return "file";
}

// =====================================================================
//  REAL BACKEND
// =====================================================================
class RealBackend {
  constructor(libs, session) {
    this.sc = libs.sc;
    this.fetch = session.fetch;
    this.webId = session.info.webId;
    // Best-guess default so root()/urlFor() never see `undefined` before init() resolves.
    this.root = this.webId.replace(/profile\/card#me$/, "");
    // Account-API session (client-credentials mgmt). Story 7.4: this is a SEPARATE
    // auth from the DPoP/WebID pod session above — the CSS account API is reached with
    // a `CSS-Account-Token`, obtained via email+password, NOT via the OIDC login. So
    // managing credentials requires an explicit account sign-in even when the pod
    // session is live. Held in memory only, for the page session.
    this._acctToken = null;
    this._ccUrl = null;
  }
  async init() {
    try {
      const pods = await this.sc.getPodUrlAll(this.webId, { fetch: this.fetch });
      if (pods && pods[0]) this.root = pods[0];
    } catch (e) {
      // Keep the webId-derived fallback set in the constructor.
    }
    return this;
  }
  async list(url) {
    // A container listing must never be served stale from the browser's HTTP cache —
    // otherwise a just-created/deleted item doesn't show up until a hard page reload.
    const noStoreFetch = (u, opts = {}) => this.fetch(u, { ...opts, cache: "no-store" });
    const ds = await this.sc.getSolidDataset(url, { fetch: noStoreFetch });
    const urls = this.sc.getContainedResourceUrlAll(ds);
    return urls.map((u) => {
      const isContainer = u.endsWith("/");
      const name = baseName(u);
      return { url: u, name, isContainer, kind: kindOf(name, isContainer) };
    });
  }
  async readText(url) {
    const file = await this.sc.getFile(url, { fetch: this.fetch });
    return await file.text();
  }
  async writeText(url, text, type = "text/plain") {
    await this.sc.overwriteFile(url, new Blob([text], { type }), {
      contentType: type,
      fetch: this.fetch,
    });
    return true;
  }
  // Upload a real File/Blob (image, PDF, …) preserving its actual content-type —
  // same overwriteFile primitive as writeText, just fed a File instead of a text Blob.
  async uploadFile(url, file) {
    await this.sc.overwriteFile(url, file, {
      contentType: file.type || "application/octet-stream",
      fetch: this.fetch,
    });
    return true;
  }
  async makeFolder(url) {
    await this.sc.createContainerAt(url, { fetch: this.fetch });
    return true;
  }
  // Copy a resource (recursively, for containers) WITHOUT deleting the source.
  // Used by `rename` to build the whole destination tree before any source deletion
  // happens, so a partial failure can roll back the destination and truly leave the
  // original untouched.
  async _copyOnly(url, newUrl) {
    const isContainer = url.endsWith("/");
    if (isContainer) {
      if (!newUrl.endsWith("/")) newUrl += "/";
      await this.sc.createContainerAt(newUrl, { fetch: this.fetch });
      const children = await this.list(url);
      for (const child of children) {
        const childNew = newUrl + child.name + (child.isContainer ? "/" : "");
        await this._copyOnly(child.url, childNew);
      }
    } else {
      const file = await this.sc.getFile(url, { fetch: this.fetch });
      await this.sc.overwriteFile(newUrl, file, {
        contentType: file.type || "application/octet-stream",
        fetch: this.fetch,
      });
    }
  }
  // Rename = copy to the new URL then delete the old (Solid/WAC has no native move).
  // Preserves raw bytes + content-type for files; recurses for containers. Any own
  // `.acl` on the source is re-applied to the destination so a shared thing stays
  // shared after rename (inherited-only resources need nothing copied).
  async rename(oldUrl, newUrl) {
    const isContainer = oldUrl.endsWith("/");
    if (isContainer) {
      if (!newUrl.endsWith("/")) newUrl += "/";
      await this.sc.createContainerAt(newUrl, { fetch: this.fetch });
      let children;
      try { children = await this.list(oldUrl); }
      catch (e) {
        try { await this.remove(newUrl); } catch (e2) { /* best-effort cleanup */ }
        throw new Error(`Could not list "${baseName(oldUrl)}" to rename its contents: ${e.message}`);
      }
      // Copy every child to the new location FIRST, without touching the original —
      // only after every child has copied cleanly do we delete any source (that
      // happens once, below, via the final `this.remove(oldUrl)`). This nested
      // `rename` must not delete its own source per-child, or a failure partway
      // through would leave already-moved children deleted from BOTH the old and
      // the rolled-back new location — actual data loss, not the "original left
      // untouched" safety this rollback claims.
      try {
        for (const child of children) {
          const childNew = newUrl + child.name + (child.isContainer ? "/" : "");
          await this._copyOnly(child.url, childNew);
        }
      } catch (e) {
        // Partial copy: roll back the destination rather than leave a half-copied
        // duplicate tree alongside the still-intact original (which was never touched).
        try { await this.remove(newUrl); } catch (e2) { /* best-effort cleanup */ }
        throw new Error(`Rename failed partway through — original left untouched. ${e.message}`);
      }
    } else {
      const file = await this.sc.getFile(oldUrl, { fetch: this.fetch });
      await this.sc.overwriteFile(newUrl, file, {
        contentType: file.type || "application/octet-stream",
        fetch: this.fetch,
      });
    }
    // Carry over an explicit (non-inherited) access grant.
    let aclCarryWarning = null;
    try {
      const access = await this.getAccess(oldUrl);
      if (!access.inherited && (access.agents.length || Object.values(access.public).some(Boolean))) {
        await this._writeAcl(newUrl, { agents: access.agents, public: access.public });
      }
      if (access.unknownBlocks && access.unknownBlocks.length) {
        aclCarryWarning = "Renamed, but access rules this app doesn't understand (e.g. group sharing) were not carried over — check them on the new location.";
      }
    } catch (e) { aclCarryWarning = "Renamed, but could not carry over access rules: " + e.message; }
    await this.remove(oldUrl);
    return aclCarryWarning ? { warning: aclCarryWarning } : true;
  }
  async remove(url) {
    if (url.endsWith("/")) {
      // CSS refuses to delete a non-empty container (HTTP 409). Empty it first,
      // depth-first (subfolders recurse), then delete the now-empty container.
      // If the listing itself fails, we can't know it's actually empty — abort
      // rather than call deleteContainer and hit the very 409 this was meant to avoid.
      let children;
      try { children = await this.list(url); }
      catch (e) { throw new Error(`Could not list "${baseName(url)}" before delete: ${e.message}`); }
      for (const child of children) await this.remove(child.url);
      await this.sc.deleteContainer(url, { fetch: this.fetch });
    } else {
      await this.sc.deleteFile(url, { fetch: this.fetch });
    }
    return true;
  }
  // How many descendants a container holds — for a delete confirmation that can
  // honestly say "this also deletes N things inside".
  async countDescendants(url) {
    if (!url.endsWith("/")) return 0;
    let children = [];
    try { children = await this.list(url); } catch (e) { return 0; }
    let n = children.length;
    for (const c of children) if (c.isContainer) n += await this.countDescendants(c.url);
    return n;
  }
  // ---- ACL: read/write the raw .acl document ourselves ----
  // Story 7.3 fix: `universalAccess.setAgentAccess/setPublicAccess` was found (live audit,
  // 2026-07-23) to write container grants without `acl:default`, so a "shared" folder let
  // another agent read/write the *container* but never its children — CSS itself honors
  // public/agent Read+Write fine (confirmed: anon PUT -> 205 against a hand-written .acl).
  // So we write the .acl Turtle directly: deterministic, and includes `acl:default` on
  // containers so grants actually inherit to children (matching the pod-root pattern).
  _aclUrlFor(url) {
    return url + ".acl";
  }
  async getAccess(url) {
    const isContainer = url.endsWith("/");
    const text = await this.turtleAcl(url, { raw: true });
    if (text == null) {
      // No standalone .acl — access is inherited from a parent container, not "no access".
      return { agents: [], public: emptyModes(), inherited: true };
    }
    const agents = [];
    let pub = emptyModes();
    // Split the Turtle into statements at top-level `.` terminators — NOT on blank lines.
    // A foreign .acl (written by another app or a CSS default) may pack several
    // authorizations onto adjacent lines with no blank separator; a blank-line split
    // then merges them into one block and OR-s their modes together, so a public
    // Read-only grant reads back as Read+Write+Control. We track `<...>` depth so a
    // `.` inside a URI is never treated as a statement terminator.
    // Authorization blocks this app can't classify (acl:agentGroup, acl:origin,
    // or anything else outside agent/foaf:Agent). _writeAcl refuses to touch a
    // resource carrying one of these, rather than silently dropping it on rewrite.
    const unknownBlocks = [];
    for (const stmt of this._turtleStatements(text)) {
      if (!/\ba\s+acl:Authorization\b/.test(stmt) && !/\bacl:mode\b/.test(stmt)) continue;
      if (!/acl:agent(Class)?\b/.test(stmt)) { unknownBlocks.push(stmt); continue; }
      const modes = emptyModes();
      MODES.forEach((m) => {
        if (new RegExp("acl:" + m[0].toUpperCase() + m.slice(1) + "\\b").test(stmt)) modes[m] = true;
      });
      if (/acl:agentClass\s+foaf:Agent\b/.test(stmt)) {
        MODES.forEach((m) => { if (modes[m]) pub[m] = true; });
      } else if (/acl:agentClass\s+(?!foaf:Agent\b)\S+/.test(stmt) || /\bacl:agentGroup\b/.test(stmt) || /\bacl:origin\b/.test(stmt)) {
        unknownBlocks.push(stmt);
      } else {
        const m = /acl:agent\s+<([^>]+)>/.exec(stmt);
        if (m && m[1] !== this.webId) {
          const existing = agents.find((a) => a.webId === m[1]);
          if (existing) MODES.forEach((mm) => { if (modes[mm]) existing.modes[mm] = true; });
          else agents.push({ webId: m[1], modes });
        } else if (!m) {
          unknownBlocks.push(stmt);
        }
      }
    }
    return { agents, public: pub, inherited: false, unknownBlocks };
  }
  // Split Turtle into top-level statements on `.` terminators, ignoring `.` inside
  // <URIs>, "strings", and after @prefix directives. Good enough for WAC .acl docs.
  _turtleStatements(text) {
    const out = [];
    let buf = "", inUri = false, inStr = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (inStr) { buf += ch; if (ch === '"') inStr = false; continue; }
      if (inUri) { buf += ch; if (ch === ">") inUri = false; continue; }
      if (ch === "<") { inUri = true; buf += ch; continue; }
      if (ch === '"') { inStr = true; buf += ch; continue; }
      if (ch === ".") { out.push(buf); buf = ""; continue; }
      buf += ch;
    }
    if (buf.trim()) out.push(buf);
    // Drop @prefix / @base directives — they're not authorization statements.
    return out.map((s) => s.trim()).filter((s) => s && !/^@(prefix|base)\b/i.test(s));
  }
  async _writeAcl(url, { agents, public: pub }) {
    const isContainer = url.endsWith("/");
    // `accessTo` must point at the target resource itself. For a container that's
    // `./` (the .acl's own base). For a plain file, `./` from `<file>.acl`'s base
    // resolves to the *parent container* — wrong target entirely, and would have
    // silently granted access to the whole folder instead of just the one file.
    const target = isContainer ? "./" : "./" + baseName(url);
    const lines = [
      "@prefix acl: <http://www.w3.org/ns/auth/acl#>.",
      "@prefix foaf: <http://xmlns.com/foaf/0.1/>.",
      "",
      "<#owner>",
      "    a acl:Authorization;",
      `    acl:agent <${this.webId}>;`,
      `    acl:accessTo <${target}>;`,
    ];
    if (isContainer) lines.push("    acl:default <./>;");
    lines.push("    acl:mode acl:Read, acl:Write, acl:Control.");
    (agents || []).forEach((a, i) => {
      const modes = MODES.filter((m) => a.modes[m]).map((m) => "acl:" + m[0].toUpperCase() + m.slice(1));
      if (!modes.length) return;
      lines.push("", `<#grant${i}>`, "    a acl:Authorization;", `    acl:agent <${a.webId}>;`, `    acl:accessTo <${target}>;`);
      if (isContainer) lines.push("    acl:default <./>;");
      lines.push(`    acl:mode ${modes.join(", ")}.`);
    });
    const pubModes = MODES.filter((m) => pub && pub[m]).map((m) => "acl:" + m[0].toUpperCase() + m.slice(1));
    if (pubModes.length) {
      lines.push("", "<#public>", "    a acl:Authorization;", "    acl:agentClass foaf:Agent;", `    acl:accessTo <${target}>;`);
      if (isContainer) lines.push("    acl:default <./>;");
      lines.push(`    acl:mode ${pubModes.join(", ")}.`);
    }
    const aclUrl = this._aclUrlFor(url);
    const res = await this.fetch(aclUrl, {
      method: "PUT",
      headers: { "content-type": "text/turtle" },
      body: lines.join("\n") + "\n",
    });
    if (!res.ok) throw new Error(`Could not write access rules (HTTP ${res.status}).`);
    return true;
  }
  async setAgentAccess(url, webId, modes) {
    // webId is spliced raw into Turtle as `acl:agent <${webId}>` in _writeAcl —
    // reject anything that could break out of the URI token (Turtle injection).
    if (!/^https?:\/\/[^\s<>"]+$/.test(webId || "")) {
      throw new Error("Not a valid WebID URL.");
    }
    const current = await this.getAccess(url);
    this._refuseIfUnknownAcl(current);
    const agents = (current.agents || []).filter((a) => a.webId !== webId);
    const any = Object.values(modes).some(Boolean);
    if (any) agents.push({ webId, modes });
    await this._writeAcl(url, { agents, public: current.public });
    return true;
  }
  // Rewriting the .acl here would silently drop any authorization this app can't
  // parse (acl:agentGroup, acl:origin, unrecognized agentClass, malformed acl:agent).
  // Refuse instead — surfaces the gap the moment it's hit, rather than quietly
  // deleting someone's group-based grant. Revisit once group sharing (team pods) lands.
  _refuseIfUnknownAcl(access) {
    if (access.unknownBlocks && access.unknownBlocks.length) {
      throw new Error(
        "This resource's access rules include something this app doesn't understand yet " +
        "(e.g. group-based sharing) — editing here would silently delete them. Not changed."
      );
    }
  }
  async setPublicAccess(url, modes) {
    const current = await this.getAccess(url);
    this._refuseIfUnknownAcl(current);
    await this._writeAcl(url, { agents: current.agents, public: modes });
    return true;
  }
  async turtleAcl(url, { raw = false } = {}) {
    // Best-effort fetch of the raw .acl document. `raw` (internal) returns null on a
    // missing .acl instead of a friendly placeholder string, for getAccess() to detect
    // "inherits from parent" distinctly from "explicit empty grant".
    try {
      const res = await this.fetch(this._aclUrlFor(url));
      if (res.ok) return await res.text();
    } catch (e) {}
    return raw ? null : "# No standalone .acl document — access is inherited from a parent container.";
  }

  // ---- Client credentials (Story 7.4) ----
  // Machine credentials that let an external app (a Discord bot, a Matrix bridge, a
  // script) act on the owner's behalf. Endpoints + full round-trip (mint -> DPoP token
  // -> authed request -> revoke -> token now fails) live-confirmed against v0.5.
  //
  // WAC caveat surfaced to the user in the UI: a credential is bound to a WebID and
  // acts with THAT WebID's full access — WAC can't scope it to one app's data. The real
  // controls are least-privilege ACLs + fast revocation, not per-app sandboxing.
  _acctAuth() {
    return { authorization: `CSS-Account-Token ${this._acctToken}` };
  }
  hasAccountSession() {
    return !!this._acctToken;
  }
  // Sign in to the account API (email+password) to unlock credential management, then
  // resolve the token-scoped client-credentials control from the authed account index.
  async accountLogin(email, password) {
    const loginRes = await fetch(new URL("/.account/login/password/", ISSUER), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!loginRes.ok) throw new Error(`Sign-in failed (${await _errDetail(loginRes)}).`);
    let authorization;
    try { ({ authorization } = await loginRes.json()); }
    catch (e) { throw new Error("Signed in but the account API returned an unreadable response."); }
    if (!authorization) throw new Error("Signed in but no account token was returned.");
    this._acctToken = authorization;
    // The clientCredentials control URL is account-scoped and only appears on the
    // AUTHED index — re-fetch it with the token. (Don't send content-type on this GET:
    // CSS content-negotiation returns a controls-less body when it's present.)
    const idxRes = await fetch(new URL("/.account/", ISSUER), { headers: this._acctAuth() });
    if (!idxRes.ok) { this._acctToken = null; throw new Error("Signed in but could not load account controls."); }
    let controls;
    try { ({ controls } = await idxRes.json()); }
    catch (e) { this._acctToken = null; throw new Error("Signed in but the account index returned an unreadable response."); }
    this._ccUrl = controls?.account?.clientCredentials;
    if (!this._ccUrl) { this._acctToken = null; throw new Error("This account exposes no client-credentials endpoint."); }
    return true;
  }
  // Drop the in-memory account token. NOTE: deliberately does NOT hit the server
  // `logout` control — that would invalidate the token for any concurrent use; here we
  // just forget it locally. (The pod/OIDC session is untouched.)
  accountLogout() {
    this._acctToken = null;
    this._ccUrl = null;
  }
  _requireAcct() {
    // Sentinel the UI catches to re-prompt for the password (token expired / logged out).
    if (!this._acctToken) throw new Error("SESSION_EXPIRED");
  }
  _onAcctResponse(res) {
    // A 401 means the account token lapsed — forget it so the UI falls back to the
    // unlock prompt instead of retrying a dead token.
    if (res.status === 401) { this._acctToken = null; throw new Error("SESSION_EXPIRED"); }
  }
  async listClientCredentials() {
    this._requireAcct();
    const res = await fetch(this._ccUrl, { headers: this._acctAuth() });
    this._onAcctResponse(res);
    if (!res.ok) throw new Error(`Could not list credentials (HTTP ${res.status}).`);
    const body = await res.json();
    const map = body.clientCredentials || {};
    // Keys are `name_uuid` (the id used for token auth); strip the trailing uuid for the
    // human label but keep the full key as the id.
    return Object.entries(map).map(([id, resource]) => ({
      id,
      name: id.replace(/_[0-9a-f-]{36}$/i, ""),
      resource,
    }));
  }
  async createClientCredential(name, webId) {
    this._requireAcct();
    // webId is echoed into a token later and stored server-side; keep it a clean URL.
    if (!/^https?:\/\/[^\s<>"]+$/.test(webId || "")) throw new Error("Not a valid WebID URL.");
    const res = await fetch(this._ccUrl, {
      method: "POST",
      headers: { ...this._acctAuth(), "content-type": "application/json" },
      body: JSON.stringify({ name: name || "", webId }),
    });
    this._onAcctResponse(res);
    if (!res.ok) throw new Error(`Could not create credential (${await _errDetail(res)}).`);
    let id, secret, resource;
    try { ({ id, secret, resource } = await res.json()); }
    catch (e) { throw new Error("Credential created but the response was unreadable — check the account's credential list."); }
    if (!id || !secret) throw new Error("Credential created but the server didn't return an id/secret — check the account's credential list.");
    // Secret is returned exactly once by CSS — never re-fetchable. Caller must show it
    // now and never persist it.
    return { id, secret, resource };
  }
  async revokeClientCredential(resourceUrl) {
    this._requireAcct();
    const res = await fetch(resourceUrl, { method: "DELETE", headers: this._acctAuth() });
    this._onAcctResponse(res);
    // A 404 means it's already gone (revoked elsewhere, expired, etc.) — that's the
    // outcome the caller wanted, not a failure.
    if (!res.ok && res.status !== 404) throw new Error(`Could not revoke (HTTP ${res.status}).`);
    return true;
  }
}

// =====================================================================
//  DEMO BACKEND — an in-memory CSS-shaped pod (the school scenario)
// =====================================================================
const DEMO_ROOT = "https://pod.nicolasdb.eu/newcomer/";
export const DEMO_WEBID = "https://pod.nicolasdb.eu/newcomer/profile/card#me";

function seedTree() {
  // path -> node. Containers end with "/".
  const t = {};
  const add = (path, opts = {}) => {
    t[path] = {
      url: DEMO_ROOT + path,
      isContainer: path.endsWith("/"),
      body: opts.body ?? "",
      type: opts.type ?? "text/plain",
      acl: opts.acl ?? { agents: [], public: emptyModes() },
    };
  };
  return { t, add };
}

class DemoBackend {
  constructor() {
    const { t, add } = seedTree();
    this.root = DEMO_ROOT;
    this.webId = DEMO_WEBID;
    add("");            // starter is deliberately near-empty: onboarding fills it
    this.t = t;
    this._agentNames = {
      "https://pod.nicolasdb.eu/teacher-0206/profile/card#me": "Ms. Delcroix (teacher)",
      "https://pod.nicolasdb.eu/parent-0070/profile/card#me": "Dad",
      "https://webid.studyapp.example/agent#id": "FlashLearn (an app)",
    };
  }
  agentName(webId) {
    return this._agentNames[webId] || baseName(webId.split("#")[0].replace(/\/profile\/card$/, ""));
  }
  _norm(url) {
    return url.startsWith("http") ? url : DEMO_ROOT + url;
  }
  async list(url) {
    url = this._norm(url);
    const prefix = url;
    const depth = prefix.replace(DEMO_ROOT, "").split("/").filter(Boolean).length;
    const out = [];
    for (const key of Object.keys(this.t)) {
      const full = this.t[key].url;
      if (full === prefix || !full.startsWith(prefix)) continue;
      const rest = full.replace(prefix, "").replace(/\/$/, "");
      if (rest.split("/").filter(Boolean).length !== 1) continue; // direct children only
      const isContainer = this.t[key].isContainer;
      const name = baseName(full);
      out.push({ url: full, name, isContainer, kind: kindOf(name, isContainer) });
    }
    return out.sort((a, b) => (b.isContainer - a.isContainer) || a.name.localeCompare(b.name));
  }
  async readText(url) {
    url = this._norm(url);
    const k = Object.keys(this.t).find((x) => this.t[x].url === url);
    return k ? this.t[k].body : "";
  }
  async writeText(url, text, type = "text/plain") {
    url = this._norm(url);
    let k = Object.keys(this.t).find((x) => this.t[x].url === url);
    if (!k) { k = url.replace(DEMO_ROOT, ""); this.t[k] = { url, isContainer: false, acl: { agents: [], public: emptyModes() } }; }
    this.t[k].body = text; this.t[k].type = type; this.t[k].isContainer = false;
    return true;
  }
  // Demo stub: store the File itself (kept in memory only) so upload/list/download
  // round-trips in the offline preview without a real content-type-preserving PUT.
  async uploadFile(url, file) {
    url = this._norm(url);
    let k = Object.keys(this.t).find((x) => this.t[x].url === url);
    if (!k) { k = url.replace(DEMO_ROOT, ""); this.t[k] = { url, isContainer: false, acl: { agents: [], public: emptyModes() } }; }
    this.t[k].file = file; this.t[k].type = file.type || "application/octet-stream"; this.t[k].isContainer = false;
    return true;
  }
  async makeFolder(url) {
    url = this._norm(url); if (!url.endsWith("/")) url += "/";
    const k = url.replace(DEMO_ROOT, "");
    if (!this.t[k]) this.t[k] = { url, isContainer: true, body: "", acl: { agents: [], public: emptyModes() } };
    return true;
  }
  async remove(url) {
    url = this._norm(url);
    for (const k of Object.keys(this.t)) if (this.t[k].url === url || this.t[k].url.startsWith(url)) delete this.t[k];
    return true;
  }
  async rename(oldUrl, newUrl) {
    oldUrl = this._norm(oldUrl); newUrl = this._norm(newUrl);
    // Re-key every node under oldUrl (self + descendants) to the new prefix.
    for (const k of Object.keys(this.t)) {
      const full = this.t[k].url;
      if (full !== oldUrl && !full.startsWith(oldUrl)) continue;
      const movedUrl = newUrl + full.slice(oldUrl.length);
      const node = { ...this.t[k], url: movedUrl };
      delete this.t[k];
      this.t[movedUrl.replace(DEMO_ROOT, "")] = node;
    }
    return true;
  }
  _node(url) {
    url = this._norm(url);
    return this.t[Object.keys(this.t).find((x) => this.t[x].url === url)];
  }
  async getAccess(url) {
    const n = this._node(url);
    if (!n) return { agents: [], public: emptyModes(), inherited: true };
    return {
      agents: n.acl.agents.map((a) => ({ webId: a.webId, modes: { ...a.modes }, name: this.agentName(a.webId) })),
      public: { ...n.acl.public },
      inherited: false,
    };
  }
  async setAgentAccess(url, webId, modes) {
    const n = this._node(url); if (!n) return false;
    const any = Object.values(modes).some(Boolean);
    n.acl.agents = n.acl.agents.filter((a) => a.webId !== webId);
    if (any) n.acl.agents.push({ webId, modes: { ...emptyModes(), ...modes } });
    return true;
  }
  async setPublicAccess(url, modes) {
    const n = this._node(url); if (!n) return false;
    n.acl.public = { ...emptyModes(), ...modes };
    return true;
  }
  // ---- Client credentials (Story 7.4) — in-memory demo so the offline preview
  // shows the Apps & credentials UI with fake, revocable data. Starts "unlocked"
  // (no account sign-in in the demo) and seeded with one example credential.
  _demoCreds = [
    { id: "discord-bridge_00000000-0000-0000-0000-000000000001", name: "discord-bridge", resource: DEMO_ROOT + ".creds/demo-1/", webId: DEMO_WEBID },
  ];
  hasAccountSession() { return true; }
  async accountLogin() { return true; }
  accountLogout() { /* demo stays unlocked */ }
  async listClientCredentials() {
    return this._demoCreds.map((c) => ({ id: c.id, name: c.name, resource: c.resource }));
  }
  async createClientCredential(name, webId) {
    const uuid = "demo-" + Math.random().toString(16).slice(2, 10);
    const id = (name || "app") + "_" + uuid;
    const resource = DEMO_ROOT + ".creds/" + uuid + "/";
    this._demoCreds.push({ id, name: name || "app", resource, webId });
    return { id, secret: "demo-secret-" + Math.random().toString(16).slice(2, 18), resource };
  }
  async revokeClientCredential(resourceUrl) {
    this._demoCreds = this._demoCreds.filter((c) => c.resource !== resourceUrl);
    return true;
  }
  async turtleAcl(url) {
    const n = this._node(url); if (!n) return "# resource not found";
    const target = baseName(n.url);
    const L = [
      "@prefix acl: <http://www.w3.org/ns/auth/acl#>.",
      "@prefix foaf: <http://xmlns.com/foaf/0.1/>.",
      "",
      `# Access control for <${target}>`,
      "<#owner>",
      "    a acl:Authorization;",
      `    acl:agent <${this.webId}>;`,
      `    acl:accessTo <${n.url}>;`,
      "    acl:mode acl:Read, acl:Write, acl:Control.",
    ];
    n.acl.agents.forEach((a, i) => {
      const modes = MODES.filter((m) => a.modes[m]).map((m) => "acl:" + m[0].toUpperCase() + m.slice(1));
      if (!modes.length) return;
      L.push("", `<#grant${i}>`, "    a acl:Authorization;",
        `    acl:agent <${a.webId}>;`, `    acl:accessTo <${n.url}>;`,
        `    acl:mode ${modes.join(", ")}.`);
    });
    const pubModes = MODES.filter((m) => n.acl.public[m]).map((m) => "acl:" + m[0].toUpperCase() + m.slice(1));
    if (pubModes.length) {
      L.push("", "<#public>", "    a acl:Authorization;", "    acl:agentClass foaf:Agent;",
        `    acl:accessTo <${n.url}>;`, `    acl:mode ${pubModes.join(", ")}.`);
    }
    return L.join("\n");
  }
}

// =====================================================================
//  SOLID — session + backend factory
// =====================================================================
export const Solid = {
  issuer: ISSUER,
  async init() {
    // Returns { loggedIn, webId } after processing any redirect.
    try {
      const { authn } = await loadLibs();
      const info = await authn.handleIncomingRedirect({ restorePreviousSession: true });
      if (info && info.isLoggedIn) return { loggedIn: true, webId: info.webId };
    } catch (e) {
      // Library couldn't load / no network (e.g. sandboxed preview). Demo still works.
      return { loggedIn: false, webId: null, offline: true, error: String(e) };
    }
    return { loggedIn: false, webId: null };
  },
  async connect() {
    const { authn } = await loadLibs();
    await authn.login({
      oidcIssuer: ISSUER,
      redirectUrl: window.location.href,
      clientName: CLIENT_NAME,
    });
  },
  async disconnect() {
    try { const { authn } = await loadLibs(); await authn.logout(); } catch (e) {}
  },
  async realClient() {
    const libs = await loadLibs();
    const session = libs.authn.getDefaultSession();
    return await new RealBackend(libs, session).init();
  },
  demoClient() {
    return new DemoBackend();
  },
  // Real CSS account/pod registration (Story 7.1). Endpoint sequence + field
  // names verified live against pod.nicolasdb.eu with a throwaway account
  // (2026-07-21): GET /.account/ -> POST controls.account.create ->
  // POST controls.password.create (authed) -> POST controls.account.pod (authed) -> login()
  //
  // RESUMABLE: CSS's account.create is anonymous and unconditional — every call
  // mints a brand-new account. So a naive retry after a mid-flow failure would
  // orphan the half-built account AND then fail again on the duplicate email at
  // password.create. To stay idempotent, the in-progress account token + which
  // steps already succeeded are stashed per podName; a retry resumes from the
  // failed step on the SAME account instead of creating another one.
  async registerAccount(podName, password, email) {
    // Defense in depth: CSS's controls.account.pod treats a missing/empty `name`
    // as "claim the pod root" instead of rejecting it (confirmed live 2026-07-22,
    // undocumented) — reject here so this can never reach the network, even if
    // called directly (the UI already guards this in obCreatePod).
    if (!podName) throw new Error("Pod name is required.");

    let pending = _pendingRegistrations[podName];
    // Story 7.2: use the owner's REAL email so they can actually log back in later.
    // Fall back to the old synthetic placeholder only if a caller somehow omits it,
    // so an empty email can never silently reach CSS as a duplicate-prone value.
    email = (email || "").trim() || `${podName}@pod.nicolasdb.eu.local`;

    // Step 0+1: create the account (only if we don't already hold a token for it).
    if (!pending) {
      const indexRes = await fetch(new URL("/.account/", ISSUER));
      if (!indexRes.ok) throw new Error("Could not reach account API.");
      const index = await indexRes.json();
      const createUrl = index.controls?.account?.create;
      if (!createUrl) throw new Error("Account API did not expose an account-create endpoint.");

      const accountRes = await fetch(createUrl, { method: "POST" });
      if (!accountRes.ok) throw new Error(`Could not create account (${await _errDetail(accountRes)}).`);
      const { authorization } = await accountRes.json();
      if (!authorization) throw new Error("Account created but no session token returned.");

      pending = _pendingRegistrations[podName] = {
        authorization, passwordDone: false, webId: null,
      };
    }

    const authHeader = { authorization: `CSS-Account-Token ${pending.authorization}` };

    // Re-fetch the authed controls each resume — endpoint URLs are token-scoped.
    const accountIndexRes = await fetch(new URL("/.account/", ISSUER), { headers: authHeader });
    if (!accountIndexRes.ok) throw new Error(`Could not authenticate the new account (${await _errDetail(accountIndexRes)}).`);
    const { controls: authedControls } = await accountIndexRes.json();
    const passwordUrl = authedControls?.password?.create;
    const podUrl = authedControls?.account?.pod;
    if (!passwordUrl || !podUrl) throw new Error("Account API did not expose the expected password/pod endpoints.");

    // Step 2: add the password login (skip if a prior attempt already did it —
    // re-POSTing the same email would fail on the duplicate). Once this step has
    // run, `pending.email` is the email CSS actually has on file — a retry that
    // passes a different `email` argument must not silently report the new,
    // never-registered value as if it were used.
    if (!pending.passwordDone) {
      const passwordRes = await fetch(passwordUrl, {
        method: "POST",
        headers: { ...authHeader, "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!passwordRes.ok) throw new Error(`Could not set a login credential (${await _errDetail(passwordRes)}).`);
      pending.passwordDone = true;
      pending.email = email;
    } else {
      email = pending.email;
    }

    // Step 3: create the pod. CSS removes the linked WebID on pod-create failure,
    // so retrying this step on the same account is safe.
    if (!pending.webId) {
      const podRes = await fetch(podUrl, {
        method: "POST",
        headers: { ...authHeader, "content-type": "application/json" },
        body: JSON.stringify({ name: podName }),
      });
      if (!podRes.ok) throw new Error(`Could not create the pod (${await _errDetail(podRes)}).`);
      const { webId } = await podRes.json();
      pending.webId = webId;
    }

    const webId = pending.webId;
    delete _pendingRegistrations[podName]; // fully provisioned — clear resume state
    return { webId, email, podName };
  },
};
