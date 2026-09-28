from __future__ import annotations

import pytest
from gymact.policy_ecology import ReactionNorm
from gymact.temperament_engineering import (
    AxisTarget,
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
    PlatformTrait,
    TemperamentDesignPlan,
)

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.temperament_design_bridge import (
    manufacture_design_benchmark_pair,
    manufacture_designed_policy_ecology,
)


def design(
    *,
    adaptive: bool = False,
    platform: bool = False,
) -> TemperamentDesignPlan:
    return TemperamentDesignPlan(
        mission_id="mission:coverage",
        topology=ControlTopology.DECENTRALIZED,
        mode=DesignMode.OFFLINE_ANTICIPATORY,
        criteria=(
            MissionCriterion(
                criterion_id="coverage",
                axis_weights=(("exploration", 2.0), ("initiative", 1.0)),
            ),
        ),
        targets=(
            AxisTarget(
                axis_id="exploration",
                mean=0.5,
                spread=0.5,
                shape=DistributionShape.UNIFORM,
            ),
            AxisTarget(
                axis_id="initiative",
                mean=0.5,
                spread=0.25,
                shape=DistributionShape.BIMODAL,
            ),
        ),
        reaction_norm=(
            ReactionNorm(slopes=(("exploration", 0.25),)) if adaptive else None
        ),
        platform_traits=(
            (
                PlatformTrait(
                    trait_id="battery_margin",
                    value=-0.2,
                    axis_couplings=(("exploration", 0.5),),
                    evidence_refs=("urn:evidence:battery",),
                ),
            )
            if platform
            else ()
        ),
        evidence_refs=("https://arxiv.org/abs/2609.29423",),
    )


def test_bridge_preserves_exact_planner_policy_across_population_members() -> None:
    policy = PolicySpec.for_role(
        "Astar",
        "blue_defender",
        parameters={"heuristic": "manhattan"},
    )
    result = manufacture_designed_policy_ecology(
        policy,
        design(),
        member_count=5,
    )
    assert result.member_count == 5
    assert all(member.policy == policy for member in result.ecology.members)
    assert result.population_ref.startswith("urn:gymact:policy-population:")
    assert result.evaluation.diversity.complexity == pytest.approx(5.0)


def test_benchmark_pair_holds_policy_and_mean_targets_constant() -> None:
    policy = PolicySpec.for_role("Astar", "blue_defender")
    pair = manufacture_design_benchmark_pair(
        policy,
        design(),
        engineered_member_count=4,
    )

    assert pair.homogeneous.member_count == 1
    assert pair.engineered.member_count == 4
    assert pair.homogeneous.policy == pair.engineered.policy == policy
    assert pair.homogeneous.population_ref != pair.engineered.population_ref

    homogeneous_fit = {
        fit.axis_id: fit.observed_mean
        for fit in pair.homogeneous.evaluation.axis_fit
    }
    engineered_fit = {
        fit.axis_id: fit.observed_mean
        for fit in pair.engineered.evaluation.axis_fit
    }
    assert homogeneous_fit == pytest.approx(engineered_fit)


def test_adaptive_design_remains_adaptive_after_bridge() -> None:
    result = manufacture_designed_policy_ecology(
        PolicySpec.for_role("MCTS", "red_disturbance"),
        design(adaptive=True),
        member_count=3,
    )
    assert result.ecology.kind.value == "adaptive"
    assert result.ecology.reaction_norm is not None


def test_platform_coupling_changes_realized_distribution_and_carries_evidence() -> None:
    result = manufacture_designed_policy_ecology(
        PolicySpec.for_role("Astar", "blue_defender"),
        design(platform=True),
        member_count=3,
    )
    explorations = [
        member.condition.as_dict()["exploration"]
        for member in result.ecology.members
    ]
    assert explorations == pytest.approx([0.0, 0.4, 0.9])
    assert all(
        "urn:evidence:battery" in member.evidence_refs
        for member in result.ecology.members
    )


def test_benchmark_pair_refuses_non_heterogeneous_member_count() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:ENGINEERED_BENCHMARK_REQUIRES_MULTIPLE_MEMBERS",
    ):
        manufacture_design_benchmark_pair(
            PolicySpec.for_role("Astar", "blue_defender"),
            design(),
            engineered_member_count=1,
        )
