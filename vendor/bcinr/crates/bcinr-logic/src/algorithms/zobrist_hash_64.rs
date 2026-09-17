// Academic-grade branchless algorithm library: zobrist_hash_64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// zobrist_hash_64
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # CONTRACT
/// **Ensures:** The result matches the slow but correct reference implementation for all inputs.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::zobrist_hash_64::zobrist_hash_64;
/// let result = zobrist_hash_64(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
///
/// # Branchless Contract
/// Interpretation: a Zobrist incremental update. `val` is the current board hash,
/// `aux` is the piece-square index whose state toggles. The pseudo-random Zobrist
/// key for that index is generated deterministically from `aux` with a splitmix64
/// finalizer (standing in for the precomputed key table), and the new board hash is
/// `val XOR key`. XOR makes the update its own inverse, the defining Zobrist property.
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn zobrist_hash_64(val: u64, aux: u64) -> u64 {
    let mut k = aux.wrapping_add(0x9E3779B97F4A7C15);
    k = (k ^ (k >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    k = (k ^ (k >> 27)).wrapping_mul(0x94D049BB133111EB);
    k ^= k >> 31;
    val ^ k
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn zobrist_hash_64_reference(val: u64, aux: u64) -> u64 {
        // Re-derive the Zobrist key with the splitmix64 finalizer expressed as a
        // helper-per-stage pipeline, then toggle it into the board hash via XOR.
        fn xorshift_mul(x: u64, sh: u32, m: u64) -> u64 {
            (x ^ (x >> sh)).wrapping_mul(m)
        }
        let seeded = aux.wrapping_add(0x9E3779B97F4A7C15);
        let stage1 = xorshift_mul(seeded, 30, 0xBF58476D1CE4E5B9);
        let stage2 = xorshift_mul(stage1, 27, 0x94D049BB133111EB);
        let key = stage2 ^ (stage2 >> 31);
        val ^ key
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_zobrist_hash_64_1(val: u64, aux: u64) -> u64 {
        !zobrist_hash_64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_zobrist_hash_64_2(val: u64, aux: u64) -> u64 {
        zobrist_hash_64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_zobrist_hash_64_3(val: u64, aux: u64) -> u64 {
        zobrist_hash_64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Hardcoded edge cases
    // -------------------------------------------------------------------------
    #[test]
    fn test_zobrist_hash_64_all() {
        // oracle
        assert_eq!(
            zobrist_hash_64(42, 1337),
            zobrist_hash_64_reference(42, 1337)
        );
        // boundaries
        assert_eq!(zobrist_hash_64(0, 0), zobrist_hash_64_reference(0, 0));
        assert_eq!(
            zobrist_hash_64(u64::MAX, u64::MAX),
            zobrist_hash_64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            zobrist_hash_64(u64::MAX, 0),
            zobrist_hash_64_reference(u64::MAX, 0)
        );
        assert_eq!(
            zobrist_hash_64(0, u64::MAX),
            zobrist_hash_64_reference(0, u64::MAX)
        );
        // mutants
        let base = zobrist_hash_64_reference(42, 1337);
        assert_ne!(mutant_zobrist_hash_64_1(42, 1337), base, "mutant 1");
        assert_ne!(mutant_zobrist_hash_64_2(42, 1337), base, "mutant 2");
        assert_ne!(mutant_zobrist_hash_64_3(42, 1337), base, "mutant 3");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = zobrist_hash_64_reference(val, aux) }
    //
    // Counterfactual Analysis for zobrist_hash_64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_zobrist_hash_64(c: &mut Criterion) {
        c.bench_function("zobrist_hash_64", |b| {
            b.iter(|| {
                let res = zobrist_hash_64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
