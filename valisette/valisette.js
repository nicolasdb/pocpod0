// Valisette — gist swipe-triage app.
//
// Hand-ported from the design handoff (`Valisette Mobile.dc.html` + README.md)
// into plain JS, matching this repo's no-build-step convention (see
// backoffice/pod-api.js).
//
// Story 7.13: Valisette now lives on its own origin (valisette.nicolasdb.eu),
// separate from backoffice.nicolasdb.eu, so it can no longer import
// backoffice's pod-api.js (that was a same-origin `/pod-api.js` path that
// only worked while both apps were served together off pod.nicolasdb.eu).
// It loads the Inrupt libraries itself, same esm.sh `?bundle` pattern as
// pod-api.js's loadLibs() — see that file's comment for why `?bundle` is
// required. Origin split also means the previous same-origin session-bounce
// guard (Solid.namedSession/canRestore) is dead code: each app's browser
// storage is scoped to its own origin now, so a plain per-app Session with a
// stable id and unconditional restorePreviousSession:true is safe.
//
// Rate compatibility: Valisette no longer writes its own aggregate file into
// a separate triage/ folder. The grouped TOML produced by the cleanup pass in
// capture/gists/ IS the buffer between swipe and the 9h Rate ingestion, so a
// swipe patches the `validation` field of one gist, in place, in that file,
// and touches nothing else. Two properties hold the design together:
//
//   * Fail-to-pending. A failed or interrupted write leaves the gist
//     `validation = "pending"` on the pod. Worst case is re-swiping one card;
//     nothing is ever half-written.
//   * Never cache the file string across swipes. Every write re-reads the
//     file and PUTs with If-Match, so a Rate run landing mid-session can
//     never be clobbered (that would erase `ingested = true` and cause
//     double ingestion).
//
// Drag mechanics write straight to DOM `style.transform` on pointermove and
// never go through a re-render (README, "Drag mechanics" — a per-move
// re-render drops frames and loses the gesture). Everything else is driven
// by `render()` after a discrete state transition.

let _libs = null;
async function loadLibs() {
  if (_libs) return _libs;
  const [authn, sc] = await Promise.all([
    import("https://esm.sh/@inrupt/solid-client-authn-browser@2.3.0?bundle"),
    import("https://esm.sh/@inrupt/solid-client@2.1.0?bundle"),
  ]);
  _libs = { authn, sc };
  return _libs;
}

const TYPE_COLOR_VAR = {
  decision: "--convergence",
  apprentissage: "--fresh",
  protocole: "--temporal",
};

const VALIDATION_COLOR_VAR = {
  validated: "--fresh",
  rejected: "--pattern",
  anagnorisis: "--anagnorisis",
};

// Demo stack. Held as a TOML *string* rather than plain objects so the
// offline path exercises the real parse/patch code instead of a parallel one.
const DEMO_FILE_URL = "demo:///capture/gists/2026-08-21.toml";
const DEMO_TOML = `# gists 2026-08-21 — cleanup pass
[gist_session]
version_schema = "v1"
date = "2026-08-21"
ingested = false

[[gist]]
id = "gist-20260821-001"
timestamp = 1787291737
type = "decision"
titre = "Cron fixé à 17h UTC (19h Bruxelles) — timezone"
moment = "2026-08-21 08:20 CEST"
validation = "pending"
raw = """
Correction du décalage UTC/Bruxelles: le cron était programmé pour 19h UTC, déclenché à 21h en été. Fixé à 17h UTC = 19h Bruxelles.
"""

[[gist]]
id = "gist-20260821-002"
timestamp = 1787292402
type = "apprentissage"
titre = "Pipeline Otis validé — 71 traces brutes → 8 gists"
moment = "2026-08-21 08:40 CEST"
validation = "pending"
raw = """
Run 44 a distillé 71 traces brutes en 8 gists. Le pipeline tient : le taux de compression est stable d'un run à l'autre, et aucune trace n'a été perdue au passage.
"""

[[gist]]
id = "gist-20260821-003"
timestamp = 1787292645
type = "protocole"
titre = "Anagnorisis ajouté au schéma"
moment = "2026-08-21 08:50 CEST"
validation = "pending"
raw = """
Tag de validation posé à la main pendant le triage. Les gists marqués auront un poids plus élevé dans le graphe.
"""

[[gist]]
id = "gist-20260821-004"
timestamp = 1787293786
type = "apprentissage"
titre = "Vocabulaire Manny : punaise, pas putain"
moment = "2026-08-21 09:10 CEST"
validation = "pending"
raw = """
Ton corrigé. Palette ajustée : grognements préhistoriques, inspiration Audiard, jamais de vulgarité.
"""

[[gist]]
id = "gist-20260821-005"
timestamp = 1787294864
type = "decision"
titre = "App de triage créée comme tâche kanban"
moment = "2026-08-21 11:30 CEST"
validation = "pending"
raw = """
Carte kanban t_da7ed1a1 créée. Prototype développé sous le nom Valisette.
"""

[[gist]]
id = "gist-20260821-006"
timestamp = 1787314088
type = "apprentissage"
titre = "Champ moment ajouté au schéma"
moment = "2026-08-21 16:00 CEST"
validation = "pending"
raw = """
Timestamp UNIX conservé pour SPARQL. Champ moment ISO 8601 + fuseau pour l'affichage humain.
"""

[[gist]]
id = "gist-20260821-007"
timestamp = 1787322848
type = "protocole"
titre = "Incrémental Otis réparé"
moment = "2026-08-21 20:00 CEST"
validation = "pending"
raw = """
Bug : session_ids comme clé de dédup perdaient les messages chevauchant deux crons. Fix : tracker le dernier message_id par session.
"""
`;

