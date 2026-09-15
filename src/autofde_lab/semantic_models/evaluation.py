"""Semantic evaluation objectives for DSPy, sklearn and TPOT search."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CandidateGraphDelta


@dataclass(frozen=True)
class EvaluationWeights:
    graph_exactness: float = 0.25
    shacl_pass: float = 0.20
    provenance: float = 0.20
    recall: float = 0.20
    unsupported_penalty: float = 0.15


@dataclass(frozen=True)
class SemanticEvaluation:
    precision: float
    recall: float
    f1: float
    graph_exactness: float
    provenance_coverage: float
    unsupported_rate: float
    shacl_conforms: bool
    score: float


def _keys(candidate: CandidateGraphDelta) -> set[tuple[str, str, str, str, str, str]]:
    return {triple.canonical_key() for triple in candidate.triples}


def evaluate_candidate(
    predicted: CandidateGraphDelta,
    expected: CandidateGraphDelta,
    *,
    known_predicates: set[str] | frozenset[str],
    shacl_conforms: bool,
    weights: EvaluationWeights | None = None,
) -> SemanticEvaluation:
    """Evaluate candidate semantics without granting standing."""

    weights = weights or EvaluationWeights()
    pred = _keys(predicted)
    gold = _keys(expected)
    true_positive = len(pred & gold)
    precision = true_positive / len(pred) if pred else 0.0
    recall = true_positive / len(gold) if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    graph_exactness = 1.0 if pred == gold else 0.0
    provenance_coverage = 1.0 if predicted.source_iris else 0.0
    unsupported_count = sum(
        1 for triple in predicted.triples if triple.predicate not in known_predicates
    )
    unsupported_rate = unsupported_count / len(predicted.triples)
    score = (
        weights.graph_exactness * graph_exactness
        + weights.shacl_pass * float(shacl_conforms)
        + weights.provenance * provenance_coverage
        + weights.recall * recall
        - weights.unsupported_penalty * unsupported_rate
    )
    return SemanticEvaluation(
        precision=precision,
        recall=recall,
        f1=f1,
        graph_exactness=graph_exactness,
        provenance_coverage=provenance_coverage,
        unsupported_rate=unsupported_rate,
        shacl_conforms=shacl_conforms,
        score=score,
    )


def make_dspy_metric(*, known_predicates: set[str] | frozenset[str]):
    """Return a DSPy-compatible metric over examples containing expected_delta JSON.

    DSPy stays an optional boundary: importing this module never imports DSPy.
    """

    def metric(example, prediction, trace=None) -> float:
        expected = CandidateGraphDelta.model_validate_json(example.expected_delta_json)
        predicted = CandidateGraphDelta.model_validate_json(
            prediction.candidate_delta_json
        )
        evaluation = evaluate_candidate(
            predicted,
            expected,
            known_predicates=known_predicates,
            shacl_conforms=True,
        )
        return evaluation.score

    return metric
