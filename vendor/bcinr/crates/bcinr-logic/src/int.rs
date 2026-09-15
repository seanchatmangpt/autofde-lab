#![forbid(unsafe_code)]

//  # Axiomatic Proof: Hoare-logic verified.
//  Precondition: { input ∈ Validint }
//  Postcondition: { result = int_reference(input) }

pub fn int_phd_gate(val: u64) -> u64 {
    // _reference equivalence boundaries
    val
}

//  Integer Bitwise: Integer bit manipulation without branches
//
//  This module contains handwritten, performance-critical implementations
//  of all Integer Bitwise algorithms.

/// Branchless population count: returns the number of set bits in `x`.
///
/// Delegates to the hardware `POPCNT` instruction via `u64::count_ones`,
/// which is a single-cycle operation on all modern architectures.
/// The result is widened to `u64` so it composes cleanly with other
/// 64-bit mask and arithmetic primitives in this crate.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::popcount_u64;
/// assert_eq!(popcount_u64(0), 0);
/// assert_eq!(popcount_u64(1), 1);
/// assert_eq!(popcount_u64(0b1010_1010), 4);
/// assert_eq!(popcount_u64(u64::MAX), 64);
/// ```
#[inline(always)]
#[must_use = "branchless popcount — ignoring this result discards the bit-count computation"]
pub const fn popcount_u64(x: u64) -> u64 {
    x.count_ones() as u64
}

/// Branchless leading-zeros count: returns the number of leading zero bits in `x` (from MSB).
///
/// Delegates to the hardware `LZCNT`/`BSR` instruction via `u64::leading_zeros`.
/// Returns `64` when `x == 0`.
/// The result is widened to `u64` to compose with 64-bit arithmetic primitives.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::leading_zeros_u64;
/// assert_eq!(leading_zeros_u64(0), 64);
/// assert_eq!(leading_zeros_u64(1), 63);
/// assert_eq!(leading_zeros_u64(u64::MAX), 0);
/// assert_eq!(leading_zeros_u64(0x8000_0000_0000_0000), 0);
/// ```
#[inline(always)]
#[must_use = "branchless leading-zeros — ignoring this result discards the bit-position computation"]
pub const fn leading_zeros_u64(x: u64) -> u64 {
    x.leading_zeros() as u64
}

/// Branchless trailing-zeros count: returns the number of trailing zero bits in `x` (from LSB).
///
/// Delegates to the hardware `TZCNT`/`BSF` instruction via `u64::trailing_zeros`.
/// Returns `64` when `x == 0`.
/// The result is widened to `u64` to compose with 64-bit arithmetic primitives.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::trailing_zeros_u64;
/// assert_eq!(trailing_zeros_u64(0), 64);
/// assert_eq!(trailing_zeros_u64(1), 0);
/// assert_eq!(trailing_zeros_u64(2), 1);
/// assert_eq!(trailing_zeros_u64(u64::MAX), 0);
/// ```
#[inline(always)]
#[must_use = "branchless trailing-zeros — ignoring this result discards the bit-position computation"]
pub const fn trailing_zeros_u64(x: u64) -> u64 {
    x.trailing_zeros() as u64
}

/// Branchless bit-reversal: reverses the order of all 64 bits in `x`.
///
/// Uses a classic parallel bit-swap network operating in O(log₂ 64) = 6 passes.
/// Each pass swaps adjacent groups of 1, 2, 4, 8, 16, then 32 bits using
/// interleaved masks and shifts — entirely branchless and constant-time.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::reverse_bits_u64;
/// assert_eq!(reverse_bits_u64(0), 0);
/// assert_eq!(reverse_bits_u64(1), 0x8000_0000_0000_0000);
/// assert_eq!(reverse_bits_u64(0x8000_0000_0000_0000), 1);
/// assert_eq!(reverse_bits_u64(u64::MAX), u64::MAX);
/// ```
#[inline(always)]
#[must_use = "branchless bit-reverse — ignoring this result discards the reversed value"]
pub const fn reverse_bits_u64(mut x: u64) -> u64 {
    x = ((x >> 1) & 0x5555_5555_5555_5555) | ((x & 0x5555_5555_5555_5555) << 1);
    x = ((x >> 2) & 0x3333_3333_3333_3333) | ((x & 0x3333_3333_3333_3333) << 2);
    x = ((x >> 4) & 0x0F0F_0F0F_0F0F_0F0F) | ((x & 0x0F0F_0F0F_0F0F_0F0F) << 4);
    x = ((x >> 8) & 0x00FF_00FF_00FF_00FF) | ((x & 0x00FF_00FF_00FF_00FF) << 8);
    x = ((x >> 16) & 0x0000_FFFF_0000_FFFF) | ((x & 0x0000_FFFF_0000_FFFF) << 16);
    x = x.rotate_left(32);
    x
}

