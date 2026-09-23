from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from autofde_lab.sa2a.gall.process_spine import (
    CHECKPOINT_REPOSITORIES,
    ProcessCheckpointReference,
    ProcessSpine,
)


def _digest(seed: str) -> str:
    return "sha256:" + (seed.encode().hex() + "0" * 64)[:64]


def _spine() -> ProcessSpine:
    ceilings = {
        "GALL-015": "REFERENCE_CORPUS",
        "GALL-016": "COMPILE_COMPUTE",
        "GALL-017": "QUERY_COMPUTE",
        "GALL-018": "DISCOVERY_CANDIDATE",
        "GALL-019": "PREDICTION_CANDIDATE",
        "GALL-020": "COMPUTE_ONLY",
        "GALL-021": "COMPUTE_ONLY",
        "GALL-022": "COMPILE_COMPUTE",
        "GALL-023": "QUERY_COMPUTE",
        "GALL-024": "OBSERVE",
        "GALL-025": "COMPARE",
        "GALL-026": "ANALYZE",
        "GALL-027": "OBSERVE_ACCOUNT",
        "GALL-028": "RECOMMEND",
        "GALL-029": "ADMIT_ONLY",
        "GALL-030": "AUTHORIZED_DO",
    }
    return ProcessSpine(
        schema="autofde.gall.process-spine/v26.9.18",
        checkpoints=tuple(
            ProcessCheckpointReference(
                checkpoint=checkpoint,
                repository=repo,
                repo_sha=f"{index:040x}",  # deterministic exact 40-hex (f"{index:x}"*40 breaks for index >= 16)
                evidence_digest=_digest(f"e{index}"),
                subject_digest=_digest(f"s{index}"),
                evidence_ceiling=ceilings[checkpoint],
            )
            for index, (checkpoint, repo) in enumerate(
                CHECKPOINT_REPOSITORIES.items(), start=1
            )
        ),
    )


def test_exact_typed_process_spine_is_content_addressed() -> None:
    spine = _spine()
    spine.validate()
    assert spine.digest.startswith("sha256:")
    assert spine.digest == _spine().digest


def test_missing_checkpoint_and_repository_substitution_fail_closed() -> None:
    spine = _spine()
    with pytest.raises(ValueError, match="requires exactly"):
        replace(spine, checkpoints=spine.checkpoints[:-1]).validate()

    bad = list(spine.checkpoints)
    bad[0] = replace(bad[0], repository="seanchatmangpt/beam4pm")
    with pytest.raises(ValueError, match="repository mismatch"):
        replace(spine, checkpoints=tuple(bad)).validate()


def test_authority_cannot_leak_upstream_of_gall_030() -> None:
    spine = _spine()
    bad = list(spine.checkpoints)
    gall_028 = next(i for i, item in enumerate(bad) if item.checkpoint == "GALL-028")
    bad[gall_028] = replace(bad[gall_028], evidence_ceiling="AUTHORIZED_DO")
    with pytest.raises(ValueError, match="cannot grant DO"):
        replace(spine, checkpoints=tuple(bad)).validate()

    gall_029 = next(i for i, item in enumerate(bad) if item.checkpoint == "GALL-029")
    bad = list(spine.checkpoints)
    bad[gall_029] = replace(bad[gall_029], evidence_ceiling="AUTHORIZED_DO")
    with pytest.raises(ValueError, match="candidate admission only"):
        replace(spine, checkpoints=tuple(bad)).validate()


def test_ex4pm_predecessor_chain_is_required_and_cannot_gain_do_authority() -> None:
    spine = _spine()
    ids = {item.checkpoint for item in spine.checkpoints}
    assert {f"GALL-{index:03d}" for index in range(15, 21)} <= ids

    gall_019 = next(
        i for i, item in enumerate(spine.checkpoints) if item.checkpoint == "GALL-019"
    )
    bad = list(spine.checkpoints)
    bad[gall_019] = replace(bad[gall_019], evidence_ceiling="AUTHORIZED_DO")
    with pytest.raises(ValueError, match="PREDICTION_CANDIDATE"):
        replace(spine, checkpoints=tuple(bad)).validate()


def _exact_spine_and_evidence() -> tuple[ProcessSpine, dict[str, bytes]]:
    """Build the full GALL-015..030 spine with independently hashed evidence.

    Carried over from gall/integrate-021-030-process-spine and extended to the
    full spine range so verify_exact_evidence's whole-manifest invariant is
    exercised.
    """
    template = _spine()
    refs = []
    evidence = {}
    for item in template.checkpoints:
        receipt = {
            "checkpoint": item.checkpoint,
            "repository": item.repository,
            "repo_sha": item.repo_sha,
            "subject_digest": item.subject_digest,
            "evidence_ceiling": item.evidence_ceiling,
            "authority": "NONE",
        }
        if item.checkpoint == "GALL-030":
            receipt["authority_source"] = "INDEPENDENT"
            receipt["do_route"] = "AshA2A.CommandBus"
        raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        evidence[item.checkpoint] = raw
        refs.append(
            replace(
                item,
                evidence_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
            )
        )
    return replace(template, checkpoints=tuple(refs)), evidence


def test_exact_evidence_binds_sha_digest_subject_repository_and_authority() -> None:
    spine, evidence = _exact_spine_and_evidence()
    spine.verify_exact_evidence(evidence)

    item = spine.checkpoints[0]
    stale = json.loads(evidence[item.checkpoint])
    stale["repo_sha"] = "f" * 40
    tampered = dict(evidence)
    tampered[item.checkpoint] = json.dumps(
        stale, sort_keys=True, separators=(",", ":")
    ).encode()
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        spine.verify_exact_evidence(tampered)

    gall_030 = json.loads(evidence["GALL-030"])
    gall_030["authority_source"] = "FINDING"
    raw = json.dumps(gall_030, sort_keys=True, separators=(",", ":")).encode()
    refs = tuple(
        replace(item, evidence_digest="sha256:" + hashlib.sha256(raw).hexdigest())
        if item.checkpoint == "GALL-030"
        else item
        for item in spine.checkpoints
    )
    bad_evidence = dict(evidence)
    bad_evidence["GALL-030"] = raw
    with pytest.raises(ValueError, match="independently supplied authority"):
        replace(spine, checkpoints=refs).verify_exact_evidence(bad_evidence)


def test_gall_030_refuses_non_commandbus_do_route() -> None:
    spine, evidence = _exact_spine_and_evidence()
    receipt = json.loads(evidence["GALL-030"])
    receipt["do_route"] = "direct"
    raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    refs = tuple(
        replace(item, evidence_digest="sha256:" + hashlib.sha256(raw).hexdigest())
        if item.checkpoint == "GALL-030"
        else item
        for item in spine.checkpoints
    )
    bad_evidence = dict(evidence)
    bad_evidence["GALL-030"] = raw
    with pytest.raises(ValueError, match="CommandBus"):
        replace(spine, checkpoints=refs).verify_exact_evidence(bad_evidence)
