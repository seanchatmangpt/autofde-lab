#!/usr/bin/env python3
"""Real native (C++ _AStarSolver_) plan over the beam4pm staged-boolean domain.

Runs under the repo's .venv python (the only interpreter carrying the
__autofde_lab_hub_cpp extension). stdin: one JSON object
    {"stages": {STAGE: bool}, "goal": {STAGE: bool},
     "actions": [{"name", "preconditions": {..}, "postconditions": {..}}, ...]}
stdout: one JSON line
    {"implementation": "native", "extension_path": ..., "plan": [action names],
     "cost": float, "goal_reached": bool, "expanded_steps": int}
Exit 1 (and a JSON line with "error") if the extension is missing or no plan.
No Python fallback exists in this file by design (Task H: no fallback).
"""
from __future__ import annotations

import json
import sys
from enum import Enum
from typing import NamedTuple, Optional

import autofde_lab.hub.__autofde_lab_hub_cpp as hub_cpp  # hard requirement, no fallback
from autofde_lab import DeterministicPlanningDomain, ImplicitSpace, Value
from autofde_lab.builders.domain import UnrestrictedActions
from autofde_lab.hub.solver.astar import Astar
from autofde_lab.hub.space.gym import EnumSpace, MultiDiscreteSpace


class State(NamedTuple):
    bits: int  # bitmask over STAGES order
    s: int  # step counter (bounds the search)


class D(DeterministicPlanningDomain, UnrestrictedActions):
    T_state = State
    T_observation = T_state
    T_event = Enum
    T_value = float
    T_predicate = bool
    T_info = None


def build_domain(spec: dict):
    stages = list(spec["stages"].keys())
    idx = {s: i for i, s in enumerate(stages)}
    acts = spec["actions"]
    ActionEnum = Enum("ActionEnum", {f"a{i}": i for i in range(len(acts))})  # type: ignore[misc]
    goal_mask = sum(1 << idx[k] for k, v in spec["goal"].items() if v)
    max_steps = int(spec.get("max_steps", 40))  # optional search bound; default unchanged
    init_bits = sum(1 << idx[k] for k, v in spec["stages"].items() if v)
    # Any action whose preconditions are unmet is a self-loop with a penalty
    # cost (the search then never prefers it); this keeps UnrestrictedActions.
    pre = []
    post_set = []
    post_clr = []
    for a in acts:
        pre.append((sum(1 << idx[k] for k, v in a["preconditions"].items() if v),
                    sum(1 << idx[k] for k, v in a["preconditions"].items() if not v)))
        post_set.append(sum(1 << idx[k] for k, v in a["postconditions"].items() if v))
        post_clr.append(sum(1 << idx[k] for k, v in a["postconditions"].items() if not v))

    class StagedDomain(D):
        T_event = ActionEnum

        def _get_next_state(self, memory: State, action):
            i = action.value
            need_on, need_off = pre[i]
            if (memory.bits & need_on) != need_on or (memory.bits & need_off) != 0:
                return State(memory.bits, memory.s + 1)
            return State((memory.bits | post_set[i]) & ~post_clr[i], memory.s + 1)

        def _get_transition_value(self, memory: State, action, next_state: Optional[State] = None):
            if next_state.bits == memory.bits:
                return Value(cost=50.0)  # inapplicable / no-op
            return Value(cost=1.0)

        def _is_terminal(self, state: State):
            return self._is_goal(state) or state.s >= max_steps

        def _get_action_space_(self):
            return EnumSpace(ActionEnum)

        def _get_goals_(self):
            return ImplicitSpace(lambda st: (st.bits & goal_mask) == goal_mask)

        def _get_initial_state_(self):
            return State(bits=init_bits, s=0)

        def _get_observation_space_(self):
            return MultiDiscreteSpace([1 << len(stages), max_steps + 1])

    def heuristic(d, st: State):
        return Value(cost=float(bin(goal_mask & ~st.bits).count("1")))

    return StagedDomain, ActionEnum, heuristic, [a["name"] for a in acts], max_steps


def main() -> int:
    spec = json.load(sys.stdin)
    StagedDomain, ActionEnum, heuristic, names, max_steps = build_domain(spec)
    dom = StagedDomain()
    plan: list[str] = []
    cost = 0.0
    with Astar(domain_factory=StagedDomain, heuristic=heuristic, verbose=False) as slv:
        slv.solve()
        obs, steps = dom.reset(), 0
        while not dom.is_goal(obs) and steps < max_steps:
            a = slv.sample_action(obs, domain=dom)
            out = dom.step(a)
            if out.observation.bits == obs.bits:
                break  # solver has nothing useful: stop rather than loop
            plan.append(names[a.value])
            cost += out.value.cost
            obs = out.observation
            steps += 1
    reached = bool(dom.is_goal(obs))
    print(json.dumps({
        "implementation": "native",
        "solver": "Astar(native _AStarSolver_)",
        "extension_path": hub_cpp.__file__,
        "plan": plan,
        "cost": cost,
        "goal_reached": reached,
        "expanded_steps": steps,
    }, sort_keys=True))
    return 0 if reached else 1


if __name__ == "__main__":
    sys.exit(main())
