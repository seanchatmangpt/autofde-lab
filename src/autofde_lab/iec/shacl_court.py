"""Real pySHACL structural admission for IEC RDF projections.

SHACL admission proves graph conformance to the supplied shapes. It does not
prove runtime behavior, semantic equivalence, or external authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyshacl import validate
from rdflib import Graph

from .model import digest


@dataclass(frozen=True, slots=True)
class ShaclAdmission:
    data_digest: str
    shapes_digest: str
    ontology_digest: str | None
    conforms: bool
    report_graph_digest: str
    report_text_digest: str
    claim_ceiling: str = "STRUCTURAL_RDF_SHACL_CONFORMANCE_ONLY"

    @property
    def admission_id(self) -> str:
        return digest(self)


def _graph_digest(graph: Graph) -> str:
    lines = [
        line
        for line in graph.serialize(format="nt").splitlines()
        if line.strip()
    ]
    return digest(sorted(lines))


def validate_graph(
    data_graph: Graph,
    shapes_graph: Graph,
    *,
    ontology_graph: Graph | None = None,
) -> ShaclAdmission:
    conforms, report_graph, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="rdfs" if ontology_graph is not None else "none",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
        meta_shacl=False,
        advanced=True,
        js=False,
        debug=False,
    )
    if not isinstance(report_graph, Graph):
        raise TypeError("pySHACL returned non-Graph report")
    return ShaclAdmission(
        data_digest=_graph_digest(data_graph),
        shapes_digest=_graph_digest(shapes_graph),
        ontology_digest=(
            _graph_digest(ontology_graph)
            if ontology_graph is not None
            else None
        ),
        conforms=bool(conforms),
        report_graph_digest=_graph_digest(report_graph),
        report_text_digest=digest(str(report_text)),
    )
