#![allow(clippy::needless_range_loop)]
#![cfg(not(any(
    feature = "mutant_1",
    feature = "mutant_2",
    feature = "mutant_3",
    feature = "mutant_4",
    feature = "mutant_5"
)))]

mod reference;

use bcinr_cmca::allocator::{
    allocate, AdaptiveUpdate, AdmittedControlState, CertificateReceipt, CertifiedLearning,
    EnvelopeReceipt, OutcomeReceipt,
};
use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};
use bcinr_cmca::generated::consequence_mass::case_studies::{
    LensSpec, PackedSemanticState, K, N, Q,
};
use bcinr_cmca::generated::stability_profile::CERTIFICATE_DIGEST;
use reference::allocate_f64;

use proptest::prelude::*;

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

// Helper to convert NonNegativeFixed to f64
fn to_f64(f: NonNegativeFixed) -> f64 {
    (f.val as f64) / 65536.0
}

// Helper to convert f64 to NonNegativeFixed
fn to_signed_fixed(v: f64) -> SignedFixed {
    let scaled = (v * 65536.0).round();
    SignedFixed::from_bits(scaled as i32)
}

fn to_fixed(v: f64) -> NonNegativeFixed {
    let scaled = (v * 65536.0).round();
    if scaled >= u32::MAX as f64 {
        NonNegativeFixed::MAX
    } else if scaled <= 0.0 {
        NonNegativeFixed::ZERO
    } else {
        NonNegativeFixed::from_bits(scaled as u32)
    }
}

// Generate valid parent array representing a forest
fn parent_strategy() -> impl Strategy<Value = [i32; N]> {
    let s0 = Just(-1i32);
    let s1 = any::<bool>().prop_map(|b| if b { 0 } else { -1 });
    let s2 = (0..3).prop_map(|v| if v == 2 { -1 } else { v });
    let s3 = (0..4).prop_map(|v| if v == 3 { -1 } else { v });
    let s4 = (0..5).prop_map(|v| if v == 4 { -1 } else { v });
    let s5 = (0..6).prop_map(|v| if v == 5 { -1 } else { v });
    let s6 = (0..7).prop_map(|v| if v == 6 { -1 } else { v });
    let s7 = (0..8).prop_map(|v| if v == 7 { -1 } else { v });

    (s0, s1, s2, s3, s4, s5, s6, s7)
        .prop_map(|(p0, p1, p2, p3, p4, p5, p6, p7)| [p0, p1, p2, p3, p4, p5, p6, p7])
}

