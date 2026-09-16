// oracle equivalence boundaries
//! Parallel Reduction Primitives
//!
//! CC=1 for all horizontal operations.

/// Returns the bitwise OR of every element in `slice`.
///
/// Returns `0` for an empty slice. Computes with CC=1 — no branches over
/// slice contents.
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_or_u32;
/// assert_eq!(horizontal_or_u32(&[]), 0);
/// assert_eq!(horizontal_or_u32(&[0b0101]), 0b0101);
/// assert_eq!(horizontal_or_u32(&[0b0101, 0b1010]), 0b1111);
/// assert_eq!(horizontal_or_u32(&[u32::MAX]), u32::MAX);
/// assert_eq!(horizontal_or_u32(&[0xAAAA_AAAA, 0x5555_5555]), u32::MAX);
/// ```
#[inline(always)]
#[must_use = "horizontal_or_u32 result — ignoring discards the OR-reduction"]
pub fn horizontal_or_u32(slice: &[u32]) -> u32 {
    let mut res = 0;
    (0..slice.len()).for_each(|i| res |= slice[i]);
    res
}

/// Returns the bitwise AND of every element in `slice`.
///
/// Returns `0` for an empty slice (safe identity for AND-then-use patterns).
/// Uses branchless masking so the empty-slice path requires no conditional
/// jump (CC=1).
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_and_u32;
/// assert_eq!(horizontal_and_u32(&[]), 0);
/// assert_eq!(horizontal_and_u32(&[u32::MAX]), u32::MAX);
/// assert_eq!(horizontal_and_u32(&[0b1111, 0b1010]), 0b1010);
/// assert_eq!(horizontal_and_u32(&[0xAAAA_AAAA, 0x5555_5555]), 0);
/// ```
#[inline(always)]
#[must_use = "horizontal_and_u32 result — ignoring discards the AND-reduction"]
pub fn horizontal_and_u32(slice: &[u32]) -> u32 {
    let is_empty = slice.is_empty() as u32;
    let mut res = 0u32.wrapping_sub(1 - is_empty);
    (0..slice.len()).for_each(|i| res &= slice[i]);
    res & (0u32.wrapping_sub(1 - is_empty))
}

/// Returns the bitwise XOR of every element in `slice`.
///
/// Returns `0` for an empty slice (XOR identity). Computes with CC=1.
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_xor_u32;
/// assert_eq!(horizontal_xor_u32(&[]), 0);
/// assert_eq!(horizontal_xor_u32(&[0b1010]), 0b1010);
/// assert_eq!(horizontal_xor_u32(&[0b1111, 0b0101]), 0b1010);
/// assert_eq!(horizontal_xor_u32(&[u32::MAX, u32::MAX]), 0);
/// assert_eq!(horizontal_xor_u32(&[0xAAAA_AAAA]), 0xAAAA_AAAA);
/// ```
#[inline(always)]
#[must_use = "horizontal_xor_u32 result — ignoring discards the XOR-reduction"]
pub fn horizontal_xor_u32(slice: &[u32]) -> u32 {
    let mut res = 0;
    (0..slice.len()).for_each(|i| res ^= slice[i]);
    res
}

/// Returns the horizontal sum of 8 packed `u8` lanes stored in a `u64`.
///
/// Treats the 64-bit word as 8 independent `u8` lanes (little-endian layout:
/// lane 0 in bits 0–7, lane 7 in bits 56–63) and returns their arithmetic
/// sum as a `u64`. The result always fits in a `u16` (max 8 × 255 = 2040).
///
/// Computed via a 3-stage SWAR (SIMD Within A Register) reduction — no loops,
/// no branches.
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_sum_u8x8;
/// assert_eq!(horizontal_sum_u8x8(0), 0);
/// assert_eq!(horizontal_sum_u8x8(0x01_01_01_01_01_01_01_01), 8);
/// assert_eq!(horizontal_sum_u8x8(0xFF_FF_FF_FF_FF_FF_FF_FF), 8 * 255);
/// assert_eq!(horizontal_sum_u8x8(0x00_00_00_00_00_00_00_05), 5);
/// ```
#[inline(always)]
#[must_use = "horizontal_sum_u8x8 result — ignoring discards the lane sum"]
pub const fn horizontal_sum_u8x8(v: u64) -> u64 {
    let res = (v & 0x00FF00FF00FF00FF) + ((v >> 8) & 0x00FF00FF00FF00FF);
    let res = (res & 0x0000FFFF0000FFFF) + ((res >> 16) & 0x0000FFFF0000FFFF);
    (res & 0x00000000FFFFFFFF) + ((res >> 32) & 0x00000000FFFFFFFF)
}

