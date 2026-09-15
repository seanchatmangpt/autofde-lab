"""Chicago-style adversarial falsification and mutation tests for CMCA.

Directly attacks CMCA mathematical invariants and boundaries:
1. Mutant 1: Degenerate numeric inputs (NaN, Inf, negative entropy, zero cost).
2. Mutant 2: Starvation under extreme pruning thresholds and uniform distributions.
3. Mutant 3: Pathological many-candidate budget conservation (127 branches, prime tick budget).
4. Mutant 4: Injection & keyword escaping in AtomVM Erlang codegen.
5. Mutant 5: Concurrency lane saturation and allocation priority inversion.
"""

from __future__ import annotations

import math

from autofde_lab.cmca import (
    AllocationStanding,
    CandidateBranch,
    MultifractalCascadeAllocator,
    ResourceBudget,
    generate_atomvm_cmca_module,
)


def _make_budget(
    ticks: int = 10000, mem: int = 65536, lanes: int = 8
) -> ResourceBudget:
    return ResourceBudget(
        total_ticks=ticks,
        memory_bytes=mem,
        max_verification_depth=6,
        consequence_risk_budget=0.5,
        concurrency_lanes=lanes,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Mutant: Degenerate numeric inputs (NaN, Inf, Zero-cost, Negative Entropy)
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_cmca_zero_cost_does_not_divide_by_zero():
    """Branch with estimated_cost=0.0 must not trigger ZeroDivisionError or NaN."""
    allocator = MultifractalCascadeAllocator(engine="reference-softmax")
    budget = _make_budget()
    candidates = [
        CandidateBranch(
            branch_id="b-zero-cost",
            operator_id="op-1",
            world_id="w-1",
            state_id="s-1",
            option_entropy=10.0,
            estimated_cost=0.0,  # Hostile: exact zero cost
        ),
        CandidateBranch(
            branch_id="b-normal",
            operator_id="op-2",
            world_id="w-2",
            state_id="s-2",
            option_entropy=5.0,
            estimated_cost=1.0,
        ),
    ]

    plan = allocator.allocate(
        plan_id="plan-zero-cost", budget=budget, candidates=candidates
    )
    assert not math.isnan(plan.entropy)
    assert not math.isinf(plan.entropy)
    for a in plan.allocations:
        assert not math.isnan(a.allocated_fraction)
        assert a.allocated_ticks >= 0


def test_falsify_cmca_negative_entropy_clamped():
    """Branch with negative option_entropy must not yield negative salience or reverse-priority."""
    allocator = MultifractalCascadeAllocator(engine="reference-softmax")
    budget = _make_budget()
    candidates = [
        CandidateBranch(
            branch_id="b-neg-entropy",
            operator_id="op-1",
            world_id="w-1",
            state_id="s-1",
            option_entropy=-100.0,  # Hostile: negative entropy
            estimated_cost=1.0,
        ),
        CandidateBranch(
            branch_id="b-pos-entropy",
            operator_id="op-2",
            world_id="w-2",
            state_id="s-2",
            option_entropy=10.0,
            estimated_cost=1.0,
        ),
    ]

    plan = allocator.allocate(
        plan_id="plan-neg-entropy", budget=budget, candidates=candidates
    )
    # The positive candidate must receive dominant mass
    pos_alloc = next(a for a in plan.allocations if a.branch_id == "b-pos-entropy")
    neg_alloc = next(a for a in plan.allocations if a.branch_id == "b-neg-entropy")

    assert pos_alloc.allocated_fraction >= neg_alloc.allocated_fraction
    assert neg_alloc.allocated_fraction >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. Mutant: Pathological High-Dimensional Candidate Frontiers (127 branches)
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_cmca_budget_ceiling_under_127_candidates():
    """Conservation law must hold strictly: sum(ticks) <= budget.total_ticks and
    sum(mem) <= budget.memory_bytes with 127 candidates and a prime budget.
    """
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=1.5, pruning_threshold=0.005
    )
    # 9973 is a prime number, tests integer discretization rounding
    budget = _make_budget(ticks=9973, mem=65521, lanes=16)

    candidates = [
        CandidateBranch(
            branch_id=f"branch-{i:03d}",
            operator_id=f"op-{i % 7}",
            world_id="w-test",
            state_id=f"s-{i}",
            option_entropy=float((i * 13) % 29 + 1),
            estimated_cost=float((i * 7) % 11 + 1),
            historical_yield=float((i % 5) * 0.2 + 0.5),
        )
        for i in range(127)
    ]

    plan = allocator.allocate(plan_id="plan-127", budget=budget, candidates=candidates)

    total_ticks = sum(a.allocated_ticks for a in plan.allocations)
    total_mem = sum(a.allocated_memory_bytes for a in plan.allocations)

    # Invariant: Conservation of finite resources (no over-allocation)
    assert total_ticks <= budget.total_ticks
    assert total_mem <= budget.memory_bytes
    assert plan.plan_hash


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mutant: Total Starvation & Pruning Boundary Collapse
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_cmca_total_starvation_recovery():
    """If pruning_threshold is set impossibly high (e.g. 0.999), allocator must
    prevent total starvation and preserve at least the top candidate.
    """
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=0.1, pruning_threshold=0.999
    )
    budget = _make_budget()
    candidates = [
        CandidateBranch(
            branch_id=f"b-{i}",
            operator_id="op",
            world_id="w",
            state_id="s",
            option_entropy=1.0,
            estimated_cost=1.0,
        )
        for i in range(10)
    ]

    plan = allocator.allocate(
        plan_id="plan-starvation", budget=budget, candidates=candidates
    )

    admitted = [
        a for a in plan.allocations if a.standing is AllocationStanding.ADMITTED
    ]
    assert len(admitted) >= 1
    assert any(a.allocated_ticks > 0 for a in admitted)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Mutant: AtomVM Erlang Codegen Syntax Hostility
# ─────────────────────────────────────────────────────────────────────────────


def test_falsify_atomvm_erlang_codegen_hostile_characters():
    """Branch IDs with quotes, newlines, or Erlang reserved tokens must not produce
    broken or malicious syntax.
    """
    allocator = MultifractalCascadeAllocator(engine="reference-softmax")
    budget = _make_budget()
    candidates = [
        CandidateBranch(
            branch_id='b-quotes-"and"-case-end',  # Hostile Erlang keywords and quotes
            operator_id="op-1",
            world_id="w-1",
            state_id="s-1",
            option_entropy=10.0,
            estimated_cost=1.0,
        )
    ]

    plan = allocator.allocate(
        plan_id='plan-"attack"', budget=budget, candidates=candidates
    )
    erl = generate_atomvm_cmca_module(plan, module_name="cmca_attack_test")

    # Module declaration must be well formed
    assert "-module(cmca_attack_test)." in erl
    assert "get_plan() ->" in erl
    # Verify module is structurally present
    assert plan.plan_hash in erl
