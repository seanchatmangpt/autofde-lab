import pytest

from autofde_lab.evidence.information_obstruction import (
    DecisionCase,
    EvidenceCeilingError,
    analyze_information_obstruction,
    assert_information_sufficient,
    enumerate_information_obstructions,
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


def test_report_enumerates_every_pairwise_obstruction() -> None:
    cases = [
        DecisionCase("a", {"x": 1}, frozenset({"A"})),
        DecisionCase("b", {"x": 1}, frozenset({"B"})),
        DecisionCase("c", {"x": 1}, frozenset({"C"})),
        DecisionCase("d", {"x": 2}, frozenset({"D"})),
    ]

    witnesses = enumerate_information_obstructions(cases)
    report = analyze_information_obstruction(cases)

    assert [(row.left_case_id, row.right_case_id) for row in witnesses] == [
        ("a", "b"),
        ("a", "c"),
        ("b", "c"),
    ]
    assert report.case_count == 4
    assert report.observation_class_count == 2
    assert report.collision_class_count == 1
    assert report.obstruction_count == 3
    assert report.information_sufficient is False
    assert report.standing == "REFUSED(EVIDENCE_CEILING)"


def test_overlapping_accepted_sets_are_not_an_obstruction() -> None:
    cases = [
        DecisionCase("a", {"x": 1}, frozenset({"A", "B"})),
        DecisionCase("b", {"x": 1}, frozenset({"B", "C"})),
    ]

    report = analyze_information_obstruction(cases)

    assert report.collision_class_count == 1
    assert report.obstruction_count == 0
    assert report.information_sufficient is True
    assert report.standing == "ADMITTED"


def test_empty_accepted_output_set_is_refused_as_malformed_contract() -> None:
    with pytest.raises(ValueError, match="ACCEPTED_OUTPUTS_REQUIRED"):
        analyze_information_obstruction(
            [DecisionCase("bad", {"x": 1}, frozenset())]
        )
