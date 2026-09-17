// These tests deliberately exercise the `#[deprecated]` authority-chain types
// (`AdaptiveUpdate`, `CertifiedLearning`, receipts, ...) that CMCA-102 fences
// pending Hoare-logic verification. The crate's integration suite is the
// documented exception allowed to construct them (see lib.rs's INTEGRATION
// NOTE); this scoped allow keeps CI's `-D warnings` clippy gate green without
// un-deprecating the types for production callers.
#![allow(deprecated)]
#![allow(dead_code)]

use bcinr_cmca::allocator::CertificateReceipt;
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::observatory::{MeasurementArtifact, ModeDelta, ObservatoryFlag, SupportStanding};

fn make_artifact(
    kappa_hat: NonNegativeFixed,
    kappa_under: NonNegativeFixed,
    gamma_min_plus_under: NonNegativeFixed,
    d_js: NonNegativeFixed,
) -> MeasurementArtifact {
    MeasurementArtifact {
        point_estimate: kappa_hat,
        lower_bound: kappa_under,
        upper_bound: kappa_hat,
        support_standing: SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: d_js,
        gram_lower_bound: gamma_min_plus_under,
        graph_digest: 0,
        control_mode_digest: 42,
        proposal: ModeDelta::ProposeDelta,
    }
}

// M01: Ignore numeric error in underline kappa. Use kappa_hat instead of kappa_under.
#[allow(clippy::too_many_arguments)]
pub fn evaluate_m01(
    kappa_hat: NonNegativeFixed,
    _kappa_under: NonNegativeFixed,
    epsilon_on: NonNegativeFixed,
    _gamma_min_plus_hat: NonNegativeFixed,
    gamma_min_plus_under: NonNegativeFixed,
    epsilon_gram: NonNegativeFixed,
    d_js: NonNegativeFixed,
    epsilon_drift: NonNegativeFixed,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let artifact = make_artifact(
        kappa_hat,
        kappa_hat, /* MUTANT! */
        gamma_min_plus_under,
        d_js,
    );
    bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        epsilon_on,
        epsilon_gram,
        epsilon_drift,
        s_meas,
        s_leaf,
    )
}

#[test]
fn kill_m01_ignore_numeric_error() {
    if !require_production_semantics("kill_m01_ignore_numeric_error") {
        return;
    }
    let result = evaluate_m01(
        NonNegativeFixed::from_bits(66000), // kappa_hat > epsilon_on
        NonNegativeFixed::from_bits(65000), // kappa_under < epsilon_on
        NonNegativeFixed::from_bits(65536), // epsilon_on = 1.0
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_ne!(result, Err(ObservatoryFlag::NumericallyUncertain));
}

// M03: Use point-estimate Gram gate without subtracting epsilon_gram.
#[allow(clippy::too_many_arguments)]
pub fn evaluate_m03(
    kappa_hat: NonNegativeFixed,
    kappa_under: NonNegativeFixed,
    epsilon_on: NonNegativeFixed,
    gamma_min_plus_hat: NonNegativeFixed,
    _gamma_min_plus_under: NonNegativeFixed,
    epsilon_gram: NonNegativeFixed,
    d_js: NonNegativeFixed,
    epsilon_drift: NonNegativeFixed,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let artifact = make_artifact(
        kappa_hat,
        kappa_under,
        gamma_min_plus_hat, /* MUTANT! */
        d_js,
    );
    bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        epsilon_on,
        epsilon_gram,
        epsilon_drift,
        s_meas,
        s_leaf,
    )
}

