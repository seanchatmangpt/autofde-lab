"""Assemble bounded semantic-kernel proposals from admitted evidence.

Kernel proposals are CONSTRUCT artifacts. The assembler does not decide that a
proposal is minimal or equivalent; those claims require the cost and
translation-validation courts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .cost import CostVector, KernelCandidate
from .graph_ir import SemanticGraph
from .model import digest


@dataclass(frozen=True, slots=True)
class Residue:
    subject_id: str
    path: str
    reason: str
    generator_failure_id: str | None = None

    def __post_init__(self) -> None:
        if not self.subject_id.strip() or not self.path.strip() or not self.reason.strip():
            raise ValueError("residue requires subject, path, and reason")

    @property
    def residue_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class SemanticKernelProposal:
    graph: SemanticGraph
    covered_observation_ids: tuple[str, ...]
    generator_route_ids: tuple[str, ...]
    residue: tuple[Residue, ...]
    verifier_set_ids: tuple[str, ...]
    preservation_fence_ids: tuple[str, ...]
    repeated_reasoning_units: int = 0

    def __post_init__(self) -> None:
        if not self.covered_observation_ids:
            raise ValueError("kernel proposal requires observation coverage")
        if self.repeated_reasoning_units < 0:
            raise ValueError("repeated_reasoning_units must be non-negative")

    @property
    def proposal_id(self) -> str:
        return digest(self)

    @property
    def cost(self) -> CostVector:
        return CostVector(
            kernel_units=len(self.graph.nodes) + len(self.graph.edges),
            generator_units=len(self.generator_route_ids),
            residue_units=len(self.residue),
            repeated_reasoning_units=self.repeated_reasoning_units,
            failed_verifier_units=0,
        )

    def as_kernel_candidate(self) -> KernelCandidate:
        return KernelCandidate(
            kernel_id=self.proposal_id,
            covered_observation_ids=self.covered_observation_ids,
            verifier_set_ids=self.verifier_set_ids,
            preservation_fence_ids=self.preservation_fence_ids,
            cost=self.cost,
        )


class KernelAssembler:
    """Create normalized proposals while preserving explicit residue."""

    def assemble(
        self,
        *,
        graph: SemanticGraph,
        covered_observation_ids: Iterable[str],
        generator_route_ids: Iterable[str] = (),
        residue: Iterable[Residue] = (),
        verifier_set_ids: Iterable[str] = (),
        preservation_fence_ids: Iterable[str] = (),
        repeated_reasoning_units: int = 0,
    ) -> SemanticKernelProposal:
        return SemanticKernelProposal(
            graph=graph,
            covered_observation_ids=tuple(sorted(set(covered_observation_ids))),
            generator_route_ids=tuple(sorted(set(generator_route_ids))),
            residue=tuple(sorted(residue, key=lambda item: item.residue_id)),
            verifier_set_ids=tuple(sorted(set(verifier_set_ids))),
            preservation_fence_ids=tuple(sorted(set(preservation_fence_ids))),
            repeated_reasoning_units=repeated_reasoning_units,
        )
