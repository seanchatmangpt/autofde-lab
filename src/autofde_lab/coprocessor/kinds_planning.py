"""Coprocessor kinds rcpsp, cp, portfolio (lane B3)."""

from __future__ import annotations

from typing import Any, Dict, List

from autofde_lab.coprocessor.envelope import (
    Envelope,
    Result,
    Status,
    blocked,
    refused,
    register_kind,
)


def _rcpsp_domain(p: Dict[str, Any]):
    """Build a real RCPSP domain from a named-task payload.

    payload: tasks {name: {duration:int, uses:{res:int}}}, precedences [[a,b]...],
    resources {res: capacity}. Returns (domain, ids) or raises ValueError.
    """
    from autofde_lab.hub.domain.rcpsp.rcpsp_sk import RCPSP

    tasks = p.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError("payload.tasks must be a non-empty object")
    resources = p.get("resources", {})
    precs = p.get("precedences", [])
    names = list(tasks)
    ids = {n: i + 2 for i, n in enumerate(names)}
    sink = len(names) + 2
    succ: Dict[int, List[int]] = {1: [], sink: []}
    for n in names:
        succ[ids[n]] = []
    for a, b in precs:
        if a not in ids or b not in ids:
            raise ValueError(f"precedence names unknown task: {a!r}->{b!r}")
        succ[ids[a]].append(ids[b])
    has_pred = {b for a, b in ((ids[a], ids[b]) for a, b in precs)}
    for n in names:
        if ids[n] not in has_pred:
            succ[1].append(ids[n])
        if not succ[ids[n]]:
            succ[ids[n]].append(sink)
    tm = {1: {1: {"duration": 0}}, sink: {1: {"duration": 0}}}
    for n in names:
        t = tasks[n]
        tm[ids[n]] = {1: {"duration": int(t["duration"]), **{k: int(v) for k, v in t.get("uses", {}).items()}}}
    horizon = int(p.get("horizon") or sum(int(t["duration"]) for t in tasks.values()) + 1)
    dom = RCPSP(
        tasks_mode=tm,
        max_horizon=horizon,
        successors=succ,
        resource_names=list(resources),
        resource_availability={k: int(v) for k, v in resources.items()},
        resource_renewable={k: True for k in resources},
    )
    return dom, ids


def _has_cycle(names, precs) -> bool:
    adj = {n: [] for n in names}
    for a, b in precs:
        adj.setdefault(a, []).append(b)
    state: Dict[Any, int] = {}

    def visit(n) -> bool:
        state[n] = 1
        for m in adj.get(n, []):
            if state.get(m) == 1 or (m not in state and visit(m)):
                return True
        state[n] = 2
        return False

    return any(n not in state and visit(n) for n in names)


@register_kind("rcpsp", module="kinds_planning")
def _rcpsp(env: Envelope) -> Result:
    p = env.payload
    try:
        from autofde_lab import rollout
        from autofde_lab.hub.solver.do_solver.do_solver_scheduling import DOSolver
        from autofde_lab.hub.solver.do_solver.sgs_policies import BasePolicyMethod, PolicyMethodParams
        from autofde_lab.hub.solver.do_solver.sk_to_do_binding import from_last_state_to_solution
        from discrete_optimization.rcpsp.solvers_map import CpSatRcpspSolver
    except ModuleNotFoundError as exc:
        return blocked(exc.name or "discrete_optimization", kind="rcpsp", solver="DOSolver/CpSat")
    tasks = p.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        return refused("payload.tasks must be a non-empty object", kind="rcpsp")
    resources = p.get("resources", {})
    # anti-vacuity: structurally infeasible instances are named, not solved
    for n, t in tasks.items():
        for r, q in t.get("uses", {}).items():
            if r not in resources:
                return refused(f"task {n!r} uses undeclared resource {r!r}", kind="rcpsp")
            if int(q) > int(resources[r]):
                return Result(Status.INFEASIBLE, kind="rcpsp", solver="precheck",
                              diagnostics={"reason": "demand_exceeds_capacity", "task": n, "resource": r})
    if _has_cycle(list(tasks), p.get("precedences", [])):
        return Result(Status.INFEASIBLE, kind="rcpsp", solver="precheck",
                      diagnostics={"reason": "precedence_cycle"})
    try:
        dom, ids = _rcpsp_domain(p)
    except (ValueError, KeyError, TypeError) as exc:
        return refused(f"bad rcpsp payload: {exc}", kind="rcpsp")
    dom.set_inplace_environment(False)
    s0 = dom.get_initial_state()
    solver = DOSolver(
        domain_factory=lambda: dom,
        policy_method_params=PolicyMethodParams(
            base_policy_method=BasePolicyMethod.FOLLOW_GANTT, delta_index_freedom=0, delta_time_freedom=0
        ),
        do_solver_type=CpSatRcpspSolver,
    )
    solver.solve()
    states, _, _ = rollout(domain=dom, solver=solver, from_memory=s0,
                           max_steps=10 * len(tasks) + 50, return_episodes=True)[0]
    sched = from_last_state_to_solution(states[-1], dom).rcpsp_schedule
    sink = len(tasks) + 2
    if sink not in sched:
        return Result(Status.NO_PLAN, kind="rcpsp", solver="DOSolver/CpSat",
                      diagnostics={"reason": "schedule_incomplete"})
    actions = sorted(
        ({"task": n, "start": int(sched[i]["start_time"]), "end": int(sched[i]["end_time"])}
         for n, i in ids.items()),
        key=lambda a: (a["start"], a["task"]),
    )
    return Result(Status.PLAN, kind="rcpsp", actions=actions,
                  cost=float(sched[sink]["end_time"]), solver="DOSolver/CpSat")



