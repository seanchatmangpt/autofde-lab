//! Error-bound characterization for `allocator::power`'s fractional-lens
//! path.
//!
//! # Scope and relationship to checkpoint E
//!
//! `lean_correspondence.rs` (checkpoint E) named this gap explicitly and
//! declared it out of scope: `escort.rs`'s own
//! `power_disagrees_with_the_exact_path_at_a_measured_bound` measured a
//! ~1.07% relative drift at `q=3` on normalized *shares* (post-sum,
//! post-division) for one small mass set, against the exact
//! `cascade::escort_weight` repeated-multiplication path -- diagnostic
//! evidence, not a domain-wide characterization, and explicitly flagged as
//! future work by both that test's own doc comment and checkpoint E's
//! module doc.
//!
//! This file is that future work: a domain-wide, reproducible bound on
//! `allocator::power`'s *own* relative error against a high-precision
//! (`f64`) reference oracle (`base.powf(q)`), not against
//! `escort_weight`'s normalized shares. Bounding `power` itself is the
//! right level -- `escort.rs`'s ~1.07% figure mixes `power`'s error with
//! cancellation/amplification from summation and division, which depends
//! on the mass set chosen and is not a property of `power` alone.
//!
//! # Method: empirical sweep, not analytical derivation
//!
//! `power(base, exponent) = exp2(exponent * log2(base))`
//! (`crates/bcinr-cmca/src/allocator/mod.rs`, `power`). Both `log2`
//! (`fixed.rs::NonNegativeFixed::log2`) and `exp2`
//! (`fixed.rs::SignedFixed::exp2`) are fixed-point polynomial
//! approximations over the mantissa/fractional part: `log2` applies one
//! quadratic Newton-style correction to a linear mantissa estimate,
//! `exp2` evaluates a degree-4 polynomial in the fractional exponent
//! bits. Composing two polynomial approximations and reasoning about the
//! resulting error analytically (a Taylor remainder bound composed
//! through a multiplication and a second approximation) is a real
//! derivation, not a checkpoint-sized one -- so this checkpoint takes the
//! empirical path the task brief explicitly allows as an honest
//! substitute: an exhaustive, finite, documented grid sweep against
//! `f64`, with the exact sweep parameters recorded below so the bound is
//! reproducible and falsifiable. **This is an EMPIRICAL bound, not an
//! analytically proven one.**
//!
//! # A real finding this sweep surfaced: error scales with `|q|`
//!
//! An initial sweep across the *entire* declared lens domain
//! (`cascade::MAX_LENS_MAGNITUDE == 16`, i.e. `q in [-16,16]`) measured a
//! maximum relative error of ~48.5% -- because `log2`'s small absolute
//! approximation error gets multiplied by `exponent` *before* `exp2`
//! exponentiates it, so the error grows roughly with `|q|`, not with
//! `base`. Bucketing by `|q|` confirms this is monotonic, not a corner
//! case:
//!
//! | `|q|` range   | max relative error (measured) |
//! |---------------|-------------------------------|
//! | `(0, 0.25]`   | 0.5%                           |
//! | `(0.25, 1]`   | 1.5%                           |
//! | `(1, 2]`      | 3.5%                           |
//! | `(2, 4]`      | 7.6%                           |
//! | `(4, 8]`      | 16.4%                          |
//! | `(8, 16]`     | 36.2%                          |
//!
//! A single bound over the full `[-16, 16]` domain would therefore have
//! to be as loose as ~40-50% to be honest -- not a useful
//! characterization for the tight-precision uses this crate's own tests
//! exercise. Per this repo's own Gall-checkpoint discipline ("one
//! consequential distinction ... no unrelated architectural expansion"),
//! this checkpoint *primarily* bounds a genuinely useful, tighter
//! sub-domain: **`|q| <= 4`**, which covers every worked example this
//! crate's own tests already use (`escort.rs`'s `q=3` diagnostic test,
//! `q(0.5)`/`q(-0.5)`/`q(1.0)`/`q(2.0)`/`q(4.0)`/`q(5.0)` in `escort.rs`'s
//! `output_sums_to_approximately_one` and
//! `higher_q_concentrates_mass_on_the_largest_input`).
//!
//! `power` remains reachable at `|q|` up to `MAX_LENS_MAGNITUDE` (16)
//! through `escort_distribution`, and CMCA-106 closed the gap this
//! paragraph used to leave open: the full `4 < |q| <= 16` sub-domain is
//! **no longer `UNKNOWN`**. `power_relative_error_full_domain_bucketed`
//! below sweeps the entire admitted domain (`|q| <= 16`) with the same
//! grid construction as the `|q| <= 4` sweep, extended, and asserts a
//! real, per-bucket measured bound (see that test's own doc comment for
//! the exact figures: growing from ~0.5% at `|q| <= 0.25` to ~36.2% at
//! `|q| <= 16`, with the exact boundary `|q| == 16` measured directly at
//! ~36.9%). The `|q| <= 4` sweep and bound below remain as the tighter,
//! separately-asserted characterization for the sub-domain this crate's
//! own worked examples actually use -- both bounds are checked
//! independently, and neither supersedes the other.
//!
//! # Domain swept (the bound this file actually asserts)
//!
//! - `base`: 60 points, geometrically spaced from `2^-6` (~0.0156) to
//!   `2^10` (1024) -- several orders of magnitude around the `[0.1, 10]`
//!   masses `escort.rs`'s own tests use, with headroom on both sides.
//!   `base == 0` is excluded -- `power` treats it as an exact special
//!   case (no `log2`/`exp2` approximation involved; see `power`'s
//!   `base_is_zero` branch), outside the approximation error surface
//!   this file characterizes.
//! - `exponent` (`q`): every `0.25`-step point in `[-4, 4]` that is NOT
//!   an exact integer -- integer `q` never reaches `power` through the
//!   public `escort_distribution` entry point (`exact_integer_lens`
//!   routes it to `cascade::escort_weight` instead), so this file only
//!   sweeps inputs `power` is actually reachable on in production use.
//! - Reference values with `|base.powf(q)| < 0.01` are excluded: at that
//!   magnitude the true answer is within ~65 Q16.16 units of zero, so
//!   *relative* error is dominated by fixed-point quantization noise (the
//!   representation's ~1.5e-5 resolution floor), not by the
//!   `log2`/`exp2` approximation this file characterizes. This is a
//!   measurement-methodology exclusion, confirmed by direct
//!   inspection (a `base=5.3, q=-6.25` case outside the `|q|<=4` domain
//!   showed a "48% relative error" driven entirely by a true answer of
//!   `2.96e-5`, i.e. ~2 representable units) -- not a way to hide real
//!   approximation error.
//! - Any `(base, exponent)` pair where `power` itself signals a numeric
//!   fault (`err != u32::MAX`) is excluded from the statistic -- a
//!   refused value is not a silently wrong value, and
//!   `escort_distribution` already turns that fault into
//!   `EscortRefusal::NumericFault` rather than propagating it.
//!
//! # Result
//!
//! Maximum observed relative error over the swept `|q| <= 4` grid: ~7.6%
//! at the domain's edge (`|q|` near 4, small `base`). See
//! `EMPIRICAL_RELATIVE_ERROR_BOUND` for the bound asserted (measured
//! maximum plus headroom) and the sweep test's own `eprintln!` for the
//! exact figure on any given run.

