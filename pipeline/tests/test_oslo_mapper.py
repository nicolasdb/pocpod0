"""Tests for oslo_mapper.py — OSLO class mapping, namespaces, provenance."""

import json
import uuid

import pytest
from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, XSD

from pocpod0_pipeline.oslo_mapper import xapi_to_rdf

POCPOD0 = Namespace("https://poc-pod0.edu/vocab/")
OSLO    = Namespace("http://data.europa.eu/m8g/")
FOAF    = Namespace("http://xmlns.com/foaf/0.1/")
XAPI_NS = Namespace("https://w3id.org/xapi/ontology#")

SAMPLE_STMT = {
    "id": str(uuid.uuid4()),
    "actor": {
        "objectType": "Agent",
        "account": {
            "homePage": "http://localhost:3000",
            "name": "http://localhost:3000/ayoub/profile/card#me",
        },
        "name": "Ayoub",
    },
    "verb": {
        "id": "http://adlnet.gov/expapi/verbs/completed",
        "display": {"en-US": "completed"},
    },
    "object": {
        "objectType": "Activity",
        "id": "https://poc-pod0.edu/vocab/activity-math-assessment-fractions",
        "definition": {
            "name": {"en-US": "Mathematics Assessment: Fractions"},
            "type": "http://adlnet.gov/expapi/activities/assessment",
        },
    },
    "result": {
        "score": {"scaled": 0.85},
        "success": True,
        "completion": True,
    },
    "context": {
        "platform": "pocpod0",
        "extensions": {
            "https://poc-pod0.edu/vocab/ext-emotional-state": "confident",
        },
    },
    "timestamp": "2025-10-15T09:30:00Z",
}


@pytest.fixture(scope="module")
def graph():
    return xapi_to_rdf(SAMPLE_STMT, pod_resource_uri="http://localhost:3000/ayoub/learning/test.ttl")


# ---------------------------------------------------------------------------
# Statement type triples
# ---------------------------------------------------------------------------

def test_statement_is_learning_statement(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    assert (stmt_uri, RDF.type, POCPOD0.LearningStatement) in graph


def test_statement_is_xapi_statement(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    assert (stmt_uri, RDF.type, XAPI_NS.Statement) in graph


# ---------------------------------------------------------------------------
# Actor -> OSLO Person
# ---------------------------------------------------------------------------

def test_actor_mapped_to_oslo_person(graph):
    actor_uri = URIRef("http://localhost:3000/ayoub/profile/card#me")
    assert (actor_uri, RDF.type, OSLO.Person) in graph


def test_actor_has_name(graph):
    actor_uri = URIRef("http://localhost:3000/ayoub/profile/card#me")
    names = list(graph.objects(actor_uri, FOAF.name))
    assert len(names) == 1
    assert str(names[0]) == "Ayoub"


def test_actor_role_inferred(graph):
    actor_uri = URIRef("http://localhost:3000/ayoub/profile/card#me")
    roles = list(graph.objects(actor_uri, POCPOD0.role))
    assert len(roles) == 1
    assert str(roles[0]) == "student"


# ---------------------------------------------------------------------------
# Verb -> OSLO education activity types
# ---------------------------------------------------------------------------

def test_verb_mapped(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    verbs = list(graph.objects(stmt_uri, POCPOD0.verb))
    assert len(verbs) == 1
    assert str(verbs[0]) == "http://adlnet.gov/expapi/verbs/completed"


# ---------------------------------------------------------------------------
# Object -> OSLO PublicService
# ---------------------------------------------------------------------------

def test_object_mapped_to_oslo_public_service(graph):
    obj_uri = URIRef("https://poc-pod0.edu/vocab/activity-math-assessment-fractions")
    assert (obj_uri, RDF.type, OSLO.PublicService) in graph


# ---------------------------------------------------------------------------
# Result -> OSLO Participation
# ---------------------------------------------------------------------------

def test_result_mapped_to_oslo_participation(graph):
    stmt_id = SAMPLE_STMT["id"]
    result_uri = URIRef(f"https://poc-pod0.edu/results/{stmt_id}")
    assert (result_uri, RDF.type, OSLO.Participation) in graph


def test_result_score_present(graph):
    stmt_id = SAMPLE_STMT["id"]
    result_uri = URIRef(f"https://poc-pod0.edu/results/{stmt_id}")
    scores = list(graph.objects(result_uri, POCPOD0.scaledScore))
    assert len(scores) == 1
    assert float(scores[0]) == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Namespace prefixes are correct
# ---------------------------------------------------------------------------

def test_pocpod0_namespace_bound(graph):
    prefixes = dict(graph.namespaces())
    assert "pocpod0" in prefixes
    assert str(prefixes["pocpod0"]) == "https://poc-pod0.edu/vocab/"


def test_oslo_namespace_bound(graph):
    prefixes = dict(graph.namespaces())
    assert "oslo" in prefixes


# ---------------------------------------------------------------------------
# Lossless: originalXapiJson present and recoverable
# ---------------------------------------------------------------------------

def test_original_xapi_json_preserved(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    originals = list(graph.objects(stmt_uri, POCPOD0.originalXapiJson))
    assert len(originals) == 1
    recovered = json.loads(str(originals[0]))
    assert recovered["id"] == stmt_id
    assert recovered["actor"]["account"]["name"] == "http://localhost:3000/ayoub/profile/card#me"


def test_original_xapi_statement_id_preserved(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    ids = list(graph.objects(stmt_uri, POCPOD0.originalXapiStatementId))
    assert len(ids) == 1
    assert str(ids[0]) == stmt_id


# ---------------------------------------------------------------------------
# Provenance triple (prov:wasDerivedFrom)
# ---------------------------------------------------------------------------

def test_provenance_triple_present(graph):
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    pod_uri = URIRef("http://localhost:3000/ayoub/learning/test.ttl")
    assert (stmt_uri, PROV.wasDerivedFrom, pod_uri) in graph


def test_no_provenance_when_not_provided():
    g = xapi_to_rdf(SAMPLE_STMT)
    stmt_id = SAMPLE_STMT["id"]
    stmt_uri = URIRef(f"https://poc-pod0.edu/statements/{stmt_id}")
    prov_triples = list(g.triples((stmt_uri, PROV.wasDerivedFrom, None)))
    assert len(prov_triples) == 0
