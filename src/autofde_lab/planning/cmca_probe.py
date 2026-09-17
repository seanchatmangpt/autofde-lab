"""CMCA planning probe for the explicit FOND x HDDL product.

This module connects the planner's lawful reachable frontier to the canonical
CMCA allocator without granting CONSTRUCT or DO authority.  DfCM owns semantic
possibility; CMCA projects finite planning resources onto that possibility
space.  A branch receiving zero allocation remains lawful unless the planner,
admission layer, or a falsifier independently removes it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

from autofde_lab.cmca.cascade import MultifractalCascadeAllocator
from autofde_lab.cmca.contracts import (
    AllocationStanding,
    CandidateBranch,
    CascadeAllocationPlan,
    ResourceBudget,
)
from autofde_lab.planning.fond_hddl_product import ProductReachability, ProductState


class PlanningFrontierCardinalityRefusal(RuntimeError):
    """The lawful planning frontier exceeds the compiled CMCA N=8 shape."""


@dataclass(frozen=True, slots=True)
class PlanningProbeResult:
    """Receiptable projection of one lawful planning frontier through CMCA."""

    state_id: str
    candidates: tuple[CandidateBranch, ...]
    allocation_plan: CascadeAllocationPlan
    lawful_branch_ids: tuple[str, ...]
    allocated_branch_ids: tuple[str, ...]
    deferred_branch_ids: tuple[str, ...]
    probe_hash: str

    @property
    def preserves_dfcm_frontier(self) -> bool:
        """Resource non-selection must never masquerade as semantic elimination."""
        return set(self.allocated_branch_ids) | set(self.deferred_branch_ids) == set(
            self.lawful_branch_ids
        )


def _reachable_from(
    reachability: ProductReachability,
    seeds: frozenset[str],
) -> frozenset[str]:
    """Return all product states reachable from ``seeds`` in the finite product graph."""
    adjacency: dict[str, set[str]] = {}
    for (source, _action), targets in reachability.fond_problem.transitions.items():
        adjacency.setdefault(source, set()).update(targets)

    seen: set[str] = set()
    queue: deque[str] = deque(sorted(seeds))
    while queue:
        state_key = queue.popleft()
        if state_key in seen:
            continue
        seen.add(state_key)
        for successor in sorted(adjacency.get(state_key, ())):
            if successor not in seen:
                queue.append(successor)
    return frozenset(seen)


def candidates_from_product_frontier(
    *,
    reachability: ProductReachability,
    state: ProductState,
    historical_yield_by_action: Mapping[str, float] | None = None,
) -> tuple[CandidateBranch, ...]:
    """Project the lawful outgoing planner frontier into CMCA candidate branches.

    ``option_entropy`` is a structural option-value proxy derived only from the
    already-built finite product graph.  It is intentionally not presented as a
    probability distribution: more viable descendants and reachable goals retain
    more lawful future option volume.
    """
    history = historical_yield_by_action or {}
    state_key = state.key()
    outgoing = sorted(
        (
            action,
            successors,
        )
        for (source, action), successors in reachability.fond_problem.transitions.items()
        if source == state_key
    )

    if len(outgoing) > 8:
        raise PlanningFrontierCardinalityRefusal(
            f"{len(outgoing)} lawful planning branches exceed CMCA's compiled N=8 "
            "shape; refusing rather than silently dropping a lawful option"
        )

    candidates: list[CandidateBranch] = []
    for action, successors in outgoing:
        future = _reachable_from(reachability, successors)
        dead_future = future & reachability.dead_end_keys
        viable_future = future - reachability.dead_end_keys
        reachable_goals = future & reachability.fond_problem.goal_states

        # A monotone structural proxy: every viable future state counts once and
        # goal reachability counts again.  log2 keeps the axis well-scaled.
        option_volume = 1 + len(viable_future) + len(reachable_goals)
        option_entropy = math.log2(1.0 + option_volume)

        # Cost is a planning probe estimate, not runtime truth.  Nondeterministic
        # fan-out and known dead-end descendants increase verification effort.
        estimated_cost = (
            1.0
            + 0.25 * max(0, len(successors) - 1)
            + 0.10 * len(dead_future)
        )

        branch_id = f"plan:{hashlib.sha256(state_key.encode()).hexdigest()[:10]}:{action}"
        candidates.append(
            CandidateBranch(
                branch_id=branch_id,
                operator_id=action,
                world_id="fond-hddl-product",
                state_id=state_key,
                option_entropy=option_entropy,
                estimated_cost=estimated_cost,
                historical_yield=float(history.get(action, 1.0)),
                metadata={
                    "planning_action": action,
                    "successor_keys": tuple(sorted(successors)),
                    "viable_future_states": len(viable_future),
                    "dead_end_future_states": len(dead_future),
                    "reachable_goal_states": len(reachable_goals),
                    "semantic_standing": "LAWFUL",
                },
            )
        )
    return tuple(candidates)


def probe_product_frontier(
    *,
    reachability: ProductReachability,
    state: ProductState,
    budget: ResourceBudget,
    plan_id: str,
    historical_yield_by_action: Mapping[str, float] | None = None,
    allocator: MultifractalCascadeAllocator | None = None,
) -> PlanningProbeResult:
    """Allocate finite planning resources without deleting lawful alternatives."""
    candidates = candidates_from_product_frontier(
        reachability=reachability,
        state=state,
        historical_yield_by_action=historical_yield_by_action,
    )
    engine = allocator or MultifractalCascadeAllocator()
    plan = engine.allocate(plan_id=plan_id, budget=budget, candidates=candidates)

    lawful = tuple(sorted(c.branch_id for c in candidates))
    allocated = tuple(
        sorted(
            allocation.branch_id
            for allocation in plan.allocations
            if allocation.standing == AllocationStanding.ADMITTED
        )
    )
    deferred = tuple(sorted(set(lawful) - set(allocated)))

    payload = {
        "state_id": state.key(),
        "lawful": lawful,
        "allocated": allocated,
        "deferred": deferred,
        "plan_hash": plan.plan_hash,
    }
    probe_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    result = PlanningProbeResult(
        state_id=state.key(),
        candidates=candidates,
        allocation_plan=plan,
        lawful_branch_ids=lawful,
        allocated_branch_ids=allocated,
        deferred_branch_ids=deferred,
        probe_hash=probe_hash,
    )
    if not result.preserves_dfcm_frontier:
        raise AssertionError("CMCA planning projection destroyed a lawful DfCM branch")
    return result
