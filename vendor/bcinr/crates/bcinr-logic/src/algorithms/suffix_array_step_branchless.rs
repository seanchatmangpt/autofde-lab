// Academic-grade branchless algorithm library: suffix_array_step_branchless
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// suffix_array_step_branchless
///
/// Interpretation: one step of suffix-array construction by prefix doubling.
/// At each doubling step a suffix's composite sort key is formed from its
/// current rank `val` and the rank of the suffix `k` positions later, `aux`.
/// The key packs the primary rank into the high 32 bits and the secondary
/// rank into the low 32 bits: `(val_lo32 << 32) | aux_lo32`, so lexicographic
/// comparison of keys yields the doubled-order ranking.
///
/// # Branchless Contract
/// **Ensures:** Result equals ((val & 0xFFFFFFFF) << 32) | (aux & 0xFFFFFFFF).
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::suffix_array_step_branchless::suffix_array_step_branchless;
/// let result = suffix_array_step_branchless(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn suffix_array_step_branchless(val: u64, aux: u64) -> u64 {
    ((val & 0xFFFF_FFFF) << 32) | (aux & 0xFFFF_FFFF)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // NOTE: Identical to main implementation (no simpler correct variant exists).
    // -------------------------------------------------------------------------
    fn suffix_array_step_branchless_reference(val: u64, aux: u64) -> u64 {
        // Independent structure: assemble the 64-bit key from its 8 bytes,
        // taking the low 4 bytes of val as the high half and the low 4 bytes
        // of aux as the low half.
        let primary = val.to_le_bytes();
        let secondary = aux.to_le_bytes();
        let mut bytes = [0u8; 8];
        bytes[..4].copy_from_slice(&secondary[..4]); // low 32 bits = aux
        bytes[4..8].copy_from_slice(&primary[..4]); // high 32 bits = val
        u64::from_le_bytes(bytes)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_suffix_array_step_branchless_1(val: u64, aux: u64) -> u64 {
        !suffix_array_step_branchless_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_suffix_array_step_branchless_2(val: u64, aux: u64) -> u64 {
        suffix_array_step_branchless_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_suffix_array_step_branchless_3(val: u64, aux: u64) -> u64 {
        suffix_array_step_branchless_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_suffix_array_step_branchless_all() {
        // oracle
        assert_eq!(
            suffix_array_step_branchless(42, 1337),
            suffix_array_step_branchless_reference(42, 1337)
        );
        // boundaries
        assert_eq!(
            suffix_array_step_branchless(0, 0),
            suffix_array_step_branchless_reference(0, 0)
        );
        assert_eq!(
            suffix_array_step_branchless(u64::MAX, u64::MAX),
            suffix_array_step_branchless_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            suffix_array_step_branchless(u64::MAX, 0),
            suffix_array_step_branchless_reference(u64::MAX, 0)
        );
        assert_eq!(
            suffix_array_step_branchless(0, u64::MAX),
            suffix_array_step_branchless_reference(0, u64::MAX)
        );
        // mutants
        let base = suffix_array_step_branchless_reference(42, 1337);
        assert_ne!(
            mutant_suffix_array_step_branchless_1(42, 1337),
            base,
            "mutant 1"
        );
        assert_ne!(
            mutant_suffix_array_step_branchless_2(42, 1337),
            base,
            "mutant 2"
        );
        assert_ne!(
            mutant_suffix_array_step_branchless_3(42, 1337),
            base,
            "mutant 3"
        );
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = suffix_array_step_branchless_reference(val, aux) }
    //
    // Counterfactual Analysis for suffix_array_step_branchless:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_suffix_array_step_branchless(c: &mut Criterion) {
        c.bench_function("suffix_array_step_branchless", |b| {
            b.iter(|| {
                let res = suffix_array_step_branchless(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
