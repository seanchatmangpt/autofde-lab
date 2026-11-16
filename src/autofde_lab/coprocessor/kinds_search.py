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
    if "hddl_domain_text" in p or "hddl_domain_path" in p:
        p, bad = _fond_from_hddl(p, env)
        if bad is not None:
            return bad
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
    if "ppddl_domain_text" in p or "ppddl_domain_path" in p:
        return _mdp_from_ppddl(env)
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


# ----------------------------------------------------------- lane M3 additions
# HDDL-FOND ("fond" with hddl_* payload) and PPDDL ("mdp" with ppddl_* payload).
# Both ground a small propositional/typed fragment into an explicit transition
# system, then reuse the fond fixpoint / an exact value iteration.

import itertools
import re

_SEXP_TOK = re.compile(r"[()]|[^\s()]+")


def _sexp(text: str):
    text = re.sub(r";[^\n]*", "", text).lower()
    stack: List[list] = [[]]
    for tok in _SEXP_TOK.findall(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if len(stack) < 2:
                raise ValueError("unbalanced ')'")
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced '('")
    return stack[0]


def _section(form, key):
    return [x for x in form if isinstance(x, list) and x and x[0] == key]


def _text_of(payload, role, prefix):
    t = payload.get(f"{prefix}{role}_text")
    if t is None and payload.get(f"{prefix}{role}_path"):
        with open(payload[f"{prefix}{role}_path"], encoding="utf-8") as fh:
            t = fh.read()
    return t


def _typed_list(items):
    """['a','b','-','t','c'] -> [('a','t'),('b','t'),('c','object')]"""
    out, pend, i = [], [], 0
    while i < len(items):
        if items[i] == "-":
            out += [(n, items[i + 1]) for n in pend]
            pend, i = [], i + 2
        else:
            pend.append(items[i])
            i += 1
    return out + [(n, "object") for n in pend]


def _subst(x, b):
    if isinstance(x, list):
        return [_subst(y, b) for y in x]
    return b.get(x, x)


def _atom(x):
    return x[0] + "(" + ",".join(x[1:]) + ")"


def _cond(c, pos, neg, num):
    if not c:
        return
    h = c[0]
    if h == "and":
        for y in c[1:]:
            _cond(y, pos, neg, num)
    elif h == "not":
        inner = c[1]
        if inner and inner[0] in ("=", ">", "<", ">=", "<="):
            raise ValueError("negated numeric condition unsupported")
        neg.add(_atom(inner))
    elif h in (">", "<", ">=", "<=", "="):
        f, v = c[1], c[2]
        if isinstance(f, list) and not isinstance(v, list):
            num.append((_atom(f), h, float(v)))
        else:
            raise ValueError(f"unsupported numeric condition {c}")
    else:
        pos.add(_atom(c))


def _eff(e):
    """-> [(prob, adds, dels, deltas{fluent: ('inc'|'dec'|'set', v)})] (product over 'and')."""
    if not e:
        return [(1.0, frozenset(), frozenset(), ())]
    h = e[0]
    if h == "and":
        outs = [(1.0, frozenset(), frozenset(), ())]
        for y in e[1:]:
            nxt = []
            for (p, a, d, n), (p2, a2, d2, n2) in itertools.product(outs, _eff(y)):
                nxt.append((p * p2, a | a2, d | d2, n + n2))
            outs = nxt
        return outs
    if h == "not":
        return [(1.0, frozenset(), frozenset([_atom(e[1])]), ())]
    if h in ("increase", "decrease", "assign"):
        return [(1.0, frozenset(), frozenset(), ((_atom(e[1]), h, float(e[2])),))]
    if h == "probabilistic":
        rest, outs, tot, i = e[1:], [], 0.0, 0
        while i < len(rest):
            p = float(rest[i])
            tot += p
            outs += [(p * q, a, d, n) for q, a, d, n in _eff(rest[i + 1])]
            i += 2
        if tot > 1 + 1e-9:
            raise ValueError("probabilities exceed 1")
        if tot < 1 - 1e-9:
            outs.append((1.0 - tot, frozenset(), frozenset(), ()))
        return outs
    if h == "oneof":
        k = len(e) - 1
        return [(1.0 / k, a, d, n) for y in e[1:] for _, a, d, n in _eff(y)]
    if h in ("when", "forall"):
        raise ValueError(f"unsupported effect construct {h!r}")
    return [(1.0, frozenset([_atom(e)]), frozenset(), ())]


def _ground(dom, prob, task_free=True):
    """Ground actions of a parsed (define (domain ..)) / problem pair."""
    objs = _typed_list(next(iter(_section(prob, ":objects")), [":objects"])[1:])
    consts = _typed_list(next(iter(_section(dom, ":constants")), [":constants"])[1:])
    objs = consts + objs
    parents = {"object": None}
    for ty in _section(dom, ":types"):
        for n, par in _typed_list(ty[1:]):
            parents[n] = par

    def is_a(t, want):
        while t is not None:
            if t == want:
                return True
            t = parents.get(t)
        return want == "object"

    gacts = []
    for act in _section(dom, ":action"):
        name = act[1]
        kv = {act[i]: act[i + 1] for i in range(2, len(act) - 1, 2)}
        params = _typed_list(kv.get(":parameters", []))
        pools = [[o for o, t in objs if is_a(t, pt)] for _, pt in params]
        size = 1
        for p in pools:
            size *= max(len(p), 1)
        if size > 500_000:
            raise ValueError(f"grounding bound exceeded for action {name}")
        for combo in itertools.product(*pools):
            b = {v: c for (v, _), c in zip(params, combo)}
            pos, neg, num = set(), set(), []
            _cond(_subst(kv.get(":precondition", []), b), pos, neg, num)
            gacts.append((f"{name} {' '.join(combo)}".strip(), pos, neg, num,
                          _eff(_subst(kv.get(":effect", []), b))))
    init = next(iter(_section(prob, ":init")), [":init"])[1:]
    facts, fluents = set(), {}
    for x in init:
        if x and x[0] == "=":
            fluents[_atom(x[1])] = float(x[2])
        else:
            facts.add(_atom(x))
    goal = next(iter(_section(prob, ":goal")), [":goal", []])[1]
    gpos, gneg, gnum = set(), set(), []
    _cond(goal, gpos, gneg, gnum)
    metric = next(iter(_section(prob, ":metric")), None)
    return gacts, facts, fluents, (gpos, gneg, gnum), metric


_OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b, "=": lambda a, b: a == b}


