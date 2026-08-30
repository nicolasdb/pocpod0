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
};

// Independent tags, written to `triage_flags` per schema-v1.md §4 (revised
// 2026-08-30) — never the pipeline's own `tags` (topical keywords, different
// field, don't touch it). Anagnorisis moved here from being its own
// `validation` outcome: the flip-flop between the two kept recurring because
// forcing a recognition moment onto the swipe direction was the wrong shape
// for it — it's an orthogonal tag on whichever outcome the swipe already
// carries, same as revisit/priority. The Weaver-side graph weighting this
// drives is unchanged; only which field it's read from moves — see
// schema-v1.md §4 and the handoff note for what the ingestion side must
// adjust for gists already swiped under the old contract.
const FLAGS = [
  { key: "revisit", emoji: "🔂", label: "revisit", colorVar: "--temporal" },
  { key: "priority", emoji: "⚠️", label: "priority", colorVar: "--convergence" },
  { key: "anagnorisis", emoji: "💡", label: "anagnorisis", colorVar: "--anagnorisis" },
];

// Demo stack — two days, held as TOML *strings* rather than plain objects so
// the offline path exercises the real parse/patch code instead of a parallel
// one, and now also the real listContainer/collectPendingFiles path (see
// listContainer's demo branch) so demo and pod never drift apart.
//
// Content is a deliberate onboarding storyline, not real capture data: each
// card teaches one Valisette mechanic, in the order you meet it under the
// default oldest-first sort — swipe right/left, the flag tray, anagnorisis,
// the note field, undo, and the writeback contract. Real schema throughout
// (id/timestamp/type/titre/moment/validation/raw) so it's a genuine parse.
const DEMO_FILE_URL_1 = "demo:///capture/gists/2026-08-20.toml";
const DEMO_TOML_1 = `# gists 2026-08-20 — welcome
[gist_session]
version_schema = "v1"
date = "2026-08-20"
ingested = false

[[gist]]
id = "gist-20260820-001"
timestamp = 1787205337
type = "protocole"
titre = "Bienvenue — c'est quoi un gist ?"
moment = "2026-08-20 08:20 CEST"
validation = "pending"
raw = """
Un gist, c'est une décision ou un apprentissage distillé d'une session — une carte à la fois. Cette pile est la file de triage : chaque swipe écrit votre appel directement dans le fichier du pod.
"""

[[gist]]
id = "gist-20260820-002"
timestamp = 1787206002
type = "decision"
titre = "Swipe à droite = validated"
moment = "2026-08-20 08:40 CEST"
validation = "pending"
raw = """
Glissez la carte vers la droite pour la garder. validation devient "validated" dans le TOML, rien d'autre ne change.
"""

[[gist]]
id = "gist-20260820-003"
timestamp = 1787206245
type = "decision"
titre = "Swipe à gauche = rejected"
moment = "2026-08-20 08:50 CEST"
validation = "pending"
raw = """
Glissez vers la gauche pour écarter. Le gist reste comme trace — validation devient "rejected", rien n'est supprimé.
"""

[[gist]]
id = "gist-20260820-004"
timestamp = 1787207386
type = "apprentissage"
titre = "Le bandeau de tags : ça arme, ça ne commit pas"
moment = "2026-08-20 09:10 CEST"
validation = "pending"
raw = """
Tapoter revisit ou priority marque juste un choix — rien n'est écrit tant que vous ne swipez pas. Le tag part avec le swipe suivant, dans un sens ou dans l'autre.
"""
`;

