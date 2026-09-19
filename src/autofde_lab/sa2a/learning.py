"""GALL-facing learning provenance and least-complex qualifying learner selection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from math import isfinite
from typing import Mapping, Sequence


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


class TrainingOrigin(StrEnum):
    GGEN_MANUFACTURED = "GGEN_MANUFACTURED"
    SOLVER_DERIVED = "SOLVER_DERIVED"
    SIMULATED = "SIMULATED"
    OBSERVED_RUNTIME = "OBSERVED_RUNTIME"


@dataclass(frozen=True, slots=True)
class TrainingExample:
    """One labeled example with explicit synthetic/runtime evidence provenance."""

    generator_identity: str
    source_ontology_identity: str
    graph_identity: str
    labeling_court: str
    court_version: str
    label_receipt: str
    origin: TrainingOrigin
    features: Mapping[str, object]
    label: object
    seed: int | None = None
    mutation_identity: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.generator_identity,
            self.source_ontology_identity,
            self.graph_identity,
            self.labeling_court,
            self.court_version,
            self.label_receipt,
        )
        if any(not item for item in required):
            raise ValueError("training example provenance identities are required")
        _digest(dict(self.features))
        _digest(self.label)

    @property
    def example_identity(self) -> str:
        return _digest(
            {
                "generator_identity": self.generator_identity,
                "source_ontology_identity": self.source_ontology_identity,
                "graph_identity": self.graph_identity,
                "labeling_court": self.labeling_court,
                "court_version": self.court_version,
                "label_receipt": self.label_receipt,
                "origin": self.origin.value,
                "features": dict(self.features),
                "label": self.label,
                "seed": self.seed,
                "mutation_identity": self.mutation_identity,
            }
        )


class LearnerTier(IntEnum):
    """Increasing computational complexity, not a quality ranking."""

    EXACT_LOOKUP = 0
    NEAREST_NEIGHBORS = 1
    LINEAR = 2
    TREE_ENSEMBLE = 3
    GRADIENT_BOOSTING = 4
    GNN = 5
    LLM = 6


@dataclass(frozen=True, slots=True)
class LearnerQualification:
    """GALL result for one learner on one exact qualification court."""

    tier: LearnerTier
    artifact_identity: str
    court_identity: str
    passed: bool
    utility_gain: float
    training_seconds: float
    inference_milliseconds: float
    formal_solution_preserved: bool

    def __post_init__(self) -> None:
        if not self.artifact_identity or not self.court_identity:
            raise ValueError("learner and court identities are required")
        for name, value in (
            ("utility_gain", self.utility_gain),
            ("training_seconds", self.training_seconds),
            ("inference_milliseconds", self.inference_milliseconds),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.training_seconds < 0 or self.inference_milliseconds < 0:
            raise ValueError("training and inference time must be non-negative")


def select_least_complex_qualifying(
    results: Sequence[LearnerQualification],
    *,
    minimum_utility_gain: float = 0.0,
) -> LearnerQualification | None:
    """Select minimum complexity only among courts preserving formal correctness."""

    if not isfinite(float(minimum_utility_gain)):
        raise ValueError("minimum_utility_gain must be finite")

    qualifying = [
        result
        for result in results
        if result.passed
        and result.formal_solution_preserved
        and result.utility_gain >= minimum_utility_gain
    ]
    if not qualifying:
        return None

    return min(
        qualifying,
        key=lambda result: (
            int(result.tier),
            result.inference_milliseconds,
            result.training_seconds,
            result.artifact_identity,
        ),
    )


__all__ = [
    "LearnerQualification",
    "LearnerTier",
    "TrainingExample",
    "TrainingOrigin",
    "select_least_complex_qualifying",
]
