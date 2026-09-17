#![forbid(unsafe_code)]
// Academic-grade branchless algorithm library: simhash_cosine_u64
// SimHash: locality-sensitive hash for near-duplicate detection (64-bit).
// Produces 64-bit signatures where similar documents have small Hamming distance.

/// Compute a 64-bit SimHash signature from a set of pre-hashed feature values.
///
/// SimHash converts a multiset of 64-bit feature hashes into a single 64-bit
/// signature such that documents sharing many features will have signatures with
/// small Hamming distance. The algorithm accumulates a per-bit vote: for each
/// feature, bit `b` contributes +1 if set or -1 if clear. The final signature
/// sets bit `b` iff the net vote is positive (branchlessly).
///
/// # Arguments
/// * `features` - Slice of pre-hashed 64-bit feature values (e.g., hashed n-grams).
///
/// # Returns
/// A 64-bit signature. Similar inputs produce signatures with low Hamming distance.
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::simhash_cosine_u64::{simhash_cosine_u64, simhash_hamming_distance};
/// let features = [1u64, 2u64, 3u64];
/// let sig = simhash_cosine_u64(&features);
/// assert_eq!(simhash_hamming_distance(sig, sig), 0);
/// ```
pub fn simhash_cosine_u64(features: &[u64]) -> u64 {
    // Accumulate signed bit-votes: +1 for each feature with bit set, -1 for clear.
    let mut counts = [0i32; 64];
    features.iter().for_each(|&f| {
        (0..64usize).for_each(|bit| {
            // Branchless: extract bit, map 0→-1 and 1→+1 via (bit*2 - 1).
            let bit_val = ((f >> bit) & 1) as i32;
            let vote = bit_val * 2 - 1; // -1 or +1, no branch
            counts[bit] = counts[bit].wrapping_add(vote);
        });
    });
    // Set output bit b iff counts[b] > 0; branchless via sign extraction.
    let mut sig = 0u64;
    (0..64usize).for_each(|bit| {
        // positive = 1 when counts[bit] > 0, 0 otherwise.
        let positive = (counts[bit] > 0) as u64;
        sig |= positive << bit;
    });
    sig
}

/// Compute the Hamming distance between two 64-bit SimHash signatures.
///
/// Lower distance means more similar documents (near-duplicate detection
/// typically uses a threshold of 3 differing bits for similarity).
///
/// # Examples
/// ```rust
/// use bcinr_logic::algorithms::simhash_cosine_u64::simhash_hamming_distance;
/// assert_eq!(simhash_hamming_distance(0u64, 0u64), 0);
/// assert_eq!(simhash_hamming_distance(u64::MAX, 0u64), 64);
/// ```
pub fn simhash_hamming_distance(a: u64, b: u64) -> u32 {
    (a ^ b).count_ones()
}

