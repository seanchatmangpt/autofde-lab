//! BCINR-CMCA-H: closing the remaining correspondence invariants named by
//! `~/mfw/mfw-theory/MFW/CMCA/Semantics/CorrespondenceManifest.lean`
//! (`MFW-CMCA-005`), which lists 7 invariants "a future Rust checkpoint
//! must be able to test" and names this checkpoint explicitly.
//! `BCINR-CMCA-E` (`crates/bcinr-cmca/tests/lean_correspondence.rs`,
//! untouched by this file) already closed invariants 1 (exact output
//! equality, on `[1,2,3,4]`), partially 2 (exact refusal identity -- one
//! constructor, `ZeroMassUnderNegativeLens`), and 5 (`q=0` sibling-vs-
//! support discrimination). This file closes the remaining ones:
//!
//! 3. Positive-scale invariance (`escort_scale_invariant`).
//! 4. Permutation equivalence (`escort_perm_equivariant`).
//! 6. Pairwise concentration across ordered lenses
//!    (`escort_pairwise_concentration_strict`, the `[1,2,10]` odds witnesses).
//! 7. Strict extrema movement on `[1,2,10]`
//!    (`escort_max_mass_share_strictly_increasing`,
//!    `escort_min_mass_share_strictly_decreasing`).
//!
//! Plus two new small-field witnesses the Lean side added specifically for
//! this checkpoint ("had no prior coverage" per `CorrespondenceManifest.lean`):
//! `escort_proportional_singleton` (`[1]`) and `escort_equal_pair_uniform`
//! (`[1,1]`).
//!
//! **Not closed here, disclosed honestly rather than rounded up**:
//! invariant 2 (exact refusal identity) remains partial -- only
//! `ZeroMassUnderNegativeLens` is checked (by E); `emptyDomain`,
//! `zeroSupport`, and `zeroPartitionSum` witnesses are not exercised by
//! either file. `allocator::power`'s fractional path remains out of scope
//! (per E's own disclosure: ~1.07% drift at `q=3`, no error-bound theorem
//! exists on the Lean side to check against).
//!
//! Every literal value below was read directly from
//! `~/mfw/mfw-theory/MFW/CMCA/Semantics/Escort.lean` in this session
//! (lines 340-409 for the structural permutation/scale theorems, 1397-1560
//! for the `[1,2,10]` golden vectors and odds/extrema witnesses) -- not
//! transcribed from a summary, not assumed.
//!
//! # Non-interference
//!
//! Same law as E's file: every test here calls a production function and
//! asserts on its return value. Nothing writes a file, calls `ggen`, or
//! mutates state the functions under test depend on. No Lean build/run is
//! performed anywhere in this file.

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::cascade::escort_weight;
use bcinr_cmca::fixed::NonNegativeFixed;

fn mass(x: f64) -> NonNegativeFixed {
    NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
}

/// Same tolerance as E's file, reused rather than re-derived (same
/// arithmetic shape: a handful of `saturating_mul`/`saturating_div`
/// steps, not an iterative approximation).
const TOL_BITS: i64 = 50;

fn approx_eq(a: NonNegativeFixed, b: NonNegativeFixed, tol_bits: i64) -> bool {
    (a.to_bits() as i64 - b.to_bits() as i64).abs() < tol_bits
}

fn lt(a: NonNegativeFixed, b: NonNegativeFixed) -> bool {
    a.to_bits() < b.to_bits()
}

/// Identical to E's `normalized_shares`: compute `escort_weight` at every
/// position for the given integer lens, then normalize by hand (sum, then
/// divide) -- `escort_distribution`'s own dispatch is never exercised
/// here, only the primitive.
fn normalized_shares(masses: &[NonNegativeFixed], lens: i32) -> Vec<NonNegativeFixed> {
    let weights: Vec<NonNegativeFixed> = masses
        .iter()
        .enumerate()
        .map(|(i, &m)| escort_weight(m, lens, i).unwrap())
        .collect();
    let mut sum = NonNegativeFixed::ZERO;
    for &w in &weights {
        sum += w;
    }
    weights.into_iter().map(|w| w / sum).collect()
}

