"""Post-Chapman semantic-model manufacturing for AutoFDE Lab.

The package enforces the boundary ``A = mu(O*)``: language models and statistical
optimizers may manufacture *candidates*, but only the admission court may change
admitted semantic state.
"""

from .admission import SemanticAdmissionCourt
from .contracts import (
    AdmissionReceipt,
    AdmissionStanding,
    CandidateGraphDelta,
    SemanticExample,
    SemanticTriple,
)
from .evaluation import EvaluationWeights, SemanticEvaluation, evaluate_candidate
from .pipeline import SemanticModelPipeline, SemanticPipelineResult

__all__ = [
    "AdmissionReceipt",
    "AdmissionStanding",
    "CandidateGraphDelta",
    "EvaluationWeights",
    "SemanticAdmissionCourt",
    "SemanticEvaluation",
    "SemanticExample",
    "SemanticModelPipeline",
    "SemanticPipelineResult",
    "SemanticTriple",
    "evaluate_candidate",
]
