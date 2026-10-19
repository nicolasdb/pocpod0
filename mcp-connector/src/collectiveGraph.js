/**
 * collectiveGraph.js
 *
 * A collective's knowledge graph: what its agent has pulled and confronted,
 * loaded into Oxigraph so the members' agents can query it. Pods stay the
 * truth and the graph is a derived index (solid-kit ADR 001); what goes in is
 * what ADR 006's pull and confrontation wrote on the collective's pod.
 *
 * Oxigraph has no access control of its own, so this module is the boundary:
 *
 * - Ingest: only the collective's agent (`hs:agent` in config.ttl), only
 *   Turtle it can read itself under the collective's `depots/` or
 *   `confrontations/`. One named graph per resource, named by its URL, and
 *   replaced (PUT) on every ingest, so ingesting twice never duplicates.
 *
 * - Query: the collective's own agent (it wrote what is there), a WebID the
 *   roster lists, or an agent a listed member declares with `acl:delegates`. The roster is read with the caller's own session, so
 *   someone who cannot read it is not a member. Read-only, and only over the
 *   collective's graphs under a folder the caller can read on the pod right
 *   now: the index never shows more than the pod does.
 *
 * The caller's query text never reaches Oxigraph. It is parsed, refused when
 * it is an update or holds a SERVICE, and the regenerated text is sent, with
 * the allowed graphs as the SPARQL protocol's dataset. Both checked live on
 * Oxigraph 0.5.6 (2026-09-29): the protocol dataset overrides FROM, FROM
 * NAMED and GRAPH <iri>, but SERVICE escapes it (Oxigraph federates, and can
 * query itself), and `SERVICE` gets past any keyword filter because
 * SPARQL processes \u escapes before parsing. sparqljs refuses the escape.
 */

const N3 = require("n3");
const { Parser: SparqlParser, Generator: SparqlGenerator } = require("sparqljs");

const OXIGRAPH_URL = (process.env.OXIGRAPH_URL || "http://oxigraph:7878").replace(/\/$/, "");

/** The folders of the collective's pod that are indexed. Members hold Read on both (ADR 006 §5). */
const INGESTABLE = ["depots/", "confrontations/"];

/** One ingest call never walks more than this; a larger folder is ingested in parts. */
const MAX_INGEST = 500;
/** A SELECT without a smaller LIMIT gets this one. */
const MAX_ROWS = 200;
/** What a query hands back to the model, at most. */
const MAX_RESULT_CHARS = 60000;
const QUERY_TIMEOUT_MS = 15000;
/** How long a reader's membership and readable folders are trusted before being read again. */
const READER_TTL_MS = 60 * 1000;

const NS = {
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  foaf: "http://xmlns.com/foaf/0.1/",
  acl: "http://www.w3.org/ns/auth/acl#",
  ldp: "http://www.w3.org/ns/ldp#",
  // Provisional, like the backoffice's (src/lib/vocab.ts there): one line to move.
  hs: "https://pod.nicolasdb.eu/hyperscope/vocab#",
};

/** A refusal the model should read as written; no status, so toToolErrorResult keeps the message. */
function refusal(message) {
  return new Error(message);
}

/** A pod read that failed. 401 keeps its status, so safeHandler re-authenticates once. */
function podError(url, res) {
  const err = new Error(`GET ${url} failed: [${res.status}] ${res.statusText || ""}`.trim());
  if (res.status === 401) err.statusCode = 401;
  err.podStatus = res.status;
  return err;
}

function parseTurtle(text, baseIRI) {
  return new N3.Parser({ baseIRI }).parse(text);
}

function objectsOf(quads, subject, predicate) {
  return quads.filter((q) => q.subject.value === subject && q.predicate.value === predicate).map((q) => q.object.value);
}

async function getTurtle(url, fetchFn) {
  const res = await fetchFn(url, { headers: { Accept: "text/turtle" } });
  if (!res.ok) throw podError(url, res);
  return { text: await res.text(), contentType: res.headers.get("content-type") || "" };
}

/* ── The collective ──────────────────────────────────────────────────── */

/**
 * The collective from its address: its IRI (`…/config.ttl#hyperscope`, what a
 * member's `org:memberOf` holds) or the config document's URL.
 */
