from __future__ import annotations

import hashlib

import pytest

from autofde_lab.sa2a.autonomics.belief import BeliefState, EpistemicValue
from autofde_lab.sa2a.autonomics.crown import VerifiedRepair, run_two_episode_crown
from autofde_lab.sa2a.autonomics.external_crown import (
    ExternalAutonomicsManifest,
    ExternalCrownEvidence,
)
from autofde_lab.sa2a.autonomics.falsifier import ActiveFalsifier, Invariant
from autofde_lab.sa2a.autonomics.feedback import FeedbackAdmission, FeedbackFinding, FeedbackRule
from autofde_lab.sa2a.autonomics.predictor import (
    MajorityBaseline,
    PredictionStanding,
    split_subjects,
)
from autofde_lab.sa2a.autonomics.redesign import (
    CanaryEnvelope,
    CanaryEvidence,
    RedesignCandidate,
)
from autofde_lab.sa2a.autonomics.repair import RepairCandidate, RepairSelector
from autofde_lab.sa2a.autonomics.telemetry import (
    Measurement,
    SemanticCorrelation,
    SemanticTelemetryArtifact,
)


def sha(seed: str) -> str:
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


def test_gall_008_semantic_telemetry_binds_layers_and_conserves_additive_measure() -> None:
    correlation = SemanticCorrelation(
        semantic_subject=sha("subject"),
        capability_id="Example.Resource.repair",
        command_id="cmd-1",
        receipt_id="rcpt-1",
        runtime_subject=sha("runtime"),
        role_id="repairer",
    )
    artifact = SemanticTelemetryArtifact.admit(
        [
            Measurement("cpu", "reductions", 40, "beam-profiler", correlation),
            Measurement("cpu", "reductions", 60, "otel", correlation),
        ],
        source_versions={"beam-profiler": "1", "otel": "1.44"},
    )
    conservation = artifact.conservation(
        dimension="cpu", unit="reductions", expected_total=100
    )
    assert conservation["attributed"] == 100
    assert conservation["residual"] == 0
    assert artifact.digest.startswith("sha256:")

    with pytest.raises(ValueError, match="secret"):
        SemanticTelemetryArtifact.admit(
            [
                Measurement(
                    "cpu",
                    "reductions",
                    1,
                    "profiler",
                    correlation,
                    metadata={"authorization": "Bearer secret"},
                )
            ],
            source_versions={"profiler": "1"},
        )



def test_gall_009_feedback_requires_explicit_rule_and_never_manufactures_authority() -> None:
    subject = sha("subject")
    source = sha("telemetry-receipt")
    finding = FeedbackFinding(
        semantic_subject_digest=subject,
        source_receipt_digest=source,
        finding_type="health-observation",
        evidence_class="validated_telemetry",
        facts={"service_healthy": False, "database_reachable": None},
    )
    rule = FeedbackRule(
        rule_id="health-feedback-v1",
        finding_type="health-observation",
        evidence_class="validated_telemetry",
        allowed_facts=("service_healthy", "database_reachable"),
    )
    admitted = FeedbackAdmission.admit(
        finding, rule, expected_subject_digest=subject
    )
    assert admitted.admitted is True
    assert admitted.normative is False
    assert admitted.authorizes_actuation is False
    assert admitted.receipt_digest.startswith("sha256:")

    belief = BeliefState(
        facts={"service_healthy": EpistemicValue.UNKNOWN},
        observation_projection="ops:v1",
        provenance_digest=source,
    )
    updated = admitted.apply(belief)
    assert updated.facts["service_healthy"] is EpistemicValue.KNOWN_FALSE
    assert updated.facts["database_reachable"] is EpistemicValue.UNKNOWN
    assert updated.provenance_digest == admitted.receipt_digest

    with pytest.raises(ValueError, match="unadmitted facts"):
        FeedbackAdmission.admit(
            FeedbackFinding(
                semantic_subject_digest=subject,
                source_receipt_digest=source,
                finding_type="health-observation",
                evidence_class="validated_telemetry",
                facts={"repair_authorized": True},
            ),
            rule,
            expected_subject_digest=subject,
        )

    with pytest.raises(ValueError, match="reserved"):
        FeedbackFinding(
            semantic_subject_digest=subject,
            source_receipt_digest=source,
            finding_type="health-observation",
            evidence_class="validated_telemetry",
            facts={"standing": True},
        ).validate()


