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
    const ds = await this.sc.getSolidDataset(url, { fetch: this.fetch });
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
  async makeFolder(url) {
    await this.sc.createContainerAt(url, { fetch: this.fetch });
    return true;
  }
  async remove(url) {
    if (url.endsWith("/")) await this.sc.deleteContainer(url, { fetch: this.fetch });
    else await this.sc.deleteFile(url, { fetch: this.fetch });
    return true;
  }
  async getAccess(url) {
    const ua = this.sc.universalAccess;
    const agents = await ua.getAgentAccessAll(url, { fetch: this.fetch });
    const pub = await ua.getPublicAccess(url, { fetch: this.fetch });
    return {
      agents: Object.entries(agents || {}).map(([webId, m]) => ({ webId, modes: m })),
      public: pub || emptyModes(),
    };
  }
  async setAgentAccess(url, webId, modes) {
    await this.sc.universalAccess.setAgentAccess(url, webId, modes, { fetch: this.fetch });
    return true;
  }
  async setPublicAccess(url, modes) {
    await this.sc.universalAccess.setPublicAccess(url, modes, { fetch: this.fetch });
    return true;
  }
  async turtleAcl(url) {
    // Best-effort fetch of the raw .acl document for the "advanced" view.
    try {
      const aclUrl = url.endsWith("/") ? url + ".acl" : url + ".acl";
      const res = await this.fetch(aclUrl);
      if (res.ok) return await res.text();
    } catch (e) {}
    return "# No standalone .acl document — access is inherited from a parent container.";
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
  _node(url) {
    url = this._norm(url);
    return this.t[Object.keys(this.t).find((x) => this.t[x].url === url)];
  }
  async getAccess(url) {
    const n = this._node(url);
    if (!n) return { agents: [], public: emptyModes() };
    return {
      agents: n.acl.agents.map((a) => ({ webId: a.webId, modes: { ...a.modes }, name: this.agentName(a.webId) })),
      public: { ...n.acl.public },
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
