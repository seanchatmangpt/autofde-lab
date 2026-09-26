from autofde_lab.evolution import (
    IntelligenceRung,
    PairedTrial,
    ReasoningRetirementCourt,
    RetirementTrial,
    SequentialDecision,
    StatisticalPairedPromotionCourt,
    StatisticalPromotionPolicy,
    compile_retirement_route,
)


def _trial(task: str, delta: float) -> PairedTrial:
    champion = 0.50
    return PairedTrial(
        task_id=task,
        seed=11,
        budget_id="steps:64",
        champion_score=champion,
        candidate_score=champion + delta,
        champion_evidence_digest=f"sha256:champion-{task}",
        candidate_evidence_digest=f"sha256:candidate-{task}",
    )


def test_statistical_court_continues_before_minimum_evidence() -> None:
    court = StatisticalPairedPromotionCourt(
        StatisticalPromotionPolicy(minimum_trials=3, maximum_trials=5)
    )

    verdict = court.evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(_trial("a", 0.10), _trial("b", 0.10)),
    )

    assert verdict.decision is SequentialDecision.CONTINUE
    assert verdict.reasons == ("MORE_PAIRED_EVIDENCE_REQUIRED",)
    assert verdict.remaining_trials == 3


def test_statistical_court_promotes_only_when_lower_bound_is_positive() -> None:
    court = StatisticalPairedPromotionCourt(
        StatisticalPromotionPolicy(
            minimum_trials=4,
            maximum_trials=8,
            minimum_mean_delta=0.01,
            minimum_lower_bound=0.0,
        )
    )

    verdict = court.evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(
            _trial("a", 0.10),
            _trial("b", 0.11),
            _trial("c", 0.09),
            _trial("d", 0.10),
        ),
    )

    assert verdict.decision is SequentialDecision.PROMOTE
    assert verdict.statistics.mean_delta > 0.09
    assert verdict.statistics.lower_confidence_bound > 0
    assert verdict.statistics.wins == 4
    assert verdict.statistics.losses == 0


def test_statistical_court_refuses_duplicate_cohort_identity() -> None:
    trial = _trial("same", 0.10)

    verdict = StatisticalPairedPromotionCourt().evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(trial, trial, _trial("other", 0.10)),
    )

    assert verdict.decision is SequentialDecision.REFUSE
    assert "DUPLICATE_COHORT_IDENTITY" in verdict.reasons


def test_statistical_digest_is_order_independent() -> None:
    court = StatisticalPairedPromotionCourt(
        StatisticalPromotionPolicy(minimum_trials=3, maximum_trials=6)
    )
    trials = (_trial("a", 0.05), _trial("b", 0.05), _trial("c", 0.05))

    forward = court.evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=trials,
    )
    reverse = court.evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=tuple(reversed(trials)),
    )

    assert forward.evidence_digest == reverse.evidence_digest


def test_statistical_court_holds_on_single_regression() -> None:
    verdict = StatisticalPairedPromotionCourt(
        StatisticalPromotionPolicy(
            minimum_trials=3,
            maximum_trials=6,
            max_single_trial_regression=0.0,
        )
    ).evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(
            _trial("a", 0.50),
            _trial("b", 0.50),
            _trial("c", -0.01),
        ),
    )

    assert verdict.decision is SequentialDecision.HOLD
    assert verdict.reasons == ("REGRESSION_BOUND_EXCEEDED",)


def _retirement(input_id: str) -> RetirementTrial:
    return RetirementTrial(
        input_id=input_id,
        incumbent_output_digest=f"sha256:{input_id}",
        candidate_output_digest=f"sha256:{input_id}",
        incumbent_success=True,
        candidate_success=True,
        incumbent_cost=5.0,
        candidate_cost=1.0,
    )


def test_retirement_route_compiles_only_from_replayable_admitted_verdict() -> None:
    trials = (_retirement("a"), _retirement("b"), _retirement("c"))
    verdict = ReasoningRetirementCourt(minimum_trials=3).evaluate(
        incumbent_rung=IntelligenceRung.GENERAL_LLM,
        candidate_rung=IntelligenceRung.RULE,
        trials=trials,
    )

    route = compile_retirement_route(
        signature_id="ticket-triage",
        candidate_artifact_digest="sha256:compiled-rule",
        verdict=verdict,
        trials=tuple(reversed(trials)),
    )

    assert route.candidate_rung is IntelligenceRung.RULE
    assert route.incumbent_rung is IntelligenceRung.GENERAL_LLM
    assert route.trial_count == 3
    assert route.authority == "none"
    assert route.route_digest.startswith("sha256:")


def test_retirement_route_rejects_changed_replay_cohort() -> None:
    trials = (_retirement("a"), _retirement("b"), _retirement("c"))
    verdict = ReasoningRetirementCourt(minimum_trials=3).evaluate(
        incumbent_rung=IntelligenceRung.GENERAL_LLM,
        candidate_rung=IntelligenceRung.RULE,
        trials=trials,
    )

    changed = RetirementTrial(
        input_id="c",
        incumbent_output_digest="sha256:c",
        candidate_output_digest="sha256:changed",
        incumbent_success=True,
        candidate_success=True,
    )

    try:
        compile_retirement_route(
            signature_id="ticket-triage",
            candidate_artifact_digest="sha256:compiled-rule",
            verdict=verdict,
            trials=(trials[0], trials[1], changed),
        )
    except ValueError as error:
        assert str(error) in {
            "RETIREMENT_REPLAY_DID_NOT_ADMIT",
            "RETIREMENT_VERDICT_DIGEST_MISMATCH",
        }
    else:
        raise AssertionError("changed replay cohort unexpectedly compiled")
