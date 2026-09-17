//! Chicago-TDD JTBD coverage for the admitted CMCA authority path.
//!
//! These scenarios exercise real production collaborators across:
//!
//! `MeasurementArtifact -> evaluate_calibration -> CertificateReceipt
//!  -> AdaptiveUpdate admission -> allocate`
//!
//! No mock, stub, or spy is used. Assertions are made against public outcomes
//! and the allocator's persistent mutable state.

#![cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5"
)))]

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertificateReceipt, CertifiedLearning,
    EnvelopeReceipt, OutcomeReceipt, StabilityRefusal,
};
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;
use bcinr_cmca::observatory::{
    evaluate_calibration, MeasurementArtifact, ModeDelta, ObservatoryFlag, SupportStanding,
};

const CONTROL_MODE_DIGEST: u64 = 42;
const SAFE_DWELL_ROUNDS: u32 = 500;

fn measurement(
    lower_bound: NonNegativeFixed,
    drift: NonNegativeFixed,
    proposal: ModeDelta,
) -> MeasurementArtifact {
    MeasurementArtifact {
        point_estimate: NonNegativeFixed::from_bits(131_072),
        lower_bound,
        upper_bound: NonNegativeFixed::from_bits(131_072),
        support_standing: SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift,
        gram_lower_bound: NonNegativeFixed::from_bits(131_072),
        graph_digest: 0,
        control_mode_digest: CONTROL_MODE_DIGEST,
        proposal,
    }
}

fn evaluate(artifact: &MeasurementArtifact) -> Result<CertificateReceipt, ObservatoryFlag> {
    evaluate_calibration(
        artifact,
        NonNegativeFixed::from_bits(65_536),
        NonNegativeFixed::from_bits(65_536),
        NonNegativeFixed::from_bits(65_536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32_768),
    )
}

fn material_certificate() -> CertificateReceipt {
    evaluate(&measurement(
        NonNegativeFixed::from_bits(131_072),
        NonNegativeFixed::ZERO,
        ModeDelta::ProposeDelta,
    ))
    .expect("material, stable telemetry must issue a control-mode receipt")
}

fn admit_update(
    state_digest: u64,
    certificate: CertificateReceipt,
    envelope_digest: u64,
    outcome_digest: u64,
) -> Option<AdaptiveUpdate<CertifiedLearning>> {
    AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(state_digest),
        certificate,
        EnvelopeReceipt::admit_envelope(envelope_digest),
        OutcomeReceipt::admit_outcome(outcome_digest),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::from_bits(65),
        CertifiedLearning::admit_learning(),
    )
}

struct AllocatorHarness {
    weights: [[NonNegativeFixed; 2 * Q]; N],
    payoffs: [[NonNegativeFixed; 2 * Q]; N],
    last_switch_t: u32,
    prev_mode: u32,
    parent: [i32; N],
    mu: [NonNegativeFixed; N],
    costs: [NonNegativeFixed; N],
}

impl AllocatorHarness {
    fn new() -> Self {
        Self {
            weights: [[NonNegativeFixed::ONE; 2 * Q]; N],
            payoffs: [[NonNegativeFixed::ZERO; 2 * Q]; N],
            last_switch_t: 0,
            prev_mode: 0,
            parent: [-1; N],
            mu: [NonNegativeFixed::ZERO; N],
            costs: [NonNegativeFixed::ZERO; N],
        }
    }

    fn allocate(
        &mut self,
        digest: [u8; 32],
        proof: Option<&AdaptiveUpdate<CertifiedLearning>>,
        dwell_rounds: u32,
    ) -> Result<[NonNegativeFixed; N], StabilityRefusal> {
        allocate(
            &OBJECT_REGISTRY,
            &LENS_REGISTRY,
            &LAMBDA,
            ETA,
            &self.parent,
            &mut self.weights,
            &self.payoffs,
            NonNegativeFixed::ZERO,
            NonNegativeFixed::ZERO,
            &self.mu,
            &self.costs,
            0,
            &mut self.last_switch_t,
            &mut self.prev_mode,
            dwell_rounds,
            digest,
            proof,
        )
    }
}

chicago_tdd_tools::test!(jtbd_material_telemetry_authorizes_adaptive_allocation, {
    let certificate = material_certificate();
    assert_eq!(
        certificate,
        CertificateReceipt::admit_certificate(CONTROL_MODE_DIGEST),
        "the Observatory receipt must remain bound to the measured control mode"
    );

    let proof = admit_update(
        CONTROL_MODE_DIGEST,
        certificate,
        CONTROL_MODE_DIGEST,
        CONTROL_MODE_DIGEST,
    )
    .expect("matching receipts within the numeric envelope must authorize adaptation");

    let mut harness = AllocatorHarness::new();
    let allocation = harness
        .allocate(CERTIFICATE_DIGEST, Some(&proof), SAFE_DWELL_ROUNDS)
        .expect("an Observatory-authorized adaptive allocation must execute");

    assert!(
        allocation.iter().any(|value| value.val > 0),
        "the completed job must produce a non-empty allocation"
    );
    assert!(
        allocation[0].val > allocation[1].val,
        "the generated cache-choice policy must prioritize artifact A over artifact B"
    );
});

