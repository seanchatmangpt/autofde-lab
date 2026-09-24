"""Candidate cross-artifact and cross-repository correspondences."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from .model import ArtifactRecord, EvidenceKind, SemanticClaim, digest

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_./:-]*")


def semantic_tokens(text: str) -> frozenset[str]:
    return frozenset(token.lower() for token in _TOKEN.findall(text) if len(token) > 2)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


@dataclass(frozen=True, slots=True)
class CorrespondenceCandidate:
    left_id: str
    right_id: str
    relation: str
    score: float
    evidence_ids: tuple[str, ...]
    exclusions: tuple[str, ...]
    required_verifier: str

    @property
    def candidate_id(self) -> str:
        return digest(self)


class CorrespondenceEngine:
    """Generate candidates while refusing to equate similarity with identity."""

    def __init__(self, *, threshold: float = 0.55) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be within [0, 1]")
        self.threshold = threshold

    def lexical_candidates(
        self, documents: Sequence[tuple[str, str, tuple[str, ...]]]
    ) -> tuple[CorrespondenceCandidate, ...]:
        prepared = [
            (identity, semantic_tokens(text), evidence_ids)
            for identity, text, evidence_ids in documents
        ]
        results: list[CorrespondenceCandidate] = []
        for i, (left_id, left_tokens, left_evidence) in enumerate(prepared):
            for right_id, right_tokens, right_evidence in prepared[i + 1 :]:
                score = jaccard(left_tokens, right_tokens)
                if score < self.threshold:
                    continue
                results.append(
                    CorrespondenceCandidate(
                        left_id=left_id,
                        right_id=right_id,
                        relation="semanticSimilarityCandidate",
                        score=round(score, 6),
                        evidence_ids=tuple(sorted(set(left_evidence + right_evidence))),
                        exclusions=("similarity_is_not_equivalence",),
                        required_verifier="iec.translation-validation",
                    )
                )
        return tuple(
            sorted(results, key=lambda item: (-item.score, item.left_id, item.right_id))
        )

    def artifact_candidates(
        self, artifacts: Iterable[ArtifactRecord]
    ) -> tuple[SemanticClaim, ...]:
        buckets: dict[str, list[ArtifactRecord]] = {}
        for artifact in artifacts:
            buckets.setdefault(artifact.content_digest, []).append(artifact)

        claims: list[SemanticClaim] = []
        for content_digest, members in sorted(buckets.items()):
            if len(members) < 2:
                continue
            ordered = sorted(members, key=lambda item: (item.subject_id, item.path))
            anchor = ordered[0]
            for other in ordered[1:]:
                claims.append(
                    SemanticClaim(
                        subject=f"{anchor.subject_id}:{anchor.path}",
                        predicate="iec:byteExactCandidate",
                        object=f"{other.subject_id}:{other.path}",
                        evidence_kind=EvidenceKind.DERIVED_DETERMINISTIC,
                        evidence_ids=(
                            tuple(sorted(set(anchor.evidence_ids + other.evidence_ids)))
                            or (content_digest,)
                        ),
                        exclusions=(
                            "byte_identity_does_not_prove_same_role",
                            "path_and_consumer_semantics_unchecked",
                        ),
                        falsifier="change one member while preserving the other",
                    )
                )
        return tuple(claims)

    @staticmethod
    def cluster(
        candidates: Iterable[CorrespondenceCandidate],
        *,
        minimum_score: float | None = None,
    ) -> tuple[frozenset[str], ...]:
        adjacency: dict[str, set[str]] = {}
        for candidate in candidates:
            if minimum_score is not None and candidate.score < minimum_score:
                continue
            adjacency.setdefault(candidate.left_id, set()).add(candidate.right_id)
            adjacency.setdefault(candidate.right_id, set()).add(candidate.left_id)

        seen: set[str] = set()
        components: list[frozenset[str]] = []
        for node in sorted(adjacency):
            if node in seen:
                continue
            stack = [node]
            component: set[str] = set()
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                component.add(current)
                stack.extend(sorted(adjacency.get(current, ()), reverse=True))
            components.append(frozenset(component))

        return tuple(
            sorted(components, key=lambda group: (-len(group), tuple(sorted(group))))
        )
