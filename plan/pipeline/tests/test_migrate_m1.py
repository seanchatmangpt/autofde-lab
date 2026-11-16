"""M1: K1/K5 temporal PDDL through coprocessor kind temporal_pddl; planner/plan.py is the oracle.

Differential on 3 seeded instances: same status, plan valid by independent replay on the original
problem, makespan within MAKESPAN_TOL of the oracle's (aries is satisficing, so plans are not
unique; both are validated plans for the same problem and horizon)."""
import os
import re
import tempfile
import zlib
from pathlib import Path

import sys

import pytest

from plankinds import registry, run_kind

PLAN = Path(__file__).resolve().parents[2]
PM = PLAN / "pm"
DOMAIN_PM = PM / "pm_domain.pddl"
sys.path.insert(0, str(PM)) if str(PM) not in sys.path else None
_ORACLE_VENV = Path.home() / "plan" / "planner" / ".venv" / "bin" / "python"
if _ORACLE_VENV.exists():  # the original oracle interpreter (unified-planning with a sound grounder)
    os.environ.setdefault("PLAN_ORACLE_PY", str(_ORACLE_VENV))
SEEDS = (11, 23, 37)
MAKESPAN_TOL = 0.25  # relative slack of coprocessor makespan vs oracle (aries anytime search)


def _planner():
    from enterprise_pipeline import planner
    return planner


def _both(domain, problem, timeout=300):
    pl = _planner()
    old = os.environ.get("PLAN_ORACLE")
    try:
        os.environ.pop("PLAN_ORACLE", None)
        new = pl.solve_files(domain, problem, timeout=timeout)
        os.environ["PLAN_ORACLE"] = "1"
        ora = pl.solve_files(domain, problem, timeout=timeout)
    finally:
        if old is None:
            os.environ.pop("PLAN_ORACLE", None)
        else:
            os.environ["PLAN_ORACLE"] = old
    return new, ora


def _makespan(text):
    steps = _planner().parse_plan(text)
    return max(s["time"] + s["duration"] for s in steps)


def _replay_valid(domain, problem, text):
    from unified_planning.engines import ValidationResultStatus
    from unified_planning.io import PDDLReader
    from unified_planning.plans import ActionInstance, TimeTriggeredPlan
    from unified_planning.shortcuts import PlanValidator
    orig = PDDLReader().parse_problem(str(domain), str(problem))
    em = orig.environment.expression_manager
    timed = [(s["time"], ActionInstance(orig.action(s["action"]),
                                        tuple(em.ObjectExp(orig.object(a)) for a in s["args"])),
              s["duration"]) for s in _planner().parse_plan(text)]
    with PlanValidator(name="up_time_triggered_validator") as v:
        return v.validate(orig, TimeTriggeredPlan(timed)).status == ValidationResultStatus.VALID


def _pm_problem(seed, td, **over):
    import jtbd_factories as jf
    from gen_problem import gen, to_pddl
    jf.reseed(seed)
    r = jf.rg()
    p = dict(n_assets=r.randint(2, 3), cadences=["monthly"], horizon=r.randint(45, 59),
             n_providers=2, n_sites=r.randint(1, 2), capacity=r.randint(2, 4), blackouts={})
    p.update(over)
    f = Path(td) / f"pm{seed}.pddl"
    f.write_text(to_pddl(gen(p["n_assets"], p["cadences"], p["horizon"], p["n_providers"],
                             p["n_sites"], p["capacity"], p["blackouts"], seed=1)))
    return f


@pytest.mark.parametrize("seed", SEEDS)
def test_k5_pm_differential_plan(seed):
    with tempfile.TemporaryDirectory() as td:
        prob = _pm_problem(seed, td)
        (rc_n, out_n), (rc_o, out_o) = _both(DOMAIN_PM, prob)
        assert rc_o == 0, out_o
        assert rc_n == 0, out_n
        assert _replay_valid(DOMAIN_PM, prob, out_n)
        mn, mo = _makespan(out_n), _makespan(out_o)
        assert mn <= mo * (1 + MAKESPAN_TOL) + 1e-6, (mn, mo)


def test_k5_pm_differential_no_plan():
    with tempfile.TemporaryDirectory() as td:
        prob = _pm_problem(SEEDS[0], td, capacity=0)
        (rc_n, out_n), (rc_o, out_o) = _both(DOMAIN_PM, prob)
        assert (rc_n, rc_o) == (2, 2), (out_n, out_o)


def test_k1_differential_three_seeds_and_no_plan():
    from plankinds import k01_aries as k1
    from enterprise_pipeline import staged, store
    pl = _planner()
    seen = []
    for i, (cid, stage, opts) in enumerate([("stage1_ok", 1, {}), ("stage2_ok", 2, {}),
                                            ("stage1_territory_out", 1, {"territory_out": True})]):
        os.environ["PLAN_TEST_SEED"] = str(SEEDS[i])
        w = k1.draw_world(cid, part=True)
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / "events.ndjson"
            ids = k1.build_store(w, sp, stage=stage, **opts)
            state = store.reduce(store.read(sp))
            c = staged.compile_wo(state, ids["wo"])
            prob, dom = Path(td) / "p.pddl", Path(td) / "d.pddl"
            prob.write_text(c.text)
            dom.write_text(staged.project_domain(pl.DOMAIN.read_text(), c.text)[0])
            (rc_n, out_n), (rc_o, out_o) = _both(dom, prob, timeout=900)
            assert rc_n == rc_o, (cid, rc_n, rc_o, out_n[-300:], out_o[-300:])
            if rc_n == 0:
                assert _replay_valid(dom, prob, out_n)
                assert _makespan(out_n) <= _makespan(out_o) * (1 + MAKESPAN_TOL) + 1e-6
            seen.append(rc_n)
    assert 0 in seen and 2 in seen, seen


def test_oracle_switch_and_repo_relative_paths():
    pl = _planner()
    for f in (pl.__file__, registry()["K1"].__file__, registry()["K5"].__file__):
        assert "/Users/sac/plan" not in Path(f).read_text(), f
    assert pl.RUN_SH.is_relative_to(PLAN) and pl.DOMAIN.is_relative_to(PLAN)
    old = os.environ.pop("PLAN_ORACLE", None)
    try:
        assert not pl.oracle_enabled()
        os.environ["PLAN_ORACLE"] = "1"
        assert pl.oracle_enabled()
    finally:
        os.environ.pop("PLAN_ORACLE", None)
        if old is not None:
            os.environ["PLAN_ORACLE"] = old


def test_coprocessor_temporal_handles_real_fluents():
    """Gap fix: Real-typed fluents + TILs must plan (previously INTERNAL_ERROR -> NO_PLAN)."""
    from enterprise_pipeline.autofde_backend import solve
    with tempfile.TemporaryDirectory() as td:
        prob = _pm_problem(SEEDS[1], td)
        r = solve("temporal_pddl", {"domain_path": str(DOMAIN_PM), "problem_path": str(prob)},
                  options={"timeout": 60}, timeout=300)
    assert r.status == "PLAN", r.diagnostics
    assert r.diagnostics.get("validator") == "VALID"


def test_k1_k5_rows_pass():
    for kind in ("K1", "K5"):
        mod = registry()[kind]
        assert mod.probe() is None
        rows = run_kind(mod)
        assert rows and all(r["ok"] for r in rows), (kind, rows)
