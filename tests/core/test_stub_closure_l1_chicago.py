"""Chicago-style tests: typed abstract-hook errors and autocast error typing (lane L1)."""

from __future__ import annotations

import pytest

from autofde_lab import Domain
from autofde_lab.builders.domain import (
    FullyObservable,
    Markovian,
    MultiAgent,
    Sequential,
    SingleAgent,
)
from autofde_lab.builders.solver.policy import (
    DeterministicPolicies,
    Policies,
    UncertainPolicies,
)
from autofde_lab.core import (
    AutocastError,
    Castable,
    Constraint,
    Distribution,
    EnumerableSpace,
    HookNotImplementedError,
    SamplableSpace,
    Space,
    autocast,
)


@pytest.mark.parametrize(
    "factory,call,hook",
    [
        (Castable, lambda o: o._cast([], []), "Castable._cast"),
        (Space, lambda o: o.contains(1), "Space.contains"),
        (EnumerableSpace, lambda o: o.get_elements(), "EnumerableSpace.get_elements"),
        (SamplableSpace, lambda o: o.sample(), "SamplableSpace.sample"),
        (Distribution, lambda o: o.sample(), "Distribution.sample"),
        (Constraint, lambda o: o.check(None, None), "Constraint.check"),
        (
            Constraint,
            lambda o: o._is_constraint_dependent_on_next_state_(),
            "Constraint._is_constraint_dependent_on_next_state_",
        ),
        (Policies, lambda o: o._sample_action(0), "Policies._sample_action"),
        (
            Policies,
            lambda o: o._is_policy_defined_for(0),
            "Policies._is_policy_defined_for",
        ),
        (
            UncertainPolicies,
            lambda o: o._get_next_action_distribution(0),
            "UncertainPolicies._get_next_action_distribution",
        ),
        (
            DeterministicPolicies,
            lambda o: o._get_next_action(0),
            "DeterministicPolicies._get_next_action",
        ),
    ],
)
def test_unoverridden_hook_raises_typed_error(factory, call, hook):
    obj = factory()
    with pytest.raises(HookNotImplementedError) as ei:
        call(obj)
    assert isinstance(ei.value, NotImplementedError)
    assert ei.value.hook == hook
    assert ei.value.owner == factory.__name__
    assert hook in str(ei.value)


def test_concrete_subclass_satisfies_hook_contract():
    class Even(Space):
        def contains(self, x):
            return x % 2 == 0

    class Fixed(DeterministicPolicies):
        def _get_next_action(self, observation, domain=None):
            return "go"

    assert 4 in Even() and 3 not in Even()
    assert Fixed().get_next_action_distribution is not None
    assert Fixed()._get_next_action_distribution(0).sample() == "go"


class _Single(Domain, SingleAgent, Sequential, FullyObservable, Markovian):
    pass


class _Multi(Domain, MultiAgent, Sequential, FullyObservable, Markovian):
    pass


def _ident():
    from autofde_lab.core import D  # noqa: F401  (annotation namespace)

    def f(observation: D.T_agent[D.T_observation]):  # noqa: F821
        return observation

    return f


def test_autocast_cast_failure_is_typed_and_chained():
    wrapped = autocast(_ident(), _Single, _Multi)
    # caller side is multi-agent (dict); a bare string cannot be cast
    with pytest.raises(AutocastError) as ei:
        wrapped("not-a-dict")
    assert ei.value.__cause__ is not None


def test_autocast_function_own_errors_pass_through_untyped():
    from autofde_lab.core import D  # noqa: F401

    def f(observation: D.T_agent[D.T_observation]):  # noqa: F821
        raise KeyError("own")

    wrapped = autocast(f, _Single, _Multi)
    with pytest.raises(KeyError):
        wrapped({"agent": 1})


def test_autocast_good_cast_still_works():
    assert autocast(_ident(), _Single, _Multi)({"agent": 7}) == 7
    assert autocast(_ident(), _Multi, _Single)(7) == {"agent": 7}