def test_gall_010_unknown_is_not_coerced_and_yields_information_action() -> None:
    belief = BeliefState(
        facts={
            "service_healthy": EpistemicValue.KNOWN_FALSE,
            "database_reachable": EpistemicValue.UNKNOWN,
        },
        observation_projection="ops:v1",
        provenance_digest=sha("evidence"),
    )
    ready, unknown = belief.require(
        {"service_healthy": False, "database_reachable": True}
    )
    assert ready is False
    assert unknown == ("database_reachable",)
    assert belief.to_fond_atoms() == (
        "unknown(database_reachable)",
        "known_false(service_healthy)",
    )
    assert belief.information_actions(
        {"database_reachable": True}
    )[0].action_id == "observe:database_reachable"

    observed = belief.observe("database_reachable", True)
    assert observed.require(
        {"service_healthy": False, "database_reachable": True}
    ) == (True, ())


def test_gall_011_active_falsifier_finds_and_minimizes_counterexample() -> None:
    invariant = Invariant[int](
        "never-two-consecutive-do",
        lambda trace: not any(left == right == 1 for left, right in zip(trace, trace[1:])),
    )
    result = ActiveFalsifier[int](budget=10).search(
        invariant,
        [(0, 1), (0, 1, 1, 0), (1, 1, 1)],
    )
    assert result.found is True
    assert result.counterexample == (1, 1)
    assert result.counterexample_digest is not None

    bounded = ActiveFalsifier[int](budget=1).search(invariant, [(0, 1), (1, 1)])
    assert bounded.found is False
    assert bounded.standing == "NO_COUNTEREXAMPLE_WITHIN_BUDGET"


def test_gall_012_prediction_remains_candidate_and_split_has_no_subject_leakage() -> None:
    train, validation, test = split_subjects(["a", "b", "c", "d", "e"])
    assert not (set(train) & set(validation))
    assert not (set(train) & set(test))
    assert not (set(validation) & set(test))

    model = MajorityBaseline().fit(["repair", "repair", "observe"])
    candidate = model.predict("held-out")
    assert candidate.predicted_label == "repair"
    assert candidate.standing is PredictionStanding.CANDIDATE
    assert candidate.model_digest.startswith("sha256:")


def test_gall_013_repair_selector_preserves_unknown_and_falsifier_boundaries() -> None:
    belief = BeliefState(
        facts={"fault_confirmed": EpistemicValue.KNOWN_TRUE},
        observation_projection="ops:v1",
        provenance_digest=sha("obs"),
    )
    safe = RepairCandidate(
        candidate_id="safe",
        capability_id="Repair.safe",
        requirements={"fault_confirmed": True},
        expected_postcondition={"healthy": True},
        cost=1.0,
        risk=0.1,
        predictor_score=0.5,
    )
    unsafe = RepairCandidate(
        candidate_id="unsafe",
        capability_id="Repair.unsafe",
        requirements={"fault_confirmed": True},
        expected_postcondition={"healthy": True},
        cost=0.5,
        risk=0.9,
        predictor_score=0.99,
    )
    selector = RepairSelector(risk_budget=0.5, cost_budget=2.0)
    lawful = selector.preflight(
        belief,
        [unsafe, safe],
        falsifiers=[lambda candidate: candidate.capability_id != "Repair.unsafe"],
    )
    assert lawful == (safe,)
    request = selector.select(
        belief,
        [unsafe, safe],
        semantic_subject=sha("fault"),
        falsifiers=[lambda candidate: candidate.capability_id != "Repair.unsafe"],
    )
    assert request.candidate_id == "safe"
    assert request.authority_required is True
    assert request.idempotency_key.startswith("sha256:")