const DEMO_FILE_URL_2 = "demo:///capture/gists/2026-08-21.toml";
const DEMO_TOML_2 = `# gists 2026-08-21 — the rest of the story
[gist_session]
version_schema = "v1"
date = "2026-08-21"
ingested = false

[[gist]]
id = "gist-20260821-001"
timestamp = 1787291737
type = "protocole"
titre = "💡 anagnorisis, un tag pas une direction"
moment = "2026-08-21 08:20 CEST"
validation = "pending"
raw = """
Tapotez 💡 comme revisit ou priority — ça marque un déclic, ça ne décide de rien. Swipez ensuite dans le sens que le gist mérite : le tag part dans triage_flags, la validation reste validated ou rejected.
"""

[[gist]]
id = "gist-20260821-002"
timestamp = 1787292402
type = "apprentissage"
titre = "Le champ commentaire, optionnel"
moment = "2026-08-21 08:40 CEST"
validation = "pending"
raw = """
Le champ sous la carte s'écrit comme note à côté du gist — un contexte que vous seul(e) aviez en tête au moment du triage.
"""

[[gist]]
id = "gist-20260821-003"
timestamp = 1787292645
type = "decision"
titre = "↺ annule le dernier swipe"
moment = "2026-08-21 08:50 CEST"
validation = "pending"
raw = """
Le bouton undo n'est pas cosmétique : il réécrit vraiment le pod à l'état précédent. Un swipe repris reste un swipe honnête.
"""

[[gist]]
id = "gist-20260821-004"
timestamp = 1787293786
type = "protocole"
titre = "Vos appels repartent directement sur le pod"
moment = "2026-08-21 09:10 CEST"
validation = "pending"
raw = """
Il n'y a pas de brouillon local séparé. Chaque swipe relit le fichier TOML du jour, patche uniquement validation (et note/triage_flags si présents) sur la ligne du bon gist, puis le réécrit avec un If-Match — si une autre écriture a eu lieu entre-temps, Valisette relit et repatche au lieu d'écraser à l'aveugle. Rien d'autre dans le fichier n'est touché : les champs que l'app ne connaît pas, comme ceux que la Rate ajoute à l'ingestion, survivent intacts. Si l'écriture échoue en cours de route, le gist reste "pending" côté pod, donc le pire des cas est un re-swipe, jamais un état à moitié écrit.
"""
`;

// Demo writes go here instead of the network, through the same patch path.
const demoFiles = { [DEMO_FILE_URL_1]: DEMO_TOML_1, [DEMO_FILE_URL_2]: DEMO_TOML_2 };

// ── TOML read/patch ────────────────────────────────────────────────────
const RAW_OPEN = 'raw = """';

function unquote(v) {
  const t = v.trim();
  if (!(t.startsWith('"') && t.endsWith('"') && t.length > 1)) return t;
  return t.slice(1, -1).replace(/\\(.)/g, "$1");
}

