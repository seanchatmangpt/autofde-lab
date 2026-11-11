"""Lane B2: coprocessor kinds fond, mdp, search via real ``python -m autofde_lab.coprocessor``."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from faker import Faker

SRC = str(Path(__file__).resolve().parents[2] / "src")
FAKE = Faker()
Faker.seed(26111)


def call(kind: str, payload: dict, options: dict | None = None):
    import os

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=SRC)
    proc = subprocess.run(
        [sys.executable, "-W", "ignore", "-m", "autofde_lab.coprocessor", kind],
        input=json.dumps({"kind": kind, "payload": payload, "options": options or {}}),
        capture_output=True, text=True, env=env, timeout=120,
    )
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    return proc.returncode, out


def _names():
    return [FAKE.unique.pystr(min_chars=4, max_chars=6) for _ in range(3)]


def _search_payload(solver: str) -> dict:
    a, b, c = _names()
    return {
        "solver": solver, "initial": a, "targets": [c],
        "edges": [[a, "go", b, 1], [a, "jump", c, 5], [b, "go", c, 1]],
    }


@pytest.mark.parametrize("solver", ["astar", "p_astar", "lrtastar"])
def test_search_plan_is_cheapest_path(solver):
    rc, out = call("search", _search_payload(solver))
    assert rc == 0 and out["status"] == "PLAN"
    assert out["actions"] == ["go", "go"] and out["cost"] == 2.0
    assert out["solver"] == solver


@pytest.mark.parametrize("solver", ["astar", "p_astar", "lrtastar"])
def test_search_unreachable_target_is_infeasible(solver):
    pl = _search_payload(solver)
    pl["targets"] = ["unreachable-" + FAKE.pystr(min_chars=3, max_chars=4)]
    rc, out = call("search", pl)
    assert rc == 2 and out["status"] == "INFEASIBLE" and out["actions"] == []


def test_search_unknown_solver_refused():
    rc, out = call("search", _search_payload("dijkstra"))
    assert rc == 2 and out["status"] == "REFUSED"


def _mdp_payload(solver: str) -> dict:
    a, b, c = _names()
    return {
        "solver": solver, "initial": a, "goals": [c],
        "transitions": {a: {"go": {b: [1, 1]}, "alt": {c: [1, 5]}},
                        b: {"go": {c: [0.5, 1], a: [0.5, 1]}}},
    }


@pytest.mark.parametrize("solver", ["lrtdp", "mdplp", "mcts"])
def test_mdp_plan_matches_analytic_expected_cost(solver):
    """V(A)=1+V(B), V(B)=1+0.5 V(A) -> 4 < 5 (alt), so the policy picks go."""
    pl = _mdp_payload(solver)
    rc, out = call("mdp", pl)
    assert rc == 0 and out["status"] == "PLAN"
    assert out["actions"][0] == "go"
    assert out["diagnostics"]["most_likely_path_end"] in pl["goals"]
    assert abs(out["cost"] - 4.0) < 0.6


def test_mdp_martdp_returns_goal_reaching_policy():
    pl = _mdp_payload("martdp")
    rc, out = call("mdp", pl)
    assert rc == 0 and out["status"] == "PLAN"
    assert out["diagnostics"]["most_likely_path_end"] in pl["goals"]
    assert out["actions"][0] in ("go", "alt")


@pytest.mark.parametrize("solver", ["lrtdp", "martdp", "mdplp", "mcts"])
def test_mdp_dead_end_risk_is_infeasible(solver):
    a, c, d = _names()
    pl = {"solver": solver, "initial": a, "goals": [c],
          "transitions": {a: {"go": {c: [0.5, 1], d: [0.5, 1]}}}}
    rc, out = call("mdp", pl)
    assert rc == 2 and out["status"] == "INFEASIBLE"


def test_mdp_unknown_solver_refused():
    rc, out = call("mdp", _mdp_payload("value_iteration_9000"))
    assert rc == 2 and out["status"] == "REFUSED"


def test_fond_strong_cyclic_valid_and_strong_infeasible():
    s0, g, _ = _names()
    base = {"initial": s0, "goals": [g], "transitions": {s0: {"go": [s0, g]}}}
    rc, out = call("fond", {**base, "semantics": "strong_cyclic"})
    assert rc == 0 and out["status"] == "PLAN"
    assert out["diagnostics"]["policy"] == {s0: "go"}
    rc, out = call("fond", {**base, "semantics": "strong"})
    assert rc == 2 and out["status"] == "INFEASIBLE"
    assert out["diagnostics"]["missing_policy_states"] == [s0]


def test_fond_supplied_policy_is_checked_not_trusted():
    s0, g, _ = _names()
    base = {"initial": s0, "goals": [g], "semantics": "strong_cyclic",
            "transitions": {s0: {"go": [s0, g]}}}
    rc, out = call("fond", {**base, "policy": {s0: "go"}})
    assert rc == 0 and out["status"] == "PLAN"
    rc, out = call("fond", {**base, "policy": {}})
    assert rc == 2 and out["status"] == "INFEASIBLE"


def test_fond_dead_end_action_is_infeasible_for_strong_cyclic():
    s0, g, dead = _names()
    pl = {"initial": s0, "goals": [g], "semantics": "strong_cyclic",
          "transitions": {s0: {"go": [g, dead]}}}
    rc, out = call("fond", pl)
    assert rc == 2 and out["status"] == "INFEASIBLE"


def test_missing_fields_refused():
    for kind in ("fond", "mdp", "search"):
        rc, out = call(kind, {})
        assert rc == 2 and out["status"] == "REFUSED"
