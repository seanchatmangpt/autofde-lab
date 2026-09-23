"""IEC-001: exact corpus freeze (PR-001, ARD A1).

A corpus is a frozen list of exact repository subjects. Every later observation
binds to one of them by commit and tree id, and reads content from the git object
database at that commit -- never from the working tree -- so an uncommitted edit in
a checkout cannot leak into an observation that claims the commit's identity.

The privacy fence (ARD section 22) is enforced here: a public corpus refuses a
subject declared private, because its identity alone would leak into public
evidence. Visibility is a *declared* input; git cannot observe it, and this module
does not guess it.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .model import IECRefusal, content_id

__all__ = [
    "CorpusManifest",
    "RepositorySubject",
    "freeze_corpus",
    "git",
    "observe_checkout",
    "verify_checkout",
]

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_VISIBILITIES = ("public", "private")


def git(checkout: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    """Run one read-only git plumbing command in `checkout`; refuse on failure."""
    completed = subprocess.run(
        ["git", "-C", str(checkout), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY",
            f"git {' '.join(args)} in {checkout}: {completed.stderr.decode(errors='replace').strip()}",
        )
    return completed.stdout


def _normalize_remote(url: str) -> str:
    """`owner/name` from an https or ssh GitHub remote, lower-cased; '' if not GitHub."""
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    if not match:
        return ""
    return f"{match.group(1)}/{match.group(2)}".lower()


@dataclass(frozen=True)
class RepositorySubject:
    repository: str
    remote_url: str
    branch: str
    commit: str
    tree: str
    visibility: str
    inclusion_reason: str

    def __post_init__(self) -> None:
        if not _REPOSITORY.match(self.repository):
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY", f"repository {self.repository!r}"
            )
        if not (_SHA1.match(self.commit) and _SHA1.match(self.tree)):
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY",
                f"{self.repository}: commit/tree must be 40-hex",
            )
        if self.visibility not in _VISIBILITIES:
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY",
                f"{self.repository}: visibility must be declared as one of {_VISIBILITIES}",
            )
        if not self.inclusion_reason.strip():
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY", f"{self.repository}: no inclusion reason"
            )

    @property
    def uri(self) -> str:
        return f"git:{self.repository}@{self.commit}"

    def to_json(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "remote_url": self.remote_url,
            "branch": self.branch,
            "commit": self.commit,
            "tree": self.tree,
            "visibility": self.visibility,
            "inclusion_reason": self.inclusion_reason,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "RepositorySubject":
        return cls(**{key: str(data[key]) for key in cls.__dataclass_fields__})


def observe_checkout(
    checkout: Path,
    *,
    repository: str,
    branch: str,
    visibility: str,
    inclusion_reason: str,
    commit: str = "HEAD",
) -> RepositorySubject:
    """Bind a local checkout to an exact subject, refusing a mismatched remote.

    `repository` is what the caller claims; the checkout's `origin` remote must
    name the same GitHub repository, or the identity is ambiguous and refused.
    """
    checkout = Path(checkout)
    resolved_commit = (
        git(checkout, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    )
    tree = (
        git(checkout, "rev-parse", "--verify", f"{resolved_commit}^{{tree}}")
        .decode()
        .strip()
    )
    remote_url = git(checkout, "remote", "get-url", "origin").decode().strip()
    if _normalize_remote(remote_url) != repository.lower():
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY",
            f"checkout {checkout} has origin {remote_url!r}, not {repository!r}",
        )
    return RepositorySubject(
        repository=repository,
        remote_url=remote_url,
        branch=branch,
        commit=resolved_commit,
        tree=tree,
        visibility=visibility,
        inclusion_reason=inclusion_reason,
    )


def verify_checkout(subject: RepositorySubject, checkout: Path) -> None:
    """Refuse unless `checkout` contains `subject.commit` with `subject.tree`."""
    tree = (
        git(Path(checkout), "rev-parse", "--verify", f"{subject.commit}^{{tree}}")
        .decode()
        .strip()
    )
    if tree != subject.tree:
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY",
            f"{subject.uri}: tree {tree} in {checkout} != frozen tree {subject.tree}",
        )


@dataclass(frozen=True)
class CorpusManifest:
    revision: str
    fence: str
    subjects: tuple[RepositorySubject, ...]

    @property
    def id(self) -> str:
        return content_id(self.to_json(include_id=False))

    def subject(self, repository: str) -> RepositorySubject:
        for subject in self.subjects:
            if subject.repository == repository:
                return subject
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY", f"{repository} is not in corpus {self.revision}"
        )

    def to_json(self, *, include_id: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "schema": "autofde-lab.iec.corpus/1",
            "revision": self.revision,
            "fence": self.fence,
            "subjects": [subject.to_json() for subject in self.subjects],
        }
        if include_id:
            record["id"] = self.id
        return record

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "CorpusManifest":
        manifest = freeze_corpus(
            (RepositorySubject.from_json(item) for item in data["subjects"]),
            revision=str(data["revision"]),
            fence=str(data["fence"]),
        )
        if "id" in data and data["id"] != manifest.id:
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY",
                f"manifest id {data['id']} does not match its content ({manifest.id})",
            )
        return manifest


def freeze_corpus(
    subjects: Iterable[RepositorySubject], *, revision: str, fence: str = "public"
) -> CorpusManifest:
    """Freeze subjects into a manifest. Order-independent; duplicates refused."""
    if fence not in _VISIBILITIES:
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY", f"fence must be one of {_VISIBILITIES}"
        )
    if not revision.strip():
        raise IECRefusal("BLOCKED_CORPUS_IDENTITY", "corpus revision is required")
    ordered = tuple(sorted(subjects, key=lambda subject: subject.repository.lower()))
    seen: set[str] = set()
    for subject in ordered:
        key = subject.repository.lower()
        if key in seen:
            raise IECRefusal(
                "BLOCKED_CORPUS_IDENTITY", f"{subject.repository} listed twice"
            )
        seen.add(key)
        if fence == "public" and subject.visibility != "public":
            raise IECRefusal(
                "REFUSED_PRIVATE_IDENTITY_LEAK",
                f"{subject.repository} is declared {subject.visibility}; corpus fence is public",
            )
    if not ordered:
        raise IECRefusal(
            "BLOCKED_CORPUS_IDENTITY", "a corpus needs at least one subject"
        )
    return CorpusManifest(revision=revision, fence=fence, subjects=ordered)
