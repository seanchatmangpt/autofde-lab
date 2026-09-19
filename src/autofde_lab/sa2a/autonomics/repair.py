"""GALL-013 bounded repair selection; execution is delegated to ash_a2a."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Callable, Iterable, Mapping

from .belief import BeliefState


@dataclass(frozen=True, slots=True)
class RepairCandidate:
    candidate_id: str
    capability_id: str
    requirements: Mapping[str, bool]
    expected_postcondition: Mapping[str, object]
    cost: float
    risk: float
    predictor_score: float = 0.0


@dataclass(frozen=True, slots=True)
class InterventionRequest:
    candidate_id: str
    capability_id: str
    semantic_subject: str
    authority_required: bool
    idempotency_key: str
    expected_postcondition: Mapping[str, object]
    selection_digest: str


class RepairSelector:
    def __init__(self, *, risk_budget: float, cost_budget: float) -> None:
        self.risk_budget = risk_budget
        self.cost_budget = cost_budget

    def preflight(
        self,
        belief: BeliefState,
        candidates: Iterable[RepairCandidate],
        *,
        falsifiers: Iterable[Callable[[RepairCandidate], bool]] = (),
    ) -> tuple[RepairCandidate, ...]:
        lawful: list[RepairCandidate] = []
        checks = tuple(falsifiers)
        for candidate in candidates:
            ready, _unknown = belief.require(candidate.requirements)
            if not ready:
                continue
            if candidate.risk > self.risk_budget or candidate.cost > self.cost_budget:
                continue
            if any(not check(candidate) for check in checks):
                continue
            lawful.append(candidate)
        return tuple(
            sorted(
                lawful,
                key=lambda item: (
                    item.risk,
                    item.cost,
                    -item.predictor_score,
                    item.candidate_id,
                ),
            )
        )

    def select(
        self,
        belief: BeliefState,
        candidates: Iterable[RepairCandidate],
        *,
        semantic_subject: str,
        falsifiers: Iterable[Callable[[RepairCandidate], bool]] = (),
    ) -> InterventionRequest:
        lawful = self.preflight(belief, candidates, falsifiers=falsifiers)
        if not lawful:
            raise RuntimeError("BLOCKED(no-lawful-repair-candidate)")
        selected = lawful[0]
        payload = {
            "candidate": asdict(selected),
            "semantic_subject": semantic_subject,
            "belief_digest": belief.digest,
        }
        selection_digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        return InterventionRequest(
            candidate_id=selected.candidate_id,
            capability_id=selected.capability_id,
            semantic_subject=semantic_subject,
            authority_required=True,
            idempotency_key=selection_digest,
            expected_postcondition=selected.expected_postcondition,
            selection_digest=selection_digest,
        )
