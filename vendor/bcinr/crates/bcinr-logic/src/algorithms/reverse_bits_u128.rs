// Academic-grade branchless algorithm library: reverse_bits_u128
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// reverse_bits_u128
///
/// Returns the **low 64 bits** of the bit-reversed 128-bit integer formed by
/// `(val, aux)` where `val` is the low word and `aux` is the high word.
///
/// When reversing a 128-bit number, the low output word is the bit-reversal
/// of the high input word:
/// - `low_output  = aux.reverse_bits()`
/// - `high_output = val.reverse_bits()`  (call with arguments swapped to obtain this)
///
/// # Arguments
/// - `val` — low 64 bits of the 128-bit input
/// - `aux` — high 64 bits of the 128-bit input
///
/// # Returns
/// Low 64 bits of the bit-reversed 128-bit value.
///
/// # Branchless Contract
/// **Ensures:** The result matches the low word of the 128-bit bit reversal.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::reverse_bits_u128::reverse_bits_u128;
/// // (val=0, aux=1): 128-bit number with bit 64 set.
/// // Reversed: bit 63 of the low output word is set.
/// assert_eq!(reverse_bits_u128(0, 1), 0x8000_0000_0000_0000u64);
/// // (val=1, aux=0): 128-bit number with bit 0 set.
/// // Reversed: low output word = 0.reverse_bits() = 0.
/// assert_eq!(reverse_bits_u128(1, 0), 0u64);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
pub fn reverse_bits_u128(val: u64, aux: u64) -> u64 {
    // Interprets (val=low, aux=high) as a 128-bit integer.
    // The LOW 64 bits of the bit-reversed 128-bit value = aux.reverse_bits().
    // (The high 64 bits of the reversal = val.reverse_bits(); call with args swapped for that half.)
    let _ = val; // low word of input → high word of output (use swapped call for that half)
    aux.reverse_bits()
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // Treats (val=low, aux=high) as a 128-bit integer, reverses all 128 bits,
    // returns the LOW 64 bits of the result.
    // -------------------------------------------------------------------------
    fn reverse_bits_u128_reference(val: u64, aux: u64) -> u64 {
        // Reconstruct the 128-bit value
        let n128: u128 = (val as u128) | ((aux as u128) << 64);
        // Reverse all 128 bits
        let rev = n128.reverse_bits();
        // Return the low 64 bits
        rev as u64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_reverse_bits_u128_1(val: u64, aux: u64) -> u64 {
        !reverse_bits_u128_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_reverse_bits_u128_2(val: u64, aux: u64) -> u64 {
        reverse_bits_u128_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_reverse_bits_u128_3(val: u64, aux: u64) -> u64 {
        reverse_bits_u128_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    proptest! {
        #[test]
        fn test_reverse_bits_u128_equivalence(val in any::<u64>(), aux in any::<u64>()) {
            let expected = reverse_bits_u128_reference(val, aux);
            let actual = reverse_bits_u128(val, aux);
            prop_assert_eq!(expected, actual, "Adversarial failure: branchless mismatch val={:#018x} aux={:#018x}", val, aux);
        }
    }

    #[test]
    fn test_reverse_bits_u128_boundaries() {
        // (0, 0): no bits set → reversal = 0; low word = 0
        assert_eq!(reverse_bits_u128(0, 0), 0);
        assert_eq!(reverse_bits_u128(0, 0), reverse_bits_u128_reference(0, 0));

        // (u64::MAX, u64::MAX): all 128 bits set → reversed all set; low word = u64::MAX
        assert_eq!(reverse_bits_u128(u64::MAX, u64::MAX), u64::MAX);
        assert_eq!(
            reverse_bits_u128(u64::MAX, u64::MAX),
            reverse_bits_u128_reference(u64::MAX, u64::MAX)
        );

        // (u64::MAX, 0): low input word = all ones, high input = 0.
        // Low output = 0.reverse_bits() = 0
        assert_eq!(reverse_bits_u128(u64::MAX, 0), 0);
        assert_eq!(
            reverse_bits_u128(u64::MAX, 0),
            reverse_bits_u128_reference(u64::MAX, 0)
        );

        // (0, u64::MAX): low input = 0, high input = all ones.
        // Low output = u64::MAX.reverse_bits() = u64::MAX
        assert_eq!(reverse_bits_u128(0, u64::MAX), u64::MAX);
        assert_eq!(
            reverse_bits_u128(0, u64::MAX),
            reverse_bits_u128_reference(0, u64::MAX)
        );

        // (1, 0): bit 0 set in input. Reversed 128-bit has bit 127 set.
        // Low output word = 0 (bit 127 is in the HIGH output word)
        assert_eq!(reverse_bits_u128(1, 0), 0);

        // (0, 1): bit 64 set in input. Reversed 128-bit has bit 63 set.
        // Low output word = 0x8000_0000_0000_0000
        assert_eq!(reverse_bits_u128(0, 1), 0x8000_0000_0000_0000u64);

        // --- mutant divergence ---
        // Same convention as this crate's sibling algorithm files (e.g.
        // `bit_swap_u64.rs`): the NEGATIVE MUTANTS defined above exist to be
        // exercised here, not merely declared — an unwired mutant is dead
        // code (and, more importantly, proves nothing about this test
        // suite's ability to catch the bug class it represents).
        let baseline = reverse_bits_u128_reference(42, 1337);
        assert_ne!(
            mutant_reverse_bits_u128_1(42, 1337),
            baseline,
            "mutant 1 (identity bluff) must diverge from reference"
        );
        assert_ne!(
            mutant_reverse_bits_u128_2(42, 1337),
            baseline,
            "mutant 2 (bit-skip bluff) must diverge from reference"
        );
        assert_ne!(
            mutant_reverse_bits_u128_3(42, 1337),
            baseline,
            "mutant 3 (operator-swap bluff) must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = low 64 bits of reverse_bits((val as u128) | ((aux as u128) << 64)) }
    //
    // Proof: bit i of the 128-bit input maps to bit (127-i) of the reversal.
    // Bits 0-63 of the input (= val) map to bits 127-64 of the reversal (= high word).
    // Bits 64-127 of the input (= aux) map to bits 63-0 of the reversal (= low word).
    // Therefore low_output = aux.reverse_bits(). QED.
    //
    // Counterfactual Analysis for reverse_bits_u128:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_reverse_bits_u128(c: &mut Criterion) {
        c.bench_function("reverse_bits_u128", |b| {
            b.iter(|| {
                let res = reverse_bits_u128(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
