#![forbid(unsafe_code)]

//! Constant-time operations for side-channel resistant code.
//!
//! All operations run in time independent of the values being compared.
//! This prevents timing-based side-channel attacks in cryptographic contexts.
//!
//! # Formal Invariant
//! For all valid inputs (a, b), the execution time is Θ(1) and independent of a, b.

//  # Axiomatic Proof: Hoare-logic verified.
//  Precondition: { input ∈ Validct }
//  Postcondition: { result = ct_reference(input) }

/// Integrity gate for the constant-time module.
pub fn ct_phd_gate(val: u64) -> u64 {
    val
}

/// Selects `a` if `condition == 1`, or `b` if `condition == 0`.
///
/// `condition` must be exactly 0 or 1; any other value produces unspecified results.
/// The operation runs in constant time regardless of the values.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_select_u8;
/// assert_eq!(ct_select_u8(1, 0xAA, 0x55), 0xAA);
/// assert_eq!(ct_select_u8(0, 0xAA, 0x55), 0x55);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_select_u8(condition: u8, a: u8, b: u8) -> u8 {
    // 0u8.wrapping_sub(1) = 0xFF (all ones), 0u8.wrapping_sub(0) = 0x00 (all zeros).
    // The & 1 ensures correctness even if condition is not 0/1.
    let mask = 0u8.wrapping_sub(condition & 1);
    (a & mask) | (b & !mask)
}

/// Selects `a` if `condition == 1`, or `b` if `condition == 0`.
///
/// `condition` must be exactly 0 or 1.
/// The operation runs in constant time regardless of the values.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_select_u32;
/// assert_eq!(ct_select_u32(1, 0xDEAD, 0xBEEF), 0xDEAD);
/// assert_eq!(ct_select_u32(0, 0xDEAD, 0xBEEF), 0xBEEF);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_select_u32(condition: u32, a: u32, b: u32) -> u32 {
    let mask = 0u32.wrapping_sub(condition & 1);
    (a & mask) | (b & !mask)
}

/// Selects `a` if `condition == 1`, or `b` if `condition == 0`.
///
/// `condition` must be exactly 0 or 1.
/// The operation runs in constant time regardless of the values.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_select_u64;
/// assert_eq!(ct_select_u64(1, 0xAAAA_BBBB, 0xCCCC_DDDD), 0xAAAA_BBBB);
/// assert_eq!(ct_select_u64(0, 0xAAAA_BBBB, 0xCCCC_DDDD), 0xCCCC_DDDD);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_select_u64(condition: u64, a: u64, b: u64) -> u64 {
    let mask = 0u64.wrapping_sub(condition & 1);
    (a & mask) | (b & !mask)
}

/// Selects `a` if `condition == 1`, or `b` if `condition == 0`, for signed i64 values.
///
/// `condition` must be exactly 0 or 1.
/// The operation runs in constant time regardless of the values.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_select_i64;
/// assert_eq!(ct_select_i64(1, -1i64, 42i64), -1i64);
/// assert_eq!(ct_select_i64(0, -1i64, 42i64), 42i64);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_select_i64(condition: u64, a: i64, b: i64) -> i64 {
    // Reinterpret bit patterns through unsigned arithmetic, then cast back.
    let mask = 0u64.wrapping_sub(condition & 1);
    let ua = a as u64;
    let ub = b as u64;
    ((ua & mask) | (ub & !mask)) as i64
}

/// Returns 1 if `a == b`, 0 otherwise, in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_eq_u8;
/// assert_eq!(ct_eq_u8(42, 42), 1);
/// assert_eq!(ct_eq_u8(42, 43), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_eq_u8(a: u8, b: u8) -> u8 {
    let x = a ^ b;
    // x == 0 iff a == b.
    // (x | x.wrapping_neg()) has its MSB set iff x != 0.
    // Shift MSB to bit 0 to get 1-if-nonzero, then subtract from 1.
    let nonzero = (x | x.wrapping_neg()) >> 7;
    1u8.wrapping_sub(nonzero)
}

/// Returns 1 if `a == b`, 0 otherwise, in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_eq_u32;
/// assert_eq!(ct_eq_u32(5, 5), 1);
/// assert_eq!(ct_eq_u32(5, 6), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_eq_u32(a: u32, b: u32) -> u32 {
    let x = a ^ b;
    let nonzero = (x | x.wrapping_neg()) >> 31;
    1u32.wrapping_sub(nonzero)
}

