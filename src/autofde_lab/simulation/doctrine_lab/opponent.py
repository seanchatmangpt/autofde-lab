"""Deterministic adaptive opponent over the fortune5_safe Scenario.

The opponent adapts after round ``k`` (static: never, lagged: k=2, mirror: k=1)
by raising the Scenario multiplier that counters what it observed of our policy.
Observation quality follows the world's info_quality axis and our own
concealment. Its rng is seeded from sha256(seed | strategy signature | world id):
the strategy enters by its operational identity (primitive composition), so two
catalog entries with identical compositions face an identical opponent.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, replace

from autofde_lab.simulation.fortune5_safe.model import (
    ArchitectureRule,
    CadenceRule,
    CapacityRule,
    FundingRule,
    PolicyVector,
    PriorityRule,
    RiskRule,
    Scenario,
)

from .world import Adaptation, Coalition, InfoQuality, World

ADAPT_AFTER: dict[Adaptation, int | None] = {
    Adaptation.STATIC: None,
    Adaptation.LAGGED: 2,
    Adaptation.MIRROR: 1,
}

# policy value -> (scenario field the opponent pushes, direction)
_COUNTERS: dict[object, tuple[str, int]] = {
    CapacityRule.FLOW_FIRST: ("dependency_multiplier", 1),
    CapacityRule.RELIABILITY_RESERVE: ("demand_multiplier", 1),
    CapacityRule.INNOVATION_RESERVE: ("demand_multiplier", 1),
    PriorityRule.COST_OF_DELAY: ("change_load", 1),
    PriorityRule.DEPENDENCY_FIRST: ("coordination_multiplier", 1),
    FundingRule.DYNAMIC_CAPACITY: ("budget_multiplier", -1),
    FundingRule.OPTION_RESERVE: ("demand_multiplier", 1),
    CadenceRule.SYNCHRONIZED: ("coordination_multiplier", 1),
    ArchitectureRule.PLATFORM_FIRST: ("architecture_multiplier", 1),
    ArchitectureRule.RUNWAY_FIRST: ("architecture_multiplier", 1),
    RiskRule.FAST_FEEDBACK: ("compliance_multiplier", 1),
}
_ALL_TARGETS: tuple[tuple[str, int], ...] = tuple(sorted(set(_COUNTERS.values())))
_MISREAD = {InfoQuality.FULL: 0.0, InfoQuality.NOISY: 0.35, InfoQuality.DECEPTIVE: 0.6}
_COALITION_GAIN = {
    Coalition.SOLO: 1.0,
    Coalition.ALLIED: 0.85,
    Coalition.FRACTURING: 1.2,
}


@dataclass(frozen=True)
class OpponentMove:
    round: int
    adapted: bool
    target: str | None
    delta: float


def opponent_rng(seed: int, strategy_signature: str, world: World) -> random.Random:
    material = f"{seed}|{strategy_signature}|{world.id}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], "big"))


class Opponent:
    def __init__(
        self, seed: int, strategy_signature: str, world: World, *, concealed: bool
    ) -> None:
        self.world = world
        self.concealed = concealed
        self.after = ADAPT_AFTER[world.adaptation]
        self.rng = opponent_rng(seed, strategy_signature, world)

    def respond(
        self, round_index: int, policy: PolicyVector, scenario: Scenario
    ) -> tuple[Scenario, OpponentMove]:
        # draw every round so the stream position is round-indexed, not branch-indexed
        misread_draw = self.rng.random()
        pick_draw = self.rng.random()
        strength_draw = self.rng.random()
        if self.after is None or round_index <= self.after:
            return scenario, OpponentMove(round_index, False, None, 0.0)
        misread = _MISREAD[self.world.info_quality]
        strength = 0.08 * (0.75 + 0.5 * strength_draw)
        strength *= _COALITION_GAIN[self.world.coalition]
        if self.world.adaptation is Adaptation.MIRROR:
            strength *= 1.25
        if self.concealed:
            misread = 1.0 - (1.0 - misread) * 0.5
            strength *= 0.5
        observed = tuple(
            _COUNTERS[value]
            for value in (
                policy.priority,
                policy.funding,
                policy.capacity,
                policy.cadence,
                policy.architecture,
                policy.risk,
            )
            if value in _COUNTERS
        )
        pool = _ALL_TARGETS if (misread_draw < misread or not observed) else observed
        field, direction = pool[int(pick_draw * len(pool)) % len(pool)]
        current = getattr(scenario, field)
        if field == "change_load":
            updated = min(0.18, current + strength * 0.5)
        else:
            updated = max(0.5, current * (1.0 + direction * strength))
        delta = round(updated - current, 12)
        return (
            replace(scenario, **{field: round(updated, 12)}),
            OpponentMove(round_index, True, field, delta),
        )