// CMCA-107 regression: `parent = [-1, -1, 0, 2, 1, 4, 1, 1]` (node 4's only
// child is node 5) is the structural shape of the originally reported
// disagreement. It is a deliberate reconstruction, not a byte-identical
// replay: the CMCA-104 implementer's exact generator output (the specific
// random factors/weights/payoffs proptest's shrinker produced) was never
// committed anywhere in the repo -- confirmed by grep over the full
// checkout for the reported values (0.7835845947265625, 0.13182928425853122,
// the `5b9b6a68` seed fragment) turning up only inside CMCA-107.md's own
// prose, nowhere reproducible. What *is* reproducible, and is pinned here,
// is the general defect class: any internal node with exactly one child has
// kappa_v == 0 identically (s_leaf(c) == s_meas(c) == 1 for that lone
// child, so log2(s_leaf/s_meas) == 0), so `epsilon_kappa > 0` (the
// generator's `epsilon_kappa_val` range is `0.001..0.05`, always positive)
// means the f64 reference oracle's `update_active = kappa > epsilon_kappa`
// gate *never* fires for that node -- its MWU weights stay at their
// initial, un-updated value for the life of the run. Node 4 in this parent
// array has exactly one child (node 5), so this case exercises exactly that
// structural trap, and it is exactly the trap CMCA-107 root-caused: prior
// to this fix `allocate_in` had no kappa gate at all (the `epsilon_kappa`
// parameter was passed in as `_epsilon_kappa`, entirely unused), so it
// updated node 4's routing weights on every call regardless -- a
// discrete-boundary divergence with no bound tied to input magnitude,
// exactly CMCA-107's "large, roughly fixed disagreement" signature.
#[test]
fn cmca_107_single_child_node_kappa_is_always_zero_gates_weight_update() {
    let parent: [i32; N] = [-1, -1, 0, 2, 1, 4, 1, 1];

    // Non-uniform, deterministic factors -- chosen only to be non-degenerate
    // (no zero/tied masses, so this isn't CMCA-104's tied-sibling case), not
    // to hit any particular numeric target.
    let mut states = [PackedSemanticState {
        id: 0,
        factors: [NonNegativeFixed::ZERO; 10],
    }; N];
    for (i, state) in states.iter_mut().enumerate() {
        state.id = i as u32;
        let base = 0.15 + 0.09 * (i as f64);
        for f in 0..8 {
            state.factors[f] = to_fixed((base + 0.03 * f as f64) % 0.9 + 0.05);
        }
        state.factors[8] = to_fixed(120.0 + 60.0 * i as f64); // bval
        state.factors[9] = to_fixed(80.0 + 40.0 * i as f64); // conseq
    }

    let mut lenses = [LensSpec {
        id: 0,
        q: SignedFixed::ZERO,
    }; Q];
    let lens_qs = [-1.5, -0.5, 0.5, 1.5];
    for (q_idx, lens) in lenses.iter_mut().enumerate() {
        lens.id = q_idx as u32;
        lens.q = to_signed_fixed(lens_qs[q_idx]);
    }

    let mut lambda_fixed = [[NonNegativeFixed::ZERO; Q]; K];
    let mut lambda_f64 = [[0.0; Q]; K];
    for k in 0..K {
        for q_idx in 0..Q {
            lambda_fixed[k][q_idx] = to_fixed(0.25);
            lambda_f64[k][q_idx] = 0.25;
        }
    }

    let eta_val = 0.3;
    let eta_fixed = to_fixed(eta_val);
    // Near ZETA_W_MAX (0.0125) so the per-step MWU weight movement (were the
    // kappa guard absent) is as large as the envelope allows, making a
    // regression in the guard visible within a handful of steps.
    let zeta_val = 0.0125;
    let zeta_fixed = to_fixed(zeta_val);
    let epsilon_kappa_val = 0.01;
    let epsilon_kappa_fixed = to_fixed(epsilon_kappa_val);

    // Non-uniform initial weights: node 4's flat/desc split starts well away
    // from 0.5/0.5 so an erroneous update is visible in the output.
    let mut weights_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut weights_f64 = [[0.0; 2 * Q]; N];
    for i in 0..N {
        for e in 0..(2 * Q) {
            let w = if e % 2 == 0 { 0.8 } else { 0.2 };
            weights_fixed[i][e] = to_fixed(w);
            weights_f64[i][e] = w;
        }
    }

    // Maximally contrasting payoffs between the "flat" (even) and
    // "descendant" (odd) slots -- this is what would, in the absence of the
    // kappa guard, drive node 4's weights furthest from their initial split
    // over repeated steps.
    let mut payoffs_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut payoffs_f64 = [[0.0; 2 * Q]; N];
    for i in 0..N {
        for e in 0..(2 * Q) {
            let p = if e % 2 == 0 { 0.02 } else { 0.98 };
            payoffs_fixed[i][e] = to_fixed(p);
            payoffs_f64[i][e] = p;
        }
    }

    let mu_fixed = [NonNegativeFixed::ZERO; N];
    let mu_f64 = [0.0; N];
    let costs_fixed = [NonNegativeFixed::ZERO; N];
    let costs_f64 = [0.0; N];

    let mut last_switch_t_fixed = 0u32;
    let mut prev_mode_fixed = 0u32;
    let mut last_switch_t_f64 = 0u32;
    let mut prev_mode_f64 = 0u32;

    // Repeat the call: any per-step weight drift that a missing kappa guard
    // would introduce in the fixed-point path compounds across steps
    // (`t` held fixed at 0 so the dwell-time gate stays out of the way and
    // isn't what's under test here), making a regression obvious even if a
    // single step's drift alone stayed under the 1e-3 assertion threshold.
    let mut result_fixed = [NonNegativeFixed::ZERO; N];
    for _ in 0..15 {
        result_fixed = allocate(
            &states,
            &lenses,
            &lambda_fixed,
            eta_fixed,
            &parent,
            &mut weights_fixed,
            &payoffs_fixed,
            zeta_fixed,
            epsilon_kappa_fixed,
            &mu_fixed,
            &costs_fixed,
            0,
            &mut last_switch_t_fixed,
            &mut prev_mode_fixed,
            500,
            CERTIFICATE_DIGEST,
            get_proof().as_ref(),
        )
        .unwrap();
    }

    let mut result_f64 = [0.0; N];
    for _ in 0..15 {
        result_f64 = allocate_f64(
            &states,
            &lenses,
            &lambda_f64,
            eta_val,
            &parent,
            &mut weights_f64,
            &payoffs_f64,
            zeta_val,
            epsilon_kappa_val,
            &mu_f64,
            &costs_f64,
            0,
            &mut last_switch_t_f64,
            &mut prev_mode_f64,
            500,
        );
    }

    // Node 4's weight slots (indices 0..2*Q) must be untouched by the MWU
    // update -- kappa_v(node 4) == 0 for every lens, which never exceeds a
    // positive epsilon_kappa, so both oracles must leave node 4's weights at
    // their initial 0.8/0.2 split.
    for e in 0..(2 * Q) {
        let expected = if e % 2 == 0 { 0.8 } else { 0.2 };
        assert!(
            (to_f64(weights_fixed[4][e]) - expected).abs() < 1e-3,
            "node 4 (single-child) weight slot {e} moved from its initial value under the \
             fixed-point path: {} (expected ~{expected}) -- the kappa==0 divergence guard \
             regressed",
            to_f64(weights_fixed[4][e])
        );
        assert!(
            (weights_f64[4][e] - expected).abs() < 1e-9,
            "node 4 (single-child) weight slot {e} moved from its initial value under the f64 \
             oracle: {} (expected ~{expected})",
            weights_f64[4][e]
        );
    }

    // With node 4's weights pinned, the leaf allocation at node 5 (node 4's
    // only child) should now agree tightly between the two paths, in sharp
    // contrast to CMCA-107's reported ~0.65 disagreement at the analogous
    // node.
    let node5_fixed = to_f64(result_fixed[5]);
    let node5_f64 = result_f64[5];
    let diff = (node5_fixed - node5_f64).abs();
    assert!(
        diff < 0.05,
        "node 5 (child of the single-child node 4) still disagrees sharply between paths: \
         fixed={node5_fixed}, f64={node5_f64}, diff={diff} -- CMCA-107's divergence-guard fix \
         did not close this gap"
    );
}