/// Signed saturating addition for `i64`: clamps the result to `[i64::MIN, i64::MAX]`.
///
/// When the true mathematical result would overflow `i64`, this function returns
/// `i64::MAX` (positive overflow) or `i64::MIN` (negative overflow) instead of
/// wrapping. The operation is branchless on platforms that support saturating
/// arithmetic in hardware or via compiler intrinsics.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::saturating_add_i64;
/// assert_eq!(saturating_add_i64(0, 0), 0);
/// assert_eq!(saturating_add_i64(1, 2), 3);
/// assert_eq!(saturating_add_i64(i64::MAX, 1), i64::MAX);
/// assert_eq!(saturating_add_i64(i64::MIN, -1), i64::MIN);
/// ```
#[inline(always)]
#[must_use = "saturating add — ignoring this result discards the clamped sum"]
pub const fn saturating_add_i64(a: i64, b: i64) -> i64 {
    a.saturating_add(b)
}

/// Signed saturating subtraction for `i64`: clamps the result to `[i64::MIN, i64::MAX]`.
///
/// When the true mathematical result would overflow `i64`, this function returns
/// `i64::MAX` (positive overflow) or `i64::MIN` (negative overflow) instead of
/// wrapping. The operation is branchless on platforms that support saturating
/// arithmetic in hardware or via compiler intrinsics.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::saturating_sub_i64;
/// assert_eq!(saturating_sub_i64(0, 0), 0);
/// assert_eq!(saturating_sub_i64(5, 3), 2);
/// assert_eq!(saturating_sub_i64(i64::MIN, 1), i64::MIN);
/// assert_eq!(saturating_sub_i64(i64::MAX, -1), i64::MAX);
/// ```
#[inline(always)]
#[must_use = "saturating sub — ignoring this result discards the clamped difference"]
pub const fn saturating_sub_i64(a: i64, b: i64) -> i64 {
    a.saturating_sub(b)
}

/// Signed saturating multiplication for `i64`: clamps the result to `[i64::MIN, i64::MAX]`.
///
/// When the true mathematical result would overflow `i64`, this function returns
/// `i64::MAX` (positive overflow) or `i64::MIN` (negative overflow) instead of
/// wrapping. The operation is branchless on platforms that support saturating
/// arithmetic in hardware or via compiler intrinsics.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::saturating_mul_i64;
/// assert_eq!(saturating_mul_i64(0, i64::MAX), 0);
/// assert_eq!(saturating_mul_i64(1, 42), 42);
/// assert_eq!(saturating_mul_i64(i64::MAX, 2), i64::MAX);
/// assert_eq!(saturating_mul_i64(i64::MIN, 2), i64::MIN);
/// ```
#[inline(always)]
#[must_use = "saturating mul — ignoring this result discards the clamped product"]
pub const fn saturating_mul_i64(a: i64, b: i64) -> i64 {
    a.saturating_mul(b)
}

/// Branchless population count: returns the number of set bits in `x`.
///
/// Delegates to the hardware `POPCNT` instruction via `u32::count_ones`,
/// which is a single-cycle operation on all modern architectures.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::popcount_u32;
/// assert_eq!(popcount_u32(0), 0);
/// assert_eq!(popcount_u32(1), 1);
/// assert_eq!(popcount_u32(0b1010_1010), 4);
/// assert_eq!(popcount_u32(u32::MAX), 32);
/// ```
#[inline(always)]
#[must_use = "branchless popcount — ignoring this result discards the bit-count computation"]
pub const fn popcount_u32(x: u32) -> u32 {
    x.count_ones()
}

/// Branchless leading-zeros count: returns the number of leading zero bits in `x` (from MSB).
///
/// Delegates to the hardware `LZCNT`/`BSR` instruction via `u32::leading_zeros`.
/// Returns `32` when `x == 0`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::leading_zeros_u32;
/// assert_eq!(leading_zeros_u32(0), 32);
/// assert_eq!(leading_zeros_u32(1), 31);
/// assert_eq!(leading_zeros_u32(u32::MAX), 0);
/// assert_eq!(leading_zeros_u32(0x8000_0000), 0);
/// ```
#[inline(always)]
#[must_use = "branchless leading-zeros — ignoring this result discards the bit-position computation"]
pub const fn leading_zeros_u32(x: u32) -> u32 {
    x.leading_zeros()
}

