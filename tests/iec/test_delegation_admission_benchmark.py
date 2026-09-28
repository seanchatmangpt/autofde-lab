"""Mutation and capacity-stress tests for delegation admission."""

from __future__ import annotations

import json

import pytest

from autofde_lab.iec.crowns.delegation_admission_benchmark import (
    capacity_sweep,
    main,
    mutation_court,
    run_benchmark,
)
from autofde_lab.iec.crowns.model import IECRefusal

SUBJECT = "git:seanchatmangpt/autofde-lab@benchmark"


def artifact(*, units: int = 4, scope: int = 4) -> dict:
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
                "provenance_id": "sha256:provenance",
                "ontology_id": "sha256:ontology",
                "rationale_id": "sha256:rationale",
            },
            "verify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "verifier_id": "urn:verifier:independent",
                "verifier_set_id": "sha256:verifiers",
                "receipt_id": "sha256:verify",
                "independent": True,
            },
            "modify": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "change_id": "sha256:change",
                "result_id": "sha256:result",
                "replay_id": "sha256:modify-replay",
            },
            "account": {
                "subject": SUBJECT,
                "verdict": "PASS",
                "scope_units": scope,
                "authority_id": "sha256:authority",
                "consequence_id": "sha256:consequence",
                "receipt_id": "sha256:account",
                "replay_id": "sha256:account-replay",
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def test_mutation_court_kills_every_declared_semantic_mutation() -> None:
    report = mutation_court(artifact())
    assert report["gate"] == "PASS"
    assert report["mutations"] == 8
    assert report["killed"] == 8
    assert report["kill_rate"] == 1.0
    assert all(case["killed"] for case in report["cases"])


def test_capacity_sweep_has_no_false_accepts_or_rejects() -> None:
    report = capacity_sweep(artifact(), max_units=12)
    assert report["gate"] == "PASS"
    assert report["checked_pairs"] == 169
    assert report["false_accepts"] == []
    assert report["false_rejects"] == []


def test_capacity_sweep_refuses_invalid_bound() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_BENCHMARK_BOUND"):
        capacity_sweep(artifact(), max_units=-1)


def test_benchmark_refuses_nonpassing_baseline() -> None:
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_BENCHMARK_BASELINE"):
        run_benchmark(artifact(units=5, scope=4))


def test_aggregate_benchmark_is_content_addressed_and_green() -> None:
    first = run_benchmark(artifact(), max_units=8)
    second = run_benchmark(artifact(), max_units=8)
    assert first == second
    assert first["gate"] == "PASS"
    assert first["mutation_court"]["kill_rate"] == 1.0
    assert first["capacity_sweep"]["checked_pairs"] == 81
    assert first["receipt_id"].startswith("sha256:")


def test_cli_writes_byte_identical_receipt(tmp_path) -> None:
    candidate = tmp_path / "candidate.json"
    receipt = tmp_path / "receipt.json"
    candidate.write_text(json.dumps(artifact()), encoding="utf-8")

    assert (
        main(
            [
                str(candidate),
                str(receipt),
                "--max-units",
                "10",
                "--gate",
            ]
        )
        == 0
    )
    first = receipt.read_bytes()
    assert main([str(candidate), str(receipt), "--max-units", "10"]) == 0
    assert receipt.read_bytes() == first