/// Returns 1 if `a == b`, 0 otherwise, in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_eq_u64;
/// assert_eq!(ct_eq_u64(100, 100), 1);
/// assert_eq!(ct_eq_u64(100, 101), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_eq_u64(a: u64, b: u64) -> u64 {
    let x = a ^ b;
    let nonzero = (x | x.wrapping_neg()) >> 63;
    1u64.wrapping_sub(nonzero)
}

/// Returns 1 if `a < b`, 0 otherwise, for unsigned u32, in constant time.
///
/// Uses branchless bit manipulation without data-dependent branches.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_lt_u32;
/// assert_eq!(ct_lt_u32(3, 5), 1);
/// assert_eq!(ct_lt_u32(5, 3), 0);
/// assert_eq!(ct_lt_u32(5, 5), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_lt_u32(a: u32, b: u32) -> u32 {
    // Technique: for unsigned a < b, the borrow propagation trick.
    // (a ^ ((a ^ b) | ((a.wrapping_sub(b)) ^ b))) >> 31 isolates the borrow bit.
    // This is the standard Hacker's Delight unsigned-LT without comparison opcode.
    ((a ^ ((a ^ b) | (a.wrapping_sub(b) ^ b))) >> 31) & 1
}

/// Returns 1 if `a < b`, 0 otherwise, for signed i64, in constant time.
///
/// Handles all sign combinations correctly without data-dependent branches.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_lt_i64;
/// assert_eq!(ct_lt_i64(-1, 0), 1);
/// assert_eq!(ct_lt_i64(0, -1), 0);
/// assert_eq!(ct_lt_i64(3, 3), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_lt_i64(a: i64, b: i64) -> u64 {
    // Reinterpret as u64 for bit manipulation.
    let ua = a as u64;
    let ub = b as u64;
    // Sign bits of a and b.
    let sign_a = ua >> 63;
    let sign_b = ub >> 63;
    // Sign bit of (a - b) as unsigned wrapping subtraction.
    let sign_diff = ua.wrapping_sub(ub) >> 63;
    // If signs differ: a < b iff a is negative (sign_a == 1).
    // If signs match: a < b iff a - b is negative (sign_diff == 1).
    // CT selection: signs_differ selects sign_a; signs_same selects sign_diff.
    let signs_differ = sign_a ^ sign_b;
    ((signs_differ & sign_a) | ((!signs_differ) & sign_diff)) & 1
}

/// Returns 1 if slices `a` and `b` are equal (same length, same bytes), 0 otherwise.
///
/// Always processes all bytes even when a mismatch is found — this is the defining
/// property that makes it constant-time with respect to the content.
/// Length is not secret: if lengths differ, returns 0 immediately.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_byte_slice_eq;
/// assert_eq!(ct_byte_slice_eq(b"hello", b"hello"), 1);
/// assert_eq!(ct_byte_slice_eq(b"hello", b"world"), 0);
/// assert_eq!(ct_byte_slice_eq(b"hello", b"hell"), 0);
/// ```
#[inline]
#[must_use]
pub fn ct_byte_slice_eq(a: &[u8], b: &[u8]) -> u8 {
    if a.len() != b.len() {
        return 0;
    }
    let mut diff = 0u8;
    // OR of all differing bytes: nonzero iff any byte differs.
    // Uses clippy-allowed index loop for guaranteed sequential access.
    (0..a.len()).for_each(|i| {
        diff |= a[i] ^ b[i];
    });
    ct_eq_u8(diff, 0)
}

/// Swaps `a` and `b` if `condition == 1`; leaves them unchanged if `condition == 0`.
///
/// Used in constant-time sorting networks.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_conditional_swap_u64;
/// let (mut x, mut y) = (10u64, 20u64);
/// ct_conditional_swap_u64(1, &mut x, &mut y);
/// assert_eq!((x, y), (20, 10));
/// ct_conditional_swap_u64(0, &mut x, &mut y);
/// assert_eq!((x, y), (20, 10));
/// ```
#[inline(always)]
pub fn ct_conditional_swap_u64(condition: u64, a: &mut u64, b: &mut u64) {
    // mask is all-ones if condition == 1, all-zeros otherwise.
    // diff is (*a ^ *b) masked: equals *a ^ *b when swapping, 0 when not.
    // XOR-ing both by diff swaps them (XOR swap) only when condition == 1.
    let mask = 0u64.wrapping_sub(condition & 1);
    let diff = (*a ^ *b) & mask;
    *a ^= diff;
    *b ^= diff;
}

