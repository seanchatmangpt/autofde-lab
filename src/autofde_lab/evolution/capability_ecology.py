"""Qualified-capability ecology consumer for AutoFDE.

This module composes existing paired-promotion and cognition-retirement courts
into the exact-subject lifecycle manufactured by ggen-marketplace's
qualified-capability-ecology-pack.

It manufactures evidence only. It never grants DO authority.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from hashlib import sha256

from .paired_promotion import (
    CompiledRetirementRoute,
    PromotionDecision,
    PromotionVerdict,
)

_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"REFUSED:{name.upper()}_IMMUTABLE_DIGEST_REQUIRED")


@dataclass(frozen=True, slots=True)
class GitCapabilitySubject:
    """Exact repository/commit/artifact identity for one capability version."""

    repository: str
    commit: str
    capability_id: str
    artifact_digest: str

    def __post_init__(self) -> None:
        if not self.repository.strip():
            raise ValueError("REFUSED:SUBJECT_REPOSITORY_REQUIRED")
        if not _GIT_SHA.fullmatch(self.commit):
            raise ValueError("REFUSED:IMMUTABLE_GIT_COMMIT_REQUIRED")
        if not self.capability_id.strip():
            raise ValueError("REFUSED:CAPABILITY_ID_REQUIRED")
        _require_digest("artifact", self.artifact_digest)

    @property
    def exact_subject_digest(self) -> str:
        return _canonical_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class FrozenCapabilityRecord:
    """Candidate that passed paired evidence and is frozen for runtime selection."""

    subject: GitCapabilitySubject
    qualification_digest: str
    promotion_evidence_digest: str
    replay_digest: str
    independent_verification_digest: str
    closure_digest: str
    schema: str = "ggen.qualified-capability-frozen/1"
    authority: str = "none"
    grants_do_authority: bool = False

    @property
    def record_digest(self) -> str:
        return _canonical_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class CapabilitySubstitutionReceipt:
    """Consequence-preserving replacement evidence with conserved authority."""

    original: GitCapabilitySubject
    replacement: GitCapabilitySubject
    frozen_record_digest: str
    behavioral_court_digest: str
    cohort_digest: str
    route_digest: str
    predecessor_authority_depth: int
    successor_authority_depth: int
    consequence_preserved: bool
    replay_verified: bool
    schema: str = "ggen.qualified-capability-substitution/1"
    authority: str = "none"
    grants_do_authority: bool = False

    @property
    def receipt_digest(self) -> str:
        return _canonical_digest(asdict(self))


@dataclass(frozen=True, slots=True)
class ResidualHumanWork:
    """Human work remaining after automation, including the hidden tail."""

    baseline_work: float
    exception_work: float
    verification_work: float
    correction_work: float
    maintenance_work: float

    def __post_init__(self) -> None:
        values = (
            self.baseline_work,
            self.exception_work,
            self.verification_work,
            self.correction_work,
            self.maintenance_work,
        )
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("REFUSED:HUMAN_WORK_MUST_BE_FINITE_NONNEGATIVE")

    @property
    def residual_work(self) -> float:
        return (
            self.exception_work
            + self.verification_work
            + self.correction_work
            + self.maintenance_work
        )

    @property
    def net_human_work_delta(self) -> float:
        return self.residual_work - self.baseline_work


@dataclass(frozen=True, slots=True)
class CapabilityRetirementReceipt:
    """Evidence that a predecessor may be retired from the selected route."""

    substitution_receipt_digest: str
    human_work: ResidualHumanWork
    net_human_work_delta: float
    schema: str = "ggen.qualified-capability-retirement/1"
    authority: str = "none"
    grants_do_authority: bool = False

    @property
    def receipt_digest(self) -> str:
        return _canonical_digest(asdict(self))


def freeze_promoted_candidate(
    *,
    subject: GitCapabilitySubject,
    promotion: PromotionVerdict,
    replay_digest: str,
    independent_verification_digest: str,
) -> FrozenCapabilityRecord:
    """Bind a PROMOTE verdict to an immutable candidate and frozen closure."""

    if promotion.decision is not PromotionDecision.PROMOTE:
        raise ValueError("REFUSED:CANDIDATE_NOT_PROMOTED")
    if promotion.authority != "none":
        raise ValueError("REFUSED:PROMOTION_AMBIENT_AUTHORITY")
    if promotion.candidate_id != subject.capability_id:
        raise ValueError("REFUSED:PROMOTION_EXACT_SUBJECT_MISMATCH")

    _require_digest("promotion_evidence", promotion.evidence_digest)
    _require_digest("replay", replay_digest)
    _require_digest("independent_verification", independent_verification_digest)

    qualification_payload = {
        "subject": asdict(subject),
        "promotion_evidence_digest": promotion.evidence_digest,
        "replay_digest": replay_digest,
        "independent_verification_digest": independent_verification_digest,
    }
    qualification_digest = _canonical_digest(qualification_payload)
    closure_digest = _canonical_digest(
        {
            "capability": subject.capability_id,
            "artifact_digest": subject.artifact_digest,
            "qualification_digest": qualification_digest,
            "authority": "none",
        }
    )
    return FrozenCapabilityRecord(
        subject=subject,
        qualification_digest=qualification_digest,
        promotion_evidence_digest=promotion.evidence_digest,
        replay_digest=replay_digest,
        independent_verification_digest=independent_verification_digest,
        closure_digest=closure_digest,
    )


def qualify_substitution(
    *,
    original: GitCapabilitySubject,
    replacement: FrozenCapabilityRecord,
    route: CompiledRetirementRoute,
    predecessor_authority_depth: int,
    successor_authority_depth: int,
) -> CapabilitySubstitutionReceipt:
    """Manufacture substitution evidence from an admitted replay route.

    Consequence preservation is derived from CompiledRetirementRoute rather
    than accepted as a caller boolean: that route can only be compiled from a
    RETIRE_INCUMBENT verdict whose incumbent-success outputs replay exactly.
    """

    if predecessor_authority_depth < 0 or successor_authority_depth < 0:
        raise ValueError("REFUSED:NEGATIVE_AUTHORITY_DEPTH")
    if successor_authority_depth > predecessor_authority_depth:
        raise ValueError("REFUSED:AUTHORITY_INCREASE")
    if route.authority != "none":
        raise ValueError("REFUSED:RETIREMENT_ROUTE_AMBIENT_AUTHORITY")
    if route.candidate_artifact_digest != replacement.subject.artifact_digest:
        raise ValueError("REFUSED:SUBSTITUTION_ARTIFACT_MISMATCH")

    _require_digest("behavioral_court", route.behavioral_court_digest)
    _require_digest("cohort", route.cohort_digest)
    _require_digest("route", route.route_digest)

    return CapabilitySubstitutionReceipt(
        original=original,
        replacement=replacement.subject,
        frozen_record_digest=replacement.record_digest,
        behavioral_court_digest=route.behavioral_court_digest,
        cohort_digest=route.cohort_digest,
        route_digest=route.route_digest,
        predecessor_authority_depth=predecessor_authority_depth,
        successor_authority_depth=successor_authority_depth,
        consequence_preserved=True,
        replay_verified=True,
    )


def qualify_retirement(
    *,
    substitution: CapabilitySubstitutionReceipt,
    human_work: ResidualHumanWork,
) -> CapabilityRetirementReceipt:
    """Retire only when substitution is receipted and residual human work falls."""

    if not substitution.consequence_preserved or not substitution.replay_verified:
        raise ValueError("REFUSED:UNQUALIFIED_SUBSTITUTION")
    _require_digest("substitution_receipt", substitution.receipt_digest)

    delta = human_work.net_human_work_delta
    if delta >= 0:
        raise ValueError("REFUSED:RESIDUAL_HUMAN_WORK_NOT_REDUCED")

    return CapabilityRetirementReceipt(
        substitution_receipt_digest=substitution.receipt_digest,
        human_work=human_work,
        net_human_work_delta=delta,
    )
