//! CMCA-119: a runnable, end-to-end example for a first-time integrator.
//!
//! Run with:
//!
//! ```text
//! cargo run --example basic_allocation -p bcinr-cmca --features std
//! ```
//!
//! ## Which entry point does this example use, and why
//!
//! This example calls [`allocate`], the crate's top-level, LAMBDA-weighted
//! allocation entry point (see `bcinr_cmca`'s crate-level "Which entry point
//! do I want?" doc section for how it relates to `allocate_in`,
//! `allocate_single_lens`, `cascade::consequence_mass`, and
//! `escort::escort_distribution`). `allocate` is the right starting point
//! for a new integrator who just wants "one allocation vector across the
//! whole object registry" without picking a feasible region or isolating a
//! single lens.
//!
//! The registry below reuses this crate's own compiled-in `N = 8`, `K = 4`,
//! `Q = 4` shape from `generated::consequence_mass::case_studies` -- see
//! `allocate`'s own doc comment (and CMCA-108) for why that shape is fixed
//! rather than caller-generic.
// These tests deliberately exercise the `#[deprecated]` authority-chain types
// (`AdaptiveUpdate`, `CertifiedLearning`, receipts, ...) that CMCA-102 fences
// pending Hoare-logic verification. The crate's integration suite is the
// documented exception allowed to construct them (see lib.rs's INTEGRATION
// NOTE); this scoped allow keeps CI's `-D warnings` clippy gate green without
// un-deprecating the types for production callers.
#![allow(deprecated)]

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertificateReceipt, CertifiedLearning,
    EnvelopeReceipt, OutcomeReceipt, StabilityRefusal,
};
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

/// A trivially-admitted proof of adaptive update, the same construction
/// `tests/case_studies.rs` uses -- production callers would thread through
/// a real, previously-certified `AdaptiveUpdate` instead.
#[allow(deprecated)] // CMCA-102/CMCA-114: authority chain pending Hoare-logic verification;
                     // example mirrors tests/case_studies.rs's trivial admission, not a production pattern.
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

fn main() {
    // A flat forest: every object is its own root (no hierarchy).
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut last_switch_t = 0u32;
    let mut prev_mode = 0u32;

    let result: Result<[NonNegativeFixed; N], StabilityRefusal> = allocate(
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
    );

    match result {
        Ok(shares) => {
            println!("allocate() succeeded -- per-object allocation shares:");
            for (i, share) in shares.iter().enumerate() {
                println!("  object[{i}] = {share:?}");
            }
        }
        Err(refusal) => {
            // `StabilityRefusal` implements `Display` (CMCA-119), so a
            // downstream caller can propagate it with `?` under `std` via
            // `Box<dyn std::error::Error>`, or match on the typed variant
            // directly when finer handling is needed.
            println!("allocate() refused: {refusal} ({refusal:?})");
        }
    }
}
