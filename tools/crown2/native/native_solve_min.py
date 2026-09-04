#!/usr/bin/env python3
"""Smallest real native solve through the hub: A* (C++ _AStarSolver_) on a 10x10 grid.

Domain is the same GridDomain shape as tests/solvers/cpp/test_cpp_solvers.py
(copied, not imported, so this script has no pytest dependency). Prints one
JSON line on stdout: extension path, plan length, cost, and the expected
optimum (18 moves, cost 18 for a 10x10 grid from (0,0) to (9,9)). Exit 0 only
if the native solver produced that optimal plan; no Python fallback exists in
this file — if the C++ extension is missing the import raises and exit is 1.
"""
from __future__ import annotations

import json
import sys
from enum import Enum
from math import sqrt
from typing import NamedTuple, Optional

import autofde_lab.hub.__autofde_lab_hub_cpp as hub_cpp  # hard requirement, no fallback
from autofde_lab import DeterministicPlanningDomain, ImplicitSpace, Space, Value
from autofde_lab.builders.domain import UnrestrictedActions
from autofde_lab.hub.solver.astar import Astar
from autofde_lab.hub.space.gym import EnumSpace, MultiDiscreteSpace


class State(NamedTuple):
    x: int
    y: int
    s: int


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
    def __init__(self, num_cols: int = 10, num_rows: int = 10) -> None:
        self.num_cols = num_cols
        self.num_rows = num_rows

    def _get_next_state(self, memory, action):
        if action == Action.left:
            return State(max(memory.x - 1, 0), memory.y, memory.s + 1)
        if action == Action.right:
            return State(min(memory.x + 1, self.num_cols - 1), memory.y, memory.s + 1)
        if action == Action.up:
            return State(memory.x, max(memory.y - 1, 0), memory.s + 1)
        return State(memory.x, min(memory.y + 1, self.num_rows - 1), memory.s + 1)

    def _get_transition_value(self, memory, action, next_state: Optional[State] = None):
        if next_state.x == memory.x and next_state.y == memory.y:
            return Value(cost=2)
        return Value(cost=abs(next_state.x - memory.x) + abs(next_state.y - memory.y))

    def _is_terminal(self, state):
        return self._is_goal(state) or state.s >= 100

    def _get_action_space_(self):
        return EnumSpace(Action)

    def _get_goals_(self):
        return ImplicitSpace(
            lambda st: st.x == (self.num_cols - 1) and st.y == (self.num_rows - 1)
        )

    def _get_initial_state_(self):
        return State(x=0, y=0, s=0)

    def _get_observation_space_(self):
        return MultiDiscreteSpace([self.num_cols, self.num_rows, 100])


def main() -> int:
    dom = GridDomain()
    with Astar(
        domain_factory=GridDomain,
        heuristic=lambda d, s: Value(
            cost=sqrt((d.num_cols - 1 - s.x) ** 2 + (d.num_rows - 1 - s.y) ** 2)
        ),
        verbose=False,
    ) as slv:
        slv.solve()
        plan, cost, obs, steps = [], 0.0, dom.reset(), 0
        while not dom.is_goal(obs) and steps < 20:
            a = slv.sample_action(obs, domain=dom)
            plan.append(a.name)
            out = dom.step(a)
            cost += out.value.cost
            obs = out.observation
            steps += 1
    ok = len(plan) == 18 and cost == 18
    print(
        json.dumps(
            {
                "solver": "Astar(native _AStarSolver_)",
                "extension_path": hub_cpp.__file__,
                "plan_len": len(plan),
                "cost": cost,
                "expected_plan_len": 18,
                "expected_cost": 18,
                "goal_reached": bool(dom.is_goal(obs)),
                "ok": ok,
            },
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
