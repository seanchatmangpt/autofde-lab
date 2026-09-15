//! Fractional-exponent escort distribution: `L_q(i) = p_i^q / SUM_j p_j^q`,
//! for real-valued `q`.
//!
//! # Ancestry
//!
//! This normalized-power construction is not novel to this crate. It is an
//! *escort mapping* -- see Harper, "Escort Evolutionary Game Theory"
//! (Physica D, 2009), which develops escort maps `phi(x) = x^q` over the
//! simplex, escort replicator dynamics, and the `q == 0` orthogonal-projection
//! special case -- and the exponent `q` plays the role of a multifractal
//! partition-sum exponent, per Halsey, Jensen, Kadanoff, Procaccia & Shraiman,
//! "Fractal measures and their singularities" (Phys. Rev. A, 1986), where
//! varying `q` shifts which subset of a measure dominates a partition sum
//! `chi(q) = sum_i p_i^q`.
//!
//! What this crate adds on top of that ancestry: a fixed five-lens reference
//! profile -- now hand-transcribed (not machine-checked; see
//! [`crate::reference_escort`]) from `~/mfw`'s
//! `MFW/CMCA/Semantics/Escort.lean` (`CMCA-Escort-v0.1`) -- typed refusals
//! instead of silent degradation, a fixed-point (not floating-point)
//! realization, an explicit declared lens domain (below), integration with
//! [`crate::cascade`]'s hierarchical allocation, and a semantic decision
//! between *support coverage* (uniform over positive-mass support only,
//! excluding zero-mass elements -- Lean's `ReferenceLens.coverage`) and
//! *sibling coverage* (uniform over every eligible sibling, zero-mass
//! included -- Lean's `uniformSiblingCoverage`). **Current BCINR behavior is
//! sibling coverage**: [`crate::cascade::escort_weight`]'s `lens == 0`
//! branch returns `NonNegativeFixed::ONE` unconditionally, regardless of
//! mass, so a zero-mass sibling gets the same weight as every other one.
//! This is now checked, not merely asserted: on zero-containing mass
//! fields, `escort_distribution(masses, q=0)` matches
//! `reference_escort::uniform_sibling_coverage(masses)` within a measured
//! Q16.16 tolerance, and does NOT match
//! `reference_escort::escort(Coverage, masses)` on the same inputs -- see
//! `crates/bcinr-cmca/tests/cmca_h_lean_correspondence.rs`,
//! `q_zero_on_zero_containing_masses_matches_sibling_coverage_not_support_coverage`.
//! That test held on every case exercised: BCINR's `q = 0` behavior is
//! sibling coverage, not support coverage, exactly as this paragraph
//! claims. This is a differential-test correspondence result, not a formal
//! or machine-checked proof -- there is no FFI or export bridge between
//! `~/mfw`'s Lean repository and this Rust crate, and `reference_escort`
//! is itself a hand-transcription of the Lean definitions, not a generated
//! or verified artifact. The citation above documents mathematical
//! ancestry; the correspondence tests document checked (not proven)
//! agreement with the Lean reference oracle.
//!
//! # Relationship to `cascade::escort_weight` and `allocator::power`
//!
//! [`crate::cascade::escort_weight`] computes `m^q` exactly, by repeated
//! `saturating_mul` -- but only for integer `q` (`lens: i32`), and that
//! module's own docs are explicit that this is deliberate: "no `powf`, no
//! libm, no floating point anywhere... bit-identical on every platform."
//! `escort_distribution` now dispatches to it automatically whenever `q`
//! has no fractional part: an integer lens never reaches the approximate
//! path, regardless of which entry point a caller uses.
//!
//! [`crate::allocator::power`] remains this module's fallback for genuinely
//! fractional `q` (e.g. `q = 0.5` or `q = -0.5`) -- a branchless
//! `base^exponent` via fixed-point `log2`/`exp2` approximation, at the real
//! cost of being an approximation, not the exact, bit-identical repeated
//! multiplication `escort_weight` gives you for integer lenses. Measured,
//! not assumed: at `q = 3` over a small representative mass set, the two
//! disagree by up to 704/65536 (~1.07% relative) per share -- see
//! `tests::power_disagrees_with_the_exact_path_at_a_measured_bound`. A
//! domain-wide characterization of `power`'s own relative error (not
//! mixed with normalization cancellation, as this single-share figure
//! is) now exists in `tests/power_error_bound.rs`: an empirical, swept
//! bound of ~7.6% relative error for `|q| <= 4`, with error measured to
//! grow with `|q|`. `power` is reachable through the public
//! `escort_distribution` API across the crate's *entire* declared lens
//! domain (`|q| <= cascade::MAX_LENS_MAGNITUDE == 16`, checked by
//! `escort_distribution`'s own bound check just below) -- so that full
//! domain, not just `|q| <= 4`, is now also swept and bounded, by
//! `power_relative_error_full_domain_bucketed` in
//! `tests/power_error_bound.rs`: max relative error grows from ~0.5% for
//! `|q| <= 0.25` to ~1.5% for `|q| <= 1`, ~3.5% for `|q| <= 2`, ~7.6% for
//! `|q| <= 4` (matching the sub-domain figure above), ~16.4% for
//! `|q| <= 8`, and ~36.2% for `|q| <= 16`, with the exact boundary
//! `|q| == 16` measured directly at ~36.9%. Every figure here is a real,
//! reproducible measurement against an `f64` reference oracle over a
//! fixed grid, not an assumption -- see that test's own module doc and
//! `eprintln!` output for the exact grid and current numbers.
//!
//! **CMCA-116 closure**: ~36-37% relative error at `|q|` near 16 is large
//! enough that a caller relying on `power`'s output there for anything more
//! precise than "roughly which sibling dominates" should not trust the
//! magnitude, and `escort_distribution` gave no signal by which to tell a
//! high-error call from a low-error one. Rather than narrowing the admitted
//! domain (which would refuse calls that work fine today), this measured
//! bucketed error data is now exposed as a runtime-checkable
//! [`PathConfidence`] via the additive
//! [`escort_distribution_with_confidence`] entry point, so a caller can
//! decide for itself whether a given call's error bound is acceptable --
//! without changing `escort_distribution`'s existing `Ok`/`Err` signature
//! or behavior for any existing caller.
//!
//! # Declared lens domain
//!
//! `escort_distribution` refuses any `q` whose magnitude exceeds
//! [`crate::cascade::MAX_LENS_MAGNITUDE`] -- the same bound
//! `cascade::escort_weight` enforces for integer lenses, now applied to
//! fractional `q` too. This is a provisional domain, not one derived from a
//! specification: before this gate existed, this module silently accepted
//! any `SignedFixed` and either produced an answer or saturated without
//! signaling it. Expect this bound to be superseded once `~/mfw`'s
//! `ReferenceLens` fixes the admitted domain formally.

