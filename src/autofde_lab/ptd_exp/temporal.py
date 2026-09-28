"""Temporal regime; the strong-phase predicate is the canonical one in ``autofde_lab.ptd.metrics``."""
from autofde_lab.ptd.metrics import strong_phase_regime as strong_temporal_regime

__all__ = ["strong_temporal_regime", "temporal_advantage"]


def temporal_advantage(realignment_time: float, phase_duration: float) -> float:
    if phase_duration <= 0:
        raise ValueError("phase duration must be > 0")
    return realignment_time / phase_duration
