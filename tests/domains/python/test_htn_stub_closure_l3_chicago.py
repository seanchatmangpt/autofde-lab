# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""L3: numeric and fluent effects/conditions in the from-scratch HTN planner.

Chicago style: real HDDL parsed by unified-planning's real reader, real planner,
independent oracle = unified-planning's SequentialSimulator replaying the plan
(and up-aries when it accepts the problem).
"""

from fractions import Fraction

import pytest

pytest.importorskip("unified_planning")

from unified_planning.engines.sequential_simulator import UPSequentialSimulator as SequentialSimulator
from unified_planning.io import PDDLReader
from unified_planning.shortcuts import FluentExp

from autofde_lab.hub.domain.htn.domain import HTNDomain
from autofde_lab.hub.domain.htn.planner import (
    HTNPlanningFailure,
    HTNTotalOrderPlanner,
)

DOMAIN = """(define (domain d)
 (:requirements :typing :hierarchy :numeric-fluents :negative-preconditions)
 (:types loc)
 (:predicates (at ?l - loc) (rich) (low) (bonus))
 (:functions (fuel) (cost) (ratio) - number)
 (:task go :parameters (?a - loc ?b - loc))
 (:method m-go :parameters (?a - loc ?b - loc) :task (go ?a ?b)
   :precondition (>= (fuel) 3)
   :ordered-subtasks (and (drive ?a ?b) (fill) (drive ?b ?a)))
 (:action drive :parameters (?a - loc ?b - loc)
   :precondition (and (at ?a) (>= (fuel) 3))
   :effect (and (not (at ?a)) (at ?b) (decrease (fuel) 3)
                (increase (cost) (fuel))
                (when (< (fuel) 5) (rich))
                (when (= (fuel) 4) (low))))
 (:action fill :parameters ()
   :effect (and (assign (fuel) (* 2 (+ (fuel) 1))) (assign (ratio) (/ (fuel) 4)))))
"""
PROBLEM = """(define (problem p) (:domain d) (:objects x y - loc)
 (:htn :ordered-subtasks (and (go x y)))
 (:init (at x) (= (fuel) 4) (= (cost) 0) (= (ratio) 0)))"""


def _num(state, name):
    return next(a[2] for a in state if len(a) == 3 and a[0] == name)


def _oracle_replay(problem, plan):
    sim = SequentialSimulator(problem, error_on_failed_checks=False)
    st = sim.get_initial_state()
    for ga in plan:
        act = problem.action(ga.name)
        objs = [problem.object(n) for n in ga.args]
        st = sim.apply(st, act, objs)
        assert st is not None, f"oracle rejected {ga}"
    return st


def test_numeric_effects_match_up_sequential_simulator_oracle():
    problem = PDDLReader().parse_problem_string(DOMAIN, PROBLEM)
    planner = HTNTotalOrderPlanner(problem)
    plan = planner.solve()
    assert [g.name for g in plan] == ["drive", "fill", "drive"]

    # Replay own semantics.
    from autofde_lab.hub.domain.htn.planner import _apply_effects

    state = planner.initial_state()
    for ga in plan:
        act = problem.action(ga.name)
        b = {p.name: v for p, v in zip(act.parameters, ga.args)}
        state = _apply_effects(act, b, state)

    # Hand-computed: fuel 4 -> drive: fuel 1, cost 0+4(pre-state fuel)=4, rich, low
    # fill: fuel=2*(1+1)=4, ratio=1/4 uses pre-state fuel(1) -> 1/4
    # drive: fuel 1, cost 4+4=8
    assert _num(state, "fuel") == Fraction(1)
    assert _num(state, "cost") == Fraction(8)
    assert _num(state, "ratio") == Fraction(1, 4)
    assert ("rich", ()) in state and ("low", ()) in state
    assert ("at", ("x",)) in state and ("at", ("y",)) not in state

    # Independent oracle.
    st = _oracle_replay(problem, plan)
    for name in ("fuel", "cost", "ratio"):
        fl = problem.fluent(name)
        assert Fraction(st.get_value(FluentExp(fl)).constant_value()) == _num(state, name)
    for name in ("rich", "low"):
        assert st.get_value(FluentExp(problem.fluent(name))).is_true() is (
            (name, ()) in state
        )


def test_numeric_precondition_failure_is_refused_not_faked():
    bad = PROBLEM.replace("(= (fuel) 4)", "(= (fuel) 2)")
    problem = PDDLReader().parse_problem_string(DOMAIN, bad)
    with pytest.raises(HTNPlanningFailure):
        HTNTotalOrderPlanner(problem).solve()


def test_htn_domain_executes_numeric_plan_through_domain_protocol(tmp_path):
    d = tmp_path / "d.hddl"
    p = tmp_path / "p.hddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM)
    dom = HTNDomain(str(d), str(p))
    state = dom.get_initial_state()
    for ga in dom.plan:
        state = dom.get_next_state(state, ga)
    assert dom.is_terminal(state)
    assert _num(state.atoms, "cost") == Fraction(8)


EXPR_DOMAIN = """(define (domain e)
 (:requirements :typing :hierarchy :numeric-fluents :negative-preconditions
   :disjunctive-preconditions :existential-preconditions :universal-preconditions)
 (:types item)
 (:constants a - item)
 (:predicates (has ?i - item) (done) (flag))
 (:functions (n) (w ?i - item) - number)
 (:task t :parameters ())
 (:method m :parameters () :task (t)
   :precondition (and (exists (?i - item) (and (has ?i) (> (w ?i) 2)))
                      (imply (flag) (done)) (< (n) 10) (<= (n) 5))
   :ordered-subtasks (and (step)))
 (:action step :parameters ()
   :effect (and (done) (increase (n) (w a)) (decrease (n) 1))))
