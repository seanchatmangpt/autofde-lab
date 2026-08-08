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
from dataclasses import dataclass
from importlib.metadata import entry_points

from autofde_lab.hub.domain.gym_procedure.gym_procedure import (
    GymProcedureDomain,
    Recipe,
)


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
            results.append(
                SolverClassification(
                    name=ep.name,
                    entry_point=ep.value,
                    status=f"UNAVAILABLE:{type(exc).__name__}",
                )
            )
            continue
        try:
            ok = cls.check_domain(domain)
            status = "SUPPORTED" if ok else "UNSUPPORTED:CHECK_DOMAIN_FALSE"
        except Exception as exc:  # noqa: BLE001
            status = f"UNSUPPORTED:{type(exc).__name__}"
        results.append(
            SolverClassification(name=ep.name, entry_point=ep.value, status=status)
        )
    return results


def solver_kwargs(solver_name: str, recipe: Recipe) -> dict:
    """Real, principled constructor arguments for solvers that genuinely require them.

    `Solver.get_domain_requirements()` derives *domain characteristics* only and
    says nothing about *constructor* requirements (see
    `hub/solver/CLAUDE.md` invariant 1). So a solver can classify SUPPORTED and
    still refuse `cls(domain_factory=...)` alone. `IW`, `RIW` and `BFWS` are the
    real case here: all three implement iterated-width novelty search, which is
    *defined* over a vector of state atoms, so `state_features` is a genuine
    algorithmic input, not boilerplate. A recipe supplies exactly that vector:
    the fact universe it can ever mention, as a fixed-order 0/1 membership
    vector. This is the standard IW propositional feature set, not a stand-in.
    """
    if solver_name in ("IW", "RIW", "BFWS"):
        universe = sorted(
            set(recipe.initial_facts)
            | set(recipe.goal_facts)
            | {f for s in recipe.steps for f in s.preconditions}
            | {f for s in recipe.steps for f in s.establishes}
            | {f for s in recipe.steps for f in s.removes}
        )
        return {
            "state_features": lambda d, s, _u=tuple(universe): [
                1 if f in s.facts else 0 for f in _u
            ]
        }
    return {}


def _solve_one(
    solver_name: str, recipe: Recipe, timeout_s: float, problem_digest: str
) -> PlannerAttempt:
    from autofde_lab import utils

    # Two SEPARATE domain instances, deliberately. `Solver.__init__` wraps the
    # factory so that `autocast_all(domain, domain, T_domain)` MUTATES whatever
    # instance the factory hands back. Passing `lambda: domain` and then
    # rolling out on that same `domain` therefore rolls out on a
    # solver-mutated object -- shared mutable state across a boundary, the same
    # class of defect as the Level 3 shared-scratch incident. The rollout
    # domain below is never given to any solver.
    rollout_domain = GymProcedureDomain(recipe)
    start = time.monotonic()
    try:
        cls = utils.load_registered_solver(solver_name)
        if cls is None:
            return PlannerAttempt(
                solver_name,
                "recipe",
                problem_digest,
                "UNSUPPORTED",
                detail="not registered",
            )
        step_bound = len(recipe.steps) + 2
        with cls(
            domain_factory=lambda: GymProcedureDomain(recipe),
            **solver_kwargs(solver_name, recipe),
        ) as solver:
            solver.solve()
            domain = rollout_domain
            obs = domain.reset()
            plan: list[str] = []
            for _ in range(step_bound):
                if time.monotonic() - start > timeout_s:
                    return PlannerAttempt(
                        solver_name,
                        "recipe",
                        problem_digest,
                        "TIMEOUT",
                        tuple(plan),
                        time.monotonic() - start,
                    )
                if domain._is_terminal(obs):
                    break
                action = solver.sample_action(obs)
                # A plan is only a candidate if every action in it was legal in
                # the state it was taken from. `GymProcedureDomain._get_next_state`
                # applies a step's effects unconditionally -- it trusts the
                # caller to have checked `get_applicable_actions`. Without this
                # check a solver that samples from the full action space (the
                # POMDP solvers do) gets its precondition-violating action
                # applied anyway and the federation records a PLAN_CANDIDATE
                # for a plan that could never run. Measured: SARSOP "solved"
                # agentdojo_banking_pay_bill in 1 step by paying a bill it had
                # never read. That is a false success, so it is refused here.
                legal = domain._get_applicable_actions_from(obs).get_elements()
                if action not in legal:
                    return PlannerAttempt(
                        solver_name,
                        "recipe",
                        problem_digest,
                        "REFUSED",
                        tuple(plan),
                        time.monotonic() - start,
                        detail=(
                            f"proposed inapplicable action {action!r} at step "
                            f"{len(plan)}; applicable={sorted(legal)}"
                        ),
                    )
                plan.append(action)
                outcome = domain.step(action)
                obs = outcome.observation
            duration = time.monotonic() - start
            if domain._is_goal(obs):
                return PlannerAttempt(
                    solver_name,
                    "recipe",
                    problem_digest,
                    "PLAN_CANDIDATE",
                    tuple(plan),
                    duration,
                )
            return PlannerAttempt(
                solver_name,
                "recipe",
                problem_digest,
                "FAILED",
                tuple(plan),
                duration,
                detail="goal not reached within step bound",
            )
    except Exception as exc:  # noqa: BLE001 - a solver failure is evidence, not a crash of the federation
        return PlannerAttempt(
            solver_name,
            "recipe",
            problem_digest,
            "FAILED",
            (),
            time.monotonic() - start,
            detail=f"{type(exc).__name__}: {exc}"[:200],
        )


