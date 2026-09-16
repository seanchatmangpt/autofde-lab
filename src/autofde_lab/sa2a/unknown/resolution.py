"""UNKNOWN state handler and resolution pipeline (§36, §37, §64).

RFC-SA2A-001 v26.9.16:
UNKNOWN routes to candidate frontier; discovery produces a Candidate;
a Candidate must pass admission to become KNOWN (O*).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from autofde_lab.sa2a.unknown.allocator import (
    CandidateAllocation,
    CMCACandidateAllocator,
    ExplorationBudget,
    FrontierAllocationPlan,
    UnknownCandidate,
)


class EpistemicState(str, Enum):
    """Semantic epistemic state (§36, §37)."""

    UNKNOWN = "UNKNOWN"
    CANDIDATE = "CANDIDATE"
    KNOWN = "KNOWN"
    REFUSED = "REFUSED"


@dataclass(frozen=True, slots=True)
class UnknownQuery:
    """An inquiry or missing knowledge item in UNKNOWN state (§36)."""

    query_id: str
    predicate_or_topic: str
    context: Mapping[str, Any] = field(default_factory=dict)
    option_entropy: float = 1.0
    estimated_cost: float = 10.0


@dataclass(frozen=True, slots=True)
class CandidateResolution:
    """Candidate output produced by discovery exploration (§37, §64)."""

    candidate_id: str
    query_id: str
    proposed_assertion: str  # Structured rule, triple or relation
    evidence_payload: Mapping[str, Any]
    source_identity: str
    consumed_ticks: int
    consumed_tokens: int

    @property
    def candidate_hash(self) -> str:
        dumped = json.dumps(
            {
                "candidate_id": self.candidate_id,
                "query_id": self.query_id,
                "proposed_assertion": self.proposed_assertion,
                "evidence": self.evidence_payload,
                "source": self.source_identity,
            },
            sort_keys=True,
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AdmissionReceipt:
    """Receipt proving admission court evaluation of a candidate (§64)."""

    receipt_id: str
    candidate_hash: str
    admitted: bool
    epistemic_standing: EpistemicState
    reasons: tuple[str, ...]
    admitted_assertion: str | None = None


class UnknownResolutionPipeline:
    """Manages UNKNOWN -> Candidate Frontier -> Discovery -> Admission -> KNOWN lifecycle (§36, §37, §64)."""

    def __init__(
        self,
        *,
        allocator: CMCACandidateAllocator | None = None,
        admission_court: Callable[[CandidateResolution], AdmissionReceipt] | None = None,
    ) -> None:
        self.allocator = allocator or CMCACandidateAllocator()
        self.admission_court = admission_court or self._default_admission_court
        self._known_store: dict[str, str] = {}

    @property
    def known_store(self) -> Mapping[str, str]:
        return dict(self._known_store)

    @staticmethod
    def _default_admission_court(candidate: CandidateResolution) -> AdmissionReceipt:
        """Default fail-closed admission court (§64).

        Requires non-empty proposed assertion, evidence with source or hash,
        and no unsupported markers.
        """
        reasons: list[str] = []
        if not candidate.proposed_assertion.strip():
            reasons.append("EMPTY_ASSERTION")
        if not candidate.evidence_payload:
            reasons.append("MISSING_EVIDENCE")
        elif "error" in candidate.evidence_payload or "unsupported" in candidate.evidence_payload:
            reasons.append("UNSUPPORTED_OR_ERROR_EVIDENCE")

        if reasons:
            return AdmissionReceipt(
                receipt_id=f"rec-{uuid.uuid4().hex[:8]}",
                candidate_hash=candidate.candidate_hash,
                admitted=False,
                epistemic_standing=EpistemicState.REFUSED,
                reasons=tuple(reasons),
                admitted_assertion=None,
            )

        return AdmissionReceipt(
            receipt_id=f"rec-{uuid.uuid4().hex[:8]}",
            candidate_hash=candidate.candidate_hash,
            admitted=True,
            epistemic_standing=EpistemicState.KNOWN,
            reasons=("CONFORMS_TO_SPEC",),
            admitted_assertion=candidate.proposed_assertion,
        )

    def route_unknown_to_frontier(
        self,
        queries: Sequence[UnknownQuery],
        budget: ExplorationBudget,
        plan_id: str = "frontier_plan",
    ) -> tuple[FrontierAllocationPlan, dict[str, UnknownCandidate]]:
        """Route UNKNOWN items to candidate frontier with CMCA resource allocation (§37, §38)."""
        candidates_map: dict[str, UnknownCandidate] = {}
        candidate_list: list[UnknownCandidate] = []

        for q in queries:
            c = UnknownCandidate(
                item_id=q.query_id,
                description=f"Resolve UNKNOWN {q.predicate_or_topic}",
                option_entropy=q.option_entropy,
                estimated_cost=q.estimated_cost,
                metadata=q.context,
            )
            candidates_map[q.query_id] = c
            candidate_list.append(c)

        plan = self.allocator.allocate(
            plan_id=plan_id, budget=budget, candidates=candidate_list
        )
        return plan, candidates_map

    def admit_candidate(self, candidate: CandidateResolution) -> AdmissionReceipt:
        """Subject a discovered candidate to the admission court (§64).

        A candidate cannot grant itself KNOWN standing; only admission court can transition
        it to KNOWN and store it in admitted knowledge (O*).
        """
        receipt = self.admission_court(candidate)
        if receipt.admitted and receipt.admitted_assertion:
            self._known_store[candidate.query_id] = receipt.admitted_assertion
        return receipt
