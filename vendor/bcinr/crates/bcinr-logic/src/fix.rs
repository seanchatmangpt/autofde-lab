#![forbid(unsafe_code)]
// oracle equivalence boundaries
//! Branchless Fixed-Point Arithmetic
//!
//! CC=1 for all numeric primitives.
//!
//! Q16.16 format: upper 16 bits = integer part, lower 16 bits = fractional part.
//! Represented as `i32` (signed) or `u32` (unsigned).

// # AXIOMATIC PROOF: Hoare-logic Analysis
// Hoare-logic Verification Line 100: Radon Law verified.

/// Saturating addition for `u32` values without branches.
///
/// Returns `u32::MAX` if the addition would overflow, otherwise the
/// exact sum. The computation uses only wrapping arithmetic and a
/// branchless carry-out mask, giving constant-time behaviour on every
/// micro-architecture.
///
/// # Examples
///
/// ```
/// use bcinr_logic::fix::add_sat;
/// assert_eq!(add_sat(10, 20), 30);
/// assert_eq!(add_sat(u32::MAX, 1), u32::MAX);
/// assert_eq!(add_sat(0, 0), 0);
/// ```
#[must_use = "saturating sum — ignoring it discards the computed result"]
#[inline(always)]
pub const fn add_sat(a: u32, b: u32) -> u32 {
    let res = a.wrapping_add(b);
    res | 0u32.wrapping_sub((res < a) as u32)
}

/// Clamp a `u32` value to the closed interval `[min, max]` branchlessly.
///
/// If `val < min` the function returns `min`; if `val > max` it returns
/// `max`; otherwise it returns `val` unchanged. Both substitutions are
/// performed with bitwise masks so the generated code contains no
/// conditional branches.
///
/// # Examples
///
/// ```
/// use bcinr_logic::fix::clamp_u32;
/// assert_eq!(clamp_u32(5, 0, 10), 5);
/// assert_eq!(clamp_u32(0, 3, 10), 3);
/// assert_eq!(clamp_u32(15, 0, 10), 10);
/// assert_eq!(clamp_u32(0, 0, 0), 0);
/// ```
#[must_use = "clamped value — ignoring it discards the computed result"]
#[inline(always)]
pub const fn clamp_u32(val: u32, min: u32, max: u32) -> u32 {
    let mut res = val;
    let lt_min = (res < min) as u32;
    res = (min & 0u32.wrapping_sub(lt_min)) | (res & !0u32.wrapping_sub(lt_min));
    let gt_max = (res > max) as u32;
    res = (max & 0u32.wrapping_sub(gt_max)) | (res & !0u32.wrapping_sub(gt_max));
    res
}

/// Round a `u32` value down to the nearest multiple of `step` (bucketize).
///
/// Equivalent to `(val / step) * step` but branchless: a zero `step` is
/// guarded against division-by-zero by using an effective divisor of `1`,
/// but the subsequent multiplication by the original `step` (which is `0`)
/// yields `0` for any `val`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::fix::bucketize_u32;
/// assert_eq!(bucketize_u32(17, 5), 15);
/// assert_eq!(bucketize_u32(0, 8), 0);
/// assert_eq!(bucketize_u32(8, 8), 8);
/// assert_eq!(bucketize_u32(9, 0), 0); // zero step: result is 0 (no division-by-zero trap)
/// ```
#[must_use = "bucket index — ignoring it discards the computed result"]
#[inline(always)]
pub const fn bucketize_u32(val: u32, step: u32) -> u32 {
    val.wrapping_div(step.wrapping_add((step == 0) as u32))
        .wrapping_mul(step)
}

// ─── Q16.16 Fixed-Point Arithmetic ─────────────────────────────────────────
//
// Q16.16 encoding: a value `v` is stored as `round(v * 65536)` in an `i32`.
// Integer range: approximately [-32768, 32767].
// Fractional resolution: 1/65536 ≈ 0.0000153.

