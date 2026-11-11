"""L17: misc domain stub closure (Chicago style: real domains, real solvers)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from autofde_lab import ImplicitSpace, utils
from autofde_lab.hub.domain.pddl import PDDLDomain
from autofde_lab.hub.domain.pddl.domain import PDDLAction, PDDLActionSpace

BLOCKS = Path(__file__).resolve().parent / "pddl_domains/blocks"
DOMAIN = str(BLOCKS / "domain.pddl")
PROBLEM = str(BLOCKS / "probBLOCKS-3-0.pddl")
UNSOLVABLE = (
    "(define (problem U) (:domain BLOCKS) (:objects A B) "
    "(:init (ONTABLE A) (ONTABLE B) (CLEAR A) (CLEAR B) (HANDEMPTY)) "
    "(:goal (AND (ON A B) (ON B A))))\n"
)


def _domain(problem: str = PROBLEM) -> PDDLDomain:
    return PDDLDomain(DOMAIN, problem)


def test_pddl_action_space_is_an_implicit_space_with_type_membership():
    d = _domain()
    space = d.get_action_space()
    assert isinstance(space, PDDLActionSpace) and isinstance(space, ImplicitSpace)
    action = space.sample_from(d.reset())
    assert action in space
    assert "not-an-action" not in space


def test_sample_from_returns_an_applicable_action_and_progresses_state():
    d = _domain()
    s = d.reset()
    space = d.get_action_space()
    applicable = space.applicable(s)
    assert applicable
    a = space.sample_from(s, random.Random(0))
    assert a in applicable
    assert d.get_next_state(s, a) != s


def test_bare_sample_is_a_typed_error_not_attributeerror():
    with pytest.raises(TypeError, match="state-dependent"):
        _domain().get_action_space().sample()


def test_sample_from_dead_end_raises_lookuperror():
    d = _domain()
    space = d.get_action_space()
    state = d.reset()
    # walk until a dead end or goal; blocks always has actions, so use an empty applicable fn
    empty = PDDLActionSpace(PDDLAction, lambda s: [])
    with pytest.raises(LookupError):
        empty.sample_from(state)
    assert space.applicable(state)


def test_astar_on_unsolvable_problem_does_not_crash(tmp_path):
    p = tmp_path / "u.pddl"
    p.write_text(UNSOLVABLE)
    d = _domain(str(p))
    astar = utils.load_registered_solver("Astar")
    with astar(domain_factory=lambda: d) as solver:
        solver.solve()
        assert solver.is_policy_defined_for(d.reset()) is False


def test_registered_domains_load_and_default_constructible_ones_step():
    stepped = []
    for name in utils.get_registered_domains():
        cls = utils.load_registered_domain(name)
        if name in {"MasterMind", "Maze", "SimpleGridWorld", "RockPaperScissors"}:
            d = cls()
            s = d.reset()
            if name == "RockPaperScissors":
                continue
            a = d.get_applicable_actions(s).get_elements()[0]
            out = d.step(a)
            assert out is not None
            stepped.append(name)
    assert set(stepped) == {"MasterMind", "Maze", "SimpleGridWorld"}


def test_rddl_domain_loads_and_steps():
    pytest.importorskip("pyRDDLGym")
    from autofde_lab.hub.domain.rddl import RDDLDomainRL

    d = RDDLDomainRL(
        rddl_domain="CartPole_Continuous_gym",
        rddl_instance="0",
        display_with_pygame=False,
        display_within_jupyter=False,
    )
    s = d.reset()
    a = d.get_action_space().sample()
    assert d.step(a) is not None and s is not None
