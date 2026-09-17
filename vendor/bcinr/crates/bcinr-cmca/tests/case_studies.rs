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

fn get_proof() -> Option<AdaptiveUpdate<CertifiedLearning>> {
    AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        CertifiedLearning::admit_learning(),
    )
}
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

#[test]
fn test_case_study_1_cache_choice() {
    // Artifact_A has high recomputation cost (0.9), Artifact_B has low recomputation cost (0.1).
    // Access frequencies are both 0.5. Standings are 1.0.
    // Under Cache Choice head, Artifact_A should receive more resource than Artifact_B.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

    // We construct a simple tree where 0 and 1 are root leaf nodes
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .unwrap();

    // Verify that Artifact_A (index 0) gets more cache allocation than Artifact_B (index 1)
    // In our lambda matrix, index 0 is MeasureCache, which dominates lens 0 (2.0) and 1 (1.0).
    println!("result[0]: {:?}, result[1]: {:?}", result[0], result[1]);
    assert!(
        result[0].val > result[1].val,
        "Artifact_A should have higher cache allocation than Artifact_B"
    );
}

#[test]
fn test_case_study_2_single_object_multiple_decisions() {
    // Obj_Single (index 6) has high retrieval demand (0.9) and high business value (100).
    // Let's verify it gets a significant portion of resource allocation under weighted retrieval.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .unwrap();

    // Obj_Single (index 6) has high business value and retrieval demand, should have higher allocation than Obj_Obligation.
    for (i, r) in result.iter().enumerate() {
        println!("CS2 result[{}]: {:?}", i, r);
    }
    assert!(
        result[6].val > result[4].val,
        "Obj_Single should have higher allocation than Obj_Obligation"
    );
}

#[test]
fn test_case_study_3_downstream_consequence() {
    // Obj_Obligation (index 4) has business value 0, but depends on Obj_Activity which eventually
    // depends on Obj_Value (1000).
    // Consequence mass is 1000. Under search-weighted allocation, it should get a high allocation.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

    // Parent-child relationships for Case Study 3
    let mut parent = [-1; N];
    parent[2] = 4; // Obj_Activity depends on Obj_Obligation
    parent[3] = 2; // Obj_Deployment depends on Obj_Activity
    parent[5] = 3; // Obj_Outcome depends on Obj_Deployment
    parent[7] = 5; // Obj_Value depends on Obj_Outcome

    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let result = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .unwrap();

    // Obj_Value (index 7) is the only leaf in the chain, so it receives the allocated resource.
    assert!(result[7].val > 0, "Obj_Value should receive allocation");
}

/// Case Study 4: Generalization (see `docs/cmca-rdf/ARCHITECTURE.md`, "Case
/// Study 4: Generalization").
///
/// The claim under test: a *second* ontology configuration
/// (`crates/bcinr-cmca/ontology/generalization.ttl`, compiled to
/// `crates/bcinr-cmca/src/generated/generalization.rs`) with different
/// global coefficients (`eta = 0.3` vs. this file's `eta = 0.5`) and a
/// different problem shape (9 objects / 5 measures / 5 lenses vs. this
/// file's 8/4/4) compiles through the *same* generator and core allocator
/// types without any handwritten per-schema code.
///
/// `allocate()` itself is monomorphized against `case_studies`'s N=8/Q=4/K=4
/// (see `crates/bcinr-cmca/src/allocator.rs`'s `use
/// crate::generated::consequence_mass::case_studies::{N, Q, K, F, ...}`), so the
/// generalization registry cannot be fed through it directly — the
/// generalization claim is that the *schema and generator* produce a
/// structurally different, internally consistent registry, which we assert
/// against directly.
#[test]
fn test_case_study_4_generalization() {
    use bcinr_cmca::generated::consequence_mass::generalization::{
        ETA as GEN_ETA, LAMBDA as GEN_LAMBDA, LENS_REGISTRY as GEN_LENS_REGISTRY, N as GEN_N,
        OBJECT_REGISTRY as GEN_OBJECT_REGISTRY, Q as GEN_Q,
    };

    // The generated shape must genuinely differ from case_studies — a
    // schema that "generalizes" by re-emitting the same N/Q/K would prove
    // nothing about the generator handling new topologies.
    assert_eq!(
        GEN_N, 9,
        "generalization config must have a distinct object count from case_studies (N=8)"
    );
    assert_eq!(
        GEN_Q, 5,
        "generalization config must have a distinct lens count from case_studies (Q=4)"
    );
    assert_ne!(
        GEN_N, N,
        "generalization registry must not just alias case_studies's N"
    );
    assert_ne!(
        GEN_Q, Q,
        "generalization registry must not just alias case_studies's Q"
    );

    // The global coefficient must genuinely differ (0.3 vs. case_studies's
    // 0.5), proving the generator threads per-config coefficients through
    // rather than hardcoding one value across all compiled schemas.
    assert_eq!(
        GEN_ETA.val, 19661,
        "generalization eta must be 0.3 (19661/65536), distinct from case_studies eta=0.5"
    );
    assert_ne!(
        GEN_ETA.val, ETA.val,
        "generalization eta must differ from case_studies eta"
    );

    // The registry must be internally consistent: every object has the
    // expected factor-vector width (F=10, same across schemas), and every
    // lens id is unique and in range — real structural checks on the
    // generated data, not a placeholder.
    assert_eq!(GEN_OBJECT_REGISTRY.len(), GEN_N);
    for (i, obj) in GEN_OBJECT_REGISTRY.iter().enumerate() {
        assert_eq!(
            obj.id as usize, i,
            "object {} must have self-consistent id",
            i
        );
        assert_eq!(
            obj.factors.len(),
            10,
            "object {} must carry all 10 factors",
            i
        );
    }

    assert_eq!(GEN_LENS_REGISTRY.len(), GEN_Q);
    let mut seen_lens_ids = std::collections::HashSet::new();
    for lens in GEN_LENS_REGISTRY.iter() {
        assert!(
            seen_lens_ids.insert(lens.id),
            "lens id {} must be unique within the generalization registry",
            lens.id
        );
    }

    // LAMBDA must be a real K x Q table sized to the generalization
    // schema's own K=5/Q=5, not left at case_studies's 4x4 shape.
    assert_eq!(
        GEN_LAMBDA.len(),
        5,
        "generalization LAMBDA must have K=5 measure rows"
    );
    for row in GEN_LAMBDA.iter() {
        assert_eq!(
            row.len(),
            GEN_Q,
            "each LAMBDA row must have Q={} lens weights",
            GEN_Q
        );
    }
}

