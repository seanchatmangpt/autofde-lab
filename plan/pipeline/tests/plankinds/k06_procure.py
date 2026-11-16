"""K6: ProcurePass supplier chooser (CP-SAT) and the procure PDDL pair (aries)."""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K6"
TITLE = "ProcurePass CP-SAT + PDDL pair"
ROOT = Path(__file__).resolve().parents[3]
PP = ROOT / "procurepass"
RUN = ROOT / "planner" / "run.sh"
HINT = "install uv; sh planner/run.sh bootstraps planner/.venv (aries); ortools via `uv run --with ortools`"
BASE = json.loads((PP / "scenario_compressor.json").read_text())
REQUIRED = ["sla_minutes", "nte_limit", "labor_cost", "markup_pct", "diagnose_minutes",
            "install_minutes", "travel_minutes", "options"]
PROBLEMS = {"in_nte": "problem_compressor_in_nte.pddl", "change_order": "problem_compressor_over_nte.pddl"}


def probe():
    if not shutil.which("uv"):
        return Skip("uv not found; cannot provision ortools", HINT)
    if not (ROOT / "planner" / ".venv" / "bin" / "python").exists():
        return Skip("planner/.venv missing (aries)", HINT)
    return None


def cases():
    import jtbd_factories as jf
    jf.reseed(jf.seed_from_env())
    r = jf.rg()
    total = BASE["labor_cost"] + BASE["options"][0]["part_cost"] * (100 + BASE["markup_pct"]) // 100
    fast_lead = BASE["options"][0]["lead_minutes"]
    out = []

    def add(cid, expect, req, **extra):
        out.append(Case(cid, expect, {"req": req, "expect_path": extra.get("path"), "reason": extra.get("reason"),
                                      "pddl": extra.get("pddl")}))
    q = copy.deepcopy(BASE); q["nte_limit"] = r.randint(total, 2 * total)
    add("cpsat_in_nte", "PLAN", q, path="in_nte")
    q = copy.deepcopy(BASE); q["nte_limit"] = r.randint(BASE["labor_cost"], total - 1)
    add("cpsat_change_order", "PLAN", q, path="change_order")
    q = copy.deepcopy(BASE); q["sla_minutes"] = r.randint(1, fast_lead)
    add("cpsat_lead_time_exceeds_sla", "INFEASIBLE", q, reason="LEAD_TIME_EXCEEDS_SLA")
    q = copy.deepcopy(BASE); q["options"] = []
    add("cpsat_no_options", "INFEASIBLE", q, reason="NO_OPTIONS")
    q = copy.deepcopy(BASE); del q[r.choice(REQUIRED)]
    add("cpsat_missing_fields", "REFUSED", q, reason="MISSING_FIELDS")
    for path in PROBLEMS:
        add(f"pddl_{path}", "PLAN", None, path=path, pddl=PROBLEMS[path])
    return out


def pddl_request(problem_file: str) -> dict:
    """CP-SAT request equivalent to a procure PDDL problem, every number parsed from the file."""
    t = (PP / problem_file).read_text()
    g = lambda pat: int(re.search(pat, t)[1])
    lead = g(r"part-lead-time \w+\) (\d+)")
    diag = g(r"diagnose-duration \w+\) (\d+)")
    inst = g(r"install-duration \w+\) (\d+)")
    return {"sla_minutes": 4320, "nte_limit": g(r"wo-nte-limit \w+\) (\d+)"),
            "labor_cost": g(r"wo-labor-cost \w+\) (\d+)"), "markup_pct": g(r"part-markup \w+\) (\d+)") - 100,
            "diagnose_minutes": diag, "install_minutes": inst, "travel_minutes": 0,
            "options": [{"supplier": "s", "warehouse": "w", "part_cost": g(r"part-cost \w+\) (\d+)"), "ship_cost": 0,
                         "lead_minutes": lead, "slots": [{"start": diag + lead, "fee": 0}]}]}


def cpsat(req: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "req.json"
        f.write_text(json.dumps(req))
        p = subprocess.run([sys.executable, str(PP / "supplier_cpsat.py"), str(f)],
                           capture_output=True, text=True, timeout=300, cwd=PP)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"status": "ERROR", "reason": (p.stderr or p.stdout)[-300:]}


def pddl_path(problem_file: str) -> tuple[str, str]:
    """(status, path) from aries: path is change_order iff the plan spawns a change order."""
    with tempfile.TemporaryDirectory() as td:
        soln = Path(td) / "s.soln"
        p = subprocess.run(["sh", str(RUN), str(PP / "procure_domain.pddl"), str(PP / problem_file), str(soln)],
                           capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            return ("NO_PLAN" if p.returncode == 2 else "UNSUPPORTED", "")
        txt = soln.read_text()
    return "PLAN", ("change_order" if "spawn-change-order" in txt else "in_nte")


def run(case):
    pl = case.payload
    if pl["pddl"]:
        st, path = pddl_path(pl["pddl"])
        return Outcome(st, f"path={path}")
    res = cpsat(pl["req"])
    s = res.get("status")
    if s == "OPTIMAL":
        return Outcome("PLAN", f"path={res['path']}")
    if s == "INFEASIBLE":
        return Outcome("INFEASIBLE", f"reason={res['reason']}")
    if s == "INVALID":
        return Outcome("REFUSED", f"reason={res['reason']}")
    return Outcome("UNSUPPORTED", f"{s} {res.get('reason')}")
