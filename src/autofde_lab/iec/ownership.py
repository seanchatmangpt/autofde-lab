"""Artifact ownership/provenance resolution without first-match guessing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .model import digest


class OwnershipStanding(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class OwnershipEvidenceKind(str, Enum):
    EXPLICIT_MANIFEST = "EXPLICIT_MANIFEST"
    GENERATED_MARKER = "GENERATED_MARKER"
    DIRECTORY_POLICY = "DIRECTORY_POLICY"
    DOCUMENTED_DOCTRINE = "DOCUMENTED_DOCTRINE"
    HISTORICAL_RECEIPT = "HISTORICAL_RECEIPT"


@dataclass(frozen=True, slots=True)
class OwnershipEvidence:
    artifact_id: str
    producer: str
    kind: OwnershipEvidenceKind
    evidence_id: str
    exact_subject_id: str

    @property
    def ownership_evidence_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ArtifactOwnership:
    artifact_id: str
    producer: str | None
    standing: OwnershipStanding
    evidence_ids: tuple[str, ...]
    conflicting_producers: tuple[str, ...] = ()

    @property
    def ownership_id(self) -> str:
        return digest(self)


class OwnershipResolver:
    """Resolve ownership only when producer evidence is non-contradictory."""

    _PRIORITY = {
        OwnershipEvidenceKind.EXPLICIT_MANIFEST: 0,
        OwnershipEvidenceKind.HISTORICAL_RECEIPT: 1,
        OwnershipEvidenceKind.GENERATED_MARKER: 2,
        OwnershipEvidenceKind.DOCUMENTED_DOCTRINE: 3,
        OwnershipEvidenceKind.DIRECTORY_POLICY: 4,
    }

    def resolve(
        self,
        artifact_id: str,
        evidence: Iterable[OwnershipEvidence],
    ) -> ArtifactOwnership:
        applicable = tuple(
            sorted(
                (item for item in evidence if item.artifact_id == artifact_id),
                key=lambda item: (
                    self._PRIORITY[item.kind],
                    item.producer,
                    item.evidence_id,
                ),
            )
        )
        if not applicable:
            return ArtifactOwnership(
                artifact_id=artifact_id,
                producer=None,
                standing=OwnershipStanding.UNKNOWN,
                evidence_ids=(),
            )

        producers = tuple(sorted({item.producer for item in applicable}))
        evidence_ids = tuple(
            sorted(item.ownership_evidence_id for item in applicable)
        )
        if len(producers) > 1:
            return ArtifactOwnership(
                artifact_id=artifact_id,
                producer=None,
                standing=OwnershipStanding.CONTRADICTED,
                evidence_ids=evidence_ids,
                conflicting_producers=producers,
            )

        strongest = applicable[0]
        standing = (
            OwnershipStanding.OBSERVED
            if strongest.kind
            in {
                OwnershipEvidenceKind.EXPLICIT_MANIFEST,
                OwnershipEvidenceKind.HISTORICAL_RECEIPT,
            }
            else OwnershipStanding.DERIVED
        )
        return ArtifactOwnership(
            artifact_id=artifact_id,
            producer=strongest.producer,
            standing=standing,
            evidence_ids=evidence_ids,
        )
