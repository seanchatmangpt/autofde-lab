"""Chicago-style tests for SubjectResolver / ExactSubject (v26.9.17 PRD §6.1-6.2,
ARD §5.1, §6-7). Real objects throughout, zero mocks."""

from __future__ import annotations

from pathlib import Path

from autofde_lab.sa2a.composition.exact_subject import ArtifactRef, ExactSubject, RepositoryRef
from autofde_lab.sa2a.composition.resolver import (
    REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY,
    REFUSED_CONFLICTING_REPOSITORY_SHA,
    REFUSED_FLOATING_REPOSITORY_REF,
    REFUSED_MISSING_ARTIFACT_DIGEST,
    REFUSED_MISSING_ROOT_MANIFEST_DIGEST,
    SubjectResolutionError,
    SubjectResolver,
    resolve_self_identity,
)

_VALID_MANIFEST = {
    "release_id": "v26.9.17-test",
    "repositories": [{"name": "autofde-lab", "exact_sha": "a" * 40, "remote_url": "https://example.invalid/a"}],
    "artifacts": [{"artifact_id": "artifact-1", "digest": "b" * 64}],
    "root_manifest_digest": "c" * 64,
    "semantic_profile": "SA2A-STRICT",
    "court_revision": "v26.9.17",
    "falsifier_corpus_digest": "d" * 64,
    "query_set_digest": "e" * 64,
    "environment_identity": "test-env",
}


def test_resolve_self_identity_reads_real_local_git_state() -> None:
    """Real, local `git rev-parse HEAD` / `git status --porcelain` -- no network."""
    identity = resolve_self_identity(Path(__file__).resolve().parents[3])
    assert len(identity.sha) == 40
    assert all(c in "0123456789abcdef" for c in identity.sha)
    assert isinstance(identity.dirty, bool)


def test_resolve_produces_deterministic_composition_digest() -> None:
    subject = SubjectResolver().resolve(_VALID_MANIFEST)
    assert isinstance(subject, ExactSubject)
    assert len(subject.repositories) == 1
    assert subject.repositories[0] == RepositoryRef(
        name="autofde-lab", exact_sha="a" * 40, remote_url="https://example.invalid/a"
    )
    assert subject.artifacts[0] == ArtifactRef(artifact_id="artifact-1", digest="b" * 64)

    again = SubjectResolver().resolve(_VALID_MANIFEST)
    assert subject.composition_digest == again.composition_digest

    changed = SubjectResolver().resolve({**_VALID_MANIFEST, "release_id": "different"})
    assert changed.composition_digest != subject.composition_digest


def test_refuses_floating_branch_reference() -> None:
    manifest = {**_VALID_MANIFEST, "repositories": [{"name": "x", "exact_sha": "main"}]}
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse a branch name in place of an exact SHA"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_FLOATING_REPOSITORY_REF


def test_refuses_conflicting_sha_for_same_logical_repository() -> None:
    manifest = {
        **_VALID_MANIFEST,
        "repositories": [
            {"name": "x", "exact_sha": "a" * 40},
            {"name": "x", "exact_sha": "b" * 40},
        ],
    }
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse two conflicting SHAs for one logical dependency"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_CONFLICTING_REPOSITORY_SHA


def test_refuses_ambiguous_remote_for_identically_pinned_repository() -> None:
    manifest = {
        **_VALID_MANIFEST,
        "repositories": [
            {"name": "x", "exact_sha": "a" * 40, "remote_url": "https://one.invalid/x"},
            {"name": "x", "exact_sha": "a" * 40, "remote_url": "https://two.invalid/x"},
        ],
    }
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse the same pinned commit claiming two different remotes"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY


def test_identical_duplicate_repository_entry_is_not_an_error() -> None:
    manifest = {
        **_VALID_MANIFEST,
        "repositories": [
            {"name": "x", "exact_sha": "a" * 40, "remote_url": "https://one.invalid/x"},
            {"name": "x", "exact_sha": "a" * 40, "remote_url": "https://one.invalid/x"},
        ],
    }
    subject = SubjectResolver().resolve(manifest)
    assert len(subject.repositories) == 1


def test_refuses_missing_artifact_digest() -> None:
    manifest = {**_VALID_MANIFEST, "artifacts": [{"artifact_id": "no-digest"}]}
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse an artifact reference with no digest"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_MISSING_ARTIFACT_DIGEST


def test_refuses_missing_root_manifest_digest() -> None:
    manifest = {**_VALID_MANIFEST, "root_manifest_digest": ""}
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse a subject with no root_manifest_digest"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_MISSING_ROOT_MANIFEST_DIGEST


def test_dirty_prefixed_sha_is_exact_but_distinguishable_from_clean() -> None:
    """A dirty worktree is an exact, non-floating identity (not REFUSED here) --
    ARD §61's dirty-worktree gate is a separate, later PREFLIGHT check
    (`ReleaseRun`), not this resolver's concern."""
    manifest = {**_VALID_MANIFEST, "repositories": [{"name": "x", "exact_sha": f"dirty:{'a' * 40}"}]}
    subject = SubjectResolver().resolve(manifest)
    assert subject.repositories[0].exact_sha == f"dirty:{'a' * 40}"