// Only needs to handle a flat array of quoted strings — the shape both
// `tags` and `triage_flags` use.
function parseArrayLiteral(v) {
  const t = v.trim();
  if (!t.startsWith("[") || !t.endsWith("]")) return [];
  const inner = t.slice(1, -1).trim();
  if (!inner) return [];
  return inner.split(",").map((s) => unquote(s.trim())).filter(Boolean);
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
    const rawVal = t.slice(eq + 1);
    if (key === "triage_flags") { current.flags = parseArrayLiteral(rawVal); continue; }
    const val = unquote(rawVal);
    if (key === "id") current.id = val;
    else if (key === "timestamp") current.timestamp = parseInt(val, 10);
    else if (key === "type") current.type = val;
    else if (key === "titre") current.titre = val;
    else if (key === "moment") current.moment = val;
    else if (key === "validation") current.validation = val;
    else if (key === "note") current.note = val;
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

function tomlString(v) {
  return `"${String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function tomlStringArray(items) {
  return `[${items.map(tomlString).join(", ")}]`;
}

// String-level patch — deliberately NOT parse-then-rebuild. The file is
// written by the cleanup pass, not by us: a rebuild would silently drop any
// field this app doesn't know about (`ingested` being the one that matters
// today, and whatever the pipeline adds tomorrow). Only `validation` (always)
// and `note`/`triage_flags` (when non-empty) change; every other field,
// including pipeline-added ones, survives byte-identical. Returns null when
// the gist, or its validation line, isn't there — a failed patch has to
// surface, never pass as a silent no-op.
//
// `triage_flags` is Valisette's own field — deliberately not the pipeline's
// `tags` (topical keywords like ["cron","timezone"], already present on every
// gist and meaning something entirely different). Reusing that key would
// corrupt real pipeline data on the next patch.
function patchGistFields(text, gistId, validation, note, flags) {
  const lines = text.split("\n");
  let inRaw = false, inGist = false, curId = null, valLine = -1, noteLine = -1, flagsLine = -1;
  let target = null;

  const closeBlock = () => {
    if (inGist && curId === gistId && valLine !== -1 && !target) {
      target = { valLine, noteLine, flagsLine };
    }
    curId = null; valLine = -1; noteLine = -1; flagsLine = -1;
  };

  for (let n = 0; n < lines.length && !target; n++) {
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
    else if (key === "note") noteLine = n;
    else if (key === "triage_flags") flagsLine = n;
  }
  if (!target) closeBlock();

  if (!target) return null;
  const indent = lines[target.valLine].match(/^\s*/)[0];
  lines[target.valLine] = `${indent}validation = ${tomlString(validation)}`;

  // Insert after validation, in a stable order, so a fresh insert doesn't
  // shift a line the other field already patched this same call. An empty
  // note/flags value removes an existing line outright — undo has to be able
  // to erase a field a swipe just added, not merely leave it untouched.
  let insertAt = target.valLine + 1;
  if (note) {
    const noteText = `${indent}note = ${tomlString(note)}`;
    if (target.noteLine !== -1) { lines[target.noteLine] = noteText; }
    else { lines.splice(insertAt, 0, noteText); insertAt++; if (target.flagsLine >= insertAt - 1 && target.flagsLine !== -1) target.flagsLine++; }
  } else if (target.noteLine !== -1) {
    lines.splice(target.noteLine, 1);
    if (target.flagsLine > target.noteLine) target.flagsLine--;
    if (insertAt > target.noteLine) insertAt--;
  }
  if (flags && flags.length) {
    const flagsText = `${indent}triage_flags = ${tomlStringArray(flags)}`;
    if (target.flagsLine !== -1) lines[target.flagsLine] = flagsText;
    else lines.splice(insertAt, 0, flagsText);
  } else if (target.flagsLine !== -1) {
    lines.splice(target.flagsLine, 1);
  }
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

// Local date+hour for the card header — sv-SE gives YYYY-MM-DD directly, no
// manual padding needed for the date half; the time half still needs it.
function localDateHour(ts) {
  if (!ts) return null;
  const d = new Date(ts * 1000);
  const date = d.toLocaleDateString("sv-SE");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${date} · ${hh}:${mm}`;
}

// ── app state ──────────────────────────────────────────────────────────
const state = {
  screen: "login",
  provider: "https://pod.nicolasdb.eu",
  webId: null,
  demo: false,
  authBusy: false,
  libReady: false,
  sourcePath: "",
  sortMode: "oldest",  // "oldest" | "newest" — file order within the deck; see collectPendingFiles
  gists: [],           // pending gists only, ordered per sortMode; each carries sourceUrl
  fileDates: [],       // distinct source dates present in the deck, ordered per sortMode
  loadState: "ok",    // ok | no-files | none-pending | error
  i: 0,
  decisions: {},
  history: [],
  writing: 0,
  writeError: null,
  batchClosed: false,     // true only while the deck's own current file is closed
  closedFiles: new Set(), // sourceUrls that came back batch-closed this session
  lastWriteAt: null,
  failures: 0,
  pulseGroup: null, // sourceUrl whose group just completed — one-shot mark pulse, cleared after paint
  comment: "",
  flags: {}, // { [flagKey]: true } — toggled in the tray, committed with the next swipe
};

let session = null; // this app's own isolated Inrupt Session (see header comment)
let libs = null;    // { authn, sc } — loaded once, shared with the session above
let animating = false;
let drag = null;
// Which gist's note is currently loaded into #comment-input — so a
// renderDeck() triggered by an async write settling (e.g. after undo)
// doesn't stomp an in-progress edit for the still-displayed card.
let commentLoadedFor = null;
// Which gist's raw text is currently expanded (double-tap or the "more"
// hint) — cleared whenever renderDeck shows a different gist.
let rawExpandedFor = null;
let lastTapAt = 0, lastTapX = 0, lastTapY = 0;

const el = (id) => document.getElementById(id);
const screens = { login: el("screen-login"), setup: el("screen-setup"), deck: el("screen-deck"), done: el("screen-done") };
const cardEl = el("gist-card");
const rejectEl = el("reject-overlay");
const validateEl = el("validate-overlay");

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
  // Demo runs through the exact same collectPendingFiles path as a real pod —
  // no separate demo shortcut — so the two never drift apart. The only demo
  // seam is here and in readFile/writeFile below.
  if (state.demo) {
    return Object.keys(demoFiles).map((u) => ({ url: u, name: baseName(u), isContainer: false }));
  }
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
async function writeValidation(gist, value, note = "", flags = []) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const { text, etag } = await readFile(gist.sourceUrl);
    if (isIngested(text)) {
      const e = new Error("this batch was ingested — remaining gists roll to the next one");
      e.code = "batch-closed";
      throw e;
    }
    const patched = patchGistFields(text, gist.id, value, note, flags);
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
      if (e.status === 412) {
        if (attempt === 0) continue;
        // Two stale writes in a row means something is actively contending
        // for this file — treat it the same as an ingested batch closing.
        const closed = new Error("this batch keeps moving under us — remaining gists roll to the next one");
        closed.code = "batch-closed";
        throw closed;
      }
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

// No pod behind demo mode, so no folder to pick — straight to the deck.
// sourcePath is still a folder shape (listContainer's demo branch ignores
// its value), so demo runs through the identical collectPendingFiles path a
// real pod does: same sort, same multi-day grouping, same ingested check.
function bootDemo() {
  state.demo = true;
  state.webId = "https://pod.nicolasdb.eu/hyperscope_ndb/profile/card#me";
  state.sourcePath = "demo:///capture/gists/";
  loadGists();
}

// ── scanning the source folder ─────────────────────────────────────────
// A .toml is a candidate buffer unless the Rate has stamped it ingested.
// Order follows state.sortMode (see collectPendingFiles): oldest-first by
// default, so triage replays the day chronologically instead of walking
// backwards through decisions already made.
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
  const barEl = el("scan-bar"), fillEl = el("scan-fill");
  barEl.hidden = false;
  fillEl.style.width = "0%";

  const onProgress = (done, total) => {
    if (token !== scanToken) return;
    el("stack-line").textContent = `looking… ${done}/${total}`;
    fillEl.style.width = `${Math.round((done / total) * 100)}%`;
  };

  let files = [], failedCount = 0;
  try {
    ({ files, failedCount } = await collectPendingFiles(folder, onProgress));
  } catch (e) {
    if (token !== scanToken) return;
    state.scan = null;
    barEl.hidden = true;
    el("stack-line").textContent = "couldn't read that folder";
    return;
  }
  if (token !== scanToken) return;
  barEl.hidden = true;

  state.scan = { folder, files, failedCount };
  const total = files.reduce((n, f) => n + f.gists.length, 0);
  const failNote = failedCount ? ` (${failedCount} file${failedCount > 1 ? "s" : ""} unreadable)` : "";
  if (!files.length && failedCount) {
    el("stack-line").textContent = "couldn't read any files here" + failNote;
  } else if (!files.length) {
    el("stack-line").textContent = "no open batches here";
  } else if (!total) {
    el("stack-line").textContent = "nothing pending — all swiped" + failNote;
  } else {
    const shape = files.filter((f) => f.gists.length).map((f) => `${f.date} ${f.gists.length}`).join(" · ");
    el("stack-line").textContent = `${total} pending — ${shape}${failNote}`;
  }
}

