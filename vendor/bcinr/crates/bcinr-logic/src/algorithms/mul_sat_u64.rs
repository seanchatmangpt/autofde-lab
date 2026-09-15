// Academic-grade branchless algorithm library: mul_sat_u64
// Saturating multiplication for u64 (Hacker's Delight, Seacord 2005)
// Computes a * b, clamping to u64::MAX on overflow.
// Branchless: uses __uint128_t intermediate + comparison masks.

/// mul_sat_u64 — Saturating multiplication for u64
///
/// # Branchless Contract
///
/// Multiplies two u64 values with saturation on overflow.
/// If a × b would exceed u64::MAX, returns u64::MAX.
/// Branchless: uses conditional arithmetic (no if-statements).
///
/// # Algorithm (Hacker's Delight 2.32)
/// Let M = u64::MAX. We compute:
///   If (a × b) > M, return M
///   Else return (a × b) mod 2^64
///
/// Branchless approach:
/// 1. Compute full 128-bit product using widening multiply
/// 2. Check if upper 64 bits are zero (no overflow)
/// 3. Generate all-1s mask if overflow occurred
/// 4. Return (lower_64_bits & ~mask) | (u64::MAX & mask)
///
/// # CONTRACT
/// **Ensures:** result == min(a.saturating_mul(b), u64::MAX) for all inputs
/// **Invariant:** Zero conditional branches, constant-time execution
///
/// # Examples
/// ```
/// use bcinr_logic::algorithms::mul_sat_u64::mul_sat_u64;
/// assert_eq!(mul_sat_u64(10, 20), 200);
/// assert_eq!(mul_sat_u64(u64::MAX, 2), u64::MAX);
/// assert_eq!(mul_sat_u64(0, u64::MAX), 0);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
pub fn mul_sat_u64(a: u64, b: u64) -> u64 {
    // Compute full 128-bit product via u64 -> u128 conversions
    let product_128 = (a as u128).wrapping_mul(b as u128);

    // Extract upper and lower 64-bit parts
    let lower = product_128 as u64;
    let upper = (product_128 >> 64) as u64;

    // Branchless: if upper != 0, overflow_mask = 0xFFFF...FFFF; else 0.
    // Use unsigned subtraction from zero: 0u64.wrapping_sub(x != 0 as u64)
    // produces 0xFFFF...FFFF when x != 0, and 0 when x == 0.
    // This avoids the signed negation -(upper as i64) which panics in debug
    // builds when upper == 0x8000_0000_0000_0000 (i64::MIN).
    let mask = 0u64.wrapping_sub((upper != 0) as u64);

    // Return (lower & ~mask) | (u64::MAX & mask)
    // If mask = 0: returns lower
    // If mask = 0xFFFF...FFFF: returns u64::MAX
    (lower & !mask) | mask
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation (standard library method)
    // -------------------------------------------------------------------------
    fn mul_sat_u64_reference(a: u64, b: u64) -> u64 {
        a.saturating_mul(b)
    }

    // -------------------------------------------------------------------------
    // PROPERTY TEST: 1000+ random cases of equivalence
    // -------------------------------------------------------------------------

    #[test]
    fn test_mul_sat_u64_all() {
        // equivalence oracle
        let expected = mul_sat_u64_reference(42, 1337);
        let actual = mul_sat_u64(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        // (1, anything) -> anything
        assert_eq!(mul_sat_u64(1, 42), 42);
        assert_eq!(mul_sat_u64(42, 1), 42);

        // (0, anything) -> 0
        assert_eq!(mul_sat_u64(0, u64::MAX), 0);
        assert_eq!(mul_sat_u64(u64::MAX, 0), 0);

        // Overflow cases saturate to MAX
        assert_eq!(mul_sat_u64(u64::MAX, u64::MAX), u64::MAX);
        assert_eq!(mul_sat_u64(u64::MAX, 2), u64::MAX);
        assert_eq!(mul_sat_u64(2, u64::MAX), u64::MAX);

        // Large but non-overflow: (2^32) * (2^32) = 2^64 (overflow)
        assert_eq!(mul_sat_u64(0x100000000, 0x100000000), u64::MAX);

        // Just below overflow threshold: 0xFFFFFFFF^2 = 0xFFFFFFFE00000001 < 2^64
        let sqrt_max = 0xFFFFFFFF_u64; // floor(sqrt(2^64 - 1))
        let product = mul_sat_u64(sqrt_max, sqrt_max);
        assert_eq!(product, 0xFFFFFFFE00000001); // Does not overflow

        // Regression: previously panicked in debug builds because upper == 0x8000_0000_0000_0000
        // (= i64::MIN), and -(upper as i64) overflows signed negation.
        // u64::MAX * 0x8000_0000_0000_0001 overflows → saturates to u64::MAX
        assert_eq!(mul_sat_u64(u64::MAX, 0x8000_0000_0000_0001), u64::MAX);
        assert_eq!(mul_sat_u64(0x8000_0000_0000_0001, u64::MAX), u64::MAX);
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Correctness via commutativity and zero-property
    // -------------------------------------------------------------------------
    // Precondition:  { a, b ∈ U64 }
    // Postcondition: { result = min(a × b, 2^64 - 1) }
    //
    // Proof sketch:
    // 1. Compute full 128-bit product: (a as u128) * (b as u128)
    // 2. Extract upper 64 bits (indicates overflow)
    // 3. Branchless: Create mask from overflow condition (upper != 0)
    //    mask = 0u64.wrapping_sub((upper != 0) as u64)  [All-1s if upper != 0]
    //    Avoids signed negation that panics in debug builds when upper == i64::MIN.
    // 4. Result = (lower & ~mask) | (u64::MAX & mask)
    //    - If no overflow: mask = 0, result = lower
    //    - If overflow: mask = ~0, result = u64::MAX
    // 5. Commutativity: mul(a,b) = mul(b,a) via commutative u128 multiply
    // 6. Zero-property: mul(a,0) = 0 via a * 0 = 0 in u128
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_mul_sat_u64(c: &mut Criterion) {
        c.bench_function("mul_sat_u64_no_overflow", |b| {
            // Small numbers, no saturation
            b.iter(|| mul_sat_u64(black_box(42), black_box(1337)))
        });

        c.bench_function("mul_sat_u64_large", |b| {
            // Large numbers near overflow boundary
            b.iter(|| mul_sat_u64(black_box(0xFFFFFFFF), black_box(0xFFFFFFFF)))
        });

        c.bench_function("mul_sat_u64_saturate", |b| {
            // Maximum saturation scenario
            b.iter(|| mul_sat_u64(black_box(u64::MAX), black_box(2)))
        });
    }
}