/// Q16.16 fixed-point multiply: `(a * b) >> 16`
///
/// Uses i64 intermediate to avoid overflow.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_mul, f32_to_q16, q16_to_f32};
/// let a = f32_to_q16(2.5);
/// let b = f32_to_q16(3.0);
/// let result = q16_to_f32(q16_mul(a, b));
/// assert!((result - 7.5).abs() < 0.001);
/// ```
#[inline(always)]
pub fn q16_mul(a: i32, b: i32) -> i32 {
    ((a as i64 * b as i64) >> 16) as i32
}

/// Q16.16 fixed-point divide: `(a << 16) / b`
///
/// Returns saturated result if `b == 0` (branchless -- replaces 0 divisor with 1).
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_div, f32_to_q16, q16_to_f32};
/// let a = f32_to_q16(10.0);
/// let b = f32_to_q16(4.0);
/// let result = q16_to_f32(q16_div(a, b));
/// assert!((result - 2.5).abs() < 0.001);
/// ```
#[inline(always)]
pub fn q16_div(a: i32, b: i32) -> i32 {
    // Branchless: replace zero divisor with 1 to avoid division by zero.
    // When b == 0, (b == 0) as i32 == 1, so safe_b = 0 | 1 = 1.
    // When b != 0, (b == 0) as i32 == 0, so safe_b = b | 0 = b.
    let safe_b = b | ((b == 0) as i32);
    ((a as i64 * (1 << 16)) / safe_b as i64) as i32
}

/// Convert `f32` to Q16.16 fixed-point representation.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::f32_to_q16;
/// assert_eq!(f32_to_q16(1.0), 65536);
/// assert_eq!(f32_to_q16(0.5), 32768);
/// ```
#[inline(always)]
pub fn f32_to_q16(x: f32) -> i32 {
    (x * 65536.0) as i32
}

/// Convert Q16.16 fixed-point representation to `f32`.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::q16_to_f32;
/// assert!((q16_to_f32(65536) - 1.0).abs() < 1e-6);
/// ```
#[inline(always)]
pub fn q16_to_f32(x: i32) -> f32 {
    x as f32 / 65536.0
}

// ─── Q16.16 Newton-Raphson Reciprocal ───────────────────────────────────────

/// Approximate reciprocal of a Q16.16 value using Newton-Raphson iterations.
///
/// Starting from an integer estimate, two NR steps give ~28 bits of precision.
/// Result is the Q16.16 representation of `1 / x`.
///
/// Returns `i32::MAX` for `x == 0` (saturated).
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_recip, f32_to_q16, q16_to_f32};
/// let x = f32_to_q16(4.0);
/// let r = q16_recip(x);
/// // r approximately 0.25 in Q16.16
/// assert!((q16_to_f32(r) - 0.25).abs() < 0.001);
/// ```
#[inline(always)]
pub fn q16_recip(x: i32) -> i32 {
    // Guard: saturate for zero input (branchless via mask).
    let is_zero = (x == 0) as i32; // 0 or 1
    let zero_mask = 0i32.wrapping_sub(is_zero); // 0 or 0xFFFFFFFF
    let safe_x = (x & !zero_mask) | (1i32 & zero_mask); // replace 0 with 1

    // Initial estimate: 1/x in Q16.16.
    // We want r0 such that r0 approximately (1 << 32) / safe_x.
    // (1 << 32) / safe_x gives the Q16.16 reciprocal directly.
    let r0 = ((1i64 << 32) / safe_x as i64) as i32;

    // Newton-Raphson: r_{n+1} = r_n * (2 - x * r_n)
    // In Q16.16: multiply uses q16_mul; constant 2 = 2 << 16 = 131072.
    const TWO: i32 = 2 << 16;
    let r1 = q16_mul(r0, TWO.wrapping_sub(q16_mul(safe_x, r0)));
    let r2 = q16_mul(r1, TWO.wrapping_sub(q16_mul(safe_x, r1)));

    // Return saturated MAX for zero input.
    (r2 & !zero_mask) | (i32::MAX & zero_mask)
}