// Demo writes go here instead of the network, through the same patch path.
const demoFiles = { [DEMO_FILE_URL]: DEMO_TOML };

// ── TOML read/patch ────────────────────────────────────────────────────
const RAW_OPEN = 'raw = """';

function unquote(v) {
  const t = v.trim();
  return (t.startsWith('"') && t.endsWith('"') && t.length > 1) ? t.slice(1, -1) : t;
}

function parseGistTOML(text) {
  const gists = [];
  let current = null, rawBuffer = null, inRaw = false, inGist = false;
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (t === "[[gist]]") {
      if (current && current.id) gists.push(current);
      current = { validation: "pending" };
      rawBuffer = null; inRaw = false; inGist = true;
      continue;
    }
    if (!inGist || !current) continue;
    if (inRaw) {
      if (t === '"""') { current.raw = (current.raw || "") + rawBuffer; inRaw = false; rawBuffer = null; }
      else { rawBuffer = (rawBuffer || "") + line + "\n"; }
      continue;
    }
    if (t.startsWith(RAW_OPEN)) {
      const after = t.slice(RAW_OPEN.length);
      if (after.endsWith('"""')) {
        // Opens and closes on the same line — the common case in practice.
        current.raw = after.slice(0, -3);
      } else {
        inRaw = true; rawBuffer = after ? after + "\n" : "";
      }
      continue;
    }
    const eq = t.indexOf("="); if (eq === -1) continue;
    const key = t.slice(0, eq).trim();
    const val = unquote(t.slice(eq + 1));
    if (key === "id") current.id = val;
    else if (key === "timestamp") current.timestamp = parseInt(val, 10);
    else if (key === "type") current.type = val;
    else if (key === "titre") current.titre = val;
    else if (key === "moment") current.moment = val;
    else if (key === "validation") current.validation = val;
  }
  if (current && current.id) gists.push(current);
  return gists;
}

// Session-level flag, set by the Rate once it has ingested the batch. Only
// the header (everything before the first [[gist]]) is inspected.
function isIngested(text) {
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (t === "[[gist]]") break;
    const m = /^ingested\s*=\s*(true|false)\b/.exec(t);
    if (m) return m[1] === "true";
  }
  return false;
}