_SIGNAL_NAMES = {6: "SIGABRT", 8: "SIGFPE", 9: "SIGKILL", 11: "SIGSEGV"}


def _solve_one_isolated(
    solver_name: str, recipe: Recipe, timeout_s: float, problem_digest: str
) -> PlannerAttempt:
    """Run one planner in a forked child so a NATIVE crash is evidence.

    `_solve_one`'s `except Exception` catches Python exceptions only. A C++
    hub solver that segfaults raises nothing -- it kills the interpreter,
    and with it every other planner's evidence and every remaining trial of
    a frozen crown. Measured: the C++ `AOstar` solver dies with SIGSEGV on
    the `lock_and_key` recipe, taking the whole harness down mid-run.

    Isolation also gives the only real wall-clock bound available: the
    in-process timeout in `_solve_one` is checked between rollout steps, so
    it cannot interrupt a native `solve()` that never returns.

    A crash is recorded as `CRASHED`, never silently dropped and never
    upgraded to a plan -- federation output is advisory in any case, and
    the typed model remains the authoritative validation gate.
    """
    import multiprocessing as mp

    try:
        ctx = mp.get_context("fork")
    except ValueError:  # platform without fork -- no isolation available
        return _solve_one(solver_name, recipe, timeout_s, problem_digest)

    parent_conn, child_conn = ctx.Pipe(duplex=False)

    def _target(conn) -> None:
        try:
            conn.send(_solve_one(solver_name, recipe, timeout_s, problem_digest))
        except BaseException as exc:  # noqa: BLE001
            conn.send(
                PlannerAttempt(
                    solver_name, "recipe", problem_digest, "FAILED", (), 0.0,
                    detail=f"{type(exc).__name__}: {exc}"[:200],
                )
            )
        finally:
            conn.close()

    proc = ctx.Process(target=_target, args=(child_conn,), daemon=True)
    start = time.monotonic()
    proc.start()
    child_conn.close()

    # Generous margin over the solver's own budget: this bound exists to
    # catch a hung native solve, not to second-guess `_solve_one`.
    attempt: PlannerAttempt | None = None
    if parent_conn.poll(timeout_s + 10.0):
        try:
            attempt = parent_conn.recv()
        except EOFError:
            attempt = None
    parent_conn.close()

    proc.join(timeout=5.0)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=5.0)
        return PlannerAttempt(
            solver_name, "recipe", problem_digest, "TIMEOUT", (),
            time.monotonic() - start,
            detail=f"killed after {timeout_s + 10.0:.1f}s wall clock (native solve did not return)",
        )
    if attempt is not None:
        return attempt

    code = proc.exitcode
    if code is not None and code < 0:
        signame = _SIGNAL_NAMES.get(-code, f"signal {-code}")
        return PlannerAttempt(
            solver_name, "recipe", problem_digest, "CRASHED", (),
            time.monotonic() - start,
            detail=f"planner process died with {signame} (native crash, no Python exception)",
        )
    return PlannerAttempt(
        solver_name, "recipe", problem_digest, "CRASHED", (),
        time.monotonic() - start,
        detail=f"planner process exited with code {code} without returning an attempt",
    )


def run_federation(
    recipe: Recipe, solver_names: list[str], timeout_s: float = 15.0
) -> list[PlannerAttempt]:
    """Run every named solver (already classified SUPPORTED) within a bounded
    per-solver timeout; record every attempt, including non-successes."""
    import hashlib
    import json

    problem_digest = hashlib.sha256(
        json.dumps(
            {
                "initial": sorted(recipe.initial_facts),
                "goal": sorted(recipe.goal_facts),
                "steps": sorted(s.id for s in recipe.steps),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    return [
        _solve_one_isolated(name, recipe, timeout_s, problem_digest)
        for name in solver_names
    ]
