"""L2: scheduling stub closure. Real RCPSP domain + CP-SAT solver, concrete subclasses for hooks."""

from __future__ import annotations

import pytest

from autofde_lab.builders.domain.scheduling.modes import (
    ConstantModeConsumption,
    MultiMode,
    SingleMode,
    VaryingModeConsumption,
)
from autofde_lab.builders.domain.scheduling.preallocations import WithPreallocations
from autofde_lab.builders.domain.scheduling.resource_costs import WithModeCosts, WithResourceCosts
from autofde_lab.builders.domain.scheduling.resource_renewability import MixedRenewable
from autofde_lab.builders.domain.scheduling.resource_type import WithResourceTypes
from autofde_lab.builders.domain.scheduling.task_duration import (
    DeterministicTaskDuration,
    SimulatedTaskDuration,
    UniformBoundedTaskDuration,
)


def _solve(renewable):
    from autofde_lab import rollout
    from autofde_lab.hub.domain.rcpsp.rcpsp_sk import RCPSP
    from autofde_lab.hub.solver.do_solver.do_solver_scheduling import DOSolver
    from autofde_lab.hub.solver.do_solver.sgs_policies import BasePolicyMethod, PolicyMethodParams
    from autofde_lab.hub.solver.do_solver.sk_to_do_binding import from_last_state_to_solution
    from discrete_optimization.rcpsp.solvers_map import CpSatRcpspSolver

    tasks = {
        1: {1: {"duration": 0}},
        2: {1: {"duration": 3, "crew": 2}},
        3: {1: {"duration": 4, "crew": 2}},
        4: {1: {"duration": 0}},
    }
    kw = {} if renewable is None else {"resource_renewable": renewable}
    dom = RCPSP(
        tasks_mode=tasks, max_horizon=30, successors={1: [2, 3], 2: [4], 3: [4], 4: []},
        resource_names=["crew"], resource_availability={"crew": 2}, **kw,
    )
    dom.set_inplace_environment(False)
    s0 = dom.get_initial_state()
    solver = DOSolver(
        domain_factory=lambda: dom,
        policy_method_params=PolicyMethodParams(
            base_policy_method=BasePolicyMethod.FOLLOW_GANTT, delta_index_freedom=0, delta_time_freedom=0
        ),
        do_solver_type=CpSatRcpspSolver,
    )
    solver.solve()
    states, _, _ = rollout(domain=dom, solver=solver, from_memory=s0, max_steps=100, return_episodes=True)[0]
    return from_last_state_to_solution(states[-1], dom).rcpsp_schedule


def test_omitted_renewability_defaults_to_all_renewable_and_schedules_serially():
    sched = _solve(None)
    a, b = sched[2], sched[3]
    # crew capacity 2, each task needs 2: they must not overlap
    assert a["end_time"] <= b["start_time"] or b["end_time"] <= a["start_time"]
    assert sched[4]["end_time"] == 7


def test_explicit_renewability_gives_same_makespan_as_default():
    assert _solve({"crew": True})[4]["end_time"] == _solve(None)[4]["end_time"]


def test_mixed_renewable_missing_resource_is_renewable_declared_false_is_not():
    class D(MixedRenewable):
        def _get_resource_renewability(self):
            return {"fuel": False}

    d = D()
    assert d.is_renewable("crew") is True
    assert d.is_renewable("fuel") is False


def test_abstract_hooks_raise_until_a_concrete_subclass_satisfies_them():
    for cls, call in [
        (WithPreallocations, lambda o: o.get_preallocations()),
        (WithModeCosts, lambda o: o.get_mode_costs()),
        (WithResourceCosts, lambda o: o.get_resource_cost_per_time_unit()),
        (WithResourceTypes, lambda o: o.get_resource_types_names()),
        (MultiMode, lambda o: o.get_tasks_modes()),
        (SingleMode, lambda o: o.get_tasks_modes()),
        (DeterministicTaskDuration, lambda o: o.get_task_duration(1)),
        (SimulatedTaskDuration, lambda o: o._sample_task_duration(1)),
    ]:
        with pytest.raises(NotImplementedError):
            call(cls())


def test_concrete_subclasses_satisfy_the_hooks():
    class Pre(WithPreallocations):
        def _get_preallocations(self):
            return {1: ["w1"]}

    class Cost(WithModeCosts, WithResourceCosts):
        def _get_mode_costs(self):
            return {1: {1: 2.5}}

        def _get_resource_cost_per_time_unit(self):
            return {"w1": 1.0}

    class Sm(SingleMode):
        def _get_tasks_mode(self):
            return {1: ConstantModeConsumption({"r": 2}), 2: VaryingModeConsumption({"r": [1, 3]})}

    class Det(DeterministicTaskDuration):
        def _get_task_duration(self, task, mode=1, progress_from=0.0):
            return 4

    class Uni(UniformBoundedTaskDuration):
        def _get_task_duration_upper_bound(self, task, mode=1, progress_from=0.0):
            return 3

        def _get_task_duration_lower_bound(self, task, mode=1, progress_from=0.0):
            return 1

    assert Pre().get_preallocations() == {1: ["w1"]}
    assert Cost().get_mode_costs() == {1: {1: 2.5}}
    assert Cost().get_resource_cost_per_time_unit() == {"w1": 1.0}
    s = Sm()
    assert s.get_task_consumption(1, 1, "r", 0) == 2
    assert s.get_task_consumption(2, 1, "r", 1) == 3
    d = Det()
    assert d.get_task_duration(1) == 4
    assert d.get_task_duration_distribution(1).sample() == 4
    u = Uni()
    assert sorted(v for v, _ in u.get_task_duration_distribution(1).get_values()) == [1, 2, 3]
