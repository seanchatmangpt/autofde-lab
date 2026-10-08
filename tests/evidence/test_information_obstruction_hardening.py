"""Adversarial falsifiers for the EVIDENCE_CEILING preflight (PR #194 hardening).

Chicago style: every test drives the real module with real inputs and asserts
on the returned witness or the typed refusal. No test doubles.
"""

from __future__ import annotations

import itertools

import pytest

from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    EvidenceCeilingError,
    ObservationProjectionError,
    assert_information_sufficient,
    find_information_obstruction,
    observation_fingerprint,
)

# --- false-equality falsifiers: distinct observations must never collide ---


def test_tag_mimicking_string_key_does_not_collide_with_typed_key() -> None:
    # A str key spelled like the internal type tag must stay distinct from
    # the real int key it mimics.
    mimic = "\u0000int:1"
    cases = [
        DecisionCase("left", {1: "a"}, frozenset({"GO"})),
        DecisionCase("right", {mimic: "a"}, frozenset({"NO_GO"})),
    ]
    assert find_information_obstruction(cases) is None


def test_unsupported_key_type_is_refused() -> None:
    with pytest.raises(ObservationProjectionError) as exc:
        observation_fingerprint({(1, 2): "a"})
    assert exc.value.refusal_code == "OBSERVATION_UNSUPPORTED_TYPE"


def test_distinct_key_types_do_not_produce_false_witness() -> None:
    # Before hardening, {1: "a"} and {"1": "a"} projected identically and a
    # false EVIDENCE_CEILING witness was emitted for distinct observations.
    cases = [
        DecisionCase("left", {1: "a"}, frozenset({"GO"})),
        DecisionCase("right", {"1": "a"}, frozenset({"NO_GO"})),
    ]
    assert find_information_obstruction(cases) is None


def test_bool_and_int_values_are_distinct_observations() -> None:
    cases = [
        DecisionCase("left", {"x": True}, frozenset({"GO"})),
        DecisionCase("right", {"x": 1}, frozenset({"NO_GO"})),
    ]
    assert find_information_obstruction(cases) is None


def test_int_and_float_values_are_distinct_observations() -> None:
    cases = [
        DecisionCase("left", {"x": 1}, frozenset({"GO"})),
        DecisionCase("right", {"x": 1.0}, frozenset({"NO_GO"})),
    ]
    assert find_information_obstruction(cases) is None


class _SameRepr:
    def __init__(self, payload: int) -> None:
        self.payload = payload

    def __repr__(self) -> str:
        return "<opaque>"


def test_opaque_objects_with_equal_repr_are_refused() -> None:
    # repr() is not identity: two objects with different payloads and the
    # same repr must not be declared observationally equal.
    with pytest.raises(ObservationProjectionError) as exc:
        find_information_obstruction(
            [
                DecisionCase("left", {"x": _SameRepr(1)}, frozenset({"GO"})),
                DecisionCase("right", {"x": _SameRepr(2)}, frozenset({"NO_GO"})),
            ]
        )
    assert exc.value.refusal_code == "OBSERVATION_UNSUPPORTED_TYPE"


def test_bytes_observation_is_refused() -> None:
    with pytest.raises(ObservationProjectionError):
        observation_fingerprint({"blob": b"\x00"})


# --- malformed contract inputs ---


@pytest.mark.parametrize(
    "outputs",
    ["GO", ["GO"], ("GO",), frozenset({1})],
)
def test_malformed_accepted_outputs_are_refused(outputs: object) -> None:
    with pytest.raises(ValueError, match="MALFORMED_CASE"):
        DecisionCase("c", {"x": 1}, outputs)  # type: ignore[arg-type]


def test_empty_acceptance_is_refused() -> None:
    with pytest.raises(ValueError, match="EMPTY_ACCEPTANCE"):
        DecisionCase("c", {"x": 1}, frozenset())


def test_empty_case_id_is_refused() -> None:
    with pytest.raises(ValueError, match="MALFORMED_CASE"):
        DecisionCase("", {"x": 1}, frozenset({"GO"}))


def test_mutable_set_is_frozen_on_admission() -> None:
    case = DecisionCase("c", {"x": 1}, {"GO"})  # type: ignore[arg-type]
    assert isinstance(case.accepted_outputs, frozenset)


# --- duplicate delivery ---


def test_identical_redelivery_is_idempotent() -> None:
    case = DecisionCase("a", {"x": 1}, frozenset({"GO"}))
    assert find_information_obstruction([case, case, case]) is None


def test_conflicting_redelivery_is_refused_not_self_witnessed() -> None:
    # Before hardening, this produced a witness "a vs a" — a case contradicting
    # itself is malformed input, not an evidence ceiling.
    with pytest.raises(ValueError, match="DUPLICATE_CASE_ID"):
        find_information_obstruction(
            [
                DecisionCase("a", {"x": 1}, frozenset({"GO"})),
                DecisionCase("a", {"x": 1}, frozenset({"NO_GO"})),
            ]
        )


# --- reordering: existence of an obstruction is order-invariant ---


def test_obstruction_existence_is_invariant_under_permutation() -> None:
    cases = [
        DecisionCase("a", {"x": 1}, frozenset({"GO", "HOLD"})),
        DecisionCase("b", {"x": 1}, frozenset({"HOLD", "NO_GO"})),
        DecisionCase("c", {"x": 2}, frozenset({"GO"})),
        DecisionCase("d", {"x": 1}, frozenset({"NO_GO"})),
    ]
    results = set()
    for perm in itertools.permutations(cases):
        witness = find_information_obstruction(perm)
        assert witness is not None
        pair = frozenset({witness.left_case_id, witness.right_case_id})
        results.add(pair)
        # every reported pair is a real obstruction
        assert pair in {frozenset({"a", "d"})}
    assert results == {frozenset({"a", "d"})}


def test_overlapping_acceptance_is_never_an_obstruction() -> None:
    cases = [
        DecisionCase(f"c{i}", {"x": 1}, frozenset({"SHARED", f"o{i}"}))
        for i in range(50)
    ]
    assert find_information_obstruction(cases) is None


def test_witness_fingerprint_is_the_observation_fingerprint() -> None:
    obs = {"b": [1, 2], "a": {"z": None}}
    witness = find_information_obstruction(
        [
            DecisionCase("l", obs, frozenset({"A"})),
            DecisionCase("r", {"a": {"z": None}, "b": [1, 2]}, frozenset({"B"})),
        ]
    )
    assert witness is not None
    assert witness.observation_fingerprint == observation_fingerprint(obs)


def test_set_observation_order_does_not_matter() -> None:
    witness = find_information_obstruction(
        [
            DecisionCase("l", {"docs": frozenset({"b", "a", "c"})}, frozenset({"A"})),
            DecisionCase("r", {"docs": {"c", "a", "b"}}, frozenset({"B"})),
        ]
    )
    assert witness is not None


def test_assert_raises_typed_error_carrying_witness_ids() -> None:
    with pytest.raises(EvidenceCeilingError) as exc:
        assert_information_sufficient(
            [
                DecisionCase("l", [1, 2], frozenset({"A"})),
                DecisionCase("r", (1, 2), frozenset({"B"})),
            ]
        )
    assert (exc.value.witness.left_case_id, exc.value.witness.right_case_id) == (
        "l",
        "r",
    )