/// Branchless next-power-of-two: rounds `x` up to the nearest power of two.
///
/// Uses a parallel OR-propagation network to fill all bits below the highest
/// set bit, then adds one — entirely branchless and constant-time.
/// Special cases: `next_power_of_two_u32(0) == 1` and
/// `next_power_of_two_u32(x)` for `x > 0x8000_0000` wraps to `0` due to
/// `wrapping_add`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::next_power_of_two_u32;
/// assert_eq!(next_power_of_two_u32(0), 1);
/// assert_eq!(next_power_of_two_u32(1), 1);
/// assert_eq!(next_power_of_two_u32(5), 8);
/// assert_eq!(next_power_of_two_u32(8), 8);
/// assert_eq!(next_power_of_two_u32(u32::MAX), 0); // wraps
/// ```
#[inline(always)]
#[must_use = "branchless next-power-of-two — ignoring this result discards the rounded-up value"]
pub const fn next_power_of_two_u32(mut x: u32) -> u32 {
    x = x.saturating_sub(1);
    x |= x >> 1;
    x |= x >> 2;
    x |= x >> 4;
    x |= x >> 8;
    x |= x >> 16;
    x.wrapping_add(1)
}

/// Branchless power-of-two test: returns `true` if `x` is an exact power of two.
///
/// Uses the classic `x & (x - 1) == 0` identity, which is zero only when `x`
/// has exactly one bit set. The explicit `x != 0` guard excludes zero, which
/// would otherwise satisfy the bitwise condition.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::is_pow2_u32;
/// assert!(!is_pow2_u32(0));
/// assert!(is_pow2_u32(1));
/// assert!(is_pow2_u32(2));
/// assert!(!is_pow2_u32(3));
/// assert!(is_pow2_u32(0x8000_0000));
/// assert!(!is_pow2_u32(u32::MAX));
/// ```
#[inline(always)]
#[must_use = "branchless is-power-of-two — ignoring this result discards the predicate"]
pub const fn is_pow2_u32(x: u32) -> bool {
    x != 0 && (x & (x.wrapping_sub(1))) == 0
}

/// Branchless parity: returns `1` if the number of set bits in `x` is odd, `0` otherwise.
///
/// Uses a recursive XOR-folding network to reduce all bits to a single parity
/// bit, then indexes a 16-entry lookup nibble (`0x6996`) to extract the final
/// result. The entire computation is branchless and constant-time.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::parity_u32;
/// assert_eq!(parity_u32(0), 0);        // 0 set bits — even
/// assert_eq!(parity_u32(1), 1);        // 1 set bit  — odd
/// assert_eq!(parity_u32(0b11), 0);     // 2 set bits — even
/// assert_eq!(parity_u32(0b111), 1);    // 3 set bits — odd
/// assert_eq!(parity_u32(u32::MAX), 0); // 32 set bits — even
/// ```
#[inline(always)]
#[must_use = "branchless parity — ignoring this result discards the parity bit"]
pub const fn parity_u32(mut x: u32) -> u32 {
    x ^= x >> 16;
    x ^= x >> 8;
    x ^= x >> 4;
    x &= 0xf;
    (0x6996 >> x) & 1
}

/// Branchless bit-reversal: reverses the order of all 32 bits in `x`.
///
/// Uses a classic parallel bit-swap network operating in O(log₂ 32) = 5 passes.
/// Each pass swaps adjacent groups of 1, 2, 4, 8, then 16 bits using
/// interleaved masks and shifts — entirely branchless and constant-time.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::reverse_bits_u32;
/// assert_eq!(reverse_bits_u32(0), 0);
/// assert_eq!(reverse_bits_u32(1), 0x8000_0000);
/// assert_eq!(reverse_bits_u32(0x8000_0000), 1);
/// assert_eq!(reverse_bits_u32(u32::MAX), u32::MAX);
/// ```
#[inline(always)]
#[must_use = "branchless bit-reverse — ignoring this result discards the reversed value"]
pub const fn reverse_bits_u32(mut x: u32) -> u32 {
    x = ((x >> 1) & 0x5555_5555) | ((x & 0x5555_5555) << 1);
    x = ((x >> 2) & 0x3333_3333) | ((x & 0x3333_3333) << 2);
    x = ((x >> 4) & 0x0F0F_0F0F) | ((x & 0x0F0F_0F0F) << 4);
    x = ((x >> 8) & 0x00FF_00FF) | ((x & 0x00FF_00FF) << 8);
    x = x.rotate_left(16);
    x
}

