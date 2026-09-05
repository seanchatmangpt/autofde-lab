"""Chicago-style test: real FORTUNE5_SPACE, real iter_lawful, real dominance.

No unittest.mock/Mock/MagicMock/patch/monkeypatch anywhere in this module --
every collaborator below is the real, installed StateSpace/Scenario/Option
machinery from autofde_lab.fortune5.
"""

from __future__ import annotations

import dataclasses

from autofde_lab.fortune5 import FORTUNE5_SPACE
from autofde_lab.fortune5.dfcm_compare import compare_lawful_scenarios


def test_pareto_frontier_is_nonempty_strict_subset_of_feasible() -> None:
    result = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=20000)

    assert len(result.pareto_scenario_ids) > 0
    frontier = set(result.pareto_scenario_ids)
    feasible = set(result.feasible_scenario_ids)
    assert frontier.issubset(feasible)
    assert frontier != feasible  # strict subset: real dominance eliminated some


def test_feasible_is_strict_subset_of_enumerated_something_was_eliminated() -> None:
    result = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=20000)

    assert len(result.feasible_scenario_ids) < result.scenario_count
    # Named cause, per the cap-7 gap: policy=baseline with a regulated
    # data_class (confidential/restricted) is eliminated by _is_feasible,
    # never rescored.


def test_frontier_members_expose_real_tradeoffs_not_one_aggregate() -> None:
    result = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=20000)

    assert len(result.tradeoffs) == len(result.pareto_scenario_ids)
    vectors = [vector for _, vector in result.tradeoffs]
    assert len(vectors) >= 2

    # At least one pair of frontier members must differ on at least one real
    # axis -- if every vector were identical, the "frontier" would be hiding
    # tradeoffs in one opaque aggregate rather than exposing them (this is
    # the PRD's own falsifier for capability 7).
    distinct_axis_found = any(
        vectors[i][axis] != vectors[j][axis]
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
        for axis in range(4)
    )
    assert distinct_axis_found


def test_digest_is_deterministic_over_space_limit_start() -> None:
    first = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=5000, start=0)
    second = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=5000, start=0)
    assert first.digest == second.digest

    shifted = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=5000, start=50)
    assert shifted.digest != first.digest


def test_result_has_no_winner_selected_or_best_field() -> None:
    field_names = {
        f.name
        for f in dataclasses.fields(
            compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=50)
        )
    }
    assert "winner" not in field_names
    assert "selected" not in field_names
    assert "best" not in field_names


def test_rejects_scenario_count_smaller_than_feasible_count_is_impossible() -> None:
    # Sanity: scenario_count must always dominate feasible + pareto counts,
    # confirming iter_lawful (real enumeration) backs every number reported.
    result = compare_lawful_scenarios(space=FORTUNE5_SPACE, limit=20000)
    assert result.scenario_count >= len(result.feasible_scenario_ids)
    assert len(result.feasible_scenario_ids) >= len(result.pareto_scenario_ids)