def test_gall_014_verified_repair_compiles_known_path_without_reusing_authority() -> None:
    belief = BeliefState(
        facts={"fault_confirmed": EpistemicValue.KNOWN_TRUE},
        observation_projection="ops:v1",
        provenance_digest=sha("obs"),
    )
    candidate = RepairCandidate(
        candidate_id="repair",
        capability_id="Repair.apply",
        requirements={"fault_confirmed": True},
        expected_postcondition={"healthy": True},
        cost=1.0,
        risk=0.1,
    )
    request = RepairSelector(risk_budget=0.5, cost_budget=2.0).select(
        belief, [candidate], semantic_subject=sha("fault")
    )
    verified = VerifiedRepair(
        semantic_disturbance_key="fault-class:1",
        intervention=request,
        independent_postcondition_digest=sha("post"),
        restored=True,
        consequence_receipt_digest=sha("consequence"),
    )
    crown = run_two_episode_crown(verified)
    assert crown.episode_2_frontier_calls == 0
    assert crown.episode_2_planner_calls == 0
    assert crown.episode_2_experience_hits == 1
    assert crown.episode_2_reflex_executions == 1
    assert crown.fresh_authority_required is True

    with pytest.raises(ValueError, match="cannot compile"):
        run_two_episode_crown(
            VerifiedRepair(
                semantic_disturbance_key="fault-class:1",
                intervention=request,
                independent_postcondition_digest=sha("post"),
                restored=False,
                consequence_receipt_digest=sha("consequence"),
            )
        )


def test_gall_031_prediction_is_not_promotion_and_canary_is_bounded() -> None:
    candidate = RedesignCandidate(
        candidate_id="redesign-a",
        powl_digest=sha("powl"),
        predicted_improvement=0.2,
        formal_verification_digest=sha("formal"),
        falsifiers_passed=("ordering", "rollback"),
    )
    envelope = CanaryEnvelope.build(
        candidate,
        baseline_digest=sha("baseline"),
        scope="5-percent-cases",
        event_budget=100,
        rollback_condition="cycle_time > baseline",
    )
    assert envelope.authority_required is True
    assert envelope.event_budget == 100

    evidence = CanaryEvidence(
        envelope_digest=envelope.envelope_digest,
        independent_observer_digest=sha("observer"),
        baseline_metrics={"throughput": 10.0},
        canary_metrics={"throughput": 12.0},
        postcondition_verified=True,
    )
    promotion = evidence.promotion_candidate(metric="throughput")
    assert promotion["standing"] == "CANDIDATE"

    with pytest.raises(RuntimeError, match="not-improved"):
        CanaryEvidence(
            envelope_digest=envelope.envelope_digest,
            independent_observer_digest=sha("observer"),
            baseline_metrics={"throughput": 10.0},
            canary_metrics={"throughput": 9.0},
            postcondition_verified=True,
        ).promotion_candidate(metric="throughput")


def test_gall_032_requires_every_predecessor_and_fresh_known_execution() -> None:
    receipts = {
        f"GALL-{index:03d}": sha(f"receipt-{index}") for index in range(1, 32)
    }
    manifest = ExternalAutonomicsManifest(
        receipts=receipts,
        disturbance_class="service-latency-regression",
        process_subject_digest=sha("process"),
        authority_policy_digest=sha("authority-policy"),
        runtime_identity="autofde-lab:v26.9.18",
    )
    manifest_digest = manifest.digest

    evidence = ExternalCrownEvidence(
        manifest_digest=manifest_digest,
        episode_1_disturbance_observed=True,
        episode_1_independent_postcondition=True,
        machine_experience_digest=sha("experience"),
        episode_2_fresh_process=True,
        episode_2_frontier_calls=0,
        episode_2_llm_allocations=0,
        episode_2_planner_calls=0,
        episode_2_reflex_executions=1,
        episode_2_fresh_authority_receipt=sha("fresh-authority"),
        episode_2_independent_postcondition=True,
    )
    handoff = evidence.qualify_for_affidavit()
    assert handoff["standing"] == "EVIDENCE_READY_FOR_AFFIDAVIT"
    assert handoff["authority"] == "none"

    missing = dict(receipts)
    missing.pop("GALL-029")
    with pytest.raises(ValueError, match="missing predecessor"):
        ExternalAutonomicsManifest(
            receipts=missing,
            disturbance_class="x",
            process_subject_digest=sha("p"),
            authority_policy_digest=sha("a"),
            runtime_identity="r",
        ).validate()

    with pytest.raises(RuntimeError, match="repurchased"):
        ExternalCrownEvidence(
            manifest_digest=manifest_digest,
            episode_1_disturbance_observed=True,
            episode_1_independent_postcondition=True,
            machine_experience_digest=sha("experience"),
            episode_2_fresh_process=True,
            episode_2_frontier_calls=1,
            episode_2_llm_allocations=0,
            episode_2_planner_calls=0,
            episode_2_reflex_executions=1,
            episode_2_fresh_authority_receipt=sha("fresh"),
            episode_2_independent_postcondition=True,
        ).qualify_for_affidavit()
