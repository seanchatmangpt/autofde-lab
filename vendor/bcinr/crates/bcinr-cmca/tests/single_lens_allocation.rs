#![cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5"
)))]
#![allow(clippy::needless_range_loop)]

//! Acceptance tests for [`allocate_single_lens`], the crate's first genuine
//! single-lens allocation entry point.
//!
//! # Why this file exists
//!
//! A test-drive script run against `allocator::allocate()` over this crate's
//! own shipped `OBJECT_REGISTRY`/`LENS_REGISTRY` found that all 4 lenses
//! (Exploitation/Proportional/Coverage/Rare) produced byte-identical output.
//! Root cause, confirmed by reading `allocate_in`: `allocate()` always sums
//! all `K x Q` (measure, lens) combinations into one LAMBDA-weighted blend
//! (`pi_combined`) -- there was no public way to ask "what would lens `q`
//! alone say." `tests/falsification_adversarial.rs` already documented this
//! gap directly ("per-lens isolation is not observable through the public
//! API"). `allocate_single_lens` closes it by exposing the crate's existing
//! internal per-lens kernel (`compute_pi_kq_for_kq`) directly, rather than
//! reimplementing the escort math -- so this file's job is to prove that
//! exposure is both (a) real (the 4 lenses now genuinely diverge) and
//! (b) faithful (summing the 16 single-lens results with LAMBDA reproduces
//! `allocate()`'s own blended answer, bit-for-bit up to measured rounding).

use bcinr_cmca::allocator::{
    allocate_single_lens, AdaptiveUpdate, AdmittedControlState, CertificateReceipt,
    CertifiedLearning, EnvelopeReceipt, LensSelectionRefusal, OutcomeReceipt,
};
use bcinr_cmca::fixed::NonNegativeFixed;
use bcinr_cmca::generated::consequence_mass::case_studies::{
    ETA, K, LAMBDA, LENS_REGISTRY, N, OBJECT_REGISTRY, Q,
};

fn flat_weights() -> [[NonNegativeFixed; 2 * Q]; N] {
    [[NonNegativeFixed::ONE; 2 * Q]; N]
}

fn flat_root_parent() -> [i32; N] {
    [-1; N] // every object is its own root -- OBJECT_REGISTRY is a flat, non-tree registry
}

/// A depth-2 tree: node 0 is the root; nodes 1 and 2 are internal children
/// of 0 (each with two leaf children of their own); node 3 is a direct leaf
/// child of 0.
///
///   0 -- 1 -- 4
///     \    \- 5
///      \-2 -- 6
///      |   \- 7
///      \-3 (leaf)
///
/// `allocate_in`'s MWU update only ever fires on internal nodes
/// (`has_children = !is_leaf[v]`), so `flat_root_parent`'s all-leaf shape
/// (CMCA-111's own investigation trigger) can't exercise it at all. A
/// single-level tree (root with only direct-leaf children) can't either:
/// `compute_kappa` compares each direct child's own mass (`s_meas`) against
/// that child's *subtree-leaf* mass (`s_leaf`) -- for a direct leaf child
/// those are the same node, so `s_meas == s_leaf` trivially and
/// `kappa == 0` regardless of payoffs. Depth 2 is the minimum shape where
/// node 0's internal children (1, 2) have subtree-leaf mass that genuinely
/// differs from their own direct mass, giving `compute_kappa` a real,
/// non-degenerate signal to react to.
fn depth_two_tree_parent() -> [i32; N] {
    let mut parent = [-1i32; N];
    parent[1] = 0;
    parent[2] = 0;
    parent[3] = 0;
    parent[4] = 1;
    parent[5] = 1;
    parent[6] = 2;
    parent[7] = 2;
    parent
}

