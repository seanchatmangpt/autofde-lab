"""Domain-neutral action/precondition encoding for GraphLaw admission.

Any PDDL domain (durative or classical) plus problem plus VAL-style plan text becomes
(initial N-Triples state, [Action], goal N-Triples). Each ground atom ``(pred a b)`` is the
triple ``<urn:pddl:atom/pred/a/b> <urn:pddl:holds> <urn:pddl:true> .``; nothing in this module
names a domain, so enterprise-ops plans (K1/K6) and any other PDDL plan share one encoding.

Flattening of durative actions: a durative step becomes two ordered admission steps,
``<label>@start`` (pre: at-start and over-all atoms; effects: at-start) and ``<label>@end``
(pre: at-end and over-all atoms; effects: at-end). Events order by (time, end < til < start),
the same total order the replay executor uses. Timed initial literals become ``til@<t>`` steps.

Scope (reported in ``Encoding.skipped``, never silent): numeric comparisons and numeric effects
are not triples and are left to the numeric replay executor; ``or`` is resolved against the
encoder's own running state (first branch whose positive atoms hold; otherwise the first
branch, which GraphLaw then refuses).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from autofde_lab.law_bridge.graphlaw_admitter import Action

Atom = Tuple[str, ...]
NUMERIC_OPS = {"=", "<", ">", "<=", ">=", "+", "-", "*", "/"}
NUMERIC_EFFECTS = {"assign", "increase", "decrease", "scale-up", "scale-down"}


def sexp(text: str):
    toks = re.findall(r"\(|\)|[^\s()]+", re.sub(r";[^\n]*", "", text).lower())
    pos = 0

    def rd():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            out = []
            while toks[pos] != ")":
                out.append(rd())
            pos += 1
            return out
        return t

    return rd()


def typed(lst):
    """['a','b','-','t','c'] -> [('a','t'),('b','t'),('c','object')]"""
    out, pend, i = [], [], 0
    while i < len(lst):
        if lst[i] == "-":
            out += [(n, lst[i + 1]) for n in pend]
            pend, i = [], i + 2
        else:
            pend.append(lst[i])
            i += 1
    return out + [(n, "object") for n in pend]


def atom_triple(atom: Atom) -> str:
    return f"<urn:pddl:atom/{'/'.join(atom)}> <urn:pddl:holds> <urn:pddl:true> ."


@dataclass(frozen=True)
class Encoding:
    initial: str
    actions: Tuple[Action, ...]
    goal: str
    skipped: Tuple[str, ...] = ()
    # step index -> index of the plan line it came from (None for TIL steps)
    origin: Tuple[Optional[int], ...] = ()
    plan_lines: Tuple[str, ...] = ()

    def plan_index(self, step_index: Optional[int]) -> Optional[int]:
        if step_index is None or not 0 <= step_index < len(self.origin):
            return None
        return self.origin[step_index]


@dataclass
class _Ctx:
    state: set = field(default_factory=set)
    skipped: List[str] = field(default_factory=list)


def _bind(x, b):
    return b.get(x, x)


def _atoms(c, b, ctx: _Ctx, pos: List[Atom], neg: List[Atom]) -> None:
    """Collect the logical precondition atoms of condition `c` under binding `b`."""
    if not isinstance(c, list) or not c:
        return
    op = c[0]
    if op == "and":
        for y in c[1:]:
            _atoms(y, b, ctx, pos, neg)
    elif op == "not":
        inner = c[1]
        if isinstance(inner, list) and inner and inner[0] not in ({"and", "or", "not", "imply"} | NUMERIC_OPS):
            neg.append(tuple([inner[0]] + [_bind(a, b) for a in inner[1:]]))
        else:
            ctx.skipped.append("not-complex")
    elif op == "or":
        chosen = None
        for br in c[1:]:
            p: List[Atom] = []
            n: List[Atom] = []
            _atoms(br, b, ctx, p, n)
            if all(a in ctx.state for a in p) and not any(a in ctx.state for a in n):
                chosen = (p, n)
                break
            if chosen is None:
                chosen = (p, n)
        if chosen:
            pos += chosen[0]
            neg += chosen[1]
    elif op in NUMERIC_OPS:
        ctx.skipped.append(f"numeric:{op}")
    elif op in ("imply", "forall", "exists", "preference"):
        ctx.skipped.append(f"unsupported:{op}")
    else:
        pos.append(tuple([op] + [_bind(a, b) for a in c[1:]]))


def _effects(e, b, adds: List[Atom], dels: List[Atom], ctx: _Ctx) -> None:
    if not isinstance(e, list) or not e:
        return
    op = e[0]
    if op == "and":
        for y in e[1:]:
            _effects(y, b, adds, dels, ctx)
    elif op == "not":
        i = e[1]
        dels.append(tuple([i[0]] + [_bind(a, b) for a in i[1:]]))
    elif op in NUMERIC_EFFECTS:
        ctx.skipped.append(f"numeric-effect:{op}")
    elif op in ("when", "forall"):
        ctx.skipped.append(f"unsupported-effect:{op}")
    else:
        adds.append(tuple([op] + [_bind(a, b) for a in e[1:]]))


def _timed(x) -> List[Tuple[str, list]]:
    out: List[Tuple[str, list]] = []
    if not x:
        return out
    if x[0] == "and":
        for y in x[1:]:
            out += _timed(y)
    elif x[0] == "at":
        out.append((x[1], x[2]))
    elif x[0] == "over":
        out.append(("over", x[2]))
    return out


def _fmt(items: Sequence[Atom]) -> str:
    return "\n".join(dict.fromkeys(atom_triple(a) for a in items))


PLAN_RE = re.compile(r"^\s*([\d.]+)\s*:\s*\((.*)\)\s*(?:\[([\d.]+)\])?\s*$")


def parse_plan(text: str):
    out = []
    for ln in text.splitlines():
        ln = ln.split(";", 1)[0].strip().lower()
        if not ln:
            continue
        m = PLAN_RE.match(ln)
        if not m:
            raise ValueError(f"bad plan line: {ln!r}")
        toks = m.group(2).split()
        out.append((float(m.group(1)), toks[0], toks[1:], float(m.group(3)) if m.group(3) else 0.0))
    return out


def encode_pddl_plan(domain_text: str, problem_text: str, plan_text: str) -> Encoding:
    dom = sexp(domain_text)
    prob = sexp(problem_text)
    acts: Dict[str, dict] = {}
    for sec in dom[2:]:
        if sec[0] in (":durative-action", ":action"):
            a: dict = {"durative": sec[0] == ":durative-action"}
            i = 2
            while i < len(sec):
                a[sec[i][1:]] = sec[i + 1]
                i += 2
            a["params"] = [n for n, _ in typed(a.get("parameters", []))]
            acts[sec[1]] = a
    init: set = set()
    til: List[Tuple[float, list]] = []
    goal_c = None
    for sec in prob[2:]:
        if sec[0] == ":init":
            for e in sec[1:]:
                if e[0] == "=":
                    continue
                if e[0] == "at" and len(e) == 3 and not isinstance(e[1], list):
                    til.append((float(e[1]), e[2]))
                else:
                    init.add(tuple(e))
        elif sec[0] == ":goal":
            goal_c = sec[1]
    ctx = _Ctx(state=set(init))
    plan = parse_plan(plan_text)

    events = []  # (time, order, idx, kind, payload)
    for i, (t, name, args, dur) in enumerate(plan):
        events.append((t, 2, i, "start", (name, args, dur)))
        events.append((t + dur, 0, i, "end", None))
    for j, (t, e) in enumerate(til):
        events.append((t, 1, j, "til", e))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    last_plan_t = max((e[0] for e in events if e[3] in ("start", "end")), default=0.0)

    steps: List[Action] = []
    origin: List[Optional[int]] = []
    binds: Dict[int, dict] = {}
    for t, _o, idx, kind, pl in events:
        if kind == "til":
            if t > last_plan_t:
                continue  # outside the executed horizon
            adds: List[Atom] = []
            dels: List[Atom] = []
            _effects(pl, {}, adds, dels, ctx)
            steps.append(Action(f"til@{t:g}", add=_fmt(adds), delete=_fmt(dels)))
            origin.append(None)
        else:
            if kind == "start":
                name, args, _dur = pl
                a = acts.get(name)
                label = "(" + " ".join([name] + args) + ")"
                if a is None or len(args) != len(a["params"]):
                    # unknown action / arity: an unsatisfiable precondition names the defect
                    steps.append(Action(f"{label}@start",
                                        pre=atom_triple(("unknown-action-or-arity", name))))
                    origin.append(idx)
                    ctx.skipped.append(f"unbound:{name}")
                    binds[idx] = None  # type: ignore[assignment]
                    continue
                binds[idx] = dict(zip(a["params"], args))
            b = binds.get(idx)
            if b is None:
                continue
            name, args = plan[idx][1], plan[idx][2]
            a = acts[name]
            label = "(" + " ".join([name] + args) + ")"
            when = "start" if kind == "start" else "end"
            pos: List[Atom] = []
            neg: List[Atom] = []
            adds, dels = [], []
            if a["durative"]:
                for w, c in _timed(a.get("condition")):
                    if w == when or w == "over":
                        _atoms(c, b, ctx, pos, neg)
                for w, e in _timed(a.get("effect")):
                    if w == when:
                        _effects(e, b, adds, dels, ctx)
            elif kind == "start":
                _atoms(a.get("precondition", []), b, ctx, pos, neg)
                _effects(a.get("effect", []), b, adds, dels, ctx)
            else:
                continue  # classical action: single step
            steps.append(Action(f"{label}@{when}", pre=_fmt(pos), add=_fmt(adds),
                                delete=_fmt(dels),
                                pre_not=_fmt(neg)))
            origin.append(idx)
        # advance the encoder's own state so `or` resolves against the running state
        st = steps[-1]
        for line in st.delete.splitlines():
            ctx.state.discard(_parse_atom(line))
        for line in st.add.splitlines():
            ctx.state.add(_parse_atom(line))
    goal_pos: List[Atom] = []
    goal_neg: List[Atom] = []
    gctx = _Ctx(state=set(ctx.state))
    _atoms(goal_c or [], {}, gctx, goal_pos, goal_neg)
    ctx.skipped += [f"goal:{s}" for s in gctx.skipped]
    return Encoding(
        initial=_fmt(sorted(init)),
        actions=tuple(steps),
        goal=_fmt(goal_pos),
        skipped=tuple(sorted(set(ctx.skipped))),
        origin=tuple(origin),
        plan_lines=tuple(f"{t:g}: ({' '.join([n] + a)}) [{d:g}]" for t, n, a, d in plan),
    )


def _parse_atom(triple: str) -> Atom:
    iri = triple.split(">", 1)[0].split("urn:pddl:atom/", 1)[1]
    return tuple(iri.split("/"))
