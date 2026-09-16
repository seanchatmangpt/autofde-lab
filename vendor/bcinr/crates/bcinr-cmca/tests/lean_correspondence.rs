//! BCINR-CMCA-E: the first real Rust/Lean correspondence checkpoint.
//!
//! `~/mfw/mfw-theory/MFW/CMCA/Semantics/Escort.lean` (`MFW-CMCA-001`
//! through `004B`, all `PARTIAL_ALIVE` -- kernel-accepted theorems,
//! constructive standing blocked by the `MFW-G0-CMCA-001` `Rat`-carrier
//! boundary, unrelated to anything checked here) proves exact `ℚ`-valued
//! golden vectors for `escort`/`uniformSiblingCoverage` on concrete
//! fields, at all five reference lenses. `BCINR-CMCA-D`
//! (`runtime_semantic_classification.rs`) classified what
//! `cascade::escort_weight` actually computes but never checked it
//! against those specific proved Lean values -- its own module doc says
//! as much: "Whether that agrees with `~/mfw`'s Lean crown is checkpoint
//! E's question, not D's."
//!
//! This file is that check. Scope, deliberately narrow (a first
//! checkpoint, not the whole correspondence surface): `cascade::escort_weight`
//! on the exact-integer-lens path only, against Lean's five named
//! `[1,2,3,4]` golden-vector theorems
//! (`escort_proportional_1234`/`escort_exploit2_1234`/`escort_coverage_1234`/
//! `escort_rare1_1234`/`escort_rare2_1234`), plus the zero-mass fork
//! witnesses (`uniform_sibling_coverage_013`/`support_coverage_013`) and
//! the negative-lens zero-mass refusal (`negative_zero_refuses`/
//! `negative_zero_refuses_rare2`). `allocator::power`'s fractional path
//! is out of scope here -- D already classified it as a bounded
//! approximation, not an exact-equality candidate (measured ~1.07% drift
//! at `q=3` against the exact path in `escort.rs`'s own test suite); an
//! error-bound theorem for it is future work, not this checkpoint's --
//! see `tests/power_error_bound.rs` for that follow-up checkpoint: an
//! EMPIRICAL (swept, not analytically derived) relative-error bound of
//! ~7.6%, measured over `|q| <= 4` (narrower than this crate's full
//! declared lens domain -- error was measured to scale with `|q|`, up to
//! ~36% at `|q|` near `MAX_LENS_MAGNITUDE`, so no single bound over the
//! whole domain would be a useful characterization).
//!
//! # Non-interference
//!
//! Same law as D's own file: every test here calls a production function
//! and asserts on its return value. Nothing writes a file, calls `ggen`,
//! or mutates state the functions under test depend on.

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::cascade::{escort_weight, CascadeRefusal};
use bcinr_cmca::fixed::NonNegativeFixed;

fn mass(x: f64) -> NonNegativeFixed {
    NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
}

/// Q16.16 tolerance for comparing a fixed-point normalized share against
/// an exact rational golden value converted the same way. `50` bits
/// (~0.00076 in real terms) matches `BCINR-CMCA-D`'s own tolerance,
/// chosen there for the same kind of comparison (a handful of
/// `saturating_mul`/`saturating_div` steps, not an iterative
/// approximation) -- reused here rather than re-derived, since the
/// arithmetic shape is the same.
const TOL_BITS: i64 = 50;

fn approx_eq(a: NonNegativeFixed, b: NonNegativeFixed, tol_bits: i64) -> bool {
    (a.to_bits() as i64 - b.to_bits() as i64).abs() < tol_bits
}

/// Compute `cascade::escort_weight` at every position of `masses` for the
/// given integer lens, then normalize by hand exactly the way
/// `escort_distribution` does (sum, then divide) -- this file never
/// calls `escort_distribution` itself, so the exact-integer-lens
/// dispatch inside it is not incidentally exercised; only the primitive
/// `escort_weight` is under test, matching this checkpoint's stated
/// scope.
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

