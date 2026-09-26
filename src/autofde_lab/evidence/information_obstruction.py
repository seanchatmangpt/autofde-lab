"""Information-theoretic admission falsifier for decision systems.

If two admissible cases are indistinguishable under the permitted observation
interface but require disjoint accepted outputs, no decision procedure using
only that interface can be correct on both. This module turns that condition
into a deterministic preflight check.

The result is deliberately model-agnostic: an evidence ceiling is a property
of the observation topology, not evidence that a planner, model, or human is
insufficiently intelligent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


def _canonical(value: Any) -> Any:
    """Return a deterministic JSON-compatible projection of an observation."""
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
    """Content-address an exact permitted observation."""
    return hashlib.sha256(_canonical_payload(observation).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionCase:
    """One admissible case at a decision boundary."""

    case_id: str
    observation: Any
    accepted_outputs: frozenset[str]


@dataclass(frozen=True, slots=True)
class InformationObstructionWitness:
    """Minimal witness that the current observation interface is insufficient."""

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


class EvidenceCeilingError(ValueError):
    """Raised when a decision contract is impossible under the admitted inputs."""

    def __init__(self, witness: InformationObstructionWitness) -> None:
        self.witness = witness
        super().__init__(
            f"{witness.refusal_code}: {witness.left_case_id} and "
            f"{witness.right_case_id}: {witness.reason}"
        )


def find_information_obstruction(
    cases: Iterable[DecisionCase],
) -> InformationObstructionWitness | None:
    """Return the first deterministic obstruction witness, if one exists.

    For cases x1 and x2, the witness condition is:

        Obs(x1) == Obs(x2)
        and
        Accept(x1) intersection Accept(x2) == empty

    Equality is checked on the exact canonical observation payload. SHA-256 is
    emitted only as witness identity; hash equality is never used as proof that
    two observations are equal.
    """
    buckets: dict[str, list[DecisionCase]] = {}

    for case in cases:
        canonical = _canonical_payload(case.observation)
        bucket = buckets.setdefault(canonical, [])

        for prior in bucket:
            if prior.accepted_outputs.isdisjoint(case.accepted_outputs):
                return InformationObstructionWitness(
                    observation_fingerprint=hashlib.sha256(
                        canonical.encode("utf-8")
                    ).hexdigest(),
                    left_case_id=prior.case_id,
                    right_case_id=case.case_id,
                    left_accepted_outputs=tuple(sorted(prior.accepted_outputs)),
                    right_accepted_outputs=tuple(sorted(case.accepted_outputs)),
                )

        bucket.append(case)

    return None


def assert_information_sufficient(cases: Sequence[DecisionCase]) -> None:
    """Fail closed when the admitted interface cannot satisfy the contract."""
    witness = find_information_obstruction(cases)
    if witness is not None:
        raise EvidenceCeilingError(witness)
