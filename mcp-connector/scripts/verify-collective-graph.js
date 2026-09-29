#!/usr/bin/env node
/**
 * verify-collective-graph.js
 *
 * The collective's graph (src/collectiveGraph.js): who may ingest, who may
 * query, and that a query never sees another collective's graphs. The pods
 * are faked, one fetch per identity with its own rights; Oxigraph is real,
 * because the isolation depends on how Oxigraph treats the protocol dataset.
 *
 * Usage (a throwaway Oxigraph, never the VPS one: this writes to it):
 *   podman run -d --rm --name oxi-test -p 127.0.0.1:17878:7878 \
 *     ghcr.io/oxigraph/oxigraph:0.5.6 serve --location /data --bind 0.0.0.0:7878
 *   OXIGRAPH_URL=http://127.0.0.1:17878 node scripts/verify-collective-graph.js
 *
 * Without OXIGRAPH_URL only the query checks run (offline).
 */

const assert = require("node:assert/strict");

const LIVE = Boolean(process.env.OXIGRAPH_URL);
if (LIVE && !/^http:\/\/(127\.0\.0\.1|localhost)[:/]/.test(process.env.OXIGRAPH_URL)) {
  console.error("OXIGRAPH_URL must be a local throwaway Oxigraph: this script writes to it.");
  process.exit(1);
}
const graph = require("../src/collectiveGraph");

const HS = "https://pod.example/hs/";
const OTHER = "https://pod.example/other/";
const HS_AGENT = HS + "agents/agent#me";
const OTHER_AGENT = OTHER + "agents/agent#me";
const XAVIER = "https://pod.example/xavier/profile/card#me";
const NICOLAS = "https://pod.example/nicolas/profile/card#me";
const NICOLAS_CLAUDE = "https://pod.example/nicolas/profile/claude#me";
const STRANGER_BOT = "https://pod.example/eve/profile/bot#me";
const OUTSIDER = "https://pod.example/eve/profile/card#me";

const config = (root, name, agent) => `
@prefix hs: <https://pod.nicolasdb.eu/hyperscope/vocab#> . @prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix ldp: <http://www.w3.org/ns/ldp#> .
<#${name}> a hs:Collective, foaf:Group ; foaf:name "${name}" ; hs:roster <membres.ttl> ;
  ldp:inbox <inbox/> ; hs:agent <${agent}> ; hs:bundleFolder "output2/${name}/" .`;
const listing = (children) =>
  `@prefix ldp: <http://www.w3.org/ns/ldp#>. <> a ldp:Container${children.length ? `; ldp:contains ${children.map((c) => `<${c}>`).join(", ")}` : ""}.`;
const sidecar = (title, author) => `
@prefix dct: <http://purl.org/dc/terms/> . @prefix prov: <http://www.w3.org/ns/prov#> .
<resume.md> dct:title "${title}" ; dct:creator <${author}> ; prov:wasDerivedFrom <../source.md> .`;

// Who can read what on the pods. `*` = anyone; otherwise a list of WebIDs.
const docs = {
  [HS + "config.ttl"]: { read: "*", body: config(HS, "hs", HS_AGENT) },
  [HS + "membres.ttl"]: {
    read: [HS_AGENT, XAVIER, NICOLAS, NICOLAS_CLAUDE],
    body: `<config.ttl#hs> <http://xmlns.com/foaf/0.1/member> <${XAVIER}>, <${NICOLAS}> .`,
  },
  [HS + "depots/"]: { read: [HS_AGENT, XAVIER, NICOLAS, NICOLAS_CLAUDE], body: listing(["xavier/"]) },
  [HS + "depots/xavier/"]: { read: [HS_AGENT], body: listing(["2026-09-29T1000/"]) },
  [HS + "depots/xavier/2026-09-29T1000/"]: { read: [HS_AGENT], body: listing(["resume.md", "provenance.ttl"]) },
  [HS + "depots/xavier/2026-09-29T1000/provenance.ttl"]: { read: [HS_AGENT], body: sidecar("Xavier's summary", XAVIER) },
  [HS + "depots/xavier/2026-09-29T1000/resume.md"]: { read: [HS_AGENT], type: "text/markdown", body: "# Summary" },
  // Xavier cannot read confrontations/ (yet): his graph view is depots/ only.
  [HS + "confrontations/"]: { read: [HS_AGENT, NICOLAS, NICOLAS_CLAUDE], body: listing(["c1.ttl"]) },
  [HS + "confrontations/c1.ttl"]: { read: [HS_AGENT], body: `<#c1> <http://purl.org/dc/terms/title> "Confrontation 1" .` },
  [HS + "principles/p.ttl"]: { read: [HS_AGENT], body: `<#p> <http://purl.org/dc/terms/title> "not ingestable" .` },
  "https://pod.example/nicolas/profile/card": {
    read: "*",
    body: `<#me> <http://www.w3.org/ns/auth/acl#delegates> <claude#me> .`,
  },
  "https://pod.example/xavier/profile/card": { read: "*", body: `<#me> a <http://xmlns.com/foaf/0.1/Person> .` },
  [OTHER + "config.ttl"]: { read: "*", body: config(OTHER, "other", OTHER_AGENT) },
  [OTHER + "membres.ttl"]: { read: [OTHER_AGENT], body: `<config.ttl#other> <http://xmlns.com/foaf/0.1/member> <${OUTSIDER}> .` },
  [OTHER + "depots/"]: { read: [OTHER_AGENT], body: listing(["secret.ttl"]) },
  [OTHER + "depots/secret.ttl"]: { read: [OTHER_AGENT], body: `<#s> <http://purl.org/dc/terms/title> "OTHER-SECRET" .` },
};

