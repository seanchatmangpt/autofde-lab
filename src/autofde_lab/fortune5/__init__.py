"""Fortune-5-scale combinatorial enterprise exploration surface."""

from .catalog import AXES, CATALOG_ROWS
from .f5bench import (
    BenchmarkMutation,
    ResynchronizationWitness,
    architecture_optionality_density,
    verify_resynchronization,
)
from .readiness import (
    F5ReadinessVerifier,
    GateEvidence,
    ReadinessSubmission,
    ReadinessWitness,
    REQUIRED_GATES,
    build_submission,
    evidence_digest,
    failure_rate,
    reference_profile_digest,
    subject_identity_digest,
)
from .space import (
    Axis,
    CompatibilityLaw,
    Option,
    Scenario,
    StateSpace,
    pairwise_covering,
    pairwise_token_count,
)

FORTUNE5_SPACE = StateSpace(axes=AXES)

__all__ = [
    "AXES",
    "CATALOG_ROWS",
    "FORTUNE5_SPACE",
    "Axis",
    "BenchmarkMutation",
    "CompatibilityLaw",
    "F5ReadinessVerifier",
    "GateEvidence",
    "Option",
    "REQUIRED_GATES",
    "ReadinessSubmission",
    "ReadinessWitness",
    "ResynchronizationWitness",
    "Scenario",
    "StateSpace",
    "architecture_optionality_density",
    "build_submission",
    "evidence_digest",
    "failure_rate",
    "pairwise_covering",
    "pairwise_token_count",
    "reference_profile_digest",
    "subject_identity_digest",
    "verify_resynchronization",
]
