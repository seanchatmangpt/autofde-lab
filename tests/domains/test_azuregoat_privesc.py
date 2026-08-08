# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-school test for
autofde_lab.hub.domain.azuregoat_privesc.AzureGoatPrivilegeEscalation.

Exercises the real domain (the ten documented steps transcribed from
AzureGoat's ``attack-manuals/module-1/05-Privilege Escalation.md``, no
mocked domain internals) against the real, already-registered Astar
solver's ``solve()``. Assertions are on real final state (attacker holds
the Owner role) and the real returned plan - no mocking of the domain or
solver under test.
"""

from __future__ import annotations

from autofde_lab.hub.domain.azuregoat_privesc import AzureGoatPrivilegeEscalation
from autofde_lab.hub.domain.azuregoat_privesc.azuregoat_privesc import (
    ATTACK_STEPS,
    GOAL_FACT,
)
from autofde_lab.hub.solver.astar import Astar


def test_attack_steps_are_the_documented_azuregoat_manual_chain():
    """The transcribed steps must form a real, satisfiable precondition chain
    (each step's preconditions are establishable by some earlier step), and
    must end with the manual's own stated objective."""
    assert len(ATTACK_STEPS) == 10
    assert ATTACK_STEPS[0].preconditions == frozenset()
    assert ATTACK_STEPS[-1].establishes == GOAL_FACT

    established_so_far: set[str] = set()
    for step in ATTACK_STEPS:
        assert step.preconditions <= established_so_far, (
            f"step {step.id!r} ({step.manual_step}) requires "
            f"{step.preconditions - established_so_far} before it is reachable "
            "in the documented order"
        )
        established_so_far.add(step.establishes)


def test_astar_solves_azuregoat_privilege_escalation_to_owner_role():
    """Real domain, real Astar solver, real solve() call, real final state:
    the attacker reaches has_owner_role_on_resource_group."""
    domain_factory = lambda: AzureGoatPrivilegeEscalation()
    domain = domain_factory()

    initial_state = domain.get_initial_state()
    assert initial_state.facts == frozenset()
    assert not domain.is_goal(initial_state)

    with Astar(domain_factory=domain_factory) as solver:
        solver.solve()

        state = initial_state
        applied_actions = []
        for _ in range(len(ATTACK_STEPS) + 1):
            if domain.is_goal(state):
                break
            action = solver.get_next_action(state)
            state = domain.get_next_state(state, action)
            applied_actions.append(action)

        # Real goal state reached: attacker now holds the Owner role.
        assert domain.is_goal(state)
        assert GOAL_FACT in state.facts

        # Every documented step was taken exactly once, in a precondition-valid
        # order (no repeats, no omissions, no skipped prerequisites).
        assert set(applied_actions) == {s.id for s in ATTACK_STEPS}
        assert len(applied_actions) == 10
        assert applied_actions[0] == "ssh_login_vm"
        assert applied_actions[-1] == "confirm_owner_role"

        plan = solver.get_plan(initial_state)
        assert len(plan) == 10
        total_cost = sum(value.cost for _, _, value in plan)
        assert total_cost == 10.0
