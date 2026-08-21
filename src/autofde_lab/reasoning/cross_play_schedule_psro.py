# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Drives a real PSRO step from `cross_play_schedule_payoff.py`'s real,
bounded scoring of `cover_cross_play`'s scheduled matches -- closing the
gap this pass's own investigation found: `admit_cross_play_schedule_payoffs`
had zero real callers outside its own test; its real `PayoffHypergraph`
output had never itself been driven through
`exploration_psro_loop.py`-style `PolicySpaceResponseOracle.step()`
(`grep -rln "admit_cross_play_schedule_payoffs|ScheduledMatchPayoffOutcome"
src/ tests/` found only its own definition and test file).

Real, load-bearing finding confirmed live before any code was written:
`cover_cross_play`'s own real covering schedule is explicitly **not** a
full N x N sweep ("Deterministic covering schedule over admitted edges,
not an N^2 sweep" -- its own docstring). Each real constructor planner is
paired against only `rounds` real opponents, and different constructors'
opponent windows shift. Seeding a real `PsroState` uniformly over every
real opponent observed in a bounded subset therefore usually -- and
correctly -- produces a real `REFUSED:PSRO_MISSING_PAYOFF_CLOSURE`, not an
advance: confirmed live with `limit=6` against `BreachClockDomain`,
`AOstar`'s real opponent window is `{AOstar, Astar, BFWS}` and `Astar`'s is
`{Astar, BFWS, DESPOT}` -- neither has real coverage of the union, so PSRO
correctly refuses rather than guessing. This is `psro.py`'s own designed
fail-closed contract working exactly as intended, not a defect in this
module. `run_cross_play_schedule_psro_round` therefore seeds `PsroState`
over the real union of every opponent actually observed in the bounded
subset **by default** -- never artificially narrowed to a
conveniently-always-covered subset. A caller wanting a genuine advance
over multiple real candidates may pass an explicit `opponent_ids` naming a
real intersecting subset (confirmed live: seeding just `("Astar", "BFWS")`
-- the real intersection of `AOstar`'s and `Astar`'s own observed
opponents -- produces a real `ALIVE` advance, `Astar` selected via
`empirical_best_response`'s own real lexicographic tie-break at an
observed real 0.5/0.5 tie) -- but this module never computes or defaults
to that intersection itself; doing so silently would manufacture an
advance rather than report the real, empirically-observed contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from autofde_lab.planner_league import PayoffHypergraph
from autofde_lab.planner_league.cross_play_world_schedule import CrossPlayScheduleOutcome
from autofde_lab.planner_league.psro import PolicySpaceResponseOracle, PsroState, PsroStep

from .cross_play_schedule_payoff import ScheduledMatchPayoffOutcome, admit_cross_play_schedule_payoffs

__all__ = ["CrossPlaySchedulePsroOutcome", "run_cross_play_schedule_psro_round"]


@dataclass(frozen=True, slots=True)
class CrossPlaySchedulePsroOutcome:
    """Real, typed result of one full real run: the real per-match payoff
    outcomes, the real `PayoffHypergraph` they populated, and the real
    `PsroStep` computed from it -- every real intermediate object
    preserved, never only a summary derived from them."""

    payoff_outcomes: tuple[ScheduledMatchPayoffOutcome, ...]
    hypergraph: PayoffHypergraph
    psro_step: PsroStep


def run_cross_play_schedule_psro_round(
    schedule: CrossPlayScheduleOutcome,
    domain: object,
    *,
    limit: int,
    role_id: str,
    opponent_role_id: str,
    world_id: str,
    opponent_ids: Sequence[str] | None = None,
    observation_projection_id: str = "full_observation",
    budget_id: str = "balanced",
) -> CrossPlaySchedulePsroOutcome:
    """Real-score the first `limit` real matches of `schedule` (via
    `admit_cross_play_schedule_payoffs`), then run one real PSRO step
    treating every distinct real left-side planner observed as a
    candidate and (by default) every distinct real right-side planner
    observed as the opponent population -- see module docstring for why
    that default is the real union, never a manufactured intersection.

    `opponent_ids`, if supplied, replaces the default union with the
    caller's own explicit real opponent set (e.g. a real intersecting
    subset, to make an advance possible) -- this function performs no
    validation that the supplied set is itself real/intersecting; an
    invalid choice simply flows into `PsroState.seed`'s own real
    validation and `empirical_best_response`'s own real coverage check,
    exactly as any other caller of those real objects would experience.

    Raises `ValueError("REFUSED:NO_SCHEDULED_MATCHES")` if the bounded
    subset produced zero real candidates (an empty/refused `schedule`, or
    `limit` larger than `schedule.matches` is otherwise harmless -- Python
    slicing -- but zero real matches leaves nothing to seed PSRO with).
    """
    hypergraph = PayoffHypergraph()
    payoff_outcomes = admit_cross_play_schedule_payoffs(schedule, domain, hypergraph=hypergraph, limit=limit)

    constructor_planner_ids = tuple(dict.fromkeys(o.match.left_policy.planner_id for o in payoff_outcomes))
    if not constructor_planner_ids:
        raise ValueError("REFUSED:NO_SCHEDULED_MATCHES")

    real_opponent_ids = (
        tuple(opponent_ids)
        if opponent_ids is not None
        else tuple(dict.fromkeys(o.match.right_policy.planner_id for o in payoff_outcomes))
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
        payoff_outcomes=payoff_outcomes, hypergraph=hypergraph, psro_step=psro_step
    )
