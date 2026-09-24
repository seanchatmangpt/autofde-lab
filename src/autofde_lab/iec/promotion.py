"""Promotion routing from IEC discoveries to owning repositories.

PromotionCandidate is an inert change intent. It is not a Git operation and
cannot merge, publish, or otherwise cross the BRCE consequence boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import digest


class CapabilityOwner(str, Enum):
    AUTOFDE_LAB = "seanchatmangpt/autofde-lab"
    GGEN_CREATE = "seanchatmangpt/ggen-create"
    GGEN_MARKETPLACE = "seanchatmangpt/ggen-marketplace"
    GGEN_IGNITER = "seanchatmangpt/ggen_igniter"
    ENGINEERING_STANDARDS = "seanchatmangpt/engineering-standards"
    GGEN_ECOSYSTEM = "seanchatmangpt/ggen-ecosystem"
    AFFIDAVIT = "seanchatmangpt/affidavit"
    XAAS = "seanchatmangpt/xaas"


class PromotionKind(str, Enum):
    EXPERIMENT = "EXPERIMENT"
    REVERSE_COMPILER_PRIMITIVE = "REVERSE_COMPILER_PRIMITIVE"
    REUSABLE_PACK = "REUSABLE_PACK"
    ELIXIR_PROJECTION = "ELIXIR_PROJECTION"
    PROTOCOL_LAW = "PROTOCOL_LAW"
    COMPOSITION_POLICY = "COMPOSITION_POLICY"
    RECEIPT_PROFILE = "RECEIPT_PROFILE"
    WORK_GRAPH = "WORK_GRAPH"


_DEFAULT_OWNER = {
    PromotionKind.EXPERIMENT: CapabilityOwner.AUTOFDE_LAB,
    PromotionKind.REVERSE_COMPILER_PRIMITIVE: CapabilityOwner.GGEN_CREATE,
    PromotionKind.REUSABLE_PACK: CapabilityOwner.GGEN_MARKETPLACE,
    PromotionKind.ELIXIR_PROJECTION: CapabilityOwner.GGEN_IGNITER,
    PromotionKind.PROTOCOL_LAW: CapabilityOwner.ENGINEERING_STANDARDS,
    PromotionKind.COMPOSITION_POLICY: CapabilityOwner.GGEN_ECOSYSTEM,
    PromotionKind.RECEIPT_PROFILE: CapabilityOwner.AFFIDAVIT,
    PromotionKind.WORK_GRAPH: CapabilityOwner.XAAS,
}


@dataclass(frozen=True, slots=True)
class PromotionCandidate:
    kind: PromotionKind
    owner: CapabilityOwner
    source_evidence_ids: tuple[str, ...]
    artifact_identity: str
    verifier_receipt_ids: tuple[str, ...]
    standing: str = "CANDIDATE"
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if not self.artifact_identity.strip():
            raise ValueError("artifact_identity must be non-empty")
        if not self.source_evidence_ids:
            raise ValueError("promotion requires source evidence")
        if self.standing != "CANDIDATE" or self.authority != "NONE":
            raise ValueError("promotion output is candidate intent only")

    @property
    def candidate_id(self) -> str:
        return digest(self)


class PromotionRouter:
    def route(
        self,
        *,
        kind: PromotionKind,
        artifact_identity: str,
        source_evidence_ids: tuple[str, ...],
        verifier_receipt_ids: tuple[str, ...] = (),
    ) -> PromotionCandidate:
        return PromotionCandidate(
            kind=kind,
            owner=_DEFAULT_OWNER[kind],
            source_evidence_ids=tuple(sorted(set(source_evidence_ids))),
            artifact_identity=artifact_identity,
            verifier_receipt_ids=tuple(sorted(set(verifier_receipt_ids))),
        )