// String-level patch — deliberately NOT parse-then-rebuild. The file is
// written by the cleanup pass, not by us: a rebuild would silently drop any
// field this app doesn't know about (`ingested` being the one that matters
// today, and whatever the pipeline adds tomorrow). Exactly one line changes.
// Returns null when the gist, or its validation line, isn't there — a failed
// patch has to surface, never pass as a silent no-op.
function patchValidationLine(text, gistId, value) {
  const lines = text.split("\n");
  let inRaw = false, inGist = false, curId = null, valLine = -1, target = -1;

  const closeBlock = () => {
    if (inGist && curId === gistId && valLine !== -1 && target === -1) target = valLine;
    curId = null; valLine = -1;
  };

  for (let n = 0; n < lines.length && target === -1; n++) {
    const t = lines[n].trim();
    // Skip multi-line raw bodies, so prose containing "validation = " is
    // never mistaken for the field.
    if (inRaw) { if (t === '"""') inRaw = false; continue; }
    if (t.startsWith(RAW_OPEN)) {
      // Opens and closes on the same line unless it doesn't end in `"""` —
      // must match parseGistTOML's rule exactly or the two disagree on where
      // a block ends.
      if (!t.slice(RAW_OPEN.length).endsWith('"""')) inRaw = true;
      continue;
    }
    if (t === "[[gist]]") { closeBlock(); inGist = true; continue; }
    if (t.startsWith("[")) { closeBlock(); inGist = false; continue; }
    if (!inGist) continue;
    const eq = t.indexOf("="); if (eq === -1) continue;
    const key = t.slice(0, eq).trim();
    if (key === "id") curId = unquote(t.slice(eq + 1));
    else if (key === "validation") valLine = n;
  }
  closeBlock();

  if (target === -1) return null;
  const indent = lines[target].match(/^\s*/)[0];
  lines[target] = `${indent}validation = "${value}"`;
  return lines.join("\n");
}

// Storage root = the container holding the WebID document, minus the
// conventional profile/ folder. Do NOT use u.origin alone.
function podRootFrom(webId) {
  try {
    const u = new URL(webId);
    const parts = u.pathname.split("/").filter(Boolean);
    parts.pop();
    if (parts[parts.length - 1] === "profile") parts.pop();
    return u.origin + "/" + (parts.length ? parts.join("/") + "/" : "");
  } catch (e) {
    return "https://pod.nicolasdb.eu/";
  }
}

const words = ["nothing", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];

// ── app state ──────────────────────────────────────────────────────────
const state = {
  screen: "login",
  provider: "https://pod.nicolasdb.eu",
  webId: null,
  demo: false,
  authBusy: false,
  libReady: false,
  sourcePath: "",
  gists: [],          // pending gists only, newest file first; each carries sourceUrl
  fileDates: [],      // distinct source dates present in the deck, newest first
  loadState: "ok",    // ok | no-files | none-pending | error
  i: 0,
  decisions: {},
  history: [],
  writing: 0,
  writeError: null,
  batchClosed: false,
  lastWriteAt: null,
  failures: 0,
  now: Date.now(),
};

let session = null; // this app's own isolated Inrupt Session (see header comment)
let libs = null;    // { authn, sc } — loaded once, shared with the session above
let animating = false;
let drag = null;

const el = (id) => document.getElementById(id);
const screens = { login: el("screen-login"), setup: el("screen-setup"), deck: el("screen-deck"), done: el("screen-done") };
const cardEl = el("gist-card");
const rejectEl = el("reject-overlay");
const validateEl = el("validate-overlay");
const anagnorisisEl = el("anagnorisis-overlay");

// ── persistence ────────────────────────────────────────────────────────
// Only the source folder is remembered. There is no
// local mirror of decisions any more: the TOML on the pod is the single
// source of truth, and a stale mirror could resurrect a swiped gist or hide
// a pending one.
function saveSetupToLocalStorage() {
  if (state.demo) return; // demo has no pod — its synthetic path must never leak into a real login
  try {
    localStorage.setItem("valisette:setup", JSON.stringify({ sourcePath: state.sourcePath }));
  } catch (e) { /* ignore */ }
}
function restoreSetupFromLocalStorage() {
  try {
    const raw = localStorage.getItem("valisette:setup");
    if (!raw) return false;
    const saved = JSON.parse(raw);
    // Guard against a demo path saved before this fix existed.
    if (saved.sourcePath && !saved.sourcePath.startsWith("demo:")) state.sourcePath = saved.sourcePath;
    return true;
  } catch (e) { return false; }
}

// ── screen switching ───────────────────────────────────────────────────
function showScreen(name) {
  state.screen = name;
  for (const [k, node] of Object.entries(screens)) node.classList.toggle("vz-active", k === name);
  render();
}

// ── auth ───────────────────────────────────────────────────────────────
function setLoginStatus(msg, toneVar) {
  const node = el("login-status");
  node.textContent = msg;
  node.style.color = `var(${toneVar})`;
}

// Stable across reloads so restorePreviousSession can find it.
const SESSION_ID = "valisette";

