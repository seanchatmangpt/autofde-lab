"""The chuffed tag must always resolve to a MiniZinc solver that is installed."""

import warnings

import minizinc
from discrete_optimization.generic_tools import cp_tools

from autofde_lab.hub.solver.do_solver.do_solver_scheduling import (
    _ensure_available_minizinc_solver,
)


def test_chuffed_tag_resolves_to_installed_solver():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        name = _ensure_available_minizinc_solver()
    assert cp_tools.map_cp_solver_name[cp_tools.CpSolverName.CHUFFED] == name
    assert minizinc.Solver.lookup(name) is not None
