"""K4/K5/K6 plan kinds against real solvers, plus K4-vs-K5 and K6 CP-SAT-vs-PDDL differential courts."""
import pytest

from plankinds import k04_pm_cpsat as k4, k05_pm_pddl as k5, k06_procure as k6, run_kind

# Registered divergences: (instance, K4 status, K5 status) -> id. Anything else is a failed court.
REGISTERED = {
    ("infeasible_blackout_window", "INFEASIBLE", "PLAN"):
        "KD-PM-01: gen_problem.to_pddl drops provider/global blackouts, PDDL cannot see them",
}


@pytest.mark.parametrize("mod", [k4, k5, k6], ids=lambda m: m.KIND)
def test_kind_cases_match_expected(mod):
    rows = run_kind(mod)
    for r in rows:
        print(r["kind"], r["case"], r["expect"], r["status"], r["detail"])
    assert all(r["status"] != "SKIP" for r in rows), rows
    bad = [r for r in rows if not r["ok"]]
    assert not bad, bad


def test_k6_path_and_reason_details():
    for c in k6.cases():
        o = k6.run(c)
        if c.payload["expect_path"]:
            assert o.detail == f"path={c.payload['expect_path']}", (c.id, o)
        if c.payload["reason"]:
            assert o.detail == f"reason={c.payload['reason']}", (c.id, o)


def test_differential_k4_vs_k5():
    divergences = []
    for name, (params, _e4, _e5) in k4.draw_instances().items():
        a = k4.run(k4.Case(name, "", {"params": params})).status
        b = k5.solve_pddl(params).status
        agree = (a == "PLAN") == (b == "PLAN")
        print("DIFF", name, "K4=", a, "K5=", b, "agree" if agree else "DIVERGE")
        if not agree:
            divergences.append(((name, a, b), REGISTERED.get((name, a, b))))
    assert all(kd for _, kd in divergences), divergences


def test_differential_k6_cpsat_vs_pddl():
    for path, pf in k6.PROBLEMS.items():
        res = k6.cpsat(k6.pddl_request(pf))
        st, pddl = k6.pddl_path(pf)
        print("DIFF", path, "cpsat=", res.get("status"), res.get("path"), "pddl=", st, pddl)
        assert res["status"] == "OPTIMAL" and st == "PLAN"
        assert res["path"] == pddl == path
