"""Inert semantic work-order projection for sJira/XaaS handoff.

A work order describes required work and evidence. It is never authority to
execute that work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import ClaimCeiling, Counterexample, Failure, digest
from .promotion import PromotionCandidate


class WorkKind(str, Enum):
    OBSERVE = "OBSERVE"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    MANUFACTURE = "MANUFACTURE"
    VERIFY = "VERIFY"
    PROMOTE = "PROMOTE"


@dataclass(frozen=True, slots=True)
class WorkOrder:
    repository: str
    kind: WorkKind
    title: str
    subject_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    acceptance: tuple[str, ...]
    falsifiers: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    claim_ceiling: ClaimCeiling = ClaimCeiling.STRUCTURAL_EQUIVALENCE_ONLY
    authority: str = "NONE"
    standing: str = "CANDIDATE"

    def __post_init__(self) -> None:
        if not self.repository.strip() or not self.title.strip():
            raise ValueError("work order requires repository and title")
        if not self.acceptance:
            raise ValueError("work order requires acceptance criteria")
        if not self.falsifiers:
            raise ValueError("work order requires at least one falsifier")
        if self.authority != "NONE" or self.standing != "CANDIDATE":
            raise ValueError("work orders are inert candidate intents only")

    @property
    def work_order_id(self) -> str:
        return digest(self)


class WorkOrderProjector:
    """Convert typed findings into owner-routed, evidence-bounded work."""

    def from_counterexample(
        self,
        *,
        repository: str,
        counterexample: Counterexample,
        dependencies: Iterable[str] = (),
    ) -> WorkOrder:
        return WorkOrder(
            repository=repository,
            kind=WorkKind.REPAIR,
            title=(
                f"Repair {counterexample.dimension.value} counterexample "
                f"{counterexample.counterexample_id[:20]}"
            ),
            subject_ids=(counterexample.hypothesis_id,),
            evidence_ids=tuple(sorted(set(counterexample.evidence_ids))),
            acceptance=(
                "counterexample is reproduced before repair",
                "repair changes the discriminating hypothesis or implementation",
                "same verifier passes at exact repaired subject",
                "counterexample remains as regression witness",
            ),
            falsifiers=(
                "same counterexample persists after claimed repair",
                "verifier is weakened to obtain pass",
            ),
            dependencies=tuple(sorted(set(dependencies))),
        )

    def from_failure(
        self,
        *,
        repository: str,
        failure: Failure,
        dependencies: Iterable[str] = (),
    ) -> WorkOrder:
        return WorkOrder(
            repository=repository,
            kind=WorkKind.DIAGNOSE,
            title=f"Resolve {failure.kind.value}",
            subject_ids=(failure.subject_id,) if failure.subject_id else (),
            evidence_ids=tuple(sorted(set(failure.evidence_ids))),
            acceptance=(
                "failed transition is reproduced or typed as transport-only",
                "root cause is narrowed to one boundary",
                "repair or explicit unsupported state is recorded",
            ),
            falsifiers=(
                "failure is hidden without changing the failed transition",
            ),
            dependencies=tuple(sorted(set(dependencies))),
        )

    def from_promotion(
        self,
        promotion: PromotionCandidate,
        *,
        dependencies: Iterable[str] = (),
    ) -> WorkOrder:
        return WorkOrder(
            repository=promotion.owner.value,
            kind=WorkKind.PROMOTE,
            title=f"Promote {promotion.kind.value}: {promotion.artifact_identity}",
            subject_ids=(promotion.artifact_identity,),
            evidence_ids=promotion.source_evidence_ids
            + promotion.verifier_receipt_ids,
            acceptance=(
                "owner repository doctrine is read",
                "artifact is represented in owner-native canonical form",
                "owner-native verification passes",
                "no generated projection is hand-edited",
            ),
            falsifiers=(
                "promotion requires ownership boundary violation",
                "owner-native verifier rejects artifact",
            ),
            dependencies=tuple(sorted(set(dependencies))),
        )
