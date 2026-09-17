"""ExactSubject: the immutable identity of one release composition (ARD §5.1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    """One repository's pinned identity. `exact_sha` is a full 40-hex commit SHA,
    or `"dirty:<40-hex-sha>"` for a known-dirty local worktree (still an exact,
    non-floating identity -- a dirty worktree is not an *ambiguous* one, though
    `SubjectResolver`'s caller (the release crown) refuses to issue final standing
    against a dirty subject per ARD §61, a separate, later gate)."""

    name: str
    exact_sha: str
    remote_url: str = ""


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """One artifact's content digest."""

    artifact_id: str
    digest: str


@dataclass(frozen=True, slots=True)
class ExactSubject:
    """The exact, immutable composition a crown run qualifies (ARD §5.1)."""

    release_id: str
    repositories: tuple[RepositoryRef, ...]
    artifacts: tuple[ArtifactRef, ...]
    root_manifest_digest: str
    semantic_profile: str
    court_revision: str
    falsifier_corpus_digest: str
    query_set_digest: str
    environment_identity: str

    @property
    def composition_digest(self) -> str:
        """Deterministic digest over identity-bearing fields (ARD §7).

        Excludes nothing incidental here because every field on this frozen
        dataclass IS identity-bearing by construction; formatting/serialization
        choices (key order, whitespace) are neutralized by `sort_keys` + compact
        separators, matching `admission/canonicalizer.py`'s own digest discipline.
        """
        payload = {
            "release_id": self.release_id,
            "repositories": sorted(
                (r.name, r.exact_sha, r.remote_url) for r in self.repositories
            ),
            "artifacts": sorted((a.artifact_id, a.digest) for a in self.artifacts),
            "root_manifest_digest": self.root_manifest_digest,
            "semantic_profile": self.semantic_profile,
            "court_revision": self.court_revision,
            "falsifier_corpus_digest": self.falsifier_corpus_digest,
            "query_set_digest": self.query_set_digest,
            "environment_identity": self.environment_identity,
        }
        dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