// Exercises `cascade`/`escort`/`reference_escort` (alloc-gated modules): without
// the feature this target compiles to zero tests, keeping the default-feature
// matrix green instead of failing to resolve gated imports.
#![cfg(feature = "alloc")]

use bcinr_cmca::allocator::{power, StabilityRefusal};
use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};

fn to_f64(f: NonNegativeFixed) -> f64 {
    (f.to_bits() as f64) / 65536.0
}

fn fixed_mass(v: f64) -> NonNegativeFixed {
    let scaled = (v * 65536.0).round();
    if scaled >= u32::MAX as f64 {
        NonNegativeFixed::MAX
    } else if scaled <= 0.0 {
        NonNegativeFixed::ZERO
    } else {
        NonNegativeFixed::from_bits(scaled as u32)
    }
}

fn fixed_exponent(v: f64) -> SignedFixed {
    SignedFixed::from_bits((v * 65536.0).round() as i32)
}

/// This checkpoint's declared sub-domain for `exponent` (`q`): `|q| <=
/// MAX_SWEPT_LENS_MAGNITUDE`, strictly narrower than
/// `cascade::MAX_LENS_MAGNITUDE` (16) -- see module doc for why a
/// uniform bound over the full declared lens domain would be
/// uninformatively loose (~40-50%).
const MAX_SWEPT_LENS_MAGNITUDE: f64 = 4.0;

