"""Bounded promotion campaign composed from paired evidence and champion state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256

from .paired_promotion import (
    PairedTrial,
    SequentialDecision,
    SequentialPromotionVerdict,
    StatisticalPairedPromotionCourt,
    StatisticalPromotionPolicy,
)
from .promotion_registry import ChampionRegistry, ChampionState, PromotionRecord


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class CampaignStatus(StrEnum):
    COLLECTING = "COLLECTING"
    PROMOTABLE = "PROMOTABLE"
    HELD = "HELD"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class PromotionCampaign:
    campaign_id: str
    champion_id: str
    champion_generation: int
    champion_history_digest: str
    candidate_id: str
    policy: StatisticalPromotionPolicy
    trials: tuple[PairedTrial, ...]
    status: CampaignStatus
    verdict_digest: str | None
    campaign_digest: str
    authority: str = "none"


@dataclass(frozen=True, slots=True)
class PromotionCommit:
    campaign_digest: str
    cohort_digest: str
    record: PromotionRecord
    state: ChampionState
    commit_digest: str
    authority: str = "none"


class PromotionCampaignController:
    """Collect paired trials against one immutable champion generation."""

    @staticmethod
    def start(
        *,
        campaign_id: str,
        champion: ChampionState,
        candidate_id: str,
        policy: StatisticalPromotionPolicy | None = None,
    ) -> PromotionCampaign:
        if not campaign_id.strip():
            raise ValueError("CAMPAIGN_ID_REQUIRED")
        if not candidate_id.strip():
            raise ValueError("CANDIDATE_ID_REQUIRED")
        if candidate_id == champion.champion_id:
            raise ValueError("CANDIDATE_EQUALS_CHAMPION")
        policy = policy or StatisticalPromotionPolicy()
        return _build_campaign(
            campaign_id=campaign_id,
            champion=champion,
            candidate_id=candidate_id,
            policy=policy,
            trials=(),
            verdict=None,
        )

    @staticmethod
    def observe(
        campaign: PromotionCampaign,
        trial: PairedTrial,
    ) -> PromotionCampaign:
        if campaign.status is not CampaignStatus.COLLECTING:
            raise ValueError("CAMPAIGN_NOT_COLLECTING")
        if trial.cohort_key in {existing.cohort_key for existing in campaign.trials}:
            raise ValueError("DUPLICATE_COHORT_IDENTITY")

        trials = tuple(
            sorted((*campaign.trials, trial), key=lambda item: item.cohort_key)
        )
        court = StatisticalPairedPromotionCourt(campaign.policy)
        verdict = court.evaluate(
            champion_id=campaign.champion_id,
            candidate_id=campaign.candidate_id,
            trials=trials,
        )
        return _build_campaign(
            campaign_id=campaign.campaign_id,
            champion=ChampionState(
                champion_id=campaign.champion_id,
                generation=campaign.champion_generation,
                history_digest=campaign.champion_history_digest,
            ),
            candidate_id=campaign.candidate_id,
            policy=campaign.policy,
            trials=trials,
            verdict=verdict,
        )

    @staticmethod
    def verify_current_champion(
        campaign: PromotionCampaign,
        current: ChampionState,
    ) -> None:
        if current.champion_id != campaign.champion_id:
            raise ValueError("CAMPAIGN_CHAMPION_CHANGED")
        if current.generation != campaign.champion_generation:
            raise ValueError("CAMPAIGN_GENERATION_CHANGED")
        if current.history_digest != campaign.champion_history_digest:
            raise ValueError("CAMPAIGN_HISTORY_CHANGED")

    @staticmethod
    def commit(
        campaign: PromotionCampaign,
        *,
        current: ChampionState,
        cohort_digest: str,
    ) -> PromotionCommit:
        PromotionCampaignController.verify_current_champion(campaign, current)
        if campaign.status is not CampaignStatus.PROMOTABLE:
            raise ValueError("CAMPAIGN_NOT_PROMOTABLE")

        verdict = StatisticalPairedPromotionCourt(campaign.policy).evaluate(
            champion_id=campaign.champion_id,
            candidate_id=campaign.candidate_id,
            trials=campaign.trials,
        )
        if verdict.decision is not SequentialDecision.PROMOTE:
            raise ValueError("CAMPAIGN_REPLAY_NOT_PROMOTABLE")
        if verdict.evidence_digest != campaign.verdict_digest:
            raise ValueError("CAMPAIGN_VERDICT_DIGEST_MISMATCH")

        state, record = ChampionRegistry.apply(
            current,
            verdict,
            cohort_digest=cohort_digest,
        )
        commit_payload = {
            "campaign_digest": campaign.campaign_digest,
            "cohort_digest": cohort_digest,
            "record_digest": record.record_digest,
            "history_digest": state.history_digest,
        }
        return PromotionCommit(
            campaign_digest=campaign.campaign_digest,
            cohort_digest=cohort_digest,
            record=record,
            state=state,
            commit_digest=_digest(commit_payload),
        )


def _build_campaign(
    *,
    campaign_id: str,
    champion: ChampionState,
    candidate_id: str,
    policy: StatisticalPromotionPolicy,
    trials: tuple[PairedTrial, ...],
    verdict: SequentialPromotionVerdict | None,
) -> PromotionCampaign:
    status = _status(verdict)
    payload = {
        "campaign_id": campaign_id,
        "champion_id": champion.champion_id,
        "champion_generation": champion.generation,
        "champion_history_digest": champion.history_digest,
        "candidate_id": candidate_id,
        "policy": asdict(policy),
        "trials": [asdict(trial) for trial in trials],
        "status": status.value,
        "verdict_digest": verdict.evidence_digest if verdict else None,
    }
    return PromotionCampaign(
        campaign_id=campaign_id,
        champion_id=champion.champion_id,
        champion_generation=champion.generation,
        champion_history_digest=champion.history_digest,
        candidate_id=candidate_id,
        policy=policy,
        trials=trials,
        status=status,
        verdict_digest=verdict.evidence_digest if verdict else None,
        campaign_digest=_digest(payload),
    )


def _status(verdict: SequentialPromotionVerdict | None) -> CampaignStatus:
    if verdict is None or verdict.decision is SequentialDecision.CONTINUE:
        return CampaignStatus.COLLECTING
    if verdict.decision is SequentialDecision.PROMOTE:
        return CampaignStatus.PROMOTABLE
    if verdict.decision is SequentialDecision.HOLD:
        return CampaignStatus.HELD
    return CampaignStatus.REFUSED