/// The 4 lenses now genuinely diverge over the crate's real registry -- the
/// original test-drive scenario this file exists to close, now with real
/// assertions instead of `println!`.
///
/// Sanity-checked during implementation: hardcoding `lens_idx` to a fixed
/// value inside `allocate_single_lens` makes this test fail, confirming it
/// isn't accidentally vacuous.
#[test]
fn the_four_lenses_produce_genuinely_different_allocations() {
    let weights = flat_weights();
    let parent = flat_root_parent();

    let mut per_lens_results = Vec::with_capacity(Q);
    for lens_idx in 0..Q {
        let result = allocate_single_lens(
            &OBJECT_REGISTRY,
            &LENS_REGISTRY,
            0,
            lens_idx,
            &parent,
            &weights,
        )
        .unwrap();
        per_lens_results.push(result);
    }

    // At least one pair of lenses must disagree on at least one object's
    // allocation -- the property that was silently false for `allocate()`.
    let mut any_divergence = false;
    'outer: for a in 0..Q {
        for b in (a + 1)..Q {
            for i in 0..N {
                if per_lens_results[a][i].val != per_lens_results[b][i].val {
                    any_divergence = true;
                    break 'outer;
                }
            }
        }
    }
    assert!(
        any_divergence,
        "expected the 4 lenses to diverge on at least one object; got identical results: {per_lens_results:?}"
    );
}

/// Refusal correctness: each `LensSelectionRefusal` variant fires on the
/// input it names, matching the crate's `assert_eq!`-against-typed-`Result`
/// convention (`case_studies.rs`, `calibration.rs`) rather than a bare
/// `is_err()`.
#[test]
fn refuses_out_of_range_measure_index() {
    let weights = flat_weights();
    let parent = flat_root_parent();
    assert_eq!(
        allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, K, 0, &parent, &weights),
        Err(LensSelectionRefusal::MeasureIndexOutOfRange { measure: K })
    );
}

#[test]
fn refuses_out_of_range_lens_index() {
    let weights = flat_weights();
    let parent = flat_root_parent();
    assert_eq!(
        allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, 0, Q, &parent, &weights),
        Err(LensSelectionRefusal::LensIndexOutOfRange { lens_idx: Q })
    );
}

#[test]
fn refuses_cyclic_parent() {
    let weights = flat_weights();
    // 0 -> 1 -> 0: a real cycle, no root anywhere.
    let mut parent = flat_root_parent();
    parent[0] = 1;
    parent[1] = 0;
    assert_eq!(
        allocate_single_lens(&OBJECT_REGISTRY, &LENS_REGISTRY, 0, 0, &parent, &weights),
        Err(LensSelectionRefusal::Cyclic)
    );
}

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

