// Valisette — gist swipe-triage app.
//
// Hand-ported from the design handoff (`Valisette Mobile.dc.html` + README.md)
// into plain JS, matching this repo's no-build-step convention (see
// backoffice/pod-api.js). Auth reuses backoffice's dynamic esm.sh import of
// the Inrupt libraries (Solid.namedSession), but with its OWN named Session —
// NOT the shared default session backoffice uses. Sharing the default session
// caused restorePreviousSession's silent-refresh to bounce back to backoffice
// (whichever app logs in last owns the origin's one "current session" pointer
// and its stored redirectUrl); see the comment on Solid.namedSession in
// pod-api.js for the full explanation.
//
// Drag mechanics write straight to DOM `style.transform` on pointermove and
// never go through a re-render (README, "Drag mechanics" — a per-move
// re-render drops frames and loses the gesture). Everything else is driven
// by `render()` after a discrete state transition.

import { Solid } from "/pod-api.js";

const AUTOSAVE_MS = 30000;

const FLAGS = [
  { key: "anagnorisis", emoji: "💡", label: "anagnorisis" },
  { key: "revisit", emoji: "🔂", label: "revisit" },
  { key: "priority", emoji: "⚠️", label: "priority" },
];

const TYPE_COLOR_VAR = {
  decision: "--convergence",
  apprentissage: "--fresh",
  protocole: "--temporal",
};

const EMBEDDED_GISTS = [
  { id: "gist-20260821-001", timestamp: 1787291737, type: "decision", titre: "Cron fixé à 17h UTC (19h Bruxelles) — timezone", moment: "2026-08-21 08:20 CEST", raw: "Correction du décalage UTC/Bruxelles: le cron était programmé pour 19h UTC, déclenché à 21h en été. Fixé à 17h UTC = 19h Bruxelles." },
  { id: "gist-20260821-002", timestamp: 1787292402, type: "apprentissage", titre: "Pipeline Otis validé — 71 traces brutes → 8 gists", moment: "2026-08-21 08:40 CEST", raw: "Run 44 a distillé 71 traces brutes en 8 gists. Le pipeline tient : le taux de compression est stable d'un run à l'autre, et aucune trace n'a été perdue au passage." },
  { id: "gist-20260821-003", timestamp: 1787292645, type: "protocole", titre: "Anagnorisis ajouté au schéma", moment: "2026-08-21 08:50 CEST", raw: "Tag de validation posé à la main pendant le triage. Les gists marqués auront un poids plus élevé dans le graphe." },
  { id: "gist-20260821-004", timestamp: 1787293786, type: "apprentissage", titre: "Vocabulaire Manny : punaise, pas putain", moment: "2026-08-21 09:10 CEST", raw: "Ton corrigé. Palette ajustée : grognements préhistoriques, inspiration Audiard, jamais de vulgarité." },
  { id: "gist-20260821-005", timestamp: 1787294864, type: "decision", titre: "App de triage créée comme tâche kanban", moment: "2026-08-21 11:30 CEST", raw: "Carte kanban t_da7ed1a1 créée. Prototype développé sous le nom Valisette." },
  { id: "gist-20260821-006", timestamp: 1787314088, type: "apprentissage", titre: "Champ moment ajouté au schéma", moment: "2026-08-21 16:00 CEST", raw: "Timestamp UNIX conservé pour SPARQL. Champ moment ISO 8601 + fuseau pour l'affichage humain." },
  { id: "gist-20260821-007", timestamp: 1787322848, type: "protocole", titre: "Incrémental Otis réparé", moment: "2026-08-21 20:00 CEST", raw: "Bug : session_ids comme clé de dédup perdaient les messages chevauchant deux crons. Fix : tracker le dernier message_id par session." },
];

