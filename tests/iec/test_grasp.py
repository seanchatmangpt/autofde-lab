from __future__ import annotations

import dataclasses

import pytest

from autofde_lab.iec.crowns.model import Verdict
from autofde_lab.iec.grasp import (
    Doctrine,
    StrategyCandidate,
    evaluate_candidate,
    partition_doctrine,
    select_candidate,
)


SUBJECT = "urn:berthier:v26.9.25:mission-1"


def doctrine(**changes) -> Doctrine:
    values = {
        "doctrine_id": "doctrine:33-strategies:v26.9.25",
        "exact_subject": SUBJECT,
        "required_constraints": frozenset({"authority-conserved", "bounded"}),
        "allowed_strategy_ids": frozenset({"s1", "s2", "s3", "s4"}),
        "max_partitions": 4,
        "max_strategies_per_partition": 2,
        "max_candidates_per_partition": 3,
    }
    values.update(changes)
    return Doctrine(**values)


def partitions(d: Doctrine | None = None):
    d = d or doctrine()
    return partition_doctrine(
        d,
        [
            {
                "partition_id": "direct",
                "strategy_ids": ["s1", "s2"],
                "constraints": ["authority-conserved", "bounded", "direct-only"],
            },
            {
                "partition_id": "indirect",
                "strategy_ids": ["s3", "s4"],
                "constraints": ["authority-conserved", "bounded", "indirect-only"],
            },
        ],
    )


def candidate(partition, *, candidate_id="c1", score=1.0, **changes):
    values = {
        "candidate_id": candidate_id,
        "exact_subject": SUBJECT,
        "partition_id": partition.partition_id,
        "partition_digest": partition.digest,
        "strategy_ids": tuple(sorted(partition.strategy_ids))[:1],
        "constraints": partition.constraints,
        "score": score,
        "producer_digest": "sha256:" + "a" * 64,
        "authority_delta": 0,
        "route": ("SA2A", "BRCE", "DO"),
    }
    values.update(changes)
    return StrategyCandidate(**values)


def test_partitioning_refuses_constraint_weakening_and_cross_partition_overlap() -> None:
    d = doctrine()
    with pytest.raises(ValueError, match="CONSTRAINT_WEAKENING"):
        partition_doctrine(
            d,
            [{"partition_id": "p", "strategy_ids": ["s1"], "constraints": ["bounded"]}],
        )

    with pytest.raises(ValueError, match="CROSS_PARTITION_CONTAMINATION"):
        partition_doctrine(
            d,
            [
                {
                    "partition_id": "p1",
                    "strategy_ids": ["s1"],
                    "constraints": ["authority-conserved", "bounded"],
                },
                {
                    "partition_id": "p2",
                    "strategy_ids": ["s1", "s2"],
                    "constraints": ["authority-conserved", "bounded"],
                },
            ],
        )


def test_candidate_court_refuses_constraint_partition_authority_and_route_drift() -> None:
    d = doctrine()
    direct, indirect = partitions(d)
    mutated = candidate(
        direct,
        partition_id=indirect.partition_id,
        strategy_ids=("s3",),
        constraints=frozenset({"bounded"}),
        authority_delta=1,
        route=("SELECT", "BRCE", "DO"),
    )
    court = evaluate_candidate(d, direct, mutated)
    assert court.verdict is Verdict.COUNTEREXAMPLE
    assert "CROSS_PARTITION_CONTAMINATION" in court.failures
    assert "CONSTRAINT_WEAKENING" in court.failures
    assert "AUTHORITY_INCREASE" in court.failures
    assert "ILLEGAL_DOWNSTREAM_ROUTE" in court.failures
    assert court.authority == "none"


def test_select_is_not_do_and_only_returns_brce_mediated_route() -> None:
    d = doctrine()
    direct, indirect = partitions(d)
    result = select_candidate(
        d,
        (direct, indirect),
        (
            candidate(direct, candidate_id="c-low", score=1.0),
            candidate(indirect, candidate_id="c-high", score=9.0),
        ),
    )
    assert result.verdict is Verdict.PASS
    assert result.phase == "SELECT"
    assert result.authority == "none"
    assert result.selected_candidate_id == "c-high"
    assert result.route in (("SA2A", "BRCE", "DO"), ("XAAS", "BRCE", "DO"))
    assert result.route[-2:] == ("BRCE", "DO")


def test_selection_replay_is_independent_of_candidate_and_partition_order() -> None:
    d = doctrine()
    direct, indirect = partitions(d)
    candidates = (
        candidate(direct, candidate_id="c1", score=3.0),
        candidate(indirect, candidate_id="c2", score=7.0),
    )
    first = select_candidate(d, (direct, indirect), candidates)
    replay = select_candidate(d, (indirect, direct), tuple(reversed(candidates)))
    assert first.selected_candidate_digest == replay.selected_candidate_digest
    assert first.candidate_court_digests == replay.candidate_court_digests
    assert first.replay_digest == replay.replay_digest


def test_equal_scores_break_ties_by_content_identity_not_input_order() -> None:
    d = doctrine()
    direct, _indirect = partitions(d)
    left = candidate(direct, candidate_id="left", score=5.0, strategy_ids=("s1",))
    right = candidate(direct, candidate_id="right", score=5.0, strategy_ids=("s2",))
    first = select_candidate(d, (direct,), (left, right))
    replay = select_candidate(d, (direct,), (right, left))
    assert first.selected_candidate_id == replay.selected_candidate_id
    assert first.replay_digest == replay.replay_digest


def test_unbounded_candidate_fanout_blocks_selection_even_with_passing_candidates() -> None:
    d = doctrine(max_candidates_per_partition=1)
    direct, _indirect = partitions(d)
    result = select_candidate(
        d,
        (direct,),
        (
            candidate(direct, candidate_id="c1", score=2.0),
            candidate(direct, candidate_id="c2", score=1.0),
        ),
    )
    assert result.verdict is Verdict.COUNTEREXAMPLE
    assert "UNBOUNDED_CANDIDATES:direct" in result.failures
    assert result.selected_candidate_id is None


def test_candidate_partition_digest_prevents_relabelled_partition() -> None:
    d = doctrine()
    direct, _indirect = partitions(d)
    altered = dataclasses.replace(direct, constraints=direct.constraints | {"new-boundary"})
    court = evaluate_candidate(d, altered, candidate(direct))
    assert court.verdict is Verdict.COUNTEREXAMPLE
    assert "PARTITION_DIGEST_MISMATCH" in court.failures
    assert "CONSTRAINT_WEAKENING" in court.failures
