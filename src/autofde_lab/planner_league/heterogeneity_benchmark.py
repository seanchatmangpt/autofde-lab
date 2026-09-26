"""Expected-payoff and paired heterogeneity benchmark manufacture.

A policy population's payoff is the expectation over its joint member
distribution, not an unweighted average of whichever phenotype matches happened
to execute. This module requires complete, receipted schedules before producing
population-level evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum

from .policy_ecology import PolicyEcology
from .policy_ecology_experiment import (
    EcologySchedule,
    HeterogeneityTrial,
    ObservedEcologyOutcome,
    manufacture_ecology_schedule,
)
from .temperament_design_bridge import DesignBenchmarkPair


@dataclass(frozen=True, slots=True)
class ExpectedPayoff:
    schedule_cardinality: int
    observation_count: int
    weighted_left_score: float
    weighted_right_score: float
    receipt_ids: tuple[str, ...]

    @property
    def weighted_margin(self) -> float:
        return self.weighted_left_score - self.weighted_right_score


def expected_payoff(
    schedule: EcologySchedule,
    outcomes: tuple[ObservedEcologyOutcome, ...],
) -> ExpectedPayoff:
    """Reduce a complete cross-product schedule to its joint-distribution payoff."""
    if schedule.truncated:
        raise ValueError("REFUSED:EXPECTED_PAYOFF_REQUIRES_COMPLETE_SCHEDULE")
    if not schedule.matches:
        raise ValueError("REFUSED:EXPECTED_PAYOFF_REQUIRES_MATCH")

    expected_ids = {match.identity_sha256 for match in schedule.matches}
    observed_by_id: dict[str, ObservedEcologyOutcome] = {}
    receipt_ids: list[str] = []
    for outcome in outcomes:
        match_id = outcome.match.identity_sha256
        if match_id not in expected_ids:
            raise ValueError(f"REFUSED:OUTCOME_OUTSIDE_SCHEDULE:{match_id}")
        if match_id in observed_by_id:
            raise ValueError(f"REFUSED:DUPLICATE_SCHEDULE_OUTCOME:{match_id}")
        observed_by_id[match_id] = outcome
        receipt_ids.extend(outcome.receipt_ids)

    missing = expected_ids.difference(observed_by_id)
    if missing:
        raise ValueError(
            "REFUSED:INCOMPLETE_SCHEDULE_EVIDENCE:"
            + ",".join(sorted(missing))
        )

    raw_weights = [
        match.left.weight * match.right.weight
        for match in schedule.matches
    ]
    total_weight = fsum(raw_weights)
    if total_weight <= 0.0:
        raise ValueError("REFUSED:NONPOSITIVE_JOINT_POPULATION_WEIGHT")

    left_terms: list[float] = []
    right_terms: list[float] = []
    for match, raw_weight in zip(schedule.matches, raw_weights, strict=True):
        normalized = raw_weight / total_weight
        outcome = observed_by_id[match.identity_sha256]
        left_terms.append(normalized * outcome.left_score)
        right_terms.append(normalized * outcome.right_score)

    return ExpectedPayoff(
        schedule_cardinality=len(schedule.matches),
        observation_count=len(outcomes),
        weighted_left_score=fsum(left_terms),
        weighted_right_score=fsum(right_terms),
        receipt_ids=tuple(dict.fromkeys(receipt_ids)),
    )


@dataclass(frozen=True, slots=True)
class HeterogeneityBenchmarkCell:
    cue: float
    homogeneous_schedule: EcologySchedule
    engineered_schedule: EcologySchedule

    def __post_init__(self) -> None:
        if self.homogeneous_schedule.truncated or self.engineered_schedule.truncated:
            raise ValueError("REFUSED:HETEROGENEITY_CELL_REQUIRES_COMPLETE_SCHEDULE")
        if any(match.cue != self.cue for match in self.homogeneous_schedule.matches):
            raise ValueError("REFUSED:HOMOGENEOUS_CUE_BINDING_MISMATCH")
        if any(match.cue != self.cue for match in self.engineered_schedule.matches):
            raise ValueError("REFUSED:ENGINEERED_CUE_BINDING_MISMATCH")


@dataclass(frozen=True, slots=True)
class HeterogeneityBenchmarkProgram:
    mission_id: str
    homogeneous_population_ref: str
    engineered_population_ref: str
    cells: tuple[HeterogeneityBenchmarkCell, ...]
    engineering_cost: float

    def __post_init__(self) -> None:
        if not self.cells:
            raise ValueError("REFUSED:HETEROGENEITY_PROGRAM_REQUIRES_CELL")
        if self.engineering_cost < 0.0:
            raise ValueError("REFUSED:NEGATIVE_HETEROGENEITY_COST")
        if self.homogeneous_population_ref == self.engineered_population_ref:
            raise ValueError("REFUSED:HETEROGENEITY_PROGRAM_REQUIRES_DISTINCT_POPULATIONS")
        cues = [cell.cue for cell in self.cells]
        if len(cues) != len(set(cues)):
            raise ValueError("REFUSED:DUPLICATE_HETEROGENEITY_PROGRAM_CUE")


def manufacture_heterogeneity_program(
    pair: DesignBenchmarkPair,
    opponent: PolicyEcology,
    *,
    world_id: str,
    left_role_id: str,
    right_role_id: str,
    cues: tuple[float, ...],
    engineering_cost: float,
) -> HeterogeneityBenchmarkProgram:
    """Manufacture matched control/engineered schedules for the same environment."""
    if not cues:
        raise ValueError("REFUSED:HETEROGENEITY_PROGRAM_REQUIRES_CUE")
    if len(cues) != len(set(cues)):
        raise ValueError("REFUSED:DUPLICATE_HETEROGENEITY_PROGRAM_CUE")
    if engineering_cost < 0.0:
        raise ValueError("REFUSED:NEGATIVE_HETEROGENEITY_COST")

    cells: list[HeterogeneityBenchmarkCell] = []
    for cue in cues:
        homogeneous = manufacture_ecology_schedule(
            pair.homogeneous.ecology,
            opponent,
            world_id=world_id,
            left_role_id=left_role_id,
            right_role_id=right_role_id,
            max_matches=(
                len(pair.homogeneous.ecology.members) * len(opponent.members)
            ),
            cue=cue,
        )
        engineered = manufacture_ecology_schedule(
            pair.engineered.ecology,
            opponent,
            world_id=world_id,
            left_role_id=left_role_id,
            right_role_id=right_role_id,
            max_matches=(
                len(pair.engineered.ecology.members) * len(opponent.members)
            ),
            cue=cue,
        )
        cells.append(
            HeterogeneityBenchmarkCell(
                cue=cue,
                homogeneous_schedule=homogeneous,
                engineered_schedule=engineered,
            )
        )

    return HeterogeneityBenchmarkProgram(
        mission_id=pair.engineered.design.mission_id,
        homogeneous_population_ref=pair.homogeneous.population_ref,
        engineered_population_ref=pair.engineered.population_ref,
        cells=tuple(cells),
        engineering_cost=engineering_cost,
    )


def complete_heterogeneity_trial(
    program: HeterogeneityBenchmarkProgram,
    *,
    cue: float,
    homogeneous_outcomes: tuple[ObservedEcologyOutcome, ...],
    engineered_outcomes: tuple[ObservedEcologyOutcome, ...],
) -> HeterogeneityTrial:
    """Admit one cue cell only after both population arms have complete receipts."""
    matches = tuple(cell for cell in program.cells if cell.cue == cue)
    if len(matches) != 1:
        raise ValueError(f"REFUSED:HETEROGENEITY_PROGRAM_CUE_NOT_FOUND:{cue}")
    cell = matches[0]

    homogeneous = expected_payoff(cell.homogeneous_schedule, homogeneous_outcomes)
    engineered = expected_payoff(cell.engineered_schedule, engineered_outcomes)

    return HeterogeneityTrial(
        mission_id=program.mission_id,
        homogeneous_score=homogeneous.weighted_left_score,
        engineered_score=engineered.weighted_left_score,
        engineering_cost=program.engineering_cost,
        receipt_ids=tuple(
            dict.fromkeys((*homogeneous.receipt_ids, *engineered.receipt_ids))
        ),
        homogeneous_population_ref=program.homogeneous_population_ref,
        engineered_population_ref=program.engineered_population_ref,
    )
