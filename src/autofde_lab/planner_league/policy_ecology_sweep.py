"""Bounded cue sweeps over conditioned policy ecologies.

Reaction norms are only meaningful across environmental cues. This module
manufactures the reversible candidate schedule for those sweeps and reduces
receipted outcomes into a response surface. It does not execute matches.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import fsum

from .policy_ecology import PolicyEcology
from .policy_ecology_experiment import (
    EcologyMatch,
    EcologySchedule,
    ObservedEcologyOutcome,
    manufacture_ecology_schedule,
)


@dataclass(frozen=True, slots=True)
class CueSweepSpec:
    cues: tuple[float, ...]
    max_matches_per_cue: int = 4096

    def __post_init__(self) -> None:
        if not self.cues:
            raise ValueError("REFUSED:CUE_SWEEP_REQUIRES_CUE")
        if len(self.cues) != len(set(self.cues)):
            raise ValueError("REFUSED:DUPLICATE_CUE")
        if self.max_matches_per_cue < 1:
            raise ValueError("REFUSED:MAX_MATCHES_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class CueSweep:
    spec: CueSweepSpec
    schedules: tuple[EcologySchedule, ...]
    total_cardinality: int
    scheduled_matches: int
    truncated: bool

    def __post_init__(self) -> None:
        if len(self.schedules) != len(self.spec.cues):
            raise ValueError("REFUSED:CUE_SWEEP_SCHEDULE_CARDINALITY")


def manufacture_cue_sweep(
    left: PolicyEcology,
    right: PolicyEcology,
    *,
    world_id: str,
    left_role_id: str,
    right_role_id: str,
    spec: CueSweepSpec,
) -> CueSweep:
    schedules = tuple(
        manufacture_ecology_schedule(
            left,
            right,
            world_id=world_id,
            left_role_id=left_role_id,
            right_role_id=right_role_id,
            max_matches=spec.max_matches_per_cue,
            cue=cue,
        )
        for cue in spec.cues
    )
    return CueSweep(
        spec=spec,
        schedules=schedules,
        total_cardinality=sum(schedule.total_cardinality for schedule in schedules),
        scheduled_matches=sum(len(schedule.matches) for schedule in schedules),
        truncated=any(schedule.truncated for schedule in schedules),
    )


@dataclass(frozen=True, slots=True)
class CueResponsePoint:
    cue: float
    observation_count: int
    mean_left_score: float
    mean_right_score: float
    mean_margin: float


@dataclass(frozen=True, slots=True)
class CueResponseSurface:
    points: tuple[CueResponsePoint, ...]

    def __post_init__(self) -> None:
        cues = [point.cue for point in self.points]
        if len(cues) != len(set(cues)):
            raise ValueError("REFUSED:DUPLICATE_CUE_RESPONSE_POINT")

    @property
    def max_abs_margin_slope(self) -> float:
        if len(self.points) < 2:
            return 0.0
        ordered = sorted(self.points, key=lambda point: point.cue)
        slopes: list[float] = []
        for left, right in zip(ordered, ordered[1:], strict=True):
            delta_cue = right.cue - left.cue
            if delta_cue == 0.0:
                continue
            slopes.append(abs((right.mean_margin - left.mean_margin) / delta_cue))
        return max(slopes, default=0.0)


def _cue_from_match(match: EcologyMatch) -> float:
    if match.cue is None:
        raise ValueError("REFUSED:CUE_RESPONSE_REQUIRES_CONDITIONED_MATCH")
    return match.cue


def build_cue_response_surface(
    observations: Iterable[ObservedEcologyOutcome],
) -> CueResponseSurface:
    grouped: dict[float, list[ObservedEcologyOutcome]] = {}
    for observation in observations:
        if not isinstance(observation, ObservedEcologyOutcome):
            raise TypeError(
                "REFUSED:CUE_RESPONSE_REQUIRES_OBSERVED_OUTCOME:"
                f"{type(observation).__name__}"
            )
        cue = _cue_from_match(observation.match)
        grouped.setdefault(cue, []).append(observation)

    if not grouped:
        raise ValueError("REFUSED:CUE_RESPONSE_REQUIRES_OBSERVATION")

    points: list[CueResponsePoint] = []
    for cue, rows in sorted(grouped.items()):
        left_scores = [row.left_score for row in rows]
        right_scores = [row.right_score for row in rows]
        mean_left = fsum(left_scores) / len(left_scores)
        mean_right = fsum(right_scores) / len(right_scores)
        points.append(
            CueResponsePoint(
                cue=cue,
                observation_count=len(rows),
                mean_left_score=mean_left,
                mean_right_score=mean_right,
                mean_margin=mean_left - mean_right,
            )
        )
    return CueResponseSurface(points=tuple(points))
