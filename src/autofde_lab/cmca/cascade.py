"""Chatman Multifractal Cascade Allocation (CMCA) core engine.

Deterministic governor dividing a finite resource budget across candidate
exploration frontiers, preserving lawful future option value without
premature single-branch collapse.

Two engines compute the allocation *measure*; the budget projection
(pruning, renormalization, anti-starvation fallback, discrete tick/memory/
depth assignment, lanes) is shared:

- ``engine="bcinr"`` (default): delegates the measure to the canonical
  Rust implementation, the vendored ``bcinr-cmca`` crate
  (:mod:`autofde_lab.cmca.bcinr_bridge`), whose branchless Q16.16
  fixed-point ``allocator::allocate()`` applies the compiled lens policy.
  ``tau`` is not a parameter of this engine (the lens weighting is
  compiled upstream), so passing one is refused rather than ignored.
- ``engine="reference-softmax"``: the original local float engine --
  salience soft-max at temperature ``tau``. Retained as an explicitly
  named reference (its temperature-asymptotics are pinned by
  ``tests/cmca/test_cmca_mathematical_proofs.py``), not as a silent
  fallback: if the bcinr binary is unavailable, the bcinr engine refuses
  with a typed :class:`~autofde_lab.cmca.bcinr_bridge.BcinrCliUnavailable`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .bcinr_bridge import rank_candidates
from .contracts import (
    AllocationStanding,
    BranchAllocation,
    CandidateBranch,
    CascadeAllocationPlan,
    ResourceBudget,
)

ENGINES = ("bcinr", "reference-softmax")


class MultifractalCascadeAllocator:
    """Deterministic governor for cascade resource allocation."""

    def __init__(
        self,
        *,
        default_tau: float = 1.0,
        pruning_threshold: float = 0.01,
        engine: str = "bcinr",
    ) -> None:
        if default_tau <= 0.0:
            raise ValueError("tau temperature must be strictly positive")
        if not (0.0 <= pruning_threshold < 1.0):
            raise ValueError("pruning_threshold must be in [0.0, 1.0)")
        if engine not in ENGINES:
            raise ValueError(f"unknown engine {engine!r}; expected one of {ENGINES}")
        if engine == "bcinr" and default_tau != 1.0:
            raise ValueError(
                "tau is a reference-softmax parameter; the bcinr engine's "
                "lens weighting is compiled upstream and ignores it -- "
                "refusing rather than silently dropping the parameter"
            )
        self.default_tau = default_tau
        self.pruning_threshold = pruning_threshold
        self.engine = engine

    def calculate_branch_salience(self, branch: CandidateBranch) -> float:
        """Score S(c_i) = Option Entropy * Historical Yield / Cost."""
        cost = max(branch.estimated_cost, 1e-6)
        # S(c_i) represents the option density per resource unit
        salience = (branch.option_entropy * branch.historical_yield) / cost
        return max(salience, 0.0)

    def allocate(
        self,
        *,
        plan_id: str,
        budget: ResourceBudget,
        candidates: Sequence[CandidateBranch],
        tau: float | None = None,
    ) -> CascadeAllocationPlan:
        """Deterministically divide finite budget across candidates via multifractal cascade."""
        budget.validate()
        if not candidates:
            return CascadeAllocationPlan(
                plan_id=plan_id,
                parent_budget=budget,
                allocations=(),
                tau_temperature=tau or self.default_tau,
                total_option_value_preserved=0.0,
                entropy=0.0,
            )

        temperature = tau if tau is not None else self.default_tau
        if temperature <= 0.0:
            raise ValueError("tau temperature must be positive")

        # 1. Deterministic canonical sort to guarantee identical replay hash
        sorted_candidates = sorted(candidates, key=lambda c: c.candidate_hash)

        # 2. Engine-specific measure -> per-candidate fractions.
        if self.engine == "bcinr":
            if tau is not None or self.default_tau != 1.0:
                raise ValueError(
                    "tau is a reference-softmax parameter; the bcinr engine's "
                    "lens weighting is compiled upstream and ignores it -- "
                    "refusing rather than silently dropping the parameter"
                )
            shares = rank_candidates(sorted_candidates)
            raw_fractions = [shares[c.branch_id] for c in sorted_candidates]
        else:
            # 2a. Compute saliences
            saliences = [self.calculate_branch_salience(c) for c in sorted_candidates]
            max_salience = max(saliences) if saliences else 0.0

            # 2b. Softmax / multifractal multiplier with numerical stability
            exp_terms = [
                math.exp(min(temperature * (s - max_salience), 50.0)) for s in saliences
            ]
            sum_exp = sum(exp_terms)

            raw_fractions = [e / sum_exp for e in exp_terms]

        # 3. Prune branches falling below preservation cutoff
        active_indices: list[int] = []
        pruned_indices: list[int] = []
        for idx, frac in enumerate(raw_fractions):
            if frac < self.pruning_threshold:
                pruned_indices.append(idx)
            else:
                active_indices.append(idx)

        # 4. Renormalize active fractions so total mass == 1.0 (or defer if all pruned)
        if not active_indices:
            # Keep top candidate to prevent total starvation. Fraction (not
            # salience) orders this: under the bcinr engine salience is only
            # one of four measure axes, and for the reference engine softmax
            # weight is monotone in salience, so this is equivalent there.
            top_idx = max(range(len(raw_fractions)), key=lambda i: raw_fractions[i])
            active_indices = [top_idx]
            pruned_indices = [i for i in range(len(raw_fractions)) if i != top_idx]

        active_sum = sum(raw_fractions[i] for i in active_indices)
        normalized_fractions = {
            i: (raw_fractions[i] / active_sum) for i in active_indices
        }

        # 5. Assign concrete discrete resources
        allocations: list[BranchAllocation] = []
        total_entropy = 0.0
        total_preserved = 0.0

        # Sort active branches by fraction descending for priority lane assignment
        sorted_active = sorted(
            active_indices, key=lambda i: normalized_fractions[i], reverse=True
        )

        lane_count = budget.concurrency_lanes

        for lane_idx, idx in enumerate(sorted_active):
            c = sorted_candidates[idx]
            frac = normalized_fractions[idx]
            ticks = math.floor(frac * budget.total_ticks)
            mem = math.floor(frac * budget.memory_bytes)
            # Depth scales logarithmically with fraction allocated
            v_depth = min(
                budget.max_verification_depth,
                max(1, round(budget.max_verification_depth * (0.5 + 0.5 * frac))),
            )
            total_entropy -= frac * math.log(max(frac, 1e-9))
            total_preserved += c.option_entropy * frac

            allocations.append(
                BranchAllocation(
                    branch_id=c.branch_id,
                    allocated_fraction=frac,
                    allocated_ticks=ticks,
                    allocated_memory_bytes=mem,
                    verification_depth=v_depth,
                    standing=AllocationStanding.ADMITTED,
                    priority_lane=lane_idx % lane_count,
                )
            )

        for idx in pruned_indices:
            c = sorted_candidates[idx]
            allocations.append(
                BranchAllocation(
                    branch_id=c.branch_id,
                    allocated_fraction=0.0,
                    allocated_ticks=0,
                    allocated_memory_bytes=0,
                    verification_depth=0,
                    standing=AllocationStanding.PRUNED,
                    priority_lane=lane_count - 1,
                )
            )

        # Sort final allocations back to canonical candidate order
        allocations.sort(key=lambda a: a.branch_id)

        return CascadeAllocationPlan(
            plan_id=plan_id,
            parent_budget=budget,
            allocations=tuple(allocations),
            tau_temperature=temperature,
            total_option_value_preserved=total_preserved,
            entropy=total_entropy,
        )
