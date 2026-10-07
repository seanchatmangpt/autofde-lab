"""AIRo risk description test: parse + structure + cited-path existence.

Mirrors the repo's Chicago-style idiom: parse the real TTL from disk, assert on
the real graph, and require every cited evidence path (file: URI) to exist on disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import RDFS

AIRO = Namespace("https://w3id.org/airo#")
SYSTEM = URIRef("https://autofde-lab.example/airo/beam-diagnosis-system")

REPO = Path(__file__).resolve().parents[2]
TTL = REPO / "ontology" / "airo_risk_description.ttl"


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = Graph()
    g.parse(TTL.as_uri(), format="turtle")
    return g


def test_ttl_exists_and_parses(graph: Graph) -> None:
    assert TTL.is_file()
    assert len(graph) > 0


def test_system_is_typed_airo_ai_system(graph: Graph) -> None:
    assert (SYSTEM, RDF.type, AIRO.AISystem) in graph


def test_risks_sources_controls_structure(graph: Graph) -> None:
    risks = set(graph.subjects(RDF.type, AIRO.Risk))
    sources = set(graph.subjects(RDF.type, AIRO.RiskSource))
    controls = set(graph.subjects(RDF.type, AIRO.RiskControl))
    assert len(risks) >= 2
    assert len(sources) >= 2
    assert len(controls) >= 3
    for source in sources:
        assert any(graph.objects(source, AIRO.isRiskSourceFor)), source
    for risk in risks:
        assert any(graph.objects(risk, AIRO.hasRiskControl)), risk
    for control in controls:
        assert any(graph.objects(control, AIRO.mitigatesRiskConcept)), control


def test_qualitative_likelihood_severity_impact(graph: Graph) -> None:
    for risk in graph.subjects(RDF.type, AIRO.Risk):
        assert any(graph.objects(risk, AIRO.hasLikelihood)), risk
    severities = list(graph.subjects(RDF.type, AIRO.Severity))
    impacts = list(graph.subjects(RDF.type, AIRO.Impact))
    assert severities, "qualitative severity individuals expected"
    assert impacts
    for impact in impacts:
        assert any(graph.objects(impact, AIRO.hasSeverity)), impact


def test_every_cited_evidence_path_exists(graph: Graph) -> None:
    cited = set(graph.objects(None, RDFS.seeAlso))
    assert len(cited) >= 6
    for uri in cited:
        rel = str(uri)
        assert rel.startswith("file:"), uri
        path = REPO / rel[len("file:"):]
        assert path.is_file(), f"cited evidence path missing: {path}"
        # Cited tests must be real test files; cited docs must be non-empty.
        if "tests/" in rel:
            assert "test_" in path.name, path
        else:
            assert path.stat().st_size > 0, path


def test_labels_on_all_defined_individuals(graph: Graph) -> None:
    for s in set(graph.subjects(RDF.type, None)):
        assert any(graph.objects(s, RDFS.label)), s
