"""Coprocessor kinds ``fond``, ``mdp`` and ``search`` (lane B2).

Payload shapes (JSON):

* ``search``: ``{"solver": "astar"|"p_astar"|"lrtastar", "initial": s, "targets": [s],
  "edges": [[src, action, dst, cost], ...]}`` on a ``GraphDomain``.
* ``mdp``: ``{"solver": "lrtdp"|"martdp"|"mdplp"|"mcts", "initial": s, "goals": [s],
  "transitions": {s: {a: {s2: [prob, cost]}}}}`` on a ``GraphDomainUncertain``
  (martdp runs through a one-agent multi-agent adapter, as MA-RTDP needs one).
* ``fond``: ``{"semantics": "strong"|"strong_cyclic", "initial": s, "goals": [s],
  "transitions": {s: {a: [s2, ...]}}, "policy": {s: a}}``; without ``policy`` a policy is
  synthesised and then checked by ``planning.fond_policy``.

Statuses: PLAN, INFEASIBLE (goal unreachable / no proper policy), REFUSED (bad input).
"""

from __future__ import annotations

import random
import warnings
from collections import deque
from typing import Any, Dict, List, Optional, Set

from autofde_lab.coprocessor.envelope import (
    Envelope,
    Result,
    Status,
    refused,
    register_kind,
)

_MOD = "kinds_search"
SEARCH_SOLVERS = ("astar", "p_astar", "lrtastar")
MDP_SOLVERS = ("lrtdp", "martdp", "mdplp", "mcts")


def _need(payload: Dict[str, Any], *keys: str) -> Optional[str]:
    missing = [k for k in keys if k not in payload]
    return f"missing payload field(s): {', '.join(missing)}" if missing else None


# --------------------------------------------------------------------- fond


def _fond_winning(
    trans: Dict[str, Dict[str, List[str]]], goals: Set[str], cyclic: bool
) -> Dict[str, str]:
    """Return a state->action policy over the winning region (goals excluded)."""
    states = set(trans) | {o for acts in trans.values() for outs in acts.values() for o in outs}
    states |= goals
    if cyclic:
        win = set(states)
        while True:
            allowed = {
                s: [a for a, outs in trans.get(s, {}).items() if outs and set(outs) <= win]
                for s in win
            }
            reach = set(goals & win)
            changed = True
            while changed:
                changed = False
                for s in win - reach:
                    if any(set(trans[s][a]) & reach for a in allowed[s]):
                        reach.add(s)
                        changed = True
            if reach == win:
                break
            win = reach
        layer: Dict[str, int] = {g: 0 for g in goals & win}
        policy: Dict[str, str] = {}
        frontier = set(layer)
        depth = 0
        while frontier:
            depth += 1
            nxt = set()
            for s in sorted(win - set(layer)):
                for a in sorted(allowed[s]):
                    if set(trans[s][a]) & frontier:
                        layer[s] = depth
                        policy[s] = a
                        nxt.add(s)
                        break
            frontier = nxt
        return policy
    layer = {g: 0 for g in goals}
    policy = {}
    depth = 0
    grew = True
    while grew:
        grew = False
        depth += 1
        for s in sorted(states - set(layer)):
            for a in sorted(trans.get(s, {})):
                outs = trans[s][a]
                if outs and all(o in layer and layer[o] < depth for o in outs):
                    layer[s] = depth
                    policy[s] = a
                    grew = True
                    break
    return policy


