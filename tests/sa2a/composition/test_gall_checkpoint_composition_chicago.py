"""Chicago tests for the GALL-005 cross-repository checkpoint composition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from autofde_lab.sa2a.composition.gall_artifact import (
    GallArtifactError,
    build_portable_artifact,
    verify_portable_artifact,
)
from autofde_lab.sa2a.composition.resolver import (
    REFUSED_CHECKPOINT_RECEIPT_CONTRACT,
    REFUSED_CHECKPOINT_RECEIPT_DRIFT,
    SubjectResolutionError,
    SubjectResolver,
)


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _manifest(tmp_path: Path) -> dict:
    checkpoints = []
    for index in range(1, 5):
        checkpoint_id = f"GALL-{index:03d}"
        relative = f"receipts/{checkpoint_id}.json"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps({"checkpoint": checkpoint_id, "standing": "PARTIAL_ALIVE"}, sort_keys=True).encode()
        path.write_bytes(raw)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_id,
                "repository": f"repo-{index}",
                "exact_sha": f"{index}" * 40,
                "receipt_path": relative,
                "receipt_digest": _digest_bytes(raw),
                "standing": "PARTIAL_ALIVE",
                "evidence_class": "local_test",
                "work_order_digest": "sha256:" + f"{index}" * 64,
            }
        )

    return {
        "release_id": "v26.9.18-gall-crown",
        "repositories": [{"name": "autofde-lab", "exact_sha": "a" * 40}],
        "artifacts": [{"artifact_id": "crown", "digest": "b" * 64}],
        "root_manifest_digest": "c" * 64,
        "semantic_profile": "SA2A-GALL",
        "court_revision": "v26.9.18",
        "falsifier_corpus_digest": "d" * 64,
        "query_set_digest": "e" * 64,
        "environment_identity": "test-env",
        "work_order_digest": "sha256:" + "f" * 64,
        "checkpoints": checkpoints,
    }


def test_gall_subject_refuses_hash_only_receipt_files(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    with pytest.raises(SubjectResolutionError) as exc_info:
        SubjectResolver().resolve_gall(manifest, base_dir=tmp_path)

    assert exc_info.value.code == REFUSED_CHECKPOINT_RECEIPT_CONTRACT


def test_mutated_upstream_receipt_is_refused_before_composition(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    (tmp_path / "receipts/GALL-003.json").write_text("tampered", encoding="utf-8")

    with pytest.raises(SubjectResolutionError) as exc_info:
        SubjectResolver().resolve_gall(manifest, base_dir=tmp_path)

    assert exc_info.value.code == REFUSED_CHECKPOINT_RECEIPT_DRIFT


def test_portable_artifact_tampering_is_refused_without_re_actuation(tmp_path: Path) -> None:
    subject = SubjectResolver().resolve(_manifest(tmp_path))
    artifact = build_portable_artifact(subject, standing="PARTIAL_ALIVE")
    artifact["standing"] = "ALIVE"

    with pytest.raises(GallArtifactError) as exc_info:
        verify_portable_artifact(artifact)

    assert exc_info.value.code == "REFUSED_ARTIFACT_DIGEST"