"""
EXPR_PROBLEM = """(define (problem q) (:domain e) (:objects b - item)
 (:htn :ordered-subtasks (and (t)))
 (:init (has b) (= (w a) 5) (= (w b) 3) (= (n) 1)))"""


def test_exists_implies_comparisons_and_fluent_valued_increase():
    problem = PDDLReader().parse_problem_string(EXPR_DOMAIN, EXPR_PROBLEM)
    planner = HTNTotalOrderPlanner(problem)
    plan = planner.solve()
    from autofde_lab.hub.domain.htn.planner import _apply_effects

    act = problem.action("step")
    state = _apply_effects(act, {}, planner.initial_state())
    assert _num(state, "n") == Fraction(5)  # 1 + 5 - 1
    st = _oracle_replay(problem, plan)
    assert Fraction(st.get_value(FluentExp(problem.fluent("n"))).constant_value()) == 5


def test_exists_has_no_witness_refused():
    problem = PDDLReader().parse_problem_string(
        EXPR_DOMAIN, EXPR_PROBLEM.replace("(has b)", "")
    )
    with pytest.raises(HTNPlanningFailure):
        HTNTotalOrderPlanner(problem).solve()


def test_up_aries_oracle_agrees_when_it_accepts_numeric_htn():
    pytest.importorskip("up_aries")
    from unified_planning.shortcuts import OneshotPlanner

    problem = PDDLReader().parse_problem_string(DOMAIN, PROBLEM)
    try:
        with OneshotPlanner(name="aries") as aries:
            res = aries.solve(problem)
    except Exception as exc:  # engine refuses numeric HTN: loud skip
        pytest.skip(f"up-aries refused numeric HTN problem: {type(exc).__name__}: {exc}")
    if res.plan is None:
        msgs = " | ".join(m.message for m in (res.log_messages or []))
        pytest.skip(f"up-aries returned no plan: {res.status}: {msgs}")
    mine = [g.name for g in HTNTotalOrderPlanner(problem).solve()]
    assert [a.action.name for a in res.plan.actions] == mine
