from __future__ import annotations

import pytest
from gymact.policy_ecology import (
    ConditionAxis,
    PopulationKind,
    ReactionNorm,
    StrategicCondition,
)

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.policy_ecology import (
    ConditionedPolicy,
    PolicyEcology,
)


def test_engineered_policy_ecology_preserves_policy_and_exposes_population_metrics() -> (
    None
):
    ecology = PolicyEcology(
        kind=PopulationKind.ENGINEERED,
        members=(
            ConditionedPolicy(
                policy=PolicySpec.for_role("Astar", "plan_constructor"),
                condition=StrategicCondition(values=(("exploration", 0.0),)),
            ),
            ConditionedPolicy(
                policy=PolicySpec.for_role("Astar", "plan_constructor"),
                condition=StrategicCondition(values=(("exploration", 1.0),)),
            ),
        ),
    )
    payload = ecology.as_gymact_candidate()
    assert payload["population_kind"] == "engineered"
    assert payload["diversity"] == pytest.approx({"disparity": 1.0, "complexity": 2.0})
    assert {member["planner_id"] for member in payload["members"]} == {"Astar"}


def test_adaptive_ecology_changes_condition_not_policy_or_authority() -> None:
    base = PolicySpec.for_role("MCTS", "blue_defender")
    ecology = PolicyEcology(
        kind=PopulationKind.ADAPTIVE,
        reaction_norm=ReactionNorm(slopes=(("initiative", 1.0),)),
        members=(
            ConditionedPolicy(
                policy=base,
                condition=StrategicCondition(values=(("initiative", 0.25),)),
                weight=4.0,
            ),
        ),
    )
    conditioned = ecology.condition(
        cue=1.0,
        axes=(ConditionAxis(axis_id="initiative", lower=0.0, upper=0.75),),
    )
    assert conditioned.members[0].policy is base
    assert conditioned.members[0].weight == 4.0
    assert conditioned.members[0].condition.as_dict() == {"initiative": 0.75}

    payload = conditioned.as_gymact_candidate()
    assert payload["authority_semantics"] == {
        "candidate_only": True,
        "temperament_has_authority": False,
        "execution_authority": "external_brce_only",
    }
    assert "authority" not in payload["members"][0]


def test_policy_ecology_refuses_authority_as_temperament_axis() -> None:
    with pytest.raises(ValueError, match="REFUSED:TEMPERAMENT_CANNOT_ENCODE_AUTHORITY"):
        StrategicCondition(values=(("authority", 1.0),))


def test_policy_ref_separates_same_planner_with_different_parameters() -> None:
    zero = ConditionedPolicy(
        policy=PolicySpec.for_role(
            "Astar",
            "plan_constructor",
            parameters={"heuristic": "zero"},
        )
    )
    manhattan = ConditionedPolicy(
        policy=PolicySpec.for_role(
            "Astar",
            "plan_constructor",
            parameters={"heuristic": "manhattan"},
        )
    )
    assert zero.policy_ref != manhattan.policy_ref
    assert zero.policy_ref.startswith("urn:autofde:policy:")
    assert manhattan.policy_ref.startswith("urn:autofde:policy:")
