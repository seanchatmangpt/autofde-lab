from __future__ import annotations

import pytest
from gymact.policy_ecology import PopulationKind, ReactionNorm, StrategicCondition

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.policy_ecology import ConditionedPolicy, PolicyEcology
from autofde_lab.planner_league.policy_ecology_experiment import ObservedEcologyOutcome
from autofde_lab.planner_league.policy_ecology_sweep import (
    CueSweepSpec,
    build_cue_response_surface,
    manufacture_cue_sweep,
)


def adaptive_ecology(planner_id: str, role_id: str, baseline: float) -> PolicyEcology:
    return PolicyEcology(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(slopes=(("exploration", 0.25),)),
        members=(
            ConditionedPolicy(
                policy=PolicySpec.for_role(planner_id, role_id),
                condition=StrategicCondition(values=(("exploration", baseline),)),
                weight=1.0,
            ),
        ),
    )


def test_cue_sweep_manufactures_one_bounded_schedule_per_cue() -> None:
    sweep = manufacture_cue_sweep(
        adaptive_ecology("Astar", "blue_defender", 0.25),
        adaptive_ecology("MCTS", "red_disturbance", 0.5),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        spec=CueSweepSpec(cues=(-1.0, 0.0, 1.0), max_matches_per_cue=1),
    )
    assert len(sweep.schedules) == 3
    assert sweep.total_cardinality == 3
    assert sweep.scheduled_matches == 3
    assert not sweep.truncated
    assert [schedule.matches[0].cue for schedule in sweep.schedules] == [-1.0, 0.0, 1.0]


def test_duplicate_cue_is_refused() -> None:
    with pytest.raises(ValueError, match="REFUSED:DUPLICATE_CUE"):
        CueSweepSpec(cues=(0.0, 0.0))


def test_response_surface_requires_receipted_observed_outcomes() -> None:
    sweep = manufacture_cue_sweep(
        adaptive_ecology("Astar", "blue_defender", 0.25),
        adaptive_ecology("MCTS", "red_disturbance", 0.5),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
        spec=CueSweepSpec(cues=(0.0, 1.0)),
    )
    observations = (
        ObservedEcologyOutcome(
            match=sweep.schedules[0].matches[0],
            left_score=0.4,
            right_score=0.6,
            receipt_ids=("r:0",),
        ),
        ObservedEcologyOutcome(
            match=sweep.schedules[1].matches[0],
            left_score=0.9,
            right_score=0.2,
            receipt_ids=("r:1",),
        ),
    )
    surface = build_cue_response_surface(observations)
    assert [point.cue for point in surface.points] == [0.0, 1.0]
    assert surface.points[0].mean_margin == pytest.approx(-0.2)
    assert surface.points[1].mean_margin == pytest.approx(0.7)
    assert surface.max_abs_margin_slope == pytest.approx(0.9)


def test_response_surface_refuses_unconditioned_match() -> None:
    from autofde_lab.planner_league.policy_ecology_experiment import (
        manufacture_ecology_schedule,
    )

    schedule = manufacture_ecology_schedule(
        adaptive_ecology("Astar", "blue_defender", 0.25),
        adaptive_ecology("MCTS", "red_disturbance", 0.5),
        world_id="cyber_incident",
        left_role_id="blue_defender",
        right_role_id="red_disturbance",
    )
    observation = ObservedEcologyOutcome(
        match=schedule.matches[0],
        left_score=1.0,
        right_score=0.0,
        receipt_ids=("r",),
    )
    with pytest.raises(
        ValueError,
        match="REFUSED:CUE_RESPONSE_REQUIRES_CONDITIONED_MATCH",
    ):
        build_cue_response_surface((observation,))