async function initSolid() {
  setLoginStatus("checking session…", "--text-tertiary");
  try {
    libs = await loadLibs();
    session = new libs.authn.Session({}, SESSION_ID);
    state.libReady = true;
    const info = await session.handleIncomingRedirect({ restorePreviousSession: true });
    if (info && info.isLoggedIn) {
      state.webId = info.webId;
      const root = podRootFrom(info.webId);
      state.sourcePath = root + "capture/gists/";
      restoreSetupFromLocalStorage();
      showScreen("setup");
      initBrowsers(root);
      return;
    }
    setLoginStatus("ready — no active session", "--text-tertiary");
  } catch (e) {
    setLoginStatus("solid client unavailable here — use offline stack", "--convergence");
  }
}

async function doLogin() {
  state.authBusy = true;
  el("login-btn").textContent = "redirecting…";
  setLoginStatus(`redirecting to ${state.provider} …`, "--text-secondary");
  try {
    await session.login({
      oidcIssuer: state.provider,
      redirectUrl: window.location.href,
      clientName: "Valisette",
    });
  } catch (e) {
    state.authBusy = false;
    el("login-btn").textContent = "Continue to your provider →";
    setLoginStatus(String((e && e.message) || e).slice(0, 80), "--pattern");
  }
}

// ── pod read/write ─────────────────────────────────────────────────────
// Reads go through session.fetch directly rather than solid-client's getFile
// so the ETag is available for the If-Match on the way back out.
function baseName(url) {
  const u = url.replace(/\/$/, "");
  return decodeURIComponent(u.slice(u.lastIndexOf("/") + 1)) || "/";
}
async function listContainer(url) {
  const noStoreFetch = (u, opts = {}) => session.fetch(u, { ...opts, cache: "no-store" });
  const ds = await libs.sc.getSolidDataset(url, { fetch: noStoreFetch });
  return libs.sc.getContainedResourceUrlAll(ds).map((u) => ({ url: u, name: baseName(u), isContainer: u.endsWith("/") }));
}
async function readFile(url) {
  if (state.demo) return { text: demoFiles[url] || "", etag: null };
  const res = await session.fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const e = new Error(`read failed — ${res.status}`);
    e.status = res.status;
    throw e;
  }
  return { text: await res.text(), etag: res.headers.get("ETag") };
}
async function writeFile(url, text, etag) {
  if (state.demo) { demoFiles[url] = text; return; }
  const headers = { "Content-Type": "text/plain" };
  if (etag) headers["If-Match"] = etag;
  const res = await session.fetch(url, { method: "PUT", headers, body: text });
  if (!res.ok) {
    const e = new Error(`write failed — ${res.status}`);
    e.status = res.status;
    throw e;
  }
}

// Read → patch → PUT, every time. The file string is never held across
// swipes: a Rate run landing mid-session would otherwise be overwritten by a
// stale copy, erasing `ingested = true`.
async function writeValidation(gist, value) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const { text, etag } = await readFile(gist.sourceUrl);
    if (isIngested(text)) {
      const e = new Error("this batch was ingested — remaining gists roll to the next one");
      e.code = "batch-closed";
      throw e;
    }
    const patched = patchValidationLine(text, gist.id, value);
    if (patched === null) {
      const e = new Error("gist is no longer in that file");
      e.code = "not-found";
      throw e;
    }
    try {
      await writeFile(gist.sourceUrl, patched, etag);
      return;
    } catch (e) {
      // 412 — the file moved under us. Re-read once and patch the new one.
      if (e.status === 412 && attempt === 0) continue;
      throw e;
    }
  }
}

// ── source folder chips — real pod listing, static fallback ────────────
const STATIC_FOLDER_HINTS = ["capture/", "gists/", "inbox/"];

// { source: { root, path } } — root is fixed (pod storage root), path is
// whatever container is currently drilled into.
const browse = { source: {} };

function renderBreadcrumb(group) {
  const { root, path } = browse[group];
  const wrap = el(`${group}-breadcrumb`);
  wrap.innerHTML = "";
  const rootBtn = document.createElement("button");
  rootBtn.type = "button";
  rootBtn.className = "vz-crumb";
  rootBtn.setAttribute("data-nodrag", "");
  rootBtn.textContent = "root";
  rootBtn.addEventListener("click", () => browseTo(group, root));
  wrap.appendChild(rootBtn);

  const rel = path.slice(root.length).replace(/\/$/, "");
  const segments = rel ? rel.split("/") : [];
  let acc = root;
  segments.forEach((seg) => {
    const sep = document.createElement("span");
    sep.className = "vz-crumb-sep";
    sep.textContent = "/";
    wrap.appendChild(sep);
    acc += seg + "/";
    const target = acc;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vz-crumb";
    btn.setAttribute("data-nodrag", "");
    btn.textContent = seg;
    btn.addEventListener("click", () => browseTo(group, target));
    wrap.appendChild(btn);
  });
}

