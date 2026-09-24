"""Structural candidate matching over IEC semantic graphs.

Fingerprints compress the search space; they are not equivalence proofs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .graph_ir import SemanticGraph
from .model import digest


@dataclass(frozen=True, slots=True)
class NodeFingerprint:
    node_id: str
    rounds: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GraphMatchCandidate:
    left_node_id: str
    right_node_id: str
    fingerprint: str
    left_graph_id: str
    right_graph_id: str
    required_verifier: str = "iec.translation-validation"

    @property
    def candidate_id(self) -> str:
        return digest(self)


def fingerprints(
    graph: SemanticGraph,
    *,
    rounds: int = 2,
) -> tuple[NodeFingerprint, ...]:
    """Compute a deterministic Weisfeiler-Lehman-style local fingerprint."""

    if rounds < 0:
        raise ValueError("rounds must be non-negative")

    labels: dict[str, str] = {}
    for node in graph.nodes:
        labels[node.node_id] = digest(
            {
                "kind": node.kind,
                "attributes": node.attributes,
            }
        )

    for _ in range(rounds):
        next_labels: dict[str, str] = {}
        for node in graph.nodes:
            outgoing = sorted(
                (edge.predicate, labels[edge.target])
                for edge in graph.outgoing(node.node_id)
            )
            incoming = sorted(
                (edge.predicate, labels[edge.source])
                for edge in graph.incoming(node.node_id)
            )
            next_labels[node.node_id] = digest(
                {
                    "self": labels[node.node_id],
                    "outgoing": outgoing,
                    "incoming": incoming,
                }
            )
        labels = next_labels

    return tuple(
        NodeFingerprint(node_id=node_id, rounds=rounds, fingerprint=labels[node_id])
        for node_id in sorted(labels)
    )


def candidate_matches(
    left: SemanticGraph,
    right: SemanticGraph,
    *,
    rounds: int = 2,
) -> tuple[GraphMatchCandidate, ...]:
    left_fingerprints = fingerprints(left, rounds=rounds)
    right_fingerprints = fingerprints(right, rounds=rounds)

    left_by_fingerprint: dict[str, list[str]] = {}
    right_by_fingerprint: dict[str, list[str]] = {}
    for item in left_fingerprints:
        left_by_fingerprint.setdefault(item.fingerprint, []).append(item.node_id)
    for item in right_fingerprints:
        right_by_fingerprint.setdefault(item.fingerprint, []).append(item.node_id)

    candidates: list[GraphMatchCandidate] = []
    for fingerprint in sorted(set(left_by_fingerprint) & set(right_by_fingerprint)):
        for left_node_id in sorted(left_by_fingerprint[fingerprint]):
            for right_node_id in sorted(right_by_fingerprint[fingerprint]):
                candidates.append(
                    GraphMatchCandidate(
                        left_node_id=left_node_id,
                        right_node_id=right_node_id,
                        fingerprint=fingerprint,
                        left_graph_id=left.graph_id,
                        right_graph_id=right.graph_id,
                    )
                )
    return tuple(candidates)
