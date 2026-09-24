"""Evidence-lineage DAG for observations, claims, projections, and receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model import digest


@dataclass(frozen=True, slots=True)
class LineageEdge:
    parent_id: str
    child_id: str
    relation: str

    def __post_init__(self) -> None:
        if (
            not self.parent_id.strip()
            or not self.child_id.strip()
            or not self.relation.strip()
        ):
            raise ValueError("lineage edge requires parent, child, and relation")
        if self.parent_id == self.child_id:
            raise ValueError("lineage self-cycle refused")

    @property
    def edge_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class EvidenceLineage:
    edges: tuple[LineageEdge, ...]

    @classmethod
    def build(cls, edges: Iterable[LineageEdge]) -> "EvidenceLineage":
        graph = cls(tuple(sorted(set(edges), key=lambda edge: edge.edge_id)))
        graph._assert_acyclic()
        return graph

    @property
    def lineage_id(self) -> str:
        return digest(self.edges)

    def parents(self, identity: str) -> tuple[str, ...]:
        return tuple(
            sorted(edge.parent_id for edge in self.edges if edge.child_id == identity)
        )

    def children(self, identity: str) -> tuple[str, ...]:
        return tuple(
            sorted(edge.child_id for edge in self.edges if edge.parent_id == identity)
        )

    def ancestors(self, identity: str) -> frozenset[str]:
        result: set[str] = set()
        stack = list(self.parents(identity))
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(self.parents(current))
        return frozenset(result)

    def _assert_acyclic(self) -> None:
        nodes = {
            identity
            for edge in self.edges
            for identity in (edge.parent_id, edge.child_id)
        }
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(node: str) -> None:
            if node in permanent:
                return
            if node in temporary:
                raise ValueError("cyclic evidence lineage refused")
            temporary.add(node)
            for child in self.children(node):
                visit(child)
            temporary.remove(node)
            permanent.add(node)

        for node in sorted(nodes):
            visit(node)
