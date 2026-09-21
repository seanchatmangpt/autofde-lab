from __future__ import annotations

from collections.abc import Iterable

from .domain import (
    CandidateTriage,
    FailureCase,
    FailureModeRule,
    MachineExperience,
    Standing,
    evidence_completeness,
)
from .synthetic import feature_frame


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
    *,
    mode_id: str,
    verifier_id: str,
    next_action: str,
) -> MachineExperience:
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
        verifier_id=verifier_id,
        exploratory_steps=3,
    )
