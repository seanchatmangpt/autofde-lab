from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from .domain import (
    CandidateHypothesis,
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


def _structural_similarity(rule: FailureModeRule, case: FailureCase) -> float:
    if not rule.applicability:
        return 0.0
    matches = sum(
        case.facts.get(key) == value for key, value in rule.applicability.items()
    )
    return matches / len(rule.applicability)


def _rank_hypotheses(
    case: FailureCase,
    rules: tuple[FailureModeRule, ...],
    model_ranking: tuple[tuple[str, float], ...],
) -> tuple[CandidateHypothesis, ...]:
    model_scores = dict(model_ranking)
    ranked = []
    for rule in rules:
        deterministic = rule.applies(case.facts) and not rule.falsified_by(case.facts)
        completeness = evidence_completeness(rule, case)
        structural = _structural_similarity(rule, case)
        if rule.mode_id in model_scores:
            score = float(model_scores[rule.mode_id])
            score_basis = "TPOT_CANDIDATE_SCORE"
        else:
            score = structural
            score_basis = "STRUCTURAL_SIMILARITY"
        evidence_ids = tuple(
            item.evidence_id
            for item in case.evidence
            if item.kind in rule.required_evidence_kinds
        )
        ranked.append(
            CandidateHypothesis(
                mode_id=rule.mode_id,
                candidate_score=score,
                score_basis=score_basis,
                structural_similarity=structural,
                deterministic_match=deterministic,
                evidence_completeness=completeness,
                prior_case_ids=rule.prior_case_ids,
                evidence_ids=evidence_ids,
                owning_team=rule.owning_team,
                action_type=rule.action_type,
                next_action=rule.next_action,
            )
        )
    return tuple(
        sorted(
            ranked,
            key=lambda item: (
                item.deterministic_match,
                item.evidence_completeness,
                item.structural_similarity,
                item.candidate_score,
            ),
            reverse=True,
        )
    )


def _closest_prior_cases(
    ranked: tuple[CandidateHypothesis, ...],
) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for hypothesis in ranked[:3]:
        for prior_case_id in hypothesis.prior_case_ids:
            if prior_case_id not in seen:
                seen.add(prior_case_id)
                result.append(prior_case_id)
    return tuple(result)


def triage(
    case: FailureCase,
    rules: Iterable[FailureModeRule],
    *,
    candidate_model=None,
) -> CandidateTriage:
    rules = tuple(rules)
    model_ranking = (
        tuple(candidate_model.rank(feature_frame(case))) if candidate_model else ()
    )
    ranked = _rank_hypotheses(case, rules, model_ranking)
    applicable = tuple(
        rule
        for rule in rules
        if rule.applies(case.facts) and not rule.falsified_by(case.facts)
    )
    closest_prior = _closest_prior_cases(ranked)

    if not applicable:
        return CandidateTriage(
            case_id=case.case_id,
            standing=Standing.UNKNOWN,
            admitted_mode=None,
            candidate_modes=tuple(item.mode_id for item in ranked),
            model_ranking=model_ranking,
            next_action="open_novel_failure_investigation",
            evidence_completeness=0.0,
            exploratory_steps=3,
            reason="no admitted known failure mode survives applicability and falsifiers",
            ranked_hypotheses=ranked,
            supporting_evidence_ids=tuple(item.evidence_id for item in case.evidence),
            closest_prior_case_ids=closest_prior,
            action_type="ESCALATE",
            owning_team="failure_analysis",
            confidence_basis="NO_RULE_ADMISSION_CANDIDATE_RANKING_NON_AUTHORITATIVE",
        )

    best = max(applicable, key=lambda rule: evidence_completeness(rule, case))
    completeness = evidence_completeness(best, case)
    supporting = tuple(
        item.evidence_id
        for item in case.evidence
        if item.kind in best.required_evidence_kinds
    )
    if completeness < 1.0:
        return CandidateTriage(
            case_id=case.case_id,
            standing=Standing.PARTIAL_ALIVE,
            admitted_mode=None,
            candidate_modes=tuple(item.mode_id for item in ranked),
            model_ranking=model_ranking,
            next_action=best.next_action,
            evidence_completeness=completeness,
            exploratory_steps=1,
            reason="applicable prior exists but required evidence is incomplete",
            ranked_hypotheses=ranked,
            supporting_evidence_ids=supporting,
            closest_prior_case_ids=closest_prior,
            action_type=best.action_type,
            owning_team=best.owning_team,
            confidence_basis="DETERMINISTIC_RULE_INCOMPLETE_EVIDENCE",
        )
    return CandidateTriage(
        case_id=case.case_id,
        standing=Standing.ALIVE,
        admitted_mode=best.mode_id,
        candidate_modes=tuple(item.mode_id for item in ranked),
        model_ranking=model_ranking,
        next_action=best.next_action,
        evidence_completeness=1.0,
        exploratory_steps=0,
        reason="applicability and required evidence admit a known mode",
        ranked_hypotheses=ranked,
        supporting_evidence_ids=supporting,
        closest_prior_case_ids=closest_prior,
        action_type=best.action_type,
        owning_team=best.owning_team,
        confidence_basis="DETERMINISTIC_RULE_AND_REQUIRED_EVIDENCE",
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
        prior_case_ids=(case.case_id,),
        owning_team="failure_analysis",
        action_type="PROCEDURE",
    )
    return MachineExperience(
        experience_id=f"MX-{case.case_id}",
        source_case_id=case.case_id,
        mode=rule,
        verifier_id=receipt.verifier_id,
        exploratory_steps=3,
    )
