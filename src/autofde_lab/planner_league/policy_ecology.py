"""Planner-league projection of GymAct policy ecology.

A planner policy remains Planner x Parameters x Objective x ObservationProjection
x ActionProjection. This layer adds a behavioral condition and a population
weight without adding authority. Execution authority remains external to the
planner league and is still enforced only by the downstream BRCE path.
"""

from __future__ import annotations

from dataclasses import dataclass

from gymact.policy_ecology import (
    DEFAULT_TEMPERAMENT_AXES,
    ConditionAxis,
    PolicyPhenotype,
    PolicyPopulation,
    PopulationDiversity,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
    WeightedPhenotype,
    condition_population,
    population_diversity,
)

from .core import PolicySpec


@dataclass(frozen=True, slots=True)
class ConditionedPolicy:
    policy: PolicySpec
    condition: StrategicCondition = StrategicCondition()
    weight: float = 1.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.weight <= 0.0:
            raise ValueError("REFUSED:POLICY_ECOLOGY_WEIGHT_MUST_BE_POSITIVE")

    @property
    def policy_ref(self) -> str:
        p = self.policy
        return (
            "urn:autofde:policy:"
            f"{p.planner_id}:{p.objective_id}:{p.observation_projection_id}:"
            f"{p.action_projection_id}:{p.budget_id}"
        )


@dataclass(frozen=True, slots=True)
class PolicyEcology:
    kind: PopulationKind
    members: tuple[ConditionedPolicy, ...]
    reaction_norm: ReactionNorm | None = None

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("REFUSED:POLICY_ECOLOGY_REQUIRES_MEMBER")
        if self.kind is PopulationKind.HOMOGENEOUS and len(self.members) != 1:
            raise ValueError("REFUSED:HOMOGENEOUS_POPULATION_REQUIRES_ONE_PHENOTYPE")
        if self.kind is PopulationKind.ADAPTIVE and self.reaction_norm is None:
            raise ValueError("REFUSED:ADAPTIVE_POPULATION_REQUIRES_REACTION_NORM")

    def as_gymact_population(self) -> PolicyPopulation:
        return PolicyPopulation(
            kind=self.kind,
            reaction_norm=self.reaction_norm,
            members=tuple(
                WeightedPhenotype(
                    phenotype=PolicyPhenotype(
                        policy_ref=member.policy_ref,
                        condition=member.condition,
                        evidence_refs=member.evidence_refs,
                    ),
                    weight=member.weight,
                )
                for member in self.members
            ),
        )

    def diversity(self) -> PopulationDiversity:
        return population_diversity(self.as_gymact_population())

    def condition(
        self,
        *,
        cue: float,
        axes: tuple[ConditionAxis, ...] = DEFAULT_TEMPERAMENT_AXES,
    ) -> "PolicyEcology":
        conditioned = condition_population(
            self.as_gymact_population(),
            cue=cue,
            axes=axes,
        )
        return PolicyEcology(
            kind=self.kind,
            reaction_norm=self.reaction_norm,
            members=tuple(
                ConditionedPolicy(
                    policy=source.policy,
                    condition=target.phenotype.condition,
                    weight=target.weight,
                    evidence_refs=target.phenotype.evidence_refs,
                )
                for source, target in zip(self.members, conditioned.members, strict=True)
            ),
        )

    def as_gymact_candidate(self) -> dict[str, object]:
        diversity = self.diversity()
        return {
            "schema_version": 1,
            "experiment_kind": "policy_ecology",
            "population_kind": self.kind.value,
            "authority_semantics": {
                "candidate_only": True,
                "temperament_has_authority": False,
                "execution_authority": "external_brce_only",
            },
            "diversity": {
                "disparity": diversity.disparity,
                "complexity": diversity.complexity,
            },
            "members": [
                {
                    "policy_ref": member.policy_ref,
                    "planner_id": member.policy.planner_id,
                    "objective_id": member.policy.objective_id,
                    "observation_projection_id": member.policy.observation_projection_id,
                    "action_projection_id": member.policy.action_projection_id,
                    "budget_id": member.policy.budget_id,
                    "parameters": dict(member.policy.parameters),
                    "condition": member.condition.as_dict(),
                    "weight": member.weight,
                    "evidence_refs": list(member.evidence_refs),
                }
                for member in self.members
            ],
        }
