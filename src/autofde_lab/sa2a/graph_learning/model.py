"""Authority-fenced learned graph inference types for Semantic A2A.

The module deliberately separates learned inference from admission and authority:

    canonical RDF / semantic features
        -> learned scorer
        -> CandidateEdge(Standing.CANDIDATE)
        -> AdmissionPipeline
        -> ... -> BRCE

A score is evidence for exploration only. It is never admission, authority,
actuation, a receipt, or standing beyond CANDIDATE.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import isfinite
from typing import Sequence

from autofde_lab.sa2a.algebra import Standing


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SemanticFeatureGraph:
    """A model-ready projection bound to an external canonical semantic graph.

    source_graph_identity identifies the canonical RDF/semantic source.
    feature_projection_identity identifies the lawful feature transform
    (for example RDF object-property topology plus datatype-property features).
    The projection is not itself the source of semantic truth.
    """

    node_ids: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    edges: tuple[tuple[int, int], ...]
    source_graph_identity: str
    feature_projection_identity: str

    def __post_init__(self) -> None:
        if not self.node_ids:
            raise ValueError("SemanticFeatureGraph requires at least one node")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must be unique")
        if len(self.features) != len(self.node_ids):
            raise ValueError("features must align one-to-one with node_ids")
        if not self.source_graph_identity:
            raise ValueError("source_graph_identity is required")
        if not self.feature_projection_identity:
            raise ValueError("feature_projection_identity is required")

        dimensions = {len(vector) for vector in self.features}
        if len(dimensions) != 1 or not dimensions or 0 in dimensions:
            raise ValueError("all feature vectors must have one non-zero dimension")
        for vector in self.features:
            if not all(isfinite(float(value)) for value in vector):
                raise ValueError("features must contain only finite numeric values")

        node_count = len(self.node_ids)
        for source, target in self.edges:
            if source < 0 or target < 0 or source >= node_count or target >= node_count:
                raise ValueError(
                    f"edge ({source}, {target}) references node outside projection"
                )

    @property
    def feature_dim(self) -> int:
        return len(self.features[0])

    @property
    def observed_pairs(self) -> frozenset[tuple[str, str]]:
        return frozenset(
            (self.node_ids[source], self.node_ids[target])
            for source, target in self.edges
        )

    @property
    def projection_digest(self) -> str:
        """Digest of the model-ready projection, distinct from RDF identity."""
        return _digest(
            {
                "node_ids": self.node_ids,
                "features": self.features,
                "edges": self.edges,
                "source_graph_identity": self.source_graph_identity,
                "feature_projection_identity": self.feature_projection_identity,
            }
        )


@dataclass(frozen=True, slots=True)
class CandidateEdge:
    """A learned edge hypothesis with no ambient admission or authority."""

    subject: str
    predicate: str
    object: str
    score: float
    source_graph_identity: str
    feature_projection_identity: str
    model_identity: str
    standing: Standing = field(default=Standing.CANDIDATE, init=False)
    authorizes_actuation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.object:
            raise ValueError("subject, predicate, and object are required")
        if not self.source_graph_identity:
            raise ValueError("source_graph_identity is required")
        if not self.feature_projection_identity:
            raise ValueError("feature_projection_identity is required")
        if not self.model_identity:
            raise ValueError("model_identity is required")
        if not isfinite(float(self.score)) or not 0.0 <= float(self.score) <= 1.0:
            raise ValueError("score must be a finite probability in [0, 1]")

    @property
    def candidate_identity(self) -> str:
        return _digest(
            {
                "subject": self.subject,
                "predicate": self.predicate,
                "object": self.object,
                "score": float(self.score),
                "source_graph_identity": self.source_graph_identity,
                "feature_projection_identity": self.feature_projection_identity,
                "model_identity": self.model_identity,
                "standing": self.standing.value,
                "authorizes_actuation": self.authorizes_actuation,
            }
        )

    def as_rdflib_graph(self):
        """Project this hypothesis into a real RDF graph for SA2A admission.

        Import is intentionally lazy: graph-learning models may be inspected or
        constructed without importing the RDF stack. The returned graph remains
        a candidate until AdmissionPipeline admits it.
        """
        from rdflib import Graph, URIRef

        graph = Graph()
        graph.add((URIRef(self.subject), URIRef(self.predicate), URIRef(self.object)))
        return graph


@dataclass(frozen=True, slots=True)
class CandidateBatch:
    """Deterministically ranked hypotheses bound to model and graph identity."""

    source_graph_identity: str
    feature_projection_identity: str
    model_identity: str
    predicate: str
    candidates: tuple[CandidateEdge, ...]
    standing: Standing = field(default=Standing.CANDIDATE, init=False)
    authorizes_actuation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for candidate in self.candidates:
            if candidate.source_graph_identity != self.source_graph_identity:
                raise ValueError("candidate source graph identity does not match batch")
            if (
                candidate.feature_projection_identity
                != self.feature_projection_identity
            ):
                raise ValueError("candidate feature projection does not match batch")
            if candidate.model_identity != self.model_identity:
                raise ValueError("candidate model identity does not match batch")
            if candidate.predicate != self.predicate:
                raise ValueError("candidate predicate does not match batch")
            if candidate.standing is not Standing.CANDIDATE:
                raise ValueError("learned inference may only emit CANDIDATE standing")
            if candidate.authorizes_actuation:
                raise ValueError("learned inference may not authorize actuation")


def candidate_batch_from_scores(
    *,
    graph: SemanticFeatureGraph,
    model_identity: str,
    predicate: str,
    pairs: Sequence[tuple[str, str]],
    scores: Sequence[float],
    top_k: int | None = None,
    min_score: float = 0.0,
    exclude_observed: bool = True,
) -> CandidateBatch:
    """Convert learned scores into a deterministic, authority-free candidate batch."""

    if len(pairs) != len(scores):
        raise ValueError("pairs and scores must have equal length")
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be >= 1 when supplied")
    if not isfinite(float(min_score)) or not 0.0 <= float(min_score) <= 1.0:
        raise ValueError("min_score must be in [0, 1]")
    if not model_identity:
        raise ValueError("model_identity is required")
    if not predicate:
        raise ValueError("predicate is required")

    known_nodes = set(graph.node_ids)
    observed = graph.observed_pairs if exclude_observed else frozenset()

    # Collapse duplicate pair proposals by their maximum score, then sort by
    # score and semantic identity so replay is independent of caller order.
    deduped: dict[tuple[str, str], float] = {}
    for pair, raw_score in zip(pairs, scores, strict=True):
        subject, object_ = pair
        if subject not in known_nodes or object_ not in known_nodes:
            raise ValueError(f"candidate pair references unknown node: {pair!r}")
        score = float(raw_score)
        if not isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError("all scores must be finite probabilities in [0, 1]")
        if (subject, object_) in observed or score < min_score:
            continue
        previous = deduped.get((subject, object_))
        if previous is None or score > previous:
            deduped[(subject, object_)] = score

    ranked = sorted(
        deduped.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )
    if top_k is not None:
        ranked = ranked[:top_k]

    candidates = tuple(
        CandidateEdge(
            subject=subject,
            predicate=predicate,
            object=object_,
            score=score,
            source_graph_identity=graph.source_graph_identity,
            feature_projection_identity=graph.feature_projection_identity,
            model_identity=model_identity,
        )
        for (subject, object_), score in ranked
    )
    return CandidateBatch(
        source_graph_identity=graph.source_graph_identity,
        feature_projection_identity=graph.feature_projection_identity,
        model_identity=model_identity,
        predicate=predicate,
        candidates=candidates,
    )


__all__ = [
    "CandidateBatch",
    "CandidateEdge",
    "SemanticFeatureGraph",
    "candidate_batch_from_scores",
]
