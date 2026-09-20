from __future__ import annotations

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
                repo_sha=f"{index:x}" * 40,
                evidence_digest=_digest(f"e{index}"),
                subject_digest=_digest(f"s{index}"),
                evidence_ceiling=ceilings[checkpoint],
            )
            for index, (checkpoint, repo) in enumerate(CHECKPOINT_REPOSITORIES.items(), start=1)
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
