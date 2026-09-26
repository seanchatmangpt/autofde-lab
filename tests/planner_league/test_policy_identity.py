from __future__ import annotations

import pytest

from autofde_lab.planner_league import PolicySpec
from autofde_lab.planner_league.policy_identity import (
    policy_identity,
    policy_identity_payload,
    policy_ref,
)


def test_policy_identity_separates_parameterizations_of_same_planner() -> None:
    zero = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": "zero"},
    )
    manhattan = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": "manhattan"},
    )
    assert policy_identity(zero) != policy_identity(manhattan)
    assert policy_ref(zero) != policy_ref(manhattan)


def test_policy_identity_separates_role_semantics() -> None:
    blue = PolicySpec.for_role("Astar", "blue_defender")
    red = PolicySpec.for_role("Astar", "red_disturbance")
    assert policy_identity(blue) != policy_identity(red)


def test_callable_identity_is_stable_and_address_free() -> None:
    offset = 3

    def heuristic(_domain, state):
        return state + offset

    spec = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"heuristic": heuristic},
    )
    first = policy_identity_payload(spec)
    second = policy_identity_payload(spec)
    assert first == second
    assert "0x" not in repr(first)
    assert policy_identity(spec) == policy_identity(spec)


def test_unstable_opaque_parameter_is_refused() -> None:
    class Opaque:
        pass

    spec = PolicySpec.for_role(
        "Astar",
        "plan_constructor",
        parameters={"opaque": Opaque()},
    )
    with pytest.raises(ValueError, match="REFUSED:UNSTABLE_POLICY_PARAMETER_IDENTITY"):
        policy_identity(spec)
