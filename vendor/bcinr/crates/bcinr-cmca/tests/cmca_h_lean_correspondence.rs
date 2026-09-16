//! Differential correspondence tests between `bcinr-cmca`'s fixed-point
//! escort implementation ([`bcinr_cmca::escort::escort_distribution`],
//! [`bcinr_cmca::cascade::escort_weight`]) and the hand-transcribed exact
//! reference oracle ([`bcinr_cmca::reference_escort`]), which itself
//! transcribes `~/mfw`'s `MFW/CMCA/Semantics/Escort.lean`
//! (`CMCA-Escort-v0.1`).
//!
//! # What this file establishes, and what it does not
//!
//! This is a **differential test correspondence layer**, not a proof. There
//! is no FFI or export bridge between the Lean repository and this Rust
//! crate; `reference_escort` is a hand-transcription checked against Lean's
//! own worked-example theorems (see its unit tests), and this file checks
//! `bcinr-cmca`'s production fixed-point code against that transcription,
//! within a measured numerical tolerance. Passing every test here is
//! evidence of agreement on the cases exercised, not a formal or
//! machine-checked correspondence claim. No test in this file asserts
//! "formally verified," "proven," or any equivalent phrase, and none
//! should be added without also being false.
//!
//! This file makes no production behavior changes: it calls
//! `escort_distribution`, `cascade::escort_weight`, and
//! `reference_escort::{escort, uniform_sibling_coverage}` exactly as they
//! are, read-only.

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::cascade::CascadeRefusal;
use bcinr_cmca::escort::{escort_distribution, EscortRefusal};
use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};
use bcinr_cmca::reference_escort::{self, ReferenceEscortRefusal, ReferenceLens};

fn masses_to_fixed(masses: &[u64]) -> Vec<NonNegativeFixed> {
    masses
        .iter()
        .map(|&m| NonNegativeFixed::from_num(m as u32))
        .collect()
}

fn signed_q(q: i32) -> SignedFixed {
    SignedFixed::from_num(q)
}

/// The five reference lenses paired with the integer `q` `escort_distribution`
/// dispatches to `cascade::escort_weight` for.
const LENSES: [(ReferenceLens, i32); 5] = [
    (ReferenceLens::RareTwo, -2),
    (ReferenceLens::RareOne, -1),
    (ReferenceLens::Coverage, 0),
    (ReferenceLens::Proportional, 1),
    (ReferenceLens::ExploitTwo, 2),
];

// ---------------------------------------------------------------------
// 1. Exact refusal-condition equivalence
// ---------------------------------------------------------------------

/// Four logical mass-field shapes crossed against all five lenses.
fn shape_cases() -> Vec<(&'static str, Vec<u64>)> {
    vec![
        ("empty", vec![]),
        ("all_zero", vec![0, 0, 0]),
        ("one_zero_mixed", vec![0, 1, 3]),
        ("all_positive", vec![1, 2, 3, 4]),
    ]
}

/// Whether the fixed-point path refused for this `(lens, masses)` case, and
/// -- when it did -- what kind of refusal, mapped onto the Lean-shaped
/// vocabulary where a 1:1 mapping actually exists. `None` in the second slot
/// means either "did not refuse" or "refused for a reason with no Lean
/// analogue" (documented at the call site, never forced into a false
/// equivalence).
fn fixed_point_outcome(lens_q: i32, masses: &[u64]) -> Result<Vec<NonNegativeFixed>, String> {
    let fixed = masses_to_fixed(masses);
    escort_distribution(&fixed, signed_q(lens_q)).map_err(|e| format!("{e:?}"))
}

