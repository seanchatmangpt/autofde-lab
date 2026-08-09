from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from rdflib import Graph, Namespace, RDF

ROOT = Path(__file__).resolve().parents[2]
ARCH = Namespace('urn:autofde-lab:architecture:')


def _load_generator():
    path = ROOT / 'scripts' / 'ontology' / 'mermaid_architecture.py'
    spec = importlib.util.spec_from_file_location('mermaid_architecture', path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sources() -> list[Path]:
    return sorted(
        [*ROOT.glob('docs/c4/*.mmd'), *ROOT.glob('docs/diagrams/*.mmd')],
        key=lambda p: int(p.name.split('_', 1)[0]),
    )


def _catalogs() -> list[Path]:
    return sorted(ROOT.glob('ontology/architecture/catalog/*.ttl'))


def _merged_catalog() -> Graph:
    g = Graph()
    for p in _catalogs():
        g.parse(p, format='turtle')
    return g


def test_fifty_mermaid_sources_have_ten_parseable_ontology_catalog_bundles() -> None:
    assert len(_sources()) == 50
    assert len(_catalogs()) == 10
    g = _merged_catalog()
    assert len(set(g.subjects(RDF.type, ARCH.Diagram))) == 50


def test_every_catalog_entry_is_identity_bound_to_its_exact_mermaid_source() -> None:
    g = _merged_catalog()
    by_path = {str(g.value(d, ARCH.sourcePath)): d for d in set(g.subjects(RDF.type, ARCH.Diagram))}
    assert len(by_path) == 50
    for src in _sources():
        rel = src.relative_to(ROOT).as_posix()
        diagram = by_path[rel]
        assert str(g.value(diagram, ARCH.sourceDigest)) == hashlib.sha256(src.read_bytes()).hexdigest()
        assert str(g.value(diagram, ARCH.parseStanding)) == 'PARSED'


def test_detailed_parser_materializes_real_elements_and_relationships_for_all_sources() -> None:
    generator = _load_generator()
    for src in _sources():
        g = generator.build(src)
        diagram = next(g.subjects(RDF.type, ARCH.Diagram))
        assert int(str(g.value(diagram, ARCH.elementCount))) > 0
        assert int(str(g.value(diagram, ARCH.relationshipCount))) > 0


def test_core_vocabulary_and_shacl_shapes_are_parseable() -> None:
    Graph().parse(ROOT / 'ontology' / 'architecture.ttl', format='turtle')
    Graph().parse(ROOT / 'ontology' / 'shapes' / 'architecture.shacl.ttl', format='turtle')
