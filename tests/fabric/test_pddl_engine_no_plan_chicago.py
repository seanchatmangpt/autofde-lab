# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""pddl_engine reports an unsolvable problem as a clean NO_PLAN, not a crash.

Real subprocess, real Astar, real PDDL files. Before Astar defined
`_is_policy_defined_for`, an unsolvable problem exited 1 only because
`sample_action` crashed with an AttributeError that was swallowed into
EXIT_NO_PLAN.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BLOCKS = Path(__file__).resolve().parents[1] / "domains/python/pddl_domains/blocks"
UNSOLVABLE = (
    "(define (problem U) (:domain BLOCKS) (:objects A B) "
    "(:init (ONTABLE A) (ONTABLE B) (CLEAR A) (CLEAR B) (HANDEMPTY)) "
    "(:goal (AND (ON A B) (ON B A))))\n"
)


def _engine(domain: Path, problem: Path, plan: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autofde_lab.fabric.pddl_engine", str(domain), str(problem), str(plan)],
        capture_output=True,
        text=True,
    )


def test_unsolvable_problem_is_a_clean_no_plan_without_a_traceback(tmp_path: Path):
    problem = tmp_path / "unsolvable.pddl"
    problem.write_text(UNSOLVABLE)
    proc = _engine(BLOCKS / "domain.pddl", problem, tmp_path / "plan.txt")
    assert proc.returncode == 1
    assert "no plan exists" in proc.stdout
    assert "Traceback" not in proc.stdout + proc.stderr
    assert not (tmp_path / "plan.txt").exists()


def test_solvable_problem_still_yields_a_plan(tmp_path: Path):
    plan = tmp_path / "plan.txt"
    proc = _engine(BLOCKS / "domain.pddl", BLOCKS / "probBLOCKS-3-0.pddl", plan)
    assert proc.returncode == 0
    assert "(stack b c)" in plan.read_text()


def test_astar_policy_is_defined_where_search_reached_a_goal():
    from autofde_lab import utils
    from autofde_lab.hub.domain.pddl import PDDLDomain

    domain = PDDLDomain(str(BLOCKS / "domain.pddl"), str(BLOCKS / "probBLOCKS-3-0.pddl"))
    astar = utils.load_registered_solver("Astar")
    with astar(domain_factory=lambda: domain) as solver:
        solver.solve()
        assert solver.is_policy_defined_for(domain.reset()) is True
