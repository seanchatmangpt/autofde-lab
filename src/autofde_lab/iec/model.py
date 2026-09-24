"""Core immutable contracts for the Inverse Ecosystem Compiler.

These types are evidence carriers, not authority objects. No value here grants
external BRCE DO authority or production standing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class EvidenceKind(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED_DETERMINISTIC = "DERIVED_DETERMINISTIC"
    INFERRED_CANDIDATE = "INFERRED_CANDIDATE"
    ADMITTED = "ADMITTED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class Standing(str, Enum):
    OBSERVED = "OBSERVED"
    CANDIDATE = "CANDIDATE"
    ADMITTED = "ADMITTED"
    MANUFACTURED = "MANUFACTURED"
    VERIFIED = "VERIFIED"
    REPLAYABLE = "REPLAYABLE"
    PROMOTABLE = "PROMOTABLE"
    REFUSED = "REFUSED"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    BUILD_BROKEN = "BUILD_BROKEN"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class ArtifactClass(str, Enum):
    CANONICAL_SOURCE = "CANONICAL_SOURCE"
    GENERATED_PROJECTION = "GENERATED_PROJECTION"
    DERIVED_CACHE = "DERIVED_CACHE"
    HANDWRITTEN_IRREDUCIBLE = "HANDWRITTEN_IRREDUCIBLE"
    HISTORICAL_RESIDUE = "HISTORICAL_RESIDUE"
    EXTERNAL_VENDORED = "EXTERNAL_VENDORED"
    UNKNOWN = "UNKNOWN"


class EquivalenceDimension(str, Enum):
    IDENTITY = "identity"
    INTERFACE = "interface"
    SYNTAX = "syntax"
    BUILD = "build"
    TEST = "test"
    RUNTIME_BEHAVIOR = "runtime_behavior"
    PROTOCOL = "protocol"
    AUTHORITY = "authority"
    RECEIPT = "receipt"
    REPLAY = "replay"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    DOCUMENTATION = "documentation"


class ClaimCeiling(str, Enum):
    STRUCTURAL_EQUIVALENCE_ONLY = "STRUCTURAL_EQUIVALENCE_ONLY"
    BUILD_AND_TEST_EQUIVALENCE_ONLY = "BUILD_AND_TEST_EQUIVALENCE_ONLY"
    BOUNDED_RUNTIME_EQUIVALENCE_ONLY = "BOUNDED_RUNTIME_EQUIVALENCE_ONLY"
    AUTHORITY_MODEL_EQUIVALENCE_ONLY = "AUTHORITY_MODEL_EQUIVALENCE_ONLY"
    TRANSLATION_VALIDATED_FOR_EXACT_SUBJECT = "TRANSLATION_VALIDATED_FOR_EXACT_SUBJECT"


class FailureKind(str, Enum):
    BLOCKED_CORPUS_IDENTITY = "BLOCKED_CORPUS_IDENTITY"
    BLOCKED_MISSING_PARSER = "BLOCKED_MISSING_PARSER"
    BLOCKED_EXECUTION_AUTHORITY = "BLOCKED_EXECUTION_AUTHORITY"
    BLOCKED_VERIFIER_UNAVAILABLE = "BLOCKED_VERIFIER_UNAVAILABLE"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    UNSUPPORTED_GENERATOR_CAPABILITY = "UNSUPPORTED_GENERATOR_CAPABILITY"
    UNSUPPORTED_EQUIVALENCE_DIMENSION = "UNSUPPORTED_EQUIVALENCE_DIMENSION"
    UNSUPPORTED_RUNTIME_PROBE = "UNSUPPORTED_RUNTIME_PROBE"
    REFUSED_PRIVATE_IDENTITY_LEAK = "REFUSED_PRIVATE_IDENTITY_LEAK"
    REFUSED_PATH_ESCAPE = "REFUSED_PATH_ESCAPE"
    REFUSED_SYMLINK = "REFUSED_SYMLINK"
    REFUSED_AMBIGUOUS_AUTHORITY = "REFUSED_AMBIGUOUS_AUTHORITY"
    REFUSED_UNBOUNDED_EQUIVALENCE = "REFUSED_UNBOUNDED_EQUIVALENCE"
    REFUSED_DISPOSITION_WITHOUT_REPLACEMENT = "REFUSED_DISPOSITION_WITHOUT_REPLACEMENT"
    BUILD_BROKEN_GENERATED_SUBJECT = "BUILD_BROKEN_GENERATED_SUBJECT"
    COUNTEREXAMPLE_EQUIVALENCE = "COUNTEREXAMPLE_EQUIVALENCE"
    CONTRADICTED_SEMANTIC_FACT = "CONTRADICTED_SEMANTIC_FACT"
    UNKNOWN_ORIGIN = "UNKNOWN_ORIGIN"
    UNKNOWN_GENERATOR = "UNKNOWN_GENERATOR"
    UNKNOWN_CONSUMER = "UNKNOWN_CONSUMER"
    UNKNOWN_RUNTIME_BEHAVIOR = "UNKNOWN_RUNTIME_BEHAVIOR"


def _stable_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _canonical(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=_stable_sort_key)
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def require_nonempty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class RepositorySubject:
    repository: str
    revision: str
    default_branch: str
    visibility: str = "public"
    tree_digest: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "repository", require_nonempty(self.repository, "repository")
        )
        object.__setattr__(
            self, "revision", require_nonempty(self.revision, "revision")
        )
        object.__setattr__(
            self,
            "default_branch",
            require_nonempty(self.default_branch, "default_branch"),
        )
        if self.visibility not in {"public", "private", "internal"}:
            raise ValueError(f"unsupported visibility: {self.visibility}")

    @property
    def subject_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class Provenance:
    subject_id: str
    path: str
    extractor: str
    extractor_version: str = "1"
    source_digest: str | None = None
    span: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        for name in ("subject_id", "path", "extractor", "extractor_version"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), name))
        if self.span is not None:
            start, end = self.span
            if start < 0 or end < start:
                raise ValueError("span must satisfy 0 <= start <= end")


@dataclass(frozen=True, slots=True)
class Observation:
    predicate: str
    value: Any
    provenance: Provenance
    evidence_kind: EvidenceKind = EvidenceKind.OBSERVED
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "predicate", require_nonempty(self.predicate, "predicate")
        )
        if self.evidence_kind not in {
            EvidenceKind.OBSERVED,
            EvidenceKind.DERIVED_DETERMINISTIC,
        }:
            raise ValueError(
                "Observation may only carry OBSERVED or DERIVED_DETERMINISTIC evidence"
            )

    @property
    def observation_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class SemanticClaim:
    subject: str
    predicate: str
    object: str
    evidence_kind: EvidenceKind
    evidence_ids: tuple[str, ...]
    exclusions: tuple[str, ...] = ()
    falsifier: str | None = None

    def __post_init__(self) -> None:
        for name in ("subject", "predicate", "object"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), name))
        if not self.evidence_ids:
            raise ValueError("SemanticClaim requires at least one evidence id")
        if self.evidence_kind is EvidenceKind.ADMITTED and self.falsifier is None:
            raise ValueError("admitted claim requires a named falsifier")

    @property
    def claim_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class Counterexample:
    hypothesis_id: str
    dimension: EquivalenceDimension
    verifier_id: str
    expected: Any
    actual: Any
    detail: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "verifier_id", "detail"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), name))

    @property
    def counterexample_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class TranslationValidation:
    original_subject_id: str
    generated_subject_id: str
    verifier_set_id: str
    dimensions: tuple[EquivalenceDimension, ...]
    claim_ceiling: ClaimCeiling
    passed: bool
    counterexamples: tuple[Counterexample, ...] = ()
    verifier_receipts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("original_subject_id", "generated_subject_id", "verifier_set_id"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), name))
        if not self.dimensions:
            raise ValueError("translation validation requires at least one dimension")
        if self.passed and self.counterexamples:
            raise ValueError("passing validation cannot contain counterexamples")
        if not self.passed and not self.counterexamples:
            raise ValueError("failed validation requires a counterexample")

    @property
    def validation_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class Failure:
    kind: FailureKind
    detail: str
    subject_id: str | None = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", require_nonempty(self.detail, "detail"))

    @property
    def failure_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    subject_id: str
    path: str
    artifact_class: ArtifactClass
    content_digest: str
    producer: str | None = None
    evidence_ids: tuple[str, ...] = ()
    unknown_reason: str | None = None

    def __post_init__(self) -> None:
        for name in ("subject_id", "path", "content_digest"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), name))
        if (
            self.artifact_class is ArtifactClass.GENERATED_PROJECTION
            and not self.producer
        ):
            raise ValueError("generated projection requires producer")
        if self.artifact_class is ArtifactClass.UNKNOWN and not self.unknown_reason:
            raise ValueError("UNKNOWN artifact requires unknown_reason")


def aggregate_digest(items: Iterable[Any]) -> str:
    return digest(sorted(digest(item) for item in items))


def ensure_unique(values: Sequence[str], *, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label} identity")
