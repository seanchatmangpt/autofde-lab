"""SubjectResolver: candidate manifest -> ExactSubject, fail-closed (ARD §6).

Structural/format validation only (see package docstring for the scope boundary).
Refuses, with a named typed reason, on: a floating branch reference (not an exact
40-hex SHA), a missing artifact digest, a missing root-manifest digest, an ambiguous
repository identity (same logical name, no SHA at all), a duplicate logical
repository dependency asserted with two conflicting SHAs, or a duplicate logical
artifact asserted with two conflicting content digests.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from autofde_lab.sa2a.composition.exact_subject import (
    ArtifactRef,
    CheckpointRef,
    ExactSubject,
    RepositoryRef,
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

REFUSED_FLOATING_REPOSITORY_REF = "REFUSED_FLOATING_REPOSITORY_REF"
REFUSED_MISSING_ARTIFACT_DIGEST = "REFUSED_MISSING_ARTIFACT_DIGEST"
REFUSED_MISSING_ROOT_MANIFEST_DIGEST = "REFUSED_MISSING_ROOT_MANIFEST_DIGEST"
REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY = "REFUSED_AMBIGUOUS_REPOSITORY_IDENTITY"
REFUSED_CONFLICTING_REPOSITORY_SHA = "REFUSED_CONFLICTING_REPOSITORY_SHA"
#: Hardening pass (2026-09-17, QUALIFICATION): `_resolve_artifacts` accepted two
#: entries sharing one `artifact_id` but carrying two different `digest` values --
#: both were silently admitted into `ExactSubject.artifacts`, exactly the
#: "duplicate logical identity, conflicting content" shape `_resolve_repositories`
#: already refuses via `REFUSED_CONFLICTING_REPOSITORY_SHA`. An `ExactSubject` with
#: two digests claimed for the same `artifact_id` cannot answer "which digest is
#: this artifact's identity" -- the composition is not exact. Mirrors the
#: repository check: identical duplicates (same id, same digest) are not an error.
REFUSED_CONFLICTING_ARTIFACT_DIGEST = "REFUSED_CONFLICTING_ARTIFACT_DIGEST"
#: Hardening pass (2026-09-17): a malformed manifest shape (e.g. `repositories` is a
#: string instead of a list, or a list entry isn't a mapping) used to raise a raw
#: `AttributeError`/`TypeError` instead of the typed refusal this fail-closed
#: resolver promises everywhere else -- a caller catching only
#: `SubjectResolutionError` (as every falsifier test in this repo does) would see an
#: uncaught crash instead of a clean REFUSED verdict. Every such shape violation now
#: surfaces as this one code.
REFUSED_MALFORMED_MANIFEST = "REFUSED_MALFORMED_MANIFEST"
REFUSED_MISSING_GALL_CHECKPOINT = "REFUSED_MISSING_GALL_CHECKPOINT"
REFUSED_INVALID_GALL_CHECKPOINT = "REFUSED_INVALID_GALL_CHECKPOINT"
REFUSED_CHECKPOINT_RECEIPT_DRIFT = "REFUSED_CHECKPOINT_RECEIPT_DRIFT"

_REQUIRED_GALL_CHECKPOINTS = ("GALL-001", "GALL-002", "GALL-003", "GALL-004")
_DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")


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
        """Resolve `candidate_manifest` into an `ExactSubject`, fail-closed.

        Any shape violation (`candidate_manifest` itself not Mapping-like,
        `repositories`/`artifacts` not iterable, an entry not Mapping-like) is
        caught and re-raised as a typed `SubjectResolutionError(REFUSED_MALFORMED_
        MANIFEST, ...)` rather than an arbitrary `AttributeError`/`TypeError` --
        "fail closed" means every rejection is the one typed exception every caller
        in this repo already catches, never a surprise exception type.
        """
        try:
            return self._resolve_unguarded(candidate_manifest)
        except SubjectResolutionError:
            raise
        except (AttributeError, TypeError, KeyError, ValueError) as exc:
            raise SubjectResolutionError(
                REFUSED_MALFORMED_MANIFEST, f"candidate_manifest has an unexpected shape: {exc!r}"
            ) from exc

    def resolve_gall(
        self, candidate_manifest: Mapping[str, Any], *, base_dir: Path | None = None
    ) -> ExactSubject:
        """Resolve and independently verify the GALL-001..004 receipt set.

        The receipt digest is over the durable file bytes, not a producer
        boolean. A path is transport-only and does not enter ExactSubject;
        only the verified digest and bounded claim do.
        """
        subject = self.resolve(candidate_manifest)
        by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in subject.checkpoints}
        missing = [checkpoint for checkpoint in _REQUIRED_GALL_CHECKPOINTS if checkpoint not in by_id]
        if missing:
            raise SubjectResolutionError(
                REFUSED_MISSING_GALL_CHECKPOINT,
                f"composition is missing required checkpoint(s): {', '.join(missing)}",
            )

        raw_checkpoints = candidate_manifest.get(
            "checkpoints", candidate_manifest.get("gall_checkpoints", ())
        )
        root = base_dir or Path.cwd()
        for entry in raw_checkpoints:
            checkpoint_id = str(entry.get("checkpoint_id", "")).strip()
            if checkpoint_id not in _REQUIRED_GALL_CHECKPOINTS:
                continue
            receipt_path = str(entry.get("receipt_path", "")).strip()
            if not receipt_path:
                raise SubjectResolutionError(
                    REFUSED_INVALID_GALL_CHECKPOINT,
                    f"{checkpoint_id} has no receipt_path for independent verification",
                )
            path = Path(receipt_path)
            if not path.is_absolute():
                path = root / path
            try:
                bytes_ = path.read_bytes()
            except OSError as exc:
                raise SubjectResolutionError(
                    REFUSED_INVALID_GALL_CHECKPOINT,
                    f"{checkpoint_id} receipt is unreadable at {path}: {exc}",
                ) from exc
            observed = "sha256:" + hashlib.sha256(bytes_).hexdigest()
            expected = by_id[checkpoint_id].receipt_digest
            expected = expected if expected.startswith("sha256:") else "sha256:" + expected
            if observed != expected:
                raise SubjectResolutionError(
                    REFUSED_CHECKPOINT_RECEIPT_DRIFT,
                    f"{checkpoint_id} receipt digest mismatch: expected {expected}, observed {observed}",
                )
        return subject

    def _resolve_unguarded(self, candidate_manifest: Mapping[str, Any]) -> ExactSubject:
        release_id = str(candidate_manifest.get("release_id", "")).strip()
        if not release_id:
            raise SubjectResolutionError(
                REFUSED_FLOATING_REPOSITORY_REF, "release_id is empty"
            )

        repositories = self._resolve_repositories(candidate_manifest.get("repositories", ()))
        artifacts = self._resolve_artifacts(candidate_manifest.get("artifacts", ()))
        checkpoints = self._resolve_checkpoints(
            candidate_manifest.get("checkpoints", candidate_manifest.get("gall_checkpoints", ()))
        )

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
            checkpoints=checkpoints,
            work_order_digest=str(candidate_manifest.get("work_order_digest", "")),
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
        by_id: dict[str, ArtifactRef] = {}
        refs: list[ArtifactRef] = []
        for entry in raw:
            artifact_id = str(entry.get("artifact_id", "")).strip()
            digest = str(entry.get("digest", "")).strip()
            if not artifact_id or not digest:
                raise SubjectResolutionError(
                    REFUSED_MISSING_ARTIFACT_DIGEST,
                    f"artifact {artifact_id or '<unnamed>'!r} is missing a digest",
                )
            if artifact_id in by_id:
                prior = by_id[artifact_id]
                if prior.digest != digest:
                    raise SubjectResolutionError(
                        REFUSED_CONFLICTING_ARTIFACT_DIGEST,
                        f"artifact {artifact_id!r} asserted with two conflicting "
                        f"digests: {prior.digest!r} and {digest!r}",
                    )
                continue  # identical duplicate, not an error
            ref = ArtifactRef(artifact_id=artifact_id, digest=digest)
            by_id[artifact_id] = ref
            refs.append(ref)
        return tuple(refs)


    @staticmethod
    def _resolve_checkpoints(raw: Sequence[Mapping[str, Any]]) -> tuple[CheckpointRef, ...]:
        by_id: dict[str, CheckpointRef] = {}
        refs: list[CheckpointRef] = []
        for entry in raw:
            checkpoint_id = str(entry.get("checkpoint_id", "")).strip()
            repository = str(entry.get("repository", "")).strip()
            exact_sha = str(entry.get("exact_sha", "")).strip()
            receipt_digest = str(entry.get("receipt_digest", "")).strip()
            standing = str(entry.get("standing", "")).strip()
            evidence_class = str(entry.get("evidence_class", "")).strip()
            work_order_digest = str(entry.get("work_order_digest", "")).strip()

            if (
                not checkpoint_id
                or not repository
                or not _is_exact_sha(exact_sha)
                or not _DIGEST_RE.match(receipt_digest)
                or not standing
                or not evidence_class
                or (work_order_digest and not _DIGEST_RE.match(work_order_digest))
            ):
                raise SubjectResolutionError(
                    REFUSED_INVALID_GALL_CHECKPOINT,
                    f"invalid GALL checkpoint identity for {checkpoint_id or '<unnamed>'!r}",
                )

            ref = CheckpointRef(
                checkpoint_id=checkpoint_id,
                repository=repository,
                exact_sha=exact_sha,
                receipt_digest=receipt_digest,
                standing=standing,
                evidence_class=evidence_class,
                work_order_digest=work_order_digest,
            )
            prior = by_id.get(checkpoint_id)
            if prior is not None and prior != ref:
                raise SubjectResolutionError(
                    REFUSED_INVALID_GALL_CHECKPOINT,
                    f"{checkpoint_id} is asserted with conflicting identities",
                )
            if prior is None:
                by_id[checkpoint_id] = ref
                refs.append(ref)
        return tuple(refs)
