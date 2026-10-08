import pytest

from autofde_lab.evolution import (
    StatisticalPromotionPolicy,
)
from autofde_lab.evolution.paired_promotion import PairedTrial
from autofde_lab.evolution.promotion_campaign import (
    CampaignStatus,
    PromotionCampaignController,
)
from autofde_lab.evolution.promotion_registry import ChampionRegistry


def _trial(task: str, delta: float = 0.1) -> PairedTrial:
    return PairedTrial(
        task_id=task,
        seed=19,
        budget_id="steps:64",
        champion_score=0.5,
        candidate_score=0.5 + delta,
        champion_evidence_digest=f"sha256:champion-{task}",
        candidate_evidence_digest=f"sha256:candidate-{task}",
    )


def _campaign():
    champion = ChampionRegistry.initialize("cap:v1")
    campaign = PromotionCampaignController.start(
        campaign_id="campaign:1",
        champion=champion,
        candidate_id="cap:v2",
        policy=StatisticalPromotionPolicy(
            minimum_trials=3,
            maximum_trials=5,
            minimum_lower_bound=0.0,
        ),
    )
    return champion, campaign


def test_campaign_collects_until_statistical_bound_then_becomes_promotable() -> None:
    champion, campaign = _campaign()

    campaign = PromotionCampaignController.observe(campaign, _trial("a"))
    assert campaign.status is CampaignStatus.COLLECTING

    campaign = PromotionCampaignController.observe(campaign, _trial("b"))
    assert campaign.status is CampaignStatus.COLLECTING

    campaign = PromotionCampaignController.observe(campaign, _trial("c"))
    assert campaign.status is CampaignStatus.PROMOTABLE
    assert campaign.verdict_digest is not None
    assert campaign.authority == "none"

    commit = PromotionCampaignController.commit(
        campaign,
        current=champion,
        cohort_digest="sha256:cohort",
    )
    assert commit.state.champion_id == "cap:v2"
    assert commit.record.champion_before == "cap:v1"
    assert commit.authority == "none"


def test_campaign_refuses_duplicate_cohort_before_court_reuse() -> None:
    _champion, campaign = _campaign()
    campaign = PromotionCampaignController.observe(campaign, _trial("a"))

    with pytest.raises(ValueError, match="DUPLICATE_COHORT_IDENTITY"):
        PromotionCampaignController.observe(campaign, _trial("a"))


def test_campaign_cannot_commit_after_champion_generation_changes() -> None:
    champion, campaign = _campaign()
    for task in ("a", "b", "c"):
        campaign = PromotionCampaignController.observe(campaign, _trial(task))

    competing = PromotionCampaignController.start(
        campaign_id="competing",
        champion=champion,
        candidate_id="cap:v3",
        policy=campaign.policy,
    )
    for task in ("d", "e", "f"):
        competing = PromotionCampaignController.observe(competing, _trial(task))
    competing_commit = PromotionCampaignController.commit(
        competing,
        current=champion,
        cohort_digest="sha256:competing",
    )

    with pytest.raises(ValueError, match="CAMPAIGN_CHAMPION_CHANGED"):
        PromotionCampaignController.commit(
            campaign,
            current=competing_commit.state,
            cohort_digest="sha256:stale",
        )


def test_regression_closes_campaign_as_held_and_prevents_more_evidence() -> None:
    _champion, campaign = _campaign()
    campaign = PromotionCampaignController.observe(campaign, _trial("a", -0.01))

    assert campaign.status is CampaignStatus.HELD

    with pytest.raises(ValueError, match="CAMPAIGN_NOT_COLLECTING"):
        PromotionCampaignController.observe(campaign, _trial("b"))


def test_campaign_digest_is_independent_of_observation_order_after_same_set() -> None:
    champion, first = _campaign()
    second = PromotionCampaignController.start(
        campaign_id=first.campaign_id,
        champion=champion,
        candidate_id=first.candidate_id,
        policy=first.policy,
    )

    for task in ("a", "b"):
        first = PromotionCampaignController.observe(first, _trial(task))

    for task in ("b", "a"):
        second = PromotionCampaignController.observe(second, _trial(task))

    assert first.campaign_digest == second.campaign_digest
