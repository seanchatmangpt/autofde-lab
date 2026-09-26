"""Falsifiers for executable SWE-Prometheus paired probes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus import DIMENSIONS
from autofde_lab.iec.crowns.prometheus_mutation import MUTATION_REPORT_SCHEMA
from autofde_lab.iec.crowns.prometheus_probe import (
    MANIFEST_SCHEMA,
    SCORECARD_SCHEMA,
    assemble_case,
    execute_manifest,
    pair_runs,
    parse_manifest,
)


def manifest() -> dict:
    probes = [
        {
            "id": f"gov-{index}",
            "role": "governance",
            "dimension": dimension,
            "argv": ["probe", dimension],
            "scope": "both",
        }
        for index, dimension in enumerate(DIMENSIONS, start=1)
    ]
    probes.extend(
        [
            {
                "id": "behavior",
                "role": "behavior",
                "argv": ["probe", "behavior"],
                "scope": "both",
                "comparison": "stdout_digest",
            },
            {
                "id": "mutation-1",
                "role": "mutation",
                "argv": ["probe", "mutation-1"],
                "scope": "treated",
            },
            {
                "id": "clean",
                "role": "clean_environment",
                "argv": ["probe", "clean"],
                "scope": "treated",
            },
            {
                "id": "replay",
                "role": "replay",
                "argv": ["probe", "replay"],
                "scope": "treated",
            },
        ]
    )
    return {
        "schema": MANIFEST_SCHEMA,
        "repository": "seanchatmangpt/example",
        "base_commit": "0123456789abcdef",
        "patch_digest": "sha256:patch",
        "probes": probes,
    }


def executor(
    *,
    behavior_treated: bytes = b"same\n",
    mutation_exit: int = 0,
    fail_dimension: str | None = None,
):
    def run(argv, *, cwd, env, capture_output, timeout, check):
        del env, capture_output, timeout, check
        key = argv[-1]
        side = "treated" if "treated" in Path(cwd).name else "base"
        if key == "behavior":
            stdout = (
                behavior_treated
                if side == "treated"
                else b"same\n"
            )
            return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")
        if key == "mutation-1":
            return SimpleNamespace(
                returncode=mutation_exit,
                stdout=b"",
                stderr=b"",
            )
        if key == fail_dimension and side == "treated":
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"failed")
        return SimpleNamespace(returncode=0, stdout=b"ok\n", stderr=b"")

    return run


def paired(
    tmp_path,
    *,
    behavior_treated: bytes = b"same\n",
    mutation_exit: int = 0,
    fail_dimension: str | None = None,
):
    base = tmp_path / "base"
    treated = tmp_path / "treated"
    base.mkdir()
    treated.mkdir()
    doc = manifest()
    run = executor(
        behavior_treated=behavior_treated,
        mutation_exit=mutation_exit,
        fail_dimension=fail_dimension,
    )
    base_run = execute_manifest(
        doc,
        root=base,
        side="base",
        executor=run,
        env={},
    )
    treated_run = execute_manifest(
        doc,
        root=treated,
        side="treated",
        executor=run,
        env={},
    )
    return doc, base_run, treated_run, pair_runs(doc, base_run, treated_run)


def scorecard(pair_id: str) -> dict:
    return {
        "schema": SCORECARD_SCHEMA,
        "pair_id": pair_id,
        "model": "MACHINE_SERIAL",
        "scaffold": "typed-probes",
        "dimensions": {
            dimension: {"base": 2, "treated": 4}
            for dimension in DIMENSIONS
        },
    }


def test_executes_pair_and_manufactures_detected_gate(tmp_path) -> None:
    _, base_run, treated_run, pair = paired(tmp_path)
    assert base_run["side"] == "base"
    assert treated_run["side"] == "treated"
    assert pair["behavior"] == "preserved"
    assert pair["gate_strength"] == "detected"
    assert pair["mutation_receipt_id"].startswith("sha256:")
    assert pair["clean_environment"]["verdict"] == "PASS"
    assert pair["replay"]["verdict"] == "PASS"
    assert all(
        rows and {row["status"] for row in rows} == {"pass"}
        for rows in pair["governance_evidence"].values()
    )


def test_behavior_stdout_drift_is_broken_even_when_exit_zero(tmp_path) -> None:
    _, _, _, pair = paired(
        tmp_path,
        behavior_treated=b"different\n",
    )
    assert pair["behavior"] == "broken"


def test_mutation_survival_caps_gate_at_blind(tmp_path) -> None:
    _, _, _, pair = paired(tmp_path, mutation_exit=1)
    assert pair["gate_strength"] == "blind"
    assert pair["mutation_receipt_id"] is None


def test_behavior_without_mutations_is_vacuous(tmp_path) -> None:
    base = tmp_path / "base"
    treated = tmp_path / "treated"
    base.mkdir()
    treated.mkdir()
    doc = manifest()
    doc["probes"] = [
        probe
        for probe in doc["probes"]
        if probe["role"] != "mutation"
    ]
    run = executor()
    pair = pair_runs(
        doc,
        execute_manifest(doc, root=base, side="base", executor=run, env={}),
        execute_manifest(doc, root=treated, side="treated", executor=run, env={}),
    )
    assert pair["gate_strength"] == "vacuous"
    assert pair["mutation_receipt_id"] is None


def test_no_behavior_probe_has_no_gate(tmp_path) -> None:
    base = tmp_path / "base"
    treated = tmp_path / "treated"
    base.mkdir()
    treated.mkdir()
    doc = manifest()
    doc["probes"] = [
        probe
        for probe in doc["probes"]
        if probe["role"] not in {"behavior", "mutation"}
    ]
    run = executor()
    pair = pair_runs(
        doc,
        execute_manifest(doc, root=base, side="base", executor=run, env={}),
        execute_manifest(doc, root=treated, side="treated", executor=run, env={}),
    )
    assert pair["behavior"] == "unavailable"
    assert pair["gate_strength"] == "none"


def test_scorecard_is_bound_to_exact_pair_and_only_pass_evidence(tmp_path) -> None:
    _, _, _, pair = paired(
        tmp_path,
        fail_dimension="quality_gates",
    )
    case = assemble_case(pair, scorecard(pair["pair_id"]))
    assert case["dimensions"]["tests_ci"] == {
        "evidence_status": "pass",
        "base": 2.0,
        "treated": 4.0,
    }
    assert case["dimensions"]["quality_gates"] == {
        "evidence_status": "fail"
    }


def test_scorecard_cannot_move_to_another_pair(tmp_path) -> None:
    _, _, _, pair = paired(tmp_path)
    card = scorecard("sha256:other-pair")
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        assemble_case(pair, card)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda doc: doc["probes"].append(dict(doc["probes"][0])),
        lambda doc: doc["probes"][0].update(cwd="../escape"),
        lambda doc: doc["probes"].append(
            {
                "id": "mutation-base",
                "role": "mutation",
                "scope": "base",
                "argv": ["probe", "mutation"],
            }
        ),
        lambda doc: doc["probes"].append(
            {
                "id": "behavior-2",
                "role": "behavior",
                "scope": "both",
                "argv": ["probe", "behavior-2"],
            }
        ),
    ],
)
def test_manifest_refuses_identity_or_scope_ambiguity(mutator) -> None:
    doc = manifest()
    mutator(doc)
    with pytest.raises(IECRefusal, match="REFUSED_INVALID_PROBE_MANIFEST"):
        parse_manifest(doc)


def test_missing_cwd_is_unavailable_not_pass(tmp_path) -> None:
    doc = manifest()
    doc["probes"][0]["cwd"] = "does-not-exist"
    report = execute_manifest(
        doc,
        root=tmp_path,
        side="base",
        executor=executor(),
        env={},
    )
    row = next(
        receipt
        for receipt in report["receipts"]
        if receipt["probe_id"] == "gov-1"
    )
    assert row["status"] == "unavailable"
    assert row["exit_code"] is None


def test_timeout_is_typed_and_enters_pair_as_timeout(tmp_path) -> None:
    base = tmp_path / "base"
    treated = tmp_path / "treated"
    base.mkdir()
    treated.mkdir()
    doc = manifest()

    def run(argv, **kwargs):
        del kwargs
        if argv[-1] == "tests_ci":
            raise subprocess.TimeoutExpired(argv, timeout=1)
        return SimpleNamespace(returncode=0, stdout=b"same\n", stderr=b"")

    base_run = execute_manifest(
        doc,
        root=base,
        side="base",
        executor=run,
        env={},
    )
    treated_run = execute_manifest(
        doc,
        root=treated,
        side="treated",
        executor=run,
        env={},
    )
    pair = pair_runs(doc, base_run, treated_run)
    assert pair["governance_evidence"]["tests_ci"][0]["status"] == "timeout"


def test_run_identity_ignores_wall_time_but_binds_semantics(tmp_path) -> None:
    root = tmp_path / "base"
    root.mkdir()
    doc = manifest()
    run = executor()
    first = execute_manifest(
        doc,
        root=root,
        side="base",
        executor=run,
        env={},
    )
    second = execute_manifest(
        doc,
        root=root,
        side="base",
        executor=run,
        env={},
    )
    assert first["run_id"] == second["run_id"]
    assert first["receipts"][0]["semantic_id"] == second["receipts"][0]["semantic_id"]


def test_probe_runner_never_assigns_governance_scores(tmp_path) -> None:
    _, base_run, treated_run, pair = paired(tmp_path)
    encoded = json.dumps(
        {
            "base": base_run,
            "treated": treated_run,
            "pair": pair,
        },
        sort_keys=True,
    )
    assert '"base_score"' not in encoded
    assert '"treated_score"' not in encoded


def test_reversible_mutation_report_overrides_compatibility_probe_classification(
    tmp_path,
) -> None:
    doc, base_run, treated_run, _ = paired(
        tmp_path,
        mutation_exit=1,
    )
    report = {
        "schema": MUTATION_REPORT_SCHEMA,
        "repository": doc["repository"],
        "base_commit": doc["base_commit"],
        "patch_digest": doc["patch_digest"],
        "gate_strength": "detected",
        "receipt_id": "sha256:reversible-court",
    }
    pair = pair_runs(
        doc,
        base_run,
        treated_run,
        mutation_report=report,
    )
    assert pair["gate_strength"] == "detected"
    assert pair["mutation_receipt_id"] == "sha256:reversible-court"
    assert pair["mutation_source"] == "reversible-mutation-court"


def test_mutation_report_subject_drift_is_refused(tmp_path) -> None:
    doc, base_run, treated_run, _ = paired(tmp_path)
    report = {
        "schema": MUTATION_REPORT_SCHEMA,
        "repository": "other/repo",
        "base_commit": doc["base_commit"],
        "patch_digest": doc["patch_digest"],
        "gate_strength": "detected",
        "receipt_id": "sha256:other",
    }
    with pytest.raises(
        IECRefusal,
        match="REFUSED_EXACT_SUBJECT_MISMATCH",
    ):
        pair_runs(
            doc,
            base_run,
            treated_run,
            mutation_report=report,
        )


def test_detected_mutation_override_requires_receipt_id(tmp_path) -> None:
    doc, base_run, treated_run, _ = paired(tmp_path)
    report = {
        "schema": MUTATION_REPORT_SCHEMA,
        "repository": doc["repository"],
        "base_commit": doc["base_commit"],
        "patch_digest": doc["patch_digest"],
        "gate_strength": "detected",
    }
    with pytest.raises(
        IECRefusal,
        match="REFUSED_UNBOUNDED_EQUIVALENCE",
    ):
        pair_runs(
            doc,
            base_run,
            treated_run,
            mutation_report=report,
        )
