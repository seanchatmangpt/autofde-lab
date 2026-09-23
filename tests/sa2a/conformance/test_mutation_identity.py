# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Mutation tests for Gate 1 Identity & Root Manifest Court (RFC-SA2A-002 v26.9.16).

Per `.claude/rules/level4-completion-law.md`'s "Mutation law": for every required
identity/relation this court enforces, construct an otherwise-complete, currently-valid
admission episode, mutate EXACTLY ONE identity or field in it, and require the court's
real `verify_*` method to reject it with a typed non-ALIVE/refusal result -- never a
silent pass, never a broad `except` swallowing everything.

Each test below therefore does two real calls against the same `IdentityCourt`
instance: first a baseline call proving the unmutated episode is currently CONFORMANT
(so the mutation is known to start from a genuinely valid state, not an already-broken
one), then the mutated call, asserting a typed refusal exception is raised.

Chicago Zero-Mock Standard:
- Real git repositories (two genuine commits, not synthetic SHA strings) for the git
  identity swap.
- Real pydantic model construction/state for the envelope digest mutation. `SemanticGraph`
  is `frozen=True` and enforces `digest == sha256(content)` inside its own
  `model_validator`, so a mismatched (digest, content) pair cannot be produced through its
  normal validated constructor -- that is precisely the frozen-model's job. To manufacture
  the one realistic production vector that CAN produce this state (a bypassed/adversarial
  deserialization such as `model_construct`, or direct corruption of an
  already-constructed object's memory) without faking any collaborator, this file uses
  `object.__setattr__` directly on the real `SemanticGraph` instance -- genuine mutation
  of real object state, not a mock, stub, or patched method. No `unittest.mock`,
  `Mock`, `MagicMock`, `patch`, or `monkeypatch` appears anywhere in this file.
- A real `AuthorityBroker` with a real registered grant for the actor-id swap.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from autofde_lab.sa2a.algebra import Standing
from autofde_lab.sa2a.authority.broker import AuthorityBroker, AuthorityGrant
from autofde_lab.sa2a.conformance.courts.identity_court import (
    CHI_ID_GIT_SHA,
    SA2A_ENV_DIGEST_MISMATCH,
    SA2A_ENV_STANDING_ESCALATION,
    EnvelopeDigestMismatchError,
    GitShaMismatchError,
    IdentityCourt,
    IdentityVerdict,
    StandingEscalationRefusalError,
)
from autofde_lab.sa2a.envelope import (
    ProvenanceRecord,
    SemanticEnvelope,
    SemanticGraph,
)


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a real git subprocess and return stripped stdout."""
    res = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def _init_real_git_repo_with_two_commits(repo_dir: Path) -> tuple[str, str]:
    """Initialize a genuine on-disk git repository with two real, distinct commits.

    Returns (first_commit_sha, second_commit_sha), both real HEAD SHAs resolved by the
    genuine git binary -- not synthetic strings.
    """
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-b", "main"], repo_dir)
    _run_git(["config", "user.name", "Mutation Test Agent"], repo_dir)
    _run_git(["config", "user.email", "mutation-test@autofde.org"], repo_dir)

    readme = repo_dir / "README.md"
    readme.write_text("# first admitted commit\n", encoding="utf-8")
    _run_git(["add", "README.md"], repo_dir)
    _run_git(["commit", "-m", "first commit"], repo_dir)
    first_sha = _run_git(["rev-parse", "HEAD"], repo_dir).lower()

    readme.write_text("# second admitted commit\n", encoding="utf-8")
    _run_git(["add", "README.md"], repo_dir)
    _run_git(["commit", "-m", "second commit"], repo_dir)
    second_sha = _run_git(["rev-parse", "HEAD"], repo_dir).lower()

    return first_sha, second_sha


# =============================================================================
# 1. CHI-ID-GIT-SHA -- identity swap between two REAL, well-formed commits
# =============================================================================


def test_git_sha_swap_between_two_real_commits_is_rejected(tmp_path: Path) -> None:
    """Mutation: swap the declared commit identity for a DIFFERENT, real, well-formed
    commit SHA resolved from the same live repository -- not a synthetic/garbage
    string. This is the exact 'swap one referenced object identity for a
    wrong-but-well-formed one' case from level4-completion-law.md's Mutation law:
    both SHAs are genuine 40-hex-char git commit identifiers, and only the identity
    bound to `expected_sha` is mutated -- shape, format, and repository state are
    otherwise untouched.

    A verifier that only checks 'looks like a SHA' (format-only validation) would pass
    this mutation; `verify_git_sha` must reject it because it resolves the actual
    live-repository HEAD and compares real identities, not shapes.
    """
    repo_dir = tmp_path / "identity_swap_repo"
    first_sha, second_sha = _init_real_git_repo_with_two_commits(repo_dir)
    assert first_sha != second_sha  # sanity: genuinely two distinct real identities

    court = IdentityCourt()

    # Baseline: currently-valid episode. Repo HEAD is second_sha; declaring second_sha
    # as expected must be CONFORMANT before we mutate anything.
    baseline = court.verify_git_sha(
        expected_sha=second_sha,
        repo_path=repo_dir,
        fail_closed=True,
    )
    assert baseline.passed is True
    assert baseline.verdict == IdentityVerdict.CONFORMANT
    assert baseline.details["sha"] == second_sha

    # Mutation: swap the declared identity for the OTHER real, well-formed commit SHA
    # from the same repository. Repository state (still at second_sha) is untouched --
    # only the expected-identity binding is mutated.
    with pytest.raises(GitShaMismatchError) as exc_info:
        court.verify_git_sha(
            expected_sha=first_sha,
            repo_path=repo_dir,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == CHI_ID_GIT_SHA
    assert first_sha in str(exc_info.value)
    assert second_sha in str(exc_info.value)

    # Non-fail-closed path must also refuse (typed NON_CONFORMANT verdict), never a
    # silent pass.
    res = court.verify_git_sha(
        expected_sha=first_sha,
        repo_path=repo_dir,
        fail_closed=False,
    )
    assert res.passed is False
    assert res.verdict == IdentityVerdict.NON_CONFORMANT
    assert res.rule_id == CHI_ID_GIT_SHA
    assert res.details["expected_sha"] == first_sha
    assert res.details["actual_sha"] == second_sha


# =============================================================================
# 2. SA2A-ENV-DIGEST-MISMATCH -- corrupt exactly one field (graph content) on an
#    otherwise-complete, currently-valid SemanticEnvelope
# =============================================================================


def test_envelope_graph_digest_corruption_after_valid_construction_is_rejected() -> (
    None
):
    """Mutation: construct a fully valid `SemanticEnvelope` (graph digest genuinely
    matches its content -- pydantic's own `model_validator` proves this at
    construction time), then corrupt EXACTLY the `graph.content` field in place,
    leaving `graph.digest` unchanged. Require `verify_envelope_digest` to detect the
    resulting mismatch and raise `EnvelopeDigestMismatchError` (SA2A-ENV-DIGEST-MISMATCH).

    `SemanticGraph` is `frozen=True` with a `model_validator` enforcing
    `digest == sha256(content)`, so this exact corrupted (content, digest) pair cannot
    be produced through the model's normal validated constructor -- attempting to
    reassign `graph.content` normally raises pydantic's own `ValidationError` for a
    frozen instance (proven below). The one realistic production vector that DOES
    reach this state is a bypassed/adversarial deserialization path (e.g.
    `SemanticGraph.model_construct(...)`, or direct memory corruption of an
    already-validated object) that produces a syntactically well-typed
    `SemanticEnvelope` without re-running the graph's own digest check. `object.__setattr__`
    reproduces that exact real-world condition on the real object -- it is direct
    manipulation of genuine object state, not a mock or stub of any collaborator.
    """
    content = "urn:subject:system urn:predicate:declares urn:object:intent-v1 ."
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    graph = SemanticGraph(mediaType="text/turtle", digest=digest, content=content)

    envelope = SemanticEnvelope(
        kind="INTENT",
        envelopeId="env-mutation-digest-001",
        subjects=["urn:subject:system"],
        standing=Standing.CANDIDATE,
        provenance=ProvenanceRecord(
            issuer="urn:agent:mutation-test",
            timestamp="2026-09-16T00:00:00Z",
        ),
        graph=graph,
    )

    court = IdentityCourt()

    # Baseline: currently-valid episode -- genuine digest/content pair, must be CONFORMANT.
    baseline = court.verify_envelope_digest(envelope=envelope, fail_closed=True)
    assert baseline.passed is True
    assert baseline.verdict == IdentityVerdict.CONFORMANT
    assert baseline.rule_id == SA2A_ENV_DIGEST_MISMATCH

    # Prove the model itself refuses the normal, validated route to this mutation:
    # reassigning `content` on a frozen SemanticGraph raises pydantic's own error.
    with pytest.raises(Exception) as frozen_exc_info:
        envelope.graph.content = "TAMPERED via normal (blocked) assignment"
    assert "frozen" in str(frozen_exc_info.value).lower()

    # Mutation: corrupt EXACTLY the content field on the real, already-constructed
    # object, bypassing the frozen guard -- the digest field is left untouched.
    object.__setattr__(
        envelope.graph, "content", "TAMPERED graph payload -- injected consequence"
    )
    assert envelope.graph.digest == digest  # only ONE field was mutated

    with pytest.raises(EnvelopeDigestMismatchError) as exc_info:
        court.verify_envelope_digest(envelope=envelope, fail_closed=True)
    assert exc_info.value.rule_id == SA2A_ENV_DIGEST_MISMATCH
    assert digest in str(exc_info.value)


# =============================================================================
# 3. SA2A-ENV-STANDING-ESCALATION -- actor-id binding swap against a genuine grant
# =============================================================================


def test_envelope_actor_id_swap_against_genuine_grant_is_rejected() -> None:
    """Mutation: register a REAL `AuthorityGrant` for actor A in a real
    `AuthorityBroker`, construct an envelope that is genuinely AUTHORIZED under actor
    A (verified CONFORMANT as the baseline), then mutate EXACTLY the
    `provenance.issuer` actor-id binding to a different, well-formed actor B that
    holds no grant -- everything else (standing, authorityRequirement, prior_standing)
    stays identical. Require `verify_envelope_standing_escalation` to reject the swap.

    This is the 'actor-id binding' mutation named directly in
    level4-completion-law.md's Mutation law, exercised against a REAL AuthorityBroker
    holding a REAL registered grant (not an empty broker) so the baseline is a
    genuinely admitted, currently-valid episode before the identity is swapped.
    """
    actor_a = "urn:agent:authorized-controller-a"
    actor_b = "urn:agent:authorized-controller-b"  # different, well-formed, ungranted

    broker = AuthorityBroker()
    broker.register_grant(
        AuthorityGrant(
            grant_id="grant-mutation-actor-swap-001",
            subject_id=actor_a,
            action_iri="urn:action:quarantine",
            target_resource_iri="urn:cap:nodes",
        )
    )

    court = IdentityCourt()

    envelope_valid = {
        "standing": Standing.AUTHORIZED.value,
        "provenance": {"issuer": actor_a},
        "authorityRequirement": {
            "requiredCapability": "urn:cap:nodes",
            "authorizedBy": "urn:broker:authority:primary",
        },
    }

    # Baseline: currently-valid episode -- actor_a genuinely holds a grant.
    baseline = court.verify_envelope_standing_escalation(
        envelope=envelope_valid,
        prior_standing=Standing.CONSTRUCTED,
        authority_broker=broker,
        fail_closed=True,
    )
    assert baseline.passed is True
    assert baseline.verdict == IdentityVerdict.CONFORMANT
    assert baseline.rule_id == SA2A_ENV_STANDING_ESCALATION

    # Mutation: swap EXACTLY the provenance.issuer actor-id binding to actor_b.
    # standing, authorityRequirement, and prior_standing are untouched.
    envelope_mutated = dict(envelope_valid)
    envelope_mutated["provenance"] = {"issuer": actor_b}
    assert envelope_mutated["standing"] == envelope_valid["standing"]
    assert (
        envelope_mutated["authorityRequirement"]
        == envelope_valid["authorityRequirement"]
    )

    with pytest.raises(StandingEscalationRefusalError) as exc_info:
        court.verify_envelope_standing_escalation(
            envelope=envelope_mutated,
            prior_standing=Standing.CONSTRUCTED,
            authority_broker=broker,
            fail_closed=True,
        )
    assert exc_info.value.rule_id == SA2A_ENV_STANDING_ESCALATION
    assert actor_b in str(exc_info.value)
    assert "without valid grant in AuthorityBroker" in str(exc_info.value)

    # Non-fail-closed path must also refuse with a typed REFUSED verdict.
    res = court.verify_envelope_standing_escalation(
        envelope=envelope_mutated,
        prior_standing=Standing.CONSTRUCTED,
        authority_broker=broker,
        fail_closed=False,
    )
    assert res.passed is False
    assert res.verdict == IdentityVerdict.REFUSED
    assert res.rule_id == SA2A_ENV_STANDING_ESCALATION
    assert res.details["actor_id"] == actor_b
