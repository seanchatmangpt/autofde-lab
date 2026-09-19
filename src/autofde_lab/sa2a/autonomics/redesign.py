"""GALL-031 process redesign canary: Prediction is not Promotion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RedesignCandidate:
    candidate_id: str
    powl_digest: str
    predicted_improvement: float
    formal_verification_digest: str
    falsifiers_passed: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanaryEnvelope:
    candidate: RedesignCandidate
    baseline_digest: str
    scope: str
    event_budget: int
    rollback_condition: str
    authority_required: bool
    envelope_digest: str

    @classmethod
    def build(
        cls,
        candidate: RedesignCandidate,
        *,
        baseline_digest: str,
        scope: str,
        event_budget: int,
        rollback_condition: str,
    ) -> "CanaryEnvelope":
        if event_budget <= 0 or not scope:
            raise ValueError("canary requires positive event budget and explicit scope")
        payload = {
            "candidate": asdict(candidate),
            "baseline_digest": baseline_digest,
            "scope": scope,
            "event_budget": event_budget,
            "rollback_condition": rollback_condition,
            "authority_required": True,
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        return cls(candidate=candidate, envelope_digest=digest, **{
            key: payload[key] for key in (
                "baseline_digest", "scope", "event_budget",
                "rollback_condition", "authority_required"
            )
        })


@dataclass(frozen=True, slots=True)
class CanaryEvidence:
    envelope_digest: str
    independent_observer_digest: str
    baseline_metrics: Mapping[str, float]
    canary_metrics: Mapping[str, float]
    postcondition_verified: bool
    rolled_back: bool = False

    def promotion_candidate(self, *, metric: str, higher_is_better: bool = True) -> dict[str, str]:
        if not self.postcondition_verified or self.rolled_back:
            raise RuntimeError("REFUSED(promotion-without-successful-independent-canary)")
        before = self.baseline_metrics[metric]
        after = self.canary_metrics[metric]
        improved = after > before if higher_is_better else after < before
        if not improved:
            raise RuntimeError("REFUSED(canary-not-improved)")
        return {
            "standing": "CANDIDATE",
            "kind": "PROCESS_LAW_PROMOTION_CANDIDATE",
            "canary_envelope_digest": self.envelope_digest,
            "observer_digest": self.independent_observer_digest,
        }