fn shares_of(masses_f64: &[f64], lens: i32) -> Vec<NonNegativeFixed> {
    let m: Vec<NonNegativeFixed> = masses_f64.iter().copied().map(mass).collect();
    normalized_shares(&m, lens)
}

fn assert_matches_golden(who: &str, lens: i32, masses: &[f64], golden: &[f64]) {
    let shares = shares_of(masses, lens);
    assert_eq!(shares.len(), golden.len(), "{who}: length mismatch");
    for (i, (&got, &want)) in shares.iter().zip(golden.iter()).enumerate() {
        let expected = mass(want);
        assert!(
            approx_eq(got, expected, TOL_BITS),
            "{who}[{i}]: got {got:?} ({:.6}), Lean golden vector expects {want:.6} ({expected:?})",
            got.to_bits() as f64 / 65536.0
        );
    }
}

const LENSES: [i32; 5] = [-2, -1, 0, 1, 2];

// ---------------------------------------------------------------------
// Manifest invariant 3: positive-scale invariance.
// `escort_scale_invariant (lens) (masses) (c) (hc : 0 < c) :
//    escort lens (masses.map (c * ·)) = escort lens masses`
// A structural property: checked against Rust's own output on both
// sides, no new golden literals needed.
// ---------------------------------------------------------------------

#[test]
fn escort_weight_is_scale_invariant_for_every_lens() {
    let base = [1.0, 2.0, 3.0, 4.0];
    let scaled: Vec<f64> = base.iter().map(|x| x * 3.0).collect();

    for &lens in &LENSES {
        let base_shares = shares_of(&base, lens);
        let scaled_shares = shares_of(&scaled, lens);
        for i in 0..base_shares.len() {
            assert!(
                approx_eq(base_shares[i], scaled_shares[i], TOL_BITS),
                "lens={lens}, index {i}: base share {:?} vs 3x-scaled share {:?} \
                 -- escort_scale_invariant requires these to match",
                base_shares[i],
                scaled_shares[i]
            );
        }
    }
}

// ---------------------------------------------------------------------
// Manifest invariant 4: permutation equivalence.
// Reuses Lean's own nontrivial witness permutation,
// `perm_1234_4132 : [1,2,3,4].Perm [4,1,3,2]` (deliberately non-identity,
// non-reversal, per Lean's own doc comment on why this permutation was
// chosen over a weaker special case).
// ---------------------------------------------------------------------

#[test]
fn escort_weight_permutes_correspondingly_for_every_lens() {
    let original = [1.0, 2.0, 3.0, 4.0];
    let permuted = [4.0, 1.0, 3.0, 2.0];
    // permuted[i] == original[perm_index[i]]
    let perm_index = [3usize, 0, 2, 1];

    for &lens in &LENSES {
        let original_shares = shares_of(&original, lens);
        let permuted_shares = shares_of(&permuted, lens);
        for i in 0..permuted_shares.len() {
            assert!(
                approx_eq(permuted_shares[i], original_shares[perm_index[i]], TOL_BITS),
                "lens={lens}, permuted index {i} (maps to original index {}): \
                 permuted share {:?} vs original share {:?} \
                 -- escort_perm_equivariant requires the permuted output to be \
                 the original output permuted the same way",
                perm_index[i],
                permuted_shares[i],
                original_shares[perm_index[i]]
            );
        }
    }
}

// ---------------------------------------------------------------------
// [1,2,10] golden vectors -- exact Lean values, `Escort.lean` lines
// 1408-1560. Position 0 = mass 1, position 2 = mass 10.
// ---------------------------------------------------------------------

const FIELD_1_2_10: [f64; 3] = [1.0, 2.0, 10.0];

