"""Exact-subject SA2A advice over the canonical FOND x HDDL product frontier.

Formal FOND/HDDL reachability remains sovereign.  Computation advice can only
reorder actions already present on the exact product-state frontier.
"""

from __future__ import annotations

from dataclasses import dataclass

from autofde_lab.planning.fond_hddl_product import ProductReachability, ProductState
from autofde_lab.sa2a.computation import PlanningAdvice, order_formally_admitted


@dataclass(frozen=True, slots=True)
class ProductFrontierOrder:
    state_id: str
    planning_subject_identity: str
    formal_projection_identity: str
    formal_action_refs: tuple[str, ...]
    ordered_action_refs: tuple[str, ...]
    advice_identity: str

    @property
    def preserves_formal_frontier(self) -> bool:
        return set(self.formal_action_refs) == set(self.ordered_action_refs)


def order_product_frontier(
    *,
    reachability: ProductReachability,
    state: ProductState,
    advice: PlanningAdvice,
    planning_subject_identity: str,
    formal_projection_identity: str,
) -> ProductFrontierOrder:
    """Apply powerless advice to one exact FOND x HDDL product frontier."""

    if advice.planning_subject_identity != planning_subject_identity:
        raise ValueError("PLANNING_ADVICE_SUBJECT_IDENTITY_MISMATCH")
    if advice.formal_projection_identity != formal_projection_identity:
        raise ValueError("PLANNING_ADVICE_FORMAL_PROJECTION_MISMATCH")

    state_id = state.key()
    if state_id not in reachability.states_by_key:
        raise ValueError("PLANNING_ADVICE_STATE_NOT_IN_PRODUCT")

    formal_actions = tuple(
        sorted(
            action
            for (source, action) in reachability.fond_problem.transitions
            if source == state_id
        )
    )
    ordered = order_formally_admitted(advice, formal_actions)

    result = ProductFrontierOrder(
        state_id=state_id,
        planning_subject_identity=planning_subject_identity,
        formal_projection_identity=formal_projection_identity,
        formal_action_refs=formal_actions,
        ordered_action_refs=ordered,
        advice_identity=advice.advice_identity,
    )
    if not result.preserves_formal_frontier:
        raise AssertionError("SA2A advice destroyed the formal FOND x HDDL frontier")
    return result


__all__ = ["ProductFrontierOrder", "order_product_frontier"]