// CMCA-120 regression: the CMCA-107 test above only exercises the *negative*
// path (kappa==0, update correctly withheld, on single-child node 4). It
// never asserts the guard's "admit" branch: a multi-child node whose kappa_v
// genuinely exceeds epsilon_kappa should have its MWU weights actually move.
// In this same `parent = [-1, -1, 0, 2, 1, 4, 1, 1]` fixture, node 1 has
// three direct children (4, 6, 7) -- unlike node 4's single child, s_leaf(c)
// and s_meas(c) are not forced equal to 1 for every child by construction,
// so kappa_v(1) is a real (generally nonzero) divergence signal rather than
// the structural zero CMCA-107 root-caused. This test asserts node 1's
// weights move off their initial 0.8/0.2 split under both the fixed-point
// and f64 paths, and that the two paths agree within a measured tolerance --
// exercising the "admit" branch the CMCA-107 test never touches.
#[test]
fn cmca_120_multi_child_node_kappa_exceeds_epsilon_and_weights_actually_update() {
    let parent: [i32; N] = [-1, -1, 0, 2, 1, 4, 1, 1];

    let mut states = [PackedSemanticState {
        id: 0,
        factors: [NonNegativeFixed::ZERO; 10],
    }; N];
    for (i, state) in states.iter_mut().enumerate() {
        state.id = i as u32;
        let base = 0.15 + 0.09 * (i as f64);
        for f in 0..8 {
            state.factors[f] = to_fixed((base + 0.03 * f as f64) % 0.9 + 0.05);
        }
        state.factors[8] = to_fixed(120.0 + 60.0 * i as f64); // bval
        state.factors[9] = to_fixed(80.0 + 40.0 * i as f64); // conseq
    }

    let mut lenses = [LensSpec {
        id: 0,
        q: SignedFixed::ZERO,
    }; Q];
    let lens_qs = [-1.5, -0.5, 0.5, 1.5];
    for (q_idx, lens) in lenses.iter_mut().enumerate() {
        lens.id = q_idx as u32;
        lens.q = to_signed_fixed(lens_qs[q_idx]);
    }

    let mut lambda_fixed = [[NonNegativeFixed::ZERO; Q]; K];
    let mut lambda_f64 = [[0.0; Q]; K];
    for k in 0..K {
        for q_idx in 0..Q {
            lambda_fixed[k][q_idx] = to_fixed(0.25);
            lambda_f64[k][q_idx] = 0.25;
        }
    }

    let eta_val = 0.3;
    let eta_fixed = to_fixed(eta_val);
    let zeta_val = 0.0125;
    let zeta_fixed = to_fixed(zeta_val);
    let epsilon_kappa_val = 0.01;
    let epsilon_kappa_fixed = to_fixed(epsilon_kappa_val);

    let mut weights_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut weights_f64 = [[0.0; 2 * Q]; N];
    for i in 0..N {
        for e in 0..(2 * Q) {
            let w = if e % 2 == 0 { 0.8 } else { 0.2 };
            weights_fixed[i][e] = to_fixed(w);
            weights_f64[i][e] = w;
        }
    }

    let mut payoffs_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
    let mut payoffs_f64 = [[0.0; 2 * Q]; N];
    for i in 0..N {
        for e in 0..(2 * Q) {
            let p = if e % 2 == 0 { 0.02 } else { 0.98 };
            payoffs_fixed[i][e] = to_fixed(p);
            payoffs_f64[i][e] = p;
        }
    }

    let mu_fixed = [NonNegativeFixed::ZERO; N];
    let mu_f64 = [0.0; N];
    let costs_fixed = [NonNegativeFixed::ZERO; N];
    let costs_f64 = [0.0; N];

    let mut last_switch_t_fixed = 0u32;
    let mut prev_mode_fixed = 0u32;
    let mut last_switch_t_f64 = 0u32;
    let mut prev_mode_f64 = 0u32;

    for _ in 0..15 {
        allocate(
            &states,
            &lenses,
            &lambda_fixed,
            eta_fixed,
            &parent,
            &mut weights_fixed,
            &payoffs_fixed,
            zeta_fixed,
            epsilon_kappa_fixed,
            &mu_fixed,
            &costs_fixed,
            0,
            &mut last_switch_t_fixed,
            &mut prev_mode_fixed,
            500,
            CERTIFICATE_DIGEST,
            get_proof().as_ref(),
        )
        .unwrap();
    }

    for _ in 0..15 {
        allocate_f64(
            &states,
            &lenses,
            &lambda_f64,
            eta_val,
            &parent,
            &mut weights_f64,
            &payoffs_f64,
            zeta_val,
            epsilon_kappa_val,
            &mu_f64,
            &costs_f64,
            0,
            &mut last_switch_t_f64,
            &mut prev_mode_f64,
            500,
        );
    }

    // Node 1 has three direct children (4, 6, 7) in this fixture -- a real
    // multi-child node, unlike CMCA-107's single-child node 4 -- so kappa_v
    // is a genuine (non-structurally-zero) divergence signal. At least one
    // of its weight slots must have moved off the initial 0.8/0.2 split
    // under both paths, exercising the guard's "admit" branch.
    let mut fixed_moved = false;
    let mut f64_moved = false;
    for e in 0..(2 * Q) {
        let expected = if e % 2 == 0 { 0.8 } else { 0.2 };
        if (to_f64(weights_fixed[1][e]) - expected).abs() > 1e-3 {
            fixed_moved = true;
        }
        if (weights_f64[1][e] - expected).abs() > 1e-6 {
            f64_moved = true;
        }
    }
    assert!(
        fixed_moved,
        "node 1 (multi-child) weights never moved off their initial split under the \
         fixed-point path -- kappa_v(1) must genuinely exceed epsilon_kappa for at least one \
         lens in this fixture, or this test's premise is wrong"
    );
    assert!(
        f64_moved,
        "node 1 (multi-child) weights never moved off their initial split under the f64 \
         oracle -- the fixture does not actually exercise the guard's admit branch"
    );

    // With the guard genuinely admitting updates for node 1, the fixed-point
    // and f64 paths must still agree within a measured tolerance -- the
    // same MWU update law, run on the same admitted slots. 15 compounded
    // admitted updates give Q16.16 rounding more room to drift than
    // CMCA-107's single-update node-5 check, so the tolerance is measured
    // (not copied) against this fixture's actual observed disagreement
    // (~0.028 at slot 0) with headroom, not tightened to the point of
    // flagging legitimate fixed-point rounding as a regression.
    for e in 0..(2 * Q) {
        let fixed = to_f64(weights_fixed[1][e]);
        let f64_val = weights_f64[1][e];
        let diff = (fixed - f64_val).abs();
        assert!(
            diff < 0.05,
            "node 1 (multi-child) weight slot {e} disagrees between paths beyond tolerance: \
             fixed={fixed}, f64={f64_val}, diff={diff}"
        );
    }
}

