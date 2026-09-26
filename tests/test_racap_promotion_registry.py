from dataclasses import replace

import pytest

from autofde_lab.evolution import (
    PairedPromotionCourt,
    PairedTrial,
    SequentialDecision,
    StatisticalPairedPromotionCourt,
    StatisticalPromotionPolicy,
)
from autofde_lab.evolution.promotion_registry import ChampionRegistry


def _trial(task: str, champion: float = 0.4, candidate: float = 0.6) -> PairedTrial:
    return PairedTrial(
        task_id=task,
        seed=3,
        budget_id="steps:16",
        champion_score=champion,
        candidate_score=candidate,
        champion_evidence_digest=f"sha256:champion-{task}",
        candidate_evidence_digest=f"sha256:candidate-{task}",
    )


def test_promotion_advances_exact_champion_generation_and_hash_chain() -> None:
    initial = ChampionRegistry.initialize("cap:v1")
    verdict = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a"),),
    )

    current, record = ChampionRegistry.apply(
        initial,
        verdict,
        cohort_digest="sha256:cohort-a",
    )

    assert current.champion_id == "cap:v2"
    assert current.generation == 1
    assert record.champion_before == "cap:v1"
    assert record.champion_after == "cap:v2"
    assert record.authority == "none"
    assert ChampionRegistry.replay(initial, (record,)) == current


def test_stale_verdict_cannot_replace_newer_champion() -> None:
    initial = ChampionRegistry.initialize("cap:v1")
    first = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a"),),
    )
    current, _record = ChampionRegistry.apply(
        initial,
        first,
        cohort_digest="sha256:cohort-a",
    )

    stale = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v3",
        trials=(_trial("b"),),
    )

    with pytest.raises(ValueError, match="STALE_CHAMPION_VERDICT"):
        ChampionRegistry.apply(current, stale, cohort_digest="sha256:cohort-b")


def test_non_promotion_verdict_cannot_advance_registry() -> None:
    initial = ChampionRegistry.initialize("cap:v1")
    hold = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a", champion=0.9, candidate=0.8),),
    )

    with pytest.raises(ValueError, match="PROMOTION_VERDICT_NOT_ADMITTED"):
        ChampionRegistry.apply(initial, hold, cohort_digest="sha256:cohort")


def test_statistical_promotion_verdict_uses_same_registry_boundary() -> None:
    initial = ChampionRegistry.initialize("cap:v1")
    court = StatisticalPairedPromotionCourt(
        StatisticalPromotionPolicy(minimum_trials=3, maximum_trials=5)
    )
    verdict = court.evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a"), _trial("b"), _trial("c")),
    )

    assert verdict.decision is SequentialDecision.PROMOTE
    current, record = ChampionRegistry.apply(
        initial,
        verdict,
        cohort_digest="sha256:statistical-cohort",
    )
    assert current.champion_id == "cap:v2"
    assert record.verdict_digest == verdict.evidence_digest


def test_replay_refuses_tampered_record_chain() -> None:
    initial = ChampionRegistry.initialize("cap:v1")
    verdict = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a"),),
    )
    _current, record = ChampionRegistry.apply(
        initial,
        verdict,
        cohort_digest="sha256:cohort-a",
    )

    tampered = replace(record, champion_after="cap:evil")

    with pytest.raises(ValueError, match="PROMOTION_RECORD_DIGEST_MISMATCH"):
        ChampionRegistry.replay(initial, (tampered,))
