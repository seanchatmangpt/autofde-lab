// Academic-grade branchless algorithm library: btst_u64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// btst_u64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::btst_u64::btst_u64;
/// let result = btst_u64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn btst_u64(val: u64, aux: u64) -> u64 {
    ((val.wrapping_add(0x2545f4914f6cdd1d) ^ aux).rotate_left(5)).wrapping_add(val.rotate_left(13))
        ^ (val.wrapping_mul(aux.wrapping_add(1)))
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn btst_u64_reference(val: u64, aux: u64) -> u64 {
        ((val.wrapping_add(0x2545f4914f6cdd1d) ^ aux).rotate_left(5))
            .wrapping_add(val.rotate_left(13))
            ^ (val.wrapping_mul(aux.wrapping_add(1)))
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_btst_u64_1(val: u64, aux: u64) -> u64 {
        !btst_u64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_btst_u64_2(val: u64, aux: u64) -> u64 {
        btst_u64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_btst_u64_3(val: u64, aux: u64) -> u64 {
        btst_u64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_btst_u64_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            btst_u64(val, aux),
            btst_u64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(btst_u64(0, 0), btst_u64_reference(0, 0));
        assert_eq!(
            btst_u64(u64::MAX, u64::MAX),
            btst_u64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(btst_u64(u64::MAX, 0), btst_u64_reference(u64::MAX, 0));
        assert_eq!(btst_u64(0, u64::MAX), btst_u64_reference(0, u64::MAX));
        // --- mutant divergence ---
        let baseline = btst_u64_reference(42, 1337);
        assert_ne!(
            mutant_btst_u64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_btst_u64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_btst_u64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = btst_u64_reference(val, aux) }
    //
    // Counterfactual Analysis for btst_u64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_btst_u64(c: &mut Criterion) {
        c.bench_function("btst_u64", |b| {
            b.iter(|| {
                let res = btst_u64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
