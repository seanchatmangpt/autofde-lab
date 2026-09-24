"""Descriptive IEC metrics. Metrics never grant standing."""

from __future__ import annotations

from dataclasses import dataclass


def _ratio(numerator: int, denominator: int) -> float:
    if numerator < 0 or denominator < 0:
        raise ValueError("metric counts must be non-negative")
    if denominator == 0:
        return 0.0
    return numerator / denominator


@dataclass(frozen=True, slots=True)
class IECMetrics:
    admitted_artifacts: int
    classified_artifacts: int
    recurring_transforms: int
    mechanized_transforms: int
    semantic_units: int
    irreducible_units: int
    active_hypotheses_tested: int
    hypotheses_falsified: int
    repeated_reasoning_classes: int
    retired_reasoning_classes: int

    @property
    def coverage(self) -> float:
        return _ratio(self.classified_artifacts, self.admitted_artifacts)

    @property
    def mechanization(self) -> float:
        return _ratio(self.mechanized_transforms, self.recurring_transforms)

    @property
    def residue(self) -> float:
        return _ratio(self.irreducible_units, self.semantic_units)

    @property
    def counterexample_yield(self) -> float:
        return _ratio(self.hypotheses_falsified, self.active_hypotheses_tested)

    @property
    def retirement(self) -> float:
        return _ratio(
            self.retired_reasoning_classes,
            self.repeated_reasoning_classes,
        )
