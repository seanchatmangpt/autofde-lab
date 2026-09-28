from __future__ import annotations

import pytest
from gymact.temperament_engineering import (
    AxisTarget,
    ControlTopology,
    DesignMode,
    DistributionShape,
    MissionCriterion,
    TemperamentDesignPlan,
)

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.heterogeneity_benchmark import (
    complete_heterogeneity_trial,
    expected_payoff,
    manufacture_heterogeneity_program,
)
from autofde_lab.planner_league.policy_ecology import ConditionedPolicy, PolicyEcology
from autofde_lab.planner_league.policy_ecology_experiment import (
    ObservedEcologyOutcome,
    manufacture_ecology_schedule,
)
from autofde_lab.planner_league.temperament_design_bridge import (
    manufacture_design_benchmark_pair,
)
from gymact.policy_ecology import PopulationKind, StrategicCondition


def static_ecology(
    planner_id: str,
    role_id: str,
    values_and_weights: tuple[tuple[float, float], ...],
) -> PolicyEcology:
    return PolicyEcology(
        kind=(
            PopulationKind.HOMOGENEOUS
            if len(values_and_weights) == 1
            else PopulationKind.ENGINEERED
        ),
        members=tuple(
            ConditionedPolicy(
                policy=PolicySpec.for_role(planner_id, role_id),
                condition=StrategicCondition(values=(("exploration", value),)),
                weight=weight,
            )
            for value, weight in values_and_weights
        ),
    )


def design() -> TemperamentDesignPlan:
    return TemperamentDesignPlan(
        mission_id="mission:coverage",
        topology=ControlTopology.CENTRALIZED,
        mode=DesignMode.ONLINE_PLANNER_OUTPUT,
        criteria=(
            MissionCriterion(
                criterion_id="coverage",
                axis_weights=(("exploration", 1.0),),
            ),
        ),
        targets=(
            AxisTarget(
                axis_id="exploration",
                mean=0.5,
                spread=0.5,
                shape=DistributionShape.UNIFORM,
            ),
        ),
    )


def observed(schedule, scores, *, prefix="receipt"):
    return tuple(
        ObservedEcologyOutcome(
            match=match,
            left_score=left,
            right_score=right,
            receipt_ids=(f"{prefix}:{index}",),
        )
        for index, (match, (left, right)) in enumerate(
            zip(schedule.matches, scores, strict=True)
        )
    )


def test_expected_payoff_uses_joint_population_weights() -> None:
    schedule = manufacture_ecology_schedule(
        static_ecology("Astar", "blue_defender", ((0.0, 1.0), (1.0, 3.0))),
        static_ecology("MCTS", "red_disturbance", ((0.0, 1.0), (1.0, 1.0))),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        max_matches=4,
        cue=0.0,
    )
    payoff = expected_payoff(
        schedule,
        observed(
            schedule,
            (
                (0.0, 1.0),
                (0.0, 1.0),
                (1.0, 0.0),
                (1.0, 0.0),
            ),
        ),
    )
    assert payoff.weighted_left_score == pytest.approx(0.75)
    assert payoff.weighted_right_score == pytest.approx(0.25)
    assert payoff.weighted_margin == pytest.approx(0.5)


def test_expected_payoff_refuses_incomplete_or_extraneous_evidence() -> None:
    schedule = manufacture_ecology_schedule(
        static_ecology("Astar", "blue_defender", ((0.5, 1.0),)),
        static_ecology("MCTS", "red_disturbance", ((0.5, 1.0),)),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        cue=0.0,
    )
    with pytest.raises(ValueError, match="REFUSED:INCOMPLETE_SCHEDULE_EVIDENCE"):
        expected_payoff(schedule, ())


