"""v26.9.18 GALL autonomics primitives.

These modules preserve the boundary:
observation -> candidate -> selection -> delegated authority/DO -> independent
verification -> qualified MachineExperience. Nothing in this package performs
an external consequence.
"""

from .belief import BeliefState, EpistemicValue, InformationAction
from .crown import AutonomicsCrown, VerifiedRepair
from .external_crown import ExternalAutonomicsManifest, ExternalCrownEvidence
from .falsifier import ActiveFalsifier, FalsifierResult, Invariant
from .feedback import AdmittedFeedback, FeedbackAdmission, FeedbackFinding, FeedbackRule
from .predictor import PredictionCandidate, PredictionStanding
from .redesign import CanaryEnvelope, CanaryEvidence, RedesignCandidate
from .repair import InterventionRequest, RepairCandidate, RepairSelector
from .telemetry import Measurement, SemanticCorrelation, SemanticTelemetryArtifact

__all__ = [
    "ActiveFalsifier",
    "AdmittedFeedback",
    "AutonomicsCrown",
    "BeliefState",
    "CanaryEnvelope",
    "CanaryEvidence",
    "EpistemicValue",
    "ExternalAutonomicsManifest",
    "ExternalCrownEvidence",
    "FalsifierResult",
    "FeedbackAdmission",
    "FeedbackFinding",
    "FeedbackRule",
    "InformationAction",
    "InterventionRequest",
    "Invariant",
    "Measurement",
    "PredictionCandidate",
    "PredictionStanding",
    "RedesignCandidate",
    "RepairCandidate",
    "RepairSelector",
    "SemanticCorrelation",
    "SemanticTelemetryArtifact",
    "VerifiedRepair",
]