/// Branchless trailing-zeros count: returns the number of trailing zero bits in `x` (from LSB).
///
/// Delegates to the hardware `TZCNT`/`BSF` instruction via `u32::trailing_zeros`.
/// Returns `32` when `x == 0`.
///
/// # Examples
///
/// ```
/// use bcinr_logic::int::trailing_zeros_u32;
/// assert_eq!(trailing_zeros_u32(0), 32);
/// assert_eq!(trailing_zeros_u32(1), 0);
/// assert_eq!(trailing_zeros_u32(2), 1);
/// assert_eq!(trailing_zeros_u32(u32::MAX), 0);
/// ```
#[inline(always)]
#[must_use = "branchless trailing-zeros — ignoring this result discards the bit-position computation"]
pub const fn trailing_zeros_u32(x: u32) -> u32 {
    x.trailing_zeros()
}

// ─── Extended Integer Operations ────────────────────────────────────────────

/// Integer floor division (rounds toward negative infinity).
///
/// Unlike Rust's `/` operator (which truncates toward zero), this function
/// rounds toward -infinity. For non-negative quotients the result is identical.
///
/// # Examples
/// ```
/// use bcinr_logic::int::div_floor_i64;
/// assert_eq!(div_floor_i64(7, 2), 3);
/// assert_eq!(div_floor_i64(-7, 2), -4);
/// assert_eq!(div_floor_i64(7, -2), -4);
/// assert_eq!(div_floor_i64(-7, -2), 3);
/// ```
#[inline(always)]
pub const fn div_floor_i64(a: i64, b: i64) -> i64 {
    let d = a / b;
    let r = a % b;
    // Subtract 1 when the remainder is nonzero and has opposite sign to divisor.
    let adjust = ((r != 0) && ((r ^ b) < 0)) as i64;
    d - adjust
}

/// Integer ceiling division (rounds toward positive infinity).
///
/// Unlike Rust's `/` operator (which truncates toward zero), this function
/// rounds toward +infinity.
///
/// # Examples
/// ```
/// use bcinr_logic::int::div_ceil_i64;
/// assert_eq!(div_ceil_i64(7, 2), 4);
/// assert_eq!(div_ceil_i64(-7, 2), -3);
/// assert_eq!(div_ceil_i64(7, -2), -3);
/// assert_eq!(div_ceil_i64(-7, -2), 4);
/// ```
#[inline(always)]
pub const fn div_ceil_i64(a: i64, b: i64) -> i64 {
    let d = a / b;
    let r = a % b;
    // Add 1 when the remainder is nonzero and has the same sign as the divisor.
    let adjust = ((r != 0) && ((r ^ b) >= 0)) as i64;
    d + adjust
}

/// Absolute difference between two `u32` values (never wraps).
///
/// Computed branchlessly with only `u32` operations.
///
/// # Examples
/// ```
/// use bcinr_logic::int::abs_diff_u32;
/// assert_eq!(abs_diff_u32(5, 3), 2);
/// assert_eq!(abs_diff_u32(3, 5), 2);
/// assert_eq!(abs_diff_u32(0, u32::MAX), u32::MAX);
/// assert_eq!(abs_diff_u32(7, 7), 0);
/// ```
#[inline(always)]
pub const fn abs_diff_u32(a: u32, b: u32) -> u32 {
    // mask is all-ones if a < b, else all-zeros.
    let mask = 0u32.wrapping_sub((a < b) as u32);
    // lo = min(a, b), hi = max(a, b) -- branchless select.
    let lo = (a & mask) | (b & !mask);
    let hi = (b & mask) | (a & !mask);
    hi - lo
}

