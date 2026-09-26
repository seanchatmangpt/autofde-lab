"""Deterministic world sampling beyond the 10 fixed Fortune-5 disruption scenarios.

`WorldSample` carries the same nine multipliers as `Scenario` PLUS four new
strategic axes the fixed scenarios cannot express:

- `information_quality` in [0.60, 1.00] — how much decision-grade information
  the enterprise has (scales predictability in the engine).
- `authority_concentration` in [0.50, 2.00] — how concentrated decision
  authority is (scales coordination overhead in the engine).
- `volatility` in [0.00, 0.25] — half-width of an extra per-PI demand noise
  term (zero means no extra noise and no extra RNG draw).
- `timing_jitter` in [0.00, 0.10] — extra half-width added to the per-PI
  execution jitter band (zero reproduces the engine's default band).

`sample_worlds(seed, n)` is deterministic: the same seed yields byte-identical
worlds in the same order (sha256-seeded `random.Random`, drawn in field
declaration order). `WorldSample` is frozen, hashable, and digestable via the
repo's `stable_digest` idiom; `world_id` is content-addressed from the
multipliers alone, so identical worlds share one id regardless of sampler.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from functools import cached_property

from .model import stable_digest

#: Documented sampling ranges, field order == draw order (deterministic).
WORLD_RANGES: dict[str, tuple[float, float]] = {
    "demand_multiplier": (0.70, 1.40),
    "capacity_multiplier": (0.70, 1.15),
    "budget_multiplier": (0.75, 1.10),
    "dependency_multiplier": (0.80, 2.00),
    "compliance_multiplier": (0.80, 1.80),
    "reliability_multiplier": (0.70, 1.05),
    "coordination_multiplier": (0.80, 1.40),
    "architecture_multiplier": (0.80, 1.30),
    "change_load": (0.00, 0.18),
    "information_quality": (0.60, 1.00),
    "authority_concentration": (0.50, 2.00),
    "volatility": (0.00, 0.25),
    "timing_jitter": (0.00, 0.10),
}


@dataclass(frozen=True)
class WorldSample:
    """A sampled disruption world: Scenario multipliers plus four new axes.

    Field order mirrors `Scenario` first (same names, same defaults) so the
    engine can consume either kind through one duck-typed fast path, then the
    new strategic axes. Ranges are enforced by `sample_worlds`; direct
    construction is allowed for hand-rigged boundary probes (tests use this).
    """

    demand_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    budget_multiplier: float = 1.0
    dependency_multiplier: float = 1.0
    compliance_multiplier: float = 1.0
    reliability_multiplier: float = 1.0
    coordination_multiplier: float = 1.0
    architecture_multiplier: float = 1.0
    change_load: float = 0.0
    information_quality: float = 1.0
    authority_concentration: float = 1.0
    volatility: float = 0.0
    timing_jitter: float = 0.0

    @cached_property
    def digest(self) -> str:
        return stable_digest(self)

    @cached_property
    def world_id(self) -> str:
        """Content-addressed identity: identical multipliers => identical id."""
        return f"world-{self.digest[:12]}"


def sample_worlds(seed: int, n: int) -> list[WorldSample]:
    """Draw `n` worlds deterministically from `seed`.

    Same seed => byte-identical world list (the RNG is sha256-seeded from the
    seed alone, and each world draws exactly `len(WORLD_RANGES)` uniforms in
    `WORLD_RANGES` key order). Values are drawn uniformly in the documented
    closed ranges. `n` must be non-negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    material = f"autofde-lab/worldgen/v1|{seed}".encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], "big"))
    worlds: list[WorldSample] = []
    for _ in range(n):
        values = {
            field: rng.uniform(low, high)
            for field, (low, high) in WORLD_RANGES.items()
        }
        worlds.append(WorldSample(**values))
    return worlds