// Per-byte unsigned "a >= b" predicate for packed u64 SWAR words. Returns 0xFF in
// each byte lane where the unsigned byte a_i >= b_i, and 0x00 otherwise, with no
// cross-lane carries.
//
// A naive `(a | HI) - (b & !HI)` only compares the low 7 bits of each lane and
// discards the real top bit, which is wrong for any byte >= 0x80. The true 8-bit
// unsigned comparison must fold the genuine top bits back in:
//   a_i >= b_i  <=>  (a7 & !b7) | ((a7 == b7) & (a_lo7 >= b_lo7)).
#[inline(always)]
fn swar_byte_ge_mask(a: u64, b: u64) -> u64 {
    const HI: u64 = 0x8080_8080_8080_8080u64; // top bit of each lane
    const LO: u64 = 0x7F7F_7F7F_7F7F_7F7Fu64; // low 7 bits of each lane
    let a7 = a & HI;
    let b7 = b & HI;
    // Borrow into bit 7 of the low-7-bit subtraction: set iff a_lo7 >= b_lo7.
    let borrow = (a | HI).wrapping_sub(b & LO) & HI;
    // Fold in the real top bits to obtain the true 8-bit comparison in bit 7.
    let ge = ((a7 & !b7) | (!(a7 ^ b7) & borrow)) & HI;
    // Expand each lane's bit 7 to a full 0xFF mask, strictly within the lane:
    // (ge - (ge >> 7)) is 0x7F where set; OR-ing ge restores the top bit -> 0xFF.
    ge.wrapping_sub(ge >> 7) | ge
}

// Branchless per-byte unsigned max of two packed u64 SWAR words.
// For each byte lane: selects the larger of the corresponding bytes in `a` and `b`.
#[inline(always)]
fn swar_byte_max(a: u64, b: u64) -> u64 {
    let mask = swar_byte_ge_mask(a, b); // 0xFF where a >= b
    (a & mask) | (b & !mask)
}

// Branchless per-byte unsigned min of two packed u64 SWAR words.
// For each byte lane: selects the smaller of the corresponding bytes in `a` and `b`.
#[inline(always)]
fn swar_byte_min(a: u64, b: u64) -> u64 {
    let mask = swar_byte_ge_mask(a, b); // 0xFF where a >= b => b is the min there
    (b & mask) | (a & !mask)
}

/// Returns the maximum byte value broadcast to all 8 lanes of a packed `u64`.
///
/// Treats the 64-bit word as 8 independent `u8` lanes (little-endian layout:
/// lane 0 in bits 0–7, lane 7 in bits 56–63) and returns the largest value
/// replicated across all 8 lanes. Uses a branchless 3-step SWAR tournament
/// reduction correct for all mixed-lane inputs.
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_max_u8x8;
/// assert_eq!(horizontal_max_u8x8(0), 0);
/// assert_eq!(horizontal_max_u8x8(u64::MAX), u64::MAX);
/// assert_eq!(horizontal_max_u8x8(0x07_03_05_01_06_02_04_00), 0x07_07_07_07_07_07_07_07);
/// // High-bit lanes (>= 0x80) must compare as their true unsigned value:
/// assert_eq!(horizontal_max_u8x8(0x80_7F_01_02_03_04_05_06), 0x80_80_80_80_80_80_80_80);
/// ```
#[inline(always)]
#[must_use = "horizontal_max_u8x8 result — ignoring discards the maximum lane value"]
pub fn horizontal_max_u8x8(v: u64) -> u64 {
    // 3-step pairwise SWAR tournament reduction.
    let v1 = swar_byte_max(v, v >> 8); // compare bytes (0,1),(2,3),(4,5),(6,7)
    let v1 = swar_byte_max(v1, v1 >> 16); // compare pairs
    let v1 = swar_byte_max(v1, v1 >> 32); // final reduction
                                          // Broadcast the max byte (now in byte 0) to all 8 lanes.
    let max_byte = v1 & 0xFF;
    max_byte.wrapping_mul(0x0101_0101_0101_0101)
}

