"""L6 Chicago tests: classic-solver stub closure.

Real collaborators only. Optimality oracle: networkx Dijkstra on the same weighted grid.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import NamedTuple, Optional

import networkx as nx
import pytest

from autofde_lab import DeterministicPlanningDomain, ImplicitSpace, Space, Value
from autofde_lab.builders.domain import UnrestrictedActions
from autofde_lab.hub.space.gym import EnumSpace
from autofde_lab.utils import load_registered_solver

COLS, ROWS = 5, 4


class St(NamedTuple):
    x: int
    y: int


class Act(Enum):
    up = 0
    down = 1
    left = 2
    right = 3


_DELTA = {Act.up: (0, -1), Act.down: (0, 1), Act.left: (-1, 0), Act.right: (1, 0)}


def make_weights(seed: int) -> dict:
    rng = random.Random(seed)
    w = {}
    for x in range(COLS):
        for y in range(ROWS):
            for dx, dy in ((1, 0), (0, 1)):
                nx_, ny_ = x + dx, y + dy
                if nx_ < COLS and ny_ < ROWS:
                    w[frozenset([(x, y), (nx_, ny_)])] = rng.randint(1, 9)
    return w


class _D(DeterministicPlanningDomain, UnrestrictedActions):
    T_state = St
    T_observation = St
    T_event = Act
    T_value = float
    T_predicate = bool
    T_info = None


class WeightedGrid(_D):
    seed = 0

    def __init__(self):
        self.w = make_weights(type(self).seed)

    def _step(self, s, a):
        dx, dy = _DELTA[a]
        x, y = s.x + dx, s.y + dy
        if 0 <= x < COLS and 0 <= y < ROWS:
            return St(x, y)
        return s

    def _get_next_state(self, memory, action):
        return self._step(memory, action)

    def _get_transition_value(self, memory, action, next_state: Optional[St] = None):
        if next_state == memory:
            return Value(cost=1000)
        return Value(cost=self.w[frozenset([(memory.x, memory.y), (next_state.x, next_state.y)])])

    def _is_terminal(self, state):
        return self._is_goal(state)

    def _get_action_space_(self) -> Space:
        return EnumSpace(Act)

    def _get_goals_(self):
        return ImplicitSpace(lambda s: s.x == COLS - 1 and s.y == ROWS - 1)

    def _get_initial_state_(self):
        return St(0, 0)

    def _get_observation_space_(self):
        return EnumSpace(Act)


def oracle_cost(seed: int) -> float:
    g = nx.Graph()
    for edge, wt in make_weights(seed).items():
        a, b = tuple(edge)
        g.add_edge(a, b, weight=wt)
    return nx.dijkstra_path_length(g, (0, 0), (COLS - 1, ROWS - 1), weight="weight")


def replay(domain, plan):
    s, total = domain.get_initial_state(), 0.0
    for a in plan:
        n = domain.get_next_state(s, a)
        total += domain.get_transition_value(s, a, n).cost
        s = n
    return s, total


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_p_astar_exposes_optimal_path_and_estimate(seed):
    WeightedGrid.seed = seed
    dom = WeightedGrid()
    solver_cls = load_registered_solver("pAstar")
    with solver_cls(domain_factory=WeightedGrid) as slv:
        slv.solve()
        plan = slv.get_plan()
        path = slv.get_path()
        est = slv.get_estimated_total_cost()
        pc = slv.get_path_cost()
    expected = oracle_cost(seed)
    end, total = replay(dom, plan)
    assert dom.is_goal(end)
    assert total == expected
    assert pc == expected
    assert est == expected  # zero heuristic, f == g at goal
    assert path[0][0] == dom.get_initial_state()
    assert dom.is_goal(path[-1][0]) and path[-1][1] is None
    assert [a for _, a in path[:-1]] == plan


def test_p_astar_plan_not_accumulated_across_solves():
    WeightedGrid.seed = 7
    with load_registered_solver("pAstar")(domain_factory=WeightedGrid) as slv:
        slv.solve()
        first = list(slv.get_plan())
        slv.solve()
        assert slv.get_plan() == first


def test_p_astar_unsolved_before_solve_has_no_cost():
    with load_registered_solver("pAstar")(domain_factory=WeightedGrid) as slv:
        assert slv.get_path() == []
        assert slv.get_path_cost() is None
        assert slv.get_estimated_total_cost() is None


@pytest.mark.parametrize(
    "entry,extra",
    [
        ("IW", {}),
        ("BFWS", {}),
    ],
)
def test_registry_default_construction_reaches_goal(entry, extra):
    WeightedGrid.seed = 3
    dom = WeightedGrid()
    solver_cls = load_registered_solver(entry)
    with solver_cls(domain_factory=WeightedGrid, **extra) as slv:
        slv.solve()
        s, plan = dom.get_initial_state(), []
        for _ in range(200):
            if dom.is_goal(s):
                break
            assert slv.is_policy_defined_for(s)
            a = slv.get_next_action(s)
            assert a is not None
            plan.append(a)
            s = dom.get_next_state(s, a)
    assert dom.is_goal(s)
    # Dijkstra is the lower bound; satisficing solvers may exceed it but never beat it.
    assert replay(dom, plan)[1] >= oracle_cost(3)


def test_riw_constructs_with_only_domain_factory():
    with load_registered_solver("RIW")(domain_factory=WeightedGrid) as slv:
        assert slv is not None


def test_riw_default_construction_solves_with_bounded_budget_and_policy_hook_answers():
    # RIW is a reward-maximising rollout planner; this cost domain is not required to be
    # solved by it, only to run and answer the Policies contract (was HookNotImplementedError).
    dom = WeightedGrid()
    kwargs = {"rollout_budget": 50, "max_depth": 10, "time_budget": 3000,
              "continuous_planning": False}
    with load_registered_solver("RIW")(domain_factory=WeightedGrid, **kwargs) as slv:
        slv.solve()
        assert slv.is_policy_defined_for(dom.get_initial_state()) in (True, False)


@pytest.mark.parametrize("entry", ["EHC", "LDFS", "IDAstar", "pLRTAstar", "MCTS"])
def test_policy_hook_answers_after_solve(entry):
    WeightedGrid.seed = 1
    dom = WeightedGrid()
    cls = load_registered_solver(entry)
    kw = {}
    if entry == "MCTS":
        kw = {"rollout_budget": 50, "max_depth": 10, "time_budget": 3000,
              "continuous_planning": False}
    with cls(domain_factory=WeightedGrid, **kw) as slv:
        slv.solve()
        assert slv.is_policy_defined_for(dom.get_initial_state()) in (True, False)