function renderChipRow(group, url, names) {
  const wrap = el(`${group}-chips`);
  wrap.innerHTML = "";
  if (!names.length) {
    const span = document.createElement("span");
    span.className = "vz-chip-empty";
    span.textContent = "no subfolders here";
    wrap.appendChild(span);
    return;
  }
  names.forEach((name) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vz-chip";
    btn.setAttribute("data-nodrag", "");
    btn.textContent = name;
    btn.addEventListener("click", () => browseTo(group, url + name));
    wrap.appendChild(btn);
  });
}

// Drill into (or jump to) `url`: updates the input (which always mirrors the
// current drilled path — no separate "select" step, per the UX review), the
// breadcrumb, and re-lists that container's own sub-containers as the next
// chip row. Then scans it, so the setup screen can say what's actually there.
async function browseTo(group, url) {
  browse[group].path = url;
  el("source-input").value = url;
  state.sourcePath = url;
  renderBreadcrumb(group);
  if (state.demo) {
    renderChipRow(group, url, url === browse[group].root ? STATIC_FOLDER_HINTS : []);
    scanSource();
    return;
  }
  try {
    const items = await listContainer(url);
    const names = items.filter((it) => it.isContainer).map((it) => it.name + "/");
    renderChipRow(group, url, names);
  } catch (e) {
    renderChipRow(group, url, []);
  }
  scanSource();
}

function initBrowsers(root) {
  browse.source = { root, path: state.sourcePath };
  browseTo("source", state.sourcePath);
}

// No pod behind demo mode, so no folder to pick — straight to the deck on
// the one synthetic file.
function bootDemo() {
  state.demo = true;
  state.webId = "https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me";
  state.sourcePath = DEMO_FILE_URL;
  loadGists();
}

// ── scanning the source folder ─────────────────────────────────────────
// A .toml is a candidate buffer unless the Rate has stamped it ingested.
// Newest first: tonight's gists lead, and a backlog sinks below them rather
// than standing between you and the batch you actually came to triage.
function dateOfFile(name, gists) {
  const m = /(\d{4}-\d{2}-\d{2})/.exec(name);
  if (m) return m[1];
  const first = gists && gists[0];
  return (first && first.moment) ? first.moment.slice(0, 10) : name.replace(/\.toml$/, "");
}

let scanToken = 0;

async function scanSource() {
  const token = ++scanToken;
  const folder = state.sourcePath.replace(/\/?$/, "/");
  el("stack-line").textContent = "looking…";

  let files = [];
  try {
    files = await collectPendingFiles(folder);
  } catch (e) {
    if (token !== scanToken) return;
    state.scan = null;
    el("stack-line").textContent = "couldn't read that folder";
    return;
  }
  if (token !== scanToken) return;

  state.scan = { folder, files };
  const total = files.reduce((n, f) => n + f.gists.length, 0);
  if (!files.length) {
    el("stack-line").textContent = "no open batches here";
  } else if (!total) {
    el("stack-line").textContent = "nothing pending — all swiped";
  } else {
    const shape = files.filter((f) => f.gists.length).map((f) => `${f.date} ${f.gists.length}`).join(" · ");
    el("stack-line").textContent = `${total} pending — ${shape}`;
  }
}

async function collectPendingFiles(folder) {
  if (state.demo) {
    const gists = parseGistTOML(DEMO_TOML).filter((g) => g.validation === "pending");
    gists.forEach((g) => { g.sourceUrl = DEMO_FILE_URL; });
    return [{ url: DEMO_FILE_URL, date: "2026-08-21", gists }];
  }
  const items = await listContainer(folder);
  const tomls = items
    .filter((it) => !it.isContainer && it.name.endsWith(".toml"))
    .sort((a, b) => b.name.localeCompare(a.name)); // YYYY-MM-DD.toml sorts newest-first

  const files = [];
  for (const item of tomls) {
    let text;
    try { ({ text } = await readFile(item.url)); } catch (e) { continue; }
    if (isIngested(text)) continue; // the Rate has taken this batch
    const parsed = parseGistTOML(text);
    const pending = parsed.filter((g) => g.validation === "pending");
    pending.forEach((g) => { g.sourceUrl = item.url; });
    files.push({ url: item.url, date: dateOfFile(item.name, parsed), gists: pending });
  }
  return files;
}

