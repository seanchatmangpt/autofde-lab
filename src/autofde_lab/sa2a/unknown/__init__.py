"""Unknown state handling and candidate frontier management (RFC-SA2A-001 v26.9.16)."""

from __future__ import annotations

from .allocator import (
    AllocationStanding,
    AutonomousBudgetExpansionRefused,
    CandidateAllocation,
    CMCACandidateAllocator,
    ExplorationBudget,
    FrontierAllocationPlan,
    UnknownCandidate,
)
from .compilation import (
    CompiledDeterministicRule,
    ExperienceCompilationReceipt,
    MachineExperienceCompiler,
)
from .novelty_ingest import (
    NoveltyIngestionGateway,
    NoveltyPacket,
)
from .resolution import (
    AdmissionReceipt,
    CandidateResolution,
    EpistemicState,
    UnknownQuery,
    UnknownResolutionPipeline,
)

__all__ = [
    "AdmissionReceipt",
    "AllocationStanding",
    "AutonomousBudgetExpansionRefused",
    "CandidateAllocation",
    "CandidateResolution",
    "CMCACandidateAllocator",
    "CompiledDeterministicRule",
    "EpistemicState",
    "ExperienceCompilationReceipt",
    "ExplorationBudget",
    "FrontierAllocationPlan",
    "MachineExperienceCompiler",
    "NoveltyIngestionGateway",
    "NoveltyPacket",
    "UnknownCandidate",
    "UnknownQuery",
    "UnknownResolutionPipeline",
]
