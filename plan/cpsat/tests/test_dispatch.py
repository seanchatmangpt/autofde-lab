import json, subprocess, sys, pathlib
from hypothesis import given, settings, strategies as st
from servengine_cpsat import solve, oracle, DIMS

ROOT = pathlib.Path(__file__).resolve().parents[1]
VALS = ["a", "b", "c"]

def base_wo(**kw):
    wo = {d: "a" for d in DIMS}
    wo.update(nte_cents=1000, client_billable_rate_cents=900)
    wo.update(kw)
    return wo

def prov(id, **kw):
    p = dict(id=id, blacklisted=False, entity_aligned=True, trade_and_rate_approved=True,
             coi_and_license_unexpired=True, trade_rank=5, rate_cents=500, inc={}, exc={})
    p.update(kw)
    return p

def test_picks_lowest_rank_then_rate():
    r = solve({"work_order": base_wo(), "providers": [
        prov("A", trade_rank=3, rate_cents=800), prov("B", trade_rank=2, rate_cents=850),
        prov("C", trade_rank=2, rate_cents=700)]})
    assert r["selected_provider"] == "C" and r["objective_score"] == 200700

def test_reactive_hire_when_none():
    r = solve({"work_order": base_wo(), "providers": [prov("A", blacklisted=True)]})
    assert r["selected_provider"] is None and r["trigger_reactive_hire"]
    assert r["vetoes"]["A"] == ["blacklist"]

def test_margin_and_nte_vetoes():
    r = solve({"work_order": base_wo(), "providers": [
        prov("A", rate_cents=900), prov("B", rate_cents=1100)]})
    assert r["trigger_reactive_hire"] and set(r["vetoes"]) == {"A", "B"}

def test_inclusion_exclusion():
    inst = {"work_order": base_wo(site="s1"), "providers": [
        prov("A", inc={"site": ["s2"]}), prov("B", exc={"site": ["s1"]}),
        prov("C", inc={"site": ["s1"]}, rate_cents=600)]}
    assert solve(inst)["selected_provider"] == "C"

def test_cli_roundtrip():
    inst = {"work_order": base_wo(), "providers": [prov("A")]}
    out = subprocess.run([sys.executable, "-m", "servengine_cpsat"], input=json.dumps(inst),
                         capture_output=True, text=True, cwd=ROOT, check=True)
    assert json.loads(out.stdout)["selected_provider"] == "A"

def test_cli_bad_input_exit2():
    out = subprocess.run([sys.executable, "-m", "servengine_cpsat"], input="{}",
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 2 and "error" in json.loads(out.stdout)

sets = st.lists(st.sampled_from(VALS), unique=True, max_size=3)
bools = st.booleans()
prov_st = st.fixed_dictionaries({
    "blacklisted": st.sampled_from([False, False, False, True]),
    "entity_aligned": st.sampled_from([True, True, True, False]),
    "trade_and_rate_approved": st.sampled_from([True, True, True, False]),
    "coi_and_license_unexpired": st.sampled_from([True, True, True, False]),
    "trade_rank": st.integers(1, 20), "rate_cents": st.integers(0, 1200),
    "inc": st.fixed_dictionaries({}, optional={d: sets for d in DIMS}),
    "exc": st.fixed_dictionaries({}, optional={d: sets for d in DIMS}),
})
inst_st = st.builds(
    lambda wo, ps, nte, bill: {"work_order": {**wo, "nte_cents": nte, "client_billable_rate_cents": bill},
        "providers": [{"id": f"P{i}", **p} for i, p in enumerate(ps)]},
    st.fixed_dictionaries({d: st.sampled_from(VALS) for d in DIMS}),
    st.lists(prov_st, max_size=8), st.integers(0, 1200), st.integers(0, 1200))

@settings(max_examples=300, deadline=None)
@given(inst_st)
def test_cpsat_matches_bruteforce_oracle(inst):
    r, o = solve(inst), oracle(inst)
    for k in ("selected_provider", "trigger_reactive_hire", "eligible", "objective_score"):
        assert r[k] == o[k], (k, r, o)