#[test]
fn refusal_presence_matches_the_reference_oracle_across_the_shape_lens_matrix() {
    for (shape_name, masses) in shape_cases() {
        for (lens, q) in LENSES {
            // Known, documented divergence: `escort(Coverage, all_zero)`
            // refuses `ZeroSupport` in the reference oracle, but
            // `escort_distribution(all_zero, q=0)` *succeeds* on BCINR's
            // current sibling-coverage realization. Asserting equal
            // is-err-ness here would be a false equivalence; see
            // `zero_support_on_all_zero_coverage_lens_has_no_fixed_point_analogue`
            // for the documented, executable statement of this divergence.
            if shape_name == "all_zero" && lens == ReferenceLens::Coverage {
                continue;
            }

            let reference_result = reference_escort::escort(lens, &masses);
            let fixed_result = fixed_point_outcome(q, &masses);

            assert_eq!(
                reference_result.is_err(),
                fixed_result.is_err(),
                "shape={shape_name} lens={lens:?} q={q} reference={reference_result:?} fixed={fixed_result:?}"
            );
        }
    }
}

/// Explicit refusal-reason mapping for the cases where the two refusal
/// vocabularies actually align 1:1. `escort_distribution`'s `EmptyInput` is
/// checked directly (it never reaches `cascade::escort_weight`); the
/// per-element cases require unwrapping through
/// `EscortRefusal::ExactPathRefused { reason: CascadeRefusal, .. }` --
/// documented per case below, since `CascadeRefusal`'s shape does not mirror
/// Lean's flat four-constructor `EscortRefusal` one-for-one.
#[test]
fn empty_domain_maps_to_empty_input() {
    for (lens, q) in LENSES {
        let reference_result = reference_escort::escort(lens, &[]);
        let fixed_result = fixed_point_outcome(q, &[]);
        assert_eq!(reference_result, Err(ReferenceEscortRefusal::EmptyDomain));
        assert_eq!(
            fixed_result,
            Err(format!("{:?}", EscortRefusal::EmptyInput))
        );
    }
}

/// `zeroMassUnderNegativeLens` (Lean) maps to
/// `EscortRefusal::ExactPathRefused { reason:
/// CascadeRefusal::ZeroMassUnderNegativeLens { .. }, .. }` on the fixed
/// path, for the two negative lenses. Verified by matching the wrapped
/// `CascadeRefusal` variant, not merely the top-level `EscortRefusal`
/// variant name, since `ExactPathRefused` also wraps several *other*
/// `CascadeRefusal` shapes that have no Lean-side analogue at all (see the
/// documentation note below this test).
#[test]
fn zero_mass_under_negative_lens_maps_through_exact_path_refused() {
    let masses = [0u64, 1, 3];
    for (lens, q) in [(ReferenceLens::RareTwo, -2), (ReferenceLens::RareOne, -1)] {
        let reference_result = reference_escort::escort(lens, &masses);
        assert_eq!(
            reference_result,
            Err(ReferenceEscortRefusal::ZeroMassUnderNegativeLens)
        );

        let fixed = masses_to_fixed(&masses);
        let fixed_result = escort_distribution(&fixed, signed_q(q));
        match fixed_result {
            Err(EscortRefusal::ExactPathRefused {
                reason: CascadeRefusal::ZeroMassUnderNegativeLens { .. },
                ..
            }) => {}
            other => panic!(
                "q={q}: expected ExactPathRefused{{ZeroMassUnderNegativeLens}}, got {other:?}"
            ),
        }
    }
}

/// `zeroPartitionSum` (Lean, all-zero field under a positive lens) maps to
/// `EscortRefusal::DegenerateNormalization` on the fixed path -- NOT through
/// `ExactPathRefused`, because `cascade::escort_weight` computes `0^q = 0`
/// successfully per element for `q > 0` (Escort.lean's `rawWeight
/// .proportional`/`.exploit2` agree: raw weight of a zero mass under a
/// positive lens is `0`, not a refusal); it is `escort_distribution`'s own
/// post-loop sum check that refuses, one level up from where Lean's
/// `escort` checks `masses.all (· == 0)` up front. This is a real shape
/// mismatch between the two refusal vocabularies (Lean refuses at the
/// per-field level before computing anything; the fixed path refuses after
/// computing zero weights and finding no denominator) -- documented here,
/// not forced into a false 1:1 mapping.
#[test]
fn zero_partition_sum_on_all_zero_positive_lens_maps_to_degenerate_normalization() {
    let masses = [0u64, 0, 0];
    for (lens, q) in [
        (ReferenceLens::Proportional, 1),
        (ReferenceLens::ExploitTwo, 2),
    ] {
        let reference_result = reference_escort::escort(lens, &masses);
        assert_eq!(
            reference_result,
            Err(ReferenceEscortRefusal::ZeroPartitionSum)
        );

        let fixed = masses_to_fixed(&masses);
        let fixed_result = escort_distribution(&fixed, signed_q(q));
        assert_eq!(
            fixed_result,
            Err(EscortRefusal::DegenerateNormalization),
            "q={q}"
        );
    }
}