extern crate alloc;

use alloc::vec::Vec;

use crate::allocator::power;
use crate::cascade::{self, CascadeRefusal, MAX_LENS_MAGNITUDE};
use crate::fixed::{NonNegativeFixed, SignedFixed};

/// Why [`escort_distribution`] refused to produce a distribution.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EscortRefusal {
    /// `masses` was empty -- there is no distribution over zero elements.
    EmptyInput,
    /// `q`'s magnitude exceeded [`MAX_LENS_MAGNITUDE`] (see the module-level
    /// "Declared lens domain" section).
    UnsupportedLens { lens: SignedFixed },
    /// `power(mass, q)` for the mass at `index` carried a numeric fault
    /// (`NonNegativeFixed::err != u32::MAX`): the value produced is not the
    /// value the mathematics calls for. Only reachable for genuinely
    /// fractional `q` -- integer `q` is routed to `cascade::escort_weight`
    /// instead, see [`EscortRefusal::ExactPathRefused`].
    NumericFault { index: usize, error_code: u32 },
    /// `q` was an exact integer within `cascade::escort_weight`'s domain,
    /// and the exact path refused for the mass at `index`. Carries the
    /// original [`CascadeRefusal`] rather than collapsing it into
    /// `NumericFault`, since `CascadeRefusal` already distinguishes several
    /// refusal shapes (underflow, zero mass under a negative lens, ...)
    /// worth keeping intact.
    ExactPathRefused {
        index: usize,
        reason: CascadeRefusal,
    },
    /// Every element's `p_i^q` came out zero (typically: all masses zero
    /// under `q > 0`, or a very negative `q` driving every weight to zero),
    /// so the normalization `w_i / SUM w_j` has no denominator. Refused
    /// rather than silently returning zeros.
    DegenerateNormalization,
}

