"""Tests for Canonicalizer and SHACL/ShEx validation layers (RFC-SA2A-001)."""

import pytest
import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import RDF, XSD

from autofde_lab.sa2a.admission.canonicalizer import (
    canonicalize_graph,
    compute_graph_digest,
)
from autofde_lab.sa2a.admission.shacl_layer import ShaclValidator
from autofde_lab.sa2a.admission.shex_layer import (
    NodeKind,
    PredicateConstraint,
    ShexValidator,
    StructuralShape,
)


class TestCanonicalizer:
    def test_canonicalize_deterministic_insertion_order(self):
        """Graphs created with identical triples in different order have identical canonical output."""
        g1 = rdflib.Graph()
        g2 = rdflib.Graph()

        s1 = URIRef("http://example.org/entity/1")
        s2 = URIRef("http://example.org/entity/2")
        p1 = URIRef("http://example.org/pred/name")
        p2 = URIRef("http://example.org/pred/age")
        o1 = Literal("Alice")
        o2 = Literal("30", datatype=XSD.integer)
        o3 = Literal("Bob")

        # Add triples in order A
        g1.add((s1, p1, o1))
        g1.add((s1, p2, o2))
        g1.add((s2, p1, o3))

        # Add triples in reversed / different order B
        g2.add((s2, p1, o3))
        g2.add((s1, p2, o2))
        g2.add((s1, p1, o1))

        c1 = canonicalize_graph(g1)
        c2 = canonicalize_graph(g2)

        assert c1 == c2
        assert compute_graph_digest(g1) == compute_graph_digest(g2)
        assert len(compute_graph_digest(g1)) == 64  # SHA-256 hex digest length

    def test_canonicalize_blank_node_isomorphism(self):
        """Graphs with isomorphic blank node structures produce identical canonical hashes."""
        g1 = rdflib.Graph()
        g2 = rdflib.Graph()

        b1_a = BNode()
        b1_b = BNode()
        b2_x = BNode()
        b2_y = BNode()

        link = URIRef("http://example.org/link")
        val = URIRef("http://example.org/value")

        g1.add((b1_a, link, b1_b))
        g1.add((b1_b, val, Literal("test-data")))

        g2.add((b2_x, link, b2_y))
        g2.add((b2_y, val, Literal("test-data")))

        digest1 = compute_graph_digest(g1)
        digest2 = compute_graph_digest(g2)
        assert digest1 == digest2


class TestShaclLayer:
    @pytest.fixture
    def person_shapes(self):
        return """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:PersonShape a sh:NodeShape ;
            sh:targetClass ex:Person ;
            sh:property [
                sh:path ex:name ;
                sh:datatype xsd:string ;
                sh:minCount 1 ;
                sh:maxCount 1 ;
                sh:message "Person must have exactly one string name" ;
            ] ;
            sh:property [
                sh:path ex:age ;
                sh:datatype xsd:integer ;
                sh:minCount 1 ;
                sh:message "Person must have at least one integer age" ;
            ] .
        """

    def test_shacl_validation_conforms(self, person_shapes):
        validator = ShaclValidator(shapes=person_shapes)
        valid_data = """
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        ex:Alice a ex:Person ;
            ex:name "Alice" ;
            ex:age 35 .
        """
        report = validator.validate(valid_data)
        assert report.conforms is True
        assert len(report.violations) == 0

    def test_shacl_validation_failure_missing_required_property(self, person_shapes):
        validator = ShaclValidator(shapes=person_shapes)
        invalid_data = """
        @prefix ex: <http://example.org/> .

        ex:Bob a ex:Person ;
            ex:name "Bob" .
        """
        report = validator.validate(invalid_data)
        assert report.conforms is False
        assert len(report.violations) > 0
        assert any(
            "age" in v.lower()
            or "person must have at least one integer age" in v.lower()
            for v in report.violations
        )

    def test_shacl_validation_failure_wrong_datatype(self, person_shapes):
        validator = ShaclValidator(shapes=person_shapes)
        invalid_data = """
        @prefix ex: <http://example.org/> .

        ex:Charlie a ex:Person ;
            ex:name "Charlie" ;
            ex:age "not-an-integer" .
        """
        report = validator.validate(invalid_data)
        assert report.conforms is False
        assert len(report.violations) > 0


class TestShexLayer:
    def test_shex_structural_validation(self):
        ex = rdflib.Namespace("http://example.org/")

        agent_shape = StructuralShape(
            name="AgentShape",
            target_class=ex.Agent,
            node_kind=NodeKind.IRI,
            required_types=(ex.Agent,),
            predicates=(
                PredicateConstraint(
                    predicate=ex.agentId,
                    min_count=1,
                    max_count=1,
                    node_kind=NodeKind.LITERAL,
                ),
                PredicateConstraint(
                    predicate=ex.status,
                    min_count=1,
                    allowed_values=(Literal("ACTIVE"), Literal("IDLE")),
                ),
            ),
            closed=True,
        )

        validator = ShexValidator([agent_shape])

        # Valid agent graph
        g_valid = rdflib.Graph()
        alice = ex.Alice
        g_valid.add((alice, RDF.type, ex.Agent))
        g_valid.add((alice, ex.agentId, Literal("agent-007")))
        g_valid.add((alice, ex.status, Literal("ACTIVE")))

        rep_valid = validator.validate(g_valid)
        assert rep_valid.conforms is True
        assert len(rep_valid.violations) == 0

        # Invalid: missing agentId, bad status enum, extra property in closed shape
        g_invalid = rdflib.Graph()
        bob = ex.Bob
        g_invalid.add((bob, RDF.type, ex.Agent))
        g_invalid.add((bob, ex.status, Literal("UNKNOWN_STATUS")))
        g_invalid.add((bob, ex.extraProp, Literal("unwanted")))

        rep_invalid = validator.validate(g_invalid)
        assert rep_invalid.conforms is False
        assert len(rep_invalid.violations) >= 3
        violation_text = " ".join(rep_invalid.violations)
        assert "minCount violation" in violation_text
        assert "allowed values" in violation_text
        assert "unpermitted predicate" in violation_text
