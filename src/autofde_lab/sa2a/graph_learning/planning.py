"""Planning-advice projection for authority-fenced graph learning."""

from __future__ import annotations

from autofde_lab.sa2a.computation import (
    ComputationArtifact,
    ComputationRuntime,
    EvidenceClass,
    PlanningAdvice,
    PlanningAdviceKind,
    ScoredCandidate,
)
from autofde_lab.sa2a.graph_learning.model import CandidateBatch


def candidate_batch_to_planning_advice(
    batch: CandidateBatch,
    *,
    planning_subject_identity: str,
    formal_projection_identity: str,
    kind: PlanningAdviceKind = PlanningAdviceKind.FRONTIER,
) -> PlanningAdvice:
    """Project GNN edge hypotheses into the universal powerless advice contract."""

    artifact = ComputationArtifact(
        artifact_identity=batch.model_identity,
        capability_iri="https://schema.org/Action",
        runtime=ComputationRuntime.PYTORCH,
        input_schema_identity="urn:sa2a:semantic-feature-graph",
        output_schema_identity="urn:sa2a:candidate-edge-batch",
        input_projection_identity=batch.feature_projection_identity,
        deterministic=True,
    )
    return PlanningAdvice(
        planning_subject_identity=planning_subject_identity,
        formal_projection_identity=formal_projection_identity,
        artifact=artifact,
        kind=kind,
        candidates=tuple(
            ScoredCandidate(
                candidate_ref=candidate.candidate_identity,
                score=candidate.score,
            )
            for candidate in batch.candidates
        ),
        evidence_class=EvidenceClass.INFERRED,
    )


__all__ = ["candidate_batch_to_planning_advice"]