// Returns `{ files, failedCount }` — a single unreadable file must never
// silently vanish from the scan; its failure has to be visible even when
// other files in the same folder loaded fine. Reads run in parallel — a
// 20-file backlog used to read one file at a time and looked hung; the pod
// is happy to serve them concurrently. `onProgress(done, total)`, if given,
// fires as each read settles, in no particular order.
async function collectPendingFiles(folder, onProgress) {
  const items = await listContainer(folder);
  // YYYY-MM-DD.toml sorts lexicographically same as chronologically.
  const dir = state.sortMode === "newest" ? -1 : 1;
  const tomls = items
    .filter((it) => !it.isContainer && it.name.endsWith(".toml"))
    .sort((a, b) => dir * a.name.localeCompare(b.name));

  let done = 0;
  const total = tomls.length;
  const results = await Promise.all(tomls.map(async (item) => {
    try {
      const { text } = await readFile(item.url);
      if (onProgress) onProgress(++done, total);
      if (isIngested(text)) return null; // the Rate has taken this batch
      const parsed = parseGistTOML(text);
      const pending = parsed.filter((g) => g.validation === "pending");
      pending.forEach((g) => { g.sourceUrl = item.url; });
      return { url: item.url, date: dateOfFile(item.name, parsed), gists: pending };
    } catch (e) {
      if (onProgress) onProgress(++done, total);
      return "failed";
    }
  }));

  const files = [];
  let failedCount = 0;
  // tomls is already in sort order; Promise.all preserves index-to-result
  // correspondence regardless of settle order, so this stays ordered.
  for (const r of results) {
    if (r === "failed") failedCount++;
    else if (r) files.push(r);
  }
  return { files, failedCount };
}