#[test]
fn test_stability_refusals_and_graceful_fallback() {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    // 1. Invalid certificate digest with degrade=false -> should return CertificateDigestMismatch
    let wrong_digest = [0u8; 32];
    let res = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        wrong_digest,
        get_proof().as_ref(),
    );
    assert_eq!(res, Err(StabilityRefusal::CertificateDigestMismatch));

    // 2. Invalid certificate digest with degrade=true -> should succeed but freeze learning
    // (CertifiedSelectionOnly). CMCA-103 confirmed this specific case is a
    // legitimate, deliberately documented contract: `digest_err` (unlike
    // `q_err`/`price_err`/`eta_err`) only gates the weight-update / mode-
    // switch code, which proof=None already disables independently -- see
    // `allocate_in`'s CMCA-103 comment and
    // tests/jtbd_certified_actuation_chicago.rs's
    // `jtbd_drift_refusal_routes_to_selection_only_without_state_drift`.
    let weights_before = weights;
    let res_degraded = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        wrong_digest,
        None,
    );
    assert!(res_degraded.is_ok());
    // Learning should be frozen, meaning weights are not modified/updated
    assert_eq!(weights, weights_before);

    // 3. Mode dwell rounds too fast with degrade=false -> should return ModeDwellTimeViolated
    let fast_dwell = 10u32;
    let res_dwell = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        fast_dwell,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    );
    assert_eq!(res_dwell, Err(StabilityRefusal::ModeDwellTimeViolated));

    // 4. Learning rate outside envelope with degrade=false -> should return LearningRateOutsideEnvelope
    let high_zeta = NonNegativeFixed::from_bits(2000); // Exceeds ZETA_W_MAX (819)
    let res_lr = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        high_zeta,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    );
    assert_eq!(res_lr, Err(StabilityRefusal::LearningRateOutsideEnvelope));
}

#[test]
fn test_typestate_bounds_checks() {
    // 1. Safe boundary: temperature = 5.0 (327680), distinguishability = 0.001 (65)
    let p_ok = AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::from_bits(327680),
        NonNegativeFixed::from_bits(65),
        CertifiedLearning::admit_learning(),
    );
    assert!(p_ok.is_some());

    // 2. Temp too high: temperature = 5.0 + eps (327681), distinguishability = 0.001 (65)
    let p_temp_high = AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::from_bits(327681),
        NonNegativeFixed::from_bits(65),
        CertifiedLearning::admit_learning(),
    );
    assert!(p_temp_high.is_none());

    // 3. Distinguishability too low: temperature = 5.0 (327680), distinguishability = 64
    let p_dist_low = AdaptiveUpdate::admit_adaptive_update(
        AdmittedControlState::admit_control_state(0),
        CertificateReceipt::admit_certificate(0),
        EnvelopeReceipt::admit_envelope(0),
        OutcomeReceipt::admit_outcome(0),
        NonNegativeFixed::from_bits(327680),
        NonNegativeFixed::from_bits(64),
        CertifiedLearning::admit_learning(),
    );
    assert!(p_dist_low.is_none());
}

#[test]
fn test_rejection_invariance() {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 123u32;
    let mut prev_mode = 4u32;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    let weights_before = weights;
    let last_switch_t_before = last_switch_t;
    let prev_mode_before = prev_mode;

    // Trigger a refusal (e.g. invalid digest)
    let res = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        [0u8; 32],
        get_proof().as_ref(),
    );

    assert!(res.is_err());
    assert_eq!(
        weights, weights_before,
        "CHEAT-021: REJECTION_STATE_DRIFT - weights modified on rejection!"
    );
    assert_eq!(
        last_switch_t, last_switch_t_before,
        "CHEAT-021: REJECTION_STATE_DRIFT - last_switch_t modified on rejection!"
    );
    assert_eq!(
        prev_mode, prev_mode_before,
        "CHEAT-021: REJECTION_STATE_DRIFT - prev_mode modified on rejection!"
    );
}
