"""Batch transport court tests for delegation admission."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.delegation_admission_batch import (
    evaluate_batch,
    main,
)
from autofde_lab.iec.crowns.model import IECRefusal


def artifact(subject: str, *, units: int = 2, scope: int = 2) -> dict:
    return {
        "schema": "autofde-lab.delegation-admission/1",
        "subject": subject,
        "delegation": {
            "units": units,
            "boundary_id": f"sha256:boundary:{subject}",
            "authority_scope_id": f"sha256:authority:{subject}",
            "producer_id": "urn:producer:subject",
        },
        "obligations": {
            "explain": {
                "subject": subject,
                "verdict": "PASS",
                "scope_units": scope,
                "provenance_id": "sha256:p",
                "ontology_id": "sha256:o",
                "rationale_id": "sha256:r",
            },
            "verify": {
                "subject": subject,
                "verdict": "PASS",
                "scope_units": scope,
                "verifier_id": "urn:verifier:independent",
                "verifier_set_id": "sha256:v",
                "receipt_id": "sha256:vr",
                "independent": True,
            },
            "modify": {
                "subject": subject,
                "verdict": "PASS",
                "scope_units": scope,
                "change_id": "sha256:c",
                "result_id": "sha256:result",
                "replay_id": "sha256:mr",
            },
            "account": {
                "subject": subject,
                "verdict": "PASS",
                "scope_units": scope,
                "authority_id": "sha256:a",
                "consequence_id": "sha256:k",
                "receipt_id": "sha256:ar",
                "replay_id": "sha256:rr",
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def batch(*cases: dict) -> dict:
    return {
        "schema": "autofde-lab.delegation-admission-batch/1",
        "cases": list(cases),
    }


def test_batch_preserves_per_subject_receipts() -> None:
    report = evaluate_batch(
        batch(
            artifact("git:example/a@sha"),
            artifact("git:example/b@sha", units=3, scope=3),
        )
    )
    assert report["gate"] == "PASS"
    assert report["case_count"] == 2
    assert report["pass_count"] == 2
    assert report["metrics"]["total_delegation_units"] == 5
    assert report["metrics"]["total_admission_debt_units"] == 0
    assert len({row["receipt_id"] for row in report["case_receipts"]}) == 2


def test_batch_cannot_hide_failing_member_by_aggregation() -> None:
    report = evaluate_batch(
        batch(
            artifact("git:example/a@sha"),
            artifact("git:example/b@sha", units=4, scope=2),
        )
    )
    assert report["gate"] == "COUNTEREXAMPLE"
    assert report["counterexample_count"] == 1
    assert report["metrics"]["total_admission_debt_units"] == 2
    assert report["failing_cases"][0]["subject"] == "git:example/b@sha"


def test_batch_refuses_duplicate_exact_identity() -> None:
    duplicate = artifact("git:example/a@sha")
    with pytest.raises(
        IECRefusal,
        match="REFUSED_DUPLICATE_DELEGATION_SUBJECT",
    ):
        evaluate_batch(batch(duplicate, duplicate))


def test_empty_batch_is_not_vacuous_pass() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_EMPTY_DELEGATION_BATCH"):
        evaluate_batch(batch())


def test_batch_cli_is_byte_replayable(tmp_path) -> None:
    source = tmp_path / "batch.json"
    receipt = tmp_path / "receipt.json"
    source.write_text(
        json.dumps(
            batch(
                artifact("git:example/a@sha"),
                artifact("git:example/b@sha"),
            )
        ),
        encoding="utf-8",
    )
    assert main([str(source), str(receipt), "--gate"]) == 0
    first = receipt.read_bytes()
    assert main([str(source), str(receipt)]) == 0
    assert receipt.read_bytes() == first