chicago_tdd_tools::test!(
    jtbd_drift_refusal_routes_to_selection_only_without_state_drift,
    {
        let result = evaluate(&measurement(
            NonNegativeFixed::from_bits(131_072),
            NonNegativeFixed::from_bits(131_072),
            ModeDelta::ProposeDelta,
        ));
        assert_eq!(result, Err(ObservatoryFlag::Drifting));

        let mut harness = AllocatorHarness::new();
        harness.last_switch_t = 123;
        harness.prev_mode = 4;
        let weights_before = harness.weights;
        let last_switch_before = harness.last_switch_t;
        let mode_before = harness.prev_mode;
        let wrong_digest = [0u8; 32];
        assert_ne!(wrong_digest, CERTIFICATE_DIGEST);

        let allocation = harness
            .allocate(wrong_digest, None, SAFE_DWELL_ROUNDS)
            .expect("absence of adaptive authority must degrade to certified selection");

        assert!(allocation.iter().any(|value| value.val > 0));
        assert_eq!(harness.weights, weights_before);
        assert_eq!(harness.last_switch_t, last_switch_before);
        assert_eq!(harness.prev_mode, mode_before);
    }
);

chicago_tdd_tools::test!(
    jtbd_observatory_receipt_cannot_authorize_mismatched_job_receipts,
    {
        let certificate = material_certificate();

        let admitted = admit_update(
            CONTROL_MODE_DIGEST,
            certificate,
            CONTROL_MODE_DIGEST,
            CONTROL_MODE_DIGEST,
        );
        assert!(admitted.is_some());

        assert!(
            admit_update(
                CONTROL_MODE_DIGEST + 1,
                certificate,
                CONTROL_MODE_DIGEST,
                CONTROL_MODE_DIGEST,
            )
            .is_none(),
            "a certificate from one control state cannot authorize another state"
        );
        assert!(
            admit_update(
                CONTROL_MODE_DIGEST,
                certificate,
                CONTROL_MODE_DIGEST + 1,
                CONTROL_MODE_DIGEST,
            )
            .is_none(),
            "a certificate cannot cross an envelope boundary"
        );
        assert!(
            admit_update(
                CONTROL_MODE_DIGEST,
                certificate,
                CONTROL_MODE_DIGEST,
                CONTROL_MODE_DIGEST + 1,
            )
            .is_none(),
            "a certificate cannot authorize an unrelated outcome"
        );
    }
);

chicago_tdd_tools::test!(
    jtbd_invalid_allocator_certificate_is_typed_and_non_mutating,
    {
        let certificate = material_certificate();
        let proof = admit_update(
            CONTROL_MODE_DIGEST,
            certificate,
            CONTROL_MODE_DIGEST,
            CONTROL_MODE_DIGEST,
        )
        .expect("matching Observatory and job receipts must authorize the attempt");

        let mut harness = AllocatorHarness::new();
        harness.last_switch_t = 123;
        harness.prev_mode = 4;
        let weights_before = harness.weights;
        let last_switch_before = harness.last_switch_t;
        let mode_before = harness.prev_mode;
        let wrong_digest = [0u8; 32];
        assert_ne!(wrong_digest, CERTIFICATE_DIGEST);

        let result = harness.allocate(wrong_digest, Some(&proof), SAFE_DWELL_ROUNDS);

        assert_eq!(result, Err(StabilityRefusal::CertificateDigestMismatch));
        assert_eq!(harness.weights, weights_before);
        assert_eq!(harness.last_switch_t, last_switch_before);
        assert_eq!(harness.prev_mode, mode_before);
    }
);

chicago_tdd_tools::test!(jtbd_insufficient_dwell_is_typed_and_non_mutating, {
    let certificate = material_certificate();
    let proof = admit_update(
        CONTROL_MODE_DIGEST,
        certificate,
        CONTROL_MODE_DIGEST,
        CONTROL_MODE_DIGEST,
    )
    .expect("matching Observatory and job receipts must authorize the attempt");

    let mut harness = AllocatorHarness::new();
    harness.last_switch_t = 123;
    harness.prev_mode = 4;
    let weights_before = harness.weights;
    let last_switch_before = harness.last_switch_t;
    let mode_before = harness.prev_mode;

    let result = harness.allocate(CERTIFICATE_DIGEST, Some(&proof), 10);

    assert_eq!(result, Err(StabilityRefusal::ModeDwellTimeViolated));
    assert_eq!(harness.weights, weights_before);
    assert_eq!(harness.last_switch_t, last_switch_before);
    assert_eq!(harness.prev_mode, mode_before);
});
