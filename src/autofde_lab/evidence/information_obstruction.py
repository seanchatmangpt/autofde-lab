"""Information-theoretic admission falsifier for decision systems.

If two admissible cases are indistinguishable under the permitted observation
interface but require disjoint accepted outputs, no decision procedure using
only that interface can be correct on both. This module turns that condition
into deterministic, model-agnostic evidence.

An evidence ceiling is a property of the observation topology, not evidence
that a planner, model, or human is insufficiently intelligent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical(item) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _canonical_payload(observation: Any) -> str:
    return json.dumps(
        _canonical(observation),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def observation_fingerprint(observation: Any) -> str:
    return hashlib.sha256(_canonical_payload(observation).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionCase:
    case_id: str
    observation: Any
    accepted_outputs: frozenset[str]


@dataclass(frozen=True, slots=True)
class InformationObstructionWitness:
    observation_fingerprint: str
    left_case_id: str
    right_case_id: str
    left_accepted_outputs: tuple[str, ...]
    right_accepted_outputs: tuple[str, ...]

    @property
    def refusal_code(self) -> str:
        return "EVIDENCE_CEILING"

    @property
    def reason(self) -> str:
        return (
            "permitted observations are identical while accepted output sets "
            "are disjoint"
        )


@dataclass(frozen=True, slots=True)
class ObservationClass:
    observation_fingerprint: str
    case_ids: tuple[str, ...]
    accepted_output_sets: tuple[tuple[str, ...], ...]

    @property
    def collision(self) -> bool:
        return len(self.case_ids) > 1


@dataclass(frozen=True, slots=True)
class InformationObstructionReport:
    case_count: int
    observation_class_count: int
    collision_class_count: int
    obstruction_count: int
    observation_classes: tuple[ObservationClass, ...]
    witnesses: tuple[InformationObstructionWitness, ...]

    @property
    def information_sufficient(self) -> bool:
        return self.obstruction_count == 0

    @property
    def standing(self) -> str:
        return "ADMITTED" if self.information_sufficient else "REFUSED(EVIDENCE_CEILING)"


class EvidenceCeilingError(ValueError):
    def __init__(self, witness: InformationObstructionWitness) -> None:
        self.witness = witness
        super().__init__(
            f"{witness.refusal_code}: {witness.left_case_id} and "
            f"{witness.right_case_id}: {witness.reason}"
        )


def _bucket_cases(
    cases: Iterable[DecisionCase],
) -> tuple[tuple[str, tuple[DecisionCase, ...]], ...]:
    buckets: dict[str, list[DecisionCase]] = {}
    for case in cases:
        if not case.case_id:
            raise ValueError("DECISION_CASE_ID_REQUIRED")
        if not case.accepted_outputs:
            raise ValueError(f"ACCEPTED_OUTPUTS_REQUIRED:{case.case_id}")
        canonical = _canonical_payload(case.observation)
        buckets.setdefault(canonical, []).append(case)
    return tuple((canonical, tuple(rows)) for canonical, rows in buckets.items())


def enumerate_information_obstructions(
    cases: Iterable[DecisionCase],
) -> tuple[InformationObstructionWitness, ...]:
    """Return every pairwise obstruction in stable corpus order.

    Exact canonical observation equality is the proof condition. SHA-256 is
    emitted only as witness identity.
    """
    witnesses: list[InformationObstructionWitness] = []
    for canonical, bucket in _bucket_cases(cases):
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        for left, right in combinations(bucket, 2):
            if left.accepted_outputs.isdisjoint(right.accepted_outputs):
                witnesses.append(
                    InformationObstructionWitness(
                        observation_fingerprint=fingerprint,
                        left_case_id=left.case_id,
                        right_case_id=right.case_id,
                        left_accepted_outputs=tuple(sorted(left.accepted_outputs)),
                        right_accepted_outputs=tuple(sorted(right.accepted_outputs)),
                    )
                )
    return tuple(witnesses)


def analyze_information_obstruction(
    cases: Iterable[DecisionCase],
) -> InformationObstructionReport:
    rows = tuple(cases)
    bucketed = _bucket_cases(rows)
    classes = tuple(
        ObservationClass(
            observation_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            case_ids=tuple(case.case_id for case in bucket),
            accepted_output_sets=tuple(
                tuple(sorted(case.accepted_outputs)) for case in bucket
            ),
        )
        for canonical, bucket in bucketed
    )
    witnesses = enumerate_information_obstructions(rows)
    return InformationObstructionReport(
        case_count=len(rows),
        observation_class_count=len(classes),
        collision_class_count=sum(int(group.collision) for group in classes),
        obstruction_count=len(witnesses),
        observation_classes=classes,
        witnesses=witnesses,
    )


def find_information_obstruction(
    cases: Iterable[DecisionCase],
) -> InformationObstructionWitness | None:
    witnesses = enumerate_information_obstructions(cases)
    return witnesses[0] if witnesses else None


def assert_information_sufficient(cases: Sequence[DecisionCase]) -> None:
    witness = find_information_obstruction(cases)
    if witness is not None:
        raise EvidenceCeilingError(witness)
