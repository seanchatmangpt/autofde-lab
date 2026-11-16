"""Temporal planning for the pipeline: autofde-lab coprocessor kind ``temporal_pddl``.

The old ``planner/plan.py`` path (unified-planning + aries in its own venv) is kept as the
differential ORACLE, selected with ``PLAN_ORACLE=1``.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .align import Skip

PLAN_ROOT = Path(__file__).resolve().parents[2]
RUN_SH = PLAN_ROOT / "planner" / "run.sh"
DOMAIN = PLAN_ROOT / "spec" / "servengine_ideal_domain.pddl"
LAB_PY = PLAN_ROOT.parent / ".venv" / "bin" / "python"
STEP = re.compile(r"^\s*(?:(\d+(?:\.\d+)?)\s*:\s*)?\(([^()]+)\)\s*(?:\[(\d+(?:\.\d+)?)\])?\s*$")


def oracle_enabled():
    return os.environ.get("PLAN_ORACLE") == "1"


def wait_for_planner(deadline_s=5.0):
    """Oracle path only: run.sh must be executable."""
    end = time.monotonic() + deadline_s
    while not (RUN_SH.exists() and RUN_SH.stat().st_mode & 0o111):
        if time.monotonic() >= end:
            raise Skip(f"planner absent at {RUN_SH} after {deadline_s}s deadline")
        time.sleep(0.1)  # SLEEP-CLASS: POLL-STEP (bounded by monotonic deadline)


def parse_plan(text):
    steps = []
    for line in text.splitlines():
        m = STEP.match(line)
        if m:
            t, body, dur = m.groups()
            name, *args = body.split()
            steps.append({"time": float(t) if t else None, "action": name, "args": args,
                          "duration": float(dur) if dur else None})
    return steps


def _oracle_python():
    """Oracle interpreter: PLAN_ORACLE_PY, else planner/.venv, else the autofde-lab venv."""
    env = os.environ.get("PLAN_ORACLE_PY")
    if env:
        return Path(env)
    venv = RUN_SH.parent / ".venv" / "bin" / "python"
    return venv if venv.exists() else LAB_PY


def _action_line(a):
    m = re.match(r"^([^(]+)\((.*)\)$", a["action"])
    name, args = (m.group(1), [x.strip() for x in m.group(2).split(",") if x.strip()]) if m \
        else (a["action"], [])
    return "%.3f: (%s) [%.3f]" % (a["start"], " ".join([name, *args]), a["duration"])


def solve_files(domain_path, problem_path, timeout=600, out_path=None):
    """Plan domain+problem. -> (rc, text) with rc 0 PLAN, 2 NO_PLAN, 3 invalid/refused, 4 blocked.

    text is run.sh-shaped (``t: (action args) [d]`` lines) so ``parse_plan`` reads either path."""
    if oracle_enabled():
        wait_for_planner()
        out = out_path or (str(problem_path) + ".soln")
        r = subprocess.run([str(_oracle_python()), "-u", str(RUN_SH.parent / "plan.py"),
                            str(domain_path), str(problem_path), str(out)],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    from .autofde_backend import solve
    r = solve("temporal_pddl", {"domain_path": str(domain_path), "problem_path": str(problem_path)},
              options={"timeout": float(os.environ.get("PLAN_SEARCH_TIMEOUT_S", "60"))}, timeout=timeout)
    if r.status == "PLAN":
        lines = [_action_line(a) for a in r.actions]
        text = "search status: %s\nplan end time: %s\n%s\n" % (
            r.diagnostics.get("engine_status"), r.cost, "\n".join(lines))
        if out_path:
            Path(out_path).write_text("\n".join(lines) + "\n")
        return 0, text
    text = "%s %s\n" % (r.status, r.diagnostics)
    return {"NO_PLAN": 2, "INFEASIBLE": 2, "BLOCKED": 4}.get(r.status, 3), text


def run_planner(problem_path, deadline_s=5.0, timeout=600):
    out = Path(str(problem_path) + ".soln")
    rc, text = solve_files(DOMAIN, problem_path, timeout=timeout, out_path=out)
    return rc, text, (parse_plan(text) if rc == 0 else [])
