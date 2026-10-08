"""The doctrine-lab world product: 5 axes x 3 values = 243 frozen worlds.

A world is a condition under which a strategy is evaluated. It projects onto the
existing Fortune-5 SAFe ``Scenario`` multipliers (``to_scenario``); it adds no new
dynamics to the engine. Results are relative to that simulation model only.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum

from autofde_lab.simulation.fortune5_safe.model import Scenario, ScenarioName


class Adaptation(str, Enum):
    STATIC = "static"
    LAGGED = "lagged"
    MIRROR = "mirror"


class InfoQuality(str, Enum):
    FULL = "full"
    NOISY = "noisy"
    DECEPTIVE = "deceptive"


class Coalition(str, Enum):
    SOLO = "solo"
    ALLIED = "allied"
    FRACTURING = "fracturing"


class Timing(str, Enum):
    EARLY = "early"
    MID = "mid"
    LATE = "late"


class Asymmetry(str, Enum):
    INFERIOR = "inferior"
    PARITY = "parity"
    SUPERIOR = "superior"


AXES: tuple[tuple[str, type[Enum]], ...] = (
    ("adaptation", Adaptation),
    ("info_quality", InfoQuality),
    ("coalition", Coalition),
    ("timing", Timing),
    ("asymmetry", Asymmetry),
)

# (demand, capacity, budget, dependency, compliance, reliability, coordination,
#  architecture, change_load) multiplicative/additive contributions per axis value.
_BASE = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)
_EFFECTS: dict[Enum, tuple[float, ...]] = {
    Adaptation.STATIC: _BASE,
    Adaptation.LAGGED: (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.03),
    Adaptation.MIRROR: (1.0, 1.0, 1.0, 1.05, 1.0, 1.0, 1.0, 1.0, 0.06),
    InfoQuality.FULL: _BASE,
    InfoQuality.NOISY: (1.0, 1.0, 1.0, 1.12, 1.0, 1.0, 1.05, 1.0, 0.0),
    InfoQuality.DECEPTIVE: (1.0, 1.0, 1.0, 1.30, 1.10, 0.92, 1.12, 1.0, 0.02),
    Coalition.SOLO: _BASE,
    Coalition.ALLIED: (1.0, 1.08, 1.0, 1.0, 1.0, 1.0, 1.10, 1.0, 0.0),
    Coalition.FRACTURING: (1.0, 0.94, 1.0, 1.15, 1.0, 1.0, 1.25, 1.0, 0.04),
    Timing.EARLY: (0.94, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.90, 0.0),
    Timing.MID: _BASE,
    Timing.LATE: (1.18, 1.0, 1.0, 1.0, 1.05, 1.0, 1.0, 1.15, 0.02),
    Asymmetry.INFERIOR: (1.0, 0.86, 0.86, 1.0, 1.0, 0.97, 1.0, 1.0, 0.0),
    Asymmetry.PARITY: _BASE,
    Asymmetry.SUPERIOR: (1.0, 1.12, 1.08, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0),
}


@dataclass(frozen=True)
class World:
    adaptation: Adaptation
    info_quality: InfoQuality
    coalition: Coalition
    timing: Timing
    asymmetry: Asymmetry

    @property
    def id(self) -> str:
        return "/".join(getattr(self, name).value for name, _ in AXES)

    def axis(self, name: str) -> str:
        return getattr(self, name).value

    def to_scenario(self) -> Scenario:
        """Project the world onto the existing fortune5_safe Scenario multipliers."""
        mult = [1.0] * 8
        change = 0.0
        for name, _ in AXES:
            effect = _EFFECTS[getattr(self, name)]
            for index in range(8):
                mult[index] *= effect[index]
            change += effect[8]
        return Scenario(
            ScenarioName.BASELINE,
            demand_multiplier=round(mult[0], 12),
            capacity_multiplier=round(mult[1], 12),
            budget_multiplier=round(mult[2], 12),
            dependency_multiplier=round(mult[3], 12),
            compliance_multiplier=round(mult[4], 12),
            reliability_multiplier=round(mult[5], 12),
            coordination_multiplier=round(mult[6], 12),
            architecture_multiplier=round(mult[7], 12),
            change_load=round(change, 12),
        )


ALL_WORLDS: tuple[World, ...] = tuple(
    World(*values)
    for values in itertools.product(
        Adaptation, InfoQuality, Coalition, Timing, Asymmetry
    )
)


def world_by_id(world_id: str) -> World:
    parts = world_id.split("/")
    if len(parts) != len(AXES):
        raise ValueError(f"world id must have {len(AXES)} axes: {world_id!r}")
    return World(*(enum(value) for (_, enum), value in zip(AXES, parts)))
