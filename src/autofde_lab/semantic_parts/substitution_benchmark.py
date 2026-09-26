"""Falsifier for semantic software-part discovery.

The benchmark consumes independent behavioral-equivalence judgements as its
oracle. CodeGraph/ontology overlap may rank candidates, but it cannot create the
oracle labels it is evaluated against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class SubstitutionCase:
    """One hidden-name substitution discovery court."""

    subject_id: str
    verified_equivalents: frozenset[str]
    lexical_candidates: tuple[str, ...]
    semantic_candidates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.subject_id:
            raise ValueError("subject_id must be non-empty")
        if not self.verified_equivalents:
            raise ValueError("verified_equivalents must be non-empty")
        if self.subject_id in self.verified_equivalents:
            raise ValueError("subject_id cannot verify itself as a substitution")


def _top_k_unique(\n    candidates: Sequence[str], k: int, subject_id: str\n) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        if not candidate or candidate == subject_id or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
        if len(result) == k:
            break
    return tuple(result)


def _metrics(\n    cases: Sequence[SubstitutionCase], attr: str, k: int\n) -> dict[str, float | int]:
    hits = 0
    true_positives = 0
    returned = 0

    for case in cases:
        candidates = _top_k_unique(getattr(case, attr), k, case.subject_id)
        returned += len(candidates)
        matched = set(candidates) & set(case.verified_equivalents)
        true_positives += len(matched)
        hits += int(bool(matched))

    total = len(cases)
    return {
        "cases": total,
        "hits": hits,
        "discovery_rate": hits / total if total else 0.0,
        "precision_at_k": true_positives / returned if returned else 0.0,
        "verified_candidates": true_positives,
        "returned_candidates": returned,
    }


def evaluate_substitution_discovery(
    cases: Iterable[SubstitutionCase],
    *,
    k: int = 5,
) -> dict[str, object]:
    """Compare semantic discovery with a lexical baseline.

    Falsifier:
        semantic discovery rate <= lexical discovery rate

    The benchmark therefore rewards only additional independently verified
    substitutions. Taxonomy overlap by itself contributes zero score.
    """

    if k < 1:
        raise ValueError("k must be >= 1")

    admitted = tuple(cases)
    if not admitted:
        raise ValueError("at least one substitution case is required")

    lexical = _metrics(admitted, "lexical_candidates", k)
    semantic = _metrics(admitted, "semantic_candidates", k)
    lift = float(semantic["discovery_rate"]) - float(lexical["discovery_rate"])

    return {
        "schema": "autofde.semantic-substitution-benchmark.v1",
        "k": k,
        "oracle": "independent_behavioral_verification",
        "lexical": lexical,
        "semantic": semantic,
        "discovery_rate_lift": lift,
        "falsifier": "semantic_discovery_rate <= lexical_discovery_rate",
        "falsifier_triggered": lift <= 0.0,
        "authority": "NONE",
    }
