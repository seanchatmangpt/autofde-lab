from autofde_lab.fabric.crown import (
    CrownReport,
    CrownRequirement,
    RequirementStatus,
    crown_report,
)


def test_canonical_registry_is_machine_valid():
    report = crown_report()
    assert report.validate() == ()
    assert len(report.requirements) >= 70


def test_competitive_crown_is_closed_until_every_parity_and_differentiator_gate_passes():
    report = crown_report()
    assert report.palantir_defeat_ready is False
    open_gates = [
        r.requirement_id
        for r in report.requirements
        if (r.requirement_id.startswith("P") or r.requirement_id.startswith("D"))
        and r.status is not RequirementStatus.SATISFIED
    ]
    assert set(open_gates) == {*(f"P{i}" for i in range(1, 8)), *(f"D{i}" for i in range(1, 9))}


def test_satisfied_without_evidence_is_invalid():
    report = CrownReport(
        (CrownRequirement("X", "claim", RequirementStatus.SATISFIED),)
    )
    assert report.validate() == ("X: SATISFIED without evidence",)


def test_external_dependency_cannot_be_internally_satisfied():
    report = CrownReport(
        (
            CrownRequirement(
                "X",
                "claim",
                RequirementStatus.SATISFIED,
                ("tests/fake.py",),
                external_dependency="customer",
            ),
        )
    )
    assert "external dependency" in report.validate()[0]


def test_customer_adoption_cannot_be_manufactured_from_internal_fixture():
    report = CrownReport(
        (
            CrownRequirement(
                "R-1501",
                "ADOPTED",
                RequirementStatus.SATISFIED,
                ("tests/fixtures/fake_customer.json",),
            ),
        )
    )
    assert any("ADOPTED" in problem for problem in report.validate())


def test_zero_unreceipted_actuation_is_preserved_verbatim_as_requirement():
    assert "Zero unreceipted actuation" in crown_report().get("R-001").statement


def test_new_primitives_have_bounded_satisfied_standing():
    report = crown_report()
    assert report.get("R-201").status is RequirementStatus.SATISFIED
    assert report.get("R-202").status is RequirementStatus.SATISFIED
    assert report.get("R-303").status is RequirementStatus.SATISFIED
    assert report.get("R-304").status is RequirementStatus.SATISFIED
    assert report.get("R-501").status is RequirementStatus.SATISFIED
    assert report.get("R-602").status is RequirementStatus.SATISFIED
    assert report.get("R-1003").status is RequirementStatus.SATISFIED
    assert report.get("R-1103").status is RequirementStatus.SATISFIED
    assert report.get("R-1200").status is RequirementStatus.SATISFIED
    assert report.get("R-1402").status is RequirementStatus.SATISFIED
    assert report.get("R-1301").status is RequirementStatus.BLOCKED
    assert report.get("R-1501").status is RequirementStatus.BLOCKED