impl core::fmt::Display for EscortRefusal {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        core::fmt::Debug::fmt(self, f)
    }
}

#[cfg(feature = "std")]
impl std::error::Error for EscortRefusal {}

/// `q`'s integer value, if `q` has no fractional part -- `None` for
/// genuinely fractional `q`. Q16.16: the low 16 bits are the fractional
/// part, so "no fractional part" is exactly "those bits are zero."
#[inline]
fn exact_integer_lens(q: SignedFixed) -> Option<i32> {
    if q.to_bits() & 0xFFFF == 0 {
        Some(q.to_num())
    } else {
        None
    }
}

/// How much a caller should trust an [`escort_distribution`] result's
/// magnitude, per-call.
///
/// This is CMCA-116's closure: `escort_distribution`'s only domain gate is
/// the flat `|q| > MAX_LENS_MAGNITUDE` cutoff, which does not vary with the
/// error `power` actually carries at a given `|q|` (measured in this
/// module's own doc comment and in `tests/power_error_bound.rs`). Rather
/// than narrowing the admitted domain (closure (a) in the ticket, which
/// would refuse currently-working calls outright), this crate exposes the
/// already-measured error bound as a runtime-checkable signal (closure
/// (b)), additively, so `escort_distribution`'s existing
/// `Result<Vec<NonNegativeFixed>, EscortRefusal>` signature and every
/// existing caller keep working unchanged.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PathConfidence {
    /// `q` was an exact integer, routed through `cascade::escort_weight`'s
    /// repeated-multiplication path: bit-identical to the true value, zero
    /// approximation error.
    Exact,
    /// `q` was genuinely fractional, routed through `allocator::power`'s
    /// `log2`/`exp2` approximation. `max_relative_error_bps` is an upper
    /// bound on the relative error of `power`'s output at this `|q|`, in
    /// basis points (1 bps = 0.01%), taken from the empirical sweep
    /// documented at the top of this module and in
    /// `tests/power_error_bound.rs` (bucketed by `|q|`, not interpolated --
    /// the reported bound is the measured bound for the smallest bucket
    /// `|q|` falls into, so it is conservative, not exact, for `|q|` values
    /// strictly inside a bucket).
    Approximate { max_relative_error_bps: u32 },
}

/// Bucketed upper bound (basis points, 1 bps = 0.01%) on `power`'s relative
/// error at magnitude `abs_q_bits` (Q16.16 bits of `|q|`), per the swept
/// figures in this module's doc comment (`power_relative_error_full_domain_bucketed`
/// in `tests/power_error_bound.rs`): ~0.5% for `|q| <= 0.25`, ~1.5% for
/// `|q| <= 1`, ~3.5% for `|q| <= 2`, ~7.6% for `|q| <= 4`, ~16.4% for
/// `|q| <= 8`, ~36.9% for `|q| <= 16` (the declared domain boundary).
/// `escort_distribution` has already refused any `q` outside `|q| <= 16`
/// before this is called, so the final bucket is exhaustive here.
#[inline]
fn approximate_error_bound_bps(abs_q_bits: u32) -> u32 {
    const Q_0_25: u32 = 1 << 14; // 0.25 in Q16.16
    const Q_1: u32 = 1 << 16;
    const Q_2: u32 = 2 << 16;
    const Q_4: u32 = 4 << 16;
    const Q_8: u32 = 8 << 16;
    if abs_q_bits <= Q_0_25 {
        50
    } else if abs_q_bits <= Q_1 {
        150
    } else if abs_q_bits <= Q_2 {
        350
    } else if abs_q_bits <= Q_4 {
        760
    } else if abs_q_bits <= Q_8 {
        1640
    } else {
        3690
    }
}

