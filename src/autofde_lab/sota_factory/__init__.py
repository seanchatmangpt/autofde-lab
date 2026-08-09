"""AutoFDE Lab SOTA factory control plane.

The package represents benchmark targets, DecisionBasis architecture spaces,
experiment designs, score/frontier standing, and failure-driven learning. It is
SELECT/LEARN only: execution results are ingested from the governed GymAct /
benchmark runtime boundary.
"""

from .compiler import CompiledExperimentSet, ExperimentCompiler
from .factory import FactorySnapshot, SOTAFactory
from .learning import FailureRouter, LearningCompiler, LearningSignal
from .models import (
    ArchitecturePoint,
    BasisChoice,
    BenchmarkScore,
    BenchmarkTarget,
    BudgetPolicy,
    DecisionBasis,
    ExperimentBasis,
    ExperimentPlan,
    FailureCluster,
    FailureKind,
    FrontierStanding,
    OptimizationDirection,
    RepairLeverage,
    SelectionStrategy,
    TrialOutcome,
    TrialResult,
)
from .score import ScoreLaw
from .scoreboard import Scoreboard
from .space import CompatibilityRule, DecisionSpace, hamming_distance, pairwise_covering

__all__ = [
    "ArchitecturePoint",
    "BasisChoice",
    "BenchmarkScore",
    "BenchmarkTarget",
    "BudgetPolicy",
    "CompatibilityRule",
    "CompiledExperimentSet",
    "DecisionBasis",
    "DecisionSpace",
    "ExperimentBasis",
    "ExperimentCompiler",
    "ExperimentPlan",
    "FactorySnapshot",
    "FailureCluster",
    "FailureKind",
    "FailureRouter",
    "FrontierStanding",
    "LearningCompiler",
    "LearningSignal",
    "OptimizationDirection",
    "RepairLeverage",
    "SOTAFactory",
    "ScoreLaw",
    "Scoreboard",
    "SelectionStrategy",
    "TrialOutcome",
    "TrialResult",
    "hamming_distance",
    "pairwise_covering",
]
