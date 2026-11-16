"""K5: the K4 instance as PDDL (gen_problem.to_pddl) solved by aries via planner/run.sh."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip
from . import k04_pm_cpsat as k4
from enterprise_pipeline import planner
from gen_problem import to_pddl

KIND = "K5"
TITLE = "PM sweep PDDL (aries)"
ROOT = Path(__file__).resolve().parents[3]
DOMAIN = ROOT / "pm" / "pm_domain.pddl"
HINT = "uv venv .venv at the autofde-lab root (coprocessor temporal_pddl); PLAN_ORACLE=1 uses planner/plan.py"


def probe():
    from enterprise_pipeline import autofde_backend as ab
    if not os.path.exists(ab.backend_python()):
        return Skip("autofde-lab venv python missing", HINT)
    if not DOMAIN.exists():
        return Skip("pm/pm_domain.pddl missing", "restore pm/")
    return None


def cases():
    return [Case(n, e5, {"name": n, "params": p}) for n, (p, _e4, e5) in k4.draw_instances().items()]


def solve_pddl(params: dict) -> Outcome:
    inst = k4.build(params)
    with tempfile.TemporaryDirectory() as td:
        prob = Path(td) / "p.pddl"
        prob.write_text(to_pddl(inst))
        rc, out = planner.solve_files(DOMAIN, prob, timeout=300, out_path=Path(td) / "s.soln")
    tail = " ".join(out.strip().splitlines()[:1])
    if rc == 0:
        return Outcome("PLAN", f"rc=0 {tail}")
    if rc == 2:
        return Outcome("NO_PLAN", f"rc=2 {tail}")
    return Outcome("UNSUPPORTED", f"rc={rc} {tail}")


def run(case):
    return solve_pddl(case.payload["params"])
