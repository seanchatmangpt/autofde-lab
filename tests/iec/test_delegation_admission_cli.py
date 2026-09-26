"""Canonical IEC CLI integration for delegation admission courts."""

from __future__ import annotations

import json

from autofde_lab.iec.cli import build_parser, main as iec_main

SUBJECT = "git:seanchatmangpt/autofde-lab@cli"


def artifact(*, units: int = 2, scope: int = 2) -> dict:
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
                "standing": "PARTIAL_ALIVE",
            },
        },
    }


def write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_canonical_cli_runs_snapshot_and_benchmark(tmp_path) -> None:
    candidate = tmp_path / "candidate.json"
    snapshot_receipt = tmp_path / "snapshot.json"
    benchmark_receipt = tmp_path / "benchmark.json"
    write(candidate, artifact())

    assert (
        iec_main(
            [
                "delegation-admission",
                str(candidate),
                str(snapshot_receipt),
                "--gate",
            ]
        )
        == 0
    )
    assert json.loads(snapshot_receipt.read_text())["gate"] == "PASS"

    assert (
        iec_main(
            [
                "delegation-admission-benchmark",
                str(candidate),
                str(benchmark_receipt),
                "--max-units",
                "6",
                "--gate",
            ]
        )
        == 0
    )
    benchmark = json.loads(benchmark_receipt.read_text())
    assert benchmark["gate"] == "PASS"
    assert benchmark["capacity_sweep"]["checked_pairs"] == 49


def test_canonical_cli_runs_history_and_batch(tmp_path) -> None:
    history_source = tmp_path / "history.json"
    history_receipt = tmp_path / "history-receipt.json"
    batch_source = tmp_path / "batch.json"
    batch_receipt = tmp_path / "batch-receipt.json"

    write(
        history_source,
        {
            "schema": "autofde-lab.delegation-admission-history/1",
            "snapshots": [
                {"sequence": 0, "artifact": artifact(units=1, scope=1)},
                {"sequence": 1, "artifact": artifact(units=2, scope=2)},
            ],
        },
    )
    write(
        batch_source,
        {
            "schema": "autofde-lab.delegation-admission-batch/1",
            "cases": [artifact()],
        },
    )

    assert (
        iec_main(
            [
                "delegation-admission-history",
                str(history_source),
                str(history_receipt),
                "--gate",
            ]
        )
        == 0
    )
    assert (
        iec_main(
            [
                "delegation-admission-batch",
                str(batch_source),
                str(batch_receipt),
                "--gate",
            ]
        )
        == 0
    )


def test_canonical_cli_plans_numeric_repair(tmp_path) -> None:
    candidate = tmp_path / "candidate.json"
    receipt = tmp_path / "repair.json"
    write(candidate, artifact(units=4, scope=2))

    assert (
        iec_main(
            [
                "delegation-admission-repair",
                str(candidate),
                str(receipt),
            ]
        )
        == 0
    )
    result = json.loads(receipt.read_text())
    assert result["standing"] == "PASS"
    assert result["total_increment_units"] == 8
    assert result["expected_admission_debt_units"] == 0


def test_canonical_cli_runs_headroom_spc(tmp_path) -> None:
    history_receipt = tmp_path / "history-receipt.json"
    spc_receipt = tmp_path / "spc.json"
    write(
        history_receipt,
        {
            "schema": "autofde-lab.delegation-admission-history-receipt/1",
            "subject": SUBJECT,
            "receipt_id": "sha256:history",
            "snapshots": [
                {
                    "sequence": index,
                    "subject": SUBJECT,
                    "receipt_id": f"sha256:{index}",
                    "gate": "PASS",
                    "delegation_units": 1,
                    "admission_capacity_units": 5 if index < 5 else 4,
                    "admission_debt_units": 0,
                    "standing": "PARTIAL_ALIVE",
                    "falsifiers": [],
                }
                for index in range(6)
            ],
            "transitions": [],
        },
    )
    assert (
        iec_main(
            [
                "delegation-admission-spc",
                str(history_receipt),
                str(spc_receipt),
                "--baseline-count",
                "5",
            ]
        )
        == 0
    )
    assert json.loads(spc_receipt.read_text())["standing"] == "DRIFT_SIGNAL"


def test_canonical_tlc_parser_accepts_delegation_models() -> None:
    parser = build_parser()
    reference = parser.parse_args(
        [
            "tlc-court",
            "--model",
            "delegation-admission",
            "--out",
            "out",
        ]
    )
    mutant = parser.parse_args(
        [
            "tlc-court",
            "--model",
            "delegation-mutant:SELF_VERIFICATION",
            "--out",
            "out",
        ]
    )
    assert reference.model == "delegation-admission"
    assert mutant.model == "delegation-mutant:SELF_VERIFICATION"