fn assert_matches_golden(who: &str, lens: i32, masses: &[f64], golden: &[f64]) {
    let m: Vec<NonNegativeFixed> = masses.iter().copied().map(mass).collect();
    let shares = normalized_shares(&m, lens);
    assert_eq!(shares.len(), golden.len(), "{who}: length mismatch");
    for (i, (&got, &want)) in shares.iter().zip(golden.iter()).enumerate() {
        let expected = mass(want);
        assert!(
            approx_eq(got, expected, TOL_BITS),
            "{who}[{i}]: escort_weight(lens={lens}) got {got:?} ({:.6}), Lean golden vector expects {want:.6} ({expected:?})",
            got.to_bits() as f64 / 65536.0
        );
    }
}

// ---------------------------------------------------------------------
// Escort.lean's five [1,2,3,4] golden vectors -- exact `ℚ` values, kernel-
// checked (`escort_proportional_1234`, `escort_exploit2_1234`,
// `escort_coverage_1234`, `escort_rare1_1234`, `escort_rare2_1234`).
// ---------------------------------------------------------------------

#[test]
fn escort_weight_proportional_matches_lean_golden_vector_1234() {
    // escort_proportional_1234 : escort .proportional [1,2,3,4] = .ok [1/10,2/10,3/10,4/10]
    assert_matches_golden(
        "cascade::escort_weight(lens=1)",
        1,
        &[1.0, 2.0, 3.0, 4.0],
        &[1.0 / 10.0, 2.0 / 10.0, 3.0 / 10.0, 4.0 / 10.0],
    );
}

#[test]
fn escort_weight_exploit2_matches_lean_golden_vector_1234() {
    // escort_exploit2_1234 : escort .exploit2 [1,2,3,4] = .ok [1/30,4/30,9/30,16/30]
    assert_matches_golden(
        "cascade::escort_weight(lens=2)",
        2,
        &[1.0, 2.0, 3.0, 4.0],
        &[1.0 / 30.0, 4.0 / 30.0, 9.0 / 30.0, 16.0 / 30.0],
    );
}

#[test]
fn escort_weight_coverage_matches_lean_golden_vector_1234() {
    // escort_coverage_1234 : escort .coverage [1,2,3,4] = .ok [1/4,1/4,1/4,1/4]
    // Every mass here is strictly positive, so ReferenceLens.coverage and
    // uniformSiblingCoverage agree (Escort.lean's own module docstring:
    // both operations produce the same vector on a strictly positive
    // field -- they separate only on zero-containing input, tested
    // below). This witness alone cannot distinguish which one Rust's
    // q=0 realizes; that is exactly why the [0,1,3] fork test exists.
    assert_matches_golden(
        "cascade::escort_weight(lens=0)",
        0,
        &[1.0, 2.0, 3.0, 4.0],
        &[0.25, 0.25, 0.25, 0.25],
    );
}

#[test]
fn escort_weight_rare1_matches_lean_golden_vector_1234() {
    // escort_rare1_1234 : escort .rare1 [1,2,3,4] = .ok [12/25,6/25,4/25,3/25]
    assert_matches_golden(
        "cascade::escort_weight(lens=-1)",
        -1,
        &[1.0, 2.0, 3.0, 4.0],
        &[12.0 / 25.0, 6.0 / 25.0, 4.0 / 25.0, 3.0 / 25.0],
    );
}

#[test]
fn escort_weight_rare2_matches_lean_golden_vector_1234() {
    // escort_rare2_1234 : escort .rare2 [1,2,3,4] = .ok [144/205,36/205,16/205,9/205]
    assert_matches_golden(
        "cascade::escort_weight(lens=-2)",
        -2,
        &[1.0, 2.0, 3.0, 4.0],
        &[144.0 / 205.0, 36.0 / 205.0, 16.0 / 205.0, 9.0 / 205.0],
    );
}

// ---------------------------------------------------------------------
// The zero-mass fork: Escort.lean proves `ReferenceLens.coverage` and
// `uniformSiblingCoverage` disagree on [0,1,3] (support_coverage_013 vs.
// uniform_sibling_coverage_013). D already established Rust's q=0
// realizes sibling coverage on this exact field; this test ties that
// finding to Lean's specific proved value rather than to the classified
// vocabulary alone, and is the checkpoint's positive correspondence
// claim for q=0.
// ---------------------------------------------------------------------

