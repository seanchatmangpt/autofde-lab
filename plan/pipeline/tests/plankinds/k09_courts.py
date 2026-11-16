"""K9: L8 mutation courts (courts/court.py table M) against the real planner and reach.py backends,
plus an aries-vs-reach differential."""
from __future__ import annotations

import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K9"
TITLE = "L8 PDDL mutation courts (aries vs delete-relaxation reach)"

ROOT = Path(__file__).resolve().parents[3]
COURTS = ROOT / "courts"
PLAN_ARG = COURTS / "plan_arg.sh"
REACH = COURTS / "reach.py"
DOM = ROOT / "spec" / "servengine_ideal_domain.pddl"
PROB = ROOT / "spec" / "problem_enterprise_ops.pddl"
VENV = ROOT / "planner" / ".venv" / "bin" / "python"

DIVERGENCES: list[str] = []   # filled by run(); read by the test/receipt


def _court():
    if str(COURTS) not in sys.path:
        sys.path.insert(0, str(COURTS))
    import court
    return court


def probe():
    for p in (PLAN_ARG, REACH, DOM, PROB, COURTS / "court.py"):
        if not p.is_file():
            return Skip(f"missing {p}", "restore courts/ and spec/")
    if not VENV.exists():
        return Skip("planner/.venv absent", "sh planner/run.sh (creates the aries venv)")
    return None


def cases():
    c = _court()
    out = [Case("baseline-aries", "PLAN", {"backend": "planner", "mid": 0}),
           Case("baseline-reach", "PLAN", {"backend": "reach", "mid": 0}),
           Case("baseline-differential", "PLAN", {"backend": "diff", "mid": 0})]
    for mid, inv, needle, op in c.M:
        for be in ("planner", "reach"):
            out.append(Case(f"M{mid:02d}-{be}-{inv}", "INFEASIBLE",
                            {"backend": be, "mid": mid, "needle": needle, "op": list(op)}))
        out.append(Case(f"M{mid:02d}-differential", "INFEASIBLE",
                        {"backend": "diff", "mid": mid, "needle": needle, "op": list(op)}))
    return out


_CACHE: dict = {}
_LOCK = threading.Lock()


def _mutant_text(c, mid, needle, op):
    if not mid:
        return PROB.read_text()
    text, err = c.mutate(PROB.read_text(), needle, tuple(op), mid)
    return None if err else text


def _solve_text(c, backend, text):
    """Real solve of `text`; memoized per (backend, text) so diff cases reuse the per-backend cases."""
    key = (backend, text)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    with tempfile.TemporaryDirectory() as d:
        pp = Path(d) / "problem.pddl"
        pp.write_text(text)
        res = c.solve(backend, str(pp))
    with _LOCK:
        _CACHE[key] = res
    return res


def _prefetch(c):
    """aries needs ~60s per unsolvable mutant: run all real planner solves concurrently, once."""
    if _CACHE.get("_prefetched"):
        return
    jobs = [(_mutant_text(c, 0, None, None))] + [_mutant_text(c, m, n, o) for m, _i, n, o in c.M]
    jobs = [t for t in jobs if t]
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        list(ex.map(lambda t: _solve_text(c, "planner", t), jobs))
    _CACHE["_prefetched"] = True


def run(case):
    c = _court()
    p = case.payload
    _prefetch(c)
    text = _mutant_text(c, p["mid"], p.get("needle"), p.get("op"))
    if text is None:
        return Outcome("UNSUPPORTED", "mutation inapplicable")
    if p["backend"] == "diff":
        a, r = _solve_text(c, "planner", text), _solve_text(c, "reach", text)
        if a != r:
            DIVERGENCES.append(f"M{p['mid']:02d} aries={a[:60]} reach={r[:60]}")
            return Outcome("NO_PLAN", f"DIVERGENCE aries={a[:60]} reach={r[:60]}")
        return Outcome("INFEASIBLE" if a == "UNSOLVABLE" else "PLAN", f"agree {a}")
    res = _solve_text(c, p["backend"], text)
    if res == "SOLVED":
        return Outcome("PLAN", res)
    if res == "UNSOLVABLE":
        return Outcome("INFEASIBLE", res)
    return Outcome("UNSUPPORTED", res[:160])
