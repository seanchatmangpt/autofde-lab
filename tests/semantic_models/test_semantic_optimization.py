from __future__ import annotations

import pytest

from autofde_lab.semantic_models.contracts import CandidateGraphDelta, SemanticTriple
from autofde_lab.semantic_models.evaluation import evaluate_candidate
from autofde_lab.semantic_models.sklearn_search import (
    TPOTSearchConfig,
    candidate_features,
)

P = "urn:test:p"


def delta(*, predicate: str = P, confidence: float = 0.8) -> CandidateGraphDelta:
    return CandidateGraphDelta(
        observation_id="urn:o:1",
        triples=(SemanticTriple(subject="urn:s", predicate=predicate, object="urn:o"),),
        source_iris=("urn:source:1",),
        generator_id="unit-test",
        confidence=confidence,
    )


def test_exact_semantics_outscore_unsupported_semantics() -> None:
    expected = delta()
    exact = evaluate_candidate(
        expected,
        expected,
        known_predicates={P},
        shacl_conforms=True,
    )
    unsupported = evaluate_candidate(
        delta(predicate="urn:test:invented"),
        expected,
        known_predicates={P},
        shacl_conforms=False,
    )

    assert exact.graph_exactness == 1.0
    assert exact.unsupported_rate == 0.0
    assert exact.score > unsupported.score


def test_candidate_features_are_fixed_width_and_deterministic() -> None:
    features = candidate_features(delta(), known_predicates={P})
    assert features == [1.0, 1.0, 1.0, 1.0, 0.8]


def test_tpot_search_space_is_fail_closed_to_light_templates() -> None:
    assert TPOTSearchConfig(search_space="linear-light").random_state == 42
    with pytest.raises(ValueError, match="restricted"):
        TPOTSearchConfig(search_space="graph")
