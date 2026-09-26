import pytest

from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    EvidenceCeilingError,
    assert_information_sufficient,
    find_information_obstruction,
)


def test_identical_observation_with_disjoint_outputs_is_evidence_ceiling() -> None:
    cases = [
        DecisionCase(
            case_id="case-a",
            observation={"documents": ["same.docx"], "facts": {"visible": True}},
            accepted_outputs=frozenset({"GO"}),
        ),
        DecisionCase(
            case_id="case-b",
            observation={"facts": {"visible": True}, "documents": ["same.docx"]},
            accepted_outputs=frozenset({"NO_GO"}),
        ),
    ]

    witness = find_information_obstruction(cases)

    assert witness is not None
    assert witness.refusal_code == "EVIDENCE_CEILING"
    assert witness.left_case_id == "case-a"
    assert witness.right_case_id == "case-b"
    assert witness.left_accepted_outputs == ("GO",)
    assert witness.right_accepted_outputs == ("NO_GO",)


def test_additional_decisive_fact_removes_obstruction() -> None:
    cases = [
        DecisionCase(
            case_id="case-a",
            observation={"documents": ["same.docx"], "signing_authority": True},
            accepted_outputs=frozenset({"GO"}),
        ),
        DecisionCase(
            case_id="case-b",
            observation={"documents": ["same.docx"], "signing_authority": False},
            accepted_outputs=frozenset({"NO_GO"}),
        ),
    ]

    assert find_information_obstruction(cases) is None
    assert_information_sufficient(cases)


def test_assertion_fails_closed_with_typed_witness() -> None:
    cases = [
        DecisionCase("left", {"x": 1}, frozenset({"A"})),
        DecisionCase("right", {"x": 1}, frozenset({"B"})),
    ]

    with pytest.raises(EvidenceCeilingError) as exc:
        assert_information_sufficient(cases)

    assert exc.value.witness.refusal_code == "EVIDENCE_CEILING"
