"""OSLO vocabulary mapping logic.

Converts xAPI statements to OSLO-mapped RDF triples using rdflib.
Lossless: original xAPI JSON is preserved as pocpod0:originalXapiJson literal.
"""

import json
from typing import Dict, Optional
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, PROV, RDF, RDFS, XSD

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

POCPOD0 = Namespace("https://poc-pod0.edu/vocab/")
OSLO    = Namespace("http://data.europa.eu/m8g/")
FOAF    = Namespace("http://xmlns.com/foaf/0.1/")
SCHEMA  = Namespace("http://schema.org/")
XAPI_NS = Namespace("https://w3id.org/xapi/ontology#")
ADL     = Namespace("http://adlnet.gov/expapi/")


def _safe_uri(base: str, local: str) -> URIRef:
    """Build a URI, percent-encoding the local part."""
    return URIRef(f"{base}{quote(local, safe='/-_.')}")


def xapi_to_rdf(stmt: Dict, pod_resource_uri: Optional[str] = None) -> Graph:
    """Convert a single xAPI statement dict to an RDF graph.

    Args:
        stmt: xAPI statement as a Python dict.
        pod_resource_uri: The CSS Pod URL where this Turtle will be stored.
                          Used for the prov:wasDerivedFrom triple.

    Returns:
        rdflib.Graph with all triples for this statement.
    """
    g = Graph()
    g.bind("pocpod0", POCPOD0)
    g.bind("oslo",    OSLO)
    g.bind("foaf",    FOAF)
    g.bind("prov",    PROV)
    g.bind("rdf",     RDF)
    g.bind("rdfs",    RDFS)
    g.bind("xsd",     XSD)
    g.bind("xapi",    XAPI_NS)
    g.bind("schema",  SCHEMA)

    stmt_id = stmt.get("id", "")
    stmt_uri = _safe_uri("https://poc-pod0.edu/statements/", stmt_id)

    # Statement type
    g.add((stmt_uri, RDF.type, POCPOD0.LearningStatement))
    g.add((stmt_uri, RDF.type, XAPI_NS.Statement))

    # --- Actor ---
    actor = stmt.get("actor", {})
    actor_uri = _actor_uri(actor)
    g.add((stmt_uri, POCPOD0.actor, actor_uri))
    g.add((actor_uri, RDF.type, OSLO.Person))
    actor_name = actor.get("name") or actor.get("account", {}).get("name", "")
    if actor_name:
        g.add((actor_uri, FOAF.name, Literal(actor_name)))
    # Role from pod name (inferred)
    account = actor.get("account", {})
    webid_str = account.get("name", "")
    if webid_str:
        g.add((actor_uri, FOAF.account, URIRef(webid_str)))
        role = _infer_role(webid_str)
        if role:
            g.add((actor_uri, POCPOD0.role, Literal(role)))

    # --- Verb ---
    verb = stmt.get("verb", {})
    verb_uri = URIRef(verb.get("id", ""))
    g.add((stmt_uri, POCPOD0.verb, verb_uri))
    g.add((verb_uri, RDF.type, POCPOD0.LearningVerb))
    for lang, label in (verb.get("display") or {}).items():
        g.add((verb_uri, RDFS.label, Literal(label, lang=lang)))

    # --- Object (Activity) ---
    obj = stmt.get("object", {})
    obj_uri = URIRef(obj.get("id", ""))
    g.add((stmt_uri, POCPOD0.object, obj_uri))
    g.add((obj_uri, RDF.type, OSLO.PublicService))  # generic OSLO education resource

    defn = obj.get("definition", {})
    for lang, label in (defn.get("name") or {}).items():
        g.add((obj_uri, RDFS.label, Literal(label, lang=lang)))
    obj_type = defn.get("type", "")
    if obj_type:
        g.add((obj_uri, RDF.type, URIRef(obj_type)))

    # --- Result ---
    result = stmt.get("result")
    if result:
        result_uri = _safe_uri("https://poc-pod0.edu/results/", stmt_id)
        g.add((stmt_uri, POCPOD0.result, result_uri))
        g.add((result_uri, RDF.type, OSLO.Participation))  # OSLO evaluation result
        score = (result.get("score") or {}).get("scaled")
        if score is not None:
            g.add((result_uri, POCPOD0.scaledScore, Literal(score, datatype=XSD.decimal)))
        success = result.get("success")
        if success is not None:
            g.add((result_uri, POCPOD0.success, Literal(success, datatype=XSD.boolean)))
        completion = result.get("completion")
        if completion is not None:
            g.add((result_uri, POCPOD0.completion, Literal(completion, datatype=XSD.boolean)))

    # --- Context ---
    ctx = stmt.get("context", {})
    if ctx:
        ctx_uri = _safe_uri("https://poc-pod0.edu/contexts/", stmt_id)
        g.add((stmt_uri, POCPOD0.context, ctx_uri))
        g.add((ctx_uri, RDF.type, POCPOD0.LearningContext))
        for ext_key, ext_val in (ctx.get("extensions") or {}).items():
            g.add((ctx_uri, URIRef(ext_key), Literal(str(ext_val))))
        platform = ctx.get("platform", "")
        if platform:
            g.add((ctx_uri, SCHEMA.provider, Literal(platform)))

    # --- Timestamp ---
    ts = stmt.get("timestamp", "")
    if ts:
        g.add((stmt_uri, POCPOD0.timestamp, Literal(ts, datatype=XSD.dateTime)))

    # --- Lossless preservation (FR10) ---
    # Remove internal routing hint before serializing
    clean_stmt = {k: v for k, v in stmt.items() if k != "_pocpod0_pod"}
    original_json = json.dumps(clean_stmt, ensure_ascii=False)
    g.add((stmt_uri, POCPOD0.originalXapiJson, Literal(original_json, datatype=XSD.string)))
    g.add((stmt_uri, POCPOD0.originalXapiStatementId, Literal(stmt_id, datatype=XSD.string)))

    # --- Provenance ---
    if pod_resource_uri:
        g.add((stmt_uri, PROV.wasDerivedFrom, URIRef(pod_resource_uri)))

    return g


def _actor_uri(actor: Dict) -> URIRef:
    """Derive a stable URI for the actor."""
    account = actor.get("account", {})
    name = account.get("name", "")
    if name and name.startswith("http"):
        return URIRef(name)
    if name:
        return _safe_uri("https://poc-pod0.edu/actors/", name)
    mbox = actor.get("mbox", "")
    if mbox:
        return URIRef(mbox)
    openid = actor.get("openid", "")
    if openid:
        return URIRef(openid)
    return _safe_uri("https://poc-pod0.edu/actors/", actor.get("name", "unknown"))


def _infer_role(webid: str) -> Optional[str]:
    """Infer a role label from a WebID URL path segment."""
    parts = webid.rstrip("/").split("/")
    # URL like http://localhost:3000/claire-student-1/profile/card#me
    if len(parts) >= 4:
        pod = parts[3]
        if "student" in pod or pod in ("ayoub",):
            return "student"
        if "teacher" in pod or pod in ("claire",):
            return "teacher"
        if "parent" in pod or pod in ("fatima",):
            return "parent"
        if "admin" in pod:
            return "admin"
    return None
