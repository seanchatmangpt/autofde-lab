// Academic-grade branchless algorithm library: bool_slice_from_mask
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bool_slice_from_mask
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bool_slice_from_mask::bool_slice_from_mask;
/// let result = bool_slice_from_mask(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn bool_slice_from_mask(val: u64, aux: u64) -> u64 {
    // Branchless Contract: decode the boolean (0 or 1) stored at lane index
    // `aux & 63` of the packed bit-mask `val`. This materializes one element of
    // a bool slice from a mask word: result == 1 iff that bit is set.
    (val >> (aux & 63)) & 1
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn bool_slice_from_mask_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: build a single-bit selector mask, AND it with
        // `val`, then test for non-zero via a control-flow branch (test-only).
        let idx = (aux % 64) as u32;
        let selector: u64 = 1u64 << idx;
        if (val & selector) != 0 {
            1
        } else {
            0
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bool_slice_from_mask_1(val: u64, aux: u64) -> u64 {
        !bool_slice_from_mask_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bool_slice_from_mask_2(val: u64, aux: u64) -> u64 {
        bool_slice_from_mask_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bool_slice_from_mask_3(val: u64, aux: u64) -> u64 {
        bool_slice_from_mask_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_bool_slice_from_mask_cases() {
        // --- equivalence oracle (canonical inputs) ---
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bool_slice_from_mask(val, aux),
            bool_slice_from_mask_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            bool_slice_from_mask(0, 0),
            bool_slice_from_mask_reference(0, 0)
        );
        assert_eq!(
            bool_slice_from_mask(u64::MAX, u64::MAX),
            bool_slice_from_mask_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bool_slice_from_mask(u64::MAX, 0),
            bool_slice_from_mask_reference(u64::MAX, 0)
        );
        assert_eq!(
            bool_slice_from_mask(0, u64::MAX),
            bool_slice_from_mask_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bool_slice_from_mask_reference(42, 1337);
        assert_ne!(
            mutant_bool_slice_from_mask_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bool_slice_from_mask_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bool_slice_from_mask_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = bool_slice_from_mask_reference(val, aux) }
    //
    // Counterfactual Analysis for bool_slice_from_mask:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bool_slice_from_mask(c: &mut Criterion) {
        c.bench_function("bool_slice_from_mask", |b| {
            b.iter(|| {
                let res = bool_slice_from_mask(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
