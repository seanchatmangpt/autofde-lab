from autofde_lab.ptd import PhaseTrial, PTDCriteria, evaluate_trial, summarize_trials


def trial(**overrides: object) -> PhaseTrial:
    values: dict[str, object] = {
        "trial_id": "phase-1-2",
        "from_phase": "S1",
        "to_phase": "S2",
        "semantic_admitted": True,
        "prior_phase_attack_performance": 0.2,
        "fresh_phase_attack_performance": 0.8,
        "attacker_realign_cost": 50.0,
        "defender_reconstruction_cost": 5.0,
        "attacker_realignment_time": 12.0,
        "phase_duration": 10.0,
        "realization_distance": 100.0,
        "common_mode_failure": False,
        "persistent_authority_compromised": False,
    }
    values.update(overrides)
    return PhaseTrial(**values)


CRITERIA = PTDCriteria(
    max_knowledge_retention=0.5,
    min_regeneration_advantage=2.0,
    require_strong_phase_regime=True,
)


def test_admitted_low_transfer_transition_passes() -> None:
    result = evaluate_trial(trial(), CRITERIA)
    assert result["passed"] is True
    assert result["falsifiers"] == []
    assert result["metrics"]["knowledge_retention"] == 0.25
    assert result["metrics"]["knowledge_depreciation"] == 0.75
    assert result["metrics"]["regeneration_advantage"] == 10.0


def test_cosmetic_change_falsifies_ptd_when_knowledge_transfers() -> None:
    result = evaluate_trial(
        trial(
            prior_phase_attack_performance=0.79,
            fresh_phase_attack_performance=0.8,
            realization_distance=10_000.0,
        ),
        CRITERIA,
    )
    assert result["passed"] is False
    assert "KNOWLEDGE_RETENTION_TOO_HIGH" in result["falsifiers"]


def test_common_mode_persistence_is_explicit_failure() -> None:
    result = evaluate_trial(trial(common_mode_failure=True), CRITERIA)
    assert "COMMON_MODE_FAILURE_PERSISTS" in result["falsifiers"]


def test_persistent_authority_compromise_is_explicit_failure() -> None:
    result = evaluate_trial(trial(persistent_authority_compromised=True), CRITERIA)
    assert "PERSISTENT_AUTHORITY_COMPROMISED" in result["falsifiers"]


def test_semantic_admission_is_required() -> None:
    result = evaluate_trial(trial(semantic_admitted=False), CRITERIA)
    assert "SEMANTIC_ADMISSION_FAILED" in result["falsifiers"]


def test_attacker_must_not_realign_inside_phase_when_required() -> None:
    result = evaluate_trial(
        trial(attacker_realignment_time=9.0, phase_duration=10.0),
        CRITERIA,
    )
    assert "ATTACKER_REALIGNS_WITHIN_PHASE" in result["falsifiers"]


def test_summary_keeps_failures_visible() -> None:
    report = summarize_trials(
        [
            trial(trial_id="good"),
            trial(
                trial_id="bad",
                prior_phase_attack_performance=0.8,
                fresh_phase_attack_performance=0.8,
            ),
        ],
        CRITERIA,
    )
    assert report["trial_count"] == 2
    assert report["passed_count"] == 1
    assert report["failed_count"] == 1
