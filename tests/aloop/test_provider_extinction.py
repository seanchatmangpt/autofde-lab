# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP-004 provider-extinction semantic conservation court."""

from __future__ import annotations

import dataclasses

import pytest

from autofde_lab.aloop.provider_extinction import (
    ArtifactHandoff,
    ExecutionSemantics,
    FailureInjection,
    compare_provider_substitution,
    qualify_fresh_job_recovery,
)


@pytest.fixture
def claude_run() -> ExecutionSemantics:
    return ExecutionSemantics(
        workorder_digest="sha256:workorder",
        command_digest="sha256:command",
        candidate_digest="sha256:candidate",
        exact_subject_sha="a" * 40,
        authority_digest="sha256:authority",
        consequence_key="repo:a:repair-17",
        verification_digest="sha256:verification-contract",
        provider="claude",
        run_id="run-claude-1",
    )


def test_provider_can_die_without_changing_semantics(
    claude_run: ExecutionSemantics,
) -> None:
    zcode = dataclasses.replace(claude_run, provider="zcode", run_id="run-zcode-1")
    result = compare_provider_substitution(claude_run, zcode)
    assert result.qualified and result.verdict == "QUALIFIED"
    assert result.changed_fields == () and result.reasons == ()
    assert result.before_semantic_digest == result.after_semantic_digest


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("workorder_digest", "sha256:different-work"),
        ("command_digest", "sha256:different-command"),
        ("candidate_digest", "sha256:different-candidate"),
        ("exact_subject_sha", "b" * 40),
        ("authority_digest", "sha256:different-authority"),
        ("consequence_key", "repo:a:replacement-consequence"),
        ("verification_digest", "sha256:different-verifier"),
    ],
)
def test_provider_substitution_refuses_semantic_drift(
    claude_run: ExecutionSemantics, field: str, replacement: str
) -> None:
    zcode = dataclasses.replace(
        claude_run, provider="zcode", run_id="run-zcode-1", **{field: replacement}
    )
    result = compare_provider_substitution(claude_run, zcode)
    assert not result.qualified
    assert result.changed_fields == (field,)
    assert f"SEMANTIC_DRIFT:{field}" in result.reasons
    assert result.before_semantic_digest != result.after_semantic_digest


def test_same_provider_is_not_provider_extinction(
    claude_run: ExecutionSemantics,
) -> None:
    result = compare_provider_substitution(
        claude_run, dataclasses.replace(claude_run, run_id="run-claude-2")
    )
    assert not result.qualified and result.reasons == ("PROVIDER_NOT_REPLACED",)


def test_run_identity_cannot_be_reused_across_provider_boundary(
    claude_run: ExecutionSemantics,
) -> None:
    result = compare_provider_substitution(
        claude_run, dataclasses.replace(claude_run, provider="zcode")
    )
    assert not result.qualified
    assert result.reasons == ("RUN_ID_REUSED_ACROSS_PROVIDER_REPLACEMENT",)



def test_fresh_job_recovery_uses_content_identity_not_workstation_path(
    claude_run: ExecutionSemantics,
) -> None:
    artifact = "sha256:" + "d" * 64
    before = dataclasses.replace(claude_run, candidate_digest=artifact)
    after = dataclasses.replace(
        before,
        provider="zcode",
        run_id="run-zcode-2",
    )
    handoff = ArtifactHandoff(
        artifact_digest=artifact,
        manifest_digest="sha256:" + "e" * 64,
        producer_digest="sha256:" + "f" * 64,
        source_provider="claude",
        source_run_id="run-claude-1",
        target_provider="zcode",
        target_run_id="run-zcode-2",
        source_locator="/tmp/job-a/out/candidate.bin",
        target_locator="/workspace/job-b/in/candidate.bin",
    )
    result = qualify_fresh_job_recovery(
        before,
        after,
        handoff=handoff,
        failure=FailureInjection(
            injection_id="fi:provider-extinction:1",
            kind="PROVIDER_EXTINCTION",
            failed_provider="claude",
            failed_run_id="run-claude-1",
        ),
    )
    assert result.qualified
    assert result.verdict == "QUALIFIED"
    assert result.reasons == ()

    relocated = dataclasses.replace(
        handoff,
        source_locator="C:/ephemeral/job-a/candidate.bin",
        target_locator="/another/fresh/job/candidate.bin",
    )
    relocated_result = qualify_fresh_job_recovery(
        before,
        after,
        handoff=relocated,
        failure=FailureInjection(
            injection_id="fi:provider-extinction:1",
            kind="PROVIDER_EXTINCTION",
            failed_provider="claude",
            failed_run_id="run-claude-1",
        ),
    )
    assert relocated_result.handoff_content_digest == result.handoff_content_digest


def test_fresh_job_recovery_refuses_artifact_or_failure_identity_drift(
    claude_run: ExecutionSemantics,
) -> None:
    artifact = "sha256:" + "1" * 64
    before = dataclasses.replace(claude_run, candidate_digest=artifact)
    after = dataclasses.replace(
        before,
        provider="zcode",
        run_id="run-zcode-3",
        candidate_digest="sha256:" + "2" * 64,
    )
    handoff = ArtifactHandoff(
        artifact_digest=artifact,
        manifest_digest="sha256:" + "3" * 64,
        producer_digest="sha256:" + "4" * 64,
        source_provider="claude",
        source_run_id="run-claude-1",
        target_provider="zcode",
        target_run_id="run-zcode-3",
    )
    result = qualify_fresh_job_recovery(
        before,
        after,
        handoff=handoff,
        failure=FailureInjection(
            injection_id="fi:crash:wrong-run",
            kind="CRASH",
            failed_provider="claude",
            failed_run_id="run-other",
        ),
    )
    assert not result.qualified
    assert "SEMANTIC_DRIFT:candidate_digest" in result.reasons
    assert "TARGET_ARTIFACT_IDENTITY_MISMATCH" in result.reasons
    assert "FAILURE_RUN_MISMATCH" in result.reasons


def test_failure_injection_kind_is_typed() -> None:
    with pytest.raises(ValueError, match="unsupported failure injection kind"):
        FailureInjection(
            injection_id="fi:bad",
            kind="NETWORK_MAYBE",
            failed_provider="claude",
            failed_run_id="run-claude-1",
        )