/// Reference values below this magnitude are excluded from the relative-
/// error statistic: at that scale, Q16.16 quantization noise (the
/// representation's ~1.5e-5 resolution floor) dominates relative error,
/// not the `log2`/`exp2` approximation this file characterizes. See
/// module doc.
const MIN_REFERENCE_MAGNITUDE: f64 = 0.01;

/// The exact base grid and exponent grid this checkpoint's bound is
/// measured over -- shared between the passing sweep test and the
/// falsifier test so both exercise identically-shaped inputs.
fn base_grid() -> Vec<f64> {
    (0..60)
        .map(|i| {
            let exp = -6.0 + (i as f64) * (16.0 / 59.0); // -6.0 ..= 10.0
            2f64.powf(exp)
        })
        .collect()
}

fn exponent_grid() -> Vec<f64> {
    exponent_grid_to(MAX_SWEPT_LENS_MAGNITUDE)
}

/// Same construction as [`exponent_grid`], generalized to an arbitrary
/// magnitude so the full-domain sweep below (`|q| <= 16`, i.e.
/// `cascade::MAX_LENS_MAGNITUDE`) can reuse it without duplicating the
/// step/filter logic.
fn exponent_grid_to(max_magnitude: f64) -> Vec<f64> {
    let steps = (4.0 * max_magnitude * 2.0) as i64 + 1; // 0.25 step
    (0..steps)
        .map(|i| -max_magnitude + (i as f64) * 0.25)
        .filter(|q| q.fract().abs() > 1e-9) // exclude exact integers: never reach `power` in production
        .collect()
}

/// The crate's own declared admitted domain boundary
/// (`cascade::MAX_LENS_MAGNITUDE`), duplicated here as an `f64` literal so
/// this file doesn't need a dependency on `bcinr_cmca::cascade` just for
/// one constant. Kept in sync by
/// `full_domain_sweep_matches_declared_admitted_boundary` below, which
/// fails loudly if the crate's constant ever moves without this file being
/// updated.
const FULL_DOMAIN_MAX_LENS_MAGNITUDE: f64 = 16.0;

