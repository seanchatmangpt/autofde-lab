#![cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5"
)))]

use bcinr_cmca::allocator::CertificateReceipt;
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::observatory::{
    evaluate_calibration, MeasurementArtifact, ModeDelta, ObservatoryFlag, SupportStanding,
};

fn make_artifact(
    kappa_hat: NonNegativeFixed,
    kappa_under: NonNegativeFixed,
    gamma_min_plus_under: NonNegativeFixed,
    d_js: NonNegativeFixed,
    proposal: ModeDelta,
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
        proposal,
    }
}

// Core Calibration Fixtures
#[test]
fn test_f02_numerically_uncertain() {
    let artifact = make_artifact(
        NonNegativeFixed::from_bits(66000), // kappa_hat > epsilon_on
        NonNegativeFixed::from_bits(65000), // kappa_under < epsilon_on
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ZERO,
        ModeDelta::ProposeDelta,
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536), // epsilon_on = 1.0
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(result, Err(ObservatoryFlag::NumericallyUncertain));
}

#[test]
fn test_f03_gram_degenerate() {
    let artifact = make_artifact(
        NonNegativeFixed::from_bits(131072), // kappa_hat > epsilon_on
        NonNegativeFixed::from_bits(131072), // kappa_under > epsilon_on
        NonNegativeFixed::from_bits(32768),  // gamma_min_plus_under < epsilon_gram
        NonNegativeFixed::ZERO,
        ModeDelta::ProposeDelta,
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536), // epsilon_on = 1.0
        NonNegativeFixed::from_bits(65536), // epsilon_gram = 1.0
        NonNegativeFixed::ONE,
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(result, Err(ObservatoryFlag::GramDegenerate));
}

#[test]
fn test_f09_nonstationary_window() {
    let artifact = make_artifact(
        NonNegativeFixed::from_bits(131072), // kappa_hat
        NonNegativeFixed::from_bits(131072), // kappa_under
        NonNegativeFixed::from_bits(131072), // gamma_min_plus_under
        NonNegativeFixed::from_bits(131072), // d_js > epsilon_drift
        ModeDelta::ProposeDelta,
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536), // epsilon_on
        NonNegativeFixed::from_bits(65536), // epsilon_gram
        NonNegativeFixed::from_bits(65536), // epsilon_drift
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(result, Err(ObservatoryFlag::Drifting));
}

#[test]
fn test_f00_exact_scale_collapse() {
    let artifact = make_artifact(
        NonNegativeFixed::ZERO,              // kappa_hat
        NonNegativeFixed::ZERO,              // kappa_under
        NonNegativeFixed::from_bits(131072), // gamma_min_plus_under
        NonNegativeFixed::ZERO,              // d_js
        ModeDelta::ProposeDelta,
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536), // epsilon_on
        NonNegativeFixed::from_bits(65536), // epsilon_gram
        NonNegativeFixed::from_bits(65536), // epsilon_drift
        NonNegativeFixed::ONE,              // s_meas
        NonNegativeFixed::ONE,              // s_leaf == s_meas
    );
    assert_eq!(result, Err(ObservatoryFlag::ScaleInert));
}

#[test]
fn test_f01_material_scale_information() {
    let artifact = make_artifact(
        NonNegativeFixed::from_bits(131072), // kappa_hat
        NonNegativeFixed::from_bits(131072), // kappa_under
        NonNegativeFixed::from_bits(131072), // gamma_min_plus_under
        NonNegativeFixed::ZERO,              // d_js
        ModeDelta::ProposeDelta,
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536), // epsilon_on
        NonNegativeFixed::from_bits(65536), // epsilon_gram
        NonNegativeFixed::from_bits(65536), // epsilon_drift
        NonNegativeFixed::ONE,              // s_meas
        NonNegativeFixed::from_bits(32768), // s_leaf
    );
    assert_eq!(result, Ok(CertificateReceipt::admit_certificate(42))); // RECERTIFICATION_CANDIDATE
}

#[test]
fn test_f04_mode_delta_unadmitted() {
    let artifact = make_artifact(
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::from_bits(131072),
        NonNegativeFixed::ZERO,
        ModeDelta::Retain, // Retain!
    );
    let result = evaluate_calibration(
        &artifact,
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::from_bits(65536),
        NonNegativeFixed::ONE,
        NonNegativeFixed::from_bits(32768),
    );
    assert_eq!(result, Err(ObservatoryFlag::ModeDeltaUnadmitted));
}
