# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago-style tests for the real cross-play schedule -> payoff -> PSRO join.

Real collaborators throughout: ``BreachClockDomain``, ``PlannerLeague``,
``schedule_cross_play_for_world``, and installed planner entry points. No
interaction mocks are used. The reversible experiment compares the existing
fail-closed union seed with an explicit evidence-derived intersection seed and
with the previous caller-supplied manual intersection.
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
        league,
        "cyber_incident",
        left_role_id="plan_constructor",
        right_role_id="plan_falsifier",
    )


def _run(schedule, domain, **kwargs):
    return run_cross_play_schedule_psro_round(
        schedule,
        domain,
        limit=kwargs.pop("limit", 6),
        role_id="plan_constructor",
        opponent_role_id="plan_falsifier",
        world_id="cyber_incident",
        **kwargs,
    )


def test_single_candidate_subset_advances_trivially() -> None:
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = _run(schedule, domain, limit=3)

    assert isinstance(result, CrossPlaySchedulePsroOutcome)
    assert len(result.payoff_outcomes) == 3
    assert len(result.hypergraph.observations) == 3
    assert result.opponent_ids == ("AOstar", "Astar", "BFWS")
    assert result.psro_step.advanced
    assert result.psro_step.standing == "ALIVE"
    assert result.psro_step.receipt is not None
    assert result.psro_step.receipt.selected_best_response == "AOstar"


def test_default_union_seed_over_two_candidates_honestly_refuses() -> None:
    """The old/default alternative remains fail-closed on incomplete coverage."""
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = _run(schedule, domain)

    assert len(result.payoff_outcomes) == 6
    assert len(result.hypergraph.observations) == 6
    assert result.opponent_ids == ("AOstar", "Astar", "BFWS", "DESPOT")
    assert not result.psro_step.advanced
    assert result.psro_step.standing == "REFUSED"
    assert result.psro_step.reason == "REFUSED:PSRO_MISSING_PAYOFF_CLOSURE"
    assert result.psro_step.receipt is None


def test_explicit_intersecting_opponent_ids_makes_a_real_two_candidate_advance_possible() -> None:
    schedule = _real_schedule()
    domain = BreachClockDomain()

    result = _run(schedule, domain, opponent_ids=("Astar", "BFWS"))

    assert result.opponent_ids == ("Astar", "BFWS")
    assert result.psro_step.advanced
    assert result.psro_step.standing == "ALIVE"
    assert result.psro_step.receipt is not None
    assert result.psro_step.receipt.selected_best_response == "Astar"


def test_intersection_strategy_derives_the_same_real_seed_and_receipt_as_manual_override() -> None:
    """Falsifier for the new feature: derive, do not invent, the known closure."""
    schedule = _real_schedule()
    domain = BreachClockDomain()

    derived = _run(schedule, domain, opponent_selection="intersection")
    manual = _run(schedule, domain, opponent_ids=("Astar", "BFWS"))

    assert derived.opponent_ids == ("Astar", "BFWS")
    assert derived.opponent_ids == manual.opponent_ids
    assert derived.psro_step.advanced
    assert derived.psro_step.standing == "ALIVE"
    assert derived.psro_step.receipt is not None
    assert manual.psro_step.receipt is not None
    assert derived.psro_step.receipt == manual.psro_step.receipt
    assert derived.hypergraph.observations == manual.hypergraph.observations


def test_intersection_strategy_is_deterministic_across_independent_runs() -> None:
    schedule = _real_schedule()

    first = _run(schedule, BreachClockDomain(), opponent_selection="intersection")
    second = _run(schedule, BreachClockDomain(), opponent_selection="intersection")

    assert first.opponent_ids == second.opponent_ids == ("Astar", "BFWS")
    assert first.psro_step.receipt == second.psro_step.receipt
    assert first.hypergraph.observations == second.hypergraph.observations


def test_unknown_opponent_selection_refuses_instead_of_falling_back() -> None:
    schedule = _real_schedule()
    domain = BreachClockDomain()

    try:
        _run(schedule, domain, opponent_selection="guess")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "REFUSED:UNKNOWN_OPPONENT_SELECTION:guess"


def test_refuses_when_the_bounded_subset_has_zero_real_matches() -> None:
    league = PlannerLeague()
    unsupported_schedule = schedule_cross_play_for_world(
        league,
        "cyber_incident",
        left_role_id="plan_constructor",
        right_role_id="plan_falsifier",
        domain_factories={},
    )
    assert unsupported_schedule.standing == "UNSUPPORTED"
    assert unsupported_schedule.matches == ()

    domain = BreachClockDomain()
    try:
        _run(unsupported_schedule, domain, limit=5)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "REFUSED:NO_SCHEDULED_MATCHES"
