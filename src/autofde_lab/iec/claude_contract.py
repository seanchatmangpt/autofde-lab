"""Typed handoff contract for Claude or another expensive semantic reasoner.

Outputs are hypotheses only. This module intentionally contains no provider
client and no autonomous execution loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from .frontier import FrontierItem
from .model import EvidenceKind, SemanticClaim, digest


@dataclass(frozen=True, slots=True)
class ArchaeologyPacket:
    exact_subject_ids: tuple[str, ...]
    frontier_items: tuple[FrontierItem, ...]
    evidence_ids: tuple[str, ...]
    prior_art_requirements: tuple[str, ...] = (
        "search existing standards and mature formal methods before invention",
        "reuse ggen-create and framework-native generators before local synthesis",
        "treat similarity as candidate evidence only",
    )
    hard_constraints: tuple[str, ...] = (
        "preserve UNKNOWN",
        "no ambient DO authority",
        "no repository deletion or merge",
        "no generated projection hand editing",
        "every equivalence hypothesis requires a falsifier",
    )

    @property
    def packet_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ArchaeologyHypothesis:
    packet_id: str
    subject: str
    predicate: str
    object: str
    evidence_ids: tuple[str, ...]
    exclusions: tuple[str, ...]
    falsifier: str
    rationale_digest: str | None = None
    evidence_kind: EvidenceKind = EvidenceKind.INFERRED_CANDIDATE
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if self.evidence_kind is not EvidenceKind.INFERRED_CANDIDATE:
            raise ValueError("semantic reasoner output starts as INFERRED_CANDIDATE")
        if self.authority != "NONE":
            raise ValueError("semantic reasoner output has no execution authority")
        if not self.falsifier.strip():
            raise ValueError("hypothesis requires a falsifier")

    @property
    def hypothesis_id(self) -> str:
        return digest(self)

    def as_semantic_claim(self) -> SemanticClaim:
        return SemanticClaim(
            subject=self.subject,
            predicate=self.predicate,
            object=self.object,
            evidence_kind=EvidenceKind.INFERRED_CANDIDATE,
            evidence_ids=self.evidence_ids,
            exclusions=self.exclusions,
            falsifier=self.falsifier,
        )


def make_packet(
    *,
    exact_subject_ids: tuple[str, ...],
    frontier_items: tuple[FrontierItem, ...],
    evidence_ids: tuple[str, ...],
) -> ArchaeologyPacket:
    if not exact_subject_ids:
        raise ValueError("Claude archaeology packet requires exact subjects")
    if not frontier_items:
        raise ValueError("Claude archaeology packet requires bounded frontier items")
    return ArchaeologyPacket(
        exact_subject_ids=tuple(sorted(set(exact_subject_ids))),
        frontier_items=frontier_items,
        evidence_ids=tuple(sorted(set(evidence_ids))),
    )
