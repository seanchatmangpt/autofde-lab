# Architecture ontology projection

The 50 Mermaid diagrams under `docs/c4/` and `docs/diagrams/` are the admitted source observations.

`ontology/architecture.ttl` defines one shared semantic basis. `graphs/*.ttl` are **generated** RDF projections grouped into ten bundles of five diagrams: five C4 scopes plus sequence, state, flow, class, and ER families. Every diagram remains an individually addressable `arch:Diagram` with exact source path, SHA-256 source digest, diagram kind, elements, relationships, and source-line provenance.

Do **not** hand-edit `graphs/*.ttl`. Regenerate them:

```bash
python scripts/ontology/mermaid_architecture.py
python scripts/ontology/mermaid_architecture.py --check
```

Validation basis:

- RDF vocabulary: `ontology/architecture.ttl`
- SHACL: `ontology/shapes/architecture.shacl.ttl`
- Source identity: `arch:sourcePath` + `arch:sourceDigest`
- Public ontology reuse: DCTERMS, PROV-O, SKOS, OWL/RDFS/XSD
- Drift tests: `tests/ontology/test_architecture_diagram_ontology_chicago.py`

The ontology projection is intentionally generic. C4, sequence, state, flow, class, and ER syntax become one graph algebra rather than six unrelated semantic systems.
