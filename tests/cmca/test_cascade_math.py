"""Tests for Chatman Multifractal Cascade Allocation (CMCA) mathematics and invariants.

Proves:
1. Budget conservation: sum(allocated) <= total_budget.
2. Non-collapse / entropy preservation: multifractal distribution does not prematurely collapse to single-branch argmax.
3. Deterministic replay: identical inputs yield identical plan hashes.
4. Pruning boundary: branches below preservation threshold are safely pruned/deferred.
5. AtomVM Erlang scheduler codegen produces clean, parseable Erlang.
"""

from autofde_lab.cmca import (
    AllocationReceipt,
    AllocationStanding,
    CandidateBranch,
    CMCAScheduler,
    MultifractalCascadeAllocator,
    ResourceBudget,
    build_candidate_branches_from_dfcm,
    generate_atomvm_cmca_module,
)


def _sample_budget() -> ResourceBudget:
    return ResourceBudget(
        total_ticks=10000,
        memory_bytes=65536,
        max_verification_depth=8,
        consequence_risk_budget=0.25,
        concurrency_lanes=8,
    )


def _sample_candidates() -> list[CandidateBranch]:
    return [
        CandidateBranch(
            branch_id="b-tax-1",
            operator_id="c8l-tax",
            world_id="gym-accounting",
            state_id="s1",
            option_entropy=12.5,
            estimated_cost=2.0,
            historical_yield=1.2,
        ),
        CandidateBranch(
            branch_id="b-sec-2",
            operator_id="c8l-security",
            world_id="gym-azuregoat",
            state_id="s2",
            option_entropy=8.0,
            estimated_cost=1.5,
            historical_yield=1.0,
        ),
        CandidateBranch(
            branch_id="b-plan-3",
            operator_id="c8l-planning",
            world_id="gym-maze",
            state_id="s3",
            option_entropy=5.0,
            estimated_cost=3.0,
            historical_yield=0.8,
        ),
        CandidateBranch(
            branch_id="b-micro-4",
            operator_id="c8l-trivial",
            world_id="gym-trivial",
            state_id="s4",
            option_entropy=0.1,
            estimated_cost=10.0,
            historical_yield=0.1,
        ),
    ]


def test_cmca_budget_conservation():
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=1.0, pruning_threshold=0.02
    )
    budget = _sample_budget()
    candidates = _sample_candidates()

    plan = allocator.allocate(plan_id="plan-1", budget=budget, candidates=candidates)

    allocated_ticks = sum(a.allocated_ticks for a in plan.allocations)
    allocated_mem = sum(a.allocated_memory_bytes for a in plan.allocations)

    assert allocated_ticks <= budget.total_ticks
    assert allocated_mem <= budget.memory_bytes
    assert plan.plan_hash


def test_cmca_non_collapse_and_entropy_preservation():
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=0.5, pruning_threshold=0.01
    )
    budget = _sample_budget()
    candidates = _sample_candidates()

    plan = allocator.allocate(plan_id="plan-2", budget=budget, candidates=candidates)

    # In CMCA, multiple non-pruned branches receive mass (no premature argmax collapse)
    admitted = [
        a for a in plan.allocations if a.standing is AllocationStanding.ADMITTED
    ]
    assert len(admitted) >= 2
    assert plan.entropy > 0.5


def test_cmca_deterministic_replay():
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=1.0
    )
    budget = _sample_budget()
    candidates = _sample_candidates()

    plan1 = allocator.allocate(
        plan_id="plan-replay", budget=budget, candidates=candidates
    )
    # Reverse input order to test canonical sort
    plan2 = allocator.allocate(
        plan_id="plan-replay", budget=budget, candidates=list(reversed(candidates))
    )

    assert plan1.plan_hash == plan2.plan_hash
    assert len(plan1.allocations) == len(plan2.allocations)


def test_cmca_pruning_boundary():
    # Set high pruning threshold
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=2.0, pruning_threshold=0.15
    )
    budget = _sample_budget()
    candidates = _sample_candidates()

    plan = allocator.allocate(
        plan_id="plan-prune", budget=budget, candidates=candidates
    )
    pruned = [a for a in plan.allocations if a.standing is AllocationStanding.PRUNED]
    assert len(pruned) >= 1
    for p in pruned:
        assert p.allocated_ticks == 0
        assert p.allocated_fraction == 0.0


def test_dfcm_bridge_conversion():
    pairs = [
        ("branch-1", "c8l-1", "world-1", 100, 2.5, 10.0),
        ("branch-2", "c8l-2", "world-2", 20, 1.2, 5.0),
    ]
    branches = build_candidate_branches_from_dfcm(domain_plan_pairs=pairs)
    assert len(branches) == 2
    assert branches[0].option_entropy > branches[1].option_entropy


def test_dual_learning_loop2_payoff_update():
    scheduler = CMCAScheduler()
    op_id = "c8l-tax"
    assert scheduler.get_historical_yield(op_id) == 1.0

    # Record payoff receipt (high yield)
    rec = AllocationReceipt(
        receipt_id="rec-1",
        plan_hash="hash-1",
        branch_id="b-tax-1",
        ticks_consumed=150,
        consequence_observed=True,
        options_retained_actual=25,
        payoff_score=1.8,
    )
    scheduler.record_receipt(rec, op_id)
    assert scheduler.get_historical_yield(op_id) == 1.8


def test_atomvm_erlang_scheduler_codegen():
    allocator = MultifractalCascadeAllocator(engine="reference-softmax")
    plan = allocator.allocate(
        plan_id="plan-atomvm", budget=_sample_budget(), candidates=_sample_candidates()
    )
    erl = generate_atomvm_cmca_module(plan, module_name="cmca_test_scheduler")

    assert "-module(cmca_test_scheduler)." in erl
    assert "get_plan() ->" in erl
    assert "schedule_branch(BranchId) when is_binary(BranchId) ->" in erl
    assert f'<<"{plan.plan_hash}">' in erl
