"""
Tests for Story 2.1: OSLO Vocabulary Schema Contract

Validates that all 4 Turtle schema files are syntactically correct,
contain required namespace prefixes, xAPI-to-OSLO mappings, and
pocpod0: custom classes with rdfs:label annotations.
"""

import pytest
from pathlib import Path

try:
    import rdflib
    from rdflib import Graph, Namespace, RDF, RDFS, OWL
    from rdflib.namespace import SKOS

    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

pytestmark = pytest.mark.skipif(
    not HAS_RDFLIB, reason="rdflib not installed; run: pip install rdflib"
)

# Namespace constants
OSLO_EDUC = Namespace("https://data.vlaanderen.be/ns/onderwijs#")
OSLO_PERSON = Namespace("https://data.vlaanderen.be/ns/persoon#")
XAPI = Namespace("https://w3id.org/xapi/ontology#")
POCPOD0 = Namespace("https://pocpod0.example.org/vocab#")


# =============================================================================
# AC1/AC3: All 4 Turtle files parse without errors
# =============================================================================


class TestTurtleFilesExistAndParse:
    """AC1: Schema files exist. AC3: Files parse without errors."""

    def test_oslo_education_ttl_exists(self, oslo_education_ttl: Path):
        assert oslo_education_ttl.exists(), f"Missing: {oslo_education_ttl}"

    def test_oslo_person_ttl_exists(self, oslo_person_ttl: Path):
        assert oslo_person_ttl.exists(), f"Missing: {oslo_person_ttl}"

    def test_xapi_to_oslo_ttl_exists(self, xapi_to_oslo_ttl: Path):
        assert xapi_to_oslo_ttl.exists(), f"Missing: {xapi_to_oslo_ttl}"

    def test_pocpod0_vocab_ttl_exists(self, pocpod0_vocab_ttl: Path):
        assert pocpod0_vocab_ttl.exists(), f"Missing: {pocpod0_vocab_ttl}"

    def test_oslo_education_parses(self, oslo_education_ttl: Path):
        g = Graph()
        g.parse(str(oslo_education_ttl), format="turtle")
        assert len(g) > 0, "oslo-education.ttl parsed to empty graph"

    def test_oslo_person_parses(self, oslo_person_ttl: Path):
        g = Graph()
        g.parse(str(oslo_person_ttl), format="turtle")
        assert len(g) > 0, "oslo-person.ttl parsed to empty graph"

    def test_xapi_to_oslo_parses(self, xapi_to_oslo_ttl: Path):
        g = Graph()
        g.parse(str(xapi_to_oslo_ttl), format="turtle")
        assert len(g) > 0, "xapi-to-oslo.ttl parsed to empty graph"

    def test_pocpod0_vocab_parses(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")
        assert len(g) > 0, "pocpod0-vocab.ttl parsed to empty graph"


# =============================================================================
# AC2: Required namespace prefixes are defined
# =============================================================================


class TestNamespacePrefixes:
    """AC2: Namespace prefixes follow OSLO conventions."""

    REQUIRED_NAMESPACES = {
        "oslo-educ": "https://data.vlaanderen.be/ns/onderwijs#",
        "oslo-person": "https://data.vlaanderen.be/ns/persoon#",
        "xapi": "https://w3id.org/xapi/ontology#",
        "pocpod0": "https://pocpod0.example.org/vocab#",
    }

    def _load_combined(self, all_schema_files):
        g = Graph()
        for f in all_schema_files:
            g.parse(str(f), format="turtle")
        return g

    def test_oslo_educ_namespace_in_education(self, oslo_education_ttl: Path):
        g = Graph()
        g.parse(str(oslo_education_ttl), format="turtle")
        ns_map = dict(g.namespaces())
        assert "oslo-educ" in ns_map, "oslo-educ prefix not defined in oslo-education.ttl"
        assert str(ns_map["oslo-educ"]) == "https://data.vlaanderen.be/ns/onderwijs#"

    def test_oslo_person_namespace_in_person(self, oslo_person_ttl: Path):
        g = Graph()
        g.parse(str(oslo_person_ttl), format="turtle")
        ns_map = dict(g.namespaces())
        assert "oslo-person" in ns_map, "oslo-person prefix not defined in oslo-person.ttl"
        assert str(ns_map["oslo-person"]) == "https://data.vlaanderen.be/ns/persoon#"

    def test_xapi_namespace_in_mapping(self, xapi_to_oslo_ttl: Path):
        g = Graph()
        g.parse(str(xapi_to_oslo_ttl), format="turtle")
        ns_map = dict(g.namespaces())
        assert "xapi" in ns_map, "xapi prefix not defined in xapi-to-oslo.ttl"
        assert str(ns_map["xapi"]) == "https://w3id.org/xapi/ontology#"

    def test_pocpod0_namespace_in_vocab(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")
        ns_map = dict(g.namespaces())
        assert "pocpod0" in ns_map, "pocpod0 prefix not defined in pocpod0-vocab.ttl"
        assert str(ns_map["pocpod0"]) == "https://pocpod0.example.org/vocab#"


# =============================================================================
# AC2: All xAPI components have at least one OSLO mapping
# =============================================================================


class TestXapiToOsloMappings:
    """AC2: xAPI actor/verb/object/result/context each have OSLO mappings."""

    def _load_all(self, all_schema_files):
        g = Graph()
        for f in all_schema_files:
            g.parse(str(f), format="turtle")
        return g

    def test_xapi_actor_maps_to_oslo_person(self, all_schema_files):
        g = self._load_all(all_schema_files)
        # xapi:Agent should be owl:equivalentClass or rdfs:subClassOf an oslo-person class
        xapi_agent = XAPI.Agent
        oslo_registered = OSLO_PERSON.GeregistreerdPersoon
        has_mapping = (
            (xapi_agent, OWL.equivalentClass, oslo_registered) in g
            or (xapi_agent, RDFS.subClassOf, oslo_registered) in g
        )
        assert has_mapping, "xapi:Agent has no mapping to oslo-person:GeregistreerdPersoon"

    def test_xapi_verb_maps_to_oslo_activity(self, all_schema_files):
        g = self._load_all(all_schema_files)
        # xapi:Verb should have skos:closeMatch or equivalent to an oslo-educ class
        xapi_verb = XAPI.Verb
        oslo_activity = OSLO_EDUC.Leeractiviteit
        has_mapping = (
            (xapi_verb, SKOS.closeMatch, oslo_activity) in g
            or (xapi_verb, OWL.equivalentClass, oslo_activity) in g
        )
        assert has_mapping, "xapi:Verb has no mapping to oslo-educ:Leeractiviteit"

    def test_xapi_object_maps_to_oslo_resource(self, all_schema_files):
        g = self._load_all(all_schema_files)
        xapi_activity = XAPI.Activity
        oslo_resource = OSLO_EDUC.Leermiddel
        has_mapping = (
            (xapi_activity, SKOS.closeMatch, oslo_resource) in g
            or (xapi_activity, OWL.equivalentClass, oslo_resource) in g
        )
        assert has_mapping, "xapi:Activity has no mapping to oslo-educ:Leermiddel"

    def test_xapi_result_maps_to_oslo_evaluation(self, all_schema_files):
        g = self._load_all(all_schema_files)
        xapi_result = XAPI.Result
        oslo_result = OSLO_EDUC.EvaluatieResultaat
        has_mapping = (
            (xapi_result, OWL.equivalentClass, oslo_result) in g
            or (xapi_result, SKOS.closeMatch, oslo_result) in g
        )
        assert has_mapping, "xapi:Result has no mapping to oslo-educ:EvaluatieResultaat"

    def test_xapi_context_maps_to_oslo_institution(self, all_schema_files):
        g = self._load_all(all_schema_files)
        xapi_context = XAPI.Context
        oslo_institution = OSLO_EDUC.OnderwijsInstelling
        has_mapping = (
            (xapi_context, SKOS.closeMatch, oslo_institution) in g
            or (xapi_context, OWL.equivalentClass, oslo_institution) in g
        )
        assert has_mapping, "xapi:Context has no mapping to oslo-educ:OnderwijsInstelling"

    def test_core_adl_verbs_have_oslo_mappings(self, all_schema_files):
        """Key xAPI ADL verbs should each have a OSLO mapping."""
        from rdflib import URIRef

        g = self._load_all(all_schema_files)
        adl_verbs = [
            "http://adlnet.gov/expapi/verbs/attempted",
            "http://adlnet.gov/expapi/verbs/completed",
            "http://adlnet.gov/expapi/verbs/passed",
            "http://adlnet.gov/expapi/verbs/failed",
        ]
        for verb_uri in adl_verbs:
            verb = URIRef(verb_uri)
            has_mapping = any(
                (verb, pred, obj) in g
                for pred in [SKOS.closeMatch, SKOS.exactMatch, OWL.equivalentClass]
                for obj in g.objects(verb, pred)
            )
            assert has_mapping, f"ADL verb {verb_uri} has no OSLO mapping"

    def test_provenance_wasDerivedFrom_in_mapping(self, all_schema_files):
        """Mapping schema must reference prov:wasDerivedFrom for lossless recovery."""
        from rdflib import URIRef

        g = self._load_all(all_schema_files)
        prov_derived = URIRef("http://www.w3.org/ns/prov#wasDerivedFrom")
        # pocpod0:wasDerivedFromPodResource should be rdfs:subPropertyOf prov:wasDerivedFrom
        uses_prov = any(
            (s, RDFS.subPropertyOf, prov_derived) in g
            for s in g.subjects(RDFS.subPropertyOf, prov_derived)
        )
        assert uses_prov, "No property is rdfs:subPropertyOf prov:wasDerivedFrom"


# =============================================================================
# AC2: All pocpod0: custom classes have rdfs:label
# =============================================================================


class TestPocpod0ClassLabels:
    """AC2: All custom pocpod0: classes must have rdfs:label."""

    EXPECTED_POCPOD0_CLASSES = [
        POCPOD0.TutoringSession,
        POCPOD0.SelfStudyActivity,
        POCPOD0.RoboticsWorkshop,
        POCPOD0.ExtracurricularActivity,
        POCPOD0.CrossSchoolTransfer,
    ]

    def test_pocpod0_classes_have_rdfs_label(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")

        for cls in self.EXPECTED_POCPOD0_CLASSES:
            labels = list(g.objects(cls, RDFS.label))
            assert len(labels) > 0, f"{cls} is missing rdfs:label in pocpod0-vocab.ttl"

    def test_pocpod0_classes_have_rdfs_comment(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")

        for cls in self.EXPECTED_POCPOD0_CLASSES:
            comments = list(g.objects(cls, RDFS.comment))
            assert len(comments) > 0, f"{cls} is missing rdfs:comment in pocpod0-vocab.ttl"

    def test_pocpod0_deletedAt_property_has_label(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")
        labels = list(g.objects(POCPOD0.deletedAt, RDFS.label))
        assert len(labels) > 0, "pocpod0:deletedAt missing rdfs:label"

    def test_pocpod0_communityLanguage_property_has_label(self, pocpod0_vocab_ttl: Path):
        g = Graph()
        g.parse(str(pocpod0_vocab_ttl), format="turtle")
        labels = list(g.objects(POCPOD0.communityLanguage, RDFS.label))
        assert len(labels) > 0, "pocpod0:communityLanguage missing rdfs:label"