// ── TOML parser/writer — ported near-verbatim from Valisette.html ────────
function parseGistTOML(text) {
  const gists = [];
  let current = null, rawBuffer = null, inRaw = false, inGist = false;
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (t === "[[gist]]") {
      if (current && current.id) gists.push(current);
      current = { tags: [] };
      rawBuffer = null; inRaw = false; inGist = true;
      continue;
    }
    if (!inGist || !current) continue;
    if (inRaw) {
      if (t === '"""') { current.raw = (current.raw || "") + rawBuffer; inRaw = false; rawBuffer = null; }
      else { rawBuffer = (rawBuffer || "") + line + "\n"; }
      continue;
    }
    if (t.startsWith('raw = """')) {
      inRaw = true; rawBuffer = "";
      const after = t.slice(9);
      if (after && after !== '"""') rawBuffer = after + "\n";
      continue;
    }
    const eq = t.indexOf("="); if (eq === -1) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if (val.startsWith('"') && val.endsWith('"') && val.length > 1) val = val.slice(1, -1);
    if (key === "id") current.id = val;
    else if (key === "timestamp") current.timestamp = parseInt(val, 10);
    else if (key === "type") current.type = val;
    else if (key === "titre") current.titre = val;
    else if (key === "moment") current.moment = val;
  }
  if (current && current.id) gists.push(current);
  return gists;
}

function buildTOML(gists, decisions, date) {
  const ids = Object.keys(decisions);
  let out = `# Valisette — triage ${date}\n# written ${new Date().toISOString()}\n\n[triage_session]\nversion_schema = "v1"\ndate = "${date}"\ngists_count = ${ids.length}\n`;
  for (const g of gists) {
    const d = decisions[g.id];
    if (!d) continue;
    out += `\n[[gist]]\nid = "${g.id}"\ntimestamp = ${g.timestamp || 0}\ntype = "${g.type || ""}"\ntitre = "${String(g.titre || "").replace(/"/g, '\\"')}"\nvalidation = "${d.validation}"\n`;
    if (g.moment) out += `moment = "${g.moment}"\n`;
    if (d.flags && d.flags.length) out += `tags = [${d.flags.map((f) => `"${f}"`).join(", ")}]\n`;
    if (d.note) out += `note = "${d.note.replace(/"/g, '\\"')}"\n`;
    out += `raw = """\n${g.raw || ""}\n"""\n`;
  }
  return out;
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
  outPath: "",
  gists: [],
  i: 0,
  decisions: {},
  flags: {},
  comment: "",
  history: [],
  pending: [],
  pendingSince: null,
  lastSaveAt: null,
  savedPath: null,
  saveError: null,
  now: Date.now(),
  trayOpen: false,
};

let session = null; // this app's own isolated Inrupt Session (see header comment)
let libs = null;    // { authn, sc } — loaded once, shared with the session above
let saving = false;
let animating = false;
let drag = null;

const el = (id) => document.getElementById(id);
const screens = { login: el("screen-login"), setup: el("screen-setup"), deck: el("screen-deck"), done: el("screen-done") };
const cardEl = el("gist-card");
const rejectEl = el("reject-overlay");
const validateEl = el("validate-overlay");
const trayEl = el("flag-tray");