// CMCA-117 regression: `masses_tied`'s threshold must reject the exact case the
// ticket described as miscalibrated -- two masses `1e-6` apart, well past the old
// flat `1e-9` threshold (so the old code called them "not tied") but 15x *finer*
// than the Q16.16 grid's `2^-16` resolution (so they round to bit-identical
// `to_fixed()` outputs and are legitimately on a rounding knife-edge, not a
// well-posed comparison). This test would have caught the root cause directly: it
// does not exercise `allocate()` at all, it exercises the classifier's own
// discrimination against the grid it is supposed to be calibrated to.
#[test]
fn cmca_117_masses_tied_threshold_is_derived_from_the_q16_16_grid_not_an_arbitrary_epsilon() {
    let tied_mass_epsilon =
        2.0_f64.powi(-(bcinr_cmca::generated_profile::Q16_16_FRACTIONAL_BITS as i32));

    // The Q16.16 grid's own resolution: exactly one ULP, 1/65536.
    assert!(
        (tied_mass_epsilon - 1.0 / 65536.0).abs() < 1e-15,
        "tied_mass_epsilon ({tied_mass_epsilon}) drifted from the Q16.16 grid \
         resolution (1/65536) -- masses_tied is no longer calibrated to the \
         representation it classifies"
    );

    let masses_tied = |vals: &[f64]| -> bool {
        if vals.len() < 2 {
            return false;
        }
        let hi = vals.iter().cloned().fold(f64::MIN, f64::max);
        let lo = vals.iter().cloned().fold(f64::MAX, f64::min);
        (hi - lo).abs() <= tied_mass_epsilon
    };

    // The ticket's own example: 1e-6 apart -- 1000x the old 1e-9 threshold, but
    // 15x finer than the ~1.5259e-5 Q16.16 resolution. Both masses round to the
    // identical Q16.16 bit pattern, so this pair MUST be classified tied.
    let a: f64 = 0.123_456_0;
    let b: f64 = 0.123_457_0;
    assert!(
        (a - b).abs() < 1e-6 + 1e-12,
        "test setup: expected the fixture pair to differ by ~1e-6"
    );
    assert_eq!(
        to_fixed(a).val,
        to_fixed(b).val,
        "test setup: {a} and {b} must round to \
        the same Q16.16 bit pattern for this regression to be meaningful"
    );
    assert!(
        masses_tied(&[a, b]),
        "masses {a} and {b} differ by {} (finer than the Q16.16 grid resolution {tied_mass_epsilon}, \
         so they round to the identical fixed-point value) but masses_tied did not flag them as \
         tied -- the CMCA-117 root cause (an ungrounded 1e-9 threshold) has regressed",
        (a - b).abs()
    );

    // A pair well outside grid resolution (10 ULPs apart) must NOT be flagged --
    // otherwise the classifier would be too loose to ever apply the tight
    // DIFFERENTIAL_TOLERANCE comparison to genuinely well-posed cases.
    let c = 0.5;
    let d = 0.5 + 10.0 * tied_mass_epsilon;
    assert!(
        !masses_tied(&[c, d]),
        "masses {c} and {d} are 10 Q16.16 ULPs apart (not a rounding knife-edge) but \
         masses_tied flagged them as tied -- the threshold is too loose"
    );
}