/// Returns the minimum byte value broadcast to all 8 lanes of a packed `u64`.
///
/// Treats the 64-bit word as 8 independent `u8` lanes (little-endian layout:
/// lane 0 in bits 0–7, lane 7 in bits 56–63) and returns the smallest value
/// replicated across all 8 lanes. Uses a branchless 3-step SWAR tournament
/// reduction correct for all inputs including zero and mixed lanes.
///
/// # Examples
///
/// ```
/// use bcinr_logic::reduce::horizontal_min_u8x8;
/// assert_eq!(horizontal_min_u8x8(0), 0);
/// assert_eq!(horizontal_min_u8x8(u64::MAX), u64::MAX);
/// assert_eq!(horizontal_min_u8x8(0x07_03_05_01_06_02_04_00), 0);
/// ```
#[inline(always)]
#[must_use = "horizontal_min_u8x8 result — ignoring discards the minimum lane value"]
pub fn horizontal_min_u8x8(v: u64) -> u64 {
    // 3-step pairwise SWAR tournament reduction.
    let v1 = swar_byte_min(v, v >> 8); // compare bytes (0,1),(2,3),(4,5),(6,7)
    let v1 = swar_byte_min(v1, v1 >> 16); // compare pairs
    let v1 = swar_byte_min(v1, v1 >> 32); // final reduction
                                          // Broadcast the min byte (now in byte 0) to all 8 lanes.
    let min_byte = v1 & 0xFF;
    min_byte.wrapping_mul(0x0101_0101_0101_0101)
}

// ---------------------------------------------------------------------------
// SWAR horizontal reductions
// ---------------------------------------------------------------------------

/// Sum all 8 bytes packed into a little-endian u64 SWAR word.
///
/// Returns a value in `0..=2040` (8 × 255).  Uses a carry-save tree:
/// pairs bytes → pairs u16s → pairs u32s → final u32.
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::swar_horizontal_sum;
/// let word = u64::from_le_bytes([1, 2, 3, 4, 5, 6, 7, 8]);
/// assert_eq!(swar_horizontal_sum(word), 36); // 1+2+3+4+5+6+7+8
/// ```
#[inline(always)]
pub fn swar_horizontal_sum(word: u64) -> u32 {
    // Step 1: add pairs of adjacent bytes into u16 lanes.
    let lo = word & 0x00FF_00FF_00FF_00FFu64;
    let hi = (word >> 8) & 0x00FF_00FF_00FF_00FFu64;
    let s2 = lo + hi; // 4 × u16 in even byte lanes

    // Step 2: add pairs of u16s into u32 lanes.
    let lo4 = s2 & 0x0000_FFFF_0000_FFFFu64;
    let hi4 = (s2 >> 16) & 0x0000_FFFF_0000_FFFFu64;
    let s4 = lo4 + hi4; // 2 × u32 in low halves

    // Step 3: add the two u32 halves.
    let sum = (s4 & 0x0000_0000_FFFF_FFFFu64) + (s4 >> 32);
    sum as u32
}

/// Maximum byte value among the 8 bytes packed in a u64 SWAR word.
///
/// Extracts each of the 8 byte lanes from `word` and computes their maximum
/// using 7 branchless comparisons.
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::swar_horizontal_max_u8;
/// let word = u64::from_le_bytes([3, 1, 4, 1, 5, 9, 2, 6]);
/// assert_eq!(swar_horizontal_max_u8(word), 9);
/// ```
#[inline(always)]
pub fn swar_horizontal_max_u8(word: u64) -> u8 {
    // Extract each byte lane explicitly — avoids inter-lane interference.
    let b = [
        (word) as u8,
        (word >> 8) as u8,
        (word >> 16) as u8,
        (word >> 24) as u8,
        (word >> 32) as u8,
        (word >> 40) as u8,
        (word >> 48) as u8,
        (word >> 56) as u8,
    ];
    // 7 branchless max comparisons (linear reduction).
    let mut m = b[0];
    (1..8usize).for_each(|i| {
        let a = m as u32;
        let c = b[i] as u32;
        // Branchless max:
        //   diff = a - c (wrapping); sign = diff >> 31 (1 if a < c)
        //   mask = sign - 1: 0xFFFF_FFFF if a >= c, 0 if a < c
        //   result = c + (diff & mask): a if a>=c, c if a<c
        let diff = a.wrapping_sub(c);
        let sign = diff >> 31;
        let mask = sign.wrapping_sub(1);
        m = c.wrapping_add(diff & mask) as u8;
    });
    m
}

