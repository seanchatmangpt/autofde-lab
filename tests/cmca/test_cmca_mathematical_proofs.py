"""Exhaustive mathematical verification and proof tests for CMCA.

Directly proves:
1. Strict resource conservation (no memory/tick leakage across prime/high-dimension budgets)
2. Asymptotic temperature behavior (monotonicity dH/dtau <= 0, tau->0 uniform, tau->inf argmax)
3. Salience preservation and monotonicity (strictly higher salience gets strictly >= fraction)
4. Canonical permutation invariance across candidate ordering
5. Anti-starvation and singular cost handling
"""

from __future__ import annotations

import math
import random

import pytest

from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    AllocationStanding,
    CandidateBranch,
    ResourceBudget,
)


def _make_budget(
    ticks: int = 10000,
    mem: int = 100000,
    depth: int = 5,
    risk: float = 0.5,
    lanes: int = 8,
) -> ResourceBudget:
    return ResourceBudget(
        total_ticks=ticks,
        memory_bytes=mem,
        max_verification_depth=depth,
        consequence_risk_budget=risk,
        concurrency_lanes=lanes,
    )


@pytest.fixture
def allocator() -> MultifractalCascadeAllocator:
    return MultifractalCascadeAllocator(default_tau=1.0, pruning_threshold=0.01)


def test_theorem_1_strict_resource_conservation_under_prime_budgets(
    allocator: MultifractalCascadeAllocator,
) -> None:
    """Theorem 1: Discrete floor allocation guarantees sum(allocated) <= Budget for all arbitrary dimensions."""
    # Large prime budgets to stress floor and integer remainder mechanics
    prime_ticks = 104729
    prime_mem = 2147483647
    budget = _make_budget(ticks=prime_ticks, mem=prime_mem, depth=10, lanes=16)

    # 100 heterogeneous candidates
    candidates = [
        CandidateBranch(
            branch_id=f"branch_{i:03d}",
            operator_id="op_test",
            world_id="w_test",
            state_id=f"s_{i}",
            option_entropy=round(1.0 + (i % 7) * 0.5, 2),
            historical_yield=round(0.1 + (i % 5) * 0.2, 2),
            estimated_cost=round(10.0 + (i % 11) * 3.0, 2),
        )
        for i in range(100)
    ]

    plan = allocator.allocate(
        plan_id="plan_t1", budget=budget, candidates=candidates, tau=1.5
    )

    total_allocated_ticks = sum(a.allocated_ticks for a in plan.allocations)
    total_allocated_mem = sum(a.allocated_memory_bytes for a in plan.allocations)

    # Strictly conserved (never exceeds budget)
    assert total_allocated_ticks <= prime_ticks
    assert total_allocated_mem <= prime_mem
    # High efficiency: with 100 active/pruned candidates, floor remainder is strictly < number of active branches
    admitted = [
        a for a in plan.allocations if a.standing == AllocationStanding.ADMITTED
    ]
    assert prime_ticks - total_allocated_ticks <= len(admitted)
    assert sum(a.allocated_fraction for a in admitted) == pytest.approx(1.0, rel=1e-6)


