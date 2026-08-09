from __future__ import annotations

import hashlib
from pathlib import Path

from rdflib import Graph, Namespace, RDF

ROOT = Path(__file__).resolve().parents[2]
ARCH = Namespace('urn:autofde-lab:architecture:')


def _sources() -> list[Path]:
    return sorted(
        [*ROOT.glob('docs/c4/*.mmd'), *ROOT.glob('docs/diagrams/*.mmd')],
        key=lambda p: int(p.name.split('_', 1)[0]),
    )


def _graphs() -> list[Path]:
    return sorted(ROOT.glob('ontology/architecture/graphs/*.ttl'))


def _merged() -> Graph:
    g = Graph()
    for p in _graphs():
        g.parse(p, format='turtle')
    return g


def test_fifty_mermaid_sources_are_projected_into_ten_parseable_rdf_bundles() -> None:
    assert len(_sources()) == 50
    assert len(_graphs()) == 10
    for path in _graphs():
        Graph().parse(path, format='turtle')
    g = _merged()
    assert len(set(g.subjects(RDF.type, ARCH.Diagram))) == 50


def test_every_projection_is_identity_bound_to_its_exact_mermaid_source() -> None:
    g = _merged()
    by_path = {str(g.value(d, ARCH.sourcePath)): d for d in set(g.subjects(RDF.type, ARCH.Diagram))}
    assert len(by_path) == 50
    for src in _sources():
        rel = src.relative_to(ROOT).as_posix()
        diagram = by_path[rel]
        assert str(g.value(diagram, ARCH.sourceDigest)) == hashlib.sha256(src.read_bytes()).hexdigest()
        assert str(g.value(diagram, ARCH.parseStanding)) == 'PARSED'


def test_core_vocabulary_and_shacl_shapes_are_parseable() -> None:
    Graph().parse(ROOT / 'ontology' / 'architecture.ttl', format='turtle')
    Graph().parse(ROOT / 'ontology' / 'shapes' / 'architecture.shacl.ttl', format='turtle')
