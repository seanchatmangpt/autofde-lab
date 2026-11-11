"""L18: RCPSP default renewability and 1-based task-id validation (real DO solve)."""
import pytest

from autofde_lab import rollout
from autofde_lab.hub.domain.rcpsp.rcpsp_sk import RCPSP
from autofde_lab.hub.solver.do_solver.do_solver_scheduling import DOSolver
from autofde_lab.hub.solver.do_solver.sgs_policies import (
    BasePolicyMethod,
    PolicyMethodParams,
)
from discrete_optimization.rcpsp.solvers_map import CpSatRcpspSolver


def _tasks(first):
    a, b, c, d = first, first + 1, first + 2, first + 3
    tasks = {
        a: {1: {"duration": 0}},
        b: {1: {"duration": 2, "crew": 1}},
        c: {1: {"duration": 3, "crew": 1}},
        d: {1: {"duration": 0}},
    }
    return tasks, {a: [b, c], b: [d], c: [d], d: []}


def test_default_renewability_marks_every_declared_resource_renewable():
    tasks, succ = _tasks(1)
    dom = RCPSP(tasks_mode=tasks, max_horizon=20, successors=succ,
                resource_names=["crew"], resource_availability={"crew": 1})
    assert dom.get_resource_renewability() == {"crew": True}


def test_explicit_renewability_overrides_default():
    tasks, succ = _tasks(1)
    dom = RCPSP(tasks_mode=tasks, max_horizon=20, successors=succ,
                resource_names=["crew", "fuel"],
                resource_availability={"crew": 1, "fuel": 1},
                resource_renewable={"fuel": False})
    assert dom.get_resource_renewability() == {"crew": True, "fuel": False}


def test_rollout_without_resource_renewable_completes():
    tasks, succ = _tasks(1)
    dom = RCPSP(tasks_mode=tasks, max_horizon=20, successors=succ,
                resource_names=["crew"], resource_availability={"crew": 1})
    dom.set_inplace_environment(False)
    s0 = dom.get_initial_state()
    solver = DOSolver(
        domain_factory=lambda: dom,
        policy_method_params=PolicyMethodParams(
            base_policy_method=BasePolicyMethod.FOLLOW_GANTT,
            delta_index_freedom=0, delta_time_freedom=0),
        do_solver_type=CpSatRcpspSolver,
    )
    solver.solve()
    states, _, _ = rollout(domain=dom, solver=solver, from_memory=s0,
                           max_steps=100, return_episodes=True)[0]
    assert dom.is_terminal(states[-1])


def test_zero_based_ids_raise_actionable_value_error():
    tasks, succ = _tasks(0)
    with pytest.raises(ValueError, match="1-based"):
        RCPSP(tasks_mode=tasks, max_horizon=20, successors=succ,
              resource_names=["crew"], resource_availability={"crew": 1})
