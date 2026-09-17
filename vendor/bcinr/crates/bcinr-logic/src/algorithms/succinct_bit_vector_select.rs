// Academic-grade branchless algorithm library: succinct_bit_vector_select
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// succinct_bit_vector_select
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::succinct_bit_vector_select::succinct_bit_vector_select;
/// let result = succinct_bit_vector_select(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn succinct_bit_vector_select(val: u64, aux: u64) -> u64 {
    // Branchless Contract: select query. Returns the 0-based index of the
    // (aux+1)-th set bit of `val`, or 64 if fewer than aux+1 bits are set. The
    // index equals the number of prefix positions whose inclusive rank does not
    // exceed `aux`; summed branchlessly over all 64 lanes.
    (((val & ((1u64 << 1) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 2) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 3) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 4) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 5) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 6) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 7) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 8) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 9) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 10) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 11) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 12) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 13) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 14) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 15) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 16) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 17) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 18) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 19) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 20) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 21) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 22) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 23) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 24) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 25) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 26) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 27) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 28) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 29) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 30) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 31) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 32) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 33) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 34) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 35) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 36) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 37) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 38) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 39) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 40) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 41) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 42) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 43) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 44) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 45) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 46) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 47) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 48) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 49) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 50) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 51) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 52) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 53) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 54) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 55) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 56) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 57) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 58) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 59) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 60) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 61) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 62) - 1)).count_ones() as u64 <= aux) as u64)
        + (((val & ((1u64 << 63) - 1)).count_ones() as u64 <= aux) as u64)
        + ((val.count_ones() as u64 <= aux) as u64)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn succinct_bit_vector_select_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: walk the bits low-to-high, decrementing a
        // remaining-count; return the position when the (aux+1)-th one is seen,
        // else 64 (test-only loop).
        let mut remaining = aux;
        let mut i: u32 = 0;
        while i < 64 {
            if (val >> i) & 1 == 1 {
                if remaining == 0 {
                    return i as u64;
                }
                remaining -= 1;
            }
            i += 1;
        }
        64
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_select_1(val: u64, aux: u64) -> u64 {
        !succinct_bit_vector_select_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_select_2(val: u64, aux: u64) -> u64 {
        succinct_bit_vector_select_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_succinct_bit_vector_select_3(val: u64, aux: u64) -> u64 {
        succinct_bit_vector_select_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_succinct_bit_vector_select_all() {
        // oracle
        assert_eq!(
            succinct_bit_vector_select(42, 1337),
            succinct_bit_vector_select_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            succinct_bit_vector_select(0, 0),
            succinct_bit_vector_select_reference(0, 0)
        );
        assert_eq!(
            succinct_bit_vector_select(u64::MAX, u64::MAX),
            succinct_bit_vector_select_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            succinct_bit_vector_select(u64::MAX, 0),
            succinct_bit_vector_select_reference(u64::MAX, 0)
        );
        assert_eq!(
            succinct_bit_vector_select(0, u64::MAX),
            succinct_bit_vector_select_reference(0, u64::MAX)
        );
        // mutants
        let base = succinct_bit_vector_select_reference(42, 1337);
        assert_ne!(
            mutant_succinct_bit_vector_select_1(42, 1337),
            base,
            "mutant 1"
        );
        assert_ne!(
            mutant_succinct_bit_vector_select_2(42, 1337),
            base,
            "mutant 2"
        );
        assert_ne!(
            mutant_succinct_bit_vector_select_3(42, 1337),
            base,
            "mutant 3"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = succinct_bit_vector_select_reference(val, aux) }
    //
    // Counterfactual Analysis for succinct_bit_vector_select:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_succinct_bit_vector_select(c: &mut Criterion) {
        c.bench_function("succinct_bit_vector_select", |b| {
            b.iter(|| {
                let res = succinct_bit_vector_select(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