@register_kind("fond", module=_MOD)
def _fond(env: Envelope) -> Result:
    from autofde_lab.planning.fond_policy import (
        CandidatePolicy,
        FONDProblem,
        PolicySemantics,
        check_candidate_policy,
    )

    p = env.payload
    err = _need(p, "initial", "goals", "transitions")
    if err:
        return refused(err, kind="fond")
    try:
        sem = PolicySemantics(p.get("semantics", "strong_cyclic"))
    except ValueError:
        return refused(f"unknown semantics {p.get('semantics')!r}", kind="fond")
    trans = {s: {a: list(o) for a, o in acts.items()} for s, acts in p["transitions"].items()}
    goals = set(p["goals"])
    problem = FONDProblem(
        str(p["initial"]),
        frozenset(goals),
        {(s, a): frozenset(o) for s, acts in trans.items() for a, o in acts.items()},
    )
    synthesised = "policy" not in p
    policy = (
        _fond_winning(trans, goals, sem is PolicySemantics.STRONG_CYCLIC)
        if synthesised
        else dict(p["policy"])
    )
    chk = check_candidate_policy(problem, CandidatePolicy(policy), semantics=sem)
    diag = {
        "semantics": sem.value,
        "synthesised": synthesised,
        "missing_policy_states": sorted(chk.missing_policy_states),
        "dead_end_states": sorted(chk.dead_end_states),
        "non_goal_cycle_states": sorted(chk.non_goal_cycle_states),
        "claim_ceiling": chk.claim_ceiling,
    }
    if not chk.valid:
        return Result(Status.INFEASIBLE, solver="fond_policy", diagnostics=diag)
    diag["policy"] = {s: policy[s] for s in sorted(chk.reachable_states) if s in policy}
    return Result(
        Status.PLAN,
        solver="fond_policy",
        actions=[[s, a] for s, a in sorted(diag["policy"].items())],
        diagnostics=diag,
    )


# ------------------------------------------------------------------- search


def _reachable(adj: Dict[str, List[str]], start: str, targets: Set[str]) -> bool:
    seen, q = {start}, deque([start])
    while q:
        s = q.popleft()
        if s in targets:
            return True
        for n in adj.get(s, []):
            if n not in seen:
                seen.add(n)
                q.append(n)
    return False


@register_kind("search", module=_MOD)
def _search(env: Envelope) -> Result:
    from autofde_lab import Value
    from autofde_lab.hub.domain.graph_domain.GraphDomain import GraphDomain

    p = env.payload
    err = _need(p, "initial", "targets", "edges")
    if err:
        return refused(err, kind="search")
    name = p.get("solver", "astar")
    if name not in SEARCH_SOLVERS:
        return refused(f"unknown search solver {name!r}", kind="search", known=list(SEARCH_SOLVERS))
    initial, targets = str(p["initial"]), {str(t) for t in p["targets"]}
    nsm: Dict[str, Dict[str, str]] = {}
    att: Dict[str, Dict[str, Dict[str, float]]] = {}
    adj: Dict[str, List[str]] = {}
    for src, act, dst, cost in p["edges"]:
        nsm.setdefault(src, {})[act] = dst
        att.setdefault(src, {})[act] = {"weight": float(cost)}
        adj.setdefault(src, []).append(dst)
        nsm.setdefault(dst, {})
        att.setdefault(dst, {})
    nsm.setdefault(initial, {})
    att.setdefault(initial, {})
    diag: Dict[str, Any] = {"initial": initial}
    if not _reachable(adj, initial, targets):
        diag["reason"] = "no target reachable from initial"
        return Result(Status.INFEASIBLE, solver=name, diagnostics=diag)

    class _Graph(GraphDomain):
        def _get_initial_state_(self):
            return initial

    def factory() -> GraphDomain:
        return _Graph(nsm, att, targets=targets)

    warnings.simplefilter("ignore")
    h = lambda d, s: Value(cost=0.0)  # noqa: E731
    if name == "astar":
        from autofde_lab.hub.solver.astar import Astar as S

        solver = S(domain_factory=factory, heuristic=h)
    elif name == "p_astar":
        from autofde_lab.hub.solver.p_astar import Astar as S

        solver = S(domain_factory=factory, heuristic=h)
    else:
        from autofde_lab.hub.solver.lrtastar import LRTAstar as S

        solver = S(domain_factory=factory, heuristic=h)
    with solver as s:
        if name == "lrtastar":
            s.solve()
        else:
            s.solve(from_memory=initial)
        if name == "p_astar":
            plan = list(s.get_plan())
        else:
            plan, cur = [], initial
            for _ in range(len(nsm) + 1):
                if cur in targets:
                    break
                a = s.get_next_action(cur)
                plan.append(a)
                cur = nsm[cur][a]
    cur, cost = initial, 0.0
    for a in plan:
        if a not in nsm.get(cur, {}):
            return Result(Status.NO_PLAN, solver=name,
                          diagnostics={**diag, "reason": f"plan action {a!r} inapplicable"})
        cost += att[cur][a]["weight"]
        cur = nsm[cur][a]
    if cur not in targets:
        return Result(Status.NO_PLAN, solver=name,
                      diagnostics={**diag, "reason": "plan does not end in a target"})
    diag["final_state"] = cur
    return Result(Status.PLAN, solver=name, actions=plan, cost=cost, diagnostics=diag)


