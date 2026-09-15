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
    ModelQualificationRecord,
    OptimizationReceipt,
    SemanticExample,
    SemanticTriple,
)
from .dataset import ExperienceRecord, ManufacturedDataset, manufacture_dataset
from .evaluation import EvaluationWeights, SemanticEvaluation, evaluate_candidate
from .loop import ClosedManufacturingCycleResult, run_closed_manufacturing_cycle
from .pipeline import SemanticModelPipeline, SemanticPipelineResult

__all__ = [
    "AdmissionReceipt",
    "AdmissionStanding",
    "CandidateGraphDelta",
    "ClosedManufacturingCycleResult",
    "EvaluationWeights",
    "ExperienceRecord",
    "ManufacturedDataset",
    "ModelQualificationRecord",
    "OptimizationReceipt",
    "SemanticAdmissionCourt",
    "SemanticEvaluation",
    "SemanticExample",
    "SemanticModelPipeline",
    "SemanticPipelineResult",
    "SemanticTriple",
    "evaluate_candidate",
    "manufacture_dataset",
    "run_closed_manufacturing_cycle",
]
