"""scikit-learn/TPOT2 search over *candidate quality*, never semantic truth.

The search space is deliberately narrow. DfCM selects the lawful semantic universe first;
AutoML is allowed only to optimize prioritization/calibration inside that admitted frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .contracts import CandidateGraphDelta

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
    return [candidate_features(c, known_predicates=known_predicates) for c in candidates]


@dataclass(frozen=True)
class TPOTSearchConfig:
    """Bounded, deterministic TPOT2 search configuration."""

    search_space: str = "linear-light"
    scorer: str = "roc_auc"
    cv: int = 5
    max_time_mins: float = 10.0
    max_eval_time_mins: float = 2.0
    n_jobs: int = 1
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.search_space not in {"linear-light", "graph-light"}:
            raise ValueError(
                "semantic candidate search is restricted to TPOT light search spaces"
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
