"""Chicago-style courts for SA2A learned graph inference.

No mocks: the admission case uses the real AdmissionPipeline and the GraphSAGE
case uses real torch-geometric modules when that optional backend is installed.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from autofde_lab.sa2a.admission.pipeline import AdmissionPipeline
from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.graph_learning import (
    GraphSAGECandidateScorer,
    SemanticFeatureGraph,
    candidate_batch_from_scores,
)


def _feature_graph() -> SemanticFeatureGraph:
    return SemanticFeatureGraph(
        node_ids=(
            "urn:agent:a",
            "urn:agent:b",
            "urn:agent:c",
            "urn:agent:d",
        ),
        features=(
            (1.0, 0.0, 0.2),
            (0.8, 0.1, 0.4),
            (0.1, 0.9, 0.6),
            (0.0, 1.0, 0.8),
        ),
        edges=((0, 1), (1, 2), (2, 3)),
        source_graph_identity="sha256:rdf-canonical-example",
        feature_projection_identity="rdf-object-plus-datatype:v1",
    )


def test_candidate_manufacture_is_deterministic_and_authority_free() -> None:
    graph = _feature_graph()
    pairs = (
        ("urn:agent:a", "urn:agent:c"),
        ("urn:agent:a", "urn:agent:b"),
        ("urn:agent:d", "urn:agent:a"),
        ("urn:agent:a", "urn:agent:c"),
    )
    scores = (0.81, 0.99, 0.72, 0.87)

    first = candidate_batch_from_scores(
        graph=graph,
        model_identity="sha256:model-1",
        predicate="urn:sa2a:mayDelegateTo",
        pairs=pairs,
        scores=scores,
        top_k=2,
    )
    second = candidate_batch_from_scores(
        graph=graph,
        model_identity="sha256:model-1",
        predicate="urn:sa2a:mayDelegateTo",
        pairs=tuple(reversed(pairs)),
        scores=tuple(reversed(scores)),
        top_k=2,
    )

    # Existing a->b is excluded; duplicate a->c collapses to its maximum score.
    assert [(c.subject, c.object, c.score) for c in first.candidates] == [
        ("urn:agent:a", "urn:agent:c", 0.87),
        ("urn:agent:d", "urn:agent:a", 0.72),
    ]
    assert [c.candidate_identity for c in first.candidates] == [
        c.candidate_identity for c in second.candidates
    ]
    assert first.standing is Standing.CANDIDATE
    assert not first.authorizes_actuation
    assert all(c.standing is Standing.CANDIDATE for c in first.candidates)
    assert all(not c.authorizes_actuation for c in first.candidates)


def test_learned_candidate_requires_real_admission_before_admitted_standing() -> None:
    graph = _feature_graph()
    batch = candidate_batch_from_scores(
        graph=graph,
        model_identity="sha256:model-2",
        predicate="urn:sa2a:mayDelegateTo",
        pairs=(("urn:agent:a", "urn:agent:c"),),
        scores=(0.91,),
    )
    candidate = batch.candidates[0]

    assert candidate.standing is Standing.CANDIDATE
    assert not candidate.authorizes_actuation

    result = AdmissionPipeline().admit(
        candidate.as_rdflib_graph(),
        provenance_record={
            "issuer": "urn:agent:graph-learning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert result.is_admitted
    assert result.standing is Standing.ADMITTED
    assert candidate.standing is Standing.CANDIDATE
    assert not candidate.authorizes_actuation


def test_real_graphsage_replays_and_cannot_promote_standing() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")

    graph = _feature_graph()
    candidate_pairs = (
        ("urn:agent:a", "urn:agent:b"),  # observed and therefore excluded
        ("urn:agent:a", "urn:agent:c"),
        ("urn:agent:a", "urn:agent:d"),
        ("urn:agent:d", "urn:agent:b"),
    )

    first_model = GraphSAGECandidateScorer(
        graph.feature_dim,
        hidden_dim=5,
        output_dim=4,
        seed=17,
    )
    second_model = GraphSAGECandidateScorer(
        graph.feature_dim,
        hidden_dim=5,
        output_dim=4,
        seed=17,
    )

    first = first_model.propose(
        graph,
        predicate="urn:sa2a:mayDelegateTo",
        candidate_pairs=candidate_pairs,
        top_k=3,
    )
    second = second_model.propose(
        graph,
        predicate="urn:sa2a:mayDelegateTo",
        candidate_pairs=tuple(reversed(candidate_pairs)),
        top_k=3,
    )

    assert first_model.model_identity == second_model.model_identity
    assert [(c.subject, c.object, c.score) for c in first.candidates] == [
        (c.subject, c.object, c.score) for c in second.candidates
    ]
    assert ("urn:agent:a", "urn:agent:b") not in {
        (c.subject, c.object) for c in first.candidates
    }
    assert first.standing is Standing.CANDIDATE
    assert not first.authorizes_actuation
    assert all(c.standing is Standing.CANDIDATE for c in first.candidates)
    assert all(not c.authorizes_actuation for c in first.candidates)
