from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .domain import (
    CandidateTriage,
    FailureCase,
    FailureModeRule,
    MachineExperience,
    Standing,
    evidence_completeness,
)
from .synthetic import feature_frame

if TYPE_CHECKING:
    from .receipts import VerificationReceipt


def triage(
    case: FailureCase,
    rules: Iterable[FailureModeRule],
    *,
    candidate_model=None,
) -> CandidateTriage:
    rules = tuple(rules)
    model_ranking = candidate_model.rank(feature_frame(case)) if candidate_model else ()
    applicable = tuple(
        rule
        for rule in rules
        if rule.applies(case.facts) and not rule.falsified_by(case.facts)
    )
    if not applicable:
        return CandidateTriage(
            case_id=case.case_id,
            standing=Standing.UNKNOWN,
            admitted_mode=None,
            candidate_modes=tuple(mode for mode, _ in model_ranking),
            model_ranking=model_ranking,
            next_action="open_novel_failure_investigation",
            evidence_completeness=0.0,
            exploratory_steps=3,
            reason="no admitted known failure mode survives applicability and falsifiers",
        )

    best = max(applicable, key=lambda rule: evidence_completeness(rule, case))
    completeness = evidence_completeness(best, case)
    if completeness < 1.0:
        return CandidateTriage(
            case_id=case.case_id,
            standing=Standing.PARTIAL_ALIVE,
            admitted_mode=None,
            candidate_modes=tuple(rule.mode_id for rule in applicable),
            model_ranking=model_ranking,
            next_action=best.next_action,
            evidence_completeness=completeness,
            exploratory_steps=1,
            reason="applicable prior exists but required evidence is incomplete",
        )
    return CandidateTriage(
        case_id=case.case_id,
        standing=Standing.ALIVE,
        admitted_mode=best.mode_id,
        candidate_modes=tuple(rule.mode_id for rule in applicable),
        model_ranking=model_ranking,
        next_action=best.next_action,
        evidence_completeness=1.0,
        exploratory_steps=0,
        reason="applicability and required evidence admit a known mode",
    )


def compile_experience(
    case: FailureCase,
    source_triage: CandidateTriage,
    receipt: "VerificationReceipt",
    *,
    mode_id: str,
    next_action: str,
) -> MachineExperience:
    from .receipts import candidate_digest, verify_receipt

    if not verify_receipt(receipt):
        raise ValueError("REFUSED:INVALID_RECEIPT")
    if receipt.subject_id != case.case_id or source_triage.case_id != case.case_id:
        raise ValueError("REFUSED:SUBJECT_BINDING")
    if receipt.candidate_digest != candidate_digest(source_triage):
        raise ValueError("REFUSED:CANDIDATE_BINDING")
    if receipt.observed_disposition != mode_id:
        raise ValueError("REFUSED:DISPOSITION_BINDING")
    if source_triage.standing is not Standing.UNKNOWN:
        raise ValueError("REFUSED:SOURCE_NOT_UNKNOWN")

    rule = FailureModeRule(
        mode_id=mode_id,
        applicability={
            "symptom_code": case.facts["symptom_code"],
            "firmware": case.facts["firmware"],
            "supplier": case.facts["supplier"],
            "station": case.facts["station"],
        },
        falsifiers={},
        required_evidence_kinds=frozenset(item.kind for item in case.evidence),
        next_action=next_action,
    )
    return MachineExperience(
        experience_id=f"MX-{case.case_id}",
        source_case_id=case.case_id,
        mode=rule,
        verifier_id=receipt.verifier_id,
        exploratory_steps=3,
    )
