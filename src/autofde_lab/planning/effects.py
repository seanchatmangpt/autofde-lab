"""Planner-only effect compatibility calculus.

This module computes candidate concurrency relationships. It never grants
authority and never performs consequential DO.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, FrozenSet, Optional


@dataclass(frozen=True)
class Effect:
    """An immutable planner-visible description of an action's observable footprint."""

    subject: str
    operation: str
    read_set: FrozenSet[str] = field(default_factory=frozenset)
    write_set: FrozenSet[str] = field(default_factory=frozenset)
    consequence_class: str = "NONE"
    reversibility: str = "UNKNOWN"
    authority_requirement: str = "NONE"
    idempotency_scope: Optional[str] = None
    footprint_known: bool = True

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError("subject must be non-empty")
        if not self.operation:
            raise ValueError("operation must be non-empty")

    @property
    def touch_set(self) -> FrozenSet[str]:
        return self.read_set | self.write_set


@dataclass(frozen=True)
class CompatibilityCheck:
    parallel_candidate: bool
    reason: str
    conflict_set: FrozenSet[str] = field(default_factory=frozenset)


CommutativityRule = Callable[[Effect, Effect], bool]


def conflicts(a: Effect, b: Effect) -> FrozenSet[str]:
    """Return resources whose accesses require ordering under the default law."""
    return (a.write_set & b.touch_set) | (b.write_set & a.touch_set)


def independent(a: Effect, b: Effect) -> bool:
    """True only when both footprints are known and default conflicts are absent."""
    return a.footprint_known and b.footprint_known and not conflicts(a, b)


def commutes(
    a: Effect,
    b: Effect,
    *,
    rule: CommutativityRule | None = None,
) -> bool:
    """Return candidate commutativity; explicit rules may prove an overlap safe."""
    if independent(a, b):
        return True
    if not a.footprint_known or not b.footprint_known:
        return False
    return bool(rule and rule(a, b))


def check_parallel_candidate(
    a: Effect,
    b: Effect,
    *,
    commutativity_rule: CommutativityRule | None = None,
) -> CompatibilityCheck:
    """Classify a pair without granting execution authority."""
    if not a.footprint_known or not b.footprint_known:
        return CompatibilityCheck(False, "UNKNOWN_EFFECT")

    overlap = conflicts(a, b)
    if not overlap:
        return CompatibilityCheck(True, "DISJOINT_OR_READ_ONLY")

    if commutativity_rule and commutativity_rule(a, b):
        return CompatibilityCheck(True, "PROVEN_COMMUTATIVE", overlap)

    return CompatibilityCheck(False, "EFFECT_CONFLICT", overlap)


def parallel_candidate(
    a: Effect,
    b: Effect,
    *,
    commutativity_rule: CommutativityRule | None = None,
) -> bool:
    return check_parallel_candidate(
        a, b, commutativity_rule=commutativity_rule
    ).parallel_candidate