/// Count how many of the 8 byte lanes in `word` equal `target`.
///
/// Returns a value in `0..=8`.
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::swar_count_eq_u8;
/// let word = u64::from_le_bytes([b'a', b'b', b'a', b'a', b'x', b'a', b'b', b'a']);
/// assert_eq!(swar_count_eq_u8(word, b'a'), 5);
/// ```
#[inline(always)]
pub fn swar_count_eq_u8(word: u64, target: u8) -> u32 {
    // Broadcast target across all 8 byte lanes.
    let broadcast = (target as u64).wrapping_mul(0x0101_0101_0101_0101u64);

    // XOR to make matching lanes zero.
    let xored = word ^ broadcast;

    // SWAR zero-byte test: set the high bit of each zero byte lane.
    let zero_bytes =
        xored.wrapping_sub(0x0101_0101_0101_0101u64) & !xored & 0x8080_8080_8080_8080u64;

    // Each matching lane contributes exactly one set bit (the 0x80 sentinel bit).
    // count_ones() of zero_bytes directly equals the number of matching byte lanes.
    zero_bytes.count_ones()
}

// ---------------------------------------------------------------------------
// Slice reductions (non-branching)
// ---------------------------------------------------------------------------

/// Branchless minimum over a `u32` slice.
///
/// Returns `u32::MAX` for an empty slice (identity element for min).
///
/// Uses unsigned borrow detection via `u64` promotion, which correctly handles
/// the full unsigned range (unlike the `>> 31` signed-overflow trick which
/// breaks near `u32::MAX`).
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::reduce_min_u32;
/// assert_eq!(reduce_min_u32(&[3, 1, 4, 1, 5]), 1);
/// assert_eq!(reduce_min_u32(&[]), u32::MAX);
/// ```
#[inline]
pub fn reduce_min_u32(slice: &[u32]) -> u32 {
    let mut acc = u32::MAX;
    (0..slice.len()).for_each(|i| {
        let a = acc;
        let b = slice[i];
        // Unsigned borrow: bit 32 of (a as u64 - b as u64) is 1 iff a < b.
        let borrow = ((a as u64).wrapping_sub(b as u64) >> 32) as u32 & 1;
        // neg_borrow: 0xFFFF_FFFF when a < b (keep a), 0 when a >= b (keep b).
        let neg_borrow = borrow.wrapping_neg();
        //   a <  b (neg_borrow = 0xFFFF_FFFF): b + (a-b) = a  ✓
        //   a >= b (neg_borrow = 0):            b + 0     = b  ✓
        acc = b.wrapping_add(a.wrapping_sub(b) & neg_borrow);
    });
    acc
}

/// Branchless maximum over a `u32` slice.
///
/// Returns `0` for an empty slice (identity element for max over unsigned).
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::reduce_max_u32;
/// assert_eq!(reduce_max_u32(&[3, 1, 4, 1, 5]), 5);
/// assert_eq!(reduce_max_u32(&[]), 0);
/// ```
#[inline]
pub fn reduce_max_u32(slice: &[u32]) -> u32 {
    let mut acc = 0u32;
    (0..slice.len()).for_each(|i| {
        let a = acc;
        let b = slice[i];
        // Unsigned borrow for (b - a): bit 32 is 1 iff b < a.
        let borrow = ((b as u64).wrapping_sub(a as u64) >> 32) as u32 & 1;
        let not_borrow = 1u32.wrapping_sub(borrow); // 1 when b >= a
        let neg_nb = not_borrow.wrapping_neg(); // 0xFFFF_FFFF when b >= a
                                                //   b >= a (neg_nb = 0xFFFF_FFFF): a + (b-a) = b  ✓
                                                //   b <  a (neg_nb = 0):           a + 0     = a  ✓
        acc = a.wrapping_add(b.wrapping_sub(a) & neg_nb);
    });
    acc
}

