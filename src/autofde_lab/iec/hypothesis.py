"""Counterexample-guided hypothesis frontier for IEC."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .model import Counterexample, digest


@dataclass(frozen=True, slots=True)
class Hypothesis:
    covered_observation_ids: tuple[str, ...]
    excluded_observation_ids: tuple[str, ...]
    kernel_delta: Any
    generator_delta: Any
    required_residue: tuple[str, ...]
    predicted_consequences: tuple[str, ...]
    falsifier: str
    estimated_cost: float
    authority_requirements: tuple[str, ...] = ()
    counterexample_ids: tuple[str, ...] = ()
    generation: int = 0

    def __post_init__(self) -> None:
        if not self.covered_observation_ids:
            raise ValueError("hypothesis must cover at least one observation")
        if not self.falsifier.strip():
            raise ValueError("hypothesis requires a falsifier")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost must be non-negative")

    @property
    def hypothesis_id(self) -> str:
        return digest(self)

    @property
    def falsified(self) -> bool:
        return bool(self.counterexample_ids)


class HypothesisFrontier:
    """Preserve competing reversible explanations until evidence discriminates."""

    def __init__(self) -> None:
        self._hypotheses: dict[str, Hypothesis] = {}
        self._counterexamples: dict[str, Counterexample] = {}

    def add(self, hypothesis: Hypothesis) -> Hypothesis:
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def falsify(
        self,
        hypothesis_id: str,
        counterexample: Counterexample,
    ) -> Hypothesis:
        try:
            current = self._hypotheses[hypothesis_id]
        except KeyError as exc:
            raise KeyError(f"unknown hypothesis: {hypothesis_id}") from exc
        self._counterexamples[counterexample.counterexample_id] = counterexample
        updated = replace(
            current,
            counterexample_ids=tuple(
                sorted(
                    set(
                        current.counterexample_ids
                        + (counterexample.counterexample_id,)
                    )
                )
            ),
        )
        del self._hypotheses[hypothesis_id]
        self._hypotheses[updated.hypothesis_id] = updated
        return updated

    def refine(
        self,
        falsified_id: str,
        *,
        kernel_delta: Any,
        generator_delta: Any,
        required_residue: tuple[str, ...],
        predicted_consequences: tuple[str, ...],
        falsifier: str,
        estimated_cost: float,
    ) -> Hypothesis:
        try:
            prior = self._hypotheses[falsified_id]
        except KeyError as exc:
            raise KeyError(f"unknown hypothesis: {falsified_id}") from exc
        if not prior.falsified:
            raise ValueError("refinement requires a falsified hypothesis")
        if (
            kernel_delta == prior.kernel_delta
            and generator_delta == prior.generator_delta
            and required_residue == prior.required_residue
        ):
            raise ValueError(
                "unchanged failed hypothesis cannot be rerun without a new discriminating change"
            )
        child = Hypothesis(
            covered_observation_ids=prior.covered_observation_ids,
            excluded_observation_ids=prior.excluded_observation_ids,
            kernel_delta=kernel_delta,
            generator_delta=generator_delta,
            required_residue=required_residue,
            predicted_consequences=predicted_consequences,
            falsifier=falsifier,
            estimated_cost=estimated_cost,
            authority_requirements=prior.authority_requirements,
            counterexample_ids=(),
            generation=prior.generation + 1,
        )
        return self.add(child)

    def active(self) -> tuple[Hypothesis, ...]:
        return tuple(
            sorted(
                (h for h in self._hypotheses.values() if not h.falsified),
                key=lambda h: (
                    h.estimated_cost,
                    -len(h.covered_observation_ids),
                    h.hypothesis_id,
                ),
            )
        )

    def falsified(self) -> tuple[Hypothesis, ...]:
        return tuple(
            sorted(
                (h for h in self._hypotheses.values() if h.falsified),
                key=lambda h: h.hypothesis_id,
            )
        )

    def counterexamples(self) -> tuple[Counterexample, ...]:
        return tuple(
            self._counterexamples[key] for key in sorted(self._counterexamples)
        )
