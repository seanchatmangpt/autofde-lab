"""Inverse Ecosystem Compiler (IEC).

IEC is an exploration/verification surface. It may observe, infer candidate
semantics, manufacture inert projections, and run bounded equivalence courts.
It deliberately has no external actuation authority.
"""

from .anti_unification import AntiUnifier, Generalization
from .corpus import CorpusFreezer, CorpusRevision
from .correspondence import CorrespondenceEngine
from .cost import CostVector, KernelCandidate, dominates
from .disposition import Disposition, DispositionCourt, PreservationFence
from .engine import InverseEcosystemCompiler
from .equivalence import EquivalenceCourt
from .ggen_create_adapter import GgenCreateAdapter
from .hypothesis import Hypothesis, HypothesisFrontier
from .incremental import CacheEntry, CacheKey, ObservationCache
from .manufacture import ManufactureRequirement, ManufactureRouter
from .metrics import IECMetrics
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
from .observations import ObservationExtractor, PassiveFile
from .prior_art import (
    CandidateFailure,
    NoveltyRefusal,
    PriorArtCandidate,
    PriorArtDisposition,
    PriorArtVerdict,
    assert_novelty_receipt,
    classify_prior_art,
)
from .probe import ProbeCandidate, ProbePlanner
from .promotion import PromotionKind, PromotionRouter
from .python_api import extract_python_api, python_api_verifier
from .receipts import IECReceipt, IECStage, ReceiptChain
from .retirement import RetirementLedger
from .structural import StructuralParserRegistry
from .tree import TreeEntry, TreeSnapshot, compare_trees, tree_equivalence_verifier

__all__ = [
    "AntiUnifier",
    "ArtifactClass",
    "CacheEntry",
    "CacheKey",
    "ClaimCeiling",
    "CorrespondenceEngine",
    "CorpusFreezer",
    "CorpusRevision",
    "CostVector",
    "Disposition",
    "DispositionCourt",
    "EquivalenceCourt",
    "EquivalenceDimension",
    "EvidenceKind",
    "FailureKind",
    "Generalization",
    "GgenCreateAdapter",
    "Hypothesis",
    "HypothesisFrontier",
    "IECReceipt",
    "IECMetrics",
    "IECStage",
    "InverseEcosystemCompiler",
    "KernelCandidate",
    "ManufactureRequirement",
    "ManufactureRouter",
    "Observation",
    "ObservationCache",
    "ObservationExtractor",
    "PassiveFile",
    "PreservationFence",
    "ProbeCandidate",
    "ProbePlanner",
    "CandidateFailure",
    "NoveltyRefusal",
    "PriorArtCandidate",
    "PriorArtDisposition",
    "PriorArtVerdict",
    "assert_novelty_receipt",
    "classify_prior_art",
    "PromotionKind",
    "PromotionRouter",
    "ReceiptChain",
    "RepositorySubject",
    "RetirementLedger",
    "SemanticClaim",
    "Standing",
    "StructuralParserRegistry",
    "TreeEntry",
    "TreeSnapshot",
    "compare_trees",
    "dominates",
    "extract_python_api",
    "python_api_verifier",
    "tree_equivalence_verifier",
]