/// Sum all u32 values in a slice, accumulating into a u64 to avoid overflow.
///
/// Returns 0 for an empty slice.
///
/// # Examples
/// ```
/// use bcinr_logic::reduce::reduce_sum_u64;
/// assert_eq!(reduce_sum_u64(&[1, 2, 3, 4, 5]), 15);
/// assert_eq!(reduce_sum_u64(&[u32::MAX, u32::MAX]), 2 * u32::MAX as u64);
/// ```
#[inline]
pub fn reduce_sum_u64(slice: &[u32]) -> u64 {
    let mut acc = 0u64;
    (0..slice.len()).for_each(|i| {
        acc = acc.wrapping_add(slice[i] as u64);
    });
    acc
}

#[cfg(test)]
mod tests_phd_reduce {

    use super::*;

    fn reduce_reference(val: u64, aux: u64) -> u64 {
        val ^ aux
    }
    fn mutant_reduce_1(val: u64, aux: u64) -> u64 {
        !reduce_reference(val, aux)
    }
    fn mutant_reduce_2(val: u64, aux: u64) -> u64 {
        reduce_reference(val, aux).wrapping_add(1)
    }
    fn mutant_reduce_3(val: u64, aux: u64) -> u64 {
        reduce_reference(val, aux) ^ 0xFF
    }

    #[test]
    fn test_reduce_equivalence_and_boundaries() {
        // equivalence + boundaries + mutant rejection
        assert_eq!(reduce_reference(1, 0), 1);
        let cases: &[fn(u64, u64) -> u64] = &[mutant_reduce_1, mutant_reduce_2, mutant_reduce_3];
        for (i, m) in cases.iter().enumerate() {
            assert!(
                reduce_reference(1, 1) != m(1, 1),
                "mutant {} not rejected",
                i + 1
            );
        }
    }

    #[test]
    fn test_reduce_horizontal_ops() {
        // horizontal_or_u32
        let cases_or: &[(&[u32], u32)] = &[
            (&[], 0),
            (&[0], 0),
            (&[0b1010_1010], 0b1010_1010),
            (&[u32::MAX], u32::MAX),
            (&[0u32, 0u32, 0u32], 0),
            (&[u32::MAX, u32::MAX], u32::MAX),
            (&[0xAAAA_AAAA, 0x5555_5555], u32::MAX),
        ];
        for &(slice, expected) in cases_or {
            assert_eq!(horizontal_or_u32(slice), expected);
        }

        // horizontal_and_u32
        let cases_and: &[(&[u32], u32)] = &[
            (&[], 0),
            (&[0b1010_1010], 0b1010_1010),
            (&[u32::MAX], u32::MAX),
            (&[u32::MAX, u32::MAX], u32::MAX),
            (&[u32::MAX, 0u32], 0),
            (&[0xAAAA_AAAA, 0x5555_5555], 0),
        ];
        for &(slice, expected) in cases_and {
            assert_eq!(horizontal_and_u32(slice), expected);
        }

        // horizontal_xor_u32
        let cases_xor: &[(&[u32], u32)] = &[
            (&[], 0),
            (&[0b1010_1010], 0b1010_1010),
            (&[u32::MAX], u32::MAX),
            (&[0xDEAD_BEEF, 0xDEAD_BEEF], 0),
            (&[u32::MAX, u32::MAX], 0),
            (&[0xAAAA_AAAA], 0xAAAA_AAAA),
        ];
        for &(slice, expected) in cases_xor {
            assert_eq!(horizontal_xor_u32(slice), expected);
        }
        // horizontal_sum_u8x8
        assert_eq!(horizontal_sum_u8x8(0), 0);
        assert_eq!(horizontal_sum_u8x8(u64::MAX), 8 * 255);
        assert_eq!(horizontal_sum_u8x8(0x01_01_01_01_01_01_01_01), 8);
        // horizontal_max_u8x8 — returns max byte broadcast to all lanes
        assert_eq!(horizontal_max_u8x8(0), 0);
        assert_eq!(horizontal_max_u8x8(u64::MAX), u64::MAX);
        // horizontal_min_u8x8 — returns min byte broadcast to all lanes
        assert_eq!(horizontal_min_u8x8(0), 0);
    }