/// `zeroSupport` (Lean, all-zero field under `coverage`) has **no**
/// analogue on the fixed path at all: `cascade::escort_weight`'s `lens ==
/// 0` branch returns `NonNegativeFixed::ONE` unconditionally, without
/// inspecting mass, so `escort_distribution(all_zero, q=0)` *succeeds* --
/// it does not refuse with `DegenerateNormalization`, `ExactPathRefused`,
/// or anything else. This is documented, not forced into an equivalence:
/// the reference oracle's `zeroSupport` refusal has no counterpart in
/// current BCINR behavior, because BCINR realizes `uniformSiblingCoverage`
/// at `q = 0`, not `ReferenceLens.coverage` -- see part 2 below and
/// `escort.rs`'s module docs.
#[test]
fn zero_support_on_all_zero_coverage_lens_has_no_fixed_point_analogue() {
    let masses = [0u64, 0, 0];
    let reference_result = reference_escort::escort(ReferenceLens::Coverage, &masses);
    assert_eq!(reference_result, Err(ReferenceEscortRefusal::ZeroSupport));

    let fixed = masses_to_fixed(&masses);
    let fixed_result = escort_distribution(&fixed, signed_q(0));
    assert!(
        fixed_result.is_ok(),
        "expected BCINR's q=0 path to succeed (sibling coverage), got {fixed_result:?}"
    );
}

// ---------------------------------------------------------------------
// 2. q=0 sibling-coverage correspondence
// ---------------------------------------------------------------------

/// Measured fixed-point rounding tolerance for Q16.16 conversions in this
/// file: `ExactRational::to_q16_16_bits_round` rounds to the nearest bit,
/// and `escort_distribution`'s own arithmetic (division by a small integer
/// sibling count) is exact for the sibling counts exercised here modulo at
/// most a few ULPs of Q16.16 truncation. 4 bits (~0.006% of `ONE`) is
/// generous headroom over the exact rounding error, following the same
/// measure-then-assert precedent as `escort.rs`'s own
/// `power_disagrees_with_the_exact_path_at_a_measured_bound`.
const Q0_TOLERANCE_BITS: i64 = 4;

fn approx_eq_bits(a: u32, b: u32, tol: i64) -> bool {
    (i64::from(a) - i64::from(b)).abs() <= tol
}