_OPS = ("<=", ">=", "==")


def _cp_model(env: Envelope) -> Result:
    """General declarative CP-SAT payload.

    payload.model:
      vars: {name: [lo, hi]}                       (bool = [0, 1]; fixed = [v, v])
      constraints: list of
        {"type":"exactly_one","vars":[...]}
        {"type":"linear","terms":[[coef,var]...],"op":"<=|>=|==","rhs":int,"only_if":var?}
        {"type":"implies","a":var,"b":var}
        {"type":"no_overlap","intervals":[{"start":int|var,"size":int,"present":var?}]}
        {"type":"infeasible"}
      objective: {"sense":"min|max","terms":[[coef,var]...]}   (optional)
    Reply: actions=[{"var","value"}...] sorted by name, cost=objective value,
    diagnostics.optimal=True when CP-SAT proved optimality.
    """
    from ortools.sat.python import cp_model

    mod = env.payload["model"]
    vs = mod.get("vars")
    if not isinstance(vs, dict) or not vs:
        return refused("model.vars must be a non-empty object", kind="cp")
    m = cp_model.CpModel()
    try:
        v = {n: m.NewIntVar(int(lo), int(hi), n) for n, (lo, hi) in vs.items()}

        def lin(terms):
            return sum(int(c) * v[n] for c, n in terms)

        for c in mod.get("constraints", []):
            t = c["type"]
            if t == "exactly_one":
                m.AddExactlyOne(v[n] for n in c["vars"])
            elif t == "linear":
                if c["op"] not in _OPS:
                    return refused(f"bad op {c['op']!r}", kind="cp")
                e = lin(c["terms"])
                r = int(c["rhs"])
                ct = e <= r if c["op"] == "<=" else e >= r if c["op"] == ">=" else e == r
                k = m.Add(ct)
                if c.get("only_if"):
                    k.OnlyEnforceIf(v[c["only_if"]])
            elif t == "implies":
                m.AddImplication(v[c["a"]], v[c["b"]])
            elif t == "no_overlap":
                ivs = []
                for i, iv in enumerate(c["intervals"]):
                    st = iv["start"]
                    st = v[st] if isinstance(st, str) else int(st)
                    sz = int(iv["size"])
                    if iv.get("present"):
                        ivs.append(m.NewOptionalFixedSizeIntervalVar(st, sz, v[iv["present"]], f"iv{i}"))
                    else:
                        ivs.append(m.NewFixedSizeIntervalVar(st, sz, f"iv{i}"))
                m.AddNoOverlap(ivs)
            elif t == "infeasible":
                m.AddBoolOr([])
            else:
                return refused(f"unknown constraint type {t!r}", kind="cp")
        obj = mod.get("objective")
        if obj:
            if obj.get("sense") not in ("min", "max"):
                return refused("objective.sense must be min|max", kind="cp")
            (m.Minimize if obj["sense"] == "min" else m.Maximize)(lin(obj["terms"]))
    except (KeyError, ValueError, TypeError) as exc:
        return refused(f"bad cp model: {exc!r}", kind="cp")
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 0
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = float(env.options.get("time_limit", 30))
    st = solver.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        actions = [{"var": n, "value": int(solver.Value(v[n]))} for n in sorted(v)]
        return Result(Status.PLAN, kind="cp", actions=actions,
                      cost=float(solver.ObjectiveValue()) if obj else 0.0, solver="ortools-cpsat",
                      diagnostics={"optimal": st == cp_model.OPTIMAL})
    if st == cp_model.INFEASIBLE:
        return Result(Status.INFEASIBLE, kind="cp", solver="ortools-cpsat",
                      diagnostics={"reason": "model_infeasible"})
    return Result(Status.NO_PLAN, kind="cp", solver="ortools-cpsat",
                  diagnostics={"reason": "unknown_within_time_limit"})


