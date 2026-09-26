"""OCEL projection tests for delegation/admission history."""

from __future__ import annotations

from autofde_lab.iec.crowns.delegation_admission_history import evaluate_history
from autofde_lab.iec.crowns.delegation_admission_ocel import (
    history_receipt_to_ocel,
)

SUBJECT = "git:seanchatmangpt/autofde-lab@ocel"


def artifact(*, units: int, scope: int) -> dict:
    return {
        "schema": "autofde-lab.delegation-admission/1",
        "subject": SUBJECT,
        "delegation": {
            "units": units,
            "boundary_id": "sha256:b",
            "authority_scope_id": "sha256:a",
            "producer_id": "urn:producer:subject",
        },
        "obligations": {
            "explain": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "provenance_id": "sha256:p",
                "ontology_id": "sha256:o",
                "rationale_id": "sha256:r",
            },
            "verify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "verifier_set_id": "sha256:v",
                "receipt_id": "sha256:vr",
                "independent": True,
            },
            "modify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "change_id": "sha256:c",
                "result_id": "sha256:result",
                "replay_id": "sha256:mr",
            },
            "account": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "authority_id": "sha256:auth",
                "consequence_id": "sha256:k",
                "receipt_id": "sha256:ar",
                "replay_id": "sha256:rr",
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def history(*artifacts: dict) -> dict:
    return {
        "schema": "autofde-lab.delegation-admission-history/1",
        "snapshots": [
            {"sequence": index, "artifact": value}
            for index, value in enumerate(artifacts)
        ],
    }


def test_ocel_projection_is_valid_and_deterministic() -> None:
    receipt = evaluate_history(
        history(
            artifact(units=1, scope=1),
            artifact(units=2, scope=2),
            artifact(units=1, scope=1),
        )
    )
    first = history_receipt_to_ocel(receipt)
    second = history_receipt_to_ocel(receipt)
    assert first.validate(strict_qualifiers=True) is first
    assert first.digest() == second.digest()
    assert [event.activity for event in first.events].count(
        "AdmissionSnapshotObserved"
    ) == 3
    assert [event.activity for event in first.events].count(
        "AdmissionTransition"
    ) == 2
    assert "AdmissionFailed" not in [event.activity for event in first.events]


def test_failed_snapshot_projects_explicit_admission_failed_event() -> None:
    receipt = evaluate_history(
        history(
            artifact(units=2, scope=2),
            artifact(units=2, scope=1),
        )
    )
    log = history_receipt_to_ocel(receipt)
    activities = [event.activity for event in log.events]
    assert "AdmissionFailed" in activities
    assert activities.count("AdmissionSnapshotObserved") == 2


def test_projection_preserves_snapshot_and_transition_objects() -> None:
    receipt = evaluate_history(
        history(
            artifact(units=1, scope=1),
            artifact(units=2, scope=2),
        )
    )
    log = history_receipt_to_ocel(receipt)
    object_types = [obj.object_type for obj in log.objects]
    assert object_types.count("DelegationSubject") == 1
    assert object_types.count("AdmissionSnapshot") == 2
    assert object_types.count("AdmissionTransition") == 1
