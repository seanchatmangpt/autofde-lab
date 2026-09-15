//! # Weighted Small-Gain Theorem: independent numeric verification
//!
//! `allocator::allocate`'s `gd_ok` check tests, at runtime, that the constants in
//! [`crate::generated::stability_profile::PROFILE`] satisfy one specific weighted-diagonal-
//! dominance inequality (for each row $i$: $\sum_j G_{ij} d_j \le (1-\delta) d_i$). That
//! inequality is the *hypothesis* of the Weighted Small-Gain Theorem the profile is named
//! after; it is not itself a check that the theorem's *conclusion* -- $\rho(G) \le 1 - \delta$,
//! where $\rho$ is the spectral radius -- actually holds for these numbers. This module
//! computes that conclusion independently, from scratch, via power iteration, rather than
//! trusting that the row-wise hypothesis and the spectral-radius conclusion agree.
//!
//! It also independently evaluates the companion average-dwell-time bound
//! $$ \tau_D > \frac{\ln(\chi_{\max})}{-\ln(1-\delta)} $$
//! against the profile's declared `minimum_dwell_rounds`.
//!
//! ## No-`std` note
//! This crate is `no_std` by default (see `lib.rs`). `core::f64` does not expose `sqrt`,
//! `ln`, or `powi` (verified: those require linking `std`/libm, unlike `+ - * /` and `.abs()`,
//! which compile to native FP instructions). Adding an external `libm` dependency is out of
//! scope here, so this module carries its own small `ln` (bit-decomposition + atanh series)
//! and avoids `sqrt` entirely by normalizing the power-iteration vector with the infinity
//! norm instead of the Euclidean norm -- valid because `GAIN_MATRIX` is entrywise
//! non-negative, so Perron-Frobenius power iteration converges under any vector norm.

use crate::generated::stability_profile::NonNegativeFixed;

/// Bounded iteration count for the power-iteration spectral-radius estimate.
pub const SPECTRAL_RADIUS_MAX_ITERATIONS: u32 = 200;

/// Power iteration stops early once successive infinity-norm estimates differ by less
/// than this amount.
pub const SPECTRAL_RADIUS_CONVERGENCE_TOLERANCE: f64 = 1e-12;

/// Number of atanh-series terms used by the local `ln` approximation. The series argument
/// is bounded by `1/3` (see [`ln_f64`]), so this many terms is far past the precision a
/// stability margin comparison needs.
const LN_SERIES_TERMS: u32 = 24;

const LN_2: f64 = core::f64::consts::LN_2;

/// Converts a `generated::stability_profile::NonNegativeFixed` to `f64`.
///
/// No existing fixed-point-to-`f64` conversion exists on either `NonNegativeFixed` type in
/// this crate (checked `fixed.rs`: it defines `to_bits`/`to_num`/`log2` on the Q16.16
/// `crate::fixed::NonNegativeFixed`, but no `f64` path, and that is a different type from
/// this module's `crate::generated::stability_profile::NonNegativeFixed` anyway). This
/// mirrors the raw/1e9 scale `allocator::allocate`'s `gd_ok` block already uses directly on
/// `.raw` for these same constants.
fn raw_to_f64(x: NonNegativeFixed) -> f64 {
    x.raw as f64 / 1_000_000_000.0
}

/// Natural log for `x > 0`, implemented without `std`/libm.
///
/// Decomposes the IEEE-754 bit pattern into exponent `e` and mantissa `m` in `[1, 2)` (pure
/// bit manipulation via `to_bits`/`from_bits`, both available in `core`), then evaluates
/// `ln(m)` with the atanh series `ln(m) = 2*atanh((m-1)/(m+1))`, whose argument is at most
/// `1/3` for `m` in `[1, 2)`, so it converges quickly. `ln(x) = e * ln(2) + ln(m)`.
///
/// Only handles normal (non-subnormal) finite positive `f64`, which covers every value this
/// module is called with (proportions and ratios, never near the subnormal range).
fn ln_f64(x: f64) -> f64 {
    if x == 0.0 {
        return f64::NEG_INFINITY;
    }
    if x < 0.0 {
        return f64::NAN;
    }
    let bits = x.to_bits();
    let exponent = ((bits >> 52) & 0x7FF) as i64 - 1023;
    let mantissa_bits = (bits & 0x000F_FFFF_FFFF_FFFF) | 0x3FF0_0000_0000_0000;
    let m = f64::from_bits(mantissa_bits);

    let y = (m - 1.0) / (m + 1.0);
    let y2 = y * y;
    let mut term = y;
    let mut sum = y;
    let mut k = 1u32;
    while k < LN_SERIES_TERMS {
        term *= y2;
        let n = (2 * k + 1) as f64;
        sum += term / n;
        k += 1;
    }
    2.0 * sum + (exponent as f64) * LN_2
}

