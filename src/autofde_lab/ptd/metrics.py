"""Observable Phasing Target Defense metrics.

The realization constructor is intentionally opaque. Metrics require only measured
attack performance, costs, time, and a declared realization-distance function.
"""

from __future__ import annotations

import math


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _positive_finite(name: str, value: float) -> float:
    value = _nonnegative_finite(name, value)
    if value == 0:
        raise ValueError(f"{name} must be > 0")
    return value


def knowledge_retention(
    prior_phase_performance: float,
    fresh_phase_performance: float,
) -> float:
    """Cross-phase attack-knowledge transfer using a fresh-phase baseline."""
    prior = _nonnegative_finite("prior_phase_performance", prior_phase_performance)
    fresh = _positive_finite("fresh_phase_performance", fresh_phase_performance)
    return prior / fresh


def knowledge_depreciation(
    prior_phase_performance: float,
    fresh_phase_performance: float,
) -> float:
    """One minus cross-phase knowledge retention; negative results are preserved."""
    return 1.0 - knowledge_retention(
        prior_phase_performance,
        fresh_phase_performance,
    )


def regeneration_advantage(
    attacker_realign_cost: float,
    defender_reconstruction_cost: float,
) -> float:
    """Attacker cost to restore capability divided by defender reconstruction cost."""
    attacker = _nonnegative_finite("attacker_realign_cost", attacker_realign_cost)
    defender = _positive_finite(
        "defender_reconstruction_cost",
        defender_reconstruction_cost,
    )
    return attacker / defender


def generative_leverage(
    realization_distance: float,
    defender_reconstruction_cost: float,
) -> float:
    """Meaningful realization distance produced per unit defender cost."""
    distance = _nonnegative_finite("realization_distance", realization_distance)
    defender = _positive_finite(
        "defender_reconstruction_cost",
        defender_reconstruction_cost,
    )
    return distance / defender


def ptd_efficiency(
    attacker_knowledge_depreciation: float,
    defender_reconstruction_cost: float,
) -> float:
    """Knowledge depreciation per unit defender reconstruction cost."""
    depreciation = float(attacker_knowledge_depreciation)
    if not math.isfinite(depreciation):
        raise ValueError("attacker_knowledge_depreciation must be finite")
    defender = _positive_finite(
        "defender_reconstruction_cost",
        defender_reconstruction_cost,
    )
    return depreciation / defender


def ptd_advantage(
    attacker_knowledge_depreciation: float,
    attacker_realign_cost: float,
    defender_reconstruction_cost: float,
) -> float:
    """Knowledge depreciation weighted by regeneration advantage."""
    return attacker_knowledge_depreciation * regeneration_advantage(
        attacker_realign_cost,
        defender_reconstruction_cost,
    )


def strong_phase_regime(
    attacker_realignment_time: float,
    phase_duration: float,
) -> bool:
    """Whether attacker realignment takes longer than the phase remains current."""
    attacker = _nonnegative_finite(
        "attacker_realignment_time",
        attacker_realignment_time,
    )
    phase = _positive_finite("phase_duration", phase_duration)
    return attacker > phase
