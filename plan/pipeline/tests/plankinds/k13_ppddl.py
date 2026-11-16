"""K13: PPDDL policy synthesis. `run` routes to the coprocessor mdp kind (exact value iteration);
`run_oracle` keeps the real `ferroplan-ppddl` binary as differential oracle."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from enterprise_pipeline import autofde_backend as backend
from plankinds import Case, Outcome, Skip

KIND = "K13"
TITLE = "probabilistic PPDDL (ferroplan-ppddl)"
ROOT = Path(os.environ.get("FERROPLAN_ROOT", "/Users/sac/ferroplan"))
BIN = ROOT / "target" / "release" / "ferroplan-ppddl"
DAM = ROOT / "examples" / "daily_agent_methods"
TIMEOUT_S = 120


def probe():
    if not Path(backend.AUTOFDE_VENV_PYTHON).exists():
        return Skip("autofde-lab venv absent", "cd /Users/sac/autofde-lab && uv sync")
    return None


def oracle_probe():
    if not BIN.exists():
        return Skip(f"ferroplan-ppddl binary absent: {BIN}",
                    f"cd {ROOT} && cargo build --release")
    if not (DAM / "domain.ppddl").exists():
        return Skip(f"examples missing under {DAM}", "")
    return None


def cases():
    catalog = DAM / "method-catalog.json"
    return [
        # dated snapshot: the real binary refuses it (typed grounding error, exit 1)
        Case("daily-2026-07-31", "REFUSED",
             {"domain": str(DAM / "domain.ppddl"),
              "problem": str(DAM / "problem-2026-07-31.ppddl"), "catalog": str(catalog)}),
        Case("daily-future", "PLAN",
             {"domain": str(DAM / "future" / "domain.ppddl"),
              "problem": str(DAM / "future" / "problem.ppddl")}),
        Case("daily-snapshot-2026-08-02", "REFUSED",
             {"domain": str(DAM / "snapshots" / "2026-08-02" / "domain.ppddl"),
              "problem": str(DAM / "snapshots" / "2026-08-02" / "problem.ppddl")}),
    ]


def run(case):
    cat = case.payload.get("catalog")
    if cat:
        json.loads(Path(cat).read_text())
    r = backend.solve("mdp", {"ppddl_domain_path": case.payload["domain"],
                              "ppddl_problem_path": case.payload["problem"]}, timeout=TIMEOUT_S)
    status = "NO_PLAN" if r.status == "INFEASIBLE" else r.status
    return Outcome(status, f"coprocessor:mdp solver={r.solver} cost={r.cost} "
                           f"p_goal={r.diagnostics.get('goal_probability')} {r.diagnostics.get('reason', '')}")


def run_oracle(case):
    sk = oracle_probe()
    if sk:
        return Outcome("SKIP", sk.reason)
    cat = case.payload.get("catalog")
    if cat:
        json.loads(Path(cat).read_text())  # catalog must be valid JSON
    try:
        r = subprocess.run([str(BIN), "-o", case.payload["domain"], "-f", case.payload["problem"]],
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return Outcome("UNSUPPORTED", f"timeout>{TIMEOUT_S}s")
    if r.returncode != 0:
        return Outcome("REFUSED", f"exit={r.returncode} {r.stderr.strip()[:200]}")
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return Outcome("REFUSED", f"exit=0 non-JSON stdout: {r.stdout[:120]!r}")
    if "solution" in j:
        return Outcome("PLAN", f"exit=0 standing={j.get('standing')} "
                               f"validation={j.get('execution', {}).get('validation')}")
    return Outcome("NO_PLAN", f"exit=0 keys={sorted(j)}")