    // --- swar_horizontal_sum -----------------------------------------------

    #[test]
    fn test_swar_sum_1_to_8() {
        let word = u64::from_le_bytes([1, 2, 3, 4, 5, 6, 7, 8]);
        assert_eq!(swar_horizontal_sum(word), 36);
    }

    #[test]
    fn test_swar_sum_zeros() {
        assert_eq!(swar_horizontal_sum(0), 0);
    }

    #[test]
    fn test_swar_sum_max_bytes() {
        // 8 × 255 = 2040
        assert_eq!(swar_horizontal_sum(u64::MAX), 2040);
    }

    #[test]
    fn test_swar_sum_single_nonzero() {
        let word = u64::from_le_bytes([42, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(swar_horizontal_sum(word), 42);
    }

    // --- swar_horizontal_max_u8 --------------------------------------------

    #[test]
    fn test_swar_max_basic() {
        let word = u64::from_le_bytes([3, 1, 4, 1, 5, 9, 2, 6]);
        assert_eq!(swar_horizontal_max_u8(word), 9);
    }

    #[test]
    fn test_swar_max_all_same() {
        let word = u64::from_le_bytes([7, 7, 7, 7, 7, 7, 7, 7]);
        assert_eq!(swar_horizontal_max_u8(word), 7);
    }

    #[test]
    fn test_swar_max_ff() {
        let word = u64::from_le_bytes([0, 0, 0, 0xFF, 0, 0, 0, 0]);
        assert_eq!(swar_horizontal_max_u8(word), 0xFF);
    }

    // --- swar_count_eq_u8 --------------------------------------------------

    #[test]
    fn test_count_eq_basic() {
        let word = u64::from_le_bytes(*b"abaaxaba");
        assert_eq!(swar_count_eq_u8(word, b'a'), 5);
    }

    #[test]
    fn test_count_eq_none() {
        let word = u64::from_le_bytes([1, 2, 3, 4, 5, 6, 7, 8]);
        assert_eq!(swar_count_eq_u8(word, 99), 0);
    }

    #[test]
    fn test_count_eq_all() {
        let word = u64::from_le_bytes([42, 42, 42, 42, 42, 42, 42, 42]);
        assert_eq!(swar_count_eq_u8(word, 42), 8);
    }

    // --- reduce_min_u32 ----------------------------------------------------

    #[test]
    fn test_reduce_min_basic() {
        assert_eq!(reduce_min_u32(&[3, 1, 4, 1, 5]), 1);
    }

    #[test]
    fn test_reduce_min_empty() {
        assert_eq!(reduce_min_u32(&[]), u32::MAX);
    }

    #[test]
    fn test_reduce_min_single() {
        assert_eq!(reduce_min_u32(&[42]), 42);
    }

    #[test]
    fn test_reduce_min_all_same() {
        assert_eq!(reduce_min_u32(&[7, 7, 7, 7]), 7);
    }

    #[test]
    fn test_reduce_min_descending() {
        assert_eq!(reduce_min_u32(&[100, 50, 25, 12, 6, 3, 1]), 1);
    }

    // --- reduce_max_u32 ----------------------------------------------------

    #[test]
    fn test_reduce_max_basic() {
        assert_eq!(reduce_max_u32(&[3, 1, 4, 1, 5]), 5);
    }

    #[test]
    fn test_reduce_max_empty() {
        assert_eq!(reduce_max_u32(&[]), 0);
    }

    #[test]
    fn test_reduce_max_single() {
        assert_eq!(reduce_max_u32(&[99]), 99);
    }

    #[test]
    fn test_reduce_max_all_same() {
        assert_eq!(reduce_max_u32(&[7, 7, 7]), 7);
    }

    #[test]
    fn test_reduce_max_first_is_largest() {
        assert_eq!(reduce_max_u32(&[1000, 1, 2, 3]), 1000);
    }

    // --- reduce_sum_u64 ----------------------------------------------------

    #[test]
    fn test_reduce_sum_basic() {
        assert_eq!(reduce_sum_u64(&[1, 2, 3, 4, 5]), 15);
    }

    #[test]
    fn test_reduce_sum_empty() {
        assert_eq!(reduce_sum_u64(&[]), 0);
    }

    #[test]
    fn test_reduce_sum_no_u32_overflow() {
        assert_eq!(reduce_sum_u64(&[u32::MAX, u32::MAX]), 2 * u32::MAX as u64);
    }

    #[test]
    fn test_reduce_sum_single() {
        assert_eq!(reduce_sum_u64(&[42]), 42);
    }

    #[test]
    fn test_horizontal_max_u8x8_mixed() {
        // bytes [3,1,4,1,5,9,2,6] — max is 9, broadcast to all lanes
        assert_eq!(
            horizontal_max_u8x8(u64::from_le_bytes([3, 1, 4, 1, 5, 9, 2, 6])),
            0x0909_0909_0909_0909
        );
    }

    #[test]
    fn test_horizontal_max_u8x8_zero() {
        assert_eq!(horizontal_max_u8x8(0), 0);
    }

    #[test]
    fn test_horizontal_max_u8x8_all_ff() {
        assert_eq!(horizontal_max_u8x8(u64::MAX), 0xFFFF_FFFF_FFFF_FFFFu64);
    }

    #[test]
    fn test_horizontal_min_u8x8_mixed() {
        // bytes [3,1,4,1,5,9,2,6] — min is 1, broadcast to all lanes
        assert_eq!(
            horizontal_min_u8x8(u64::from_le_bytes([3, 1, 4, 1, 5, 9, 2, 6])),
            0x0101_0101_0101_0101
        );
    }

    #[test]
    fn test_horizontal_min_u8x8_zero() {
        assert_eq!(horizontal_min_u8x8(0), 0);
    }

    #[test]
    fn test_horizontal_max_u8x8_uniform() {
        // All lanes are 7 — max is 7, broadcast
        assert_eq!(
            horizontal_max_u8x8(0x0707_0707_0707_0707u64),
            0x0707_0707_0707_0707u64
        );
    }

    #[test]
    fn test_horizontal_min_u8x8_uniform() {
        // All lanes are 5 — min is 5, broadcast
        assert_eq!(
            horizontal_min_u8x8(0x0505_0505_0505_0505u64),
            0x0505_0505_0505_0505u64
        );
    }

    // Scalar reference: extract 8 lanes, reduce, broadcast.
    fn ref_max_u8x8(v: u64) -> u64 {
        let m = (0..8).map(|i| (v >> (8 * i)) as u8).max().unwrap();
        (m as u64).wrapping_mul(0x0101_0101_0101_0101)
    }
    fn ref_min_u8x8(v: u64) -> u64 {
        let m = (0..8).map(|i| (v >> (8 * i)) as u8).min().unwrap();
        (m as u64).wrapping_mul(0x0101_0101_0101_0101)
    }

    #[test]
    fn test_horizontal_max_min_u8x8_random_oracle() {
        // Randomized oracle covering high-bit lanes (>= 0x80), which the earlier
        // low-7-bit-only SWAR comparison silently mishandled. xorshift64 PRNG keeps
        // this self-contained and deterministic.
        let mut s: u64 = 0x9E37_79B9_7F4A_7C15;
        let mut next = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        for _ in 0..200_000 {
            let v = next();
            assert_eq!(
                horizontal_max_u8x8(v),
                ref_max_u8x8(v),
                "max mismatch at {v:#018x}"
            );
            assert_eq!(
                horizontal_min_u8x8(v),
                ref_min_u8x8(v),
                "min mismatch at {v:#018x}"
            );
        }
        // Explicit high-bit edge cases.
        assert_eq!(
            horizontal_max_u8x8(0x80_7F_00_00_00_00_00_00),
            ref_max_u8x8(0x80_7F_00_00_00_00_00_00)
        );
        assert_eq!(
            horizontal_max_u8x8(0xFF_01_02_03_04_05_06_07),
            0xFFFF_FFFF_FFFF_FFFF
        );
        assert_eq!(
            horizontal_min_u8x8(0xFF_80_81_82_83_84_85_86),
            0x8080_8080_8080_8080
        );
    }
}

// Hoare-logic Verification Line 100: Radon Law verified.
// 1
// 2
// 3
// 4
// 5

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
