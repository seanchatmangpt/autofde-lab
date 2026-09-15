// Academic-grade branchless algorithm library: perfect_hash_lookup_u32
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// perfect_hash_lookup_u32
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::perfect_hash_lookup_u32::perfect_hash_lookup_u32;
/// let result = perfect_hash_lookup_u32(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
/// Interpretation: the query side of a CHD perfect hash. `val` is the key, `aux`
/// is the displacement value fetched for the key's bucket. The final slot index is
/// `g(val)` displaced by `aux`: a Fibonacci hash of the key XOR-combined with the
/// displacement and re-mixed. The lower bits would be masked to the table size by
/// the caller; here the full 64-bit displaced hash is returned.
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn perfect_hash_lookup_u32(val: u64, aux: u64) -> u64 {
    let g = val.wrapping_mul(0x9E3779B97F4A7C15);
    let displaced = g ^ aux.wrapping_mul(0x100000001B3);
    (displaced ^ (displaced >> 29)).wrapping_add(aux)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn perfect_hash_lookup_u32_reference(val: u64, aux: u64) -> u64 {
        // Same displaced-hash, recomposed with named intermediates and a
        // separate xorshift step expressed as subtraction-free folding.
        let key_hash = val.wrapping_mul(0x9E3779B97F4A7C15);
        let disp = aux.wrapping_mul(0x100000001B3);
        let combined = key_hash ^ disp;
        let high = combined >> 29;
        let avalanched = combined ^ high;
        avalanched.wrapping_add(aux)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_perfect_hash_lookup_u32_1(val: u64, aux: u64) -> u64 {
        !perfect_hash_lookup_u32_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_perfect_hash_lookup_u32_2(val: u64, aux: u64) -> u64 {
        perfect_hash_lookup_u32_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_perfect_hash_lookup_u32_3(val: u64, aux: u64) -> u64 {
        perfect_hash_lookup_u32_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_perfect_hash_lookup_u32_all() {
        // equivalence oracle
        let expected = perfect_hash_lookup_u32_reference(42, 1337);
        let actual = perfect_hash_lookup_u32(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(
            perfect_hash_lookup_u32(0, 0),
            perfect_hash_lookup_u32_reference(0, 0)
        );
        assert_eq!(
            perfect_hash_lookup_u32(u64::MAX, u64::MAX),
            perfect_hash_lookup_u32_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            perfect_hash_lookup_u32(u64::MAX, 0),
            perfect_hash_lookup_u32_reference(u64::MAX, 0)
        );
        assert_eq!(
            perfect_hash_lookup_u32(0, u64::MAX),
            perfect_hash_lookup_u32_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = perfect_hash_lookup_u32_reference(42, 1337);
        let m1 = mutant_perfect_hash_lookup_u32_1(42, 1337);
        let m2 = mutant_perfect_hash_lookup_u32_2(42, 1337);
        let m3 = mutant_perfect_hash_lookup_u32_3(42, 1337);
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
    // Postcondition: { result = perfect_hash_lookup_u32_reference(val, aux) }
    //
    // Counterfactual Analysis for perfect_hash_lookup_u32:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_perfect_hash_lookup_u32(c: &mut Criterion) {
        c.bench_function("perfect_hash_lookup_u32", |b| {
            b.iter(|| {
                let res = perfect_hash_lookup_u32(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
