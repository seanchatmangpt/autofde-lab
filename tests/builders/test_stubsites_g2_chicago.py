"""Chicago tests: abstract hooks of domain builders raise the typed HookNotImplementedError
on a bare class, and a concrete subclass that overrides the hook satisfies it."""

import pytest

from autofde_lab.builders.domain.dynamics import (
    DeterministicTransitions,
    EnumerableTransitions,
    Environment,
    Simulation,
    UncertainTransitions,
)
from autofde_lab.builders.domain.events import Events
from autofde_lab.builders.domain.initialization import (
    DeterministicInitialized,
    Initializable,
    UncertainInitialized,
)
from autofde_lab.builders.domain.observability import (
    PartiallyObservable,
    TransformedObservable,
)
from autofde_lab.core import HookNotImplementedError

HOOKS = [
    (DeterministicTransitions, "_get_next_state", 2),
    (EnumerableTransitions, "_get_next_state_distribution", 2),
    (Environment, "_state_step", 1),
    (Simulation, "_state_sample", 2),
    (UncertainTransitions, "_get_next_state_distribution", 2),
    (UncertainTransitions, "_get_transition_value", 3),
    (UncertainTransitions, "_is_terminal", 1),
    (Events, "_get_action_space_", 0),
    (Events, "_get_applicable_actions_from", 1),
    (Events, "_get_enabled_events_from", 1),
    (DeterministicInitialized, "_get_initial_state_", 0),
    (Initializable, "_state_reset", 0),
    (UncertainInitialized, "_get_initial_state_distribution_", 0),
    (PartiallyObservable, "_get_observation_distribution", 2),
    (PartiallyObservable, "_get_observation_space_", 0),
    (TransformedObservable, "_get_observation", 1),
]


@pytest.mark.parametrize("cls,hook,nargs", HOOKS)
def test_bare_class_raises_typed_hook_error(cls, hook, nargs):
    bare = type("Bare", (cls,), {})()
    with pytest.raises(HookNotImplementedError) as ei:
        getattr(bare, hook)(*([None] * nargs))
    assert ei.value.hook == hook
    assert ei.value.owner == "Bare"
    assert isinstance(ei.value, NotImplementedError)


@pytest.mark.parametrize("cls,hook,nargs", HOOKS)
def test_concrete_subclass_satisfies_hook(cls, hook, nargs):
    sub = type("Concrete", (cls,), {hook: lambda self, *a, **k: "ok"})()
    assert getattr(sub, hook)(*([None] * nargs)) == "ok"
