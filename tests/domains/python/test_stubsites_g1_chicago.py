"""Chicago tests for scheduling hook stubs (lane G1): real classes, no doubles."""

import inspect

import pytest

from autofde_lab.builders.domain.scheduling import (
    conditional_tasks as ct,
    modes,
    preallocations,
    preemptivity,
    resource_availability as ra,
    resource_costs,
    resource_type,
    skills,
    task_duration as td,
)
from autofde_lab.builders.domain.scheduling.scheduling_domains import (
    SchedulingDomain,
)
from autofde_lab.builders.domain.scheduling.scheduling_domains_modelling import State
from autofde_lab.core import HookNotImplementedError

HOOKS = [
    (ct.WithConditionalTasks, "_get_all_condition_items"),
    (ct.WithConditionalTasks, "_get_task_existence_conditions"),
    (ct.WithConditionalTasks, "_get_task_on_completion_added_conditions"),
    (modes.ModeConsumption, "_get_non_zero_ressource_need_names"),
    (modes.ModeConsumption, "_get_resource_need_at_time"),
    (modes.ModeConsumption, "_get_ressource_names"),
    (modes.MultiMode, "_get_tasks_ids"),
    (modes.MultiMode, "_get_tasks_modes"),
    (modes.SingleMode, "_get_tasks_mode"),
    (preallocations.WithPreallocations, "_get_preallocations"),
    (preemptivity.WithPreemptivity, "_get_task_paused_non_renewable_resource_returned"),
    (preemptivity.WithPreemptivity, "_get_task_preemptivity"),
    (preemptivity.WithPreemptivity, "_get_task_resuming_type"),
    (ra.DeterministicResourceAvailabilityChanges, "_get_quantity_resource"),
    (ra.UncertainResourceAvailabilityChanges, "_sample_quantity_resource"),
    (ra.WithoutResourceAvailabilityChange, "_get_original_quantity_resource"),
    (resource_costs.WithModeCosts, "_get_mode_costs"),
    (resource_costs.WithResourceCosts, "_get_resource_cost_per_time_unit"),
    (resource_type.WithResourceTypes, "_get_resource_types_names"),
    (resource_type.WithResourceUnits, "_get_resource_type_for_unit"),
    (resource_type.WithResourceUnits, "_get_resource_units_names"),
    (SchedulingDomain, "_get_max_horizon"),
    (SchedulingDomain, "_get_objectives"),
    (skills.WithResourceSkills, "_get_all_resources_skills"),
    (skills.WithResourceSkills, "_get_all_tasks_skills"),
    (td.DeterministicTaskDuration, "_get_task_duration"),
    (td.SimulatedTaskDuration, "_sample_task_duration"),
    (td.UncertainBoundedTaskDuration, "_get_task_duration_distribution"),
    (td.UncertainBoundedTaskDuration, "_get_task_duration_lower_bound"),
    (td.UncertainBoundedTaskDuration, "_get_task_duration_upper_bound"),
    (td.UncertainMultivariateTaskDuration, "_get_task_duration_distribution"),
    (td.UncertainUnivariateTaskDuration, "_get_task_duration_distribution"),
]


def _call(obj, name):
    fn = getattr(obj, name)
    args = [
        0 if p.annotation in ("int", int) else "x"
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind is p.POSITIONAL_OR_KEYWORD
    ]
    return fn(*args)


@pytest.mark.parametrize("cls,name", HOOKS, ids=[f"{c.__name__}.{n}" for c, n in HOOKS])
def test_bare_hook_raises_typed_error_and_subclass_satisfies(cls, name):
    bare = object.__new__(cls)
    with pytest.raises(HookNotImplementedError) as ei:
        _call(bare, name)
    assert ei.value.hook == name
    assert isinstance(ei.value, NotImplementedError)

    sentinel = object()
    sub = type("Concrete", (cls,), {name: lambda self, *a, **k: sentinel})
    assert _call(object.__new__(sub), name) is sentinel


def test_action_and_observation_spaces_are_real_membership_spaces():
    dom = object.__new__(SchedulingDomain)
    action_space = dom._get_action_space_()
    obs_space = dom._get_observation_space_()
    assert action_space is not None and obs_space is not None
    state = State(task_ids=[1, 2])
    assert obs_space.contains(state)
    assert not obs_space.contains("not a state")
    assert not action_space.contains("not an action")


def test_state_defines_hash_based_equality():
    a, b = State(task_ids=[1, 2]), State(task_ids=[1, 2])
    assert a == b and hash(a) == hash(b)