// ── persistence ────────────────────────────────────────────────────────
function sessionDateOf(s) {
  return (s.gists[0] && s.gists[0].moment) ? s.gists[0].moment.slice(0, 10) : new Date().toISOString().slice(0, 10);
}
function sessionStorageKey(s) {
  return `valisette:session:${sessionDateOf(s)}`;
}
function saveSessionToLocalStorage() {
  try {
    localStorage.setItem(sessionStorageKey(state), JSON.stringify({
      gists: state.gists, decisions: state.decisions, i: state.i, history: state.history,
      pending: state.pending, pendingSince: state.pendingSince, lastSaveAt: state.lastSaveAt,
      savedPath: state.savedPath, sourcePath: state.sourcePath, outPath: state.outPath,
      webId: state.webId, demo: state.demo,
    }));
  } catch (e) { /* storage unavailable — swipes still work, just not resumable */ }
}
function restoreSessionFromLocalStorage(dateHint) {
  try {
    const raw = localStorage.getItem(`valisette:session:${dateHint}`);
    if (!raw) return false;
    const saved = JSON.parse(raw);
    if (!saved.gists || !saved.gists.length) return false;
    Object.assign(state, {
      gists: saved.gists, decisions: saved.decisions || {}, i: saved.i || 0,
      history: saved.history || [], pending: saved.pending || [], pendingSince: saved.pendingSince || null,
      lastSaveAt: saved.lastSaveAt || null, savedPath: saved.savedPath || null,
    });
    return true;
  } catch (e) { return false; }
}
function saveSetupToLocalStorage() {
  try {
    localStorage.setItem("valisette:setup", JSON.stringify({ sourcePath: state.sourcePath, outPath: state.outPath }));
  } catch (e) { /* ignore */ }
}
function restoreSetupFromLocalStorage() {
  try {
    const raw = localStorage.getItem("valisette:setup");
    if (!raw) return false;
    const saved = JSON.parse(raw);
    if (saved.sourcePath) state.sourcePath = saved.sourcePath;
    if (saved.outPath) state.outPath = saved.outPath;
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

// See the long comment on Solid.namedSession in pod-api.js: this origin's
// silent-restore pointer is global, shared with backoffice, so we only ask
// for a restore when that pointer already belongs to Valisette's own
// session id — otherwise fall through to the ordinary login screen instead
// of silently bouncing to whichever app logged in more recently.
const SESSION_ID = "valisette";

async function initSolid() {
  setLoginStatus("checking session…", "--text-tertiary");
  try {
    ({ session, libs } = await Solid.namedSession(SESSION_ID));
    state.libReady = true;
    const canRestore = Solid.canRestore(SESSION_ID);
    const info = await session.handleIncomingRedirect({ restorePreviousSession: canRestore });
    if (info && info.isLoggedIn) {
      state.webId = info.webId;
      const root = podRootFrom(info.webId);
      state.sourcePath = root + "gists/";
      state.outPath = root + "triage/";
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

// ── pod read/write — thin wrappers over solid-client, this session's fetch ──
function baseName(url) {
  const u = url.replace(/\/$/, "");
  return decodeURIComponent(u.slice(u.lastIndexOf("/") + 1)) || "/";
}
async function listContainer(url) {
  const noStoreFetch = (u, opts = {}) => session.fetch(u, { ...opts, cache: "no-store" });
  const ds = await libs.sc.getSolidDataset(url, { fetch: noStoreFetch });
  return libs.sc.getContainedResourceUrlAll(ds).map((u) => ({ url: u, name: baseName(u), isContainer: u.endsWith("/") }));
}
async function readText(url) {
  const file = await libs.sc.getFile(url, { fetch: session.fetch });
  return await file.text();
}
async function writeText(url, text, type) {
  await libs.sc.overwriteFile(url, new Blob([text], { type }), { contentType: type, fetch: session.fetch });
}

// ── source/output folder chips — real pod listing, static fallback ─────
const STATIC_FOLDER_HINTS = ["gists/", "otis/out/", "inbox/"];
const RECENTS_KEY = "valisette:recentFolders";
const RECENTS_MAX = 5;

// { source: { root, path }, output: { root, path } } — root is fixed (pod
// storage root), path is whatever container is currently drilled into.
const browse = { source: {}, output: {} };

function loadRecents() {
  try { return JSON.parse(localStorage.getItem(RECENTS_KEY) || "[]"); } catch (e) { return []; }
}
function saveRecent(path) {
  try {
    const list = [path, ...loadRecents().filter((p) => p !== path)].slice(0, RECENTS_MAX);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(list));
  } catch (e) { /* ignore */ }
}
function renderRecents(group) {
  const wrap = el(`${group}-recents`);
  const list = loadRecents();
  wrap.hidden = list.length === 0;
  wrap.innerHTML = "";
  list.forEach((path) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "vz-chip vz-chip-recent";
    btn.setAttribute("data-nodrag", "");
    btn.title = path;
    btn.textContent = path.startsWith(browse[group].root) ? path.slice(browse[group].root.length) || "(root)" : path;
    btn.addEventListener("click", () => browseTo(group, path));
    wrap.appendChild(btn);
  });
}

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

// Drill into (or jump to) `url` for the given group ("source" or "output"):
// updates the input (which always mirrors the current drilled path — no
// separate "select" step, per the UX review), the breadcrumb, and re-lists
// that container's own sub-containers as the next chip row.
async function browseTo(group, url) {
  browse[group].path = url;
  const inputId = group === "source" ? "source-input" : "output-input";
  el(inputId).value = url;
  if (group === "source") state.sourcePath = url; else state.outPath = url;
  renderBreadcrumb(group);
  if (state.demo) {
    renderChipRow(group, url, url === browse[group].root ? STATIC_FOLDER_HINTS : []);
    return;
  }
  try {
    const items = await listContainer(url);
    const names = items.filter((it) => it.isContainer).map((it) => it.name + "/");
    renderChipRow(group, url, names);
  } catch (e) {
    renderChipRow(group, url, []);
  }
}

function initBrowsers(root) {
  browse.source = { root, path: state.sourcePath };
  browse.output = { root, path: state.outPath };
  renderRecents("source");
  renderRecents("output");
  browseTo("source", state.sourcePath);
  browseTo("output", state.outPath);
}

function bootDemo() {
  state.demo = true;
  state.webId = "https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me";
  state.sourcePath = "https://pod.nicolasdb.eu/hyperscope_ndb/gists/";
  state.outPath = "https://pod.nicolasdb.eu/hyperscope_ndb/triage/";
  showScreen("setup");
  initBrowsers("https://pod.nicolasdb.eu/hyperscope_ndb/");
}

// ── loading gists — real container listing, no hardcoded-date fallback ──
async function loadGists() {
  saveRecent(state.sourcePath);
  saveRecent(state.outPath);
  if (state.demo) {
    state.gists = EMBEDDED_GISTS.slice();
    state.i = 0;
    restoreSessionFromLocalStorage(sessionDateOf(state));
    showScreen("deck");
    return;
  }
  saveSetupToLocalStorage();
  try {
    const items = await listContainer(state.sourcePath.replace(/\/?$/, "/"));
    const tomls = items
      .filter((it) => !it.isContainer && it.name.endsWith(".toml"))
      .sort((a, b) => b.name.localeCompare(a.name)); // YYYY-MM-DD.toml sorts newest-first
    let gists = [];
    for (const item of tomls) {
      const text = await readText(item.url);
      const parsed = parseGistTOML(text);
      if (parsed.length) { gists = parsed; break; }
    }
    state.gists = gists;
  } catch (e) {
    state.gists = [];
  }
  state.i = 0;
  restoreSessionFromLocalStorage(sessionDateOf(state));
  showScreen("deck");
}

// ── autosave / write ───────────────────────────────────────────────────
function dueForSave() {
  return state.pending.length > 0 && state.pendingSince && Date.now() - state.pendingSince >= AUTOSAVE_MS;
}

async function flushSave() {
  if (saving || !state.pending.length) return;
  saving = true;
  const date = sessionDateOf(state);
  const toml = buildTOML(state.gists, state.decisions, date);
  const url = state.outPath.replace(/\/?$/, "/") + `triage-${date}.toml`;
  let error = null;
  if (session && session.info.isLoggedIn) {
    try {
      await writeText(url, toml, "text/plain");
    } catch (e) {
      error = String((e && e.message) || e).slice(0, 60);
    }
  }
  saving = false;
  if (!error) {
    state.pending = [];
    state.pendingSince = null;
    state.lastSaveAt = Date.now();
  }
  state.savedPath = url;
  state.saveError = error;
  saveSessionToLocalStorage();
  renderDeckStatus();
  if (state.screen === "done") renderDone();
}

// ── swipe mechanics — DOM writes only, no re-render mid-drag ────────────
function paintTray(up) {
  const k = Math.min(1, up / 72);
  const open = state.trayOpen;
  const a = Math.max(open ? 1 : 0, k);
  trayEl.style.opacity = String(a);
  trayEl.style.transform = `translateY(${(-6 + 6 * a).toFixed(2)}px)`;
  trayEl.style.pointerEvents = (open || k > 0.9) ? "auto" : "none";
}

function paint() {
  if (!drag) return;
  const { x, y } = drag;
  const up = Math.max(0, -y);
  const lean = up * 0.42;
  cardEl.style.transform = `translate(${x.toFixed(1)}px,${(-lean + Math.max(0, y) * 0.2).toFixed(1)}px) rotate(${(x * 0.035).toFixed(2)}deg)`;
  const rk = Math.min(1, Math.max(0, -x) / 105);
  const vk = Math.min(1, Math.max(0, x) / 105);
  rejectEl.style.opacity = String(rk);
  validateEl.style.opacity = String(vk);
  paintTray(up);
}

function resetCard() {
  cardEl.style.transition = "transform .3s cubic-bezier(.2,.8,.3,1)";
  cardEl.style.transform = "none";
  cardEl.style.opacity = "1";
  rejectEl.style.opacity = "0";
  validateEl.style.opacity = "0";
  paintTray(0);
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
  if (x > 100) return commit("validated");
  if (x < -100) return commit("rejected");
  if (-y > 64) { state.trayOpen = true; resetCard(); return; }
  resetCard();
}

function commit(vote) {
  const { i, gists } = state;
  if (animating || i >= gists.length) return;
  const g = gists[i];
  const flags = Object.keys(state.flags).filter((k) => state.flags[k]);
  const decision = { validation: vote, flags, note: state.comment.trim(), moment: g.moment || null };
  animating = true;
  cardEl.style.transition = "transform .26s cubic-bezier(.3,.7,.3,1), opacity .26s ease";
  cardEl.style.transform = `translate(${vote === "validated" ? 460 : -460}px,-24px) rotate(${vote === "validated" ? 12 : -12}deg)`;
  cardEl.style.opacity = "0";
  setTimeout(() => {
    animating = false;
    const prevDecision = state.decisions[g.id] || null;
    state.decisions = { ...state.decisions, [g.id]: decision };
    state.pending = state.pending.filter((p) => p !== g.id).concat([g.id]);
    if (!state.pendingSince) state.pendingSince = Date.now();
    state.history = state.history.concat([{ id: g.id, index: state.i, prev: prevDecision }]);
    state.i = state.i + 1;
    state.flags = {};
    state.comment = "";
    el("comment-input").value = "";
    state.trayOpen = false;
    saveSessionToLocalStorage();
    cardEl.style.transition = "none";
    cardEl.style.transform = "none";
    cardEl.style.opacity = "1";
    rejectEl.style.opacity = "0";
    validateEl.style.opacity = "0";
    paintTray(0);
    if (state.i >= state.gists.length) {
      showScreen("done");
      flushSave();
    } else {
      renderDeck();
    }
  }, 230);
}

function undo() {
  const { history, pending } = state;
  if (!history.length || !pending.length) return;
  const last = history[history.length - 1];
  if (pending.indexOf(last.id) === -1) return;
  const restored = state.decisions[last.id];
  const decisions = { ...state.decisions };
  if (last.prev) decisions[last.id] = last.prev; else delete decisions[last.id];
  state.decisions = decisions;
  state.pending = state.pending.filter((p) => p !== last.id);
  if (!state.pending.length) state.pendingSince = null;
  state.history = state.history.slice(0, -1);
  state.i = last.index;
  const flags = {};
  (restored && restored.flags || []).forEach((f) => { flags[f] = true; });
  state.flags = flags;
  state.comment = (restored && restored.note) || "";
  el("comment-input").value = state.comment;
  state.trayOpen = false;
  saveSessionToLocalStorage();
  showScreen("deck");
  resetCard();
}

function toggleFlag(key) {
  state.flags = { ...state.flags, [key]: !state.flags[key] };
  renderFlags();
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
  el("output-input").value = state.outPath;
  el("out-preview").textContent = `writes triage-${new Date().toISOString().slice(0, 10)}.toml — RDF-ready schema`;
  el("stack-line").textContent = state.demo
    ? "offline stack · 7 gists embedded"
    : "reads today, falls back to the last day found";
}

function renderFlags() {
  document.querySelectorAll(".vz-flag-btn").forEach((btn) => {
    const key = btn.dataset.flag;
    btn.classList.toggle("vz-flag-on", !!state.flags[key]);
  });
  const activeEl = el("active-flags");
  activeEl.innerHTML = "";
  FLAGS.filter((f) => state.flags[f.key]).forEach((f) => {
    const span = document.createElement("span");
    span.className = "vz-active-flag";
    span.style.setProperty("--flag-color", f.key === "anagnorisis" ? "var(--anagnorisis)" : f.key === "revisit" ? "var(--temporal)" : "var(--convergence)");
    span.textContent = `${f.emoji} ${f.label}`;
    activeEl.appendChild(span);
  });
}

function renderDeckStatus() {
  const secsPending = state.pendingSince ? Math.max(0, Math.ceil((AUTOSAVE_MS - (Date.now() - state.pendingSince)) / 1000)) : 0;
  const sinceSave = state.lastSaveAt ? Math.round((Date.now() - state.lastSaveAt) / 1000) : null;
  const saveTextEl = el("save-text");
  const saveDotEl = el("save-dot");
  let text, toneVar;
  if (state.saveError) { text = `save failed — ${state.saveError} · retrying`; toneVar = "--pattern"; }
  else if (state.pending.length) { text = `${state.pending.length} held · saving in ${secsPending}s`; toneVar = "--convergence"; }
  else if (sinceSave !== null) { text = `saved ${sinceSave < 60 ? sinceSave + "s" : Math.round(sinceSave / 60) + "m"} ago`; toneVar = "--fresh"; }
  else { text = "nothing to save yet"; toneVar = "--text-tertiary"; }
  saveTextEl.textContent = text;
  saveTextEl.style.color = `var(${toneVar})`;
  saveDotEl.style.background = `var(${toneVar})`;
  el("undo-btn").classList.toggle("vz-undo-active", !!(state.history.length && state.pending.length));
}

function renderDeck() {
  const total = state.gists.length || 1;
  el("session-date").textContent = sessionDateOf(state);
  el("counter-text").textContent = `${Math.min(state.i + 1, total)} / ${total}`;

  const marksEl = el("marks");
  marksEl.innerHTML = "";
  state.gists.forEach((g, n) => {
    const d = state.decisions[g.id];
    let colorVar = "--border-subtle";
    if (d) colorVar = d.validation === "rejected" ? "--pattern" : (d.flags && d.flags.length ? "--anagnorisis" : "--fresh");
    else if (n === state.i) colorVar = "--text-tertiary";
    const mark = document.createElement("span");
    mark.className = "vz-mark";
    mark.style.background = `var(${colorVar})`;
    marksEl.appendChild(mark);
  });

  const g = state.gists[state.i];
  const finished = !g;
  el("gist-card").hidden = finished;
  document.querySelector(".vz-ghost-card").hidden = finished;
  el("empty-stack").hidden = !finished;
  el("comment-input").disabled = finished;
  el("undo-btn").disabled = finished && !state.history.length;

  if (g) {
    el("gist-type").textContent = g.type || "—";
    el("gist-type").style.color = `var(${TYPE_COLOR_VAR[g.type] || "--text-tertiary"})`;
    el("gist-moment").textContent = g.moment ? g.moment.slice(11) : "";
    el("gist-title").textContent = g.titre || "";
    el("gist-raw").textContent = g.raw || "";
    el("comment-input").value = state.comment;
  } else if (state.gists.length === 0) {
    el("empty-stack").textContent = "couldn't find any gists to triage in this source.";
  }

  renderFlags();
  renderDeckStatus();
}

function renderDone() {
  const tallyList = Object.keys(state.decisions).map((k) => state.decisions[k]);
  const nVal = tallyList.filter((d) => d.validation === "validated").length;
  const nRej = tallyList.filter((d) => d.validation === "rejected").length;
  const nFlag = tallyList.filter((d) => d.flags && d.flags.length).length;
  const n = tallyList.length;
  const doneLine = `${words[n] || String(n)}${n === 1 ? " gist, " : " gists, "}all accounted for.`;
  const sessionDate = sessionDateOf(state);
  const podWrite = !!(session && state.webId && !state.demo);

  el("done-session-date").textContent = sessionDate;
  el("done-line").textContent = doneLine;
  el("write-status").textContent = state.saveError
    ? "write failed"
    : (state.pending.length ? "writing…" : (podWrite ? "written to your pod" : "held locally — no pod connected"));
  el("saved-path").textContent = state.savedPath || (state.outPath.replace(/\/?$/, "/") + `triage-${sessionDate}.toml`);
  el("saved-stamp").textContent = state.lastSaveAt
    ? new Date(state.lastSaveAt).toTimeString().slice(0, 8) + " · " + (podWrite ? "PUT 200" : "local only, sign in to push")
    : "pending";
  el("tally-validated").textContent = `${nVal} validated`;
  el("tally-rejected").textContent = `${nRej} rejected`;
  el("tally-flagged").textContent = `${nFlag} flagged`;
}

// ── wiring ─────────────────────────────────────────────────────────────
el("provider-input").addEventListener("change", (e) => { state.provider = e.target.value; });
el("login-btn").addEventListener("click", doLogin);
el("demo-btn").addEventListener("click", bootDemo);

el("source-input").addEventListener("change", (e) => { browseTo("source", e.target.value.replace(/\/?$/, "/")); });
el("output-input").addEventListener("change", (e) => {
  browseTo("output", e.target.value.replace(/\/?$/, "/"));
  el("out-preview").textContent = `writes triage-${new Date().toISOString().slice(0, 10)}.toml — RDF-ready schema`;
});
el("signout-btn").addEventListener("click", async () => {
  if (session) await session.logout();
  state.webId = null;
  state.demo = false;
  showScreen("login");
});
el("open-stack-btn").addEventListener("click", loadGists);

document.querySelectorAll(".vz-flag-btn").forEach((btn) => {
  btn.addEventListener("click", () => toggleFlag(btn.dataset.flag));
});
el("card-area").addEventListener("pointerdown", onDown);
el("card-area").addEventListener("pointermove", onMove);
el("card-area").addEventListener("pointerup", onUp);
el("card-area").addEventListener("pointercancel", onUp);
el("undo-btn").addEventListener("click", undo);
el("comment-input").addEventListener("change", (e) => { state.comment = e.target.value; });

el("close-btn").addEventListener("click", () => {
  state.screen = "login";
  state.i = 0;
  state.decisions = {};
  state.history = [];
  state.pending = [];
  state.pendingSince = null;
  state.gists = [];
  showScreen("login");
});

document.addEventListener("keydown", (e) => {
  if (state.screen !== "deck") return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (e.key === "ArrowLeft") commit("rejected");
  else if (e.key === "ArrowRight") commit("validated");
  else if (e.key === "ArrowUp") { e.preventDefault(); state.trayOpen = true; resetCard(); }
  else if (e.key === "ArrowDown" || e.key === "Backspace") { e.preventDefault(); undo(); }
});

setInterval(() => {
  state.now = Date.now();
  if (state.screen === "deck") renderDeckStatus();
  if (dueForSave()) flushSave();
}, 1000);

showScreen("login");
initSolid();