// ── loading the deck ───────────────────────────────────────────────────
async function loadGists() {
  saveSetupToLocalStorage();
  const folder = state.sourcePath.replace(/\/?$/, "/");

  let files;
  const cached = state.scan;
  if (cached && cached.folder === folder) {
    files = cached.files;
  } else {
    try {
      files = await collectPendingFiles(folder);
    } catch (e) {
      state.gists = [];
      state.fileDates = [];
      state.loadState = "error";
      resetDeckState();
      showScreen("deck");
      return;
    }
  }

  state.gists = files.flatMap((f) => f.gists);
  state.fileDates = files.filter((f) => f.gists.length).map((f) => f.date);
  state.loadState = !files.length ? "no-files" : (state.gists.length ? "ok" : "none-pending");
  resetDeckState();
  showScreen("deck");
}

function resetDeckState() {
  state.i = 0;
  state.decisions = {};
  state.history = [];
  state.writing = 0;
  state.writeError = null;
  state.batchClosed = false;
  state.lastWriteAt = null;
  state.failures = 0;
}

// ── swipe mechanics — DOM writes only, no re-render mid-drag ────────────
function paint() {
  if (!drag) return;
  const { x, y } = drag;
  const up = Math.max(0, -y);
  cardEl.style.transform = `translate(${x.toFixed(1)}px,${(y * 0.55).toFixed(1)}px) rotate(${(x * 0.035).toFixed(2)}deg)`;
  rejectEl.style.opacity = String(Math.min(1, Math.max(0, -x) / 105));
  validateEl.style.opacity = String(Math.min(1, Math.max(0, x) / 105));
  anagnorisisEl.style.opacity = String(Math.min(1, up / 105));
}

function resetCard() {
  cardEl.style.transition = "transform .3s cubic-bezier(.2,.8,.3,1)";
  cardEl.style.transform = "none";
  cardEl.style.opacity = "1";
  rejectEl.style.opacity = "0";
  validateEl.style.opacity = "0";
  anagnorisisEl.style.opacity = "0";
}