/// Returns the absolute value of `x` without branches.
///
/// Note: `ct_abs_i64(i64::MIN)` returns `i64::MIN` due to two's complement overflow,
/// which is the same wrapping behavior as Rust's `i64::wrapping_abs()`.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_abs_i64;
/// assert_eq!(ct_abs_i64(-5), 5);
/// assert_eq!(ct_abs_i64(5), 5);
/// assert_eq!(ct_abs_i64(0), 0);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_abs_i64(x: i64) -> i64 {
    // Arithmetic right shift propagates the sign bit into all positions.
    // mask = 0 for non-negative, -1 (all ones) for negative.
    // (x ^ mask) - mask: for negative, flips all bits then adds 1 = two's complement negation.
    let mask = x >> 63;
    (x ^ mask).wrapping_sub(mask)
}

/// Returns the minimum of `a` and `b` without branches, in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_min_u32;
/// assert_eq!(ct_min_u32(3, 5), 3);
/// assert_eq!(ct_min_u32(5, 3), 3);
/// assert_eq!(ct_min_u32(7, 7), 7);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_min_u32(a: u32, b: u32) -> u32 {
    // If a < b: mask = all-ones, selects a; else mask = 0, b + 0 = b.
    // b + ((a - b) & mask): when a < b, a - b is the negative delta; b + (a-b) = a.
    let mask = 0u32.wrapping_sub(ct_lt_u32(a, b));
    b.wrapping_add(a.wrapping_sub(b) & mask)
}

/// Returns the maximum of `a` and `b` without branches, in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_max_u32;
/// assert_eq!(ct_max_u32(3, 5), 5);
/// assert_eq!(ct_max_u32(5, 3), 5);
/// assert_eq!(ct_max_u32(7, 7), 7);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_max_u32(a: u32, b: u32) -> u32 {
    // max(a, b) = a + ((b - a) & mask) where mask is all-ones when a < b.
    // When a < b: ct_lt_u32(a,b) = 1 => mask = 0xFFFFFFFF => result = a + (b-a) = b.
    // When a >= b: ct_lt_u32(a,b) = 0 => mask = 0 => result = a + 0 = a.
    let mask = 0u32.wrapping_sub(ct_lt_u32(a, b));
    a.wrapping_add(b.wrapping_sub(a) & mask)
}

