"""K8: plan-replay executor (/Users/sac/plan/executor/run.py) over seeded mutations of the real plan."""
from __future__ import annotations

import random
import subprocess
import sys
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

DIVERGENCES: list[str] = []   # dup-* cases expected REFUSED (self-consuming) yet accepted
KIND = "K8"
TITLE = "plan-replay executor (fail-closed durative state machine)"

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "executor" / "run.py"
PLAN = ROOT / "planner" / "plan_solution.soln"
FX = ROOT / "executor" / "fixtures"


def probe():
    for p in (RUN, PLAN, FX / "servengine_ideal_domain.pddl", FX / "problem_enterprise_ops.pddl"):
        if not p.is_file():
            return Skip(f"missing {p}", "restore executor/ and planner/plan_solution.soln")
    return None


def _lines():
    return [ln for ln in PLAN.read_text().splitlines() if ln.strip()]


def _split(ln):
    t, rest = ln.split(": ", 1)
    body, _, dur = rest.partition(") [")
    return t, body[1:].split(), dur


def _join(t, toks, dur):
    return f"{t}: ({' '.join(toks)}) [{dur}"


def _preds(x, neg=None, out=None):
    out = set() if out is None else out
    if isinstance(x, list) and x:
        if x[0] == "not":
            _preds(x[1], True, out)
        elif isinstance(x[0], str):
            if x[0] in ("and", "at", "over", "forall", "when", "or"):
                for y in x[1:]:
                    if isinstance(y, list):
                        _preds(y, neg, out)
            else:
                out.add((x[0], bool(neg)))
    return out


def _self_consuming():
    sys.path.insert(0, str(ROOT / "executor"))
    from pddl import Domain
    dom = Domain((FX / "servengine_ideal_domain.pddl").read_text())
    res = set()
    for name, a in dom.actions.items():
        need = set(); dels = set()
        for when, c in a["cond"]:
            if when == "start":
                need |= {p for p, ng in _preds(c) if not ng}
        for when, e in a["eff"]:
            if when == "start":
                dels |= {p for p, ng in _preds(e) if ng}
        if need & dels:
            res.add(name)
    return res


def _seed():
    from jtbd_factories import seed_from_env
    return seed_from_env()


def cases():
    lines = _lines()
    n = len(lines)
    rng = random.Random(_seed())
    out = [Case("unchanged", "PLAN", {"plan": "\n".join(lines)})]
    # reorder: swap the action bodies of two positions (timestamps keep their slots); all pairs
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(pairs)
    for i, j in pairs:
        L = list(lines)
        ti, bi, di = _split(L[i]); tj, bj, dj = _split(L[j])
        if ti == tj:   # simultaneous actions: swapping bodies is the identical plan, not a mutation
            continue
        L[i] = _join(ti, bj, dj); L[j] = _join(tj, bi, di)
        out.append(Case(f"reorder-{i}-{j}", "REFUSED", {"plan": "\n".join(L)}))
    # drop: every position
    for i in rng.sample(range(n), n):
        out.append(Case(f"drop-{i}", "REFUSED", {"plan": "\n".join(lines[:i] + lines[i + 1:])}))
    # duplicate: every position (copy inserted right after the original, same timestamp). Expectation is
    # derived from the real domain: the copy starts in the same instant, so it is refused iff the action's
    # at-start effects delete a fact its own at-start condition requires; otherwise re-assertion is idempotent.
    selfconsuming = _self_consuming()
    for i in rng.sample(range(n), n):
        out.append(Case(f"dup-{i}", "REFUSED" if _split(lines[i])[1][0] in selfconsuming else "PLAN",
                        {"plan": "\n".join(lines[:i + 1] + [lines[i]] + lines[i + 1:])}))
    # swap args: first two arguments of every action that has >=2
    for i in rng.sample(range(n), n):
        t, toks, d = _split(lines[i])
        if len(toks) < 3 or toks[1] == toks[2]:
            continue
        toks[1], toks[2] = toks[2], toks[1]
        L = list(lines); L[i] = _join(t, toks, d)
        out.append(Case(f"swapargs-{i}", "REFUSED", {"plan": "\n".join(L)}))
    return out


def run(case):
    with tempfile.TemporaryDirectory() as d:
        plan = Path(d) / "plan.soln"
        plan.write_text(case.payload["plan"] + "\n")
        r = subprocess.run([sys.executable, str(RUN), str(plan), str(Path(d) / "r.jsonl")],
                           capture_output=True, text=True, timeout=120)
    tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
    detail = f"rc={r.returncode} {tail[0][:140]}"
    if r.returncode == 0:
        if case.id.startswith("dup-") and case.expect == "REFUSED":
            DIVERGENCES.append(f"{case.id} accepted: {detail}")
        return Outcome("PLAN", detail)
    if r.returncode in (1, 2):
        return Outcome("REFUSED", detail)
    return Outcome("UNSUPPORTED", detail)
