"""Deterministic admission-capacity repair planner tests."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.delegation_admission_repair import (
    plan_capacity_repair,
)
from autofde_lab.iec.crowns.model import IECRefusal

SUBJECT = "git:seanchatmangpt/autofde-lab@repair"


def artifact(
    *,
    units: int = 5,
    scopes: dict[str, int] | None = None,
    independent: bool = True,
) -> dict:
    scopes = scopes or {
        "explain": 5,
        "verify": 5,
        "modify": 5,
        "account": 5,
    }
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
                "scope_units": scopes["explain"],
                "provenance_id": "sha256:p",
                "ontology_id": "sha256:o",
                "rationale_id": "sha256:r",
            },
            "verify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scopes["verify"],
                "verifier_set_id": "sha256:v",
                "receipt_id": "sha256:vr",
                "independent": independent,
            },
            "modify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scopes["modify"],
                "change_id": "sha256:c",
                "result_id": "sha256:result",
                "replay_id": "sha256:mr",
            },
            "account": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scopes["account"],
                "authority_id": "sha256:auth",
                "consequence_id": "sha256:k",
                "receipt_id": "sha256:ar",
                "replay_id": "sha256:rr",
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def test_repair_plan_is_exact_minimum_scope_increment() -> None:
    report = plan_capacity_repair(
        artifact(
            scopes={
                "explain": 5,
                "verify": 2,
                "modify": 3,
                "account": 4,
            }
        )
    )
    assert report["standing"] == "PASS"
    assert report["current_capacity_units"] == 2
    assert report["expected_capacity_units"] == 5
    assert report["expected_admission_debt_units"] == 0
    assert report["total_increment_units"] == 6
    by_name = {action["obligation"]: action for action in report["actions"]}
    assert by_name["verify"]["increment_units"] == 3
    assert by_name["modify"]["increment_units"] == 2
    assert by_name["account"]["increment_units"] == 1
    assert "explain" not in by_name


def test_repair_plan_uses_declared_costs_without_changing_required_units() -> None:
    report = plan_capacity_repair(
        artifact(
            scopes={
                "explain": 4,
                "verify": 4,
                "modify": 4,
                "account": 4,
            }
        ),
        unit_costs={
            "explain": 10,
            "verify": 2,
            "modify": 3,
            "account": 4,
        },
    )
    assert report["total_increment_units"] == 4
    assert report["total_cost"] == 19.0
    assert [action["obligation"] for action in report["actions"]] == [
        "verify",
        "modify",
        "account",
        "explain",
    ]


def test_clean_artifact_needs_no_repair() -> None:
    report = plan_capacity_repair(artifact())
    assert report["standing"] == "PASS"
    assert report["actions"] == []
    assert report["total_cost"] == 0.0


def test_semantic_evidence_failure_is_not_faked_as_numeric_repair() -> None:
    report = plan_capacity_repair(artifact(independent=False))
    assert report["standing"] == "UNSUPPORTED"
    assert report["reason"] == "NON_CAPACITY_EVIDENCE_REPAIR_REQUIRED"
    assert report["actions"] == []
    assert "VERIFY_NOT_INDEPENDENT" in report["semantic_issues"]


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True])
def test_invalid_costs_are_refused(value) -> None:
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_REPAIR_COST"):
        plan_capacity_repair(artifact(), unit_costs={"verify": value})


def test_repair_receipt_is_deterministic() -> None:
    candidate = artifact(
        scopes={
            "explain": 2,
            "verify": 3,
            "modify": 4,
            "account": 5,
        }
    )
    assert plan_capacity_repair(candidate) == plan_capacity_repair(candidate)
