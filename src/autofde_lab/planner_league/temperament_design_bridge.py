"""Bridge GymAct temperament design plans into Planner League policy ecologies.

The bridge keeps mission/distribution semantics in GymAct and planner semantics
in AutoFDE. It does not duplicate the design calculus and it does not execute
anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from gymact.policy_ecology import PolicyPopulation
from gymact.policy_ecology_rdf import population_digest
from gymact.temperament_engineering import (
    DesignEvaluation,
    TemperamentDesignPlan,
    apply_platform_heterogeneity,
    evaluate_design,
    manufacture_population,
)

from .core import PolicySpec
from .policy_ecology import ConditionedPolicy, PolicyEcology
from .policy_ecology_experiment import policy_identity


@dataclass(frozen=True, slots=True)
class DesignedPolicyEcology:
    policy: PolicySpec
    design: TemperamentDesignPlan
    ecology: PolicyEcology
    population_ref: str
    evaluation: DesignEvaluation
    member_count: int

    def __post_init__(self) -> None:
        if self.member_count < 1:
            raise ValueError("REFUSED:DESIGNED_ECOLOGY_REQUIRES_MEMBER")


@dataclass(frozen=True, slots=True)
class DesignBenchmarkPair:
    homogeneous: DesignedPolicyEcology
    engineered: DesignedPolicyEcology

    def __post_init__(self) -> None:
        if policy_identity(self.homogeneous.policy) != policy_identity(self.engineered.policy):
            raise ValueError("REFUSED:DESIGN_BENCHMARK_POLICY_MISMATCH")
        if self.homogeneous.population_ref == self.engineered.population_ref:
            raise ValueError("REFUSED:DESIGN_BENCHMARK_REQUIRES_DISTINCT_POPULATIONS")


def _policy_ref(policy: PolicySpec) -> str:
    return f"urn:autofde:policy:{policy_identity(policy)}"


def _to_policy_ecology(
    policy: PolicySpec,
    population: PolicyPopulation,
) -> PolicyEcology:
    return PolicyEcology(
        kind=population.kind,
        reaction_norm=population.reaction_norm,
        members=tuple(
            ConditionedPolicy(
                policy=policy,
                condition=member.phenotype.condition,
                weight=member.weight,
                evidence_refs=member.phenotype.evidence_refs,
            )
            for member in population.members
        ),
    )


def manufacture_designed_policy_ecology(
    policy: PolicySpec,
    design: TemperamentDesignPlan,
    *,
    member_count: int,
    apply_platform: bool = True,
) -> DesignedPolicyEcology:
    """Manufacture one Planner League ecology from the admitted GymAct design."""
    population = manufacture_population(
        design,
        policy_ref=_policy_ref(policy),
        member_count=member_count,
    )
    if apply_platform:
        population = apply_platform_heterogeneity(population, design)

    evaluation = evaluate_design(design, population)
    digest = population_digest(population)
    return DesignedPolicyEcology(
        policy=policy,
        design=design,
        ecology=_to_policy_ecology(policy, population),
        population_ref=f"urn:gymact:policy-population:{digest}",
        evaluation=evaluation,
        member_count=len(population.members),
    )


def manufacture_design_benchmark_pair(
    policy: PolicySpec,
    design: TemperamentDesignPlan,
    *,
    engineered_member_count: int,
    apply_platform: bool = True,
) -> DesignBenchmarkPair:
    """Build a one-member control and engineered arm from the same design."""
    if engineered_member_count < 2:
        raise ValueError("REFUSED:ENGINEERED_BENCHMARK_REQUIRES_MULTIPLE_MEMBERS")

    homogeneous = manufacture_designed_policy_ecology(
        policy,
        design,
        member_count=1,
        apply_platform=apply_platform,
    )
    engineered = manufacture_designed_policy_ecology(
        policy,
        design,
        member_count=engineered_member_count,
        apply_platform=apply_platform,
    )
    return DesignBenchmarkPair(
        homogeneous=homogeneous,
        engineered=engineered,
    )
