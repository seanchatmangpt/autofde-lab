"""Chicago tests verifying mathematical equivalence between AutoFDE-Lab Gibbs allocation
and bcinr-cmca escort measure distributions.

Proves:
When m(c_i) = exp(S(c_i)) and q = tau:
L_q(c_i) = m(c_i)^q / sum(m(c_j)^q) == exp(tau * S(c_i)) / sum(exp(tau * S(c_j)))
"""

from __future__ import annotations

import math

import pytest

from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    CandidateBranch,
    ResourceBudget,
)


def _escort_distribution_reference(masses: list[float], q: float) -> list[float]:
    """Reference implementation of bcinr-cmca escort measure: L_q(c_i) = m(c_i)^q / sum_j m(c_j)^q."""
    powered = [math.pow(m, q) for m in masses]
    total = sum(powered)
    return [p / total for p in powered]


def test_cmca_gibbs_is_exact_exponential_escort_measure() -> None:
    """Verify that CMCA Gibbs allocation with temperature tau exactly matches bcinr-cmca escort distribution with lens q = tau."""
    allocator = MultifractalCascadeAllocator(
        engine="reference-softmax", default_tau=1.0, pruning_threshold=0.0
    )

    budget = ResourceBudget(
        total_ticks=10000,
        memory_bytes=65536,
        max_verification_depth=5,
        consequence_risk_budget=0.5,
        concurrency_lanes=4,
    )

    candidates = [
        CandidateBranch(
            branch_id=f"c_{i}",
            operator_id="op",
            world_id="w",
            state_id=f"s_{i}",
            option_entropy=1.5 + (i * 0.4),
            historical_yield=0.5 + (i * 0.1),
            estimated_cost=10.0,
        )
        for i in range(5)
    ]

    saliences = [allocator.calculate_branch_salience(c) for c in candidates]
    masses = [math.exp(s) for s in saliences]

    for q in [0.001, 0.5, 1.0, 1.5, 2.0]:
        plan = allocator.allocate(
            plan_id="p", budget=budget, candidates=candidates, tau=q
        )
        cmca_fractions = [a.allocated_fraction for a in plan.allocations]

        ref_fractions = _escort_distribution_reference(masses, q)

        for cmca_f, ref_f in zip(cmca_fractions, ref_fractions, strict=True):
            assert cmca_f == pytest.approx(ref_f, rel=1e-6)