function onDown(e) {
  if (animating || state.i >= state.gists.length) return;
  if (e.target && e.target.closest && e.target.closest("[data-nodrag]")) return;
  drag = { x0: e.clientX, y0: e.clientY, x: 0, y: 0 };
  cardEl.style.transition = "none";
  try { el("card-area").setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
}
function onMove(e) {
  if (!drag) return;
  drag.x = e.clientX - drag.x0;
  drag.y = e.clientY - drag.y0;
  paint();
}
function onUp() {
  if (!drag) return;
  const { x, y } = drag;
  drag = null;
  // Three peers, three directions. Up is a decision now, not a mode switch.
  if (-y > 100 && Math.abs(y) > Math.abs(x)) return commit("anagnorisis");
  if (x > 100) return commit("validated");
  if (x < -100) return commit("rejected");
  resetCard();
}

const FLIGHT = { validated: [460, -24, 12], rejected: [-460, -24, -12], anagnorisis: [0, -620, 0] };

// Optimistic: the card leaves on the gesture, the write follows. A write that
// fails puts the gist back in the deck (see settleWrite) rather than pretending.
function commit(vote) {
  const { i, gists } = state;
  if (animating || i >= gists.length) return;
  const g = gists[i];
  const [fx, fy, rot] = FLIGHT[vote];
  animating = true;
  cardEl.style.transition = "transform .26s cubic-bezier(.3,.7,.3,1), opacity .26s ease";
  cardEl.style.transform = `translate(${fx}px,${fy}px) rotate(${rot}deg)`;
  cardEl.style.opacity = "0";

  const prev = state.decisions[g.id] || null;
  state.decisions = { ...state.decisions, [g.id]: vote };
  state.history = state.history.concat([{ id: g.id, index: i, prev, gist: g }]);
  state.i = i + 1;
  state.writeError = null;
  state.writing += 1;

  writeValidation(g, vote).then(
    () => settleWrite(g, null),
    (err) => settleWrite(g, err),
  );

  setTimeout(() => {
    animating = false;
    cardEl.style.transition = "none";
    cardEl.style.transform = "none";
    cardEl.style.opacity = "1";
    rejectEl.style.opacity = "0";
    validateEl.style.opacity = "0";
    anagnorisisEl.style.opacity = "0";
    if (state.i >= state.gists.length) showScreen("done");
    else renderDeck();
  }, 230);
}

// A write either landed or it didn't. If it didn't, the gist goes back into
// the deck as the next card up — the pod still says "pending", so re-swiping
// it is the whole repair. Undo history is cleared because the indices it
// refers to have just shifted.
function settleWrite(gist, err) {
  state.writing = Math.max(0, state.writing - 1);
  if (!err) {
    state.lastWriteAt = Date.now();
  } else {
    state.failures += 1;
    delete state.decisions[gist.id];
    state.history = [];
    if (err.code === "batch-closed") {
      state.batchClosed = true;
      state.writeError = err.message;
    } else {
      state.writeError = String(err.message || err).slice(0, 70);
      // The gist was never removed from state.gists (commit() only advances
      // the pointer) — it's still sitting at its original index, so putting
      // it back up next is a pointer move, not a re-insertion. Re-inserting
      // here would duplicate it and the deck total would grow every retry.
      const idx = state.gists.indexOf(gist);
      if (idx !== -1) state.i = idx;
    }
  }
  if (state.screen === "deck") renderDeck();
  if (state.screen === "done") renderDone();
}

// Undo has to un-write, or it is a lie: the pod would still read "validated"
// while the UI claimed the swipe was taken back.
function undo() {
  if (animating || !state.history.length) return;
  const last = state.history[state.history.length - 1];
  const target = last.prev || "pending";

  const decisions = { ...state.decisions };
  if (last.prev) decisions[last.id] = last.prev; else delete decisions[last.id];
  state.decisions = decisions;
  state.history = state.history.slice(0, -1);
  state.i = last.index;
  state.writeError = null;
  state.writing += 1;

  writeValidation(last.gist, target).then(
    () => { state.writing = Math.max(0, state.writing - 1); state.lastWriteAt = Date.now(); renderDeck(); },
    (err) => {
      state.writing = Math.max(0, state.writing - 1);
      state.writeError = `couldn't take that back — ${String(err.message || err).slice(0, 50)}`;
      renderDeck();
    },
  );

  showScreen("deck");
  resetCard();
}

// ── rendering ──────────────────────────────────────────────────────────
function render() {
  if (state.screen === "setup") renderSetup();
  if (state.screen === "deck") renderDeck();
  if (state.screen === "done") renderDone();
}

function renderSetup() {
  el("webid-short").textContent = state.webId
    ? state.webId.replace(/^https?:\/\//, "").replace(/\/profile\/card#me$/, "")
    : "offline";
  el("source-input").value = state.sourcePath;
}

const EMPTY_COPY = {
  "no-files": "no open batches in this folder. the cleanup pass writes them here.",
  "none-pending": "nothing pending. next batch after tonight's run.",
  "error": "couldn't read that folder — check the path and your access.",
  "ok": "that's the stack.",
};

function renderDeckStatus() {
  const saveTextEl = el("save-text");
  const saveDotEl = el("save-dot");
  const sinceWrite = state.lastWriteAt ? Math.round((Date.now() - state.lastWriteAt) / 1000) : null;
  let text, toneVar;
  if (state.batchClosed) { text = "batch closed by the rate — the rest rolls over"; toneVar = "--convergence"; }
  else if (state.writeError) { text = state.writeError; toneVar = "--pattern"; }
  else if (state.writing) { text = "saving…"; toneVar = "--convergence"; }
  else if (sinceWrite !== null) { text = `saved ${sinceWrite < 60 ? sinceWrite + "s" : Math.round(sinceWrite / 60) + "m"} ago`; toneVar = "--fresh"; }
  else { text = "nothing swiped yet"; toneVar = "--text-tertiary"; }
  saveTextEl.textContent = text;
  saveTextEl.style.color = `var(${toneVar})`;
  saveDotEl.style.background = `var(${toneVar})`;
  el("undo-btn").classList.toggle("vz-undo-active", state.history.length > 0);
}

function renderDeck() {
  const total = state.gists.length || 1;
  const g = state.gists[state.i];
  const multiDay = state.fileDates.length > 1;
  const newest = state.fileDates[0] || "";
  const dayOf = (gist) => (gist && gist.moment) ? gist.moment.slice(0, 10) : newest;
  const backlog = multiDay && g && dayOf(g) !== newest;

  el("session-date").textContent = (g ? dayOf(g) : newest) + (backlog ? " · backlog" : "");
  el("counter-text").textContent = `${Math.min(state.i + 1, total)} / ${total}`;

  const marksEl = el("marks");
  marksEl.innerHTML = "";
  state.gists.forEach((gi, n) => {
    const d = state.decisions[gi.id];
    let colorVar = "--border-subtle";
    if (d) colorVar = VALIDATION_COLOR_VAR[d] || "--fresh";
    else if (n === state.i) colorVar = "--text-tertiary";
    const mark = document.createElement("span");
    mark.className = "vz-mark";
    mark.style.background = `var(${colorVar})`;
    marksEl.appendChild(mark);
  });

  const finished = !g;
  el("gist-card").hidden = finished;
  document.querySelector(".vz-ghost-card").hidden = finished;
  el("empty-stack").hidden = !finished;
  el("undo-btn").disabled = !state.history.length;

  if (g) {
    el("gist-type").textContent = g.type || "—";
    el("gist-type").style.color = `var(${TYPE_COLOR_VAR[g.type] || "--text-tertiary"})`;
    // A gist carried over from an earlier day has to say so, or it reads as
    // a bug rather than as the backlog it is.
    el("gist-moment").textContent = g.moment ? (backlog ? g.moment : g.moment.slice(11)) : "";
    el("gist-moment").style.color = backlog ? "var(--temporal)" : "var(--text-tertiary)";
    el("gist-title").textContent = g.titre || "";
    el("gist-raw").textContent = g.raw || "";
  } else {
    el("empty-stack").textContent = EMPTY_COPY[state.loadState] || EMPTY_COPY.ok;
  }

  renderDeckStatus();
}

function renderDone() {
  const votes = Object.values(state.decisions);
  const nVal = votes.filter((v) => v === "validated").length;
  const nRej = votes.filter((v) => v === "rejected").length;
  const nAna = votes.filter((v) => v === "anagnorisis").length;
  const n = votes.length;
  const doneLine = `${words[n] || String(n)}${n === 1 ? " gist, " : " gists, "}all accounted for.`;
  const podWrite = !!(session && state.webId && !state.demo);

  el("done-session-date").textContent = state.fileDates.join(" · ") || "—";
  el("done-line").textContent = doneLine;
  el("write-status").textContent = state.batchClosed
    ? "batch closed by the rate — the rest rolls over"
    : (state.failures ? `${state.failures} didn't save — still pending, swipe again` : (state.writing ? "writing…" : (podWrite ? "written back to the batch" : "offline stack — nothing left the browser")));
  el("saved-path").textContent = state.sourcePath;
  el("saved-stamp").textContent = state.lastWriteAt
    ? new Date(state.lastWriteAt).toTimeString().slice(0, 8) + " · " + (podWrite ? "ingestion at 9h" : "local only, sign in to push")
    : "nothing written";
  el("tally-validated").textContent = `${nVal} validated`;
  el("tally-rejected").textContent = `${nRej} rejected`;
  el("tally-anagnorisis").textContent = `${nAna} anagnorisis`;
}

// ── wiring ─────────────────────────────────────────────────────────────
el("provider-input").addEventListener("change", (e) => { state.provider = e.target.value; });
el("login-btn").addEventListener("click", doLogin);
el("demo-btn").addEventListener("click", bootDemo);

el("source-input").addEventListener("change", (e) => { browseTo("source", e.target.value.replace(/\/?$/, "/")); });
el("signout-btn").addEventListener("click", async () => {
  if (session) await session.logout();
  state.webId = null;
  state.demo = false;
  showScreen("login");
});
el("open-stack-btn").addEventListener("click", loadGists);

el("card-area").addEventListener("pointerdown", onDown);
el("card-area").addEventListener("pointermove", onMove);
el("card-area").addEventListener("pointerup", onUp);
el("card-area").addEventListener("pointercancel", onUp);
el("undo-btn").addEventListener("click", undo);

el("close-btn").addEventListener("click", () => {
  state.gists = [];
  resetDeckState();
  showScreen("login");
});

document.addEventListener("keydown", (e) => {
  if (state.screen !== "deck") return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (e.key === "ArrowLeft") commit("rejected");
  else if (e.key === "ArrowRight") commit("validated");
  else if (e.key === "ArrowUp") { e.preventDefault(); commit("anagnorisis"); }
  else if (e.key === "ArrowDown" || e.key === "Backspace") { e.preventDefault(); undo(); }
});

// Keeps the "saved Ns ago" line honest without a re-render of the deck.
setInterval(() => {
  state.now = Date.now();
  if (state.screen === "deck") renderDeckStatus();
}, 1000);

showScreen("login");
initSolid();