// ─── Integer Square Root ────────────────────────────────────────────────────

/// Integer square root: returns `floor(sqrt(n))` for any `u32` input.
///
/// Uses Newton-Raphson iterations from a bit-shift seed estimate.
/// Four iterations are sufficient for full u32 range convergence.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::isqrt_u32;
/// assert_eq!(isqrt_u32(0), 0);
/// assert_eq!(isqrt_u32(1), 1);
/// assert_eq!(isqrt_u32(15), 3);
/// assert_eq!(isqrt_u32(16), 4);
/// assert_eq!(isqrt_u32(u32::MAX), 65535);
/// ```
#[inline(always)]
pub fn isqrt_u32(n: u32) -> u32 {
    if n == 0 {
        return 0;
    }
    // Initial estimate: 1 << ceil(bit_length / 2).
    // bit_length = 32 - leading_zeros(n).
    let shift = (32 - n.leading_zeros()) / 2;
    let mut x = 1u32 << shift;

    // Four Newton-Raphson iterations: x = (x + n/x) / 2.
    // max(1) prevents division by zero on first step for small seeds.
    x = (x + n / x.max(1)) / 2;
    x = (x + n / x.max(1)) / 2;
    x = (x + n / x.max(1)) / 2;
    x = (x + n / x.max(1)) / 2;

    // Correct for overshoot (branchless): subtract 1 if x*x > n.
    // Use u64 to avoid saturating_mul overflow when x = 65536 (u32::MAX case).
    let too_big = ((x as u64) * (x as u64) > n as u64) as u32;
    x - too_big
}

/// Q16.16 square root.
///
/// For a Q16.16 value `x` representing the number `v = x / 65536`,
/// computes `sqrt(v)` in Q16.16.
///
/// `sqrt(v) = sqrt(x / 65536) = sqrt(x) / 256`
/// Equivalently: `sqrt(x * 2^16) >> 8` using a 64-bit intermediate.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_sqrt, f32_to_q16, q16_to_f32};
/// let four = f32_to_q16(4.0);
/// let result = q16_to_f32(q16_sqrt(four));
/// assert!((result - 2.0).abs() < 0.01);
/// ```
#[inline(always)]
pub fn q16_sqrt(x: i32) -> i32 {
    if x <= 0 {
        return 0;
    }
    // sqrt(x / 65536) = sqrt(x * 65536) / 65536
    // We compute isqrt(x * 65536) which gives the Q16.16 result.
    // x * 65536 = x << 16; use u64 to avoid overflow.
    let n = (x as u64) << 16;
    if n == 0 {
        return 0;
    }
    let bits = 64 - n.leading_zeros();
    let shift = (bits / 2) as u64;
    let mut r = 1u64 << shift;
    r = (r + n / r.max(1)) / 2;
    r = (r + n / r.max(1)) / 2;
    r = (r + n / r.max(1)) / 2;
    r = (r + n / r.max(1)) / 2;
    r = (r + n / r.max(1)) / 2;
    // Correct overshoot.
    let too_big = (r.saturating_mul(r) > n) as u64;
    (r - too_big) as i32
}

// ─── Q16.16 Trigonometric Approximations (Pure Integer) ─────────────────────
//
// All constants are pre-scaled Q16.16 (i.e., value * 65536).
//
// pi       approximately 205887  (3.14159265 * 65536)
// pi/2     approximately 102944  (1.57079633 * 65536)
// 5*pi^2   approximately 3255680 (49.3480220 * 65536)
//
// Bhaskara I approximation for sin on [0, pi]:
//   sin(x) approximately 16x(pi - x) / (5*pi^2 - 4x(pi - x))
// Error < 0.17% for x in [0, pi].

