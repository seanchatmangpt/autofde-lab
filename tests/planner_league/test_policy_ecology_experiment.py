from __future__ import annotations

import pytest
from gymact.policy_ecology import PopulationKind, ReactionNorm, StrategicCondition

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.policy_ecology import ConditionedPolicy, PolicyEcology
from autofde_lab.planner_league.policy_ecology_experiment import (
    HeterogeneityTrial,
    ObservedEcologyOutcome,
    manufacture_ecology_schedule,
    policy_identity,
    summarize_heterogeneity,
)


def ecology(
    planner_id: str,
    values: tuple[float, ...],
    *,
    role_id: str,
    adaptive: bool = False,
) -> PolicyEcology:
    return PolicyEcology(
        kind=PopulationKind.ADAPTIVE if adaptive else PopulationKind.ENGINEERED,
        reaction_norm=(
            ReactionNorm(slopes=(("exploration", 0.25),)) if adaptive else None
        ),
        members=tuple(
            ConditionedPolicy(
                policy=PolicySpec.for_role(planner_id, role_id),
                condition=StrategicCondition(values=(("exploration", value),)),
                weight=float(index + 1),
            )
            for index, value in enumerate(values)
        ),
    )


def test_policy_identity_includes_real_parameterization() -> None:
    a = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": "zero"},
    )
    b = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": "manhattan"},
    )
    assert policy_identity(a) != policy_identity(b)
    assert policy_identity(a) == policy_identity(a)


def test_policy_identity_handles_callable_parameters_without_memory_addresses() -> None:
    def heuristic(_domain, _state):
        return 0

    spec = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": heuristic},
    )
    identity = policy_identity(spec)
    assert len(identity) == 64
    assert identity == policy_identity(spec)


def test_conditioned_cross_play_exposes_full_cardinality_and_truncation() -> None:
    schedule = manufacture_ecology_schedule(
        ecology("Astar", (0.0, 0.5, 1.0), role_id="blue_defender"),
        ecology("MCTS", (0.1, 0.9), role_id="red_disturbance"),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        max_matches=4,
    )
    assert schedule.total_cardinality == 6
    assert len(schedule.matches) == 4
    assert schedule.truncated


def test_conditioned_cross_play_is_candidate_only_and_authority_free() -> None:
    schedule = manufacture_ecology_schedule(
        ecology("Astar", (0.2,), role_id="blue_defender"),
        ecology("MCTS", (0.8,), role_id="red_disturbance"),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
    )
    payload = schedule.matches[0].as_gymact_candidate()
    assert payload["authority_semantics"] == {
        "candidate_only": True,
        "phenotype_has_authority": False,
        "execution_authority": "external_brce_only",
    }
    assert "authority" not in payload["players"]["left"]
    assert "authority" not in payload["players"]["right"]


def test_cue_conditions_adaptive_ecology_before_schedule_manufacture() -> None:
    schedule = manufacture_ecology_schedule(
        ecology("Astar", (0.25,), role_id="blue_defender", adaptive=True),
        ecology("MCTS", (0.5,), role_id="red_disturbance", adaptive=True),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        cue=1.0,
    )
    match = schedule.matches[0]
    assert dict(match.left.condition)["exploration"] == pytest.approx(0.5)
    assert dict(match.right.condition)["exploration"] == pytest.approx(0.75)
    assert match.cue == 1.0


def test_ecology_payoff_requires_external_execution_receipt() -> None:
    match = manufacture_ecology_schedule(
        ecology("Astar", (0.2,), role_id="blue_defender"),
        ecology("MCTS", (0.8,), role_id="red_disturbance"),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
    ).matches[0]

    with pytest.raises(ValueError, match="REFUSED:UNRECEIPTED_ECOLOGY_PAYOFF"):
        ObservedEcologyOutcome(
            match=match,
            left_score=1.0,
            right_score=-1.0,
            receipt_ids=(),
        )


def test_heterogeneity_evidence_measures_gain_after_engineering_cost() -> None:
    trials = (
        HeterogeneityTrial(
            mission_id="exploration",
            homogeneous_score=0.60,
            engineered_score=0.82,
            engineering_cost=0.05,
            receipt_ids=("receipt:1",),
            homogeneous_population_ref="pop:homogeneous:1",
            engineered_population_ref="pop:engineered:1",
        ),
        HeterogeneityTrial(
            mission_id="exploration",
            homogeneous_score=0.65,
            engineered_score=0.70,
            engineering_cost=0.08,
            receipt_ids=("receipt:2",),
            homogeneous_population_ref="pop:homogeneous:2",
            engineered_population_ref="pop:engineered:2",
        ),
    )
    evidence = summarize_heterogeneity(trials)
    assert evidence.trial_count == 2
    assert evidence.mean_gross_gain == pytest.approx(0.135)
    assert evidence.mean_net_gain == pytest.approx(0.07)
    assert evidence.positive_net_fraction == pytest.approx(0.5)


def test_heterogeneity_trial_refuses_same_population_as_both_arms() -> None:
    with pytest.raises(
        ValueError,
        match="REFUSED:HETEROGENEITY_TRIAL_REQUIRES_DISTINCT_POPULATIONS",
    ):
        HeterogeneityTrial(
            mission_id="m",
            homogeneous_score=1.0,
            engineered_score=1.0,
            engineering_cost=0.0,
            receipt_ids=("receipt:1",),
            homogeneous_population_ref="pop:same",
            engineered_population_ref="pop:same",
        )


def test_schedule_refuses_policy_bound_to_wrong_role() -> None:
    with pytest.raises(ValueError, match="REFUSED:ECOLOGY_POLICY_ROLE_MISMATCH:right"):
        manufacture_ecology_schedule(
            ecology("Astar", (0.2,), role_id="blue_defender"),
            ecology("MCTS", (0.8,), role_id="blue_defender"),
            world_id="cyber_incident",
            left_role_id="blue_defender",
            right_role_id="red_disturbance",
        )
