"""Generation-bound champion state for replayable candidate promotion.

A court verdict is evidence about champion X versus candidate Y. It is not valid
against a later champion merely because Y still exists. This module binds
promotion to the exact current champion generation and hash-chains the resulting
history. It performs no deployment or consequential actuation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class PromotionVerdictLike(Protocol):
    champion_id: str
    candidate_id: str
    evidence_digest: str
    decision: object


@dataclass(frozen=True, slots=True)
class ChampionState:
    champion_id: str
    generation: int
    history_digest: str
    authority: str = "none"


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    generation_before: int
    generation_after: int
    champion_before: str
    champion_after: str
    verdict_digest: str
    cohort_digest: str
    predecessor_history_digest: str
    record_digest: str
    history_digest: str
    authority: str = "none"


class ChampionRegistry:
    """Pure state transition for applying already-admitted promotion evidence."""

    @staticmethod
    def initialize(champion_id: str) -> ChampionState:
        if not champion_id.strip():
            raise ValueError("CHAMPION_ID_REQUIRED")
        genesis = _digest({"champion_id": champion_id, "generation": 0})
        return ChampionState(
            champion_id=champion_id,
            generation=0,
            history_digest=genesis,
        )

    @staticmethod
    def apply(
        state: ChampionState,
        verdict: PromotionVerdictLike,
        *,
        cohort_digest: str,
    ) -> tuple[ChampionState, PromotionRecord]:
        if _decision_value(verdict.decision) != "PROMOTE":
            raise ValueError("PROMOTION_VERDICT_NOT_ADMITTED")
        if verdict.champion_id != state.champion_id:
            raise ValueError("STALE_CHAMPION_VERDICT")
        if verdict.candidate_id == state.champion_id:
            raise ValueError("CANDIDATE_EQUALS_CHAMPION")
        if not cohort_digest.strip():
            raise ValueError("COHORT_DIGEST_REQUIRED")
        if not verdict.evidence_digest.strip():
            raise ValueError("VERDICT_DIGEST_REQUIRED")

        generation_after = state.generation + 1
        record_payload = {
            "generation_before": state.generation,
            "generation_after": generation_after,
            "champion_before": state.champion_id,
            "champion_after": verdict.candidate_id,
            "verdict_digest": verdict.evidence_digest,
            "cohort_digest": cohort_digest,
            "predecessor_history_digest": state.history_digest,
        }
        record_digest = _digest(record_payload)
        history_digest = _digest(
            {
                "predecessor": state.history_digest,
                "record_digest": record_digest,
            }
        )

        record = PromotionRecord(
            generation_before=state.generation,
            generation_after=generation_after,
            champion_before=state.champion_id,
            champion_after=verdict.candidate_id,
            verdict_digest=verdict.evidence_digest,
            cohort_digest=cohort_digest,
            predecessor_history_digest=state.history_digest,
            record_digest=record_digest,
            history_digest=history_digest,
        )
        next_state = ChampionState(
            champion_id=verdict.candidate_id,
            generation=generation_after,
            history_digest=history_digest,
        )
        return next_state, record

    @staticmethod
    def replay(
        initial: ChampionState,
        records: tuple[PromotionRecord, ...],
    ) -> ChampionState:
        state = initial
        for record in records:
            if record.generation_before != state.generation:
                raise ValueError("PROMOTION_GENERATION_DISCONTINUITY")
            if record.champion_before != state.champion_id:
                raise ValueError("PROMOTION_CHAMPION_DISCONTINUITY")
            if record.predecessor_history_digest != state.history_digest:
                raise ValueError("PROMOTION_HISTORY_PREDECESSOR_MISMATCH")

            expected_payload = {
                "generation_before": record.generation_before,
                "generation_after": record.generation_after,
                "champion_before": record.champion_before,
                "champion_after": record.champion_after,
                "verdict_digest": record.verdict_digest,
                "cohort_digest": record.cohort_digest,
                "predecessor_history_digest": record.predecessor_history_digest,
            }
            expected_record_digest = _digest(expected_payload)
            if expected_record_digest != record.record_digest:
                raise ValueError("PROMOTION_RECORD_DIGEST_MISMATCH")

            expected_history = _digest(
                {
                    "predecessor": state.history_digest,
                    "record_digest": record.record_digest,
                }
            )
            if expected_history != record.history_digest:
                raise ValueError("PROMOTION_HISTORY_DIGEST_MISMATCH")

            if record.generation_after != record.generation_before + 1:
                raise ValueError("PROMOTION_GENERATION_STEP_INVALID")

            state = ChampionState(
                champion_id=record.champion_after,
                generation=record.generation_after,
                history_digest=record.history_digest,
            )

        return state


def _decision_value(decision: object) -> str:
    value = getattr(decision, "value", decision)
    return str(value)