async function loadCollective(address, fetchFn) {
  let url;
  try {
    url = new URL(address);
  } catch {
    throw refusal(`"${address}" is not an address. Give the collective's config.ttl address.`);
  }
  const expected = url.hash ? url.href : null;
  url.hash = "";
  const configUrl = url.href;

  let quads;
  try {
    quads = parseTurtle((await getTurtle(configUrl, fetchFn)).text, configUrl);
  } catch (err) {
    if (err.statusCode === 401) throw err;
    throw refusal(`Could not read the collective's config at ${configUrl}: ${err.message}`);
  }
  const declared = quads
    .filter((q) => q.predicate.value === NS.rdf + "type" && q.object.value === NS.hs + "Collective")
    .map((q) => q.subject.value);
  const group = expected ? declared.find((d) => d === expected) : declared.length === 1 ? declared[0] : null;
  if (!group) throw refusal(`${configUrl} does not declare ${expected ? expected : "exactly one"} hs:Collective.`);

  const one = (predicate, label) => {
    const values = objectsOf(quads, group, predicate);
    if (values.length !== 1) throw refusal(`${configUrl}: expected exactly one ${label}, found ${values.length}.`);
    return values[0];
  };
  return {
    configUrl,
    group,
    root: new URL("./", configUrl).href,
    roster: one(NS.hs + "roster", "hs:roster"),
    agent: one(NS.hs + "agent", "hs:agent"),
  };
}

/** The folders of this collective that are indexed, as full URLs. */
function ingestableFolders(collective) {
  return INGESTABLE.map((f) => collective.root + f);
}

/* ── Who may read the graph ──────────────────────────────────────────── */

const readers = new Map();

/**
 * Whether `webId` may query the collective's graph, and over which folders.
 * Throws a refusal when it may not. `fetchFn` is the caller's own session:
 * the pod decides what it can read, not this module.
 */
async function authorizeReader(collective, webId, fetchFn, now = Date.now()) {
  const key = `${collective.configUrl}\n${webId}`;
  const kept = readers.get(key);
  if (kept && now - kept.at < READER_TTL_MS) return kept.value;

  // The collective's own agent: it pulled, confronted and loaded all of it, so
  // reading it back shows it nothing new. The folder check below still applies.
  if (webId === collective.agent) return readableFolders(collective, webId, fetchFn, key, now, collective.group);

  let members;
  try {
    const roster = await getTurtle(collective.roster, fetchFn);
    members = objectsOf(parseTurtle(roster.text, collective.roster), collective.group, NS.foaf + "member");
  } catch (err) {
    if (err.statusCode === 401) throw err;
    throw refusal(
      `${webId} cannot read the roster of ${collective.group}` +
        (err.podStatus ? ` (${err.podStatus})` : "") +
        ", so it is not treated as a member. A member's agent needs Read on the roster, given when its human is accepted."
    );
  }

  let actingFor = null;
  if (members.includes(webId)) {
    actingFor = webId;
  } else {
    // A member's agent: declared by the member, in the member's own profile.
    const declared = await Promise.all(
      members.map(async (member) => {
        try {
          const doc = new URL(member);
          doc.hash = "";
          const profile = await getTurtle(doc.href, fetchFn);
          return objectsOf(parseTurtle(profile.text, doc.href), member, NS.acl + "delegates").includes(webId) ? member : null;
        } catch {
          return null;
        }
      })
    );
    actingFor = declared.find(Boolean) || null;
  }
  if (!actingFor) {
    throw refusal(`${webId} is not on the roster of ${collective.group}, and no member there declares it as their agent (acl:delegates).`);
  }
  return readableFolders(collective, webId, fetchFn, key, now, actingFor);
}

/** The indexed folders `webId` can read on the pod right now; a refusal when none. */
async function readableFolders(collective, webId, fetchFn, key, now, actingFor) {
  const folders = [];
  await Promise.all(
    ingestableFolders(collective).map(async (folder) => {
      const res = await fetchFn(folder, { method: "HEAD" });
      if (res.status === 401) throw podError(folder, res);
      if (res.ok) folders.push(folder);
    })
  );
  if (!folders.length) {
    throw refusal(`${webId} is a member's identity but can read none of ${ingestableFolders(collective).join(", ")} on the pod, so the graph shows it nothing.`);
  }

  const value = { actingFor, folders: folders.sort() };
  readers.set(key, { at: now, value });
  return value;
}