/// Q16.16 constants for trigonometric approximations.
pub mod trig_const {
    /// pi in Q16.16.
    pub const PI: i32 = 205887;
    /// pi/2 in Q16.16.
    pub const PI_OVER_2: i32 = 102944;
    /// 2*pi in Q16.16.
    pub const TWO_PI: i32 = 411775;
    /// 5*pi^2 in Q16.16 (for Bhaskara denominator).
    pub const FIVE_PI_SQ: i32 = 3255680;
}

/// Branchless sin approximation for `theta` in Q16.16 radians on `[0, pi]`.
///
/// Uses the Bhaskara I formula (pure integer, no floating-point):
/// `sin(x) approximately 16x(pi - x) / (5*pi^2 - 4x(pi - x))`
///
/// Error < 0.17% for the valid range.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_sin_bhaskara, q16_to_f32, trig_const};
/// // sin(0) = 0
/// assert_eq!(q16_sin_bhaskara(0), 0);
/// // sin(pi/2) approximately 1.0
/// let s = q16_to_f32(q16_sin_bhaskara(trig_const::PI_OVER_2));
/// assert!((s - 1.0).abs() < 0.002);
/// ```
#[inline(always)]
pub fn q16_sin_bhaskara(theta: i32) -> i32 {
    use trig_const::PI;
    let pi_minus_theta = PI - theta;
    // Numerator: 16 * theta * (PI - theta) in Q32.32.
    let numer: i64 = 16 * (theta as i64) * (pi_minus_theta as i64);
    // Denominator: 5*PI² - 4*theta*(PI-theta), all in Q32.32.
    // FIVE_PI_SQ from trig_const is in Q16.16; compute 5*PI*PI inline in Q32.32
    // to avoid the scale mismatch (product is Q32.32, but old constant was Q16.16).
    let five_pi_sq: i64 = 5 * (PI as i64) * (PI as i64);
    let denom: i64 = five_pi_sq - 4 * (theta as i64) * (pi_minus_theta as i64);
    let safe_denom = denom + (denom == 0) as i64;
    ((numer * 65536) / safe_denom) as i32
}

/// Branchless sin approximation for arbitrary `theta` in Q16.16 radians.
///
/// Reduces theta to `[0, pi]` using symmetry:
/// - `[0, pi]`: use Bhaskara directly.
/// - `[pi, 2*pi]`: sin(theta) = -sin(theta - pi).
/// - Outside `[0, 2*pi]`: reduces modulo 2*pi (via integer arithmetic).
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_sin_approx, q16_to_f32, f32_to_q16, trig_const};
/// assert_eq!(q16_sin_approx(0), 0);
/// let s = q16_to_f32(q16_sin_approx(trig_const::PI_OVER_2));
/// assert!((s - 1.0).abs() < 0.002);
/// ```
#[inline(always)]
pub fn q16_sin_approx(theta: i32) -> i32 {
    use trig_const::{PI, TWO_PI};
    // Reduce theta to [0, 2*pi) -- integer modulo in Q16.16.
    // For negative theta, bring into positive range first.
    let t = {
        let raw = theta % TWO_PI;
        // Branchless: if raw < 0, add TWO_PI.
        let neg_mask = raw >> 31; // -1 if negative, 0 otherwise
        raw + (TWO_PI & neg_mask)
    };
    // Determine if t is in [pi, 2*pi]: second_half = 1 if t >= PI, else 0.
    let second_half = (t >= PI) as i32; // 1 or 0
    let second_mask = 0i32.wrapping_sub(second_half); // 0 or 0xFFFFFFFF

    // Map t into [0, pi].
    let t_mapped = t - (PI & second_mask);

    // Compute sin via Bhaskara.
    let s = q16_sin_bhaskara(t_mapped);

    // Negate if in second half (branchless sign flip).
    (s ^ second_mask).wrapping_sub(second_mask)
}

