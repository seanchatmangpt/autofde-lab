"""SubjectResolver: candidate manifest -> ExactSubject, fail-closed (ARD §6).

Structural/format validation only (see package docstring for the scope boundary).
Refuses, with a named typed reason, on: a floating branch reference (not an exact
40-hex SHA), a missing artifact digest, a missing root-manifest digest, an ambiguous
repository identity (same logical name, no SHA at all), or a duplicate logical
dependency asserted with two conflicting SHAs.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from autofde_lab.sa2a.composition.exact_subject import ArtifactRef, ExactSubject, RepositoryRef

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

REFUSED_FLOATING_REPOSITORY_REF = "REFUSED_FLOATING_REPOSITORY_REF"
REFUSED_MISSING_ARTIFACT_DIGEST = "REFUSED_MISSING_ARTIFACT_DIGEST"
REFUSED_MISSING_ROOT_MANIFEST_DIGEST = "REFUSED_MISSING_ROOT_MANIFEST_DIGEST"
REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY = "REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY"
REFUSED_CONFLICTING_REPOSITORY_SHA = "REFUSED_CONFLICTING_REPOSITORY_SHA"


class SubjectResolutionError(ValueError):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


def _is_exact_sha(value: str) -> bool:
    if value.startswith("dirty:"):
        return _SHA_RE.match(value[len("dirty:") :]) is not None
    return _SHA_RE.match(value) is not None


@dataclass(frozen=True, slots=True)
class SelfIdentity:
    """This repo's own current exact git identity (real, local, read-only)."""

    sha: str
    dirty: bool

    @property
    def exact_sha(self) -> str:
        return f"dirty:{self.sha}" if self.dirty else self.sha


def resolve_self_identity(repo_root: Path | None = None) -> SelfIdentity:
    """Resolve THIS repository's own exact identity via real, local `git` calls.

    Never contacts a remote -- `git rev-parse HEAD` and `git status --porcelain`
    both read only the local `.git` directory and working tree.
    """
    cwd = repo_root or Path.cwd()
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout
    return SelfIdentity(sha=sha, dirty=bool(status.strip()))


class SubjectResolver:
    """Resolves a candidate composition manifest into an ExactSubject, fail-closed."""

    def resolve(self, candidate_manifest: Mapping[str, Any]) -> ExactSubject:
        release_id = str(candidate_manifest.get("release_id", "")).strip()
        if not release_id:
            raise SubjectResolutionError(
                REFUSED_FLOATING_REPOSITORY_REF, "release_id is empty"
            )

        repositories = self._resolve_repositories(candidate_manifest.get("repositories", ()))
        artifacts = self._resolve_artifacts(candidate_manifest.get("artifacts", ()))

        root_manifest_digest = str(candidate_manifest.get("root_manifest_digest", "")).strip()
        if not root_manifest_digest:
            raise SubjectResolutionError(
                REFUSED_MISSING_ROOT_MANIFEST_DIGEST, "root_manifest_digest is empty"
            )

        return ExactSubject(
            release_id=release_id,
            repositories=repositories,
            artifacts=artifacts,
            root_manifest_digest=root_manifest_digest,
            semantic_profile=str(candidate_manifest.get("semantic_profile", "")),
            court_revision=str(candidate_manifest.get("court_revision", "")),
            falsifier_corpus_digest=str(candidate_manifest.get("falsifier_corpus_digest", "")),
            query_set_digest=str(candidate_manifest.get("query_set_digest", "")),
            environment_identity=str(candidate_manifest.get("environment_identity", "")),
        )

    @staticmethod
    def _resolve_repositories(raw: Sequence[Mapping[str, Any]]) -> tuple[RepositoryRef, ...]:
        by_name: dict[str, RepositoryRef] = {}
        refs: list[RepositoryRef] = []
        for entry in raw:
            name = str(entry.get("name", "")).strip()
            exact_sha = str(entry.get("exact_sha", "")).strip()
            remote_url = str(entry.get("remote_url", ""))
            if not name or not exact_sha or not _is_exact_sha(exact_sha):
                raise SubjectResolutionError(
                    REFUSED_FLOATING_REPOSITORY_REF,
                    f"repository {name or '<unnamed>'!r} has no exact 40-hex SHA "
                    f"(got {exact_sha!r}) -- a branch name alone is not sufficient",
                )
            if name in by_name:
                prior = by_name[name]
                if prior.exact_sha != exact_sha:
                    raise SubjectResolutionError(
                        REFUSED_CONFLICTING_REPOSITORY_SHA,
                        f"repository {name!r} asserted with two conflicting SHAs: "
                        f"{prior.exact_sha!r} and {exact_sha!r}",
                    )
                if prior.remote_url and remote_url and prior.remote_url != remote_url:
                    # Same name, same SHA, but two different claimed origins --
                    # this is not a SHA conflict, it's a genuinely ambiguous
                    # identity: which remote does this pinned commit actually
                    # belong to?
                    raise SubjectResolutionError(
                        REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY,
                        f"repository {name!r} pinned at {exact_sha!r} claims two "
                        f"different remotes: {prior.remote_url!r} and {remote_url!r}",
                    )
                continue  # identical duplicate, not an error
            ref = RepositoryRef(name=name, exact_sha=exact_sha, remote_url=remote_url)
            by_name[name] = ref
            refs.append(ref)
        return tuple(refs)

    @staticmethod
    def _resolve_artifacts(raw: Sequence[Mapping[str, Any]]) -> tuple[ArtifactRef, ...]:
        refs: list[ArtifactRef] = []
        for entry in raw:
            artifact_id = str(entry.get("artifact_id", "")).strip()
            digest = str(entry.get("digest", "")).strip()
            if not artifact_id or not digest:
                raise SubjectResolutionError(
                    REFUSED_MISSING_ARTIFACT_DIGEST,
                    f"artifact {artifact_id or '<unnamed>'!r} is missing a digest",
                )
            refs.append(ArtifactRef(artifact_id=artifact_id, digest=digest))
        return tuple(refs)