/// The core architectural claim: `allocate_single_lens` is not a parallel
/// reimplementation that could drift from `allocate()` -- summing its 16
/// `(measure, lens)` results with the crate's own `LAMBDA` weights
/// reproduces `pi_combined`, the value `allocate_in` builds internally
/// before folding in `mu`/`costs`/`eta` pricing (`allocator/mod.rs`'s
/// `pi_res` construction), within a measured Q16.16 rounding tolerance --
/// not `DIFFERENTIAL_TOLERANCE`'s 0.22 placeholder, which is an unrelated
/// f64-vs-fixed compatibility hack.
///
/// `allocate()` does not return `pi_combined` directly, only the
/// fully-priced `pi_res`, so this test replicates `allocate_in`'s own
/// pricing formula (`val = eta*nl_recip + (1-eta)*p_mu`, with `mu`/`costs`
/// zeroed so `p_mu` reduces to `pi_combined[x] / sum_leaves(pi_combined)`)
/// against the LAMBDA-weighted reconstruction from `allocate_single_lens`,
/// rather than against a second, independently-guessed value.
#[test]
fn blend_equals_the_lambda_weighted_sum_of_single_lens_results() {
    use bcinr_cmca::allocator::allocate;
    use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

    let weights = flat_weights();
    let parent = flat_root_parent();
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];
    let payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut mut_weights = weights;
    let mut last_switch_t = 0u32;
    let mut prev_mode = 0u32;

    let blended = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA, // the crate's own registry ETA (0.5) -- allocate_in refuses eta below a floor
        &parent,
        &mut mut_weights,
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

    let mut pi_combined = [NonNegativeFixed::ZERO; N];
    for k in 0..K {
        for q_idx in 0..Q {
            let single = allocate_single_lens(
                &OBJECT_REGISTRY,
                &LENS_REGISTRY,
                k,
                q_idx,
                &parent,
                &weights,
            )
            .unwrap();
            for i in 0..N {
                pi_combined[i] += LAMBDA[k][q_idx] * single[i];
            }
        }
    }

    // mu=costs=0 everywhere -> exp(-(mu*costs)) == ONE for every object, so
    // `p_mu[x] == pi_combined[x] / priced_sum`, `priced_sum` the sum of
    // `pi_combined` over leaves (all N objects here, flat root parent).
    let mut priced_sum = NonNegativeFixed::ZERO;
    for i in 0..N {
        priced_sum += pi_combined[i];
    }
    // `LEAF_RECIP[N]` (allocator/mod.rs's lookup table) for N=8 leaves == 1/8.
    let nl_recip = NonNegativeFixed::from_bits(8192);

    let mut expected = [NonNegativeFixed::ZERO; N];
    for i in 0..N {
        let p_mu = pi_combined[i] / priced_sum;
        expected[i] = ETA * nl_recip + (NonNegativeFixed::ONE - ETA) * p_mu;
    }

    // Measured, not guessed: the actual observed diff on this registry (all
    // 8 objects) is exactly 0 -- `pi_kq`'s max-shift-stabilised softmax and
    // `compute_pi_kq_for_kq`'s exact repeated-multiplication path leave no
    // rounding room to lose here. 8 bits of headroom above that measured 0
    // (matching `cmca_h_lean_correspondence.rs`'s `NORMALIZATION_TOLERANCE_BITS`
    // precedent) catches a real regression without being a brittle exact-zero
    // assertion tied to this one registry's specific values.
    const RECONSTRUCTION_TOLERANCE_BITS: i64 = 8;
    for i in 0..N {
        let diff = (blended[i].to_bits() as i64 - expected[i].to_bits() as i64).abs();
        assert!(
            diff <= RECONSTRUCTION_TOLERANCE_BITS,
            "object {i}: blended={:?} expected_from_single_lens_reconstruction={:?} diff={diff}",
            blended[i],
            expected[i]
        );
    }
}