/// Estimates the spectral radius (Perron root) of a 5x5 non-negative gain matrix via power
/// iteration, normalizing with the infinity norm at each step to avoid needing `sqrt`.
///
/// Runs for at most [`SPECTRAL_RADIUS_MAX_ITERATIONS`], stopping early once successive
/// infinity-norm estimates differ by less than [`SPECTRAL_RADIUS_CONVERGENCE_TOLERANCE`].
pub fn spectral_radius(matrix: &[[NonNegativeFixed; 5]; 5]) -> f64 {
    let mut m = [[0.0f64; 5]; 5];
    for i in 0..5 {
        for j in 0..5 {
            m[i][j] = raw_to_f64(matrix[i][j]);
        }
    }

    let mut v = [1.0f64 / 5.0; 5];
    let mut estimate = 0.0f64;
    let mut iter = 0u32;
    while iter < SPECTRAL_RADIUS_MAX_ITERATIONS {
        let mut w = [0.0f64; 5];
        for i in 0..5 {
            let mut sum = 0.0f64;
            for j in 0..5 {
                sum += m[i][j] * v[j];
            }
            w[i] = sum;
        }

        let mut norm = 0.0f64;
        for wi in w {
            let a = wi.abs();
            if a > norm {
                norm = a;
            }
        }
        if norm == 0.0 {
            // Zero matrix (or the iterate collapsed to zero): spectral radius is 0.
            return 0.0;
        }
        for i in 0..5 {
            v[i] = w[i] / norm;
        }

        let delta = (norm - estimate).abs();
        estimate = norm;
        if delta < SPECTRAL_RADIUS_CONVERGENCE_TOLERANCE {
            break;
        }
        iter += 1;
    }
    estimate
}

/// Theoretically-required minimum average dwell time between mode switches:
/// $$ \tau_D > \frac{\ln(\chi_{\max})}{-\ln(1-\delta)} $$
/// where `delta = contraction_margin` (as `f64`) and `chi_max` is the worst-case ratio by
/// which a mode switch can grow the certificate/Lyapunov function.
///
/// `chi_max` is a required caller-supplied parameter rather than being read off
/// [`crate::generated::stability_profile::StabilityProfile`]: none of that struct's fields
/// clearly represent it. `mode_jump_bound` (0.2 in the real profile) and
/// `total_homeostatic_radius` (0.12) were checked -- both are dimensionally *additive radii*
/// in the same normalized envelope as `certified_switching_radius` and
/// `certified_noise_radius` (all in [0, 1]), not a *multiplicative* growth ratio. A `chi_max`
/// that actually explains the profile's own `minimum_dwell_rounds = 461` at `delta = 0.01`
/// would need to be about 103 (solved from this same formula), which no field is anywhere
/// near. Treating `mode_jump_bound` as `chi_max` anyway would make this check pass trivially
/// (`ln(0.2) < 0`, so any `tau_D >= 0` satisfies it) without actually exercising the bound --
/// worse than an honest parameter. See `stability_profile_is_consistent` for how this is
/// wired against the real profile.
pub fn minimum_dwell_rounds(contraction_margin: NonNegativeFixed, chi_max: f64) -> f64 {
    let delta = raw_to_f64(contraction_margin);
    ln_f64(chi_max) / -ln_f64(1.0 - delta)
}

/// Independently checks both halves of the Weighted Small-Gain / average-dwell-time
/// certificate against the real [`crate::generated::stability_profile::PROFILE`] constants:
///
/// - `.0`: `spectral_radius(PROFILE.gain_matrix) <= 1.0 - delta`, i.e. the theorem's
///   *conclusion* actually holds for these numbers (not just the per-row hypothesis
///   `allocator::allocate`'s `gd_ok` checks at runtime).
/// - `.1`: the dwell-time bound computed by [`minimum_dwell_rounds`] for the given `chi_max`
///   is at or below `PROFILE.minimum_dwell_rounds`, i.e. the profile's declared dwell floor
///   is actually sufficient for that `chi_max`.
///
/// `chi_max` is threaded through from the caller rather than defaulted or fabricated here,
/// for the same reason documented on [`minimum_dwell_rounds`]: no profile field represents
/// it, and inventing a value would defeat the point of an independent check.
pub fn stability_profile_is_consistent(chi_max: f64) -> (bool, bool) {
    let profile = &crate::generated::stability_profile::PROFILE;

    let rho = spectral_radius(&profile.gain_matrix);
    let delta = raw_to_f64(profile.deterministic_margin);
    let gain_ok = rho <= 1.0 - delta;

    let required_dwell = minimum_dwell_rounds(profile.deterministic_margin, chi_max);
    let dwell_ok = required_dwell <= profile.minimum_dwell_rounds as f64;

    (gain_ok, dwell_ok)
}