def test_theorem_2_temperature_asymptotics_and_monotonic_entropy_decay() -> None:
    """Theorem 2: dH/dtau <= 0. As tau -> 0, distribution is uniform; as tau -> inf, it collapses to argmax."""
    # Zero pruning threshold to evaluate pure Gibbs-Boltzmann entropy
    pure_allocator = MultifractalCascadeAllocator(
        default_tau=1.0, pruning_threshold=0.0
    )

    budget = _make_budget(ticks=10000, mem=100000, depth=5, lanes=4)

    candidates = [
        CandidateBranch(
            branch_id="b1",
            operator_id="op",
            world_id="w",
            state_id="s1",
            option_entropy=2.0,
            historical_yield=0.8,
            estimated_cost=10.0,
        ),  # S = 0.16
        CandidateBranch(
            branch_id="b2",
            operator_id="op",
            world_id="w",
            state_id="s2",
            option_entropy=3.0,
            historical_yield=0.9,
            estimated_cost=10.0,
        ),  # S = 0.27 (Top candidate)
        CandidateBranch(
            branch_id="b3",
            operator_id="op",
            world_id="w",
            state_id="s3",
            option_entropy=1.5,
            historical_yield=0.4,
            estimated_cost=10.0,
        ),  # S = 0.06
        CandidateBranch(
            branch_id="b4",
            operator_id="op",
            world_id="w",
            state_id="s4",
            option_entropy=1.0,
            historical_yield=0.2,
            estimated_cost=10.0,
        ),  # S = 0.02
    ]

    # Test monotonic entropy decrease across 6 orders of magnitude of tau
    taus = [1e-4, 0.01, 0.1, 1.0, 5.0, 20.0, 100.0]
    entropies: list[float] = []

    for tau in taus:
        plan = pure_allocator.allocate(
            plan_id=f"plan_tau_{tau}", budget=budget, candidates=candidates, tau=tau
        )
        entropies.append(plan.entropy)

    # 1. Monotonicity check: H(tau_k) >= H(tau_{k+1})
    for k in range(len(entropies) - 1):
        assert entropies[k] >= entropies[k + 1] - 1e-9, (
            f"Entropy increased from tau={taus[k]} to {taus[k + 1]}"
        )

    # 2. Asymptotic limit tau -> 0: H -> ln(4) = ~1.38629, each gets 1/4
    plan_cold = pure_allocator.allocate(
        plan_id="plan_cold", budget=budget, candidates=candidates, tau=1e-5
    )
    assert plan_cold.entropy == pytest.approx(math.log(4.0), rel=1e-3)
    for a in plan_cold.allocations:
        assert a.allocated_fraction == pytest.approx(0.25, rel=1e-3)

    # 3. Asymptotic limit tau -> inf: H -> 0.0, top candidate gets ~100%
    plan_hot = pure_allocator.allocate(
        plan_id="plan_hot", budget=budget, candidates=candidates, tau=500.0
    )
    assert plan_hot.entropy == pytest.approx(0.0, abs=1e-4)
    top_alloc = next(a for a in plan_hot.allocations if a.branch_id == "b2")
    assert top_alloc.allocated_fraction == pytest.approx(1.0, rel=1e-4)


def test_theorem_3_salience_ordering_monotonicity(
    allocator: MultifractalCascadeAllocator,
) -> None:
    """Theorem 3: Higher salience S(c_i) > S(c_j) strictly implies allocated_fraction(c_i) >= allocated_fraction(c_j)."""
    budget = _make_budget(ticks=10000, mem=100000, depth=5, lanes=4)

    candidates = [
        CandidateBranch(
            branch_id="b1",
            operator_id="op",
            world_id="w",
            state_id="s1",
            option_entropy=1.0,
            historical_yield=0.2,
            estimated_cost=10.0,
        ),
        CandidateBranch(
            branch_id="b2",
            operator_id="op",
            world_id="w",
            state_id="s2",
            option_entropy=2.0,
            historical_yield=0.5,
            estimated_cost=10.0,
        ),
        CandidateBranch(
            branch_id="b3",
            operator_id="op",
            world_id="w",
            state_id="s3",
            option_entropy=3.0,
            historical_yield=0.8,
            estimated_cost=10.0,
        ),
        CandidateBranch(
            branch_id="b4",
            operator_id="op",
            world_id="w",
            state_id="s4",
            option_entropy=4.0,
            historical_yield=0.9,
            estimated_cost=10.0,
        ),
    ]

    saliences = {
        c.branch_id: allocator.calculate_branch_salience(c) for c in candidates
    }
    plan = allocator.allocate(
        plan_id="plan_t3", budget=budget, candidates=candidates, tau=1.0
    )
    alloc_map = {a.branch_id: a.allocated_fraction for a in plan.allocations}

    # Verify order preservation
    branch_order = ["b1", "b2", "b3", "b4"]
    for i in range(len(branch_order) - 1):
        b_low = branch_order[i]
        b_high = branch_order[i + 1]
        assert saliences[b_low] < saliences[b_high]
        assert alloc_map[b_low] <= alloc_map[b_high]
        if alloc_map[b_low] > 0:
            assert alloc_map[b_low] < alloc_map[b_high]


