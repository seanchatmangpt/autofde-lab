# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for the base `MCTS` C++-backed solver (registered entry
point "MCTS", distinct from its `UCT` subclass which is already exercised in
`tests/solvers/cpp/test_cpp_solvers.py`). `MCTS` itself -- with a custom
heuristic and the `RANDOM` rollout policy -- was genuinely untested before
this file: neither `tests/solvers/cpp/test_cpp_solvers.py` nor
`tests/solvers/python/test_python_solvers.py` construct it.

Fixture and domain shape are copied verbatim (not re-derived) from the
`GridDomain` in `tests/solvers/cpp/test_cpp_solvers.py`, which is itself the
nearest working sibling for a `DeterministicPlanningDomain` exercised by a
tree-search solver.

No mocks: a real `GridDomain` instance and the real registered `MCTS` solver
class (backed by the real compiled `_MCTSSolver_` C++ extension) are
exercised end to end; assertions are on the solver's real returned plan/cost,
not on any interaction.
"""

from __future__ import annotations

from enum import Enum
from math import sqrt
from typing import NamedTuple, Optional

from autofde_lab import DeterministicPlanningDomain, ImplicitSpace, Space, Value
from autofde_lab.builders.domain import UnrestrictedActions
from autofde_lab.hub.space.gym import EnumSpace, MultiDiscreteSpace
from autofde_lab.utils import load_registered_solver


class State(NamedTuple):
    x: int
    y: int
    s: int  # step => to make the domain cycle-free for algorithms like AO*


class Action(Enum):
    up = 0
    down = 1
    left = 2
    right = 3


class D(DeterministicPlanningDomain, UnrestrictedActions):
    T_state = State
    T_observation = T_state
    T_event = Action
    T_value = float
    T_predicate = bool
    T_info = None


class GridDomain(D):
    def __init__(self, num_cols=5, num_rows=5):
        self.num_cols = num_cols
        self.num_rows = num_rows

    def _get_next_state(
        self,
        memory: D.T_memory[D.T_state],
        action: D.T_agent[D.T_concurrency[D.T_event]],
    ) -> D.T_state:
        if action == Action.left:
            next_state = State(max(memory.x - 1, 0), memory.y, memory.s + 1)
        if action == Action.right:
            next_state = State(
                min(memory.x + 1, self.num_cols - 1), memory.y, memory.s + 1
            )
        if action == Action.up:
            next_state = State(memory.x, max(memory.y - 1, 0), memory.s + 1)
        if action == Action.down:
            next_state = State(
                memory.x, min(memory.y + 1, self.num_rows - 1), memory.s + 1
            )

        return next_state

    def _get_transition_value(
        self,
        memory: D.T_memory[D.T_state],
        action: D.T_agent[D.T_concurrency[D.T_event]],
        next_state: Optional[D.T_state] = None,
    ) -> D.T_agent[Value[D.T_value]]:
        if next_state.x == memory.x and next_state.y == memory.y:
            cost = 2  # big penalty when hitting a wall
        else:
            cost = abs(next_state.x - memory.x) + abs(next_state.y - memory.y)

        return Value(cost=cost)

    def _is_terminal(self, state: D.T_state) -> D.T_agent[D.T_predicate]:
        return self._is_goal(state) or state.s >= 49

    def _get_action_space_(self) -> D.T_agent[Space[D.T_event]]:
        return EnumSpace(Action)

    def _get_goals_(self) -> D.T_agent[Space[D.T_observation]]:
        return ImplicitSpace(
            lambda state: state.x == (self.num_cols - 1)
            and state.y == (self.num_rows - 1)
        )

    def _get_initial_state_(self) -> D.T_state:
        return State(x=0, y=0, s=0)

    def _get_observation_space_(self) -> D.T_agent[Space[D.T_observation]]:
        return MultiDiscreteSpace(
            nvec=[self.num_cols, self.num_rows, 50], element_class=State
        )


def test_mcts_solves_grid_domain_and_returns_real_plan():
    """Constructs a real GridDomain and runs the real registered MCTS
    solver (not its UCT subclass) with a real heuristic, asserting on the
    real greedy rollout's returned plan and total cost -- no mock."""
    solver_type = load_registered_solver("MCTS")
    assert solver_type is not None, "MCTS entry point failed to load"

    dom = GridDomain()
    assert solver_type.check_domain(dom)

    with solver_type(
        domain_factory=GridDomain,
        time_budget=2000,
        rollout_budget=200,
        max_depth=15,
        heuristic=lambda d, s: (
            Value(cost=sqrt((d.num_cols - 1 - s.x) ** 2 + (d.num_rows - 1 - s.y) ** 2)),
            1,
        ),
        continuous_planning=True,
        verbose=False,
    ) as solver:
        solver.solve()

        observation = dom.reset()
        plan = []
        cost = 0.0
        nb_steps = 0
        while (not dom.is_goal(observation)) and nb_steps < 30:
            action = solver.sample_action(observation)
            plan.append(action)
            outcome = dom.step(action)
            cost += outcome.value.cost
            observation = outcome.observation
            nb_steps += 1

    # Real, observed consequence: MCTS reached the goal from (0,0) to
    # (num_cols-1, num_rows-1) with a real, non-empty plan and finite cost.
    assert dom.is_goal(observation)
    assert len(plan) > 0
    assert cost >= 0.0
    assert all(isinstance(a, Action) for a in plan)