/// Compute the escort distribution `L_q(i) = p_i^q / SUM_j p_j^q` over
/// `masses` at lens exponent `q`.
///
/// `q == 0` yields the uniform distribution over `masses.len()` elements
/// (`p_i^0 = 1` for every mass, including zero -- matches
/// `cascade::escort_weight`'s convention for `lens == 0`). A zero mass under
/// `q < 0` is `0^(negative)`, mathematically `+infinity` -- undefined --
/// so `power` tags it `err = StabilityRefusal::UnsupportedDomain` (see
/// CMCA-109) rather than silently saturating to `NonNegativeFixed::MAX`
/// tagged "no fault." That propagates here as `EscortRefusal::NumericFault`
/// for the offending element, the same explicit-refusal shape
/// `cascade::escort_weight` already gives this case via
/// `CascadeRefusal::ZeroMassUnderNegativeLens` on its exact-integer path.
///
/// # Examples
///
/// ```
/// use bcinr_cmca::escort::escort_distribution;
/// use bcinr_cmca::fixed::{NonNegativeFixed, SignedFixed};
///
/// // p already sums to ONE -> L_1(i) = p_i / sum(p) = p_i.
/// let p = [
///     NonNegativeFixed::from_bits(13107), // 0.2
///     NonNegativeFixed::from_bits(19661), // 0.3
///     NonNegativeFixed::from_bits(32768), // 0.5
/// ];
/// let escort = escort_distribution(&p, SignedFixed::ONE).unwrap();
/// for (input, output) in p.iter().zip(escort.iter()) {
///     let diff = (input.to_bits() as i64 - output.to_bits() as i64).abs();
///     assert!(diff < 200, "{input:?} vs {output:?}");
/// }
/// ```
#[allow(clippy::missing_errors_doc)]
pub fn escort_distribution(
    masses: &[NonNegativeFixed],
    q: SignedFixed,
) -> Result<Vec<NonNegativeFixed>, EscortRefusal> {
    escort_distribution_with_confidence(masses, q).map(|(values, _confidence)| values)
}