/// CMCA-111 regression: the blend identity's doc comment now states it
/// holds only for the *post-MWU-update* `weights` snapshot `allocate_in`
/// writes back through its `&mut weights` parameter -- not for an
/// independently-held pre-call snapshot. This test exercises **non-zero,
/// differentiated** payoffs (unlike
/// `blend_equals_the_lambda_weighted_sum_of_single_lens_results`'s
/// all-zero-payoffs case, which is structurally incapable of triggering
/// the MWU update at all: `exp(beta*0) == 1` is a no-op regardless of
/// `kappa`) and proves both halves of the corrected claim:
///
/// 1. Reconstructing from the **pre-call** `weights` snapshot genuinely
///    diverges from `allocate()`'s blended `pi_combined` once the MWU
///    update has actually fired -- the divergence CMCA-111 reported is
///    real, not merely a documentation nit.
/// 2. Reconstructing from the **post-call** `weights` snapshot (the same
///    array, read *after* `allocate` mutated it in place) reproduces
///    `pi_combined` within the same measured tolerance as the degenerate
///    all-zero-payoffs case.
#[test]
fn blend_identity_requires_the_post_mwu_update_weights_snapshot() {
    use bcinr_cmca::allocator::allocate;
    use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;

    let pre_call_weights = flat_weights();
    let parent = depth_two_tree_parent();
    let mu = [NonNegativeFixed::ZERO; N];
    let costs = [NonNegativeFixed::ZERO; N];

    // Non-zero, differentiated payoffs -- every (node, flat/desc) slot gets
    // a distinct value so the MWU multiplicative update actually reshapes
    // `local_weights` rather than scaling every slot identically.
    let mut payoffs = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    for v in 0..N {
        for e in 0..(2 * Q) {
            payoffs[v][e] = NonNegativeFixed::from_num((v * (2 * Q) + e + 1) as u32);
        }
    }

    let mut post_call_weights = pre_call_weights;
    let mut last_switch_t = 0u32;
    let mut prev_mode = 0u32;

    let blended = allocate(
        &OBJECT_REGISTRY,
        &LENS_REGISTRY,
        &LAMBDA,
        ETA,
        &parent,
        &mut post_call_weights,
        &payoffs,
        // A non-zero zeta (within `ZETA_W_MAX`'s admission envelope) /
        // epsilon_kappa=0 admits the MWU update on every (v, q_idx) slot
        // with children and non-zero payoff, so kappa's divergence guard
        // doesn't accidentally suppress it here.
        NonNegativeFixed::from_bits(328), // ~0.005, under ZETA_W_MAX (0.0125)
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

    // Confirm the MWU update actually fired -- otherwise this test would be
    // just as degenerate as the all-zero-payoffs case it's meant to
    // improve on.
    assert_ne!(
        pre_call_weights, post_call_weights,
        "expected the MWU update to change local_weights for non-zero, \
         differentiated payoffs -- test setup is degenerate if this fires"
    );

    let reconstruct = |weights: &[[NonNegativeFixed; 2 * Q]; N]| {
        let mut pi_combined = [NonNegativeFixed::ZERO; N];
        for k in 0..K {
            for q_idx in 0..Q {
                let single = allocate_single_lens(
                    &OBJECT_REGISTRY,
                    &LENS_REGISTRY,
                    k,
                    q_idx,
                    &parent,
                    weights,
                )
                .unwrap();
                for i in 0..N {
                    pi_combined[i] += LAMBDA[k][q_idx] * single[i];
                }
            }
        }
        pi_combined
    };

    let pi_combined_from_post_call = reconstruct(&post_call_weights);
    let pi_combined_from_pre_call = reconstruct(&pre_call_weights);

    // Half 1: the pre-call snapshot genuinely diverges from what the blend
    // actually used.
    let any_pre_call_divergence = (0..N)
        .any(|i| pi_combined_from_pre_call[i].to_bits() != pi_combined_from_post_call[i].to_bits());
    assert!(
        any_pre_call_divergence,
        "expected the pre-call weights snapshot to diverge from the blend's \
         actual pi_combined once the MWU update fired -- got identical \
         reconstructions: {pi_combined_from_pre_call:?}"
    );

    // Half 2: reconstructing from the post-call (post-MWU-update) snapshot
    // reproduces `pi_combined` -- same pricing-formula inversion as
    // `blend_equals_the_lambda_weighted_sum_of_single_lens_results`, same
    // measured tolerance. Nodes 0, 1, 2 are internal in
    // `depth_two_tree_parent`'s shape; only the 5 leaves (3, 4, 5, 6, 7)
    // participate in `priced_sum`/the explore-floor blend, since
    // `allocate_in` only ever writes leaf `pi_res` slots.
    const LEAVES: [usize; 5] = [3, 4, 5, 6, 7];
    let mut priced_sum = NonNegativeFixed::ZERO;
    for &i in &LEAVES {
        priced_sum += pi_combined_from_post_call[i];
    }
    let nl_recip = NonNegativeFixed::from_bits(13107); // LEAF_RECIP[5] == 1/5

    let mut expected = [NonNegativeFixed::ZERO; N];
    for &i in &LEAVES {
        let p_mu = pi_combined_from_post_call[i] / priced_sum;
        expected[i] = ETA * nl_recip + (NonNegativeFixed::ONE - ETA) * p_mu;
    }

    const RECONSTRUCTION_TOLERANCE_BITS: i64 = 8;
    for i in 0..N {
        let diff = (blended[i].to_bits() as i64 - expected[i].to_bits() as i64).abs();
        assert!(
            diff <= RECONSTRUCTION_TOLERANCE_BITS,
            "object {i}: blended={:?} expected_from_post_call_reconstruction={:?} diff={diff}",
            blended[i],
            expected[i]
        );
    }
}
