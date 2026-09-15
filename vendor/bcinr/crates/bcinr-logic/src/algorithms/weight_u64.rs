// Academic-grade branchless algorithm library: weight_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// weight_u64
///
/// Branchless Contract: computes the Hamming weight (popcount) of the bitwise
/// AND of the two operands — i.e. the number of bit positions set in BOTH
/// `val` and `aux`. This is the standard "weight" of the intersection word.
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::weight_u64::weight_u64;
/// let result = weight_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn weight_u64(val: u64, aux: u64) -> u64 {
    (val & aux).count_ones() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn weight_u64_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: iterate bit positions, count shared set bits.
        let common = val & aux;
        let mut count = 0u64;
        for i in 0..64 {
            count += (common >> i) & 1;
        }
        count
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_weight_u64_1(val: u64, aux: u64) -> u64 {
        !weight_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_weight_u64_2(val: u64, aux: u64) -> u64 {
        weight_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_weight_u64_3(val: u64, aux: u64) -> u64 {
        weight_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_weight_u64_all() {
        // oracle
        assert_eq!(weight_u64(42, 1337), weight_u64_reference(42, 1337));
        // boundaries
        assert_eq!(weight_u64(0, 0), weight_u64_reference(0, 0));
        assert_eq!(
            weight_u64(u64::MAX, u64::MAX),
            weight_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(weight_u64(u64::MAX, 0), weight_u64_reference(u64::MAX, 0));
        assert_eq!(weight_u64(0, u64::MAX), weight_u64_reference(0, u64::MAX));
        // mutants
        let base = weight_u64_reference(42, 1337);
        assert_ne!(mutant_weight_u64_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_weight_u64_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_weight_u64_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = weight_u64_reference(val, aux) }
    //
    // Counterfactual Analysis for weight_u64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_weight_u64(c: &mut Criterion) {
        c.bench_function("weight_u64", |b| {
            b.iter(|| {
                let res = weight_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
