"""Reversible mutation-court falsifiers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from autofde_lab.iec.crowns.model import IECRefusal
from autofde_lab.iec.crowns.prometheus_mutation import (
    MUTATION_MANIFEST_SCHEMA,
    parse_mutation_manifest,
    run_mutation_court,
)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def subject(tmp_path) -> Path:
    root = tmp_path / "treated"
    root.mkdir()
    (root / "logic.txt").write_text("ALLOW\n", encoding="utf-8")
    return root


def manifest(*, detection_mode: str = "exit_changed") -> dict:
    return {
        "schema": MUTATION_MANIFEST_SCHEMA,
        "repository": "org/repo",
        "base_commit": "abc",
        "patch_digest": "sha256:patch",
        "verifier": {
            "argv": ["verify"],
            "cwd": ".",
            "expected_exit": 0,
            "timeout_seconds": 1,
            "detection_mode": detection_mode,
        },
        "mutations": [
            {
                "id": "flip-allow",
                "path": "logic.txt",
                "before_sha256": digest(b"ALLOW\n"),
                "operator": "replace_once",
                "old": "ALLOW",
                "new": "DENY",
            }
        ],
    }


def exit_detector(argv, *, cwd, capture_output, timeout, check):
    del argv, capture_output, timeout, check
    text = (Path(cwd) / "logic.txt").read_text(encoding="utf-8")
    return SimpleNamespace(
        returncode=1 if "DENY" in text else 0,
        stdout=b"",
        stderr=b"",
    )


def test_detected_gate_requires_every_declared_mutation_to_be_caught(
    tmp_path,
) -> None:
    root = subject(tmp_path)
    result = run_mutation_court(
        manifest(),
        root=root,
        executor=exit_detector,
    )
    assert result["gate_strength"] == "detected"
    assert result["standing"] == "OBSERVED"
    assert result["summary"] == {
        "declared": 1,
        "executed": 1,
        "detected": 1,
        "survived": 0,
        "unsupported": 0,
    }
    assert result["receipt_id"].startswith("sha256:")
    assert (root / "logic.txt").read_text(encoding="utf-8") == "ALLOW\n"


def test_surviving_mutation_is_blind(tmp_path) -> None:
    root = subject(tmp_path)

    def blind(argv, **kwargs):
        del argv, kwargs
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    result = run_mutation_court(
        manifest(),
        root=root,
        executor=blind,
    )
    assert result["gate_strength"] == "blind"
    assert result["summary"]["survived"] == 1


def test_unavailable_mutation_observation_is_not_mislabeled_blind(
    tmp_path,
) -> None:
    root = subject(tmp_path)

    def unavailable_on_mutant(argv, *, cwd, **kwargs):
        del argv, kwargs
        text = (Path(cwd) / "logic.txt").read_text(encoding="utf-8")
        if "DENY" in text:
            raise FileNotFoundError("verifier disappeared")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    result = run_mutation_court(
        manifest(),
        root=root,
        executor=unavailable_on_mutant,
    )
    assert result["gate_strength"] == "none"
    assert result["standing"] == "PARTIAL"
    assert result["summary"]["unsupported"] == 1


def test_vacuous_gate_has_passing_baseline_but_no_mutation_falsifier(
    tmp_path,
) -> None:
    root = subject(tmp_path)
    doc = manifest()
    doc["mutations"] = []
    result = run_mutation_court(
        doc,
        root=root,
        executor=exit_detector,
    )
    assert result["gate_strength"] == "vacuous"
    assert result["summary"]["declared"] == 0


def test_invalid_baseline_executes_no_mutations(tmp_path) -> None:
    root = subject(tmp_path)

    def broken_baseline(argv, **kwargs):
        del argv, kwargs
        return SimpleNamespace(returncode=2, stdout=b"", stderr=b"")

    result = run_mutation_court(
        manifest(),
        root=root,
        executor=broken_baseline,
    )
    assert result["gate_strength"] == "none"
    assert result["standing"] == "INVALID_BASELINE"
    assert result["summary"]["executed"] == 0


def test_stdout_detection_can_catch_semantic_change_without_exit_change(
    tmp_path,
) -> None:
    root = subject(tmp_path)

    def stdout_detector(argv, *, cwd, **kwargs):
        del argv, kwargs
        payload = (Path(cwd) / "logic.txt").read_bytes()
        return SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

    result = run_mutation_court(
        manifest(detection_mode="stdout_changed"),
        root=root,
        executor=stdout_detector,
    )
    assert result["gate_strength"] == "detected"


def test_preimage_digest_prevents_mutating_wrong_subject(tmp_path) -> None:
    root = subject(tmp_path)
    doc = manifest()
    doc["mutations"][0]["before_sha256"] = "sha256:wrong"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_MUTATION_PREIMAGE_MISMATCH",
    ):
        run_mutation_court(
            doc,
            root=root,
            executor=exit_detector,
        )
    assert (root / "logic.txt").read_text(encoding="utf-8") == "ALLOW\n"


def test_replace_once_refuses_ambiguous_cardinality(tmp_path) -> None:
    root = subject(tmp_path)
    (root / "logic.txt").write_text(
        "ALLOW ALLOW\n",
        encoding="utf-8",
    )
    doc = manifest()
    doc["mutations"][0]["before_sha256"] = digest(b"ALLOW ALLOW\n")
    with pytest.raises(
        IECRefusal,
        match="REFUSED_MUTATION_CARDINALITY",
    ):
        run_mutation_court(
            doc,
            root=root,
            executor=exit_detector,
        )


@pytest.mark.parametrize(
    "operator",
    ["append_text", "write_text", "delete_once"],
)
def test_other_reversible_operator_shapes_are_executable(
    tmp_path,
    operator,
) -> None:
    root = subject(tmp_path)
    doc = manifest()
    row = doc["mutations"][0]
    row["operator"] = operator
    if operator == "append_text":
        row.pop("old")
        row.pop("new")
        row["text"] = "DENY\n"
    elif operator == "write_text":
        row.pop("old")
        row.pop("new")
        row["text"] = "DENY\n"
    else:
        row.pop("new")

    result = run_mutation_court(
        doc,
        root=root,
        executor=exit_detector,
    )
    assert result["summary"]["executed"] == 1
    assert (root / "logic.txt").read_text(encoding="utf-8") == "ALLOW\n"


def test_manifest_refuses_escape_duplicate_or_unknown_operator() -> None:
    escaped = manifest()
    escaped["mutations"][0]["path"] = "../logic.txt"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_INVALID_MUTATION_MANIFEST",
    ):
        parse_mutation_manifest(escaped)

    duplicate = manifest()
    duplicate["mutations"].append(dict(duplicate["mutations"][0]))
    with pytest.raises(
        IECRefusal,
        match="REFUSED_INVALID_MUTATION_MANIFEST",
    ):
        parse_mutation_manifest(duplicate)

    unknown = manifest()
    unknown["mutations"][0]["operator"] = "arbitrary_python"
    with pytest.raises(
        IECRefusal,
        match="REFUSED_INVALID_MUTATION_MANIFEST",
    ):
        parse_mutation_manifest(unknown)


def test_receipt_identity_excludes_wall_time_and_scratch_paths(tmp_path) -> None:
    root = subject(tmp_path)
    first = run_mutation_court(
        manifest(),
        root=root,
        executor=exit_detector,
    )
    second = run_mutation_court(
        manifest(),
        root=root,
        executor=exit_detector,
    )
    assert first["receipt_id"] == second["receipt_id"]
    assert (
        first["mutations"][0]["verifier"]["semantic_id"]
        == second["mutations"][0]["verifier"]["semantic_id"]
    )
