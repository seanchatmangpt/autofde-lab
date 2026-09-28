"""GRASP/Berthier strategy partition and selection court.

Implements the bounded pipeline:

    Doctrine -> StrategyPartition[] -> Candidate[] -> Court[] -> SELECT

SELECT remains a candidate-routing result. It is never DO authority. Any
selected candidate may proceed only through SA2A/XaaS -> BRCE -> DO, where
BRCE performs the independent authority/admission step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .crowns.model import Verdict, content_id

__all__ = [
    "Doctrine",
    "StrategyPartition",
    "StrategyCandidate",
    "CandidateCourtResult",
    "SelectionReceipt",
    "partition_doctrine",
    "evaluate_candidate",
    "select_candidate",
]

ALLOWED_DOWNSTREAM_ROUTES = {("SA2A", "BRCE", "DO"), ("XAAS", "BRCE", "DO")}


def _clean_set(values: Iterable[str], name: str) -> frozenset[str]:
    cleaned = frozenset(value.strip() for value in values)
    if not cleaned or any(not value for value in cleaned):
        raise ValueError(f"{name} must contain non-empty values")
    return cleaned


@dataclass(frozen=True)
class Doctrine:
    doctrine_id: str
    exact_subject: str
    required_constraints: frozenset[str]
    allowed_strategy_ids: frozenset[str]
    max_partitions: int = 16
    max_strategies_per_partition: int = 32
    max_candidates_per_partition: int = 64

    def __post_init__(self) -> None:
        if not self.doctrine_id.strip() or not self.exact_subject.strip():
            raise ValueError("doctrine_id and exact_subject are required")
        object.__setattr__(
            self, "required_constraints",
            _clean_set(self.required_constraints, "required_constraints"),
        )
        object.__setattr__(
            self, "allowed_strategy_ids",
            _clean_set(self.allowed_strategy_ids, "allowed_strategy_ids"),
        )
        if self.max_partitions < 1:
            raise ValueError("max_partitions must be positive")
        if self.max_strategies_per_partition < 1:
            raise ValueError("max_strategies_per_partition must be positive")
        if self.max_candidates_per_partition < 1:
            raise ValueError("max_candidates_per_partition must be positive")

    @property
    def digest(self) -> str:
        return content_id(
            {
                "doctrine_id": self.doctrine_id,
                "exact_subject": self.exact_subject,
                "required_constraints": sorted(self.required_constraints),
                "allowed_strategy_ids": sorted(self.allowed_strategy_ids),
                "max_partitions": self.max_partitions,
                "max_strategies_per_partition": self.max_strategies_per_partition,
                "max_candidates_per_partition": self.max_candidates_per_partition,
            }
        )


@dataclass(frozen=True)
class StrategyPartition:
    partition_id: str
    doctrine_digest: str
    strategy_ids: frozenset[str]
    constraints: frozenset[str]
    ordinal: int

    @property
    def digest(self) -> str:
        return content_id(
            {
                "partition_id": self.partition_id,
                "doctrine_digest": self.doctrine_digest,
                "strategy_ids": sorted(self.strategy_ids),
                "constraints": sorted(self.constraints),
                "ordinal": self.ordinal,
            }
        )


@dataclass(frozen=True)
class StrategyCandidate:
    candidate_id: str
    exact_subject: str
    partition_id: str
    partition_digest: str
    strategy_ids: tuple[str, ...]
    constraints: frozenset[str]
    score: float
    producer_digest: str
    authority_delta: int = 0
    route: tuple[str, str, str] = ("SA2A", "BRCE", "DO")

    @property
    def digest(self) -> str:
        return content_id(
            {
                "candidate_id": self.candidate_id,
                "exact_subject": self.exact_subject,
                "partition_id": self.partition_id,
                "partition_digest": self.partition_digest,
                "strategy_ids": list(self.strategy_ids),
                "constraints": sorted(self.constraints),
                "score": self.score,
                "producer_digest": self.producer_digest,
                "authority_delta": self.authority_delta,
                "route": list(self.route),
            }
        )


@dataclass(frozen=True)
class CandidateCourtResult:
    candidate_id: str
    candidate_digest: str
    verdict: Verdict
    failures: tuple[str, ...]
    authority: str = "none"

    @property
    def digest(self) -> str:
        return content_id(
            {
                "candidate_id": self.candidate_id,
                "candidate_digest": self.candidate_digest,
                "verdict": self.verdict.value,
                "failures": list(self.failures),
                "authority": self.authority,
            }
        )


@dataclass(frozen=True)
class SelectionReceipt:
    schema: str
    exact_subject: str
    doctrine_digest: str
    selected_candidate_id: str | None
    selected_candidate_digest: str | None
    candidate_court_digests: tuple[str, ...]
    verdict: Verdict
    failures: tuple[str, ...]
    route: tuple[str, ...]
    phase: str = "SELECT"
    authority: str = "none"

    @property
    def replay_digest(self) -> str:
        return content_id(
            {
                "schema": self.schema,
                "exact_subject": self.exact_subject,
                "doctrine_digest": self.doctrine_digest,
                "selected_candidate_id": self.selected_candidate_id,
                "selected_candidate_digest": self.selected_candidate_digest,
                "candidate_court_digests": list(self.candidate_court_digests),
                "verdict": self.verdict.value,
                "failures": list(self.failures),
                "route": list(self.route),
                "phase": self.phase,
                "authority": self.authority,
            }
        )


def partition_doctrine(
    doctrine: Doctrine,
    specs: Sequence[Mapping[str, object]],
) -> tuple[StrategyPartition, ...]:
    """Construct bounded, disjoint strategy partitions from admitted doctrine."""

    if len(specs) > doctrine.max_partitions:
        raise ValueError("UNBOUNDED_PARTITION_COUNT")
    partitions: list[StrategyPartition] = []
    seen_strategy_ids: set[str] = set()
    seen_partition_ids: set[str] = set()
    for ordinal, spec in enumerate(specs):
        partition_id = str(spec.get("partition_id", "")).strip()
        if not partition_id or partition_id in seen_partition_ids:
            raise ValueError("INVALID_OR_DUPLICATE_PARTITION_ID")
        seen_partition_ids.add(partition_id)
        raw_strategies = spec.get("strategy_ids", ())
        if not isinstance(raw_strategies, (list, tuple, set, frozenset)):
            raise ValueError("INVALID_STRATEGY_SET")
        strategies = frozenset(str(item).strip() for item in raw_strategies)
        if not strategies or any(not item for item in strategies):
            raise ValueError("EMPTY_STRATEGY_PARTITION")
        if len(strategies) > doctrine.max_strategies_per_partition:
            raise ValueError("UNBOUNDED_STRATEGY_PARTITION")
        if not strategies.issubset(doctrine.allowed_strategy_ids):
            raise ValueError("STRATEGY_OUTSIDE_DOCTRINE")
        overlap = strategies & seen_strategy_ids
        if overlap:
            raise ValueError(f"CROSS_PARTITION_CONTAMINATION:{sorted(overlap)!r}")
        seen_strategy_ids.update(strategies)
        raw_constraints = spec.get("constraints", ())
        if not isinstance(raw_constraints, (list, tuple, set, frozenset)):
            raise ValueError("INVALID_PARTITION_CONSTRAINTS")
        constraints = frozenset(str(item).strip() for item in raw_constraints)
        if not doctrine.required_constraints.issubset(constraints):
            raise ValueError("CONSTRAINT_WEAKENING")
        partitions.append(
            StrategyPartition(
                partition_id=partition_id,
                doctrine_digest=doctrine.digest,
                strategy_ids=strategies,
                constraints=constraints,
                ordinal=ordinal,
            )
        )
    return tuple(partitions)


def evaluate_candidate(
    doctrine: Doctrine,
    partition: StrategyPartition,
    candidate: StrategyCandidate,
) -> CandidateCourtResult:
    """Fail closed on partition, constraint, route, and authority drift."""

    failures: list[str] = []
    if partition.doctrine_digest != doctrine.digest:
        failures.append("PARTITION_DOCTRINE_MISMATCH")
    if candidate.exact_subject != doctrine.exact_subject:
        failures.append("EXACT_SUBJECT_MISMATCH")
    if candidate.partition_id != partition.partition_id:
        failures.append("CROSS_PARTITION_CONTAMINATION")
    if candidate.partition_digest != partition.digest:
        failures.append("PARTITION_DIGEST_MISMATCH")
    strategy_ids = tuple(candidate.strategy_ids)
    if not strategy_ids:
        failures.append("EMPTY_STRATEGY")
    if len(strategy_ids) != len(set(strategy_ids)):
        failures.append("DUPLICATE_STRATEGY")
    if len(strategy_ids) > doctrine.max_strategies_per_partition:
        failures.append("UNBOUNDED_STRATEGY")
    if not set(strategy_ids).issubset(partition.strategy_ids):
        failures.append("CROSS_PARTITION_CONTAMINATION")
    required = doctrine.required_constraints | partition.constraints
    if not required.issubset(candidate.constraints):
        failures.append("CONSTRAINT_WEAKENING")
    if candidate.authority_delta > 0:
        failures.append("AUTHORITY_INCREASE")
    if candidate.route not in ALLOWED_DOWNSTREAM_ROUTES:
        failures.append("ILLEGAL_DOWNSTREAM_ROUTE")
    if candidate.route[-1] != "DO" or candidate.route[-2] != "BRCE":
        failures.append("SELECT_DO_COLLAPSE")
    unique = tuple(dict.fromkeys(failures))
    return CandidateCourtResult(
        candidate_id=candidate.candidate_id,
        candidate_digest=candidate.digest,
        verdict=Verdict.PASS if not unique else Verdict.COUNTEREXAMPLE,
        failures=unique,
    )


def select_candidate(
    doctrine: Doctrine,
    partitions: Sequence[StrategyPartition],
    candidates: Sequence[StrategyCandidate],
) -> SelectionReceipt:
    """Deterministically SELECT the highest-scoring admitted candidate.

    This function has no actuation edge. Ties are broken by content identity
    rather than caller order, making replay independent of iteration order.
    """

    partition_by_id = {partition.partition_id: partition for partition in partitions}
    failures: list[str] = []
    if len(partition_by_id) != len(partitions):
        failures.append("DUPLICATE_PARTITION_ID")
    counts: dict[str, int] = {}
    court_pairs: list[tuple[StrategyCandidate, CandidateCourtResult]] = []
    for candidate in candidates:
        counts[candidate.partition_id] = counts.get(candidate.partition_id, 0) + 1
        partition = partition_by_id.get(candidate.partition_id)
        if partition is None:
            court_pairs.append(
                (
                    candidate,
                    CandidateCourtResult(
                        candidate_id=candidate.candidate_id,
                        candidate_digest=candidate.digest,
                        verdict=Verdict.COUNTEREXAMPLE,
                        failures=("UNKNOWN_PARTITION",),
                    ),
                )
            )
            continue
        court_pairs.append((candidate, evaluate_candidate(doctrine, partition, candidate)))
    for partition_id, count in counts.items():
        if count > doctrine.max_candidates_per_partition:
            failures.append(f"UNBOUNDED_CANDIDATES:{partition_id}")

    passing = [pair for pair in court_pairs if pair[1].verdict is Verdict.PASS]
    selected: StrategyCandidate | None = None
    if passing and not failures:
        selected = sorted(
            (candidate for candidate, _court in passing),
            key=lambda item: (-item.score, item.digest, item.candidate_id),
        )[0]
    elif not passing:
        failures.append("NO_ADMITTED_CANDIDATE")

    route: tuple[str, ...] = selected.route if selected is not None else ()
    verdict = Verdict.PASS if selected is not None and not failures else Verdict.COUNTEREXAMPLE
    court_digests = tuple(
        sorted(court.digest for _candidate, court in court_pairs)
    )
    return SelectionReceipt(
        schema="autofde-lab.grasp-selection/1",
        exact_subject=doctrine.exact_subject,
        doctrine_digest=doctrine.digest,
        selected_candidate_id=selected.candidate_id if selected else None,
        selected_candidate_digest=selected.digest if selected else None,
        candidate_court_digests=court_digests,
        verdict=verdict,
        failures=tuple(dict.fromkeys(failures)),
        route=route,
    )