# ---------------------------------------------------------------------- mdp


def _mdp_domains(nm, goals, initial, seed):
    from autofde_lab import TransitionOutcome, Value
    from autofde_lab.builders.domain.agent import MultiAgent
    from autofde_lab.builders.domain.concurrency import Sequential
    from autofde_lab.builders.domain.dynamics import Simulation
    from autofde_lab.builders.domain.events import Actions
    from autofde_lab.builders.domain.goals import Goals
    from autofde_lab.builders.domain.initialization import DeterministicInitialized
    from autofde_lab.builders.domain.memory import Markovian
    from autofde_lab.builders.domain.observability import FullyObservable
    from autofde_lab.builders.domain.value import PositiveCosts
    from autofde_lab.core import ImplicitSpace
    from autofde_lab.domains import Domain
    from autofde_lab.hub.domain.graph_domain.GraphDomain import (
        ActionSpace,
        GraphDomainUncertain,
    )
    from autofde_lab.hub.space.gym import ListSpace

    term = {s: s in goals for s in nm}

    class Uncertain(GraphDomainUncertain):
        def _get_initial_state_(self):
            return initial

    class _Hd(dict):
        def __hash__(self):
            return hash(frozenset(self.items()))

    class _MA(
        Domain, MultiAgent, Sequential, Simulation, Actions, DeterministicInitialized,
        Markovian, PositiveCosts, Goals, FullyObservable,
    ):
        def __init__(self):
            self.rng = random.Random(seed)

        def get_agents(self):
            return {"a"}

        def _get_initial_state_(self):
            return _Hd({"a": initial})

        def _state_sample(self, memory, action):
            st = memory["a"]
            if st in goals:
                return TransitionOutcome(state=_Hd({"a": st}), value={"a": Value(cost=0)},
                                         termination={"a": True}, info=None)
            d = nm[st][action["a"]]
            nxt = list(d)
            n = self.rng.choices(nxt, [d[x][0] for x in nxt], k=1)[0]
            return TransitionOutcome(state=_Hd({"a": n}), value={"a": Value(cost=d[n][1])},
                                     termination={"a": n in goals}, info=None)

        def get_agent_applicable_actions(self, memory, other_agents_actions, agent):
            st = memory[agent]
            return ActionSpace(["stay"] if st in goals else list(nm.get(st, {})))

        def _get_action_space_(self):
            return ImplicitSpace(lambda x: True)

        def _get_applicable_actions_from(self, memory):
            return ActionSpace([{"a": a} for a in nm.get(memory["a"], {})])

        def _get_goals_(self):
            return {"a": ListSpace(sorted(goals))}

        def _get_observation_space_(self):
            return ImplicitSpace(lambda x: True)

    return (lambda: Uncertain(nm, term, dict(term))), _MA, _Hd


