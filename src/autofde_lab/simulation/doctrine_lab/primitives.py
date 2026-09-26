"""The 14 sd: primitive operators as deterministic PolicyVector deltas.

Each operator sets exactly one PolicyVector field to one value. A strategy is an
ordered tuple of operators folded left over ``BASE_POLICY``; later operators
overwrite earlier ones on the same field, which is how distinct compositions can
collide on one policy (reported as primitive-equivalence collisions).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence

from autofde_lab.simulation.fortune5_safe.model import (
    ArchitectureRule,
    CadenceRule,
    CapacityRule,
    FundingRule,
    PolicyVector,
    PriorityRule,
    RiskRule,
)

BASE_POLICY = PolicyVector(
    PriorityRule.WSJF,
    FundingRule.PROPORTIONAL_VALUE,
    CapacityRule.BALANCED,
    CadenceRule.SYNCHRONIZED,
    ArchitectureRule.JUST_IN_TIME,
    RiskRule.BALANCED,
)


@dataclass(frozen=True)
class Primitive:
    name: str
    dual: str | None
    field: str
    value: Enum

    def apply(self, policy: PolicyVector) -> PolicyVector:
        return replace(policy, **{self.field: self.value})


PRIMITIVES: dict[str, Primitive] = {
    p.name: p
    for p in (
        Primitive("shape", None, "architecture", ArchitectureRule.PLATFORM_FIRST),
        Primitive("probe", None, "risk", RiskRule.FAST_FEEDBACK),
        Primitive("conceal", "reveal", "cadence", CadenceRule.STAGGERED),
        Primitive("reveal", "conceal", "cadence", CadenceRule.SYNCHRONIZED),
        Primitive("concentrate", "disperse", "capacity", CapacityRule.FLOW_FIRST),
        Primitive("disperse", "concentrate", "capacity", CapacityRule.BALANCED),
        Primitive("delay", "accelerate", "funding", FundingRule.OPTION_RESERVE),
        Primitive("accelerate", "delay", "priority", PriorityRule.COST_OF_DELAY),
        Primitive("commit", "withdraw", "funding", FundingRule.DYNAMIC_CAPACITY),
        Primitive("withdraw", "commit", "capacity", CapacityRule.RELIABILITY_RESERVE),
        Primitive("divide", "combine", "priority", PriorityRule.DEPENDENCY_FIRST),
        Primitive("combine", "divide", "architecture", ArchitectureRule.RUNWAY_FIRST),
        Primitive("substitute", None, "architecture", ArchitectureRule.JUST_IN_TIME),
        Primitive("transform", None, "capacity", CapacityRule.INNOVATION_RESERVE),
    )
}

PRIMITIVE_NAMES: tuple[str, ...] = tuple(PRIMITIVES)
DUALS: tuple[tuple[str, str], ...] = (
    ("conceal", "reveal"),
    ("concentrate", "disperse"),
    ("delay", "accelerate"),
    ("commit", "withdraw"),
    ("divide", "combine"),
)


def compose(names: Sequence[str], base: PolicyVector = BASE_POLICY) -> PolicyVector:
    policy = base
    for name in names:
        try:
            primitive = PRIMITIVES[name]
        except KeyError:
            raise ValueError(f"unknown sd primitive: {name!r}") from None
        policy = primitive.apply(policy)
    return policy


def concealed(names: Sequence[str]) -> bool:
    """True when the last conceal/reveal operator in the tuple is ``conceal``."""
    for name in reversed(tuple(names)):
        if name in ("conceal", "reveal"):
            return name == "conceal"
    return False