#[test]
fn kill_m03_point_estimate_gram_gate() {
    if !require_production_semantics("kill_m03_point_estimate_gram_gate") {
        return;
    }
    let result = evaluate_m03(
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(131072), // gamma_hat > epsilon_gram
        NonNegativeFixed::from_bits(32768),  // gamma_under < epsilon_gram
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_ne!(result, Err(ObservatoryFlag::GramDegenerate));
}

// M05: Ignore drift.
#[allow(clippy::too_many_arguments)]
pub fn evaluate_m05(
    kappa_hat: NonNegativeFixed,
    kappa_under: NonNegativeFixed,
    epsilon_on: NonNegativeFixed,
    _gamma_min_plus_hat: NonNegativeFixed,
    gamma_min_plus_under: NonNegativeFixed,
    epsilon_gram: NonNegativeFixed,
    _d_js: NonNegativeFixed,
    epsilon_drift: NonNegativeFixed,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let artifact = make_artifact(
        kappa_hat,
        kappa_under,
        gamma_min_plus_under,
        NonNegativeFixed::ZERO, /* MUTANT! Ignores drift */
    );
    bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        epsilon_on,
        epsilon_gram,
        epsilon_drift,
        s_meas,
        s_leaf,
    )
}

#[test]
fn kill_m05_ignore_drift() {
    if !require_production_semantics("kill_m05_ignore_drift") {
        return;
    }
    let result = evaluate_m05(
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(131072), // d_js > epsilon_drift
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_ne!(result, Err(ObservatoryFlag::Drifting));
}

// M07: Activate learner based on kappa only, ignoring Gram distinguishability.
#[allow(clippy::too_many_arguments)]
pub fn evaluate_m07(
    kappa_hat: NonNegativeFixed,
    kappa_under: NonNegativeFixed,
    epsilon_on: NonNegativeFixed,
    _gamma_min_plus_hat: NonNegativeFixed,
    _gamma_min_plus_under: NonNegativeFixed,
    epsilon_gram: NonNegativeFixed,
    d_js: NonNegativeFixed,
    epsilon_drift: NonNegativeFixed,
    s_meas: NonNegativeFixed,
    s_leaf: NonNegativeFixed,
) -> Result<CertificateReceipt, ObservatoryFlag> {
    let artifact = make_artifact(
        kappa_hat,
        kappa_under,
        NonNegativeFixed::from_bits(1310720), /* MUTANT! Forcing gamma_under to be large */
        d_js,
    );
    bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        epsilon_on,
        epsilon_gram,
        epsilon_drift,
        s_meas,
        s_leaf,
    )
}

#[test]
fn kill_m07_ignore_gram() {
    if !require_production_semantics("kill_m07_ignore_gram") {
        return;
    }
    let result = evaluate_m07(
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(32768),
        NonNegativeFixed::from_bits(32768), // Both gamma < epsilon_gram
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ONE,
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_ne!(result, Err(ObservatoryFlag::GramDegenerate));
}

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertifiedLearning, EnvelopeReceipt,
    OutcomeReceipt, StabilityRefusal,
};
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

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

fn run_alloc_baseline() -> [NonNegativeFixed; N] {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    allocate(
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
    .unwrap()
}

fn run_alloc_tree() -> [NonNegativeFixed; N] {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

    let mut parent = [-1; N];
    parent[1] = 0;
    parent[2] = 0;

    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    allocate(
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
    .unwrap()
}

fn run_alloc_mu_cost() -> Result<[NonNegativeFixed; N], StabilityRefusal> {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];

    // Set mu negative so clipping to zero differs from unclipped
    let mu = [NonNegativeFixed::from_bits(0u32.wrapping_sub(327680)); N];
    let costs = [NonNegativeFixed::ONE; N];

    allocate(
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
        // CMCA-103: proof=None used to bypass admission entirely
        // (degrade_to_certified_selection silently accepted out-of-domain
        // inputs). Since the fix, this out-of-domain `mu` is refused
        // (PriceGainUnsafe) unconditionally, regardless of proof -- so this
        // no longer "freezes learning but succeeds."
        None,
    )
}

/// CMCA-122 regression test: constructs a call where `eta_err` and
/// `price_err` are both true simultaneously, and asserts the returned
/// `StabilityRefusal` correctly identifies the pricing fault rather than
/// misreporting `LearningRateOutsideEnvelope` (the pre-fix behavior, which
/// masked `price_err` because `eta_err` was folded into the same
/// `(lr_err | beta_err | eta_err)` priority-chain bucket).
fn run_alloc_eta_and_price_err() -> Result<[NonNegativeFixed; N], StabilityRefusal> {
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];

    // Out-of-domain mu (mu > mu_max): triggers `price_err`, same as
    // `run_alloc_mu_cost` above.
    let mu = [NonNegativeFixed::from_bits(0u32.wrapping_sub(327680)); N];
    let costs = [NonNegativeFixed::ONE; N];

    // eta above ETA_G_MAX (1.0 in Q16.16 == 65536): triggers `eta_err`.
    let eta_out_of_range = NonNegativeFixed::from_bits(NonNegativeFixed::ONE.val + 1);

    allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        eta_out_of_range,
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
        None,
    )
}