/// Sweeps `base_grid() x exponent_grid()` through a caller-supplied
/// `power`-shaped function, returning the maximum relative error observed
/// against the `f64` reference oracle `base.powf(q)`, plus how many grid
/// points were excluded because the function under test signaled a
/// numeric fault. Parameterized over the implementation under test so the
/// falsifier test below can run the identical sweep against a
/// deliberately degraded approximation.
fn max_relative_error(
    compute: impl Fn(NonNegativeFixed, SignedFixed) -> NonNegativeFixed,
) -> (f64, usize, usize) {
    let mut max_rel_err = 0.0f64;
    let mut faulted = 0usize;
    let mut checked = 0usize;

    for &base in &base_grid() {
        for &q in &exponent_grid() {
            let b = fixed_mass(base);
            let e = fixed_exponent(q);
            let got = compute(b, e);
            // A signaled numeric fault is a refusal, not a silently wrong
            // value -- excluded from the error statistic, matching
            // `escort_distribution`'s own `NumericFault` handling.
            if got.err != u32::MAX {
                faulted += 1;
                continue;
            }
            let reference = base.powf(q);
            if !reference.is_finite() || reference.abs() < MIN_REFERENCE_MAGNITUDE {
                // Quantization-dominated or degenerate reference -- see
                // module doc's "Domain swept" section.
                continue;
            }
            let observed = to_f64(got);
            let rel_err = ((observed - reference) / reference).abs();
            checked += 1;
            if rel_err > max_rel_err {
                max_rel_err = rel_err;
            }
        }
    }
    (max_rel_err, checked, faulted)
}

/// Sweeps the full admitted lens domain (`|q| <= FULL_DOMAIN_MAX_LENS_MAGNITUDE`,
/// i.e. `cascade::MAX_LENS_MAGNITUDE`) through `power`, bucketing the
/// observed relative error by `|q|` range using the same buckets as the
/// module doc's table. Returns `(bucket_max_by_upper_bound, overall_max,
/// checked, faulted)`. `bucket_max_by_upper_bound` pairs each bucket's
/// upper `|q|` edge with the max relative error observed for `|q|` in
/// that bucket.
fn max_relative_error_full_domain_bucketed() -> (Vec<(f64, f64)>, f64, usize, usize) {
    const BUCKET_EDGES: [f64; 6] = [0.25, 1.0, 2.0, 4.0, 8.0, 16.0];
    let mut bucket_max = vec![0.0f64; BUCKET_EDGES.len()];
    let mut overall_max = 0.0f64;
    let mut faulted = 0usize;
    let mut checked = 0usize;

    for &base in &base_grid() {
        for &q in &exponent_grid_to(FULL_DOMAIN_MAX_LENS_MAGNITUDE) {
            let b = fixed_mass(base);
            let e = fixed_exponent(q);
            let got = power(b, e);
            if got.err != u32::MAX {
                faulted += 1;
                continue;
            }
            let reference = base.powf(q);
            if !reference.is_finite() || reference.abs() < MIN_REFERENCE_MAGNITUDE {
                continue;
            }
            let observed = to_f64(got);
            let rel_err = ((observed - reference) / reference).abs();
            checked += 1;
            if rel_err > overall_max {
                overall_max = rel_err;
            }
            let abs_q = q.abs();
            if let Some(bucket) = BUCKET_EDGES.iter().position(|&edge| abs_q <= edge) {
                if rel_err > bucket_max[bucket] {
                    bucket_max[bucket] = rel_err;
                }
            }
        }
    }

    let named: Vec<(f64, f64)> = BUCKET_EDGES.iter().copied().zip(bucket_max).collect();
    (named, overall_max, checked, faulted)
}

/// This checkpoint's real, measured worst-case relative error over the
/// FULL admitted domain (`|q| <= 16`), not just the `|q| <= 4` sub-domain
/// bounded above. Per-bucket bounds are the module doc table's measured
/// figures plus headroom, matching the pattern
/// `EMPIRICAL_RELATIVE_ERROR_BOUND` already uses for the `|q| <= 4`
/// bound -- a real number derived from a real sweep, not "no bound
/// claimed."
///
/// Measured maxima at the time this test was written (see this test's own
/// `eprintln!` for the figure on any given run): `(0,0.25]` ~0.54%,
/// `(0.25,1]` ~1.53%, `(1,2]` ~3.54%, `(2,4]` ~7.64%, `(4,8]` ~16.44%,
/// `(8,16]` ~36.21%, with the single worst point over the entire swept
/// domain also ~36.21% and the exact boundary `|q| == 16` measured
/// directly at ~36.85% (small `base`, both signs of `q`). (An earlier,
/// coarser manual sweep during this checkpoint's initial exploration
/// reported ~48.5% for the full domain; the reproducible grid this test
/// asserts against -- same `base_grid`/`exponent_grid` construction the
/// `|q| <= 4` bound above uses, extended to `|q| <= 16` -- measures
/// ~36.2%. The grid and its exact points are what this test actually
/// checks, not the earlier figure.) Bounds below are each measured
/// maximum plus headroom.
const FULL_DOMAIN_BUCKET_BOUNDS: [f64; 6] = [0.015, 0.05, 0.08, 0.12, 0.25, 0.50];

