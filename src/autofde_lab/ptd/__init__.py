"""Phasing Target Defense public experimental surface."""

from .metrics import (
    generative_leverage,
    knowledge_depreciation,
    knowledge_retention,
    ptd_advantage,
    ptd_efficiency,
    regeneration_advantage,
    strong_phase_regime,
)
from .model import PhaseTrial, PTDCriteria, evaluate_trial, summarize_trials

__all__ = [
    "PTDCriteria",
    "PhaseTrial",
    "evaluate_trial",
    "generative_leverage",
    "knowledge_depreciation",
    "knowledge_retention",
    "ptd_advantage",
    "ptd_efficiency",
    "regeneration_advantage",
    "strong_phase_regime",
    "summarize_trials",
]
