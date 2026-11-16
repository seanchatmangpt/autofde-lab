"""M3: K11 (HDDL/HTN + FOND), K12 (classical PDDL), K13 (PPDDL) on the autofde-lab coprocessor.

Real subprocess solvers only. Ferroplan binaries are differential oracles where they run.
"""
import json
import random
import re
from pathlib import Path

import pytest
from plankinds import registry, run_kind

from enterprise_pipeline import autofde_backend as backend

ROOT = Path("/Users/sac/ferroplan")
DOM = ROOT / "domains"
DAM = ROOT / "examples" / "daily_agent_methods"

K11, K12, K13 = (registry()[k] for k in ("K11", "K12", "K13"))


def _need(mod):
    if mod.oracle_probe():
        pytest.skip(mod.oracle_probe().reason)


# ------------------------------------------------------------------ rows
@pytest.mark.parametrize("kind", ["K11", "K12", "K13"])
def test_rows_all_ok(kind):
    rows = run_kind(registry()[kind])
    assert rows and all(r.get("ok") for r in rows), [r for r in rows if not r.get("ok")]


# ------------------------------------------------------------------ K11
def _fond_payload(name, init_text=None):
    pr = (DOM / f"{name}.problem.hddl").read_text()
    if init_text is not None:
        pr = re.sub(r"\(:init.*?\)\s*(?=\(:goal)", init_text + "\n ", pr, count=1, flags=re.S)
    return {"hddl_domain_path": str(DOM / f"{name}.hddl"), "hddl_problem_text": pr}


def _replay_policy(trans, policy, initial, goals, seed, steps=200):
    """Execute the policy against random adversary resolutions of every oneof; must reach goal."""
    rng = random.Random(seed)
    cur = initial
    for _ in range(steps):
        if cur in goals:
            return True
        cur = rng.choice(trans[cur][policy[cur]])
    return False


@pytest.mark.parametrize("name", ["wo-dispatch-fond", "solve_x"])
def test_k11_fond_policy_replays_to_goal_on_three_seeds(name):
    r = backend.solve("fond", _fond_payload(name))
    assert r.status == "PLAN", r
    from autofde_lab.coprocessor import kinds_search  # noqa: F401  (same venv as the kind)
    pol = dict(r.diagnostics["policy"])
    assert pol, r
    # Re-derive the transition system independently from the same HDDL via the kind's grounder.
    from autofde_lab.coprocessor.kinds_search import _fond_from_hddl
    from autofde_lab.coprocessor.envelope import Envelope
    p, bad = _fond_from_hddl(_fond_payload(name) | {
        "hddl_domain_text": (DOM / f"{name}.hddl").read_text()}, Envelope("fond", {}, {}))
    assert bad is None
    for seed in (1, 2, 3):
        assert _replay_policy(p["transitions"], pol, p["initial"], set(p["goals"]), seed)


@pytest.mark.parametrize("name", ["wo-dispatch-fond", "solve_x"])
def test_k11_fond_empty_init_is_infeasible(name):
    r = backend.solve("fond", _fond_payload(name, "(:init)"))
    assert r.status == "INFEASIBLE", r


def test_k11_fond_undeclared_subtask_refused():
    dom = (DOM / "solve_x.hddl").read_text().replace("(:action fence", "(:action fence-renamed")
    r = backend.solve("fond", {"hddl_domain_text": dom,
                               "hddl_problem_text": (DOM / "solve_x.problem.hddl").read_text()})
    assert r.status == "REFUSED" and "fence" in json.dumps(r.diagnostics), r


def test_k11_htn_plan_valid_and_anti_vacuity():
    sa = K11.SA2A.read_text()
    r = backend.solve("htn", {"domain_text": sa, "problem_text": K11.SA2A_PROBLEM})
    assert r.status == "PLAN"
    assert [a[0] for a in r.actions] == ["admit", "select", "construct", "do", "receipt", "replay"]
    bad = backend.solve("htn", {"domain_text": sa, "problem_text": K11.SA2A_PROBLEM.replace(
        "(:init (observed x) (authorized x))", "(:init)")})
    assert bad.status == "NO_PLAN", bad


def test_k11_oracle_differential():
    _need(K11)
    for c in K11.cases():
        o, got = K11.run_oracle(c), K11.run(c)
        assert o.status == got.status == c.expect, (c.id, o, got)


# ------------------------------------------------------------------ K12
@pytest.mark.parametrize("seed", K12.SEEDS)
def test_k12_plan_is_valid_and_optimal(seed):
    prob, dist = K12.travel_instance(seed)
    r = backend.solve("pddl", {"domain_text": K12.TRAVEL_DOMAIN, "problem_text": prob})
    assert r.status == "PLAN" and dist is not None, r
    assert len(r.actions) == dist, (len(r.actions), dist)           # A* is optimal: analytic BFS
    edges = set(re.findall(r"\(road (l\d+) (l\d+)\)", prob))
    start = re.search(r"\(at (l\d+)\)", prob).group(1)
    goal = re.search(r":goal \(at (l\d+)\)", prob).group(1)
    cur = start
    for a in r.actions:                                              # replay validity
        assert a[0] == "go" and a[1] == cur and (a[1], a[2]) in edges, a
        cur = a[2]
    assert cur == goal