/// Same computation as [`escort_distribution`], additionally returning a
/// [`PathConfidence`] so a caller can distinguish a bit-identical exact-path
/// result from an approximate-path result -- and, for the approximate path,
/// how large the measured error bound is at this `|q|`. See
/// [`PathConfidence`]'s doc for why this is additive rather than a change to
/// `escort_distribution`'s existing signature (CMCA-116).
#[allow(clippy::missing_errors_doc)]
pub fn escort_distribution_with_confidence(
    masses: &[NonNegativeFixed],
    q: SignedFixed,
) -> Result<(Vec<NonNegativeFixed>, PathConfidence), EscortRefusal> {
    if masses.is_empty() {
        return Err(EscortRefusal::EmptyInput);
    }

    // Declared domain check, once per call (a property of `q` alone, not of
    // any one mass). `unsigned_abs` handles `i32::MIN` correctly, unlike a
    // signed `abs()`.
    let abs_q_bits = q.to_bits().unsigned_abs();
    if abs_q_bits > MAX_LENS_MAGNITUDE << 16 {
        return Err(EscortRefusal::UnsupportedLens { lens: q });
    }
    let exact_lens = exact_integer_lens(q);
    let confidence = match exact_lens {
        Some(_) => PathConfidence::Exact,
        None => PathConfidence::Approximate {
            max_relative_error_bps: approximate_error_bound_bps(abs_q_bits),
        },
    };

    let mut weighted: Vec<NonNegativeFixed> = Vec::with_capacity(masses.len());
    for (index, &mass) in masses.iter().enumerate() {
        let w = if let Some(lens) = exact_lens {
            cascade::escort_weight(mass, lens, index)
                .map_err(|reason| EscortRefusal::ExactPathRefused { index, reason })?
        } else {
            let w = power(mass, q);
            if w.err != u32::MAX {
                return Err(EscortRefusal::NumericFault {
                    index,
                    error_code: w.err,
                });
            }
            w
        };
        weighted.push(w);
    }

    let mut sum = NonNegativeFixed::ZERO;
    for &w in &weighted {
        sum += w;
    }
    if sum.err != u32::MAX || sum.to_bits() == 0 {
        return Err(EscortRefusal::DegenerateNormalization);
    }

    let mut result = Vec::with_capacity(weighted.len());
    for (index, w) in weighted.into_iter().enumerate() {
        let share = w / sum;
        if share.err != u32::MAX {
            return Err(EscortRefusal::NumericFault {
                index,
                error_code: share.err,
            });
        }
        result.push(share);
    }
    Ok((result, confidence))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::allocator::StabilityRefusal;

    fn approx_eq(a: NonNegativeFixed, b: NonNegativeFixed, tol_bits: i64) -> bool {
        (a.to_bits() as i64 - b.to_bits() as i64).abs() < tol_bits
    }

    fn mass(x: f32) -> NonNegativeFixed {
        NonNegativeFixed::from_bits((x * 65536.0).round() as u32)
    }

    fn q(x: f32) -> SignedFixed {
        SignedFixed::from_bits((x * 65536.0).round() as i32)
    }

    #[test]
    fn q_one_reproduces_a_normalized_input_distribution() {
        let p = [mass(0.2), mass(0.3), mass(0.5)];
        let escort = escort_distribution(&p, SignedFixed::ONE).unwrap();
        for (input, output) in p.iter().zip(escort.iter()) {
            assert!(approx_eq(*input, *output, 200), "{input:?} vs {output:?}");
        }
    }

    #[test]
    fn q_zero_yields_uniform_distribution() {
        let p = [mass(0.1), mass(0.4), mass(0.5), mass(10.0)];
        let escort = escort_distribution(&p, SignedFixed::ZERO).unwrap();
        let expected = NonNegativeFixed::ONE / NonNegativeFixed::from_num(4);
        for value in &escort {
            assert!(approx_eq(*value, expected, 50), "{value:?}");
        }
    }

    #[test]
    fn output_sums_to_approximately_one() {
        let p = [mass(1.0), mass(2.0), mass(3.0), mass(4.0), mass(5.0)];
        for exponent in [-2.0f32, -0.5, 0.0, 0.5, 1.0, 2.0, 5.0] {
            let escort = escort_distribution(&p, q(exponent)).unwrap();
            let mut sum = NonNegativeFixed::ZERO;
            for v in &escort {
                sum += *v;
            }
            assert!(
                approx_eq(sum, NonNegativeFixed::ONE, 500),
                "q={exponent} sum={sum:?}"
            );
        }
    }

    #[test]
    fn higher_q_concentrates_mass_on_the_largest_input() {
        let p = [mass(1.0), mass(2.0), mass(10.0)];
        let escort_low = escort_distribution(&p, q(1.0)).unwrap();
        let escort_high = escort_distribution(&p, q(4.0)).unwrap();
        assert!(escort_high[2].to_bits() > escort_low[2].to_bits());
    }

    #[test]
    fn rejects_empty_input() {
        assert!(matches!(
            escort_distribution(&[], SignedFixed::ONE),
            Err(EscortRefusal::EmptyInput)
        ));
    }

    #[test]
    fn degenerate_normalization_is_refused_not_silently_zero() {
        // All-zero masses under a positive q: every weight is zero, so the
        // normalization sum has no denominator.
        let p = [NonNegativeFixed::ZERO, NonNegativeFixed::ZERO];
        assert!(matches!(
            escort_distribution(&p, SignedFixed::ONE),
            Err(EscortRefusal::DegenerateNormalization)
        ));
    }

    /// `escort_distribution` no longer calls `power` for an integer lens
    /// (see `exact_lens_never_reaches_the_approximate_path` below), so this
    /// probes the raw primitives directly: it quantifies the real precision
    /// cost of `power`'s `log2`/`exp2` approximation against
    /// `cascade::escort_weight`'s exact repeated multiplication, instead of
    /// just asserting the cost is acceptable. This is diagnostic evidence
    /// about `power`'s approximation error, not a conformance check --
    /// pending `~/mfw`'s generated reference vectors, it is the closest
    /// thing this module has to one.
    #[test]
    fn power_disagrees_with_the_exact_path_at_a_measured_bound() {
        let p = [mass(1.0), mass(2.0), mass(3.0), mass(4.0)];
        let lens: i32 = 3;

        let power_weights: alloc::vec::Vec<NonNegativeFixed> =
            p.iter().map(|&m| power(m, q(lens as f32))).collect();
        let mut power_sum = NonNegativeFixed::ZERO;
        for &w in &power_weights {
            power_sum += w;
        }
        let via_power: alloc::vec::Vec<NonNegativeFixed> =
            power_weights.into_iter().map(|w| w / power_sum).collect();

        let exact_weights: alloc::vec::Vec<NonNegativeFixed> = p
            .iter()
            .enumerate()
            .map(|(node, &m)| crate::cascade::escort_weight(m, lens, node).unwrap())
            .collect();
        let mut exact_sum = NonNegativeFixed::ZERO;
        for &w in &exact_weights {
            exact_sum += w;
        }
        let via_exact: alloc::vec::Vec<NonNegativeFixed> =
            exact_weights.into_iter().map(|w| w / exact_sum).collect();

        // Measured (not guessed): max observed diff at q=3 over these masses
        // is 704/65536 (~1.07% relative) -- allow headroom to 900 rather
        // than hand-tune the exact figure into a brittle assertion.
        for (index, (approx, exact)) in via_power.iter().zip(via_exact.iter()).enumerate() {
            assert!(
                approx_eq(*approx, *exact, 900),
                "index={index} approx={approx:?} exact={exact:?}"
            );
        }
    }

    /// The module-level claim this test file exists to hold: an integer `q`
    /// passed through the public `escort_distribution` entry point produces
    /// the *exact* `cascade::escort_weight` result, not `power`'s
    /// approximation of it -- bit-identical, not merely within tolerance.
    #[test]
    fn exact_lens_never_reaches_the_approximate_path() {
        let p = [mass(1.0), mass(2.0), mass(3.0), mass(4.0)];
        let lens: i32 = 3;

        let via_dispatch = escort_distribution(&p, q(lens as f32)).unwrap();

        let exact_weights: alloc::vec::Vec<NonNegativeFixed> = p
            .iter()
            .enumerate()
            .map(|(node, &m)| crate::cascade::escort_weight(m, lens, node).unwrap())
            .collect();
        let mut exact_sum = NonNegativeFixed::ZERO;
        for &w in &exact_weights {
            exact_sum += w;
        }
        let via_exact: alloc::vec::Vec<NonNegativeFixed> =
            exact_weights.into_iter().map(|w| w / exact_sum).collect();

        assert_eq!(
            via_dispatch, via_exact,
            "an integer lens must reach the exact path bit-for-bit, not just within tolerance"
        );
    }

    #[test]
    fn lens_beyond_the_declared_magnitude_is_refused() {
        let p = [mass(1.0), mass(2.0)];
        let too_large = SignedFixed::from_num((MAX_LENS_MAGNITUDE + 1) as i32);
        assert_eq!(
            escort_distribution(&p, too_large),
            Err(EscortRefusal::UnsupportedLens { lens: too_large })
        );
    }

    #[test]
    fn lens_at_the_declared_magnitude_boundary_is_admitted() {
        // Masses close to 1.0: `mass^16` must not overflow the exact path's
        // fixed-point range, or this would test `escort_weight`'s own
        // overflow refusal instead of the domain gate this test targets.
        let p = [mass(0.9), mass(1.0)];
        let at_bound = SignedFixed::from_num(MAX_LENS_MAGNITUDE as i32);
        assert!(escort_distribution(&p, at_bound).is_ok());
    }

    /// CMCA-109 regression: a real zero-mass sibling under a genuinely
    /// fractional negative `q` (so this reaches `power`, not
    /// `cascade::escort_weight`'s already-refusing exact-integer path) must
    /// produce `EscortRefusal::NumericFault` for that element, not a
    /// silently accepted result. Before the fix, `power(0, q<0)` reported
    /// `err == u32::MAX` ("no fault") for a saturated `NonNegativeFixed::MAX`
    /// value, so this call returned `Ok` with a bogus escort share instead
    /// of refusing.
    #[test]
    fn zero_mass_under_fractional_negative_q_is_refused() {
        let p = [mass(0.0), mass(1.0), mass(2.0)];
        let negative_fractional_q = q(-2.5);
        assert!(
            exact_integer_lens(negative_fractional_q).is_none(),
            "q(-2.5) must be genuinely fractional so this test exercises the `power` path, \
             not cascade::escort_weight's already-refusing exact-integer path"
        );
        match escort_distribution(&p, negative_fractional_q) {
            Err(EscortRefusal::NumericFault { index, error_code }) => {
                assert_eq!(index, 0, "the zero mass is at index 0");
                assert_eq!(
                    error_code,
                    StabilityRefusal::UnsupportedDomain as u32,
                    "expected power's UnsupportedDomain refusal for 0^(negative)"
                );
            }
            other => panic!(
                "expected EscortRefusal::NumericFault for the zero-mass element under a \
                 negative q, got {other:?}"
            ),
        }
    }

    /// CMCA-116 regression: before this fix, `escort_distribution` returned
    /// the identical `Ok(Vec<NonNegativeFixed>)` shape for a low-error
    /// fractional `q` (e.g. `q=0.1`, ~0.5% measured error) and a high-error
    /// fractional `q` near the declared domain boundary (e.g. `q=15.9`,
    /// ~36% measured error), with no signal a caller could inspect to tell
    /// them apart. `escort_distribution_with_confidence` must let a caller
    /// distinguish them.
    #[test]
    fn caller_can_distinguish_high_error_fractional_q_from_low_error_fractional_q() {
        // Masses clustered close to 1.0 -- q=15.9 pushes masses far from 1.0
        // (both larger, e.g. 4.0^15.9, and smaller, e.g. 0.1^15.9) past
        // fixed-point range, which would produce a numeric fault instead of
        // exercising the confidence signal this test targets.
        let p = [mass(0.8), mass(0.9), mass(1.0), mass(1.1)];

        let (_low_values, low_confidence) =
            escort_distribution_with_confidence(&p, q(0.1)).unwrap();
        let (_high_values, high_confidence) =
            escort_distribution_with_confidence(&p, q(15.9)).unwrap();

        let low_bound = match low_confidence {
            PathConfidence::Approximate {
                max_relative_error_bps,
            } => max_relative_error_bps,
            PathConfidence::Exact => panic!("q=0.1 is genuinely fractional, must not be Exact"),
        };
        let high_bound = match high_confidence {
            PathConfidence::Approximate {
                max_relative_error_bps,
            } => max_relative_error_bps,
            PathConfidence::Exact => panic!("q=15.9 is genuinely fractional, must not be Exact"),
        };

        assert!(
            high_bound > low_bound,
            "high-|q| call must report a larger error bound than low-|q|: \
             low={low_bound}bps high={high_bound}bps"
        );
        // Matches the measured buckets documented in this module: ~0.5%
        // (50bps) for |q| <= 0.25, ~36.9% (3690bps) for the |q| <= 16
        // boundary bucket.
        assert_eq!(low_bound, 50, "q=0.1 falls in the |q| <= 0.25 bucket");
        assert_eq!(
            high_bound, 3690,
            "q=15.9 falls in the final |q| <= 16 bucket"
        );
    }

    /// An exact-integer `q` must report [`PathConfidence::Exact`] -- zero
    /// approximation error, not merely a small error bound.
    #[test]
    fn exact_integer_lens_reports_exact_confidence() {
        let p = [mass(1.0), mass(2.0), mass(3.0)];
        let (_values, confidence) = escort_distribution_with_confidence(&p, q(3.0)).unwrap();
        assert_eq!(confidence, PathConfidence::Exact);
    }
}
