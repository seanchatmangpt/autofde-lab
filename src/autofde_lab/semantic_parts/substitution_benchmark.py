"""Falsifier for semantic software-part discovery.

The benchmark consumes independent behavioral-equivalence judgements as its
oracle. CodeGraph/ontology overlap may rank candidates, but it cannot create the
oracle labels it is evaluated against.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb
import re
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class BehavioralWitness:
    """Receipt-backed evidence for one behavioral-equivalence judgement."""

    candidate_id: str
    receipt_digest: str
    verifier: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("behavioral witness candidate_id must be non-empty")
        if not self.verifier:
            raise ValueError("behavioral witness verifier must be non-empty")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.receipt_digest):
            raise ValueError(
                "behavioral witness receipt_digest must be sha256:<64 lowercase hex>"
            )

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "BehavioralWitness":
        candidate_id = value.get("candidate_id")
        receipt_digest = value.get("receipt_digest")
        verifier = value.get("verifier")
        if not all(isinstance(item, str) for item in (candidate_id, receipt_digest, verifier)):
            raise ValueError("behavioral witness fields must be strings")
        return cls(
            candidate_id=candidate_id,
            receipt_digest=receipt_digest,
            verifier=verifier,
        )


@dataclass(frozen=True)
class SubstitutionCase:
    """One hidden-name substitution discovery court."""

    subject_id: str
    verified_equivalents: frozenset[str]
    lexical_candidates: tuple[str, ...]
    semantic_candidates: tuple[str, ...]
    behavioral_witnesses: tuple[BehavioralWitness, ...] = ()

    def __post_init__(self) -> None:
        if not self.subject_id:
            raise ValueError("subject_id must be non-empty")
        if not self.verified_equivalents:
            raise ValueError("verified_equivalents must be non-empty")
        if self.subject_id in self.verified_equivalents:
            raise ValueError("subject_id cannot verify itself as a substitution")

        witness_ids = [witness.candidate_id for witness in self.behavioral_witnesses]
        if len(set(witness_ids)) != len(witness_ids):
            raise ValueError("behavioral witness candidate_ids must be unique")
        unknown_witnesses = set(witness_ids) - set(self.verified_equivalents)
        if unknown_witnesses:
            raise ValueError(
                "behavioral witnesses may only reference verified_equivalents: "
                + ",".join(sorted(unknown_witnesses))
            )

    @property
    def oracle_receipted(self) -> bool:
        witnessed = {witness.candidate_id for witness in self.behavioral_witnesses}
        return witnessed == set(self.verified_equivalents)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "SubstitutionCase":
        """Admit one JSON-compatible benchmark case."""

        subject = value.get("subject_id")
        verified = value.get("verified_equivalents")
        lexical = value.get("lexical_candidates", [])
        semantic = value.get("semantic_candidates", [])
        witnesses = value.get("behavioral_witnesses", [])

        if not isinstance(subject, str):
            raise ValueError("subject_id must be a string")
        if not isinstance(verified, list) or not all(
            isinstance(item, str) for item in verified
        ):
            raise ValueError("verified_equivalents must be a list of strings")
        if not isinstance(lexical, list) or not all(
            isinstance(item, str) for item in lexical
        ):
            raise ValueError("lexical_candidates must be a list of strings")
        if not isinstance(semantic, list) or not all(
            isinstance(item, str) for item in semantic
        ):
            raise ValueError("semantic_candidates must be a list of strings")
        if not isinstance(witnesses, list) or not all(
            isinstance(item, dict) for item in witnesses
        ):
            raise ValueError("behavioral_witnesses must be a list of objects")

        return cls(
            subject_id=subject,
            verified_equivalents=frozenset(verified),
            lexical_candidates=tuple(lexical),
            semantic_candidates=tuple(semantic),
            behavioral_witnesses=tuple(
                BehavioralWitness.from_mapping(item) for item in witnesses
            ),
        )


def _top_k_unique(
    candidates: Sequence[str], k: int, subject_id: str
) -> tuple[str, ...]:
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


def _metrics(
    cases: Sequence[SubstitutionCase], attr: str, k: int
) -> dict[str, float | int]:
    hits = 0
    top1_hits = 0
    true_positives = 0
    returned = 0
    relevant = 0
    reciprocal_rank = 0.0

    for case in cases:
        candidates = _top_k_unique(getattr(case, attr), k, case.subject_id)
        verified = set(case.verified_equivalents)
        returned += len(candidates)
        relevant += len(verified)

        matched = set(candidates) & verified
        true_positives += len(matched)
        hits += int(bool(matched))
        top1_hits += int(bool(candidates and candidates[0] in verified))

        first_rank = next(
            (rank for rank, candidate in enumerate(candidates, start=1) if candidate in verified),
            None,
        )
        if first_rank is not None:
            reciprocal_rank += 1.0 / first_rank

    total = len(cases)
    return {
        "cases": total,
        "hits": hits,
        "top1_hits": top1_hits,
        "discovery_rate": hits / total if total else 0.0,
        "top1_rate": top1_hits / total if total else 0.0,
        "precision_at_k": true_positives / returned if returned else 0.0,
        "recall_at_k": true_positives / relevant if relevant else 0.0,
        "mrr_at_k": reciprocal_rank / total if total else 0.0,
        "verified_candidates": true_positives,
        "relevant_candidates": relevant,
        "returned_candidates": returned,
    }



def _paired_outcomes(
    cases: Sequence[SubstitutionCase], k: int
) -> dict[str, float | int | bool]:
    semantic_wins = 0
    lexical_wins = 0
    ties = 0

    for case in cases:
        verified = set(case.verified_equivalents)
        lexical_hit = bool(
            set(_top_k_unique(case.lexical_candidates, k, case.subject_id)) & verified
        )
        semantic_hit = bool(
            set(_top_k_unique(case.semantic_candidates, k, case.subject_id)) & verified
        )
        if semantic_hit and not lexical_hit:
            semantic_wins += 1
        elif lexical_hit and not semantic_hit:
            lexical_wins += 1
        else:
            ties += 1

    non_ties = semantic_wins + lexical_wins
    if non_ties == 0:
        p_value = 1.0
    else:
        tail = min(semantic_wins, lexical_wins)
        one_tail = sum(comb(non_ties, i) for i in range(tail + 1)) / (2**non_ties)
        p_value = min(1.0, 2.0 * one_tail)

    return {
        "semantic_wins": semantic_wins,
        "lexical_wins": lexical_wins,
        "ties": ties,
        "non_ties": non_ties,
        "two_sided_sign_test_p_value": p_value,
        "semantic_advantage": semantic_wins > lexical_wins,
        "statistically_supported_0_05": (
            semantic_wins > lexical_wins and p_value <= 0.05
        ),
    }


def evaluate_substitution_discovery(
    cases: Iterable[SubstitutionCase],
    *,
    k: int = 5,
    require_receipts: bool = False,
) -> dict[str, object]:
    """Compare semantic discovery with a lexical baseline.

    Primary falsifier:
        semantic discovery rate <= lexical discovery rate

    The benchmark rewards only additional independently verified
    substitutions. Taxonomy overlap by itself contributes zero score.
    """

    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k must be an integer >= 1")

    admitted = tuple(cases)
    if not admitted:
        raise ValueError("at least one substitution case is required")
    if not all(isinstance(case, SubstitutionCase) for case in admitted):
        raise TypeError("cases must contain SubstitutionCase values")

    receipted_cases = sum(case.oracle_receipted for case in admitted)
    if require_receipts and receipted_cases != len(admitted):
        raise ValueError(
            "behavioral witness receipts are required for every verified equivalent"
        )

    lexical = _metrics(admitted, "lexical_candidates", k)
    semantic = _metrics(admitted, "semantic_candidates", k)
    discovery_lift = float(semantic["discovery_rate"]) - float(
        lexical["discovery_rate"]
    )
    mrr_lift = float(semantic["mrr_at_k"]) - float(lexical["mrr_at_k"])
    recall_lift = float(semantic["recall_at_k"]) - float(lexical["recall_at_k"])
    paired = _paired_outcomes(admitted, k)

    return {
        "schema": "autofde.semantic-substitution-benchmark.v1",
        "k": k,
        "case_count": len(admitted),
        "oracle": "independent_behavioral_verification",
        "oracle_standing": (
            "RECEIPTED" if receipted_cases == len(admitted) else "DECLARED"
        ),
        "receipted_cases": receipted_cases,
        "lexical": lexical,
        "semantic": semantic,
        "discovery_rate_lift": discovery_lift,
        "mrr_lift": mrr_lift,
        "recall_lift": recall_lift,
        "paired": paired,
        "falsifier": "semantic_discovery_rate <= lexical_discovery_rate",
        "falsifier_triggered": discovery_lift <= 0.0,
        "authority": "NONE",
        "standing": "OBSERVED",
    }


def evaluate_at_cutoffs(
    cases: Iterable[SubstitutionCase],
    *,
    cutoffs: Sequence[int] = (1, 3, 5, 10),
    require_receipts: bool = False,
) -> dict[str, object]:
    """Evaluate the same admitted court at several retrieval budgets."""

    admitted = tuple(cases)
    if not admitted:
        raise ValueError("at least one substitution case is required")
    normalized = tuple(cutoffs)
    if not normalized or any(
        not isinstance(k, int) or isinstance(k, bool) or k < 1 for k in normalized
    ):
        raise ValueError("cutoffs must contain positive integers")
    if len(set(normalized)) != len(normalized):
        raise ValueError("cutoffs must be unique")

    reports = {
        str(k): evaluate_substitution_discovery(
            admitted, k=k, require_receipts=require_receipts
        )
        for k in sorted(normalized)
    }
    return {
        "schema": "autofde.semantic-substitution-sweep.v1",
        "oracle": "independent_behavioral_verification",
        "oracle_standing": (
            "RECEIPTED" if all(case.oracle_receipted for case in admitted) else "DECLARED"
        ),
        "cutoffs": sorted(normalized),
        "reports": reports,
        "authority": "NONE",
        "standing": "OBSERVED",
    }