#[test]
fn escort_weight_at_q_zero_matches_lean_uniform_sibling_coverage_not_support_coverage_013() {
    // uniform_sibling_coverage_013 : uniformSiblingCoverage [0,1,3] = .ok [1/3,1/3,1/3]
    // support_coverage_013         : escort .coverage [0,1,3] = .ok [0,1/2,1/2]
    // Rust matches the first, not the second -- asserted against both
    // concrete Lean values, not just the sibling-coverage label.
    let masses = [mass(0.0), mass(1.0), mass(3.0)];
    let shares = normalized_shares(&masses, 0);

    let sibling_coverage = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0];
    let support_coverage = [0.0, 0.5, 0.5];

    for (i, &got) in shares.iter().enumerate() {
        assert!(
            approx_eq(got, mass(sibling_coverage[i]), TOL_BITS),
            "index {i}: got {got:?}, expected Lean's uniformSiblingCoverage value {:?}",
            mass(sibling_coverage[i])
        );
        assert!(
            !approx_eq(got, mass(support_coverage[i]), TOL_BITS) || sibling_coverage[i] == support_coverage[i],
            "index {i}: got {got:?} unexpectedly also matches Lean's support_coverage_013 value {:?} -- \
             the two golden vectors are supposed to differ at this index",
            mass(support_coverage[i])
        );
    }
}

// ---------------------------------------------------------------------
// Negative-lens zero-mass refusal: Lean's negative_zero_refuses/
// negative_zero_refuses_rare2 refuse with zeroMassUnderNegativeLens.
// cascade::escort_weight's own ZeroMassUnderNegativeLens is the
// strongest 1:1 refusal-constructor match D found in the whole Rust
// surface -- checked directly here, not merely asserted in prose.
// ---------------------------------------------------------------------

#[test]
fn escort_weight_refuses_zero_mass_under_negative_lens_matching_lean() {
    // negative_zero_refuses      : escort .rare1 [0,1] = .error .zeroMassUnderNegativeLens
    // negative_zero_refuses_rare2: escort .rare2 [1,0] = .error .zeroMassUnderNegativeLens
    let zero = mass(0.0);
    let one = mass(1.0);

    match escort_weight(zero, -1, 0) {
        Err(CascadeRefusal::ZeroMassUnderNegativeLens { .. }) => {}
        other => panic!("rare1, zero mass: expected ZeroMassUnderNegativeLens, got {other:?}"),
    }
    match escort_weight(zero, -2, 1) {
        Err(CascadeRefusal::ZeroMassUnderNegativeLens { .. }) => {}
        other => panic!("rare2, zero mass: expected ZeroMassUnderNegativeLens, got {other:?}"),
    }
    // The nonzero sibling in the same field does not spuriously refuse.
    assert!(escort_weight(one, -1, 1).is_ok());
    assert!(escort_weight(one, -2, 0).is_ok());
}

// ---------------------------------------------------------------------
// Falsifiers -- each one is a deliberately wrong claim, run once to
// confirm it actually fails against the real function, then not kept as
// a permanent (skipped) test. Recorded here as comments with the exact
// observed failure, matching D's own falsifier discipline.
//
// F1 (wrong golden vector): asserting `escort_proportional_1234`'s
// vector against `lens=2` (exploit2) instead of `lens=1` failed with
// index 0 mismatch (got ~0.033 for exploit2's [1,4,9,16]/30, expected
// 0.1) -- confirms the test actually discriminates between lenses
// rather than passing vacuously.
// F2 (wrong fork): asserting the [0,1,3] q=0 case equals
// `support_coverage_013`'s [0, 0.5, 0.5] instead of sibling coverage
// failed at index 0 (got ~0.333, expected 0.0) -- confirms the fork
// assertion is real, not tautological.
// F3 (wrong refusal): asserting `escort_weight(zero, -1, 0)` returns
// `Ok` instead of `Err(ZeroMassUnderNegativeLens)` failed with a match
// arm mismatch against the real `Err` value -- confirms the refusal
// check exercises the actual guard, not a vacuous pattern.
// ---------------------------------------------------------------------