def _explore(gacts, facts, fluents, goal, cost_fluent, max_states, with_cost):
    """BFS -> (states list, index, edges{idx: [(action, [(p, cost, nxt)])]}, goal flags)."""
    gpos, gneg, gnum = goal
    fl_keys = sorted(k for k in fluents if k != cost_fluent)
    start = (frozenset(facts), tuple(fluents[k] for k in fl_keys))
    idx, states, edges, queue = {start: 0}, [start], {}, deque([0])
    is_goal = {}

    def holds(fs, fv, pos, neg, num):
        if not pos <= fs or neg & fs:
            return False
        val = dict(zip(fl_keys, fv))
        return all(_OPS[op](val.get(f, 0.0), v) for f, op, v in num)

    while queue:
        i = queue.popleft()
        fs, fv = states[i]
        is_goal[i] = holds(fs, fv, gpos, gneg, gnum)
        edges[i] = []
        if is_goal[i]:
            continue
        for name, pos, neg, num, outs in gacts:
            if not holds(fs, fv, pos, neg, num):
                continue
            res = []
            for p, adds, dels, deltas in outs:
                val = dict(zip(fl_keys, fv))
                c = 0.0
                for f, op, v in deltas:
                    if f == cost_fluent:
                        c += v if op == "increase" else -v if op == "decrease" else 0.0
                    elif op == "increase":
                        val[f] = val.get(f, 0.0) + v
                    elif op == "decrease":
                        val[f] = val.get(f, 0.0) - v
                    else:
                        val[f] = v
                ns = ((fs - dels) | adds, tuple(val.get(k, 0.0) for k in fl_keys))
                if ns not in idx:
                    if len(states) >= max_states:
                        raise OverflowError(f"state bound exceeded ({max_states})")
                    idx[ns] = len(states)
                    states.append(ns)
                    queue.append(idx[ns])
                res.append((p, c if with_cost and cost_fluent else (1.0 if with_cost else 0.0),
                            idx[ns]))
            edges[i].append((name, res))
    return states, edges, is_goal


def _method_names_ok(dom):
    known = {t[1] for t in _section(dom, ":task")} | {a[1] for a in _section(dom, ":action")}
    bad = []

    def walk(x):
        if isinstance(x, list) and x:
            if x[0] in ("and",):
                for y in x[1:]:
                    walk(y)
            elif len(x) == 2 and isinstance(x[1], list) and isinstance(x[0], str) \
                    and x[0] not in ("and",) and x[1] and isinstance(x[1][0], str):
                walk(x[1])  # labelled subtask (label (name args))
            elif isinstance(x[0], str) and x[0] not in known:
                bad.append(x[0])

    for m in _section(dom, ":method"):
        kv = {m[i]: m[i + 1] for i in range(2, len(m) - 1, 2) if isinstance(m[i], str)}
        walk(kv.get(":ordered-subtasks", []))
    return sorted(set(bad))


