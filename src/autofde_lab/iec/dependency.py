"""Dependency closure over semantic graph relations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .graph_ir import SemanticGraph
from .model import digest


@dataclass(frozen=True, slots=True)
class DependencyClosure:
    root_ids: tuple[str, ...]
    included_node_ids: tuple[str, ...]
    included_edge_ids: tuple[str, ...]
    predicates: tuple[str, ...]
    direction: str

    @property
    def closure_id(self) -> str:
        return digest(self)


def dependency_closure(
    graph: SemanticGraph,
    roots: Iterable[str],
    *,
    predicates: Iterable[str] = (),
    direction: str = "outgoing",
) -> DependencyClosure:
    if direction not in {"outgoing", "incoming", "both"}:
        raise ValueError("direction must be outgoing, incoming, or both")
    roots_tuple = tuple(sorted(set(roots)))
    if not roots_tuple:
        raise ValueError("dependency closure requires roots")
    known = {node.node_id for node in graph.nodes}
    unknown = set(roots_tuple) - known
    if unknown:
        raise KeyError("unknown dependency roots: " + ",".join(sorted(unknown)))

    admitted_predicates = frozenset(predicates)
    visited: set[str] = set()
    edge_ids: set[str] = set()
    stack = list(roots_tuple)

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)

        candidate_edges = []
        if direction in {"outgoing", "both"}:
            candidate_edges.extend(graph.outgoing(current))
        if direction in {"incoming", "both"}:
            candidate_edges.extend(graph.incoming(current))

        for edge in candidate_edges:
            if admitted_predicates and edge.predicate not in admitted_predicates:
                continue
            edge_ids.add(edge.edge_id)
            neighbor = edge.target if edge.source == current else edge.source
            if neighbor not in visited:
                stack.append(neighbor)

    return DependencyClosure(
        root_ids=roots_tuple,
        included_node_ids=tuple(sorted(visited)),
        included_edge_ids=tuple(sorted(edge_ids)),
        predicates=tuple(sorted(admitted_predicates)),
        direction=direction,
    )