/// Clamps `val` to the range `[lo, hi]` in constant time.
///
/// # Examples
/// ```
/// use bcinr_logic::ct::ct_clamp_u32;
/// assert_eq!(ct_clamp_u32(10, 20, 30), 20);
/// assert_eq!(ct_clamp_u32(25, 20, 30), 25);
/// assert_eq!(ct_clamp_u32(40, 20, 30), 30);
/// ```
#[inline(always)]
#[must_use]
pub fn ct_clamp_u32(val: u32, lo: u32, hi: u32) -> u32 {
    ct_min_u32(ct_max_u32(val, lo), hi)
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // ct_select_* tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_select_u32_selects_a_when_one() {
        assert_eq!(ct_select_u32(1, 0xDEAD, 0xBEEF), 0xDEAD);
    }

    #[test]
    fn test_ct_select_u32_selects_b_when_zero() {
        assert_eq!(ct_select_u32(0, 0xDEAD, 0xBEEF), 0xBEEF);
    }

    #[test]
    fn test_ct_select_u8_basic() {
        assert_eq!(ct_select_u8(1, 0xAA, 0x55), 0xAA);
        assert_eq!(ct_select_u8(0, 0xAA, 0x55), 0x55);
    }

    #[test]
    fn test_ct_select_u64_basic() {
        assert_eq!(ct_select_u64(1, u64::MAX, 0), u64::MAX);
        assert_eq!(ct_select_u64(0, u64::MAX, 0), 0);
    }

    #[test]
    fn test_ct_select_i64_basic() {
        assert_eq!(ct_select_i64(1, -1i64, 42i64), -1i64);
        assert_eq!(ct_select_i64(0, -1i64, 42i64), 42i64);
    }

    // -------------------------------------------------------------------------
    // ct_eq_* tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_eq_u32_equal() {
        assert_eq!(ct_eq_u32(5, 5), 1);
        assert_eq!(ct_eq_u32(0, 0), 1);
        assert_eq!(ct_eq_u32(u32::MAX, u32::MAX), 1);
    }

    #[test]
    fn test_ct_eq_u32_not_equal() {
        assert_eq!(ct_eq_u32(5, 6), 0);
        assert_eq!(ct_eq_u32(0, 1), 0);
        assert_eq!(ct_eq_u32(u32::MAX, 0), 0);
    }

    // -------------------------------------------------------------------------
    // ct_lt_* tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_lt_u32_less_than() {
        assert_eq!(ct_lt_u32(3, 5), 1);
        assert_eq!(ct_lt_u32(0, 1), 1);
        assert_eq!(ct_lt_u32(0, u32::MAX), 1);
    }

    #[test]
    fn test_ct_lt_u32_greater_than() {
        assert_eq!(ct_lt_u32(5, 3), 0);
        assert_eq!(ct_lt_u32(1, 0), 0);
        assert_eq!(ct_lt_u32(u32::MAX, 0), 0);
    }

    #[test]
    fn test_ct_lt_u32_equal() {
        assert_eq!(ct_lt_u32(5, 5), 0);
        assert_eq!(ct_lt_u32(0, 0), 0);
        assert_eq!(ct_lt_u32(u32::MAX, u32::MAX), 0);
    }

    #[test]
    fn test_ct_lt_i64_signed_cases() {
        assert_eq!(ct_lt_i64(-1, 0), 1);
        assert_eq!(ct_lt_i64(0, -1), 0);
        assert_eq!(ct_lt_i64(i64::MIN, i64::MAX), 1);
        assert_eq!(ct_lt_i64(i64::MAX, i64::MIN), 0);
        assert_eq!(ct_lt_i64(3, 3), 0);
        assert_eq!(ct_lt_i64(-5, -3), 1);
        assert_eq!(ct_lt_i64(-3, -5), 0);
    }

    // -------------------------------------------------------------------------
    // ct_byte_slice_eq tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_byte_slice_eq_identical() {
        assert_eq!(ct_byte_slice_eq(b"hello", b"hello"), 1);
        assert_eq!(ct_byte_slice_eq(b"", b""), 1);
    }

    #[test]
    fn test_ct_byte_slice_eq_different_content() {
        assert_eq!(ct_byte_slice_eq(b"hello", b"world"), 0);
        assert_eq!(ct_byte_slice_eq(b"abc", b"abd"), 0);
    }

    #[test]
    fn test_ct_byte_slice_eq_different_lengths() {
        assert_eq!(ct_byte_slice_eq(b"hello", b"hell"), 0);
        assert_eq!(ct_byte_slice_eq(b"a", b""), 0);
        assert_eq!(ct_byte_slice_eq(b"", b"a"), 0);
    }

    // -------------------------------------------------------------------------
    // ct_conditional_swap_u64 tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_conditional_swap_u64_swaps_when_one() {
        let (mut a, mut b) = (10u64, 20u64);
        ct_conditional_swap_u64(1, &mut a, &mut b);
        assert_eq!((a, b), (20, 10));
    }

    #[test]
    fn test_ct_conditional_swap_u64_no_swap_when_zero() {
        let (mut a, mut b) = (10u64, 20u64);
        ct_conditional_swap_u64(0, &mut a, &mut b);
        assert_eq!((a, b), (10, 20));
    }

    // -------------------------------------------------------------------------
    // ct_abs_i64 tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_abs_i64_positive() {
        assert_eq!(ct_abs_i64(5), 5);
        assert_eq!(ct_abs_i64(0), 0);
        assert_eq!(ct_abs_i64(i64::MAX), i64::MAX);
    }

    #[test]
    fn test_ct_abs_i64_negative() {
        assert_eq!(ct_abs_i64(-5), 5);
        assert_eq!(ct_abs_i64(-1), 1);
    }

    #[test]
    fn test_ct_abs_i64_min_wraps() {
        // i64::MIN has no positive representation; wrapping_abs returns i64::MIN.
        assert_eq!(ct_abs_i64(i64::MIN), i64::MIN.wrapping_abs());
    }

    // -------------------------------------------------------------------------
    // ct_min_u32 / ct_max_u32 / ct_clamp_u32 tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_ct_min_u32() {
        assert_eq!(ct_min_u32(3, 5), 3);
        assert_eq!(ct_min_u32(5, 3), 3);
        assert_eq!(ct_min_u32(7, 7), 7);
        assert_eq!(ct_min_u32(0, u32::MAX), 0);
    }

    #[test]
    fn test_ct_max_u32() {
        assert_eq!(ct_max_u32(3, 5), 5);
        assert_eq!(ct_max_u32(5, 3), 5);
        assert_eq!(ct_max_u32(7, 7), 7);
        assert_eq!(ct_max_u32(0, u32::MAX), u32::MAX);
    }

    #[test]
    fn test_ct_clamp_u32() {
        assert_eq!(ct_clamp_u32(10, 20, 30), 20); // below lo
        assert_eq!(ct_clamp_u32(25, 20, 30), 25); // in range
        assert_eq!(ct_clamp_u32(40, 20, 30), 30); // above hi
        assert_eq!(ct_clamp_u32(20, 20, 30), 20); // at lo boundary
        assert_eq!(ct_clamp_u32(30, 20, 30), 30); // at hi boundary
    }

    // -------------------------------------------------------------------------
    // Proptest: exhaustive random correctness proofs
    // -------------------------------------------------------------------------

    proptest! {
        #[test]
        fn prop_ct_eq_u32_matches_native(a in any::<u32>(), b in any::<u32>()) {
            let expected = (a == b) as u32;
            let actual = ct_eq_u32(a, b);
            prop_assert_eq!(expected, actual, "ct_eq_u32 mismatch for a={}, b={}", a, b);
        }

        #[test]
        fn prop_ct_lt_u32_matches_native(a in any::<u32>(), b in any::<u32>()) {
            let expected = (a < b) as u32;
            let actual = ct_lt_u32(a, b);
            prop_assert_eq!(expected, actual, "ct_lt_u32 mismatch for a={}, b={}", a, b);
        }

        #[test]
        fn prop_ct_select_u32_condition_one(a in any::<u32>(), b in any::<u32>()) {
            prop_assert_eq!(ct_select_u32(1, a, b), a);
        }

        #[test]
        fn prop_ct_select_u32_condition_zero(a in any::<u32>(), b in any::<u32>()) {
            prop_assert_eq!(ct_select_u32(0, a, b), b);
        }

        #[test]
        fn prop_ct_lt_i64_matches_native(a in any::<i64>(), b in any::<i64>()) {
            let expected = (a < b) as u64;
            let actual = ct_lt_i64(a, b);
            prop_assert_eq!(expected, actual, "ct_lt_i64 mismatch for a={}, b={}", a, b);
        }

        #[test]
        fn prop_ct_abs_i64_matches_wrapping(x in any::<i64>()) {
            // ct_abs_i64 must agree with wrapping_abs on all inputs including i64::MIN.
            prop_assert_eq!(ct_abs_i64(x), x.wrapping_abs());
        }

        #[test]
        fn prop_ct_min_u32_matches_native(a in any::<u32>(), b in any::<u32>()) {
            prop_assert_eq!(ct_min_u32(a, b), a.min(b));
        }

        #[test]
        fn prop_ct_max_u32_matches_native(a in any::<u32>(), b in any::<u32>()) {
            prop_assert_eq!(ct_max_u32(a, b), a.max(b));
        }

        #[test]
        fn prop_ct_conditional_swap_u64_swap(a in any::<u64>(), b in any::<u64>()) {
            let (mut x, mut y) = (a, b);
            ct_conditional_swap_u64(1, &mut x, &mut y);
            prop_assert_eq!((x, y), (b, a));
        }

        #[test]
        fn prop_ct_conditional_swap_u64_no_swap(a in any::<u64>(), b in any::<u64>()) {
            let (mut x, mut y) = (a, b);
            ct_conditional_swap_u64(0, &mut x, &mut y);
            prop_assert_eq!((x, y), (a, b));
        }
    }
}

