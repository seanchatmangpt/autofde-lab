"""Repository disposition candidates with Chesterton preservation fences.

A disposition is a SELECT artifact only.  No class in this module performs
repository mutation, merge, archive, delete, publication, or deployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import ClaimCeiling, digest


class Disposition(str, Enum):
    KEEP = "KEEP"
    GENERATE = "GENERATE"
    COMPOSE = "COMPOSE"
    MERGE = "MERGE"
    ADAPTER = "ADAPTER"
    ARCHIVE = "ARCHIVE"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class PreservationFence:
    system: str
    boundary: str
    origin: str
    function: str
    consumers: tuple[str, ...]
    authority: str
    compatibility: tuple[str, ...]
    historical_reason: str
    replacement_path: str | None
    rollback_path: str | None

    def __post_init__(self) -> None:
        required = {
            "system": self.system,
            "boundary": self.boundary,
            "origin": self.origin,
            "function": self.function,
            "authority": self.authority,
            "historical_reason": self.historical_reason,
        }
        empty = [name for name, value in required.items() if not value.strip()]
        if empty:
            raise ValueError("preservation fence missing: " + ",".join(empty))

    @property
    def fence_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class DispositionCandidate:
    subject_id: str
    disposition: Disposition
    reason: str
    fence: PreservationFence
    verifier_set_ids: tuple[str, ...]
    claim_ceiling: ClaimCeiling
    counterexample_ids: tuple[str, ...] = ()
    authority_required: str = "BRCE"
    standing: str = "CANDIDATE"

    def __post_init__(self) -> None:
        if not self.subject_id.strip() or not self.reason.strip():
            raise ValueError("subject_id and reason must be non-empty")
        if self.disposition is not Disposition.KEEP:
            if not self.fence.replacement_path:
                raise ValueError(
                    "REFUSED_DISPOSITION_WITHOUT_REPLACEMENT: replacement path required"
                )
            if not self.fence.rollback_path:
                raise ValueError(
                    "REFUSED_DISPOSITION_WITHOUT_REPLACEMENT: rollback path required"
                )
            if not self.verifier_set_ids:
                raise ValueError(
                    "REFUSED_DISPOSITION_WITHOUT_REPLACEMENT: verifier set required"
                )
        if self.standing != "CANDIDATE":
            raise ValueError("disposition objects are candidate SELECT artifacts only")

    @property
    def candidate_id(self) -> str:
        return digest(self)


class DispositionCourt:
    """Construct bounded disposition candidates; never enact them."""

    def propose(
        self,
        *,
        subject_id: str,
        disposition: Disposition,
        reason: str,
        fence: PreservationFence,
        verifier_set_ids: tuple[str, ...] = (),
        claim_ceiling: ClaimCeiling = ClaimCeiling.STRUCTURAL_EQUIVALENCE_ONLY,
        counterexample_ids: tuple[str, ...] = (),
    ) -> DispositionCandidate:
        return DispositionCandidate(
            subject_id=subject_id,
            disposition=disposition,
            reason=reason,
            fence=fence,
            verifier_set_ids=tuple(sorted(set(verifier_set_ids))),
            claim_ceiling=claim_ceiling,
            counterexample_ids=tuple(sorted(set(counterexample_ids))),
        )
