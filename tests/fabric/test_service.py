from __future__ import annotations

import pytest

from skdecide.fabric.models import (
    CacheStatus,
    DecisionRefusal,
    DecisionRequest,
    DecisionStanding,
    RefusalCode,
)
from skdecide.fabric.service import DecisionFabric


def test_catalog_and_match_share_one_registry(fabric: DecisionFabric) -> None:
    assert fabric.catalog().domains == ("Counter",)
    assert fabric.catalog().solvers == ("CounterSolver",)

    first = fabric.match("Counter", domain_arguments={"limit": 3})
    second = fabric.match("Counter", domain_arguments={"limit": 3})

    assert first.cache_status is CacheStatus.MISS
    assert second.cache_status is CacheStatus.HIT
    assert first.compatible_solvers == ("CounterSolver",)
    assert first.identity_sha256 == second.identity_sha256


def test_solve_is_receipted_and_second_run_is_cache_hit(
    fabric: DecisionFabric,
) -> None:
    request = DecisionRequest(
        domain="Counter",
        domain_arguments={"limit": 2},
        subject_digest="subject:a",
        policy_digest="policy:a",
        environment_digest="env:a",
    )

    first = fabric.solve(request)
    second = fabric.solve(request)

    assert first.standing is DecisionStanding.SOLVED
    assert first.cache_status is CacheStatus.MISS
    assert second.cache_status is CacheStatus.HIT
    assert len(first.steps) == 2
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.trajectory_sha256 == second.trajectory_sha256


def test_material_identity_change_invalidates_exact_reuse(
    fabric: DecisionFabric,
) -> None:
    first = fabric.solve(
        DecisionRequest(
            domain="Counter",
            policy_digest="policy:a",
            subject_digest="subject:a",
            environment_digest="env:a",
        )
    )
    changed = fabric.solve(
        DecisionRequest(
            domain="Counter",
            policy_digest="policy:b",
            subject_digest="subject:a",
            environment_digest="env:a",
        )
    )

    assert first.cache_status is CacheStatus.MISS
    assert changed.cache_status is CacheStatus.MISS
    assert first.input_sha256 != changed.input_sha256


def test_bounded_run_does_not_claim_goal_completion(fabric: DecisionFabric) -> None:
    result = fabric.solve(
        DecisionRequest(
            domain="Counter",
            domain_arguments={"limit": 5},
            max_steps=2,
            use_cache=False,
        )
    )

    assert result.standing is DecisionStanding.BOUNDED
    assert result.terminal is False
    assert result.cache_status is CacheStatus.BYPASS


def test_deterministic_refusal_is_cached(fabric: DecisionFabric) -> None:
    request = DecisionRequest(domain="Counter", solver="Other")

    with pytest.raises(DecisionRefusal) as first:
        fabric.solve(request)
    with pytest.raises(DecisionRefusal) as second:
        fabric.solve(request)

    assert first.value.code is RefusalCode.SOLVER_INCOMPATIBLE
    assert second.value.code is RefusalCode.SOLVER_INCOMPATIBLE
    assert second.value.cache_status is CacheStatus.HIT