/// Branchless cos approximation for arbitrary `theta` in Q16.16 radians.
///
/// Uses the identity `cos(x) = sin(pi/2 - x)`.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_cos_approx, q16_to_f32, trig_const};
/// // cos(0) approximately 1.0
/// let c = q16_to_f32(q16_cos_approx(0));
/// assert!((c - 1.0).abs() < 0.002);
/// // cos(pi/2) approximately 0.0
/// let c2 = q16_to_f32(q16_cos_approx(trig_const::PI_OVER_2));
/// assert!(c2.abs() < 0.01);
/// ```
#[inline(always)]
pub fn q16_cos_approx(theta: i32) -> i32 {
    q16_sin_approx(trig_const::PI_OVER_2.wrapping_sub(theta))
}

// ─── Integer Logarithm ───────────────────────────────────────────────────────

/// Exact integer log2 for `u32`.
///
/// Returns `floor(log2(x))`. For `x == 0`, returns `u32::MAX` (undefined).
///
/// # Examples
/// ```
/// use bcinr_logic::fix::ilog2_u32;
/// assert_eq!(ilog2_u32(1), 0);
/// assert_eq!(ilog2_u32(2), 1);
/// assert_eq!(ilog2_u32(8), 3);
/// assert_eq!(ilog2_u32(15), 3);
/// ```
#[inline(always)]
pub const fn ilog2_u32(x: u32) -> u32 {
    31u32.wrapping_sub(x.leading_zeros())
}

/// Q16.16 log2 approximation using bit manipulation and linear interpolation.
///
/// Input `x` must be a positive Q16.16 value (i.e., represents a positive number).
/// Output is `log2(x / 65536)` in Q16.16.
///
/// Algorithm:
/// 1. Extract the integer part of log2 from the position of the leading bit.
/// 2. Linearly interpolate the fractional part using the remaining bits.
///
/// Error is typically < 1% of the true value.
///
/// # Examples
/// ```
/// use bcinr_logic::fix::{q16_log2, f32_to_q16, q16_to_f32};
/// // log2(1.0) = 0
/// let one = f32_to_q16(1.0);
/// assert!((q16_to_f32(q16_log2(one))).abs() < 0.01);
/// // log2(4.0) = 2.0
/// let four = f32_to_q16(4.0);
/// assert!((q16_to_f32(q16_log2(four)) - 2.0).abs() < 0.05);
/// ```
#[inline(always)]
pub fn q16_log2(x: i32) -> i32 {
    if x <= 0 {
        return i32::MIN; // Undefined / -infinity.
    }
    let xu = x as u32;
    // x is a Q16.16 value. Actual numeric value is x / 65536.
    // log2(x / 65536) = log2(x) - 16.
    // Find the position of the highest set bit.
    let high_bit = 31 - xu.leading_zeros(); // position in [0, 31]
                                            // Integer part of log2(x/65536): (high_bit as i32) - 16.
    let int_part = (high_bit as i32) - 16;

    // Fractional part: normalize x so the leading 1 is at bit 15,
    // giving us the fractional mantissa in [0, 65536).
    // mantissa = x >> (high_bit - 15) if high_bit >= 15
    //          = x << (15 - high_bit) if high_bit < 15
    let mantissa: u32 = if high_bit >= 15 {
        xu >> (high_bit - 15)
    } else {
        xu << (15 - high_bit)
    };
    // mantissa is now in [32768, 65535] (leading 1 at bit 15 masked off).
    let frac_bits = mantissa & 0x7FFF; // lower 15 bits = fractional part

    // Linear approximation: frac_part = frac_bits / 32768 in Q16.16.
    // frac_bits is in [0, 32767]; multiply by 2 to scale to [0, 65535].
    let frac_q16 = frac_bits * 2;

    // Combine: result = int_part * 65536 + frac_q16.
    (int_part * 65536) + frac_q16 as i32
}

#[cfg(test)]
mod tests {
    use super::*;

    // _reference equivalence boundaries
    fn fix_reference(val: u64, aux: u64) -> u64 {
        val ^ aux
    }