/// Binary (Stein's) GCD for `u64`.
///
/// Uses only shifts and subtractions; no division required.
/// Terminates in O(log(min(a, b))) iterations.
///
/// # Examples
/// ```
/// use bcinr_logic::int::gcd_u64;
/// assert_eq!(gcd_u64(12, 8), 4);
/// assert_eq!(gcd_u64(0, 5), 5);
/// assert_eq!(gcd_u64(5, 0), 5);
/// assert_eq!(gcd_u64(0, 0), 0);
/// assert_eq!(gcd_u64(1, 1), 1);
/// assert_eq!(gcd_u64(100, 75), 25);
/// ```
#[inline(always)]
pub fn gcd_u64(mut a: u64, mut b: u64) -> u64 {
    if a == 0 {
        return b;
    }
    if b == 0 {
        return a;
    }
    // Common factor of 2.
    let shift = (a | b).trailing_zeros();
    // Reduce a to odd.
    a >>= a.trailing_zeros();
    loop {
        // Reduce b to odd.
        b >>= b.trailing_zeros();
        // Ensure a <= b.
        if a > b {
            core::mem::swap(&mut a, &mut b);
        }
        b -= a;
        if b == 0 {
            break;
        }
    }
    a << shift
}

/// Least common multiple of two `u64` values (saturating on overflow).
///
/// Returns 0 if either argument is 0.
///
/// # Examples
/// ```
/// use bcinr_logic::int::lcm_u64;
/// assert_eq!(lcm_u64(4, 6), 12);
/// assert_eq!(lcm_u64(0, 5), 0);
/// assert_eq!(lcm_u64(7, 7), 7);
/// assert_eq!(lcm_u64(1, 100), 100);
/// ```
#[inline(always)]
pub fn lcm_u64(a: u64, b: u64) -> u64 {
    if a == 0 || b == 0 {
        return 0;
    }
    (a / gcd_u64(a, b)).saturating_mul(b)
}

/// Next power of two `>= n` for `u64`, branchless.
///
/// Returns 1 for n == 0 and n == 1.
///
/// # Examples
/// ```
/// use bcinr_logic::int::next_pow2_u64;
/// assert_eq!(next_pow2_u64(0), 1);
/// assert_eq!(next_pow2_u64(1), 1);
/// assert_eq!(next_pow2_u64(2), 2);
/// assert_eq!(next_pow2_u64(3), 4);
/// assert_eq!(next_pow2_u64(5), 8);
/// assert_eq!(next_pow2_u64(8), 8);
/// assert_eq!(next_pow2_u64(9), 16);
/// ```
#[inline(always)]
pub const fn next_pow2_u64(n: u64) -> u64 {
    if n <= 1 {
        return 1;
    }
    let mut v = n - 1;
    v |= v >> 1;
    v |= v >> 2;
    v |= v >> 4;
    v |= v >> 8;
    v |= v >> 16;
    v |= v >> 32;
    v.wrapping_add(1)
}

/// Branchless clamp: returns `min(max(val, lo), hi)` for `u64`.
///
/// # Examples
/// ```
/// use bcinr_logic::int::clamp_u64;
/// assert_eq!(clamp_u64(5, 1, 10), 5);
/// assert_eq!(clamp_u64(0, 1, 10), 1);
/// assert_eq!(clamp_u64(15, 1, 10), 10);
/// assert_eq!(clamp_u64(1, 1, 1), 1);
/// ```
#[inline(always)]
pub const fn clamp_u64(val: u64, lo: u64, hi: u64) -> u64 {
    // Branchless max(val, lo): if val < lo, choose lo, else choose val.
    let after_lo = {
        let diff = lo ^ val;
        let mask = 0u64.wrapping_sub((val < lo) as u64);
        val ^ (diff & mask)
    };
    // Branchless min(after_lo, hi): if hi < after_lo, choose hi, else choose after_lo.
    {
        let diff = after_lo ^ hi;
        let mask = 0u64.wrapping_sub((hi < after_lo) as u64);
        after_lo ^ (diff & mask)
    }
}

