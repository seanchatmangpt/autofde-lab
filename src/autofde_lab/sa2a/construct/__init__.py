"""Constructor package for Semantic A2A (RFC-SA2A-001 v26.9.16)."""

from .constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    ConstructionReceipt,
    ExecutableArtifact,
    TargetProfile,
    compute_digest,
)
from .ephemeral import (
    EphemeralLifecycleRunner,
    EphemeralProjectionWrapper,
    EphemeralState,
    ExecutionResult,
    ProjectionMutationForbiddenError,
)

__all__ = [
    "AdmittedSemantics",
    "ArtifactManufacturer",
    "ConstructionReceipt",
    "ExecutableArtifact",
    "TargetProfile",
    "compute_digest",
    "EphemeralLifecycleRunner",
    "EphemeralProjectionWrapper",
    "EphemeralState",
    "ExecutionResult",
    "ProjectionMutationForbiddenError",
]