#[test]
fn eta_err_and_price_err_co_occurring_reports_price_gain_unsafe_not_learning_rate() {
    let result = run_alloc_eta_and_price_err();
    assert_eq!(
        result,
        Err(StabilityRefusal::PriceGainUnsafe),
        "when eta_err and price_err are both true, the reported reason must be \
         PriceGainUnsafe (the real cause), not LearningRateOutsideEnvelope \
         (which CMCA-122 fixed away from bundling eta_err into)"
    );
}

#[test]
fn eta_err_alone_reports_its_own_dedicated_reason() {
    // Same eta out-of-range as above, but mu within domain -- isolates
    // eta_err from price_err to confirm eta_err now has its own,
    // non-learning-rate reason.
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let eta_out_of_range = NonNegativeFixed::from_bits(NonNegativeFixed::ONE.val + 1);

    let result = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        eta_out_of_range,
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
        None,
    );

    assert_eq!(
        result,
        Err(StabilityRefusal::ExploreFloorOutsideEnvelope),
        "eta_err alone must report its own dedicated reason, not \
         LearningRateOutsideEnvelope"
    );
}

const CORRECT_BASELINE: [u32; N] = [8349, 7741, 6684, 6684, 6684, 6684, 7973, 14733];
const CORRECT_TREE: [u32; N] = [0, 9391, 6623, 8066, 8066, 8066, 9275, 16043];

const ACTIVE_MUTANT_COUNT: u8 = cfg!(feature = "mutant_1") as u8
    + cfg!(feature = "mutant_2") as u8
    + cfg!(feature = "mutant_3") as u8
    + cfg!(feature = "mutant_4") as u8
    + cfg!(feature = "mutant_5") as u8
    + cfg!(feature = "mutant_6") as u8
    + cfg!(feature = "mutant_7") as u8
    + cfg!(feature = "mutant_8") as u8
    + cfg!(feature = "mutant_9") as u8
    + cfg!(feature = "mutant_10") as u8
    + cfg!(feature = "mutant_11") as u8;

fn require_isolated_mutant(mutant: &str) -> bool {
    if ACTIVE_MUTANT_COUNT == 1 {
        true
    } else {
        eprintln!(
            "BCINR_TYPED_SKIP[cmca-mutant-composition]: {mutant} requires exactly one active mutant feature; observed {ACTIVE_MUTANT_COUNT}"
        );
        false
    }
}

fn require_production_semantics(test: &str) -> bool {
    if ACTIVE_MUTANT_COUNT == 0 {
        true
    } else {
        eprintln!(
            "BCINR_TYPED_SKIP[cmca-mutant-composition]: {test} is a handcrafted wrapper rail and requires zero crate-level mutant features; observed {ACTIVE_MUTANT_COUNT}"
        );
        false
    }
}

#[cfg(feature = "mutant_1")]
#[test]
fn kill_mutant_1_single_measure_collapse() {
    if !require_isolated_mutant("mutant_1") {
        return;
    }
    let result_mutant = run_alloc_baseline().map(|x| x.val);
    assert_ne!(
        result_mutant, CORRECT_BASELINE,
        "Mutant 1 should deviate from correct baseline"
    );
}

#[cfg(feature = "mutant_2")]
#[test]
fn kill_mutant_2_q_sign_inversion() {
    if !require_isolated_mutant("mutant_2") {
        return;
    }
    let result_mutant = run_alloc_baseline().map(|x| x.val);
    assert_ne!(
        result_mutant, CORRECT_BASELINE,
        "Mutant 2 should deviate from correct baseline"
    );
}