/// Bound on the single worst point anywhere in the full `|q| <= 16`
/// domain -- looser than any individual bucket bound above since it is
/// the max over the whole swept grid, not one range of `|q|`.
const FULL_DOMAIN_OVERALL_BOUND: f64 = 0.55;

#[test]
fn power_relative_error_full_domain_bucketed() {
    let (bucket_max, overall_max, checked, faulted) = max_relative_error_full_domain_bucketed();

    eprintln!(
        "power_relative_error_full_domain_bucketed: overall_max={overall_max:.6} \
         ({:.3}%), checked={checked}, faulted_excluded={faulted}",
        overall_max * 100.0
    );
    for (edge, max_err) in &bucket_max {
        eprintln!(
            "  |q| in (prev, {edge}]: max_rel_err={max_err:.6} ({:.3}%)",
            max_err * 100.0
        );
    }

    // Explicit boundary figure: the crate's own declared admitted edge,
    // |q| == MAX_LENS_MAGNITUDE == 16, measured directly (not just folded
    // into the (8,16] bucket).
    let boundary_q = FULL_DOMAIN_MAX_LENS_MAGNITUDE;
    let mut boundary_max = 0.0f64;
    for &base in &base_grid() {
        for &sign in &[1.0, -1.0] {
            let q = sign * boundary_q;
            let b = fixed_mass(base);
            let e = fixed_exponent(q);
            let got = power(b, e);
            if got.err != u32::MAX {
                continue;
            }
            let reference = base.powf(q);
            if !reference.is_finite() || reference.abs() < MIN_REFERENCE_MAGNITUDE {
                continue;
            }
            let observed = to_f64(got);
            let rel_err = ((observed - reference) / reference).abs();
            if rel_err > boundary_max {
                boundary_max = rel_err;
            }
        }
    }
    eprintln!(
        "  boundary |q|=={boundary_q} exactly: max_rel_err={boundary_max:.6} ({:.3}%)",
        boundary_max * 100.0
    );

    assert!(
        checked > 1500,
        "full-domain sweep grid too small to be a meaningful characterization: only {checked} \
         points checked"
    );

    for ((edge, max_err), bound) in bucket_max.iter().zip(FULL_DOMAIN_BUCKET_BOUNDS) {
        assert!(
            *max_err < bound,
            "bucket |q| <= {edge}: measured max relative error {max_err:.6} ({:.3}%) exceeded \
             its declared bound {bound:.6} ({:.3}%)",
            max_err * 100.0,
            bound * 100.0
        );
    }

    assert!(
        overall_max < FULL_DOMAIN_OVERALL_BOUND,
        "full-domain (|q| <= {FULL_DOMAIN_MAX_LENS_MAGNITUDE}) max relative error {overall_max:.6} \
         ({:.3}%) exceeded the declared overall bound {FULL_DOMAIN_OVERALL_BOUND:.6} \
         ({:.3}%)",
        overall_max * 100.0,
        FULL_DOMAIN_OVERALL_BOUND * 100.0
    );
}

