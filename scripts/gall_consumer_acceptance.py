"""Consumer acceptance: K14 cases + every coprocessor kind + graphlaw round-trip.

Run: cd /Users/sac/plan && PYTHONPATH=pipeline:pipeline/tests \
     uv run --quiet python /Users/sac/autofde-lab/scripts/gall_consumer_acceptance.py
Each coprocessor kind has a PLAN case and an anti-vacuity REFUSED/INFEASIBLE/NO_PLAN case.
Exit 1 on any mismatch, any SKIP, any absent module, or a Traceback in a child.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from plankinds import k14_autofde as k14

REPO = Path("/Users/sac/autofde-lab")
PY = str(REPO / ".venv/bin/python")
BLOCKS = REPO / "tests/domains/python/pddl_domains/blocks"
HTN = REPO / "tests/domains/htn_fixtures"
KIND_FILES = {
    "pddl": "kinds_pddl", "temporal_pddl": "kinds_pddl", "htn": "kinds_pddl",
    "rcpsp": "kinds_planning", "cp": "kinds_planning", "portfolio": "kinds_planning",
    "rl_shielded": "kinds_rl", "powl": "kinds_rl",
    "search": "kinds_search", "mdp": "kinds_search", "fond": "kinds_search",
}
UNSOLVABLE = ("(define (problem U) (:domain BLOCKS) (:objects A B) (:init (ONTABLE A) (ONTABLE B)"
              " (CLEAR A) (CLEAR B) (HANDEMPTY)) (:goal (AND (ON A B) (ON B A))))\n")
TDOM = """(define (domain tw) (:requirements :typing :durative-actions)
 (:types loc)
 (:predicates (at ?l - loc) (road ?a ?b - loc))
 (:durative-action go :parameters (?a ?b - loc)
  :duration (= ?duration 5)
  :condition (and (at start (at ?a)) (at start (road ?a ?b)))
  :effect (and (at start (not (at ?a))) (at end (at ?b)))))
