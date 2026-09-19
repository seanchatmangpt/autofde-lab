"""Courts for the universal SA2A computation boundary."""

from __future__ import annotations

import pytest

from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.computation import (
    ComputationArtifact,
    ComputationRuntime,
    EvidenceClass,
    PlanningAdvice,
    PlanningAdviceKind,
    ScoredCandidate,
    SemanticClaim,
    order_formally_admitted,
    qualify_runtime_equivalence,
)
from autofde_lab.sa2a.graph_learning import (
    SemanticFeatureGraph,
    candidate_batch_from_scores,
    candidate_batch_to_planning_advice,
)


def _artifact(runtime: ComputationRuntime = ComputationRuntime.ONNX) -> ComputationArtifact:
    return ComputationArtifact(
        artifact_identity="sha256:model",
        capability_iri="https://schema.org/Action",
        runtime=runtime,
        input_schema_identity="sha256:input-schema",
        output_schema_identity="sha256:output-schema",
        input_projection_identity="sha256:rdf-planning-projection",
        deterministic=True,
        training_corpus_identity="sha256:ggen-corpus",
        calibration_identity="sha256:calibration",
    )


def test_any_computation_becomes_a_powerless_typed_claim() -> None:
    claim = SemanticClaim(
        subject_identity="sha256:planning-subject",
        predicate_iri="https://schema.org/value",
        value={"candidate": "rollback", "score": 0.91},
        artifact=_artifact(),
        evidence_class=EvidenceClass.INFERRED,
    )

    assert claim.standing is Standing.CANDIDATE
    assert not claim.authorizes_actuation
    assert len(claim.claim_identity) == 64


def test_model_advice_can_reorder_but_not_prune_or_enlarge_formal_frontier() -> None:
    advice = PlanningAdvice(
        planning_subject_identity="sha256:planning-subject",
        formal_projection_identity="sha256:hddl-projection",
        artifact=_artifact(),
        kind=PlanningAdviceKind.METHOD_ORDER,
        candidates=(
            ScoredCandidate(candidate_ref="failover", score=0.72),
            ScoredCandidate(candidate_ref="not-formally-applicable", score=0.99),
            ScoredCandidate(candidate_ref="rollback", score=0.91),
        ),
    )

    ordered = order_formally_admitted(
        advice,
        ("restart", "rollback", "failover", "scale-out"),
    )

    assert ordered == ("rollback", "failover", "restart", "scale-out")
    assert set(ordered) == {"restart", "rollback", "failover", "scale-out"}
    assert "not-formally-applicable" not in ordered
    assert advice.standing is Standing.CANDIDATE
    assert not advice.authorizes_actuation


def test_graphsage_candidates_project_into_same_universal_advice_contract() -> None:
    graph = SemanticFeatureGraph(
        node_ids=("urn:a", "urn:b", "urn:c"),
        features=((1.0, 0.0), (0.5, 0.5), (0.0, 1.0)),
        edges=((0, 1),),
        source_graph_identity="sha256:rdf",
        feature_projection_identity="sha256:features",
    )
    batch = candidate_batch_from_scores(
        graph=graph,
        model_identity="sha256:graphsage",
        predicate="urn:mayUse",
        pairs=(("urn:a", "urn:c"),),
        scores=(0.88,),
    )

    advice = candidate_batch_to_planning_advice(
        batch,
        planning_subject_identity="sha256:subject",
        formal_projection_identity="sha256:fond-hddl",
        kind=PlanningAdviceKind.FRONTIER,
    )

    assert advice.artifact.runtime is ComputationRuntime.PYTORCH
    assert advice.artifact.artifact_identity == "sha256:graphsage"
    assert advice.candidates[0].candidate_ref == batch.candidates[0].candidate_identity
    assert advice.standing is Standing.CANDIDATE
    assert not advice.authorizes_actuation


def test_duplicate_formal_or_model_candidates_fail_closed() -> None:
    with pytest.raises(ValueError, match="candidate refs must be unique"):
        PlanningAdvice(
            planning_subject_identity="sha256:subject",
            formal_projection_identity="sha256:fond",
            artifact=_artifact(),
            kind=PlanningAdviceKind.ACTION_ORDER,
            candidates=(
                ScoredCandidate(candidate_ref="a", score=1.0),
                ScoredCandidate(candidate_ref="a", score=0.5),
            ),
        )

    advice = PlanningAdvice(
        planning_subject_identity="sha256:subject",
        formal_projection_identity="sha256:fond",
        artifact=_artifact(),
        kind=PlanningAdviceKind.ACTION_ORDER,
        candidates=(),
    )
    with pytest.raises(ValueError, match="formal admitted refs must be unique"):
        order_formally_admitted(advice, ("a", "a"))


def test_onnx_or_nx_transport_must_preserve_outputs_and_ranking() -> None:
    equivalent = qualify_runtime_equivalence(
        {"rollback": 0.9000000, "failover": 0.7000000},
        {"rollback": 0.9000001, "failover": 0.6999999},
        tolerance=1e-5,
    )
    assert equivalent.passed
    assert equivalent.ranking_equal

    drifted = qualify_runtime_equivalence(
        {"rollback": 0.51, "failover": 0.50},
        {"rollback": 0.49, "failover": 0.52},
        tolerance=0.05,
    )
    assert not drifted.passed
    assert not drifted.ranking_equal
    assert drifted.reason == "RUNTIME_OUTPUT_DRIFT"


def test_runtime_identity_is_part_of_artifact_descriptor() -> None:
    onnx = _artifact(ComputationRuntime.ONNX)
    nx = _artifact(ComputationRuntime.NX)

    assert onnx.descriptor_identity != nx.descriptor_identity
