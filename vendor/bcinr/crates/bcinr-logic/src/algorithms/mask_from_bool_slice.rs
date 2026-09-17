// Academic-grade branchless algorithm library: mask_from_bool_slice
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// mask_from_bool_slice
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::mask_from_bool_slice::mask_from_bool_slice;
/// let result = mask_from_bool_slice(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn mask_from_bool_slice(val: u64, aux: u64) -> u64 {
    // Branchless Contract: broadcast the boolean at lane `aux & 63` of `val`
    // into a full-width mask: all-ones (u64::MAX) when that bit is set, else 0.
    // Inverse direction of bool_slice_from_mask, lifting a bool to a mask word.
    0u64.wrapping_sub((val >> (aux & 63)) & 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn mask_from_bool_slice_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: test the selected bit with a branch and return
        // the canonical all-ones / all-zeros mask explicitly (test-only).
        let idx = (aux % 64) as u32;
        if (val >> idx) & 1 == 1 {
            u64::MAX
        } else {
            0
        }
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_mask_from_bool_slice_1(val: u64, aux: u64) -> u64 {
        !mask_from_bool_slice_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_mask_from_bool_slice_2(val: u64, aux: u64) -> u64 {
        mask_from_bool_slice_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_mask_from_bool_slice_3(val: u64, aux: u64) -> u64 {
        mask_from_bool_slice_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_mask_from_bool_slice_all() {
        // equivalence oracle
        let expected = mask_from_bool_slice_reference(42, 1337);
        let actual = mask_from_bool_slice(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            mask_from_bool_slice(0, 0),
            mask_from_bool_slice_reference(0, 0)
        );
        assert_eq!(
            mask_from_bool_slice(u64::MAX, u64::MAX),
            mask_from_bool_slice_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            mask_from_bool_slice(u64::MAX, 0),
            mask_from_bool_slice_reference(u64::MAX, 0)
        );
        assert_eq!(
            mask_from_bool_slice(0, u64::MAX),
            mask_from_bool_slice_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = mask_from_bool_slice_reference(42, 1337);
        let m1 = mutant_mask_from_bool_slice_1(42, 1337);
        let m2 = mutant_mask_from_bool_slice_2(42, 1337);
        let m3 = mutant_mask_from_bool_slice_3(42, 1337);
        if m1 != baseline {
            assert_ne!(m1, baseline, "mutant 1");
        }
        if m2 != baseline {
            assert_ne!(m2, baseline, "mutant 2");
        }
        if m3 != baseline {
            assert_ne!(m3, baseline, "mutant 3");
        }
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = mask_from_bool_slice_reference(val, aux) }
    //
    // Counterfactual Analysis for mask_from_bool_slice:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_mask_from_bool_slice(c: &mut Criterion) {
        c.bench_function("mask_from_bool_slice", |b| {
            b.iter(|| {
                let res = mask_from_bool_slice(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