#[cfg(feature = "mutant_3")]
#[test]
fn kill_mutant_3_broken_normalization() {
    if !require_isolated_mutant("mutant_3") {
        return;
    }
    let result_mutant = run_alloc_tree().map(|x| x.val);
    assert_ne!(
        result_mutant, CORRECT_TREE,
        "Mutant 3 should deviate from correct tree baseline"
    );
}

#[cfg(feature = "mutant_4")]
#[test]
fn kill_mutant_4_rdf_identity_skew() {
    if !require_isolated_mutant("mutant_4") {
        return;
    }
    let result_mutant = run_alloc_baseline().map(|x| x.val);
    assert_ne!(
        result_mutant, CORRECT_BASELINE,
        "Mutant 4 should deviate from correct baseline"
    );
}

#[cfg(feature = "mutant_5")]
#[test]
fn kill_mutant_5_consequence_truncation() {
    if !require_isolated_mutant("mutant_5") {
        return;
    }
    // CMCA-103 note: `run_alloc_mu_cost`'s deliberately out-of-domain `mu`
    // (used to distinguish clipped vs. unclipped `mu_actual`) is now refused
    // by the *unconditionally*-enforced admission gate (`price_err`) before
    // mutant_5's clip removal can have any observable effect on the returned
    // allocation -- both the baseline and the mutant now return the same
    // `Err(PriceGainUnsafe)` via this public entry point, so this mutant is
    // no longer killable through `allocate`/`allocate_in`. This is a
    // consequence of fixing CMCA-103 (out-of-domain admission is no longer
    // bypassable via proof=None). CMCA-122 resolves the follow-up: `clip`'s
    // clamping behavior now has direct, real unit-level coverage in
    // `allocator::clip_tests` (src/allocator/mod.rs) that bypasses the
    // admission gate entirely, so the underlying behavior this mutant would
    // have broken is still regression-tested -- just not through this
    // public-API-level test. Asserting the (now-shared) refusal here
    // instead of silently asserting the old, no-longer-true "mutant
    // deviates from baseline" claim.
    let result_mutant = run_alloc_mu_cost();
    assert!(
        result_mutant.is_err(),
        "expected the out-of-domain admission refusal to fire regardless of mutant_5"
    );
}

#[cfg(feature = "mutant_6")]
#[test]
fn kill_mutant_6_saturating_add_false_overflow() {
    if !require_isolated_mutant("mutant_6") {
        return;
    }
    let a = NonNegativeFixed {
        val: 10,
        err: u32::MAX,
    };
    let b = NonNegativeFixed {
        val: 20,
        err: u32::MAX,
    };
    let c = a.saturating_add(b);
    assert_eq!(
        c.err,
        bcinr_cmca::allocator::StabilityRefusal::NumericRangeExceeded as u32,
        "Mutant 6 should trigger NumericRangeExceeded"
    );
}

#[cfg(feature = "mutant_7")]
#[test]
fn kill_mutant_7_saturating_div_false_zero() {
    if !require_isolated_mutant("mutant_7") {
        return;
    }
    let a = NonNegativeFixed {
        val: 100,
        err: u32::MAX,
    };
    let b = NonNegativeFixed {
        val: 20,
        err: u32::MAX,
    };
    let c = a.saturating_div(b);
    assert_eq!(
        c.val,
        u32::MAX,
        "Mutant 7 should falsely classify a nonzero denominator as zero and saturate"
    );
    assert_eq!(
        c.err,
        u32::MAX,
        "Mutant 7 should expose the coupled equality-mask defect that suppresses the refusal code"
    );
}

#[cfg(feature = "mutant_8")]
#[test]
fn kill_mutant_8_log2_false_zero() {
    if !require_isolated_mutant("mutant_8") {
        return;
    }
    let a = NonNegativeFixed {
        val: 100,
        err: u32::MAX,
    };
    let c = a.log2();
    assert_eq!(
        c.err,
        bcinr_cmca::allocator::StabilityRefusal::UnsupportedDomain as u32,
        "Mutant 8 should trigger UnsupportedDomain"
    );
}

