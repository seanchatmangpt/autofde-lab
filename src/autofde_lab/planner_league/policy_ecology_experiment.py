"""Conditioned policy cross-play and heterogeneity payoff evidence.

This module turns Planner League policy ecologies into bounded candidate
experiment schedules, then admits payoff evidence only when an external
execution receipt is supplied. It never dispatches a solver or grants authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import fsum
from typing import Any

from .catalog import ROLE_SPECS
from .core import PolicySpec
from .policy_ecology import ConditionedPolicy, PolicyEcology
from .policy_identity import policy_identity



def _validate_role_binding(ecology: PolicyEcology, role_id: str, side: str) -> None:
    role = ROLE_SPECS.get(role_id)
    if role is None:
        raise ValueError(f"REFUSED:UNKNOWN_ROLE:{role_id}")
    for index, member in enumerate(ecology.members):
        policy = member.policy
        if (
            policy.objective_id != role["objective"]
            or policy.action_projection_id != role["action_projection"]
        ):
            raise ValueError(
                f"REFUSED:ECOLOGY_POLICY_ROLE_MISMATCH:{side}:{index}:{role_id}"
            )


@dataclass(frozen=True, slots=True)
class EcologyParticipant:
    member_index: int
    policy: PolicySpec
    condition: tuple[tuple[str, float], ...]
    weight: float
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def from_member(
        cls,
        member: ConditionedPolicy,
        index: int,
    ) -> "EcologyParticipant":
        return cls(
            member_index=index,
            policy=member.policy,
            condition=member.condition.values,
            weight=member.weight,
            evidence_refs=member.evidence_refs,
        )

    @property
    def identity_sha256(self) -> str:
        payload = {
            "member_index": self.member_index,
            "policy_identity": policy_identity(self.policy),
            "condition": self.condition,
            "weight": self.weight,
            "evidence_refs": self.evidence_refs,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class EcologyMatch:
    world_id: str
    left_role_id: str
    right_role_id: str
    left: EcologyParticipant
    right: EcologyParticipant
    cue: float | None = None

    @property
    def identity_sha256(self) -> str:
        payload = {
            "world_id": self.world_id,
            "left_role_id": self.left_role_id,
            "right_role_id": self.right_role_id,
            "left": self.left.identity_sha256,
            "right": self.right.identity_sha256,
            "cue": self.cue,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def as_gymact_candidate(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "experiment_kind": "conditioned_policy_cross_play",
            "experiment_identity_sha256": self.identity_sha256,
            "world_id": self.world_id,
            "roles": {
                "left": self.left_role_id,
                "right": self.right_role_id,
            },
            "cue": self.cue,
            "players": {
                "left": {
                    "policy_identity_sha256": policy_identity(self.left.policy),
                    "planner_id": self.left.policy.planner_id,
                    "condition": dict(self.left.condition),
                    "population_weight": self.left.weight,
                },
                "right": {
                    "policy_identity_sha256": policy_identity(self.right.policy),
                    "planner_id": self.right.policy.planner_id,
                    "condition": dict(self.right.condition),
                    "population_weight": self.right.weight,
                },
            },
            "authority_semantics": {
                "candidate_only": True,
                "phenotype_has_authority": False,
                "execution_authority": "external_brce_only",
            },
        }


@dataclass(frozen=True, slots=True)
class EcologySchedule:
    matches: tuple[EcologyMatch, ...]
    total_cardinality: int
    truncated: bool
    max_matches: int

    def __post_init__(self) -> None:
        if self.max_matches < 1:
            raise ValueError("REFUSED:MAX_MATCHES_MUST_BE_POSITIVE")
        if len(self.matches) > self.max_matches:
            raise ValueError("REFUSED:ECOLOGY_SCHEDULE_BOUND_EXCEEDED")


def manufacture_ecology_schedule(
    left: PolicyEcology,
    right: PolicyEcology,
    *,
    world_id: str,
    left_role_id: str,
    right_role_id: str,
    max_matches: int = 4096,
    cue: float | None = None,
) -> EcologySchedule:
    """Enumerate the bounded phenotype cross-product without executing it."""
    if max_matches < 1:
        raise ValueError("REFUSED:MAX_MATCHES_MUST_BE_POSITIVE")
    _validate_role_binding(left, left_role_id, "left")
    _validate_role_binding(right, right_role_id, "right")
    if cue is not None:
        left = left.condition(cue=cue)
        right = right.condition(cue=cue)

    left_members = tuple(
        EcologyParticipant.from_member(member, index)
        for index, member in enumerate(left.members)
    )
    right_members = tuple(
        EcologyParticipant.from_member(member, index)
        for index, member in enumerate(right.members)
    )
    total = len(left_members) * len(right_members)
    matches: list[EcologyMatch] = []
    for left_member in left_members:
        for right_member in right_members:
            if len(matches) >= max_matches:
                break
            matches.append(
                EcologyMatch(
                    world_id=world_id,
                    left_role_id=left_role_id,
                    right_role_id=right_role_id,
                    left=left_member,
                    right=right_member,
                    cue=cue,
                )
            )
        if len(matches) >= max_matches:
            break

    return EcologySchedule(
        matches=tuple(matches),
        total_cardinality=total,
        truncated=total > len(matches),
        max_matches=max_matches,
    )


@dataclass(frozen=True, slots=True)
class ObservedEcologyOutcome:
    match: EcologyMatch
    left_score: float
    right_score: float
    receipt_ids: tuple[str, ...]
    execution_observed: bool = True

    def __post_init__(self) -> None:
        if not self.execution_observed:
            raise ValueError("REFUSED:UNOBSERVED_ECOLOGY_PAYOFF")
        if not self.receipt_ids or any(not receipt.strip() for receipt in self.receipt_ids):
            raise ValueError("REFUSED:UNRECEIPTED_ECOLOGY_PAYOFF")


@dataclass(slots=True)
class EcologyPayoffSurface:
    observations: list[ObservedEcologyOutcome] = field(default_factory=list)

    def add(self, observation: ObservedEcologyOutcome) -> None:
        if not isinstance(observation, ObservedEcologyOutcome):
            raise TypeError(
                "REFUSED:ECOLOGY_PAYOFF_REQUIRES_OBSERVED_OUTCOME:"
                f"{type(observation).__name__}"
            )
        self.observations.append(observation)

    def mean_score(
        self,
        *,
        policy_identity_sha256: str,
        role_id: str,
        world_id: str,
    ) -> float | None:
        scores: list[float] = []
        for observation in self.observations:
            match = observation.match
            if match.world_id != world_id:
                continue
            if (
                match.left_role_id == role_id
                and policy_identity(match.left.policy) == policy_identity_sha256
            ):
                scores.append(observation.left_score)
            if (
                match.right_role_id == role_id
                and policy_identity(match.right.policy) == policy_identity_sha256
            ):
                scores.append(observation.right_score)
        return None if not scores else fsum(scores) / len(scores)


@dataclass(frozen=True, slots=True)
class HeterogeneityTrial:
    mission_id: str
    homogeneous_score: float
    engineered_score: float
    engineering_cost: float
    receipt_ids: tuple[str, ...]
    homogeneous_population_ref: str
    engineered_population_ref: str

    def __post_init__(self) -> None:
        if self.engineering_cost < 0.0:
            raise ValueError("REFUSED:NEGATIVE_HETEROGENEITY_COST")
        if not self.receipt_ids or any(not receipt.strip() for receipt in self.receipt_ids):
            raise ValueError("REFUSED:UNRECEIPTED_HETEROGENEITY_TRIAL")
        if self.homogeneous_population_ref == self.engineered_population_ref:
            raise ValueError("REFUSED:HETEROGENEITY_TRIAL_REQUIRES_DISTINCT_POPULATIONS")

    @property
    def gross_gain(self) -> float:
        return self.engineered_score - self.homogeneous_score

    @property
    def net_gain(self) -> float:
        return self.gross_gain - self.engineering_cost


@dataclass(frozen=True, slots=True)
class HeterogeneityEvidence:
    trial_count: int
    mean_gross_gain: float
    mean_net_gain: float
    positive_net_fraction: float


def summarize_heterogeneity(
    trials: Iterable[HeterogeneityTrial],
) -> HeterogeneityEvidence:
    values = tuple(trials)
    if not values:
        raise ValueError("REFUSED:HETEROGENEITY_EVIDENCE_REQUIRES_TRIAL")

    gross = [trial.gross_gain for trial in values]
    net = [trial.net_gain for trial in values]
    return HeterogeneityEvidence(
        trial_count=len(values),
        mean_gross_gain=fsum(gross) / len(gross),
        mean_net_gain=fsum(net) / len(net),
        positive_net_fraction=sum(value > 0.0 for value in net) / len(net),
    )