"""
TPROB = ("(define (problem tp) (:domain tw) (:objects l0 l1 l2 - loc)"
         " (:init (at l0) (road l0 l1) (road l1 l2)) (:goal (at l2)))")
RC_OK = {"tasks": {"t1": {"duration": 2, "uses": {"r": 1}}, "t2": {"duration": 3, "uses": {"r": 1}}},
         "precedences": [["t1", "t2"]], "resources": {"r": 1}}
RC_BAD = {"tasks": {"t1": {"duration": 2, "uses": {"r": 5}}}, "resources": {"r": 1}}

# (kind, case, expected, payload, options)
EDGES = [["a", "go", "b", 1], ["b", "go", "c", 1]]
MDP_T = {"a": {"go": {"b": [1.0, 1]}}, "b": {"go": {"c": [1.0, 1]}}}
FOND_T = {"s0": {"go": ["s0", "g"]}}
COP = [
    ("search", "astar-reachable", "PLAN",
     {"solver": "astar", "initial": "a", "targets": ["c"], "edges": EDGES}, {}),
    ("search", "astar-unreachable", "INFEASIBLE",
     {"solver": "astar", "initial": "a", "targets": ["z"], "edges": EDGES}, {}),
    ("mdp", "lrtdp-reachable", "PLAN",
     {"solver": "lrtdp", "initial": "a", "goals": ["c"], "transitions": MDP_T}, {}),
    ("mdp", "lrtdp-unreachable", "INFEASIBLE",
     {"solver": "lrtdp", "initial": "a", "goals": ["z"], "transitions": MDP_T}, {}),
    ("fond", "strong-cyclic", "PLAN",
     {"semantics": "strong_cyclic", "initial": "s0", "goals": ["g"], "transitions": FOND_T}, {}),
    ("fond", "strong-on-cycle", "INFEASIBLE",
     {"semantics": "strong", "initial": "s0", "goals": ["g"], "transitions": FOND_T}, {}),
    ("pddl", "blocks-3", "PLAN", {"domain_path": str(BLOCKS / "domain.pddl"),
                                  "problem_path": str(BLOCKS / "probBLOCKS-3-0.pddl")}, {}),
    ("pddl", "unsolvable", "NO_PLAN", {"domain_path": str(BLOCKS / "domain.pddl"),
                                       "problem_text": UNSOLVABLE}, {}),
    ("temporal_pddl", "durative-go", "PLAN", {"domain_text": TDOM, "problem_text": TPROB}, {}),
    ("temporal_pddl", "garbage-input", "REFUSED",
     {"domain_text": "(oops", "problem_text": "(oops"}, {}),
    ("htn", "verify-and-commit", "PLAN",
     {"domain_path": str(HTN / "verify-and-commit.hddl"),
      "problem_path": str(HTN / "verify-and-commit-problem.hddl")}, {}),
    ("htn", "unparsable-domain", "REFUSED",
     {"domain_text": "(not hddl", "problem_text": "(also not"}, {}),
    ("rcpsp", "two-tasks-one-resource", "PLAN", RC_OK, {}),
    ("rcpsp", "demand-exceeds-capacity", "INFEASIBLE", RC_BAD, {}),
    ("cp", "two-flights-two-stands", "PLAN",
     {"flights": [["a", 0, 10], ["b", 5, 15]], "stands": 2}, {}),
    ("cp", "overlap-one-stand", "INFEASIBLE",
     {"flights": [["a", 0, 10], ["b", 5, 15]], "stands": 1}, {}),
    ("portfolio", "rcpsp-domain", "PLAN", dict(RC_OK, domain="rcpsp"), {}),
    ("portfolio", "unknown-domain", "REFUSED", {"domain": "nonsense"}, {}),
    ("rl_shielded", "four-stands", "PLAN", {"n_stands": 4, "horizon": 8, "seed": 0},
     {"timesteps": 2048, "max_seconds": 60}),
    ("rl_shielded", "all-stands-blocked", "INFEASIBLE",
     {"n_stands": 2, "horizon": 4, "blocked_stands": [0, 1]}, {}),
    ("powl", "two-step-plan", "PLAN", {"plan": ["(move a b)", "(move b c)"]}, {}),
    ("powl", "empty-plan", "REFUSED", {"plan": []}, {}),
]

GL = r'''
import json, sys
from autofde_lab.law_bridge.graphlaw_admitter import Action, GraphLawAdmitter
a = json.loads(sys.argv[1])
v = GraphLawAdmitter().admit(a["init"], [Action(a["name"], pre=a["pre"], add=a["add"])])
print(json.dumps({"status": v.status, "state": getattr(v, "state_id", ""),
                  "chain": len(getattr(v, "receipts", ())),
                  "unmet": list(getattr(v, "unmet", ()))}))
'''
T = "<urn:s> <urn:p> <urn:o> ."
GRAPHLAW = [
    ("graphlaw", "precondition-met", "PLAN", {"init": T, "name": "step", "pre": T,
                                              "add": "<urn:s> <urn:p> <urn:o2> ."}),
    ("graphlaw", "precondition-unmet", "REFUSED", {"init": T, "name": "step",
                                                   "pre": "<urn:x> <urn:p> <urn:y> .",
                                                   "add": "<urn:s> <urn:p> <urn:o2> ."}),
]


def run_cop(kind, payload, options):
    r = subprocess.run([PY, "-m", "autofde_lab.coprocessor", kind], cwd=REPO, capture_output=True,
                       text=True, input=json.dumps({"payload": payload, "options": options}))
    if "Traceback" in r.stderr:
        return "CRASH", r.stderr.strip()[-120:]
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return "CRASH", f"rc={r.returncode} unparsable stdout {r.stdout[-80:]!r}"
    d = o["diagnostics"].get("reason") or o["diagnostics"].get("blocked_on") or ""
    return o["status"], f"cost={o['cost']} n_actions={len(o['actions'])} {d}"[:90]


def run_gl(payload):
    r = subprocess.run([PY, "-c", GL, json.dumps(payload)], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        return "CRASH", r.stderr.strip()[-120:]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    st = "PLAN" if o["status"] == "ADMITTED" else "REFUSED"
    return st, f"{o['status']} receipts={o['chain']} unmet={o['unmet']}"[:90]


def main() -> int:
    rows, bad = [], 0
    sk = k14.probe()
    if sk:
        print(f"SKIP: {sk.reason} | {sk.hint}")
        return 1
    for c in k14.cases():
        o = k14.run(c)
        rows.append(("k14", c.id, c.expect, o.status, o.detail[:60]))
    needed = {KIND_FILES[k] for k, *_ in COP}
    for mod in sorted(needed):
        if not (REPO / "src/autofde_lab/coprocessor" / f"{mod}.py").is_file():
            print(f"SKIP: {mod}.py absent")
            bad += 1
    for kind, case, exp, payload, opts in COP:
        got, det = run_cop(kind, payload, opts)
        rows.append((kind, case, exp, got, det))
    for kind, case, exp, payload in GRAPHLAW:
        got, det = run_gl(payload)
        rows.append((kind, case, exp, got, det))
    print(f"{'kind':14} {'case':26} {'expected':11} {'actual':11} ok  detail")
    for kind, case, exp, got, det in rows:
        ok = got == exp
        bad += not ok
        print(f"{kind:14} {case:26} {exp:11} {got:11} {'Y' if ok else 'N':3} {det}")
    print(f"ROWS={len(rows)} MISMATCH_OR_SKIP={bad}")
    print("RESULT:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
