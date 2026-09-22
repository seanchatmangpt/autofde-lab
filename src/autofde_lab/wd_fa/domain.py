from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class Standing(StrEnum):
    UNKNOWN = "UNKNOWN"
    PARTIAL_ALIVE = "PARTIAL_ALIVE"
    ALIVE = "ALIVE"
    BLOCKED = "BLOCKED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class EvidenceArtifact:
    evidence_id: str
    kind: str
    digest: str
    source_ref: str = ""
    modality: str = "unknown"


@dataclass(frozen=True)
class FailureModeRule:
    mode_id: str
    applicability: Mapping[str, object]
    falsifiers: Mapping[str, object]
    required_evidence_kinds: frozenset[str]
    next_action: str
    prior_case_ids: tuple[str, ...] = ()
    owning_team: str = "failure_analysis"
    action_type: str = "ANALYZE"

    def applies(self, facts: Mapping[str, object]) -> bool:
        return all(facts.get(key) == value for key, value in self.applicability.items())

    def falsified_by(self, facts: Mapping[str, object]) -> bool:
        return any(facts.get(key) == value for key, value in self.falsifiers.items())


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    drive_id: str
    symptom: str
    facts: Mapping[str, object]
    evidence: tuple[EvidenceArtifact, ...]
    process: tuple[str, ...]


@dataclass(frozen=True)
class CandidateHypothesis:
    mode_id: str
    candidate_score: float
    score_basis: str
    structural_similarity: float
    deterministic_match: bool
    evidence_completeness: float
    prior_case_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    owning_team: str
    action_type: str
    next_action: str


@dataclass(frozen=True)
class CandidateTriage:
    case_id: str
    standing: Standing
    admitted_mode: str | None
    candidate_modes: tuple[str, ...]
    model_ranking: tuple[tuple[str, float], ...]
    next_action: str
    evidence_completeness: float
    exploratory_steps: int
    reason: str
    ranked_hypotheses: tuple[CandidateHypothesis, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    closest_prior_case_ids: tuple[str, ...] = ()
    action_type: str = "ANALYZE"
    owning_team: str = "failure_analysis"
    confidence_basis: str = "UNSPECIFIED"
    human_gate: str = "ENGINEER_DISPOSITION_REQUIRED"


@dataclass(frozen=True)
class MachineExperience:
    experience_id: str
    source_case_id: str
    mode: FailureModeRule
    verifier_id: str
    exploratory_steps: int


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    subject_case_id: str
    standing: Standing
    evidence_ids: tuple[str, ...]
    hypotheses: tuple[str, ...]
    next_action: str
    acceptance: tuple[str, ...]
    action_type: str
    owning_team: str
    human_gate: str
    authority: str = "SELECT_ONLY"


def evidence_kinds(case: FailureCase) -> frozenset[str]:
    return frozenset(item.kind for item in case.evidence)


def evidence_completeness(rule: FailureModeRule, case: FailureCase) -> float:
    required = rule.required_evidence_kinds
    if not required:
        return 1.0
    return len(required & evidence_kinds(case)) / len(required)


def make_work_order(triage: CandidateTriage, case: FailureCase) -> WorkOrder:
    return WorkOrder(
        work_order_id=f"WO-{case.case_id}",
        subject_case_id=case.case_id,
        standing=triage.standing,
        evidence_ids=triage.supporting_evidence_ids
        or tuple(item.evidence_id for item in case.evidence),
        hypotheses=triage.candidate_modes,
        next_action=triage.next_action,
        acceptance=("independent-verifier-confirms", "receipt-replays"),
        action_type=triage.action_type,
        owning_team=triage.owning_team,
        human_gate=triage.human_gate,
    )
