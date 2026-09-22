"""Semantic graph-learning projection for SA2A.

Learned models may propose graph edges for exploration. They never acquire
admission, authority, receipt, or actuation semantics from this package.
"""

from autofde_lab.sa2a.graph_learning.model import (
    CandidateBatch,
    CandidateEdge,
    SemanticFeatureGraph,
    candidate_batch_from_scores,
)
from autofde_lab.sa2a.graph_learning.torch_geometric import (
    GraphLearningBackendUnavailable,
    GraphSAGECandidateScorer,
)

__all__ = [
    "CandidateBatch",
    "CandidateEdge",
    "GraphLearningBackendUnavailable",
    "GraphSAGECandidateScorer",
    "SemanticFeatureGraph",
    "candidate_batch_from_scores",
]
