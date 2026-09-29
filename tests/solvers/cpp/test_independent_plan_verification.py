"""Independent verification of planner output on a problem whose optimum is known.

The solver is trusted for one thing only: producing actions. Whether the returned plan reaches
the goal, and what it costs, is re-derived here with independent arithmetic (a re-implementation
of the grid dynamics that shares no code with the domain under test), and compared with the known
optimum. A solver that misreports its own cost, or returns a plan that does not reach the goal,
cannot pass.

Scope: unit/integration checkpoint of the documented deterministic planners on one grid family.
It does not establish anything about other domains, or about stochastic/POMDP solvers.

Optimum: corner to corner on an N x N open grid costs 2*(N-1) (one per cell moved).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from autofde_lab import Value
from autofde_lab.utils import load_registered_solver

_spec = importlib.util.spec_from_file_location(
    "_grid_fixture", Path(__file__).with_name("test_lrtdp.py")
)
_grid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_grid)

N = 10
OPTIMUM = 2 * (N - 1)
MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def replay(actions):
    """Independent dynamics: returns (reached_goal, cost). A wall bump costs 2, a move costs 1."""
    x = y = cost = 0
    for action in actions:
        dx, dy = MOVES[action.name]
        nx, ny = min(max(x + dx, 0), N - 1), min(max(y + dy, 0), N - 1)
        cost += 2 if (nx, ny) == (x, y) else abs(nx - x) + abs(ny - y)
        x, y = nx, ny
    return (x, y) == (N - 1, N - 1), cost


def manhattan(_domain, state):
    return Value(cost=abs(N - 1 - state.x) + abs(N - 1 - state.y))  # admissible


OPTIMAL_PLANNERS = {
    "Astar": {"heuristic": manhattan},
    "AOstar": {"heuristic": manhattan, "discount": 1.0},
    "ILAOstar": {"heuristic": manhattan, "discount": 1.0, "epsilon": 0.001},
    "LRTDP": {
        "heuristic": manhattan,
        "use_labels": True,
        "discount": 1.0,
        "epsilon": 0.001,
    },
    "VI": {"discount": 1.0, "epsilon": 0.001},
    "PI": {"discount": 1.0, "epsilon": 0.001, "max_eval_sweeps": 100},
}


@pytest.mark.parametrize("name", sorted(OPTIMAL_PLANNERS))
def test_optimal_planner_reaches_goal_at_the_known_optimum(name):
    solver_cls = load_registered_solver(name)
    assert solver_cls is not None, (
        f"{name} is registered but did not load (UNSUPPORTED)"
    )
    with solver_cls(
        domain_factory=lambda: _grid.GridDomain(N, N), **OPTIMAL_PLANNERS[name]
    ) as solver:
        solver.solve()
        plan, reported_cost = _grid.get_plan(_grid.GridDomain(N, N), solver)

    reached, independent_cost = replay(plan)
    assert reached, f"{name}: plan does not reach the goal under independent dynamics"
    assert independent_cost == OPTIMUM, (
        f"{name}: independent cost {independent_cost} != optimum {OPTIMUM}"
    )
    assert reported_cost == independent_cost, f"{name} misreports its own plan cost"


def test_the_verifier_can_fail():
    """Anti-vacuity: a wrong plan is rejected, so a green result above means something."""
    too_short = [_grid.Action.right] * (N - 1)  # never leaves the top row
    reached, _ = replay(too_short)
    assert not reached
    detour = (
        [_grid.Action.right] * (N - 1)
        + [_grid.Action.left, _grid.Action.right]
        + [_grid.Action.down] * (N - 1)
    )
    reached, cost = replay(detour)
    assert reached and cost > OPTIMUM