function forgetReaders() {
  readers.clear();
}

/* ── The query ───────────────────────────────────────────────────────── */

function findNode(node, type) {
  if (!node || typeof node !== "object") return false;
  if (Array.isArray(node)) return node.some((n) => findNode(n, type));
  if (node.type === type) return true;
  return Object.values(node).some((v) => findNode(v, type));
}

/**
 * The query as it will be sent: parsed, checked, regenerated. Throws a
 * refusal for anything that is not a read, or that could leave the dataset.
 */
function checkQuery(text) {
  let ast;
  try {
    ast = new SparqlParser({ skipValidation: false }).parse(text);
  } catch (err) {
    throw refusal(`The query does not parse: ${String(err.message).split("\n")[0]}. Write plain SPARQL 1.1, without \\u escapes.`);
  }
  if (ast.type !== "query") throw refusal("Only queries are allowed here (SELECT, ASK, CONSTRUCT, DESCRIBE); the graph is read-only.");
  if (findNode(ast.where, "service") || findNode(ast, "service")) {
    throw refusal("SERVICE is not allowed: the graph answers only from the collective's own data.");
  }
  // The protocol's dataset is what applies; the query's own is dropped so the text says what runs.
  delete ast.from;
  if (ast.queryType === "SELECT" && !(ast.limit > 0 && ast.limit <= MAX_ROWS)) ast.limit = MAX_ROWS;
  return { queryType: ast.queryType, text: new SparqlGenerator().stringify(ast) };
}

async function oxigraph(path, init) {
  let res;
  try {
    res = await fetch(OXIGRAPH_URL + path, { ...init, signal: AbortSignal.timeout(QUERY_TIMEOUT_MS) });
  } catch (err) {
    throw refusal(`The collective's graph (Oxigraph) cannot be reached: ${err.message}`);
  }
  if (!res.ok) throw refusal(`The graph refused the request: [${res.status}] ${(await res.text()).slice(0, 300)}`);
  return res;
}

/** Every named graph under one of `folders`. Our own query, not the caller's. */
async function graphsUnder(folders) {
  const res = await oxigraph("/query", {
    method: "POST",
    headers: { "Content-Type": "application/sparql-query", Accept: "application/sparql-results+json" },
    body: "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }",
  });
  const json = await res.json();
  return json.results.bindings.map((b) => b.g.value).filter((g) => folders.some((f) => g.startsWith(f)));
}

/** Runs a checked query over exactly `graphs`, as the default graph and as the named graphs. */
async function runQuery(checked, graphs) {
  const construct = checked.queryType === "CONSTRUCT" || checked.queryType === "DESCRIBE";
  if (!graphs.length) {
    // An empty dataset in the protocol means "the whole store". Never send one.
    return construct ? "" : checked.queryType === "ASK" ? '{"head":{},"boolean":false}' : '{"head":{"vars":[]},"results":{"bindings":[]}}';
  }
  const body = new URLSearchParams({ query: checked.text });
  for (const g of graphs) {
    body.append("default-graph-uri", g);
    body.append("named-graph-uri", g);
  }
  const res = await oxigraph("/query", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: construct ? "text/turtle" : "application/sparql-results+json" },
    body,
  });
  return res.text();
}

/** A SELECT's JSON as a small table the model reads easily; anything else as it came. */
function formatResult(queryType, raw) {
  let out = raw;
  if (queryType === "SELECT") {
    const json = JSON.parse(raw);
    const vars = json.head.vars;
    const rows = json.results.bindings.map((b) => vars.map((v) => (b[v] ? b[v].value : "")).join("\t"));
    out = `${rows.length} row${rows.length === 1 ? "" : "s"}\n${vars.join("\t")}\n${rows.join("\n")}`;
  } else if (queryType === "ASK") {
    out = String(JSON.parse(raw).boolean);
  }
  return out.length > MAX_RESULT_CHARS ? out.slice(0, MAX_RESULT_CHARS) + "\n… (cut: ask for fewer rows)" : out;
}