/// Confirms this file's hardcoded `FULL_DOMAIN_MAX_LENS_MAGNITUDE` literal
/// still matches the crate's real declared boundary
/// (`cascade::MAX_LENS_MAGNITUDE`), so the full-domain sweep above can
/// never silently drift out of sync with the boundary it claims to
/// characterize.
#[test]
fn full_domain_sweep_matches_declared_admitted_boundary() {
    assert_eq!(
        FULL_DOMAIN_MAX_LENS_MAGNITUDE,
        f64::from(bcinr_cmca::cascade::MAX_LENS_MAGNITUDE),
        "this file's FULL_DOMAIN_MAX_LENS_MAGNITUDE literal has drifted from \
         cascade::MAX_LENS_MAGNITUDE -- update both the literal and the full-domain sweep's \
         bucket edges"
    );
}

/// Empirical bound on `power`'s relative error over the swept `|q| <= 4`
/// sub-domain (see module doc for the exact grid). The full `|q| <= 16`
/// admitted domain is now separately swept and bounded by
/// `power_relative_error_full_domain_bucketed` below -- this constant and
/// its test remain as the tighter, independently-asserted bound for the
/// sub-domain this crate's own worked examples actually use. Measured
/// maximum at the time this checkpoint was written: ~7.64% (0.0764), at
/// the sub-domain's edge (`|q|` near 4, small `base`). `0.10` (10%) is
/// that measured maximum plus headroom, not the measured figure itself --
/// this characterizes a bounded approximation over a specific, tighter
/// sub-domain, not a claim that `power` is accurate to 10% everywhere in
/// `escort_distribution`'s admitted lens range (see the full-domain bound
/// for that).
const EMPIRICAL_RELATIVE_ERROR_BOUND: f64 = 0.10;

#[test]
fn power_relative_error_stays_within_swept_empirical_bound() {
    let (max_rel_err, checked, faulted) = max_relative_error(power);
    eprintln!(
        "power_relative_error_stays_within_swept_empirical_bound: \
         max_rel_err={max_rel_err:.6} ({:.3}%), checked={checked}, faulted_excluded={faulted}",
        max_rel_err * 100.0
    );
    assert!(
        checked > 500,
        "sweep grid too small to be a meaningful characterization: only {checked} points checked"
    );
    assert!(
        max_rel_err < EMPIRICAL_RELATIVE_ERROR_BOUND,
        "power's relative error {max_rel_err:.6} ({:.3}%) exceeded the declared empirical bound \
         {EMPIRICAL_RELATIVE_ERROR_BOUND:.6} ({:.3}%) somewhere in the swept |q| <= {MAX_SWEPT_LENS_MAGNITUDE} \
         grid -- either the approximation regressed, or the bound needs re-measuring, not silently loosening",
        max_rel_err * 100.0,
        EMPIRICAL_RELATIVE_ERROR_BOUND * 100.0
    );
}

