"""Deterministic graph canonicalization (RFC-SA2A-001 §12).

Implements canonical graph formatting and deterministic digest computation
using rdflib's canonical isomorphic graph representation and sorted N-Triples.
"""

from __future__ import annotations

import hashlib
from typing import Union
import rdflib
from rdflib.compare import to_canonical_graph


def canonicalize_graph(graph: rdflib.Graph) -> str:
    """Canonicalize an RDF graph to a deterministic, sorted N-Triples string.

    Converts the input graph into a canonical graph representation where blank nodes
    are systematically renamed to deterministic identifiers. The resulting triples
    are sorted lexicographically to produce a stable, canonical N-Triples document.

    Args:
        graph: The RDF graph to canonicalize.

    Returns:
        Deterministic, line-sorted N-Triples string representation.
    """
    canonical_g = to_canonical_graph(graph)
    # Serialize to N-Triples
    raw_nt: str = canonical_g.serialize(format="nt")
    # Split lines, strip whitespace, remove empty lines, and sort lexicographically
    lines = [line.strip() for line in raw_nt.splitlines() if line.strip()]
    lines.sort()
    return "\n".join(lines) + ("\n" if lines else "")


def compute_graph_digest(
    graph: Union[rdflib.Graph, str],
    hash_algorithm: str = "sha256",
) -> str:
    """Compute a cryptographic digest of a canonicalized RDF graph.

    Args:
        graph: An RDF graph or a canonical N-Triples string.
        hash_algorithm: The hashlib algorithm name (default: 'sha256').

    Returns:
        Hexadecimal hash string of the canonical N-Triples encoding.
    """
    if isinstance(graph, rdflib.Graph):
        canonical_str = canonicalize_graph(graph)
    else:
        canonical_str = graph

    hasher = hashlib.new(hash_algorithm)
    hasher.update(canonical_str.encode("utf-8"))
    return hasher.hexdigest()
