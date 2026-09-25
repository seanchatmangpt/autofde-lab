# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""ALOOP-004 provider-extinction semantic conservation court."""

from __future__ import annotations

import dataclasses
import pytest

from autofde_lab.aloop.provider_extinction import ExecutionSemantics, compare_provider_substitution

@pytest.fixture
def claude_run() -> ExecutionSemantics:
    return ExecutionSemantics(
        workorder_digest="sha256:workorder", command_digest="sha256:command",
        candidate_digest="sha256:candidate", exact_subject_sha="a" * 40,
        authority_digest="sha256:authority", consequence_key="repo:a:repair-17",
        verification_digest="sha256:verification-contract",
        provider="claude", run_id="run-claude-1",
    )

def test_provider_can_die_without_changing_semantics(claude_run: ExecutionSemantics) -> None:
    zcode = dataclasses.replace(claude_run, provider="zcode", run_id="run-zcode-1")
    result = compare_provider_substitution(claude_run, zcode)
    assert result.qualified and result.verdict == "QUALIFIED"
    assert result.changed_fields == () and result.reasons == ()
    assert result.before_semantic_digest == result.after_semantic_digest

@pytest.mark.parametrize(("field", "replacement"), [
    ("workorder_digest", "sha256:different-work"),
    ("command_digest", "sha256:different-command"),
    ("candidate_digest", "sha256:different-candidate"),
    ("exact_subject_sha", "b" * 40),
    ("authority_digest", "sha256:different-authority"),
    ("consequence_key", "repo:a:replacement-consequence"),
    ("verification_digest", "sha256:different-verifier"),
])
def test_provider_substitution_refuses_semantic_drift(claude_run: ExecutionSemantics, field: str, replacement: str) -> None:
    zcode = dataclasses.replace(claude_run, provider="zcode", run_id="run-zcode-1", **{field: replacement})
    result = compare_provider_substitution(claude_run, zcode)
    assert not result.qualified
    assert result.changed_fields == (field,)
    assert f"SEMANTIC_DRIFT:{field}" in result.reasons
    assert result.before_semantic_digest != result.after_semantic_digest

def test_same_provider_is_not_provider_extinction(claude_run: ExecutionSemantics) -> None:
    result = compare_provider_substitution(claude_run, dataclasses.replace(claude_run, run_id="run-claude-2"))
    assert not result.qualified and result.reasons == ("PROVIDER_NOT_REPLACED",)

def test_run_identity_cannot_be_reused_across_provider_boundary(claude_run: ExecutionSemantics) -> None:
    result = compare_provider_substitution(claude_run, dataclasses.replace(claude_run, provider="zcode"))
    assert not result.qualified
    assert result.reasons == ("RUN_ID_REUSED_ACROSS_PROVIDER_REPLACEMENT",)
