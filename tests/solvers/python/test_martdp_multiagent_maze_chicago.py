# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style test for `MARTDP` (multi-agent real-time dynamic
programming, C++-backed) directly against a real `MultiAgent` +
`Simulation` + `Goals` domain.

Genuinely untested before this file: MARTDP is used in the repo only
wrapped inside the meta-solver `MAHD` in
`examples/maze_multiagent_mdp_multisolve.py` (an interactive script, never
executed headlessly or asserted on), never directly, and never in
`tests/`. This fixture is a deliberately shrunk (2 agents, tiny open grid,
no internal walls) version of that same example's `MultiAgentMaze` domain,
copied structurally rather than re-derived, so the solver can converge in a
bounded rollout budget suitable for a test.

No mocks: a real `MultiAgentMaze` instance and the real registered `MARTDP`
solver (backed by the real compiled `_MARTDPSolver_` C++ extension) are
exercised end to end. Assertions are on the real returned joint action and
the real joint utility value -- not on any interaction.
"""

from __future__ import annotations

import random as rd
from enum import Enum
from typing import NamedTuple, Optional

from autofde_lab.builders.domain.agent import MultiAgent
from autofde_lab.builders.domain.concurrency import Sequential
from autofde_lab.builders.domain.dynamics import Simulation
from autofde_lab.builders.domain.events import Actions
from autofde_lab.builders.domain.goals import Goals
from autofde_lab.builders.domain.initialization import DeterministicInitialized
from autofde_lab.builders.domain.memory import Markovian
from autofde_lab.builders.domain.observability import FullyObservable
from autofde_lab.builders.domain.value import PositiveCosts
from autofde_lab.core import SamplableSpace, Space, StrDict, TransitionOutcome, Value
from autofde_lab.domains import Domain
from autofde_lab.hub.space.gym import EnumSpace, ListSpace, MultiDiscreteSpace
from autofde_lab.utils import load_registered_solver

# A tiny 3x3 open grid (no internal walls) so a 2-agent joint search
# converges quickly under a small rollout budget.
TINY_MAZE = """
+-+-+-+
|     |
+     +
|     |
+     +
|     |
+-+-+-+
"""


class AgentState(NamedTuple):
    x: int
    y: int


class AgentAction(Enum):
    up = 0
    down = 1
    left = 2
    right = 3
    stay = 4


class HashableDict(dict):
    def __hash__(self):
        return hash(frozenset(self.items()))


class D(
    Domain,
    MultiAgent,
    Sequential,
    Simulation,
    Actions,
    DeterministicInitialized,
    Markovian,
    PositiveCosts,
    Goals,
    FullyObservable,
):
    T_state = StrDict[AgentState]
    T_observation = T_state
    T_event = StrDict[AgentAction]
    T_value = int
    T_predicate = StrDict[bool]
    T_info = None


class TinyMultiAgentMaze(D):
    """Two agents that must swap corners of a tiny open 3x3 grid."""

    def __init__(self):
        maze = []
        for line in TINY_MAZE.strip("\n").split("\n"):
            line = line.rstrip()
            row = [1 if c == " " else 0 for c in line]
            maze.append(row)
        self._maze = maze
        self._num_cols = len(maze[0])
        self._num_rows = len(maze)
        self._agents_starts = {
            "Agent #0": AgentState(x=0, y=0),
            "Agent #1": AgentState(x=self._num_cols - 1, y=self._num_rows - 1),
        }
        self._agents_goals = {
            "Agent #0": AgentState(x=self._num_cols - 1, y=self._num_rows - 1),
            "Agent #1": AgentState(x=0, y=0),
        }

    def get_agents(self):
        return {"Agent #0", "Agent #1"}

    def _get_initial_state_(self) -> D.T_state:
        return HashableDict(self._agents_starts)

    def _state_sample(
        self,
        memory: D.T_memory[D.T_state],
        action: D.T_agent[D.T_concurrency[D.T_event]],
    ) -> TransitionOutcome[
        D.T_state,
        D.T_agent[Value[D.T_value]],
        D.T_agent[D.T_predicate],
        D.T_agent[D.T_info],
    ]:
        next_state = {}
        transition_value = {}
        for agent, state in memory.items():
            if state == self._agents_goals[agent]:
                next_state[agent] = state
                transition_value[agent] = Value(cost=0)
                continue
            act = action[agent]
            nx, ny = state.x, state.y
            if act == AgentAction.left and state.x > 0:
                nx = state.x - 1
            elif act == AgentAction.right and state.x < self._num_cols - 1:
                nx = state.x + 1
            elif act == AgentAction.up and state.y > 0:
                ny = state.y - 1
            elif act == AgentAction.down and state.y < self._num_rows - 1:
                ny = state.y + 1
            next_state[agent] = AgentState(x=nx, y=ny)
            transition_value[agent] = Value(cost=1)
        return TransitionOutcome(
            state=HashableDict(next_state),
            value=transition_value,
            termination={a: False for a in memory},
            info=None,
        )

    def get_agent_applicable_actions(
        self,
        memory: D.T_memory[D.T_state],
        other_agents_actions: D.T_agent[D.T_concurrency[D.T_event]],
        agent: str,
    ) -> Space[D.T_event]:
        if memory[agent] == self._agents_goals[agent]:
            return ListSpace([AgentAction.stay])
        applicable_actions = [AgentAction.stay]
        state = memory[agent]
        if state.y > 0:
            applicable_actions.append(AgentAction.up)
        if state.y < self._num_rows - 1:
            applicable_actions.append(AgentAction.down)
        if state.x > 0:
            applicable_actions.append(AgentAction.left)
        if state.x < self._num_cols - 1:
            applicable_actions.append(AgentAction.right)
        return ListSpace(applicable_actions)

    class SamplableActionSpace(SamplableSpace):
        def __init__(self, domain, memory):
            self._domain = domain
            self._memory = memory

        def items(self):
            return [(a, EnumSpace(AgentAction)) for a in self._memory.keys()]

        def sample(self):
            agents_order = rd.sample(
                list(self._memory.keys()), k=len(self._memory.keys())
            )
            agents_actions = {}
            for agent in agents_order:
                agents_actions[agent] = self._domain.get_agent_applicable_actions(
                    self._memory, agents_actions, agent
                ).sample()
            return HashableDict(agents_actions)

    def _get_applicable_actions_from(
        self, memory: D.T_memory[D.T_state]
    ) -> D.T_agent[Space[D.T_event]]:
        return TinyMultiAgentMaze.SamplableActionSpace(domain=self, memory=memory)

    def _get_goals_(self) -> D.T_agent[Space[D.T_observation]]:
        return {agent: ListSpace([goal]) for agent, goal in self._agents_goals.items()}

    def _get_observation_space_(self) -> D.T_agent[Space[D.T_observation]]:
        return StrDict[MultiDiscreteSpace([self._num_cols, self._num_rows])]

    def _get_action_space_(self) -> D.T_agent[Space[D.T_event]]:
        return {a: EnumSpace(AgentAction) for a in self.get_agents()}


def test_martdp_solves_real_tiny_multiagent_maze_and_returns_a_real_joint_action():
    """Constructs a real 2-agent TinyMultiAgentMaze and runs the real
    registered MARTDP solver directly (not via the MAHD meta-solver),
    asserting on the real computed joint action and joint utility at the
    initial joint state -- no mock."""
    solver_type = load_registered_solver("MARTDP")
    assert solver_type is not None, "MARTDP entry point failed to load"

    domain_factory = TinyMultiAgentMaze
    dom = domain_factory()
    assert solver_type.check_domain(dom)

    with solver_type(
        domain_factory=domain_factory,
        heuristic=lambda d, s: (
            {
                a: Value(
                    cost=abs(d._agents_goals[a].x - s[a].x)
                    + abs(d._agents_goals[a].y - s[a].y)
                )
                for a in s
            },
            {a: None for a in s},
        ),
        time_budget=5000,
        rollout_budget=500,
        max_depth=20,
        residual_moving_average_window=10,
        action_choice_noise=0.1,
        dead_end_cost=1000,
        online_node_garbage=False,
        continuous_planning=True,
        verbose=False,
    ) as solver:
        solver.solve()

        initial_state = dom.get_initial_state()
        joint_action = solver.get_next_action(initial_state)
        utility = solver.get_utility(initial_state)

    # Real, observed consequence: MARTDP returned a legal joint action
    # (one action per agent) and a finite non-negative joint utility.
    assert set(joint_action.keys()) == {"Agent #0", "Agent #1"}
    for agent, act in joint_action.items():
        assert isinstance(act, AgentAction)
    assert utility is not None
    for agent, val in utility.items():
        assert val.cost >= 0.0
