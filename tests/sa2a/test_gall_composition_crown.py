from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from autofde_lab.sa2a.gall.composition import (
    GALLCompositionManifest,
    ReceiptReference,
)
from autofde_lab.sa2a.gall.crown import (
    MachineExperienceArtifact,
    compile_verified_experience,
    run_known_replay,
)


def _sha(seed: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def _write(path: Path, payload: dict) -> ReceiptReference:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    checkpoint = payload["_checkpoint"]
    repository = {
        "GALL-001": "seanchatmangpt/ggen",
        "GALL-002": "seanchatmangpt/ggen_igniter",
        "GALL-003": "seanchatmangpt/ash_a2a",
        "GALL-004": "seanchatmangpt/beam4pm",
    }[checkpoint]
    raw_payload = dict(payload)
    raw_payload.pop("_checkpoint")
    path.write_text(json.dumps(raw_payload, sort_keys=True), encoding="utf-8")
    return ReceiptReference.from_path(
        checkpoint=checkpoint,
        repository=repository,
        repo_sha=(checkpoint[-1] * 40),
        path=path,
    )


def _fixture(tmp_path: Path) -> GALLCompositionManifest:
    manufacturer = _sha("manufacturer")
    semantic = {
        "graph_digest": _sha("graph"),
        "projection_digest": _sha("projection"),
        "manufacturer_digest": manufacturer,
    }

    refs = (
        _write(
            tmp_path / "g1.json",
            {
                "_checkpoint": "GALL-001",
                "standing": "ALIVE",
                "subject": {"pack_digest": _sha("pack")},
                "replay": {"status": "PASS"},
            },
        ),
        _write(
            tmp_path / "g2.json",
            {
                "_checkpoint": "GALL-002",
                "standing": "ALIVE",
                "manufacturer_digest": manufacturer,
                "projection_digest": _sha("projection"),
            },
        ),
        _write(
            tmp_path / "g3.json",
            {
                "_checkpoint": "GALL-003",
                "standing": "ALIVE",
                "handoff_digest": _sha("handoff"),
                "semantic_subject": semantic,
                "consequence": "external_do",
            },
        ),
        _write(
            tmp_path / "g4.json",
            {
                "_checkpoint": "GALL-004",
                "standing": "ALIVE",
                "observer_receipt_digest": _sha("observer"),
                "gall_003_receipt_digest": _sha("handoff"),
                "semantic_subject_digest": _sha("semantic-subject"),
                "post_state_source": "database_read",
                "occurrence_count": 1,
            },
        ),
    )

    return GALLCompositionManifest(
        schema="autofde.gall.composition/v26.9.18",
        receipts=refs,
        autofde_lab_sha="a" * 40,
        planner_identity="fond-hddl:v26.9.18",
        cmca_identity="cmca:v26.9.18",
        machine_experience_compiler_identity="MachineExperienceCompiler:v1",
        corpus_identity=_sha("corpus"),
        semantic_key="incident:known-class",
    )


def test_exact_receipts_compile_experience_and_known_replay_is_zero_exploration(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    artifact, episode_1 = compile_verified_experience(
        manifest, deterministic_output={"repair": "apply-known-fix"}
    )
    output, episode_2 = run_known_replay(
        manifest, artifact, semantic_key=manifest.semantic_key
    )

    assert episode_1.standing == "PARTIAL_ALIVE"
    assert episode_1.gate_11 == "OPEN"
    assert output == {"repair": "apply-known-fix"}
    assert episode_2.frontier_resolution_calls == 0
    assert episode_2.llm_allocations == 0
    assert episode_2.planner_invocations == 0
    assert episode_2.machine_experience_hits == 1
    assert episode_2.reflex_executions == 1
    assert episode_2.gate_12 == "PASS"


def test_tampered_receipt_digest_refuses(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[0]
    Path(ref.path).write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="receipt digest mismatch"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_stale_or_mismatched_manufacturer_subject_refuses(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    gall3 = manifest.receipts[2]
    payload = json.loads(Path(gall3.path).read_text())
    payload["semantic_subject"]["manufacturer_digest"] = _sha("other")
    Path(gall3.path).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    updated = ReceiptReference.from_path(
        checkpoint=gall3.checkpoint,
        repository=gall3.repository,
        repo_sha=gall3.repo_sha,
        path=gall3.path,
    )
    manifest = replace(
        manifest,
        receipts=(manifest.receipts[0], manifest.receipts[1], updated, manifest.receipts[3]),
    )

    with pytest.raises(ValueError, match="manufacturer and GALL-003"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_known_artifact_rejects_composition_or_semantic_key_mismatch(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    artifact, _ = compile_verified_experience(
        manifest, deterministic_output={"repair": "known"}
    )

    with pytest.raises(KeyError):
        run_known_replay(manifest, artifact, semantic_key="other")

    moved = replace(manifest, corpus_identity=_sha("moved"))
    with pytest.raises(ValueError, match="composition identity mismatch"):
        run_known_replay(moved, artifact, semantic_key=artifact.semantic_key)


def test_fresh_python_process_can_execute_known_artifact(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    artifact, _ = compile_verified_experience(
        manifest, deterministic_output={"repair": "known"}
    )

    manifest_path = tmp_path / "manifest.json"
    experience_path = tmp_path / "experience.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    experience_path.write_text(json.dumps(artifact.to_dict()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_gall_composition_crown.py",
            "replay",
            "--manifest",
            str(manifest_path),
            "--experience",
            str(experience_path),
            "--semantic-key",
            manifest.semantic_key,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["machine_experience_hits"] == 1
    assert result["reflex_executions"] == 1
    assert result["frontier_resolution_calls"] == 0
    assert result["llm_allocations"] == 0
    assert result["planner_invocations"] == 0
