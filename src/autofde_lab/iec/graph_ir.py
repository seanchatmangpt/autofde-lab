"""Language-neutral semantic graph for IEC observations and admitted hypotheses.

The graph is intentionally small: nodes and edges carry exact evidence ids and
standing, and every mutation returns a new immutable graph.  It is an
intermediate representation, not a source of external authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .model import EvidenceKind, digest


@dataclass(frozen=True, slots=True)
class SemanticNode:
    kind: str
    key: str
    attributes: tuple[tuple[str, str], ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_kind: EvidenceKind = EvidenceKind.INFERRED_CANDIDATE

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.key.strip():
            raise ValueError("semantic node requires kind and key")
        if tuple(sorted(self.attributes)) != self.attributes:
            raise ValueError("node attributes must be sorted")
        if len(self.attributes) != len({name for name, _ in self.attributes}):
            raise ValueError("duplicate node attribute")

    @classmethod
    def create(
        cls,
        *,
        kind: str,
        key: str,
        attributes: Mapping[str, str] | None = None,
        evidence_ids: Iterable[str] = (),
        evidence_kind: EvidenceKind = EvidenceKind.INFERRED_CANDIDATE,
    ) -> "SemanticNode":
        return cls(
            kind=kind,
            key=key,
            attributes=tuple(sorted((attributes or {}).items())),
            evidence_ids=tuple(sorted(set(evidence_ids))),
            evidence_kind=evidence_kind,
        )

    @property
    def node_id(self) -> str:
        return digest(
            {
                "kind": self.kind,
                "key": self.key,
                "attributes": self.attributes,
            }
        )


@dataclass(frozen=True, slots=True)
class SemanticEdge:
    source: str
    predicate: str
    target: str
    attributes: tuple[tuple[str, str], ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_kind: EvidenceKind = EvidenceKind.INFERRED_CANDIDATE

    def __post_init__(self) -> None:
        for value, label in (
            (self.source, "source"),
            (self.predicate, "predicate"),
            (self.target, "target"),
        ):
            if not value.strip():
                raise ValueError(f"semantic edge requires {label}")
        if tuple(sorted(self.attributes)) != self.attributes:
            raise ValueError("edge attributes must be sorted")

    @classmethod
    def create(
        cls,
        *,
        source: str,
        predicate: str,
        target: str,
        attributes: Mapping[str, str] | None = None,
        evidence_ids: Iterable[str] = (),
        evidence_kind: EvidenceKind = EvidenceKind.INFERRED_CANDIDATE,
    ) -> "SemanticEdge":
        return cls(
            source=source,
            predicate=predicate,
            target=target,
            attributes=tuple(sorted((attributes or {}).items())),
            evidence_ids=tuple(sorted(set(evidence_ids))),
            evidence_kind=evidence_kind,
        )

    @property
    def edge_id(self) -> str:
        return digest(
            {
                "source": self.source,
                "predicate": self.predicate,
                "target": self.target,
                "attributes": self.attributes,
            }
        )


@dataclass(frozen=True, slots=True)
class SemanticGraph:
    nodes: tuple[SemanticNode, ...] = ()
    edges: tuple[SemanticEdge, ...] = ()

    def __post_init__(self) -> None:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate semantic node")
        edge_ids = [edge.edge_id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate semantic edge")
        known = set(node_ids)
        dangling = [
            edge.edge_id
            for edge in self.edges
            if edge.source not in known or edge.target not in known
        ]
        if dangling:
            raise ValueError("dangling semantic edges: " + ",".join(dangling))

    @classmethod
    def build(
        cls,
        nodes: Iterable[SemanticNode],
        edges: Iterable[SemanticEdge],
    ) -> "SemanticGraph":
        return cls(
            nodes=tuple(sorted(nodes, key=lambda node: node.node_id)),
            edges=tuple(sorted(edges, key=lambda edge: edge.edge_id)),
        )

    @property
    def graph_id(self) -> str:
        return digest(
            {
                "nodes": tuple(node.node_id for node in self.nodes),
                "edges": tuple(edge.edge_id for edge in self.edges),
            }
        )

    def node(self, node_id: str) -> SemanticNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def outgoing(self, node_id: str) -> tuple[SemanticEdge, ...]:
        return tuple(edge for edge in self.edges if edge.source == node_id)

    def incoming(self, node_id: str) -> tuple[SemanticEdge, ...]:
        return tuple(edge for edge in self.edges if edge.target == node_id)

    def reachable(self, start: str) -> frozenset[str]:
        if start not in {node.node_id for node in self.nodes}:
            raise KeyError(start)
        visited: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(
                edge.target
                for edge in self.outgoing(current)
                if edge.target not in visited
            )
        return frozenset(visited)

    def subgraph(self, node_ids: Iterable[str]) -> "SemanticGraph":
        admitted = set(node_ids)
        nodes = tuple(node for node in self.nodes if node.node_id in admitted)
        edges = tuple(
            edge
            for edge in self.edges
            if edge.source in admitted and edge.target in admitted
        )
        return SemanticGraph.build(nodes, edges)