/// `escort_distribution(masses, q=0)` matches `uniform_sibling_coverage`,
/// not `escort(Coverage, masses)`, whenever a zero mass is present --
/// executing this crate's own doc-comment claim
/// ("Current BCINR behavior is sibling coverage") as a differential test
/// rather than leaving it asserted only in prose.
#[test]
fn q_zero_on_zero_containing_masses_matches_sibling_coverage_not_support_coverage() {
    let cases: [&[u64]; 4] = [&[0, 1, 3], &[0, 0], &[0, 5, 5, 0], &[0]];

    for masses in cases {
        let fixed = masses_to_fixed(masses);
        let fixed_result = escort_distribution(&fixed, signed_q(0))
            .unwrap_or_else(|e| panic!("masses={masses:?}: expected success, got {e:?}"));

        let sibling_reference = reference_escort::uniform_sibling_coverage(masses).unwrap();
        assert_eq!(fixed_result.len(), sibling_reference.len());
        for (index, (fixed_share, exact_share)) in fixed_result
            .iter()
            .zip(sibling_reference.iter())
            .enumerate()
        {
            let exact_bits = exact_share.to_q16_16_bits_round();
            assert!(
                approx_eq_bits(fixed_share.to_bits(), exact_bits, Q0_TOLERANCE_BITS),
                "masses={masses:?} index={index} fixed={:?} exact_bits={exact_bits}",
                fixed_share
            );
        }

        // And it must NOT match support coverage on the same input, when the
        // two operations actually disagree (some but not all masses zero;
        // on an all-zero field support coverage refuses outright, which is
        // already covered by `zero_support_on_all_zero_coverage_lens_has_no_fixed_point_analogue`).
        if masses.contains(&0) && masses.iter().any(|&m| m != 0) {
            let support_reference = reference_escort::escort(ReferenceLens::Coverage, masses)
                .expect("mixed zero/nonzero field succeeds under support coverage");
            let mut any_differs = false;
            for (fixed_share, support_share) in fixed_result.iter().zip(support_reference.iter()) {
                let support_bits = support_share.to_q16_16_bits_round();
                if !approx_eq_bits(fixed_share.to_bits(), support_bits, Q0_TOLERANCE_BITS) {
                    any_differs = true;
                }
            }
            assert!(
                any_differs,
                "masses={masses:?}: expected BCINR's q=0 output to diverge from support coverage \
                 (it should match sibling coverage instead), but it matched support coverage too"
            );
        }
    }
}

// ---------------------------------------------------------------------
// 3. Integer-lens (q in {-2,-1,1,2}) exact-path correspondence
// ---------------------------------------------------------------------

fn mass_fields() -> Vec<Vec<u64>> {
    vec![
        vec![1, 2, 3],
        vec![1, 2, 3, 4],
        vec![1, 2, 3, 4, 5],
        vec![1, 5, 25],
        vec![2, 4, 8, 16],
        vec![1, 1, 1, 1],
        vec![7, 3, 11, 2, 9],
        vec![100, 200, 300],
        vec![1, 1000],
    ]
}

/// Measures (does not assume) the maximum observed Q16.16-bit disagreement
/// between `escort_distribution`'s exact-integer path and the reference
/// oracle over a spread of all-positive mass fields, at every non-coverage
/// integer lens. Prints the measured max so it can be cited verbatim in the
/// ticket report, then asserts a tolerance bound set from that measurement
/// with headroom, following `escort.rs`'s own
/// `power_disagrees_with_the_exact_path_at_a_measured_bound` precedent.
#[test]
fn integer_lens_exact_path_matches_reference_oracle_within_a_measured_bound() {
    let mut max_diff_bits: i64 = 0;
    let mut worst: Option<(ReferenceLens, Vec<u64>, usize, u32, u32)> = None;

    for (lens, q) in [
        (ReferenceLens::RareTwo, -2),
        (ReferenceLens::RareOne, -1),
        (ReferenceLens::Proportional, 1),
        (ReferenceLens::ExploitTwo, 2),
    ] {
        for masses in mass_fields() {
            let reference_result = match reference_escort::escort(lens, &masses) {
                Ok(v) => v,
                Err(_) => continue,
            };
            let fixed = masses_to_fixed(&masses);
            // Some mass fields exceed the fixed-point exact path's Q16.16
            // range at |q|=2 (e.g. 300^2 accumulated by repeated
            // multiplication overflows u32) -- a genuine numeric-range
            // limitation of the fixed-point realization, not a
            // correspondence defect. Skip rather than treat as a
            // disagreement: this test measures agreement where the fixed
            // path actually produces an answer.
            let fixed_result = match escort_distribution(&fixed, signed_q(q)) {
                Ok(v) => v,
                Err(_) => continue,
            };
            assert_eq!(fixed_result.len(), reference_result.len());

            for (index, (fixed_share, exact_share)) in
                fixed_result.iter().zip(reference_result.iter()).enumerate()
            {
                let exact_bits = exact_share.to_q16_16_bits_round();
                let diff = (i64::from(fixed_share.to_bits()) - i64::from(exact_bits)).abs();
                if diff > max_diff_bits {
                    max_diff_bits = diff;
                    worst = Some((
                        lens,
                        masses.clone(),
                        index,
                        fixed_share.to_bits(),
                        exact_bits,
                    ));
                }
            }
        }
    }

    eprintln!(
        "integer_lens_exact_path_matches_reference_oracle_within_a_measured_bound: \
         max observed |fixed_bits - exact_bits| = {max_diff_bits} (of 65536 = ONE); worst case = {worst:?}"
    );

    // Measured (not guessed): max observed |fixed_bits - exact_bits| over
    // this mass-field/lens spread is 24 (of 65536 = ONE, ~0.037% relative),
    // at RareOne on masses=[100,200,300], index 0 (fixed=35771,
    // exact_bits=35747) -- see the eprintln above for the exact figure this
    // run measured. `cascade::escort_weight` is exact repeated
    // multiplication for the raw weight itself, so this diff is purely
    // Q16.16 division truncation in the final normalization step (`w_i /
    // sum`), not approximation error. Bound set to 40 for headroom over the
    // measured 24, following `escort.rs`'s own
    // `power_disagrees_with_the_exact_path_at_a_measured_bound` precedent
    // of measuring first and asserting second.
    assert!(
        max_diff_bits <= 40,
        "max observed diff {max_diff_bits} exceeds the asserted bound; update the bound to the \
         newly measured value with headroom and report the change, per AGENTS.md's ban on \
         silently weakening a test to force a pass"
    );
}

