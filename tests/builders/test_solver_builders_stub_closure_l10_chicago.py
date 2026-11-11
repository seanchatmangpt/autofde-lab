"""Chicago contract tests for builders/solver capability mixins (lane L10).

Each mixin hook is abstract-by-design: unimplemented -> typed NotImplementedError
naming the class and hook, and flagged __isabstractmethod__; a concrete subclass
satisfies it; a real Astar solver exercises FromAnyState + Utilities end to end.
"""

from __future__ import annotations

import pytest

from autofde_lab import D, DeterministicPlanningDomain, ImplicitSpace, Solver, Space, Value
from autofde_lab.builders.solver import (
    FromAnyState,
    FromInitialState,
    QValues,
    Restorable,
    Utilities,
)
from autofde_lab.hub.domain.graph_domain.GraphDomain import ActionSpace
from autofde_lab.hub.solver.astar.astar import Astar

HOOKS = [
    (Restorable, "_save", ("p",)),
    (Restorable, "_load", ("p",)),
    (FromInitialState, "_solve", ()),
    (FromAnyState, "_solve_from", (0,)),
    (Utilities, "_get_utility", (0,)),
    (QValues, "_get_q_value", (0, "a")),
]


@pytest.mark.parametrize("cls,hook,args", HOOKS)
def test_unimplemented_hook_is_marked_abstract_and_raises_typed(cls, hook, args):
    assert getattr(getattr(cls, hook), "__isabstractmethod__", False) is True
    with pytest.raises(NotImplementedError, match=f"{cls.__name__} must implement {hook}"):
        getattr(cls(), hook)(*args)


def test_restorable_roundtrip(tmp_path):
    class Box(Restorable):
        def __init__(self):
            self.v = 0

        def _save(self, path):
            with open(path, "w") as f:
                f.write(str(self.v))

        def _load(self, path):
            with open(path) as f:
                self.v = int(f.read())

    a, b = Box(), Box()
    a.v = 42
    p = str(tmp_path / "s.txt")
    a.save(p)
    b.load(p)
    assert b.v == 42


class Chain(DeterministicPlanningDomain):
    def __init__(self):
        self.t = {0: {"r": 1}, 1: {"r": 2, "l": 0}, 2: {"r": 3, "l": 1}, 3: {}}

    def _get_next_state(self, memory, event):
        return self.t[memory][event]

    def _get_transition_value(self, memory, event, next_state=None):
        return Value(cost=1.0)

    def _is_terminal(self, state):
        return state == 3

    def _get_action_space_(self) -> Space[D.T_event]:
        return ImplicitSpace(lambda x: True)

    def _get_applicable_actions_from(self, memory):
        return ActionSpace(list(self.t[memory]))

    def _get_goals_(self):
        return ImplicitSpace(lambda x: x == 3)

    def _get_initial_state_(self):
        return 0

    def _get_observation_space_(self):
        return ImplicitSpace(lambda x: True)


def test_astar_solve_from_any_state_and_utility():
    with Astar(domain_factory=Chain) as s:
        s.solve_from(1)
        assert s.get_next_action(1) == "r"
        assert s.get_utility(1).cost == pytest.approx(2.0)


def test_astar_solve_default_initial_state():
    with Astar(domain_factory=Chain) as s:
        s.solve()
        assert s.get_utility(0).cost == pytest.approx(3.0)


def test_from_any_state_none_memory_non_initializable_raises():
    class NoInit(FromAnyState):
        def __init__(self):
            self._domain_factory = lambda: object()

    with pytest.raises(ValueError, match="not initializable"):
        NoInit().solve()


def test_from_any_state_none_memory_initializable_uses_reset_memory():
    seen = []

    class S(FromAnyState):
        def __init__(self):
            self._domain_factory = Chain

        def _solve_from(self, memory):
            seen.append(memory)

    S().solve()
    assert len(seen) == 1
