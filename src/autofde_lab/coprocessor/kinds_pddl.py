"""Kinds ``pddl``, ``temporal_pddl`` and ``htn``.

Payload (all three): ``domain_path`` or ``domain_text``, and ``problem_path``
or ``problem_text``. Inline text is materialised under ``scratch_dir()``.

* pddl: subprocess to ``autofde_lab.fabric.pddl_engine`` (exit 0 PLAN,
  1 NO_PLAN, 2 REFUSED).
* temporal_pddl: unified-planning reader plus the ``aries`` temporal engine;
  actions carry ``start`` and ``duration``; cost is the makespan.
* htn: ``HTNTotalOrderPlanner`` over a unified-planning HDDL problem.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Dict, Tuple

from autofde_lab.coprocessor.envelope import (
    NO_PLAN,
    PLAN,
    REFUSED,
    Envelope,
    Result,
    blocked,
    refused,
    register_kind,
    scratch_dir,
    subprocess_env,
)


def _materialise(env: Envelope, workdir: str) -> Tuple[str, str]:
    paths = []
    for role in ("domain", "problem"):
        p = env.payload.get(f"{role}_path")
        text = env.payload.get(f"{role}_text")
        if p is None and text is None:
            raise ValueError(f"payload needs {role}_path or {role}_text")
        if p is None:
            p = os.path.join(workdir, f"{role}.pddl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
        paths.append(str(p))
    return paths[0], paths[1]


def _split_action(line: str):
    return line.strip().strip("()").split()


@register_kind("pddl", module="kinds_pddl")
def _pddl(env: Envelope) -> Result:
    solver = "autofde_lab.fabric.pddl_engine:Astar"
    timeout = float(env.options.get("timeout", 300))
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="cop-pddl-") as wd:
        try:
            dom, prob = _materialise(env, wd)
        except ValueError as exc:
            return refused(str(exc), solver=solver)
        plan_path = os.path.join(wd, "plan.txt")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "autofde_lab.fabric.pddl_engine", dom, prob, plan_path],
                capture_output=True, text=True, timeout=timeout,
                env=subprocess_env(), stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return Result(NO_PLAN, solver=solver, diagnostics={"reason": "timeout"})
        diag: Dict = {"engine_exit": proc.returncode}
        if proc.returncode == 0:
            actions, cost = [], None
            with open(plan_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("; cost ="):
                        cost = float(line.split("=")[1].split()[0])
                    elif line.startswith("("):
                        actions.append(_split_action(line))
            return Result(PLAN, actions=actions, cost=cost, solver=solver, diagnostics=diag)
        if proc.returncode == 1:
            return Result(NO_PLAN, solver=solver, diagnostics=diag)
        return Result(REFUSED, solver=solver, diagnostics=diag)


@register_kind("temporal_pddl", module="kinds_pddl")
def _temporal(env: Envelope) -> Result:
    solver = "unified_planning:aries"
    try:
        from unified_planning.io import PDDLReader
        from unified_planning.shortcuts import OneshotPlanner
        from unified_planning.engines.results import POSITIVE_OUTCOMES
    except ModuleNotFoundError as exc:
        return blocked(exc.name or "unified-planning", solver=solver)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="cop-tpddl-") as wd:
        try:
            dom, prob = _materialise(env, wd)
        except ValueError as exc:
            return refused(str(exc), solver=solver)
        try:
            problem = PDDLReader().parse_problem(dom, prob)
        except Exception as exc:  # noqa: BLE001
            return refused(f"cannot parse: {type(exc).__name__}: {exc}", solver=solver)
        try:
            with OneshotPlanner(name="aries") as planner:
                res = planner.solve(problem, timeout=float(env.options.get("timeout", 30)))
        except ModuleNotFoundError as exc:
            return blocked(exc.name or "aries", solver=solver)
        diag = {"engine_status": res.status.name}
        if res.status not in POSITIVE_OUTCOMES or res.plan is None:
            return Result(NO_PLAN, solver=solver, diagnostics=diag)
        timed = getattr(res.plan, "timed_actions", None)
        actions, makespan = [], 0.0
        if timed is None:
            for i, a in enumerate(res.plan.actions):
                actions.append({"action": str(a), "start": float(i), "duration": 0.0})
            makespan = float(len(actions))
        else:
            for start, act, dur in timed:
                s = float(start)
                d = float(dur) if dur is not None else 0.0
                actions.append({"action": str(act), "start": s, "duration": d})
                makespan = max(makespan, s + d)
        return Result(PLAN, actions=actions, cost=makespan, solver=solver, diagnostics=diag)


@register_kind("htn", module="kinds_pddl")
def _htn(env: Envelope) -> Result:
    solver = "autofde_lab.hub.domain.htn:HTNTotalOrderPlanner"
    try:
        from unified_planning.io import PDDLReader
        from autofde_lab.hub.domain.htn.planner import (
            HTNPlanningFailure,
            HTNTotalOrderPlanner,
        )
    except ModuleNotFoundError as exc:
        return blocked(exc.name or "unified-planning", solver=solver)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="cop-htn-") as wd:
        try:
            dom, prob = _materialise(env, wd)
        except ValueError as exc:
            return refused(str(exc), solver=solver)
        try:
            problem = PDDLReader().parse_problem(dom, prob)
            planner = HTNTotalOrderPlanner(problem)
        except Exception as exc:  # noqa: BLE001
            return refused(f"cannot parse: {type(exc).__name__}: {exc}", solver=solver)
        try:
            plan = planner.solve()
        except HTNPlanningFailure as exc:
            return Result(NO_PLAN, solver=solver, diagnostics={"reason": str(exc)})
        except NotImplementedError as exc:
            return refused(f"unsupported construct: {exc}", solver=solver)
        actions = [[a.name, *a.args] for a in plan]
        return Result(PLAN, actions=actions, cost=float(len(actions)), solver=solver)
