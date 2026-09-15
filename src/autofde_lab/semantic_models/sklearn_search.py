"""scikit-learn/TPOT2 search over *candidate quality*, never semantic truth.

The search space is deliberately narrow. DfCM selects the lawful semantic universe first;
AutoML is allowed only to optimize prioritization/calibration inside that admitted frame.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import CandidateGraphDelta, OptimizationReceipt

FEATURE_NAMES = (
    "triple_count",
    "predicate_diversity",
    "known_predicate_ratio",
    "provenance_count",
    "confidence",
)


def candidate_features(
    candidate: CandidateGraphDelta,
    *,
    known_predicates: set[str] | frozenset[str],
) -> list[float]:
    predicates = [triple.predicate for triple in candidate.triples]
    known = sum(predicate in known_predicates for predicate in predicates)
    count = len(candidate.triples)
    return [
        float(count),
        float(len(set(predicates)) / count),
        float(known / count),
        float(len(set(candidate.source_iris))),
        float(candidate.confidence if candidate.confidence is not None else 0.5),
    ]


def feature_matrix(
    candidates: Iterable[CandidateGraphDelta],
    *,
    known_predicates: set[str] | frozenset[str],
) -> list[list[float]]:
    return [
        candidate_features(c, known_predicates=known_predicates) for c in candidates
    ]


MICRO_EXPORTABLE_CONFIG: dict[str, Any] = {
    "sklearn.linear_model.LogisticRegression": {
        "penalty": ["l2"],
        "C": [0.1, 1.0, 10.0],
        "solver": ["lbfgs"],
    },
    "sklearn.tree.DecisionTreeClassifier": {
        "max_depth": [2, 3, 4],
        "min_samples_split": [2, 5],
    },
    "sklearn.naive_bayes.ComplementNB": {
        "alpha": [0.1, 1.0],
    },
}


@dataclass(frozen=True)
class TPOTSearchConfig:
    """Bounded, deterministic TPOT2 search configuration."""

    search_space: str = "micro-exportable"
    scorer: str = "roc_auc"
    cv: int = 5
    max_time_mins: float = 10.0
    max_eval_time_mins: float = 2.0
    n_jobs: int = 1
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.search_space not in {"linear-light", "graph-light", "micro-exportable"}:
            raise ValueError(
                "semantic candidate search is restricted to TPOT light or micro-exportable search spaces"
            )


def build_tpot_classifier(config: TPOTSearchConfig | None = None):
    """Build current TPOT (formerly TPOT2) classifier with a bounded search space."""
    config = config or TPOTSearchConfig()
    try:
        import tpot
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise RuntimeError(
            "TPOT search requires the semantic-models extra (tpot, scikit-learn)"
        ) from exc

    return tpot.TPOTClassifier(
        search_space=config.search_space,
        scorers=[config.scorer],
        scorers_weights=[1.0],
        cv=config.cv,
        max_time_mins=config.max_time_mins,
        max_eval_time_mins=config.max_eval_time_mins,
        n_jobs=config.n_jobs,
        random_state=config.random_state,
        allow_inner_classifiers=False,
        verbose=2,
    )


def fit_tpot_candidate_ranker(
    candidates: Sequence[CandidateGraphDelta],
    labels: Sequence[int],
    *,
    known_predicates: set[str] | frozenset[str],
    config: TPOTSearchConfig | None = None,
):
    """Fit an AutoML ranker using receipt-derived labels.

    Labels describe historical admission/quality outcomes.  Predictions are advisory and
    are never consumed by SemanticAdmissionCourt as authority.
    """
    if len(candidates) != len(labels):
        raise ValueError("candidates and labels must have equal length")
    if len(set(labels)) < 2:
        raise ValueError("TPOT ranking requires at least two label classes")
    ranker = build_tpot_classifier(config)
    X = feature_matrix(candidates, known_predicates=known_predicates)
    ranker.fit(X, labels)
    return ranker


def build_sklearn_baseline(*, random_state: int = 42):
    """Cheap deterministic baseline used before spending a TPOT search budget."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise RuntimeError("baseline ranking requires scikit-learn") from exc

    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(max_iter=1000, random_state=random_state),
            ),
        ]
    )


def fit_and_receipt_baseline(
    candidates: Sequence[CandidateGraphDelta],
    labels: Sequence[int],
    *,
    known_predicates: set[str] | frozenset[str],
    dataset_hash: str,
    ontology_hash: str,
    random_state: int = 42,
) -> tuple[Any, OptimizationReceipt]:
    """Fit a deterministic sklearn baseline ranker and manufacture an immutable OptimizationReceipt."""
    pipeline = build_sklearn_baseline(random_state=random_state)
    X = feature_matrix(candidates, known_predicates=known_predicates)
    pipeline.fit(X, labels)

    # In-sample accuracy metric
    predictions = pipeline.predict(X)
    correct = sum(p == y for p, y in zip(predictions, labels, strict=False))
    accuracy = float(correct / len(labels)) if labels else 0.0

    pipe_dump = repr(pipeline)
    program_hash = hashlib.sha256(pipe_dump.encode("utf-8")).hexdigest()

    receipt = OptimizationReceipt.manufacture(
        dataset_hash=dataset_hash,
        ontology_hash=ontology_hash,
        optimizer_name="sklearn-logistic-baseline",
        optimizer_config={
            "scaler": "StandardScaler",
            "classifier": "LogisticRegression",
            "random_state": random_state,
        },
        metric_vector={"accuracy": accuracy, "sample_count": float(len(labels))},
        program_hash=program_hash,
        lm_identity="statistical_pipeline",
    )
    return pipeline, receipt