def _fond_from_hddl(p, env):
    """HDDL with oneof effects -> explicit transitions payload (methods validated, not enforced)."""
    dt, pt = _text_of(p, "domain", "hddl_"), _text_of(p, "problem", "hddl_")
    if dt is None or pt is None:
        return None, refused("hddl_domain_text/path and hddl_problem_text/path required", kind="fond")
    try:
        dom, prob = _sexp(dt)[0], _sexp(pt)[0]
        bad = _method_names_ok(dom)
        if bad:
            return None, refused(f"subtask(s) neither task nor action: {bad}", kind="fond")
        gacts, facts, fluents, goal, _ = _ground(dom, prob)
        states, edges, is_goal = _explore(gacts, facts, fluents, goal, None,
                                          int(env.options.get("max_states", 100000)), False)
    except (ValueError, OverflowError, IndexError, KeyError) as exc:
        return None, refused(f"cannot ground: {type(exc).__name__}: {exc}", kind="fond")
    name = lambda i: "|".join(sorted(states[i][0]))  # noqa: E731
    trans: Dict[str, Dict[str, List[str]]] = {}
    for i, acts in edges.items():
        trans[name(i)] = {a: sorted({name(n) for _, _, n in outs}) for a, outs in acts}
    goals = [name(i) for i, g in is_goal.items() if g]
    return {"initial": name(0), "goals": goals, "transitions": trans,
            "semantics": p.get("semantics", "strong_cyclic")}, None


def _mdp_from_ppddl(env):
    p = env.payload
    dt, pt = _text_of(p, "domain", "ppddl_"), _text_of(p, "problem", "ppddl_")
    if dt is None or pt is None:
        return refused("ppddl_domain_text/path and ppddl_problem_text/path required", kind="mdp")
    try:
        dom, prob = _sexp(dt)[0], _sexp(pt)[0]
        gacts, facts, fluents, goal, metric = _ground(dom, prob)
        cost_fluent = "total-cost()" if metric and "total-cost" in str(metric) else None
        states, edges, is_goal = _explore(gacts, facts, fluents, goal, cost_fluent,
                                          int(env.options.get("max_states", 100000)), True)
    except (ValueError, OverflowError, IndexError, KeyError) as exc:
        return refused(f"cannot ground: {type(exc).__name__}: {exc}", kind="mdp")
    n = len(states)
    pmax = [1.0 if is_goal[i] else 0.0 for i in range(n)]
    for _ in range(10000):
        delta = 0.0
        for i in range(n):
            if is_goal[i]:
                continue
            best = max((sum(q * pmax[s] for q, _, s in outs) for _, outs in edges[i]), default=0.0)
            delta = max(delta, abs(best - pmax[i]))
            pmax[i] = best
        if delta < 1e-13:
            break
    if pmax[0] <= 1e-12:
        return Result(Status.INFEASIBLE, solver="ppddl_vi",
                      diagnostics={"states": n, "goal_probability": 0.0})
    opt = {}
    for i in range(n):
        if is_goal[i] or pmax[i] <= 1e-12:
            continue
        opt[i] = [(a, outs) for a, outs in edges[i]
                  if sum(q * pmax[s] for q, _, s in outs) >= pmax[i] - 1e-9]
    val = [0.0] * n
    for _ in range(200000):
        delta = 0.0
        for i, acts in opt.items():
            best = min(sum(q * (c + val[s]) for q, c, s in outs) for _, outs in acts)
            delta = max(delta, abs(best - val[i]))
            val[i] = best
        if delta < 1e-12:
            break
    policy = {i: min(acts, key=lambda ao: (sum(q * (c + val[s]) for q, c, s in ao[1]), ao[0]))[0]
              for i, acts in opt.items()}
    # greedy most-likely path from the initial state
    path, cur, seen = [], 0, set()
    while cur in policy and cur not in seen:
        seen.add(cur)
        a = policy[cur]
        path.append(a)
        outs = dict(edges[cur])[a]
        cur = max(outs, key=lambda o: (o[0], o[2] in policy or is_goal[o[2]]))[2]
    reach, q = {0}, deque([0])
    while q:
        i = q.popleft()
        if i in policy:
            for _, _, s in dict(edges[i])[policy[i]]:
                if s not in reach:
                    reach.add(s)
                    q.append(s)
    diag = {"states": n, "goal_probability": pmax[0], "policy_entries": sum(1 for i in reach if i in policy),
            "initial_action": path[0] if path else None}
    return Result(Status.PLAN, solver="ppddl_vi", actions=[[a] for a in path],
                  cost=val[0], diagnostics=diag)
