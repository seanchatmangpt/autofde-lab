# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Drive a real PSRO step from bounded cross-play schedule payoffs.

The default opponent-selection policy remains ``union``: every opponent
observed in the bounded schedule is seeded into PSRO, preserving the existing
fail-closed behavior when the covering schedule does not provide complete
pairwise payoff closure.

A caller may now explicitly select ``intersection``. That strategy derives
only opponents that were actually observed against every candidate planner in
the bounded sample. It never synthesizes a missing payoff and refuses when no
common observed opponent exists. ``opponent_ids`` remains the highest-priority
explicit override for callers that already own a real opponent subset.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from autofde_lab.planner_league import PayoffHypergraph
from autofde_lab.planner_league.cross_play_world_schedule import (
    CrossPlayScheduleOutcome,
)
from autofde_lab.planner_league.psro import (
    PolicySpaceResponseOracle,
    PsroState,
    PsroStep,
)

from .cross_play_schedule_payoff import (
    ScheduledMatchPayoffOutcome,
    admit_cross_play_schedule_payoffs,
)

__all__ = ["CrossPlaySchedulePsroOutcome", "run_cross_play_schedule_psro_round"]


@dataclass(frozen=True, slots=True)
class CrossPlaySchedulePsroOutcome:
    """Typed result preserving the real score, hypergraph, PSRO step, and seed."""

    payoff_outcomes: tuple[ScheduledMatchPayoffOutcome, ...]
    hypergraph: PayoffHypergraph
    psro_step: PsroStep
    opponent_ids: tuple[str, ...]


def _observed_opponent_intersection(
    payoff_outcomes: Sequence[ScheduledMatchPayoffOutcome],
    constructor_planner_ids: Sequence[str],
) -> tuple[str, ...]:
    """Return opponents observed against every candidate, in stable first-seen order.

    This is evidence-preserving intersection: only match observations already
    present in ``payoff_outcomes`` can enter the result. An empty intersection
    is a typed refusal because silently broadening or inventing coverage would
    violate PSRO's payoff-closure contract.
    """
    opponents_by_constructor: dict[str, set[str]] = {
        planner_id: set() for planner_id in constructor_planner_ids
    }
    first_seen: list[str] = []
    for outcome in payoff_outcomes:
        left = outcome.match.left_policy.planner_id
        right = outcome.match.right_policy.planner_id
        if left in opponents_by_constructor:
            opponents_by_constructor[left].add(right)
        if right not in first_seen:
            first_seen.append(right)

    common = set.intersection(
        *(
            opponents_by_constructor[planner_id]
            for planner_id in constructor_planner_ids
        )
    )
    selected = tuple(opponent_id for opponent_id in first_seen if opponent_id in common)
    if not selected:
        raise ValueError("REFUSED:NO_COMMON_OBSERVED_OPPONENTS")
    return selected


def _select_opponent_ids(
    payoff_outcomes: Sequence[ScheduledMatchPayoffOutcome],
    constructor_planner_ids: Sequence[str],
    *,
    opponent_ids: Sequence[str] | None,
    opponent_selection: str,
) -> tuple[str, ...]:
    if opponent_ids is not None:
        return tuple(opponent_ids)
    if opponent_selection == "union":
        return tuple(
            dict.fromkeys(o.match.right_policy.planner_id for o in payoff_outcomes)
        )
    if opponent_selection == "intersection":
        return _observed_opponent_intersection(payoff_outcomes, constructor_planner_ids)
    raise ValueError(f"REFUSED:UNKNOWN_OPPONENT_SELECTION:{opponent_selection}")


def run_cross_play_schedule_psro_round(
    schedule: CrossPlayScheduleOutcome,
    domain: object,
    *,
    limit: int,
    role_id: str,
    opponent_role_id: str,
    world_id: str,
    opponent_ids: Sequence[str] | None = None,
    opponent_selection: str = "union",
    observation_projection_id: str = "full_observation",
    budget_id: str = "balanced",
) -> CrossPlaySchedulePsroOutcome:
    """Score a bounded real schedule and run one real PSRO step.

    ``opponent_selection="union"`` preserves the prior default and therefore
    preserves honest ``REFUSED:PSRO_MISSING_PAYOFF_CLOSURE`` outcomes when the
    covering schedule is incomplete. ``opponent_selection="intersection"`` is
    an explicit reversible alternative that derives the largest common
    first-seen opponent subset actually observed for every candidate.

    ``opponent_ids`` remains an explicit caller-owned override and takes
    precedence over ``opponent_selection``. Unknown strategies and empty
    observed intersections refuse rather than falling back.
    """
    hypergraph = PayoffHypergraph()
    payoff_outcomes = admit_cross_play_schedule_payoffs(
        schedule, domain, hypergraph=hypergraph, limit=limit
    )

    constructor_planner_ids = tuple(
        dict.fromkeys(o.match.left_policy.planner_id for o in payoff_outcomes)
    )
    if not constructor_planner_ids:
        raise ValueError("REFUSED:NO_SCHEDULED_MATCHES")

    real_opponent_ids = _select_opponent_ids(
        payoff_outcomes,
        constructor_planner_ids,
        opponent_ids=opponent_ids,
        opponent_selection=opponent_selection,
    )

    state = PsroState.seed(real_opponent_ids)
    oracle = PolicySpaceResponseOracle(
        hypergraph,
        role_id=role_id,
        opponent_role_id=opponent_role_id,
        world_id=world_id,
        observation_projection_id=observation_projection_id,
        budget_id=budget_id,
    )
    psro_step = oracle.step(state, candidates=constructor_planner_ids)

    return CrossPlaySchedulePsroOutcome(
        payoff_outcomes=payoff_outcomes,
        hypergraph=hypergraph,
        psro_step=psro_step,
        opponent_ids=real_opponent_ids,
    )
