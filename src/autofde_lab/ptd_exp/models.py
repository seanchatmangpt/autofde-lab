"""Typed PTD observations; numeric fields are validated at construction so NaN or
negative values can never reach a metric."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _finite(name: str, value: float, *, positive: bool = False) -> None:
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be finite and {'> 0' if positive else '>= 0'}")


@dataclass(frozen=True)
class EpochObservation:
    """One realization epoch of one exact subject.

    ``surface`` is the attacker-facing representation, ``critical`` the subset whose
    persistence is disqualifying, ``nondeterministic`` the surface facts that vary
    legitimately run to run (reported, never silently compared).
    """

    subject_id: str
    epoch_id: str
    semantic_digest: str
    realization_digest: str
    defender_cost: float
    phase_duration: float
    authority_id: str = "authority:unset"
    admitted: bool = True
    authority_compromised: bool = False
    surface: frozenset = field(default_factory=frozenset)
    critical: frozenset = field(default_factory=frozenset)
    nondeterministic: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        _finite("defender_cost", self.defender_cost, positive=True)
        _finite("phase_duration", self.phase_duration, positive=True)
        if not self.critical <= self.surface:
            raise ValueError("critical facts must be a subset of the surface")

    @property
    def stable_surface(self) -> frozenset:
        return self.surface - self.nondeterministic


@dataclass(frozen=True)
class AttackObservation:
    """Measured attacker performance of source-epoch knowledge against a target epoch."""

    task_id: str
    source_epoch: str
    target_epoch: str
    stale_performance: float
    fresh_performance: float
    realignment_cost: float
    realignment_time: float
    stale_facts: frozenset = field(default_factory=frozenset)
    predicted_surface: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        _finite("stale_performance", self.stale_performance)
        _finite("fresh_performance", self.fresh_performance, positive=True)
        _finite("realignment_cost", self.realignment_cost)
        _finite("realignment_time", self.realignment_time)


@dataclass(frozen=True)
class PTDThresholds:
    """Declared before results are seen; never inferred afterwards."""

    max_retention: float = 0.5
    min_regeneration_advantage: float = 1.0
    require_temporal_advantage: bool = False
    max_common_mode: float = 0.5
    max_fact_disagreement: float = 0.5
    budget: float | None = None