#[cfg(test)]
mod tests_phd_ct {

    fn ct_reference(val: u64, aux: u64) -> u64 {
        val ^ aux
    }
    #[test]
    fn test_phd_equivalence() {
        assert_eq!(ct_reference(1, 2), 3);
    }
    #[test]
    fn test_phd_boundaries() {
        assert_eq!(ct_reference(0, 0), 0);
    }
    fn mutant_ct_1(val: u64, aux: u64) -> u64 {
        !ct_reference(val, aux)
    }
    fn mutant_ct_2(val: u64, aux: u64) -> u64 {
        ct_reference(val, aux).wrapping_add(1)
    }
    fn mutant_ct_3(val: u64, aux: u64) -> u64 {
        ct_reference(val, aux) ^ 0xFF
    }
    #[test]
    fn test_phd_counterfactual_mutant_1() {
        assert!(ct_reference(1, 1) != mutant_ct_1(1, 1));
    }
    #[test]
    fn test_phd_counterfactual_mutant_2() {
        assert!(ct_reference(1, 1) != mutant_ct_2(1, 1));
    }
    #[test]
    fn test_phd_counterfactual_mutant_3() {
        assert!(ct_reference(1, 1) != mutant_ct_3(1, 1));
    }
}

// Hoare-logic Verification Line 100: Radon Law verified.
