"""PTD trial model, admission boundary, and falsification court."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable

from .metrics import (
    generative_leverage,
    knowledge_depreciation,
    knowledge_retention,
    ptd_advantage,
    ptd_efficiency,
    regeneration_advantage,
    strong_phase_regime,
)


@dataclass(frozen=True)
class PTDCriteria:
    """Experiment-declared success thresholds; never inferred after results."""

    max_knowledge_retention: float
    min_regeneration_advantage: float
    require_strong_phase_regime: bool = False


@dataclass(frozen=True)
class PhaseTrial:
    """One observable transition from a prior realization to a new realization."""

    trial_id: str
    from_phase: str
    to_phase: str
    semantic_admitted: bool
    prior_phase_attack_performance: float
    fresh_phase_attack_performance: float
    attacker_realign_cost: float
    defender_reconstruction_cost: float
    attacker_realignment_time: float
    phase_duration: float
    realization_distance: float
    common_mode_failure: bool = False
    persistent_authority_compromised: bool = False


def _validate_criteria(criteria: PTDCriteria) -> None:
    if criteria.max_knowledge_retention < 0:
        raise ValueError("max_knowledge_retention must be >= 0")
    if criteria.min_regeneration_advantage < 0:
        raise ValueError("min_regeneration_advantage must be >= 0")


def evaluate_trial(trial: PhaseTrial, criteria: PTDCriteria) -> dict[str, object]:
    """Evaluate one transition using only public, observable PTD quantities."""
    _validate_criteria(criteria)
    retention = knowledge_retention(
        trial.prior_phase_attack_performance,
        trial.fresh_phase_attack_performance,
    )
    depreciation = knowledge_depreciation(
        trial.prior_phase_attack_performance,
        trial.fresh_phase_attack_performance,
    )
    advantage = regeneration_advantage(
        trial.attacker_realign_cost,
        trial.defender_reconstruction_cost,
    )
    leverage = generative_leverage(
        trial.realization_distance,
        trial.defender_reconstruction_cost,
    )
    strong = strong_phase_regime(
        trial.attacker_realignment_time,
        trial.phase_duration,
    )

    falsifiers: list[str] = []
    if not trial.semantic_admitted:
        falsifiers.append("SEMANTIC_ADMISSION_FAILED")
    if retention > criteria.max_knowledge_retention:
        falsifiers.append("KNOWLEDGE_RETENTION_TOO_HIGH")
    if advantage < criteria.min_regeneration_advantage:
        falsifiers.append("REGENERATION_ADVANTAGE_TOO_LOW")
    if criteria.require_strong_phase_regime and not strong:
        falsifiers.append("ATTACKER_REALIGNS_WITHIN_PHASE")
    if trial.common_mode_failure:
        falsifiers.append("COMMON_MODE_FAILURE_PERSISTS")
    if trial.persistent_authority_compromised:
        falsifiers.append("PERSISTENT_AUTHORITY_COMPROMISED")

    metrics = {
        "knowledge_retention": retention,
        "knowledge_depreciation": depreciation,
        "regeneration_advantage": advantage,
        "generative_leverage": leverage,
        "ptd_efficiency": ptd_efficiency(
            depreciation,
            trial.defender_reconstruction_cost,
        ),
        "ptd_advantage": ptd_advantage(
            depreciation,
            trial.attacker_realign_cost,
            trial.defender_reconstruction_cost,
        ),
        "strong_phase_regime": strong,
    }
    return {
        "trial": asdict(trial),
        "criteria": asdict(criteria),
        "metrics": metrics,
        "falsifiers": falsifiers,
        "passed": not falsifiers,
    }


def summarize_trials(
    trials: Iterable[PhaseTrial],
    criteria: PTDCriteria,
) -> dict[str, object]:
    """Evaluate a cohort while keeping every negative result visible."""
    evaluations = [evaluate_trial(trial, criteria) for trial in trials]
    if not evaluations:
        raise ValueError("at least one phase trial is required")

    metric_rows = [row["metrics"] for row in evaluations]
    numeric_names = (
        "knowledge_retention",
        "knowledge_depreciation",
        "regeneration_advantage",
        "generative_leverage",
        "ptd_efficiency",
        "ptd_advantage",
    )
    means = {
        name: mean(float(row[name]) for row in metric_rows) for name in numeric_names
    }
    passed_count = sum(bool(row["passed"]) for row in evaluations)
    strong_count = sum(bool(row["strong_phase_regime"]) for row in metric_rows)
    return {
        "schema": "autofde-lab.ptd.summary/v1",
        "criteria": asdict(criteria),
        "trial_count": len(evaluations),
        "passed_count": passed_count,
        "failed_count": len(evaluations) - passed_count,
        "strong_phase_count": strong_count,
        "mean_metrics": means,
        "evaluations": evaluations,
    }