#[cfg(feature = "mutant_9")]
#[test]
fn kill_mutant_9_false_drift() {
    if !require_isolated_mutant("mutant_9") {
        return;
    }
    let artifact = bcinr_cmca::observatory::MeasurementArtifact {
        point_estimate: NonNegativeFixed::from_bits(65536),
        lower_bound: NonNegativeFixed::from_bits(65536),
        upper_bound: NonNegativeFixed::from_bits(65536),
        support_standing: bcinr_cmca::observatory::SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: NonNegativeFixed::ZERO,
        gram_lower_bound: NonNegativeFixed::from_bits(131072),
        graph_digest: 0,
        control_mode_digest: 42,
        proposal: bcinr_cmca::observatory::ModeDelta::ProposeDelta,
    };
    let result = bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(
        result,
        Err(bcinr_cmca::observatory::ObservatoryFlag::Drifting)
    );
}

#[cfg(feature = "mutant_10")]
#[test]
fn kill_mutant_10_false_numerically_uncertain() {
    if !require_isolated_mutant("mutant_10") {
        return;
    }
    let artifact = bcinr_cmca::observatory::MeasurementArtifact {
        point_estimate: NonNegativeFixed::from_bits(131072),
        lower_bound: NonNegativeFixed::from_bits(131072),
        upper_bound: NonNegativeFixed::from_bits(131072),
        support_standing: bcinr_cmca::observatory::SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: NonNegativeFixed::ZERO,
        gram_lower_bound: NonNegativeFixed::from_bits(131072),
        graph_digest: 0,
        control_mode_digest: 42,
        proposal: bcinr_cmca::observatory::ModeDelta::ProposeDelta,
    };
    let result = bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(
        result,
        Err(bcinr_cmca::observatory::ObservatoryFlag::NumericallyUncertain)
    );
}

#[cfg(feature = "mutant_11")]
#[test]
fn kill_mutant_11_false_gram_degenerate() {
    if !require_isolated_mutant("mutant_11") {
        return;
    }
    let artifact = bcinr_cmca::observatory::MeasurementArtifact {
        point_estimate: NonNegativeFixed::from_bits(131072),
        lower_bound: NonNegativeFixed::from_bits(131072),
        upper_bound: NonNegativeFixed::from_bits(131072),
        support_standing: bcinr_cmca::observatory::SupportStanding {
            is_supported: true,
            smoothing_applied: false,
        },
        effective_sample_size: NonNegativeFixed::ONE,
        dependence_standing: 0,
        numeric_error: NonNegativeFixed::ZERO,
        drift: NonNegativeFixed::ZERO,
        gram_lower_bound: NonNegativeFixed::from_bits(131072),
        graph_digest: 0,
        control_mode_digest: 42,
        proposal: bcinr_cmca::observatory::ModeDelta::ProposeDelta,
    };
    let result = bcinr_cmca::observatory::evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(
        result,
        Err(bcinr_cmca::observatory::ObservatoryFlag::GramDegenerate)
    );
}

#[cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5",
    feature = "mutant_6",
    feature = "mutant_7",
    feature = "mutant_8",
    feature = "mutant_9",
    feature = "mutant_10",
    feature = "mutant_11"
)))]
#[test]
fn verify_correctness_baselines() {
    assert_eq!(run_alloc_baseline().map(|x| x.val), CORRECT_BASELINE);
    assert_eq!(run_alloc_tree().map(|x| x.val), CORRECT_TREE);
    // CMCA-103: this baseline's `mu` is deliberately out of the declared
    // domain (see `run_alloc_mu_cost`'s comment); admission is now
    // unconditional, so it is correctly refused rather than silently
    // accepted with a frozen-learning degrade.
    assert_eq!(run_alloc_mu_cost(), Err(StabilityRefusal::PriceGainUnsafe));
}
