"""Universal computation boundary for Semantic A2A.

The producer may be an ONNX model, GNN, sklearn estimator, Nx/Axon model,
LLM, symbolic planner, query engine, rule engine, ordinary function, or
human.  This module deliberately normalizes only semantic identity and
planning advice.  It does not grant admission, authority, actuation,
receipt, or standing beyond CANDIDATE.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence

from autofde_lab.sa2a.algebra import Standing


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ComputationRuntime(str, Enum):
    ONNX = "ONNX"
    NX = "NX"
    AXON = "AXON"
    PYTORCH = "PYTORCH"
    SCIKIT_LEARN = "SCIKIT_LEARN"
    LLM = "LLM"
    RULE = "RULE"
    SPARQL = "SPARQL"
    FOND = "FOND"
    HDDL = "HDDL"
    NATIVE = "NATIVE"
    WASM = "WASM"
    HUMAN = "HUMAN"


class EvidenceClass(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    PROVEN = "PROVEN"
    INFERRED = "INFERRED"
    GENERATED = "GENERATED"
    HUMAN_ASSERTED = "HUMAN_ASSERTED"


class PlanningAdviceKind(str, Enum):
    FRONTIER = "FRONTIER"
    STATE_HEURISTIC = "STATE_HEURISTIC"
    ACTION_ORDER = "ACTION_ORDER"
    METHOD_ORDER = "METHOD_ORDER"
    BINDING_ORDER = "BINDING_ORDER"
    OUTCOME = "OUTCOME"
    REPAIR = "REPAIR"
    CONSEQUENCE = "CONSEQUENCE"
    EXPERIENCE = "EXPERIENCE"


@dataclass(frozen=True, slots=True)
class ComputationArtifact:
    """Portable producer identity.  Capability is stable across runtimes."""

    artifact_identity: str
    capability_iri: str
    runtime: ComputationRuntime
    input_schema_identity: str
    output_schema_identity: str
    input_projection_identity: str
    deterministic: bool
    training_corpus_identity: str | None = None
    calibration_identity: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.artifact_identity,
            self.capability_iri,
            self.input_schema_identity,
            self.output_schema_identity,
            self.input_projection_identity,
        )
        if any(not value for value in required):
            raise ValueError("computation artifact identities are required")

    @property
    def descriptor_identity(self) -> str:
        return _digest(
            {
                "artifact_identity": self.artifact_identity,
                "capability_iri": self.capability_iri,
                "runtime": self.runtime.value,
                "input_schema_identity": self.input_schema_identity,
                "output_schema_identity": self.output_schema_identity,
                "input_projection_identity": self.input_projection_identity,
                "deterministic": self.deterministic,
                "training_corpus_identity": self.training_corpus_identity,
                "calibration_identity": self.calibration_identity,
            }
        )


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    """Typed producer output that is powerless until separately admitted."""

    subject_identity: str
    predicate_iri: str
    value: object
    artifact: ComputationArtifact
    evidence_class: EvidenceClass
    standing: Standing = field(default=Standing.CANDIDATE, init=False)
    authorizes_actuation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.subject_identity or not self.predicate_iri:
            raise ValueError("claim subject and predicate are required")
        # Fail early if a producer attempts to emit a non-canonical payload.
        _digest(self.value)

    @property
    def claim_identity(self) -> str:
        return _digest(
            {
                "subject_identity": self.subject_identity,
                "predicate_iri": self.predicate_iri,
                "value": self.value,
                "artifact_identity": self.artifact.artifact_identity,
                "artifact_descriptor_identity": self.artifact.descriptor_identity,
                "evidence_class": self.evidence_class.value,
                "standing": self.standing.value,
                "authorizes_actuation": self.authorizes_actuation,
            }
        )


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate_ref: str
    score: float

    def __post_init__(self) -> None:
        if not self.candidate_ref:
            raise ValueError("candidate_ref is required")
        if not isfinite(float(self.score)):
            raise ValueError("candidate score must be finite")


@dataclass(frozen=True, slots=True)
class PlanningAdvice:
    """Model guidance bound to an exact formal planning subject.

    Advice may reorder formally admitted candidates.  It cannot make a candidate
    applicable, remove an admitted candidate, or carry authority.
    """

    planning_subject_identity: str
    formal_projection_identity: str
    artifact: ComputationArtifact
    kind: PlanningAdviceKind
    candidates: tuple[ScoredCandidate, ...]
    evidence_class: EvidenceClass = EvidenceClass.INFERRED
    standing: Standing = field(default=Standing.CANDIDATE, init=False)
    authorizes_actuation: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.planning_subject_identity:
            raise ValueError("planning_subject_identity is required")
        if not self.formal_projection_identity:
            raise ValueError("formal_projection_identity is required")
        refs = tuple(candidate.candidate_ref for candidate in self.candidates)
        if len(refs) != len(set(refs)):
            raise ValueError("planning advice candidate refs must be unique")

    @property
    def advice_identity(self) -> str:
        return _digest(
            {
                "planning_subject_identity": self.planning_subject_identity,
                "formal_projection_identity": self.formal_projection_identity,
                "artifact_descriptor_identity": self.artifact.descriptor_identity,
                "kind": self.kind.value,
                "candidates": [
                    {"candidate_ref": item.candidate_ref, "score": float(item.score)}
                    for item in self.candidates
                ],
                "evidence_class": self.evidence_class.value,
                "standing": self.standing.value,
                "authorizes_actuation": self.authorizes_actuation,
            }
        )


def order_formally_admitted(
    advice: PlanningAdvice,
    admitted_refs: Sequence[str],
) -> tuple[str, ...]:
    """Use learned advice only as an ordering hint over a formal candidate set.

    Every admitted candidate remains present exactly once.  Advice for an unknown
    candidate is ignored rather than allowing the producer to enlarge the formal
    action/method set.
    """

    admitted = tuple(admitted_refs)
    if len(admitted) != len(set(admitted)):
        raise ValueError("formal admitted refs must be unique")
    admitted_set = set(admitted)
    ranked = tuple(
        candidate.candidate_ref
        for candidate in sorted(
            advice.candidates,
            key=lambda item: (-float(item.score), item.candidate_ref),
        )
        if candidate.candidate_ref in admitted_set
    )
    ranked_set = set(ranked)
    return (*ranked, *(ref for ref in admitted if ref not in ranked_set))


@dataclass(frozen=True, slots=True)
class RuntimeEquivalence:
    passed: bool
    max_abs_error: float
    ranking_equal: bool
    reason: str


def qualify_runtime_equivalence(
    reference: Mapping[str, float],
    candidate: Mapping[str, float],
    *,
    tolerance: float = 1e-6,
) -> RuntimeEquivalence:
    """Qualify transport/runtime portability without promoting semantic standing."""

    if tolerance < 0 or not isfinite(float(tolerance)):
        raise ValueError("tolerance must be a finite non-negative number")
    if set(reference) != set(candidate):
        return RuntimeEquivalence(
            passed=False,
            max_abs_error=float("inf"),
            ranking_equal=False,
            reason="OUTPUT_KEY_SET_MISMATCH",
        )
    if not reference:
        return RuntimeEquivalence(
            passed=True,
            max_abs_error=0.0,
            ranking_equal=True,
            reason="EMPTY_OUTPUTS_EQUIVALENT",
        )

    errors = []
    for key in reference:
        left = float(reference[key])
        right = float(candidate[key])
        if not isfinite(left) or not isfinite(right):
            raise ValueError("runtime outputs must be finite")
        errors.append(abs(left - right))

    def ranking(values: Mapping[str, float]) -> tuple[str, ...]:
        return tuple(sorted(values, key=lambda key: (-float(values[key]), key)))

    max_error = max(errors)
    ranking_equal = ranking(reference) == ranking(candidate)
    passed = max_error <= tolerance and ranking_equal
    return RuntimeEquivalence(
        passed=passed,
        max_abs_error=max_error,
        ranking_equal=ranking_equal,
        reason="RUNTIME_EQUIVALENT" if passed else "RUNTIME_OUTPUT_DRIFT",
    )


__all__ = [
    "ComputationArtifact",
    "ComputationRuntime",
    "EvidenceClass",
    "PlanningAdvice",
    "PlanningAdviceKind",
    "RuntimeEquivalence",
    "ScoredCandidate",
    "SemanticClaim",
    "order_formally_admitted",
    "qualify_runtime_equivalence",
]
