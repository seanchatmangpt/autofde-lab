"""Versioned bounded minimality calculus.

IEC never claims global program minimality. This module compares candidates
only when coverage, verifier obligations, and preservation fences are identical.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import digest


@dataclass(frozen=True, slots=True)
class CostVector:
    kernel_units: int
    generator_units: int
    residue_units: int
    repeated_reasoning_units: int
    failed_verifier_units: int
    version: str = "iec-cost/v1"
    residue_weight: int = 3
    reasoning_weight: int = 5
    failure_weight: int = 1000

    def __post_init__(self) -> None:
        values = (
            self.kernel_units,
            self.generator_units,
            self.residue_units,
            self.repeated_reasoning_units,
            self.failed_verifier_units,
        )
        if any(value < 0 for value in values):
            raise ValueError("cost units must be non-negative")

    @property
    def scalar(self) -> int:
        return (
            self.kernel_units
            + self.generator_units
            + self.residue_weight * self.residue_units
            + self.reasoning_weight * self.repeated_reasoning_units
            + self.failure_weight * self.failed_verifier_units
        )


@dataclass(frozen=True, slots=True)
class KernelCandidate:
    kernel_id: str
    covered_observation_ids: tuple[str, ...]
    verifier_set_ids: tuple[str, ...]
    preservation_fence_ids: tuple[str, ...]
    cost: CostVector

    @property
    def candidate_id(self) -> str:
        return digest(self)


def dominates(left: KernelCandidate, right: KernelCandidate) -> bool:
    """Return true only for comparable candidates with lower declared cost."""

    if set(left.covered_observation_ids) != set(right.covered_observation_ids):
        return False
    if set(left.verifier_set_ids) != set(right.verifier_set_ids):
        return False
    if set(left.preservation_fence_ids) != set(right.preservation_fence_ids):
        return False
    if left.cost.version != right.cost.version:
        return False
    return left.cost.scalar < right.cost.scalar
