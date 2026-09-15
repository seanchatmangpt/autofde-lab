"""Chatman Multifractal Cascade Allocation (CMCA) core engine.

Deterministic governor dividing a finite resource budget across candidate
exploration frontiers, preserving lawful future option value without
premature single-branch collapse.

The allocation *measure* is delegated in full to the canonical Rust
implementation, the vendored ``bcinr-cmca`` crate
(:mod:`autofde_lab.cmca.bcinr_bridge`): its branchless Q16.16 fixed-point
``allocator::allocate()`` applies the compiled lens policy
(``LENS_REGISTRY``/``LAMBDA``/``ETA``), evaluated in-process through the
prebuilt WASM cdylib (:mod:`autofde_lab.cmca.bcinr_wasm`) when the
``wasmtime`` runtime and artifact are present, falling back to the
``cmca_rank_cli`` subprocess otherwise. There is no local float
reimplementation of the measure anywhere in this package: this module owns
only the deterministic budget *projection* -- canonical candidate
ordering, pruning, renormalization, anti-starvation fallback, discrete
tick/memory/depth assignment, and concurrency lanes.

Consequences of the single-measure law:

- There is no ``tau`` parameter. The lens weighting is compiled upstream
  in the vendored crate; a caller who needs different lens behaviour must
  change the vendored policy (and rebuild the wasm artifact per
  ``wasm/README.md``), not reach for a temperature knob.
- The compiled allocator shape is ``N = 8`` (upstream CMCA-108): more
  than 8 candidates is refused with a typed
  :class:`~autofde_lab.cmca.bcinr_bridge.BcinrCardinalityRefusal` rather
  than truncated, and never silently re-ranked locally.
- If no transport resolves (neither the WASM artifact nor the CLI
  binary), allocation refuses with a typed
  :class:`~autofde_lab.cmca.bcinr_bridge.BcinrCliUnavailable` -- never a
  silent fallback to a local measure.
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


class MultifractalCascadeAllocator:
    """Deterministic governor for cascade resource allocation."""

    def __init__(
        self,
        *,
        pruning_threshold: float = 0.01,
    ) -> None:
        if not (0.0 <= pruning_threshold < 1.0):
            raise ValueError("pruning_threshold must be in [0.0, 1.0)")
        self.pruning_threshold = pruning_threshold

    def allocate(
        self,
        *,
        plan_id: str,
        budget: ResourceBudget,
        candidates: Sequence[CandidateBranch],
    ) -> CascadeAllocationPlan:
        """Deterministically divide finite budget across candidates.

        The measure comes from the vendored bcinr allocator (see the module
        docstring); this method projects its shares onto the discrete
        budget. Deterministic for identical inputs: candidates are ranked
        in canonical ``candidate_hash`` order and both transports are
        deterministic fixed-point built from the same vendored commit.
        """
        budget.validate()
        if not candidates:
            return CascadeAllocationPlan(
                plan_id=plan_id,
                parent_budget=budget,
                allocations=(),
                total_option_value_preserved=0.0,
                entropy=0.0,
            )

        # 1. Deterministic canonical sort to guarantee identical replay hash
        sorted_candidates = sorted(candidates, key=lambda c: c.candidate_hash)

        # 2. The measure: per-candidate fractions from the vendored Rust
        #    allocator (wasm-first, CLI fallback -- see bcinr_bridge).
        raw_fractions_by_id = rank_candidates(sorted_candidates)
        raw_fractions = [raw_fractions_by_id[c.branch_id] for c in sorted_candidates]

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
            # Keep the top candidate to prevent total starvation.
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
            total_option_value_preserved=total_preserved,
            entropy=total_entropy,
        )
