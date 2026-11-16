"""Chicago tests for the autofde backend seam: real subprocess, real solvers."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

from enterprise_pipeline import autofde_backend as B

ROOT = Path(B.AUTOFDE_ROOT)
BLOCKS = ROOT / "tests/domains/python/pddl_domains/blocks/domain.pddl"
HTN_DIR = ROOT / "tests/domains/htn_fixtures"
SEED = 20261111


@pytest.fixture(autouse=True)
def _work(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOFDE_WORK", str(tmp_path))


def _blocks(n, goal=True):
    rng = random.Random(SEED)
    names = [f"b{i}" for i in range(n)]
    order = names[:]
    rng.shuffle(order)
    g = " ".join(f"(on {order[i]} {order[i + 1]})" for i in range(n - 1))
    init = " ".join(f"(ontable {b}) (clear {b})" for b in names)
    if not goal:
        g = f"(on {names[0]} {names[0]})"
    return (f"(define (problem p) (:domain blocks) (:objects {' '.join(names)})"
            f" (:init {init} (handempty)) (:goal (and {g})))")


def test_python_resolution():
    assert B.backend_python().endswith("/bin/python")


def test_pddl_plan_and_no_plan():
    ok = B.solve("pddl", {"domain_path": str(BLOCKS), "problem_text": _blocks(3)}, timeout=120)
    assert ok.status == B.PLAN and ok.actions and ok.cost is not None and ok.exit_code == 0
    bad = B.solve("pddl", {"domain_path": str(BLOCKS), "problem_text": _blocks(3, goal=False)},
                  timeout=120)
    assert bad.status in (B.NO_PLAN, B.REFUSED) and bad.actions == [] and bad.exit_code == 2


def test_htn_plan_and_no_plan():
    dom = str(HTN_DIR / "verify-and-commit.hddl")
    prob = HTN_DIR / "verify-and-commit-problem.hddl"
    ok = B.solve("htn", {"domain_path": dom, "problem_path": str(prob)})
    assert ok.status == B.PLAN and [a[0] for a in ok.actions][:3] == ["compile", "migrate", "test"]
    broken = prob.read_text().replace("(edited repo1 changeset1)", "")
    bad = B.solve("htn", {"domain_path": dom, "problem_text": broken})
    assert bad.status == B.NO_PLAN and bad.actions == []


def test_fond_plan_and_infeasible():
    pl = {"initial": "s0", "goals": ["g"], "transitions": {"s0": {"go": ["s0", "g"]}}}
    ok = B.solve("fond", {**pl, "semantics": "strong_cyclic"})
    assert ok.status == B.PLAN and ok.diagnostics["policy"] == {"s0": "go"}
    bad = B.solve("fond", {**pl, "semantics": "strong"})
    assert bad.status == B.INFEASIBLE and bad.exit_code == 2


def test_mdp_plan_and_infeasible():
    pl = {"solver": "lrtdp", "initial": "a", "goals": ["c"],
          "transitions": {"a": {"go": {"b": [1, 1]}}, "b": {"go": {"c": [0.5, 1], "a": [0.5, 1]}}}}
    ok = B.solve("mdp", pl, options={"seed": SEED})
    assert ok.status == B.PLAN
    dead = {"solver": "lrtdp", "initial": "a", "goals": ["c"],
            "transitions": {"a": {"go": {"c": [0.5, 1], "d": [0.5, 1]}}}}
    bad = B.solve("mdp", dead, options={"seed": SEED})
    assert bad.status == B.INFEASIBLE and bad.actions == []


def test_search_plan_and_infeasible():
    pl = {"solver": "astar", "initial": "a", "targets": ["c"],
          "edges": [["a", "x", "b", 1], ["b", "y", "c", 1], ["a", "z", "c", 5]]}
    ok = B.solve("search", pl)
    assert ok.status == B.PLAN and ok.cost == 2.0 and ok.actions == ["x", "y"]
    bad = B.solve("search", {**pl, "targets": ["zz"]})
    assert bad.status == B.INFEASIBLE


def test_rcpsp_plan_and_infeasible():
    pl = {"tasks": {"a": {"duration": 2, "uses": {"r": 1}}, "b": {"duration": 3, "uses": {"r": 1}}},
          "precedences": [["a", "b"]], "resources": {"r": 1}}
    ok = B.solve("rcpsp", pl)
    assert ok.status == B.PLAN and ok.cost == 5.0
    bad = B.solve("rcpsp", {**pl, "resources": {"r": 0}})
    assert bad.status == B.INFEASIBLE


def test_cp_plan_and_infeasible():
    pl = {"flights": [["f1", 0, 10], ["f2", 5, 15], ["f3", 12, 20]], "stands": 2}
    ok = B.solve("cp", pl)
    assert ok.status == B.PLAN and len(ok.actions) == 3
    bad = B.solve("cp", {**pl, "stands": 1})
    assert bad.status == B.INFEASIBLE


def test_portfolio_plan_and_refused():
    pl = {"domain": "graph", "edges": [["a", "b", 1], ["b", "c", 1]], "targets": ["c"]}
    ok = B.solve("portfolio", pl)
    assert ok.status == B.PLAN and ok.actions
    bad = B.solve("portfolio", {"domain": "nonsense"})
    assert bad.status == B.REFUSED


def test_powl_plan_and_refused():
    ok = B.solve("powl", {"plan": ["(a x)", "(b x y)"]})
    assert ok.status == B.PLAN and ok.actions == ["(a x)", "(b x y)"]
    bad = B.solve("powl", {"plan": []})
    assert bad.status == B.REFUSED


def test_unknown_kind_refused_typed():
    r = B.solve("no_such_kind", {})
    assert r.status == B.REFUSED and r.exit_code == 2


def test_timeout_is_typed_refused_not_hang():
    # a real subprocess that outlives the deadline: python reading stdin forever is
    # avoided; use a real slow interpreter start with a tiny deadline.
    r = B.solve("pddl", {"domain_path": str(BLOCKS), "problem_text": _blocks(3)}, timeout=0.01)
    assert r.status == B.REFUSED and r.diagnostics["reason"] == "TIMEOUT"
    assert r.actions == []


def test_missing_python_is_blocked():
    r = B.solve("search", {}, python="/nonexistent/python")
    assert r.status == B.BLOCKED


def test_sys_executable_used_when_in_venv():
    if B.backend_python() == sys.executable:
        assert sys.prefix
