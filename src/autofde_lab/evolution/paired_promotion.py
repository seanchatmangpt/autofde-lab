"""RACaP-style paired promotion and cognition-retirement courts.

The paper boundary is preserved here: candidates are powerless artifacts. This
module compares evidence and manufactures deterministic verdicts; it never grants
execution authority and never performs consequential DO.

PairedPromotionCourt compares champion and candidate on identical task/seed/budget
identities and refuses malformed cohorts. ReasoningRetirementCourt admits
replacement of a higher-intelligence execution route only when a lower rung
reproduces accepted behavior on a bounded cohort without success regression.

The output digests are replay identities, not authority tokens.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _require_nonempty(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name.upper()}_REQUIRED")


@dataclass(frozen=True, slots=True)
class PairedTrial:
    """One champion/candidate comparison under exactly one cohort identity."""

    task_id: str
    seed: int
    budget_id: str
    champion_score: float
    candidate_score: float
    champion_evidence_digest: str
    candidate_evidence_digest: str

    def __post_init__(self) -> None:
        _require_nonempty("task_id", self.task_id)
        _require_nonempty("budget_id", self.budget_id)
        _require_nonempty("champion_evidence_digest", self.champion_evidence_digest)
        _require_nonempty("candidate_evidence_digest", self.candidate_evidence_digest)
        if not isfinite(self.champion_score) or not isfinite(self.candidate_score):
            raise ValueError("NON_FINITE_SCORE")

    @property
    def cohort_key(self) -> tuple[str, int, str]:
        return (self.task_id, self.seed, self.budget_id)

    @property
    def delta(self) -> float:
        return self.candidate_score - self.champion_score


@dataclass(frozen=True, slots=True)
class PairedPromotionPolicy:
    """Explicit promotion bounds with visible regression tolerance."""

    minimum_trials: int = 1
    minimum_total_delta: float = 0.0
    max_single_trial_regression: float = 0.0

    def __post_init__(self) -> None:
        if self.minimum_trials < 1:
            raise ValueError("MINIMUM_TRIALS_MUST_BE_POSITIVE")
        if self.max_single_trial_regression < 0:
            raise ValueError("MAX_REGRESSION_MUST_BE_NONNEGATIVE")


class PromotionDecision(StrEnum):
    PROMOTE = "PROMOTE"
    HOLD = "HOLD"
    REFUSE = "REFUSE"


@dataclass(frozen=True, slots=True)
class PromotionVerdict:
    decision: PromotionDecision
    champion_id: str
    candidate_id: str
    trial_count: int
    total_delta: float
    worst_delta: float
    regression_count: int
    reasons: tuple[str, ...]
    evidence_digest: str
    authority: str = "none"


class PairedPromotionCourt:
    """Evaluate a powerless candidate against the current champion."""

    def __init__(self, policy: PairedPromotionPolicy | None = None) -> None:
        self.policy = policy or PairedPromotionPolicy()

    def evaluate(
        self,
        *,
        champion_id: str,
        candidate_id: str,
        trials: Iterable[PairedTrial],
    ) -> PromotionVerdict:
        _require_nonempty("champion_id", champion_id)
        _require_nonempty("candidate_id", candidate_id)
        cohort = tuple(trials)

        reasons: list[str] = []
        if champion_id == candidate_id:
            reasons.append("CANDIDATE_EQUALS_CHAMPION")
        if len(cohort) < self.policy.minimum_trials:
            reasons.append("INSUFFICIENT_PAIRED_TRIALS")

        keys = [trial.cohort_key for trial in cohort]
        if len(keys) != len(set(keys)):
            reasons.append("DUPLICATE_COHORT_IDENTITY")

        total_delta = sum(trial.delta for trial in cohort)
        worst_delta = min((trial.delta for trial in cohort), default=0.0)
        regression_count = sum(1 for trial in cohort if trial.delta < 0)

        if reasons:
            decision = PromotionDecision.REFUSE
        elif worst_delta < -self.policy.max_single_trial_regression:
            decision = PromotionDecision.HOLD
            reasons.append("REGRESSION_BOUND_EXCEEDED")
        elif total_delta <= self.policy.minimum_total_delta:
            decision = PromotionDecision.HOLD
            reasons.append("INSUFFICIENT_NET_GAIN")
        else:
            decision = PromotionDecision.PROMOTE
            reasons.append("PAIRED_PROMOTION_CONFORMS")

        evidence = {
            "champion_id": champion_id,
            "candidate_id": candidate_id,
            "policy": asdict(self.policy),
            "trials": [asdict(trial) for trial in cohort],
            "decision": decision.value,
            "reasons": reasons,
        }
        return PromotionVerdict(
            decision=decision,
            champion_id=champion_id,
            candidate_id=candidate_id,
            trial_count=len(cohort),
            total_delta=total_delta,
            worst_delta=worst_delta,
            regression_count=regression_count,
            reasons=tuple(reasons),
            evidence_digest=_digest(evidence),
        )


class IntelligenceRung(IntEnum):
    """Lower values are preferred once equivalent behavior is witnessed."""

    REUSE = 1
    COMPOSE = 2
    RULE = 3
    PLAN = 4
    CONSTRAINT = 5
    GENERATOR = 6
    SPECIALIZED_MODEL = 7
    GENERAL_LLM = 8


@dataclass(frozen=True, slots=True)
class RetirementTrial:
    """One identical-input comparison of incumbent and compiled replacement."""

    input_id: str
    incumbent_output_digest: str
    candidate_output_digest: str
    incumbent_success: bool
    candidate_success: bool
    incumbent_cost: float = 0.0
    candidate_cost: float = 0.0

    def __post_init__(self) -> None:
        _require_nonempty("input_id", self.input_id)
        _require_nonempty("incumbent_output_digest", self.incumbent_output_digest)
        _require_nonempty("candidate_output_digest", self.candidate_output_digest)
        if self.incumbent_cost < 0 or self.candidate_cost < 0:
            raise ValueError("NEGATIVE_COST")


class RetirementDecision(StrEnum):
    RETIRE_INCUMBENT = "RETIRE_INCUMBENT"
    KEEP_INCUMBENT = "KEEP_INCUMBENT"
    REFUSE = "REFUSE"


@dataclass(frozen=True, slots=True)
class RetirementVerdict:
    decision: RetirementDecision
    incumbent_rung: IntelligenceRung
    candidate_rung: IntelligenceRung
    trial_count: int
    exact_match_count: int
    success_regressions: int
    incumbent_cost: float
    candidate_cost: float
    reasons: tuple[str, ...]
    evidence_digest: str
    authority: str = "none"


class ReasoningRetirementCourt:
    """Admit lower-intelligence replacement for recurring reasoning."""

    def __init__(self, *, minimum_trials: int = 3) -> None:
        if minimum_trials < 1:
            raise ValueError("MINIMUM_TRIALS_MUST_BE_POSITIVE")
        self.minimum_trials = minimum_trials

    def evaluate(
        self,
        *,
        incumbent_rung: IntelligenceRung,
        candidate_rung: IntelligenceRung,
        trials: Iterable[RetirementTrial],
    ) -> RetirementVerdict:
        cohort = tuple(trials)
        reasons: list[str] = []

        if candidate_rung >= incumbent_rung:
            reasons.append("CANDIDATE_NOT_LOWER_INTELLIGENCE")
        if len(cohort) < self.minimum_trials:
            reasons.append("INSUFFICIENT_RETIREMENT_TRIALS")

        ids = [trial.input_id for trial in cohort]
        if len(ids) != len(set(ids)):
            reasons.append("DUPLICATE_INPUT_IDENTITY")

        success_regressions = sum(
            1
            for trial in cohort
            if trial.incumbent_success and not trial.candidate_success
        )
        exact_match_count = sum(
            1
            for trial in cohort
            if (
                trial.incumbent_success
                and trial.candidate_success
                and trial.incumbent_output_digest == trial.candidate_output_digest
            )
        )
        incumbent_successes = sum(1 for trial in cohort if trial.incumbent_success)
        incumbent_cost = sum(trial.incumbent_cost for trial in cohort)
        candidate_cost = sum(trial.candidate_cost for trial in cohort)

        if reasons:
            decision = RetirementDecision.REFUSE
        elif success_regressions:
            decision = RetirementDecision.KEEP_INCUMBENT
            reasons.append("SUCCESS_REGRESSION")
        elif exact_match_count != incumbent_successes:
            decision = RetirementDecision.KEEP_INCUMBENT
            reasons.append("OUTPUT_SEMANTICS_CHANGED")
        else:
            decision = RetirementDecision.RETIRE_INCUMBENT
            reasons.append("LOWER_INTELLIGENCE_ROUTE_CONFORMS")

        evidence = {
            "incumbent_rung": int(incumbent_rung),
            "candidate_rung": int(candidate_rung),
            "minimum_trials": self.minimum_trials,
            "trials": [asdict(trial) for trial in cohort],
            "decision": decision.value,
            "reasons": reasons,
        }
        return RetirementVerdict(
            decision=decision,
            incumbent_rung=incumbent_rung,
            candidate_rung=candidate_rung,
            trial_count=len(cohort),
            exact_match_count=exact_match_count,
            success_regressions=success_regressions,
            incumbent_cost=incumbent_cost,
            candidate_cost=candidate_cost,
            reasons=tuple(reasons),
            evidence_digest=_digest(evidence),
        )
