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


class ObservationProjectionError(TypeError):
    """Raised when an observation has no exact, injective canonical projection.

    Refusal codes:
    - OBSERVATION_KEY_COLLISION: two distinct mapping keys project to the same
      string key, so the projection would silently drop information.
    - OBSERVATION_UNSUPPORTED_TYPE: a value is not JSON-native (or a set/tuple
      of JSON-native values); repr() is not an exact identity, so equality of
      such observations cannot be proven.
    """

    def __init__(self, refusal_code: str, detail: str) -> None:
        self.refusal_code = refusal_code
        super().__init__(f"{refusal_code}: {detail}")


_KEY_TAG = "\u0000"


def _canonical(value: Any) -> Any:
    """Return a deterministic, injective JSON projection of an observation.

    Fails closed instead of collapsing distinct observations: a false
    equality would manufacture a false EVIDENCE_CEILING witness.
    """
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)) and key is not None:
                raise ObservationProjectionError(
                    "OBSERVATION_UNSUPPORTED_TYPE",
                    f"mapping key of type {type(key).__name__}",
                )
            # Type-tag non-str keys (and escape str keys that could mimic a
            # tag) so {1: v} and {"1": v} project to different payloads.
            if isinstance(key, str) and not key.startswith(_KEY_TAG):
                name = key
            else:
                name = f"{_KEY_TAG}{type(key).__name__}:{json.dumps(key)}"
            if name in projected:
                raise ObservationProjectionError(
                    "OBSERVATION_KEY_COLLISION",
                    f"distinct keys project to {name!r}",
                )
            projected[name] = _canonical(item)
        return dict(sorted(projected.items()))
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ObservationProjectionError(
        "OBSERVATION_UNSUPPORTED_TYPE", f"value of type {type(value).__name__}"
    )


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

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError("MALFORMED_CASE: case_id must be a non-empty str")
        outputs = self.accepted_outputs
        if isinstance(outputs, (str, bytes)) or not isinstance(
            outputs, (set, frozenset)
        ):
            raise ValueError(
                f"MALFORMED_CASE: {self.case_id}: accepted_outputs must be a "
                "set of str, not a bare string or sequence"
            )
        if not outputs:
            raise ValueError(
                f"EMPTY_ACCEPTANCE: {self.case_id}: a case with no accepted "
                "output is unsatisfiable on its own and cannot witness a ceiling"
            )
        if any(not isinstance(item, str) for item in outputs):
            raise ValueError(
                f"MALFORMED_CASE: {self.case_id}: accepted outputs must be str"
            )
        if not isinstance(outputs, frozenset):
            object.__setattr__(self, "accepted_outputs", frozenset(outputs))


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
    # canonical payload -> {distinct accepted-output set -> first case}
    buckets: dict[str, dict[frozenset[str], DecisionCase]] = {}
    # case_id -> (canonical payload, accepted outputs) for duplicate delivery
    seen: dict[str, tuple[str, frozenset[str]]] = {}

    for case in cases:
        canonical = _canonical_payload(case.observation)
        identity = (canonical, case.accepted_outputs)
        prior_identity = seen.get(case.case_id)
        if prior_identity is not None:
            if prior_identity != identity:
                raise ValueError(
                    f"DUPLICATE_CASE_ID: {case.case_id} redelivered with a "
                    "different observation or acceptance set"
                )
            continue  # idempotent redelivery of the identical case
        seen[case.case_id] = identity

        bucket = buckets.setdefault(canonical, {})
        if case.accepted_outputs in bucket:
            continue  # same observation, same acceptance: cannot be disjoint

        for prior in bucket.values():
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

        bucket[case.accepted_outputs] = case

    return None


def assert_information_sufficient(cases: Sequence[DecisionCase]) -> None:
    """Fail closed when the admitted interface cannot satisfy the contract."""
    witness = find_information_obstruction(cases)
    if witness is not None:
        raise EvidenceCeilingError(witness)