@register_kind("cp", module="kinds_planning")
def _cp(env: Envelope) -> Result:
    """Stand assignment: payload.flights [[name, arrive, depart]], payload.stands int."""
    try:
        from ortools.sat.python import cp_model
    except ModuleNotFoundError:
        return blocked("ortools", kind="cp", solver="ortools-cpsat")
    p = env.payload
    if "model" in p:
        return _cp_model(env)
    flights = p.get("flights")
    stands = p.get("stands")
    if not isinstance(flights, list) or not flights or not isinstance(stands, int) or stands < 1:
        return refused("payload needs flights [[name,arr,dep]...] and integer stands>=1", kind="cp")
    try:
        fl = [(str(f), int(a), int(d)) for f, a, d in flights]
    except (ValueError, TypeError) as exc:
        return refused(f"bad flights: {exc}", kind="cp")
    if any(d <= a for _, a, d in fl):
        return refused("flight with departure <= arrival", kind="cp")
    m = cp_model.CpModel()
    x = {(f, s): m.NewBoolVar(f"{f}_{s}") for f, _, _ in fl for s in range(stands)}
    for f, _, _ in fl:
        m.AddExactlyOne(x[f, s] for s in range(stands))
    for s in range(stands):
        m.AddNoOverlap([m.NewOptionalIntervalVar(a, d - a, d, x[f, s], f"i_{f}_{s}") for f, a, d in fl])
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 0
    solver.parameters.num_workers = 1
    solver.parameters.max_time_in_seconds = float(env.options.get("time_limit", 30))
    st = solver.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        actions = [{"flight": f, "stand": next(s for s in range(stands) if solver.Value(x[f, s]))}
                   for f, _, _ in fl]
        return Result(Status.PLAN, kind="cp", actions=actions,
                      cost=float(len({a["stand"] for a in actions})), solver="ortools-cpsat")
    if st == cp_model.INFEASIBLE:
        return Result(Status.INFEASIBLE, kind="cp", solver="ortools-cpsat",
                      diagnostics={"reason": "no_overlap_free_assignment", "stands": stands})
    return Result(Status.NO_PLAN, kind="cp", solver="ortools-cpsat",
                  diagnostics={"reason": "unknown_within_time_limit"})


@register_kind("portfolio", module="kinds_planning")
def _portfolio(env: Envelope) -> Result:
    """Match registered solvers to a described domain.

    payload.domain: "rcpsp" (plus the rcpsp payload fields) or "graph" (edges [[a,b,w]...],
    targets [names]).
    """
    from autofde_lab.utils import match_solvers

    p = env.payload
    kind = p.get("domain")
    try:
        if kind == "rcpsp":
            dom, _ = _rcpsp_domain(p)
        elif kind == "graph":
            from autofde_lab.hub.domain.graph_domain.GraphDomain import GraphDomain

            nsm: Dict[str, Dict[str, str]] = {}
            attr: Dict[str, Dict[str, Dict[str, int]]] = {}
            for a, b, w in p["edges"]:
                for u, v in ((a, b), (b, a)):
                    nsm.setdefault(u, {})[v] = v
                    attr.setdefault(u, {})[v] = {"weight": int(w)}
            dom = GraphDomain(nsm, attr, targets=set(p["targets"]))
        else:
            return refused(f"unknown domain description {kind!r}", kind="portfolio",
                           known=["graph", "rcpsp"])
    except (ValueError, KeyError, TypeError) as exc:
        return refused(f"bad domain description: {exc}", kind="portfolio")
    matched = match_solvers(dom)
    names = sorted(f"{c.__module__}.{c.__name__}" for c in matched)
    if not names:
        return Result(Status.NO_PLAN, kind="portfolio", solver="match_solvers",
                      diagnostics={"reason": "no_compatible_solver", "domain": kind})
    return Result(Status.PLAN, kind="portfolio", actions=names, cost=float(len(names)),
                  solver="match_solvers", diagnostics={"domain": kind})
