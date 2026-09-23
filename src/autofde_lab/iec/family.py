"""Cross-repository structural family discovery.

Repository signatures compress observation space. Family edges are candidates
only and require later semantic/equivalence verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable

from .engine import RepositoryAnalysis
from .model import ArtifactClass, digest


@dataclass(frozen=True, slots=True)
class RepositorySignature:
    subject_id: str
    artifact_classes: tuple[tuple[str, int], ...]
    suffixes: tuple[tuple[str, int], ...]
    producers: tuple[str, ...]
    canonical_roots: tuple[str, ...]
    total_artifacts: int

    @property
    def signature_id(self) -> str:
        return digest(
            {
                "artifact_classes": self.artifact_classes,
                "suffixes": self.suffixes,
                "producers": self.producers,
                "canonical_roots": self.canonical_roots,
                "total_artifacts": self.total_artifacts,
            }
        )


@dataclass(frozen=True, slots=True)
class RepositoryFamilyCandidate:
    left_subject_id: str
    right_subject_id: str
    score: float
    shared_features: tuple[str, ...]
    required_verifier: str = "iec.cross-repository-equivalence"

    @property
    def candidate_id(self) -> str:
        return digest(self)


def repository_signature(analysis: RepositoryAnalysis) -> RepositorySignature:
    class_counts: dict[str, int] = {}
    suffix_counts: dict[str, int] = {}
    producers: set[str] = set()
    roots: set[str] = set()

    for artifact in analysis.artifacts:
        class_counts[artifact.artifact_class.value] = (
            class_counts.get(artifact.artifact_class.value, 0) + 1
        )
        suffix = PurePosixPath(artifact.path).suffix.lower() or "<none>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
        if artifact.producer:
            producers.add(artifact.producer)
        if artifact.artifact_class is ArtifactClass.CANONICAL_SOURCE:
            roots.add(PurePosixPath(artifact.path).parts[0])

    return RepositorySignature(
        subject_id=analysis.subject.subject_id,
        artifact_classes=tuple(sorted(class_counts.items())),
        suffixes=tuple(sorted(suffix_counts.items())),
        producers=tuple(sorted(producers)),
        canonical_roots=tuple(sorted(roots)),
        total_artifacts=len(analysis.artifacts),
    )


def _feature_set(signature: RepositorySignature) -> frozenset[str]:
    features: set[str] = set()
    for name, count in signature.artifact_classes:
        if count:
            features.add("class:" + name)
    for suffix, count in signature.suffixes:
        if count:
            features.add("suffix:" + suffix)
    features.update("producer:" + producer for producer in signature.producers)
    features.update("root:" + root for root in signature.canonical_roots)
    return frozenset(features)


def family_candidates(
    signatures: Iterable[RepositorySignature],
    *,
    threshold: float = 0.5,
) -> tuple[RepositoryFamilyCandidate, ...]:
    ordered = tuple(sorted(signatures, key=lambda item: item.subject_id))
    results: list[RepositoryFamilyCandidate] = []

    for index, left in enumerate(ordered):
        left_features = _feature_set(left)
        for right in ordered[index + 1 :]:
            right_features = _feature_set(right)
            union = left_features | right_features
            score = len(left_features & right_features) / len(union) if union else 1.0
            if score < threshold:
                continue
            results.append(
                RepositoryFamilyCandidate(
                    left_subject_id=left.subject_id,
                    right_subject_id=right.subject_id,
                    score=round(score, 6),
                    shared_features=tuple(sorted(left_features & right_features)),
                )
            )

    return tuple(
        sorted(
            results,
            key=lambda item: (-item.score, item.left_subject_id, item.right_subject_id),
        )
    )