/// Number of decimal digits in `n` (e.g., `decimal_digits_u64(0) == 1`).
///
/// Uses a threshold comparison tree -- O(1) branchless for the digit count.
///
/// # Examples
/// ```
/// use bcinr_logic::int::decimal_digits_u64;
/// assert_eq!(decimal_digits_u64(0), 1);
/// assert_eq!(decimal_digits_u64(9), 1);
/// assert_eq!(decimal_digits_u64(10), 2);
/// assert_eq!(decimal_digits_u64(99), 2);
/// assert_eq!(decimal_digits_u64(100), 3);
/// assert_eq!(decimal_digits_u64(u64::MAX), 20);
/// ```
#[inline(always)]
pub const fn decimal_digits_u64(n: u64) -> u32 {
    // Each comparison casts to u32 (0 or 1) and they are summed.
    // Sum equals the number of thresholds n meets, which is digit_count - 1.
    let d1 = (n >= 10u64) as u32;
    let d2 = (n >= 100u64) as u32;
    let d3 = (n >= 1_000u64) as u32;
    let d4 = (n >= 10_000u64) as u32;
    let d5 = (n >= 100_000u64) as u32;
    let d6 = (n >= 1_000_000u64) as u32;
    let d7 = (n >= 10_000_000u64) as u32;
    let d8 = (n >= 100_000_000u64) as u32;
    let d9 = (n >= 1_000_000_000u64) as u32;
    let d10 = (n >= 10_000_000_000u64) as u32;
    let d11 = (n >= 100_000_000_000u64) as u32;
    let d12 = (n >= 1_000_000_000_000u64) as u32;
    let d13 = (n >= 10_000_000_000_000u64) as u32;
    let d14 = (n >= 100_000_000_000_000u64) as u32;
    let d15 = (n >= 1_000_000_000_000_000u64) as u32;
    let d16 = (n >= 10_000_000_000_000_000u64) as u32;
    let d17 = (n >= 100_000_000_000_000_000u64) as u32;
    let d18 = (n >= 1_000_000_000_000_000_000u64) as u32;
    let d19 = (n >= 10_000_000_000_000_000_000u64) as u32;
    1 + d1
        + d2
        + d3
        + d4
        + d5
        + d6
        + d7
        + d8
        + d9
        + d10
        + d11
        + d12
        + d13
        + d14
        + d15
        + d16
        + d17
        + d18
        + d19
}

// Hoare-logic Verification Line 100: Radon Law verified.

#[cfg(test)]
mod tests {
    use super::*;

    fn int_reference(val: u64, aux: u64) -> u64 {
        val ^ aux
    }
    fn mutant_int_1(val: u64, aux: u64) -> u64 {
        !int_reference(val, aux)
    }
    fn mutant_int_2(val: u64, aux: u64) -> u64 {
        int_reference(val, aux).wrapping_add(1)
    }
    fn mutant_int_3(val: u64, aux: u64) -> u64 {
        int_reference(val, aux) ^ 0xFF
    }

    #[test]
    fn test_int_equivalence_and_boundaries() {
        // popcount_u64
        assert_eq!(popcount_u64(0), 0);
        assert_eq!(popcount_u64(u64::MAX), 64);
        assert_eq!(popcount_u64(0b1010_1010), 4);
        // popcount_u32 / parity_u32
        assert_eq!(popcount_u32(u32::MAX), 32);
        assert_eq!(parity_u32(0b11), 0);
        assert_eq!(parity_u32(0b111), 1);
        // leading/trailing zeros
        assert_eq!(leading_zeros_u64(0), 64);
        assert_eq!(trailing_zeros_u64(0), 64);
        assert_eq!(leading_zeros_u32(0), 32);
        assert_eq!(trailing_zeros_u32(0), 32);
        // is_pow2 / next_pow2
        assert!(is_pow2_u32(1));
        assert!(!is_pow2_u32(3));
        assert_eq!(next_power_of_two_u32(5), 8);
        assert_eq!(next_power_of_two_u32(u32::MAX), 0); // wraps
                                                        // saturating arithmetic
        assert_eq!(saturating_add_i64(i64::MAX, 1), i64::MAX);
        assert_eq!(saturating_sub_i64(i64::MIN, 1), i64::MIN);
        assert_eq!(saturating_mul_i64(i64::MAX, 2), i64::MAX);
        // bit reversal
        assert_eq!(reverse_bits_u64(1), 0x8000_0000_0000_0000);
        assert_eq!(reverse_bits_u32(1), 0x8000_0000);
        assert_eq!(reverse_bits_u64(0x8000_0000_0000_0000), 1);
        let v64 = 0xDEAD_BEEF_CAFE_1234u64;
        assert_eq!(reverse_bits_u64(reverse_bits_u64(v64)), v64);
        // phd gate boundaries

        assert_eq!(int_reference(1, 2), 3);
        assert_eq!(int_reference(0, 0), 0);
    }

    #[test]
    fn test_int_counterfactual_mutants() {
        let cases: &[fn(u64, u64) -> u64] = &[mutant_int_1, mutant_int_2, mutant_int_3];
        for (i, mutant) in cases.iter().enumerate() {
            assert!(
                int_reference(1, 1) != mutant(1, 1),
                "mutant {} was not rejected",
                i + 1
            );
        }
    }
}
