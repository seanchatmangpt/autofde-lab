"""Chicago-style tests for coprocessor kinds pddl, temporal_pddl, htn.

Every case is a real subprocess ``python -m autofde_lab.coprocessor <kind>``
against real solvers; problems are built from a seeded RNG.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BLOCKS_DOMAIN = ROOT / "tests/domains/python/pddl_domains/blocks/domain.pddl"
HTN_DIR = ROOT / "tests/domains/htn_fixtures"
SEED = 20261111

TEMPORAL_DOMAIN = """(define (domain tw) (:requirements :typing :durative-actions)
 (:types loc)
 (:predicates (at ?l - loc) (road ?a ?b - loc))
 (:durative-action go :parameters (?a ?b - loc)
  :duration (= ?duration 5)
  :condition (and (at start (at ?a)) (at start (road ?a ?b)))
  :effect (and (at start (not (at ?a))) (at end (at ?b)))))
"""


def run_kind(kind: str, payload: dict, tmp_path: Path, extra_env=None, options=None):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AUTOFDE_WORK"] = str(tmp_path)
    env.update(extra_env or {})
    proc = subprocess.run(
        [sys.executable, "-m", "autofde_lab.coprocessor", kind],
        input=json.dumps({"payload": payload, "options": options or {}}),
        capture_output=True, text=True, timeout=300, env=env, cwd=str(ROOT),
    )
    out = proc.stdout.strip().splitlines()
    assert out, f"no stdout; stderr tail: {proc.stderr[-400:]}"
    return proc.returncode, proc.stdout, json.loads(out[-1])


def blocks_problem(rng: random.Random, n: int):
    names = [f"b{i}" for i in range(n)]
    rng.shuffle(names)
    # initial: all on table; goal: random tower
    order = names[:]
    rng.shuffle(order)
    goal = " ".join(f"(on {order[i]} {order[i + 1]})" for i in range(n - 1))
    init = " ".join(f"(ontable {b}) (clear {b})" for b in names)
    text = (
        f"(define (problem gen) (:domain blocks) (:objects {' '.join(names)})"
        f" (:init {init} (handempty)) (:goal (and {goal})))"
    )
    return text, order


def replay_blocks(order, actions):
    ontable = {b: True for b in order}
    on, holding = {}, None
    for name, *args in actions:
        if name == "pick-up":
            assert holding is None and ontable.pop(args[0])
            holding = args[0]
        elif name == "unstack":
            assert holding is None and on.pop(args[0]) == args[1]
            holding = args[0]
        elif name == "put-down":
            assert holding == args[0]
            ontable[holding] = True
            holding = None
        elif name == "stack":
            assert holding == args[0]
            on[args[0]] = args[1]
            holding = None
        else:
            raise AssertionError(name)
    for i in range(len(order) - 1):
        assert on.get(order[i]) == order[i + 1]


def test_pddl_plan_replays_to_goal(tmp_path):
    rng = random.Random(SEED)
    text, order = blocks_problem(rng, 3)
    rc, raw, res = run_kind(
        "pddl", {"domain_path": str(BLOCKS_DOMAIN), "problem_text": text}, tmp_path
    )
    assert rc == 0 and res["status"] == "PLAN"
    assert res["cost"] == len(res["actions"]) > 0
    replay_blocks(order, res["actions"])


def test_pddl_output_is_canonical_and_deterministic(tmp_path):
    text, _ = blocks_problem(random.Random(SEED), 3)
    payload = {"domain_path": str(BLOCKS_DOMAIN), "problem_text": text}
    _, raw1, res1 = run_kind("pddl", payload, tmp_path)
    _, raw2, _ = run_kind("pddl", payload, tmp_path)
    assert raw1 == raw2
    assert raw1.strip() == json.dumps(res1, sort_keys=True, separators=(",", ":"))


def test_pddl_no_plan_on_unreachable_goal(tmp_path):
    text = (
        "(define (problem bad) (:domain blocks) (:objects a b)"
        " (:init (ontable a) (ontable b) (clear a) (clear b) (handempty))"
        " (:goal (and (on a b) (on b a))))"
    )
    rc, _, res = run_kind(
        "pddl", {"domain_path": str(BLOCKS_DOMAIN), "problem_text": text}, tmp_path
    )
    assert rc == 2 and res["status"] == "NO_PLAN" and res["actions"] == []


def test_pddl_refused_on_garbage_domain(tmp_path):
    rc, _, res = run_kind(
        "pddl", {"domain_text": "(this is not pddl", "problem_text": "(nor this"}, tmp_path
    )
    assert rc == 2 and res["status"] == "REFUSED"


def test_envelope_missing_payload_fields_refused(tmp_path):
    rc, _, res = run_kind("pddl", {}, tmp_path)
    assert rc == 2 and res["status"] == "REFUSED"


def temporal_problem(rng: random.Random, n: int, reachable: bool):
    locs = [f"l{i}" for i in range(n)]
    roads = " ".join(f"(road {locs[i]} {locs[i + 1]})" for i in range(n - 1))
    goal = locs[-1] if reachable else locs[0]
    init_at = locs[0] if reachable else locs[-1]
    return (
        f"(define (problem tp) (:domain tw) (:objects {' '.join(locs)} - loc)"
        f" (:init (at {init_at}) {roads}) (:goal (at {goal})))"
    ), locs


def test_temporal_plan_has_ordered_durations(tmp_path):
    n = random.Random(SEED).randint(3, 4)
    text, locs = temporal_problem(random.Random(SEED), n, True)
    rc, _, res = run_kind(
        "temporal_pddl", {"domain_text": TEMPORAL_DOMAIN, "problem_text": text}, tmp_path
    )
    assert rc == 0 and res["status"] == "PLAN"
    acts = res["actions"]
    assert len(acts) == n - 1
    for i, a in enumerate(acts):
        assert a["action"] == f"go({locs[i]}, {locs[i + 1]})"
        assert a["duration"] == 5.0
        if i:
            assert a["start"] >= acts[i - 1]["start"] + acts[i - 1]["duration"]
    assert res["cost"] >= 5.0 * (n - 1)


def test_temporal_no_plan_when_goal_unreachable(tmp_path):
    text, _ = temporal_problem(random.Random(SEED), 3, False)
    rc, _, res = run_kind(
        "temporal_pddl", {"domain_text": TEMPORAL_DOMAIN, "problem_text": text}, tmp_path,
        options={"timeout": 15},
    )
    assert rc == 2 and res["status"] in ("NO_PLAN", "INFEASIBLE")


def test_temporal_refused_on_garbage(tmp_path):
    rc, _, res = run_kind(
        "temporal_pddl", {"domain_text": "(oops", "problem_text": "(oops"}, tmp_path
    )
    assert rc == 2 and res["status"] == "REFUSED"


def test_htn_plan_follows_method_order(tmp_path):
    rc, _, res = run_kind(
        "htn",
        {
            "domain_path": str(HTN_DIR / "verify-and-commit.hddl"),
            "problem_path": str(HTN_DIR / "verify-and-commit-problem.hddl"),
        },
        tmp_path,
    )
    assert rc == 0 and res["status"] == "PLAN"
    names = [a[0] for a in res["actions"]]
    assert names[:3] == ["compile", "migrate", "test"] and len(names) == 5
    assert names[-1].startswith("commit")


def test_htn_no_plan_when_precondition_missing(tmp_path):
    problem = (HTN_DIR / "verify-and-commit-problem.hddl").read_text()
    broken = problem.replace("(edited repo1 changeset1)", "")
    rc, _, res = run_kind(
        "htn",
        {"domain_path": str(HTN_DIR / "verify-and-commit.hddl"), "problem_text": broken},
        tmp_path,
    )
    assert rc == 2 and res["status"] == "NO_PLAN" and res["actions"] == []


def test_htn_refused_on_garbage(tmp_path):
    rc, _, res = run_kind(
        "htn", {"domain_text": "(nope", "problem_text": "(nope"}, tmp_path
    )
    assert rc == 2 and res["status"] == "REFUSED"


def test_absent_kind_module_reports_blocked(tmp_path):
    # kinds_search/planning/rl may or may not exist yet; an unknown kind must be
    # either BLOCKED:<module> (exit 3) or REFUSED unknown kind (exit 2), never PLAN.
    rc, _, res = run_kind("no_such_kind", {}, tmp_path)
    assert res["status"] in ("BLOCKED", "REFUSED") and res["actions"] == []
    assert rc == (3 if res["status"] == "BLOCKED" else 2)
