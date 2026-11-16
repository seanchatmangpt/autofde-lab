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


TIL_HORIZON = 10000


def _purge_items_list(self, items_list, params, conds):
    """GrounderHelper._purge_items_list without the double-remove: some unified-planning
    1.3.0 builds call ``temp_list.remove(obj)`` once per static condition that excludes
    ``obj``, raising ValueError when two conditions prune the same object."""
    out = []
    for param, object_list in zip(params, items_list):
        keep = list(object_list)
        pexp = self._problem.environment.expression_manager.ParameterExp(param)
        for cond in conds:
            pos = next((i for i, fp in enumerate(cond.args) if fp == pexp), -1)
            if pos != -1:
                valid = self._bool_static_fluent_valid_parameters(cond, pos)
                keep = [o for o in keep if o in valid]
        out.append(keep)
    return out


def _fix_grounder() -> None:
    from unified_planning.engines.compilers.grounder import GrounderHelper
    GrounderHelper._purge_items_list = _purge_items_list
REAL_AS_INT_MAX = 100_000_000


def _solve_temporal(dom: str, prob: str, timeout: float, horizon: float):
    """Search on an Int-typed, grounded copy (aries has no Real; TILs past
    ``horizon`` deferred), then validate the plan on the ORIGINAL problem.

    Returns (status, timed_actions|None, diagnostics)."""
    from unified_planning.engines import CompilationKind
    from unified_planning.engines.results import POSITIVE_OUTCOMES
    from unified_planning.engines import ValidationResultStatus
    from unified_planning.io import PDDLReader
    from unified_planning.shortcuts import Compiler, OneshotPlanner, PlanValidator, get_environment
    import unified_planning.plans as plans
    from unified_planning.plans import ActionInstance

    _fix_grounder()
    orig = PDDLReader().parse_problem(dom, prob)
    tm = get_environment().type_manager
    saved = tm.RealType
    tm.RealType = lambda *a, **k: tm.IntType(0, REAL_AS_INT_MAX)
    try:
        sp = PDDLReader().parse_problem(dom, prob)
    finally:
        tm.RealType = saved
    late = [t for t in list(sp.timed_effects) if float(t.delay) > horizon]
    for t in late:
        del sp._timed_effects[t]
    with Compiler(name="up_grounder", compilation_kind=CompilationKind.GROUNDING) as c:
        g = c.compile(sp, CompilationKind.GROUNDING)
    with OneshotPlanner(name="aries") as pl:
        res = pl.solve(g.problem, timeout=timeout)
    diag = {"engine_status": res.status.name, "deferred_tils": len(late)}
    if res.status not in POSITIVE_OUTCOMES or res.plan is None:
        return NO_PLAN, None, diag
    plan = res.plan.replace_action_instances(g.map_back_action_instance)
    em = orig.environment.expression_manager
    timed = [
        (s, ActionInstance(orig.action(a.action.name),
                           tuple(em.ObjectExp(orig.object(p.object().name))
                                 for p in a.actual_parameters)), d)
        for s, a, d in plan.timed_actions
    ]
    plan_o = plans.TimeTriggeredPlan(timed)
    end = max((float(s) + float(d or 0) for s, _a, d in timed), default=0.0)
    if end >= horizon:
        diag["reason"] = "plan reaches deferred TIL horizon"
        return REFUSED, None, diag
    with PlanValidator(name="up_time_triggered_validator") as v:
        vr = v.validate(orig, plan_o)
    diag["validator"] = vr.status.name
    if vr.status != ValidationResultStatus.VALID:
        diag["reason"] = "VALIDATION_FAILED"
        return REFUSED, None, diag
    return PLAN, timed, diag


@register_kind("temporal_pddl", module="kinds_pddl")
def _temporal(env: Envelope) -> Result:
    solver = "unified_planning:aries"
    try:
        import unified_planning  # noqa: F401
        from unified_planning.io import PDDLReader  # noqa: F401
    except ModuleNotFoundError as exc:
        return blocked(exc.name or "unified-planning", solver=solver)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="cop-tpddl-") as wd:
        try:
            dom, prob = _materialise(env, wd)
        except ValueError as exc:
            return refused(str(exc), solver=solver)
        try:
            from unified_planning.io import PDDLReader
            PDDLReader().parse_problem(dom, prob)
        except Exception as exc:  # noqa: BLE001
            return refused(f"cannot parse: {type(exc).__name__}: {exc}", solver=solver)
        try:
            status, timed, diag = _solve_temporal(
                dom, prob, float(env.options.get("timeout", 30)),
                float(env.options.get("til_horizon", TIL_HORIZON)))
        except ModuleNotFoundError as exc:
            return blocked(exc.name or "aries", solver=solver)
        if status != PLAN:
            return Result(status, solver=solver, diagnostics=diag)
        actions, makespan = [], 0.0
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
