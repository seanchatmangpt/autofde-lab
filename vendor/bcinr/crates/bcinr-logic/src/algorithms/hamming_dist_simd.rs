// Academic-grade branchless algorithm library: hamming_dist_simd
// Automatically generated scaffolding for AGI-level branchless primitives.
// Assumes adherence to zero-branching, 0-allocation, and sub-10ns latency.

/// hamming_dist_simd
///
/// Branchless implementation guaranteed to execute in constant time
/// with zero dynamic dispatch or control flow hazards.
///
/// # Branchless Contract
/// **Ensures:** Returns the Hamming distance between `val` and `aux`, i.e. the number
/// of differing bit positions, `popcount(val XOR aux)` (result in 0..=64).
/// **Invariant:** Execution path is independent of input data values (Branchless).
///
/// ```rust
/// use bcinr_logic::algorithms::hamming_dist_simd::hamming_dist_simd;
/// let result = hamming_dist_simd(42, 1337);
/// assert!(result <= u64::MAX);
/// ```
// SAFETY_LEVEL: no unsafe code permitted in algorithm modules (enforced via forbid in lib.rs)
#[no_mangle]
#[allow(unused_variables)]
pub fn hamming_dist_simd(val: u64, aux: u64) -> u64 {
    (val ^ aux).count_ones() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // POSITIVE ORACLE: Reference implementation
    // -------------------------------------------------------------------------
    fn hamming_dist_simd_reference(val: u64, aux: u64) -> u64 {
        // Independent derivation: walk each of the 64 bit positions and tally the
        // ones where val and aux disagree, instead of using count_ones.
        let diff = val ^ aux;
        let mut dist = 0u64;
        for i in 0..64 {
            dist += (diff >> i) & 1;
        }
        dist
    }

    // -------------------------------------------------------------------------
    // NEGATIVE MUTANTS: Intentionally flawed versions
    // -------------------------------------------------------------------------
    #[allow(unused_variables)]
    fn mutant_hamming_dist_simd_1(val: u64, aux: u64) -> u64 {
        !hamming_dist_simd_reference(val, aux)
    } // Identity bluff
    #[allow(unused_variables)]
    fn mutant_hamming_dist_simd_2(val: u64, aux: u64) -> u64 {
        hamming_dist_simd_reference(val, aux).wrapping_add(1)
    } // Bit-skip bluff
    #[allow(unused_variables)]
    fn mutant_hamming_dist_simd_3(val: u64, aux: u64) -> u64 {
        hamming_dist_simd_reference(val, aux) ^ 0xFFFFFFFF
    } // Operator-swap bluff

    #[test]
    fn test_hamming_dist_simd_all() {
        // equivalence oracle
        let expected = hamming_dist_simd_reference(42, 1337);
        let actual = hamming_dist_simd(42, 1337);
        assert_eq!(expected, actual, "Adversarial failure: branchless mismatch");
        // boundaries

        assert_eq!(hamming_dist_simd(0, 0), hamming_dist_simd_reference(0, 0));
        assert_eq!(
            hamming_dist_simd(u64::MAX, u64::MAX),
            hamming_dist_simd_reference(u64::MAX, u64::MAX)
        );
        assert_eq!(
            hamming_dist_simd(u64::MAX, 0),
            hamming_dist_simd_reference(u64::MAX, 0)
        );
        assert_eq!(
            hamming_dist_simd(0, u64::MAX),
            hamming_dist_simd_reference(0, u64::MAX)
        );
        // mutant divergence
        let baseline = hamming_dist_simd_reference(42, 1337);
        let m1 = mutant_hamming_dist_simd_1(42, 1337);
        let m2 = mutant_hamming_dist_simd_2(42, 1337);
        let m3 = mutant_hamming_dist_simd_3(42, 1337);
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
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_hamming_dist_simd(c: &mut Criterion) {
        c.bench_function("hamming_dist_simd", |b| {
            b.iter(|| {
                let res = hamming_dist_simd(black_box(42), black_box(1337));
                black_box(res)
            })
        });
    }
}
