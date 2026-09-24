"""Exact-subject manifest for IEC experiment replay."""

from __future__ import annotations

from dataclasses import dataclass

from .model import ClaimCeiling, RepositorySubject, digest


@dataclass(frozen=True, slots=True)
class ToolIdentity:
    name: str
    version: str
    executable_digest: str | None = None
    source_revision: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("tool identity requires name and version")

    @property
    def tool_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class MoonshotManifest:
    version: str
    implementation_subject: RepositorySubject
    corpus_subjects: tuple[RepositorySubject, ...]
    tools: tuple[ToolIdentity, ...]
    verifier_set_ids: tuple[str, ...]
    claim_ceiling: ClaimCeiling
    cost_function_version: str = "iec-cost/v1"
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("manifest version must be non-empty")
        if not self.corpus_subjects:
            raise ValueError("manifest requires corpus subjects")
        repositories = [subject.repository for subject in self.corpus_subjects]
        if len(repositories) != len(set(repositories)):
            raise ValueError("manifest has duplicate repository subjects")
        if self.authority != "NONE":
            raise ValueError("IEC manifest carries no external authority")

    @property
    def manifest_id(self) -> str:
        return digest(self)
