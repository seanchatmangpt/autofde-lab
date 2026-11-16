"""M2: K3/K4/K6 CP-SAT paths run on the coprocessor 'cp' kind; old solvers are differential oracles."""
import copy
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

import jtbd_factories as jf
from enterprise_pipeline import align, autofde_backend
from plankinds import registry, run_kind

PLAN = Path(__file__).resolve().parents[2]
SEEDS = (11, 23, 47)
sys.path.insert(0, str(PLAN / "pm"))
sys.path.insert(0, str(PLAN / "procurepass"))
sys.path.insert(0, str(PLAN / "cpsat"))
import sweep_scheduler as sweep  # noqa: E402
import supplier_cpsat as procure  # noqa: E402
from gen_problem import gen  # noqa: E402


def test_cpsat_dir_is_repo_relative():
    assert align.CPSAT_DIR == PLAN / "cpsat"
    assert "/Users/sac/plan/" not in Path(align.__file__).read_text()


def test_cp_general_model_proves_optimum():
    m = {"vars": {"a": [0, 1], "b": [0, 1], "c": [0, 5]},
         "constraints": [{"type": "exactly_one", "vars": ["a", "b"]},
                         {"type": "linear", "terms": [[1, "c"], [-3, "b"]], "op": ">=", "rhs": 0}],
         "objective": {"sense": "max", "terms": [[10, "b"], [-1, "c"]]}}
    r = autofde_backend.solve("cp", {"model": m})
    v = {a["var"]: a["value"] for a in r.actions}
    assert r.status == "PLAN" and r.diagnostics["optimal"] and r.cost == 7.0 and v["b"] == 1 and v["c"] == 3
    bad = autofde_backend.solve("cp", {"model": {"vars": {"x": [0, 1]}, "constraints": [{"type": "infeasible"}]}})
    assert bad.status == "INFEASIBLE"
    ov = {"vars": {"s1": [0, 3], "s2": [0, 3]},
          "constraints": [{"type": "no_overlap", "intervals": [{"start": "s1", "size": 2}, {"start": "s2", "size": 2}]},
                          {"type": "linear", "terms": [[1, "s1"]], "op": "==", "rhs": 1},
                          {"type": "linear", "terms": [[1, "s2"]], "op": "<=", "rhs": 2}]}
    assert autofde_backend.solve("cp", {"model": ov}).status == "INFEASIBLE"


def _sweep_inst(seed, kind):
    r = random.Random(seed)
    h = r.randint(60, 89)
    bl = {"all": list(range(0, 30))} if kind == "blackout" else {}
    return gen(r.randint(2, 3), ["monthly"], h, 2, r.randint(1, 2), 0 if kind == "cap0" else r.randint(2, 4), bl, seed=seed)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("kind", ["feasible", "cap0", "blackout"])
def test_k4_matches_oracle(seed, kind):
    inst = _sweep_inst(seed, kind)
    new = sweep.solve(inst)
    old = sweep.solve_oracle(inst)
    assert (new["status"] == "INFEASIBLE") == (old["status"] == "INFEASIBLE")
    if old["status"] == "OPTIMAL":
        assert new["status"] == "OPTIMAL" and new["clusters"] == old["clusters"]
        assert len(new["schedule"]) == len(inst["jobs"])


@pytest.mark.parametrize("seed", SEEDS)
def test_k6_matches_oracle(seed):
    r = random.Random(seed)
    base = json.loads((PLAN / "procurepass/scenario_compressor.json").read_text())
    reqs = []
    q = copy.deepcopy(base); q["nte_limit"] = r.randint(1, 3 * base["nte_limit"]); reqs.append(q)
    q = copy.deepcopy(base); q["sla_minutes"] = r.randint(1, base["options"][0]["lead_minutes"]); reqs.append(q)
    q = copy.deepcopy(base)
    for o in q["options"]:
        o["part_cost"] = r.randint(1, 5 * o["part_cost"]); o["ship_cost"] = r.randint(0, 5000)
    reqs.append(q)
    for q in reqs:
        new, old = procure.solve(q), procure.solve_oracle(q)
        assert new["status"] == old["status"]
        if old["status"] == "OPTIMAL":
            for k in ("procurement_cost", "install_end", "path", "supplier", "warehouse"):
                assert new[k] == old[k], (k, new, old)
        else:
            assert new["reason"] == old["reason"]


def test_k4_k6_oracle_env_path_still_runs():
    inst = _sweep_inst(11, "feasible")
    code = ("import json,sys;sys.path.insert(0,'pm');import sweep_scheduler as s;"
            "print(s.solve(json.load(sys.stdin))['clusters'])")
    out = subprocess.run([sys.executable, "-c", code], input=json.dumps(inst), capture_output=True, text=True,
                         cwd=PLAN, env={**os.environ, "PLAN_ORACLE": "1", "PYTHONPATH": str(PLAN / "pipeline")})
    assert out.returncode == 0 and int(out.stdout) == sweep.solve_oracle(inst)["clusters"], out.stderr


@pytest.mark.parametrize("seed", SEEDS)
def test_k3_matches_servengine_oracle_and_k2(seed):
    from servengine_cpsat.solver import solve as oracle_solve
    from plankinds.k02_minizinc import build_state, elig_cases
    jf.reseed(seed)
    for case in elig_cases():
        state, wo_id = build_state(case)
        wo = next(x for x in state["work_orders"] if x["id"] == wo_id)
        elig, trig = align.run_cpsat(state, wo)
        o = oracle_solve(align.cpsat_input(state, wo))
        assert {p for p, ok in elig.items() if ok} == set(o["eligible"]) and trig == o["trigger_reactive_hire"]
        assert (elig, trig) == align.run_minizinc(state, wo)


@pytest.mark.parametrize("kind", ["K2", "K3", "K4", "K6"])
def test_kind_rows_green(kind):
    mod = registry()[kind]
    assert mod.probe() is None or kind == "K2"
    rows = run_kind(mod)
    assert rows and all(r["ok"] for r in rows), rows
