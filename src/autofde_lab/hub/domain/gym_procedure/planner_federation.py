# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real planner-federation inventory + bounded multi-solver execution.

Not "assume 50+ planners" -- measure. `classify_registered_solvers`
enumerates every solver actually registered under the
`autofde_lab.solvers` entry-point group and classifies each via the exact
mechanism the solver framework itself uses to gate applicability
(`cls.check_domain(domain)`), against a real `GymProcedureDomain` instance.
`run_federation` then executes every classified-SUPPORTED solver within a
bounded per-solver time budget and records a `PlannerAttempt` for every
one, including solvers that time out or raise -- disagreement/failure is
evidence, not something to discard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, Optional

from autofde_lab.hub.domain.gym_procedure.gym_procedure import GymProcedureDomain, Recipe


@dataclass(frozen=True)
class SolverClassification:
    name: str
    entry_point: str
    status: str  # "SUPPORTED" | "UNSUPPORTED:<reason>" | "UNAVAILABLE:<reason>"


@dataclass(frozen=True)
class PlannerAttempt:
    planner_identity: str
    representation: str
    problem_digest: str
    outcome: str  # "PLAN_CANDIDATE" | "UNSUPPORTED" | "TIMEOUT" | "FAILED" | "REFUSED"
    candidate_plan: tuple[str, ...] = ()
    planning_duration_s: float = 0.0
    detail: str = ""


def classify_registered_solvers(recipe: Recipe) -> list[SolverClassification]:
    """Real classification against a real domain instance -- no hardcoded list."""
    domain = GymProcedureDomain(recipe)
    results: list[SolverClassification] = []
    for ep in entry_points(group="autofde_lab.solvers"):
        try:
            cls = ep.load()
        except Exception as exc:  # noqa: BLE001 - genuinely need to record any import failure as evidence
            results.append(SolverClassification(name=ep.name, entry_point=ep.value, status=f"UNAVAILABLE:{type(exc).__name__}"))
            continue
        try:
            ok = cls.check_domain(domain)
            status = "SUPPORTED" if ok else "UNSUPPORTED:CHECK_DOMAIN_FALSE"
        except Exception as exc:  # noqa: BLE001
            status = f"UNSUPPORTED:{type(exc).__name__}"
        results.append(SolverClassification(name=ep.name, entry_point=ep.value, status=status))
    return results


def _solve_one(solver_name: str, recipe: Recipe, timeout_s: float, problem_digest: str) -> PlannerAttempt:
    from autofde_lab import utils

    domain = GymProcedureDomain(recipe)
    start = time.monotonic()
    try:
        cls = utils.load_registered_solver(solver_name)
        if cls is None:
            return PlannerAttempt(solver_name, "recipe", problem_digest, "UNSUPPORTED", detail="not registered")
        with cls(domain_factory=lambda: domain) as solver:
            solver.solve()
            obs = domain.reset()
            plan: list[str] = []
            for _ in range(50):
                if time.monotonic() - start > timeout_s:
                    return PlannerAttempt(solver_name, "recipe", problem_digest, "TIMEOUT", tuple(plan), time.monotonic() - start)
                if domain._is_terminal(obs):
                    break
                action = solver.sample_action(obs)
                plan.append(action)
                outcome = domain.step(action)
                obs = outcome.observation
            duration = time.monotonic() - start
            if domain._is_goal(obs):
                return PlannerAttempt(solver_name, "recipe", problem_digest, "PLAN_CANDIDATE", tuple(plan), duration)
            return PlannerAttempt(solver_name, "recipe", problem_digest, "FAILED", tuple(plan), duration, detail="goal not reached within step bound")
    except Exception as exc:  # noqa: BLE001 - a solver failure is evidence, not a crash of the federation
        return PlannerAttempt(solver_name, "recipe", problem_digest, "FAILED", (), time.monotonic() - start, detail=f"{type(exc).__name__}: {exc}"[:200])


def run_federation(recipe: Recipe, solver_names: list[str], timeout_s: float = 15.0) -> list[PlannerAttempt]:
    """Run every named solver (already classified SUPPORTED) within a bounded
    per-solver timeout; record every attempt, including non-successes."""
    import hashlib
    import json

    problem_digest = hashlib.sha256(
        json.dumps(
            {"initial": sorted(recipe.initial_facts), "goal": sorted(recipe.goal_facts), "steps": sorted(s.id for s in recipe.steps)},
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    return [_solve_one(name, recipe, timeout_s, problem_digest) for name in solver_names]
