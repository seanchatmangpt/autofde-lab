"""RDF projection for the language-neutral IEC semantic graph.

RDF is a projection of the immutable SemanticGraph.  The Python graph remains
the exact in-process subject for this module; downstream ontology admission may
promote the RDF projection separately.
"""

from __future__ import annotations

from rdflib import RDF, Graph, Literal, Namespace, URIRef

from .graph_ir import SemanticGraph
from .model import digest

IEC = Namespace("urn:autofde-lab:iec:")
NODE = Namespace("urn:autofde-lab:iec:node:")


def _node_iri(node_id: str) -> URIRef:
    return NODE[node_id.split(":", 1)[-1]]


def to_rdf(graph: SemanticGraph) -> Graph:
    result = Graph()
    result.bind("iec", IEC)

    for node in graph.nodes:
        subject = _node_iri(node.node_id)
        result.add((subject, RDF.type, IEC.SemanticNode))
        result.add((subject, IEC.nodeKind, Literal(node.kind)))
        result.add((subject, IEC.nodeKey, Literal(node.key)))
        result.add((subject, IEC.evidenceKind, Literal(node.evidence_kind.value)))
        for name, value in node.attributes:
            attribute = URIRef(f"{IEC}attribute/{name}")
            result.add((subject, attribute, Literal(value)))
        for evidence_id in node.evidence_ids:
            result.add((subject, IEC.evidenceId, Literal(evidence_id)))

    for edge in graph.edges:
        edge_iri = NODE[edge.edge_id.split(":", 1)[-1]]
        result.add((edge_iri, RDF.type, IEC.SemanticEdge))
        result.add((edge_iri, IEC.source, _node_iri(edge.source)))
        result.add((edge_iri, IEC.target, _node_iri(edge.target)))
        result.add((edge_iri, IEC.relation, Literal(edge.predicate)))
        result.add((edge_iri, IEC.evidenceKind, Literal(edge.evidence_kind.value)))
        for name, value in edge.attributes:
            attribute = URIRef(f"{IEC}edgeAttribute/{name}")
            result.add((edge_iri, attribute, Literal(value)))
        for evidence_id in edge.evidence_ids:
            result.add((edge_iri, IEC.evidenceId, Literal(evidence_id)))

    return result


def canonical_ntriples(graph: SemanticGraph) -> str:
    rdf_graph = to_rdf(graph)
    lines = [
        line for line in rdf_graph.serialize(format="nt").splitlines() if line.strip()
    ]
    return "\n".join(sorted(lines)) + "\n"


def rdf_projection_id(graph: SemanticGraph) -> str:
    return digest(
        {
            "semantic_graph_id": graph.graph_id,
            "ntriples": canonical_ntriples(graph),
        }
    )
