"""CMCA resource allocator for candidate frontier (§38, §73).

Discrete cascade allocating bounded budget (compute, tokens, experimentation)
to UNKNOWN items across the candidate frontier.
Enforces that models/proposers cannot grant themselves more budget.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class AllocationStanding(str, Enum):
    ADMITTED = "ADMITTED"
    PRUNED = "PRUNED"
    DEFERRED = "DEFERRED"
    EXHAUSTED = "EXHAUSTED"


class AutonomousBudgetExpansionRefused(PermissionError):
    """Raised when an agent, model, or candidate attempts to self-grant or expand its allocated budget (§38, §73)."""


@dataclass(frozen=True, slots=True)
class ExplorationBudget:
    """Discrete finite resource budget for resolving UNKNOWN items (§38)."""

    max_compute_ticks: int
    max_tokens: int
    max_experiments: int
    concurrency_lanes: int = 8  # Chatman constant 8

    def validate(self) -> None:
        if self.max_compute_ticks <= 0:
            raise ValueError("max_compute_ticks must be strictly positive")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be strictly positive")
        if self.max_experiments <= 0:
            raise ValueError("max_experiments must be strictly positive")
        if self.concurrency_lanes <= 0:
            raise ValueError("concurrency_lanes must be strictly positive")


@dataclass(frozen=True, slots=True)
class UnknownCandidate:
    """Candidate on the UNKNOWN frontier competing for exploration budget (§38)."""

    item_id: str
    description: str
    option_entropy: float  # Estimated option entropy / information gain
    estimated_cost: float  # Baseline cost estimate
    historical_yield: float = 1.0  # Historical payoff ratio
    requested_tokens: int | None = None
    metadata: Mapping[str, Any] | None = None

    @property
    def item_hash(self) -> str:
        blob = f"{self.item_id}:{self.description}:{self.option_entropy}:{self.estimated_cost}:{self.historical_yield}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CandidateAllocation:
    """Allocated slice of exploration budget for an UNKNOWN item."""

    item_id: str
    allocated_fraction: float
    allocated_ticks: int
    allocated_tokens: int
    allocated_experiments: int
    priority_lane: int
    standing: AllocationStanding


@dataclass(frozen=True, slots=True)
class FrontierAllocationPlan:
    """Immutable, content-bound manifest of a CMCA frontier allocation (§38)."""

    plan_id: str
    parent_budget: ExplorationBudget
    allocations: tuple[CandidateAllocation, ...]
    total_entropy_preserved: float

    @property
    def plan_hash(self) -> str:
        payload = {
            "plan_id": self.plan_id,
            "preserved": round(self.total_entropy_preserved, 8),
            "allocations": [
                {
                    "item_id": a.item_id,
                    "fraction": round(a.allocated_fraction, 8),
                    "ticks": a.allocated_ticks,
                    "tokens": a.allocated_tokens,
                    "experiments": a.allocated_experiments,
                    "standing": a.standing.value,
                    "lane": a.priority_lane,
                }
                for a in self.allocations
            ],
        }
        dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


class CMCACandidateAllocator:
    """Discrete cascade allocating bounded budget to UNKNOWN candidate items (§38, §73)."""

    def __init__(self, *, pruning_threshold: float = 0.01) -> None:
        if not (0.0 <= pruning_threshold < 1.0):
            raise ValueError("pruning_threshold must be in [0.0, 1.0)")
        self.pruning_threshold = pruning_threshold

    def allocate(
        self,
        *,
        plan_id: str,
        budget: ExplorationBudget,
        candidates: Sequence[UnknownCandidate],
    ) -> FrontierAllocationPlan:
        """Deterministically allocate exploration budget across candidate frontier items."""
        budget.validate()
        if not candidates:
            return FrontierAllocationPlan(
                plan_id=plan_id,
                parent_budget=budget,
                allocations=(),
                total_entropy_preserved=0.0,
            )

        # Enforce N <= 8 (Chatman constant / compiled lens capacity)
        if len(candidates) > budget.concurrency_lanes:
            raise ValueError(
                f"Candidate frontier cardinality {len(candidates)} exceeds maximum lanes {budget.concurrency_lanes}"
            )

        # 1. Deterministic canonical ordering by candidate hash
        sorted_candidates = sorted(candidates, key=lambda c: c.item_hash)

        # 2. Compute salience measures S = option_entropy * historical_yield / max(cost, 1e-6)
        saliences: list[float] = []
        for c in sorted_candidates:
            if math.isnan(c.option_entropy) or math.isnan(c.estimated_cost) or math.isnan(c.historical_yield):
                raise ValueError(f"Candidate {c.item_id} carries non-finite feature values")
            cost = max(c.estimated_cost, 1e-6)
            entropy = max(c.option_entropy, 0.0)
            yield_score = max(c.historical_yield, 0.0)
            salience = (entropy * yield_score) / cost
            saliences.append(salience)

        total_salience = sum(saliences)
        if total_salience <= 0.0:
            raw_fractions = [1.0 / len(sorted_candidates)] * len(sorted_candidates)
        else:
            raw_fractions = [s / total_salience for s in saliences]

        # 3. Prune candidates falling below preservation threshold
        active_indices: list[int] = []
        pruned_indices: list[int] = []
        for idx, frac in enumerate(raw_fractions):
            if frac < self.pruning_threshold:
                pruned_indices.append(idx)
            else:
                active_indices.append(idx)

        # Prevent total starvation: keep top candidate
        if not active_indices:
            top_idx = max(range(len(raw_fractions)), key=lambda i: raw_fractions[i])
            active_indices = [top_idx]
            pruned_indices = [i for i in range(len(raw_fractions)) if i != top_idx]

        active_sum = sum(raw_fractions[i] for i in active_indices)
        normalized_fractions = {
            i: (raw_fractions[i] / active_sum) for i in active_indices
        }

        # 4. Discrete resource projection
        allocations: list[CandidateAllocation] = []
        total_entropy = 0.0

        sorted_active = sorted(
            active_indices, key=lambda i: normalized_fractions[i], reverse=True
        )
        lane_count = budget.concurrency_lanes

        for lane_idx, idx in enumerate(sorted_active):
            c = sorted_candidates[idx]
            frac = normalized_fractions[idx]
            ticks = max(1, math.floor(frac * budget.max_compute_ticks))
            tokens = max(1, math.floor(frac * budget.max_tokens))
            experiments = max(1, math.floor(frac * budget.max_experiments))

            # Enforce budget cap: candidate cannot exceed parent budget
            ticks = min(ticks, budget.max_compute_ticks)
            tokens = min(tokens, budget.max_tokens)
            experiments = min(experiments, budget.max_experiments)

            total_entropy += c.option_entropy * frac
            allocations.append(
                CandidateAllocation(
                    item_id=c.item_id,
                    allocated_fraction=frac,
                    allocated_ticks=ticks,
                    allocated_tokens=tokens,
                    allocated_experiments=experiments,
                    priority_lane=lane_idx % lane_count,
                    standing=AllocationStanding.ADMITTED,
                )
            )

        for idx in pruned_indices:
            c = sorted_candidates[idx]
            allocations.append(
                CandidateAllocation(
                    item_id=c.item_id,
                    allocated_fraction=0.0,
                    allocated_ticks=0,
                    allocated_tokens=0,
                    allocated_experiments=0,
                    priority_lane=lane_count - 1,
                    standing=AllocationStanding.PRUNED,
                )
            )

        allocations.sort(key=lambda a: a.item_id)

        return FrontierAllocationPlan(
            plan_id=plan_id,
            parent_budget=budget,
            allocations=tuple(allocations),
            total_entropy_preserved=total_entropy,
        )

    def enforce_no_autonomous_expansion(
        self,
        *,
        allocation: CandidateAllocation,
        requested_additional_ticks: int = 0,
        requested_additional_tokens: int = 0,
        requested_additional_experiments: int = 0,
        caller_authority: str = "model",
    ) -> None:
        """Enforce invariant §38 & §73: model cannot grant itself more budget.

        If caller_authority is model/candidate/planner, any request for positive
        additional budget without an external administrative re-allocation raises
        AutonomousBudgetExpansionRefused.
        """
        if requested_additional_ticks < 0 or requested_additional_tokens < 0 or requested_additional_experiments < 0:
            raise ValueError("Requested additional resource amounts cannot be negative")

        has_expansion_request = (
            requested_additional_ticks > 0
            or requested_additional_tokens > 0
            or requested_additional_experiments > 0
        )

        if has_expansion_request:
            if caller_authority.lower() in ("model", "candidate", "planner", "subagent", "untrusted"):
                raise AutonomousBudgetExpansionRefused(
                    f"Authority '{caller_authority}' attempted autonomous budget expansion on item '{allocation.item_id}'. "
                    f"Enforcement §38 & §73: models cannot grant themselves more budget."
                )
