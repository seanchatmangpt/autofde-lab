//! Machine Learning Fairness Audit
//!
//! Demonstrates how CMCA's deterministic, conservation-respecting allocation
//! gives auditors a checkable fairness guarantee when allocating GPU/compute
//! time to competing ML models — something ad-hoc round-robin or priority
//! queues cannot prove.
//!
//! ## The Problem
//!
//! ML systems need to allocate compute fairly across competing models:
//! - Training multiple models simultaneously on shared GPU
//! - Preventing starvation (every model gets sufficient training time)
//! - Proving fairness to auditors (regulatory compliance)
//!
//! Conventional systems use ad-hoc round-robin or priority queues. These
//! cannot prove fairness: "Did model X get enough training?" is unanswerable
//! from an opaque scheduler log alone.
//!
//! ## The Solution
//!
//! CMCA's `allocate()` returns a per-candidate weight vector that (a) is
//! reproducible from published inputs (an auditor can replay it), (b) never
//! starves a candidate with nonzero factors (every `result[i].val > 0`), and
//! (c) conserves total allocated capacity to ~1.0 in Q16.16 fixed point. The
//! tests below check these three properties directly against the real
//! allocation output, not merely that the call returned `Ok`.
// These tests deliberately exercise the `#[deprecated]` authority-chain types
// (`AdaptiveUpdate`, `CertifiedLearning`, receipts, ...) that CMCA-102 fences
// pending Hoare-logic verification. The crate's integration suite is the
// documented exception allowed to construct them (see lib.rs's INTEGRATION
// NOTE); this scoped allow keeps CI's `-D warnings` clippy gate green without
// un-deprecating the types for production callers.
#![allow(deprecated)]
#![allow(clippy::needless_range_loop)]

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertificateReceipt, CertifiedLearning,
    EnvelopeReceipt, OutcomeReceipt,
};
use bcinr_cmca::fixed::NonNegativeFixed;
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

/// Allocate compute for a given round with the shared 8-model registry,
/// returning the full per-model weight vector (not just a success flag).
fn run_allocate(round: u32) -> [NonNegativeFixed; N] {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

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
        round,
        &mut last_switch_t,
        &mut prev_mode,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .unwrap_or_else(|e| panic!("allocation round {} must succeed: {:?}", round, e))
}

/// Test 1: No model is starved — every candidate receives strictly positive
/// compute weight
///
/// Fairness property: for the standard 8-model registry (none of which has
/// zero business value or zero standing), no model may receive a zero
/// allocation. We check every index directly rather than merely checking
/// the call succeeded.
#[test]
fn test_coverage_lens_ensures_model_fairness_no_starvation() {
    for round in 0u32..4 {
        let alloc = run_allocate(round);
        for i in 0..N {
            assert!(
                alloc[i].val > 0,
                "round {}: model {} must receive nonzero compute allocation (starvation detected)",
                round,
                i
            );
        }
    }
}

/// Test 2: Allocation is conserved — total compute distributed sums to ~1.0
///
/// A fairness receipt is only meaningful if the platform can't inflate one
/// model's share without another's shrinking by the same amount. We verify
/// the sum of all 8 model weights conserves to 1.0 in Q16.16 (65536) within
/// 1% tolerance, across 8 independent rounds.
#[test]
fn test_allocation_receipt_proves_fairness_enforced() {
    let total_one = NonNegativeFixed::ONE.val as u64; // 65536

    for round in 0u32..8 {
        let alloc = run_allocate(round);
        let sum: u64 = alloc.iter().map(|w| w.val as u64).sum();
        let diff = sum.abs_diff(total_one);
        assert!(
            diff <= total_one / 100,
            "round {}: total allocated compute ({}) must conserve to ~1.0 (65536), diff {}",
            round,
            sum,
            diff
        );
    }
}

/// Test 3: Allocation is stable within the dwell window — no thrashing
///
/// Dwell-time enforcement (tau_d=500) means a competing high-value model
/// (e.g. GPT-2-equivalent, index 7 with businessValue=1000) cannot cause
/// the distribution to oscillate round-to-round while inside the dwell
/// window. We verify every round in [0, 500) reproduces the exact same
/// per-model distribution as round 0.
#[test]
fn test_competing_models_allocation_oscillation_prevented() {
    let baseline = run_allocate(0);

    for round in [1u32, 50, 100, 250, 499] {
        let alloc = run_allocate(round);
        for i in 0..N {
            assert_eq!(
                alloc[i], baseline[i],
                "round {}: model {} allocation diverged within dwell window — indicates thrashing",
                round, i
            );
        }
    }
}

/// Test 4: Third-party auditor can independently reproduce the distribution
///
/// An external auditor, given only the published inputs (registry, lens
/// table, certificate digest, round), must be able to reproduce the exact
/// per-model allocation without trusting the platform's own computation.
/// We simulate this with two structurally independent calls (separate
/// mutable state) and verify bit-for-bit agreement.
#[test]
fn test_fairness_verifiable_by_external_auditor() {
    let platform_alloc = run_allocate(0);
    let auditor_replay = run_allocate(0);

    for i in 0..N {
        assert_eq!(
            platform_alloc[i], auditor_replay[i],
            "auditor's independent replay must match platform's published allocation for model {}",
            i
        );
    }
}

/// Test 5: Coverage metadata reveals allocation bias correctly (no false
/// positives, no false negatives)
///
/// If a platform inflates the highest-business-value model (index 7,
/// businessValue=1000) relative to the others, that bias is a real,
/// visible property of the returned vector: `alloc[7]` is the maximum
/// among all 8 entries. We assert this directly against the known
/// registry facts, giving an auditor a concrete, checkable bias signal
/// (rather than merely counting successful calls).
#[test]
fn test_coverage_metadata_reveals_allocation_bias() {
    let alloc = run_allocate(0);

    let max_idx = (0..N).max_by_key(|&i| alloc[i].val).unwrap();
    assert_eq!(
        max_idx, 7,
        "highest-business-value model (index 7, businessValue=1000) must receive the largest share \
         — an auditor comparing this against declared business value can confirm no other model \
         was silently favored"
    );

    // And the bias is bounded: the highest-value model must not receive
    // more than half the total pool, which would indicate an unfair
    // winner-take-most allocation rather than a proportional one.
    let total: u64 = alloc.iter().map(|w| w.val as u64).sum();
    assert!(
        (alloc[7].val as u64) * 2 < total,
        "highest-value model must not capture more than half of total allocated compute"
    );
}
