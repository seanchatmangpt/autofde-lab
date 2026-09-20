from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from autofde_lab.sa2a.composition.resolver import (
    REFUSED_CHECKPOINT_CHAIN_MISMATCH,
    SubjectResolutionError,
    SubjectResolver,
)
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


REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
        "engine": {"name": "ggen", "version": "6.0.0"},
        "toolchain": {"rustc": "rustc 1.91.0", "cargo": "cargo 1.91.0"},
        "environment": {
            "os": "linux",
            "arch": "x86_64",
            "family": "unix",
            "variables_count": 3,
            "variables_sha256": _sha("bounded-environment"),
        },
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
            "reconstructed_receipt_sha256": _sha("reconstructed-receipt"),
            "court": "ggen-engine::replay::verify_project_replay",
            "identity": {
                field: {"sha256": _sha(f"identity:{field}"), "equal": True}
                for field in (
                    "schema",
                    "spec",
                    "engine",
                    "subject",
                    "dependencies",
                    "composition",
                    "graph",
                    "work_order",
                    "admission",
                    "consequences",
                    "toolchain",
                    "environment",
                    "standing",
                )
            },
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
        "receipt_standing": "durable",
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


def _resolver_manifest(manifest: GALLCompositionManifest) -> dict:
    standing = {
        "GALL-001": "ALIVE",
        "GALL-002": "ALIVE",
        "GALL-003": "DURABLE",
        "GALL-004": "ALIVE",
    }
    evidence_class = {
        "GALL-001": "portable_replay",
        "GALL-002": "project_manufacturer",
        "GALL-003": "command_receipt",
        "GALL-004": "independent_observer",
    }
    return {
        "release_id": "v26.9.18-gall-crown",
        "repositories": [
            {"name": "autofde-lab", "exact_sha": manifest.autofde_lab_sha}
        ],
        "artifacts": [{"artifact_id": "crown", "digest": "b" * 64}],
        "root_manifest_digest": "c" * 64,
        "semantic_profile": "SA2A-GALL",
        "court_revision": "v26.9.18",
        "falsifier_corpus_digest": "d" * 64,
        "query_set_digest": "e" * 64,
        "environment_identity": "test-env",
        "work_order_digest": _sha("work-order"),
        "checkpoints": [
            {
                "checkpoint_id": ref.checkpoint,
                "repository": ref.repository,
                "exact_sha": ref.repo_sha,
                "receipt_path": ref.path,
                "receipt_digest": ref.receipt_digest,
                "standing": standing[ref.checkpoint],
                "evidence_class": evidence_class[ref.checkpoint],
            }
            for ref in manifest.receipts
        ],
    }


def test_subject_resolver_admits_actual_typed_upstream_receipt_contracts(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)

    subject = SubjectResolver().resolve_gall(_resolver_manifest(manifest))

    assert [item.checkpoint_id for item in subject.checkpoints] == [
        "GALL-001",
        "GALL-002",
        "GALL-003",
        "GALL-004",
    ]


