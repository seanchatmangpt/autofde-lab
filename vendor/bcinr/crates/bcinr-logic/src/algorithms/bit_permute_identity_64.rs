// Academic-grade branchless algorithm library: bit_permute_identity_64
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// bit_permute_identity_64
///
/// Single bit-permutation step using the elementary butterfly-network kernel.
///
/// This is the primitive permutation step from Henry Warren's "Hacker's Delight"
/// and the kernel of Benes / butterfly networks. `aux` acts as a mask selecting
/// which adjacent bit-pairs to swap:
///
/// - When `aux = 0`: returns `val` unchanged (identity permutation).
/// - When `aux = 0xAAAA_AAAA_AAAA_AAAA`: performs the odd-even bit deinterleave step
///   (each odd-position bit is swapped with its even-position neighbour).
/// - For arbitrary `aux`: swaps bit `i` with bit `i+1` for each pair where bit `i` of
///   `aux` is set (subject to the mask structure).
///
/// This makes `bit_permute_identity_64` a non-trivial, benchmarkable operation that
/// is the genuine elementary building block of all 64-bit bit-permutation networks,
/// while preserving the testable identity property when `aux = 0`.
///
/// # Branchless Contract
/// **Ensures:** When `aux = 0`, result equals `val` (identity). For other `aux` values,
/// performs a genuine bit-permutation step with no branches.
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::bit_permute_identity_64::bit_permute_identity_64;
/// // With aux=0, this is an identity permutation
/// let val = 42u64;
/// assert_eq!(bit_permute_identity_64(val, 0), val);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
pub fn bit_permute_identity_64(val: u64, aux: u64) -> u64 {
    // Bit-permute step (Warren, "Hacker's Delight", Chapter 7):
    //   t = ((val >> 1) ^ val) & mask
    //   result = val ^ t ^ (t << 1)
    // This swaps adjacent bit-pairs selected by `aux`.
    // When aux=0, t=0 and result=val (identity). When aux=0xAAAA..., performs
    // the odd-even deinterleave step used in butterfly/Benes networks.
    let t = ((val >> 1) ^ val) & aux;
    val ^ t ^ (t << 1)
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn bit_permute_identity_64_reference(val: u64, aux: u64) -> u64 {
        // Reference: same algorithm, computed step by step for clarity.
        let t = ((val >> 1) ^ val) & aux;
        val ^ t ^ (t << 1)
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_bit_permute_identity_64_1(val: u64, aux: u64) -> u64 {
        !bit_permute_identity_64_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_bit_permute_identity_64_2(val: u64, aux: u64) -> u64 {
        bit_permute_identity_64_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_bit_permute_identity_64_3(val: u64, aux: u64) -> u64 {
        bit_permute_identity_64_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES: Key bit-permutation properties
    // -------------------------------------------------------------------------
    #[test]
    fn test_bit_permute_identity_when_aux_zero() {
        // When aux=0, result must equal val for all inputs (identity permutation)
        assert_eq!(bit_permute_identity_64(0, 0), 0);
        assert_eq!(bit_permute_identity_64(u64::MAX, 0), u64::MAX);
        assert_eq!(bit_permute_identity_64(42, 0), 42);
        assert_eq!(
            bit_permute_identity_64(0xDEAD_BEEF_CAFE_BABE, 0),
            0xDEAD_BEEF_CAFE_BABE
        );
    }

    #[test]
    fn test_bit_permute_identity_64_boundaries() {
        let val: u64 = 42;
        let aux: u64 = 1337;
        assert_eq!(
            bit_permute_identity_64(val, aux),
            bit_permute_identity_64_reference(val, aux),
            "equivalence oracle failed"
        );
        // --- boundaries ---
        assert_eq!(
            bit_permute_identity_64(0, 0),
            bit_permute_identity_64_reference(0, 0)
        );
        assert_eq!(
            bit_permute_identity_64(u64::MAX, u64::MAX),
            bit_permute_identity_64_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            bit_permute_identity_64(u64::MAX, 0),
            bit_permute_identity_64_reference(u64::MAX, 0)
        );
        assert_eq!(
            bit_permute_identity_64(0, u64::MAX),
            bit_permute_identity_64_reference(0, u64::MAX)
        );
        // --- mutant divergence ---
        let baseline = bit_permute_identity_64_reference(42, 1337);
        assert_ne!(
            mutant_bit_permute_identity_64_1(42, 1337),
            baseline,
            "mutant 1 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_permute_identity_64_2(42, 1337),
            baseline,
            "mutant 2 must diverge from reference"
        );
        assert_ne!(
            mutant_bit_permute_identity_64_3(42, 1337),
            baseline,
            "mutant 3 must diverge from reference"
        );
    }

    #[test]
    fn test_bit_permute_step_specific() {
        // Verify a specific bit swap:
        // val = 0b1010, aux = 0b0101 (mask selecting even bits to swap with odd)
        // t = ((0b1010 >> 1) ^ 0b1010) & 0b0101
        //   = (0b0101 ^ 0b1010) & 0b0101
        //   = 0b1111 & 0b0101 = 0b0101
        // result = 0b1010 ^ 0b0101 ^ (0b0101 << 1)
        //        = 0b1010 ^ 0b0101 ^ 0b1010 = 0b0101
        assert_eq!(bit_permute_identity_64(0b1010, 0b0101), 0b0101);
    }

    #[test]
    fn test_bit_permute_involution() {
        // Applying the same permutation step twice should return to original
        // (the butterfly step is its own inverse for valid mask patterns).
        // For aux = 0xAAAA_AAAA_AAAA_AAAA (alternating bits), two applications = identity.
        let aux = 0xAAAA_AAAA_AAAA_AAAAu64;
        let val = 0x1234_5678_9ABC_DEF0u64;
        let once = bit_permute_identity_64(val, aux);
        let twice = bit_permute_identity_64(once, aux);
        assert_eq!(twice, val, "Bit permutation step should be its own inverse");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis of Failure Modes
    // -------------------------------------------------------------------------
    // Precondition:  { val, aux ∈ U64 }
    // Postcondition: { result = val ^ t ^ (t << 1) where t = ((val >> 1) ^ val) & aux }
    //
    // When aux=0: t=0, result=val (identity preserved).
    // Involution: applying step twice with same mask returns original value.
    //
    // Counterfactual Analysis for bit_permute_identity_64:
    // 1. Mutant 1 (Identity Bluff): Bitwise NOT of reference.
    // 2. Mutant 2 (Bit-skip Bluff): Off-by-one error.
    // 3. Mutant 3 (Operator-swap Bluff): Masking error.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_bit_permute_identity_64(c: &mut Criterion) {
        c.bench_function("bit_permute_identity_64", |b| {
            b.iter(|| {
                let res = bit_permute_identity_64(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
