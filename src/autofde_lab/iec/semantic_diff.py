"""Deterministic semantic-graph delta for incremental archaeology."""

from __future__ import annotations

from dataclasses import dataclass

from .graph_ir import SemanticGraph
from .model import digest


@dataclass(frozen=True, slots=True)
class SemanticGraphDelta:
    base_graph_id: str
    candidate_graph_id: str
    added_node_ids: tuple[str, ...]
    removed_node_ids: tuple[str, ...]
    added_edge_ids: tuple[str, ...]
    removed_edge_ids: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not (
            self.added_node_ids
            or self.removed_node_ids
            or self.added_edge_ids
            or self.removed_edge_ids
        )

    @property
    def delta_id(self) -> str:
        return digest(self)


def diff_graphs(
    base: SemanticGraph,
    candidate: SemanticGraph,
) -> SemanticGraphDelta:
    base_nodes = {node.node_id for node in base.nodes}
    candidate_nodes = {node.node_id for node in candidate.nodes}
    base_edges = {edge.edge_id for edge in base.edges}
    candidate_edges = {edge.edge_id for edge in candidate.edges}
    return SemanticGraphDelta(
        base_graph_id=base.graph_id,
        candidate_graph_id=candidate.graph_id,
        added_node_ids=tuple(sorted(candidate_nodes - base_nodes)),
        removed_node_ids=tuple(sorted(base_nodes - candidate_nodes)),
        added_edge_ids=tuple(sorted(candidate_edges - base_edges)),
        removed_edge_ids=tuple(sorted(base_edges - candidate_edges)),
    )
