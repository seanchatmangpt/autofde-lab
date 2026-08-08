from dataclasses import replace

from autofde_lab.fabric.crown import RequirementStatus, crown_report
from autofde_lab.fabric.crown_errc import ERRC, ErrcAction, closure_delta, errc_crown_report


def test_errc_projection_closes_executed_requirements_without_promoting_external_blockers():
    report = errc_crown_report()
    assert report.get("R-001").status is RequirementStatus.SATISFIED
    assert report.get("R-1201").status is RequirementStatus.SATISFIED
    assert report.get("R-1301").status is RequirementStatus.BLOCKED
    assert report.get("R-1501").status is RequirementStatus.BLOCKED
    assert report.palantir_defeat_ready is False


def test_derived_gates_are_conjunctive_and_evidence_backed():
    report = errc_crown_report()
    for gate in ("P1", "P2", "D1", "D2", "D3", "D4", "D6"):
        requirement = report.get(gate)
        assert requirement.status is RequirementStatus.SATISFIED
        assert requirement.evidence


def test_gate_refuses_false_crown_when_one_prerequisite_is_demoted():
    base = crown_report()
    requirements = tuple(
        replace(r, status=RequirementStatus.BLOCKED, external_dependency="falsifier")
        if r.requirement_id == "R-1201"
        else r
        for r in base.requirements
    )
    report = errc_crown_report(type(base)(requirements))
    assert report.get("R-1201").status is RequirementStatus.BLOCKED
    assert report.get("D6").status is RequirementStatus.PARTIAL


def test_closure_delta_is_material_and_preserves_blockers():
    delta = closure_delta()
    assert delta["after_satisfied"] > delta["before_satisfied"]
    assert delta["after_satisfied"] >= 40
    assert delta["blocked_preserved"] == 2
    assert delta["remaining_partial"] > 0


def test_errc_preserves_all_four_actions_and_zero_unreceipted_actuation_direction():
    assert set(ERRC.values()) == set(ErrcAction)
    assert ERRC["ambient_or_duplicated_actuation_authority"] is ErrcAction.ELIMINATE
    assert ERRC["independent_postcondition_verification"] is ErrcAction.RAISE
    assert ERRC["evidence_derived_gate_court"] is ErrcAction.CREATE
