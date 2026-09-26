"""Temporal delegation/admission history court tests."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.delegation_admission_history import (
    evaluate_history,
    main,
)
from autofde_lab.iec.crowns.model import IECRefusal

SUBJECT = "git:seanchatmangpt/autofde-lab@history"


def artifact(*, units: int, scope: int, standing: str = "PARTIAL_ALIVE") -> dict:
    return {
        "schema": "autofde-lab.delegation-admission/1",
        "subject": SUBJECT,
        "delegation": {
            "units": units,
            "boundary_id": "sha256:boundary",
            "authority_scope_id": "sha256:authority-scope",
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
                "verifier_id": "urn:verifier:independent",
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
                "authority_id": "sha256:a",
                "consequence_id": "sha256:k",
                "receipt_id": "sha256:ar",
                "replay_id": "sha256:rr",
                "standing": standing,
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


def test_history_allows_growth_and_later_safe_contraction() -> None:
    report = evaluate_history(
        history(
            artifact(units=1, scope=1),
            artifact(units=2, scope=2),
            artifact(units=3, scope=3),
            artifact(units=1, scope=1),
        )
    )
    assert report["gate"] == "PASS"
    assert report["falsifiers"] == []
    assert report["metrics"]["peak_delegation_units"] == 3
    assert report["metrics"]["capacity_loss_events"] == 1
    assert report["metrics"]["admission_debt_area"] == 0


def test_history_fails_when_capacity_is_revoked_without_contraction() -> None:
    report = evaluate_history(
        history(
            artifact(units=3, scope=3),
            artifact(units=3, scope=1),
        )
    )
    assert report["gate"] == "COUNTEREXAMPLE"
    assert "CAPACITY_REVOKED_WITH_LIVE_DELEGATION" in report["falsifiers"]
    assert "SNAPSHOT_ADMISSION_FAILURE" in report["falsifiers"]
    assert report["metrics"]["admission_debt_area"] == 2


def test_live_standing_cannot_survive_admission_failure() -> None:
    report = evaluate_history(
        history(
            artifact(units=1, scope=1),
            artifact(units=2, scope=1, standing="ALIVE"),
        )
    )
    assert "STANDING_SURVIVED_ADMISSION_FAILURE" in report["falsifiers"]


def test_history_refuses_sequence_gap() -> None:
    document = history(artifact(units=1, scope=1), artifact(units=1, scope=1))
    document["snapshots"][1]["sequence"] = 3
    with pytest.raises(IECRefusal, match="REFUSED_HISTORY_SEQUENCE"):
        evaluate_history(document)


def test_history_refuses_subject_drift() -> None:
    second = artifact(units=1, scope=1)
    second["subject"] = "git:other/repo@sha"
    for obligation in second["obligations"].values():
        obligation["subject"] = second["subject"]
    with pytest.raises(IECRefusal, match="REFUSED_EXACT_SUBJECT_MISMATCH"):
        evaluate_history(
            history(
                artifact(units=1, scope=1),
                second,
            )
        )


def test_history_cli_is_byte_replayable(tmp_path) -> None:
    source = tmp_path / "history.json"
    receipt = tmp_path / "receipt.json"
    source.write_text(
        json.dumps(
            history(
                artifact(units=1, scope=1),
                artifact(units=2, scope=2),
            )
        ),
        encoding="utf-8",
    )
    assert main([str(source), str(receipt), "--gate"]) == 0
    first = receipt.read_bytes()
    assert main([str(source), str(receipt)]) == 0
    assert receipt.read_bytes() == first
