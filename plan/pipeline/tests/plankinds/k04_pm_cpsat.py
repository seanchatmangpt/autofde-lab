"""K4: CP-SAT PM sweep (pm/sweep_scheduler.py) on instances from pm/gen_problem.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K4"
TITLE = "CP-SAT PM sweep scheduler"
PM = Path(__file__).resolve().parents[3] / "pm"
HINT = "install uv (https://docs.astral.sh/uv/); ortools is fetched by `uv run --with ortools`"
sys.path.insert(0, str(PM)) if str(PM) not in sys.path else None
from gen_problem import gen  # noqa: E402

CADENCE = "monthly"
WINDOW = 30  # gen_problem.CAD[monthly]


def _rg():
    import jtbd_factories as jf
    return jf.rg()


def draw_instances() -> dict:
    """{name: (params, expect_k4, expect_k5)}; reseeded from PLAN_TEST_SEED, no literal values."""
    import jtbd_factories as jf
    jf.reseed(jf.seed_from_env())
    r = _rg()

    def base(**over):
        p = dict(n_assets=r.randint(2, 3), cadences=[CADENCE], horizon=r.randint(2 * WINDOW, 3 * WINDOW - 1),
                 n_providers=2, n_sites=r.randint(1, 2), capacity=r.randint(2, 4), blackouts={})
        p.update(over)
        return p
    short = sorted(r.sample(range(0, WINDOW), 2))
    return {
        "feasible": (base(), "PLAN", "PLAN"),
        "feasible_short_blackout": (base(blackouts={"all": short}), "PLAN", "PLAN"),
        "infeasible_capacity": (base(capacity=0), "INFEASIBLE", "NO_PLAN"),
        # PDDL encoding (gen_problem.to_pddl) drops blackouts -> registered divergence KD-PM-01
        "infeasible_blackout_window": (base(blackouts={"all": list(range(0, WINDOW))}), "INFEASIBLE", "PLAN"),
    }


def build(params: dict) -> dict:
    return gen(params["n_assets"], params["cadences"], params["horizon"], params["n_providers"],
               params["n_sites"], params["capacity"], params["blackouts"], seed=1)


def probe():
    if not (PM / "sweep_scheduler.py").exists():
        return Skip("pm/sweep_scheduler.py missing", "restore pm/")
    return None


def cases():
    return [Case(n, e4, {"name": n, "params": p}) for n, (p, e4, _e5) in draw_instances().items()]


def run(case):
    inst = build(case.payload["params"])
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "inst.json"
        f.write_text(json.dumps(inst))
        p = subprocess.run([sys.executable, str(PM / "sweep_scheduler.py"), str(f)], capture_output=True, text=True, timeout=300, cwd=PM)
    word = (p.stdout.split() or ["?"])[0]
    st = {"OPTIMAL": "PLAN", "FEASIBLE": "PLAN", "INFEASIBLE": "INFEASIBLE"}.get(word, "UNSUPPORTED")
    return Outcome(st, f"rc={p.returncode} {p.stdout.strip()}" + (f" err={p.stderr[-200:]}" if p.returncode not in (0, 3) else ""))