// ---------------------------------------------------------------------
// 4. Property parity tests
// ---------------------------------------------------------------------

const NORMALIZATION_TOLERANCE_BITS: i64 = 8;

#[test]
fn fixed_point_output_sums_within_tolerance_of_one() {
    for (_, q) in LENSES {
        for masses in mass_fields() {
            let fixed = masses_to_fixed(&masses);
            if let Ok(result) = escort_distribution(&fixed, signed_q(q)) {
                let mut sum = NonNegativeFixed::ZERO;
                for v in &result {
                    sum += *v;
                }
                let diff =
                    (i64::from(sum.to_bits()) - i64::from(NonNegativeFixed::ONE.to_bits())).abs();
                assert!(
                    diff <= NORMALIZATION_TOLERANCE_BITS,
                    "q={q} masses={masses:?} sum={sum:?} diff={diff}"
                );
            }
        }
    }
}

#[test]
fn reference_oracle_is_permutation_invariant() {
    let masses = vec![1u64, 2, 3, 4];
    let permuted = vec![4u64, 1, 3, 2];
    for (lens, _) in LENSES {
        let a = reference_escort::escort(lens, &masses);
        let b = reference_escort::escort(lens, &permuted);
        match (a, b) {
            (Ok(av), Ok(bv)) => {
                let mut a_sorted = av;
                let mut b_sorted = bv;
                a_sorted.sort();
                b_sorted.sort();
                assert_eq!(a_sorted, b_sorted, "lens={lens:?}");
            }
            (Err(ea), Err(eb)) => assert_eq!(ea, eb, "lens={lens:?}"),
            (a, b) => panic!("lens={lens:?}: mismatched outcome shapes {a:?} vs {b:?}"),
        }
    }
}

#[test]
fn fixed_point_output_is_permutation_invariant_within_tolerance() {
    let masses = vec![1u64, 2, 3, 4];
    let permuted = vec![4u64, 1, 3, 2];
    for (_, q) in LENSES {
        let fixed_a = masses_to_fixed(&masses);
        let fixed_b = masses_to_fixed(&permuted);
        let a = escort_distribution(&fixed_a, signed_q(q));
        let b = escort_distribution(&fixed_b, signed_q(q));
        if let (Ok(av), Ok(bv)) = (a, b) {
            let mut a_bits: Vec<u32> = av.iter().map(|x| x.to_bits()).collect();
            let mut b_bits: Vec<u32> = bv.iter().map(|x| x.to_bits()).collect();
            a_bits.sort_unstable();
            b_bits.sort_unstable();
            for (x, y) in a_bits.iter().zip(b_bits.iter()) {
                assert!(
                    approx_eq_bits(*x, *y, NORMALIZATION_TOLERANCE_BITS),
                    "q={q}"
                );
            }
        }
    }
}

