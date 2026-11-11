"""Lane B3: rcpsp, cp, portfolio kinds through real subprocess calls."""

from __future__ import annotations

import json
import subprocess
import sys

from faker import Faker

fake = Faker()
Faker.seed(20261111)


def call(kind, payload, options=None, timeout=300):
    proc = subprocess.run(
        [sys.executable, "-m", "autofde_lab.coprocessor", kind],
        input=json.dumps({"kind": kind, "payload": payload, "options": options or {}}),
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, json.loads(proc.stdout)


def _rcpsp_payload():
    d = {n: fake.random_int(min=2, max=9) for n in ("a", "b", "c", "d")}
    return {
        "tasks": {n: {"duration": v, "uses": {"crew": 2}} for n, v in d.items()},
        "precedences": [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]],
        "resources": {"crew": 2},
    }, d


def test_rcpsp_plan_serialises_under_capacity():
    payload, d = _rcpsp_payload()
    rc, out = call("rcpsp", payload)
    assert rc == 0 and out["status"] == "PLAN"
    by = {a["task"]: a for a in out["actions"]}
    for n, a in by.items():
        assert a["end"] - a["start"] == d[n]
    assert by["b"]["start"] >= by["a"]["end"] and by["d"]["start"] >= max(by["b"]["end"], by["c"]["end"])
    # crew 2 each, capacity 2: b and c cannot overlap
    assert by["b"]["end"] <= by["c"]["start"] or by["c"]["end"] <= by["b"]["start"]
    assert out["cost"] == sum(d.values())


def test_rcpsp_infeasible_demand_and_cycle():
    payload, _ = _rcpsp_payload()
    payload["tasks"]["a"]["uses"]["crew"] = 3
    rc, out = call("rcpsp", payload)
    assert rc == 2 and out["status"] == "INFEASIBLE"
    payload, _ = _rcpsp_payload()
    payload["precedences"].append(["d", "a"])
    rc, out = call("rcpsp", payload)
    assert rc == 2 and out["status"] == "INFEASIBLE"
    rc, out = call("rcpsp", {"tasks": {}})
    assert rc == 2 and out["status"] == "REFUSED"


def _flights(n_overlap):
    base = fake.random_int(min=0, max=50)
    return [[f"fl_{i}", base + i, base + 100 + i] for i in range(n_overlap)]


def test_cp_assigns_distinct_stands_and_refuses_too_few():
    flights = _flights(3)
    rc, out = call("cp", {"flights": flights, "stands": 3})
    assert rc == 0 and out["status"] == "PLAN"
    assert len({a["stand"] for a in out["actions"]}) == 3
    rc, out = call("cp", {"flights": flights, "stands": 2})
    assert rc == 2 and out["status"] == "INFEASIBLE"
    rc, out = call("cp", {"flights": flights, "stands": 0})
    assert rc == 2 and out["status"] == "REFUSED"


def test_portfolio_matches_solvers_and_refuses_unknown_domain():
    payload, _ = _rcpsp_payload()
    rc, out = call("portfolio", {"domain": "rcpsp", **payload})
    assert rc == 0 and out["status"] == "PLAN" and out["actions"]
    assert any("DOSolver" in a or "do_solver" in a for a in out["actions"])
    rc, out = call("portfolio", {"domain": "graph", "edges": [["x", "y", 1], ["y", "z", 2]], "targets": ["z"]})
    assert rc == 0 and any("Astar" in a for a in out["actions"])
    rc, out = call("portfolio", {"domain": "nonsense"})
    assert rc == 2 and out["status"] == "REFUSED"
