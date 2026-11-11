"""ggen-produced from autofde-lab-hook-contracts-pack. Edit the ontology, not this file.

Chicago-style contract court for the abstract hooks autofde-lab hand-writes.
Real classes only: per hook a concrete subclass must satisfy the hook and
a bare subclass must raise the typed error. Classes that cannot be instantiated
generically fail loudly (UNINSTANTIABLE), never skip silently.
Evidence only: authority NONE.
"""

from __future__ import annotations

import importlib

import pytest

from autofde_lab.core import HookNotImplementedError

SENTINEL = object()


def _cls(module: str, name: str) -> type:
    return getattr(importlib.import_module(module), name)


def _args(n: int) -> tuple:
    return (None,) * n


def _kwargs(names: str) -> dict:
    return {k: None for k in names.split(",") if k}


# autofde_lab.builders.domain.constraints.Constrained._get_constraints_  [bare]  Get the domain constraints.

def test_1_bare_Constrained__get_constraints__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.constraints", "Constrained")
    bare = type("BareConstrained", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_constraints_")(*_args(0), **_kwargs(""))


def test_1_concrete_Constrained__get_constraints__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.constraints", "Constrained")
    impl = type(
        "ImplConstrained",
        (owner,),
        {"_get_constraints_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_constraints_") is not getattr(owner, "_get_constraints_")
    assert getattr(impl, "_get_constraints_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.DeterministicTransitions._get_next_state  [typed]  Get the next state given a memory and action.

def test_2_bare_DeterministicTransitions__get_next_state_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "DeterministicTransitions")
    bare = type("BareDeterministicTransitions", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_next_state")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_next_state")
    assert info.value.owner == "BareDeterministicTransitions"


def test_2_concrete_DeterministicTransitions__get_next_state_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "DeterministicTransitions")
    impl = type(
        "ImplDeterministicTransitions",
        (owner,),
        {"_get_next_state": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_next_state") is not getattr(owner, "_get_next_state")
    assert getattr(impl, "_get_next_state")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.EnumerableTransitions._get_next_state_distribution  [typed]  Get the discrete probability distribution of next state given a memory and action.

def test_3_bare_EnumerableTransitions__get_next_state_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "EnumerableTransitions")
    bare = type("BareEnumerableTransitions", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_next_state_distribution")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_next_state_distribution")
    assert info.value.owner == "BareEnumerableTransitions"


def test_3_concrete_EnumerableTransitions__get_next_state_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "EnumerableTransitions")
    impl = type(
        "ImplEnumerableTransitions",
        (owner,),
        {"_get_next_state_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_next_state_distribution") is not getattr(owner, "_get_next_state_distribution")
    assert getattr(impl, "_get_next_state_distribution")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.Environment._state_step  [typed]  Compute one step of the transition's dynamics.

def test_4_bare_Environment__state_step_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "Environment")
    bare = type("BareEnvironment", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_state_step")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_state_step")
    assert info.value.owner == "BareEnvironment"


def test_4_concrete_Environment__state_step_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "Environment")
    impl = type(
        "ImplEnvironment",
        (owner,),
        {"_state_step": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_state_step") is not getattr(owner, "_state_step")
    assert getattr(impl, "_state_step")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.Simulation._state_sample  [typed]  Compute one sample of the transition's dynamics.

def test_5_bare_Simulation__state_sample_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "Simulation")
    bare = type("BareSimulation", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_state_sample")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_state_sample")
    assert info.value.owner == "BareSimulation"


def test_5_concrete_Simulation__state_sample_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "Simulation")
    impl = type(
        "ImplSimulation",
        (owner,),
        {"_state_sample": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_state_sample") is not getattr(owner, "_state_sample")
    assert getattr(impl, "_state_sample")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.UncertainTransitions._get_next_state_distribution  [typed]  Get the probability distribution of next state given a memory and action.

def test_6_bare_UncertainTransitions__get_next_state_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    bare = type("BareUncertainTransitions", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_next_state_distribution")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_next_state_distribution")
    assert info.value.owner == "BareUncertainTransitions"


def test_6_concrete_UncertainTransitions__get_next_state_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    impl = type(
        "ImplUncertainTransitions",
        (owner,),
        {"_get_next_state_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_next_state_distribution") is not getattr(owner, "_get_next_state_distribution")
    assert getattr(impl, "_get_next_state_distribution")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.UncertainTransitions._get_transition_value  [typed]  Get the value (reward or cost) of a transition.

def test_7_bare_UncertainTransitions__get_transition_value_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    bare = type("BareUncertainTransitions", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_transition_value")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_transition_value")
    assert info.value.owner == "BareUncertainTransitions"


def test_7_concrete_UncertainTransitions__get_transition_value_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    impl = type(
        "ImplUncertainTransitions",
        (owner,),
        {"_get_transition_value": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_transition_value") is not getattr(owner, "_get_transition_value")
    assert getattr(impl, "_get_transition_value")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.dynamics.UncertainTransitions._is_terminal  [typed]  Indicate whether a state is terminal.

def test_8_bare_UncertainTransitions__is_terminal_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    bare = type("BareUncertainTransitions", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_is_terminal")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_is_terminal")
    assert info.value.owner == "BareUncertainTransitions"


def test_8_concrete_UncertainTransitions__is_terminal_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.dynamics", "UncertainTransitions")
    impl = type(
        "ImplUncertainTransitions",
        (owner,),
        {"_is_terminal": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_is_terminal") is not getattr(owner, "_is_terminal")
    assert getattr(impl, "_is_terminal")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.events.Events._get_action_space_  [typed]  Get the domain action space (finite or infinite set).

def test_9_bare_Events__get_action_space__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    bare = type("BareEvents", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_action_space_")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_action_space_")
    assert info.value.owner == "BareEvents"


def test_9_concrete_Events__get_action_space__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    impl = type(
        "ImplEvents",
        (owner,),
        {"_get_action_space_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_action_space_") is not getattr(owner, "_get_action_space_")
    assert getattr(impl, "_get_action_space_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.events.Events._get_applicable_actions_from  [typed]  Get the space (finite or infinite set) of applicable actions in the given memory (state or history).

def test_10_bare_Events__get_applicable_actions_from_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    bare = type("BareEvents", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_applicable_actions_from")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_applicable_actions_from")
    assert info.value.owner == "BareEvents"


def test_10_concrete_Events__get_applicable_actions_from_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    impl = type(
        "ImplEvents",
        (owner,),
        {"_get_applicable_actions_from": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_applicable_actions_from") is not getattr(owner, "_get_applicable_actions_from")
    assert getattr(impl, "_get_applicable_actions_from")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.events.Events._get_enabled_events_from  [typed]  Get the space (finite or infinite set) of enabled uncontrollable events in the given memory (state or

def test_11_bare_Events__get_enabled_events_from_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    bare = type("BareEvents", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_enabled_events_from")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_enabled_events_from")
    assert info.value.owner == "BareEvents"


def test_11_concrete_Events__get_enabled_events_from_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.events", "Events")
    impl = type(
        "ImplEvents",
        (owner,),
        {"_get_enabled_events_from": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_enabled_events_from") is not getattr(owner, "_get_enabled_events_from")
    assert getattr(impl, "_get_enabled_events_from")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.goals.Goals._get_goals_  [bare]  Get the domain goals space (finite or infinite set).

def test_12_bare_Goals__get_goals__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.goals", "Goals")
    bare = type("BareGoals", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_goals_")(*_args(0), **_kwargs(""))


def test_12_concrete_Goals__get_goals__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.goals", "Goals")
    impl = type(
        "ImplGoals",
        (owner,),
        {"_get_goals_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_goals_") is not getattr(owner, "_get_goals_")
    assert getattr(impl, "_get_goals_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.initialization.DeterministicInitialized._get_initial_state_  [typed]  Get the initial state.

def test_13_bare_DeterministicInitialized__get_initial_state__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "DeterministicInitialized")
    bare = type("BareDeterministicInitialized", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_initial_state_")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_initial_state_")
    assert info.value.owner == "BareDeterministicInitialized"


def test_13_concrete_DeterministicInitialized__get_initial_state__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "DeterministicInitialized")
    impl = type(
        "ImplDeterministicInitialized",
        (owner,),
        {"_get_initial_state_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_initial_state_") is not getattr(owner, "_get_initial_state_")
    assert getattr(impl, "_get_initial_state_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.initialization.Initializable._state_reset  [typed]  Reset the state of the environment and return an initial state.

def test_14_bare_Initializable__state_reset_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "Initializable")
    bare = type("BareInitializable", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_state_reset")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_state_reset")
    assert info.value.owner == "BareInitializable"


def test_14_concrete_Initializable__state_reset_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "Initializable")
    impl = type(
        "ImplInitializable",
        (owner,),
        {"_state_reset": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_state_reset") is not getattr(owner, "_state_reset")
    assert getattr(impl, "_state_reset")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.initialization.UncertainInitialized._get_initial_state_distribution_  [typed]  Get the probability distribution of initial states.

def test_15_bare_UncertainInitialized__get_initial_state_distribution__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "UncertainInitialized")
    bare = type("BareUncertainInitialized", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_initial_state_distribution_")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_initial_state_distribution_")
    assert info.value.owner == "BareUncertainInitialized"


def test_15_concrete_UncertainInitialized__get_initial_state_distribution__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.initialization", "UncertainInitialized")
    impl = type(
        "ImplUncertainInitialized",
        (owner,),
        {"_get_initial_state_distribution_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_initial_state_distribution_") is not getattr(owner, "_get_initial_state_distribution_")
    assert getattr(impl, "_get_initial_state_distribution_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.memory.FiniteHistory._get_memory_maxlen_  [bare]  Get the memory max length.

def test_16_bare_FiniteHistory__get_memory_maxlen__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.memory", "FiniteHistory")
    bare = type("BareFiniteHistory", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_memory_maxlen_")(*_args(0), **_kwargs(""))


def test_16_concrete_FiniteHistory__get_memory_maxlen__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.memory", "FiniteHistory")
    impl = type(
        "ImplFiniteHistory",
        (owner,),
        {"_get_memory_maxlen_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_memory_maxlen_") is not getattr(owner, "_get_memory_maxlen_")
    assert getattr(impl, "_get_memory_maxlen_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.observability.PartiallyObservable._get_observation_distribution  [typed]  Get the probability distribution of the observation given a state and action.

def test_17_bare_PartiallyObservable__get_observation_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "PartiallyObservable")
    bare = type("BarePartiallyObservable", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_observation_distribution")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_observation_distribution")
    assert info.value.owner == "BarePartiallyObservable"


def test_17_concrete_PartiallyObservable__get_observation_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "PartiallyObservable")
    impl = type(
        "ImplPartiallyObservable",
        (owner,),
        {"_get_observation_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_observation_distribution") is not getattr(owner, "_get_observation_distribution")
    assert getattr(impl, "_get_observation_distribution")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.observability.PartiallyObservable._get_observation_space_  [typed]  Get the observation space (finite or infinite set).

def test_18_bare_PartiallyObservable__get_observation_space__raises() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "PartiallyObservable")
    bare = type("BarePartiallyObservable", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_observation_space_")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_observation_space_")
    assert info.value.owner == "BarePartiallyObservable"


def test_18_concrete_PartiallyObservable__get_observation_space__satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "PartiallyObservable")
    impl = type(
        "ImplPartiallyObservable",
        (owner,),
        {"_get_observation_space_": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_observation_space_") is not getattr(owner, "_get_observation_space_")
    assert getattr(impl, "_get_observation_space_")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.observability.TransformedObservable._get_observation  [typed]  Get the deterministic observation given a state and action.

def test_19_bare_TransformedObservable__get_observation_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "TransformedObservable")
    bare = type("BareTransformedObservable", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_observation")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_observation")
    assert info.value.owner == "BareTransformedObservable"


def test_19_concrete_TransformedObservable__get_observation_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.observability", "TransformedObservable")
    impl = type(
        "ImplTransformedObservable",
        (owner,),
        {"_get_observation": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_observation") is not getattr(owner, "_get_observation")
    assert getattr(impl, "_get_observation")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.renderability.Renderable._render_from  [bare]  Compute a visual render of the given memory (state or history).

def test_20_bare_Renderable__render_from_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.renderability", "Renderable")
    bare = type("BareRenderable", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_render_from")(*_args(1), **_kwargs(""))


def test_20_concrete_Renderable__render_from_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.renderability", "Renderable")
    impl = type(
        "ImplRenderable",
        (owner,),
        {"_render_from": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_render_from") is not getattr(owner, "_render_from")
    assert getattr(impl, "_render_from")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.conditional_tasks.WithConditionalTasks._get_all_condition_items  [typed]  

def test_21_bare_WithConditionalTasks__get_all_condition_items_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    bare = type("BareWithConditionalTasks", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_all_condition_items")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_all_condition_items")
    assert info.value.owner == "BareWithConditionalTasks"


def test_21_concrete_WithConditionalTasks__get_all_condition_items_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    impl = type(
        "ImplWithConditionalTasks",
        (owner,),
        {"_get_all_condition_items": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_all_condition_items") is not getattr(owner, "_get_all_condition_items")
    assert getattr(impl, "_get_all_condition_items")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.conditional_tasks.WithConditionalTasks._get_task_existence_conditions  [typed]  Return a dictionary where the key is a task id and the value a list of conditions to be respected (True)

def test_22_bare_WithConditionalTasks__get_task_existence_conditions_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    bare = type("BareWithConditionalTasks", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_existence_conditions")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_existence_conditions")
    assert info.value.owner == "BareWithConditionalTasks"


def test_22_concrete_WithConditionalTasks__get_task_existence_conditions_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    impl = type(
        "ImplWithConditionalTasks",
        (owner,),
        {"_get_task_existence_conditions": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_existence_conditions") is not getattr(owner, "_get_task_existence_conditions")
    assert getattr(impl, "_get_task_existence_conditions")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.conditional_tasks.WithConditionalTasks._get_task_on_completion_added_conditions  [typed]  

def test_23_bare_WithConditionalTasks__get_task_on_completion_added_conditions_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    bare = type("BareWithConditionalTasks", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_on_completion_added_conditions")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_on_completion_added_conditions")
    assert info.value.owner == "BareWithConditionalTasks"


def test_23_concrete_WithConditionalTasks__get_task_on_completion_added_conditions_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.conditional_tasks", "WithConditionalTasks")
    impl = type(
        "ImplWithConditionalTasks",
        (owner,),
        {"_get_task_on_completion_added_conditions": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_on_completion_added_conditions") is not getattr(owner, "_get_task_on_completion_added_conditions")
    assert getattr(impl, "_get_task_on_completion_added_conditions")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.ModeConsumption._get_non_zero_ressource_need_names  [typed]  

def test_24_bare_ModeConsumption__get_non_zero_ressource_need_names_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    bare = type("BareModeConsumption", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_non_zero_ressource_need_names")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_non_zero_ressource_need_names")
    assert info.value.owner == "BareModeConsumption"


def test_24_concrete_ModeConsumption__get_non_zero_ressource_need_names_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    impl = type(
        "ImplModeConsumption",
        (owner,),
        {"_get_non_zero_ressource_need_names": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_non_zero_ressource_need_names") is not getattr(owner, "_get_non_zero_ressource_need_names")
    assert getattr(impl, "_get_non_zero_ressource_need_names")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.ModeConsumption._get_resource_need_at_time  [typed]  Return the resource consumption for the given resource at the given time.

def test_25_bare_ModeConsumption__get_resource_need_at_time_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    bare = type("BareModeConsumption", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_resource_need_at_time")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_resource_need_at_time")
    assert info.value.owner == "BareModeConsumption"


def test_25_concrete_ModeConsumption__get_resource_need_at_time_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    impl = type(
        "ImplModeConsumption",
        (owner,),
        {"_get_resource_need_at_time": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_need_at_time") is not getattr(owner, "_get_resource_need_at_time")
    assert getattr(impl, "_get_resource_need_at_time")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.ModeConsumption._get_ressource_names  [typed]  

def test_26_bare_ModeConsumption__get_ressource_names_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    bare = type("BareModeConsumption", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_ressource_names")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_ressource_names")
    assert info.value.owner == "BareModeConsumption"


def test_26_concrete_ModeConsumption__get_ressource_names_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "ModeConsumption")
    impl = type(
        "ImplModeConsumption",
        (owner,),
        {"_get_ressource_names": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_ressource_names") is not getattr(owner, "_get_ressource_names")
    assert getattr(impl, "_get_ressource_names")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.MultiMode._get_tasks_ids  [typed]  Return a set or dict of int = id of tasks

def test_27_bare_MultiMode__get_tasks_ids_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "MultiMode")
    bare = type("BareMultiMode", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_tasks_ids")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_tasks_ids")
    assert info.value.owner == "BareMultiMode"


def test_27_concrete_MultiMode__get_tasks_ids_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "MultiMode")
    impl = type(
        "ImplMultiMode",
        (owner,),
        {"_get_tasks_ids": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_tasks_ids") is not getattr(owner, "_get_tasks_ids")
    assert getattr(impl, "_get_tasks_ids")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.MultiMode._get_tasks_modes  [typed]  Return a nested dictionary where the first key is a task id and the second key is a mode id.

def test_28_bare_MultiMode__get_tasks_modes_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "MultiMode")
    bare = type("BareMultiMode", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_tasks_modes")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_tasks_modes")
    assert info.value.owner == "BareMultiMode"


def test_28_concrete_MultiMode__get_tasks_modes_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "MultiMode")
    impl = type(
        "ImplMultiMode",
        (owner,),
        {"_get_tasks_modes": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_tasks_modes") is not getattr(owner, "_get_tasks_modes")
    assert getattr(impl, "_get_tasks_modes")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.modes.SingleMode._get_tasks_mode  [typed]  Return a dictionary where the key is a task id and the value is a ModeConsumption object defining

def test_29_bare_SingleMode__get_tasks_mode_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "SingleMode")
    bare = type("BareSingleMode", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_tasks_mode")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_tasks_mode")
    assert info.value.owner == "BareSingleMode"


def test_29_concrete_SingleMode__get_tasks_mode_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.modes", "SingleMode")
    impl = type(
        "ImplSingleMode",
        (owner,),
        {"_get_tasks_mode": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_tasks_mode") is not getattr(owner, "_get_tasks_mode")
    assert getattr(impl, "_get_tasks_mode")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.preallocations.WithPreallocations._get_preallocations  [typed]  Return a dictionary where the key is the id of a task (int)

def test_30_bare_WithPreallocations__get_preallocations_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preallocations", "WithPreallocations")
    bare = type("BareWithPreallocations", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_preallocations")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_preallocations")
    assert info.value.owner == "BareWithPreallocations"


def test_30_concrete_WithPreallocations__get_preallocations_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preallocations", "WithPreallocations")
    impl = type(
        "ImplWithPreallocations",
        (owner,),
        {"_get_preallocations": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_preallocations") is not getattr(owner, "_get_preallocations")
    assert getattr(impl, "_get_preallocations")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.precedence.WithPrecedence._get_successors  [bare]  Return the successors of the tasks. Successors are given as a list for a task given as a key.

def test_31_bare_WithPrecedence__get_successors_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.precedence", "WithPrecedence")
    bare = type("BareWithPrecedence", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_successors")(*_args(0), **_kwargs(""))


def test_31_concrete_WithPrecedence__get_successors_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.precedence", "WithPrecedence")
    impl = type(
        "ImplWithPrecedence",
        (owner,),
        {"_get_successors": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_successors") is not getattr(owner, "_get_successors")
    assert getattr(impl, "_get_successors")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.preemptivity.WithPreemptivity._get_task_paused_non_renewable_resource_returned  [typed]  Return a dictionary where the key is a task id and the value is of type bool indicating

def test_32_bare_WithPreemptivity__get_task_paused_non_renewable_resource_returned_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    bare = type("BareWithPreemptivity", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_paused_non_renewable_resource_returned")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_paused_non_renewable_resource_returned")
    assert info.value.owner == "BareWithPreemptivity"


def test_32_concrete_WithPreemptivity__get_task_paused_non_renewable_resource_returned_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    impl = type(
        "ImplWithPreemptivity",
        (owner,),
        {"_get_task_paused_non_renewable_resource_returned": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_paused_non_renewable_resource_returned") is not getattr(owner, "_get_task_paused_non_renewable_resource_returned")
    assert getattr(impl, "_get_task_paused_non_renewable_resource_returned")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.preemptivity.WithPreemptivity._get_task_preemptivity  [typed]  Return a dictionary where the key is a task id and the value a boolean indicating

def test_33_bare_WithPreemptivity__get_task_preemptivity_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    bare = type("BareWithPreemptivity", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_preemptivity")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_preemptivity")
    assert info.value.owner == "BareWithPreemptivity"


def test_33_concrete_WithPreemptivity__get_task_preemptivity_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    impl = type(
        "ImplWithPreemptivity",
        (owner,),
        {"_get_task_preemptivity": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_preemptivity") is not getattr(owner, "_get_task_preemptivity")
    assert getattr(impl, "_get_task_preemptivity")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.preemptivity.WithPreemptivity._get_task_resuming_type  [typed]  Return a dictionary where the key is a task id and the value is of type ResumeType indicating

def test_34_bare_WithPreemptivity__get_task_resuming_type_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    bare = type("BareWithPreemptivity", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_resuming_type")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_resuming_type")
    assert info.value.owner == "BareWithPreemptivity"


def test_34_concrete_WithPreemptivity__get_task_resuming_type_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.preemptivity", "WithPreemptivity")
    impl = type(
        "ImplWithPreemptivity",
        (owner,),
        {"_get_task_resuming_type": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_resuming_type") is not getattr(owner, "_get_task_resuming_type")
    assert getattr(impl, "_get_task_resuming_type")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_availability.DeterministicResourceAvailabilityChanges._get_quantity_resource  [typed]  Return the resource availability (int) for the given resource

def test_35_bare_DeterministicResourceAvailabilityChanges__get_quantity_resource_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "DeterministicResourceAvailabilityChanges")
    bare = type("BareDeterministicResourceAvailabilityChanges", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_quantity_resource")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_get_quantity_resource")
    assert info.value.owner == "BareDeterministicResourceAvailabilityChanges"


def test_35_concrete_DeterministicResourceAvailabilityChanges__get_quantity_resource_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "DeterministicResourceAvailabilityChanges")
    impl = type(
        "ImplDeterministicResourceAvailabilityChanges",
        (owner,),
        {"_get_quantity_resource": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_quantity_resource") is not getattr(owner, "_get_quantity_resource")
    assert getattr(impl, "_get_quantity_resource")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_availability.UncertainResourceAvailabilityChanges._sample_quantity_resource  [typed]  Sample an amount of resource availability (int) for the given resource

def test_36_bare_UncertainResourceAvailabilityChanges__sample_quantity_resource_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "UncertainResourceAvailabilityChanges")
    bare = type("BareUncertainResourceAvailabilityChanges", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_sample_quantity_resource")(*_args(2), **_kwargs(""))
    assert info.value.hook.endswith("_sample_quantity_resource")
    assert info.value.owner == "BareUncertainResourceAvailabilityChanges"


def test_36_concrete_UncertainResourceAvailabilityChanges__sample_quantity_resource_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "UncertainResourceAvailabilityChanges")
    impl = type(
        "ImplUncertainResourceAvailabilityChanges",
        (owner,),
        {"_sample_quantity_resource": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_sample_quantity_resource") is not getattr(owner, "_sample_quantity_resource")
    assert getattr(impl, "_sample_quantity_resource")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_availability.WithoutResourceAvailabilityChange._get_original_quantity_resource  [typed]  Return the resource availability (int) for the given resource (either resource type or resource unit).

def test_37_bare_WithoutResourceAvailabilityChange__get_original_quantity_resource_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "WithoutResourceAvailabilityChange")
    bare = type("BareWithoutResourceAvailabilityChange", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_original_quantity_resource")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_original_quantity_resource")
    assert info.value.owner == "BareWithoutResourceAvailabilityChange"


def test_37_concrete_WithoutResourceAvailabilityChange__get_original_quantity_resource_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_availability", "WithoutResourceAvailabilityChange")
    impl = type(
        "ImplWithoutResourceAvailabilityChange",
        (owner,),
        {"_get_original_quantity_resource": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_original_quantity_resource") is not getattr(owner, "_get_original_quantity_resource")
    assert getattr(impl, "_get_original_quantity_resource")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_costs.WithModeCosts._get_mode_costs  [typed]  Return a nested dictionary where the first key is the id of a task (int), the second key the id of a mode

def test_38_bare_WithModeCosts__get_mode_costs_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_costs", "WithModeCosts")
    bare = type("BareWithModeCosts", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_mode_costs")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_mode_costs")
    assert info.value.owner == "BareWithModeCosts"


def test_38_concrete_WithModeCosts__get_mode_costs_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_costs", "WithModeCosts")
    impl = type(
        "ImplWithModeCosts",
        (owner,),
        {"_get_mode_costs": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_mode_costs") is not getattr(owner, "_get_mode_costs")
    assert getattr(impl, "_get_mode_costs")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_costs.WithResourceCosts._get_resource_cost_per_time_unit  [typed]  Return a dictionary where the key is the name of a resource (str)

def test_39_bare_WithResourceCosts__get_resource_cost_per_time_unit_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_costs", "WithResourceCosts")
    bare = type("BareWithResourceCosts", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_resource_cost_per_time_unit")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_resource_cost_per_time_unit")
    assert info.value.owner == "BareWithResourceCosts"


def test_39_concrete_WithResourceCosts__get_resource_cost_per_time_unit_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_costs", "WithResourceCosts")
    impl = type(
        "ImplWithResourceCosts",
        (owner,),
        {"_get_resource_cost_per_time_unit": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_cost_per_time_unit") is not getattr(owner, "_get_resource_cost_per_time_unit")
    assert getattr(impl, "_get_resource_cost_per_time_unit")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_renewability.MixedRenewable._get_resource_renewability  [bare]  Return a dictionary where the key is a resource name (string)

def test_40_bare_MixedRenewable__get_resource_renewability_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_renewability", "MixedRenewable")
    bare = type("BareMixedRenewable", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_resource_renewability")(*_args(0), **_kwargs(""))


def test_40_concrete_MixedRenewable__get_resource_renewability_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_renewability", "MixedRenewable")
    impl = type(
        "ImplMixedRenewable",
        (owner,),
        {"_get_resource_renewability": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_renewability") is not getattr(owner, "_get_resource_renewability")
    assert getattr(impl, "_get_resource_renewability")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_type.WithResourceTypes._get_resource_types_names  [typed]  Return the names (string) of all resource types as a list.

def test_41_bare_WithResourceTypes__get_resource_types_names_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceTypes")
    bare = type("BareWithResourceTypes", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_resource_types_names")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_resource_types_names")
    assert info.value.owner == "BareWithResourceTypes"


def test_41_concrete_WithResourceTypes__get_resource_types_names_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceTypes")
    impl = type(
        "ImplWithResourceTypes",
        (owner,),
        {"_get_resource_types_names": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_types_names") is not getattr(owner, "_get_resource_types_names")
    assert getattr(impl, "_get_resource_types_names")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_type.WithResourceUnits._get_resource_type_for_unit  [typed]  Return a dictionary where the key is a resource unit name and the value a resource type name.

def test_42_bare_WithResourceUnits__get_resource_type_for_unit_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceUnits")
    bare = type("BareWithResourceUnits", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_resource_type_for_unit")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_resource_type_for_unit")
    assert info.value.owner == "BareWithResourceUnits"


def test_42_concrete_WithResourceUnits__get_resource_type_for_unit_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceUnits")
    impl = type(
        "ImplWithResourceUnits",
        (owner,),
        {"_get_resource_type_for_unit": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_type_for_unit") is not getattr(owner, "_get_resource_type_for_unit")
    assert getattr(impl, "_get_resource_type_for_unit")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.resource_type.WithResourceUnits._get_resource_units_names  [typed]  Return the names (string) of all resource units as a list.

def test_43_bare_WithResourceUnits__get_resource_units_names_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceUnits")
    bare = type("BareWithResourceUnits", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_resource_units_names")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_resource_units_names")
    assert info.value.owner == "BareWithResourceUnits"


def test_43_concrete_WithResourceUnits__get_resource_units_names_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.resource_type", "WithResourceUnits")
    impl = type(
        "ImplWithResourceUnits",
        (owner,),
        {"_get_resource_units_names": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_resource_units_names") is not getattr(owner, "_get_resource_units_names")
    assert getattr(impl, "_get_resource_units_names")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.scheduling_domains.SchedulingDomain._get_max_horizon  [typed]  Return the maximum time horizon (int)

def test_44_bare_SchedulingDomain__get_max_horizon_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.scheduling_domains", "SchedulingDomain")
    bare = type("BareSchedulingDomain", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_max_horizon")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_max_horizon")
    assert info.value.owner == "BareSchedulingDomain"


def test_44_concrete_SchedulingDomain__get_max_horizon_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.scheduling_domains", "SchedulingDomain")
    impl = type(
        "ImplSchedulingDomain",
        (owner,),
        {"_get_max_horizon": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_max_horizon") is not getattr(owner, "_get_max_horizon")
    assert getattr(impl, "_get_max_horizon")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.scheduling_domains.SchedulingDomain._get_objectives  [typed]  Return the objectives to consider as a list. The items should be of SchedulingObjectiveEnum type.

def test_45_bare_SchedulingDomain__get_objectives_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.scheduling_domains", "SchedulingDomain")
    bare = type("BareSchedulingDomain", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_objectives")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_objectives")
    assert info.value.owner == "BareSchedulingDomain"


def test_45_concrete_SchedulingDomain__get_objectives_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.scheduling_domains", "SchedulingDomain")
    impl = type(
        "ImplSchedulingDomain",
        (owner,),
        {"_get_objectives": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_objectives") is not getattr(owner, "_get_objectives")
    assert getattr(impl, "_get_objectives")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.skills.WithResourceSkills._get_all_resources_skills  [typed]  Return a nested dictionary where the first key is the name of a resource type or resource unit

def test_46_bare_WithResourceSkills__get_all_resources_skills_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.skills", "WithResourceSkills")
    bare = type("BareWithResourceSkills", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_all_resources_skills")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_all_resources_skills")
    assert info.value.owner == "BareWithResourceSkills"


def test_46_concrete_WithResourceSkills__get_all_resources_skills_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.skills", "WithResourceSkills")
    impl = type(
        "ImplWithResourceSkills",
        (owner,),
        {"_get_all_resources_skills": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_all_resources_skills") is not getattr(owner, "_get_all_resources_skills")
    assert getattr(impl, "_get_all_resources_skills")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.skills.WithResourceSkills._get_all_tasks_skills  [typed]  Return a nested dictionary where the first key is the name of a task

def test_47_bare_WithResourceSkills__get_all_tasks_skills_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.skills", "WithResourceSkills")
    bare = type("BareWithResourceSkills", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_all_tasks_skills")(*_args(0), **_kwargs(""))
    assert info.value.hook.endswith("_get_all_tasks_skills")
    assert info.value.owner == "BareWithResourceSkills"


def test_47_concrete_WithResourceSkills__get_all_tasks_skills_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.skills", "WithResourceSkills")
    impl = type(
        "ImplWithResourceSkills",
        (owner,),
        {"_get_all_tasks_skills": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_all_tasks_skills") is not getattr(owner, "_get_all_tasks_skills")
    assert getattr(impl, "_get_all_tasks_skills")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.DeterministicTaskDuration._get_task_duration  [typed]  Return the fixed deterministic task duration of the given task in the given mode.

def test_48_bare_DeterministicTaskDuration__get_task_duration_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "DeterministicTaskDuration")
    bare = type("BareDeterministicTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration")
    assert info.value.owner == "BareDeterministicTaskDuration"


def test_48_concrete_DeterministicTaskDuration__get_task_duration_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "DeterministicTaskDuration")
    impl = type(
        "ImplDeterministicTaskDuration",
        (owner,),
        {"_get_task_duration": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration") is not getattr(owner, "_get_task_duration")
    assert getattr(impl, "_get_task_duration")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.SimulatedTaskDuration._sample_task_duration  [typed]  Return a task duration for the given task in the given mode.

def test_49_bare_SimulatedTaskDuration__sample_task_duration_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "SimulatedTaskDuration")
    bare = type("BareSimulatedTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_sample_task_duration")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_sample_task_duration")
    assert info.value.owner == "BareSimulatedTaskDuration"


def test_49_concrete_SimulatedTaskDuration__sample_task_duration_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "SimulatedTaskDuration")
    impl = type(
        "ImplSimulatedTaskDuration",
        (owner,),
        {"_sample_task_duration": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_sample_task_duration") is not getattr(owner, "_sample_task_duration")
    assert getattr(impl, "_sample_task_duration")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.UncertainBoundedTaskDuration._get_task_duration_distribution  [typed]  Return the Distribution of the duration of the given task in the given mode.

def test_50_bare_UncertainBoundedTaskDuration__get_task_duration_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    bare = type("BareUncertainBoundedTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration_distribution")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration_distribution")
    assert info.value.owner == "BareUncertainBoundedTaskDuration"


def test_50_concrete_UncertainBoundedTaskDuration__get_task_duration_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    impl = type(
        "ImplUncertainBoundedTaskDuration",
        (owner,),
        {"_get_task_duration_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration_distribution") is not getattr(owner, "_get_task_duration_distribution")
    assert getattr(impl, "_get_task_duration_distribution")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.UncertainBoundedTaskDuration._get_task_duration_lower_bound  [typed]  Return the lower bound for the task duration of the given task in the given mode.

def test_51_bare_UncertainBoundedTaskDuration__get_task_duration_lower_bound_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    bare = type("BareUncertainBoundedTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration_lower_bound")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration_lower_bound")
    assert info.value.owner == "BareUncertainBoundedTaskDuration"


def test_51_concrete_UncertainBoundedTaskDuration__get_task_duration_lower_bound_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    impl = type(
        "ImplUncertainBoundedTaskDuration",
        (owner,),
        {"_get_task_duration_lower_bound": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration_lower_bound") is not getattr(owner, "_get_task_duration_lower_bound")
    assert getattr(impl, "_get_task_duration_lower_bound")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.UncertainBoundedTaskDuration._get_task_duration_upper_bound  [typed]  Return the upper bound for the task duration of the given task in the given mode.

def test_52_bare_UncertainBoundedTaskDuration__get_task_duration_upper_bound_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    bare = type("BareUncertainBoundedTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration_upper_bound")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration_upper_bound")
    assert info.value.owner == "BareUncertainBoundedTaskDuration"


def test_52_concrete_UncertainBoundedTaskDuration__get_task_duration_upper_bound_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainBoundedTaskDuration")
    impl = type(
        "ImplUncertainBoundedTaskDuration",
        (owner,),
        {"_get_task_duration_upper_bound": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration_upper_bound") is not getattr(owner, "_get_task_duration_upper_bound")
    assert getattr(impl, "_get_task_duration_upper_bound")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.UncertainMultivariateTaskDuration._get_task_duration_distribution  [typed]  Return the multivariate Distribution of the duration of the given task in the given mode.

def test_53_bare_UncertainMultivariateTaskDuration__get_task_duration_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainMultivariateTaskDuration")
    bare = type("BareUncertainMultivariateTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration_distribution")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration_distribution")
    assert info.value.owner == "BareUncertainMultivariateTaskDuration"


def test_53_concrete_UncertainMultivariateTaskDuration__get_task_duration_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainMultivariateTaskDuration")
    impl = type(
        "ImplUncertainMultivariateTaskDuration",
        (owner,),
        {"_get_task_duration_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration_distribution") is not getattr(owner, "_get_task_duration_distribution")
    assert getattr(impl, "_get_task_duration_distribution")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_duration.UncertainUnivariateTaskDuration._get_task_duration_distribution  [typed]  Return the univariate Distribution of the duration of the given task in the given mode.

def test_54_bare_UncertainUnivariateTaskDuration__get_task_duration_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainUnivariateTaskDuration")
    bare = type("BareUncertainUnivariateTaskDuration", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_task_duration_distribution")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_task_duration_distribution")
    assert info.value.owner == "BareUncertainUnivariateTaskDuration"


def test_54_concrete_UncertainUnivariateTaskDuration__get_task_duration_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_duration", "UncertainUnivariateTaskDuration")
    impl = type(
        "ImplUncertainUnivariateTaskDuration",
        (owner,),
        {"_get_task_duration_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_duration_distribution") is not getattr(owner, "_get_task_duration_distribution")
    assert getattr(impl, "_get_task_duration_distribution")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.task_progress.CustomTaskProgress._get_task_progress  [bare]  # Returns

def test_55_bare_CustomTaskProgress__get_task_progress_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_progress", "CustomTaskProgress")
    bare = type("BareCustomTaskProgress", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_task_progress")(*_args(4), **_kwargs(""))


def test_55_concrete_CustomTaskProgress__get_task_progress_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.task_progress", "CustomTaskProgress")
    impl = type(
        "ImplCustomTaskProgress",
        (owner,),
        {"_get_task_progress": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_task_progress") is not getattr(owner, "_get_task_progress")
    assert getattr(impl, "_get_task_progress")(*_args(4), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.time_lag.WithTimeLag._get_time_lags  [bare]  Return nested dictionaries where the first key is the id of a task (int)

def test_56_bare_WithTimeLag__get_time_lags_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.time_lag", "WithTimeLag")
    bare = type("BareWithTimeLag", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_time_lags")(*_args(0), **_kwargs(""))


def test_56_concrete_WithTimeLag__get_time_lags_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.time_lag", "WithTimeLag")
    impl = type(
        "ImplWithTimeLag",
        (owner,),
        {"_get_time_lags": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_time_lags") is not getattr(owner, "_get_time_lags")
    assert getattr(impl, "_get_time_lags")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.domain.scheduling.time_windows.WithTimeWindow._get_time_window  [bare]  Return a dictionary where the key is the id of a task (int)

def test_57_bare_WithTimeWindow__get_time_window_raises() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.time_windows", "WithTimeWindow")
    bare = type("BareWithTimeWindow", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_time_window")(*_args(0), **_kwargs(""))


def test_57_concrete_WithTimeWindow__get_time_window_satisfies() -> None:
    owner = _cls("autofde_lab.builders.domain.scheduling.time_windows", "WithTimeWindow")
    impl = type(
        "ImplWithTimeWindow",
        (owner,),
        {"_get_time_window": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_time_window") is not getattr(owner, "_get_time_window")
    assert getattr(impl, "_get_time_window")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.assessability.QValues._get_q_value  [bare]  Get the estimated on-policy Q value of the given observation and action.

def test_58_bare_QValues__get_q_value_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.assessability", "QValues")
    bare = type("BareQValues", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_q_value")(*_args(2), **_kwargs(""))


def test_58_concrete_QValues__get_q_value_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.assessability", "QValues")
    impl = type(
        "ImplQValues",
        (owner,),
        {"_get_q_value": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_q_value") is not getattr(owner, "_get_q_value")
    assert getattr(impl, "_get_q_value")(*_args(2), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.assessability.Utilities._get_utility  [bare]  Get the estimated on-policy utility of the given observation.

def test_59_bare_Utilities__get_utility_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.assessability", "Utilities")
    bare = type("BareUtilities", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_get_utility")(*_args(1), **_kwargs(""))


def test_59_concrete_Utilities__get_utility_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.assessability", "Utilities")
    impl = type(
        "ImplUtilities",
        (owner,),
        {"_get_utility": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_utility") is not getattr(owner, "_get_utility")
    assert getattr(impl, "_get_utility")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.fromanystatesolvability.FromAnyState._solve_from  [bare]  Run the solving process from a given state.

def test_60_bare_FromAnyState__solve_from_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.fromanystatesolvability", "FromAnyState")
    bare = type("BareFromAnyState", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_solve_from")(*_args(1), **_kwargs(""))


def test_60_concrete_FromAnyState__solve_from_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.fromanystatesolvability", "FromAnyState")
    impl = type(
        "ImplFromAnyState",
        (owner,),
        {"_solve_from": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_solve_from") is not getattr(owner, "_solve_from")
    assert getattr(impl, "_solve_from")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.fromanystatesolvability.FromInitialState._solve  [bare]  Run the solving process.

def test_61_bare_FromInitialState__solve_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.fromanystatesolvability", "FromInitialState")
    bare = type("BareFromInitialState", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_solve")(*_args(0), **_kwargs(""))


def test_61_concrete_FromInitialState__solve_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.fromanystatesolvability", "FromInitialState")
    impl = type(
        "ImplFromInitialState",
        (owner,),
        {"_solve": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_solve") is not getattr(owner, "_solve")
    assert getattr(impl, "_solve")(*_args(0), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.policy.DeterministicPolicies._get_next_action  [typed]  Get the next deterministic action (from the solver's current policy).

def test_62_bare_DeterministicPolicies__get_next_action_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "DeterministicPolicies")
    bare = type("BareDeterministicPolicies", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_next_action")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_next_action")
    assert info.value.owner == "BareDeterministicPolicies"


def test_62_concrete_DeterministicPolicies__get_next_action_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "DeterministicPolicies")
    impl = type(
        "ImplDeterministicPolicies",
        (owner,),
        {"_get_next_action": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_next_action") is not getattr(owner, "_get_next_action")
    assert getattr(impl, "_get_next_action")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.policy.Policies._is_policy_defined_for  [typed]  Check whether the solver's current policy is defined for the given observation.

def test_63_bare_Policies__is_policy_defined_for_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "Policies")
    bare = type("BarePolicies", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_is_policy_defined_for")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_is_policy_defined_for")
    assert info.value.owner == "BarePolicies"


def test_63_concrete_Policies__is_policy_defined_for_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "Policies")
    impl = type(
        "ImplPolicies",
        (owner,),
        {"_is_policy_defined_for": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_is_policy_defined_for") is not getattr(owner, "_is_policy_defined_for")
    assert getattr(impl, "_is_policy_defined_for")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.policy.Policies._sample_action  [typed]  Sample an action for the given observation (from the solver's current policy).

def test_64_bare_Policies__sample_action_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "Policies")
    bare = type("BarePolicies", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_sample_action")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_sample_action")
    assert info.value.owner == "BarePolicies"


def test_64_concrete_Policies__sample_action_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "Policies")
    impl = type(
        "ImplPolicies",
        (owner,),
        {"_sample_action": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_sample_action") is not getattr(owner, "_sample_action")
    assert getattr(impl, "_sample_action")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.policy.UncertainPolicies._get_next_action_distribution  [typed]  Get the probabilistic distribution of next action for the given observation (from the solver's current

def test_65_bare_UncertainPolicies__get_next_action_distribution_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "UncertainPolicies")
    bare = type("BareUncertainPolicies", (owner,), {})()

    with pytest.raises(HookNotImplementedError) as info:
        getattr(bare, "_get_next_action_distribution")(*_args(1), **_kwargs(""))
    assert info.value.hook.endswith("_get_next_action_distribution")
    assert info.value.owner == "BareUncertainPolicies"


def test_65_concrete_UncertainPolicies__get_next_action_distribution_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.policy", "UncertainPolicies")
    impl = type(
        "ImplUncertainPolicies",
        (owner,),
        {"_get_next_action_distribution": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_get_next_action_distribution") is not getattr(owner, "_get_next_action_distribution")
    assert getattr(impl, "_get_next_action_distribution")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.restorability.Restorable._load  [bare]  Restore the solver state from given path.

def test_66_bare_Restorable__load_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.restorability", "Restorable")
    bare = type("BareRestorable", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_load")(*_args(1), **_kwargs(""))


def test_66_concrete_Restorable__load_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.restorability", "Restorable")
    impl = type(
        "ImplRestorable",
        (owner,),
        {"_load": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_load") is not getattr(owner, "_load")
    assert getattr(impl, "_load")(*_args(1), **_kwargs("")) is SENTINEL


# autofde_lab.builders.solver.restorability.Restorable._save  [bare]  Save the solver state to given path.

def test_67_bare_Restorable__save_raises() -> None:
    owner = _cls("autofde_lab.builders.solver.restorability", "Restorable")
    bare = type("BareRestorable", (owner,), {})()

    with pytest.raises(NotImplementedError):
        getattr(bare, "_save")(*_args(1), **_kwargs(""))


def test_67_concrete_Restorable__save_satisfies() -> None:
    owner = _cls("autofde_lab.builders.solver.restorability", "Restorable")
    impl = type(
        "ImplRestorable",
        (owner,),
        {"_save": lambda self, *a, **k: SENTINEL},
    )()
    assert getattr(type(impl), "_save") is not getattr(owner, "_save")
    assert getattr(impl, "_save")(*_args(1), **_kwargs("")) is SENTINEL


