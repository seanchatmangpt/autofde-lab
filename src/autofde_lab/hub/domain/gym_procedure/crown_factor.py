# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Crown factors that cannot be satisfied from absence, by construction.

Every factor of the Level 4 acceptance equation was a bare ``bool`` (or, worse,
a collection read with ``.get(key, [])``). That representation cannot
distinguish four genuinely different situations:

* the factor was observed and holds,
* the factor was observed and does NOT hold,
* the factor was never observed,
* the factor was refused / unsupported / blocked.

Collapsing those into one boolean is what let the REPLAY factor score as
satisfied in three consecutive frozen-crown attempts without ever running: an
exception produced no mismatch key, a missing key read as an empty collection,
and an empty collection read as "clean". Every one of those is *absence*, and
absence was scored as success.

This module makes that impossible to express. A :class:`CrownFactor` has no
truthy shortcut: :meth:`CrownFactor.is_satisfied` is True **only** for
``OBSERVED_TRUE``, and every other state -- including the ones that look like
"nothing went wrong" -- is not satisfied. Constructing a factor requires
naming its evidence source, so a factor with no evidence cannot be built at
all without saying so.

See ``.claude/rules/absence-is-not-evidence.md`` for the governing law. The
short form: a factor that cannot fail is a factor that is not being checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


class FactorState(str, Enum):
    """Six states, not two. `UNKNOWN` is neither success nor failure."""

    OBSERVED_TRUE = "OBSERVED_TRUE"
    OBSERVED_FALSE = "OBSERVED_FALSE"
    UNKNOWN = "UNKNOWN"  # never observed -- NOT a failure, and NOT a pass
    REFUSED = "REFUSED"  # a typed refusal is a real answer
    UNSUPPORTED = "UNSUPPORTED"  # capability/dependency genuinely absent
    BLOCKED = "BLOCKED"  # named external prerequisite prevented observation


#: States that are *not* `OBSERVED_TRUE` but are also not evidence of failure.
#: Kept explicit so a caller that wants "did anything actually get checked?"
#: does not have to re-derive the set and get it subtly wrong.
NON_EVIDENCE_STATES = frozenset(
    {FactorState.UNKNOWN, FactorState.UNSUPPORTED, FactorState.BLOCKED}
)


@dataclass(frozen=True)
class CrownFactor(Generic[T]):
    """One acceptance-equation factor, with its evidence origin attached.

    ``source`` is mandatory and non-empty: a factor that cannot name where its
    value came from is not evidence, and the constructor refuses it rather
    than letting an unattributed value into the conjunction.
    """

    name: str
    state: FactorState
    source: str  # evidence ref: a file path, a receipt id, a command, a digest
    observed: Optional[T] = None
    refusal: Optional[str] = None  # typed refusal reason, when state is REFUSED
    unknown_reason: Optional[str] = None  # why it was never observed

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("CROWN_FACTOR_REQUIRES_NAME")
        if not self.source:
            raise ValueError(
                f"CROWN_FACTOR_REQUIRES_EVIDENCE_SOURCE: {self.name!r} has no evidence "
                f"origin; an unattributed value is not evidence"
            )
        if self.state is FactorState.REFUSED and not self.refusal:
            raise ValueError(f"REFUSED_FACTOR_REQUIRES_REASON: {self.name!r}")
        if self.state in NON_EVIDENCE_STATES and not self.unknown_reason:
            raise ValueError(
                f"NON_EVIDENCE_FACTOR_REQUIRES_REASON: {self.name!r} is "
                f"{self.state.value} and must say why it was not observed"
            )

    def is_satisfied(self) -> bool:
        """True ONLY for OBSERVED_TRUE. There is no truthy shortcut here, and
        deliberately no ``__bool__``: `if factor:` must not compile to a pass."""
        return self.state is FactorState.OBSERVED_TRUE

    def is_evidence(self) -> bool:
        """Whether anything was actually checked (true or false), as opposed to
        the factor simply never having been established."""
        return self.state in (FactorState.OBSERVED_TRUE, FactorState.OBSERVED_FALSE, FactorState.REFUSED)

    def describe(self) -> str:
        detail = self.refusal or self.unknown_reason or ""
        suffix = f" ({detail})" if detail else ""
        return f"{self.name}={self.state.value}{suffix} [src={self.source}]"

    # -- constructors, so a caller states which case it is ------------------

    @classmethod
    def from_observation(cls, name: str, value: T, source: str, holds: bool) -> "CrownFactor[T]":
        return cls(
            name=name,
            state=FactorState.OBSERVED_TRUE if holds else FactorState.OBSERVED_FALSE,
            source=source,
            observed=value,
        )

    @classmethod
    def unknown(cls, name: str, source: str, reason: str) -> "CrownFactor[T]":
        return cls(name=name, state=FactorState.UNKNOWN, source=source, unknown_reason=reason)

    @classmethod
    def refused(cls, name: str, source: str, refusal: str) -> "CrownFactor[T]":
        return cls(name=name, state=FactorState.REFUSED, source=source, refusal=refusal)

    @classmethod
    def blocked(cls, name: str, source: str, reason: str) -> "CrownFactor[T]":
        return cls(name=name, state=FactorState.BLOCKED, source=source, unknown_reason=reason)

    @classmethod
    def unsupported(cls, name: str, source: str, reason: str) -> "CrownFactor[T]":
        return cls(name=name, state=FactorState.UNSUPPORTED, source=source, unknown_reason=reason)


@dataclass(frozen=True)
class FactorConjunction:
    """The acceptance equation as an explicit, inspectable conjunction.

    Requires every REQUIRED factor to be present *and* `OBSERVED_TRUE`. A
    missing factor is a hard failure naming itself, not a silently satisfied
    one -- which is precisely the defect this type exists to make
    unrepresentable.
    """

    required: tuple[str, ...]
    factors: dict[str, CrownFactor]

    def missing(self) -> list[str]:
        return [n for n in self.required if n not in self.factors]

    def unsatisfied(self) -> list[str]:
        out = list(self.missing())
        out += [n for n in self.required if n in self.factors and not self.factors[n].is_satisfied()]
        return out

    def never_checked(self) -> list[str]:
        """Required factors that were never actually established either way --
        the ones a boolean scoreboard would have silently counted as passing."""
        return [n for n in self.required if n not in self.factors] + [
            n for n in self.required if n in self.factors and not self.factors[n].is_evidence()
        ]

    def is_alive(self) -> bool:
        return not self.unsatisfied()

    def verdict(self) -> str:
        """`ALIVE` / `UNKNOWN` / `NOT_ALIVE`, per standing-law vocabulary.

        The distinction that mattered for crown run 1: a trial whose factors
        were never checked is `UNKNOWN`, not a 0-scoring failure. Eight trials
        genuinely reached their goal there; what was absent was replay
        evidence, so the honest verdict was `UNKNOWN`, never `NOT_ALIVE`.
        """
        if self.is_alive():
            return "ALIVE"
        if self.never_checked():
            return "UNKNOWN"
        return "NOT_ALIVE"

    def report(self) -> list[str]:
        lines = [f.describe() for f in (self.factors[n] for n in self.required if n in self.factors)]
        lines += [f"{n}=ABSENT (no factor recorded)" for n in self.missing()]
        return lines


#: The Level 4 acceptance equation, as of the corrected conjunction.
LEVEL4_REQUIRED_FACTORS: tuple[str, ...] = (
    "real_goal_attained",
    "independently_verified",
    "ocel_valid",
    "ocel_referential_integrity",
    "replay_ran",
    "replay_valid",
    "zero_replay_mismatches",
)
