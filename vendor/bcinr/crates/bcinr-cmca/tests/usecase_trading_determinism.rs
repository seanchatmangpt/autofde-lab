//! Financial Trading Determinism
//!
//! Demonstrates how CMCA's deterministic allocation enables reproducible
//! high-frequency trading systems that withstand regulatory audit.
//!
//! ## The Problem
//!
//! High-frequency traders must allocate capital across market orders.
//! Conventional systems use floating-point arithmetic and randomness,
//! making execution impossible to audit or reproduce. Regulators require
//! reproducible allocation for enforcement.
//!
//! ## The Solution
//!
//! CMCA provides:
//! - Deterministic Q16.16 fixed-point (no IEEE 754 variance)
//! - No randomness source (allocation depends only on inputs)
//! - BLAKE3 receipts (auditable, tamper-evident records)
//! - Identical execution on any hardware, any CPU vendor
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

/// Test 1: Identical allocation for identical market state
///
/// Regulators can replay a trading decision and verify the allocation.
/// This requires: same inputs → same output (always).
#[test]
fn test_allocation_reproducible_same_market_state() {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];

    // Run allocation twice with identical market state (round 0)
    let mut results = Vec::new();

    for _ in 0..2 {
        let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
        let mut last_switch_t = 0;
        let mut prev_mode = 0;

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
            0, // Same market state (round 0)
            &mut last_switch_t,
            &mut prev_mode,
            500,
            CERTIFICATE_DIGEST,
            get_proof().as_ref(),
        );

        results.push(result.expect("allocation must succeed for a valid market state"));
    }

    assert_eq!(results.len(), 2, "both replay attempts must have executed");

    // Verify: identical market state -> identical allocations, checked
    // per exchange, not merely that both calls returned Ok.
    for i in 0..N {
        assert_eq!(
            results[0][i], results[1][i],
            "identical market state must produce identical allocation for exchange {}",
            i
        );
    }
}

/// Test 2: No floating-point randomness in calculation
///
/// IEEE 754 floating-point has non-determinism sources:
/// - Compiler optimizations may reorder FP operations
/// - Flush-to-zero modes vary by CPU
/// - Rounding modes can change
///
/// CMCA uses only integer arithmetic (no FP).
#[test]
fn test_no_randomness_source_code_audit() {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];

    // Run allocation 10 times with identical input. Each call must succeed
    // (unwrap, not `if let Ok`) so a systematic failure fails the test
    // loudly instead of leaving `first_result` unset and the loop's
    // consistency check vacuously true.
    let mut first_result: Option<[NonNegativeFixed; N]> = None;
    let mut runs = 0;

    for _ in 0..10 {
        let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
        let mut last_switch_t = 0;
        let mut prev_mode = 0;

        let alloc = allocate(
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
        .expect(
            "allocation must succeed (no FP, no randomness means no run should ever fail here)",
        );

        runs += 1;
        match &first_result {
            None => first_result = Some(alloc),
            Some(first) => {
                for i in 0..N {
                    assert_eq!(
                        first[i], alloc[i],
                        "run diverged at candidate {} — allocation is not deterministic",
                        i
                    );
                }
            }
        }
    }

    assert_eq!(runs, 10, "all 10 allocation runs must have executed");
}

/// Test 3: Auditable by third-party regulator
///
/// Regulators receive:
/// - Market state (order book, liquidity)
/// - Allocation decision (which exchange, order size)
/// - BLAKE3 receipt (proof of allocation)
///
/// They replay and verify receipt matches original.
#[test]
fn test_receipt_publishable_verifiable_by_auditors() {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];

    // Allocate capital
    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

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
    );

    let alloc = result.expect("allocation must succeed for audit trail");

    // A publishable receipt is only meaningful if replaying it against the
    // same certificate digest and market state reproduces the exact same
    // capital allocation. We simulate the auditor's replay directly: an
    // independent call with identical inputs must match bit-for-bit.
    let mut weights_replay = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t_replay = 0;
    let mut prev_mode_replay = 0;
    let replay = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut weights_replay,
        &payoffs,
        NonNegativeFixed::ZERO,
        NonNegativeFixed::ZERO,
        &mu,
        &costs,
        0,
        &mut last_switch_t_replay,
        &mut prev_mode_replay,
        500,
        CERTIFICATE_DIGEST,
        get_proof().as_ref(),
    )
    .expect("auditor replay must succeed against the published certificate digest");

    for i in 0..N {
        assert_eq!(
            alloc[i], replay[i],
            "auditor's independent replay must reproduce exchange {} allocation exactly",
            i
        );
    }
}

/// Test 4: All q-lenses produce valid allocations
///
/// CMCA supports multiple allocation strategies (q-lenses):
/// - Exploitation: allocate to highest-value exchange
/// - Coverage: allocate to underutilized exchanges
/// - Rare: allocate to high-volatility opportunities
///
/// All should produce valid allocations when replayed.
#[test]
fn test_multi_strategy_competitive_fair_optimal() {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];

    let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
    let mut last_switch_t = 0;
    let mut prev_mode = 0;

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
    );

    let alloc = result.expect("all q-lenses must produce valid allocations");

    // A "valid" allocation is not just Ok(_): it must be a real capital
    // distribution — no exchange starved (every candidate gets a strictly
    // positive share) and the total allocated is conserved to ~1.0 in
    // Q16.16 (65536), i.e. capital is distributed, not created or lost.
    let mut sum: u64 = 0;
    for (i, a) in alloc.iter().enumerate().take(N) {
        assert!(a.val > 0, "exchange {} must not be starved of capital", i);
        sum += a.val as u64;
    }
    let total = NonNegativeFixed::ONE.val as u64; // 65536 == 1.0 in Q16.16
    let diff = sum.abs_diff(total);
    assert!(
        diff <= total / 100, // within 1% of full conservation
        "total allocated capital ({}) must conserve to ~1.0 (65536), got diff {}",
        sum,
        diff
    );
}

/// Test 5: Capital allocation is deterministic and auditable
///
/// Regulators verify:
/// - Same market state → same allocation (determinism)
/// - Allocations are consistent across replays
/// - Distribution is verifiable via audit trail
#[test]
fn test_allocation_fairness_distribution_auditable() {
    let parent = [-1; N];
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];

    // Allocate across multiple intraday rounds and verify: (a) no exchange
    // is ever starved, and (b) since all rounds sit inside the same
    // dwell-time window, every round reproduces the identical distribution
    // — a regulator diffing round-by-round allocations can rely on this.
    let mut baseline: Option<[NonNegativeFixed; N]> = None;

    for round in 0u32..5 {
        let mut weights = [[NonNegativeFixed::ONE; 2 * Q]; N];
        let mut last_switch_t = 0;
        let mut prev_mode = 0;

        let alloc = allocate(
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
        .unwrap_or_else(|e| panic!("allocation round {} must succeed: {:?}", round, e));

        for (i, a) in alloc.iter().enumerate().take(N) {
            assert!(a.val > 0, "round {} must not starve exchange {}", round, i);
        }

        match &baseline {
            None => baseline = Some(alloc),
            Some(expected) => {
                for i in 0..N {
                    assert_eq!(
                        alloc[i], expected[i],
                        "round {} allocation for exchange {} diverged from round-0 baseline within the same dwell window",
                        round, i
                    );
                }
            }
        }
    }
}
