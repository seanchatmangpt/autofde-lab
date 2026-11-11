"""Rendered by ggen from the autofde-lab standing vocabulary (ggen output is first-class source).

Single source: ontology.ttl of autofde-lab-standing-vocabulary-pack, itself
lifted from src/autofde_lab/standing.py. Standing is a derived conclusion over
evidence, never a producer-controlled success flag. This module carries no
actuation authority: it classifies claims, it does not perform anything.
"""

from __future__ import annotations

from typing import ClassVar


class StandingError(Exception):
    """Base for every standing-law exception. Never raised directly."""

    standing: ClassVar[str] = ""

    def __init__(self, reason: str, *, evidence: str = "") -> None:
        if not type(self).standing:
            raise TypeError(
                "StandingError is abstract: raise a subclass that names a standing"
            )
        if not reason or not reason.strip():
            raise ValueError(
                f"{type(self).__name__} requires a reason. "
                "standing-law: name the exact blocker, not 'blocked'"
            )
        self.reason = reason.strip()
        self.evidence = evidence.strip()
        detail = f"{type(self).standing}:{self.reason}"
        if self.evidence:
            detail = f"{detail} -- {self.evidence}"
        super().__init__(detail)


class Blocked(StandingError):
    """A named external prerequisite prevents lawful progress."""

    standing = "BLOCKED"


class BuildBroken(StandingError):
    """The relevant build or test suite fails."""

    standing = "BUILD_BROKEN"


class NotRun(StandingError):
    """The path exists, is committed, and has never been executed."""

    standing = "NOT_RUN"


class PartialAlive(StandingError):
    """A bounded working checkpoint exists; the larger claim does not follow."""

    standing = "PARTIAL_ALIVE"


class Unknown(StandingError):
    """Observation is insufficient to classify standing. Never a synonym for probably fine."""

    standing = "UNKNOWN"


class Unsupported(StandingError):
    """A required capability or dependency is absent; an environment gate, not incomplete work."""

    standing = "UNSUPPORTED"


class NotFound(Unsupported):
    """An absence claim carrying the search boundary that produced it."""

    standing = "NOT_FOUND"



class TransitionViolation(StandingError):
    """An artifact was promoted past a transition that never occurred."""

    standing = "REFUSED"
    lawful_standing: ClassVar[str] = "UNKNOWN"

    def __init__(self, claimed: str, *, detail: str) -> None:
        super().__init__(
            f"{type(self).__name__}: claimed {claimed}, "
            f"lawful standing is {type(self).lawful_standing}",
            evidence=detail,
        )
        self.claimed = claimed
        self.lawful = type(self).lawful_standing


class AdvisoryAuthorityUsedAsBearer(TransitionViolation):
    """An advisory allow was treated as bearer authority; permits() is advisory by construction."""

    lawful_standing = "UNKNOWN"


class AuthoredNotExecuted(TransitionViolation):
    """The artifact exists; no execution witness does."""

    lawful_standing = "NOT_RUN"


class DeclaredDeployedMismatch(TransitionViolation):
    """The declared architecture and the deployed one describe different systems."""

    lawful_standing = "ABSENT"


class DeclaredMappingOnly(TransitionViolation):
    """Vocabulary exists; no executable derivation computes it."""

    lawful_standing = "ABSENT"


class FalseGreen(TransitionViolation):
    """A report announced success over a run that did not succeed."""

    lawful_standing = "BUILD_BROKEN"


class InertIntegrationSurface(TransitionViolation):
    """The surface is declared but has no executable path from input to effect."""

    lawful_standing = "ABSENT"


class MockEvidencePromoted(TransitionViolation):
    """A mocked test was cited as evidence for a real external boundary."""

    lawful_standing = "CONFIGURATION_VALIDATED"


class PredictedStandingCited(TransitionViolation):
    """A forecast was quoted as an observation."""

    lawful_standing = "UNKNOWN"


class SelfCertifiedPostcondition(TransitionViolation):
    """The performer declared its own consequence successful."""

    lawful_standing = "UNKNOWN"


class SiblingPromotedToCoreDependency(TransitionViolation):
    """An optional sibling adapter became a prerequisite of the core."""

    lawful_standing = "UNSUPPORTED"


class UndeclaredEvidenceDependency(TransitionViolation):
    """A proof passed only because of an ambient, undeclared provider."""

    lawful_standing = "UNKNOWN"


TRANSITION_VIOLATIONS: tuple[type[TransitionViolation], ...] = (
AdvisoryAuthorityUsedAsBearer,
AuthoredNotExecuted,
DeclaredDeployedMismatch,
DeclaredMappingOnly,
FalseGreen,
InertIntegrationSurface,
MockEvidencePromoted,
PredictedStandingCited,
SelfCertifiedPostcondition,
SiblingPromotedToCoreDependency,
UndeclaredEvidenceDependency,
)

STANDING_VALUES: tuple[str, ...] = (
"BLOCKED",
"BUILD_BROKEN",
"NOT_RUN",
"PARTIAL_ALIVE",
"UNKNOWN",
"UNSUPPORTED",
"NOT_FOUND",
)


def standing_class(standing: str) -> type[StandingError]:
    """Resolve a standing string to its raisable class, or refuse it."""
    for cls in (Blocked, BuildBroken, NotRun, PartialAlive, Unknown, Unsupported, NotFound, ):
        if cls.standing == standing:
            return cls
    raise ValueError(
        f"unknown standing {standing!r}: not in the standing vocabulary "
        f"{list(STANDING_VALUES)}"
    )


__all__ = [
    "StandingError",
    "TransitionViolation",
    "TRANSITION_VIOLATIONS",
    "STANDING_VALUES",
    "standing_class",
"Blocked",
"BuildBroken",
"NotRun",
"PartialAlive",
"Unknown",
"Unsupported",
"NotFound",
"AdvisoryAuthorityUsedAsBearer",
"AuthoredNotExecuted",
"DeclaredDeployedMismatch",
"DeclaredMappingOnly",
"FalseGreen",
"InertIntegrationSurface",
"MockEvidencePromoted",
"PredictedStandingCited",
"SelfCertifiedPostcondition",
"SiblingPromotedToCoreDependency",
"UndeclaredEvidenceDependency",
]
