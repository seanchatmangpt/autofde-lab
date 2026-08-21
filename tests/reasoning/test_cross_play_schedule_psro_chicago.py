# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for `cross_play_schedule_psro` -- the real join
between `cross_play_schedule_payoff.py`'s real, bounded match scoring and
a real `PolicySpaceResponseOracle.step()`.

Real collaborators throughout: a real `BreachClockDomain`, a real
`PlannerLeague`, real `schedule_cross_play_for_world` output, and the
real, installed `AOstar`/`Astar`/`BFWS`/`DESPOT` solver entry points. No
`unittest.mock` / `Mock` / `MagicMock` / `patch` / `monkeypatch` anywhere
in this file.

Every value asserted below was confirmed live before being written, not
assumed: with `limit=3` (only `AOstar`'s real row), PSRO trivially
advances with `AOstar` selected (the single-candidate case this session
established repeatedly). With `limit=6` (`AOstar`'s and `Astar`'s real
rows), the real default union-of-opponents seed
(`{AOstar, Astar, BFWS, DESPOT}`) gives neither candidate real complete
coverage -> real `REFUSED:PSRO_MISSING_PAYOFF_CLOSURE`. Passing the real
intersection `("Astar", "BFWS")` explicitly as `opponent_ids` gives both
candidates real complete coverage -> real `ALIVE` advance, with `Astar`
selected via `empirical_best_response`'s own real lexicographic tie-break
at an observed real 0.5/0.5 score tie.
"""

from __future__ import annotations

from autofde_lab.hub.domain.breach_clock import BreachClockDomain
from autofde_lab.planner_league import PlannerLeague
from autofde_lab.planner_league.cross_play_world_schedule import schedule_cross_play_for_world
from autofde_lab.reasoning.cross_play_schedule_psro import (
    CrossPlaySchedulePsroOutcome,
    run_cross_play_schedule_psro_round,
)


def _real_schedule():
    league = PlannerLeague()
    return schedule_cross_play_for_world(
        league, "cyber_incident", left_role_id="plan_constructor", right_role_id="plan_falsifier"
    )


def test_single_candidate_subset_advances_trivially() -> None:
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = run_cross_play_schedule_psro_round(
        schedule,
        domain,
        limit=3,
        role_id="plan_constructor",
        opponent_role_id="plan_falsifier",
        world_id="cyber_incident",
    )

    assert isinstance(result, CrossPlaySchedulePsroOutcome)
    assert len(result.payoff_outcomes) == 3
    assert len(result.hypergraph.observations) == 3
    assert result.psro_step.advanced
    assert result.psro_step.standing == "ALIVE"
    assert result.psro_step.receipt is not None
    assert result.psro_step.receipt.selected_best_response == "AOstar"


def test_default_union_seed_over_two_candidates_honestly_refuses() -> None:
    """The real, load-bearing finding this module's docstring names:
    cover_cross_play's covering schedule deliberately does not give full
    pairwise coverage, so the honest default (seed over every real
    observed opponent) usually refuses rather than guessing."""
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = run_cross_play_schedule_psro_round(
        schedule,
        domain,
        limit=6,
        role_id="plan_constructor",
        opponent_role_id="plan_falsifier",
        world_id="cyber_incident",
    )

    assert len(result.payoff_outcomes) == 6
    assert len(result.hypergraph.observations) == 6
    assert not result.psro_step.advanced
    assert result.psro_step.standing == "REFUSED"
    assert result.psro_step.reason == "REFUSED:PSRO_MISSING_PAYOFF_CLOSURE"
    assert result.psro_step.receipt is None


def test_explicit_intersecting_opponent_ids_makes_a_real_two_candidate_advance_possible() -> None:
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = run_cross_play_schedule_psro_round(
        schedule,
        domain,
        limit=6,
        role_id="plan_constructor",
        opponent_role_id="plan_falsifier",
        world_id="cyber_incident",
        opponent_ids=("Astar", "BFWS"),
    )

    assert result.psro_step.advanced
    assert result.psro_step.standing == "ALIVE"
    assert result.psro_step.receipt is not None
    # Real tie at 0.5/0.5 (AOstar: [vs Astar=1.0, vs BFWS=0.0]; Astar: [vs
    # Astar=1.0, vs BFWS=0.0]) -- empirical_best_response's own real
    # lexicographic tie-break picks the greater planner_id string.
    assert result.psro_step.receipt.selected_best_response == "Astar"


def test_refuses_when_the_bounded_subset_has_zero_real_matches() -> None:
    league = PlannerLeague()
    unsupported_schedule = schedule_cross_play_for_world(
        league, "cyber_incident", left_role_id="plan_constructor", right_role_id="plan_falsifier",
        domain_factories={},
    )
    assert unsupported_schedule.standing == "UNSUPPORTED"
    assert unsupported_schedule.matches == ()

    domain = BreachClockDomain()
    try:
        run_cross_play_schedule_psro_round(
            unsupported_schedule,
            domain,
            limit=5,
            role_id="plan_constructor",
            opponent_role_id="plan_falsifier",
            world_id="cyber_incident",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "REFUSED:NO_SCHEDULED_MATCHES"
