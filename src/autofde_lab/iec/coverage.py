"""Descriptive coverage court for repository archaeology."""

from __future__ import annotations

from dataclasses import dataclass

from .engine import RepositoryAnalysis
from .model import ArtifactClass, digest


@dataclass(frozen=True, slots=True)
class CoverageAssessment:
    subject_id: str
    total_artifacts: int
    classified_artifacts: int
    unknown_artifacts: int
    generated_artifacts: int
    generated_with_known_producer: int
    unknown_paths: tuple[str, ...]

    @property
    def coverage(self) -> float:
        if self.total_artifacts == 0:
            return 0.0
        return self.classified_artifacts / self.total_artifacts

    @property
    def producer_coverage(self) -> float:
        if self.generated_artifacts == 0:
            return 1.0
        return self.generated_with_known_producer / self.generated_artifacts

    @property
    def assessment_id(self) -> str:
        return digest(self)


def assess_coverage(analysis: RepositoryAnalysis) -> CoverageAssessment:
    unknown = tuple(
        sorted(
            artifact.path
            for artifact in analysis.artifacts
            if artifact.artifact_class is ArtifactClass.UNKNOWN
        )
    )
    generated = tuple(
        artifact
        for artifact in analysis.artifacts
        if artifact.artifact_class is ArtifactClass.GENERATED_PROJECTION
    )
    return CoverageAssessment(
        subject_id=analysis.subject.subject_id,
        total_artifacts=len(analysis.artifacts),
        classified_artifacts=len(analysis.artifacts) - len(unknown),
        unknown_artifacts=len(unknown),
        generated_artifacts=len(generated),
        generated_with_known_producer=sum(
            1 for artifact in generated if artifact.producer
        ),
        unknown_paths=unknown,
    )
