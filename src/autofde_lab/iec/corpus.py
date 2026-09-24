"""Exact corpus identity and privacy fencing for IEC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .model import (
    Failure,
    FailureKind,
    RepositorySubject,
    aggregate_digest,
    digest,
    ensure_unique,
)


@dataclass(frozen=True, slots=True)
class CorpusRevision:
    revision_id: str
    subjects: tuple[RepositorySubject, ...]
    excluded: tuple[tuple[str, str], ...] = ()

    @property
    def public_subjects(self) -> tuple[RepositorySubject, ...]:
        return tuple(s for s in self.subjects if s.visibility == "public")


class CorpusFreezer:
    """Manufacture deterministic corpus revisions from explicit observations."""

    def __init__(self, *, permit_private: bool = False) -> None:
        self.permit_private = permit_private

    def freeze(
        self,
        subjects: Iterable[RepositorySubject],
        *,
        excluded: Mapping[str, str] | None = None,
    ) -> CorpusRevision:
        admitted = tuple(
            sorted(subjects, key=lambda s: (s.repository, s.revision, s.default_branch))
        )
        if not admitted:
            raise ValueError("corpus must contain at least one exact subject")
        ensure_unique([s.repository for s in admitted], label="repository")

        if not self.permit_private:
            leaked = [s.repository for s in admitted if s.visibility != "public"]
            if leaked:
                raise PermissionError(
                    "REFUSED_PRIVATE_IDENTITY_LEAK:" + ",".join(sorted(leaked))
                )

        excluded_items = tuple(sorted((excluded or {}).items()))
        revision_id = digest(
            {
                "subjects": admitted,
                "excluded": excluded_items,
                "permit_private": self.permit_private,
            }
        )
        return CorpusRevision(revision_id, admitted, excluded_items)

    @staticmethod
    def compare(prior: CorpusRevision, current: CorpusRevision) -> tuple[Failure, ...]:
        prior_map = {s.repository: s for s in prior.subjects}
        current_map = {s.repository: s for s in current.subjects}
        failures: list[Failure] = []
        for repository in sorted(set(prior_map) | set(current_map)):
            left = prior_map.get(repository)
            right = current_map.get(repository)
            if left is None:
                failures.append(
                    Failure(
                        FailureKind.BLOCKED_CORPUS_IDENTITY,
                        f"repository added after freeze: {repository}",
                        right.subject_id if right else None,
                    )
                )
            elif right is None:
                failures.append(
                    Failure(
                        FailureKind.BLOCKED_CORPUS_IDENTITY,
                        f"repository removed after freeze: {repository}",
                        left.subject_id,
                    )
                )
            elif left != right:
                failures.append(
                    Failure(
                        FailureKind.BLOCKED_CORPUS_IDENTITY,
                        f"repository moved: {repository} {left.revision} -> {right.revision}",
                        right.subject_id,
                    )
                )
        return tuple(failures)

    @staticmethod
    def corpus_digest(subjects: Sequence[RepositorySubject]) -> str:
        return aggregate_digest(subjects)