def test_theorem_4_permutation_invariance_and_hash_identity(
    allocator: MultifractalCascadeAllocator,
) -> None:
    """Theorem 4: The allocation plan is strictly invariant under arbitrary permutations of the input candidate sequence."""
    budget = _make_budget(ticks=50000, mem=1048576, depth=6, lanes=8)

    base_candidates = [
        CandidateBranch(
            branch_id=f"branch_{i}",
            operator_id="op",
            world_id="w",
            state_id=f"s_{i}",
            option_entropy=1.5 + (i * 0.3),
            historical_yield=0.2 + (i * 0.05),
            estimated_cost=20.0 + (i * 2.0),
        )
        for i in range(25)
    ]

    base_plan = allocator.allocate(
        plan_id="canonical_run", budget=budget, candidates=base_candidates, tau=1.2
    )

    # Permute candidate list 50 times with different random seeds
    rng = random.Random(42)
    for _ in range(50):
        permuted_candidates = list(base_candidates)
        rng.shuffle(permuted_candidates)

        perm_plan = allocator.allocate(
            plan_id="canonical_run",
            budget=budget,
            candidates=permuted_candidates,
            tau=1.2,
        )

        assert perm_plan.entropy == pytest.approx(base_plan.entropy, rel=1e-9)
        assert perm_plan.total_option_value_preserved == pytest.approx(
            base_plan.total_option_value_preserved, rel=1e-9
        )
        assert len(perm_plan.allocations) == len(base_plan.allocations)

        for a_base, a_perm in zip(
            base_plan.allocations, perm_plan.allocations, strict=True
        ):
            assert a_base.branch_id == a_perm.branch_id
            assert a_base.allocated_fraction == pytest.approx(
                a_perm.allocated_fraction, rel=1e-9
            )
            assert a_base.allocated_ticks == a_perm.allocated_ticks
            assert a_base.allocated_memory_bytes == a_perm.allocated_memory_bytes
            assert a_base.standing == a_perm.standing
            assert a_base.priority_lane == a_perm.priority_lane


def test_edge_case_zero_cost_and_anti_starvation() -> None:
    """Edge Case: Zero cost candidates are safely bounded by epsilon; hyper-aggressive pruning preserves top branch."""
    # Aggressive pruning: 95% threshold
    aggressive_allocator = MultifractalCascadeAllocator(
        default_tau=1.0, pruning_threshold=0.95
    )

    budget = _make_budget(ticks=1000, mem=10000, depth=3, lanes=2)

    # Evenly matched candidates where none exceeds 95% initially
    candidates = [
        CandidateBranch(
            branch_id="zero_cost_branch",
            operator_id="op",
            world_id="w",
            state_id="s1",
            option_entropy=2.0,
            historical_yield=0.8,
            estimated_cost=0.0,  # Should be clamped to 1e-6 without ZeroDivisionError
        ),
        CandidateBranch(
            branch_id="normal_branch",
            operator_id="op",
            world_id="w",
            state_id="s2",
            option_entropy=2.0,
            historical_yield=0.8,
            estimated_cost=100.0,
        ),
    ]

    # Must execute safely without division by zero
    plan = aggressive_allocator.allocate(
        plan_id="plan_zero_cost", budget=budget, candidates=candidates, tau=1.0
    )

    assert len(plan.allocations) == 2
    admitted = [
        a for a in plan.allocations if a.standing == AllocationStanding.ADMITTED
    ]
    # Anti-starvation guarantees at least 1 admitted candidate even under aggressive pruning
    assert len(admitted) >= 1
    zero_cost_alloc = next(
        a for a in plan.allocations if a.branch_id == "zero_cost_branch"
    )
    assert zero_cost_alloc.standing == AllocationStanding.ADMITTED
    assert zero_cost_alloc.allocated_fraction > 0.9
