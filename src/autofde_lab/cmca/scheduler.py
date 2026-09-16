"""Scheduler and receipt feedback engine for CMCA.

Executes Dual Learning Loop 2:
Receipt -> Payoff Calculation -> Update Allocation Priors
"""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import (
    AllocationReceipt,
    AllocationStanding,
    CascadeAllocationPlan,
)


class CMCAScheduler:
    """Dispatches allocations and maintains empirical payoff tracking."""

    def __init__(self) -> None:
        # operator_id -> list of historical payoff scores
        self._operator_payoffs: dict[str, list[float]] = {}

    def get_historical_yield(self, operator_id: str, default: float = 1.0) -> float:
        history = self._operator_payoffs.get(operator_id)
        if not history:
            return default
        return sum(history) / len(history)

    def record_receipt(self, receipt: AllocationReceipt, operator_id: str) -> None:
        """Update empirical yield for Loop 2."""
        if operator_id not in self._operator_payoffs:
            self._operator_payoffs[operator_id] = []
        self._operator_payoffs[operator_id].append(receipt.payoff_score)

    def filter_actionable_allocations(
        self, plan: CascadeAllocationPlan
    ) -> Sequence[tuple[str, int, int]]:
        """Return (branch_id, ticks, depth) for admitted branches."""
        return tuple(
            (a.branch_id, a.allocated_ticks, a.verification_depth)
            for a in plan.allocations
            if a.standing is AllocationStanding.ADMITTED and a.allocated_ticks > 0
        )