#[test]
fn escort_weight_matches_lean_golden_vectors_on_1_2_10() {
    assert_matches_golden(
        "rare2",
        -2,
        &FIELD_1_2_10,
        &[50.0 / 63.0, 25.0 / 126.0, 1.0 / 126.0],
    );
    assert_matches_golden(
        "rare1",
        -1,
        &FIELD_1_2_10,
        &[5.0 / 8.0, 5.0 / 16.0, 1.0 / 16.0],
    );
    assert_matches_golden(
        "coverage",
        0,
        &FIELD_1_2_10,
        &[1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
    );
    assert_matches_golden(
        "proportional",
        1,
        &FIELD_1_2_10,
        &[1.0 / 13.0, 2.0 / 13.0, 10.0 / 13.0],
    );
    assert_matches_golden(
        "exploit2",
        2,
        &FIELD_1_2_10,
        &[1.0 / 105.0, 4.0 / 105.0, 100.0 / 105.0],
    );
}

// ---------------------------------------------------------------------
// Manifest invariant 6: pairwise concentration across ordered lenses.
// `escort_pairwise_concentration_strict` on the adjacent chain
// rare2 < rare1 < coverage < proportional < exploit2, the full span
// rare2 -> exploit2, and the nontrivial middle pair (positions 1,2) --
// 6 checks, matching Lean's 6 named odds witnesses exactly.
// ---------------------------------------------------------------------

fn odds_strict(
    a: &[NonNegativeFixed],
    b: &[NonNegativeFixed],
    pos_lo: usize,
    pos_hi: usize,
) -> bool {
    // a[pos_lo] * b[pos_hi] < b[pos_lo] * a[pos_hi]
    let lhs = (a[pos_lo].to_bits() as u128) * (b[pos_hi].to_bits() as u128);
    let rhs = (b[pos_lo].to_bits() as u128) * (a[pos_hi].to_bits() as u128);
    lhs < rhs
}

#[test]
fn escort_weight_pairwise_concentration_holds_across_the_lens_chain_on_1_2_10() {
    let rare2 = shares_of(&FIELD_1_2_10, -2);
    let rare1 = shares_of(&FIELD_1_2_10, -1);
    let coverage = shares_of(&FIELD_1_2_10, 0);
    let proportional = shares_of(&FIELD_1_2_10, 1);
    let exploit2 = shares_of(&FIELD_1_2_10, 2);

    // escort_odds_adjacent_rare2_rare1_1_10:
    //   rare1[0] * rare2[2] < rare2[0] * rare1[2]
    // (the more-extreme lens of the pair is `a`, per this file's
    // `odds_strict(a, b, ..)` = `a[i]*b[j] < b[i]*a[j]` convention --
    // confirmed against the exact Lean statement, not assumed; an
    // earlier draft had every call in this test backwards and this
    // exact test caught it, see the falsifier note below).
    assert!(
        odds_strict(&rare1, &rare2, 0, 2),
        "rare2 -> rare1 adjacent odds"
    );
    // escort_odds_adjacent_rare1_coverage_1_10:
    //   coverage[0] * rare1[2] < rare1[0] * coverage[2]
    assert!(
        odds_strict(&coverage, &rare1, 0, 2),
        "rare1 -> coverage adjacent odds"
    );
    // escort_odds_adjacent_coverage_proportional_1_10:
    //   proportional[0] * coverage[2] < coverage[0] * proportional[2]
    assert!(
        odds_strict(&proportional, &coverage, 0, 2),
        "coverage -> proportional adjacent odds"
    );
    // escort_odds_adjacent_proportional_exploit2_1_10:
    //   exploit2[0] * proportional[2] < proportional[0] * exploit2[2]
    assert!(
        odds_strict(&exploit2, &proportional, 0, 2),
        "proportional -> exploit2 adjacent odds"
    );
    // escort_odds_span_rare2_exploit2_1_10:
    //   exploit2[0] * rare2[2] < rare2[0] * exploit2[2]
    assert!(
        odds_strict(&exploit2, &rare2, 0, 2),
        "rare2 -> exploit2 full-span odds"
    );
    // escort_odds_middle_pair_proportional_exploit2_2_10 (positions 1,2):
    //   exploit2[1] * proportional[2] < proportional[1] * exploit2[2]
    assert!(
        odds_strict(&exploit2, &proportional, 1, 2),
        "proportional -> exploit2 middle-pair odds (positions 1,2)"
    );
}

// ---------------------------------------------------------------------
// Manifest invariant 7: strict extrema movement on [1,2,10].
// Position 2 (mass 10) is the field's unique maximum; position 0
// (mass 1) is its unique minimum.
// ---------------------------------------------------------------------

#[test]
fn escort_weight_extrema_move_strictly_from_proportional_to_exploit2_on_1_2_10() {
    let rare2 = shares_of(&FIELD_1_2_10, -2);
    let proportional = shares_of(&FIELD_1_2_10, 1);
    let exploit2 = shares_of(&FIELD_1_2_10, 2);

    // escort_max_share_strict_proportional_exploit2_1_2_10
    assert!(
        lt(proportional[2], exploit2[2]),
        "max share (position 2) must strictly increase from proportional to exploit2 -- \
         got proportional={:?}, exploit2={:?}",
        proportional[2],
        exploit2[2]
    );
    // escort_min_share_strict_proportional_exploit2_1_2_10
    assert!(
        lt(exploit2[0], proportional[0]),
        "min share (position 0) must strictly decrease from proportional to exploit2 -- \
         got proportional={:?}, exploit2={:?}",
        proportional[0],
        exploit2[0]
    );
    // escort_max_share_span_rare2_exploit2_1_2_10
    assert!(
        lt(rare2[2], exploit2[2]) || approx_eq(rare2[2], exploit2[2], 0),
        "full-span max share must be nondecreasing from rare2 to exploit2 -- \
         got rare2={:?}, exploit2={:?}",
        rare2[2],
        exploit2[2]
    );
}

// ---------------------------------------------------------------------
// Two new small-field witnesses (Lean's own "had no prior coverage"
// additions for this checkpoint).
// ---------------------------------------------------------------------

#[test]
fn escort_weight_matches_lean_singleton_and_equal_pair_witnesses() {
    // escort_proportional_singleton : escort .proportional [1] = .ok [1]
    assert_matches_golden("proportional singleton", 1, &[1.0], &[1.0]);

    // escort_equal_pair_uniform : every lens on [1,1] = .ok [1/2, 1/2]
    for &lens in &LENSES {
        assert_matches_golden("equal pair", lens, &[1.0, 1.0], &[0.5, 0.5]);
    }
}

// ---------------------------------------------------------------------
// Falsifiers -- each was actually applied to this file, run, confirmed
// to fail against the real function, then reverted. Not kept as
// permanent (skipped) tests, matching E's own discipline.
//
// F1 (scale, non-uniform multiplier): `scaled` was built with element 0
// multiplied by 3 and every other element by 5 (breaking the "same c
// for every mass" precondition `escort_scale_invariant` requires).
// `escort_weight_is_scale_invariant_for_every_lens` failed immediately
// at lens=-2, index 0 (got base share 46035/65536 vs "scaled" share
// 56873/65536, well outside the 50-bit tolerance) -- confirms the real
// test is sensitive to genuine non-scale-invariant mutations, not
// vacuously passing.
// F2 (permutation, no reindexing): `original_shares[perm_index[i]]` was
// replaced with `original_shares[i]` (comparing the permuted output to
// the unpermuted output position-for-position instead of through the
// permutation). `escort_weight_permutes_correspondingly_for_every_lens`
// failed at the very first checked index (lens=-2, permuted index 0,
// which maps to original index 3 -- position 0 is definitely not a
// fixed point of `[1,2,3,4] -> [4,1,3,2]`) -- confirms the reindexing in
// the real test is load-bearing, not decorative.
// F3 (odds direction, one call reverted): the first adjacent-pair call
// was reverted from the fixed `odds_strict(&rare1, &rare2, 0, 2)` back
// to the pre-fix `odds_strict(&rare2, &rare1, 0, 2)`.
// `escort_weight_pairwise_concentration_holds_across_the_lens_chain_on_1_2_10`
// failed at that exact assertion ("rare2 -> rare1 adjacent odds") --
// confirms the concentration check discriminates argument order/
// direction, not just that some strict inequality holds between the two
// vectors. (This is also the literal bug this test file caught in
// itself during development: the first draft of every one of the 6 odds
// calls had `a`/`b` swapped relative to the exact Lean statement --
// fixed by reading `Escort.lean`'s theorem statements directly and
// re-deriving the correct argument order for each pair, not by loosening
// the assertion.)
// ---------------------------------------------------------------------
