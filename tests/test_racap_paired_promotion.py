from autofde_lab.evolution import (
    IntelligenceRung,
    PairedPromotionCourt,
    PairedPromotionPolicy,
    PairedTrial,
    PromotionDecision,
    ReasoningRetirementCourt,
    RetirementDecision,
    RetirementTrial,
)


def _paired(*, task: str, champion: float, candidate: float) -> PairedTrial:
    return PairedTrial(
        task_id=task,
        seed=7,
        budget_id="steps:32",
        champion_score=champion,
        candidate_score=candidate,
        champion_evidence_digest=f"sha256:champion-{task}",
        candidate_evidence_digest=f"sha256:candidate-{task}",
    )


def test_candidate_promotes_only_on_paired_net_gain_without_regression() -> None:
    verdict = PairedPromotionCourt(
        PairedPromotionPolicy(minimum_trials=2, minimum_total_delta=0.05)
    ).evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(
            _paired(task="a", champion=0.70, candidate=0.80),
            _paired(task="b", champion=0.60, candidate=0.70),
        ),
    )

    assert verdict.decision is PromotionDecision.PROMOTE
    assert round(verdict.total_delta, 6) == 0.20
    assert verdict.regression_count == 0
    assert verdict.authority == "none"
    assert verdict.evidence_digest.startswith("sha256:")


def test_single_task_regression_holds_candidate_even_with_positive_total() -> None:
    verdict = PairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(
            _paired(task="a", champion=0.50, candidate=0.80),
            _paired(task="b", champion=0.80, candidate=0.79),
        ),
    )

    assert verdict.decision is PromotionDecision.HOLD
    assert verdict.reasons == ("REGRESSION_BOUND_EXCEEDED",)


def test_duplicate_cohort_identity_is_refused() -> None:
    trial = _paired(task="same", champion=0.5, candidate=0.6)
    verdict = PairedPromotionCourt(
        PairedPromotionPolicy(minimum_trials=2)
    ).evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(trial, trial),
    )

    assert verdict.decision is PromotionDecision.REFUSE
    assert "DUPLICATE_COHORT_IDENTITY" in verdict.reasons


def _retirement(input_id: str, output: str = "sha256:same") -> RetirementTrial:
    return RetirementTrial(
        input_id=input_id,
        incumbent_output_digest=output,
        candidate_output_digest=output,
        incumbent_success=True,
        candidate_success=True,
        incumbent_cost=10.0,
        candidate_cost=1.0,
    )


def test_recurrent_llm_reasoning_can_retire_to_rule_after_exact_replay() -> None:
    verdict = ReasoningRetirementCourt(minimum_trials=3).evaluate(
        incumbent_rung=IntelligenceRung.GENERAL_LLM,
        candidate_rung=IntelligenceRung.RULE,
        trials=(
            _retirement("case-1"),
            _retirement("case-2"),
            _retirement("case-3"),
        ),
    )

    assert verdict.decision is RetirementDecision.RETIRE_INCUMBENT
    assert verdict.exact_match_count == 3
    assert verdict.candidate_cost < verdict.incumbent_cost


def test_changed_output_keeps_incumbent() -> None:
    changed = RetirementTrial(
        input_id="case-3",
        incumbent_output_digest="sha256:teacher",
        candidate_output_digest="sha256:changed",
        incumbent_success=True,
        candidate_success=True,
    )
    verdict = ReasoningRetirementCourt(minimum_trials=3).evaluate(
        incumbent_rung=IntelligenceRung.GENERAL_LLM,
        candidate_rung=IntelligenceRung.PLAN,
        trials=(
            _retirement("case-1"),
            _retirement("case-2"),
            changed,
        ),
    )

    assert verdict.decision is RetirementDecision.KEEP_INCUMBENT
    assert verdict.reasons == ("OUTPUT_SEMANTICS_CHANGED",)


def test_higher_or_equal_intelligence_candidate_is_refused() -> None:
    verdict = ReasoningRetirementCourt(minimum_trials=1).evaluate(
        incumbent_rung=IntelligenceRung.PLAN,
        candidate_rung=IntelligenceRung.GENERAL_LLM,
        trials=(_retirement("case-1"),),
    )

    assert verdict.decision is RetirementDecision.REFUSE
    assert "CANDIDATE_NOT_LOWER_INTELLIGENCE" in verdict.reasons
