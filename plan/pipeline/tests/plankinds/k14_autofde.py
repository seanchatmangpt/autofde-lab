"""K14 autofde-lab: real entry points invoked via the in-repo autofde-lab venv python."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K14"
TITLE = "autofde-lab (classical PDDL engine, FOND policy check)"
REPO = Path(__file__).resolve().parents[4]
PY = str(REPO / ".venv/bin/python")
BLOCKS = REPO / "tests/domains/python/pddl_domains/blocks"
UNSUPPORTED_KINDS = ["SAT/SMT", "behavior trees", "executable state machine", "replanning",
                     "preference planning", "fast-downward", "VAL"]

_UNSOLVABLE = ("(define (problem U) (:domain BLOCKS) (:objects A B) (:init (ONTABLE A) (ONTABLE B)"
               " (CLEAR A) (CLEAR B) (HANDEMPTY)) (:goal (AND (ON A B) (ON B A))))\n")

_FOND = r'''
import json, sys
from autofde_lab.planning.fond_policy import *
a = json.loads(sys.argv[1])
p = FONDProblem("s0", frozenset({"g"}), {("s0","go"): frozenset({"s0","g"})})
pol = CandidatePolicy(a["policy"])
r = check_candidate_policy(p, pol, semantics=PolicySemantics(a["sem"]))
print(json.dumps({"valid": r.valid, "missing": sorted(r.missing_policy_states)}))
'''


def probe() -> Skip | None:
    if not (REPO / ".venv").is_dir():
        return Skip(f"{REPO}/.venv absent", f"cd {REPO} && uv sync")
    r = subprocess.run([PY, "-c",
                        "import autofde_lab.fabric.pddl_engine"], capture_output=True, text=True)
    if r.returncode:
        return Skip(f"autofde_lab import failed: {r.stderr.strip()[-200:]}", f"cd {REPO} && uv sync")
    return None


def cases() -> list[Case]:
    return [
        Case("pddl-blocks-3", "PLAN", {"kind": "pddl", "domain": str(BLOCKS / "domain.pddl"),
                                       "problem": str(BLOCKS / "probBLOCKS-3-0.pddl")}),
        Case("pddl-unsolvable", "NO_PLAN", {"kind": "pddl", "domain": str(BLOCKS / "domain.pddl"),
                                            "problem_text": _UNSOLVABLE}),
        Case("pddl-missing-domain", "REFUSED", {"kind": "pddl", "domain": "/nonexistent/domain.pddl",
                                                "problem": str(BLOCKS / "probBLOCKS-3-0.pddl")}),
        Case("fond-strong-cyclic-valid", "PLAN", {"kind": "fond", "sem": "strong_cyclic",
                                                  "policy": {"s0": "go"}}),
        Case("fond-strong-invalid", "INFEASIBLE", {"kind": "fond", "sem": "strong",
                                                   "policy": {"s0": "go"}}),
        Case("fond-empty-policy", "INFEASIBLE", {"kind": "fond", "sem": "strong_cyclic", "policy": {}}),
    ]


def classify_pddl_exit(returncode: int, stderr: str) -> str:
    """A Python traceback (e.g. AttributeError) exits rc=1 like a clean no-plan; keep it distinct."""
    if "Traceback (most recent call last)" in stderr:
        return "CRASH"
    return {0: "PLAN", 1: "NO_PLAN", 2: "REFUSED"}.get(returncode, "REFUSED")


def _uv(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], capture_output=True, text=True)


def run(case: Case) -> Outcome:
    p = case.payload
    if p["kind"] == "pddl":
        with tempfile.TemporaryDirectory() as d:
            prob = p.get("problem")
            if prob is None:
                prob = str(Path(d) / "problem.pddl")
                Path(prob).write_text(p["problem_text"])
            plan = Path(d) / "plan.txt"
            r = _uv("-m", "autofde_lab.fabric.pddl_engine", p["domain"], prob, str(plan))
            status = classify_pddl_exit(r.returncode, r.stderr)
            if status == "CRASH":
                return Outcome(status, f"rc={r.returncode} {r.stderr.strip()[-200:]}")
            body = plan.read_text() if plan.exists() else ""
            return Outcome(status, f"rc={r.returncode} {r.stdout.strip()[-120:]}", body.strip())
    r = _uv("-c", _FOND, json.dumps(p))
    if r.returncode:
        if "Traceback (most recent call last)" in r.stderr:
            return Outcome("CRASH", f"rc={r.returncode} {r.stderr.strip()[-200:]}")
        return Outcome("REFUSED", f"rc={r.returncode} {r.stderr.strip()[-150:]}")
    res = json.loads(r.stdout.strip().splitlines()[-1])
    return Outcome("PLAN" if res["valid"] else "INFEASIBLE", r.stdout.strip())


def run_via_backend(case: Case) -> Outcome:
    """Same case through the autofde_backend seam (coprocessor kinds pddl / fond)."""
    from enterprise_pipeline import autofde_backend as ab
    p = case.payload
    if p["kind"] == "pddl":
        pl = {"domain_path": p["domain"]}
        if "problem" in p:
            pl["problem_path"] = p["problem"]
        else:
            pl["problem_text"] = p["problem_text"]
        r = ab.solve("pddl", pl)
        return Outcome(r.status, f"backend rc={r.exit_code}", "\n".join(map(str, r.actions)))
    pol = p["policy"]
    r = ab.solve("fond", {"semantics": p["sem"], "initial": "s0", "goals": ["g"],
                          "transitions": {"s0": {"go": ["s0", "g"]}}, "policy": pol})
    return Outcome(r.status, f"backend rc={r.exit_code}")
