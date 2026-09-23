"""Inverse Ecosystem Compiler (IEC).

IEC is an exploration/verification surface. It may observe, infer candidate
semantics, manufacture inert projections, and run bounded equivalence courts.
It deliberately has no external actuation authority.
"""

from .anti_unification import AntiUnifier, Generalization
from .corpus import CorpusFreezer, CorpusRevision
from .correspondence import CorrespondenceEngine
from .engine import InverseEcosystemCompiler
from .equivalence import EquivalenceCourt
from .model import (
    ArtifactClass,
    ClaimCeiling,
    EquivalenceDimension,
    EvidenceKind,
    FailureKind,
    Observation,
    RepositorySubject,
    SemanticClaim,
    Standing,
)
from .observations import ObservationExtractor
from .retirement import RetirementLedger

__all__ = [
    "AntiUnifier",
    "ArtifactClass",
    "ClaimCeiling",
    "CorrespondenceEngine",
    "CorpusFreezer",
    "CorpusRevision",
    "EquivalenceCourt",
    "EquivalenceDimension",
    "EvidenceKind",
    "FailureKind",
    "Generalization",
    "InverseEcosystemCompiler",
    "Observation",
    "ObservationExtractor",
    "RepositorySubject",
    "RetirementLedger",
    "SemanticClaim",
    "Standing",
]