@pytest.mark.parametrize("seed", K12.SEEDS)
def test_k12_ff_oracle_agrees(seed):
    _need(K12)
    prob, dist = K12.travel_instance(seed)
    mine = K12.run(K12.Case("x", "PLAN", {"engine": "coprocessor", "problem_text": prob}))
    ff = K12.run_oracle(K12.Case("x", "PLAN", {"engine": "coprocessor", "problem_text": prob}))
    assert mine.status == ff.status == "PLAN", (mine, ff)
    assert int(re.search(r"steps=(\d+)", ff.detail).group(1)) >= dist


def test_k12_disconnected_no_plan_and_connected_flip():
    p0, d0 = K12.travel_instance(K12.SEEDS[0], connected=False)
    assert d0 is None
    r = backend.solve("pddl", {"domain_text": K12.TRAVEL_DOMAIN, "problem_text": p0})
    assert r.status == "NO_PLAN", r
    assert backend.solve("pddl", {"domain_text": K12.TRAVEL_DOMAIN,
                                  "problem_text": K12.travel_instance(K12.SEEDS[0])[0]}).status == "PLAN"


def test_k12_malformed_refused():
    r = backend.solve("pddl", {"domain_text": K12.TRAVEL_DOMAIN, "problem_text": "(define (problem"})
    assert r.status == "REFUSED", r


# ------------------------------------------------------------------ K13
def _ppddl(domain, problem, **opt):
    return backend.solve("mdp", {"ppddl_domain_path": str(domain), "ppddl_problem_path": str(problem)},
                         options=opt, timeout=120)


def test_k13_future_matches_analytic_expected_cost():
    r = _ppddl(DAM / "future" / "domain.ppddl", DAM / "future" / "problem.ppddl")
    assert r.status == "PLAN", r
    # run-bounded-experiment succeeds w.p. 0.60 and is the only stochastic action: P(goal)=0.6.
    assert abs(r.diagnostics["goal_probability"] - 0.6) < 1e-9
    assert abs(r.cost - 13.85) < 1e-9


def test_k13_oracle_differential_on_future():
    _need(K13)
    import subprocess
    out = subprocess.run([str(K13.BIN), "-o", str(DAM / "future/domain.ppddl"), "-f",
                          str(DAM / "future/problem.ppddl")], capture_output=True, text=True, timeout=120)
    j = json.loads(out.stdout)
    mine = _ppddl(DAM / "future" / "domain.ppddl", DAM / "future" / "problem.ppddl")
    assert abs(mine.cost - j["solution"]["initial_value"]) < 1e-9
    assert mine.actions[0][0].split()[0].upper() == j["solution"]["initial_action"].split()[0]


COIN_D = """(define (domain coin) (:requirements :strips :probabilistic-effects :typing)
 (:types coin) (:predicates (heads ?c - coin) (done ?c - coin))
 (:action flip :parameters (?c - coin) :precondition (and (not (done ?c)))
  :effect (probabilistic {p} (and (heads ?c) (done ?c)) {q} (and (done ?c)))))
"""
COIN_P = """(define (problem coin1) (:domain coin) (:objects c1 - coin) (:init) (:goal (heads c1)))"""


@pytest.mark.parametrize("seed", [5, 17, 29])
def test_k13_seeded_goal_probability_is_analytic(seed, tmp_path):
    rng = random.Random(seed)
    p = rng.choice([0.2, 0.35, 0.5, 0.65, 0.8])
    d, pr = tmp_path / "d.ppddl", tmp_path / "p.ppddl"
    d.write_text(COIN_D.format(p=p, q=round(1 - p, 2)))
    pr.write_text(COIN_P)
    r = _ppddl(d, pr)
    assert r.status == "PLAN", r
    assert abs(r.diagnostics["goal_probability"] - p) < 1e-9


def test_k13_unreachable_goal_infeasible(tmp_path):
    d, pr = tmp_path / "d.ppddl", tmp_path / "p.ppddl"
    d.write_text(COIN_D.format(p=0.5, q=0.5))
    pr.write_text(COIN_P.replace("(heads c1)", "(heads c2)").replace("c1 - coin", "c1 c2 - coin")
                  .replace("(:init)", "(:init (done c2))"))
    assert _ppddl(d, pr).status == "INFEASIBLE"


def test_k13_state_bound_refused_matches_oracle_class():
    r = _ppddl(DAM / "snapshots/2026-08-02/domain.ppddl", DAM / "snapshots/2026-08-02/problem.ppddl",
               max_states=2000)
    assert r.status == "REFUSED" and "state bound" in json.dumps(r.diagnostics), r