async function queryGraph({ collective: address, query }, identity) {
  const fetchFn = identity.session.fetch;
  const collective = await loadCollective(address, fetchFn);
  const checked = checkQuery(query);
  const reader = await authorizeReader(collective, identity.webId, fetchFn);
  const graphs = await graphsUnder(reader.folders);
  const raw = await runQuery(checked, graphs);
  const header =
    `Graph of ${collective.group}, read as ${identity.webId}` +
    (reader.actingFor !== identity.webId ? ` for ${reader.actingFor}` : "") +
    `: ${graphs.length} document${graphs.length === 1 ? "" : "s"} under ${reader.folders.map((f) => f.slice(collective.root.length)).join(", ")}.` +
    " Each graph is named by the pod address of the document it came from: read that document for the full text.";
  return `${header}\n\n${formatResult(checked.queryType, raw)}`;
}

/* ── Ingest ──────────────────────────────────────────────────────────── */

async function listTurtleUnder(folder, fetchFn) {
  const found = [];
  const queue = [folder];
  const seen = new Set();
  while (queue.length && found.length < MAX_INGEST) {
    const container = queue.shift();
    if (seen.has(container)) continue;
    seen.add(container);
    const { text } = await getTurtle(container, fetchFn);
    for (const child of objectsOf(parseTurtle(text, container), container, NS.ldp + "contains")) {
      if (!child.startsWith(folder)) continue; // never leave the folder asked for
      if (child.endsWith("/")) queue.push(child);
      else if (child.endsWith(".ttl")) found.push(child);
    }
  }
  return found.slice(0, MAX_INGEST);
}

/** Loads one Turtle document into its own named graph, replacing what was there. */
async function ingestOne(url, fetchFn) {
  const { text, contentType } = await getTurtle(url, fetchFn);
  if (!/turtle/i.test(contentType)) throw refusal(`${url} is ${contentType || "of no type"}, not Turtle.`);
  const quads = parseTurtle(text, url); // relative IRIs resolve against the document, not Oxigraph's base
  const ntriples = new N3.Writer({ format: "N-Triples" }).quadsToString(quads.map((q) => N3.DataFactory.triple(q.subject, q.predicate, q.object)));
  await oxigraph(`/store?graph=${encodeURIComponent(url)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/n-triples" },
    body: ntriples,
  });
  return quads.length;
}

async function ingest({ collective: address, url }, identity) {
  const fetchFn = identity.session.fetch;
  const collective = await loadCollective(address, fetchFn);
  if (identity.webId !== collective.agent) {
    throw refusal(`Only the collective's agent (${collective.agent}) ingests into its graph; this identity is ${identity.webId}.`);
  }
  const folders = ingestableFolders(collective);
  if (!folders.some((f) => url.startsWith(f))) {
    throw refusal(`Only documents under ${folders.join(" or ")} are ingested.`);
  }
  const targets = url.endsWith("/") ? await listTurtleUnder(url, fetchFn) : [url];
  const loaded = [];
  const failed = [];
  for (const target of targets) {
    try {
      loaded.push({ url: target, triples: await ingestOne(target, fetchFn) });
    } catch (err) {
      if (err.statusCode === 401) throw err;
      failed.push({ url: target, reason: err.message });
    }
  }
  const lines = [
    `Ingested ${loaded.length} of ${targets.length} Turtle document${targets.length === 1 ? "" : "s"} into the graph of ${collective.group}` +
      (targets.length >= MAX_INGEST ? ` (stopped at ${MAX_INGEST}: ingest the rest folder by folder)` : "") +
      ".",
    ...loaded.map((l) => `  ${l.url}  ${l.triples} triples`),
    ...(failed.length ? ["Not ingested:", ...failed.map((f) => `  ${f.url}  ${f.reason}`)] : []),
  ];
  return lines.join("\n");
}

module.exports = {
  INGESTABLE,
  MAX_ROWS,
  loadCollective,
  authorizeReader,
  forgetReaders,
  checkQuery,
  graphsUnder,
  runQuery,
  queryGraph,
  ingest,
};