// ── loading the deck ───────────────────────────────────────────────────
async function loadGists() {
  saveSetupToLocalStorage();
  const folder = state.sourcePath.replace(/\/?$/, "/");

  let files, failedCount;
  const cached = state.scan;
  if (cached && cached.folder === folder) {
    ({ files, failedCount } = cached);
  } else {
    try {
      ({ files, failedCount } = await collectPendingFiles(folder));
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
  // A file that failed to read is not the same as "nothing pending" — it
  // has to read as an error, even when other files in the folder loaded.
  state.loadState = !files.length
    ? (failedCount ? "error" : "no-files")
    : (state.gists.length ? "ok" : (failedCount ? "error" : "none-pending"));
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
  state.closedFiles = new Set();
  state.lastWriteAt = null;
  state.failures = 0;
  state.pulseGroup = null;
  state.comment = "";
  state.flags = {};
  commentLoadedFor = null;
}

// ── swipe mechanics — DOM writes only, no re-render mid-drag ────────────
// Flags are toggled, not committed — they ride along with whichever swipe
// comes next (see commit()), same as the pre-Rate design.
function toggleFlag(key) {
  state.flags = { ...state.flags, [key]: !state.flags[key] };
  renderFlagTray();
}

function renderFlagTray() {
  document.querySelectorAll(".vz-flag-btn").forEach((btn) => {
    btn.classList.toggle("vz-flag-on", !!state.flags[btn.dataset.flag]);
  });
  const activeEl = el("active-flags");
  activeEl.innerHTML = "";
  FLAGS.filter((f) => state.flags[f.key]).forEach((f) => {
    const span = document.createElement("span");
    span.className = "vz-active-flag";
    span.style.setProperty("--flag-color", `var(${f.colorVar})`);
    span.textContent = `${f.emoji} ${f.label}`;
    activeEl.appendChild(span);
  });
}

function toggleRawExpand() {
  const g = state.gists[state.i];
  if (!g) return;
  const raw = el("gist-raw");
  const expanded = raw.classList.toggle("vz-raw-expanded");
  rawExpandedFor = expanded ? g.id : null;
  el("gist-raw-more").hidden = expanded || !raw.classList.contains("vz-raw-scrolls");
}

// ── zone model ──────────────────────────────────────────────────────────
// The card moves 1:1 with the finger in both axes, and the decision is made
// by WHERE it is released, not by which threshold a damped axis happened to
// cross. Two targets — left, right — each owning the half-plane on their
// side. Outside ARM_RADIUS nothing is armed and release always snaps back,
// so a short or ambiguous drag can never commit.
//
// Replaces per-axis thresholds on a vertically-damped transform, which read
// as fluid horizontally and erratic vertically because the two axes did not
// move the same amount per pixel of finger travel.
const ARM_RADIUS = 88;   // px of travel before any target arms

// Which target a displacement points at, or null if too short to mean
// anything.
function zoneFor(x, y) {
  const dist = Math.hypot(x, y);
  if (dist < ARM_RADIUS) return null;
  return x > 0 ? "right" : "left";
}

function paint() {
  if (!drag) return;
  const { x, y } = drag;
  // 1:1 on both axes. The only cosmetic liberty is a slight rotation, which
  // tracks x and so cannot desync from the finger.
  cardEl.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px) rotate(${(x * 0.03).toFixed(2)}deg)`;

  const zone = zoneFor(x, y);
  drag.zone = zone;
  // Targets light up fully once armed and only preview before that, so the
  // release outcome is legible mid-gesture.
  const dist = Math.hypot(x, y);
  const preview = Math.min(0.55, dist / (ARM_RADIUS * 1.6));
  rejectEl.style.opacity = String(zone === "left" ? 1 : (x < 0 ? preview : 0));
  validateEl.style.opacity = String(zone === "right" ? 1 : (x > 0 ? preview : 0));
  cardEl.classList.toggle("vz-armed", !!zone);
}

function resetCard() {
  cardEl.style.transition = "transform .3s cubic-bezier(.2,.8,.3,1)";
  cardEl.style.transform = "none";
  cardEl.style.opacity = "1";
  cardEl.classList.remove("vz-armed");
  rejectEl.style.opacity = "0";
  validateEl.style.opacity = "0";
}

function onDown(e) {
  if (animating || state.i >= state.gists.length) return;
  if (!e.isPrimary) return; // a second finger is not a second decision
  if (e.target && e.target.closest && e.target.closest("[data-nodrag]")) return;
  drag = { x0: e.clientX, y0: e.clientY, x: 0, y: 0, zone: null };
  cardEl.style.transition = "none";
  try { el("card-area").setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
}
function onMove(e) {
  if (!drag) return;
  drag.x = e.clientX - drag.x0;
  drag.y = e.clientY - drag.y0;
  paint();
}
// A cancelled pointer is not a decision. Browser-stolen gestures used to land
// here and commit a vote on whatever x happened to be — abandon instead.
function onCancel() {
  if (!drag) return;
  drag = null;
  resetCard();
}
// Detected here rather than via the browser's own dblclick, because the drag
// handlers already own every pointer event on the card and a second gesture
// system would just race the first. A "tap" is a release that never armed a
// swipe target and barely moved; two of those close together in time and
// position toggle the raw-text expansion instead of doing nothing.
const TAP_MAX_DRIFT = 10;   // px — travel under this still counts as a tap
const DOUBLE_TAP_MS = 320;
function maybeDoubleTap(x0, y0, dist) {
  if (dist > TAP_MAX_DRIFT) { lastTapAt = 0; return; }
  const now = performance.now();
  const closeInTime = now - lastTapAt < DOUBLE_TAP_MS;
  const closeInSpace = Math.hypot(x0 - lastTapX, y0 - lastTapY) < 24;
  if (closeInTime && closeInSpace) { lastTapAt = 0; toggleRawExpand(); }
  else { lastTapAt = now; lastTapX = x0; lastTapY = y0; }
}

function onUp() {
  if (!drag) return;
  const zone = drag.zone;
  const { x0, y0, x, y } = drag;
  drag = null;
  if (zone === "right") return commit("validated");
  if (zone === "left") return commit("rejected");
  maybeDoubleTap(x0, y0, Math.hypot(x, y));
  resetCard();
}

const FLIGHT = { validated: [460, -24, 12], rejected: [-460, -24, -12] };

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

  const prevVote = state.decisions[g.id] || null;
  const prevNote = g.note || "";
  const prevFlags = g.flags || [];
  const note = state.comment.trim();
  const flags = FLAGS.map((f) => f.key).filter((k) => state.flags[k]);
  state.decisions = { ...state.decisions, [g.id]: vote };
  state.history = state.history.concat([{ id: g.id, index: i, prevVote, prevNote, prevFlags, note, flags, gist: g }]);
  g.note = note;
  g.flags = flags;
  state.i = i + 1;
  state.pulseGroup = groupJustCompleted(g.sourceUrl) ? g.sourceUrl : null;
  state.writeError = null;
  state.writing += 1;
  state.comment = "";
  state.flags = {};
  el("comment-input").value = "";
  // The note belongs to the card that just left. Dropping focus closes the
  // virtual keyboard and hands the screen back to the next card, instead of
  // leaving an empty field armed over it.
  el("comment-input").blur();
  commentLoadedFor = null;

  writeValidation(g, vote, note, flags).then(
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
    if (state.i >= state.gists.length) showScreen("done");
    else renderDeck();
  }, 230);
}

// A "group" is a file's own gists. Called right after state.i advances, on
// the source file of the card that just committed — true once every gist
// from that file has a decision (dropped ones from a batch-closed file count
// as decided too, since they can never be swiped).
function groupJustCompleted(sourceUrl) {
  return state.gists.filter((g) => g.sourceUrl === sourceUrl)
    .every((g) => state.decisions[g.id]);
}

// A write either landed or it didn't. If it didn't, the gist goes back into
// the deck as the next card up — the pod still says "pending", so re-swiping
// it is the whole repair. Only the failed commit's own history entry is
// dropped (indices on other entries are independent of state.i and stay
// valid), so the done-screen tally isn't corrupted by an unrelated failure.
function settleWrite(gist, err) {
  state.writing = Math.max(0, state.writing - 1);
  if (!err) {
    state.lastWriteAt = Date.now();
    if (state.screen === "deck") renderDeck();
    if (state.screen === "done") renderDone();
    return;
  }
  state.failures += 1;
  delete state.decisions[gist.id];
  state.history = state.history.filter((h) => h.gist !== gist);

  if (err.code === "batch-closed") {
    state.closedFiles.add(gist.sourceUrl);
    // Nothing else from this file can ever succeed — drop its remaining
    // gists from the deck instead of letting each one fail one at a time.
    const before = state.gists.length;
    state.gists = state.gists.filter((g) => g.sourceUrl !== gist.sourceUrl || state.decisions[g.id]);
    const dropped = before - state.gists.length;
    if (dropped) state.i = Math.max(0, state.i - dropped);
    state.batchClosed = true;
    state.writeError = err.message;
  } else if (err.code === "not-found") {
    // The gist is permanently gone from its file — retrying can never
    // succeed, so drop it from the deck instead of resurfacing it forever.
    const idx = state.gists.indexOf(gist);
    if (idx !== -1) {
      state.gists = state.gists.filter((g) => g !== gist);
      if (idx < state.i) state.i -= 1;
      else if (idx === state.i) { /* pointer already sits on the next card */ }
    }
    state.writeError = "gist no longer in that file — skipped";
  } else {
    state.writeError = String(err.message || err).slice(0, 70);
    // The gist was never removed from state.gists (commit() only advances
    // the pointer) — it's still sitting at its original index, so putting
    // it back up next is a pointer move, not a re-insertion. Re-inserting
    // here would duplicate it and the deck total would grow every retry.
    // A later swipe may already have advanced past this index and
    // succeeded, so walk forward from idx to the first still-undecided
    // gist rather than landing blindly on idx — that avoids resurfacing an
    // already-committed gist for a duplicate swipe.
    const idx = state.gists.indexOf(gist);
    if (idx !== -1) {
      let target = idx;
      while (target < state.gists.length && state.decisions[state.gists[target].id]) target++;
      state.i = target;
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
  const target = last.prevVote || "pending";

  const decisions = { ...state.decisions };
  if (last.prevVote) decisions[last.id] = last.prevVote; else delete decisions[last.id];
  state.decisions = decisions;
  // History keeps the entry until the repair write actually lands — a
  // failed undo has to stay retryable, not vanish along with its record.
  state.i = last.index;
  state.writeError = null;
  state.writing += 1;
  last.gist.note = last.prevNote;
  last.gist.flags = last.prevFlags;
  state.comment = last.note;
  commentLoadedFor = last.gist.id; // keep the just-typed note visible, don't let renderDeck reload it from prevNote
  el("comment-input").value = state.comment;
  const flagsMap = {};
  (last.flags || []).forEach((k) => { flagsMap[k] = true; });
  state.flags = flagsMap; // put the just-picked flags back in the tray for editing
  renderFlagTray();

  writeValidation(last.gist, target, last.prevNote, last.prevFlags).then(
    () => {
      state.writing = Math.max(0, state.writing - 1);
      state.lastWriteAt = Date.now();
      state.history = state.history.filter((h) => h !== last);
      renderDeck();
    },
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
  document.querySelectorAll("#sort-toggle .vz-seg-btn").forEach((btn) => {
    btn.classList.toggle("vz-seg-active", btn.dataset.sort === state.sortMode);
  });
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
  const newest = state.fileDates.reduce((max, d) => (d > max ? d : max), state.fileDates[0] || "");
  const dayOf = (gist) => {
    if (!gist) return newest;
    if (gist.timestamp) return new Date(gist.timestamp * 1000).toLocaleDateString("sv-SE");
    return gist.moment ? gist.moment.slice(0, 10) : newest;
  };
  const backlog = multiDay && g && dayOf(g) !== newest;

  el("counter-text").textContent = `${Math.min(state.i + 1, total)} / ${total}`;

  const marksEl = el("marks");
  marksEl.innerHTML = "";
  let prevSourceUrl = null;
  state.gists.forEach((gi, n) => {
    // A gap between files chunks the bar per day-group — the visual unit a
    // pulse (below) completes.
    if (prevSourceUrl !== null && gi.sourceUrl !== prevSourceUrl) {
      marksEl.appendChild(document.createElement("span")).className = "vz-mark-gap";
    }
    prevSourceUrl = gi.sourceUrl;
    const d = state.decisions[gi.id];
    let colorVar = "--border-subtle";
    if (d) colorVar = VALIDATION_COLOR_VAR[d] || ((gi.flags && gi.flags.length) ? "--temporal" : "--fresh");
    else if (n === state.i) colorVar = "--text-tertiary";
    const mark = document.createElement("span");
    mark.className = "vz-mark";
    if (state.pulseGroup && gi.sourceUrl === state.pulseGroup) mark.classList.add("vz-mark-pulse");
    mark.style.background = `var(${colorVar})`;
    mark.style.color = `var(${colorVar})`; // drives the pulse's currentColor glow
    marksEl.appendChild(mark);
  });
  state.pulseGroup = null; // one-shot — consumed by this paint

  const finished = !g;
  el("gist-card").hidden = finished;
  document.querySelector(".vz-ghost-card").hidden = finished;
  el("empty-stack").hidden = !finished;
  el("undo-btn").disabled = !state.history.length;
  el("comment-input").disabled = finished;

  if (g) {
    el("gist-type").textContent = g.type || "—";
    el("gist-type").style.color = `var(${TYPE_COLOR_VAR[g.type] || "--text-tertiary"})`;
    // Local date+hour, not just the capture-zone moment string — a gist
    // carried over from an earlier day still reads as backlog via color.
    el("gist-moment").textContent = (localDateHour(g.timestamp) || g.moment || "") + (backlog ? " · backlog" : "");
    el("gist-moment").style.color = backlog ? "var(--temporal)" : "var(--text-tertiary)";
    el("gist-title").textContent = g.titre || "";
    el("gist-raw").textContent = g.raw || "";
    if (rawExpandedFor !== g.id) { el("gist-raw").classList.remove("vz-raw-expanded"); rawExpandedFor = null; }
    // Only a raw block that actually overflows gets the "more" hint and the
    // desktop scroll-touch-action — see #gist-raw.vz-raw-scrolls. Measured
    // after the write, and deferred so layout has settled.
    requestAnimationFrame(() => {
      const raw = el("gist-raw");
      const overflowing = raw.scrollHeight > raw.clientHeight + 1;
      raw.classList.toggle("vz-raw-scrolls", overflowing);
      el("gist-raw-more").hidden = !overflowing || raw.classList.contains("vz-raw-expanded");
    });
    if (commentLoadedFor !== g.id) {
      state.comment = g.note || "";
      el("comment-input").value = state.comment;
      commentLoadedFor = g.id;
    }
  } else {
    el("empty-stack").textContent = EMPTY_COPY[state.loadState] || EMPTY_COPY.ok;
    commentLoadedFor = null;
  }

  renderFlagTray();
  renderDeckStatus();
}

function renderDone() {
  const votes = Object.values(state.decisions);
  const nVal = votes.filter((v) => v === "validated").length;
  const nRej = votes.filter((v) => v === "rejected").length;
  const nAna = state.history.filter((h) => h.flags && h.flags.includes("anagnorisis")).length;
  // "flagged" stays revisit/priority only — anagnorisis gets its own tally
  // line above, so it isn't double-counted here.
  const nFlagged = state.history.filter((h) => h.flags && h.flags.some((k) => k !== "anagnorisis")).length;
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
  el("tally-flagged").textContent = `${nFlagged} flagged`;
}

// ── wiring ─────────────────────────────────────────────────────────────
el("provider-input").addEventListener("change", (e) => { state.provider = e.target.value; });
el("login-btn").addEventListener("click", doLogin);
el("demo-btn").addEventListener("click", bootDemo);

el("source-input").addEventListener("change", (e) => { browseTo("source", e.target.value.replace(/\/?$/, "/")); });
document.querySelectorAll("#sort-toggle .vz-seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.sortMode = btn.dataset.sort;
    renderSetup();
    scanSource(); // re-scan under the new order so #stack-line's shape matches
  });
});
// Shared by the setup screen's sign-out button and the deck's top-left
// button (see below) — one real end to a session, landing back on login.
async function signOut() {
  if (session) await session.logout();
  state.webId = null;
  state.demo = false;
  state.gists = [];
  resetDeckState();
  showScreen("login");
}
el("signout-btn").addEventListener("click", signOut);
el("open-stack-btn").addEventListener("click", loadGists);

el("card-area").addEventListener("pointerdown", onDown);
el("card-area").addEventListener("pointermove", onMove);
el("card-area").addEventListener("pointerup", onUp);
el("card-area").addEventListener("pointercancel", onCancel);
el("undo-btn").addEventListener("click", undo);
el("gist-raw-more").addEventListener("click", toggleRawExpand);
el("comment-input").addEventListener("input", (e) => { state.comment = e.target.value; });

document.querySelectorAll(".vz-flag-btn").forEach((btn) => {
  // All three are multi-select toggles that ride along with whichever swipe
  // comes next — nothing in this tray commits on tap.
  btn.addEventListener("click", () => toggleFlag(btn.dataset.flag));
});

// ── viewport height ─────────────────────────────────────────────────────
// Best-effort refinement, not the safety net — that's the min-height +
// overflow-y:auto fallback in valisette.css. Brave on Android doesn't
// reliably shrink dvh/svh/visualViewport for its own bottom bar either, so
// even this measurement can't be trusted as the truth; it only narrows the
// gap on browsers that DO report correctly (most others). CSS still holds if
// visualViewport is absent or wrong.
function syncViewportHeight() {
  const vv = window.visualViewport;
  if (!vv) return;
  document.documentElement.style.setProperty("--vz-vh", `${Math.round(vv.height)}px`);
}
if (window.visualViewport) {
  syncViewportHeight();
  window.visualViewport.addEventListener("resize", syncViewportHeight);
  // Brave shows/hides its bottom bar on scroll, which resizes the visual
  // viewport without firing resize on some builds.
  window.visualViewport.addEventListener("scroll", syncViewportHeight);
  window.addEventListener("orientationchange", () => setTimeout(syncViewportHeight, 200));
}

el("close-btn").addEventListener("click", () => {
  state.gists = [];
  resetDeckState();
  showScreen("login");
});

// The deck's own exit — there was no clean way to pause a session mid-stack
// before this; signing out is that clean end, and setup is reached again
// right after the next login.
el("deck-back-btn").addEventListener("click", signOut);

document.addEventListener("keydown", (e) => {
  if (state.screen !== "deck") return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  if (e.key === "ArrowLeft") commit("rejected");
  else if (e.key === "ArrowRight") commit("validated");
  else if (e.key === "ArrowDown" || e.key === "Backspace") { e.preventDefault(); undo(); }
});

// Keeps the "saved Ns ago" line honest without a re-render of the deck.
setInterval(() => {
  if (state.screen === "deck") renderDeckStatus();
}, 1000);

showScreen("login");
initSolid();
