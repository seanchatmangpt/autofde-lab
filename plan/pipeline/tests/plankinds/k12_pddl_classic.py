"""K12: classical PDDL. Seeded typed-STRIPS travel instances run on the coprocessor `pddl` kind
(`run`); ferroplan example rows (ADL + durative + numeric fluents: outside the coprocessor pddl
engine's fragment) and every row's `ff` cross-check stay on the real ferroplan `ff` CLI
(`run_oracle`)."""
from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
from pathlib import Path

from enterprise_pipeline import autofde_backend as backend
from plankinds import Case, Outcome, Skip

KIND = "K12"
TITLE = "classical PDDL (ferroplan ff)"
ROOT = Path(os.environ.get("FERROPLAN_ROOT", "/Users/sac/ferroplan"))
FF = ROOT / "target" / "release" / "ff"
EX = ROOT / "examples"
TIMEOUT_S = 90


TRAVEL_DOMAIN = (
    "(define (domain travel) (:requirements :strips :typing) (:types loc)\n"
    " (:predicates (at ?l - loc) (road ?a ?b - loc))\n"
    " (:action go :parameters (?a ?b - loc) :precondition (and (at ?a) (road ?a ?b))\n"
    "  :effect (and (not (at ?a)) (at ?b))))\n")
SEEDS = (11, 23, 47)


def travel_instance(seed, connected=True, n=9):
    """Seeded directed road graph; returns (problem_text, shortest_path_len or None)."""
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    edges = {(order[i], order[i + 1]) for i in range(n - 2)}   # spine over all but the last
    for _ in range(n):
        a, b = rng.sample(order[:-1], 2)
        edges.add((a, b))
    if connected:
        edges.add((order[rng.randrange(n - 1)], order[-1]))
    start, goal = order[0], order[-1]
    dist, frontier = {start: 0}, [start]
    while frontier:
        nxt = []
        for u in frontier:
            for (a, b) in sorted(edges):
                if a == u and b not in dist:
                    dist[b] = dist[u] + 1
                    nxt.append(b)
        frontier = nxt
    roads = " ".join(f"(road l{a} l{b})" for a, b in sorted(edges))
    prob = (f"(define (problem travel-{seed}) (:domain travel)\n"
            f" (:objects {' '.join(f'l{i}' for i in range(n))} - loc)\n"
            f" (:init (at l{start}) {roads})\n (:goal (at l{goal})))\n")
    return prob, dist.get(goal)


def probe():
    if not Path(backend.AUTOFDE_VENV_PYTHON).exists():
        return Skip("autofde-lab venv absent", "cd /Users/sac/autofde-lab && uv sync")
    return None


def oracle_probe():
    if not FF.exists():
        return Skip(f"ferroplan ff binary absent: {FF}",
                    f"cd {ROOT} && cargo build --release")
    if not (EX / "jobshop" / "domain.pddl").exists():
        return Skip(f"examples missing under {EX}", "")
    return None


def cases():
    out = []
    for seed in SEEDS:
        prob, d = travel_instance(seed)
        out.append(Case(f"travel-seed{seed}", "PLAN", {"engine": "coprocessor", "problem_text": prob,
                                                       "optimal": d}))
    out.append(Case("travel-disconnected", "NO_PLAN",
                    {"engine": "coprocessor", "problem_text": travel_instance(SEEDS[0], False)[0]}))
    out.append(Case("travel-malformed", "REFUSED",
                    {"engine": "coprocessor", "problem_text": "(define (problem broken"}))
    for p in ("p1", "p3", "p5", "s10", "s20", "s50"):
        out.append(Case(f"jobshop-{p}", "PLAN",
                        {"domain": str(EX / "jobshop" / "domain.pddl"),
                         "problem": str(EX / "jobshop" / f"{p}.pddl")}))
    for p in ("p1", "p2"):
        out.append(Case(f"logistics-{p}", "PLAN",
                        {"domain": str(EX / "logistics" / "domain.pddl"),
                         "problem": str(EX / "logistics" / f"{p}.pddl")}))
    out.append(Case("logistics-p1-mutated-goal", "REFUSED",
                    {"domain": str(EX / "logistics" / "domain.pddl"),
                     "problem": str(EX / "logistics" / "p1.pddl"),
                     "mutate_goal": "(:goal (and (at nonexistent-thing nowhere)))"}))
    return out


def _problem_path(case, tmp):
    g = case.payload.get("mutate_goal")
    if not g:
        return case.payload["problem"]
    text = Path(case.payload["problem"]).read_text()
    i = text.index("(:goal")
    path = os.path.join(tmp, "mutated.pddl")
    Path(path).write_text(text[:i] + g + ")")
    return path


def run(case):
    if case.payload.get("engine") != "coprocessor":
        return run_oracle(case)   # ADL/durative/numeric: outside the coprocessor pddl fragment
    r = backend.solve("pddl", {"domain_text": TRAVEL_DOMAIN,
                               "problem_text": case.payload["problem_text"]}, timeout=TIMEOUT_S)
    status = "NO_PLAN" if r.status == "INFEASIBLE" else r.status
    return Outcome(status, f"coprocessor:pddl steps={len(r.actions)} cost={r.cost} "
                           f"{str(r.diagnostics)[:100]}")


def run_oracle(case):
    sk = oracle_probe()
    if sk:
        return Outcome("SKIP", sk.reason)
    if case.payload.get("engine") == "coprocessor":
        with tempfile.TemporaryDirectory() as tmp:
            dom, prob = os.path.join(tmp, "d.pddl"), os.path.join(tmp, "p.pddl")
            Path(dom).write_text(TRAVEL_DOMAIN)
            Path(prob).write_text(case.payload["problem_text"])
            case = Case(case.id, case.expect, {"domain": dom, "problem": prob})
            return run_oracle(case)
    with tempfile.TemporaryDirectory() as tmp:
        problem = _problem_path(case, tmp)
        try:
            r = subprocess.run([str(FF), "-o", case.payload["domain"], "-f", problem, "--json"],
                               capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return Outcome("UNSUPPORTED", f"timeout>{TIMEOUT_S}s")
    if r.returncode != 0:
        return Outcome("REFUSED", f"exit={r.returncode} {r.stderr.strip()[:200]}")
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return Outcome("REFUSED", f"exit=0 non-JSON stdout: {r.stdout[:120]!r}")
    if j.get("solved"):
        steps = len(j.get("plan", {}).get("steps", []))
        return Outcome("PLAN", f"exit=0 mode={j.get('mode')} steps={steps}")
    return Outcome("NO_PLAN", f"exit=0 solved=false notes={j.get('notes')}")