def test_subject_resolver_refuses_cross_repo_receipt_chain_mismatch(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[3]
    payload = json.loads(Path(ref.path).read_text())
    payload["command_fingerprint"] = _sha("different-command")
    Path(ref.path).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    changed = ReceiptReference.from_path(
        checkpoint=ref.checkpoint,
        repository=ref.repository,
        repo_sha=ref.repo_sha,
        path=ref.path,
    )
    manifest = replace(manifest, receipts=(*manifest.receipts[:3], changed))

    with pytest.raises(SubjectResolutionError) as exc_info:
        SubjectResolver().resolve_gall(_resolver_manifest(manifest))

    assert exc_info.value.code == REFUSED_CHECKPOINT_CHAIN_MISMATCH


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


def test_gall_001_replay_requires_complete_recomputed_identity_witness(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[0]
    payload = json.loads(Path(ref.path).read_text())
    payload["replay"]["identity"].pop("environment")
    Path(ref.path).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    changed = ReceiptReference.from_path(
        checkpoint=ref.checkpoint, repository=ref.repository, repo_sha=ref.repo_sha, path=ref.path
    )
    manifest = replace(manifest, receipts=(changed, *manifest.receipts[1:]))

    with pytest.raises(ValueError, match="recomputed identity field set"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


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



def test_multi_pack_gall_001_allows_one_exact_subject_match(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[0]
    payload = json.loads(Path(ref.path).read_text())
    payload["composition"]["resolved_packs"].append(
        {
            "name": "second-pack",
            "version": "1.0.0",
            "digest": _sha("second-pack"),
        }
    )
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
    g2_ref = manifest.receipts[1]
    g2_payload = json.loads(Path(g2_ref.path).read_text())
    g2_payload["gall_001_receipt_digest"] = changed.receipt_digest
    Path(g2_ref.path).write_text(
        json.dumps(g2_payload, sort_keys=True),
        encoding="utf-8",
    )
    changed_g2 = ReceiptReference.from_path(
        checkpoint=g2_ref.checkpoint,
        repository=g2_ref.repository,
        repo_sha=g2_ref.repo_sha,
        path=g2_ref.path,
    )
    manifest = replace(
        manifest,
        receipts=(changed, changed_g2, *manifest.receipts[2:]),
    )

    artifact, episode_1 = compile_verified_experience(
        manifest,
        deterministic_output={"x": 1},
    )
    assert artifact.source_receipts[0] == changed.receipt_digest
    assert episode_1.standing == "PARTIAL_ALIVE"


def test_duplicate_subject_identity_is_refused(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[0]
    payload = json.loads(Path(ref.path).read_text())
    payload["composition"]["resolved_packs"].append(
        {
            "name": payload["subject"]["pack"],
            "version": payload["subject"]["version"],
            "digest": payload["subject"]["pack_digest"],
        }
    )
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
    manifest = replace(manifest, receipts=(changed, *manifest.receipts[1:]))

    with pytest.raises(ValueError, match="exactly one matching member"):
        compile_verified_experience(manifest, deterministic_output={"x": 1})


def test_durable_pending_gall_003_can_be_resolved_by_independent_gall_004(
    tmp_path: Path,
) -> None:
    manifest = _fixture(tmp_path)
    ref = manifest.receipts[2]
    payload = json.loads(Path(ref.path).read_text())
    payload["status"] = "pending"
    payload["terminal_status"] = None
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
    manifest = replace(
        manifest,
        receipts=(
            *manifest.receipts[:2],
            changed,
            manifest.receipts[3],
        ),
    )

    _, episode_1 = compile_verified_experience(
        manifest,
        deterministic_output={"x": 1},
    )
    assert episode_1.process_valid is True
    assert episode_1.postcondition_valid is True


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


def test_compile_cannot_mint_gate_12_and_fresh_replay_can(tmp_path: Path) -> None:
    manifest = replace(_fixture(tmp_path), autofde_lab_sha=_repo_head())
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "output.json"
    court_dir = tmp_path / "court"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    output_path.write_text(json.dumps({"repair": "known"}), encoding="utf-8")

    compile_run = subprocess.run(
        [
            sys.executable,
            "scripts/run_gall_composition_crown.py",
            "compile",
            "--manifest",
            str(manifest_path),
            "--output-json",
            str(output_path),
            "--out-dir",
            str(court_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    compile_result = json.loads(compile_run.stdout)
    assert compile_result["gate_12"] == "OPEN"
    assert (court_dir / "machine-experience.json").is_file()
    assert not (court_dir / "episode-2-receipt.json").exists()
    assert not (court_dir / "gall-005-crown-receipt.json").exists()

    replay_run = subprocess.run(
        [
            sys.executable,
            "scripts/run_gall_composition_crown.py",
            "replay",
            "--manifest",
            str(court_dir / "gall-composition-manifest.json"),
            "--experience",
            str(court_dir / "machine-experience.json"),
            "--semantic-key",
            manifest.semantic_key,
            "--out-dir",
            str(court_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    result = json.loads(replay_run.stdout)
    assert result["machine_experience_hits"] == 1
    assert result["reflex_executions"] == 1
    assert result["frontier_resolution_calls"] == 0
    assert result["llm_allocations"] == 0
    assert result["planner_invocations"] == 0
    assert (court_dir / "episode-2-receipt.json").is_file()
    crown = json.loads((court_dir / "gall-005-crown-receipt.json").read_text())
    assert crown["gate_12"] == "PASS"
    assert crown["gate_11"] == "OPEN"
    assert crown["cross_repo_standing"] == "PARTIAL_ALIVE"


def test_runner_refuses_manifest_for_different_autofde_head(tmp_path: Path) -> None:
    manifest = _fixture(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "output.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
    output_path.write_text(json.dumps({"repair": "known"}), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_gall_composition_crown.py",
            "compile",
            "--manifest",
            str(manifest_path),
            "--output-json",
            str(output_path),
            "--out-dir",
            str(tmp_path / "court"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )
    assert completed.returncode == 65
    assert "REFUSED_EXACT_HEAD" in completed.stderr