#[test]
fn reference_oracle_output_is_nonnegative() {
    for (lens, _) in LENSES {
        for masses in mass_fields() {
            if let Ok(out) = reference_escort::escort(lens, &masses) {
                for w in out {
                    assert!(
                        w.numerator() >= 0,
                        "lens={lens:?} masses={masses:?} w={w:?}"
                    );
                }
            }
        }
    }
}

#[test]
fn fixed_point_output_is_nonnegative_by_construction() {
    // NonNegativeFixed's own type carries this invariant (unsigned `val`);
    // this test exists to make the property explicit in this file's parity
    // suite rather than to discover a possible violation.
    for (_, q) in LENSES {
        for masses in mass_fields() {
            let fixed = masses_to_fixed(&masses);
            if let Ok(result) = escort_distribution(&fixed, signed_q(q)) {
                for v in result {
                    let _: u32 = v.to_bits(); // always representable as unsigned
                }
            }
        }
    }
}

/// Direction-only cross-lens concentration: a higher exponent lens gives
/// the max-mass element a share at least as large as a lower exponent
/// lens's share for that same element. Inequality only -- not an exact
/// ratio -- matching Escort.lean's `escort_max_mass_share_nondecreasing`
/// (Escort.lean:957) in *shape* (a monotonicity direction), not in exact
/// numeric claim (that theorem is about the reference oracle; this test is
/// about the fixed-point realization, checked with tolerance headroom).
#[test]
fn higher_exponent_lens_gives_at_least_as_large_a_share_to_the_max_mass_element() {
    let masses = vec![1u64, 2, 10];
    let max_index = 2; // mass = 10, the largest
    let ascending_lenses = [-2, -1, 1, 2]; // skip q=0: different operation family

    let fixed = masses_to_fixed(&masses);
    let mut prev_share: Option<u32> = None;
    for q in ascending_lenses {
        let result = escort_distribution(&fixed, signed_q(q)).unwrap();
        let share = result[max_index].to_bits();
        if let Some(prev) = prev_share {
            // Small tolerance for Q16.16 rounding at the boundary; strictly
            // non-decreasing is the mathematical claim, but adjacent lenses
            // are compared, so equal-within-tolerance is acceptable at the
            // fixed-point layer without being a numeric-precision claim
            // about the reference oracle's exact rationals.
            assert!(
                i64::from(share) + NORMALIZATION_TOLERANCE_BITS >= i64::from(prev),
                "q={q} share={share} prev={prev}"
            );
        }
        prev_share = Some(share);
    }
}

// ---------------------------------------------------------------------
// 5. Fractional-q diagnostic (explicitly no_lean_referent)
// ---------------------------------------------------------------------

/// Diagnostic only: Lean's `ReferenceLens` is closed at five integer-exponent
/// constructors and has no fractional-`q` referent at all (Escort.lean's
/// module docs, "Boundary" section: "No fractional lenses... Fractional `q`
/// is a separately versioned extension, not a widening of this profile.").
/// This test therefore makes **no** correspondence claim -- it only checks
/// that `escort_distribution`'s approximate (`allocator::power`) path
/// produces a normalized, non-degenerate output for a fractional `q`,
/// which is a property of the fixed-point implementation alone.
#[test]
fn fractional_q_output_is_normalized_no_lean_referent() {
    let masses = masses_to_fixed(&[1, 2, 3, 4]);
    let q_half = SignedFixed::from_bits(1 << 15); // 0.5
    let result = escort_distribution(&masses, q_half).unwrap();
    let mut sum = NonNegativeFixed::ZERO;
    for v in &result {
        sum += *v;
    }
    let diff = (i64::from(sum.to_bits()) - i64::from(NonNegativeFixed::ONE.to_bits())).abs();
    assert!(diff <= 500, "sum={sum:?} diff={diff}");
}
