"""Post-Chapman semantic-model manufacturing for AutoFDE Lab.

The package enforces the boundary ``A = mu(O*)``: language models and statistical
optimizers may manufacture *candidates*, but only the admission court may change
admitted semantic state.
"""

from .admission import SemanticAdmissionCourt
from .atomvm_codegen import AtomVMStanding, generate_atomvm_erlang_module
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
from .feature_schema import SemanticFeature, SemanticFeatureSchema
from .loop import ClosedManufacturingCycleResult, run_closed_manufacturing_cycle
from .parity_court import (
    RuntimeParityRecord,
    TeacherIndependenceReport,
    compute_teacher_independence,
    evaluate_runtime_parity,
)
from .pipeline import SemanticModelPipeline, SemanticPipelineResult
from .portable_compiler import (
    PortableDecisionTree,
    PortableLinearWeights,
    PortableTreeNode,
    build_tiny_operator_from_linear,
    compile_linear_to_fixed_point,
    compile_tree_to_fixed_point,
)
from .tiny_operator import (
    QuantizationKind,
    RuntimeTarget,
    TinyOperatorManifest,
    TinyOperatorReceipt,
    TinySemanticOperator,
)

__all__ = [
    "AdmissionReceipt",
    "AdmissionStanding",
    "AtomVMStanding",
    "CandidateGraphDelta",
    "ClosedManufacturingCycleResult",
    "EvaluationWeights",
    "ExperienceRecord",
    "ManufacturedDataset",
    "ModelQualificationRecord",
    "OptimizationReceipt",
    "PortableDecisionTree",
    "PortableLinearWeights",
    "PortableTreeNode",
    "QuantizationKind",
    "RuntimeParityRecord",
    "RuntimeTarget",
    "SemanticAdmissionCourt",
    "SemanticEvaluation",
    "SemanticExample",
    "SemanticFeature",
    "SemanticFeatureSchema",
    "SemanticModelPipeline",
    "SemanticPipelineResult",
    "SemanticTriple",
    "TeacherIndependenceReport",
    "TinyOperatorManifest",
    "TinyOperatorReceipt",
    "TinySemanticOperator",
    "build_tiny_operator_from_linear",
    "compile_linear_to_fixed_point",
    "compile_tree_to_fixed_point",
    "compute_teacher_independence",
    "evaluate_candidate",
    "evaluate_runtime_parity",
    "generate_atomvm_erlang_module",
    "manufacture_dataset",
    "run_closed_manufacturing_cycle",
]
