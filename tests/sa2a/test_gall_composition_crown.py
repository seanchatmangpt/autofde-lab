from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from autofde_lab.sa2a.gall.composition import (
    EvidenceReference,
    GALLCompositionManifest,
    ReceiptReference,
)
from autofde_lab.sa2a.gall.crown import compile_verified_experience, run_known_replay


def _sha(seed: str) -> str:
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def _raw_sha(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _write_receipt(
    path: Path,
    checkpoint: str,
    repository: str,
    repo_sha: str,
    payload: dict,
) -> ReceiptReference:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return ReceiptReference.from_path(
        checkpoint=checkpoint,
        repository=repository,
        repo_sha=repo_sha,
        path=path,
    )


def _write_evidence(
    path: Path,
    evidence_class: str,
    repository: str,
    repo_sha: str,
    payload: dict,
) -> EvidenceReference:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return EvidenceReference.from_path(
        evidence_class=evidence_class,
        repository=repository,
        repo_sha=repo_sha,
        path=path,
    )


def _fixture(tmp_path: Path) -> GALLCompositionManifest:
    shas = {
        "g1": "1" * 40,
        "g2": "2" * 40,
        "g3": "3" * 40,
        "g4": "4" * 40,
        "weaver": "5" * 40,
    }
    pack_digest = _sha("pack")
    graph_digest = _sha("graph")
    projection_digest = _sha("projection")
    manufacturer_digest = _sha("manufacturer")
    command_fingerprint = _sha("command")

    g1_payload = {
        "schema": "https://ggen.dev/receipt/pack/v1",
        "spec": "RFC-GPACK-001-v26.9.17",
        "engine": {"name": "ggen-engine", "version": "6.0.0"},
        "subject": {
            "pack": "gall-pack",
            "version": "1.0.0",
            "pack_digest": pack_digest,
        },
        "dependencies": [
            {
                "name": "base",
                "version": "1.0.0",
                "digest": _sha("dep"),
                "scope": ["SEMANTICS"],
            }
        ],
        "composition": {
            "resolved_packs": [
                {
                    "name": "gall-pack",
                    "version": "1.0.0",
                    "digest": pack_digest,
                }
            ]
        },
        "graph": {"canonical_digest": graph_digest},
        "admission": {"gates_attempted": ["shape"], "refusals": []},
        "consequences": [
            {
                "target": "src/generated.rs",
                "operation": "MANAGED_WRITE",
                "sha256": _raw_sha("generated"),
            }
        ],
        "work_order": {
            "source": "work-order.ttl",
            "canonical_digest": _sha("work-order"),
        },
        "replay": {
            "status": "PASS",
            "source_receipt_sha256": _sha("source-receipt"),
            "replayed_receipt_sha256": _sha("replayed-receipt"),
            "court": "ggen-engine::replay::verify_project_replay",
        },
        "standing": "ALIVE",
    }
    g1 = _write_receipt(
        tmp_path / "g1.json",
        "GALL-001",
        "seanchatmangpt/ggen",
        shas["g1"],
        g1_payload,
    )

    g2_payload = {
        "repo_sha": shas["g2"],
        "gall_001_receipt_digest": g1.receipt_digest,
        "graph_digest": graph_digest,
        "manifest_identity": {
            "name": "gall-pack",
            "version": "26.9.18",
            "description": "fixture",
        },
        "profile": "Core1",
        "manufacturer_digest": manufacturer_digest,
        "generator_tasks": ["ash.gen.domain", "ash.gen.resource"],
        "mix_lock_digest": _sha("mix.lock"),
        "toolchain": {"elixir": "1.17", "otp": "27", "igniter": "pinned"},
        "projection_digest": projection_digest,
        "post_run_hash": projection_digest,
        "attestation_digest": _sha("attestation"),
        "generated_files": [
            {"path": "lib/generated.ex", "digest": projection_digest}
        ],
        "regeneration": "PASS",
        "standing": "ALIVE",
    }
    g2 = _write_receipt(
        tmp_path / "g2.json",
        "GALL-002",
        "seanchatmangpt/ggen_igniter",
        shas["g2"],
        g2_payload,
    )

    g3_payload = {
        "receipt_id": "rcpt-003",
        "command_id": "cmd-003",
        "capability_id": "Example.Resource.change",
        "command_fingerprint": command_fingerprint,
        "semantic_subject": {
            "graph_digest": graph_digest,
            "projection_digest": projection_digest,
            "manufacturer_digest": manufacturer_digest,
            "ephemeral?": False,
        },
        "manufacturer_subject_digest": manufacturer_digest,
        "authority_grant_digest": _sha("authority"),
        "idempotency_key": "idem-003",
        "actuation_id": "act-003",
        "consequence": "change",
        "binding_digest": _sha("binding"),
        "receipt_standing": "alive",
        "terminal_status": "executed",
        "status": "completed",
        "replayed?": False,
        "handoff_digest": _sha("handoff"),
    }
    g3 = _write_receipt(
        tmp_path / "g3.json",
        "GALL-003",
        "seanchatmangpt/ash_a2a",
        shas["g3"],
        g3_payload,
    )

    g4_payload = {
        "schema": "beam4pm.gall.observer/v26.9.18",
        "standing": "ALIVE",
        "gall_003_receipt_digest": g3_payload["handoff_digest"],
        "producer_sha": shas["g3"],
        "work_order_digest": _sha("work-order"),
        "semantic_subject_digest": _sha("semantic-subject-erlang-term"),
        "capability_id": g3_payload["capability_id"],
        "command_fingerprint": command_fingerprint,
        "independent_observer_id": "BeamPM.Gall.Observer004",
        "post_state_digest": _sha("post-state"),
        "post_state_source": "database_read",
        "ocel_digest": _sha("ocel"),
        "ordering_witnesses": [
            {"before": "receipt_prepared", "after": "do_attempted"},
            {"before": "do_attempted", "after": "post_state_observed"},
        ],
        "occurrence_count": 1,
        "falsifiers_attempted": [
            "actuator_self_report_only",
            "identity_mismatch",
            "missing_prepared_event",
            "double_consequence",
        ],
        "authority": "none",
        "observer_receipt_digest": _sha("observer-erlang-term"),
    }
    g4 = _write_receipt(
        tmp_path / "g4.json",
        "GALL-004",
        "seanchatmangpt/beam4pm",
        shas["g4"],
        g4_payload,
    )

    weaver_payload = {
        "schema": "beam4pm.gall.weaver-court/v26.9.18",
        "standing": "PARTIAL_ALIVE",
        "authority": "none",
        "weaver_version": "weaver 0.26.1",
        "registry_manifest_digest": _sha("registry-manifest"),
        "registry_definition_digest": _sha("registry-definition"),
        "live_check_report_digest": _sha("live-check"),
        "otlp_round_trip": True,
        "negative_unknown_authority_attribute_refused": True,
        "evidence_ceiling": (
            "qualification-registry; generated runtime semconv projection "
            "and independent postcondition remain separate courts"
        ),
    }
    weaver_payload["receipt_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            weaver_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    telemetry = _write_evidence(
        tmp_path / "g4-weaver.json",
        "GALL-004-TELEMETRY",
        "seanchatmangpt/beam4pm",
        shas["weaver"],
        weaver_payload,
    )

    return GALLCompositionManifest(
        schema="autofde.gall.composition/v26.9.18",
        receipts=(g1, g2, g3, g4),
        evidence=(telemetry,),
        autofde_lab_sha="a" * 40,
        planner_identity="fond-hddl:v26.9.18",
        cmca_identity="cmca:v26.9.18",
        machine_experience_compiler_identity="MachineExperienceCompiler:v1",
        corpus_identity=_sha("corpus"),
        semantic_key="incident:known-class",
    )


def test_typed_upstream_receipts_compile_and_keep_evidence_predicates_separate(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    artifact, episode_1 = compile_verified_experience(
        manifest,
        deterministic_output={"repair": "apply-known-fix"},
    )
    output, episode_2 = run_known_replay(
        manifest,
        artifact,
        semantic_key=manifest.semantic_key,
    )

    assert episode_1.telemetry_valid is True
    assert episode_1.process_valid is True
    assert episode_1.postcondition_valid is True
    assert episode_1.learned_candidate_ceiling == "CANDIDATE"
    assert episode_1.standing == "PARTIAL_ALIVE"
    assert output == {"repair": "apply-known-fix"}
    assert episode_2.frontier_resolution_calls == 0
    assert episode_2.llm_allocations == 0
    assert episode_2.planner_invocations == 0
    assert episode_2.machine_experience_hits == 1
    assert episode_2.reflex_executions == 1


def test_generic_hash_only_gall_001_payload_is_refused(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[0]
    Path(ref.path).write_text(
        json.dumps({"checkpoint": "GALL-001", "standing": "ALIVE"}),
        encoding="utf-8",
    )
    moved = ReceiptReference.from_path(
        checkpoint=ref.checkpoint,
        repository=ref.repository,
        repo_sha=ref.repo_sha,
        path=ref.path,
    )
    manifest = replace(manifest, receipts=(moved, *manifest.receipts[1:]))

    with pytest.raises(ValueError, match="portable receipt schema"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_stale_gall_002_repo_sha_with_valid_receipt_is_refused(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[1]
    stale = replace(ref, repo_sha="9" * 40)
    manifest = replace(
        manifest,
        receipts=(manifest.receipts[0], stale, *manifest.receipts[2:]),
    )

    with pytest.raises(ValueError, match="handoff repo_sha"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_tampered_receipt_digest_refuses_before_composition(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    Path(manifest.receipts[2].path).write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="receipt digest mismatch"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_telemetry_pass_does_not_substitute_for_postcondition_failure(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[3]
    payload = json.loads(Path(ref.path).read_text())
    payload["post_state_source"] = "actuator_reply"
    Path(ref.path).write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    changed = ReceiptReference.from_path(
        checkpoint=ref.checkpoint,
        repository=ref.repository,
        repo_sha=ref.repo_sha,
        path=ref.path,
    )
    manifest = replace(manifest, receipts=(*manifest.receipts[:3], changed))

    with pytest.raises(ValueError, match="post-state is not independent"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_process_postcondition_do_not_imply_telemetry_valid(tmp_path: Path) -> None:
    manifest = replace(_fixture(tmp_path), evidence=())

    with pytest.raises(ValueError, match="typed GALL-004 telemetry receipt"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_candidate_evidence_cannot_self_promote_into_gall_receipt(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[2]
    payload = json.loads(Path(ref.path).read_text())
    payload["standing"] = "CANDIDATE"
    payload["authorizes_actuation"] = False
    Path(ref.path).write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    candidate = ReceiptReference.from_path(
        checkpoint=ref.checkpoint,
        repository=ref.repository,
        repo_sha=ref.repo_sha,
        path=ref.path,
    )
    manifest = replace(
        manifest,
        receipts=(
            *manifest.receipts[:2],
            candidate,
            manifest.receipts[3],
        ),
    )

    with pytest.raises(ValueError, match="remains CANDIDATE"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_cross_repo_identity_links_are_fail_closed(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[3]
    payload = json.loads(Path(ref.path).read_text())
    payload["producer_sha"] = "9" * 40
    Path(ref.path).write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )
    changed = ReceiptReference.from_path(
        checkpoint=ref.checkpoint,
        repository=ref.repository,
        repo_sha=ref.repo_sha,
        path=ref.path,
    )
    manifest = replace(manifest, receipts=(*manifest.receipts[:3], changed))

    with pytest.raises(ValueError, match="exact admitted GALL-003 producer SHA"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_machine_experience_replay_rejects_evidence_identity_drift(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    artifact, _ = compile_verified_experience(
        manifest,
        deterministic_output={"repair": "known"},
    )
    moved = replace(manifest, evidence=())

    with pytest.raises(ValueError, match="composition identity mismatch"):
        run_known_replay(
            moved,
            artifact,
            semantic_key=artifact.semantic_key,
        )


def test_fresh_python_process_can_execute_known_artifact(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    artifact, _ = compile_verified_experience(
        manifest,
        deterministic_output={"repair": "known"},
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
        env=os.environ.copy(),
    )
    result = json.loads(completed.stdout)
    assert result["machine_experience_hits"] == 1
    assert result["reflex_executions"] == 1
    assert result["frontier_resolution_calls"] == 0
    assert result["llm_allocations"] == 0
    assert result["planner_invocations"] == 0