def test_program_pairs_same_world_roles_and_cues_for_control_and_engineered() -> None:
    pair = manufacture_design_benchmark_pair(
        PolicySpec.for_role("Astar", "blue_defender"),
        design(),
        engineered_member_count=4,
    )
    program = manufacture_heterogeneity_program(
        pair,
        static_ecology("MCTS", "red_disturbance", ((0.5, 1.0),)),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        cues=(-1.0, 0.0, 1.0),
        engineering_cost=0.05,
    )
    assert [cell.cue for cell in program.cells] == [-1.0, 0.0, 1.0]
    assert all(not cell.homogeneous_schedule.truncated for cell in program.cells)
    assert all(not cell.engineered_schedule.truncated for cell in program.cells)
    assert all(
        {match.world_id for match in cell.homogeneous_schedule.matches}
        == {"cyber_incident"}
        for cell in program.cells
    )


def test_complete_trial_requires_both_full_receipted_arms() -> None:
    pair = manufacture_design_benchmark_pair(
        PolicySpec.for_role("Astar", "blue_defender"),
        design(),
        engineered_member_count=4,
    )
    program = manufacture_heterogeneity_program(
        pair,
        static_ecology("MCTS", "red_disturbance", ((0.5, 1.0),)),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        cues=(0.0,),
        engineering_cost=0.05,
    )
    cell = program.cells[0]
    homogeneous = observed(
        cell.homogeneous_schedule,
        ((0.5, 0.5),),
        prefix="control",
    )
    engineered = observed(
        cell.engineered_schedule,
        ((0.2, 0.8), (0.4, 0.6), (0.8, 0.2), (1.0, 0.0)),
        prefix="engineered",
    )

    trial = complete_heterogeneity_trial(
        program,
        cue=0.0,
        homogeneous_outcomes=homogeneous,
        engineered_outcomes=engineered,
    )
    assert trial.homogeneous_score == pytest.approx(0.5)
    assert trial.engineered_score == pytest.approx(0.6)
    assert trial.gross_gain == pytest.approx(0.1)
    assert trial.net_gain == pytest.approx(0.05)
    assert len(trial.receipt_ids) == 5


def test_truncated_schedule_cannot_be_promoted_to_expected_payoff() -> None:
    schedule = manufacture_ecology_schedule(
        static_ecology("Astar", "blue_defender", ((0.0, 1.0), (1.0, 1.0))),
        static_ecology("MCTS", "red_disturbance", ((0.0, 1.0), (1.0, 1.0))),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        max_matches=1,
        cue=0.0,
    )
    assert schedule.truncated
    with pytest.raises(
        ValueError,
        match="REFUSED:EXPECTED_PAYOFF_REQUIRES_COMPLETE_SCHEDULE",
    ):
        expected_payoff(
            schedule,
            observed(schedule, ((1.0, 0.0),)),
        )


def test_same_receipt_cannot_prove_both_benchmark_arms() -> None:
    pair = manufacture_design_benchmark_pair(
        PolicySpec.for_role("Astar", "blue_defender"),
        design(),
        engineered_member_count=2,
    )
    program = manufacture_heterogeneity_program(
        pair,
        static_ecology("MCTS", "red_disturbance", ((0.5, 1.0),)),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        cues=(0.0,),
        engineering_cost=0.0,
    )
    cell = program.cells[0]
    control = observed(
        cell.homogeneous_schedule,
        ((0.5, 0.5),),
        prefix="shared",
    )
    engineered = tuple(
        ObservedEcologyOutcome(
            match=match,
            left_score=0.5,
            right_score=0.5,
            receipt_ids=("shared:0",) if index == 0 else (f"eng:{index}",),
        )
        for index, match in enumerate(cell.engineered_schedule.matches)
    )
    with pytest.raises(
        ValueError,
        match="REFUSED:HETEROGENEITY_ARM_RECEIPT_REUSE",
    ):
        complete_heterogeneity_trial(
            program,
            cue=0.0,
            homogeneous_outcomes=control,
            engineered_outcomes=engineered,
        )
