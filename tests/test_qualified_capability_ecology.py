from autofde_lab.evolution import (
    IntelligenceRung,
    PairedPromotionCourt,
    PairedPromotionPolicy,
    PairedTrial,
    ReasoningRetirementCourt,
    RetirementTrial,
    compile_retirement_route,
)
from autofde_lab.evolution.capability_ecology import (
    GitCapabilitySubject,
    ResidualHumanWork,
    freeze_promoted_candidate,
    qualify_retirement,
    qualify_substitution,
)


def _digest(char: str) -> str:
    return "sha256:" + char * 64


def _subject(capability: str, artifact: str, commit: str) -> GitCapabilitySubject:
    return GitCapabilitySubject(
        repository="seanchatmangpt/example",
        commit=commit,
        capability_id=capability,
        artifact_digest=_digest(artifact),
    )


def _promotion():
    return PairedPromotionCourt(
        PairedPromotionPolicy(minimum_trials=2, minimum_total_delta=0.01)
    ).evaluate(
        champion_id="cap:v1",
        candidate_id="cap:v2",
        trials=(
            PairedTrial(
                task_id="a",
                seed=1,
                budget_id="steps:32",
                champion_score=0.5,
                candidate_score=0.7,
                champion_evidence_digest=_digest("1"),
                candidate_evidence_digest=_digest("2"),
            ),
            PairedTrial(
                task_id="b",
                seed=1,
                budget_id="steps:32",
                champion_score=0.6,
                candidate_score=0.8,
                champion_evidence_digest=_digest("3"),
                candidate_evidence_digest=_digest("4"),
            ),
        ),
    )


def _route(candidate_artifact_digest: str):
    trials = tuple(
        RetirementTrial(
            input_id=f"case-{index}",
            incumbent_output_digest=_digest("a"),
            candidate_output_digest=_digest("a"),
            incumbent_success=True,
            candidate_success=True,
            incumbent_cost=10.0,
            candidate_cost=1.0,
        )
        for index in range(3)
    )
    verdict = ReasoningRetirementCourt(minimum_trials=3).evaluate(
        incumbent_rung=IntelligenceRung.GENERAL_LLM,
        candidate_rung=IntelligenceRung.RULE,
        trials=trials,
    )
    return compile_retirement_route(
        signature_id="sig:example",
        candidate_artifact_digest=candidate_artifact_digest,
        verdict=verdict,
        trials=trials,
    )


def test_full_qualified_capability_lifecycle_is_authority_inert() -> None:
    original = _subject(
        "cap:v1",
        "b",
        "0123456789abcdef0123456789abcdef01234567",
    )
    candidate = _subject(
        "cap:v2",
        "c",
        "89abcdef0123456789abcdef0123456789abcdef",
    )
    frozen = freeze_promoted_candidate(
        subject=candidate,
        promotion=_promotion(),
        replay_digest=_digest("5"),
        independent_verification_digest=_digest("6"),
    )
    substitution = qualify_substitution(
        original=original,
        replacement=frozen,
        route=_route(candidate.artifact_digest),
        predecessor_authority_depth=2,
        successor_authority_depth=1,
    )
    retirement = qualify_retirement(
        substitution=substitution,
        human_work=ResidualHumanWork(
            baseline_work=20.0,
            exception_work=2.0,
            verification_work=1.0,
            correction_work=1.0,
            maintenance_work=2.0,
        ),
    )

    assert frozen.authority == "none"
    assert not frozen.grants_do_authority
    assert substitution.consequence_preserved
    assert substitution.replay_verified
    assert substitution.authority == "none"
    assert retirement.net_human_work_delta == -14.0
    assert retirement.authority == "none"
    assert retirement.receipt_digest.startswith("sha256:")


def test_mutable_subject_refuses_before_qualification() -> None:
    try:
        _subject("cap:v2", "c", "main")
    except ValueError as error:
        assert str(error) == "REFUSED:IMMUTABLE_GIT_COMMIT_REQUIRED"
    else:
        raise AssertionError("mutable subject unexpectedly admitted")


def test_promotion_cannot_be_laundered_to_different_candidate() -> None:
    other = _subject(
        "cap:other",
        "c",
        "89abcdef0123456789abcdef0123456789abcdef",
    )
    try:
        freeze_promoted_candidate(
            subject=other,
            promotion=_promotion(),
            replay_digest=_digest("5"),
            independent_verification_digest=_digest("6"),
        )
    except ValueError as error:
        assert str(error) == "REFUSED:PROMOTION_EXACT_SUBJECT_MISMATCH"
    else:
        raise AssertionError("candidate mismatch unexpectedly admitted")


def test_authority_increase_refuses_substitution() -> None:
    original = _subject(
        "cap:v1",
        "b",
        "0123456789abcdef0123456789abcdef01234567",
    )
    candidate = _subject(
        "cap:v2",
        "c",
        "89abcdef0123456789abcdef0123456789abcdef",
    )
    frozen = freeze_promoted_candidate(
        subject=candidate,
        promotion=_promotion(),
        replay_digest=_digest("5"),
        independent_verification_digest=_digest("6"),
    )
    try:
        qualify_substitution(
            original=original,
            replacement=frozen,
            route=_route(candidate.artifact_digest),
            predecessor_authority_depth=1,
            successor_authority_depth=2,
        )
    except ValueError as error:
        assert str(error) == "REFUSED:AUTHORITY_INCREASE"
    else:
        raise AssertionError("authority increase unexpectedly admitted")


def test_residual_human_work_blocks_false_automation_win() -> None:
    original = _subject(
        "cap:v1",
        "b",
        "0123456789abcdef0123456789abcdef01234567",
    )
    candidate = _subject(
        "cap:v2",
        "c",
        "89abcdef0123456789abcdef0123456789abcdef",
    )
    frozen = freeze_promoted_candidate(
        subject=candidate,
        promotion=_promotion(),
        replay_digest=_digest("5"),
        independent_verification_digest=_digest("6"),
    )
    substitution = qualify_substitution(
        original=original,
        replacement=frozen,
        route=_route(candidate.artifact_digest),
        predecessor_authority_depth=1,
        successor_authority_depth=1,
    )
    work = ResidualHumanWork(
        baseline_work=5.0,
        exception_work=2.0,
        verification_work=2.0,
        correction_work=1.0,
        maintenance_work=1.0,
    )
    assert work.net_human_work_delta == 1.0

    try:
        qualify_retirement(substitution=substitution, human_work=work)
    except ValueError as error:
        assert str(error) == "REFUSED:RESIDUAL_HUMAN_WORK_NOT_REDUCED"
    else:
        raise AssertionError("false automation win unexpectedly retired incumbent")