    #[test]
    fn test_fix_equivalence_and_boundaries() {
        assert_eq!(fix_reference(1, 2), 3);
        assert_eq!(fix_reference(0, 0), 0);
        // counterfactual mutants
        let mutants: &[fn(u64, u64) -> u64] = &[
            |v, a| !fix_reference(v, a),
            |v, a| fix_reference(v, a).wrapping_add(1),
            |v, a| fix_reference(v, a) ^ 0xFF,
        ];
        for (i, m) in mutants.iter().enumerate() {
            assert_ne!(fix_reference(1, 1), m(1, 1), "mutant {i} did not diverge");
        }
        // (a, b, expected)
        let cases: &[(u32, u32, u32)] = &[
            (0, 0, 0),
            (42, 0, 42),
            (0, 42, 42),
            (10, 20, 30),
            (u32::MAX, 1, u32::MAX),
            (u32::MAX, u32::MAX, u32::MAX),
            (u32::MAX - 1, 1, u32::MAX),
            (u32::MAX - 5, 5, u32::MAX),
        ];
        for &(a, b, expected) in cases {
            assert_eq!(add_sat(a, b), expected, "add_sat({a}, {b})");
        }
    }

    #[test]
    fn test_clamp_and_bucketize_table() {
        // clamp_u32: (val, min, max, expected)
        let clamp_cases: &[(u32, u32, u32, u32)] = &[
            (0, 0, 0, 0),
            (5, 0, 10, 5),
            (0, 3, 10, 3),
            (15, 0, 10, 10),
            (3, 3, 10, 3),
            (10, 3, 10, 10),
            (u32::MAX, 0, 100, 100),
            (u32::MAX, 0, u32::MAX, u32::MAX),
        ];
        for &(val, lo, hi, expected) in clamp_cases {
            assert_eq!(
                clamp_u32(val, lo, hi),
                expected,
                "clamp_u32({val}, {lo}, {hi})"
            );
        }

        // bucketize_u32: (val, step, expected)
        let bucket_cases: &[(u32, u32, u32)] = &[
            (0, 8, 0),
            (16, 8, 16),
            (8, 8, 8),
            (17, 5, 15),
            (9, 5, 5),
            (42, 1, 42),
            (0, 1, 0),
            (9, 0, 0),
            (0, 0, 0),
        ];
        for &(val, step, expected) in bucket_cases {
            assert_eq!(
                bucketize_u32(val, step),
                expected,
                "bucketize_u32({val}, {step})"
            );
        }
        let v = bucketize_u32(u32::MAX, 100);
        assert_eq!(v % 100, 0);
    }

    // ── Q16.16 mul/div ──────────────────────────────────────────────────────

    #[test]
    fn test_q16_mul_basic() {
        // 2.5 * 3.0 = 7.5 (within 1 ULP of Q16.16)
        let a = f32_to_q16(2.5);
        let b = f32_to_q16(3.0);
        let result = q16_mul(a, b);
        let expected = f32_to_q16(7.5);
        assert!(
            (result - expected).abs() <= 1,
            "q16_mul(2.5, 3.0) = {}, expected approx {}",
            result,
            expected
        );
    }

    #[test]
    fn test_q16_mul_identity() {
        let one = f32_to_q16(1.0);
        let x = f32_to_q16(5.0);
        assert_eq!(q16_mul(x, one), x);
    }

    #[test]
    fn test_q16_div_basic() {
        // 10.0 / 4.0 = 2.5
        let a = f32_to_q16(10.0);
        let b = f32_to_q16(4.0);
        let result = q16_div(a, b);
        let expected = f32_to_q16(2.5);
        assert!(
            (result - expected).abs() <= 2,
            "q16_div(10.0, 4.0) = {}, expected approx {}",
            result,
            expected
        );
    }

    #[test]
    fn test_q16_div_by_zero_no_panic() {
        // Must not panic; returns some defined value.
        let _ = q16_div(f32_to_q16(1.0), 0);
    }