@register_kind("mdp", module=_MOD)
def _mdp(env: Envelope) -> Result:
    from autofde_lab import Value

    p = env.payload
    err = _need(p, "initial", "goals", "transitions")
    if err:
        return refused(err, kind="mdp")
    name = p.get("solver", "lrtdp")
    if name not in MDP_SOLVERS:
        return refused(f"unknown mdp solver {name!r}", kind="mdp", known=list(MDP_SOLVERS))
    initial, goals = str(p["initial"]), {str(g) for g in p["goals"]}
    nm: Dict[str, Dict[str, Dict[str, tuple]]] = {}
    for s, acts in p["transitions"].items():
        nm[s] = {a: {s2: (float(pc[0]), float(pc[1])) for s2, pc in outs.items()}
                 for a, outs in acts.items()}
    for acts in list(nm.values()):
        for outs in acts.values():
            for s2 in outs:
                nm.setdefault(s2, {})
    nm.setdefault(initial, {})
    for g in goals:
        nm.setdefault(g, {})
    seed = int(env.options.get("seed", 0))
    budget = int(env.options.get("time_budget_ms", 3000))
    rollouts = int(env.options.get("rollout_budget", 2000))
    diag: Dict[str, Any] = {"initial": initial}
    # A proper policy (reach goal with probability 1) must exist, else value iteration diverges.
    support = {s: {a: list(o) for a, o in acts.items()} for s, acts in nm.items()}
    proper = _fond_winning(support, goals, cyclic=True)
    if initial not in goals and initial not in proper:
        diag["reason"] = "no policy reaches a goal with probability 1 from initial"
        return Result(Status.INFEASIBLE, solver=name, diagnostics=diag)

    random.seed(seed)
    warnings.simplefilter("ignore")
    factory, ma_cls, hd = _mdp_domains(nm, goals, initial, seed)
    zero = lambda d, s: Value(cost=0.0)  # noqa: E731
    cost: Optional[float] = None
    plan: List[str] = []
    if name == "martdp":
        from autofde_lab.hub.solver.martdp import MARTDP

        solver = MARTDP(
            domain_factory=ma_cls,
            heuristic=lambda d, s: ({a: Value(cost=0) for a in s}, {a: "stay" for a in s}),
            time_budget=budget, rollout_budget=min(rollouts, 500), max_depth=50,
            max_feasibility_trials=10,
        )
        pick = lambda s, st: s.get_next_action(hd({"a": st}))["a"]  # noqa: E731
    elif name == "lrtdp":
        from autofde_lab.hub.solver.lrtdp import LRTDP

        solver = LRTDP(domain_factory=factory, heuristic=zero, use_labels=True,
                       time_budget=budget, rollout_budget=rollouts, max_depth=100,
                       epsilon=1e-4, continuous_planning=False)
        pick = lambda s, st: s.get_next_action(st)  # noqa: E731
    elif name == "mdplp":
        from autofde_lab.hub.solver.mdplp import MDPLP

        solver = MDPLP(domain_factory=factory, heuristic=zero)
        pick = lambda s, st: s.get_next_action(st)  # noqa: E731
    else:
        from autofde_lab.hub.solver.mcts import MCTS

        solver = MCTS(domain_factory=factory, time_budget=budget, rollout_budget=rollouts,
                      max_depth=50, continuous_planning=False)
        pick = lambda s, st: s.get_next_action(st)  # noqa: E731
    with solver as s:
        s.solve(from_memory=initial if name != "martdp" else hd({"a": initial}))
        if name != "martdp":
            cost = float(s.get_utility(initial).cost)
        cur, seen = initial, set()
        while cur not in goals and cur not in seen and len(plan) < 4 * len(nm):
            seen.add(cur)
            a = pick(s, cur)
            plan.append(a)
            outs = nm[cur].get(a)
            if not outs:
                return Result(Status.NO_PLAN, solver=name,
                              diagnostics={**diag, "reason": f"policy action {a!r} inapplicable at {cur}"})
            cur = max(sorted(outs), key=lambda x: (outs[x][0], x in goals))
    diag["most_likely_path_end"] = cur
    diag["policy_first_action"] = plan[0] if plan else None
    return Result(Status.PLAN, solver=name, actions=plan, cost=cost, diagnostics=diag)