/// Falsifier: a genuine Gall-checkpoint negative fixture, not a comment
/// describing one. Constructs a deliberately degraded stand-in for
/// `power` (multiplies the real result by a fixed 1.15x factor, i.e. a
/// synthetic 15% relative error injected uniformly) and confirms the same
/// sweep-and-bound machinery this file uses for the real function
/// actually discriminates: it must report a max relative error that
/// violates `EMPIRICAL_RELATIVE_ERROR_BOUND`, proving the bound check
/// above is not vacuously true (e.g. from a bug that always reports 0
/// error, or a bound so loose nothing could fail it).
#[test]
fn bound_checker_detects_a_deliberately_degraded_approximation() {
    let degraded = |base: NonNegativeFixed, exponent: SignedFixed| -> NonNegativeFixed {
        let real = power(base, exponent);
        if real.err != u32::MAX {
            return real; // preserve genuine faults untouched
        }
        let degraded_val = ((real.to_bits() as f64) * 1.15).round();
        let clamped = degraded_val.clamp(0.0, u32::MAX as f64) as u32;
        NonNegativeFixed {
            val: clamped,
            err: u32::MAX,
        }
    };

    let (max_rel_err, checked, _faulted) = max_relative_error(degraded);
    eprintln!(
        "bound_checker_detects_a_deliberately_degraded_approximation: \
         max_rel_err={max_rel_err:.6} ({:.3}%), checked={checked}",
        max_rel_err * 100.0
    );
    assert!(
        max_rel_err > EMPIRICAL_RELATIVE_ERROR_BOUND,
        "falsifier failed to falsify: a 15% synthetic degradation produced max_rel_err \
         {max_rel_err:.6}, which does not exceed the declared bound {EMPIRICAL_RELATIVE_ERROR_BOUND:.6} \
         -- the sweep or the bound is not sensitive enough to catch a real regression"
    );

    // And the real, undegraded function must still pass -- confirms this
    // test's own machinery isn't just permanently failing/passing
    // regardless of input.
    let (real_max_rel_err, _, _) = max_relative_error(power);
    assert!(
        real_max_rel_err < EMPIRICAL_RELATIVE_ERROR_BOUND,
        "sanity check failed: the real power() function itself violates the bound \
         ({real_max_rel_err:.6}), independent of the degraded closure above"
    );
}

/// CMCA-109 regression: `base = 0`, entirely unswept by
/// `max_relative_error`'s `base_grid()` (module doc above: "always
/// strictly positive," `base == 0` explicitly excluded). `0^(negative)`
/// is `+infinity` -- undefined -- and must be refused (`err !=
/// u32::MAX`) rather than silently reported as a valid saturated `MAX`
/// value. `0^0` and `0^(positive)` are exact, in-domain, no-fault
/// results and must keep reporting `err == u32::MAX`.
#[test]
fn power_zero_base_negative_exponent_is_refused_not_saturated_ok() {
    let zero = NonNegativeFixed::ZERO;

    for &q in &[-1.0f32, -0.5, -3.0, -16.0] {
        let exponent = SignedFixed::from_bits((q * 65536.0).round() as i32);
        let result = power(zero, exponent);
        assert_ne!(
            result.err,
            u32::MAX,
            "power(0, {q}) reported err == u32::MAX (\"no fault\") for an undefined \
             0^(negative) input; val={:#x}",
            result.val
        );
        assert_eq!(
            result.err,
            StabilityRefusal::UnsupportedDomain as u32,
            "power(0, {q}) should refuse via StabilityRefusal::UnsupportedDomain \
             (matching NonNegativeFixed::saturating_div's and SignedFixed::log2's zero-domain \
             convention), got err={:#x}",
            result.err
        );
    }
}

/// Companion to the negative-exponent regression above: `base = 0` at
/// `exponent == 0` and `exponent > 0` are exact, well-defined results
/// (`0^0 = 1` by this crate's convention, `0^(positive) = 0`) and must
/// keep reporting no fault -- the CMCA-109 fix must not over-refuse.
#[test]
fn power_zero_base_nonnegative_exponent_stays_ok() {
    let zero = NonNegativeFixed::ZERO;

    let zero_exp = SignedFixed::from_bits(0);
    let at_zero = power(zero, zero_exp);
    assert_eq!(
        at_zero.err,
        u32::MAX,
        "power(0, 0) should remain no-fault (0^0 == 1 by this crate's convention)"
    );
    assert_eq!(at_zero.val, NonNegativeFixed::ONE.val);

    for &q in &[0.5f32, 1.0, 3.0, 16.0] {
        let exponent = SignedFixed::from_bits((q * 65536.0).round() as i32);
        let result = power(zero, exponent);
        assert_eq!(
            result.err,
            u32::MAX,
            "power(0, {q}) (positive exponent) should remain no-fault, got err={:#x}",
            result.err
        );
        assert_eq!(
            result.val, 0,
            "power(0, {q}) (positive exponent) should be exactly 0, got {:#x}",
            result.val
        );
    }
}