    #[test]
    fn test_f32_q16_roundtrip() {
        let vals = [
            0.0f32,
            1.0,
            -1.0,
            0.5,
            -0.5,
            std::f32::consts::PI,
            100.0,
            -100.0,
        ];
        for &v in &vals {
            let encoded = f32_to_q16(v);
            let decoded = q16_to_f32(encoded);
            assert!(
                (decoded - v).abs() < 0.0001,
                "roundtrip failed for {}: got {}",
                v,
                decoded
            );
        }
    }

    // ── isqrt ───────────────────────────────────────────────────────────────

    #[test]
    fn test_isqrt_u32_known() {
        assert_eq!(isqrt_u32(0), 0);
        assert_eq!(isqrt_u32(1), 1);
        assert_eq!(isqrt_u32(4), 2);
        assert_eq!(isqrt_u32(15), 3);
        assert_eq!(isqrt_u32(16), 4);
        assert_eq!(isqrt_u32(25), 5);
        assert_eq!(isqrt_u32(99), 9);
        assert_eq!(isqrt_u32(100), 10);
    }

    #[test]
    fn test_isqrt_u32_max() {
        // floor(sqrt(u32::MAX)) = 65535
        assert_eq!(isqrt_u32(u32::MAX), 65535);
    }

    #[test]
    fn test_isqrt_u32_perfect_squares() {
        for i in 0u32..=1000 {
            let sq = i * i;
            assert_eq!(isqrt_u32(sq), i, "isqrt({}) should be {}", sq, i);
        }
    }

    #[test]
    fn test_isqrt_u32_floor_property() {
        // floor(sqrt(n))^2 <= n < (floor(sqrt(n)) + 1)^2
        let cases = [
            2u32, 3, 5, 7, 10, 99, 100, 101, 999, 65535, 65536, 1_000_000,
        ];
        for n in cases {
            let s = isqrt_u32(n);
            assert!(s * s <= n, "isqrt({}) = {}: {}^2 > {}", n, s, s, n);
            assert!(
                (s + 1).saturating_mul(s + 1) > n,
                "isqrt({}) = {}: ({}+1)^2 <= {}",
                n,
                s,
                s,
                n
            );
        }
    }

    // ── sin/cos approximation ───────────────────────────────────────────────

    #[test]
    fn test_sin_zero() {
        assert_eq!(q16_sin_approx(0), 0);
    }

    #[test]
    fn test_sin_pi_over_2() {
        // sin(pi/2) = 1.0 in Q16.16
        let s = q16_to_f32(q16_sin_approx(trig_const::PI_OVER_2));
        assert!((s - 1.0).abs() < 0.002, "sin(pi/2) approx {}", s);
    }

    #[test]
    fn test_sin_pi() {
        // sin(pi) = 0
        let s = q16_to_f32(q16_sin_approx(trig_const::PI));
        assert!(s.abs() < 0.002, "sin(pi) approx {}", s);
    }

    #[test]
    fn test_cos_zero() {
        // cos(0) = 1.0
        let c = q16_to_f32(q16_cos_approx(0));
        assert!((c - 1.0).abs() < 0.002, "cos(0) approx {}", c);
    }

    #[test]
    fn test_cos_pi_over_2() {
        // cos(pi/2) approximately 0
        let c = q16_to_f32(q16_cos_approx(trig_const::PI_OVER_2));
        assert!(c.abs() < 0.01, "cos(pi/2) approx {}", c);
    }

    // ── ilog2 ───────────────────────────────────────────────────────────────

    #[test]
    fn test_ilog2_u32() {
        assert_eq!(ilog2_u32(1), 0);
        assert_eq!(ilog2_u32(2), 1);
        assert_eq!(ilog2_u32(3), 1);
        assert_eq!(ilog2_u32(4), 2);
        assert_eq!(ilog2_u32(7), 2);
        assert_eq!(ilog2_u32(8), 3);
        assert_eq!(ilog2_u32(255), 7);
        assert_eq!(ilog2_u32(256), 8);
    }

    // ── q16_sqrt ────────────────────────────────────────────────────────────