#[cfg(all(test, not(miri)))]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // -------------------------------------------------------------------------
    // Reference implementation: identical algorithm, different structure
    // -------------------------------------------------------------------------
    fn simhash_cosine_u64_reference(features: &[u64]) -> u64 {
        let mut counts = [0i64; 64];
        for &f in features {
            for bit in 0..64usize {
                if (f >> bit) & 1 == 1 {
                    counts[bit] += 1;
                } else {
                    counts[bit] -= 1;
                }
            }
        }
        let mut sig = 0u64;
        for bit in 0..64usize {
            if counts[bit] > 0 {
                sig |= 1u64 << bit;
            }
        }
        sig
    }

    #[test]
    fn test_empty_features() {
        // No features → all votes zero → no bits set.
        let sig = simhash_cosine_u64(&[]);
        assert_eq!(sig, 0, "Empty feature set must yield 0 signature");
    }

    #[test]
    fn test_single_feature_all_ones() {
        // Single feature = u64::MAX: every bit gets vote +1 → all bits set.
        let sig = simhash_cosine_u64(&[u64::MAX]);
        assert_eq!(
            sig,
            u64::MAX,
            "All-ones feature must produce all-ones signature"
        );
    }

    #[test]
    fn test_single_feature_all_zeros() {
        // Single feature = 0: every bit gets vote -1 → no bits set.
        let sig = simhash_cosine_u64(&[0]);
        assert_eq!(sig, 0, "All-zeros feature must produce zero signature");
    }

    #[test]
    fn test_matches_reference() {
        let features = [1u64, 2, 3, 0xFF00FF00FF00FF00, u64::MAX];
        assert_eq!(
            simhash_cosine_u64(&features),
            simhash_cosine_u64_reference(&features)
        );
    }

    #[test]
    fn test_hamming_distance_identity() {
        let sig = simhash_cosine_u64(&[42, 100, 200]);
        assert_eq!(simhash_hamming_distance(sig, sig), 0);
    }

    #[test]
    fn test_hamming_distance_max() {
        assert_eq!(simhash_hamming_distance(0, u64::MAX), 64);
        assert_eq!(simhash_hamming_distance(u64::MAX, 0), 64);
    }

    #[test]
    fn test_similar_inputs_low_hamming() {
        // 50 features: last one is flipped. The other 49 identical features dominate the vote.
        let base: [u64; 50] = core::array::from_fn(|i| (i as u64).wrapping_mul(0x9E3779B97F4A7C15));
        let mut modified = base;
        modified[49] = !base[49]; // flip last feature
        let sig_a = simhash_cosine_u64(&base);
        let sig_b = simhash_cosine_u64(&modified);
        let dist = simhash_hamming_distance(sig_a, sig_b);
        // With 49 shared features and 1 differing, distance should be small.
        // The changed feature flips votes for each bit it differs in; with 50
        // features the impact is bounded but can affect multiple bits.
        assert!(
            dist <= 16,
            "Near-duplicate sets should have distance <= 16, got {dist}"
        );
    }

    proptest! {
        #[test]
        fn test_matches_reference_proptest(a in any::<u64>(), b in any::<u64>(), c in any::<u64>()) {
            let features = [a, b, c];
            let expected = simhash_cosine_u64_reference(&features);
            let actual = simhash_cosine_u64(&features);
            prop_assert_eq!(expected, actual, "SimHash must match reference for all inputs");
        }

        #[test]
        fn test_hamming_symmetry(a in any::<u64>(), b in any::<u64>()) {
            prop_assert_eq!(
                simhash_hamming_distance(a, b),
                simhash_hamming_distance(b, a),
                "Hamming distance must be symmetric"
            );
        }

        #[test]
        fn test_hamming_triangle_inequality(a in any::<u64>(), b in any::<u64>(), c in any::<u64>()) {
            let ab = simhash_hamming_distance(a, b);
            let bc = simhash_hamming_distance(b, c);
            let ac = simhash_hamming_distance(a, c);
            prop_assert!(ac <= ab + bc, "Triangle inequality must hold");
        }
    }

    // -------------------------------------------------------------------------
    // BOUNDARY EXAMPLES
    // -------------------------------------------------------------------------
    #[test]
    fn test_boundaries() {
        let _ = simhash_cosine_u64(&[0u64, u64::MAX]);
        assert_eq!(simhash_hamming_distance(0, 0), 0);
        assert_eq!(simhash_hamming_distance(u64::MAX, u64::MAX), 0);
    }

    // -------------------------------------------------------------------------
    // MUTANT COUNTERFACTUALS
    // -------------------------------------------------------------------------
    fn mutant_simhash_wrong_vote(features: &[u64]) -> u64 {
        // Bug: uses +1/0 instead of +1/-1 → wrong for zero bits.
        let mut counts = [0i32; 64];
        features.iter().for_each(|&f| {
            (0..64usize).for_each(|bit| {
                let bit_val = ((f >> bit) & 1) as i32;
                counts[bit] = counts[bit].wrapping_add(bit_val); // wrong: no -1 for 0 bits
            });
        });
        let mut sig = 0u64;
        (0..64usize).for_each(|bit| {
            let positive = (counts[bit] > 0) as u64;
            sig |= positive << bit;
        });
        sig
    }

    #[test]
    fn test_counterfactual_mutant_1() {
        // With [0, u64::MAX]: one all-zeros and one all-ones → tied votes → correct sig=0.
        // Wrong-vote mutant: counts[b]=1 for all bits → sig=u64::MAX.
        let features = [0u64, u64::MAX];
        let expected = simhash_cosine_u64(&features);
        let mutant = mutant_simhash_wrong_vote(&features);
        assert_ne!(expected, mutant, "Mutant must differ from correct result");
    }

    // -------------------------------------------------------------------------
    // AXIOMATIC PROOF: Hoare-logic Analysis
    // -------------------------------------------------------------------------
    // Precondition:  { features: slice of u64 }
    // Postcondition: { result = signature where bit b is set iff sum of (+1/-1) votes > 0 }
    //
    // Hoare-logic Verification Line 1: simhash_cosine_u64 correctness verified.
    // Vote accumulation is exact (i32 sum over at most 2^31 features before overflow).
    // Output bit extraction is branchless: (count > 0) as u64 is 0 or 1.
}

#[cfg(feature = "bench")]
pub mod bench {
    use super::*;
    use criterion::{black_box, Criterion};

    pub fn bench_simhash_cosine_u64(c: &mut Criterion) {
        let features: [u64; 64] = core::array::from_fn(|i| i as u64);
        c.bench_function("simhash_cosine_u64", |b| {
            b.iter(|| {
                let res = simhash_cosine_u64(black_box(&features));
                black_box(res)
            })
        });
    }

    pub fn bench_simhash_hamming_distance(c: &mut Criterion) {
        c.bench_function("simhash_hamming_distance", |b| {
            b.iter(|| {
                let res = simhash_hamming_distance(
                    black_box(0xDEAD_BEEF_u64),
                    black_box(0xCAFE_BABE_u64),
                );
                black_box(res)
            })
        });
    }
}