function identity(webId) {
  return {
    webId,
    session: {
      fetch: async (url, init = {}) => {
        const doc = docs[url];
        if (!doc) return new Response("", { status: 404 });
        if (doc.read !== "*" && !doc.read.includes(webId)) return new Response("", { status: 403 });
        const body = init.method === "HEAD" ? null : doc.body;
        return new Response(body, { status: 200, headers: { "content-type": doc.type || "text/turtle" } });
      },
    },
  };
}

async function refuses(promise, pattern) {
  await assert.rejects(promise, (err) => {
    assert.match(err.message, pattern);
    assert.equal(err.statusCode, undefined, "a refusal carries no status, so the tool shows its words");
    return true;
  });
}

(async () => {
  // ── The query is parsed, checked and regenerated (offline) ──
  assert.throws(() => graph.checkQuery("SELECT * WHERE { SERVICE <http://oxigraph:7878/query> { ?s ?p ?o } }"), /SERVICE is not allowed/);
  assert.throws(() => graph.checkQuery("select * where { { ?a ?b ?c } UNION { service <http://x/> { ?s ?p ?o } } }"), /SERVICE is not allowed/);
  assert.throws(() => graph.checkQuery("ASK { FILTER EXISTS { SERVICE <http://x/> { ?s ?p ?o } } }"), /SERVICE is not allowed/);
  assert.throws(() => graph.checkQuery("SELECT ?o WHERE { \\u0053ERVICE <http://x/> { ?s ?p ?o } }"), /does not parse/);
  assert.throws(() => graph.checkQuery("INSERT DATA { <http://a/> <http://b/> <http://c/> }"), /read-only/);
  assert.throws(() => graph.checkQuery("DROP ALL"), /read-only/);
  const capped = graph.checkQuery("SELECT * FROM <http://elsewhere/> WHERE { ?s ?p ?o }");
  assert.match(capped.text, new RegExp(`LIMIT ${graph.MAX_ROWS}`));
  assert.doesNotMatch(capped.text, /FROM/, "the query's own dataset is dropped; the protocol's applies");
  assert.match(graph.checkQuery("SELECT * WHERE { ?s ?p ?o } LIMIT 5").text, /LIMIT 5/);
  console.log("ok  queries: SERVICE, \\u escapes and updates refused; FROM dropped; LIMIT capped");

  if (!LIVE) {
    console.log("(OXIGRAPH_URL not set: ingest and isolation checks skipped)");
    return;
  }

  // ── Ingest: the collective's agent only, its ingestable folders only ──
  await refuses(graph.ingest({ collective: HS + "config.ttl#hs", url: HS + "depots/" }, identity(NICOLAS)), /Only the collective's agent/);
  await refuses(graph.ingest({ collective: HS + "config.ttl", url: HS + "principles/p.ttl" }, identity(HS_AGENT)), /Only documents under/);
  await refuses(graph.ingest({ collective: HS + "config.ttl", url: OTHER + "depots/secret.ttl" }, identity(HS_AGENT)), /Only documents under/);

  const out = await graph.ingest({ collective: HS + "config.ttl#hs", url: HS + "depots/" }, identity(HS_AGENT));
  assert.match(out, /Ingested 1 of 1/);
  assert.match(out, /provenance\.ttl {2}3 triples/);
  assert.doesNotMatch(out, /resume\.md/, "markdown is not loaded; its sidecar is");
  // Ingesting again replaces the graph: still 3 triples, never 6.
  await graph.ingest({ collective: HS + "config.ttl", url: HS + "depots/xavier/2026-09-29T1000/provenance.ttl" }, identity(HS_AGENT));
  await graph.ingest({ collective: HS + "config.ttl", url: HS + "confrontations/" }, identity(HS_AGENT));
  await graph.ingest({ collective: OTHER + "config.ttl", url: OTHER + "depots/" }, identity(OTHER_AGENT));
  console.log("ok  ingest: agent only, depots/ and confrontations/ only, markdown skipped, idempotent");

  // ── Query: members and their declared agents, over what they can read ──
  const ask = (who, query) => graph.queryGraph({ collective: HS + "config.ttl#hs", query }, identity(who));
  const all = "SELECT ?g ?o WHERE { GRAPH ?g { ?s ?p ?o } }";

  const asNicolas = await ask(NICOLAS, all);
  assert.match(asNicolas, /Xavier's summary/);
  assert.match(asNicolas, /Confrontation 1/);
  assert.match(asNicolas, /\b4 rows\b/, "3 sidecar triples + 1 confrontation triple: re-ingest did not duplicate");
  assert.match(asNicolas, /provenance\.ttl/, "the graph name is the document's pod address");
  assert.doesNotMatch(asNicolas, /OTHER-SECRET/);

  const asClaude = await ask(NICOLAS_CLAUDE, all);
  assert.match(asClaude, new RegExp(`for ${NICOLAS.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`), "an agent reads for its member");
  assert.match(asClaude, /Xavier's summary/);

  // Xavier cannot read confrontations/ on the pod, so the graph does not show it to him.
  const asXavier = await ask(XAVIER, all);
  assert.match(asXavier, /Xavier's summary/);
  assert.doesNotMatch(asXavier, /Confrontation 1/);

  // Escapes that the protocol dataset stops (checked live on 0.5.6).
  for (const q of [
    `SELECT ?o WHERE { GRAPH <${OTHER}depots/secret.ttl> { ?s ?p ?o } }`,
    `SELECT ?o FROM <${OTHER}depots/secret.ttl> WHERE { ?s ?p ?o }`,
    `SELECT ?o FROM NAMED <${OTHER}depots/secret.ttl> WHERE { GRAPH ?g { ?s ?p ?o } }`,
  ]) {
    assert.doesNotMatch(await ask(NICOLAS, q), /OTHER-SECRET/, q);
  }
  await refuses(ask(NICOLAS, "SELECT ?o WHERE { SERVICE <http://127.0.0.1:7878/query> { GRAPH ?g { ?s ?p ?o } } }"), /SERVICE/);

  // The collective's own agent reads back what it loaded, to check it.
  const asAgent = await ask(HS_AGENT, all);
  assert.match(asAgent, /Xavier's summary/);
  assert.match(asAgent, /Confrontation 1/);
  assert.doesNotMatch(asAgent, /OTHER-SECRET/);
  // Another collective's agent is not this one's.
  await refuses(ask(OTHER_AGENT, all), /cannot read the roster/);

  await refuses(ask(OUTSIDER, all), /cannot read the roster/);
  await refuses(ask(STRANGER_BOT, all), /cannot read the roster/);
  // On the roster's ACL but not listed, and nobody declares it.
  docs[HS + "membres.ttl"].read.push(STRANGER_BOT);
  graph.forgetReaders();
  await refuses(ask(STRANGER_BOT, all), /not on the roster/);
  console.log("ok  query: the collective's agent, members and declared agents only, per-folder view, other collective never visible");

  // A reader who can read none of the folders gets a refusal, never an empty dataset (= the whole store).
  docs[HS + "membres.ttl"].body += `\n<config.ttl#hs> <http://xmlns.com/foaf/0.1/member> <${STRANGER_BOT}> .`;
  graph.forgetReaders();
  await refuses(ask(STRANGER_BOT, all), /can read none of/);
  console.log("ok  query: no readable folder, no query");

  console.log("\nverify-collective-graph: all checks passed");
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