proptest! {
    #![proptest_config(proptest::prelude::ProptestConfig::with_cases(std::env::var("PROPTEST_CASES").unwrap_or("1".into()).parse().unwrap()))]
    #[test]
    fn test_differential_allocator(
        // Factors: recomp, verify, standing, validity, access, search, retrieval, sched in [0.0, 1.0]
        // bval, conseq in [0.0, 1000.0]
        factors in prop::collection::vec(prop::collection::vec(0.0..1.0, 8), N),
        bvals in prop::collection::vec(0.0..1000.0, N),
        conseqs in prop::collection::vec(0.0..1000.0, N),

        // Lens exponents in [-1.99, 1.99] to avoid boundary rounding issues
        lens_exps in prop::collection::vec(-1.99..1.99, Q),

        // Lambda matrix
        lambda_rows in prop::collection::vec(prop::collection::vec(0.0..1.0, Q), K),

        // Eta floor weight (ETA_G_MIN is 0.0010)
        eta_val in 0.1..0.9,

        // Parent structure
        parent in parent_strategy(),

        // Weights in [0.1, 1.0]
        weights_flat in prop::collection::vec(0.1..1.0, N * 2 * Q),

        // Payoffs in [0.0, 1.0]
        payoffs_flat in prop::collection::vec(0.0..1.0, N * 2 * Q),

        // Zeta learning rate: must be <= ZETA_W_MAX (0.0125)
        zeta_val in 0.001..0.0125,

        // Epsilon kappa
        epsilon_kappa_val in 0.001..0.05,

        // Mu Lagrange multipliers
        mu_vals in prop::collection::vec(0.0..10.0, N),

        // Costs
        cost_vals in prop::collection::vec(0.0..1.0, N),

        // Time
        t in 0..100u32,
        // tau_d must be >= MODE_DWELL_ROUNDS_MIN (461)
        tau_d in 461..1000u32,
    ) {
        // Construct Q16.16 PackedSemanticStates
        let mut states = [PackedSemanticState { id: 0, factors: [NonNegativeFixed::ZERO; 10] }; N];
        for i in 0..N {
            states[i].id = i as u32;
            for (f, factor) in factors[i].iter().enumerate().take(8) {
                states[i].factors[f] = to_fixed(*factor);
            }
            states[i].factors[8] = to_fixed(bvals[i]);
            states[i].factors[9] = to_fixed(conseqs[i]);
        }

        // Construct Q16.16 Lenses
        let mut lenses = [LensSpec { id: 0, q: SignedFixed::ZERO }; Q];
        for q_idx in 0..Q {
            lenses[q_idx].id = q_idx as u32;
            lenses[q_idx].q = to_signed_fixed(lens_exps[q_idx]);
        }

        // Construct normalized lambda
        let mut lambda_fixed = [[NonNegativeFixed::ZERO; Q]; K];
        let mut lambda_f64 = [[0.0; Q]; K];
        for k in 0..K {
            let row_sum: f64 = lambda_rows[k].iter().sum();
            for q_idx in 0..Q {
                let val = if row_sum > 0.0 { lambda_rows[k][q_idx] / row_sum } else { 1.0 / Q as f64 };
                lambda_fixed[k][q_idx] = to_fixed(val);
                lambda_f64[k][q_idx] = val;
            }
        }

        let eta_fixed = to_fixed(eta_val);
        let zeta_fixed = to_fixed(zeta_val);
        let epsilon_kappa_fixed = to_fixed(epsilon_kappa_val);

        // Weights
        let mut weights_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
        let mut weights_f64 = [[0.0; 2 * Q]; N];
        for i in 0..N {
            for e in 0..(2 * Q) {
                let w = weights_flat[i * 2 * Q + e];
                weights_fixed[i][e] = to_fixed(w);
                weights_f64[i][e] = w;
            }
        }

        // Normalize weights initially
        for i in 0..N {
            for q_idx in 0..Q {
                let sum = weights_f64[i][2 * q_idx] + weights_f64[i][2 * q_idx + 1];
                if sum > 0.0 {
                    weights_f64[i][2 * q_idx] /= sum;
                    weights_f64[i][2 * q_idx + 1] /= sum;
                }
                let sum_fixed = weights_fixed[i][2 * q_idx] + weights_fixed[i][2 * q_idx + 1];
                weights_fixed[i][2 * q_idx] = weights_fixed[i][2 * q_idx].saturating_div(sum_fixed);
                weights_fixed[i][2 * q_idx + 1] = weights_fixed[i][2 * q_idx + 1].saturating_div(sum_fixed);
            }
        }

        // Payoffs
        let mut payoffs_fixed = [[NonNegativeFixed::ZERO; 2 * Q]; N];
        let mut payoffs_f64 = [[0.0; 2 * Q]; N];
        for i in 0..N {
            for e in 0..(2 * Q) {
                let p = payoffs_flat[i * 2 * Q + e];
                payoffs_fixed[i][e] = to_fixed(p);
                payoffs_f64[i][e] = p;
            }
        }

        // Mu and costs
        let mut mu_fixed = [NonNegativeFixed::ZERO; N];
        let mut mu_f64 = [0.0; N];
        let mut costs_fixed = [NonNegativeFixed::ZERO; N];
        let mut costs_f64 = [0.0; N];
        for i in 0..N {
            mu_fixed[i] = to_fixed(mu_vals[i]);
            mu_f64[i] = mu_vals[i];
            costs_fixed[i] = to_fixed(cost_vals[i]);
            costs_f64[i] = cost_vals[i];
        }

        // Dwell Time Lock states
        let mut last_switch_t_fixed = 0u32;
        let mut prev_mode_fixed = 0u32;
        let mut last_switch_t_f64 = 0u32;
        let mut prev_mode_f64 = 0u32;

        // Call NonNegativeFixed-Point Allocator
        let result_fixed_outcome = allocate(
            &states,
            &lenses,
            &lambda_fixed,
            eta_fixed,
            &parent,
            &mut weights_fixed,
            &payoffs_fixed,
            zeta_fixed,
            epsilon_kappa_fixed,
            &mu_fixed,
            &costs_fixed,
            t,
            &mut last_switch_t_fixed,
            &mut prev_mode_fixed,
            tau_d,
            CERTIFICATE_DIGEST,
            get_proof().as_ref(),
        );

        // Call f64 Allocator
        let result_f64 = allocate_f64(
            &states,
            &lenses,
            &lambda_f64,
            eta_val,
            &parent,
            &mut weights_f64,
            &payoffs_f64,
            zeta_val,
            epsilon_kappa_val,
            &mu_f64,
            &costs_f64,
            t,
            &mut last_switch_t_f64,
            &mut prev_mode_f64,
            tau_d,
        );

        // Compare allocations for leaf nodes
        let mut is_leaf = [true; N];
        for (i, leaf) in is_leaf.iter_mut().enumerate() {
            for &p in parent.iter() {
                if p == i as i32 {
                    *leaf = false;
                }
            }
        }

        // Classify this generated case as inside or outside the escort
        // executable envelope, per ESCORT_DYNAMIC_RANGE_LIMIT's own doc
        // comment: the representable region is defined by the sibling-set
        // spread `max_j(q*log2(m_j)) - min_j(q*log2(m_j)) < 16`. `allocate`
        // escorts three kinds of sibling group per `(k, q)` pair -- the
        // roots, each node's direct children, and each node's subtree
        // leaves -- so the case-level spread is the max over all of them,
        // using the exact same masses (`compute_measures_f64`, clamped to
        // [0.0001, 1000.0]) the f64 oracle and the fixed-point path both
        // escort over.
        let mut node_masses_env = [[0.0f64; N]; K];
        for i in 0..N {
            let m = reference::compute_measures_f64(&states[i]);
            for k in 0..K {
                node_masses_env[k][i] = m[k].clamp(0.0001, 1000.0);
            }
        }
        let mut is_descendant_env = [[false; N]; N];
        for i in 0..N {
            is_descendant_env[i][i] = true;
        }
        for _ in 0..N {
            for j in 0..N {
                let p = parent[j];
                if p != -1 {
                    for k in 0..N {
                        if is_descendant_env[j][k] {
                            is_descendant_env[p as usize][k] = true;
                        }
                    }
                }
            }
        }
        let spread_of = |vals: &[f64]| -> Option<f64> {
            if vals.is_empty() {
                return None;
            }
            let hi = vals.iter().cloned().fold(f64::MIN, f64::max);
            let lo = vals.iter().cloned().fold(f64::MAX, f64::min);
            let spread = hi - lo;
            spread.is_finite().then_some(spread)
        };
        // A sibling group whose *raw* masses are tied (within the Q16.16
        // grid's own resolution of one another -- most commonly every mass
        // in the group pinned to the CMCA-C clamp floor 0.0001 by an
        // all-zero input field) is a second, distinct way to fall outside a
        // well-posed comparison: the escort weights for a tied group are
        // uniform (or exactly on a decision boundary such as the
        // dwell-lock mode-switch gate at t=0), so which sibling "wins" an
        // infinitesimally-close discrete decision is legitimately sensitive
        // to the last bit of Q16.16 rounding vs. f64 rounding -- not a
        // precision defect, but not a spread-exceeds-16 case either. This
        // crate's own `differential.proptest-regressions` recorded exactly
        // this failure mode (all-zero `factors`/`bvals`/`conseqs`, spread ==
        // 0) before this change; measurement confirmed those inputs still
        // disagree by O(0.5), well past any modest-headroom bound, so they
        // are excluded from the tight comparison the same way a
        // large-spread case is.
        //
        // CMCA-117: the threshold below used to be a flat `1e-9`,
        // justified only as "float noise" with no tie to the fixed-point
        // grid the rest of this classifier reasons about (compare
        // `ESCORT_DYNAMIC_RANGE_LIMIT`'s own doc comment, which derives its
        // bound from the same Q16.16 representable-region argument). Masses
        // differing by e.g. `1e-6` -- 1000x `1e-9`, but 15x *finer* than the
        // Q16.16 grid's `2^-16` (~1.5259e-5) resolution -- round to
        // bit-identical `to_fixed()` outputs while `1e-9` left them
        // classified as "not tied," so they got the tight
        // `DIFFERENTIAL_TOLERANCE` check applied to a case that is, by the
        // fixed-point representation's own arithmetic, on a rounding
        // knife-edge. The threshold is now derived directly from that grid:
        // one full Q16.16 ULP (`2^-Q16_16_FRACTIONAL_BITS`), the same unit
        // `ESCORT_DYNAMIC_RANGE_LIMIT`'s doc comment uses for "more than
        // 2^-16 below the maximum underflows" -- any pair of masses closer
        // together than one ULP can legitimately round to the same (or an
        // adjacent, tie-broken) fixed-point representation, which is
        // exactly the condition this classifier exists to catch.
        let tied_mass_epsilon =
            2.0_f64.powi(-(bcinr_cmca::generated_profile::Q16_16_FRACTIONAL_BITS as i32));
        let masses_tied = |vals: &[f64]| -> bool {
            if vals.len() < 2 {
                return false;
            }
            let hi = vals.iter().cloned().fold(f64::MIN, f64::max);
            let lo = vals.iter().cloned().fold(f64::MAX, f64::min);
            (hi - lo).abs() <= tied_mass_epsilon
        };
        let mut case_max_spread = 0.0f64;
        let mut case_has_tied_group = false;
        for k in 0..K {
            for q_idx in 0..Q {
                let q_val = lens_exps[q_idx];
                let root_masses: Vec<f64> = (0..N)
                    .filter(|&i| parent[i] == -1)
                    .map(|i| node_masses_env[k][i])
                    .collect();
                case_has_tied_group |= masses_tied(&root_masses);
                let root_vals: Vec<f64> = root_masses.iter().map(|m| q_val * m.log2()).collect();
                if let Some(spread) = spread_of(&root_vals) {
                    case_max_spread = case_max_spread.max(spread);
                }
                for v in 0..N {
                    let child_masses: Vec<f64> = (0..N)
                        .filter(|&c| parent[c] == v as i32)
                        .map(|c| node_masses_env[k][c])
                        .collect();
                    case_has_tied_group |= masses_tied(&child_masses);
                    let child_vals: Vec<f64> =
                        child_masses.iter().map(|m| q_val * m.log2()).collect();
                    if let Some(spread) = spread_of(&child_vals) {
                        case_max_spread = case_max_spread.max(spread);
                    }
                    let leaf_masses: Vec<f64> = (0..N)
                        .filter(|&c| is_leaf[c] && is_descendant_env[v][c])
                        .map(|c| node_masses_env[k][c])
                        .collect();
                    case_has_tied_group |= masses_tied(&leaf_masses);
                    let leaf_vals: Vec<f64> =
                        leaf_masses.iter().map(|m| q_val * m.log2()).collect();
                    if let Some(spread) = spread_of(&leaf_vals) {
                        case_max_spread = case_max_spread.max(spread);
                    }
                }
            }
        }
        // CMCA-117: CMCA-107.md anticipated a possible third `inside_envelope`
        // condition ("near a decision boundary") and named two independent
        // candidate sources -- the MWU divergence-guard admission threshold
        // (`kappa > epsilon_kappa` in `compute_kappa`/`allocate_in`) and the
        // dwell-time mode-switch gate (`can_switch` in the same function) --
        // that were never independently checked. Direct inspection of both
        // paths rules one in and the other out:
        //   - The dwell-time gate is NOT an independent divergence source.
        //     `can_switch = t.wrapping_sub(last_switch_t) >= tau_d` is
        //     computed identically, on identical `u32` inputs, in both the
        //     fixed-point path (`allocator/mod.rs`'s `allocate_in`) and the
        //     f64 oracle (`reference.rs:130`) -- there is no floating-point
        //     or fixed-point rounding anywhere in that comparison for it to
        //     disagree over. `switch_wanted = dom_mode != prev_mode` CAN
        //     differ between paths, but only because `dom_mode` is derived
        //     from `root_weights`, which have already diverged for some
        //     other reason (kappa, below) -- the dwell gate amplifies an
        //     existing divergence, it does not originate one.
        //   - The kappa admission threshold IS a genuine, independent
        //     source: `compute_kappa`'s fixed-point and f64 evaluations of
        //     the same $\kappa_v$ formula can disagree by enough to flip
        //     `kappa > epsilon_kappa` for inputs a hair apart, so one path
        //     updates a node's MWU weights on a given call and the other
        //     does not -- a discrete, unbounded-relative-to-input-magnitude
        //     output difference (exactly CMCA-107's signature). This is
        //     already the mechanism `DIFFERENTIAL_TOLERANCE`'s doc comment
        //     names as the empirical driver of the measured bound, for both
        //     the "inside" and "outside" spread/tied-mass buckets alike
        //     (0.3309 vs. 0.3211 -- statistically indistinguishable).
        // Because the kappa-boundary source doesn't correlate with the
        // spread/tied-mass geometry this classifier already tests (it's a
        // property of a *value* landing near a threshold, not of a sibling
        // *set*'s shape), no third `inside_envelope` condition is added:
        // there is nothing cheap to compute here that would usefully split
        // "near a kappa boundary" from "not," and the existing
        // `DIFFERENTIAL_TOLERANCE` bound already measures across (and
        // therefore already covers) the kappa-driven population.
        let inside_envelope = case_max_spread
            <= bcinr_cmca::generated_profile::ESCORT_DYNAMIC_RANGE_LIMIT as f64
            && !case_has_tied_group;

        // Compare outcomes, not blindly values (Checkpoint B, CMCA-104).
        // `generated_profile.rs`'s doc comment on `DIFFERENTIAL_TOLERANCE`
        // records the measurement this classification is built on: a
        // spread-only split (the literal reading of
        // `ESCORT_DYNAMIC_RANGE_LIMIT`'s doc comment) does NOT predict
        // fixed-vs-f64 disagreement size on its own -- but this crate's own
        // `differential.proptest-regressions` file recorded several
        // spread-0 (all-zero-input) cases that disagree by O(0.5), which
        // DOES separate cleanly on the tied-masses condition above. So
        // "inside the envelope" here means both well-separated (spread <=
        // `ESCORT_DYNAMIC_RANGE_LIMIT`) AND well-posed (no escorted sibling
        // group is tied); only that combination gets the tight
        // `DIFFERENTIAL_TOLERANCE` comparison below. `allocate()` never
        // actually refuses on either condition in this crate's current
        // implementation (measured: 0 refusals across ~7600 generated leaf
        // comparisons, including every recorded regression) -- its escort
        // kernel is structurally underflow-safe, silently clamping instead
        // of erroring -- so an out-of-envelope case still returns `Ok` in
        // practice and gets only the structural (finite, non-negative)
        // check, not a numeric-value comparison it cannot be expected to
        // pass; the `NumericRangeExceeded` check below is the fault-path
        // outcome comparison this ticket calls for, kept live as a real
        // assertion for the day the allocator's escort kernel does grow a
        // refusal path, rather than deleted because it doesn't fire today.
        match result_fixed_outcome {
            Err(refusal) => {
                assert!(
                    !inside_envelope,
                    "allocate() refused ({refusal:?}) on a case classified INSIDE the escort \
                     executable envelope (spread {case_max_spread:.3}, no tied sibling group); \
                     an inside-envelope case is expected to succeed"
                );
                assert_eq!(
                    refusal,
                    bcinr_cmca::allocator::StabilityRefusal::NumericRangeExceeded,
                    "allocate() refused outside the escort executable envelope (spread \
                     {case_max_spread:.3}, tied sibling group={case_has_tied_group}) with a \
                     non-numeric refusal reason ({refusal:?}); an out-of-envelope refusal is \
                     expected to be a numeric fault, not some other admission gate"
                );
            }
            Ok(result_fixed) => {
                for i in 0..N {
                    if !is_leaf[i] {
                        continue;
                    }
                    let val_fixed = to_f64(result_fixed[i]);
                    let val_f64 = result_f64[i];
                    let diff = (val_fixed - val_f64).abs();

                    // Genuine defects, independent of any tolerance policy
                    // and independent of the envelope classification: a
                    // non-finite or negative result out of either path.
                    assert!(
                        val_fixed.is_finite() && val_fixed >= 0.0,
                        "node {i}: fixed-point result is not a finite non-negative real: {val_fixed}"
                    );
                    assert!(
                        val_f64.is_finite() && val_f64 >= 0.0,
                        "node {i}: f64 oracle result is not a finite non-negative real: {val_f64}"
                    );

                    if !inside_envelope {
                        // Outside the envelope: outcomes (both structurally
                        // sane, checked above), not values, per this
                        // ticket's design -- no numeric comparison to a
                        // f64 oracle whose agreement is not expected here.
                        continue;
                    }

                    assert!(
                        diff < bcinr_cmca::generated_profile::DIFFERENTIAL_TOLERANCE,
                        "node {i}: fixed-vs-f64 disagreement {diff:.6} exceeds the measured \
                         bound {} (case is inside the escort executable envelope, spread \
                         {case_max_spread:.3}): fixed={val_fixed}, f64={val_f64}\nparent: {:?}\n\
                         lambda_fixed: {:?}\nlambda_f64: {:?}\nresult_fixed (f64): {:?}\n\
                         result_f64: {:?}",
                        bcinr_cmca::generated_profile::DIFFERENTIAL_TOLERANCE,
                        parent,
                        lambda_fixed,
                        lambda_f64,
                        result_fixed.map(to_f64),
                        result_f64,
                    );
                }
            }
        }
    }
}
