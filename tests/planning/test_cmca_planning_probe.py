from __future__ import annotations

from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import ResourceBudget
from autofde_lab.planning.cmca_probe import probe_product_frontier
from autofde_lab.planning.fond_hddl_product import (
    HDDLDomain,
    Method,
    Outcome,
    PrimitiveAction,
    ProductState,
    Task,
    build_fond_problem,
)


def _two_method_domain() -> HDDLDomain:
    return HDDLDomain(
        tasks={
            "root": Task(name="root", primitive=False),
            "left": Task(name="left", primitive=True),
            "right": Task(name="right", primitive=True),
        },
        methods={
            "root": (
                Method(
                    name="choose_left",
                    task="root",
                    preconditions=frozenset(),
                    subtasks=("left",),
                ),
                Method(
                    name="choose_right",
                    task="root",
                    preconditions=frozenset(),
                    subtasks=("right",),
                ),
            )
        },
        actions={
            "left": PrimitiveAction(
                name="left",
                preconditions=frozenset(),
                outcomes=frozenset({Outcome(add=frozenset({"done"}))}),
            ),
            "right": PrimitiveAction(
                name="right",
                preconditions=frozenset(),
                outcomes=frozenset({Outcome(add=frozenset({"done"}))}),
            ),
        },
    )


def test_cmca_planning_probe_preserves_lawful_frontier_when_budget_projection_prunes() -> (
    None
):
    domain = _two_method_domain()
    initial = ProductState(world=frozenset(), tau=("root",))
    reachability = build_fond_problem(
        domain=domain,
        initial=initial,
        is_goal=lambda state: not state.tau and "done" in state.world,
    )
    result = probe_product_frontier(
        reachability=reachability,
        state=initial,
        budget=ResourceBudget(
            total_ticks=101,
            memory_bytes=1009,
            max_verification_depth=4,
            consequence_risk_budget=0.2,
            concurrency_lanes=2,
        ),
        plan_id="test-planning-probe",
        allocator=MultifractalCascadeAllocator(pruning_threshold=0.99),
    )

    assert len(result.lawful_branch_ids) == 2
    assert len(result.allocated_branch_ids) == 1
    assert len(result.deferred_branch_ids) == 1
    assert result.preserves_dfcm_frontier is True
    assert set(result.allocated_branch_ids) | set(result.deferred_branch_ids) == set(
        result.lawful_branch_ids
    )
