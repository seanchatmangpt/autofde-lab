import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enterprise_pipeline import align, pddl, planner  # noqa: E402
from enterprise_pipeline.cli import compile_state  # noqa: E402

SPEC = ROOT.parent / "spec" / "problem_enterprise_ops.pddl"
STATE = json.loads((ROOT / "examples/canonical.json").read_text())


def test_canonical_semantically_equal_to_spec():
    text, elig = compile_state(STATE)
    assert elig["wo_reactive_9001"][0] == {"prov_sean_hvac": True}
    assert pddl.diff(SPEC.read_text(), text) == []


def test_diff_detects_mutation():
    text, _ = compile_state(STATE)
    mutated = text.replace("(eligible-for-wo prov_sean_hvac wo_reactive_9001)", "")
    assert any("eligible-for-wo" in d for d in pddl.diff(SPEC.read_text(), mutated))


def test_expired_coi_triggers_reactive_hire():
    s = copy.deepcopy(STATE)
    s["clock"] = 525600
    text, elig = compile_state(s)
    assert elig["wo_reactive_9001"] == ({"prov_sean_hvac": False}, True)
    n = pddl.normalize(text)
    assert ("reactive-hire-triggered", "wo_reactive_9001") in n["init"]
    assert ("eligible-for-wo", "prov_sean_hvac", "wo_reactive_9001") not in n["init"]


def test_blacklist_and_nte_and_exclusion():
    for mut in (lambda s: s["providers"][0].update(blacklisted=True),
                lambda s: s["work_orders"][0].update(nte_limit=100),
                lambda s: s["providers"][0]["filters"].update(exc_site=["site_sbux_0094"])):
        s = copy.deepcopy(STATE)
        mut(s)
        assert compile_state(s)[1]["wo_reactive_9001"][1] is True


def test_two_providers_one_blacklisted():
    s = copy.deepcopy(STATE)
    p2 = copy.deepcopy(s["providers"][0])
    p2["id"] = "prov_other"
    p2["docs"] = [dict(d, id=d["id"] + "_o") for d in p2["docs"]]
    p2["blacklisted"] = True
    s["providers"].append(p2)
    m, trig = compile_state(s)[1]["wo_reactive_9001"]
    assert m == {"prov_sean_hvac": True, "prov_other": False} and not trig


def test_cli_end_to_end_subprocess(tmp_path):
    out = tmp_path / "p.pddl"
    r = subprocess.run([sys.executable, "-m", "enterprise_pipeline.cli",
                        str(ROOT / "examples/canonical.json"), "--out", str(out),
                        "--plan", "--deadline", "1"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.stdout and (r.returncode == 0 or "planner rc=" in r.stdout), r.stdout + r.stderr
    assert pddl.diff(SPEC.read_text(), out.read_text()) == []
    assert "planner rc=0; 9 steps" in r.stdout


def test_cpsat_matches_minizinc():
    for clock in (0, 525600):
        st = dict(STATE, clock=clock)
        wo = st["work_orders"][0]
        assert align.run_cpsat(st, wo, deadline_s=5) == align.run_minizinc(st, wo)


def test_real_plan_canonical(tmp_path):
    text, _ = compile_state(STATE)
    f = tmp_path / "p.pddl"
    f.write_text(text)
    rc, out, steps = planner.run_planner(f, deadline_s=5)
    assert rc == 0 and "VALID" in out
    assert [x["action"] for x in steps][0] == "activate-entity"
    assert steps[-1]["action"] == "settle-provider-ap-payout" and len(steps) == 9


def test_expired_coi_reactive_branch_has_no_plan(tmp_path):
    st = dict(STATE, clock=525600)
    text, _ = compile_state(st)
    f = tmp_path / "p.pddl"
    f.write_text(text)
    rc, out, steps = planner.run_planner(f, deadline_s=5)
    assert rc == 2 and "NO PLAN" in out and steps == []


def test_parse_plan():
    steps = planner.parse_plan("0.000: (dispatch prov_sean_hvac wo_reactive_9001)  [1.000]\n; c\n")
    assert steps == [{"time": 0.0, "action": "dispatch",
                      "args": ["prov_sean_hvac", "wo_reactive_9001"], "duration": 1.0}]