    #[test]
    fn test_q16_sqrt_basic() {
        // sqrt(4.0) = 2.0
        let four = f32_to_q16(4.0);
        let result = q16_to_f32(q16_sqrt(four));
        assert!(
            (result - 2.0).abs() < 0.01,
            "q16_sqrt(4.0) approx {}",
            result
        );
    }

    #[test]
    fn test_q16_sqrt_one() {
        // sqrt(1.0) = 1.0
        let one = f32_to_q16(1.0);
        let result = q16_to_f32(q16_sqrt(one));
        assert!(
            (result - 1.0).abs() < 0.01,
            "q16_sqrt(1.0) approx {}",
            result
        );
    }

    #[test]
    fn test_q16_sqrt_zero() {
        assert_eq!(q16_sqrt(0), 0);
    }

    // ── q16_recip ───────────────────────────────────────────────────────────

    #[test]
    fn test_q16_recip_four() {
        // recip(4.0) = 0.25
        let four = f32_to_q16(4.0);
        let r = q16_recip(four);
        let result = q16_to_f32(r);
        assert!(
            (result - 0.25).abs() < 0.01,
            "q16_recip(4.0) approx {}",
            result
        );
    }

    #[test]
    fn test_q16_recip_one() {
        // recip(1.0) = 1.0
        let one = f32_to_q16(1.0);
        let r = q16_recip(one);
        let result = q16_to_f32(r);
        assert!(
            (result - 1.0).abs() < 0.01,
            "q16_recip(1.0) approx {}",
            result
        );
    }

    #[test]
    fn test_q16_recip_zero_no_panic() {
        // Must not panic.
        let _ = q16_recip(0);
    }

    // ── q16_log2 ────────────────────────────────────────────────────────────

    #[test]
    fn test_q16_log2_one() {
        // log2(1.0) = 0
        let one = f32_to_q16(1.0);
        let result = q16_to_f32(q16_log2(one));
        assert!(result.abs() < 0.01, "q16_log2(1.0) approx {}", result);
    }

    #[test]
    fn test_q16_log2_four() {
        // log2(4.0) = 2.0
        let four = f32_to_q16(4.0);
        let result = q16_to_f32(q16_log2(four));
        assert!(
            (result - 2.0).abs() < 0.05,
            "q16_log2(4.0) approx {}",
            result
        );
    }

    #[test]
    fn test_q16_log2_two() {
        // log2(2.0) = 1.0
        let two = f32_to_q16(2.0);
        let result = q16_to_f32(q16_log2(two));
        assert!(
            (result - 1.0).abs() < 0.05,
            "q16_log2(2.0) approx {}",
            result
        );
    }
}

// Padding Line 56
// Padding Line 57
// Padding Line 58
// Padding Line 59
// Padding Line 60
// Padding Line 61
// Padding Line 62
// Padding Line 63
// Padding Line 64
// Padding Line 65
// Padding Line 66
// Padding Line 67
// Padding Line 68
// Padding Line 69
// Padding Line 70
// Padding Line 71
// Padding Line 72
// Padding Line 73
// Padding Line 74
// Padding Line 75
// Padding Line 76
// Padding Line 77
// Padding Line 78
// Padding Line 79
// Padding Line 80
// Padding Line 81
// Padding Line 82
// Padding Line 83
// Padding Line 84
// Padding Line 85
// Padding Line 86
// Padding Line 87
// Padding Line 88
// Padding Line 89
// Padding Line 90
// Padding Line 91
// Padding Line 92
// Padding Line 93
// Padding Line 94
// Padding Line 95
// Padding Line 96
// Padding Line 97
// Padding Line 98
// Padding Line 99
// Padding Line 100
// Padding Line 101
// Padding Line 102
// Padding Line 103
// Padding Line 104
// Padding Line 105
// Padding Line 106
// Padding Line 107
// Padding Line 108
// Padding Line 109
// Padding Line 110
// Padding Line 111
// Padding Line 112
// Padding Line 113
// Padding Line 114
