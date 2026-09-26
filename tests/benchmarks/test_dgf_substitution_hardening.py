"""Adversarial falsifiers for DGF deterministic substitution (PR #194 hardening).

Chicago style: a real evaluator.py is written to disk and executed by the real
kernel loader; the real CLI is run as a subprocess. No test doubles.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from autofde_lab.evidence.dgf_substitution import (
    DGFAdmissionError,
    dgf_evaluator_digest,
    load_dgf_kernel,
    run_dgf_case,
    run_dgf_dataset,
)

REPO = Path(__file__).resolve().parents[2]
CLI = REPO / "benchmarks" / "dgf_substitution.py"

EVALUATOR = """
def evaluate_route(case, occurrences):
    out = []
    for occurrence, decision in zip(occurrences, case["decisions"], strict=True):
        row = dict(decision)
        row["occurrence_id"] = occurrence["occurrence_id"]
        row["position"] = occurrence["position"]
        out.append(row)
    return out
"""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _dgf_root(tmp_path: Path, source: str = EVALUATOR) -> Path:
    root = tmp_path / "dgf"
    root.mkdir(exist_ok=True)
    (root / "evaluator.py").write_text(source.strip() + "\n", encoding="utf-8")
    return root


def _case(
    dataset: Path,
    name: str,
    *,
    case_id: str | None = None,
    gates: int = 1,
    expected: list[dict] | None = None,
) -> Path:
    case_dir = dataset / name
    occurrences = [
        {"occurrence_id": f"{name}-{i}", "position": i} for i in range(gates)
    ]
    decisions = [{"gate": f"g{i}", "disposition": "GO"} for i in range(gates)]
    reference = expected
    if reference is None:
        reference = [
            {**d, "occurrence_id": o["occurrence_id"], "position": o["position"]}
            for d, o in zip(decisions, occurrences)
        ]
    _write_json(case_dir / "01_route_manifest.json", {"occurrences": occurrences})
    _write_json(
        case_dir / "99_hidden_ground_truth.json",
        {
            "case_id": case_id or name,
            "canonical_truth": {"decisions": decisions},
            "reference_decisions": reference,
        },
    )
    return case_dir


# --- wrong digest / stale subject ---


def test_summary_digest_binds_exact_executed_bytes(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a")
    _, summary = run_dgf_dataset(dataset, dgf_root=root)
    assert summary.kernel_digest == dgf_evaluator_digest(root)
    assert summary.to_dict()["kernel_digest"] == summary.kernel_digest


def test_wrong_expected_digest_is_refused_before_execution(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a")
    with pytest.raises(DGFAdmissionError) as exc:
        run_dgf_dataset(
            dataset, dgf_root=root, expected_kernel_digest="sha256:" + "0" * 64
        )
    assert exc.value.refusal_code == "KERNEL_DIGEST_MISMATCH"


def test_policy_edit_changes_digest_and_is_refused_as_stale(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a")
    pinned = dgf_evaluator_digest(root)
    (root / "evaluator.py").write_text(
        EVALUATOR.replace(
            "row = dict(decision)", "row = dict(decision, tampered=True)"
        ),
        encoding="utf-8",
    )
    with pytest.raises(DGFAdmissionError, match="KERNEL_DIGEST_MISMATCH"):
        run_dgf_dataset(dataset, dgf_root=root, expected_kernel_digest=pinned)


def test_kernel_executes_the_bytes_it_hashed(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    kernel = load_dgf_kernel(root)
    # Mutating the file after load cannot change what the bound kernel runs.
    (root / "evaluator.py").write_text(
        "def evaluate_route(case, occurrences):\n    return []\n", encoding="utf-8"
    )
    dataset = tmp_path / "ds"
    case_dir = _case(dataset, "a")
    score = run_dgf_case(case_dir, dgf_root=root, kernel=kernel)
    assert score.route_match is True
    assert kernel.digest != dgf_evaluator_digest(root)


def test_evaluator_without_entrypoint_is_refused(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path, "def other():\n    return 1\n")
    with pytest.raises(AttributeError, match="evaluate_route"):
        load_dgf_kernel(root)


def test_missing_evaluator_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_dgf_kernel(tmp_path)


# --- malformed input ---


def test_malformed_json_is_typed_refusal(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    case_dir = _case(tmp_path / "ds", "a")
    (case_dir / "99_hidden_ground_truth.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(DGFAdmissionError) as exc:
        run_dgf_case(case_dir, dgf_root=root)
    assert exc.value.refusal_code == "DGF_MALFORMED"


@pytest.mark.parametrize(
    ("filename", "payload"),
    [
        ("99_hidden_ground_truth.json", {"canonical_truth": {"decisions": []}}),
        ("99_hidden_ground_truth.json", {"reference_decisions": []}),
        ("01_route_manifest.json", {"not_occurrences": []}),
        ("01_route_manifest.json", {"occurrences": {"a": 1}}),
        (
            "99_hidden_ground_truth.json",
            {"canonical_truth": {"decisions": []}, "reference_decisions": {"g": 1}},
        ),
    ],
)
def test_missing_or_mistyped_fields_are_refused(
    tmp_path: Path, filename: str, payload: dict
) -> None:
    root = _dgf_root(tmp_path)
    case_dir = _case(tmp_path / "ds", "a")
    _write_json(case_dir / filename, payload)
    with pytest.raises(DGFAdmissionError, match="DGF_MALFORMED"):
        run_dgf_case(case_dir, dgf_root=root)


def test_non_list_route_from_policy_is_refused(tmp_path: Path) -> None:
    root = _dgf_root(
        tmp_path, "def evaluate_route(case, occurrences):\n    return None\n"
    )
    case_dir = _case(tmp_path / "ds", "a")
    with pytest.raises(DGFAdmissionError, match="DGF_MALFORMED"):
        run_dgf_case(case_dir, dgf_root=root)


# --- duplicate delivery / reordering / partial routes ---


def test_duplicate_case_id_is_refused_not_double_counted(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a", case_id="same")
    _case(dataset, "b", case_id="same")
    with pytest.raises(DGFAdmissionError) as exc:
        run_dgf_dataset(dataset, dgf_root=root)
    assert exc.value.refusal_code == "DUPLICATE_CASE_ID"


def test_reordered_reference_route_fails_every_moved_gate(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    case_dir = _case(dataset, "a", gates=3)
    hidden_path = case_dir / "99_hidden_ground_truth.json"
    hidden = json.loads(hidden_path.read_text(encoding="utf-8"))
    hidden["reference_decisions"] = list(reversed(hidden["reference_decisions"]))
    _write_json(hidden_path, hidden)
    score = run_dgf_case(case_dir, dgf_root=root)
    assert score.route_match is False
    assert score.gate_total == 3
    assert score.gate_matches == 1  # only the middle gate stays in place


def test_truncated_policy_route_cannot_pass(tmp_path: Path) -> None:
    root = _dgf_root(
        tmp_path,
        EVALUATOR.replace("    return out", "    return out[:-1]"),
    )
    case_dir = _case(tmp_path / "ds", "a", gates=2)
    score = run_dgf_case(case_dir, dgf_root=root)
    assert (score.gate_total, score.gate_matches, score.route_match) == (2, 1, False)


def test_extra_policy_gate_cannot_pass(tmp_path: Path) -> None:
    root = _dgf_root(
        tmp_path,
        EVALUATOR.replace("    return out", "    return out + [out[-1]]"),
    )
    case_dir = _case(tmp_path / "ds", "a", gates=2)
    score = run_dgf_case(case_dir, dgf_root=root)
    assert (score.gate_total, score.gate_matches, score.route_match) == (3, 2, False)


# --- replay ---


def test_replay_is_byte_identical(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    for i in range(5):
        _case(dataset, f"c{i}", gates=i + 1)
    first = run_dgf_dataset(dataset, dgf_root=root)
    second = run_dgf_dataset(dataset, dgf_root=root)
    assert first == second
    assert all(score.output_digest.startswith("sha256:") for score in first[0])


def test_replay_mismatch_is_visible_in_output_digest(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    case_dir = _case(tmp_path / "ds", "a")
    before = run_dgf_case(case_dir, dgf_root=root)
    (root / "evaluator.py").write_text(
        EVALUATOR.replace("row = dict(decision)", "row = dict(decision, drift=1)"),
        encoding="utf-8",
    )
    after = run_dgf_case(case_dir, dgf_root=root)
    assert before.output_digest != after.output_digest
    assert after.route_match is False


# --- CLI anti-vacuity ---


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    # -S: the CLI is stdlib-only; skipping site-packages keeps an ambient
    # editable install of another checkout from shadowing the tree under test.
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    return subprocess.run(
        [sys.executable, "-S", str(CLI), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_cli_refuses_empty_dataset_instead_of_vacuous_pass(tmp_path: Path) -> None:
    # Before hardening: 0 cases -> routes_passed == cases -> exit 0.
    root = _dgf_root(tmp_path)
    (tmp_path / "empty").mkdir()
    proc = _run_cli("--dgf-root", str(root), "--dataset-root", str(tmp_path / "empty"))
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["refusal"] == "EMPTY_DATASET"


def test_cli_pass_and_fail_exit_codes_and_digest(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a")
    ok = _run_cli("--dgf-root", str(root), "--dataset-root", str(dataset))
    assert ok.returncode == 0, ok.stderr
    report = json.loads(ok.stdout)
    assert report["kernel_digest"] == dgf_evaluator_digest(root)
    assert report["summary"]["kernel_digest"] == report["kernel_digest"]
    assert report["llm_calls"] == 0

    _case(dataset, "b", expected=[{"gate": "g0", "disposition": "NO_GO"}])
    bad = _run_cli("--dgf-root", str(root), "--dataset-root", str(dataset))
    assert bad.returncode == 1


def test_cli_refuses_wrong_pinned_digest(tmp_path: Path) -> None:
    root = _dgf_root(tmp_path)
    dataset = tmp_path / "ds"
    _case(dataset, "a")
    proc = _run_cli(
        "--dgf-root",
        str(root),
        "--dataset-root",
        str(dataset),
        "--expected-kernel-digest",
        "sha256:" + "f" * 64,
    )
    assert proc.returncode != 0
    assert "KERNEL_DIGEST_MISMATCH" in proc.stderr
