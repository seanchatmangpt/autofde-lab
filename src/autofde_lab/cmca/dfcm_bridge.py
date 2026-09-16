"""Bridge between DfCM option preservation and CMCA candidate frontier creation.

DfCM asks: what lawful futures can be reached?
CMCA calculates the discrete option entropy and cost per candidate branch.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .contracts import CandidateBranch


def compute_option_entropy(reachable_states: int, branching_factor: float) -> float:
    """Calculate the logarithmic option volume preserved by a lawful plan."""
    if reachable_states <= 0:
        return 0.0
    return math.log2(reachable_states + 1.0) * math.log(
        max(branching_factor, 1.0) + 1.0
    )


def build_candidate_branches_from_dfcm(
    *,
    domain_plan_pairs: Sequence[
        tuple[str, str, str, int, float, float]
    ],  # (branch_id, operator_id, world_id, reachable_count, branch_factor, cost)
    historical_yields: Mapping[str, float] | None = None,
) -> tuple[CandidateBranch, ...]:
    """Convert planning / DfCM search results into CMCA CandidateBranch records."""
    branches: list[CandidateBranch] = []
    yield_map = historical_yields or {}

    for (
        branch_id,
        op_id,
        world_id,
        reach_count,
        branch_factor,
        cost,
    ) in domain_plan_pairs:
        opt_entropy = compute_option_entropy(reach_count, branch_factor)
        hist_yield = yield_map.get(op_id, 1.0)
        branches.append(
            CandidateBranch(
                branch_id=branch_id,
                operator_id=op_id,
                world_id=world_id,
                state_id=f"state-{branch_id}",
                option_entropy=opt_entropy,
                estimated_cost=max(cost, 0.1),
                historical_yield=hist_yield,
            )
        )

    return tuple(branches)
